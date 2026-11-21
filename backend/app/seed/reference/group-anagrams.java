import java.util.*;

class Solution {
    public String[] groupAnagrams(String[] words) {
        Map<String, List<String>> groups = new HashMap<>();
        for (String w : words) {
            char[] key = w.toCharArray();
            Arrays.sort(key);
            groups.computeIfAbsent(new String(key), k -> new ArrayList<>()).add(w);
        }
        List<String> out = new ArrayList<>();
        for (List<String> g : groups.values()) {
            Collections.sort(g);
            out.add(String.join(",", g));
        }
        Collections.sort(out);
        return out.toArray(new String[0]);
    }
}
