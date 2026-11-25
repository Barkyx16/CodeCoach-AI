class Solution {
    public int[] countSmaller(int[] nums) {
        int offset = 10001, size = 20003;
        int[] tree = new int[size + 1], counts = new int[nums.length];
        for (int i = nums.length - 1; i >= 0; i--) {
            int idx = nums[i] + offset;
            int c = 0;
            for (int k = idx - 1; k > 0; k -= k & -k) c += tree[k];
            counts[i] = c;
            for (int k = idx; k <= size; k += k & -k) tree[k]++;
        }
        return counts;
    }
}
