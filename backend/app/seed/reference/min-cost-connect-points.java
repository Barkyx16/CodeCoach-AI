import java.util.*;

class Solution {
    public int minCostConnectPoints(int[][] points) {
        int n = points.length, total = 0;
        int[] dist = new int[n];
        Arrays.fill(dist, Integer.MAX_VALUE);
        dist[0] = 0;
        boolean[] inTree = new boolean[n];
        for (int round = 0; round < n; round++) {
            int u = -1;
            for (int v = 0; v < n; v++) if (!inTree[v] && (u == -1 || dist[v] < dist[u])) u = v;
            inTree[u] = true;
            total += dist[u];
            for (int v = 0; v < n; v++)
                if (!inTree[v]) dist[v] = Math.min(dist[v], Math.abs(points[u][0] - points[v][0]) + Math.abs(points[u][1] - points[v][1]));
        }
        return total;
    }
}
