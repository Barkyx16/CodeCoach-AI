class Solution {
    public String stoneGameIII(int[] values) {
        int n = values.length;
        int[] best = new int[n + 3];
        for (int i = n - 1; i >= 0; i--) {
            best[i] = Integer.MIN_VALUE;
            int taken = 0;
            for (int t = 1; t <= 3 && i + t <= n; t++) {
                taken += values[i + t - 1];
                best[i] = Math.max(best[i], taken - best[i + t]);
            }
        }
        return best[0] > 0 ? "Alice" : best[0] < 0 ? "Bob" : "Tie";
    }
}
