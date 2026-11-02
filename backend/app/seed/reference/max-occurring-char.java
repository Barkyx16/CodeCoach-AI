class Solution {
    public String mostFrequent(String s) {
        int[] counts = new int[26];
        for (char c : s.toCharArray()) counts[c - 'a']++;
        int best = 0;
        for (int i = 1; i < 26; i++) if (counts[i] > counts[best]) best = i;
        return String.valueOf((char) ('a' + best));
    }
}
