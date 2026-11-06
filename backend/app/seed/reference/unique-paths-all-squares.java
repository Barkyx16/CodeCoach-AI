class Solution {
    private int dfs(int[][] g, int r, int c, int left) {
        if (r < 0 || c < 0 || r >= g.length || c >= g[0].length || g[r][c] == -1) return 0;
        if (g[r][c] == 2) return left == 1 ? 1 : 0;
        int saved = g[r][c];
        g[r][c] = -1;
        int total = dfs(g, r + 1, c, left - 1) + dfs(g, r - 1, c, left - 1) + dfs(g, r, c + 1, left - 1) + dfs(g, r, c - 1, left - 1);
        g[r][c] = saved;
        return total;
    }
    public int uniquePathsIII(int[][] grid) {
        int remaining = 0, sr = 0, sc = 0;
        for (int i = 0; i < grid.length; i++)
            for (int j = 0; j < grid[0].length; j++) {
                if (grid[i][j] != -1) remaining++;
                if (grid[i][j] == 1) { sr = i; sc = j; }
            }
        return dfs(grid, sr, sc, remaining);
    }
}
