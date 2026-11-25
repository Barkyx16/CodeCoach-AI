import java.util.*;

class Solution {
    private Map<String, Boolean> memo = new HashMap<>();
    public boolean isScramble(String x, String y) {
        if (x.equals(y)) return true;
        String key = x + "#" + y;
        Boolean cached = memo.get(key);
        if (cached != null) return cached;
        char[] a = x.toCharArray(), b = y.toCharArray();
        Arrays.sort(a);
        Arrays.sort(b);
        boolean result = false;
        if (Arrays.equals(a, b)) {
            int n = x.length();
            for (int i = 1; i < n && !result; i++)
                result = (isScramble(x.substring(0, i), y.substring(0, i)) && isScramble(x.substring(i), y.substring(i)))
                    || (isScramble(x.substring(0, i), y.substring(n - i)) && isScramble(x.substring(i), y.substring(0, n - i)));
        }
        memo.put(key, result);
        return result;
    }
}
