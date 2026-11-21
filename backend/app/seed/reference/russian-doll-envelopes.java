import java.util.*;

class Solution {
    public int maxEnvelopes(int[][] envelopes) {
        Arrays.sort(envelopes, (a, b) -> a[0] != b[0] ? Integer.compare(a[0], b[0]) : Integer.compare(b[1], a[1]));
        int[] tails = new int[envelopes.length];
        int size = 0;
        for (int[] e : envelopes) {
            int lo = 0, hi = size;
            while (lo < hi) { int mid = (lo + hi) >>> 1; if (tails[mid] < e[1]) lo = mid + 1; else hi = mid; }
            tails[lo] = e[1];
            if (lo == size) size++;
        }
        return size;
    }
}
