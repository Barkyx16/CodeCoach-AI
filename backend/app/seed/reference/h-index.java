class Solution {
    public int hIndex(int[] citations) {
        int n = citations.length;
        int[] buckets = new int[n + 1];
        for (int c : citations) buckets[Math.min(c, n)]++;
        int total = 0;
        for (int h = n; h >= 0; h--) { total += buckets[h]; if (total >= h) return h; }
        return 0;
    }
}
