class Solution {
    public int[] uniqueSorted(int[] nums) {
        int count = 0;
        for (int i = 0; i < nums.length; i++) if (i == 0 || nums[i] != nums[i - 1]) count++;
        int[] out = new int[count];
        int w = 0;
        for (int i = 0; i < nums.length; i++) if (i == 0 || nums[i] != nums[i - 1]) out[w++] = nums[i];
        return out;
    }
}
