import java.util.*;

class Solution {
    private int find(int[] parent, int x) {
        while (parent[x] != x) { parent[x] = parent[parent[x]]; x = parent[x]; }
        return x;
    }
    public int[] numIslands2(int m, int n, int[][] positions) {
        int[] parent = new int[m * n];
        Arrays.fill(parent, -1);
        int[] out = new int[positions.length];
        int count = 0;
        int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        for (int i = 0; i < positions.length; i++) {
            int r = positions[i][0], c = positions[i][1], cell = r * n + c;
            if (parent[cell] == -1) {
                parent[cell] = cell;
                count++;
                for (int[] d : dirs) {
                    int x = r + d[0], y = c + d[1];
                    if (x < 0 || x >= m || y < 0 || y >= n || parent[x * n + y] == -1) continue;
                    int a = find(parent, cell), b = find(parent, x * n + y);
                    if (a != b) { parent[a] = b; count--; }
                }
            }
            out[i] = count;
        }
        return out;
    }
}
