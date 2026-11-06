class Solution {
    public int thirdMax(int[] nums) {
        long a = Long.MIN_VALUE, b = Long.MIN_VALUE, c = Long.MIN_VALUE;
        for (int x : nums) {
            if (x == a || x == b || x == c) continue;
            if (x > a) { c = b; b = a; a = x; }
            else if (x > b) { c = b; b = x; }
            else if (x > c) c = x;
        }
        return (int) (c == Long.MIN_VALUE ? a : c);
    }
}
