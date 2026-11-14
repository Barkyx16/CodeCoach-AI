import java.util.*;

class Solution {
    public int[] lruCache(int capacity, String[] ops) {
        LinkedHashMap<Integer, Integer> cache = new LinkedHashMap<>(16, 0.75f, true);
        List<Integer> out = new ArrayList<>();
        for (String op : ops) {
            String[] p = op.split(" ");
            int key = Integer.parseInt(p[1]);
            if (p[0].equals("get")) out.add(cache.getOrDefault(key, -1));
            else {
                cache.put(key, Integer.parseInt(p[2]));
                if (cache.size() > capacity) cache.remove(cache.keySet().iterator().next());
            }
        }
        return out.stream().mapToInt(Integer::intValue).toArray();
    }
}
