import java.util.*;

class Solution {
    public boolean canCross(int[] stones) {
        Map<Integer, Set<Integer>> jumps = new HashMap<>();
        for (int s : stones) jumps.put(s, new HashSet<>());
        jumps.get(0).add(0);
        for (int s : stones)
            for (int k : jumps.get(s))
                for (int step = k - 1; step <= k + 1; step++)
                    if (step > 0 && jumps.containsKey(s + step)) jumps.get(s + step).add(step);
        return !jumps.get(stones[stones.length - 1]).isEmpty();
    }
}
