import java.util.*;

class Solution {
    public int racecar(int target) {
        Deque<int[]> queue = new ArrayDeque<>();
        Set<Long> seen = new HashSet<>();
        queue.add(new int[] {0, 1});
        seen.add(1L);
        for (int steps = 0; ; steps++) {
            for (int k = queue.size(); k > 0; k--) {
                int[] s = queue.poll();
                if (s[0] == target) return steps;
                int[][] nexts = {{s[0] + s[1], s[1] * 2}, {s[0], s[1] > 0 ? -1 : 1}};
                for (int[] t : nexts) {
                    if (Math.abs(t[0]) > 2 * target + 2) continue;
                    long key = ((long) t[0] << 32) ^ (t[1] & 0xffffffffL);
                    if (seen.add(key)) queue.add(t);
                }
            }
        }
    }
}
