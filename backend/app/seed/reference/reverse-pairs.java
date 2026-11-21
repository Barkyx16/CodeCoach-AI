class Solution {
    private int sort(int[] a, int[] tmp, int lo, int hi) {
        if (hi - lo <= 1) return 0;
        int mid = (lo + hi) >>> 1;
        int count = sort(a, tmp, lo, mid) + sort(a, tmp, mid, hi);
        for (int i = lo, j = mid; i < mid; i++) {
            while (j < hi && (long) a[i] > 2L * a[j]) j++;
            count += j - mid;
        }
        int i = lo, j = mid, k = lo;
        while (i < mid || j < hi) tmp[k++] = (j == hi || (i < mid && a[i] <= a[j])) ? a[i++] : a[j++];
        System.arraycopy(tmp, lo, a, lo, hi - lo);
        return count;
    }
    public int reversePairs(int[] nums) {
        return sort(nums, new int[nums.length], 0, nums.length);
    }
}
