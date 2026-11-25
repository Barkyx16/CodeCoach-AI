import java.util.*;

class Solution {
    public int numberOfArithmeticSlices(int[] nums) {
        int n = nums.length;
        List<Map<Long, Integer>> dp = new ArrayList<>();
        long answer = 0;
        for (int i = 0; i < n; i++) {
            dp.add(new HashMap<>());
            for (int j = 0; j < i; j++) {
                long d = (long) nums[i] - nums[j];
                int count = dp.get(j).getOrDefault(d, 0);
                answer += count;
                dp.get(i).merge(d, count + 1, Integer::sum);
            }
        }
        return (int) answer;
    }
}
