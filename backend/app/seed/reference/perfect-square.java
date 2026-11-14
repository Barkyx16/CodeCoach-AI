class Solution {
    public boolean isPerfectSquare(int num) {
        long lo = 1, hi = num;
        while (lo <= hi) {
            long mid = (lo + hi) / 2, sq = mid * mid;
            if (sq == num) return true;
            if (sq < num) lo = mid + 1; else hi = mid - 1;
        }
        return false;
    }
}
