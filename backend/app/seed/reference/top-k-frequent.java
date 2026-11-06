import java.util.*;

class Solution {
    public int[] topKFrequent(int[] nums, int k) {
        Map<Integer, Integer> counts = new HashMap<>();
        for (int x : nums) counts.merge(x, 1, Integer::sum);
        List<Integer> values = new ArrayList<>(counts.keySet());
        values.sort((a, b) -> !counts.get(a).equals(counts.get(b)) ? counts.get(b) - counts.get(a) : Integer.compare(a, b));
        int[] out = new int[k];
        for (int i = 0; i < k; i++) out[i] = values.get(i);
        return out;
    }
}
