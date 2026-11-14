class Solution {
    public boolean isValidSudoku(String[] board) {
        boolean[][] rows = new boolean[9][10], cols = new boolean[9][10], boxes = new boolean[9][10];
        for (int r = 0; r < 9; r++)
            for (int c = 0; c < 9; c++) {
                char ch = board[r].charAt(c);
                if (ch == '.') continue;
                int d = ch - '0', b = (r / 3) * 3 + c / 3;
                if (rows[r][d] || cols[c][d] || boxes[b][d]) return false;
                rows[r][d] = cols[c][d] = boxes[b][d] = true;
            }
        return true;
    }
}
