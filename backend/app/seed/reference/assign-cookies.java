import java.util.*;

class Solution {
    public int findContentChildren(int[] greed, int[] sizes) {
        Arrays.sort(greed);
        Arrays.sort(sizes);
        int i = 0;
        for (int s : sizes) if (i < greed.length && s >= greed[i]) i++;
        return i;
    }
}
