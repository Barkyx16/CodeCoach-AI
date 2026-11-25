import java.util.*;

class Solution {
    public int shortestPathLength(int[][] graph) {
        int n = graph.length, full = (1 << n) - 1;
        boolean[][] seen = new boolean[n][1 << n];
        Deque<int[]> queue = new ArrayDeque<>();
        for (int i = 0; i < n; i++) { queue.add(new int[] {i, 1 << i}); seen[i][1 << i] = true; }
        for (int steps = 0; ; steps++) {
            for (int k = queue.size(); k > 0; k--) {
                int[] s = queue.poll();
                if (s[1] == full) return steps;
                for (int v : graph[s[0]]) {
                    int mask = s[1] | (1 << v);
                    if (!seen[v][mask]) { seen[v][mask] = true; queue.add(new int[] {v, mask}); }
                }
            }
        }
    }
}
