import java.util.*;

class Solution {
    public int[] smallestRange(int[][] lists) {
        PriorityQueue<int[]> heap = new PriorityQueue<>((a, b) -> Integer.compare(a[0], b[0]));
        int hi = Integer.MIN_VALUE;
        for (int i = 0; i < lists.length; i++) { heap.add(new int[] {lists[i][0], i, 0}); hi = Math.max(hi, lists[i][0]); }
        int[] best = {heap.peek()[0], hi};
        while (true) {
            int[] top = heap.poll();
            int lo = top[0];
            if ((long) hi - lo < (long) best[1] - best[0] || (hi - lo == best[1] - best[0] && lo < best[0])) best = new int[] {lo, hi};
            if (top[2] + 1 == lists[top[1]].length) break;
            int next = lists[top[1]][top[2] + 1];
            heap.add(new int[] {next, top[1], top[2] + 1});
            hi = Math.max(hi, next);
        }
        return best;
    }
}
