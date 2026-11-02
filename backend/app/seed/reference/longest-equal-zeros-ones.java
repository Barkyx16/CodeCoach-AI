import java.util.*;

class Solution {
    public int findMaxLength(int[] nums) {
        Map<Integer, Integer> first = new HashMap<>();
        first.put(0, -1);
        int total = 0, best = 0;
        for (int i = 0; i < nums.length; i++) {
            total += nums[i] == 1 ? 1 : -1;
            Integer seen = first.putIfAbsent(total, i);
            if (seen != null) best = Math.max(best, i - seen);
        }
        return best;
    }
}
