import java.util.*;

class Solution {
    public String[] solve(String[] board) {
        int m = board.length, n = board[0].length();
        boolean[][] safe = new boolean[m][n];
        Deque<int[]> stack = new ArrayDeque<>();
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++)
                if ((i == 0 || j == 0 || i == m - 1 || j == n - 1) && board[i].charAt(j) == 'O') {
                    safe[i][j] = true;
                    stack.push(new int[] {i, j});
                }
        int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        while (!stack.isEmpty()) {
            int[] p = stack.pop();
            for (int[] d : dirs) {
                int r = p[0] + d[0], c = p[1] + d[1];
                if (r >= 0 && r < m && c >= 0 && c < n && !safe[r][c] && board[r].charAt(c) == 'O') {
                    safe[r][c] = true;
                    stack.push(new int[] {r, c});
                }
            }
        }
        String[] out = new String[m];
        for (int i = 0; i < m; i++) {
            StringBuilder sb = new StringBuilder();
            for (int j = 0; j < n; j++) sb.append(safe[i][j] ? 'O' : 'X');
            out[i] = sb.toString();
        }
        return out;
    }
}
