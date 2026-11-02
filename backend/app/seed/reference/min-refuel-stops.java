import java.util.*;

class Solution {
    public int minRefuelStops(int target, int startFuel, int[][] stations) {
        PriorityQueue<Integer> heap = new PriorityQueue<>(Collections.reverseOrder());
        long fuel = startFuel;
        int stops = 0;
        for (int i = 0; i <= stations.length; i++) {
            if (i < stations.length && stations[i][0] >= target) continue;
            int pos = i == stations.length ? target : stations[i][0];
            while (fuel < pos) {
                if (heap.isEmpty()) return -1;
                fuel += heap.poll();
                stops++;
            }
            if (i < stations.length) heap.add(stations[i][1]);
        }
        return stops;
    }
}
