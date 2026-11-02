import java.util.*;

class Solution {
    public int findMaximizedCapital(int k, int w, int[] profits, int[] capital) {
        int n = profits.length;
        Integer[] order = new Integer[n];
        for (int i = 0; i < n; i++) order[i] = i;
        Arrays.sort(order, (a, b) -> Integer.compare(capital[a], capital[b]));
        PriorityQueue<Integer> heap = new PriorityQueue<>(Collections.reverseOrder());
        int i = 0;
        for (int round = 0; round < k; round++) {
            while (i < n && capital[order[i]] <= w) heap.add(profits[order[i++]]);
            if (heap.isEmpty()) break;
            w += heap.poll();
        }
        return w;
    }
}
