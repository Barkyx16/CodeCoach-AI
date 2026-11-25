class Solution {
    private int find(int[] parent, int x) {
        while (parent[x] != x) { parent[x] = parent[parent[x]]; x = parent[x]; }
        return x;
    }
    public int findCircleNum(int[][] isConnected) {
        int n = isConnected.length, count = n;
        int[] parent = new int[n];
        for (int i = 0; i < n; i++) parent[i] = i;
        for (int i = 0; i < n; i++)
            for (int j = i + 1; j < n; j++)
                if (isConnected[i][j] == 1) {
                    int a = find(parent, i), b = find(parent, j);
                    if (a != b) { parent[a] = b; count--; }
                }
        return count;
    }
}
