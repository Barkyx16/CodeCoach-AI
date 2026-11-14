import java.util.*;

class Solution {
    public int[] findOrder(int n, int[][] prereqs) {
        List<List<Integer>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        int[] indegree = new int[n];
        for (int[] p : prereqs) { adj.get(p[1]).add(p[0]); indegree[p[0]]++; }
        PriorityQueue<Integer> heap = new PriorityQueue<>();
        for (int i = 0; i < n; i++) if (indegree[i] == 0) heap.add(i);
        int[] order = new int[n];
        int w = 0;
        while (!heap.isEmpty()) {
            int c = heap.poll();
            order[w++] = c;
            for (int next : adj.get(c)) if (--indegree[next] == 0) heap.add(next);
        }
        return w == n ? order : new int[0];
    }
}
