import java.util.*;

class Solution {
    public int[] findMinHeightTrees(int n, int[][] edges) {
        if (n == 1) return new int[] {0};
        List<List<Integer>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        int[] degree = new int[n];
        for (int[] e : edges) { adj.get(e[0]).add(e[1]); adj.get(e[1]).add(e[0]); degree[e[0]]++; degree[e[1]]++; }
        List<Integer> leaves = new ArrayList<>();
        for (int i = 0; i < n; i++) if (degree[i] == 1) leaves.add(i);
        int remaining = n;
        while (remaining > 2) {
            remaining -= leaves.size();
            List<Integer> next = new ArrayList<>();
            for (int leaf : leaves) for (int v : adj.get(leaf)) if (--degree[v] == 1) next.add(v);
            leaves = next;
        }
        Collections.sort(leaves);
        return leaves.stream().mapToInt(Integer::intValue).toArray();
    }
}
