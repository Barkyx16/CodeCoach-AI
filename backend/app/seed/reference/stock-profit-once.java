class Solution {
    public int maxProfit(int[] prices) {
        int low = Integer.MAX_VALUE, best = 0;
        for (int p : prices) { low = Math.min(low, p); best = Math.max(best, p - low); }
        return best;
    }
}
