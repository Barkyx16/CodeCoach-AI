class Solution {
    public int longestPalindrome(String s) {
        int[] counts = new int[128];
        for (char c : s.toCharArray()) counts[c]++;
        int length = 0;
        boolean odd = false;
        for (int c : counts) { length += c / 2 * 2; if (c % 2 == 1) odd = true; }
        return odd ? length + 1 : length;
    }
}
