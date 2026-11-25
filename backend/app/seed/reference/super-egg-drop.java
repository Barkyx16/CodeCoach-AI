class Solution {
    public int superEggDrop(int k, int n) {
        long[] floors = new long[k + 1];
        int m = 0;
        while (floors[k] < n) {
            m++;
            for (int j = k; j >= 1; j--) floors[j] = floors[j - 1] + floors[j] + 1;
        }
        return m;
    }
}
