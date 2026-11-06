import java.util.*;

class Solution {
    public int minDeletions(String s) {
        int[] counts = new int[26];
        for (char c : s.toCharArray()) counts[c - 'a']++;
        Set<Integer> used = new HashSet<>();
        int deletions = 0;
        for (int c : counts) {
            while (c > 0 && used.contains(c)) { c--; deletions++; }
            used.add(c);
        }
        return deletions;
    }
}
