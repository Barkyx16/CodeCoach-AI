import java.util.*;

class Solution {
    public String frequencySort(String s) {
        int[] counts = new int[128];
        for (char c : s.toCharArray()) counts[c]++;
        List<Character> chars = new ArrayList<>();
        for (int c = 0; c < 128; c++) if (counts[c] > 0) chars.add((char) c);
        chars.sort((a, b) -> counts[a] != counts[b] ? counts[b] - counts[a] : a - b);
        StringBuilder sb = new StringBuilder();
        for (char c : chars) for (int i = 0; i < counts[c]; i++) sb.append(c);
        return sb.toString();
    }
}
