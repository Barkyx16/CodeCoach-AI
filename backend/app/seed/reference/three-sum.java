import java.util.*;

class Solution {
    public int[][] threeSum(int[] nums) {
        Arrays.sort(nums);
        List<int[]> out = new ArrayList<>();
        int n = nums.length;
        for (int i = 0; i < n - 2; i++) {
            if (i > 0 && nums[i] == nums[i - 1]) continue;
            int lo = i + 1, hi = n - 1;
            while (lo < hi) {
                int s = nums[i] + nums[lo] + nums[hi];
                if (s == 0) {
                    out.add(new int[] {nums[i], nums[lo], nums[hi]});
                    while (lo < hi && nums[lo] == nums[lo + 1]) lo++;
                    while (lo < hi && nums[hi] == nums[hi - 1]) hi--;
                    lo++; hi--;
                } else if (s < 0) lo++; else hi--;
            }
        }
        return out.toArray(new int[0][]);
    }
}
