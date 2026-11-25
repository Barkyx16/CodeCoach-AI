class Solution {
    public boolean isPalindrome(String s) {
        StringBuilder kept = new StringBuilder();
        for (char c : s.toCharArray()) {
            if (Character.isLetterOrDigit(c)) kept.append(Character.toLowerCase(c));
        }
        String forward = kept.toString();
        return forward.equals(kept.reverse().toString());
    }
}
