class Solution {
    public int countNegatives(int[] nums) {
        int count = 0;
        for (int n : nums) if (n < 0) count++;
        return count;
    }
}
