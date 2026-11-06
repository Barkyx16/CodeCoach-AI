class Solution {
    public int sumOfUnique(int[] nums) {
        int[] counts = new int[101];
        for (int x : nums) counts[x]++;
        int total = 0;
        for (int v = 1; v <= 100; v++) if (counts[v] == 1) total += v;
        return total;
    }
}
