class Solution {
    public int minCut(String s) {
        int n = s.length();
        boolean[][] pal = new boolean[n][n];
        int[] cuts = new int[n];
        for (int i = 0; i < n; i++) {
            cuts[i] = i;
            for (int j = 0; j <= i; j++)
                if (s.charAt(j) == s.charAt(i) && (i - j < 2 || pal[j + 1][i - 1])) {
                    pal[j][i] = true;
                    cuts[i] = Math.min(cuts[i], j == 0 ? 0 : cuts[j - 1] + 1);
                }
        }
        return cuts[n - 1];
    }
}
