class Solution {
    public int minPathSum(int[][] grid) {
        int n = grid[0].length;
        int[] row = new int[n];
        java.util.Arrays.fill(row, Integer.MAX_VALUE);
        row[0] = 0;
        for (int[] cells : grid) {
            row[0] += cells[0];
            for (int c = 1; c < n; c++) row[c] = cells[c] + Math.min(row[c], row[c - 1]);
        }
        return row[n - 1];
    }
}
