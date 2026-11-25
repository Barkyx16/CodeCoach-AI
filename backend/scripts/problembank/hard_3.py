"""Hard problems, part 3: parsing, simulation, heaps, math and geometry."""

from collections import Counter
from functools import lru_cache
from itertools import combinations

from scripts.problembank import P, ints, word

ONES = [
    "",
    "One",
    "Two",
    "Three",
    "Four",
    "Five",
    "Six",
    "Seven",
    "Eight",
    "Nine",
    "Ten",
    "Eleven",
    "Twelve",
    "Thirteen",
    "Fourteen",
    "Fifteen",
    "Sixteen",
    "Seventeen",
    "Eighteen",
    "Nineteen",
]
TENS = ["", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"]


def _english(n):
    if n == 0:
        return "Zero"

    def chunk(x):
        words = []
        if x >= 100:
            words += [ONES[x // 100], "Hundred"]
            x %= 100
        if x >= 20:
            words.append(TENS[x // 10])
            x %= 10
        if x:
            words.append(ONES[x])
        return words

    out = []
    for value, name in ((10**9, "Billion"), (10**6, "Million"), (10**3, "Thousand"), (1, "")):
        if n >= value:
            out += chunk(n // value) + ([name] if name else [])
            n %= value
    return " ".join(out)


def _justify(words, maxWidth):
    lines, i = [], 0
    while i < len(words):
        j, length = i, 0
        while j < len(words) and length + len(words[j]) + (j - i) <= maxWidth:
            length += len(words[j])
            j += 1
        line_words = words[i:j]
        if j == len(words) or len(line_words) == 1:
            line = " ".join(line_words)
            lines.append(line + " " * (maxWidth - len(line)))
        else:
            gaps, spaces = len(line_words) - 1, maxWidth - length
            line = ""
            for k, w in enumerate(line_words[:-1]):
                line += w + " " * (spaces // gaps + (1 if k < spaces % gaps else 0))
            lines.append(line + line_words[-1])
        i = j
    return lines


def _atoms(formula):
    def parse(i):
        counts = Counter()
        while i < len(formula) and formula[i] != ")":
            if formula[i] == "(":
                inner, i = parse(i + 1)
                i += 1
                j = i
                while j < len(formula) and formula[j].isdigit():
                    j += 1
                mult = int(formula[i:j] or 1)
                i = j
                for k, v in inner.items():
                    counts[k] += v * mult
            else:
                j = i + 1
                while j < len(formula) and formula[j].islower():
                    j += 1
                name = formula[i:j]
                k = j
                while k < len(formula) and formula[k].isdigit():
                    k += 1
                counts[name] += int(formula[j:k] or 1)
                i = k
        return counts, i

    counts, _ = parse(0)
    return "".join(name + (str(counts[name]) if counts[name] > 1 else "") for name in sorted(counts))


def _drive(target, fuel, stations, chosen):
    """Simulate the trip, refueling only at the chosen stations."""
    for i, (pos, gas) in enumerate(stations):
        if pos > target:
            break
        if fuel < pos:
            return False
        if i in chosen:
            fuel += gas
    return fuel >= target


def _skyline(buildings):
    xs = sorted({x for b in buildings for x in b[:2]})
    out, prev = [], 0
    for x in xs:
        h = max([b[2] for b in buildings if b[0] <= x < b[1]] or [0])
        if h != prev:
            out.append([x, h])
            prev = h
    return out


def _lfu(capacity, ops):
    store, freq, used, out = {}, {}, {}, []
    for clock, op in enumerate(ops, start=1):
        parts = op.split()
        key = int(parts[1])
        if parts[0] == "get":
            if key in store:
                freq[key] += 1
                used[key] = clock
                out.append(store[key])
            else:
                out.append(-1)
        else:
            if key not in store and len(store) == capacity:
                victim = min(store, key=lambda k: (freq[k], used[k]))
                del store[victim], freq[victim], used[victim]
            store[key] = int(parts[2])
            freq[key] = freq.get(key, 0) + 1
            used[key] = clock
    return out


P(
    slug="basic-calculator",
    title="Basic Calculator",
    difficulty="hard",
    topics=["stacks", "strings", "math"],
    summary="Evaluate an expression with +, -, parentheses and spaces.",
    statement="""
        Evaluate the expression `s`, which contains non-negative integers, `+`, `-`, parentheses and spaces.
        A `-` may also be unary (`-(2 + 3)` or `-4`). Don't use built-in expression evaluators. The result fits in an int.
    """,
    constraints=["1 <= s.length <= 3 * 10^5", "s is a valid expression"],
    sig="int calculate(String s)",
    hints=[
        "Without parentheses, you'd just keep a running result and the sign of the next number.",
        "On `(`, push the current result and sign, and start fresh. On `)`, finish the inner result and combine it with what you pushed.",
        "result, sign, num = 0, 1, 0\nstack = []\nfor c in s:\n    if digit: num = num*10 + c\n    elif c in '+-': result += sign*num; num = 0; sign = 1 if c == '+' else -1\n"
        "    elif c == '(': stack.push(result, sign); result, sign = 0, 1\n    elif c == ')': result += sign*num; num = 0; result = stack.popSign()*result + stack.popResult()\nreturn result + sign*num",
        'One pass with a stack of saved (result, sign) pairs: O(n). Treating `-` as "sign = -1" handles unary minus for free.',
    ],
    time="O(n)",
    space="O(n)",
    model=lambda s: eval(s.replace(" ", "")),  # noqa: S307 - trusted test inputs only
    java="""
        import java.util.*;

        class Solution {
            public int calculate(String s) {
                Deque<Integer> stack = new ArrayDeque<>();
                int result = 0, sign = 1, num = 0;
                for (char c : s.toCharArray()) {
                    if (Character.isDigit(c)) num = num * 10 + (c - '0');
                    else if (c == '+' || c == '-') { result += sign * num; num = 0; sign = c == '+' ? 1 : -1; }
                    else if (c == '(') { stack.push(result); stack.push(sign); result = 0; sign = 1; }
                    else if (c == ')') { result += sign * num; num = 0; result = stack.pop() * result + stack.pop(); }
                }
                return result + sign * num;
            }
        }
    """,
    tests=[
        {"s": "1 + 1"},
        {"s": " 2-1 + 2 "},
        {"s": "(1+(4+5+2)-3)+(6+8)"},
        {"s": "-(2 + 3)"},
        {"s": "- (3 - (4 + 5))"},
        {"s": "2147483647"},
    ],
    gen=lambda r: {
        "s": r.choice(["1-(2-(3-4))", "10 - (5 + 2) + -(1)", "((7))", "-1+2-(3+(4-5))", "100-(99-(98-97))"])
    },
    gen_count=3,
)

P(
    slug="calculator-with-precedence",
    title="Calculator With Precedence",
    difficulty="hard",
    topics=["stacks", "recursion", "strings"],
    summary="Evaluate +, -, *, / with parentheses and the usual precedence.",
    statement="""
        Evaluate `s`, which contains non-negative integers, `+ - * /`, parentheses and spaces. `*` and `/` bind
        tighter than `+` and `-`; division truncates toward zero. No unary operators. Results fit in an int.
    """,
    constraints=["1 <= s.length <= 10^4", "s is a valid expression, no division by zero"],
    sig="int calculatePrecedence(String s)",
    hints=[
        "Handle one parentheses level at a time; inside a level, `*` and `/` apply immediately, `+` and `-` wait.",
        "Recursive descent: `expression := term (('+' | '-') term)*`, `term := factor (('*' | '/') factor)*`, `factor := number | '(' expression ')'`.",
        "def expr(): v = term(); while next is + or -: v = v ± term(); return v\ndef term(): v = factor(); while next is * or /: v = v */ factor(); return v\n"
        "def factor(): if '(' : v = expr(); expect ')'; return v\n           else: return number",
        "Each character is consumed once: O(n). The grammar encodes precedence, so no operator tables are needed.",
    ],
    time="O(n)",
    space="O(depth)",
    model=lambda s: _eval_int(s.replace(" ", "")),
    java="""
        class Solution {
            private String s;
            private int i;
            private int expr() {
                int v = term();
                while (i < s.length() && (s.charAt(i) == '+' || s.charAt(i) == '-')) {
                    char op = s.charAt(i++);
                    int t = term();
                    v = op == '+' ? v + t : v - t;
                }
                return v;
            }
            private int term() {
                int v = factor();
                while (i < s.length() && (s.charAt(i) == '*' || s.charAt(i) == '/')) {
                    char op = s.charAt(i++);
                    int f = factor();
                    v = op == '*' ? v * f : v / f;
                }
                return v;
            }
            private int factor() {
                if (s.charAt(i) == '(') { i++; int v = expr(); i++; return v; }
                int v = 0;
                while (i < s.length() && Character.isDigit(s.charAt(i))) v = v * 10 + (s.charAt(i++) - '0');
                return v;
            }
            public int calculatePrecedence(String s) {
                this.s = s.replace(" ", "");
                this.i = 0;
                return expr();
            }
        }
    """,
    tests=[
        {"s": "3+2*2"},
        {"s": " 3/2 "},
        {"s": "2*(5+5*2)/3+(6/2+8)"},
        {"s": "(2+6*3+5-(3*14/7+2)*5)+3"},
        {"s": "14-3/2"},
    ],
    gen=lambda r: {
        "s": r.choice(["7-(3*(2+1))/2", "((8/3)*3)-1", "1+2*3-4/2", "100/(9-2*2)", "6*(4-(8/2))+9"])
    },
    gen_count=3,
)


def _eval_int(s):
    tokens = []
    i = 0
    while i < len(s):
        if s[i].isdigit():
            j = i
            while j < len(s) and s[j].isdigit():
                j += 1
            tokens.append(int(s[i:j]))
            i = j
        else:
            tokens.append(s[i])
            i += 1
    pos = 0

    def expr():
        nonlocal pos
        v = term()
        while pos < len(tokens) and tokens[pos] in ("+", "-"):
            op = tokens[pos]
            pos += 1
            t = term()
            v = v + t if op == "+" else v - t
        return v

    def term():
        nonlocal pos
        v = factor()
        while pos < len(tokens) and tokens[pos] in ("*", "/"):
            op = tokens[pos]
            pos += 1
            f = factor()
            v = v * f if op == "*" else int(v / f)
        return v

    def factor():
        nonlocal pos
        if tokens[pos] == "(":
            pos += 1
            v = expr()
            pos += 1
            return v
        v = tokens[pos]
        pos += 1
        return v

    return expr()


P(
    slug="text-justification",
    title="Text Justification",
    difficulty="hard",
    topics=["strings", "simulation", "greedy"],
    summary="Lay out words into fully justified lines of a fixed width.",
    statement="""
        Format `words` into lines of exactly `maxWidth` characters. Pack as many words as fit on each line (with at
        least one space between words). Spread extra spaces as evenly as possible between words; if they don't
        divide evenly, the leftmost gaps get more. The last line, and any line with a single word, is
        left-justified with single spaces and padded with spaces on the right.
    """,
    constraints=["1 <= words.length <= 300", "1 <= words[i].length <= maxWidth <= 100"],
    sig="String[] fullJustify(String[] words, int maxWidth)",
    hints=[
        "Decide which words go on each line first, then worry about spacing.",
        "Greedily add words while `letters + (words - 1) <= maxWidth`. For a normal line, spread `maxWidth - letters` spaces over `words - 1` gaps.",
        "while words remain:\n    take as many as fit\n    if last line or one word: join with ' ' and pad right\n"
        "    else: gaps = count - 1; each gap gets spaces // gaps, and the first spaces % gaps gaps get one more\nreturn lines",
        "O(total characters). The two special cases (last line, single word) are where most bugs hide.",
    ],
    time="O(n · maxWidth)",
    space="O(n · maxWidth)",
    model=_justify,
    java="""
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
    """,
    tests=[
        {"words": ["This", "is", "an", "example", "of", "text", "justification."], "maxWidth": 16},
        {"words": ["What", "must", "be", "acknowledgment", "shall", "be"], "maxWidth": 16},
        {
            "words": [
                "Science",
                "is",
                "what",
                "we",
                "understand",
                "well",
                "enough",
                "to",
                "explain",
                "to",
                "a",
                "computer.",
                "Art",
                "is",
                "everything",
                "else",
                "we",
                "do",
            ],
            "maxWidth": 20,
        },
        {"words": ["a"], "maxWidth": 1},
    ],
    gen=lambda r: (lambda w: {"words": [word(r, 1, w) for _ in range(r.randint(1, 10))], "maxWidth": w})(
        r.randint(3, 12)
    ),
)

P(
    slug="integer-to-english",
    title="Integer to English Words",
    difficulty="hard",
    topics=["strings", "math", "recursion"],
    summary="Spell out a number in English.",
    statement="""
        Return the English words for the non-negative integer `num`, capitalized as in the examples:
        `123` → `"One Hundred Twenty Three"`, `1234567` → `"One Million Two Hundred Thirty Four Thousand Five Hundred Sixty Seven"`.
        Zero is `"Zero"`. No "and", no hyphens.
    """,
    constraints=["0 <= num <= 2^31 - 1"],
    sig="String numberToWords(int num)",
    hints=[
        "Numbers repeat in groups of three digits: billions, millions, thousands, ones.",
        "Write a helper for 0-999 (hundreds, then tens/teens, then ones) and apply it to each group with its scale word.",
        "for value, name in [(1e9, 'Billion'), (1e6, 'Million'), (1e3, 'Thousand'), (1, '')]:\n    if num >= value: words += helper(num // value) + [name]; num %= value\nreturn ' '.join(words)",
        'Constant work (at most four groups). The teen numbers (10-19) need their own words; skipping empty groups avoids "Zero Thousand".',
    ],
    time="O(1)",
    space="O(1)",
    model=lambda num: _english(num),
    java="""
        class Solution {
            private static final String[] ONES = {"", "One", "Two", "Three", "Four", "Five", "Six", "Seven", "Eight", "Nine", "Ten",
                "Eleven", "Twelve", "Thirteen", "Fourteen", "Fifteen", "Sixteen", "Seventeen", "Eighteen", "Nineteen"};
            private static final String[] TENS = {"", "", "Twenty", "Thirty", "Forty", "Fifty", "Sixty", "Seventy", "Eighty", "Ninety"};
            private void chunk(int x, StringBuilder sb) {
                if (x >= 100) { sb.append(' ').append(ONES[x / 100]).append(" Hundred"); x %= 100; }
                if (x >= 20) { sb.append(' ').append(TENS[x / 10]); x %= 10; }
                if (x > 0) sb.append(' ').append(ONES[x]);
            }
            public String numberToWords(int num) {
                if (num == 0) return "Zero";
                int[] values = {1_000_000_000, 1_000_000, 1_000, 1};
                String[] names = {" Billion", " Million", " Thousand", ""};
                StringBuilder sb = new StringBuilder();
                for (int i = 0; i < 4; i++)
                    if (num >= values[i]) { chunk(num / values[i], sb); sb.append(names[i]); num %= values[i]; }
                return sb.toString().trim();
            }
        }
    """,
    tests=[
        {"num": 123},
        {"num": 12345},
        {"num": 1234567},
        {"num": 0},
        {"num": 1000010},
        {"num": 2147483647},
        {"num": 100},
    ],
    gen=lambda r: {"num": r.choice([r.randint(0, 999), r.randint(0, 10**6), r.randint(0, 2**31 - 1)])},
)

P(
    slug="min-window-subsequence",
    title="Minimum Window Subsequence",
    difficulty="hard",
    topics=["strings", "dynamic-programming", "two-pointers"],
    summary="Shortest substring of s1 that contains s2 as a subsequence.",
    statement="""
        Return the shortest substring of `s1` that contains `s2` as a subsequence (in order, not necessarily
        contiguous). If several are equally short, return the leftmost. If none exists, return `""`.
    """,
    constraints=["1 <= s1.length <= 2 * 10^4", "1 <= s2.length <= 100"],
    sig="String minWindowSubsequence(String s1, String s2)",
    hints=[
        "Find a window that ends where s2 is fully matched, then tighten its start.",
        "Scan forward matching s2; when it's complete, scan backward from that end matching s2 in reverse to find the latest possible start.",
        "i = 0\nwhile i < len(s1):\n    match s2 forward from i to find end e (or stop)\n    walk back from e matching s2 backwards to find start b\n"
        "    record s1[b:e+1] if shorter\n    i = b + 1\nreturn best",
        "The backward pass gives the shortest window ending at that position. Restarting from `b + 1` makes it O(|s1| × |s2|) worst case.",
    ],
    time="O(n m)",
    space="O(1)",
    model=lambda s1, s2: min(
        (
            s1[i:j]
            for i in range(len(s1))
            for j in range(i + 1, len(s1) + 1)
            if (lambda it: all(c in it for c in s2))(iter(s1[i:j]))
        ),
        key=len,
        default="",
    ),
    java="""
        class Solution {
            public String minWindowSubsequence(String s1, String s2) {
                int n = s1.length(), m = s2.length(), bestStart = -1, bestLen = Integer.MAX_VALUE, i = 0;
                while (i < n) {
                    int k = 0, e = i;
                    while (e < n) { if (s1.charAt(e) == s2.charAt(k) && ++k == m) break; e++; }
                    if (e == n) break;
                    int b = e;
                    k = m - 1;
                    while (k >= 0) { if (s1.charAt(b) == s2.charAt(k)) k--; b--; }
                    b++;
                    if (e - b + 1 < bestLen) { bestLen = e - b + 1; bestStart = b; }
                    i = b + 1;
                }
                return bestStart == -1 ? "" : s1.substring(bestStart, bestStart + bestLen);
            }
        }
    """,
    tests=[
        {"s1": "abcdebdde", "s2": "bde"},
        {"s1": "jmeqksfrsdcmsiwvaovztaqenprpvnbstl", "s2": "u"},
        {"s1": "aaa", "s2": "a"},
        {"s1": "cnhczmccqouqadqtmjjzl", "s2": "mm"},
    ],
    gen=lambda r: {"s1": word(r, 1, 12, "abc"), "s2": word(r, 1, 3, "abc")},
)

P(
    slug="concatenated-words-substring",
    title="Substrings Made of All the Words",
    difficulty="hard",
    topics=["strings", "sliding-window", "hash-maps"],
    summary="Start indices where every word appears exactly once, back to back.",
    statement="""
        All strings in `words` have the same length. Return (ascending) every index of `s` where a substring starts
        that is a concatenation of all the words in some order, each used exactly as many times as it appears in `words`.
    """,
    constraints=["1 <= s.length <= 10^4", "1 <= words.length <= 5000", "1 <= words[i].length <= 30"],
    sig="int[] findSubstring(String s, String[] words)",
    hints=[
        "The window length is fixed: `len(words) × word length`.",
        "Slide in steps of the word length, once for each starting offset `0..L-1`, keeping counts of words in the window.",
        "need = Counter(words)\nfor offset in range(L):\n    left = offset; window = Counter()\n    for right in range(offset, n - L + 1, L):\n"
        "        w = s[right:right+L]\n        if w not in need: reset window, left = right + L; continue\n        add w; while window[w] > need[w]: remove s[left:left+L]; left += L\n"
        "        if right + L - left == total: record left\nreturn sorted(results)",
        "Each offset's sliding window touches every word position once: O(n × L) overall, versus O(n × k × L) checking every index.",
    ],
    time="O(n L)",
    space="O(k)",
    model=lambda s, words: [
        i
        for i in range(len(s) - len(words) * len(words[0]) + 1)
        if Counter(s[i + k * len(words[0]) : i + (k + 1) * len(words[0])] for k in range(len(words)))
        == Counter(words)
    ],
    java="""
        import java.util.*;

        class Solution {
            public int[] findSubstring(String s, String[] words) {
                int L = words[0].length(), k = words.length, total = L * k, n = s.length();
                Map<String, Integer> need = new HashMap<>();
                for (String w : words) need.merge(w, 1, Integer::sum);
                List<Integer> out = new ArrayList<>();
                for (int offset = 0; offset < L; offset++) {
                    Map<String, Integer> window = new HashMap<>();
                    int left = offset;
                    for (int right = offset; right + L <= n; right += L) {
                        String w = s.substring(right, right + L);
                        if (!need.containsKey(w)) { window.clear(); left = right + L; continue; }
                        window.merge(w, 1, Integer::sum);
                        while (window.get(w) > need.get(w)) { window.merge(s.substring(left, left + L), -1, Integer::sum); left += L; }
                        if (right + L - left == total) out.add(left);
                    }
                }
                Collections.sort(out);
                return out.stream().mapToInt(Integer::intValue).toArray();
            }
        }
    """,
    tests=[
        {"s": "barfoothefoobarman", "words": ["foo", "bar"]},
        {"s": "wordgoodgoodgoodbestword", "words": ["word", "good", "best", "word"]},
        {"s": "barfoofoobarthefoobarman", "words": ["bar", "foo", "the"]},
        {"s": "aaaa", "words": ["aa", "aa"]},
    ],
    gen=lambda r: (
        lambda L: {"s": word(r, 1, 16, "ab"), "words": [word(r, L, L, "ab") for _ in range(r.randint(1, 3))]}
    )(r.randint(1, 2)),
)

P(
    slug="number-of-atoms",
    title="Count Atoms in a Formula",
    difficulty="hard",
    topics=["stacks", "strings", "hash-maps"],
    summary="Expand a chemical formula with nested groups into atom counts.",
    statement="""
        A formula like `"K4(ON(SO3)2)2"` has element names (an upper-case letter plus optional lower-case letters),
        optional counts after elements and after parenthesized groups. Return each element in alphabetical order
        followed by its count (omitted when it's 1): `"K4N2O14S4"`.
    """,
    constraints=["1 <= formula.length <= 1000", "formula is valid", "counts fit in an int"],
    sig="String countOfAtoms(String formula)",
    hints=[
        "Parentheses multiply everything inside them by the number after the closing bracket.",
        "Use a stack of count maps: `(` pushes a new map; `)` pops it, multiplies by the following number, and merges into the map below.",
        "stack = [Counter()]\nwhile i < n:\n    if '(': push Counter()\n    elif ')': inner = pop; read multiplier; add inner * multiplier into stack top\n"
        "    else: read element name and count; stack top[name] += count\nreturn ''.join(name + count for name in sorted)",
        "Each character is read once; merging maps costs at most the number of distinct elements per level.",
    ],
    time="O(n^2) worst case",
    space="O(n)",
    model=_atoms,
    java="""
        import java.util.*;

        class Solution {
            public String countOfAtoms(String formula) {
                Deque<Map<String, Integer>> stack = new ArrayDeque<>();
                stack.push(new TreeMap<>());
                int i = 0, n = formula.length();
                while (i < n) {
                    char c = formula.charAt(i);
                    if (c == '(') { stack.push(new TreeMap<>()); i++; }
                    else if (c == ')') {
                        i++;
                        int j = i;
                        while (j < n && Character.isDigit(formula.charAt(j))) j++;
                        int mult = j > i ? Integer.parseInt(formula.substring(i, j)) : 1;
                        i = j;
                        Map<String, Integer> inner = stack.pop();
                        for (Map.Entry<String, Integer> e : inner.entrySet()) stack.peek().merge(e.getKey(), e.getValue() * mult, Integer::sum);
                    } else {
                        int j = i + 1;
                        while (j < n && Character.isLowerCase(formula.charAt(j))) j++;
                        String name = formula.substring(i, j);
                        int k = j;
                        while (k < n && Character.isDigit(formula.charAt(k))) k++;
                        int count = k > j ? Integer.parseInt(formula.substring(j, k)) : 1;
                        stack.peek().merge(name, count, Integer::sum);
                        i = k;
                    }
                }
                StringBuilder sb = new StringBuilder();
                for (Map.Entry<String, Integer> e : stack.peek().entrySet()) {
                    sb.append(e.getKey());
                    if (e.getValue() > 1) sb.append(e.getValue());
                }
                return sb.toString();
            }
        }
    """,
    tests=[
        {"formula": "H2O"},
        {"formula": "Mg(OH)2"},
        {"formula": "K4(ON(SO3)2)2"},
        {"formula": "Be32"},
        {"formula": "((N42)24(OB40Li30CHe3O48LiNN26)33(C12Li48N30H13HBe31)21(BHN30Li26BCBe47N40)15(H5)16)14"},
    ],
    gen=lambda r: {"formula": r.choice(["C6H12O6", "(H2O)3", "Fe2(SO4)3", "Ca(OH)2(NO3)1", "((Ab)2Cd)3E"])},
    gen_count=3,
)

P(
    slug="count-digit-one",
    title="Count the Digit One",
    difficulty="hard",
    topics=["math"],
    summary="How many times does the digit 1 appear in all numbers up to n?",
    statement="""
        Return the total number of times the digit `1` appears when you write out every integer from `0` to `n`.
    """,
    constraints=["0 <= n <= 10^9"],
    sig="int countDigitOne(int n)",
    hints=[
        "Count position by position: how often is the ones digit 1? The tens digit?",
        "For the digit at place value `p`, split n into `high`, the digit `cur`, and `low`. The count is based on `high`, plus extra depending on `cur`.",
        "count = 0\np = 1\nwhile p <= n:\n    high, cur, low = n // (p*10), (n // p) % 10, n % p\n    count += high * p\n"
        "    if cur == 1: count += low + 1\n    elif cur > 1: count += p\n    p *= 10\nreturn count",
        "One loop per digit: O(log n). Use long arithmetic for `p * 10` near 10^9.",
    ],
    time="O(log n)",
    space="O(1)",
    model=lambda n: sum(str(i).count("1") for i in range(n + 1)) if n <= 2 * 10**5 else None,
    java="""
        class Solution {
            public int countDigitOne(int n) {
                long count = 0;
                for (long p = 1; p <= n; p *= 10) {
                    long high = n / (p * 10), cur = (n / p) % 10, low = n % p;
                    count += high * p;
                    if (cur == 1) count += low + 1;
                    else if (cur > 1) count += p;
                }
                return (int) count;
            }
        }
    """,
    tests=[{"n": 13}, {"n": 0}, {"n": 1}, {"n": 100}, {"n": 199999}, {"n": 111}],
    gen=lambda r: {"n": r.randint(0, 50000)},
)

P(
    slug="super-egg-drop",
    title="Egg Drop With K Eggs",
    difficulty="hard",
    topics=["dynamic-programming", "math", "binary-search"],
    summary="Fewest drops to find the critical floor with k eggs.",
    statement="""
        You have `k` identical eggs and a building with floors `1..n`. There's an unknown floor `f` (0 ≤ f ≤ n):
        eggs dropped above it break, eggs dropped at or below it don't. A broken egg can't be reused. Return the
        minimum number of drops that guarantees you find `f`.
    """,
    constraints=["1 <= k <= 100", "1 <= n <= 10^4"],
    sig="int superEggDrop(int k, int n)",
    hints=[
        "Flip the question: with `m` drops and `k` eggs, how many floors can you fully check?",
        "floors(m, k) = floors(m-1, k-1) + floors(m-1, k) + 1: one drop, then either the egg breaks (search below) or not (search above).",
        "floors = [0]*(k+1)\nm = 0\nwhile floors[k] < n:\n    m += 1\n    for j from k down to 1: floors[j] = floors[j-1] + floors[j] + 1\nreturn m",
        "This runs O(k × answer) steps, and the answer is at most n (with 1 egg) and much smaller otherwise. The direct DP over (eggs, floors) is O(k n^2) or O(k n log n).",
    ],
    time="O(k log n)",
    space="O(k)",
    model=lambda k, n: (
        (lambda f: f(f, k, n))(
            lru_cache(None)(
                lambda f, e, fl: (
                    0
                    if fl == 0
                    else fl
                    if e == 1
                    else 1 + min(max(f(f, e - 1, x - 1), f(f, e, fl - x)) for x in range(1, fl + 1))
                )
            )
        )
        if n <= 120
        else None
    ),
    java="""
        class Solution {
            public int superEggDrop(int k, int n) {
                long[] floors = new long[k + 1];
                int m = 0;
                while (floors[k] < n) {
                    m++;
                    for (int j = k; j >= 1; j--) floors[j] = floors[j - 1] + floors[j] + 1;
                }
                return m;
            }
        }
    """,
    tests=[{"k": 1, "n": 2}, {"k": 2, "n": 6}, {"k": 3, "n": 14}, {"k": 2, "n": 100}, {"k": 1, "n": 1}],
    gen=lambda r: {"k": r.randint(1, 4), "n": r.randint(1, 100)},
)

P(
    slug="lfu-cache",
    title="Simulate an LFU Cache",
    difficulty="hard",
    topics=["hash-maps", "simulation", "heaps"],
    summary="Run get/put on a least-frequently-used cache.",
    statement="""
        Simulate a cache holding at most `capacity` keys. Each operation in `ops` is `"put K V"` or `"get K"`. Each
        key has a use count: `get` of a present key and every `put` add one use. When a put of a new key would exceed
        capacity, first evict the key with the fewest uses; ties go to the least recently used. Return the results of
        all `get` operations (`-1` for a missing key).
    """,
    constraints=["1 <= capacity <= 10^4", "1 <= ops.length <= 2 * 10^5"],
    sig="int[] lfuCache(int capacity, String[] ops)",
    hints=[
        "You need to find the smallest use count quickly and, within it, the oldest key.",
        "Map key → (value, count), map count → insertion-ordered set of keys, and track the current minimum count.",
        "on access: move key from bucket[count] to bucket[count+1]; if bucket[minCount] empties, minCount += 1\n"
        "on put of a new key at capacity: evict the first key of bucket[minCount]; then insert with count 1, minCount = 1",
        "Every operation is O(1). A new key always resets the minimum count to 1.",
    ],
    time="O(1) per op",
    space="O(capacity)",
    model=_lfu,
    java="""
        import java.util.*;

        class Solution {
            public int[] lfuCache(int capacity, String[] ops) {
                Map<Integer, Integer> values = new HashMap<>(), counts = new HashMap<>();
                Map<Integer, LinkedHashSet<Integer>> buckets = new HashMap<>();
                int minCount = 0;
                List<Integer> out = new ArrayList<>();
                for (String op : ops) {
                    String[] p = op.split(" ");
                    int key = Integer.parseInt(p[1]);
                    boolean present = values.containsKey(key);
                    if (p[0].equals("get") && !present) { out.add(-1); continue; }
                    if (!present) {
                        if (values.size() == capacity) {
                            int victim = buckets.get(minCount).iterator().next();
                            buckets.get(minCount).remove(victim);
                            values.remove(victim);
                            counts.remove(victim);
                        }
                        values.put(key, Integer.parseInt(p[2]));
                        counts.put(key, 1);
                        buckets.computeIfAbsent(1, c -> new LinkedHashSet<>()).add(key);
                        minCount = 1;
                        continue;
                    }
                    int c = counts.get(key);
                    buckets.get(c).remove(key);
                    if (c == minCount && buckets.get(c).isEmpty()) minCount++;
                    counts.put(key, c + 1);
                    buckets.computeIfAbsent(c + 1, x -> new LinkedHashSet<>()).add(key);
                    if (p[0].equals("get")) out.add(values.get(key)); else values.put(key, Integer.parseInt(p[2]));
                }
                return out.stream().mapToInt(Integer::intValue).toArray();
            }
        }
    """,
    tests=[
        {
            "capacity": 2,
            "ops": [
                "put 1 1",
                "put 2 2",
                "get 1",
                "put 3 3",
                "get 2",
                "get 3",
                "put 4 4",
                "get 1",
                "get 3",
                "get 4",
            ],
        },
        {"capacity": 1, "ops": ["put 1 1", "get 1", "put 2 2", "get 1", "get 2"]},
        {"capacity": 2, "ops": ["put 1 1", "put 1 7", "put 2 2", "put 3 3", "get 1", "get 2", "get 3"]},
    ],
    gen=lambda r: {
        "capacity": r.randint(1, 3),
        "ops": [
            r.choice([f"put {r.randint(1, 4)} {r.randint(0, 9)}", f"get {r.randint(1, 4)}"])
            for _ in range(r.randint(1, 14))
        ],
    },
)

P(
    slug="running-median",
    title="Running Median",
    difficulty="hard",
    topics=["heaps", "sorting"],
    summary="The median after each new number arrives.",
    statement="""
        Numbers arrive one at a time from `nums`. After each arrival, report the median of everything so far. When
        the count is even, report the **lower** of the two middle values.
    """,
    constraints=["1 <= nums.length <= 10^5"],
    sig="int[] runningMedian(int[] nums)",
    hints=[
        "Re-sorting after every number is O(n^2 log n). Keep the two halves organized instead.",
        "A max-heap for the lower half and a min-heap for the upper half, balanced so the lower half has equal or one more element.",
        "for x in nums:\n    push x into low (max-heap); move low's max to high\n    if len(high) > len(low): move high's min to low\n    out.append(max of low)\nreturn out",
        "Each insertion is O(log n), and the lower median is always the top of the max-heap.",
    ],
    time="O(n log n)",
    space="O(n)",
    model=lambda nums: [sorted(nums[: i + 1])[i // 2] for i in range(len(nums))],
    java="""
        import java.util.*;

        class Solution {
            public int[] runningMedian(int[] nums) {
                PriorityQueue<Integer> low = new PriorityQueue<>(Collections.reverseOrder()), high = new PriorityQueue<>();
                int[] out = new int[nums.length];
                for (int i = 0; i < nums.length; i++) {
                    low.add(nums[i]);
                    high.add(low.poll());
                    if (high.size() > low.size()) low.add(high.poll());
                    out[i] = low.peek();
                }
                return out;
            }
        }
    """,
    tests=[{"nums": [5, 15, 1, 3]}, {"nums": [2]}, {"nums": [1, 2, 3, 4, 5]}, {"nums": [-1, -2, -3]}],
    gen=lambda r: {"nums": ints(r, 1, 15, -20, 20)},
)

P(
    slug="sliding-window-median",
    title="Sliding Window Median",
    difficulty="hard",
    topics=["sliding-window", "heaps", "sorting"],
    summary="Median of every window of size k (lower median when k is even).",
    statement="""
        Return the median of each contiguous window of size `k` in `nums`. When `k` is even, use the **lower** of the
        two middle values.
    """,
    constraints=["1 <= k <= nums.length <= 10^5"],
    sig="int[] medianSlidingWindow(int[] nums, int k)",
    hints=[
        "Each slide adds one value and removes one value.",
        "Keep the window in a sorted structure that supports insert, delete and lookup by rank (a balanced tree, or two multisets).",
        "window = sorted(nums[:k])\nfor i in range(k, n + 1):\n    out.append(window[(k - 1) // 2])\n    if i == n: break\n    remove nums[i - k] from window; insert nums[i]\nreturn out",
        "With two TreeMaps (or heaps with lazy deletion) each slide is O(log k): O(n log k) total.",
    ],
    time="O(n log k)",
    space="O(k)",
    model=lambda nums, k: [sorted(nums[i : i + k])[(k - 1) // 2] for i in range(len(nums) - k + 1)],
    java="""
        import java.util.*;

        class Solution {
            private TreeMap<Integer, Integer> low = new TreeMap<>(), high = new TreeMap<>();
            private int lowSize = 0, highSize = 0;
            private void add(TreeMap<Integer, Integer> m, int x) { m.merge(x, 1, Integer::sum); }
            private void remove(TreeMap<Integer, Integer> m, int x) { if (m.merge(x, -1, Integer::sum) == 0) m.remove(x); }
            private void rebalance() {
                while (lowSize > highSize + 1) { int x = low.lastKey(); remove(low, x); lowSize--; add(high, x); highSize++; }
                while (highSize > lowSize) { int x = high.firstKey(); remove(high, x); highSize--; add(low, x); lowSize++; }
            }
            public int[] medianSlidingWindow(int[] nums, int k) {
                int[] out = new int[nums.length - k + 1];
                for (int i = 0; i < nums.length; i++) {
                    if (lowSize == 0 || nums[i] <= low.lastKey()) { add(low, nums[i]); lowSize++; } else { add(high, nums[i]); highSize++; }
                    if (i >= k) {
                        int old = nums[i - k];
                        if (low.containsKey(old)) { remove(low, old); lowSize--; } else { remove(high, old); highSize--; }
                    }
                    rebalance();
                    if (i >= k - 1) out[i - k + 1] = low.lastKey();
                }
                return out;
            }
        }
    """,
    tests=[
        {"nums": [1, 3, -1, -3, 5, 3, 6, 7], "k": 3},
        {"nums": [1, 2, 3, 4, 2, 3, 1, 4, 2], "k": 3},
        {"nums": [5, 5, 5], "k": 2},
        {"nums": [4], "k": 1},
    ],
    gen=lambda r: (lambda nums: {"nums": nums, "k": r.randint(1, len(nums))})(ints(r, 1, 14, -6, 6)),
)

P(
    slug="smallest-range-k-lists",
    title="Smallest Range Covering K Lists",
    difficulty="hard",
    topics=["heaps", "sliding-window", "sorting"],
    summary="Tightest range that includes a value from every sorted list.",
    statement="""
        `lists` holds `k` sorted lists. Return the smallest range `[a, b]` such that every list has at least one value
        in it. A range is smaller if `b - a` is smaller, or if equal, `a` is smaller.
    """,
    constraints=["1 <= k <= 3500", "1 <= lists[i].length <= 50", "each list is sorted"],
    sig="int[] smallestRange(int[][] lists)",
    hints=[
        "Keep one pointer per list; the current range is from the smallest to the largest pointed value.",
        "A min-heap gives the smallest value. Advance the list it came from (the only move that could shrink the range), tracking the max.",
        "heap = first value of each list; hi = max of them\nwhile true:\n    lo, list, idx = pop min\n    update best with [lo, hi]\n"
        "    if idx + 1 == len(list): break\n    push next value of that list; hi = max(hi, it)\nreturn best",
        "Each value enters the heap once: O(N log k) for N total values.",
    ],
    time="O(N log k)",
    space="O(k)",
    model=lambda lists: min(
        (
            [a, b]
            for a in sorted({v for lst in lists for v in lst})
            for b in sorted({v for lst in lists for v in lst})
            if a <= b and all(any(a <= v <= b for v in lst) for lst in lists)
        ),
        key=lambda ab: (ab[1] - ab[0], ab[0]),
    ),
    java="""
        import java.util.*;

        class Solution {
            public int[] smallestRange(int[][] lists) {
                PriorityQueue<int[]> heap = new PriorityQueue<>((a, b) -> Integer.compare(a[0], b[0]));
                int hi = Integer.MIN_VALUE;
                for (int i = 0; i < lists.length; i++) { heap.add(new int[] {lists[i][0], i, 0}); hi = Math.max(hi, lists[i][0]); }
                int[] best = {heap.peek()[0], hi};
                while (true) {
                    int[] top = heap.poll();
                    int lo = top[0];
                    if ((long) hi - lo < (long) best[1] - best[0] || (hi - lo == best[1] - best[0] && lo < best[0])) best = new int[] {lo, hi};
                    if (top[2] + 1 == lists[top[1]].length) break;
                    int next = lists[top[1]][top[2] + 1];
                    heap.add(new int[] {next, top[1], top[2] + 1});
                    hi = Math.max(hi, next);
                }
                return best;
            }
        }
    """,
    tests=[
        {"lists": [[4, 10, 15, 24, 26], [0, 9, 12, 20], [5, 18, 22, 30]]},
        {"lists": [[1, 2, 3], [1, 2, 3], [1, 2, 3]]},
        {"lists": [[7]]},
    ],
    gen=lambda r: {"lists": [sorted(ints(r, 1, 5, 0, 25)) for _ in range(r.randint(1, 4))]},
)

P(
    slug="kth-smallest-pair-distance",
    title="K-th Smallest Pair Distance",
    difficulty="hard",
    topics=["binary-search", "two-pointers", "sorting"],
    summary="The k-th smallest absolute difference among all pairs.",
    statement="""
        The distance of a pair `(i, j)` with `i < j` is `|nums[i] - nums[j]|`. Return the `k`-th smallest distance
        among all pairs.
    """,
    constraints=["2 <= nums.length <= 10^4", "0 <= nums[i] <= 10^6", "1 <= k <= n(n-1)/2"],
    sig="int smallestDistancePair(int[] nums, int k)",
    hints=[
        "Listing all n^2 distances is too much. Can you count how many distances are at most some value d?",
        "Sort, then count pairs with distance ≤ d using two pointers in O(n). Binary search the smallest d whose count reaches k.",
        "sort nums\nlo, hi = 0, max - min\nwhile lo < hi:\n    mid = (lo + hi) // 2\n    if countAtMost(mid) >= k: hi = mid\n    else: lo = mid + 1\nreturn lo",
        "O(n log n + n log(range)). Binary search on the answer value, not on positions.",
    ],
    time="O(n log n + n log W)",
    space="O(1)",
    model=lambda nums, k: sorted(abs(a - b) for a, b in combinations(nums, 2))[k - 1],
    java="""
        import java.util.*;

        class Solution {
            public int smallestDistancePair(int[] nums, int k) {
                Arrays.sort(nums);
                int lo = 0, hi = nums[nums.length - 1] - nums[0];
                while (lo < hi) {
                    int mid = (lo + hi) >>> 1, count = 0;
                    for (int left = 0, right = 0; right < nums.length; right++) {
                        while (nums[right] - nums[left] > mid) left++;
                        count += right - left;
                    }
                    if (count >= k) hi = mid; else lo = mid + 1;
                }
                return lo;
            }
        }
    """,
    tests=[{"nums": [1, 3, 1], "k": 1}, {"nums": [1, 1, 1], "k": 2}, {"nums": [1, 6, 1], "k": 3}],
    gen=lambda r: (lambda nums: {"nums": nums, "k": r.randint(1, len(nums) * (len(nums) - 1) // 2)})(
        ints(r, 2, 10, 0, 30)
    ),
)

P(
    slug="kth-in-multiplication-table",
    title="K-th Smallest in a Multiplication Table",
    difficulty="hard",
    topics=["binary-search", "math"],
    summary="The k-th smallest entry of an m × n times table.",
    statement="""
        The `m × n` multiplication table has `table[i][j] = i * j` (1-indexed). Return the `k`-th smallest number in it
        (counting duplicates).
    """,
    constraints=["1 <= m, n <= 3 * 10^4", "1 <= k <= m * n"],
    sig="int findKthNumber(int m, int n, int k)",
    hints=[
        "How many entries are at most some value x? Each row i contributes `min(x / i, n)`.",
        "Binary search on x from 1 to m × n for the smallest value whose count is at least k.",
        "lo, hi = 1, m * n\nwhile lo < hi:\n    mid = (lo + hi) // 2\n    count = sum(min(mid // i, n) for i in 1..m)\n    if count >= k: hi = mid\n    else: lo = mid + 1\nreturn lo",
        "O(m log(m n)). The smallest value with count ≥ k must itself be in the table.",
    ],
    time="O(m log(m n))",
    space="O(1)",
    model=lambda m, n, k: sorted(i * j for i in range(1, m + 1) for j in range(1, n + 1))[k - 1],
    java="""
        class Solution {
            public int findKthNumber(int m, int n, int k) {
                int lo = 1, hi = m * n;
                while (lo < hi) {
                    int mid = lo + (hi - lo) / 2;
                    long count = 0;
                    for (int i = 1; i <= m; i++) count += Math.min(mid / i, n);
                    if (count >= k) hi = mid; else lo = mid + 1;
                }
                return lo;
            }
        }
    """,
    tests=[
        {"m": 3, "n": 3, "k": 5},
        {"m": 2, "n": 3, "k": 6},
        {"m": 1, "n": 1, "k": 1},
        {"m": 45, "n": 12, "k": 471},
    ],
    gen=lambda r: (lambda m, n: {"m": m, "n": n, "k": r.randint(1, m * n)})(
        r.randint(1, 15), r.randint(1, 15)
    ),
)

P(
    slug="ipo-maximize-capital",
    title="Maximize Capital With K Projects",
    difficulty="hard",
    topics=["heaps", "greedy", "sorting"],
    summary="Pick up to k affordable projects to grow your capital as much as possible.",
    statement="""
        You start with capital `w`. Project `i` needs at least `capital[i]` to start and adds `profits[i]` to your
        capital when done (you keep the capital you had). You may finish at most `k` projects, one at a time. Return
        your final capital.
    """,
    constraints=["1 <= k <= 10^5", "0 <= w <= 10^9", "1 <= n <= 10^5"],
    sig="int findMaximizedCapital(int k, int w, int[] profits, int[] capital)",
    hints=[
        "At any moment, which affordable project should you do?",
        "The most profitable affordable one. Sort projects by required capital and push newly affordable ones into a max-heap of profits.",
        "sort projects by capital\nheap = max-heap\ni = 0\nrepeat k times:\n    while i < n and capital[i] <= w: push profit[i]; i += 1\n    if heap empty: break\n    w += pop max\nreturn w",
        "Capital only grows, so a project affordable once stays affordable. O(n log n + k log n).",
    ],
    time="O((n + k) log n)",
    space="O(n)",
    model=lambda k, w, profits, capital: (lambda f: f(f, k, w, frozenset()))(
        lru_cache(None)(
            lambda f, left, cash, done: max(
                [cash]
                + (
                    [
                        f(f, left - 1, cash + profits[i], done | {i})
                        for i in range(len(profits))
                        if i not in done and capital[i] <= cash
                    ]
                    if left
                    else []
                )
            )
        )
    ),
    java="""
        import java.util.*;

        class Solution {
            public int findMaximizedCapital(int k, int w, int[] profits, int[] capital) {
                int n = profits.length;
                Integer[] order = new Integer[n];
                for (int i = 0; i < n; i++) order[i] = i;
                Arrays.sort(order, (a, b) -> Integer.compare(capital[a], capital[b]));
                PriorityQueue<Integer> heap = new PriorityQueue<>(Collections.reverseOrder());
                int i = 0;
                for (int round = 0; round < k; round++) {
                    while (i < n && capital[order[i]] <= w) heap.add(profits[order[i++]]);
                    if (heap.isEmpty()) break;
                    w += heap.poll();
                }
                return w;
            }
        }
    """,
    tests=[
        {"k": 2, "w": 0, "profits": [1, 2, 3], "capital": [0, 1, 1]},
        {"k": 3, "w": 0, "profits": [1, 2, 3], "capital": [0, 1, 2]},
        {"k": 1, "w": 0, "profits": [5], "capital": [1]},
    ],
    gen=lambda r: (
        lambda n: {
            "k": r.randint(1, 4),
            "w": r.randint(0, 3),
            "profits": ints(r, n, n, 1, 6),
            "capital": ints(r, n, n, 0, 8),
        }
    )(r.randint(1, 6)),
)

P(
    slug="min-refuel-stops",
    title="Fewest Refueling Stops",
    difficulty="hard",
    topics=["heaps", "greedy", "dynamic-programming"],
    summary="Fewest gas stations needed to reach a destination.",
    statement="""
        A car drives east toward `target` miles away, starting with `startFuel` liters and using one liter per mile.
        `stations[i] = [position, fuel]` (sorted by position). At a station you may take all its fuel. Return the
        fewest stops needed to reach the target, or `-1` if impossible.
    """,
    constraints=[
        "1 <= target, startFuel <= 10^9",
        "0 <= stations.length <= 500",
        "0 < position < target, sorted ascending",
    ],
    sig="int minRefuelStops(int target, int startFuel, int[][] stations)",
    hints=[
        "Drive as far as you can; only stop when you have to, and then use the best station you already passed.",
        "Keep a max-heap of fuel from stations you've passed. When you can't reach the next point, refuel from the biggest passed station.",
        "heap = []; fuel = startFuel; stops = 0\nfor pos, gas in stations + [(target, 0)]:\n    while fuel < pos:\n        if heap empty: return -1\n"
        "        fuel += pop max; stops += 1\n    push gas\nreturn stops",
        "Deciding retroactively which stations to use is the greedy trick: O(n log n).",
    ],
    time="O(n log n)",
    space="O(n)",
    model=lambda target, startFuel, stations: next(
        (
            k
            for k in range(len(stations) + 1)
            if any(_drive(target, startFuel, stations, set(c)) for c in combinations(range(len(stations)), k))
        ),
        -1,
    ),
    java="""
        import java.util.*;

        class Solution {
            public int minRefuelStops(int target, int startFuel, int[][] stations) {
                PriorityQueue<Integer> heap = new PriorityQueue<>(Collections.reverseOrder());
                long fuel = startFuel;
                int stops = 0;
                for (int i = 0; i <= stations.length; i++) {
                    if (i < stations.length && stations[i][0] >= target) continue;
                    int pos = i == stations.length ? target : stations[i][0];
                    while (fuel < pos) {
                        if (heap.isEmpty()) return -1;
                        fuel += heap.poll();
                        stops++;
                    }
                    if (i < stations.length) heap.add(stations[i][1]);
                }
                return stops;
            }
        }
    """,
    tests=[
        {"target": 1, "startFuel": 1, "stations": []},
        {"target": 100, "startFuel": 1, "stations": [[10, 100]]},
        {"target": 100, "startFuel": 10, "stations": [[10, 60], [20, 30], [30, 30], [60, 40]]},
    ],
    gen=lambda r: (
        lambda t: {
            "target": t,
            "startFuel": r.randint(1, 15),
            "stations": [
                [p, r.randint(1, 15)] for p in sorted(r.sample(range(1, t), min(t - 1, r.randint(0, 5))))
            ],
        }
    )(r.randint(5, 40)),
)

P(
    slug="patching-array",
    title="Patch an Array to Cover 1..n",
    difficulty="hard",
    topics=["greedy", "math"],
    summary="Fewest numbers to add so every value 1..n is a subset sum.",
    statement="""
        `nums` is sorted ascending. Add the fewest numbers so that every integer in `[1, n]` can be formed as the sum
        of some elements of the array (each used at most once). Return how many numbers you must add.
    """,
    constraints=["1 <= nums.length <= 1000", "1 <= nums[i] <= 10^4", "1 <= n <= 2^31 - 1"],
    sig="int minPatches(int[] nums, int n)",
    hints=[
        "Suppose every value in `[1, miss)` is already reachable. What does adding a number x ≤ miss do?",
        "It extends the reachable range to `[1, miss + x)`. If the next number is bigger than `miss`, patch with `miss` itself (the largest helpful number).",
        "miss = 1; i = patches = 0\nwhile miss <= n:\n    if i < len(nums) and nums[i] <= miss: miss += nums[i]; i += 1\n    else: miss += miss; patches += 1\nreturn patches",
        "Each patch doubles the range, so patches are O(log n): O(len(nums) + log n). Use a long for `miss`.",
    ],
    time="O(m + log n)",
    space="O(1)",
    model=lambda nums, n: (
        next(
            p
            for p in range(0, 40)
            if any(
                set(range(1, n + 1))
                <= __import__("functools").reduce(
                    lambda acc, x: acc | {a + x for a in acc}, list(nums) + list(extra), {0}
                )
                for extra in __import__("itertools").combinations_with_replacement(range(1, n + 1), p)
            )
        )
        if n <= 30
        else None
    ),
    java="""
        class Solution {
            public int minPatches(int[] nums, int n) {
                long miss = 1;
                int i = 0, patches = 0;
                while (miss <= n) {
                    if (i < nums.length && nums[i] <= miss) miss += nums[i++];
                    else { miss += miss; patches++; }
                }
                return patches;
            }
        }
    """,
    tests=[
        {"nums": [1, 3], "n": 6},
        {"nums": [1, 5, 10], "n": 20},
        {"nums": [1, 2, 2], "n": 5},
        {"nums": [10], "n": 9},
    ],
    gen=lambda r: {"nums": sorted(ints(r, 1, 4, 1, 12)), "n": r.randint(1, 25)},
)

P(
    slug="max-chunks-sorted-two",
    title="Most Chunks to Sort an Array",
    difficulty="hard",
    topics=["stacks", "sorting", "greedy"],
    summary="Split into the most pieces that, sorted individually, sort the whole array.",
    statement="""
        Split `arr` into as many contiguous chunks as possible so that sorting each chunk on its own and joining them
        gives the fully sorted array. Values may repeat. Return the maximum number of chunks.
    """,
    constraints=["1 <= arr.length <= 2000", "0 <= arr[i] <= 10^8"],
    sig="int maxChunksToSorted(int[] arr)",
    hints=[
        "A chunk boundary is valid when everything before it is ≤ everything after it.",
        "Keep a stack of chunk maximums. A new value smaller than the top merges chunks until the top is ≤ it.",
        "stack = []\nfor x in arr:\n    biggest = x\n    while stack and stack[-1] > x: biggest = max(biggest, stack.pop())\n    stack.append(biggest)\nreturn len(stack)",
        "Each value is pushed and popped at most once: O(n). (Comparing prefix max with suffix min also works in O(n).)",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda arr: 1 + sum(1 for i in range(1, len(arr)) if max(arr[:i]) <= min(arr[i:])),
    java="""
        import java.util.*;

        class Solution {
            public int maxChunksToSorted(int[] arr) {
                Deque<Integer> stack = new ArrayDeque<>();
                for (int x : arr) {
                    int biggest = x;
                    while (!stack.isEmpty() && stack.peek() > x) biggest = Math.max(biggest, stack.pop());
                    stack.push(biggest);
                }
                return stack.size();
            }
        }
    """,
    tests=[{"arr": [5, 4, 3, 2, 1]}, {"arr": [2, 1, 3, 4, 4]}, {"arr": [1, 1, 0, 0, 1]}, {"arr": [7]}],
    gen=lambda r: {"arr": ints(r, 1, 14, 0, 6)},
)

P(
    slug="reaching-points",
    title="Reaching Points",
    difficulty="hard",
    topics=["math"],
    summary="Can (sx, sy) become (tx, ty) by adding one coordinate to the other?",
    statement="""
        A move turns `(x, y)` into `(x + y, y)` or `(x, x + y)`. Starting from `(sx, sy)`, return `true` if you can
        reach `(tx, ty)`. All values are positive.
    """,
    constraints=["1 <= sx, sy, tx, ty <= 10^9"],
    sig="boolean reachingPoints(int sx, int sy, int tx, int ty)",
    hints=[
        "Going forward branches. Going backward from the target doesn't: the larger coordinate must have been made from the smaller one.",
        "Work backwards with modulo to skip many identical steps: if `tx > ty`, then `tx %= ty` (but stop at `sx`).",
        "while tx >= sx and ty >= sy:\n    if tx == sx and ty == sy: return true\n    if tx > ty:\n        if ty == sy: return (tx - sx) % ty == 0\n        tx %= ty\n"
        "    else:\n        if tx == sx: return (ty - sy) % tx == 0\n        ty %= tx\nreturn false",
        "Like Euclid's algorithm, this takes O(log max) steps. The special cases when one coordinate already matches are where solutions usually go wrong.",
    ],
    time="O(log max)",
    space="O(1)",
    model=lambda sx, sy, tx, ty: (
        (lambda f: f(f, tx, ty))(
            lambda f, x, y: (
                (x, y) == (sx, sy)
                or (x >= sx and y >= sy and x != y and (f(f, x - y, y) if x > y else f(f, x, y - x)))
            )
        )
        if tx + ty < 400
        else None
    ),
    java="""
        class Solution {
            public boolean reachingPoints(int sx, int sy, int tx, int ty) {
                while (tx >= sx && ty >= sy) {
                    if (tx == sx && ty == sy) return true;
                    if (tx > ty) {
                        if (ty == sy) return (tx - sx) % ty == 0;
                        tx %= ty;
                    } else if (ty > tx) {
                        if (tx == sx) return (ty - sy) % tx == 0;
                        ty %= tx;
                    } else return false;
                }
                return false;
            }
        }
    """,
    tests=[
        {"sx": 1, "sy": 1, "tx": 3, "ty": 5},
        {"sx": 1, "sy": 1, "tx": 2, "ty": 2},
        {"sx": 1, "sy": 1, "tx": 1, "ty": 1},
        {"sx": 3, "sy": 7, "tx": 3, "ty": 4},
        {"sx": 2, "sy": 3, "tx": 8, "ty": 3},
    ],
    gen=lambda r: {
        "sx": r.randint(1, 5),
        "sy": r.randint(1, 5),
        "tx": r.randint(1, 60),
        "ty": r.randint(1, 60),
    },
)

P(
    slug="perfect-rectangle",
    title="Do Rectangles Tile a Perfect Rectangle?",
    difficulty="hard",
    topics=["math", "hash-sets"],
    summary="Check that axis-aligned rectangles exactly cover one big rectangle.",
    statement="""
        `rectangles[i] = [x1, y1, x2, y2]` (bottom-left and top-right corners). Return `true` if together they
        exactly cover a single rectangular region with no gaps and no overlaps.
    """,
    constraints=["1 <= rectangles.length <= 2 * 10^4", "-10^5 <= coordinates <= 10^5"],
    sig="boolean isRectangleCover(int[][] rectangles)",
    hints=[
        "Two checks together are enough: total area, and how corners appear.",
        "The total area must equal the bounding box area. Every corner point must appear an even number of times, except the bounding box's four corners, which appear exactly once.",
        "area = sum of areas; bound = min/max of all corners\ncorners = set toggled for each rectangle's 4 corners\n"
        "return area == bound area and corners == the 4 bounding corners",
        "O(n) with a hash set. Overlaps make the area too large or leave extra odd corners; gaps do the opposite.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda rectangles: (
        lambda xs1, ys1, xs2, ys2: (
            lambda cells: (
                sum(cells.values()) == (xs2 - xs1) * (ys2 - ys1)
                and all(v == 1 for v in cells.values())
                and len(cells) == (xs2 - xs1) * (ys2 - ys1)
            )
        )(Counter((x, y) for a, b, c, d in rectangles for x in range(a, c) for y in range(b, d)))
    )(
        min(r[0] for r in rectangles),
        min(r[1] for r in rectangles),
        max(r[2] for r in rectangles),
        max(r[3] for r in rectangles),
    ),
    java="""
        import java.util.*;

        class Solution {
            public boolean isRectangleCover(int[][] rectangles) {
                long area = 0;
                int x1 = Integer.MAX_VALUE, y1 = Integer.MAX_VALUE, x2 = Integer.MIN_VALUE, y2 = Integer.MIN_VALUE;
                Set<String> corners = new HashSet<>();
                for (int[] r : rectangles) {
                    area += (long) (r[2] - r[0]) * (r[3] - r[1]);
                    x1 = Math.min(x1, r[0]); y1 = Math.min(y1, r[1]); x2 = Math.max(x2, r[2]); y2 = Math.max(y2, r[3]);
                    for (String c : new String[] {r[0] + "," + r[1], r[0] + "," + r[3], r[2] + "," + r[1], r[2] + "," + r[3]})
                        if (!corners.add(c)) corners.remove(c);
                }
                if (area != (long) (x2 - x1) * (y2 - y1) || corners.size() != 4) return false;
                return corners.contains(x1 + "," + y1) && corners.contains(x1 + "," + y2) && corners.contains(x2 + "," + y1) && corners.contains(x2 + "," + y2);
            }
        }
    """,
    tests=[
        {"rectangles": [[1, 1, 3, 3], [3, 1, 4, 2], [3, 2, 4, 4], [1, 3, 2, 4], [2, 3, 3, 4]]},
        {"rectangles": [[1, 1, 2, 3], [1, 3, 2, 4], [3, 1, 4, 2], [3, 2, 4, 4]]},
        {"rectangles": [[1, 1, 3, 3], [3, 1, 4, 2], [1, 3, 2, 4], [2, 2, 4, 4]]},
        {"rectangles": [[0, 0, 1, 1]]},
    ],
    gen=lambda r: (
        lambda w, h: {
            "rectangles": (lambda cuts: [[a, 0, b, h] for a, b in zip((0, *cuts), (*cuts, w), strict=True)])(
                sorted(r.sample(range(1, w), r.randint(0, w - 1)))
            )
            + ([[0, 0, 1, 1]] if r.random() < 0.4 else [])
        }
    )(r.randint(2, 6), r.randint(1, 4)),
)

P(
    slug="unique-chars-all-substrings",
    title="Sum of Unique Characters Over All Substrings",
    difficulty="hard",
    topics=["strings", "dynamic-programming", "math"],
    summary="Add up, for every substring, how many characters appear exactly once in it.",
    statement="""
        For a string `t`, let `unique(t)` be the number of characters that appear exactly once in `t`. Return the sum of
        `unique(t)` over every substring `t` of `s` (substrings at different positions count separately).
    """,
    constraints=["1 <= s.length <= 10^5", "upper-case letters"],
    sig="int uniqueLetterString(String s)",
    hints=[
        "Turn it around: for each position, in how many substrings is that character the only copy of itself?",
        "If the previous same letter is at `prev` and the next at `next`, position `i` is unique in `(i - prev) × (next - i)` substrings.",
        "for each letter c: positions p1 < p2 < ... (pad with -1 and n)\ntotal = sum((p[k] - p[k-1]) * (p[k+1] - p[k]) for each real position)\nreturn total",
        "Counting contributions per position gives O(n) instead of O(n^2) substrings. The answer fits in an int for n ≤ 10^5 with 26 letters.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda s: sum(
        sum(1 for v in Counter(s[i:j]).values() if v == 1)
        for i in range(len(s))
        for j in range(i + 1, len(s) + 1)
    ),
    java="""
        import java.util.*;

        class Solution {
            public int uniqueLetterString(String s) {
                int n = s.length();
                int[] prev = new int[26], prev2 = new int[26];
                Arrays.fill(prev, -1);
                Arrays.fill(prev2, -1);
                long total = 0;
                for (int i = 0; i < n; i++) {
                    int c = s.charAt(i) - 'A';
                    if (prev[c] != -1) total += (long) (prev[c] - prev2[c]) * (i - prev[c]);
                    prev2[c] = prev[c];
                    prev[c] = i;
                }
                for (int c = 0; c < 26; c++) if (prev[c] != -1) total += (long) (prev[c] - prev2[c]) * (n - prev[c]);
                return (int) total;
            }
        }
    """,
    tests=[{"s": "ABC"}, {"s": "ABA"}, {"s": "LEETCODE"}, {"s": "Z"}],
    gen=lambda r: {"s": word(r, 1, 14, "ABC")},
)

P(
    slug="skyline",
    title="The Skyline Problem",
    difficulty="hard",
    topics=["heaps", "sorting"],
    summary="Outline formed by a set of rectangular buildings.",
    statement="""
        `buildings[i] = [left, right, height]` (sorted by `left`). Return the skyline's key points `[x, h]`, sorted by
        `x`: each is where the outline's height changes to `h`. The last point has height 0. Consecutive points never
        have the same height.
    """,
    constraints=["1 <= buildings.length <= 10^4", "0 <= left < right <= 2^31 - 1", "1 <= height <= 2^31 - 1"],
    sig="int[][] getSkyline(int[][] buildings)",
    hints=[
        "The outline can only change at a building's left or right edge.",
        "Sweep over edge x-coordinates in order, keeping the heights of buildings covering x in a max-heap (removing ones that have ended).",
        "for x in sorted edge positions:\n    add buildings starting at x to the heap; drop heap tops whose right <= x\n    h = top height or 0\n    if h != last height: output [x, h]",
        "O(n log n). Lazy removal (dropping ended buildings only when they reach the top) keeps the heap simple.",
    ],
    time="O(n log n)",
    space="O(n)",
    model=_skyline,
    java="""
        import java.util.*;

        class Solution {
            public int[][] getSkyline(int[][] buildings) {
                TreeSet<Integer> xs = new TreeSet<>();
                for (int[] b : buildings) { xs.add(b[0]); xs.add(b[1]); }
                PriorityQueue<int[]> heap = new PriorityQueue<>((a, b) -> Integer.compare(b[0], a[0]));
                List<int[]> out = new ArrayList<>();
                int i = 0, prev = 0;
                for (int x : xs) {
                    while (i < buildings.length && buildings[i][0] <= x) { heap.add(new int[] {buildings[i][2], buildings[i][1]}); i++; }
                    while (!heap.isEmpty() && heap.peek()[1] <= x) heap.poll();
                    int h = heap.isEmpty() ? 0 : heap.peek()[0];
                    if (h != prev) { out.add(new int[] {x, h}); prev = h; }
                }
                return out.toArray(new int[0][]);
            }
        }
    """,
    tests=[
        {"buildings": [[2, 9, 10], [3, 7, 15], [5, 12, 12], [15, 20, 10], [19, 24, 8]]},
        {"buildings": [[0, 2, 3], [2, 5, 3]]},
        {"buildings": [[1, 2, 1]]},
    ],
    gen=lambda r: {
        "buildings": sorted([[a, a + r.randint(1, 6), r.randint(1, 9)] for a in ints(r, 1, 6, 0, 15)])
    },
)

P(
    slug="max-points-on-line",
    title="Most Points on One Line",
    difficulty="hard",
    topics=["math", "hash-maps"],
    summary="Largest number of points that lie on a single straight line.",
    statement="""
        `points[i] = [x, y]` are distinct points. Return the maximum number of points that lie on one straight line.
    """,
    constraints=["1 <= points.length <= 300", "-10^4 <= x, y <= 10^4", "points are distinct"],
    sig="int maxPoints(int[][] points)",
    hints=[
        "Every line through two points can be identified by one of its points plus a direction.",
        "For each anchor point, group the others by reduced slope `(dy/g, dx/g)` with a normalized sign. The biggest group + 1 is a candidate.",
        "best = 1\nfor i in range(n):\n    counts = {}\n    for j > i:\n        dx, dy = xj - xi, yj - yi; g = gcd(dx, dy); normalize sign\n        counts[(dx/g, dy/g)] += 1\n"
        "    best = max(best, 1 + max(counts.values(), default=0))\nreturn best",
        "O(n^2) with a hash map. Using reduced integer pairs instead of floating-point slopes avoids precision bugs.",
    ],
    time="O(n^2)",
    space="O(n)",
    model=lambda points: max(
        [1]
        + [
            sum(1 for p in points if (b[0] - a[0]) * (p[1] - a[1]) == (b[1] - a[1]) * (p[0] - a[0]))
            for a, b in combinations(points, 2)
        ]
    ),
    java="""
        import java.util.*;

        class Solution {
            private int gcd(int a, int b) { return b == 0 ? a : gcd(b, a % b); }
            public int maxPoints(int[][] points) {
                int n = points.length, best = 1;
                for (int i = 0; i < n; i++) {
                    Map<String, Integer> counts = new HashMap<>();
                    for (int j = i + 1; j < n; j++) {
                        int dx = points[j][0] - points[i][0], dy = points[j][1] - points[i][1];
                        int g = gcd(Math.abs(dx), Math.abs(dy));
                        dx /= g; dy /= g;
                        if (dx < 0 || (dx == 0 && dy < 0)) { dx = -dx; dy = -dy; }
                        best = Math.max(best, 1 + counts.merge(dx + "/" + dy, 1, Integer::sum));
                    }
                }
                return best;
            }
        }
    """,
    tests=[
        {"points": [[1, 1], [2, 2], [3, 3]]},
        {"points": [[1, 1], [3, 2], [5, 3], [4, 1], [2, 3], [1, 4]]},
        {"points": [[0, 0]]},
        {"points": [[0, 0], [0, 5], [0, -3], [2, 2]]},
    ],
    gen=lambda r: {
        "points": [
            list(p) for p in r.sample([(x, y) for x in range(-3, 4) for y in range(-3, 4)], r.randint(1, 8))
        ]
    },
)

P(
    slug="stone-game-three",
    title="Stone Game: Take 1 to 3",
    difficulty="hard",
    topics=["dynamic-programming", "math"],
    summary="Two optimal players take 1-3 stones from the front; who wins?",
    statement="""
        Stones in a row have values `values`. Alice and Bob alternate, Alice first; on each turn a player takes the
        first 1, 2 or 3 remaining stones and adds their values to their score. Both play optimally. Return `"Alice"`,
        `"Bob"` or `"Tie"` depending on who ends with more points.
    """,
    constraints=["1 <= values.length <= 5 * 10^4", "-1000 <= values[i] <= 1000"],
    sig="String stoneGameIII(int[] values)",
    hints=[
        "Score difference is all that matters, from the point of view of whoever moves next.",
        "best[i] = max over taking 1-3 stones of (sum taken) - best[i + taken]: your gain minus the opponent's best difference afterwards.",
        "best = [0]*(n+3)\nfor i from n-1 down to 0:\n    best[i] = max(sum(values[i:i+t]) - best[i+t] for t in 1..3 if i + t <= n)\n"
        "return 'Alice' if best[0] > 0 else 'Bob' if best[0] < 0 else 'Tie'",
        "A minimax DP that tracks the score difference: O(n) time. Negative values mean taking fewer stones can be better.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda values: (lambda d: "Alice" if d > 0 else "Bob" if d < 0 else "Tie")(
        (lambda f: f(f, 0))(
            lru_cache(None)(
                lambda f, i: (
                    0
                    if i >= len(values)
                    else max(sum(values[i : i + t]) - f(f, i + t) for t in (1, 2, 3) if i + t <= len(values))
                )
            )
        )
    ),
    java="""
        class Solution {
            public String stoneGameIII(int[] values) {
                int n = values.length;
                int[] best = new int[n + 3];
                for (int i = n - 1; i >= 0; i--) {
                    best[i] = Integer.MIN_VALUE;
                    int taken = 0;
                    for (int t = 1; t <= 3 && i + t <= n; t++) {
                        taken += values[i + t - 1];
                        best[i] = Math.max(best[i], taken - best[i + t]);
                    }
                }
                return best[0] > 0 ? "Alice" : best[0] < 0 ? "Bob" : "Tie";
            }
        }
    """,
    tests=[
        {"values": [1, 2, 3, 7]},
        {"values": [1, 2, 3, -9]},
        {"values": [1, 2, 3, 6]},
        {"values": [-1, -2, -3]},
    ],
    gen=lambda r: {"values": ints(r, 1, 12, -6, 6)},
)
