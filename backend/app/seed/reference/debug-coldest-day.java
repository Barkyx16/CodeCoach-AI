class Solution {
    public int coldest(int[] temps) {
        int coldest = temps[0];
        for (int t : temps) {
            if (t < coldest) {
                coldest = t;
            }
        }
        return coldest;
    }
}
