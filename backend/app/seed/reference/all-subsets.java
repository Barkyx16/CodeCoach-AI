import java.util.*;

class Solution {
    public int[][] subsets(int[] nums) {
        Arrays.sort(nums);
        int n = nums.length;
        List<int[]> out = new ArrayList<>();
        for (int mask = 0; mask < (1 << n); mask++) {
            int[] s = new int[Integer.bitCount(mask)];
            int w = 0;
            for (int i = 0; i < n; i++) if ((mask >> i & 1) == 1) s[w++] = nums[i];
            out.add(s);
        }
        out.sort((a, b) -> {
            if (a.length != b.length) return a.length - b.length;
            for (int i = 0; i < a.length; i++) if (a[i] != b[i]) return Integer.compare(a[i], b[i]);
            return 0;
        });
        return out.toArray(new int[0][]);
    }
}
