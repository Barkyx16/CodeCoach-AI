import java.util.Arrays;

class Solution {
    public int coinChange(int[] coins, int amount) {
        int[] best = new int[amount + 1];
        Arrays.fill(best, amount + 1);
        best[0] = 0;
        for (int a = 1; a <= amount; a++) {
            for (int c : coins) {
                if (c <= a) {
                    best[a] = Math.min(best[a], best[a - c] + 1);
                }
            }
        }
        return best[amount] > amount ? -1 : best[amount];
    }
}
