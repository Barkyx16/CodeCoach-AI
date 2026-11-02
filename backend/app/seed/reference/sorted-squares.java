class Solution {
    public int[] sortedSquares(int[] nums) {
        int n = nums.length, i = 0, j = n - 1;
        int[] out = new int[n];
        for (int pos = n - 1; pos >= 0; pos--) {
            if (Math.abs(nums[i]) > Math.abs(nums[j])) { out[pos] = nums[i] * nums[i]; i++; }
            else { out[pos] = nums[j] * nums[j]; j--; }
        }
        return out;
    }
}
