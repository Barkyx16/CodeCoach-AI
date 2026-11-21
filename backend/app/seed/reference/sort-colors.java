class Solution {
    public int[] sortColors(int[] nums) {
        int low = 0, mid = 0, high = nums.length - 1;
        while (mid <= high) {
            if (nums[mid] == 0) { int t = nums[low]; nums[low++] = nums[mid]; nums[mid++] = t; }
            else if (nums[mid] == 1) mid++;
            else { int t = nums[high]; nums[high--] = nums[mid]; nums[mid] = t; }
        }
        return nums;
    }
}
