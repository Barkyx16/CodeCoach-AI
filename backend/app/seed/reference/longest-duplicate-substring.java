import java.util.*;

class Solution {
    private boolean hasRepeat(String s, int len) {
        if (len == 0) return true;
        long mod = 1_000_000_007L, base = 131, power = 1, h = 0;
        for (int i = 0; i < len; i++) power = power * base % mod;
        Map<Long, List<Integer>> seen = new HashMap<>();
        for (int i = 0; i < s.length(); i++) {
            h = (h * base + s.charAt(i)) % mod;
            if (i >= len) h = ((h - s.charAt(i - len) * power) % mod + mod) % mod;
            if (i >= len - 1) {
                int start = i - len + 1;
                List<Integer> starts = seen.computeIfAbsent(h, k -> new ArrayList<>());
                for (int other : starts) if (s.regionMatches(other, s, start, len)) return true;
                starts.add(start);
            }
        }
        return false;
    }
    public int longestDupSubstring(String s) {
        int lo = 0, hi = s.length() - 1;
        while (lo < hi) {
            int mid = (lo + hi + 1) / 2;
            if (hasRepeat(s, mid)) lo = mid; else hi = mid - 1;
        }
        return lo;
    }
}
