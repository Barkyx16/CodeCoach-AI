class Solution {
    public int diagonalSum(int[][] mat) {
        int n = mat.length, total = 0;
        for (int i = 0; i < n; i++) {
            total += mat[i][i];
            if (i != n - 1 - i) total += mat[i][n - 1 - i];
        }
        return total;
    }
}
