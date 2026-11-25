class Solution {
    public int numIdenticalPairs(int[] nums) {
        int[] seen = new int[101];
        int pairs = 0;
        for (int x : nums) pairs += seen[x]++;
        return pairs;
    }
}
