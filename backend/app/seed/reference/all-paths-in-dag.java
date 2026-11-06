import java.util.*;

class Solution {
    private void dfs(int[][] g, int u, Deque<Integer> path, List<int[]> out) {
        if (u == g.length - 1) { out.add(path.stream().mapToInt(Integer::intValue).toArray()); return; }
        for (int v : g[u]) { path.addLast(v); dfs(g, v, path, out); path.removeLast(); }
    }
    public int[][] allPathsSourceTarget(int[][] graph) {
        List<int[]> out = new ArrayList<>();
        Deque<Integer> path = new ArrayDeque<>(List.of(0));
        dfs(graph, 0, path, out);
        out.sort(Arrays::compare);
        return out.toArray(new int[0][]);
    }
}
