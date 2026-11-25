import java.util.*;

class Solution {
    public int maxChunksToSorted(int[] arr) {
        Deque<Integer> stack = new ArrayDeque<>();
        for (int x : arr) {
            int biggest = x;
            while (!stack.isEmpty() && stack.peek() > x) biggest = Math.max(biggest, stack.pop());
            stack.push(biggest);
        }
        return stack.size();
    }
}
