import java.util.*;

class Solution {
    public int calPoints(String[] ops) {
        Deque<Integer> stack = new ArrayDeque<>();
        for (String op : ops) {
            if (op.equals("C")) stack.pop();
            else if (op.equals("D")) stack.push(2 * stack.peek());
            else if (op.equals("+")) { int a = stack.pop(), b = stack.peek(); stack.push(a); stack.push(a + b); }
            else stack.push(Integer.parseInt(op));
        }
        int total = 0;
        for (int s : stack) total += s;
        return total;
    }
}
