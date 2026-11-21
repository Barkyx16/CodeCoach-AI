class Solution {
    public int minSwap(int[] a, int[] b) {
        int keep = 0, swap = 1;
        for (int i = 1; i < a.length; i++) {
            int nk = Integer.MAX_VALUE, ns = Integer.MAX_VALUE;
            if (a[i - 1] < a[i] && b[i - 1] < b[i]) { nk = keep; ns = swap + 1; }
            if (a[i - 1] < b[i] && b[i - 1] < a[i]) { nk = Math.min(nk, swap); ns = Math.min(ns, keep + 1); }
            keep = nk;
            swap = ns;
        }
        return Math.min(keep, swap);
    }
}
