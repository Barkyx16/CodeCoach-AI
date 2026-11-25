class Solution {
    public int titleToNumber(String title) {
        int result = 0;
        for (char c : title.toCharArray()) result = result * 26 + (c - 'A' + 1);
        return result;
    }
}
