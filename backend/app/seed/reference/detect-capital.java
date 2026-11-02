class Solution {
    public boolean detectCapitalUse(String word) {
        int caps = 0;
        for (char c : word.toCharArray()) if (Character.isUpperCase(c)) caps++;
        return caps == 0 || caps == word.length() || (caps == 1 && Character.isUpperCase(word.charAt(0)));
    }
}
