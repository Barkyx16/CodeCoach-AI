import java.util.*;

class Solution {
    private void build(int[] c, int start, int remaining, Deque<Integer> path, List<int[]> out) {
        if (remaining == 0) { out.add(path.stream().mapToInt(Integer::intValue).toArray()); return; }
        for (int i = start; i < c.length && c[i] <= remaining; i++) {
            path.addLast(c[i]);
            build(c, i, remaining - c[i], path, out);
            path.removeLast();
        }
    }
    public int[][] combinationSum(int[] candidates, int target) {
        Arrays.sort(candidates);
        List<int[]> out = new ArrayList<>();
        build(candidates, 0, target, new ArrayDeque<>(), out);
        return out.toArray(new int[0][]);
    }
}
