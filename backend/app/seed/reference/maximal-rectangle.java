import java.util.*;

class Solution {
    public int maximalRectangle(String[] matrix) {
        int n = matrix[0].length(), best = 0;
        int[] heights = new int[n];
        for (String row : matrix) {
            for (int j = 0; j < n; j++) heights[j] = row.charAt(j) == '1' ? heights[j] + 1 : 0;
            Deque<Integer> stack = new ArrayDeque<>();
            for (int i = 0; i <= n; i++) {
                int h = i == n ? 0 : heights[i];
                while (!stack.isEmpty() && heights[stack.peek()] > h) {
                    int top = stack.pop();
                    int left = stack.isEmpty() ? 0 : stack.peek() + 1;
                    best = Math.max(best, heights[top] * (i - left));
                }
                stack.push(i);
            }
        }
        return best;
    }
}
