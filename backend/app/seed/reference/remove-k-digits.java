class Solution {
    public String removeKdigits(String num, int k) {
        StringBuilder stack = new StringBuilder();
        for (char d : num.toCharArray()) {
            while (k > 0 && stack.length() > 0 && stack.charAt(stack.length() - 1) > d) {
                stack.deleteCharAt(stack.length() - 1);
                k--;
            }
            stack.append(d);
        }
        stack.setLength(stack.length() - k);
        int i = 0;
        while (i < stack.length() && stack.charAt(i) == '0') i++;
        String out = stack.substring(i);
        return out.isEmpty() ? "0" : out;
    }
}
