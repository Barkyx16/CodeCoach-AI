import java.util.*;

class Solution {
    public int numSubmatrixSumTarget(int[][] matrix, int target) {
        int m = matrix.length, n = matrix[0].length, count = 0;
        for (int top = 0; top < m; top++) {
            int[] col = new int[n];
            for (int bottom = top; bottom < m; bottom++) {
                for (int j = 0; j < n; j++) col[j] += matrix[bottom][j];
                Map<Integer, Integer> seen = new HashMap<>();
                seen.put(0, 1);
                int sum = 0;
                for (int j = 0; j < n; j++) {
                    sum += col[j];
                    count += seen.getOrDefault(sum - target, 0);
                    seen.merge(sum, 1, Integer::sum);
                }
            }
        }
        return count;
    }
}
