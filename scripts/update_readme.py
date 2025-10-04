#!/usr/bin/env python3
from pathlib import Path
import xml.etree.ElementTree as ET
from datetime import datetime
import re
import sys

# Where to inject table rows inside README.md
MARKER_START = "<!-- ideas:start -->"
MARKER_END = "<!-- ideas:end -->"
README_PATH = Path("README.md")

# Map choice values -> friendly labels
FOCUS_MAP = {
    "cure": "Cause and Cure",
    "disaster": "Disaster and Community Support",
    "education": "Education and Youth Services",
    "sustainability": "Sustainability and Decarbonization",
    "other": "Other",
}

# Glob pattern that catches your update set XMLs regardless of scope folder
GLOB_PATTERN = "**/update/x_snc_hack4good_0_hack4good_proposal_*.xml"

def friendly_focus(value: str) -> str:
    if not value:
        return "—"
    return FOCUS_MAP.get(value.strip().lower(), value.replace("_", " ").title())

def parse_xml(file: Path):
    """
    Return dict with project_name, focus_area, sys_created_on (datetime), path.
    """
    try:
        root = ET.parse(file).getroot()
        # The record tag matches the table name
        rec = root.find(".//x_snc_hack4good_0_hack4good_proposal")
        if rec is None:
            return None

        def text(tag):
            el = rec.find(tag)
            return (el.text or "").strip() if el is not None else ""

        project_name = text("project_name")
        focus_area = friendly_focus(text("focus_area"))
        created_raw = text("sys_created_on")

        # Parse "YYYY-MM-DD HH:MM:SS" -> datetime
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

def build_table(items):
    if not items:
        return "\n_No ideas yet. Be the first to submit one!_\n"

    header = "| Date (UTC) | Focus area | Project |\n|---|---|---|\n"
    rows = []
    for it in items:
        date_disp = it["created_dt"].strftime("%Y-%m-%d") if it["created_dt"] else "—"
        # Link the project name to the file path in the repo
        link = f"[{it['project_name']}]({it['path']})"
        rows.append(f"| {date_disp} | {it['focus_area']} | {link} |")
    return "\n" + header + "\n".join(rows) + "\n"

def replace_between_markers(readme_text: str, new_block: str) -> str:
    if MARKER_START not in readme_text or MARKER_END not in readme_text:
        # If markers are missing, append the block at the end
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
    files = sorted(Path(".").glob(GLOB_PATTERN))
    items = []
    for f in files:
        rec = parse_xml(f)
        if rec:
            items.append(rec)

    # Sort newest first (fallback: entries without date go last)
    items.sort(key=lambda x: x["created_dt"] or datetime.min, reverse=True)
    table_md = build_table(items)

    readme = README_PATH.read_text(encoding="utf-8") if README_PATH.exists() else "# Hack4Good\n\n"
    updated = replace_between_markers(readme, table_md)

    if updated != readme:
        README_PATH.write_text(updated, encoding="utf-8")
        print("README.md updated.")
    else:
        print("README.md unchanged.")

if __name__ == "__main__":
    main()
