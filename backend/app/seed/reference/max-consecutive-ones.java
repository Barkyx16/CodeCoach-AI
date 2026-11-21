class Solution {
    public int longestOnes(int[] nums) {
        int best = 0, cur = 0;
        for (int n : nums) { cur = n == 1 ? cur + 1 : 0; best = Math.max(best, cur); }
        return best;
    }
}
