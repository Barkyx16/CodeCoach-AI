class Solution {
    public int[] sortByParity(int[] nums) {
        int[] out = new int[nums.length];
        int w = 0;
        for (int x : nums) if (x % 2 == 0) out[w++] = x;
        for (int x : nums) if (x % 2 != 0) out[w++] = x;
        return out;
    }
}
