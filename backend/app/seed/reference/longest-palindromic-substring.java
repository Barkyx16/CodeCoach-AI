class Solution {
    public String longestPalindrome(String s) {
        int n = s.length(), bestStart = 0, bestLen = 1;
        for (int center = 0; center < 2 * n - 1; center++) {
            int l = center / 2, r = l + center % 2;
            while (l >= 0 && r < n && s.charAt(l) == s.charAt(r)) { l--; r++; }
            int len = r - l - 1, start = l + 1;
            if (len > bestLen || (len == bestLen && start < bestStart)) { bestLen = len; bestStart = start; }
        }
        return s.substring(bestStart, bestStart + bestLen);
    }
}
