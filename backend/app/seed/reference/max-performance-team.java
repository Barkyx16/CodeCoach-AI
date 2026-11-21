import java.util.*;

class Solution {
    public long maxPerformance(int n, int[] speed, int[] efficiency, int k) {
        Integer[] order = new Integer[n];
        for (int i = 0; i < n; i++) order[i] = i;
        Arrays.sort(order, (a, b) -> Integer.compare(efficiency[b], efficiency[a]));
        PriorityQueue<Integer> heap = new PriorityQueue<>();
        long total = 0, best = 0;
        for (int i : order) {
            heap.add(speed[i]);
            total += speed[i];
            if (heap.size() > k) total -= heap.poll();
            best = Math.max(best, total * efficiency[i]);
        }
        return best;
    }
}
