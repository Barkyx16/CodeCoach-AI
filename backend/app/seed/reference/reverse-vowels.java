class Solution {
    private boolean vowel(char c) { return "aeiouAEIOU".indexOf(c) >= 0; }
    public String reverseVowels(String s) {
        char[] a = s.toCharArray();
        int i = 0, j = a.length - 1;
        while (i < j) {
            while (i < j && !vowel(a[i])) i++;
            while (i < j && !vowel(a[j])) j--;
            char t = a[i]; a[i] = a[j]; a[j] = t;
            i++; j--;
        }
        return new String(a);
    }
}
