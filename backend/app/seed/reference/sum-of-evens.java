class Solution {
    public int sumEvens(int[] nums) {
        int total = 0;
        for (int n : nums) if (n % 2 == 0) total += n;
        return total;
    }
}
