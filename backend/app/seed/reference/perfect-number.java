class Solution {
    public boolean isPerfect(int n) {
        if (n == 1) return false;
        long total = 1;
        for (long d = 2; d * d <= n; d++) {
            if (n % d == 0) { total += d; if (d != n / d) total += n / d; }
        }
        return total == n;
    }
}
