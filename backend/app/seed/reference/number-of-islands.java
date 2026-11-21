import java.util.*;

class Solution {
    public int numIslands(String[] grid) {
        int m = grid.length, n = grid[0].length(), count = 0;
        boolean[][] seen = new boolean[m][n];
        int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        for (int i = 0; i < m; i++)
            for (int j = 0; j < n; j++) {
                if (grid[i].charAt(j) != '1' || seen[i][j]) continue;
                count++;
                Deque<int[]> stack = new ArrayDeque<>();
                stack.push(new int[] {i, j});
                seen[i][j] = true;
                while (!stack.isEmpty()) {
                    int[] p = stack.pop();
                    for (int[] d : dirs) {
                        int r = p[0] + d[0], c = p[1] + d[1];
                        if (r >= 0 && r < m && c >= 0 && c < n && !seen[r][c] && grid[r].charAt(c) == '1') {
                            seen[r][c] = true;
                            stack.push(new int[] {r, c});
                        }
                    }
                }
            }
        return count;
    }
}
