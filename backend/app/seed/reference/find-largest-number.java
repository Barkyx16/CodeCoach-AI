class Solution {
    public int max(int[] nums) {
        if (nums == null || nums.length == 0) {
            throw new IllegalArgumentException("nums must not be empty");
        }
        int largest = nums[0];
        for (int n : nums) {
            if (n > largest) largest = n;
        }
        return largest;
    }
}
