import java.util.*;

class Solution {
    public int[] intersection(int[] a, int[] b) {
        Set<Integer> seen = new HashSet<>();
        for (int x : a) seen.add(x);
        TreeSet<Integer> common = new TreeSet<>();
        for (int x : b) if (seen.contains(x)) common.add(x);
        int[] out = new int[common.size()];
        int i = 0;
        for (int x : common) out[i++] = x;
        return out;
    }
}
