class Solution {
    public int countOrders(int n) {
        long ways = 1;
        for (int i = 2; i <= n; i++) ways = ways * i % 1_000_000_007 * (2L * i - 1) % 1_000_000_007;
        return (int) ways;
    }
}
