class Solution {
    public String findTheDifference(String s, String t) {
        int x = 0;
        for (char c : s.toCharArray()) x ^= c;
        for (char c : t.toCharArray()) x ^= c;
        return String.valueOf((char) x);
    }
}
