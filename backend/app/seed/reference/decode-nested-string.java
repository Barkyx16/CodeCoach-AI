import java.util.*;

class Solution {
    public String decodeString(String s) {
        Deque<Integer> counts = new ArrayDeque<>();
        Deque<StringBuilder> texts = new ArrayDeque<>();
        StringBuilder cur = new StringBuilder();
        int k = 0;
        for (char c : s.toCharArray()) {
            if (Character.isDigit(c)) k = k * 10 + (c - '0');
            else if (c == '[') { counts.push(k); texts.push(cur); cur = new StringBuilder(); k = 0; }
            else if (c == ']') {
                StringBuilder prev = texts.pop();
                int times = counts.pop();
                for (int i = 0; i < times; i++) prev.append(cur);
                cur = prev;
            } else cur.append(c);
        }
        return cur.toString();
    }
}
