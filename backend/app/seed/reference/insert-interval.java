import java.util.*;

class Solution {
    public int[][] insert(int[][] intervals, int[] newInterval) {
        List<int[]> out = new ArrayList<>();
        int i = 0, n = intervals.length, a = newInterval[0], b = newInterval[1];
        while (i < n && intervals[i][1] < a) out.add(intervals[i++]);
        while (i < n && intervals[i][0] <= b) { a = Math.min(a, intervals[i][0]); b = Math.max(b, intervals[i][1]); i++; }
        out.add(new int[] {a, b});
        while (i < n) out.add(intervals[i++]);
        return out.toArray(new int[0][]);
    }
}
