import java.util.*;

class Solution {
    public boolean canVisitAllRooms(int[][] rooms) {
        boolean[] seen = new boolean[rooms.length];
        seen[0] = true;
        int count = 1;
        Deque<Integer> stack = new ArrayDeque<>(List.of(0));
        while (!stack.isEmpty())
            for (int k : rooms[stack.pop()])
                if (!seen[k]) { seen[k] = true; count++; stack.push(k); }
        return count == rooms.length;
    }
}
