import java.util.*;

class Solution {
    public String[] letterCombinations(String digits) {
        if (digits.isEmpty()) return new String[0];
        String[] keys = {"", "", "abc", "def", "ghi", "jkl", "mno", "pqrs", "tuv", "wxyz"};
        List<String> results = new ArrayList<>(List.of(""));
        for (char d : digits.toCharArray()) {
            List<String> next = new ArrayList<>();
            for (String r : results) for (char c : keys[d - '0'].toCharArray()) next.add(r + c);
            results = next;
        }
        return results.toArray(new String[0]);
    }
}
