import java.util.*;

class Solution {
    private TreeMap<Integer, Integer> low = new TreeMap<>(), high = new TreeMap<>();
    private int lowSize = 0, highSize = 0;
    private void add(TreeMap<Integer, Integer> m, int x) { m.merge(x, 1, Integer::sum); }
    private void remove(TreeMap<Integer, Integer> m, int x) { if (m.merge(x, -1, Integer::sum) == 0) m.remove(x); }
    private void rebalance() {
        while (lowSize > highSize + 1) { int x = low.lastKey(); remove(low, x); lowSize--; add(high, x); highSize++; }
        while (highSize > lowSize) { int x = high.firstKey(); remove(high, x); highSize--; add(low, x); lowSize++; }
    }
    public int[] medianSlidingWindow(int[] nums, int k) {
        int[] out = new int[nums.length - k + 1];
        for (int i = 0; i < nums.length; i++) {
            if (lowSize == 0 || nums[i] <= low.lastKey()) { add(low, nums[i]); lowSize++; } else { add(high, nums[i]); highSize++; }
            if (i >= k) {
                int old = nums[i - k];
                if (low.containsKey(old)) { remove(low, old); lowSize--; } else { remove(high, old); highSize--; }
            }
            rebalance();
            if (i >= k - 1) out[i - k + 1] = low.lastKey();
        }
        return out;
    }
}
