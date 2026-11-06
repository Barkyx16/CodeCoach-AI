class Solution {
    public boolean repeatedSubstringPattern(String s) {
        int n = s.length();
        for (int k = 1; k <= n / 2; k++) {
            if (n % k != 0) continue;
            boolean ok = true;
            for (int i = k; i < n && ok; i++) if (s.charAt(i) != s.charAt(i - k)) ok = false;
            if (ok) return true;
        }
        return false;
    }
}
