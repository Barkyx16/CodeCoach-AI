class Solution {
    public int[][] transpose(int[][] matrix) {
        int rows = matrix.length, cols = matrix[0].length;
        int[][] out = new int[cols][rows];
        for (int i = 0; i < rows; i++) for (int j = 0; j < cols; j++) out[j][i] = matrix[i][j];
        return out;
    }
}
