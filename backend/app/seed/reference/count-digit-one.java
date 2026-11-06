class Solution {
    public int countDigitOne(int n) {
        long count = 0;
        for (long p = 1; p <= n; p *= 10) {
            long high = n / (p * 10), cur = (n / p) % 10, low = n % p;
            count += high * p;
            if (cur == 1) count += low + 1;
            else if (cur > 1) count += p;
        }
        return (int) count;
    }
}
