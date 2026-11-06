import java.util.*;

class Solution {
    public int[] findSubstring(String s, String[] words) {
        int L = words[0].length(), k = words.length, total = L * k, n = s.length();
        Map<String, Integer> need = new HashMap<>();
        for (String w : words) need.merge(w, 1, Integer::sum);
        List<Integer> out = new ArrayList<>();
        for (int offset = 0; offset < L; offset++) {
            Map<String, Integer> window = new HashMap<>();
            int left = offset;
            for (int right = offset; right + L <= n; right += L) {
                String w = s.substring(right, right + L);
                if (!need.containsKey(w)) { window.clear(); left = right + L; continue; }
                window.merge(w, 1, Integer::sum);
                while (window.get(w) > need.get(w)) { window.merge(s.substring(left, left + L), -1, Integer::sum); left += L; }
                if (right + L - left == total) out.add(left);
            }
        }
        Collections.sort(out);
        return out.stream().mapToInt(Integer::intValue).toArray();
    }
}
