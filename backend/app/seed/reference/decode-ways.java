class Solution {
    public int numDecodings(String s) {
        int prev2 = 1;
        int prev1 = s.charAt(0) != '0' ? 1 : 0;
        for (int i = 2; i <= s.length(); i++) {
            int current = 0;
            if (s.charAt(i - 1) != '0') {
                current += prev1;
            }
            int two = (s.charAt(i - 2) - '0') * 10 + (s.charAt(i - 1) - '0');
            if (two >= 10 && two <= 26) {
                current += prev2;
            }
            prev2 = prev1;
            prev1 = current;
        }
        return prev1;
    }
}
