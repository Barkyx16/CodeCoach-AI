import java.util.*;

class Solution {
    public int minimumEffortPath(int[][] heights) {
        int m = heights.length, n = heights[0].length;
        int[][] effort = new int[m][n];
        for (int[] row : effort) Arrays.fill(row, Integer.MAX_VALUE);
        effort[0][0] = 0;
        PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> Integer.compare(a[0], b[0]));
        pq.add(new int[] {0, 0, 0});
        int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        while (!pq.isEmpty()) {
            int[] top = pq.poll();
            int e = top[0], r = top[1], c = top[2];
            if (r == m - 1 && c == n - 1) return e;
            if (e > effort[r][c]) continue;
            for (int[] d : dirs) {
                int x = r + d[0], y = c + d[1];
                if (x < 0 || x >= m || y < 0 || y >= n) continue;
                int ne = Math.max(e, Math.abs(heights[x][y] - heights[r][c]));
                if (ne < effort[x][y]) { effort[x][y] = ne; pq.add(new int[] {ne, x, y}); }
            }
        }
        return 0;
    }
}
