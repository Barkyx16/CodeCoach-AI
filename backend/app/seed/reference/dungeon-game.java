import java.util.*;

class Solution {
    public int calculateMinimumHP(int[][] dungeon) {
        int m = dungeon.length, n = dungeon[0].length;
        int[][] need = new int[m + 1][n + 1];
        for (int[] row : need) Arrays.fill(row, Integer.MAX_VALUE);
        need[m][n - 1] = need[m - 1][n] = 1;
        for (int r = m - 1; r >= 0; r--)
            for (int c = n - 1; c >= 0; c--)
                need[r][c] = Math.max(1, Math.min(need[r + 1][c], need[r][c + 1]) - dungeon[r][c]);
        return need[0][0];
    }
}
