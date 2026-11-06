import java.util.*;

class Solution {
    public int[] lfuCache(int capacity, String[] ops) {
        Map<Integer, Integer> values = new HashMap<>(), counts = new HashMap<>();
        Map<Integer, LinkedHashSet<Integer>> buckets = new HashMap<>();
        int minCount = 0;
        List<Integer> out = new ArrayList<>();
        for (String op : ops) {
            String[] p = op.split(" ");
            int key = Integer.parseInt(p[1]);
            boolean present = values.containsKey(key);
            if (p[0].equals("get") && !present) { out.add(-1); continue; }
            if (!present) {
                if (values.size() == capacity) {
                    int victim = buckets.get(minCount).iterator().next();
                    buckets.get(minCount).remove(victim);
                    values.remove(victim);
                    counts.remove(victim);
                }
                values.put(key, Integer.parseInt(p[2]));
                counts.put(key, 1);
                buckets.computeIfAbsent(1, c -> new LinkedHashSet<>()).add(key);
                minCount = 1;
                continue;
            }
            int c = counts.get(key);
            buckets.get(c).remove(key);
            if (c == minCount && buckets.get(c).isEmpty()) minCount++;
            counts.put(key, c + 1);
            buckets.computeIfAbsent(c + 1, x -> new LinkedHashSet<>()).add(key);
            if (p[0].equals("get")) out.add(values.get(key)); else values.put(key, Integer.parseInt(p[2]));
        }
        return out.stream().mapToInt(Integer::intValue).toArray();
    }
}
