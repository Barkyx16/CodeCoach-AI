class Solution {
    private String typed(String x) {
        StringBuilder sb = new StringBuilder();
        for (char c : x.toCharArray()) {
            if (c == '#') { if (sb.length() > 0) sb.deleteCharAt(sb.length() - 1); }
            else sb.append(c);
        }
        return sb.toString();
    }
    public boolean backspaceCompare(String s, String t) {
        return typed(s).equals(typed(t));
    }
}
