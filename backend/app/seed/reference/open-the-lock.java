import java.util.*;

class Solution {
    public int openLock(String[] deadends, String target) {
        Set<String> dead = new HashSet<>(Arrays.asList(deadends));
        if (dead.contains("0000")) return -1;
        Set<String> seen = new HashSet<>(List.of("0000"));
        Deque<String> queue = new ArrayDeque<>(List.of("0000"));
        for (int d = 0; !queue.isEmpty(); d++) {
            for (int k = queue.size(); k > 0; k--) {
                String code = queue.poll();
                if (code.equals(target)) return d;
                char[] c = code.toCharArray();
                for (int i = 0; i < 4; i++)
                    for (int s : new int[] {1, 9}) {
                        char saved = c[i];
                        c[i] = (char) ('0' + (saved - '0' + s) % 10);
                        String next = new String(c);
                        c[i] = saved;
                        if (!dead.contains(next) && seen.add(next)) queue.add(next);
                    }
            }
        }
        return -1;
    }
}
