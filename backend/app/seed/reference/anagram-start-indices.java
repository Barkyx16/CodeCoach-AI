import java.util.*;

class Solution {
    public int[] findAnagrams(String s, String p) {
        List<Integer> out = new ArrayList<>();
        int m = p.length(), n = s.length();
        if (m > n) return new int[0];
        int[] need = new int[26], window = new int[26];
        for (int i = 0; i < m; i++) { need[p.charAt(i) - 'a']++; window[s.charAt(i) - 'a']++; }
        if (Arrays.equals(need, window)) out.add(0);
        for (int i = m; i < n; i++) {
            window[s.charAt(i) - 'a']++;
            window[s.charAt(i - m) - 'a']--;
            if (Arrays.equals(need, window)) out.add(i - m + 1);
        }
        return out.stream().mapToInt(Integer::intValue).toArray();
    }
}
