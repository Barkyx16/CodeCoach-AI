class Solution {
    public int balancedSplit(String s) {
        int balance = 0, pieces = 0;
        for (char c : s.toCharArray()) { balance += c == 'L' ? 1 : -1; if (balance == 0) pieces++; }
        return pieces;
    }
}
