import java.util.*;

class Solution {
    public int evalRPN(String[] tokens) {
        Deque<Integer> stack = new ArrayDeque<>();
        for (String t : tokens) {
            if (t.length() == 1 && "+-*/".indexOf(t.charAt(0)) >= 0) {
                int b = stack.pop(), a = stack.pop();
                switch (t.charAt(0)) {
                    case '+': stack.push(a + b); break;
                    case '-': stack.push(a - b); break;
                    case '*': stack.push(a * b); break;
                    default: stack.push(a / b);
                }
            } else stack.push(Integer.parseInt(t));
        }
        return stack.pop();
    }
}
