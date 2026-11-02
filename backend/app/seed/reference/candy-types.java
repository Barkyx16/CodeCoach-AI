import java.util.*;

class Solution {
    public int distributeCandies(int[] candyType) {
        Set<Integer> types = new HashSet<>();
        for (int t : candyType) types.add(t);
        return Math.min(types.size(), candyType.length / 2);
    }
}
