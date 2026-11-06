import java.util.*;

class Solution {
    public int shortestPathWithK(int[][] grid, int k) {
        int m = grid.length, n = grid[0].length;
        boolean[][][] seen = new boolean[m][n][k + 1];
        Deque<int[]> queue = new ArrayDeque<>();
        queue.add(new int[] {0, 0, k});
        seen[0][0][k] = true;
        int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        for (int steps = 0; !queue.isEmpty(); steps++) {
            for (int c = queue.size(); c > 0; c--) {
                int[] s = queue.poll();
                if (s[0] == m - 1 && s[1] == n - 1) return steps;
                for (int[] d : dirs) {
                    int x = s[0] + d[0], y = s[1] + d[1];
                    if (x < 0 || x >= m || y < 0 || y >= n) continue;
                    int left = s[2] - grid[x][y];
                    if (left >= 0 && !seen[x][y][left]) { seen[x][y][left] = true; queue.add(new int[] {x, y, left}); }
                }
            }
        }
        return -1;
    }
}
