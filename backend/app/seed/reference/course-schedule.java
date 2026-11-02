import java.util.*;

class Solution {
    public boolean canFinish(int n, int[][] prereqs) {
        List<List<Integer>> adj = new ArrayList<>();
        for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
        int[] indegree = new int[n];
        for (int[] p : prereqs) { adj.get(p[1]).add(p[0]); indegree[p[0]]++; }
        Deque<Integer> queue = new ArrayDeque<>();
        for (int i = 0; i < n; i++) if (indegree[i] == 0) queue.add(i);
        int taken = 0;
        while (!queue.isEmpty()) {
            int c = queue.poll();
            taken++;
            for (int next : adj.get(c)) if (--indegree[next] == 0) queue.add(next);
        }
        return taken == n;
    }
}
