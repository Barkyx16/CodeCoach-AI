import java.util.*;

class Solution {
    public boolean checkSubarraySum(int[] nums, int k) {
        Map<Integer, Integer> first = new HashMap<>();
        first.put(0, -1);
        long total = 0;
        for (int i = 0; i < nums.length; i++) {
            total = (total + nums[i]) % k;
            Integer seen = first.get((int) total);
            if (seen != null) { if (i - seen >= 2) return true; }
            else first.put((int) total, i);
        }
        return false;
    }
}
