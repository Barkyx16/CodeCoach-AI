import java.util.*;

class Solution {
    public int tallestBillboard(int[] rods) {
        Map<Integer, Integer> best = new HashMap<>();
        best.put(0, 0);
        for (int r : rods) {
            Map<Integer, Integer> next = new HashMap<>(best);
            for (Map.Entry<Integer, Integer> e : best.entrySet()) {
                int diff = e.getKey(), shortSide = e.getValue();
                next.merge(diff + r, shortSide, Math::max);
                int newDiff = Math.abs(diff - r), newShort = shortSide + Math.min(r, diff);
                next.merge(newDiff, newShort, Math::max);
            }
            best = next;
        }
        return best.get(0);
    }
}
