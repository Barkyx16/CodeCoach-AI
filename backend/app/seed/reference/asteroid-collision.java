import java.util.*;

class Solution {
    public int[] asteroidCollision(int[] asteroids) {
        Deque<Integer> stack = new ArrayDeque<>();
        for (int a : asteroids) {
            boolean alive = true;
            while (alive && a < 0 && !stack.isEmpty() && stack.peek() > 0) {
                int top = stack.peek();
                if (top < -a) { stack.pop(); continue; }
                if (top == -a) stack.pop();
                alive = false;
            }
            if (alive) stack.push(a);
        }
        int[] out = new int[stack.size()];
        for (int i = out.length - 1; i >= 0; i--) out[i] = stack.pop();
        return out;
    }
}
