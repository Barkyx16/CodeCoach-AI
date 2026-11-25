class Solution {
    public int numDistinct(String s, String t) {
        int m = t.length();
        long[] ways = new long[m + 1];
        ways[0] = 1;
        for (char c : s.toCharArray())
            for (int j = m; j >= 1; j--) if (t.charAt(j - 1) == c) ways[j] += ways[j - 1];
        return (int) ways[m];
    }
}
