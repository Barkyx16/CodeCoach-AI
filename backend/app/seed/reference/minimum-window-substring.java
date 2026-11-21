class Solution {
    public String minWindow(String s, String t) {
        int[] need = new int[128];
        for (char c : t.toCharArray()) need[c]++;
        int missing = t.length(), left = 0, bestStart = 0, bestLen = Integer.MAX_VALUE;
        for (int right = 0; right < s.length(); right++) {
            if (need[s.charAt(right)]-- > 0) missing--;
            while (missing == 0) {
                if (right - left + 1 < bestLen) { bestLen = right - left + 1; bestStart = left; }
                if (++need[s.charAt(left++)] > 0) missing++;
            }
        }
        return bestLen == Integer.MAX_VALUE ? "" : s.substring(bestStart, bestStart + bestLen);
    }
}
