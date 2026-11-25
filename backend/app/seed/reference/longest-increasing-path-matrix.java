class Solution {
    private int[][] memo;
    private int longest(int[][] g, int r, int c) {
        if (memo[r][c] != 0) return memo[r][c];
        int best = 1;
        int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        for (int[] d : dirs) {
            int x = r + d[0], y = c + d[1];
            if (x >= 0 && x < g.length && y >= 0 && y < g[0].length && g[x][y] > g[r][c]) best = Math.max(best, 1 + longest(g, x, y));
        }
        return memo[r][c] = best;
    }
    public int longestIncreasingPath(int[][] matrix) {
        memo = new int[matrix.length][matrix[0].length];
        int best = 0;
        for (int r = 0; r < matrix.length; r++) for (int c = 0; c < matrix[0].length; c++) best = Math.max(best, longest(matrix, r, c));
        return best;
    }
}
