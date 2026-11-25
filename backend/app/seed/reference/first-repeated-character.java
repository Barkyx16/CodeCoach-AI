class Solution {
    public String firstRepeated(String s) {
        boolean[] seen = new boolean[26];
        for (char c : s.toCharArray()) {
            if (seen[c - 'a']) return String.valueOf(c);
            seen[c - 'a'] = true;
        }
        return "";
    }
}
