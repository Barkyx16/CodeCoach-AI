import java.util.*;

class Solution {
    public int minNumberOfSemesters(int n, int[][] relations, int k) {
        int[] pre = new int[n];
        for (int[] r : relations) pre[r[1] - 1] |= 1 << (r[0] - 1);
        int full = (1 << n) - 1;
        int[] dist = new int[1 << n];
        Arrays.fill(dist, -1);
        dist[0] = 0;
        Deque<Integer> queue = new ArrayDeque<>(List.of(0));
        while (!queue.isEmpty()) {
            int mask = queue.poll();
            if (mask == full) return dist[mask];
            int avail = 0;
            for (int c = 0; c < n; c++) if ((mask >> c & 1) == 0 && (pre[c] & mask) == pre[c]) avail |= 1 << c;
            for (int s = avail; s > 0; s = (s - 1) & avail) {
                if (Integer.bitCount(s) > k) continue;
                int next = mask | s;
                if (dist[next] == -1) { dist[next] = dist[mask] + 1; queue.add(next); }
            }
        }
        return -1;
    }
}
