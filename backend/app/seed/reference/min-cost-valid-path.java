import java.util.*;

class Solution {
    public int minCost(int[][] grid) {
        int m = grid.length, n = grid[0].length;
        int[][] dist = new int[m][n];
        for (int[] row : dist) Arrays.fill(row, Integer.MAX_VALUE);
        dist[0][0] = 0;
        int[][] dirs = {{0, 1}, {0, -1}, {1, 0}, {-1, 0}};
        Deque<int[]> dq = new ArrayDeque<>();
        dq.add(new int[] {0, 0});
        while (!dq.isEmpty()) {
            int[] p = dq.pollFirst();
            int r = p[0], c = p[1];
            for (int d = 0; d < 4; d++) {
                int x = r + dirs[d][0], y = c + dirs[d][1];
                if (x < 0 || x >= m || y < 0 || y >= n) continue;
                int w = grid[r][c] == d + 1 ? 0 : 1;
                if (dist[r][c] + w < dist[x][y]) {
                    dist[x][y] = dist[r][c] + w;
                    if (w == 0) dq.addFirst(new int[] {x, y}); else dq.addLast(new int[] {x, y});
                }
            }
        }
        return dist[m - 1][n - 1];
    }
}
