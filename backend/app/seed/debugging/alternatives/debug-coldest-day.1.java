class Solution {
    public int coldest(int[] temps) {
        int coldest = Integer.MAX_VALUE;
        for (int t : temps) {
            coldest = Math.min(coldest, t);
        }
        return coldest;
    }
}
