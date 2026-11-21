class Solution {
    public int digitSum(int n) {
        n = Math.abs(n);
        int total = 0;
        while (n > 0) { total += n % 10; n /= 10; }
        return total;
    }
}
