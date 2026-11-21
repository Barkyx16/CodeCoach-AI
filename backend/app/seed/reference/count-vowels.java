class Solution {
    public int countVowels(String s) {
        int count = 0;
        for (char c : s.toLowerCase().toCharArray()) if ("aeiou".indexOf(c) >= 0) count++;
        return count;
    }
}
