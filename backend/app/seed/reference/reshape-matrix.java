class Solution {
    public int[][] matrixReshape(int[][] mat, int r, int c) {
        int rows = mat.length, cols = mat[0].length;
        if (rows * cols != r * c) return mat;
        int[][] out = new int[r][c];
        for (int k = 0; k < r * c; k++) out[k / c][k % c] = mat[k / cols][k % cols];
        return out;
    }
}
