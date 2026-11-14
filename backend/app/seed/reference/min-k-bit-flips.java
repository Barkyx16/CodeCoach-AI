class Solution {
    public int minKBitFlips(int[] nums, int k) {
        int n = nums.length, flips = 0, active = 0;
        int[] ended = new int[n + 1];
        for (int i = 0; i < n; i++) {
            active -= ended[i];
            if ((nums[i] + active) % 2 == 0) {
                if (i + k > n) return -1;
                flips++;
                active++;
                ended[i + k]++;
            }
        }
        return flips;
    }
}
