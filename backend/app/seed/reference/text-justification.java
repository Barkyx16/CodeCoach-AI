import java.util.*;

class Solution {
    public String[] fullJustify(String[] words, int maxWidth) {
        List<String> lines = new ArrayList<>();
        int i = 0;
        while (i < words.length) {
            int j = i, length = 0;
            while (j < words.length && length + words[j].length() + (j - i) <= maxWidth) length += words[j++].length();
            StringBuilder sb = new StringBuilder();
            int count = j - i;
            if (j == words.length || count == 1) {
                for (int k = i; k < j; k++) { if (k > i) sb.append(' '); sb.append(words[k]); }
                while (sb.length() < maxWidth) sb.append(' ');
            } else {
                int gaps = count - 1, spaces = maxWidth - length;
                for (int k = i; k < j; k++) {
                    sb.append(words[k]);
                    if (k < j - 1) sb.append(" ".repeat(spaces / gaps + (k - i < spaces % gaps ? 1 : 0)));
                }
            }
            lines.add(sb.toString());
            i = j;
        }
        return lines.toArray(new String[0]);
    }
}
