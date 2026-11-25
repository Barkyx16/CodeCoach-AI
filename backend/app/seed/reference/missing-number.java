class Solution {
    public int missingNumber(int[] nums) {
        int n = nums.length;
        long expected = (long) n * (n + 1) / 2, sum = 0;
        for (int v : nums) sum += v;
        return (int) (expected - sum);
    }
}
