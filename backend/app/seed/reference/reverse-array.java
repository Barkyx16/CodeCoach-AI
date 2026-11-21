class Solution {
    public int[] reverseArray(int[] nums) {
        int n = nums.length;
        int[] out = new int[n];
        for (int i = 0; i < n; i++) out[i] = nums[n - 1 - i];
        return out;
    }
}
