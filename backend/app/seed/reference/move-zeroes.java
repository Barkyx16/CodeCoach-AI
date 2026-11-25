class Solution {
    public int[] moveZeroes(int[] nums) {
        int w = 0;
        for (int n : nums) if (n != 0) nums[w++] = n;
        while (w < nums.length) nums[w++] = 0;
        return nums;
    }
}
