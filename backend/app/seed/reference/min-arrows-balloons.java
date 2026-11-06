import java.util.*;

class Solution {
    public int findMinArrowShots(int[][] points) {
        Arrays.sort(points, (x, y) -> Integer.compare(x[1], y[1]));
        int arrows = 0;
        long last = Long.MIN_VALUE;
        for (int[] p : points) if (p[0] > last) { arrows++; last = p[1]; }
        return arrows;
    }
}
