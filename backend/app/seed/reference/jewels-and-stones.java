class Solution {
    public int numJewelsInStones(String jewels, String stones) {
        boolean[] jewel = new boolean[128];
        for (char c : jewels.toCharArray()) jewel[c] = true;
        int count = 0;
        for (char c : stones.toCharArray()) if (jewel[c]) count++;
        return count;
    }
}
