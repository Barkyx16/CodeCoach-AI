import java.util.*;

class Solution {
    public boolean isHappy(int n) {
        Set<Integer> seen = new HashSet<>();
        while (n != 1 && seen.add(n)) {
            int next = 0;
            while (n > 0) { int d = n % 10; next += d * d; n /= 10; }
            n = next;
        }
        return n == 1;
    }
}
