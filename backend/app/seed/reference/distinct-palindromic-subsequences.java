class Solution {
    private Integer[][] memo;
    private String s;
    private int count(int i, int j) {
        if (i > j) return 0;
        if (memo[i][j] != null) return memo[i][j];
        long total = 0;
        for (char x = 'a'; x <= 'd'; x++) {
            int lo = s.indexOf(x, i), hi = s.lastIndexOf(x, j);
            if (lo == -1 || lo > j) continue;
            total += lo == hi ? 1 : 2 + count(lo + 1, hi - 1);
        }
        return memo[i][j] = (int) (total % 1_000_000_007);
    }
    public int countPalindromicSubsequences(String s) {
        this.s = s;
        memo = new Integer[s.length()][s.length()];
        return count(0, s.length() - 1);
    }
}
