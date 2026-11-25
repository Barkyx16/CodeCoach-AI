import java.util.*;

class Solution {
    public int eraseOverlapIntervals(int[][] intervals) {
        Arrays.sort(intervals, (x, y) -> Integer.compare(x[1], y[1]));
        int kept = 0;
        long end = Long.MIN_VALUE;
        for (int[] iv : intervals) if (iv[0] >= end) { kept++; end = iv[1]; }
        return intervals.length - kept;
    }
}
