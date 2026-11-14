class Solution {
    public int uniquePaths(int m, int n) {
        int[] row = new int[n];
        java.util.Arrays.fill(row, 1);
        for (int r = 1; r < m; r++) for (int c = 1; c < n; c++) row[c] += row[c - 1];
        return row[n - 1];
    }
}
