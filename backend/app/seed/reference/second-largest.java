class Solution {
    public int secondLargest(int[] nums) {
        int first = -1, second = -1;
        for (int n : nums) {
            if (n > first) { second = first; first = n; }
            else if (n < first && n > second) second = n;
        }
        return second;
    }
}
