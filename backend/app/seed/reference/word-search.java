class Solution {
    private boolean dfs(char[][] g, String word, int r, int c, int k) {
        if (k == word.length()) return true;
        if (r < 0 || c < 0 || r >= g.length || c >= g[0].length || g[r][c] != word.charAt(k)) return false;
        char saved = g[r][c];
        g[r][c] = '#';
        boolean found = dfs(g, word, r + 1, c, k + 1) || dfs(g, word, r - 1, c, k + 1)
            || dfs(g, word, r, c + 1, k + 1) || dfs(g, word, r, c - 1, k + 1);
        g[r][c] = saved;
        return found;
    }
    public boolean exist(String[] board, String word) {
        char[][] g = new char[board.length][];
        for (int i = 0; i < board.length; i++) g[i] = board[i].toCharArray();
        for (int i = 0; i < g.length; i++)
            for (int j = 0; j < g[0].length; j++) if (dfs(g, word, i, j, 0)) return true;
        return false;
    }
}
