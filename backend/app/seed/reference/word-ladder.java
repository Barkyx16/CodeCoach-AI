import java.util.*;

class Solution {
    public int ladderLength(String begin, String end, String[] words) {
        Set<String> dict = new HashSet<>(Arrays.asList(words));
        if (!dict.contains(end)) return 0;
        Deque<String> queue = new ArrayDeque<>(List.of(begin));
        dict.remove(begin);
        for (int d = 1; !queue.isEmpty(); d++) {
            for (int k = queue.size(); k > 0; k--) {
                String w = queue.poll();
                if (w.equals(end)) return d;
                char[] c = w.toCharArray();
                for (int i = 0; i < c.length; i++) {
                    char saved = c[i];
                    for (char x = 'a'; x <= 'z'; x++) {
                        c[i] = x;
                        String v = new String(c);
                        if (dict.remove(v)) queue.add(v);
                    }
                    c[i] = saved;
                }
            }
        }
        return 0;
    }
}
