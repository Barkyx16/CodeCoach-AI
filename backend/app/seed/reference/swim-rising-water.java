import java.util.*;

class Solution {
    public int swimInWater(int[][] grid) {
        int n = grid.length;
        boolean[][] seen = new boolean[n][n];
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> Integer.compare(a[0], b[0]));
        pq.add(new int[] {grid[0][0], 0, 0});
        seen[0][0] = true;
        int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        while (true) {
            int[] top = pq.poll();
            if (top[1] == n - 1 && top[2] == n - 1) return top[0];
            for (int[] d : dirs) {
                int r = top[1] + d[0], c = top[2] + d[1];
                if (r >= 0 && r < n && c >= 0 && c < n && !seen[r][c]) {
                    seen[r][c] = true;
                    pq.add(new int[] {Math.max(top[0], grid[r][c]), r, c});
                }
            }
        }
    }
}
