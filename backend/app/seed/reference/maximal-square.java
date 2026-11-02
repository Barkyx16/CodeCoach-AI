class Solution {
    public int maximalSquare(String[] matrix) {
        int m = matrix.length, n = matrix[0].length(), best = 0;
        int[][] side = new int[m + 1][n + 1];
        for (int r = 1; r <= m; r++)
            for (int c = 1; c <= n; c++)
                if (matrix[r - 1].charAt(c - 1) == '1') {
                    side[r][c] = 1 + Math.min(side[r - 1][c - 1], Math.min(side[r - 1][c], side[r][c - 1]));
                    best = Math.max(best, side[r][c]);
                }
        return best * best;
    }
}
