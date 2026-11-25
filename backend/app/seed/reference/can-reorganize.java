class Solution {
    public boolean canReorganize(String s) {
        int[] counts = new int[26];
        int top = 0;
        for (char c : s.toCharArray()) top = Math.max(top, ++counts[c - 'a']);
        return top <= (s.length() + 1) / 2;
    }
}
