class Solution {
    public String capitalizeWords(String s) {
        char[] out = s.toCharArray();
        for (int i = 0; i < out.length; i++)
            if (i == 0 || out[i - 1] == ' ') out[i] = Character.toUpperCase(out[i]);
        return new String(out);
    }
}
