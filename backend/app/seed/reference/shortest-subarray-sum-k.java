import java.util.*;

class Solution {
    public int shortestSubarray(int[] nums, int k) {
        int n = nums.length, best = Integer.MAX_VALUE;
        long[] P = new long[n + 1];
        for (int i = 0; i < n; i++) P[i + 1] = P[i] + nums[i];
        Deque<Integer> dq = new ArrayDeque<>();
        for (int j = 0; j <= n; j++) {
            while (!dq.isEmpty() && P[j] - P[dq.peekFirst()] >= k) best = Math.min(best, j - dq.pollFirst());
            while (!dq.isEmpty() && P[dq.peekLast()] >= P[j]) dq.pollLast();
            dq.addLast(j);
        }
        return best == Integer.MAX_VALUE ? -1 : best;
    }
}
