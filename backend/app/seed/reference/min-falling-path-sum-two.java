class Solution {
    public int minFallingPathSum(int[][] grid) {
        int n = grid.length;
        int[] prev = grid[0].clone();
        for (int i = 1; i < n; i++) {
            int m1 = Integer.MAX_VALUE, m2 = Integer.MAX_VALUE, col1 = -1;
            for (int j = 0; j < n; j++) {
                if (prev[j] < m1) { m2 = m1; m1 = prev[j]; col1 = j; }
                else if (prev[j] < m2) m2 = prev[j];
            }
            int[] cur = new int[n];
            for (int j = 0; j < n; j++) cur[j] = grid[i][j] + (j == col1 ? m2 : m1);
            prev = cur;
        }
        int best = Integer.MAX_VALUE;
        for (int v : prev) best = Math.min(best, v);
        return best;
    }
}
