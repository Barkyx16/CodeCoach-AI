class Solution {
    public int hammingDistance(int x, int y) {
        int d = x ^ y, count = 0;
        while (d != 0) { d &= d - 1; count++; }
        return count;
    }
}
