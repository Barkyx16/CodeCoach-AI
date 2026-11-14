import java.util.*;

class Solution {
    public boolean wordPattern(String pattern, String s) {
        String[] words = s.split(" ");
        if (words.length != pattern.length()) return false;
        Map<Character, String> fwd = new HashMap<>();
        Map<String, Character> back = new HashMap<>();
        for (int i = 0; i < words.length; i++) {
            char c = pattern.charAt(i);
            String w = words[i];
            if (!fwd.getOrDefault(c, w).equals(w) || back.getOrDefault(w, c) != c) return false;
            fwd.put(c, w);
            back.put(w, c);
        }
        return true;
    }
}
