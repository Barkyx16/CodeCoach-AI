class Solution {
    public int[] twoSumSorted(int[] nums, int target) {
        int i = 0, j = nums.length - 1;
        while (true) {
            int s = nums[i] + nums[j];
            if (s == target) return new int[] {i + 1, j + 1};
            if (s < target) i++; else j--;
        }
    }
}
