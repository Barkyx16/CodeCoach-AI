class Solution {
    public int uniquePathsWithObstacles(int[][] grid) {
        int n = grid[0].length;
        int[] row = new int[n];
        row[0] = grid[0][0] == 0 ? 1 : 0;
        for (int[] cells : grid)
            for (int c = 0; c < n; c++) {
                if (cells[c] == 1) row[c] = 0;
                else if (c > 0) row[c] += row[c - 1];
            }
        return row[n - 1];
    }
}
