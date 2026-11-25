class Solution {
    public String minWindowSubsequence(String s1, String s2) {
        int n = s1.length(), m = s2.length(), bestStart = -1, bestLen = Integer.MAX_VALUE, i = 0;
        while (i < n) {
            int k = 0, e = i;
            while (e < n) { if (s1.charAt(e) == s2.charAt(k) && ++k == m) break; e++; }
            if (e == n) break;
            int b = e;
            k = m - 1;
            while (k >= 0) { if (s1.charAt(b) == s2.charAt(k)) k--; b--; }
            b++;
            if (e - b + 1 < bestLen) { bestLen = e - b + 1; bestStart = b; }
            i = b + 1;
        }
        return bestStart == -1 ? "" : s1.substring(bestStart, bestStart + bestLen);
    }
}
