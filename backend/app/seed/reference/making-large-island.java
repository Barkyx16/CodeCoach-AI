import java.util.*;

class Solution {
    public int largestIsland(int[][] grid) {
        int n = grid.length, id = 2;
        int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
        Map<Integer, Integer> sizes = new HashMap<>();
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++) {
                if (grid[i][j] != 1) continue;
                int size = 0;
                Deque<int[]> stack = new ArrayDeque<>();
                stack.push(new int[] {i, j});
                grid[i][j] = id;
                while (!stack.isEmpty()) {
                    int[] p = stack.pop();
                    size++;
                    for (int[] d : dirs) {
                        int x = p[0] + d[0], y = p[1] + d[1];
                        if (x >= 0 && x < n && y >= 0 && y < n && grid[x][y] == 1) { grid[x][y] = id; stack.push(new int[] {x, y}); }
                    }
                }
                sizes.put(id++, size);
            }
        int best = 0;
        for (int s : sizes.values()) best = Math.max(best, s);
        for (int i = 0; i < n; i++)
            for (int j = 0; j < n; j++) {
                if (grid[i][j] != 0) continue;
                Set<Integer> ids = new HashSet<>();
                for (int[] d : dirs) {
                    int x = i + d[0], y = j + d[1];
                    if (x >= 0 && x < n && y >= 0 && y < n && grid[x][y] > 1) ids.add(grid[x][y]);
                }
                int total = 1;
                for (int k : ids) total += sizes.get(k);
                best = Math.max(best, total);
            }
        return best;
    }
}
