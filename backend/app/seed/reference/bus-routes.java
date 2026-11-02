import java.util.*;

class Solution {
    public int numBusesToDestination(int[][] routes, int source, int target) {
        if (source == target) return 0;
        Map<Integer, List<Integer>> busesAt = new HashMap<>();
        for (int b = 0; b < routes.length; b++) for (int s : routes[b]) busesAt.computeIfAbsent(s, k -> new ArrayList<>()).add(b);
        boolean[] usedBus = new boolean[routes.length];
        Set<Integer> seenStop = new HashSet<>(List.of(source));
        Deque<Integer> queue = new ArrayDeque<>();
        for (int b : busesAt.getOrDefault(source, List.of())) { usedBus[b] = true; queue.add(b); }
        for (int depth = 1; !queue.isEmpty(); depth++) {
            for (int k = queue.size(); k > 0; k--) {
                int b = queue.poll();
                for (int s : routes[b]) {
                    if (s == target) return depth;
                    if (!seenStop.add(s)) continue;
                    for (int nb : busesAt.get(s)) if (!usedBus[nb]) { usedBus[nb] = true; queue.add(nb); }
                }
            }
        }
        return -1;
    }
}
