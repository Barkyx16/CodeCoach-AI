"""Hard problems, part 2: graphs and grids."""

import heapq
from functools import lru_cache
from itertools import combinations, permutations

from scripts.problembank import P, grid, word

DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _dijkstra(n, adj, src):
    dist = [float("inf")] * n
    dist[src] = 0
    pq = [(0, src)]
    while pq:
        d, u = heapq.heappop(pq)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            if d + w < dist[v]:
                dist[v] = d + w
                heapq.heappush(pq, (dist[v], v))
    return dist


def _connected(n, edges):
    adj = {i: set() for i in range(n)}
    for a, b in edges:
        adj[a].add(b)
        adj[b].add(a)
    seen, stack = {0}, [0]
    while stack:
        for v in adj[stack.pop()]:
            if v not in seen:
                seen.add(v)
                stack.append(v)
    return len(seen)


def _connected_graph(r, n, extra):
    edges = [sorted([i, r.randint(0, i - 1)]) for i in range(1, n)]
    others = [list(e) for e in combinations(range(n), 2) if list(e) not in edges]
    return edges + r.sample(others, min(extra, len(others)))


def _islands_after_flip(grid):
    g = grid
    n = len(g)

    def largest(h):
        best, seen = 0, set()
        for i in range(n):
            for j in range(n):
                if h[i][j] and (i, j) not in seen:
                    size, stack = 0, [(i, j)]
                    seen.add((i, j))
                    while stack:
                        a, b = stack.pop()
                        size += 1
                        for da, db in DIRS:
                            x, y = a + da, b + db
                            if 0 <= x < n and 0 <= y < n and h[x][y] and (x, y) not in seen:
                                seen.add((x, y))
                                stack.append((x, y))
                    best = max(best, size)
        return best

    best = largest(g)
    for i in range(n):
        for j in range(n):
            if not g[i][j]:
                h = [row[:] for row in g]
                h[i][j] = 1
                best = max(best, largest(h))
    return best


def _bfs_states(start, is_goal, neighbors):
    frontier, seen, d = [start], {start}, 0
    while frontier:
        if any(is_goal(s) for s in frontier):
            return d
        nxt = []
        for s in frontier:
            for t in neighbors(s):
                if t not in seen:
                    seen.add(t)
                    nxt.append(t)
        frontier, d = nxt, d + 1
    return -1


P(
    slug="network-delay-time",
    title="Network Signal Delay",
    difficulty="hard",
    topics=["graphs", "heaps"],
    summary="How long until a signal reaches every node?",
    statement="""
        `times[i] = [u, v, w]` is a directed edge from node `u` to node `v` taking `w` time. Nodes are `1..n`.
        A signal starts at node `k`. Return the time until all nodes have received it, or `-1` if some never do.
    """,
    constraints=["1 <= n <= 100", "1 <= times.length <= 6000", "0 <= w <= 100"],
    sig="int networkDelayTime(int[][] times, int n, int k)",
    hints=[
        "Each node receives the signal at its shortest-path distance from k.",
        "Run Dijkstra's algorithm from k; the answer is the largest distance, or -1 if any node is unreachable.",
        "dist = {k: 0}\npq = [(0, k)]\nwhile pq:\n    d, u = pop min\n    if d > dist[u]: continue\n    for v, w in adj[u]: relax\nreturn max(dist) if all reached else -1",
        "Dijkstra with a binary heap: O(E log V). Skipping stale heap entries keeps it correct without a decrease-key operation.",
    ],
    time="O(E log V)",
    space="O(V + E)",
    model=lambda times, n, k: (lambda dist: -1 if float("inf") in dist else max(dist))(
        _bellman(n, times, k)[1:]
    ),
    java="""
        import java.util.*;

        class Solution {
            public int networkDelayTime(int[][] times, int n, int k) {
                List<List<int[]>> adj = new ArrayList<>();
                for (int i = 0; i <= n; i++) adj.add(new ArrayList<>());
                for (int[] t : times) adj.get(t[0]).add(new int[] {t[1], t[2]});
                int[] dist = new int[n + 1];
                Arrays.fill(dist, Integer.MAX_VALUE);
                dist[k] = 0;
                PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> Integer.compare(a[0], b[0]));
                pq.add(new int[] {0, k});
                while (!pq.isEmpty()) {
                    int[] top = pq.poll();
                    int d = top[0], u = top[1];
                    if (d > dist[u]) continue;
                    for (int[] e : adj.get(u))
                        if (d + e[1] < dist[e[0]]) { dist[e[0]] = d + e[1]; pq.add(new int[] {dist[e[0]], e[0]}); }
                }
                int best = 0;
                for (int i = 1; i <= n; i++) {
                    if (dist[i] == Integer.MAX_VALUE) return -1;
                    best = Math.max(best, dist[i]);
                }
                return best;
            }
        }
    """,
    tests=[
        {"times": [[2, 1, 1], [2, 3, 1], [3, 4, 1]], "n": 4, "k": 2},
        {"times": [[1, 2, 1]], "n": 2, "k": 1},
        {"times": [[1, 2, 1]], "n": 2, "k": 2},
        {"times": [[1, 2, 5], [1, 3, 1], [3, 2, 1]], "n": 3, "k": 1},
    ],
    gen=lambda r: (
        lambda n: {
            "times": [
                [a + 1, b + 1, r.randint(0, 9)]
                for a, b in r.sample(
                    [(a, b) for a in range(n) for b in range(n) if a != b],
                    min(n * (n - 1), r.randint(1, 2 * n)),
                )
            ],
            "n": n,
            "k": r.randint(1, n),
        }
    )(r.randint(1, 6)),
)


def _bellman(n, times, k):
    dist = [float("inf")] * (n + 1)
    dist[k] = 0
    for _ in range(n):
        for u, v, w in times:
            if dist[u] + w < dist[v]:
                dist[v] = dist[u] + w
    return dist


P(
    slug="cheapest-flights-k-stops",
    title="Cheapest Flight With at Most K Stops",
    difficulty="hard",
    topics=["graphs", "dynamic-programming"],
    summary="Lowest price from src to dst using at most k stops.",
    statement="""
        `flights[i] = [from, to, price]` are one-way flights between cities `0..n-1`. Return the cheapest price from
        `src` to `dst` with at most `k` stops in between (so at most `k + 1` flights), or `-1` if there's no such route.
    """,
    constraints=["1 <= n <= 100", "0 <= k < n", "src != dst"],
    sig="int findCheapestPrice(int n, int[][] flights, int src, int dst, int k)",
    hints=[
        "Plain Dijkstra may find a cheap route that uses too many stops.",
        "Bellman-Ford limited to k + 1 rounds: each round allows one more flight. Relax from a copy of the previous round so one round can't chain two flights.",
        "dist = [inf]*n; dist[src] = 0\nrepeat k + 1 times:\n    nxt = copy(dist)\n    for u, v, p in flights:\n        if dist[u] + p < nxt[v]: nxt[v] = dist[u] + p\n    dist = nxt\nreturn dist[dst] if finite else -1",
        "O(k × E) time. The copy is the important detail: it caps each round at exactly one more flight.",
    ],
    time="O(k E)",
    space="O(n)",
    model=lambda n, flights, src, dst, k: (
        lambda f: (lambda v: -1 if v == float("inf") else v)(f(f, src, k + 1))
    )(
        lru_cache(None)(
            lambda f, u, left: (
                0
                if u == dst
                else float("inf")
                if left == 0
                else min([p + f(f, b, left - 1) for a, b, p in flights if a == u] or [float("inf")])
            )
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            public int findCheapestPrice(int n, int[][] flights, int src, int dst, int k) {
                int[] dist = new int[n];
                Arrays.fill(dist, Integer.MAX_VALUE);
                dist[src] = 0;
                for (int round = 0; round <= k; round++) {
                    int[] next = dist.clone();
                    for (int[] f : flights)
                        if (dist[f[0]] != Integer.MAX_VALUE && dist[f[0]] + f[2] < next[f[1]]) next[f[1]] = dist[f[0]] + f[2];
                    dist = next;
                }
                return dist[dst] == Integer.MAX_VALUE ? -1 : dist[dst];
            }
        }
    """,
    tests=[
        {
            "n": 4,
            "flights": [[0, 1, 100], [1, 2, 100], [2, 0, 100], [1, 3, 600], [2, 3, 200]],
            "src": 0,
            "dst": 3,
            "k": 1,
        },
        {"n": 3, "flights": [[0, 1, 100], [1, 2, 100], [0, 2, 500]], "src": 0, "dst": 2, "k": 1},
        {"n": 3, "flights": [[0, 1, 100], [1, 2, 100], [0, 2, 500]], "src": 0, "dst": 2, "k": 0},
    ],
    gen=lambda r: (
        lambda n: (
            lambda s, d: {
                "n": n,
                "flights": [
                    [a, b, r.randint(1, 20)]
                    for a, b in r.sample(
                        [(a, b) for a in range(n) for b in range(n) if a != b],
                        min(n * (n - 1), r.randint(1, 2 * n)),
                    )
                ],
                "src": s,
                "dst": d,
                "k": r.randint(0, n - 1),
            }
        )(*r.sample(range(n), 2))
    )(r.randint(2, 6)),
)

P(
    slug="critical-connections",
    title="Critical Connections (Bridges)",
    difficulty="hard",
    topics=["graphs"],
    summary="Find the edges whose removal disconnects the network.",
    statement="""
        A connected undirected network has servers `0..n-1` and `connections`. A critical connection is one whose
        removal leaves some servers unable to reach others. Return all critical connections as `[a, b]` with
        `a < b`, sorted ascending.
    """,
    constraints=["2 <= n <= 10^5", "the network is connected, no duplicate connections"],
    sig="int[][] criticalConnections(int n, int[][] connections)",
    hints=[
        "An edge is critical exactly when it isn't part of any cycle.",
        "Tarjan's bridge algorithm: DFS discovery times plus `low` (earliest time reachable from a subtree). Edge (u, v) is a bridge if `low[v] > disc[u]`.",
        "def dfs(u, parent):\n    disc[u] = low[u] = time; time += 1\n    for v in adj[u]:\n        if v == parent: continue\n"
        "        if not visited v: dfs(v, u); low[u] = min(low[u], low[v]); if low[v] > disc[u]: bridge (u, v)\n        else: low[u] = min(low[u], disc[v])",
        "One DFS, O(V + E). For very large graphs use an iterative DFS to avoid stack overflow.",
    ],
    time="O(V + E)",
    space="O(V + E)",
    model=lambda n, connections: sorted(
        [
            sorted(e)
            for i, e in enumerate(connections)
            if _connected(n, connections[:i] + connections[i + 1 :]) < n
        ]
    ),
    java="""
        import java.util.*;

        class Solution {
            private int time = 0;
            private void dfs(int u, int parent, List<List<Integer>> adj, int[] disc, int[] low, List<int[]> out) {
                disc[u] = low[u] = ++time;
                for (int v : adj.get(u)) {
                    if (v == parent) continue;
                    if (disc[v] == 0) {
                        dfs(v, u, adj, disc, low, out);
                        low[u] = Math.min(low[u], low[v]);
                        if (low[v] > disc[u]) out.add(new int[] {Math.min(u, v), Math.max(u, v)});
                    } else low[u] = Math.min(low[u], disc[v]);
                }
            }
            public int[][] criticalConnections(int n, int[][] connections) {
                List<List<Integer>> adj = new ArrayList<>();
                for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
                for (int[] c : connections) { adj.get(c[0]).add(c[1]); adj.get(c[1]).add(c[0]); }
                List<int[]> out = new ArrayList<>();
                dfs(0, -1, adj, new int[n], new int[n], out);
                out.sort(Arrays::compare);
                return out.toArray(new int[0][]);
            }
        }
    """,
    tests=[
        {"n": 4, "connections": [[0, 1], [1, 2], [2, 0], [1, 3]]},
        {"n": 2, "connections": [[0, 1]]},
        {"n": 5, "connections": [[0, 1], [1, 2], [2, 0], [2, 3], [3, 4], [4, 2]]},
    ],
    gen=lambda r: (lambda n: {"n": n, "connections": _connected_graph(r, n, r.randint(0, n))})(
        r.randint(2, 7)
    ),
)

P(
    slug="course-order-smallest",
    title="Course Order, Smallest First",
    difficulty="hard",
    topics=["graphs", "topological-sort", "heaps"],
    summary="A valid course order that always picks the smallest available course.",
    statement="""
        Courses are `0..n-1`; `[a, b]` in `prereqs` means `b` must come before `a`. Return the lexicographically
        smallest order that takes every course, or an empty array if it's impossible.
    """,
    constraints=["1 <= n <= 2000", "0 <= prereqs.length <= 5000"],
    sig="int[] findOrder(int n, int[][] prereqs)",
    hints=[
        "Any topological order is valid; you want the one that's smallest at every position.",
        "Kahn's algorithm with a min-heap instead of a queue: always take the smallest course that's currently available.",
        "heap = all courses with indegree 0\nwhile heap:\n    c = pop smallest; order.append(c)\n    for nxt in adj[c]: indegree[nxt] -= 1; push nxt when it reaches 0\nreturn order if len(order) == n else []",
        "Greedily taking the smallest available course gives the smallest order. O((V + E) log V) with the heap.",
    ],
    time="O((V + E) log V)",
    space="O(V + E)",
    model=lambda n, prereqs: (lambda f: f(f, [], set(range(n))))(
        lambda f, order, left: (
            order
            if not left
            else (lambda free: [] if not free else f(f, order + [min(free)], left - {min(free)}))(
                [c for c in left if not any(a == c and b in left for a, b in prereqs)]
            )
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            public int[] findOrder(int n, int[][] prereqs) {
                List<List<Integer>> adj = new ArrayList<>();
                for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
                int[] indegree = new int[n];
                for (int[] p : prereqs) { adj.get(p[1]).add(p[0]); indegree[p[0]]++; }
                PriorityQueue<Integer> heap = new PriorityQueue<>();
                for (int i = 0; i < n; i++) if (indegree[i] == 0) heap.add(i);
                int[] order = new int[n];
                int w = 0;
                while (!heap.isEmpty()) {
                    int c = heap.poll();
                    order[w++] = c;
                    for (int next : adj.get(c)) if (--indegree[next] == 0) heap.add(next);
                }
                return w == n ? order : new int[0];
            }
        }
    """,
    tests=[
        {"n": 4, "prereqs": [[1, 0], [2, 0], [3, 1], [3, 2]]},
        {"n": 2, "prereqs": [[0, 1], [1, 0]]},
        {"n": 3, "prereqs": []},
        {"n": 3, "prereqs": [[0, 2]]},
    ],
    gen=lambda r: (
        lambda n: {
            "n": n,
            "prereqs": [
                list(p)
                for p in r.sample(
                    [(a, b) for a in range(n) for b in range(n) if a != b], min(n * (n - 1), r.randint(0, n))
                )
            ],
        }
    )(r.randint(1, 6)),
)

P(
    slug="longest-increasing-path-matrix",
    title="Longest Increasing Path in a Matrix",
    difficulty="hard",
    topics=["graphs", "dynamic-programming", "matrix"],
    summary="Longest strictly increasing walk through neighboring cells.",
    statement="""
        Return the length of the longest strictly increasing path in `matrix`, moving up, down, left or right
        (no diagonals, no wrapping).
    """,
    constraints=["1 <= rows, cols <= 200"],
    sig="int longestIncreasingPath(int[][] matrix)",
    hints=[
        "A strictly increasing path can never revisit a cell, so there are no cycles to worry about.",
        "Memoized DFS: longest(r, c) = 1 + max(longest(neighbor)) over neighbors with a larger value.",
        "memo = {}\ndef longest(r, c):\n    if (r, c) in memo: return it\n    best = 1\n    for each neighbor with larger value: best = max(best, 1 + longest(neighbor))\n"
        "    memo[(r, c)] = best; return best\nreturn max(longest(r, c) for all cells)",
        "Each cell's answer is computed once: O(m n). It's a longest path in a DAG.",
    ],
    time="O(m n)",
    space="O(m n)",
    model=lambda matrix: (
        lambda m, n: max(
            (lambda f: f(f, i, j))(
                lru_cache(None)(
                    lambda f, a, b: (
                        1
                        + max(
                            [
                                f(f, a + da, b + db)
                                for da, db in DIRS
                                if 0 <= a + da < m
                                and 0 <= b + db < n
                                and matrix[a + da][b + db] > matrix[a][b]
                            ]
                            or [0]
                        )
                    )
                )
            )
            for i in range(m)
            for j in range(n)
        )
    )(len(matrix), len(matrix[0])),
    java="""
        class Solution {
            private int[][] memo;
            private int longest(int[][] g, int r, int c) {
                if (memo[r][c] != 0) return memo[r][c];
                int best = 1;
                int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
                for (int[] d : dirs) {
                    int x = r + d[0], y = c + d[1];
                    if (x >= 0 && x < g.length && y >= 0 && y < g[0].length && g[x][y] > g[r][c]) best = Math.max(best, 1 + longest(g, x, y));
                }
                return memo[r][c] = best;
            }
            public int longestIncreasingPath(int[][] matrix) {
                memo = new int[matrix.length][matrix[0].length];
                int best = 0;
                for (int r = 0; r < matrix.length; r++) for (int c = 0; c < matrix[0].length; c++) best = Math.max(best, longest(matrix, r, c));
                return best;
            }
        }
    """,
    tests=[
        {"matrix": [[9, 9, 4], [6, 6, 8], [2, 1, 1]]},
        {"matrix": [[3, 4, 5], [3, 2, 6], [2, 2, 1]]},
        {"matrix": [[1]]},
    ],
    gen=lambda r: {"matrix": grid(r, r.randint(1, 4), r.randint(1, 4), 0, 9)},
)

P(
    slug="swim-rising-water",
    title="Swim in Rising Water",
    difficulty="hard",
    topics=["graphs", "heaps", "binary-search"],
    summary="Earliest time you can swim from corner to corner as water rises.",
    statement="""
        `grid[i][j]` is the elevation of each cell (all values are distinct, `0..n*n-1`). At time `t` the water
        depth is `t`, and you can move between neighboring cells (up/down/left/right) if both have elevation at
        most `t`. Return the earliest time you can get from the top-left to the bottom-right.
    """,
    constraints=["1 <= n <= 50", "values are a permutation of 0..n*n-1"],
    sig="int swimInWater(int[][] grid)",
    hints=[
        "The time for a path is the highest cell on it. You want the path whose highest cell is lowest.",
        "Dijkstra where a path's cost is the max elevation so far, always expanding the lowest-cost cell first.",
        "pq = [(grid[0][0], 0, 0)]\nseen = {(0, 0)}\nwhile pq:\n    t, r, c = pop min\n    if (r, c) is the goal: return t\n"
        "    for unvisited neighbors: mark; push (max(t, grid[nr][nc]), nr, nc)",
        "A min-heap on max-elevation-so-far gives O(n^2 log n). Binary search on t with a flood-fill check also works.",
    ],
    time="O(n^2 log n)",
    space="O(n^2)",
    model=lambda grid: next(
        t
        for t in range(len(grid) ** 2)
        if grid[0][0] <= t
        and _bfs_states(
            (0, 0),
            lambda s: s == (len(grid) - 1, len(grid) - 1),
            lambda s: [
                (s[0] + a, s[1] + b)
                for a, b in DIRS
                if 0 <= s[0] + a < len(grid) and 0 <= s[1] + b < len(grid) and grid[s[0] + a][s[1] + b] <= t
            ],
        )
        >= 0
    ),
    java="""
        import java.util.*;

        class Solution {
            public int swimInWater(int[][] grid) {
                int n = grid.length;
                boolean[][] seen = new boolean[n][n];
                PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> Integer.compare(a[0], b[0]));
                pq.add(new int[] {grid[0][0], 0, 0});
                seen[0][0] = true;
                int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
                while (true) {
                    int[] top = pq.poll();
                    if (top[1] == n - 1 && top[2] == n - 1) return top[0];
                    for (int[] d : dirs) {
                        int r = top[1] + d[0], c = top[2] + d[1];
                        if (r >= 0 && r < n && c >= 0 && c < n && !seen[r][c]) {
                            seen[r][c] = true;
                            pq.add(new int[] {Math.max(top[0], grid[r][c]), r, c});
                        }
                    }
                }
            }
        }
    """,
    tests=[
        {"grid": [[0, 2], [1, 3]]},
        {
            "grid": [
                [0, 1, 2, 3, 4],
                [24, 23, 22, 21, 5],
                [12, 13, 14, 15, 16],
                [11, 17, 18, 19, 20],
                [10, 9, 8, 7, 6],
            ]
        },
        {"grid": [[0]]},
    ],
    gen=lambda r: (
        lambda n: (lambda vals: {"grid": [vals[i * n : (i + 1) * n] for i in range(n)]})(
            r.sample(range(n * n), n * n)
        )
    )(r.randint(1, 4)),
)

P(
    slug="path-minimum-effort",
    title="Path With Minimum Effort",
    difficulty="hard",
    topics=["graphs", "heaps", "binary-search"],
    summary="Route that minimizes the biggest height step.",
    statement="""
        `heights` is a grid of cell heights. A path's effort is the largest absolute height difference between two
        consecutive cells on it (moves are up/down/left/right). Return the minimum effort to get from the top-left
        to the bottom-right.
    """,
    constraints=["1 <= rows, cols <= 100", "1 <= heights[i][j] <= 10^6"],
    sig="int minimumEffortPath(int[][] heights)",
    hints=[
        "A path's cost is a maximum, not a sum. Shortest-path ideas still work.",
        "Dijkstra where the cost to a cell is the max step along the best path to it.",
        "effort = all inf; effort[0][0] = 0\npq = [(0, 0, 0)]\nwhile pq:\n    e, r, c = pop min\n    if goal: return e\n"
        "    for neighbors: ne = max(e, |h[nr][nc] - h[r][c]|); if ne < effort[nr][nc]: update and push",
        "O(m n log(m n)). Binary searching the effort with a BFS reachability check is an alternative.",
    ],
    time="O(m n log(m n))",
    space="O(m n)",
    model=lambda heights: (
        lambda m, n: next(
            e
            for e in range(10**6 + 1)
            if _bfs_states(
                (0, 0),
                lambda s: s == (m - 1, n - 1),
                lambda s: [
                    (s[0] + a, s[1] + b)
                    for a, b in DIRS
                    if 0 <= s[0] + a < m
                    and 0 <= s[1] + b < n
                    and abs(heights[s[0] + a][s[1] + b] - heights[s[0]][s[1]]) <= e
                ],
            )
            >= 0
        )
    )(len(heights), len(heights[0])),
    java="""
        import java.util.*;

        class Solution {
            public int minimumEffortPath(int[][] heights) {
                int m = heights.length, n = heights[0].length;
                int[][] effort = new int[m][n];
                for (int[] row : effort) Arrays.fill(row, Integer.MAX_VALUE);
                effort[0][0] = 0;
                PriorityQueue<int[]> pq = new PriorityQueue<>((a, b) -> Integer.compare(a[0], b[0]));
                pq.add(new int[] {0, 0, 0});
                int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
                while (!pq.isEmpty()) {
                    int[] top = pq.poll();
                    int e = top[0], r = top[1], c = top[2];
                    if (r == m - 1 && c == n - 1) return e;
                    if (e > effort[r][c]) continue;
                    for (int[] d : dirs) {
                        int x = r + d[0], y = c + d[1];
                        if (x < 0 || x >= m || y < 0 || y >= n) continue;
                        int ne = Math.max(e, Math.abs(heights[x][y] - heights[r][c]));
                        if (ne < effort[x][y]) { effort[x][y] = ne; pq.add(new int[] {ne, x, y}); }
                    }
                }
                return 0;
            }
        }
    """,
    tests=[
        {"heights": [[1, 2, 2], [3, 8, 2], [5, 3, 5]]},
        {"heights": [[1, 2, 3], [3, 8, 4], [5, 3, 5]]},
        {"heights": [[4]]},
        {"heights": [[1, 2, 1, 1, 1], [1, 2, 1, 2, 1], [1, 2, 1, 2, 1], [1, 2, 1, 2, 1], [1, 1, 1, 2, 1]]},
    ],
    gen=lambda r: {"heights": grid(r, r.randint(1, 4), r.randint(1, 4), 1, 12)},
)

P(
    slug="bus-routes",
    title="Fewest Buses to Your Stop",
    difficulty="hard",
    topics=["graphs", "hash-maps"],
    summary="Minimum number of buses to ride from source to target.",
    statement="""
        `routes[i]` lists the stops bus `i` visits (it loops forever). Starting at stop `source` (not on a bus),
        return the fewest buses you must take to reach stop `target`, or `-1` if impossible. If `source == target`, the answer is 0.
    """,
    constraints=["1 <= routes.length <= 500", "stops are 0..10^6"],
    sig="int numBusesToDestination(int[][] routes, int source, int target)",
    hints=[
        "Count buses, not stops: the graph's nodes should be bus routes.",
        "BFS over buses. Map each stop to the buses that visit it; boarding a bus reveals all its stops at once.",
        "if source == target: return 0\nqueue = buses at source (depth 1)\nwhile queue:\n    for bus in this level:\n        if target in bus: return depth\n"
        "        for stop in bus: for next_bus at stop: if unseen: enqueue\n    depth += 1\nreturn -1",
        "Each bus and each stop is processed once: O(total stops across routes).",
    ],
    time="O(S)",
    space="O(S)",
    model=lambda routes, source, target: (
        0
        if source == target
        else _bfs_states(
            -1,
            lambda b: b >= 0 and target in routes[b],
            lambda b: [
                j
                for j in range(len(routes))
                if (source in routes[j] if b < 0 else set(routes[j]) & set(routes[b]))
            ],
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            public int numBusesToDestination(int[][] routes, int source, int target) {
                if (source == target) return 0;
                Map<Integer, List<Integer>> busesAt = new HashMap<>();
                for (int b = 0; b < routes.length; b++) for (int s : routes[b]) busesAt.computeIfAbsent(s, k -> new ArrayList<>()).add(b);
                boolean[] usedBus = new boolean[routes.length];
                Set<Integer> seenStop = new HashSet<>(List.of(source));
                Deque<Integer> queue = new ArrayDeque<>();
                for (int b : busesAt.getOrDefault(source, List.of())) { usedBus[b] = true; queue.add(b); }
                for (int depth = 1; !queue.isEmpty(); depth++) {
                    for (int k = queue.size(); k > 0; k--) {
                        int b = queue.poll();
                        for (int s : routes[b]) {
                            if (s == target) return depth;
                            if (!seenStop.add(s)) continue;
                            for (int nb : busesAt.get(s)) if (!usedBus[nb]) { usedBus[nb] = true; queue.add(nb); }
                        }
                    }
                }
                return -1;
            }
        }
    """,
    tests=[
        {"routes": [[1, 2, 7], [3, 6, 7]], "source": 1, "target": 6},
        {"routes": [[7, 12], [4, 5, 15], [6], [15, 19], [9, 12, 13]], "source": 15, "target": 12},
        {"routes": [[1, 2]], "source": 3, "target": 3},
        {"routes": [[1, 2], [3, 4]], "source": 1, "target": 4},
    ],
    gen=lambda r: {
        "routes": [r.sample(range(10), r.randint(1, 4)) for _ in range(r.randint(1, 5))],
        "source": r.randint(0, 9),
        "target": r.randint(0, 9),
    },
)

P(
    slug="shortest-path-all-nodes",
    title="Shortest Walk Visiting Every Node",
    difficulty="hard",
    topics=["graphs", "bit-manipulation", "dynamic-programming"],
    summary="Shortest walk that visits all nodes of a small graph.",
    statement="""
        `graph[i]` lists the neighbors of node `i` in a connected undirected graph with up to 12 nodes. Return
        the length (number of edges) of the shortest walk that visits every node. You may start and end anywhere
        and reuse nodes and edges.
    """,
    constraints=["1 <= n <= 12", "the graph is connected"],
    sig="int shortestPathLength(int[][] graph)",
    hints=[
        'The state you need is more than "which node am I on".',
        "State = (current node, set of visited nodes as a bitmask). BFS from every node at once over these states.",
        "queue = [(i, 1 << i) for every i]\nseen = those states\nsteps = 0\nwhile queue:\n    for each state in this level:\n"
        "        if mask == all visited: return steps\n        for v in graph[node]: next = (v, mask | 1 << v); enqueue if unseen\n    steps += 1",
        "There are n × 2^n states, each with up to n edges: O(n^2 2^n), fine for n ≤ 12.",
    ],
    time="O(n^2 · 2^n)",
    space="O(n · 2^n)",
    model=lambda graph: min(
        _bfs_states(
            (s, 1 << s),
            lambda st: st[1] == (1 << len(graph)) - 1,
            lambda st: [(v, st[1] | 1 << v) for v in graph[st[0]]],
        )
        for s in range(len(graph))
    ),
    java="""
        import java.util.*;

        class Solution {
            public int shortestPathLength(int[][] graph) {
                int n = graph.length, full = (1 << n) - 1;
                boolean[][] seen = new boolean[n][1 << n];
                Deque<int[]> queue = new ArrayDeque<>();
                for (int i = 0; i < n; i++) { queue.add(new int[] {i, 1 << i}); seen[i][1 << i] = true; }
                for (int steps = 0; ; steps++) {
                    for (int k = queue.size(); k > 0; k--) {
                        int[] s = queue.poll();
                        if (s[1] == full) return steps;
                        for (int v : graph[s[0]]) {
                            int mask = s[1] | (1 << v);
                            if (!seen[v][mask]) { seen[v][mask] = true; queue.add(new int[] {v, mask}); }
                        }
                    }
                }
            }
        }
    """,
    tests=[
        {"graph": [[1, 2, 3], [0], [0], [0]]},
        {"graph": [[1], [0, 2, 4], [1, 3, 4], [2], [1, 2]]},
        {"graph": [[]]},
    ],
    gen=lambda r: (
        lambda n, edges: {
            "graph": [
                sorted([b for a, b in edges if a == i] + [a for a, b in edges if b == i]) for i in range(n)
            ]
        }
    )(*(lambda n: (n, _connected_graph(r, n, r.randint(0, 2))))(r.randint(2, 6))),
)

P(
    slug="word-ladder",
    title="Word Ladder",
    difficulty="hard",
    topics=["graphs", "strings", "hash-sets"],
    summary="Fewest one-letter changes from one word to another.",
    statement="""
        Change `begin` into `end` one letter at a time, where every intermediate word (and `end`) must be in
        `words`. Return the number of words in the shortest such sequence, counting `begin` and `end`, or `0` if
        it's impossible.
    """,
    constraints=["1 <= begin.length <= 10", "1 <= words.length <= 5000", "all words have the same length"],
    sig="int ladderLength(String begin, String end, String[] words)",
    hints=[
        "Words are nodes; an edge joins words that differ in exactly one position.",
        "BFS from `begin`. Generate neighbors by trying every letter at every position and checking the word set.",
        "dictionary = set(words)\nif end not in dictionary: return 0\nqueue = [(begin, 1)]\nwhile queue:\n    w, d = pop front\n    if w == end: return d\n"
        "    for each one-letter variant v in dictionary: remove v from dictionary; push (v, d + 1)\nreturn 0",
        "Each word is visited once with 26 × L variants: O(N × 26 × L). Removing visited words from the set doubles as the visited marker.",
    ],
    time="O(N · 26 · L)",
    space="O(N)",
    model=lambda begin, end, words: (lambda d: 0 if d < 0 else d + 1)(
        _bfs_states(
            begin,
            lambda w: w == end,
            lambda w: [v for v in set(words) if sum(a != b for a, b in zip(w, v, strict=True)) == 1],
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            public int ladderLength(String begin, String end, String[] words) {
                Set<String> dict = new HashSet<>(Arrays.asList(words));
                if (!dict.contains(end)) return 0;
                Deque<String> queue = new ArrayDeque<>(List.of(begin));
                dict.remove(begin);
                for (int d = 1; !queue.isEmpty(); d++) {
                    for (int k = queue.size(); k > 0; k--) {
                        String w = queue.poll();
                        if (w.equals(end)) return d;
                        char[] c = w.toCharArray();
                        for (int i = 0; i < c.length; i++) {
                            char saved = c[i];
                            for (char x = 'a'; x <= 'z'; x++) {
                                c[i] = x;
                                String v = new String(c);
                                if (dict.remove(v)) queue.add(v);
                            }
                            c[i] = saved;
                        }
                    }
                }
                return 0;
            }
        }
    """,
    tests=[
        {"begin": "hit", "end": "cog", "words": ["hot", "dot", "dog", "lot", "log", "cog"]},
        {"begin": "hit", "end": "cog", "words": ["hot", "dot", "dog", "lot", "log"]},
        {"begin": "a", "end": "c", "words": ["a", "b", "c"]},
    ],
    gen=lambda r: (lambda words: {"begin": word(r, 3, 3, "abc"), "end": r.choice(words), "words": words})(
        [word(r, 3, 3, "abc") for _ in range(r.randint(1, 10))]
    ),
)

P(
    slug="making-large-island",
    title="Make the Largest Island",
    difficulty="hard",
    topics=["graphs", "matrix", "union-find"],
    summary="Flip at most one water cell to make the biggest island.",
    statement="""
        `grid` is an `n × n` binary grid (1 = land). You may change at most one `0` into `1`. Return the size of
        the largest island possible (islands connect up/down/left/right).
    """,
    constraints=["1 <= n <= 500"],
    sig="int largestIsland(int[][] grid)",
    hints=[
        "Flipping a water cell merges the distinct islands around it.",
        "Label every island with an id and record its size. For each 0, add 1 plus the sizes of the distinct neighboring island ids.",
        "label islands with ids 2, 3, ... and sizes[id]\nbest = max(sizes) or 0\nfor each 0 cell:\n    ids = distinct ids among its 4 neighbors\n    best = max(best, 1 + sum(sizes[i] for i in ids))\nreturn best (or n*n if no zeros)",
        "Labeling is O(n^2) and each water cell checks four neighbors: O(n^2) total. Using distinct ids avoids double-counting an island touching the cell twice.",
    ],
    time="O(n^2)",
    space="O(n^2)",
    model=_islands_after_flip,
    java="""
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
    """,
    tests=[
        {"grid": [[1, 0], [0, 1]]},
        {"grid": [[1, 1], [1, 0]]},
        {"grid": [[1, 1], [1, 1]]},
        {"grid": [[0]]},
    ],
    gen=lambda r: (lambda n: {"grid": grid(r, n, n, 0, 1)})(r.randint(1, 5)),
)

P(
    slug="shortest-path-eliminate-obstacles",
    title="Shortest Path, Breaking Up to K Walls",
    difficulty="hard",
    topics=["graphs", "matrix"],
    summary="Fewest steps across a grid when you may remove up to k obstacles.",
    statement="""
        In `grid`, `0` is open and `1` is an obstacle. Moving up/down/left/right, you may pass through at most `k`
        obstacles in total. Return the fewest steps from the top-left to the bottom-right, or `-1`.
    """,
    constraints=["1 <= rows, cols <= 40", "1 <= k <= rows * cols", "the corners are 0"],
    sig="int shortestPathWithK(int[][] grid, int k)",
    hints=[
        "Reaching a cell with more removals left is better than reaching it with fewer.",
        "BFS over states (row, col, removals left). Stepping onto a 1 costs one removal.",
        "queue = [(0, 0, k)]; seen = {(0, 0, k)}\nsteps = 0\nwhile queue:\n    for each state in this level:\n        if goal: return steps\n"
        "        for neighbors: left = rem - grid[nr][nc]; if left >= 0 and unseen: enqueue\n    steps += 1\nreturn -1",
        "At most m × n × (k + 1) states: O(m n k). If k ≥ m + n - 2 you can go straight there in m + n - 2 steps.",
    ],
    time="O(m n k)",
    space="O(m n k)",
    model=lambda grid, k: (
        lambda m, n: _bfs_states(
            (0, 0, k),
            lambda s: (s[0], s[1]) == (m - 1, n - 1),
            lambda s: [
                (s[0] + a, s[1] + b, s[2] - grid[s[0] + a][s[1] + b])
                for a, b in DIRS
                if 0 <= s[0] + a < m and 0 <= s[1] + b < n and s[2] - grid[s[0] + a][s[1] + b] >= 0
            ],
        )
    )(len(grid), len(grid[0])),
    java="""
        import java.util.*;

        class Solution {
            public int shortestPathWithK(int[][] grid, int k) {
                int m = grid.length, n = grid[0].length;
                boolean[][][] seen = new boolean[m][n][k + 1];
                Deque<int[]> queue = new ArrayDeque<>();
                queue.add(new int[] {0, 0, k});
                seen[0][0][k] = true;
                int[][] dirs = {{1, 0}, {-1, 0}, {0, 1}, {0, -1}};
                for (int steps = 0; !queue.isEmpty(); steps++) {
                    for (int c = queue.size(); c > 0; c--) {
                        int[] s = queue.poll();
                        if (s[0] == m - 1 && s[1] == n - 1) return steps;
                        for (int[] d : dirs) {
                            int x = s[0] + d[0], y = s[1] + d[1];
                            if (x < 0 || x >= m || y < 0 || y >= n) continue;
                            int left = s[2] - grid[x][y];
                            if (left >= 0 && !seen[x][y][left]) { seen[x][y][left] = true; queue.add(new int[] {x, y, left}); }
                        }
                    }
                }
                return -1;
            }
        }
    """,
    tests=[
        {"grid": [[0, 0, 0], [1, 1, 0], [0, 0, 0], [0, 1, 1], [0, 0, 0]], "k": 1},
        {"grid": [[0, 1, 1], [1, 1, 1], [1, 0, 0]], "k": 1},
        {"grid": [[0]], "k": 1},
    ],
    gen=lambda r: (
        lambda m, n: (
            lambda g: (g[0].__setitem__(0, 0), g[-1].__setitem__(-1, 0), {"grid": g, "k": r.randint(1, 3)})[2]
        )([[1 if r.random() < 0.4 else 0 for _ in range(n)] for _ in range(m)])
    )(r.randint(1, 5), r.randint(1, 5)),
)

P(
    slug="min-cost-valid-path",
    title="Cheapest Fix to Make a Valid Path",
    difficulty="hard",
    topics=["graphs", "matrix"],
    summary="Change the fewest arrows so you can walk from corner to corner.",
    statement="""
        Each cell of `grid` holds an arrow: 1 = right, 2 = left, 3 = down, 4 = up. Following arrows from the
        top-left, you want to reach the bottom-right. Changing a cell's arrow costs 1 (once per cell). Return the
        minimum total cost.
    """,
    constraints=["1 <= rows, cols <= 100", "grid[i][j] in 1..4"],
    sig="int minCost(int[][] grid)",
    hints=[
        "Moving in the arrow's direction is free; moving any other way costs 1.",
        "That's a shortest path with edge weights 0 and 1: use 0-1 BFS with a deque (free moves to the front, paid moves to the back).",
        "dist = inf; dist[0][0] = 0\ndq = [(0, 0)]\nwhile dq:\n    r, c = pop front\n    for each direction d (1..4):\n        w = 0 if grid[r][c] == d else 1\n"
        "        if dist[r][c] + w < dist[nr][nc]: update; push front if w == 0 else back\nreturn dist[m-1][n-1]",
        "0-1 BFS processes cells in order of cost like Dijkstra, but in O(m n) time.",
    ],
    time="O(m n)",
    space="O(m n)",
    model=lambda grid: (
        lambda m, n: (lambda adj: _dijkstra(m * n, adj, 0)[m * n - 1])(
            [
                [
                    ((i + a) * n + (j + b), 0 if grid[i][j] == d else 1)
                    for d, (a, b) in ((1, (0, 1)), (2, (0, -1)), (3, (1, 0)), (4, (-1, 0)))
                    if 0 <= i + a < m and 0 <= j + b < n
                ]
                for i in range(m)
                for j in range(n)
            ]
        )
    )(len(grid), len(grid[0])),
    java="""
        import java.util.*;

        class Solution {
            public int minCost(int[][] grid) {
                int m = grid.length, n = grid[0].length;
                int[][] dist = new int[m][n];
                for (int[] row : dist) Arrays.fill(row, Integer.MAX_VALUE);
                dist[0][0] = 0;
                int[][] dirs = {{0, 1}, {0, -1}, {1, 0}, {-1, 0}};
                Deque<int[]> dq = new ArrayDeque<>();
                dq.add(new int[] {0, 0});
                while (!dq.isEmpty()) {
                    int[] p = dq.pollFirst();
                    int r = p[0], c = p[1];
                    for (int d = 0; d < 4; d++) {
                        int x = r + dirs[d][0], y = c + dirs[d][1];
                        if (x < 0 || x >= m || y < 0 || y >= n) continue;
                        int w = grid[r][c] == d + 1 ? 0 : 1;
                        if (dist[r][c] + w < dist[x][y]) {
                            dist[x][y] = dist[r][c] + w;
                            if (w == 0) dq.addFirst(new int[] {x, y}); else dq.addLast(new int[] {x, y});
                        }
                    }
                }
                return dist[m - 1][n - 1];
            }
        }
    """,
    tests=[
        {"grid": [[1, 1, 1, 1], [2, 2, 2, 2], [1, 1, 1, 1], [2, 2, 2, 2]]},
        {"grid": [[1, 1, 3], [3, 2, 2], [1, 1, 4]]},
        {"grid": [[1, 2], [4, 3]]},
        {"grid": [[4]]},
    ],
    gen=lambda r: {"grid": grid(r, r.randint(1, 4), r.randint(1, 4), 1, 4)},
)

P(
    slug="islands-after-adding-land",
    title="Island Count as Land Appears",
    difficulty="hard",
    topics=["union-find", "matrix"],
    summary="Track the number of islands after each new piece of land.",
    statement="""
        An `m × n` grid starts as all water. `positions[i] = [r, c]` turns that cell into land (a repeated position
        changes nothing). Return the number of islands after each operation. Islands connect up/down/left/right.
    """,
    constraints=["1 <= m, n, positions.length <= 10^4", "m * n <= 10^4"],
    sig="int[] numIslands2(int m, int n, int[][] positions)",
    hints=[
        "Recounting islands from scratch after every addition is too slow.",
        "Union-find: each new land cell starts as its own island (+1); every union with a neighboring island merges two (-1).",
        "count = 0\nfor r, c in positions:\n    if already land: out.append(count); continue\n    make land; count += 1\n"
        "    for neighbors that are land: if find(cell) != find(nb): union; count -= 1\n    out.append(count)\nreturn out",
        "Each operation is near O(1) with path compression: O(k α(mn)) for k additions.",
    ],
    time="O(k α(mn))",
    space="O(m n)",
    model=lambda m, n, positions: [
        (lambda land: len({min_rep for min_rep in [_rep(land, p) for p in land]}))(
            {tuple(p) for p in positions[: i + 1]}
        )
        for i in range(len(positions))
    ],
    java="""
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
    """,
    tests=[
        {"m": 3, "n": 3, "positions": [[0, 0], [0, 1], [1, 2], [2, 1]]},
        {"m": 1, "n": 1, "positions": [[0, 0]]},
        {"m": 2, "n": 2, "positions": [[0, 0], [1, 1], [0, 1], [0, 1]]},
    ],
    gen=lambda r: (
        lambda m, n: {
            "m": m,
            "n": n,
            "positions": [[r.randint(0, m - 1), r.randint(0, n - 1)] for _ in range(r.randint(1, 8))],
        }
    )(r.randint(1, 4), r.randint(1, 4)),
)


def _rep(land, start):
    seen, stack = {start}, [start]
    while stack:
        a, b = stack.pop()
        for da, db in DIRS:
            q = (a + da, b + db)
            if q in land and q not in seen:
                seen.add(q)
                stack.append(q)
    return min(seen)


P(
    slug="unique-paths-all-squares",
    title="Walks That Cover Every Square",
    difficulty="hard",
    topics=["backtracking", "matrix"],
    summary="Count walks from start to end that step on every open square exactly once.",
    statement="""
        In `grid`: `1` is the start, `2` is the end, `0` is an open square and `-1` is a wall. Return the number of
        walks (up/down/left/right) from start to end that visit every non-wall square exactly once.
    """,
    constraints=["1 <= rows * cols <= 20", "exactly one start and one end"],
    sig="int uniquePathsIII(int[][] grid)",
    hints=[
        "You must count walks of an exact length: every open square plus the start.",
        "Backtracking DFS: mark squares as you step on them, unmark when you return, and count arrivals at the end with nothing left to visit.",
        "remaining = number of non-wall squares\ndef dfs(r, c, left):\n    if grid[r][c] == 2: return 1 if left == 1 else 0\n"
        "    mark (r, c)\n    total = sum(dfs(neighbor, left - 1) for open unmarked neighbors)\n    unmark\n    return total\nreturn dfs(start, remaining)",
        "Exponential in the worst case, but grids have at most 20 squares, and the visited marks prune heavily.",
    ],
    time="O(3^(m n))",
    space="O(m n)",
    model=lambda grid: (
        lambda cells, start, end: (
            sum(
                1
                for perm in permutations(cells - {start, end})
                if all(
                    abs(a[0] - b[0]) + abs(a[1] - b[1]) == 1
                    for a, b in zip((start, *perm), (*perm, end), strict=True)
                )
            )
            if len(cells) <= 9
            else None
        )
    )(
        {(i, j) for i, row in enumerate(grid) for j, v in enumerate(row) if v != -1},
        next((i, j) for i, row in enumerate(grid) for j, v in enumerate(row) if v == 1),
        next((i, j) for i, row in enumerate(grid) for j, v in enumerate(row) if v == 2),
    ),
    java="""
        class Solution {
            private int dfs(int[][] g, int r, int c, int left) {
                if (r < 0 || c < 0 || r >= g.length || c >= g[0].length || g[r][c] == -1) return 0;
                if (g[r][c] == 2) return left == 1 ? 1 : 0;
                int saved = g[r][c];
                g[r][c] = -1;
                int total = dfs(g, r + 1, c, left - 1) + dfs(g, r - 1, c, left - 1) + dfs(g, r, c + 1, left - 1) + dfs(g, r, c - 1, left - 1);
                g[r][c] = saved;
                return total;
            }
            public int uniquePathsIII(int[][] grid) {
                int remaining = 0, sr = 0, sc = 0;
                for (int i = 0; i < grid.length; i++)
                    for (int j = 0; j < grid[0].length; j++) {
                        if (grid[i][j] != -1) remaining++;
                        if (grid[i][j] == 1) { sr = i; sc = j; }
                    }
                return dfs(grid, sr, sc, remaining);
            }
        }
    """,
    tests=[
        {"grid": [[1, 0, 0], [0, 0, 0], [0, 0, 2]]},
        {"grid": [[1, 0], [0, 2]]},
        {"grid": [[0, 1], [2, 0]]},
        {"grid": [[1, -1, 2]]},
        {"grid": [[1, 0, 2]]},
    ],
    gen=lambda r: (
        lambda m, n: (
            lambda cells: (lambda g: {"grid": g})(
                [
                    [
                        (
                            1
                            if (i, j) == cells[0]
                            else 2
                            if (i, j) == cells[1]
                            else (-1 if r.random() < 0.25 else 0)
                        )
                        for j in range(n)
                    ]
                    for i in range(m)
                ]
            )
        )(r.sample([(i, j) for i in range(m) for j in range(n)], 2))
    )(r.randint(1, 3), r.randint(2, 3)),
)

P(
    slug="n-queens-count",
    title="Count N-Queens Solutions",
    difficulty="hard",
    topics=["backtracking"],
    summary="Ways to place n queens so none attack each other.",
    statement="""
        Return the number of ways to place `n` queens on an `n × n` chessboard so that no two share a row, column
        or diagonal.
    """,
    constraints=["1 <= n <= 10"],
    sig="int totalNQueens(int n)",
    hints=[
        "Each row gets exactly one queen.",
        "Place queens row by row, tracking used columns and both diagonals (`r - c` and `r + c`).",
        "def place(r):\n    if r == n: return 1\n    total = 0\n    for c in range(n):\n        if c, r-c, r+c are free: mark; total += place(r + 1); unmark\n    return total\nreturn place(0)",
        "Backtracking with O(1) conflict checks. Bitmasks for the three sets make it very fast for n ≤ 10.",
    ],
    time="O(n!)",
    space="O(n)",
    model=lambda n: sum(
        1
        for p in permutations(range(n))
        if len({p[i] - i for i in range(n)}) == n and len({p[i] + i for i in range(n)}) == n
    ),
    java="""
        class Solution {
            private int place(int n, int row, int cols, int d1, int d2) {
                if (row == n) return 1;
                int total = 0;
                for (int c = 0; c < n; c++) {
                    int a = 1 << c, b = 1 << (row - c + n), d = 1 << (row + c);
                    if ((cols & a) == 0 && (d1 & b) == 0 && (d2 & d) == 0) total += place(n, row + 1, cols | a, d1 | b, d2 | d);
                }
                return total;
            }
            public int totalNQueens(int n) {
                return place(n, 0, 0, 0, 0);
            }
        }
    """,
    tests=[{"n": 4}, {"n": 1}, {"n": 2}, {"n": 6}, {"n": 8}],
    gen=lambda r: {"n": r.randint(3, 7)},
    gen_count=2,
)

P(
    slug="sudoku-solver",
    title="Sudoku Solver",
    difficulty="hard",
    topics=["backtracking", "matrix"],
    summary="Fill in a Sudoku puzzle.",
    statement="""
        `board` is 9 strings of 9 characters (`1-9` or `.` for empty). Fill the empty cells so every row, column and
        3×3 box contains the digits 1-9 exactly once. The puzzle has exactly one solution. Return the solved board.
    """,
    constraints=["board is 9 x 9", "exactly one solution"],
    sig="String[] solveSudoku(String[] board)",
    hints=[
        "Fill one empty cell at a time, and undo when you hit a dead end.",
        "Backtracking: for the next empty cell, try each digit not already in its row, column or box.",
        "def solve():\n    find an empty cell (best: the one with the fewest options)\n    if none: return true\n"
        "    for d in options: place d; if solve(): return true; remove d\n    return false",
        "Tracking used digits per row/column/box makes each check O(1). Picking the most constrained cell first prunes the search dramatically.",
    ],
    time="O(9^empty) worst case",
    space="O(81)",
    model=lambda board: _solve_sudoku(board),
    public=2,
    java="""
        class Solution {
            private boolean[][] rows = new boolean[9][10], cols = new boolean[9][10], boxes = new boolean[9][10];
            private char[][] g = new char[9][];
            private boolean solve() {
                int bestR = -1, bestC = -1, bestCount = 10;
                for (int r = 0; r < 9; r++)
                    for (int c = 0; c < 9; c++) {
                        if (g[r][c] != '.') continue;
                        int count = 0;
                        for (int d = 1; d <= 9; d++) if (!rows[r][d] && !cols[c][d] && !boxes[(r / 3) * 3 + c / 3][d]) count++;
                        if (count < bestCount) { bestCount = count; bestR = r; bestC = c; }
                    }
                if (bestR == -1) return true;
                int b = (bestR / 3) * 3 + bestC / 3;
                for (int d = 1; d <= 9; d++) {
                    if (rows[bestR][d] || cols[bestC][d] || boxes[b][d]) continue;
                    g[bestR][bestC] = (char) ('0' + d);
                    rows[bestR][d] = cols[bestC][d] = boxes[b][d] = true;
                    if (solve()) return true;
                    rows[bestR][d] = cols[bestC][d] = boxes[b][d] = false;
                    g[bestR][bestC] = '.';
                }
                return false;
            }
            public String[] solveSudoku(String[] board) {
                for (int r = 0; r < 9; r++) {
                    g[r] = board[r].toCharArray();
                    for (int c = 0; c < 9; c++)
                        if (g[r][c] != '.') { int d = g[r][c] - '0'; rows[r][d] = cols[c][d] = boxes[(r / 3) * 3 + c / 3][d] = true; }
                }
                solve();
                String[] out = new String[9];
                for (int r = 0; r < 9; r++) out[r] = new String(g[r]);
                return out;
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
                "..9748...",
                "7........",
                ".2.1.9...",
                "..7...24.",
                ".64.1.59.",
                ".98...3..",
                "...8.3.2.",
                "........6",
                "...2759..",
            ]
        },
        {
            "board": [
                "8........",
                "..36.....",
                ".7..9.2..",
                ".5...7...",
                "....457..",
                "...1...3.",
                "..1....68",
                "..85...1.",
                ".9....4..",
            ]
        },
        {
            "board": [
                "534678912",
                "672195348",
                "198342567",
                "859761423",
                "426853791",
                "713924856",
                "961537284",
                "287419635",
                "34528617.",
            ]
        },
        {
            "board": [
                "5.4678..2",
                "67..953.8",
                "1.83.25.7",
                "8.97.14.3",
                "42.853.91",
                "7.392.85.",
                "96.53.2.4",
                "2.741.635",
                "34.28.179",
            ]
        },
    ],
)


def _solve_sudoku(board):
    g = [list(row) for row in board]

    def options(r, c):
        used = (
            set(g[r])
            | {g[i][c] for i in range(9)}
            | {g[i][j] for i in range(r // 3 * 3, r // 3 * 3 + 3) for j in range(c // 3 * 3, c // 3 * 3 + 3)}
        )
        return [d for d in "123456789" if d not in used]

    def solve():
        empties = [(r, c) for r in range(9) for c in range(9) if g[r][c] == "."]
        if not empties:
            return True
        r, c = min(empties, key=lambda rc: len(options(*rc)))
        for d in options(r, c):
            g[r][c] = d
            if solve():
                return True
        g[r][c] = "."
        return False

    solve()
    return ["".join(row) for row in g]


P(
    slug="maximal-rectangle",
    title="Largest Rectangle of Ones",
    difficulty="hard",
    topics=["stacks", "dynamic-programming", "matrix"],
    summary="Area of the biggest all-'1' rectangle in a binary matrix.",
    statement="""
        `matrix` rows are strings of `'0'` and `'1'`. Return the area of the largest rectangle containing only `'1'`s.
    """,
    constraints=["1 <= rows, cols <= 200"],
    sig="int maximalRectangle(String[] matrix)",
    hints=[
        "Turn each row into a histogram: the height of consecutive 1s ending at that row in each column.",
        "For each row's histogram, find the largest rectangle with the monotonic-stack method.",
        "heights = [0]*n\nbest = 0\nfor row in matrix:\n    heights[j] = heights[j] + 1 if row[j] == '1' else 0\n    best = max(best, largestRectangleInHistogram(heights))\nreturn best",
        "Each row costs O(n) with the stack: O(m n) total.",
    ],
    time="O(m n)",
    space="O(n)",
    model=lambda matrix: max(
        [0]
        + [
            (b - a) * (d - c)
            for a in range(len(matrix))
            for b in range(a + 1, len(matrix) + 1)
            for c in range(len(matrix[0]))
            for d in range(c + 1, len(matrix[0]) + 1)
            if all(matrix[i][j] == "1" for i in range(a, b) for j in range(c, d))
        ]
    ),
    java="""
        import java.util.*;

        class Solution {
            public int maximalRectangle(String[] matrix) {
                int n = matrix[0].length(), best = 0;
                int[] heights = new int[n];
                for (String row : matrix) {
                    for (int j = 0; j < n; j++) heights[j] = row.charAt(j) == '1' ? heights[j] + 1 : 0;
                    Deque<Integer> stack = new ArrayDeque<>();
                    for (int i = 0; i <= n; i++) {
                        int h = i == n ? 0 : heights[i];
                        while (!stack.isEmpty() && heights[stack.peek()] > h) {
                            int top = stack.pop();
                            int left = stack.isEmpty() ? 0 : stack.peek() + 1;
                            best = Math.max(best, heights[top] * (i - left));
                        }
                        stack.push(i);
                    }
                }
                return best;
            }
        }
    """,
    tests=[
        {"matrix": ["10100", "10111", "11111", "10010"]},
        {"matrix": ["0"]},
        {"matrix": ["1"]},
        {"matrix": ["111", "111"]},
    ],
    gen=lambda r: {
        "matrix": [
            "".join(r.choice("1101") for _ in range(cols))
            for cols in [r.randint(1, 4)]
            for _ in range(r.randint(1, 4))
        ]
    },
)

P(
    slug="submatrices-sum-target",
    title="Submatrices That Sum to Target",
    difficulty="hard",
    topics=["matrix", "prefix-sums", "hash-maps"],
    summary="Count rectangles in a matrix whose values add up to a target.",
    statement="""
        Return the number of non-empty rectangular submatrices of `matrix` whose values sum to `target`.
    """,
    constraints=["1 <= rows, cols <= 100", "-1000 <= matrix[i][j] <= 1000"],
    sig="int numSubmatrixSumTarget(int[][] matrix, int target)",
    hints=[
        "Fix the top and bottom rows; then it's a 1-D problem.",
        "For each pair of rows, compress columns into sums and count subarrays with sum `target` using prefix sums and a hash map.",
        "for top in rows:\n    colSums = [0]*n\n    for bottom from top down:\n        add row bottom into colSums\n        count += subarraysWithSum(colSums, target)   # prefix-count map\nreturn count",
        "O(m^2 n) time: every row pair runs a linear subarray-sum count.",
    ],
    time="O(m^2 n)",
    space="O(n)",
    model=lambda matrix, target: sum(
        1
        for a in range(len(matrix))
        for b in range(a, len(matrix))
        for c in range(len(matrix[0]))
        for d in range(c, len(matrix[0]))
        if sum(matrix[i][j] for i in range(a, b + 1) for j in range(c, d + 1)) == target
    ),
    java="""
        import java.util.*;

        class Solution {
            public int numSubmatrixSumTarget(int[][] matrix, int target) {
                int m = matrix.length, n = matrix[0].length, count = 0;
                for (int top = 0; top < m; top++) {
                    int[] col = new int[n];
                    for (int bottom = top; bottom < m; bottom++) {
                        for (int j = 0; j < n; j++) col[j] += matrix[bottom][j];
                        Map<Integer, Integer> seen = new HashMap<>();
                        seen.put(0, 1);
                        int sum = 0;
                        for (int j = 0; j < n; j++) {
                            sum += col[j];
                            count += seen.getOrDefault(sum - target, 0);
                            seen.merge(sum, 1, Integer::sum);
                        }
                    }
                }
                return count;
            }
        }
    """,
    tests=[
        {"matrix": [[0, 1, 0], [1, 1, 1], [0, 1, 0]], "target": 0},
        {"matrix": [[1, -1], [-1, 1]], "target": 0},
        {"matrix": [[904]], "target": 0},
    ],
    gen=lambda r: {"matrix": grid(r, r.randint(1, 4), r.randint(1, 4), -2, 2), "target": r.randint(-2, 2)},
)

P(
    slug="max-rectangle-sum-at-most-k",
    title="Biggest Rectangle Sum Not Above K",
    difficulty="hard",
    topics=["matrix", "prefix-sums", "binary-search"],
    summary="Largest submatrix sum that doesn't exceed k.",
    statement="""
        Return the largest sum of a non-empty rectangular submatrix of `matrix` that is at most `k`. At least one
        such rectangle is guaranteed to exist.
    """,
    constraints=["1 <= rows, cols <= 100", "-100 <= matrix[i][j] <= 100"],
    sig="int maxSumSubmatrix(int[][] matrix, int k)",
    hints=[
        'Fix the left and right columns and compress rows into sums: now it\'s "best subarray sum ≤ k" in 1-D.',
        "For a prefix sum `S`, you want the smallest earlier prefix `≥ S - k`. A sorted set (TreeSet.ceiling) finds it in O(log n).",
        "for left, right column pairs:\n    rowSums = sums of each row between left and right\n    seen = sorted set {0}; prefix = 0\n"
        "    for s in rowSums:\n        prefix += s\n        c = seen.ceiling(prefix - k)\n        if c exists: best = max(best, prefix - c)\n        seen.add(prefix)\nreturn best",
        'O(n^2 m log m). A sorted set is needed because, unlike "sum equals k", you need the closest prefix, not an exact one.',
    ],
    time="O(n^2 m log m)",
    space="O(m)",
    model=lambda matrix, k: max(
        s
        for s in (
            sum(matrix[i][j] for i in range(a, b + 1) for j in range(c, d + 1))
            for a in range(len(matrix))
            for b in range(a, len(matrix))
            for c in range(len(matrix[0]))
            for d in range(c, len(matrix[0]))
        )
        if s <= k
    ),
    java="""
        import java.util.*;

        class Solution {
            public int maxSumSubmatrix(int[][] matrix, int k) {
                int m = matrix.length, n = matrix[0].length, best = Integer.MIN_VALUE;
                for (int left = 0; left < n; left++) {
                    int[] rows = new int[m];
                    for (int right = left; right < n; right++) {
                        for (int i = 0; i < m; i++) rows[i] += matrix[i][right];
                        TreeSet<Integer> seen = new TreeSet<>(List.of(0));
                        int prefix = 0;
                        for (int s : rows) {
                            prefix += s;
                            Integer c = seen.ceiling(prefix - k);
                            if (c != null) best = Math.max(best, prefix - c);
                            seen.add(prefix);
                        }
                    }
                }
                return best;
            }
        }
    """,
    tests=[
        {"matrix": [[1, 0, 1], [0, -2, 3]], "k": 2},
        {"matrix": [[2, 2, -1]], "k": 3},
        {"matrix": [[5]], "k": 5},
    ],
    gen=lambda r: (lambda g: {"matrix": g, "k": max(min(v for row in g for v in row), r.randint(-3, 8))})(
        grid(r, r.randint(1, 4), r.randint(1, 4), -4, 4)
    ),
)

P(
    slug="cherry-pickup-two-robots",
    title="Two Robots Picking Cherries",
    difficulty="hard",
    topics=["dynamic-programming", "matrix"],
    summary="Two robots move down a grid collecting cherries; maximize the total.",
    statement="""
        `grid[i][j]` is the number of cherries in each cell. Robot A starts at the top-left and robot B at the
        top-right. Each step, both move to the next row, to the column left, same or right of where they are. A
        robot collects the cherries of each cell it enters; if both are on the same cell, the cherries count once.
        Return the most cherries they can collect by the bottom row.
    """,
    constraints=["2 <= rows, cols <= 70", "0 <= grid[i][j] <= 100"],
    sig="int cherryPickup(int[][] grid)",
    hints=[
        "Both robots are always on the same row, so the state is just their two columns.",
        "dp over rows with state (colA, colB): try all 9 move combinations from the previous row.",
        "dp = {(0, n-1): grid[0][0] + grid[0][n-1]}\nfor each next row:\n    for each state and each of 9 move pairs: new value = old + cherries at (a, b) counted once if a == b\n    keep the best per state\nreturn max(dp)",
        "O(rows × cols^2 × 9) time, O(cols^2) space.",
    ],
    time="O(m n^2)",
    space="O(n^2)",
    model=lambda grid: (
        lambda m, n: (lambda f: f(f, 0, 0, n - 1))(
            lru_cache(None)(
                lambda f, r, a, b: (
                    (grid[r][a] + (grid[r][b] if a != b else 0))
                    + (
                        0
                        if r == m - 1
                        else max(
                            f(f, r + 1, a + da, b + db)
                            for da in (-1, 0, 1)
                            for db in (-1, 0, 1)
                            if 0 <= a + da < n and 0 <= b + db < n
                        )
                    )
                )
            )
        )
    )(len(grid), len(grid[0])),
    java="""
        import java.util.*;

        class Solution {
            public int cherryPickup(int[][] grid) {
                int m = grid.length, n = grid[0].length;
                int[][] dp = new int[n][n];
                for (int[] row : dp) Arrays.fill(row, -1);
                dp[0][n - 1] = grid[0][0] + (n - 1 != 0 ? grid[0][n - 1] : 0);
                for (int r = 1; r < m; r++) {
                    int[][] next = new int[n][n];
                    for (int[] row : next) Arrays.fill(row, -1);
                    for (int a = 0; a < n; a++)
                        for (int b = 0; b < n; b++) {
                            if (dp[a][b] < 0) continue;
                            for (int da = -1; da <= 1; da++)
                                for (int db = -1; db <= 1; db++) {
                                    int x = a + da, y = b + db;
                                    if (x < 0 || x >= n || y < 0 || y >= n) continue;
                                    int gain = grid[r][x] + (x != y ? grid[r][y] : 0);
                                    next[x][y] = Math.max(next[x][y], dp[a][b] + gain);
                                }
                        }
                    dp = next;
                }
                int best = 0;
                for (int[] row : dp) for (int v : row) best = Math.max(best, v);
                return best;
            }
        }
    """,
    tests=[
        {"grid": [[3, 1, 1], [2, 5, 1], [1, 5, 5], [2, 1, 1]]},
        {
            "grid": [
                [1, 0, 0, 0, 0, 0, 1],
                [2, 0, 0, 0, 0, 3, 0],
                [2, 0, 9, 0, 0, 0, 0],
                [0, 3, 0, 5, 4, 0, 0],
                [1, 0, 2, 3, 0, 0, 6],
            ]
        },
        {"grid": [[1, 1], [1, 1]]},
    ],
    gen=lambda r: {"grid": grid(r, r.randint(2, 5), r.randint(2, 5), 0, 9)},
)

P(
    slug="min-falling-path-sum-two",
    title="Falling Path Without Repeating Columns",
    difficulty="hard",
    topics=["dynamic-programming", "matrix"],
    summary="Pick one value per row, never the same column twice in a row, minimizing the sum.",
    statement="""
        Pick exactly one value from each row of the square matrix `grid`, so that values in adjacent rows are in
        different columns. Return the minimum possible sum.
    """,
    constraints=["1 <= n <= 200", "-99 <= grid[i][j] <= 99"],
    sig="int minFallingPathSum(int[][] grid)",
    hints=[
        "For each cell, you need the best previous-row value from any *other* column.",
        "Keep only the smallest and second-smallest totals of the previous row (and the smallest's column).",
        "prev = row 0\nfor each next row:\n    m1, m2, col1 = smallest, second smallest, column of smallest in prev\n"
        "    cur[j] = grid[i][j] + (m2 if j == col1 else m1)\n    prev = cur\nreturn min(prev)",
        "Tracking two minima avoids an O(n) inner loop: O(n^2) total instead of O(n^3).",
    ],
    time="O(n^2)",
    space="O(n)",
    model=lambda grid: min(
        sum(grid[i][c] for i, c in enumerate(cols))
        for cols in __import__("itertools").product(range(len(grid)), repeat=len(grid))
        if all(cols[i] != cols[i + 1] for i in range(len(cols) - 1))
    ),
    java="""
        class Solution {
            public int minFallingPathSum(int[][] grid) {
                int n = grid.length;
                int[] prev = grid[0].clone();
                for (int i = 1; i < n; i++) {
                    int m1 = Integer.MAX_VALUE, m2 = Integer.MAX_VALUE, col1 = -1;
                    for (int j = 0; j < n; j++) {
                        if (prev[j] < m1) { m2 = m1; m1 = prev[j]; col1 = j; }
                        else if (prev[j] < m2) m2 = prev[j];
                    }
                    int[] cur = new int[n];
                    for (int j = 0; j < n; j++) cur[j] = grid[i][j] + (j == col1 ? m2 : m1);
                    prev = cur;
                }
                int best = Integer.MAX_VALUE;
                for (int v : prev) best = Math.min(best, v);
                return best;
            }
        }
    """,
    tests=[{"grid": [[1, 2, 3], [4, 5, 6], [7, 8, 9]]}, {"grid": [[7]]}, {"grid": [[2, 2], [1, 3]]}],
    gen=lambda r: (lambda n: {"grid": grid(r, n, n, -9, 9)})(r.randint(2, 5)),
)

P(
    slug="min-cost-connect-points",
    title="Cheapest Way to Connect All Points",
    difficulty="hard",
    topics=["graphs", "heaps"],
    summary="Minimum spanning tree with Manhattan distances.",
    statement="""
        `points[i] = [x, y]`. Connecting two points costs their Manhattan distance `|x1 - x2| + |y1 - y2|`.
        Return the minimum total cost to connect all points (so every pair is joined by some path).
    """,
    constraints=["1 <= points.length <= 1000", "-10^6 <= x, y <= 10^6", "distinct points"],
    sig="int minCostConnectPoints(int[][] points)",
    hints=[
        "You need a minimum spanning tree on a complete graph.",
        "Prim's algorithm with an array of best distances (no heap needed on a dense graph): add the closest unconnected point each round.",
        "dist = [inf]*n; dist[0] = 0; inTree = [false]*n\nrepeat n times:\n    u = closest point not in tree\n    total += dist[u]; inTree[u] = true\n"
        "    for v not in tree: dist[v] = min(dist[v], manhattan(u, v))\nreturn total",
        "Array-based Prim is O(n^2), which beats sorting all n^2 edges for Kruskal on a dense graph.",
    ],
    time="O(n^2)",
    space="O(n)",
    model=lambda points: (
        lambda n: (
            lambda edges: __import__("functools").reduce(
                lambda acc, e: (
                    lambda parent, total: (
                        lambda ra, rb: (parent, total) if ra == rb else ({**parent, ra: rb}, total + e[0])
                    )(_root(parent, e[1]), _root(parent, e[2]))
                )(*acc),
                edges,
                ({i: i for i in range(n)}, 0),
            )[1]
        )(
            sorted(
                (abs(points[i][0] - points[j][0]) + abs(points[i][1] - points[j][1]), i, j)
                for i in range(n)
                for j in range(i + 1, n)
            )
        )
    )(len(points)),
    java="""
        import java.util.*;

        class Solution {
            public int minCostConnectPoints(int[][] points) {
                int n = points.length, total = 0;
                int[] dist = new int[n];
                Arrays.fill(dist, Integer.MAX_VALUE);
                dist[0] = 0;
                boolean[] inTree = new boolean[n];
                for (int round = 0; round < n; round++) {
                    int u = -1;
                    for (int v = 0; v < n; v++) if (!inTree[v] && (u == -1 || dist[v] < dist[u])) u = v;
                    inTree[u] = true;
                    total += dist[u];
                    for (int v = 0; v < n; v++)
                        if (!inTree[v]) dist[v] = Math.min(dist[v], Math.abs(points[u][0] - points[v][0]) + Math.abs(points[u][1] - points[v][1]));
                }
                return total;
            }
        }
    """,
    tests=[
        {"points": [[0, 0], [2, 2], [3, 10], [5, 2], [7, 0]]},
        {"points": [[3, 12], [-2, 5], [-4, 1]]},
        {"points": [[0, 0]]},
    ],
    gen=lambda r: {
        "points": [
            list(p) for p in r.sample([(x, y) for x in range(-6, 7) for y in range(-6, 7)], r.randint(1, 8))
        ]
    },
)


def _root(parent, x):
    while parent[x] != x:
        x = parent[x]
    return x


P(
    slug="minimum-height-trees",
    title="Roots of Minimum Height Trees",
    difficulty="hard",
    topics=["graphs", "topological-sort"],
    summary="Which nodes, as the root, make a tree as short as possible?",
    statement="""
        A tree has nodes `0..n-1` and `n - 1` undirected `edges`. Choosing a root gives a rooted tree with some
        height. Return all nodes that give the minimum height, in ascending order.
    """,
    constraints=["1 <= n <= 2 * 10^4", "edges form a tree"],
    sig="int[] findMinHeightTrees(int n, int[][] edges)",
    hints=[
        "The best roots are in the middle of the tree's longest path.",
        "Peel leaves layer by layer (like a topological sort from the outside in). The last one or two nodes left are the answer.",
        "if n == 1: return [0]\nleaves = nodes with degree 1\nremaining = n\nwhile remaining > 2:\n    remaining -= len(leaves)\n"
        "    newLeaves = []\n    for leaf: for its neighbor: degree -= 1; if degree == 1: newLeaves.append\n    leaves = newLeaves\nreturn sorted(leaves)",
        "Each node and edge is removed once: O(n). There are always at most two centers.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda n, edges: (lambda heights: sorted(i for i in range(n) if heights[i] == min(heights)))(
        [
            max(
                _dijkstra(
                    n,
                    [
                        [(b, 1) for a, b in edges if a == u] + [(a, 1) for a, b in edges if b == u]
                        for u in range(n)
                    ],
                    s,
                )
            )
            for s in range(n)
        ]
    ),
    java="""
        import java.util.*;

        class Solution {
            public int[] findMinHeightTrees(int n, int[][] edges) {
                if (n == 1) return new int[] {0};
                List<List<Integer>> adj = new ArrayList<>();
                for (int i = 0; i < n; i++) adj.add(new ArrayList<>());
                int[] degree = new int[n];
                for (int[] e : edges) { adj.get(e[0]).add(e[1]); adj.get(e[1]).add(e[0]); degree[e[0]]++; degree[e[1]]++; }
                List<Integer> leaves = new ArrayList<>();
                for (int i = 0; i < n; i++) if (degree[i] == 1) leaves.add(i);
                int remaining = n;
                while (remaining > 2) {
                    remaining -= leaves.size();
                    List<Integer> next = new ArrayList<>();
                    for (int leaf : leaves) for (int v : adj.get(leaf)) if (--degree[v] == 1) next.add(v);
                    leaves = next;
                }
                Collections.sort(leaves);
                return leaves.stream().mapToInt(Integer::intValue).toArray();
            }
        }
    """,
    tests=[
        {"n": 4, "edges": [[1, 0], [1, 2], [1, 3]]},
        {"n": 6, "edges": [[3, 0], [3, 1], [3, 2], [3, 4], [5, 4]]},
        {"n": 1, "edges": []},
        {"n": 2, "edges": [[0, 1]]},
    ],
    gen=lambda r: (lambda n: {"n": n, "edges": [[i, r.randint(0, i - 1)] for i in range(1, n)]})(
        r.randint(1, 9)
    ),
)
