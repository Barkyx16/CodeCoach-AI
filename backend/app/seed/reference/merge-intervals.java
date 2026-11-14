import java.util.*;

class Solution {
    public int[][] merge(int[][] intervals) {
        Arrays.sort(intervals, (x, y) -> x[0] != y[0] ? Integer.compare(x[0], y[0]) : Integer.compare(x[1], y[1]));
        List<int[]> out = new ArrayList<>();
        for (int[] iv : intervals) {
            if (!out.isEmpty() && iv[0] <= out.get(out.size() - 1)[1])
                out.get(out.size() - 1)[1] = Math.max(out.get(out.size() - 1)[1], iv[1]);
            else out.add(new int[] {iv[0], iv[1]});
        }
        return out.toArray(new int[0][]);
    }
}
