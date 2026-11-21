class Solution {
    private int daysNeeded(int[] weights, int cap) {
        int days = 1, load = 0;
        for (int w : weights) { if (load + w > cap) { days++; load = 0; } load += w; }
        return days;
    }
    public int shipWithinDays(int[] weights, int days) {
        int lo = 0, hi = 0;
        for (int w : weights) { lo = Math.max(lo, w); hi += w; }
        while (lo < hi) {
            int mid = (lo + hi) >>> 1;
            if (daysNeeded(weights, mid) <= days) hi = mid; else lo = mid + 1;
        }
        return lo;
    }
}
