class Solution {
    public String longestCommonPrefix(String[] words) {
        String first = words[0];
        for (int i = 0; i < first.length(); i++)
            for (String w : words)
                if (i == w.length() || w.charAt(i) != first.charAt(i)) return first.substring(0, i);
        return first;
    }
}
