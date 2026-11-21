class Solution {
    public boolean isIsomorphic(String s, String t) {
        int[] fwd = new int[256], back = new int[256];
        for (int i = 0; i < s.length(); i++) {
            char a = s.charAt(i), b = t.charAt(i);
            if (fwd[a] == 0 && back[b] == 0) { fwd[a] = b + 1; back[b] = a + 1; }
            else if (fwd[a] != b + 1 || back[b] != a + 1) return false;
        }
        return true;
    }
}
