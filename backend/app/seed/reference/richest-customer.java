class Solution {
    public int maximumWealth(int[][] accounts) {
        int best = 0;
        for (int[] row : accounts) {
            int s = 0;
            for (int v : row) s += v;
            best = Math.max(best, s);
        }
        return best;
    }
}
