class Solution {
    public int[] maxSumOfThreeSubarrays(int[] nums, int k) {
        int m = nums.length - k + 1;
        int[] w = new int[m];
        int sum = 0;
        for (int i = 0; i < nums.length; i++) {
            sum += nums[i];
            if (i >= k) sum -= nums[i - k];
            if (i >= k - 1) w[i - k + 1] = sum;
        }
        int[] left = new int[m], right = new int[m];
        for (int i = 0, best = 0; i < m; i++) { if (w[i] > w[best]) best = i; left[i] = best; }
        for (int i = m - 1, best = m - 1; i >= 0; i--) { if (w[i] >= w[best]) best = i; right[i] = best; }
        int[] ans = null;
        for (int mid = k; mid + k < m; mid++) {
            int a = left[mid - k], c = right[mid + k];
            if (ans == null || w[a] + w[mid] + w[c] > w[ans[0]] + w[ans[1]] + w[ans[2]]) ans = new int[] {a, mid, c};
        }
        return ans;
    }
}
