import java.util.*;

class Solution {
    public String countOfAtoms(String formula) {
        Deque<Map<String, Integer>> stack = new ArrayDeque<>();
        stack.push(new TreeMap<>());
        int i = 0, n = formula.length();
        while (i < n) {
            char c = formula.charAt(i);
            if (c == '(') { stack.push(new TreeMap<>()); i++; }
            else if (c == ')') {
                i++;
                int j = i;
                while (j < n && Character.isDigit(formula.charAt(j))) j++;
                int mult = j > i ? Integer.parseInt(formula.substring(i, j)) : 1;
                i = j;
                Map<String, Integer> inner = stack.pop();
                for (Map.Entry<String, Integer> e : inner.entrySet()) stack.peek().merge(e.getKey(), e.getValue() * mult, Integer::sum);
            } else {
                int j = i + 1;
                while (j < n && Character.isLowerCase(formula.charAt(j))) j++;
                String name = formula.substring(i, j);
                int k = j;
                while (k < n && Character.isDigit(formula.charAt(k))) k++;
                int count = k > j ? Integer.parseInt(formula.substring(j, k)) : 1;
                stack.peek().merge(name, count, Integer::sum);
                i = k;
            }
        }
        StringBuilder sb = new StringBuilder();
        for (Map.Entry<String, Integer> e : stack.peek().entrySet()) {
            sb.append(e.getKey());
            if (e.getValue() > 1) sb.append(e.getValue());
        }
        return sb.toString();
    }
}
