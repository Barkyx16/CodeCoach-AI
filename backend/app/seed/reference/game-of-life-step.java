class Solution {
    public int[][] gameOfLife(int[][] board) {
        int m = board.length, n = board[0].length;
        int[][] next = new int[m][n];
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                int live = 0;
                for (int a = -1; a <= 1; a++)
                    for (int b = -1; b <= 1; b++)
                        if ((a != 0 || b != 0) && i + a >= 0 && i + a < m && j + b >= 0 && j + b < n) live += board[i + a][j + b];
                next[i][j] = live == 3 || (board[i][j] == 1 && live == 2) ? 1 : 0;
            }
        return next;
    }
}
