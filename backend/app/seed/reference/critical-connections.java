import java.util.*;

class Solution {
    private int time = 0;
    private void dfs(int u, int parent, List<List<Integer>> adj, int[] disc, int[] low, List<int[]> out) {
        disc[u] = low[u] = ++time;
        for (int v : adj.get(u)) {
            if (v == parent) continue;
            if (disc[v] == 0) {
                dfs(v, u, adj, disc, low, out);
                low[u] = Math.min(low[u], low[v]);
                if (low[v] > disc[u]) out.add(new int[] {Math.min(u, v), Math.max(u, v)});
            } else low[u] = Math.min(low[u], disc[v]);
        }
    }
    public int[][] criticalConnections(int n, int[][] connections) {
        List<List<Integer>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        for (int[] c : connections) { adj.get(c[0]).add(c[1]); adj.get(c[1]).add(c[0]); }
        List<int[]> out = new ArrayList<>();
        dfs(0, -1, adj, new int[n], new int[n], out);
        out.sort(Arrays::compare);
        return out.toArray(new int[0][]);
    }
}
