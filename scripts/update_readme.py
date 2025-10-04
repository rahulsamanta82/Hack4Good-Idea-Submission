#!/usr/bin/env python3
from pathlib import Path
import xml.etree.ElementTree as ET
from datetime import datetime
import re
import sys
import os
import json
import subprocess
import urllib.request
import urllib.error

MARKER_START = "<!-- ideas:start -->"
MARKER_END = "<!-- ideas:end -->"
README_PATH = Path("README.md")
ATTR_CACHE_PATH = Path(".idea_attribution.json")

# Focus area mapping
FOCUS_MAP = {
    "cure": "🧪 Cause and Cure",
    "disaster": "🆘 Disaster and Community Support",
    "education": "🎓 Education and Youth Services",
    "sustainability": "🌱 Sustainability and Decarbonization",
    "other": "🧩 Other",
}

GLOB_PATTERN = "**/update/x_snc_hack4good_0_hack4good_proposal_*.xml"

def friendly_focus(value: str) -> str:
    if not value:
        return "—"
    return FOCUS_MAP.get(value.strip().lower(), value.replace("_", " ").title())

def parse_xml(file: Path):
    try:
        root = ET.parse(file).getroot()
        rec = root.find(".//x_snc_hack4good_0_hack4good_proposal")
        if rec is None:
            return None
        def text(tag):
            el = rec.find(tag)
            return (el.text or "").strip() if el is not None else ""
        project_name = text("project_name")
        focus_area = friendly_focus(text("focus_area"))
        created_raw = text("sys_created_on")
        created_dt = None
        if created_raw:
            created_dt = datetime.strptime(created_raw, "%Y-%m-%d %H:%M:%S")
        if not project_name:
            return None
        return {
            "project_name": project_name,
            "focus_area": focus_area,
            "created_dt": created_dt,
            "created_raw": created_raw,
            "path": str(file),
        }
    except Exception as e:
        print(f"WARNING: Failed to parse {file}: {e}", file=sys.stderr)
        return None

def git_first_commit_for_path(path: str) -> str | None:
    try:
        sha = subprocess.check_output(
            ["git", "log", "--diff-filter=A", "--format=%H", "--", path],
            text=True
        ).strip().splitlines()
        return sha[0] if sha else None
    except subprocess.CalledProcessError:
        return None

def gh_api(url: str):
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    headers = {
        "User-Agent": "hack4good-readme-bot",
        "Accept": "application/vnd.github+json",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        print(f"GitHub API error {e.code} for {url}", file=sys.stderr)
    except Exception as e:
        print(f"GitHub API exception for {url}: {e}", file=sys.stderr)
    return None

def pr_author_for_commit(owner: str, repo: str, commit_sha: str):
    """
    Use: GET /repos/{owner}/{repo}/commits/{commit_sha}/pulls
    Fallback: GET /repos/{owner}/{repo}/commits/{sha} to get commit author.
    """
    if not commit_sha:
        return None
    pulls = gh_api(f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}/pulls")
    if isinstance(pulls, list) and pulls:
        # pick the earliest merged PR or the first
        pulls_sorted = sorted(
            pulls, key=lambda p: (p.get("merged_at") or p.get("created_at") or ""), reverse=False
        )
        pr = pulls_sorted[0]
        user = pr.get("user") or {}
        return {
            "login": user.get("login"),
            "avatar_url": (user.get("avatar_url") or "") + "&s=40",
            "html_url": user.get("html_url"),
        }
    # Fallback to commit author info
    commit = gh_api(f"https://api.github.com/repos/{owner}/{repo}/commits/{commit_sha}")
    if isinstance(commit, dict):
        # Prefer linked GitHub user if present
        if commit.get("author"):
            user = commit["author"]
            return {
                "login": user.get("login"),
                "avatar_url": (user.get("avatar_url") or "") + "&s=40",
                "html_url": user.get("html_url"),
            }
        # Otherwise use the raw commit author (name/email), without avatar
        raw = commit.get("commit", {}).get("author", {}) or {}
        login = raw.get("name") or raw.get("email") or "Unknown"
        return {"login": login, "avatar_url": "", "html_url": ""}
    return None

def load_cache():
    if ATTR_CACHE_PATH.exists():
        try:
            return json.loads(ATTR_CACHE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def save_cache(cache):
    ATTR_CACHE_PATH.write_text(json.dumps(cache, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def resolve_attribution(xml_path: str, cache: dict, owner: str, repo: str):
    if xml_path in cache and cache[xml_path].get("login"):
        return cache[xml_path]
    first_sha = git_first_commit_for_path(xml_path)
    info = pr_author_for_commit(owner, repo, first_sha) if first_sha else None
    cache[xml_path] = info or {"login": "Unknown", "avatar_url": "", "html_url": ""}
    return cache[xml_path]

def render_submitter(cell):
    login = cell.get("login") or "unknown"
    url = cell.get("html_url") or ""
    avatar = cell.get("avatar_url") or ""
    if url:
        img = f'<img src="{avatar}" width="20" height="20" style="border-radius:50%; vertical-align:middle;" alt="@{login}"/>'
        return f'<a href="{url}">{img} @{login}</a>'
    return f"@{login}"

def build_table(items, owner: str, repo: str):
    if not items:
        return "\n_No ideas yet. Be the first to submit one!_\n"

    # Column order: Project | Focus area | Avatar | Created
    header = "| Project | Focus area | Submitted by | Created (UTC) |\n|---|---|---|---|\n"
    rows = []
    cache = load_cache()
    try:
        for it in items:
            project = f"[{it['project_name']}]({it['path']})"
            focus = it['focus_area']
            submitter = resolve_attribution(it["path"], cache, owner, repo)
            submitter_cell = render_submitter(submitter)
            created = it["created_dt"].strftime("%Y-%m-%d") if it["created_dt"] else "—"
            rows.append(f"| {project} | {focus} | {submitter_cell} | {created} |")
    finally:
        save_cache(cache)

    return "\n" + header + "\n".join(rows) + "\n"

def replace_between_markers(readme_text: str, new_block: str) -> str:
    if MARKER_START not in readme_text or MARKER_END not in readme_text:
        return (
            readme_text.rstrip()
            + f"\n\n{MARKER_START}\n\n_Updated automatically on merge to `main`._\n\n"
            + new_block
            + f"\n{MARKER_END}\n"
        )
    pattern = re.compile(
        rf"({re.escape(MARKER_START)})(.*)({re.escape(MARKER_END)})",
        flags=re.DOTALL,
    )
    replacement = rf"\1\n\n_Updated automatically on merge to `main`._\n{new_block}\3"
    return pattern.sub(replacement, readme_text)

def main():
    repo_full = os.environ.get("GITHUB_REPOSITORY", "")
    owner, repo = (repo_full.split("/", 1) + [""])[:2]

    files = sorted(Path(".").glob(GLOB_PATTERN))
    items = []
    for f in files:
        rec = parse_xml(f)
        if rec:
            items.append(rec)

    items.sort(key=lambda x: x["created_dt"] or datetime.min, reverse=True)
    table_md = build_table(items, owner, repo)

    readme = README_PATH.read_text(encoding="utf-8") if README_PATH.exists() else "# Hack4Good\n\n"
    updated = replace_between_markers(readme, table_md)

    if updated != readme:
        README_PATH.write_text(updated, encoding="utf-8")
        print("README.md updated.")
    else:
        print("README.md unchanged.")

if __name__ == "__main__":
    main()
