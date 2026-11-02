class Solution {
    public boolean isInterleave(String s1, String s2, String s3) {
        int n = s1.length(), m = s2.length();
        if (n + m != s3.length()) return false;
        boolean[] ok = new boolean[m + 1];
        for (int i = 0; i <= n; i++)
            for (int j = 0; j <= m; j++) {
                if (i == 0 && j == 0) { ok[0] = true; continue; }
                boolean fromTop = i > 0 && ok[j] && s1.charAt(i - 1) == s3.charAt(i + j - 1);
                boolean fromLeft = j > 0 && ok[j - 1] && s2.charAt(j - 1) == s3.charAt(i + j - 1);
                ok[j] = fromTop || fromLeft;
            }
        return ok[m];
    }
}
