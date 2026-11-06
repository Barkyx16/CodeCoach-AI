import java.util.*;

class Solution {
    public boolean wordBreak(String s, String[] dict) {
        Set<String> words = new HashSet<>(Arrays.asList(dict));
        int n = s.length();
        boolean[] ok = new boolean[n + 1];
        ok[0] = true;
        for (int i = 1; i <= n; i++)
            for (int j = 0; j < i && !ok[i]; j++)
                if (ok[j] && words.contains(s.substring(j, i))) ok[i] = true;
        return ok[n];
    }
}
