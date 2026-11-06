class Solution {
    private boolean[][] rows = new boolean[9][10], cols = new boolean[9][10], boxes = new boolean[9][10];
    private char[][] g = new char[9][];
    private boolean solve() {
        int bestR = -1, bestC = -1, bestCount = 10;
        for (int r = 0; r < 9; r++)
            for (int c = 0; c < 9; c++) {
                if (g[r][c] != '.') continue;
                int count = 0;
                for (int d = 1; d <= 9; d++) if (!rows[r][d] && !cols[c][d] && !boxes[(r / 3) * 3 + c / 3][d]) count++;
                if (count < bestCount) { bestCount = count; bestR = r; bestC = c; }
            }
        if (bestR == -1) return true;
        int b = (bestR / 3) * 3 + bestC / 3;
        for (int d = 1; d <= 9; d++) {
            if (rows[bestR][d] || cols[bestC][d] || boxes[b][d]) continue;
            g[bestR][bestC] = (char) ('0' + d);
            rows[bestR][d] = cols[bestC][d] = boxes[b][d] = true;
            if (solve()) return true;
            rows[bestR][d] = cols[bestC][d] = boxes[b][d] = false;
            g[bestR][bestC] = '.';
        }
        return false;
    }
    public String[] solveSudoku(String[] board) {
        for (int r = 0; r < 9; r++) {
            g[r] = board[r].toCharArray();
            for (int c = 0; c < 9; c++)
                if (g[r][c] != '.') { int d = g[r][c] - '0'; rows[r][d] = cols[c][d] = boxes[(r / 3) * 3 + c / 3][d] = true; }
        }
        solve();
        String[] out = new String[9];
        for (int r = 0; r < 9; r++) out[r] = new String(g[r]);
        return out;
    }
}
