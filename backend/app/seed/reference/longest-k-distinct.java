class Solution {
    public int lengthOfLongestKDistinct(String s, int k) {
        int[] counts = new int[26];
        int left = 0, distinct = 0, best = 0;
        for (int right = 0; right < s.length(); right++) {
            if (counts[s.charAt(right) - 'a']++ == 0) distinct++;
            while (distinct > k) if (--counts[s.charAt(left++) - 'a'] == 0) distinct--;
            best = Math.max(best, right - left + 1);
        }
        return best;
    }
}
