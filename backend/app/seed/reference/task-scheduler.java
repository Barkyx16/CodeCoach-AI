class Solution {
    public int leastInterval(String tasks, int n) {
        int[] counts = new int[26];
        int m = 0;
        for (char c : tasks.toCharArray()) m = Math.max(m, ++counts[c - 'A']);
        int k = 0;
        for (int c : counts) if (c == m) k++;
        return Math.max(tasks.length(), (m - 1) * (n + 1) + k);
    }
}
