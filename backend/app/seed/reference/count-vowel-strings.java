class Solution {
    public int countVowelPermutation(int n) {
        long M = 1_000_000_007, a = 1, e = 1, i = 1, o = 1, u = 1;
        for (int k = 1; k < n; k++) {
            long na = (e + i + u) % M, ne = (a + i) % M, ni = (e + o) % M, no = i, nu = (i + o) % M;
            a = na; e = ne; i = ni; o = no; u = nu;
        }
        return (int) ((a + e + i + o + u) % M);
    }
}
