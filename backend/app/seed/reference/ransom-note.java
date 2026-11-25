class Solution {
    public boolean canConstruct(String note, String magazine) {
        int[] counts = new int[26];
        for (char c : magazine.toCharArray()) counts[c - 'a']++;
        for (char c : note.toCharArray()) if (--counts[c - 'a'] < 0) return false;
        return true;
    }
}
