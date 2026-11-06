import java.util.*;

class Solution {
    public int minJumps(int[] nums) {
        int n = nums.length;
        Map<Integer, List<Integer>> groups = new HashMap<>();
        for (int i = 0; i < n; i++) groups.computeIfAbsent(nums[i], k -> new ArrayList<>()).add(i);
        int[] dist = new int[n];
        Arrays.fill(dist, -1);
        dist[0] = 0;
        Deque<Integer> queue = new ArrayDeque<>(List.of(0));
        while (!queue.isEmpty()) {
            int i = queue.poll();
            if (i == n - 1) return dist[i];
            List<Integer> next = new ArrayList<>(groups.getOrDefault(nums[i], List.of()));
            next.add(i - 1);
            next.add(i + 1);
            groups.remove(nums[i]);
            for (int j : next)
                if (j >= 0 && j < n && dist[j] == -1) { dist[j] = dist[i] + 1; queue.add(j); }
        }
        return -1;
    }
}
