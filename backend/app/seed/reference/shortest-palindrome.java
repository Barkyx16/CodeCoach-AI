class Solution {
    public String shortestPalindrome(String s) {
        String rev = new StringBuilder(s).reverse().toString();
        String t = s + "#" + rev;
        int[] fail = new int[t.length()];
        for (int i = 1; i < t.length(); i++) {
            int k = fail[i - 1];
            while (k > 0 && t.charAt(i) != t.charAt(k)) k = fail[k - 1];
            if (t.charAt(i) == t.charAt(k)) k++;
            fail[i] = k;
        }
        int keep = fail[t.length() - 1];
        return rev.substring(0, s.length() - keep) + s;
    }
}
