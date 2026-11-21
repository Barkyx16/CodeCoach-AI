class Solution {
    private String s;
    private int i;
    private int expr() {
        int v = term();
        while (i < s.length() && (s.charAt(i) == '+' || s.charAt(i) == '-')) {
            char op = s.charAt(i++);
            int t = term();
            v = op == '+' ? v + t : v - t;
        }
        return v;
    }
    private int term() {
        int v = factor();
        while (i < s.length() && (s.charAt(i) == '*' || s.charAt(i) == '/')) {
            char op = s.charAt(i++);
            int f = factor();
            v = op == '*' ? v * f : v / f;
        }
        return v;
    }
    private int factor() {
        if (s.charAt(i) == '(') { i++; int v = expr(); i++; return v; }
        int v = 0;
        while (i < s.length() && Character.isDigit(s.charAt(i))) v = v * 10 + (s.charAt(i++) - '0');
        return v;
    }
    public int calculatePrecedence(String s) {
        this.s = s.replace(" ", "");
        this.i = 0;
        return expr();
    }
}
