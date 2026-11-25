class Solution {
    public int heightChecker(int[] heights) {
        int[] counts = new int[101];
        for (int h : heights) counts[h]++;
        int wrong = 0, h = 0;
        for (int x : heights) {
            while (counts[h] == 0) h++;
            if (x != h) wrong++;
            counts[h]--;
        }
        return wrong;
    }
}
