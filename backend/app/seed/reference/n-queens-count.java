class Solution {
    private int place(int n, int row, int cols, int d1, int d2) {
        if (row == n) return 1;
        int total = 0;
        for (int c = 0; c < n; c++) {
            int a = 1 << c, b = 1 << (row - c + n), d = 1 << (row + c);
            if ((cols & a) == 0 && (d1 & b) == 0 && (d2 & d) == 0) total += place(n, row + 1, cols | a, d1 | b, d2 | d);
        }
        return total;
    }
    public int totalNQueens(int n) {
        return place(n, 0, 0, 0, 0);
    }
}
