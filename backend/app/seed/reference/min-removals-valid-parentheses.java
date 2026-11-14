class Solution {
    public int minRemovals(String s) {
        int open = 0, removals = 0;
        for (char c : s.toCharArray()) {
            if (c == '(') open++;
            else if (c == ')') { if (open > 0) open--; else removals++; }
        }
        return removals + open;
    }
}
