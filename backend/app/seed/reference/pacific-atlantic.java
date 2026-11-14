import java.util.*;

class Solution {
    private void climb(int[][] h, boolean[][] seen, Deque<int[]> stack) {
        int m = h.length, n = h[0].length;
        int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        while (!stack.isEmpty()) {
            int[] p = stack.pop();
            for (int[] d : dirs) {
                int r = p[0] + d[0], c = p[1] + d[1];
                if (r >= 0 && r < m && c >= 0 && c < n && !seen[r][c] && h[r][c] >= h[p[0]][p[1]]) {
                    seen[r][c] = true;
                    stack.push(new int[] {r, c});
                }
            }
        }
    }
    public int[][] pacificAtlantic(int[][] heights) {
        int m = heights.length, n = heights[0].length;
        boolean[][] pac = new boolean[m][n], atl = new boolean[m][n];
        Deque<int[]> ps = new ArrayDeque<>(), as = new ArrayDeque<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                if (i == 0 || j == 0) { pac[i][j] = true; ps.push(new int[] {i, j}); }
                if (i == m - 1 || j == n - 1) { atl[i][j] = true; as.push(new int[] {i, j}); }
            }
        climb(heights, pac, ps);
        climb(heights, atl, as);
        List<int[]> out = new ArrayList<>();
        for (int i = 0; i < m; i++) for (int j = 0; j < n; j++) if (pac[i][j] && atl[i][j]) out.add(new int[] {i, j});
        return out.toArray(new int[0][]);
    }
}
