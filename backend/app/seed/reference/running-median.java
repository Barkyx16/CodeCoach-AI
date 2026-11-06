import java.util.*;

class Solution {
    public int[] runningMedian(int[] nums) {
        PriorityQueue<Integer> low = new PriorityQueue<>(Collections.reverseOrder()), high = new PriorityQueue<>();
        int[] out = new int[nums.length];
        for (int i = 0; i < nums.length; i++) {
            low.add(nums[i]);
            high.add(low.poll());
            if (high.size() > low.size()) low.add(high.poll());
            out[i] = low.peek();
        }
        return out;
    }
}
