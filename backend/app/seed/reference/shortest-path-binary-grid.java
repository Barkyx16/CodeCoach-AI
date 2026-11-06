import java.util.*;

class Solution {
    public int shortestPathBinaryMatrix(int[][] grid) {
        int n = grid.length;
        if (grid[0][0] == 1 || grid[n - 1][n - 1] == 1) return -1;
        boolean[][] seen = new boolean[n][n];
        Deque<int[]> queue = new ArrayDeque<>();
        queue.add(new int[] {0, 0, 1});
        seen[0][0] = true;
        while (!queue.isEmpty()) {
            int[] p = queue.poll();
            if (p[0] == n - 1 && p[1] == n - 1) return p[2];
            for (int a = -1; a <= 1; a++)
                for (int b = -1; b <= 1; b++) {
                    int r = p[0] + a, c = p[1] + b;
                    if (r >= 0 && r < n && c >= 0 && c < n && !seen[r][c] && grid[r][c] == 0) {
                        seen[r][c] = true;
                        queue.add(new int[] {r, c, p[2] + 1});
                    }
                }
        }
        return -1;
    }
}
