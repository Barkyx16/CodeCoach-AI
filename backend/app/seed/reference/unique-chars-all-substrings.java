import java.util.*;

class Solution {
    public int uniqueLetterString(String s) {
        int n = s.length();
        int[] prev = new int[26], prev2 = new int[26];
        Arrays.fill(prev, -1);
        Arrays.fill(prev2, -1);
        long total = 0;
        for (int i = 0; i < n; i++) {
            int c = s.charAt(i) - 'A';
            if (prev[c] != -1) total += (long) (prev[c] - prev2[c]) * (i - prev[c]);
            prev2[c] = prev[c];
            prev[c] = i;
        }
        for (int c = 0; c < 26; c++) if (prev[c] != -1) total += (long) (prev[c] - prev2[c]) * (n - prev[c]);
        return (int) total;
    }
}
