import java.util.*;

class Solution {
    public int[][] getSkyline(int[][] buildings) {
        TreeSet<Integer> xs = new TreeSet<>();
        for (int[] b : buildings) { xs.add(b[0]); xs.add(b[1]); }
        PriorityQueue<int[]> heap = new PriorityQueue<>((a, b) -> Integer.compare(b[0], a[0]));
        List<int[]> out = new ArrayList<>();
        int i = 0, prev = 0;
        for (int x : xs) {
            while (i < buildings.length && buildings[i][0] <= x) { heap.add(new int[] {buildings[i][2], buildings[i][1]}); i++; }
            while (!heap.isEmpty() && heap.peek()[1] <= x) heap.poll();
            int h = heap.isEmpty() ? 0 : heap.peek()[0];
            if (h != prev) { out.add(new int[] {x, h}); prev = h; }
        }
        return out.toArray(new int[0][]);
    }
}
