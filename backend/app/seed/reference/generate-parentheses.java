import java.util.*;

class Solution {
    private void build(String s, int open, int close, int n, List<String> out) {
        if (s.length() == 2 * n) { out.add(s); return; }
        if (open < n) build(s + "(", open + 1, close, n, out);
        if (close < open) build(s + ")", open, close + 1, n, out);
    }
    public String[] generateParenthesis(int n) {
        List<String> out = new ArrayList<>();
        build("", 0, 0, n, out);
        return out.toArray(new String[0]);
    }
}
