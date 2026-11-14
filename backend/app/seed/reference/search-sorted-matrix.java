class Solution {
    public boolean searchMatrix(int[][] matrix, int target) {
        int rows = matrix.length, cols = matrix[0].length, lo = 0, hi = rows * cols - 1;
        while (lo <= hi) {
            int mid = (lo + hi) >>> 1, v = matrix[mid / cols][mid % cols];
            if (v == target) return true;
            if (v < target) lo = mid + 1; else hi = mid - 1;
        }
        return false;
    }
}
