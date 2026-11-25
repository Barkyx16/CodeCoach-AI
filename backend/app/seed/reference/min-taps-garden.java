class Solution {
    public int minTaps(int n, int[] ranges) {
        int[] reach = new int[n + 1];
        for (int i = 0; i <= n; i++) {
            int l = Math.max(0, i - ranges[i]), r = Math.min(n, i + ranges[i]);
            reach[l] = Math.max(reach[l], r);
        }
        int taps = 0, end = 0, far = 0;
        for (int i = 0; i < n; i++) {
            far = Math.max(far, reach[i]);
            if (i == end) {
                if (far <= i) return -1;
                taps++;
                end = far;
            }
        }
        return taps;
    }
}
