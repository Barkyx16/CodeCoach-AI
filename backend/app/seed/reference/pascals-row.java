class Solution {
    public int[] pascalRow(int n) {
        int[] row = new int[n + 1];
        row[0] = 1;
        for (int i = 1; i <= n; i++)
            for (int j = i; j >= 1; j--) row[j] += row[j - 1];
        return row;
    }
}
