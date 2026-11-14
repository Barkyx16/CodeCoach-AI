import java.util.*;

class Solution {
    public int longestConsecutive(int[] nums) {
        Set<Integer> s = new HashSet<>();
        for (int x : nums) s.add(x);
        int best = 0;
        for (int x : s) {
            if (s.contains(x - 1)) continue;
            int length = 1;
            while (s.contains(x + length)) length++;
            best = Math.max(best, length);
        }
        return best;
    }
}
