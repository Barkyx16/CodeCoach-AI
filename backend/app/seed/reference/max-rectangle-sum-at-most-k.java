import java.util.*;

class Solution {
    public int maxSumSubmatrix(int[][] matrix, int k) {
        int m = matrix.length, n = matrix[0].length, best = Integer.MIN_VALUE;
        for (int left = 0; left < n; left++) {
            int[] rows = new int[m];
            for (int right = left; right < n; right++) {
                for (int i = 0; i < m; i++) rows[i] += matrix[i][right];
                TreeSet<Integer> seen = new TreeSet<>(List.of(0));
                int prefix = 0;
                for (int s : rows) {
                    prefix += s;
                    Integer c = seen.ceiling(prefix - k);
                    if (c != null) best = Math.max(best, prefix - c);
                    seen.add(prefix);
                }
            }
        }
        return best;
    }
}
