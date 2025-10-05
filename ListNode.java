
class Solution {
    public ListNode reverseKGroup(ListNode head, int k) {
        if(head == null && k==1){
            return head;
        }
        ListNode curr = head;
        ListNode newHead = null;
        ListNode tail = null;
        //outerLoop
        while(curr!=null){
            // Check if there are at least k nodes remaining
            ListNode temp = curr;
            int count = 0;
            while (temp != null && count < k) {
                temp = temp.next;
                count++;
            }

            if (count < k) {
                // Not enough nodes to reverse, link the rest as is it
                if (tail != null) {
                    tail.next = curr;
                }
                break;
            }

            ListNode grpHead = curr;
            ListNode nextNode = null;
            ListNode prev = null;
            count =0;
            //innerLoop
 // Reverse the nodes in the current group
            while(curr!=null && count<k){
                nextNode = curr.next;
                curr.next = prev;

                prev = curr;
                curr = nextNode;
                count++;
            }

            // If newHead is null, set it to the
            // last node of the first group
            if(newHead == null) newHead = prev;

            // Connect the previous group to the 
            // current reversed group
            if(tail != null) tail.next = prev;

            // Move tail to the end of the
          	// reversed group
            tail = grpHead;
        }
        return newHead;
    }
}
