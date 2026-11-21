class Solution {
    public int change(int amount, int[] coins) {
        int[] ways = new int[amount + 1];
        ways[0] = 1;
        for (int c : coins) for (int a = c; a <= amount; a++) ways[a] += ways[a - c];
        return ways[amount];
    }
}
