"""Medium problems, part 3: graphs, grids, backtracking and simulation."""

from itertools import combinations, permutations, product

from scripts.problembank import P, grid, word


def _char_grid(r, rows_lo=1, rows_hi=5, cols_lo=1, cols_hi=6, chars="1100"):
    m, n = r.randint(rows_lo, rows_hi), r.randint(cols_lo, cols_hi)
    return ["".join(r.choice(chars) for _ in range(n)) for _ in range(m)]


def _components(cells, neighbors):
    seen, count = set(), 0
    for c in cells:
        if c in seen:
            continue
        count += 1
        stack = [c]
        seen.add(c)
        while stack:
            x = stack.pop()
            for y in neighbors(x):
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
    return count


def _islands(grid):
    land = {(i, j) for i, row in enumerate(grid) for j, ch in enumerate(row) if ch == "1"}
    return _components(
        sorted(land),
        lambda p: [
            q for q in ((p[0] + 1, p[1]), (p[0] - 1, p[1]), (p[0], p[1] + 1), (p[0], p[1] - 1)) if q in land
        ],
    )


def _edges(r, n, m_hi):
    pairs = list(combinations(range(n), 2))
    return [list(e) for e in r.sample(pairs, min(len(pairs), r.randint(0, m_hi)))]


def _fewest_squares(n):
    best = [0] + [n] * n
    for i in range(1, n + 1):
        best[i] = 1 + min(best[i - s * s] for s in range(1, int(i**0.5) + 2) if s * s <= i)
    return best[n]


def _comp_count(n, edges):
    adj = {i: [] for i in range(n)}
    for a, b in edges:
        adj[a].append(b)
        adj[b].append(a)
    return _components(range(n), lambda x: adj[x])


P(
    slug="number-of-islands",
    title="Number of Islands",
    difficulty="medium",
    topics=["graphs", "matrix"],
    summary="Count groups of connected land cells.",
    statement="""
        `grid` is a list of rows made of `'1'` (land) and `'0'` (water). Land cells connect up, down, left
        and right. Return the number of islands (connected groups of land).
    """,
    constraints=["1 <= rows, cols <= 300"],
    sig="int numIslands(String[] grid)",
    hints=[
        "Each time you find land you haven't visited, you've found a new island.",
        "From that cell, flood-fill (DFS or BFS) to mark the whole island as visited.",
        "count = 0\nfor each cell:\n    if land and not visited:\n        count += 1\n        flood fill from it marking visited\nreturn count",
        "Every cell is visited a constant number of times: O(rows × cols). Use an explicit stack or BFS queue to avoid deep recursion on big grids.",
    ],
    time="O(m n)",
    space="O(m n)",
    model=_islands,
    java="""
        import java.util.*;

        class Solution {
            public int numIslands(String[] grid) {
                int m = grid.length, n = grid[0].length(), count = 0;
                boolean[][] seen = new boolean[m][n];
                int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
                for (int i = 0; i < m; i++)
                    for (int j = 0; j < n; j++) {
                        if (grid[i].charAt(j) != '1' || seen[i][j]) continue;
                        count++;
                        Deque<int[]> stack = new ArrayDeque<>();
                        stack.push(new int[] {i, j});
                        seen[i][j] = true;
                        while (!stack.isEmpty()) {
                            int[] p = stack.pop();
                            for (int[] d : dirs) {
                                int r = p[0] + d[0], c = p[1] + d[1];
                                if (r >= 0 && r < m && c >= 0 && c < n && !seen[r][c] && grid[r].charAt(c) == '1') {
                                    seen[r][c] = true;
                                    stack.push(new int[] {r, c});
                                }
                            }
                        }
                    }
                return count;
            }
        }
    """,
    tests=[
        {"grid": ["11110", "11010", "11000", "00000"]},
        {"grid": ["11000", "11000", "00100", "00011"]},
        {"grid": ["0"]},
        {"grid": ["101", "010", "101"]},
    ],
    gen=lambda r: {"grid": _char_grid(r)},
)

P(
    slug="rotting-oranges",
    title="Rotting Oranges",
    difficulty="medium",
    topics=["graphs", "matrix"],
    summary="Minutes until every orange is rotten, spreading each minute.",
    statement="""
        In `grid`, `0` is empty, `1` is a fresh orange and `2` is a rotten one. Every minute, fresh oranges next
        to a rotten one (up/down/left/right) become rotten. Return the minutes until no fresh orange remains,
        or `-1` if that's impossible.
    """,
    constraints=["1 <= rows, cols <= 10"],
    sig="int orangesRotting(int[][] grid)",
    hints=[
        "Rot spreads from all rotten oranges at once.",
        "Multi-source BFS: start the queue with every rotten orange and process it minute by minute (level by level).",
        "queue = all rotten cells; fresh = count of fresh\nminutes = 0\nwhile queue and fresh:\n    for each cell in this level:\n"
        "        rot fresh neighbors, fresh -= 1, enqueue them\n    minutes += 1\nreturn minutes if fresh == 0 else -1",
        "BFS levels are minutes. Each cell is enqueued at most once: O(rows × cols).",
    ],
    time="O(m n)",
    space="O(m n)",
    model=lambda grid: (lambda f: f(f, [row[:] for row in grid], 0))(
        lambda f, g, t: (
            t
            if not any(1 in row for row in g)
            else -1
            if not any(
                g[i][j] == 1
                and any(
                    0 <= i + a < len(g) and 0 <= j + b < len(g[0]) and g[i + a][j + b] == 2
                    for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))
                )
                for i in range(len(g))
                for j in range(len(g[0]))
            )
            else f(
                f,
                [
                    [
                        2
                        if g[i][j] == 2
                        or (
                            g[i][j] == 1
                            and any(
                                0 <= i + a < len(g) and 0 <= j + b < len(g[0]) and g[i + a][j + b] == 2
                                for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))
                            )
                        )
                        else g[i][j]
                        for j in range(len(g[0]))
                    ]
                    for i in range(len(g))
                ],
                t + 1,
            )
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            public int orangesRotting(int[][] grid) {
                int m = grid.length, n = grid[0].length, fresh = 0, minutes = 0;
                Deque<int[]> queue = new ArrayDeque<>();
                for (int i = 0; i < m; i++)
                    for (int j = 0; j < n; j++) {
                        if (grid[i][j] == 2) queue.add(new int[] {i, j});
                        else if (grid[i][j] == 1) fresh++;
                    }
                int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
                while (!queue.isEmpty() && fresh > 0) {
                    for (int k = queue.size(); k > 0; k--) {
                        int[] p = queue.poll();
                        for (int[] d : dirs) {
                            int r = p[0] + d[0], c = p[1] + d[1];
                            if (r >= 0 && r < m && c >= 0 && c < n && grid[r][c] == 1) {
                                grid[r][c] = 2;
                                fresh--;
                                queue.add(new int[] {r, c});
                            }
                        }
                    }
                    minutes++;
                }
                return fresh == 0 ? minutes : -1;
            }
        }
    """,
    tests=[
        {"grid": [[2, 1, 1], [1, 1, 0], [0, 1, 1]]},
        {"grid": [[2, 1, 1], [0, 1, 1], [1, 0, 1]]},
        {"grid": [[0, 2]]},
        {"grid": [[1]]},
    ],
    gen=lambda r: {"grid": grid(r, r.randint(1, 4), r.randint(1, 4), 0, 2)},
)

P(
    slug="course-schedule",
    title="Can You Finish Every Course?",
    difficulty="medium",
    topics=["graphs", "topological-sort"],
    summary="Detect whether prerequisites contain a cycle.",
    statement="""
        There are `n` courses labeled `0..n-1`. Each pair `[a, b]` in `prereqs` means you must take `b` before
        `a`. Return `true` if it's possible to finish all courses.
    """,
    constraints=["1 <= n <= 2000", "0 <= prereqs.length <= 5000"],
    sig="boolean canFinish(int n, int[][] prereqs)",
    hints=[
        "When is it impossible? Think about requirements that loop back on themselves.",
        "Kahn's algorithm: repeatedly take a course with no remaining prerequisites. If you take all n, there's no cycle.",
        "indegree, adj = build from prereqs\nqueue = courses with indegree 0\ntaken = 0\nwhile queue:\n    c = pop; taken += 1\n"
        "    for nxt in adj[c]:\n        indegree[nxt] -= 1\n        if indegree[nxt] == 0: push nxt\nreturn taken == n",
        "Topological sort in O(n + edges). Courses stuck in a cycle never reach indegree 0.",
    ],
    time="O(n + e)",
    space="O(n + e)",
    model=lambda n, prereqs: (lambda f: f(f, set(range(n))))(
        lambda f, left: (
            not left
            or (lambda free: bool(free) and f(f, left - free))(
                {c for c in left if not any(a == c and b in left for a, b in prereqs)}
            )
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            public boolean canFinish(int n, int[][] prereqs) {
                List<List<Integer>> adj = new ArrayList<>();
                for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
                int[] indegree = new int[n];
                for (int[] p : prereqs) { adj.get(p[1]).add(p[0]); indegree[p[0]]++; }
                Deque<Integer> queue = new ArrayDeque<>();
                for (int i = 0; i < n; i++) if (indegree[i] == 0) queue.add(i);
                int taken = 0;
                while (!queue.isEmpty()) {
                    int c = queue.poll();
                    taken++;
                    for (int next : adj.get(c)) if (--indegree[next] == 0) queue.add(next);
                }
                return taken == n;
            }
        }
    """,
    tests=[
        {"n": 2, "prereqs": [[1, 0]]},
        {"n": 2, "prereqs": [[1, 0], [0, 1]]},
        {"n": 3, "prereqs": []},
        {"n": 4, "prereqs": [[1, 0], [2, 1], [3, 2], [1, 3]]},
    ],
    gen=lambda r: (
        lambda n: {
            "n": n,
            "prereqs": [
                list(p)
                for p in r.sample(
                    [(a, b) for a in range(n) for b in range(n) if a != b],
                    min(n * (n - 1), r.randint(0, n + 1)),
                )
            ],
        }
    )(r.randint(1, 6)),
)

P(
    slug="pacific-atlantic",
    title="Water Flowing to Both Oceans",
    difficulty="medium",
    topics=["graphs", "matrix"],
    summary="Which cells can drain into both oceans?",
    statement="""
        `heights` is an island. The Pacific touches the top and left edges; the Atlantic touches the bottom
        and right edges. Water flows from a cell to a neighbor (up/down/left/right) of equal or lower height.
        Return the cells `[r, c]` from which water can reach both oceans, sorted by row then column.
    """,
    constraints=["1 <= rows, cols <= 200"],
    sig="int[][] pacificAtlantic(int[][] heights)",
    hints=[
        "Instead of flowing down from every cell, think backwards from the oceans.",
        "From each ocean's edge cells, walk uphill (to neighbors at least as high). Cells reached from both oceans are the answer.",
        "pac = reachable going uphill from top and left edges\natl = reachable going uphill from bottom and right edges\n"
        "return sorted(pac ∩ atl)",
        "Two graph searches, each O(rows × cols), instead of one search per cell.",
    ],
    time="O(m n)",
    space="O(m n)",
    model=lambda heights: (
        lambda m, n: (
            lambda reach: sorted(
                [
                    list(c)
                    for c in reach(lambda i, j: i == 0 or j == 0)
                    & reach(lambda i, j: i == m - 1 or j == n - 1)
                ]
            )
        )(
            lambda edge: (lambda f: f(f, {(i, j) for i in range(m) for j in range(n) if edge(i, j)}))(
                lambda f, s: (lambda grown: s if grown == s else f(f, grown))(
                    s
                    | {
                        (i + a, j + b)
                        for i, j in s
                        for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))
                        if 0 <= i + a < m and 0 <= j + b < n and heights[i + a][j + b] >= heights[i][j]
                    }
                )
            )
        )
    )(len(heights), len(heights[0])),
    java="""
        import java.util.*;

        class Solution {
            private void climb(int[][] h, boolean[][] seen, Deque<int[]> stack) {
                int m = h.length, n = h[0].length;
                int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
                while (!stack.isEmpty()) {
                    int[] p = stack.pop();
                    for (int[] d : dirs) {
                        int r = p[0] + d[0], c = p[1] + d[1];
                        if (r >= 0 && r < m && c >= 0 && c < n && !seen[r][c] && h[r][c] >= h[p[0]][p[1]]) {
                            seen[r][c] = true;
                            stack.push(new int[] {r, c});
                        }
                    }
                }
            }
            public int[][] pacificAtlantic(int[][] heights) {
                int m = heights.length, n = heights[0].length;
                boolean[][] pac = new boolean[m][n], atl = new boolean[m][n];
                Deque<int[]> ps = new ArrayDeque<>(), as = new ArrayDeque<>();
                for (int i = 0; i < m; i++)
                    for (int j = 0; j < n; j++) {
                        if (i == 0 || j == 0) { pac[i][j] = true; ps.push(new int[] {i, j}); }
                        if (i == m - 1 || j == n - 1) { atl[i][j] = true; as.push(new int[] {i, j}); }
                    }
                climb(heights, pac, ps);
                climb(heights, atl, as);
                List<int[]> out = new ArrayList<>();
                for (int i = 0; i < m; i++) for (int j = 0; j < n; j++) if (pac[i][j] && atl[i][j]) out.add(new int[] {i, j});
                return out.toArray(new int[0][]);
            }
        }
    """,
    tests=[
        {"heights": [[1, 2, 2, 3, 5], [3, 2, 3, 4, 4], [2, 4, 5, 3, 1], [6, 7, 1, 4, 5], [5, 1, 1, 2, 4]]},
        {"heights": [[1]]},
        {"heights": [[3, 3], [3, 3]]},
    ],
    gen=lambda r: {"heights": grid(r, r.randint(1, 4), r.randint(1, 4), 0, 5)},
)

P(
    slug="surrounded-regions",
    title="Capture Surrounded Regions",
    difficulty="medium",
    topics=["graphs", "matrix"],
    summary="Flip every 'O' region that doesn't touch the border.",
    statement="""
        `board` rows contain `'X'` and `'O'`. Replace every `'O'` that is not connected (up/down/left/right)
        to an `'O'` on the border with `'X'`. Return the resulting board.
    """,
    constraints=["1 <= rows, cols <= 200"],
    sig="String[] solve(String[] board)",
    hints=[
        "Which O's survive? Think from the edges inward.",
        "Flood-fill from every border O to mark the safe ones; everything else becomes X.",
        "safe = flood fill from all border 'O' cells\nfor each cell: 'O' if in safe else 'X'",
        "One flood fill over the grid: O(rows × cols).",
    ],
    time="O(m n)",
    space="O(m n)",
    model=lambda board: (
        lambda m, n: (
            lambda cells: (
                lambda f: (
                    lambda safe: ["".join("O" if (i, j) in safe else "X" for j in range(n)) for i in range(m)]
                )(f(f, {c for c in cells if c[0] in (0, m - 1) or c[1] in (0, n - 1)}))
            )(
                lambda f, s: (lambda g: s if g == s else f(f, g))(
                    s
                    | {
                        (i + a, j + b)
                        for i, j in s
                        for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))
                        if (i + a, j + b) in cells
                    }
                )
            )
        )({(i, j) for i in range(m) for j in range(n) if board[i][j] == "O"})
    )(len(board), len(board[0])),
    java="""
        import java.util.*;

        class Solution {
            public String[] solve(String[] board) {
                int m = board.length, n = board[0].length();
                boolean[][] safe = new boolean[m][n];
                Deque<int[]> stack = new ArrayDeque<>();
                for (int i = 0; i < m; i++)
                    for (int j = 0; j < n; j++)
                        if ((i == 0 || j == 0 || i == m - 1 || j == n - 1) && board[i].charAt(j) == 'O') {
                            safe[i][j] = true;
                            stack.push(new int[] {i, j});
                        }
                int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
                while (!stack.isEmpty()) {
                    int[] p = stack.pop();
                    for (int[] d : dirs) {
                        int r = p[0] + d[0], c = p[1] + d[1];
                        if (r >= 0 && r < m && c >= 0 && c < n && !safe[r][c] && board[r].charAt(c) == 'O') {
                            safe[r][c] = true;
                            stack.push(new int[] {r, c});
                        }
                    }
                }
                String[] out = new String[m];
                for (int i = 0; i < m; i++) {
                    StringBuilder sb = new StringBuilder();
                    for (int j = 0; j < n; j++) sb.append(safe[i][j] ? 'O' : 'X');
                    out[i] = sb.toString();
                }
                return out;
            }
        }
    """,
    tests=[{"board": ["XXXX", "XOOX", "XXOX", "XOXX"]}, {"board": ["X"]}, {"board": ["OOO", "OXO", "OOO"]}],
    gen=lambda r: {"board": _char_grid(r, 1, 5, 1, 5, "XXO")},
)

P(
    slug="word-search",
    title="Word Search in a Grid",
    difficulty="medium",
    topics=["backtracking", "matrix"],
    summary="Can a word be traced through adjacent letters?",
    statement="""
        Return `true` if `word` can be built from letters of `board` by moving between cells that share an
        edge, using each cell at most once.
    """,
    constraints=["1 <= rows, cols <= 6", "1 <= word.length <= 15"],
    sig="boolean exist(String[] board, String word)",
    hints=[
        "Try starting from every cell that matches the first letter.",
        "Depth-first search with backtracking: mark a cell as used, explore the four neighbors for the next letter, then unmark it.",
        "def dfs(r, c, k):\n    if k == len(word): return true\n    if out of bounds or used or board[r][c] != word[k]: return false\n"
        "    mark used\n    found = any(dfs(nr, nc, k+1) for each neighbor)\n    unmark\n    return found",
        "Worst case O(cells × 3^L) for a word of length L, since each step has at most three new directions. Unmarking on the way back is what lets other paths reuse the cell.",
    ],
    time="O(m n 3^L)",
    space="O(L)",
    model=lambda board, word: any(
        (lambda f: f(f, i, j, 0, frozenset()))(
            lambda f, r, c, k, used: (
                k == len(word)
                or (
                    0 <= r < len(board)
                    and 0 <= c < len(board[0])
                    and (r, c) not in used
                    and board[r][c] == word[k]
                    and any(
                        f(f, r + a, c + b, k + 1, used | {(r, c)})
                        for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))
                    )
                )
            )
        )
        for i in range(len(board))
        for j in range(len(board[0]))
    ),
    java="""
        class Solution {
            private boolean dfs(char[][] g, String word, int r, int c, int k) {
                if (k == word.length()) return true;
                if (r < 0 || c < 0 || r >= g.length || c >= g[0].length || g[r][c] != word.charAt(k)) return false;
                char saved = g[r][c];
                g[r][c] = '#';
                boolean found = dfs(g, word, r + 1, c, k + 1) || dfs(g, word, r - 1, c, k + 1)
                    || dfs(g, word, r, c + 1, k + 1) || dfs(g, word, r, c - 1, k + 1);
                g[r][c] = saved;
                return found;
            }
            public boolean exist(String[] board, String word) {
                char[][] g = new char[board.length][];
                for (int i = 0; i < board.length; i++) g[i] = board[i].toCharArray();
                for (int i = 0; i < g.length; i++)
                    for (int j = 0; j < g[0].length; j++) if (dfs(g, word, i, j, 0)) return true;
                return false;
            }
        }
    """,
    tests=[
        {"board": ["ABCE", "SFCS", "ADEE"], "word": "ABCCED"},
        {"board": ["ABCE", "SFCS", "ADEE"], "word": "SEE"},
        {"board": ["ABCE", "SFCS", "ADEE"], "word": "ABCB"},
        {"board": ["A"], "word": "A"},
    ],
    gen=lambda r: {"board": _char_grid(r, 1, 3, 1, 4, "ABC"), "word": word(r, 1, 4, "ABC")},
)

P(
    slug="all-permutations",
    title="All Permutations",
    difficulty="medium",
    topics=["backtracking", "recursion"],
    summary="List every ordering of distinct numbers.",
    statement="""
        `nums` has distinct values. Return all permutations, in lexicographic (dictionary) order.
    """,
    constraints=["1 <= nums.length <= 6", "distinct values"],
    sig="int[][] permute(int[] nums)",
    hints=[
        "Build a permutation one position at a time.",
        "Sort first. At each position, try every unused value in increasing order, recurse, then undo.",
        "sort nums\ndef build(path, used):\n    if len(path) == n: out.append(copy of path); return\n"
        "    for i in 0..n-1:\n        if not used[i]: use i; path.append(nums[i]); build(...); undo\nbuild([], [false]*n)",
        "Backtracking generates n! permutations at O(n) each: O(n · n!). Trying values in sorted order yields lexicographic output.",
    ],
    time="O(n · n!)",
    space="O(n)",
    model=lambda nums: [list(p) for p in permutations(sorted(nums))],
    java="""
        import java.util.*;

        class Solution {
            private void build(int[] nums, boolean[] used, List<Integer> path, List<int[]> out) {
                if (path.size() == nums.length) { out.add(path.stream().mapToInt(Integer::intValue).toArray()); return; }
                for (int i = 0; i < nums.length; i++) {
                    if (used[i]) continue;
                    used[i] = true;
                    path.add(nums[i]);
                    build(nums, used, path, out);
                    path.remove(path.size() - 1);
                    used[i] = false;
                }
            }
            public int[][] permute(int[] nums) {
                Arrays.sort(nums);
                List<int[]> out = new ArrayList<>();
                build(nums, new boolean[nums.length], new ArrayList<>(), out);
                return out.toArray(new int[0][]);
            }
        }
    """,
    tests=[{"nums": [1, 2, 3]}, {"nums": [0, 1]}, {"nums": [1]}, {"nums": [3, -1, 2]}],
    gen=lambda r: {"nums": r.sample(range(-5, 6), r.randint(1, 4))},
)

P(
    slug="all-subsets",
    title="All Subsets",
    difficulty="medium",
    topics=["backtracking", "bit-manipulation"],
    summary="List every subset of distinct numbers.",
    statement="""
        `nums` has distinct values. Return every subset. Each subset lists its values in ascending order; sort
        the subsets by size, then lexicographically. The empty subset comes first.
    """,
    constraints=["1 <= nums.length <= 10", "distinct values"],
    sig="int[][] subsets(int[] nums)",
    hints=[
        "Each value is either in or out, so there are 2^n subsets.",
        "Generate them with backtracking or by counting from 0 to 2^n - 1 and using bits; then sort as required.",
        "sort nums\nsubsets = [[nums[i] for i in range(n) if mask >> i & 1] for mask in range(2**n)]\nsort subsets by (len, values)\nreturn subsets",
        "There are 2^n subsets of size up to n, so O(n · 2^n). The required order needs a comparator: length first, then element by element.",
    ],
    time="O(n · 2^n)",
    space="O(n · 2^n)",
    model=lambda nums: [list(c) for k in range(len(nums) + 1) for c in combinations(sorted(nums), k)],
    java="""
        import java.util.*;

        class Solution {
            public int[][] subsets(int[] nums) {
                Arrays.sort(nums);
                int n = nums.length;
                List<int[]> out = new ArrayList<>();
                for (int mask = 0; mask < (1 << n); mask++) {
                    int[] s = new int[Integer.bitCount(mask)];
                    int w = 0;
                    for (int i = 0; i < n; i++) if ((mask >> i & 1) == 1) s[w++] = nums[i];
                    out.add(s);
                }
                out.sort((a, b) -> {
                    if (a.length != b.length) return a.length - b.length;
                    for (int i = 0; i < a.length; i++) if (a[i] != b[i]) return Integer.compare(a[i], b[i]);
                    return 0;
                });
                return out.toArray(new int[0][]);
            }
        }
    """,
    tests=[{"nums": [1, 2, 3]}, {"nums": [0]}, {"nums": [4, -1]}],
    gen=lambda r: {"nums": r.sample(range(-9, 10), r.randint(1, 5))},
)

P(
    slug="combination-sum",
    title="Combination Sum",
    difficulty="medium",
    topics=["backtracking"],
    summary="All combinations of candidates (reusable) that sum to a target.",
    statement="""
        `candidates` are distinct positive integers. Return every combination (values may repeat) that sums to
        `target`. Each combination is in ascending order, and the list of combinations is in lexicographic order.
    """,
    constraints=["1 <= candidates.length <= 30", "2 <= candidates[i] <= 40", "1 <= target <= 40"],
    sig="int[][] combinationSum(int[] candidates, int target)",
    hints=[
        "To avoid counting [2,3] and [3,2] separately, only ever add values in non-decreasing order.",
        "Sort, then backtrack from a start index: you may reuse the current value or move to a later one.",
        "sort candidates\ndef build(start, remaining, path):\n    if remaining == 0: record path\n"
        "    for i in start..n-1:\n        if candidates[i] > remaining: break\n        build(i, remaining - candidates[i], path + [candidates[i]])",
        "Passing `i` (not `i + 1`) allows reuse; breaking early on a too-large value prunes the search. Output is exponential in the worst case.",
    ],
    time="O(answer size)",
    space="O(target)",
    model=lambda candidates, target: sorted(
        [
            list(c)
            for k in range(1, target // min(candidates) + 1)
            for c in __import__("itertools").combinations_with_replacement(sorted(candidates), k)
            if sum(c) == target
        ]
    ),
    java="""
        import java.util.*;

        class Solution {
            private void build(int[] c, int start, int remaining, Deque<Integer> path, List<int[]> out) {
                if (remaining == 0) { out.add(path.stream().mapToInt(Integer::intValue).toArray()); return; }
                for (int i = start; i < c.length && c[i] <= remaining; i++) {
                    path.addLast(c[i]);
                    build(c, i, remaining - c[i], path, out);
                    path.removeLast();
                }
            }
            public int[][] combinationSum(int[] candidates, int target) {
                Arrays.sort(candidates);
                List<int[]> out = new ArrayList<>();
                build(candidates, 0, target, new ArrayDeque<>(), out);
                return out.toArray(new int[0][]);
            }
        }
    """,
    tests=[
        {"candidates": [2, 3, 6, 7], "target": 7},
        {"candidates": [2, 3, 5], "target": 8},
        {"candidates": [2], "target": 1},
    ],
    gen=lambda r: {"candidates": r.sample(range(2, 9), r.randint(1, 4)), "target": r.randint(1, 16)},
)

P(
    slug="generate-parentheses",
    title="Generate Balanced Parentheses",
    difficulty="medium",
    topics=["backtracking", "strings"],
    summary="All strings of n pairs of balanced parentheses.",
    statement="""
        Return every well-formed string of `n` pairs of parentheses, in lexicographic order (`'('` comes before `')'`).
    """,
    constraints=["1 <= n <= 8"],
    sig="String[] generateParenthesis(int n)",
    hints=[
        "When is adding a `)` allowed?",
        "Track how many `(` and `)` you've used: add `(` while you have some left; add `)` only if it doesn't exceed the opens.",
        "def build(s, open, close):\n    if len(s) == 2n: record s\n    if open < n: build(s + '(', open + 1, close)\n    if close < open: build(s + ')', open, close + 1)",
        "Only valid prefixes are ever built, and trying `(` first produces lexicographic order. The count is the Catalan number.",
    ],
    time="O(4^n / sqrt(n))",
    space="O(n)",
    model=lambda n: sorted(
        s
        for s in ("".join(p) for p in product("()", repeat=2 * n))
        if all(s[:i].count("(") >= s[:i].count(")") for i in range(2 * n + 1)) and s.count("(") == n
    ),
    java="""
        import java.util.*;

        class Solution {
            private void build(String s, int open, int close, int n, List<String> out) {
                if (s.length() == 2 * n) { out.add(s); return; }
                if (open < n) build(s + "(", open + 1, close, n, out);
                if (close < open) build(s + ")", open, close + 1, n, out);
            }
            public String[] generateParenthesis(int n) {
                List<String> out = new ArrayList<>();
                build("", 0, 0, n, out);
                return out.toArray(new String[0]);
            }
        }
    """,
    tests=[{"n": 3}, {"n": 1}, {"n": 2}, {"n": 4}, {"n": 5}, {"n": 6}],
)

P(
    slug="phone-letter-combinations",
    title="Phone Keypad Letter Combinations",
    difficulty="medium",
    topics=["backtracking", "strings"],
    summary="Every word a digit string could spell on a phone keypad.",
    statement="""
        On a phone keypad, 2=abc, 3=def, 4=ghi, 5=jkl, 6=mno, 7=pqrs, 8=tuv, 9=wxyz. Return every letter
        string `digits` could represent, in lexicographic order. Return an empty list for an empty input.
    """,
    constraints=["0 <= digits.length <= 4", "digits in 2-9"],
    sig="String[] letterCombinations(String digits)",
    hints=[
        "Each digit multiplies the number of results by its letter count.",
        "Build results digit by digit: extend each partial string with each letter of the next digit.",
        "if not digits: return []\nresults = ['']\nfor d in digits:\n    results = [r + c for r in results for c in letters[d]]\nreturn results",
        "Up to 4^n results of length n: O(n · 4^n). Extending in keypad order keeps results lexicographic.",
    ],
    time="O(n · 4^n)",
    space="O(n · 4^n)",
    model=lambda digits: (
        []
        if not digits
        else [
            "".join(p)
            for p in product(
                *[
                    {
                        "2": "abc",
                        "3": "def",
                        "4": "ghi",
                        "5": "jkl",
                        "6": "mno",
                        "7": "pqrs",
                        "8": "tuv",
                        "9": "wxyz",
                    }[d]
                    for d in digits
                ]
            )
        ]
    ),
    java="""
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
    """,
    tests=[{"digits": "23"}, {"digits": ""}, {"digits": "2"}, {"digits": "79"}],
    gen=lambda r: {"digits": word(r, 1, 3, "23456789")},
)

P(
    slug="count-provinces",
    title="Count Provinces",
    difficulty="medium",
    topics=["graphs", "union-find"],
    summary="Count groups of directly or indirectly connected cities.",
    statement="""
        `isConnected[i][j]` is `1` if cities `i` and `j` are directly connected (the matrix is symmetric with
        1s on the diagonal). A province is a group of cities connected directly or through other cities.
        Return the number of provinces.
    """,
    constraints=["1 <= n <= 200"],
    sig="int findCircleNum(int[][] isConnected)",
    hints=[
        "This is counting connected components in a graph given as an adjacency matrix.",
        "Union-find: union every connected pair, then count distinct roots. DFS from each unvisited city also works.",
        "parent = list(range(n))\nfor i, j with isConnected[i][j]: union(i, j)\nreturn number of i with find(i) == i",
        "Reading the matrix is O(n^2); union-find with path compression is near-constant per operation.",
    ],
    time="O(n^2)",
    space="O(n)",
    model=lambda isConnected: _components(
        range(len(isConnected)), lambda i: [j for j in range(len(isConnected)) if isConnected[i][j]]
    ),
    java="""
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
    """,
    tests=[
        {"isConnected": [[1, 1, 0], [1, 1, 0], [0, 0, 1]]},
        {"isConnected": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]},
        {"isConnected": [[1]]},
    ],
    gen=lambda r: (
        lambda n, edges: {
            "isConnected": [
                [1 if i == j or [min(i, j), max(i, j)] in edges else 0 for j in range(n)] for i in range(n)
            ]
        }
    )(*(lambda n: (n, _edges(r, n, n)))(r.randint(1, 6))),
)

P(
    slug="redundant-connection",
    title="Redundant Connection",
    difficulty="medium",
    topics=["graphs", "union-find"],
    summary="Find the edge whose removal turns the graph back into a tree.",
    statement="""
        A tree with nodes `1..n` had one extra edge added, giving `n` edges in `edges`. Return the edge that
        can be removed to leave a tree. If several work, return the one that appears last in `edges`.
    """,
    constraints=["3 <= n <= 1000", "edges[i] = [a, b] with a < b"],
    sig="int[] findRedundantConnection(int[][] edges)",
    hints=[
        "Add edges one at a time. Which edge is the first to create a cycle?",
        "With union-find, an edge whose endpoints already share a root closes a cycle. That's the answer.",
        "parent = list(range(n + 1))\nfor a, b in edges:\n    if find(a) == find(b): return [a, b]\n    union(a, b)",
        "The first edge that closes the cycle is also the last cycle edge in input order, which is what's asked. Near O(n).",
    ],
    time="O(n α(n))",
    space="O(n)",
    model=lambda edges: next(
        edges[i]
        for i in range(len(edges) - 1, -1, -1)
        if _comp_count(len(edges) + 1, edges[:i] + edges[i + 1 :]) == 2
    ),
    java="""
        class Solution {
            private int find(int[] parent, int x) {
                while (parent[x] != x) { parent[x] = parent[parent[x]]; x = parent[x]; }
                return x;
            }
            public int[] findRedundantConnection(int[][] edges) {
                int[] parent = new int[edges.length + 1];
                for (int i = 0; i < parent.length; i++) parent[i] = i;
                for (int[] e : edges) {
                    int a = find(parent, e[0]), b = find(parent, e[1]);
                    if (a == b) return e;
                    parent[a] = b;
                }
                return new int[0];
            }
        }
    """,
    tests=[
        {"edges": [[1, 2], [1, 3], [2, 3]]},
        {"edges": [[1, 2], [2, 3], [3, 4], [1, 4], [1, 5]]},
        {"edges": [[1, 2], [2, 3], [1, 3]]},
    ],
    gen=lambda r: (
        lambda n: (
            lambda tree: (lambda extra: {"edges": r.sample(tree + [extra], n)})(
                r.choice([list(e) for e in combinations(range(1, n + 1), 2) if list(e) not in tree])
            )
        )([sorted([i, r.randint(1, i - 1)]) for i in range(2, n + 1)])
    )(r.randint(3, 7)),
)

P(
    slug="connected-components",
    title="Connected Components in a Graph",
    difficulty="medium",
    topics=["graphs", "union-find"],
    summary="Count the connected pieces of an undirected graph.",
    statement="""
        A graph has `n` nodes `0..n-1` and undirected `edges`. Return the number of connected components.
    """,
    constraints=["1 <= n <= 2000", "0 <= edges.length <= 5000"],
    sig="int countComponents(int n, int[][] edges)",
    hints=[
        "Start with every node alone, then merge.",
        "Union-find: each edge that joins two different components reduces the count by one.",
        "count = n\nfor a, b in edges:\n    if find(a) != find(b): union(a, b); count -= 1\nreturn count",
        "Union-find with path compression is near-linear: O(n + e). BFS/DFS also works in O(n + e).",
    ],
    time="O(n + e)",
    space="O(n)",
    model=lambda n, edges: _comp_count(n, edges),
    java="""
        class Solution {
            private int find(int[] parent, int x) {
                while (parent[x] != x) { parent[x] = parent[parent[x]]; x = parent[x]; }
                return x;
            }
            public int countComponents(int n, int[][] edges) {
                int[] parent = new int[n];
                for (int i = 0; i < n; i++) parent[i] = i;
                int count = n;
                for (int[] e : edges) {
                    int a = find(parent, e[0]), b = find(parent, e[1]);
                    if (a != b) { parent[a] = b; count--; }
                }
                return count;
            }
        }
    """,
    tests=[
        {"n": 5, "edges": [[0, 1], [1, 2], [3, 4]]},
        {"n": 5, "edges": [[0, 1], [1, 2], [2, 3], [3, 4]]},
        {"n": 3, "edges": []},
    ],
    gen=lambda r: (lambda n: {"n": n, "edges": _edges(r, n, n)})(r.randint(1, 8)),
)

P(
    slug="graph-valid-tree",
    title="Is the Graph a Tree?",
    difficulty="medium",
    topics=["graphs", "union-find"],
    summary="Check that an undirected graph is connected and has no cycles.",
    statement="""
        Given `n` nodes `0..n-1` and undirected `edges`, return `true` if the edges form a valid tree:
        connected and without cycles.
    """,
    constraints=["1 <= n <= 2000", "no duplicate edges or self-loops"],
    sig="boolean validTree(int n, int[][] edges)",
    hints=[
        "A tree with n nodes has exactly n - 1 edges.",
        "Check the edge count, then make sure no edge joins two nodes that are already connected.",
        "if len(edges) != n - 1: return false\nfor a, b in edges:\n    if find(a) == find(b): return false\n    union(a, b)\nreturn true",
        "With exactly n - 1 edges, having no cycle implies connectivity. Union-find makes it near O(n).",
    ],
    time="O(n α(n))",
    space="O(n)",
    model=lambda n, edges: len(edges) == n - 1 and _comp_count(n, edges) == 1,
    java="""
        class Solution {
            private int find(int[] parent, int x) {
                while (parent[x] != x) { parent[x] = parent[parent[x]]; x = parent[x]; }
                return x;
            }
            public boolean validTree(int n, int[][] edges) {
                if (edges.length != n - 1) return false;
                int[] parent = new int[n];
                for (int i = 0; i < n; i++) parent[i] = i;
                for (int[] e : edges) {
                    int a = find(parent, e[0]), b = find(parent, e[1]);
                    if (a == b) return false;
                    parent[a] = b;
                }
                return true;
            }
        }
    """,
    tests=[
        {"n": 5, "edges": [[0, 1], [0, 2], [0, 3], [1, 4]]},
        {"n": 5, "edges": [[0, 1], [1, 2], [2, 3], [1, 3], [1, 4]]},
        {"n": 1, "edges": []},
        {"n": 4, "edges": [[0, 1], [2, 3], [0, 2]]},
    ],
    gen=lambda r: (lambda n: {"n": n, "edges": _edges(r, n, n)})(r.randint(1, 6)),
)

P(
    slug="shortest-path-binary-grid",
    title="Shortest Clear Path in a Grid",
    difficulty="medium",
    topics=["graphs", "matrix"],
    summary="Fewest cells on a path of 0s, moving in 8 directions.",
    statement="""
        In the square binary `grid`, return the number of cells on the shortest path of `0` cells from the
        top-left to the bottom-right, moving in any of the 8 directions. Return `-1` if there's no such path.
    """,
    constraints=["1 <= n <= 100"],
    sig="int shortestPathBinaryMatrix(int[][] grid)",
    hints=[
        "All moves cost the same, so which search finds the fewest steps?",
        "Breadth-first search from the top-left, counting path length in cells, exploring all 8 neighbors.",
        "if grid[0][0] or grid[n-1][n-1]: return -1\nqueue = [(0, 0, 1)]\nmark (0,0)\nwhile queue:\n    r, c, d = pop front\n"
        "    if (r, c) is the goal: return d\n    for 8 neighbors that are 0 and unmarked: mark, push (nr, nc, d + 1)\nreturn -1",
        "BFS visits each cell once: O(n^2). Marking cells when you enqueue them (not when you pop them) avoids duplicates.",
    ],
    time="O(n^2)",
    space="O(n^2)",
    model=lambda grid: (
        lambda n: (
            -1
            if grid[0][0] or grid[n - 1][n - 1]
            else (lambda f: f(f, {(0, 0)}, {(0, 0)}, 1))(
                lambda f, frontier, seen, d: (
                    d
                    if (n - 1, n - 1) in frontier
                    else -1
                    if not frontier
                    else (lambda nxt: f(f, nxt, seen | nxt, d + 1))(
                        {
                            (r + a, c + b)
                            for r, c in frontier
                            for a in (-1, 0, 1)
                            for b in (-1, 0, 1)
                            if 0 <= r + a < n
                            and 0 <= c + b < n
                            and not grid[r + a][c + b]
                            and (r + a, c + b) not in seen
                        }
                    )
                )
            )
        )
    )(len(grid)),
    java="""
        import java.util.*;

        class Solution {
            public int shortestPathBinaryMatrix(int[][] grid) {
                int n = grid.length;
                if (grid[0][0] == 1 || grid[n - 1][n - 1] == 1) return -1;
                boolean[][] seen = new boolean[n][n];
                Deque<int[]> queue = new ArrayDeque<>();
                queue.add(new int[] {0, 0, 1});
                seen[0][0] = true;
                while (!queue.isEmpty()) {
                    int[] p = queue.poll();
                    if (p[0] == n - 1 && p[1] == n - 1) return p[2];
                    for (int a = -1; a <= 1; a++)
                        for (int b = -1; b <= 1; b++) {
                            int r = p[0] + a, c = p[1] + b;
                            if (r >= 0 && r < n && c >= 0 && c < n && !seen[r][c] && grid[r][c] == 0) {
                                seen[r][c] = true;
                                queue.add(new int[] {r, c, p[2] + 1});
                            }
                        }
                }
                return -1;
            }
        }
    """,
    tests=[
        {"grid": [[0, 1], [1, 0]]},
        {"grid": [[0, 0, 0], [1, 1, 0], [1, 1, 0]]},
        {"grid": [[1, 0, 0], [1, 1, 0], [1, 1, 0]]},
        {"grid": [[0]]},
    ],
    gen=lambda r: (lambda n: {"grid": [[1 if r.random() < 0.3 else 0 for _ in range(n)] for _ in range(n)]})(
        r.randint(1, 5)
    ),
)

P(
    slug="open-the-lock",
    title="Open the Combination Lock",
    difficulty="medium",
    topics=["graphs", "strings"],
    summary="Fewest wheel turns to reach a code while avoiding dead ends.",
    statement="""
        A lock has 4 wheels showing digits, starting at `"0000"`. One move turns one wheel one step up or down
        (9 wraps to 0 and back). Codes in `deadends` lock you out. Return the fewest moves to reach `target`,
        or `-1` if it's impossible.
    """,
    constraints=["0 <= deadends.length <= 500", "target is not a deadend"],
    sig="int openLock(String[] deadends, String target)",
    hints=[
        "Each code is a node with 8 neighbors (4 wheels × up or down).",
        'Breadth-first search from "0000", never entering a deadend. If "0000" is itself a deadend, the answer is -1.',
        "if '0000' in dead: return -1\nqueue = [('0000', 0)]\nseen = {'0000'}\nwhile queue:\n    code, d = pop front\n"
        "    if code == target: return d\n    for each of the 8 neighbors not in dead or seen: add to seen, push (nb, d + 1)\nreturn -1",
        "There are only 10^4 codes, so BFS is O(10^4 × 8) at most.",
    ],
    time="O(10^4)",
    space="O(10^4)",
    model=lambda deadends, target: (
        lambda dead: (
            -1
            if "0000" in dead
            else (lambda f: f(f, {"0000"}, {"0000"}, 0))(
                lambda f, frontier, seen, d: (
                    d
                    if target in frontier
                    else -1
                    if not frontier
                    else (lambda nxt: f(f, nxt, seen | nxt, d + 1))(
                        {
                            c[:i] + str((int(c[i]) + s) % 10) + c[i + 1 :]
                            for c in frontier
                            for i in range(4)
                            for s in (1, -1)
                        }
                        - seen
                        - dead
                    )
                )
            )
        )
    )(set(deadends)),
    java="""
        import java.util.*;

        class Solution {
            public int openLock(String[] deadends, String target) {
                Set<String> dead = new HashSet<>(Arrays.asList(deadends));
                if (dead.contains("0000")) return -1;
                Set<String> seen = new HashSet<>(List.of("0000"));
                Deque<String> queue = new ArrayDeque<>(List.of("0000"));
                for (int d = 0; !queue.isEmpty(); d++) {
                    for (int k = queue.size(); k > 0; k--) {
                        String code = queue.poll();
                        if (code.equals(target)) return d;
                        char[] c = code.toCharArray();
                        for (int i = 0; i < 4; i++)
                            for (int s : new int[] {1, 9}) {
                                char saved = c[i];
                                c[i] = (char) ('0' + (saved - '0' + s) % 10);
                                String next = new String(c);
                                c[i] = saved;
                                if (!dead.contains(next) && seen.add(next)) queue.add(next);
                            }
                    }
                }
                return -1;
            }
        }
    """,
    tests=[
        {"deadends": ["0201", "0101", "0102", "1212", "2002"], "target": "0202"},
        {"deadends": ["8888"], "target": "0009"},
        {"deadends": ["8887", "8889", "8878", "8898", "8788", "8988", "7888", "9888"], "target": "8888"},
        {"deadends": ["0000"], "target": "8888"},
    ],
    gen=lambda r: {
        "deadends": [word(r, 4, 4, "0123") for _ in range(r.randint(0, 6))],
        "target": word(r, 4, 4, "0129"),
    },
    gen_count=3,
)

P(
    slug="is-graph-bipartite",
    title="Is the Graph Two-Colorable?",
    difficulty="medium",
    topics=["graphs"],
    summary="Can nodes be split into two groups with every edge crossing between them?",
    statement="""
        `graph[i]` lists the neighbors of node `i` in an undirected graph (it may be disconnected). Return
        `true` if the nodes can be split into two sets so that every edge connects nodes from different sets.
    """,
    constraints=["1 <= n <= 100", "no self-loops, symmetric adjacency"],
    sig="boolean isBipartite(int[][] graph)",
    hints=[
        "Try to color the graph with two colors so neighbors always differ.",
        "BFS or DFS from every uncolored node, giving each neighbor the opposite color. A clash means it's not bipartite.",
        "color = [None]*n\nfor start in range(n):\n    if color[start] is None:\n        color[start] = 0; queue = [start]\n"
        "        while queue:\n            u = pop\n            for v in graph[u]:\n                if color[v] is None: color[v] = 1 - color[u]; push v\n"
        "                elif color[v] == color[u]: return false\nreturn true",
        "O(n + e). Starting a search from every uncolored node handles disconnected graphs.",
    ],
    time="O(n + e)",
    space="O(n)",
    model=lambda graph: any(
        all(mask >> u & 1 != mask >> v & 1 for u in range(len(graph)) for v in graph[u])
        for mask in range(1 << len(graph))
    ),
    java="""
        import java.util.*;

        class Solution {
            public boolean isBipartite(int[][] graph) {
                int n = graph.length;
                int[] color = new int[n];
                Arrays.fill(color, -1);
                for (int s = 0; s < n; s++) {
                    if (color[s] != -1) continue;
                    color[s] = 0;
                    Deque<Integer> queue = new ArrayDeque<>(List.of(s));
                    while (!queue.isEmpty()) {
                        int u = queue.poll();
                        for (int v : graph[u]) {
                            if (color[v] == -1) { color[v] = 1 - color[u]; queue.add(v); }
                            else if (color[v] == color[u]) return false;
                        }
                    }
                }
                return true;
            }
        }
    """,
    tests=[
        {"graph": [[1, 2, 3], [0, 2], [0, 1, 3], [0, 2]]},
        {"graph": [[1, 3], [0, 2], [1, 3], [0, 2]]},
        {"graph": [[]]},
        {"graph": [[1], [0], [3], [2]]},
    ],
    gen=lambda r: (
        lambda n, edges: {
            "graph": [
                sorted([b for a, b in edges if a == i] + [a for a, b in edges if b == i]) for i in range(n)
            ]
        }
    )(*(lambda n: (n, _edges(r, n, n)))(r.randint(1, 7))),
)

P(
    slug="keys-and-rooms",
    title="Visit Every Room",
    difficulty="medium",
    topics=["graphs"],
    summary="Rooms contain keys to other rooms. Can you open them all?",
    statement="""
        Room 0 is unlocked; every other room is locked. `rooms[i]` lists the keys found in room `i` (key `k`
        opens room `k`). Return `true` if you can visit every room.
    """,
    constraints=["2 <= n <= 1000", "0 <= keys <= n - 1"],
    sig="boolean canVisitAllRooms(int[][] rooms)",
    hints=[
        "Keys are directed edges from a room to the rooms they open.",
        "Search from room 0 (DFS or BFS), following keys, and count the rooms you reach.",
        "seen = {0}\nstack = [0]\nwhile stack:\n    for k in rooms[stack.pop()]:\n        if k not in seen: seen.add(k); stack.append(k)\nreturn len(seen) == n",
        "A graph search over rooms and keys: O(n + total keys).",
    ],
    time="O(n + k)",
    space="O(n)",
    model=lambda rooms: (lambda f: len(f(f, {0})) == len(rooms))(
        lambda f, s: (lambda g: s if g == s else f(f, g))(s | {k for i in s for k in rooms[i]})
    ),
    java="""
        import java.util.*;

        class Solution {
            public boolean canVisitAllRooms(int[][] rooms) {
                boolean[] seen = new boolean[rooms.length];
                seen[0] = true;
                int count = 1;
                Deque<Integer> stack = new ArrayDeque<>(List.of(0));
                while (!stack.isEmpty())
                    for (int k : rooms[stack.pop()])
                        if (!seen[k]) { seen[k] = true; count++; stack.push(k); }
                return count == rooms.length;
            }
        }
    """,
    tests=[{"rooms": [[1], [2], [3], []]}, {"rooms": [[1, 3], [3, 0, 1], [2], [0]]}, {"rooms": [[1], []]}],
    gen=lambda r: (lambda n: {"rooms": [r.sample(range(n), r.randint(0, 2)) for _ in range(n)]})(
        r.randint(2, 6)
    ),
)

P(
    slug="all-paths-in-dag",
    title="All Paths From Source to Target",
    difficulty="medium",
    topics=["graphs", "backtracking"],
    summary="List every path from node 0 to the last node of a DAG.",
    statement="""
        `graph[i]` lists the nodes you can go to from node `i` in a directed acyclic graph with nodes `0..n-1`.
        Return every path from `0` to `n - 1`, in lexicographic order.
    """,
    constraints=["2 <= n <= 15", "the graph is acyclic"],
    sig="int[][] allPathsSourceTarget(int[][] graph)",
    hints=[
        "No cycles means you can explore paths without tracking visited nodes.",
        "Depth-first search from node 0, extending the current path; record it when you reach `n - 1`. Sort at the end.",
        "def dfs(u, path):\n    if u == n - 1: out.append(path)\n    for v in graph[u]: dfs(v, path + [v])\ndfs(0, [0])\nreturn sorted(out)",
        "The output can be exponential in n; the search does work proportional to the paths found.",
    ],
    time="O(2^n · n)",
    space="O(n)",
    model=lambda graph: sorted(
        (lambda f: f(f, 0))(
            lambda f, u: [[u]] if u == len(graph) - 1 else [[u] + p for v in graph[u] for p in f(f, v)]
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            private void dfs(int[][] g, int u, Deque<Integer> path, List<int[]> out) {
                if (u == g.length - 1) { out.add(path.stream().mapToInt(Integer::intValue).toArray()); return; }
                for (int v : g[u]) { path.addLast(v); dfs(g, v, path, out); path.removeLast(); }
            }
            public int[][] allPathsSourceTarget(int[][] graph) {
                List<int[]> out = new ArrayList<>();
                Deque<Integer> path = new ArrayDeque<>(List.of(0));
                dfs(graph, 0, path, out);
                out.sort(Arrays::compare);
                return out.toArray(new int[0][]);
            }
        }
    """,
    tests=[
        {"graph": [[1, 2], [3], [3], []]},
        {"graph": [[4, 3, 1], [3, 2, 4], [3], [4], []]},
        {"graph": [[1], []]},
    ],
    gen=lambda r: (
        lambda n: {
            "graph": [
                sorted(r.sample(range(i + 1, n), r.randint(0, min(3, n - i - 1)))) if i < n - 1 else []
                for i in range(n)
            ]
        }
    )(r.randint(2, 6)),
)

P(
    slug="rotate-image",
    title="Rotate an Image",
    difficulty="medium",
    topics=["matrix"],
    summary="Rotate a square matrix 90 degrees clockwise.",
    statement="""
        Return the square matrix `matrix` rotated 90 degrees clockwise. Try to do it in place.
    """,
    constraints=["1 <= n <= 20"],
    sig="int[][] rotate(int[][] matrix)",
    hints=[
        "Where does the top row end up after a clockwise turn?",
        "Transpose the matrix (swap across the main diagonal), then reverse each row.",
        "for i in range(n):\n    for j in range(i + 1, n): swap matrix[i][j], matrix[j][i]\nfor row in matrix: reverse row\nreturn matrix",
        "Two in-place passes, O(n^2) time and O(1) extra space.",
    ],
    time="O(n^2)",
    space="O(1)",
    model=lambda matrix: [list(row) for row in zip(*matrix[::-1], strict=True)],
    java="""
        class Solution {
            public int[][] rotate(int[][] matrix) {
                int n = matrix.length;
                for (int i = 0; i < n; i++)
                    for (int j = i + 1; j < n; j++) { int t = matrix[i][j]; matrix[i][j] = matrix[j][i]; matrix[j][i] = t; }
                for (int[] row : matrix)
                    for (int i = 0, j = n - 1; i < j; i++, j--) { int t = row[i]; row[i] = row[j]; row[j] = t; }
                return matrix;
            }
        }
    """,
    tests=[
        {"matrix": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]},
        {"matrix": [[5, 1, 9, 11], [2, 4, 8, 10], [13, 3, 6, 7], [15, 14, 12, 16]]},
        {"matrix": [[1]]},
    ],
    gen=lambda r: (lambda n: {"matrix": grid(r, n, n, 0, 9)})(r.randint(1, 5)),
)

P(
    slug="spiral-order",
    title="Spiral Order",
    difficulty="medium",
    topics=["matrix", "simulation"],
    summary="Read a matrix in clockwise spiral order.",
    statement="""
        Return all values of `matrix` in clockwise spiral order, starting at the top-left.
    """,
    constraints=["1 <= rows, cols <= 10"],
    sig="int[] spiralOrder(int[][] matrix)",
    hints=[
        "Peel the matrix layer by layer.",
        "Keep four boundaries (top, bottom, left, right). Walk right, down, left, up, shrinking a boundary after each side.",
        "top, bottom, left, right = 0, m-1, 0, n-1\nwhile top <= bottom and left <= right:\n    walk top row; top += 1\n    walk right col; right -= 1\n"
        "    if top <= bottom: walk bottom row backwards; bottom -= 1\n    if left <= right: walk left col upwards; left += 1",
        "Each value is read once: O(m n). The two `if` checks stop a single remaining row or column from being read twice.",
    ],
    time="O(m n)",
    space="O(1)",
    model=lambda matrix: (lambda f: f(f, [row[:] for row in matrix]))(
        lambda f, m: (
            []
            if not m or not m[0]
            else m[0] + f(f, [list(r) for r in zip(*m[1:], strict=False)][::-1])
            if m[1:]
            else list(m[0])
        )
    ),
    java="""
        class Solution {
            public int[] spiralOrder(int[][] matrix) {
                int m = matrix.length, n = matrix[0].length, w = 0;
                int[] out = new int[m * n];
                int top = 0, bottom = m - 1, left = 0, right = n - 1;
                while (top <= bottom && left <= right) {
                    for (int j = left; j <= right; j++) out[w++] = matrix[top][j];
                    top++;
                    for (int i = top; i <= bottom; i++) out[w++] = matrix[i][right];
                    right--;
                    if (top <= bottom) { for (int j = right; j >= left; j--) out[w++] = matrix[bottom][j]; bottom--; }
                    if (left <= right) { for (int i = bottom; i >= top; i--) out[w++] = matrix[i][left]; left++; }
                }
                return out;
            }
        }
    """,
    tests=[
        {"matrix": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]},
        {"matrix": [[1, 2, 3, 4], [5, 6, 7, 8], [9, 10, 11, 12]]},
        {"matrix": [[1], [2], [3]]},
    ],
    gen=lambda r: {"matrix": grid(r, r.randint(1, 5), r.randint(1, 5), 0, 20)},
)

P(
    slug="set-matrix-zeroes",
    title="Set Matrix Zeroes",
    difficulty="medium",
    topics=["matrix"],
    summary="Zero out every row and column that contains a zero.",
    statement="""
        If a cell of `matrix` is `0`, set its entire row and column to `0`. Base the decision on the original
        zeros only. Return the matrix. Try for O(1) extra space.
    """,
    constraints=["1 <= rows, cols <= 200"],
    sig="int[][] setZeroes(int[][] matrix)",
    hints=[
        "Record which rows and columns to clear before changing anything.",
        "For O(1) space, use the first row and first column as the markers, with two flags for whether they themselves need clearing.",
        "rows, cols = rows containing 0, cols containing 0\nfor i, j: if i in rows or j in cols: matrix[i][j] = 0\nreturn matrix",
        "Two passes, O(m n) time. Storing markers in the first row/column brings extra space down to O(1).",
    ],
    time="O(m n)",
    space="O(1)",
    model=lambda matrix: (
        lambda rows, cols: [
            [0 if i in rows or j in cols else v for j, v in enumerate(row)] for i, row in enumerate(matrix)
        ]
    )(
        {i for i, row in enumerate(matrix) if 0 in row},
        {j for row in matrix for j, v in enumerate(row) if v == 0},
    ),
    java="""
        class Solution {
            public int[][] setZeroes(int[][] matrix) {
                int m = matrix.length, n = matrix[0].length;
                boolean firstRow = false, firstCol = false;
                for (int j = 0; j < n; j++) if (matrix[0][j] == 0) firstRow = true;
                for (int i = 0; i < m; i++) if (matrix[i][0] == 0) firstCol = true;
                for (int i = 1; i < m; i++)
                    for (int j = 1; j < n; j++) if (matrix[i][j] == 0) { matrix[i][0] = 0; matrix[0][j] = 0; }
                for (int i = 1; i < m; i++)
                    for (int j = 1; j < n; j++) if (matrix[i][0] == 0 || matrix[0][j] == 0) matrix[i][j] = 0;
                if (firstRow) for (int j = 0; j < n; j++) matrix[0][j] = 0;
                if (firstCol) for (int i = 0; i < m; i++) matrix[i][0] = 0;
                return matrix;
            }
        }
    """,
    tests=[
        {"matrix": [[1, 1, 1], [1, 0, 1], [1, 1, 1]]},
        {"matrix": [[0, 1, 2, 0], [3, 4, 5, 2], [1, 3, 1, 5]]},
        {"matrix": [[5]]},
    ],
    gen=lambda r: {"matrix": grid(r, r.randint(1, 5), r.randint(1, 5), 0, 4)},
)

P(
    slug="game-of-life-step",
    title="Game of Life: Next Step",
    difficulty="medium",
    topics=["matrix", "simulation"],
    summary="Compute one generation of Conway's Game of Life.",
    statement="""
        Each cell of `board` is alive (`1`) or dead (`0`). Using the 8 neighbors of each cell, all at once:
        a live cell with 2 or 3 live neighbors survives; a dead cell with exactly 3 live neighbors comes alive;
        every other cell is dead. Return the next board.
    """,
    constraints=["1 <= rows, cols <= 25"],
    sig="int[][] gameOfLife(int[][] board)",
    hints=[
        "All cells update at the same time, so don't let updated cells affect their neighbors' counts.",
        "Either write into a new board, or encode the transition in place (e.g. 2 = was alive, now dead).",
        "next = copy\nfor each cell:\n    live = count live among 8 neighbors in the ORIGINAL board\n"
        "    next[cell] = 1 if live == 3 or (board[cell] and live == 2) else 0\nreturn next",
        "O(m n × 8) time. The in-place encoding trick makes it O(1) extra space.",
    ],
    time="O(m n)",
    space="O(m n)",
    model=lambda board: [
        [
            1
            if (lambda live: live == 3 or (board[i][j] and live == 2))(
                sum(
                    board[i + a][j + b]
                    for a in (-1, 0, 1)
                    for b in (-1, 0, 1)
                    if (a or b) and 0 <= i + a < len(board) and 0 <= j + b < len(board[0])
                )
            )
            else 0
            for j in range(len(board[0]))
        ]
        for i in range(len(board))
    ],
    java="""
        class Solution {
            public int[][] gameOfLife(int[][] board) {
                int m = board.length, n = board[0].length;
                int[][] next = new int[m][n];
                for (int i = 0; i < m; i++)
                    for (int j = 0; j < n; j++) {
                        int live = 0;
                        for (int a = -1; a <= 1; a++)
                            for (int b = -1; b <= 1; b++)
                                if ((a != 0 || b != 0) && i + a >= 0 && i + a < m && j + b >= 0 && j + b < n) live += board[i + a][j + b];
                        next[i][j] = live == 3 || (board[i][j] == 1 && live == 2) ? 1 : 0;
                    }
                return next;
            }
        }
    """,
    tests=[
        {"board": [[0, 1, 0], [0, 0, 1], [1, 1, 1], [0, 0, 0]]},
        {"board": [[1, 1], [1, 0]]},
        {"board": [[1]]},
    ],
    gen=lambda r: {"board": grid(r, r.randint(1, 5), r.randint(1, 5), 0, 1)},
)

P(
    slug="valid-sudoku",
    title="Valid Sudoku Board",
    difficulty="medium",
    topics=["hash-sets", "matrix"],
    summary="Check a partly filled Sudoku for repeated digits.",
    statement="""
        `board` has 9 strings of 9 characters each: digits `1-9` or `.` for empty. Return `true` if no digit
        repeats within any row, any column, or any of the nine 3×3 boxes. (The board doesn't need to be solvable.)
    """,
    constraints=["board is 9 x 9"],
    sig="boolean isValidSudoku(String[] board)",
    hints=[
        "There are 27 groups to check: 9 rows, 9 columns and 9 boxes.",
        "Keep a seen-set for each group; cell (r, c) belongs to box `(r / 3) * 3 + c / 3`.",
        "for r, c with a digit d:\n    if d in rows[r] or d in cols[c] or d in boxes[box(r, c)]: return false\n    add d to all three\nreturn true",
        "One pass over 81 cells with constant-size sets: O(1) for a fixed board size.",
    ],
    time="O(1)",
    space="O(1)",
    model=lambda board: all(
        len(g) == len(set(g))
        for g in [
            *[[ch for ch in row if ch != "."] for row in board],
            *[[board[i][j] for i in range(9) if board[i][j] != "."] for j in range(9)],
            *[
                [board[i][j] for i in range(bi, bi + 3) for j in range(bj, bj + 3) if board[i][j] != "."]
                for bi in (0, 3, 6)
                for bj in (0, 3, 6)
            ],
        ]
    ),
    java="""
        class Solution {
            public boolean isValidSudoku(String[] board) {
                boolean[][] rows = new boolean[9][10], cols = new boolean[9][10], boxes = new boolean[9][10];
                for (int r = 0; r < 9; r++)
                    for (int c = 0; c < 9; c++) {
                        char ch = board[r].charAt(c);
                        if (ch == '.') continue;
                        int d = ch - '0', b = (r / 3) * 3 + c / 3;
                        if (rows[r][d] || cols[c][d] || boxes[b][d]) return false;
                        rows[r][d] = cols[c][d] = boxes[b][d] = true;
                    }
                return true;
            }
        }
    """,
    tests=[
        {
            "board": [
                "53..7....",
                "6..195...",
                ".98....6.",
                "8...6...3",
                "4..8.3..1",
                "7...2...6",
                ".6....28.",
                "...419..5",
                "....8..79",
            ]
        },
        {
            "board": [
                "83..7....",
                "6..195...",
                ".98....6.",
                "8...6...3",
                "4..8.3..1",
                "7...2...6",
                ".6....28.",
                "...419..5",
                "....8..79",
            ]
        },
        {"board": ["........."] * 9},
    ],
    gen=lambda r: {"board": ["".join(r.choice("123456789" + "." * 12) for _ in range(9)) for _ in range(9)]},
)

P(
    slug="integer-to-roman",
    title="Integer to Roman Numerals",
    difficulty="medium",
    topics=["strings", "math", "greedy"],
    summary="Write a number in Roman numerals.",
    statement="""
        Convert `num` to a Roman numeral using I, V, X, L, C, D, M and the six subtractive forms
        (IV, IX, XL, XC, CD, CM).
    """,
    constraints=["1 <= num <= 3999"],
    sig="String intToRoman(int num)",
    hints=[
        "Write the largest symbol that fits, then repeat with what's left.",
        "Include the subtractive pairs as their own symbols: 1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1.",
        "for value, symbol in table (largest first):\n    while num >= value: out += symbol; num -= value\nreturn out",
        "Greedy over 13 symbols: O(1) for numbers below 4000.",
    ],
    time="O(1)",
    space="O(1)",
    model=lambda num: "".join(
        ["", "M", "MM", "MMM"][num // 1000]
        + ["", "C", "CC", "CCC", "CD", "D", "DC", "DCC", "DCCC", "CM"][num // 100 % 10]
        + ["", "X", "XX", "XXX", "XL", "L", "LX", "LXX", "LXXX", "XC"][num // 10 % 10]
        + ["", "I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX"][num % 10]
    ),
    java="""
        class Solution {
            public String intToRoman(int num) {
                int[] values = {1000, 900, 500, 400, 100, 90, 50, 40, 10, 9, 5, 4, 1};
                String[] symbols = {"M", "CM", "D", "CD", "C", "XC", "L", "XL", "X", "IX", "V", "IV", "I"};
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < values.length; i++)
                    while (num >= values[i]) { sb.append(symbols[i]); num -= values[i]; }
                return sb.toString();
            }
        }
    """,
    tests=[{"num": 3749}, {"num": 58}, {"num": 1994}, {"num": 4}, {"num": 3999}],
    gen=lambda r: {"num": r.randint(1, 3999)},
)

P(
    slug="multiply-strings",
    title="Multiply Two Number Strings",
    difficulty="medium",
    topics=["strings", "math"],
    summary="Multiply big numbers given as strings, without BigInteger.",
    statement="""
        `a` and `b` are non-negative integers as strings (no leading zeros except `"0"`). Return their product as
        a string. Don't convert the inputs to built-in big-number types.
    """,
    constraints=["1 <= a.length, b.length <= 200"],
    sig="String multiply(String a, String b)",
    hints=[
        "Do long multiplication like on paper.",
        "Digit `a[i]` times digit `b[j]` lands at positions `i + j` and `i + j + 1` of an array of length n + m.",
        "res = [0]*(n + m)\nfor i from n-1 down to 0:\n    for j from m-1 down to 0:\n        total = a[i]*b[j] + res[i+j+1]\n"
        "        res[i+j+1] = total % 10\n        res[i+j] += total // 10\nstrip leading zeros\nreturn result or '0'",
        "O(n m) digit products with a position array that handles carries as it goes.",
    ],
    time="O(n m)",
    space="O(n + m)",
    model=lambda a, b: str(int(a) * int(b)),
    java="""
        class Solution {
            public String multiply(String a, String b) {
                int n = a.length(), m = b.length();
                int[] res = new int[n + m];
                for (int i = n - 1; i >= 0; i--)
                    for (int j = m - 1; j >= 0; j--) {
                        int total = (a.charAt(i) - '0') * (b.charAt(j) - '0') + res[i + j + 1];
                        res[i + j + 1] = total % 10;
                        res[i + j] += total / 10;
                    }
                StringBuilder sb = new StringBuilder();
                for (int d : res) if (sb.length() > 0 || d != 0) sb.append(d);
                return sb.length() == 0 ? "0" : sb.toString();
            }
        }
    """,
    tests=[
        {"a": "2", "b": "3"},
        {"a": "123", "b": "456"},
        {"a": "0", "b": "9999"},
        {"a": "99999999999999999999", "b": "99999999999999999999"},
    ],
    gen=lambda r: {"a": str(r.randint(0, 10**25)), "b": str(r.randint(0, 10**25))},
)

P(
    slug="lru-cache",
    title="Simulate an LRU Cache",
    difficulty="medium",
    topics=["hash-maps", "simulation"],
    summary="Run get/put operations on a least-recently-used cache.",
    statement="""
        Simulate an LRU cache holding at most `capacity` keys. Each operation in `ops` is `"put K V"` (insert or
        update key K with value V) or `"get K"`. `get` returns the value, or `-1` if absent, and both operations
        mark the key as most recently used. When a put would exceed capacity, evict the least recently used key
        first. Return the results of the `get` operations, in order.
    """,
    constraints=["1 <= capacity <= 100", "1 <= ops.length <= 10^4"],
    sig="int[] lruCache(int capacity, String[] ops)",
    hints=[
        'You need fast lookup and fast "move to most recent".',
        "A hash map plus a doubly linked list does both in O(1). In Java, `LinkedHashMap` with access order is exactly this.",
        "cache = ordered map\nfor op in ops:\n    if get: if key in cache: move to end; record value else record -1\n"
        "    if put: insert/update and move to end; if size > capacity: remove the first (oldest) key",
        "Every operation is O(1). Updating an existing key also counts as a use.",
    ],
    time="O(1) per op",
    space="O(capacity)",
    model=lambda capacity, ops: (
        lambda od, out: (
            [
                (
                    (
                        lambda parts: (
                            (od.move_to_end(int(parts[1])), out.append(od[int(parts[1])]))
                            if parts[0] == "get" and int(parts[1]) in od
                            else out.append(-1)
                            if parts[0] == "get"
                            else (
                                od.__setitem__(int(parts[1]), int(parts[2])),
                                od.move_to_end(int(parts[1])),
                                od.popitem(last=False) if len(od) > capacity else None,
                            )
                        )
                    )(op.split())
                )
                for op in ops
            ]
            and out
        )
    )(__import__("collections").OrderedDict(), []),
    java="""
        import java.util.*;

        class Solution {
            public int[] lruCache(int capacity, String[] ops) {
                LinkedHashMap<Integer, Integer> cache = new LinkedHashMap<>(16, 0.75f, true);
                List<Integer> out = new ArrayList<>();
                for (String op : ops) {
                    String[] p = op.split(" ");
                    int key = Integer.parseInt(p[1]);
                    if (p[0].equals("get")) out.add(cache.getOrDefault(key, -1));
                    else {
                        cache.put(key, Integer.parseInt(p[2]));
                        if (cache.size() > capacity) cache.remove(cache.keySet().iterator().next());
                    }
                }
                return out.stream().mapToInt(Integer::intValue).toArray();
            }
        }
    """,
    tests=[
        {
            "capacity": 2,
            "ops": ["put 1 1", "put 2 2", "get 1", "put 3 3", "get 2", "put 4 4", "get 1", "get 3", "get 4"],
        },
        {"capacity": 1, "ops": ["put 2 1", "get 2", "put 3 2", "get 2", "get 3"]},
        {"capacity": 2, "ops": ["put 1 1", "put 1 5", "get 1", "put 2 2", "put 3 3", "get 1"]},
    ],
    gen=lambda r: {
        "capacity": r.randint(1, 3),
        "ops": [
            r.choice([f"put {r.randint(1, 4)} {r.randint(0, 9)}", f"get {r.randint(1, 4)}"])
            for _ in range(r.randint(1, 12))
        ],
    },
)

P(
    slug="perfect-squares",
    title="Fewest Perfect Squares",
    difficulty="medium",
    topics=["dynamic-programming", "math"],
    summary="Smallest number of square numbers that add up to n.",
    statement="""
        Return the fewest perfect squares (1, 4, 9, 16, ...) that add up to `n`.
    """,
    constraints=["1 <= n <= 10^4"],
    sig="int numSquares(int n)",
    hints=[
        "The best answer for n builds on the best answer for something smaller.",
        "best[i] = 1 + min(best[i - s]) over squares `s <= i`.",
        "best = [0] + [inf]*n\nfor i in 1..n:\n    for each square s <= i: best[i] = min(best[i], best[i - s] + 1)\nreturn best[n]",
        "O(n sqrt(n)) DP. (Number theory says the answer is always at most 4, which allows a faster check.)",
    ],
    time="O(n sqrt(n))",
    space="O(n)",
    model=lambda n: _fewest_squares(n),
    java="""
        import java.util.*;

        class Solution {
            public int numSquares(int n) {
                int[] best = new int[n + 1];
                Arrays.fill(best, Integer.MAX_VALUE);
                best[0] = 0;
                for (int i = 1; i <= n; i++)
                    for (int s = 1; s * s <= i; s++) best[i] = Math.min(best[i], best[i - s * s] + 1);
                return best[n];
            }
        }
    """,
    tests=[{"n": 12}, {"n": 13}, {"n": 1}, {"n": 7}, {"n": 9999}],
    gen=lambda r: {"n": r.randint(1, 400)},
)

P(
    slug="maximal-square",
    title="Largest Square of Ones",
    difficulty="medium",
    topics=["dynamic-programming", "matrix"],
    summary="Area of the biggest all-'1' square in a binary matrix.",
    statement="""
        `matrix` rows are strings of `'0'` and `'1'`. Return the area of the largest square containing only `'1'`s.
    """,
    constraints=["1 <= rows, cols <= 300"],
    sig="int maximalSquare(String[] matrix)",
    hints=[
        "Think about the largest square whose bottom-right corner is a given cell.",
        "side[r][c] = 1 + min(side[r-1][c], side[r][c-1], side[r-1][c-1]) when the cell is '1', else 0.",
        "best = 0\nfor r, c:\n    if matrix[r][c] == '1':\n        side[r][c] = 1 + min(up, left, diagonal)\n        best = max(best, side[r][c])\nreturn best * best",
        "Each cell is computed once from three neighbors: O(m n) time, O(n) space with a rolling row.",
    ],
    time="O(m n)",
    space="O(n)",
    model=lambda matrix: max(
        [0]
        + [
            k * k
            for i in range(len(matrix))
            for j in range(len(matrix[0]))
            for k in range(1, min(len(matrix) - i, len(matrix[0]) - j) + 1)
            if all(matrix[a][b] == "1" for a in range(i, i + k) for b in range(j, j + k))
        ]
    ),
    java="""
        class Solution {
            public int maximalSquare(String[] matrix) {
                int m = matrix.length, n = matrix[0].length(), best = 0;
                int[][] side = new int[m + 1][n + 1];
                for (int r = 1; r <= m; r++)
                    for (int c = 1; c <= n; c++)
                        if (matrix[r - 1].charAt(c - 1) == '1') {
                            side[r][c] = 1 + Math.min(side[r - 1][c - 1], Math.min(side[r - 1][c], side[r][c - 1]));
                            best = Math.max(best, side[r][c]);
                        }
                return best * best;
            }
        }
    """,
    tests=[
        {"matrix": ["10100", "10111", "11111", "10010"]},
        {"matrix": ["01", "10"]},
        {"matrix": ["0"]},
        {"matrix": ["111", "111", "111"]},
    ],
    gen=lambda r: {"matrix": _char_grid(r, 1, 5, 1, 5, "1110")},
)
