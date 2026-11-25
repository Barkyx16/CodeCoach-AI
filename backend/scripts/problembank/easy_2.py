"""Easy problems, part 2: strings and hashing."""

from collections import Counter

from scripts.problembank import P, word

LOWER = "abcdefghijklmnopqrstuvwxyz"

P(
    slug="count-vowels",
    title="Count the Vowels",
    difficulty="easy",
    topics=["strings", "counting"],
    summary="Count the vowels in a string.",
    statement="""
        Return how many characters of `s` are vowels (`a, e, i, o, u`, in either case).
    """,
    constraints=["0 <= s.length <= 10^4", "s contains printable ASCII characters"],
    sig="int countVowels(String s)",
    hints=[
        "Look at each character once.",
        'Lower-case the character (or check both cases) and test membership in "aeiou".',
        "count = 0\nfor c in s:\n    if lower(c) in 'aeiou': count += 1\nreturn count",
        "One pass, O(n) time and O(1) space. Forgetting upper-case vowels is the usual bug.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s: sum(1 for c in s.lower() if c in "aeiou"),
    java="""
        class Solution {
            public int countVowels(String s) {
                int count = 0;
                for (char c : s.toLowerCase().toCharArray()) if ("aeiou".indexOf(c) >= 0) count++;
                return count;
            }
        }
    """,
    tests=[{"s": "Hello World"}, {"s": "rhythm"}, {"s": ""}, {"s": "AEIOUaeiou"}, {"s": "Queue!"}],
    gen=lambda r: {"s": word(r, 0, 30, "abcdeiouXYZAE ")},
)

P(
    slug="valid-anagram",
    title="Valid Anagram",
    difficulty="easy",
    topics=["strings", "hash-maps"],
    summary="Do two strings use exactly the same letters?",
    statement="""
        Return `true` if `t` is an anagram of `s`: it uses exactly the same characters, the same
        number of times, in any order.
    """,
    constraints=["0 <= s.length, t.length <= 5 * 10^4", "lower-case English letters"],
    sig="boolean isAnagram(String s, String t)",
    hints=[
        "Two strings are anagrams when their character counts match.",
        "Count letters of `s` up and letters of `t` down in a 26-slot array; everything must end at zero.",
        "if len(s) != len(t): return false\ncounts = [0]*26\nfor c in s: counts[c] += 1\nfor c in t: counts[c] -= 1\n"
        "return all(c == 0 for c in counts)",
        "Counting is O(n) time and O(1) space (26 slots). Sorting both strings also works but is O(n log n).",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s, t: Counter(s) == Counter(t),
    java="""
        class Solution {
            public boolean isAnagram(String s, String t) {
                if (s.length() != t.length()) return false;
                int[] counts = new int[26];
                for (int i = 0; i < s.length(); i++) { counts[s.charAt(i) - 'a']++; counts[t.charAt(i) - 'a']--; }
                for (int c : counts) if (c != 0) return false;
                return true;
            }
        }
    """,
    tests=[
        {"s": "anagram", "t": "nagaram"},
        {"s": "rat", "t": "car"},
        {"s": "", "t": ""},
        {"s": "a", "t": "ab"},
        {"s": "aab", "t": "abb"},
    ],
    gen=lambda r: (
        lambda s: {
            "s": s,
            "t": "".join(r.sample(s, len(s))) if r.random() < 0.6 else word(r, len(s), len(s), "abc"),
        }
    )(word(r, 0, 12, "abc")),
)

P(
    slug="palindrome-number",
    title="Palindrome Number",
    difficulty="easy",
    topics=["math"],
    summary="Does a number read the same backwards?",
    statement="""
        Return `true` if the integer `x` reads the same forwards and backwards. Negative numbers
        are never palindromes (`-121` reads `121-` backwards).
    """,
    constraints=["-2^31 <= x <= 2^31 - 1"],
    sig="boolean isPalindrome(int x)",
    hints=[
        "Reversing the number and comparing would work. Watch out for overflow.",
        "Reverse only the second half of the digits and compare it with the first half.",
        "if x < 0 or (x % 10 == 0 and x != 0): return false\nrev = 0\nwhile x > rev:\n    rev = rev*10 + x%10\n"
        "    x //= 10\nreturn x == rev or x == rev // 10",
        "Reversing half the digits avoids overflow and runs in O(log x). The `rev // 10` case handles "
        "an odd number of digits, where the middle digit doesn't matter.",
    ],
    time="O(log x)",
    space="O(1)",
    model=lambda x: str(x) == str(x)[::-1],
    java="""
        class Solution {
            public boolean isPalindrome(int x) {
                if (x < 0 || (x % 10 == 0 && x != 0)) return false;
                int rev = 0;
                while (x > rev) { rev = rev * 10 + x % 10; x /= 10; }
                return x == rev || x == rev / 10;
            }
        }
    """,
    tests=[{"x": 121}, {"x": -121}, {"x": 10}, {"x": 0}, {"x": 1221}, {"x": 2147447412}, {"x": 2147483647}],
    gen=lambda r: {
        "x": (lambda h: int(h + h[::-1][r.randint(0, 1) :]))(str(r.randint(1, 9999)))
        if r.random() < 0.5
        else r.randint(0, 10**6)
    },
)

P(
    slug="reverse-words",
    title="Reverse the Words",
    difficulty="easy",
    topics=["strings", "two-pointers"],
    summary="Reverse the order of words in a sentence.",
    statement="""
        Given a string `s` of words separated by spaces, return the words in reverse order joined by
        a single space. `s` may have leading, trailing or repeated spaces; the result must not.
    """,
    constraints=["1 <= s.length <= 10^4", "s contains letters, digits and spaces, and at least one word"],
    sig="String reverseWords(String s)",
    hints=[
        "First get the words out cleanly, then deal with their order.",
        "Split on runs of spaces (ignoring empty pieces), reverse the list, and join with one space.",
        "words = [w for w in s.split(' ') if w]\nreturn ' '.join(reversed(words))",
        'Splitting and joining is O(n). In Java, `s.trim().split("\\\\s+")` gives the words; build the '
        "result with a StringBuilder from the last word to the first.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda s: " ".join(reversed(s.split())),
    java="""
        class Solution {
            public String reverseWords(String s) {
                String[] words = s.trim().split("\\\\s+");
                StringBuilder sb = new StringBuilder();
                for (int i = words.length - 1; i >= 0; i--) {
                    sb.append(words[i]);
                    if (i > 0) sb.append(' ');
                }
                return sb.toString();
            }
        }
    """,
    tests=[{"s": "the sky is blue"}, {"s": "  hello world  "}, {"s": "a good   example"}, {"s": "one"}],
    gen=lambda r: {"s": " ".join(word(r, 1, 5) + " " * r.randint(0, 2) for _ in range(r.randint(1, 6)))},
)

P(
    slug="last-word-length",
    title="Length of the Last Word",
    difficulty="easy",
    topics=["strings"],
    summary="How long is the final word of a sentence?",
    statement="""
        Return the length of the last word in `s`. Words are separated by spaces, and `s` may end
        with spaces.
    """,
    constraints=["1 <= s.length <= 10^4", "s has at least one word"],
    sig="int lengthOfLastWord(String s)",
    hints=[
        "Start from the end of the string.",
        "Skip trailing spaces, then count characters until the next space or the start.",
        "i = len(s) - 1\nwhile s[i] == ' ': i -= 1\nlength = 0\nwhile i >= 0 and s[i] != ' ': length += 1; i -= 1\n"
        "return length",
        "Scanning from the end only touches the last word and any trailing spaces: O(n) worst case, O(1) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s: len(s.split()[-1]),
    java="""
        class Solution {
            public int lengthOfLastWord(String s) {
                int i = s.length() - 1, length = 0;
                while (s.charAt(i) == ' ') i--;
                while (i >= 0 && s.charAt(i) != ' ') { length++; i--; }
                return length;
            }
        }
    """,
    tests=[{"s": "Hello World"}, {"s": "   fly me   to   the moon  "}, {"s": "a"}, {"s": "day "}],
    gen=lambda r: {"s": " ".join(word(r, 1, 8) for _ in range(r.randint(1, 5))) + " " * r.randint(0, 3)},
)

P(
    slug="capitalize-words",
    title="Capitalize Each Word",
    difficulty="easy",
    topics=["strings"],
    summary="Make the first letter of every word upper-case.",
    statement="""
        `s` contains lower-case words separated by single spaces. Return it with the first letter of
        each word in upper case.
    """,
    constraints=["0 <= s.length <= 10^4", "lower-case letters and single spaces, no leading/trailing spaces"],
    sig="String capitalizeWords(String s)",
    hints=[
        "A letter starts a word if it's the first character or follows a space.",
        "Walk the characters; upper-case one when it's at index 0 or the previous character is a space.",
        "out = list(s)\nfor i in range(len(s)):\n    if i == 0 or s[i-1] == ' ': out[i] = upper(s[i])\nreturn ''.join(out)",
        "One pass with a StringBuilder (or char array): O(n). Building with `+` in a loop would be O(n^2) in Java.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda s: " ".join(w[:1].upper() + w[1:] for w in s.split(" ")),
    java="""
        class Solution {
            public String capitalizeWords(String s) {
                char[] out = s.toCharArray();
                for (int i = 0; i < out.length; i++)
                    if (i == 0 || out[i - 1] == ' ') out[i] = Character.toUpperCase(out[i]);
                return new String(out);
            }
        }
    """,
    tests=[{"s": "hello world"}, {"s": "a b c"}, {"s": ""}, {"s": "java"}],
    gen=lambda r: {"s": " ".join(word(r, 1, 6) for _ in range(r.randint(1, 6)))},
)

P(
    slug="count-words",
    title="Count the Words",
    difficulty="easy",
    topics=["strings", "counting"],
    summary="Count space-separated words, ignoring extra spaces.",
    statement="""
        Return the number of words in `s`. A word is a maximal run of non-space characters; `s` may
        contain extra spaces anywhere.
    """,
    constraints=["0 <= s.length <= 10^4"],
    sig="int countWords(String s)",
    hints=[
        "A new word starts where a non-space character follows a space (or the start).",
        "Count positions `i` where `s[i] != ' '` and (`i == 0` or `s[i-1] == ' '`).",
        "count = 0\nfor i in range(len(s)):\n    if s[i] != ' ' and (i == 0 or s[i-1] == ' '): count += 1\nreturn count",
        "Counting word starts is O(n) and needs no extra memory, unlike splitting into an array.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s: len(s.split()),
    java="""
        class Solution {
            public int countWords(String s) {
                int count = 0;
                for (int i = 0; i < s.length(); i++)
                    if (s.charAt(i) != ' ' && (i == 0 || s.charAt(i - 1) == ' ')) count++;
                return count;
            }
        }
    """,
    tests=[{"s": "Hello, my name is Ada"}, {"s": "   "}, {"s": ""}, {"s": "  two  words "}],
    gen=lambda r: {"s": "".join(r.choice(["ab", " ", "  ", "x"]) for _ in range(r.randint(0, 12)))},
)

P(
    slug="roman-to-integer",
    title="Roman Numerals to Integer",
    difficulty="easy",
    topics=["strings", "hash-maps"],
    summary="Convert a Roman numeral to a number.",
    statement="""
        Convert the Roman numeral `s` to an integer. Symbols: I=1, V=5, X=10, L=50, C=100, D=500,
        M=1000. A smaller symbol before a larger one is subtracted (`IV` = 4, `XC` = 90).
    """,
    constraints=["1 <= s.length <= 15", "s is a valid numeral for a value in [1, 3999]"],
    sig="int romanToInt(String s)",
    hints=[
        "Most symbols just add. When does a symbol subtract?",
        "A symbol subtracts when the next symbol is larger.",
        "total = 0\nfor i in range(len(s)):\n    v = value(s[i])\n    if i+1 < len(s) and v < value(s[i+1]): total -= v\n"
        "    else: total += v\nreturn total",
        "Comparing each symbol with the next one handles all six subtractive pairs in one O(n) pass.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s: (
        lambda v: sum(-v[a] if v[a] < v[b] else v[a] for a, b in zip(s, s[1:] + "I", strict=False))
    )({"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}),
    java="""
        class Solution {
            private int value(char c) {
                switch (c) {
                    case 'I': return 1; case 'V': return 5; case 'X': return 10; case 'L': return 50;
                    case 'C': return 100; case 'D': return 500; default: return 1000;
                }
            }
            public int romanToInt(String s) {
                int total = 0;
                for (int i = 0; i < s.length(); i++) {
                    int v = value(s.charAt(i));
                    if (i + 1 < s.length() && v < value(s.charAt(i + 1))) total -= v; else total += v;
                }
                return total;
            }
        }
    """,
    tests=[{"s": "III"}, {"s": "LVIII"}, {"s": "MCMXCIV"}, {"s": "IV"}, {"s": "MMMCMXCIX"}, {"s": "XL"}],
    gen=lambda r: {
        "s": (
            lambda n: (
                "".join(sym * (n // val) for val, sym in [])
                or __import__("functools").reduce(
                    lambda acc, pair: (acc[0] % pair[0], acc[1] + pair[1] * (acc[0] // pair[0])),
                    [
                        (1000, "M"),
                        (900, "CM"),
                        (500, "D"),
                        (400, "CD"),
                        (100, "C"),
                        (90, "XC"),
                        (50, "L"),
                        (40, "XL"),
                        (10, "X"),
                        (9, "IX"),
                        (5, "V"),
                        (4, "IV"),
                        (1, "I"),
                    ],
                    (n, ""),
                )[1]
            )
        )(r.randint(1, 3999))
    },
    explain={2: "M + CM + XC + IV = 1000 + 900 + 90 + 4."},
)

P(
    slug="isomorphic-strings",
    title="Isomorphic Strings",
    difficulty="easy",
    topics=["strings", "hash-maps"],
    summary="Can one string's letters be consistently renamed into the other?",
    statement="""
        Two strings are isomorphic if the characters of `s` can be replaced to get `t`, where each
        character always maps to the same character and no two characters map to the same one.
        Return whether `s` and `t` are isomorphic.
    """,
    constraints=["1 <= s.length == t.length <= 5 * 10^4", "ASCII characters"],
    sig="boolean isIsomorphic(String s, String t)",
    hints=[
        "You need a consistent mapping in both directions.",
        "Keep two maps: s-char → t-char and t-char → s-char. Any conflict means false.",
        "for a, b in zip(s, t):\n    if fwd.get(a, b) != b or back.get(b, a) != a: return false\n"
        "    fwd[a] = b; back[b] = a\nreturn true",
        "Two maps catch both kinds of conflict (one char mapping to two, two chars mapping to one) in "
        "O(n) time. With ASCII, two 256-slot arrays work as maps.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s, t: len(set(zip(s, t, strict=False))) == len(set(s)) == len(set(t)),
    java="""
        class Solution {
            public boolean isIsomorphic(String s, String t) {
                int[] fwd = new int[256], back = new int[256];
                for (int i = 0; i < s.length(); i++) {
                    char a = s.charAt(i), b = t.charAt(i);
                    if (fwd[a] == 0 && back[b] == 0) { fwd[a] = b + 1; back[b] = a + 1; }
                    else if (fwd[a] != b + 1 || back[b] != a + 1) return false;
                }
                return true;
            }
        }
    """,
    tests=[
        {"s": "egg", "t": "add"},
        {"s": "foo", "t": "bar"},
        {"s": "paper", "t": "title"},
        {"s": "ab", "t": "aa"},
        {"s": "badc", "t": "baba"},
    ],
    gen=lambda r: (lambda s: {"s": s, "t": word(r, len(s), len(s), "xyz")})(word(r, 1, 8, "abc")),
)

P(
    slug="word-pattern",
    title="Word Pattern",
    difficulty="easy",
    topics=["strings", "hash-maps"],
    summary="Do the words of a sentence follow a letter pattern?",
    statement="""
        `pattern` is a string of letters and `s` is words separated by single spaces. Return `true`
        if there is a one-to-one match between pattern letters and words, so that replacing each
        letter by its word gives `s`.
    """,
    constraints=["1 <= pattern.length <= 300", "1 <= s.length <= 3000"],
    sig="boolean wordPattern(String pattern, String s)",
    hints=[
        "First check that there are as many words as letters.",
        "Then keep two maps (letter → word, word → letter) and check them as you go.",
        "words = s.split(' ')\nif len(words) != len(pattern): return false\n"
        "for c, w in zip(pattern, words):\n    if map1.get(c, w) != w or map2.get(w, c) != c: return false\n"
        "    map1[c] = w; map2[w] = c\nreturn true",
        "A bijection needs checks in both directions; one map alone would accept `abba` with `dog dog dog dog`. O(n).",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda pattern, s: (
        len(s.split(" ")) == len(pattern)
        and len(set(zip(pattern, s.split(" "), strict=False))) == len(set(pattern)) == len(set(s.split(" ")))
    ),
    java="""
        import java.util.*;

        class Solution {
            public boolean wordPattern(String pattern, String s) {
                String[] words = s.split(" ");
                if (words.length != pattern.length()) return false;
                Map<Character, String> fwd = new HashMap<>();
                Map<String, Character> back = new HashMap<>();
                for (int i = 0; i < words.length; i++) {
                    char c = pattern.charAt(i);
                    String w = words[i];
                    if (!fwd.getOrDefault(c, w).equals(w) || back.getOrDefault(w, c) != c) return false;
                    fwd.put(c, w);
                    back.put(w, c);
                }
                return true;
            }
        }
    """,
    tests=[
        {"pattern": "abba", "s": "dog cat cat dog"},
        {"pattern": "abba", "s": "dog cat cat fish"},
        {"pattern": "aaaa", "s": "dog cat cat dog"},
        {"pattern": "abba", "s": "dog dog dog dog"},
        {"pattern": "ab", "s": "x y z"},
    ],
    gen=lambda r: (lambda p: {"pattern": p, "s": " ".join(r.choice(["cat", "dog", "owl"]) for _ in p)})(
        word(r, 1, 6, "ab")
    ),
)

P(
    slug="ransom-note",
    title="Ransom Note",
    difficulty="easy",
    topics=["strings", "counting"],
    summary="Can one string be built from another's letters?",
    statement="""
        Return `true` if `note` can be written using letters cut out of `magazine`, where each letter
        in `magazine` can be used at most once.
    """,
    constraints=["1 <= note.length, magazine.length <= 10^5", "lower-case English letters"],
    sig="boolean canConstruct(String note, String magazine)",
    hints=[
        "What you need is enough copies of each letter.",
        "Count the magazine's letters, then spend them on the note's letters.",
        "counts = count letters of magazine\nfor c in note:\n    counts[c] -= 1\n    if counts[c] < 0: return false\nreturn true",
        "A 26-slot count array makes this O(n + m) time and O(1) space.",
    ],
    time="O(n + m)",
    space="O(1)",
    model=lambda note, magazine: not (Counter(note) - Counter(magazine)),
    java="""
        class Solution {
            public boolean canConstruct(String note, String magazine) {
                int[] counts = new int[26];
                for (char c : magazine.toCharArray()) counts[c - 'a']++;
                for (char c : note.toCharArray()) if (--counts[c - 'a'] < 0) return false;
                return true;
            }
        }
    """,
    tests=[
        {"note": "a", "magazine": "b"},
        {"note": "aa", "magazine": "ab"},
        {"note": "aa", "magazine": "aab"},
        {"note": "abc", "magazine": "cba"},
    ],
    gen=lambda r: {"note": word(r, 1, 6, "abcd"), "magazine": word(r, 1, 12, "abcd")},
)

P(
    slug="longest-common-prefix",
    title="Longest Common Prefix",
    difficulty="easy",
    topics=["strings"],
    summary="Find the longest start shared by all strings.",
    statement="""
        Return the longest string that is a prefix of every string in `words`. If there is none,
        return `""`.
    """,
    constraints=["1 <= words.length <= 200", "0 <= words[i].length <= 200"],
    sig="String longestCommonPrefix(String[] words)",
    hints=[
        "Compare the strings one column (character position) at a time.",
        "Stop at the first position where some string ends or has a different character.",
        "for i in range(len(words[0])):\n    for w in words[1:]:\n        if i == len(w) or w[i] != words[0][i]: return words[0][:i]\n"
        "return words[0]",
        "Vertical scanning stops as soon as the prefix ends: O(total characters) in the worst case, O(1) extra space.",
    ],
    time="O(S)",
    space="O(1)",
    model=lambda words: __import__("os").path.commonprefix(words),
    java="""
        class Solution {
            public String longestCommonPrefix(String[] words) {
                String first = words[0];
                for (int i = 0; i < first.length(); i++)
                    for (String w : words)
                        if (i == w.length() || w.charAt(i) != first.charAt(i)) return first.substring(0, i);
                return first;
            }
        }
    """,
    tests=[
        {"words": ["flower", "flow", "flight"]},
        {"words": ["dog", "racecar", "car"]},
        {"words": ["alone"]},
        {"words": ["", "a"]},
        {"words": ["ab", "a"]},
    ],
    gen=lambda r: (lambda p: {"words": [p + word(r, 0, 4, "xy") for _ in range(r.randint(1, 5))]})(
        word(r, 0, 5, "ab")
    ),
)

P(
    slug="add-binary",
    title="Add Two Binary Strings",
    difficulty="easy",
    topics=["strings", "math"],
    summary="Add two numbers written in binary.",
    statement="""
        `a` and `b` are binary strings (only `0` and `1`, no leading zeros except `"0"`). Return their
        sum as a binary string.
    """,
    constraints=["1 <= a.length, b.length <= 10^4"],
    sig="String addBinary(String a, String b)",
    hints=[
        "Add from the rightmost digits, like column addition.",
        "Keep a carry. Each column's sum is 0-3: the digit is `sum % 2`, the new carry is `sum / 2`.",
        "i, j, carry = len(a)-1, len(b)-1, 0\nwhile i >= 0 or j >= 0 or carry:\n    total = carry + digit(a, i) + digit(b, j)\n"
        "    out.append(total % 2); carry = total // 2; i -= 1; j -= 1\nreturn reversed(out)",
        "One pass over the longer string: O(max(n, m)). Strings can be 10^4 bits, so converting to a "
        "long would overflow.",
    ],
    time="O(max(n, m))",
    space="O(max(n, m))",
    model=lambda a, b: bin(int(a, 2) + int(b, 2))[2:],
    java="""
        class Solution {
            public String addBinary(String a, String b) {
                StringBuilder sb = new StringBuilder();
                int i = a.length() - 1, j = b.length() - 1, carry = 0;
                while (i >= 0 || j >= 0 || carry > 0) {
                    int total = carry;
                    if (i >= 0) total += a.charAt(i--) - '0';
                    if (j >= 0) total += b.charAt(j--) - '0';
                    sb.append(total % 2);
                    carry = total / 2;
                }
                return sb.reverse().toString();
            }
        }
    """,
    tests=[
        {"a": "11", "b": "1"},
        {"a": "1010", "b": "1011"},
        {"a": "0", "b": "0"},
        {"a": "1111111111", "b": "1"},
    ],
    gen=lambda r: {"a": "1" + word(r, 0, 70, "01"), "b": "1" + word(r, 0, 70, "01")},
)

P(
    slug="column-title-to-number",
    title="Spreadsheet Column to Number",
    difficulty="easy",
    topics=["strings", "math"],
    summary='Convert a spreadsheet column label like "AB" to its number.',
    statement="""
        Spreadsheet columns are labeled A, B, ..., Z, AA, AB, ..., AZ, BA, ... Return the column number
        for `title` (A = 1, Z = 26, AA = 27).
    """,
    constraints=["1 <= title.length <= 7", "upper-case letters", "the result fits in an int"],
    sig="int titleToNumber(String title)",
    hints=[
        "It's like reading a number in base 26, but the digits run 1 to 26 instead of 0 to 25.",
        "For each letter: result = result * 26 + (letter - 'A' + 1).",
        "result = 0\nfor c in title:\n    result = result * 26 + (ord(c) - ord('A') + 1)\nreturn result",
        'Horner\'s method over the letters: O(n). The "+1" is what makes this bijective base-26.',
    ],
    time="O(n)",
    space="O(1)",
    model=lambda title: __import__("functools").reduce(lambda acc, c: acc * 26 + ord(c) - 64, title, 0),
    java="""
        class Solution {
            public int titleToNumber(String title) {
                int result = 0;
                for (char c : title.toCharArray()) result = result * 26 + (c - 'A' + 1);
                return result;
            }
        }
    """,
    tests=[{"title": "A"}, {"title": "AB"}, {"title": "ZY"}, {"title": "FXSHRXW"}],
    gen=lambda r: {"title": word(r, 1, 5, "ABCDEFGHIJKLMNOPQRSTUVWXYZ")},
)

P(
    slug="number-to-column-title",
    title="Number to Spreadsheet Column",
    difficulty="easy",
    topics=["strings", "math"],
    summary='Convert a column number back to a label like "AB".',
    statement="""
        Return the spreadsheet column label for `n` (1 = A, 26 = Z, 27 = AA, 28 = AB).
    """,
    constraints=["1 <= n <= 2^31 - 1"],
    sig="String convertToTitle(int n)",
    hints=[
        "This is the reverse of reading a label. Why doesn't plain base 26 work?",
        "There's no zero digit. Subtract 1 before taking `% 26` so Z (26) maps to the last letter.",
        "out = ''\nwhile n > 0:\n    n -= 1\n    out = chr(ord('A') + n % 26) + out\n    n //= 26\nreturn out",
        "Shifting by one each round turns 1..26 into 0..25: O(log n). Without the `n -= 1`, 26 would "
        'come out as "A@".',
    ],
    time="O(log n)",
    space="O(log n)",
    model=lambda n: (lambda f: f(f, n))(
        lambda f, k: "" if k == 0 else f(f, (k - 1) // 26) + chr(65 + (k - 1) % 26)
    ),
    java="""
        class Solution {
            public String convertToTitle(int n) {
                StringBuilder sb = new StringBuilder();
                while (n > 0) { n--; sb.append((char) ('A' + n % 26)); n /= 26; }
                return sb.reverse().toString();
            }
        }
    """,
    tests=[{"n": 1}, {"n": 28}, {"n": 701}, {"n": 26}, {"n": 2147483647}],
    gen=lambda r: {"n": r.randint(1, 10**6)},
)

P(
    slug="first-repeated-character",
    title="First Repeated Character",
    difficulty="easy",
    topics=["strings", "hash-sets"],
    summary="Find the first character whose second appearance comes earliest.",
    statement="""
        Return the first character in `s` that appears for the second time (the repeat that happens
        earliest while reading left to right). If no character repeats, return an empty string.
    """,
    constraints=["1 <= s.length <= 10^4", "lower-case English letters"],
    sig="String firstRepeated(String s)",
    hints=[
        "Read left to right and remember what you've seen.",
        "The first character that's already in your set is the answer.",
        "seen = set()\nfor c in s:\n    if c in seen: return c\n    seen.add(c)\nreturn ''",
        "Stop at the first repeat: O(n) time, O(1) space (at most 26 letters). Note the answer is the "
        'earliest *second* occurrence, so for "abba" it\'s "b".',
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s: next((s[i] for i in range(len(s)) if s[i] in s[:i]), ""),
    java="""
        class Solution {
            public String firstRepeated(String s) {
                boolean[] seen = new boolean[26];
                for (char c : s.toCharArray()) {
                    if (seen[c - 'a']) return String.valueOf(c);
                    seen[c - 'a'] = true;
                }
                return "";
            }
        }
    """,
    tests=[{"s": "abccbaacz"}, {"s": "abcd"}, {"s": "abba"}, {"s": "zz"}],
    gen=lambda r: {"s": word(r, 1, 10, "abcdefgh")},
)

P(
    slug="is-subsequence",
    title="Is Subsequence",
    difficulty="easy",
    topics=["strings", "two-pointers"],
    summary="Can one string be found inside another in order?",
    statement="""
        Return `true` if `s` is a subsequence of `t`: you can delete some (or no) characters of `t`
        without reordering the rest to get `s`.
    """,
    constraints=["0 <= s.length <= 100", "0 <= t.length <= 10^4", "lower-case English letters"],
    sig="boolean isSubsequence(String s, String t)",
    hints=[
        "Match the characters of `s` in order as you read `t`.",
        "Use a pointer into `s` that only moves when the current character of `t` matches.",
        "i = 0\nfor c in t:\n    if i < len(s) and s[i] == c: i += 1\nreturn i == len(s)",
        "Greedy matching is safe: taking the earliest match never hurts later matches. O(|t|) time, O(1) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s, t: (lambda it: all(c in it for c in s))(iter(t)),
    java="""
        class Solution {
            public boolean isSubsequence(String s, String t) {
                int i = 0;
                for (int j = 0; j < t.length() && i < s.length(); j++) if (s.charAt(i) == t.charAt(j)) i++;
                return i == s.length();
            }
        }
    """,
    tests=[
        {"s": "abc", "t": "ahbgdc"},
        {"s": "axc", "t": "ahbgdc"},
        {"s": "", "t": "abc"},
        {"s": "aa", "t": "a"},
    ],
    gen=lambda r: {"s": word(r, 0, 4, "abc"), "t": word(r, 0, 12, "abc")},
)

P(
    slug="reverse-vowels",
    title="Reverse Only the Vowels",
    difficulty="easy",
    topics=["strings", "two-pointers"],
    summary="Reverse the order of the vowels, leaving other characters in place.",
    statement="""
        Return `s` with only its vowels (`aeiou`, either case) reversed; every other character stays where it is.
    """,
    constraints=["1 <= s.length <= 3 * 10^5", "printable ASCII"],
    sig="String reverseVowels(String s)",
    hints=[
        "Use two pointers moving toward each other.",
        "Move the left pointer to the next vowel and the right pointer to the previous vowel, then swap.",
        "i, j = 0, len(s)-1\nwhile i < j:\n    while i < j and s[i] not a vowel: i += 1\n    while i < j and s[j] not a vowel: j -= 1\n"
        "    swap s[i], s[j]; i += 1; j -= 1\nreturn s",
        "Each pointer moves at most n steps in total, so it's O(n) time with a char array to swap in.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda s: (lambda vs: "".join(vs.pop() if c in "aeiouAEIOU" else c for c in s))(
        [c for c in s if c in "aeiouAEIOU"]
    ),
    java="""
        class Solution {
            private boolean vowel(char c) { return "aeiouAEIOU".indexOf(c) >= 0; }
            public String reverseVowels(String s) {
                char[] a = s.toCharArray();
                int i = 0, j = a.length - 1;
                while (i < j) {
                    while (i < j && !vowel(a[i])) i++;
                    while (i < j && !vowel(a[j])) j--;
                    char t = a[i]; a[i] = a[j]; a[j] = t;
                    i++; j--;
                }
                return new String(a);
            }
        }
    """,
    tests=[{"s": "hello"}, {"s": "IceCreAm"}, {"s": "xyz"}, {"s": "a"}],
    gen=lambda r: {"s": word(r, 1, 15, "abeioxyzAU")},
)

P(
    slug="longest-palindrome-length",
    title="Longest Palindrome You Can Build",
    difficulty="easy",
    topics=["strings", "counting", "greedy"],
    summary="Use letters to build the longest palindrome possible.",
    statement="""
        Return the length of the longest palindrome you can build from the letters of `s` (case-sensitive).
        You don't have to use every letter.
    """,
    constraints=["1 <= s.length <= 2000", "upper- and lower-case English letters"],
    sig="int longestPalindrome(String s)",
    hints=[
        "A palindrome is made of pairs, plus at most one single letter in the middle.",
        "For each letter, use `count / 2 * 2` copies. If any letter has an odd count, add one for the middle.",
        "length = sum(c // 2 * 2 for c in counts)\nif any(c % 2 for c in counts): length += 1\nreturn length",
        "Counting then summing pairs is O(n). Only one odd letter can sit in the center, so add 1 at most once.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s: (
        lambda c: sum(v // 2 * 2 for v in c.values()) + (1 if any(v % 2 for v in c.values()) else 0)
    )(Counter(s)),
    java="""
        class Solution {
            public int longestPalindrome(String s) {
                int[] counts = new int[128];
                for (char c : s.toCharArray()) counts[c]++;
                int length = 0;
                boolean odd = false;
                for (int c : counts) { length += c / 2 * 2; if (c % 2 == 1) odd = true; }
                return odd ? length + 1 : length;
            }
        }
    """,
    tests=[{"s": "abccccdd"}, {"s": "a"}, {"s": "Aa"}, {"s": "bb"}],
    gen=lambda r: {"s": word(r, 1, 20, "aabbcAB")},
    explain={0: '"dccaccd" has length 7.'},
)

P(
    slug="find-added-letter",
    title="Find the Added Letter",
    difficulty="easy",
    topics=["strings", "bit-manipulation"],
    summary="One string is a shuffle of another plus one letter. Which letter?",
    statement="""
        `t` is made by shuffling `s` and adding one more letter at a random position. Return the added
        letter as a one-character string.
    """,
    constraints=["0 <= s.length <= 1000", "t.length == s.length + 1", "lower-case English letters"],
    sig="String findTheDifference(String s, String t)",
    hints=[
        "Counting letters works. Is there something even simpler?",
        "XOR all characters of both strings together: everything cancels except the added letter.",
        "x = 0\nfor c in s + t: x ^= ord(c)\nreturn chr(x)",
        "XOR (or the difference of character-code sums) gives O(n) time and O(1) space.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s, t: next(iter(Counter(t) - Counter(s))),
    java="""
        class Solution {
            public String findTheDifference(String s, String t) {
                int x = 0;
                for (char c : s.toCharArray()) x ^= c;
                for (char c : t.toCharArray()) x ^= c;
                return String.valueOf((char) x);
            }
        }
    """,
    tests=[{"s": "abcd", "t": "abcde"}, {"s": "", "t": "y"}, {"s": "aab", "t": "abaa"}],
    gen=lambda r: (lambda s, extra: {"s": s, "t": "".join(r.sample(s + extra, len(s) + 1))})(
        word(r, 0, 10, "abcz"), r.choice("abcz")
    ),
)

P(
    slug="detect-capital",
    title="Correct Use of Capitals",
    difficulty="easy",
    topics=["strings"],
    summary="Check a word's capitalization.",
    statement="""
        A word uses capitals correctly if it is all upper case (`"USA"`), all lower case (`"leet"`),
        or only its first letter is upper case (`"Google"`). Return whether `word` does.
    """,
    constraints=["1 <= word.length <= 100", "English letters"],
    sig="boolean detectCapitalUse(String word)",
    hints=[
        "Count the capitals and note whether the first letter is one.",
        "Valid when the number of capitals is 0, equals the length, or is 1 with the first letter capital.",
        "caps = count of upper-case letters\nreturn caps == 0 or caps == len(word) or (caps == 1 and word[0].isupper())",
        "A single count pass decides it: O(n).",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda word: (
        word.isupper() or word.islower() or (word[0].isupper() and word[1:].islower()) or len(word) == 1
    ),
    java="""
        class Solution {
            public boolean detectCapitalUse(String word) {
                int caps = 0;
                for (char c : word.toCharArray()) if (Character.isUpperCase(c)) caps++;
                return caps == 0 || caps == word.length() || (caps == 1 && Character.isUpperCase(word.charAt(0)));
            }
        }
    """,
    tests=[
        {"word": "USA"},
        {"word": "FlaG"},
        {"word": "Google"},
        {"word": "leetcode"},
        {"word": "g"},
        {"word": "gO"},
    ],
    gen=lambda r: {"word": word(r, 1, 6, "abAB")},
)

P(
    slug="repeated-pattern",
    title="Built From a Repeated Piece",
    difficulty="easy",
    topics=["strings"],
    summary="Is a string some shorter piece repeated several times?",
    statement="""
        Return `true` if `s` can be built by taking a substring of it and repeating it two or more times
        (`"abab"` is `"ab"` twice).
    """,
    constraints=["1 <= s.length <= 10^4", "lower-case English letters"],
    sig="boolean repeatedSubstringPattern(String s)",
    hints=[
        "The repeated piece's length must divide the string's length.",
        "Try each length `k` that divides `n` (with `k < n`) and check `s[i] == s[i - k]` for all `i >= k`.",
        "for k in 1..n//2:\n    if n % k == 0 and all(s[i] == s[i-k] for i in k..n-1): return true\nreturn false",
        "Trying divisors is O(n * d(n)), fast in practice. A neat alternative: `s` is repeated exactly "
        "when it appears inside `(s + s)` with the first and last characters removed.",
    ],
    time="O(n * d(n))",
    space="O(1)",
    model=lambda s: any(len(s) % k == 0 and s[:k] * (len(s) // k) == s for k in range(1, len(s) // 2 + 1)),
    java="""
        class Solution {
            public boolean repeatedSubstringPattern(String s) {
                int n = s.length();
                for (int k = 1; k <= n / 2; k++) {
                    if (n % k != 0) continue;
                    boolean ok = true;
                    for (int i = k; i < n && ok; i++) if (s.charAt(i) != s.charAt(i - k)) ok = false;
                    if (ok) return true;
                }
                return false;
            }
        }
    """,
    tests=[{"s": "abab"}, {"s": "aba"}, {"s": "abcabcabcabc"}, {"s": "a"}, {"s": "aaaa"}],
    gen=lambda r: {"s": word(r, 1, 3, "ab") * r.randint(1, 4) + (word(r, 0, 1, "ab"))},
)

P(
    slug="backspace-compare",
    title="Compare With Backspaces",
    difficulty="easy",
    topics=["strings", "stacks"],
    summary="Do two typed strings match after applying backspaces?",
    statement="""
        In `s` and `t`, the character `#` means backspace (delete the previous character, if any).
        Return `true` if both strings are equal after typing them out.
    """,
    constraints=["1 <= s.length, t.length <= 200", "lower-case letters and '#'"],
    sig="boolean backspaceCompare(String s, String t)",
    hints=[
        "Simulate typing each string.",
        "A stack (or StringBuilder) works: push letters, pop on `#` if not empty.",
        "def typed(x):\n    out = []\n    for c in x:\n        if c == '#': out.pop() if out else None\n        else: out.append(c)\n"
        "    return out\nreturn typed(s) == typed(t)",
        "Simulating is O(n + m). For O(1) space, walk both strings from the end, skipping characters that "
        "later backspaces delete.",
    ],
    time="O(n + m)",
    space="O(n + m)",
    model=lambda s, t: (lambda f: f(s) == f(t))(
        lambda x: __import__("functools").reduce(lambda acc, c: acc[:-1] if c == "#" else acc + c, x, "")
    ),
    java="""
        class Solution {
            private String typed(String x) {
                StringBuilder sb = new StringBuilder();
                for (char c : x.toCharArray()) {
                    if (c == '#') { if (sb.length() > 0) sb.deleteCharAt(sb.length() - 1); }
                    else sb.append(c);
                }
                return sb.toString();
            }
            public boolean backspaceCompare(String s, String t) {
                return typed(s).equals(typed(t));
            }
        }
    """,
    tests=[
        {"s": "ab#c", "t": "ad#c"},
        {"s": "ab##", "t": "c#d#"},
        {"s": "a#c", "t": "b"},
        {"s": "###", "t": "#"},
        {"s": "a##c", "t": "#a#c"},
    ],
    gen=lambda r: {"s": word(r, 1, 8, "ab#"), "t": word(r, 1, 8, "ab#")},
)

P(
    slug="run-length-encode",
    title="Run-Length Encoding",
    difficulty="easy",
    topics=["strings", "two-pointers"],
    summary="Compress runs of repeated letters as letter + count.",
    statement="""
        Compress `s` by replacing each run of the same letter with the letter followed by the run
        length, for example `"aaabcc"` becomes `"a3b1c2"`.
    """,
    constraints=["0 <= s.length <= 10^4", "lower-case English letters"],
    sig="String encode(String s)",
    hints=[
        "Find where each run starts and ends.",
        "Walk with index `i`; move `j` forward while `s[j] == s[i]`; the run length is `j - i`.",
        "i = 0\nwhile i < len(s):\n    j = i\n    while j < len(s) and s[j] == s[i]: j += 1\n    out += s[i] + str(j - i)\n    i = j\nreturn out",
        "Each character is visited once by `j`, so it's O(n). Use a StringBuilder in Java.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda s: "".join(k + str(len(list(g))) for k, g in __import__("itertools").groupby(s)),
    java="""
        class Solution {
            public String encode(String s) {
                StringBuilder sb = new StringBuilder();
                int i = 0;
                while (i < s.length()) {
                    int j = i;
                    while (j < s.length() && s.charAt(j) == s.charAt(i)) j++;
                    sb.append(s.charAt(i)).append(j - i);
                    i = j;
                }
                return sb.toString();
            }
        }
    """,
    tests=[{"s": "aaabcc"}, {"s": "abc"}, {"s": ""}, {"s": "zzzzzzzzzzzz"}],
    gen=lambda r: {"s": "".join(r.choice("abc") * r.randint(1, 4) for _ in range(r.randint(0, 6)))},
)

P(
    slug="max-occurring-char",
    title="Most Frequent Character",
    difficulty="easy",
    topics=["strings", "counting"],
    summary="Which letter appears most often? Ties go to the alphabetically first.",
    statement="""
        Return the letter that appears most often in `s` as a one-character string. If several letters
        tie, return the one that comes first in the alphabet.
    """,
    constraints=["1 <= s.length <= 10^5", "lower-case English letters"],
    sig="String mostFrequent(String s)",
    hints=[
        "Count every letter first.",
        "Then scan the 26 counts from 'a' to 'z', keeping the first letter with the highest count.",
        "counts = [0]*26\nfor c in s: counts[c] += 1\nbest = 0\nfor i in 1..25:\n    if counts[i] > counts[best]: best = i\nreturn letter(best)",
        "O(n) to count, O(26) to choose. Scanning a→z and only replacing on a strictly greater count "
        "makes ties go to the earlier letter.",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s: min(Counter(s).items(), key=lambda kv: (-kv[1], kv[0]))[0],
    java="""
        class Solution {
            public String mostFrequent(String s) {
                int[] counts = new int[26];
                for (char c : s.toCharArray()) counts[c - 'a']++;
                int best = 0;
                for (int i = 1; i < 26; i++) if (counts[i] > counts[best]) best = i;
                return String.valueOf((char) ('a' + best));
            }
        }
    """,
    tests=[{"s": "banana"}, {"s": "abc"}, {"s": "zzyy"}, {"s": "q"}],
    gen=lambda r: {"s": word(r, 1, 20, "abcde")},
)

P(
    slug="jewels-and-stones",
    title="Jewels and Stones",
    difficulty="easy",
    topics=["strings", "hash-sets"],
    summary="Count how many of your stones are jewels.",
    statement="""
        Each character in `jewels` is a type of jewel. Return how many characters in `stones` are
        jewels. Letters are case-sensitive (`a` and `A` are different).
    """,
    constraints=["1 <= jewels.length, stones.length <= 50", "jewels has distinct letters"],
    sig="int numJewelsInStones(String jewels, String stones)",
    hints=[
        'For each stone you need a fast "is this a jewel?" check.',
        "Put the jewel letters in a set (or a 128-slot boolean array).",
        "jewel = set(jewels)\nreturn count of c in stones where c in jewel",
        "Set lookups make this O(J + S) instead of O(J * S).",
    ],
    time="O(J + S)",
    space="O(1)",
    model=lambda jewels, stones: sum(1 for c in stones if c in jewels),
    java="""
        class Solution {
            public int numJewelsInStones(String jewels, String stones) {
                boolean[] jewel = new boolean[128];
                for (char c : jewels.toCharArray()) jewel[c] = true;
                int count = 0;
                for (char c : stones.toCharArray()) if (jewel[c]) count++;
                return count;
            }
        }
    """,
    tests=[
        {"jewels": "aA", "stones": "aAAbbbb"},
        {"jewels": "z", "stones": "ZZ"},
        {"jewels": "abc", "stones": "a"},
    ],
    gen=lambda r: {"jewels": "".join(r.sample("abcAB", r.randint(1, 3))), "stones": word(r, 1, 15, "abcABz")},
)

P(
    slug="split-balanced-strings",
    title="Split Into Balanced Strings",
    difficulty="easy",
    topics=["strings", "greedy"],
    summary="Split an L/R string into as many balanced pieces as possible.",
    statement="""
        A string of `L`s and `R`s is balanced if it has the same number of each. `s` is balanced.
        Split it into the maximum number of balanced pieces and return that number.
    """,
    constraints=["2 <= s.length <= 1000", "s is balanced"],
    sig="int balancedSplit(String s)",
    hints=[
        "Cut as soon as you can.",
        "Keep a balance: +1 for L, -1 for R. Every time it returns to 0, you've finished a piece.",
        "balance = pieces = 0\nfor c in s:\n    balance += 1 if c == 'L' else -1\n    if balance == 0: pieces += 1\nreturn pieces",
        "Greedily cutting at each zero is optimal: delaying a cut can only merge pieces. O(n), O(1).",
    ],
    time="O(n)",
    space="O(1)",
    model=lambda s: sum(1 for i in range(1, len(s) + 1) if s[:i].count("L") == s[:i].count("R")),
    java="""
        class Solution {
            public int balancedSplit(String s) {
                int balance = 0, pieces = 0;
                for (char c : s.toCharArray()) { balance += c == 'L' ? 1 : -1; if (balance == 0) pieces++; }
                return pieces;
            }
        }
    """,
    tests=[{"s": "RLRRLLRLRL"}, {"s": "RLRRRLLRLL"}, {"s": "LLLLRRRR"}, {"s": "LR"}],
    gen=lambda r: {"s": "".join(r.sample("LR" * (k := r.randint(1, 6)), 2 * k))},
)

P(
    slug="shuffle-by-index",
    title="Shuffle by Index",
    difficulty="easy",
    topics=["strings", "arrays"],
    summary="Rebuild a string by moving each character to its target index.",
    statement="""
        The character `s[i]` belongs at position `indices[i]` of the result. `indices` is a
        permutation of `0..n-1`. Return the rebuilt string.
    """,
    constraints=["1 <= s.length == indices.length <= 100", "indices is a permutation"],
    sig="String restoreString(String s, int[] indices)",
    hints=[
        "You know exactly where each character goes.",
        "Create a char array of length n and write `s[i]` into slot `indices[i]`.",
        "out = [None]*n\nfor i in range(n): out[indices[i]] = s[i]\nreturn ''.join(out)",
        "One placement per character: O(n) time and space.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda s, indices: "".join(c for _, c in sorted(zip(indices, s, strict=False))),
    java="""
        class Solution {
            public String restoreString(String s, int[] indices) {
                char[] out = new char[s.length()];
                for (int i = 0; i < s.length(); i++) out[indices[i]] = s.charAt(i);
                return new String(out);
            }
        }
    """,
    tests=[
        {"s": "codeleet", "indices": [4, 5, 6, 7, 0, 2, 1, 3]},
        {"s": "abc", "indices": [0, 1, 2]},
        {"s": "ab", "indices": [1, 0]},
    ],
    gen=lambda r: (lambda s: {"s": s, "indices": r.sample(range(len(s)), len(s))})(word(r, 1, 12)),
    explain={0: '"leetcode"'},
)

P(
    slug="defang-ip",
    title="Defang an IP Address",
    difficulty="easy",
    topics=["strings"],
    summary="Replace every dot in an IP address with [.]",
    statement="""
        Return the IPv4 address `address` with every `.` replaced by `[.]`.
    """,
    constraints=["address is a valid IPv4 address"],
    sig="String defangIPaddr(String address)",
    hints=[
        "Build the result character by character.",
        "Append `[.]` for a dot and the character itself otherwise.",
        "out = ''\nfor c in address: out += '[.]' if c == '.' else c\nreturn out",
        'One pass with a StringBuilder: O(n). (`address.replace(".", "[.]")` also works.)',
    ],
    time="O(n)",
    space="O(n)",
    model=lambda address: address.replace(".", "[.]"),
    java="""
        class Solution {
            public String defangIPaddr(String address) {
                StringBuilder sb = new StringBuilder();
                for (char c : address.toCharArray()) sb.append(c == '.' ? "[.]" : String.valueOf(c));
                return sb.toString();
            }
        }
    """,
    tests=[{"address": "1.1.1.1"}, {"address": "255.100.50.0"}, {"address": "10.0.0.255"}],
    gen=lambda r: {"address": ".".join(str(r.randint(0, 255)) for _ in range(4))},
)

P(
    slug="good-pairs",
    title="Count Good Pairs",
    difficulty="easy",
    topics=["arrays", "hash-maps", "math"],
    summary="Count pairs of equal values.",
    statement="""
        A pair `(i, j)` is good if `nums[i] == nums[j]` and `i < j`. Return the number of good pairs.
    """,
    constraints=["1 <= nums.length <= 10^4", "1 <= nums[i] <= 100"],
    sig="int numIdenticalPairs(int[] nums)",
    hints=[
        "Checking every pair is O(n^2). Can you count instead?",
        "When you see a value that has already appeared k times, it forms k new pairs.",
        "seen = {}\npairs = 0\nfor x in nums:\n    pairs += seen.get(x, 0)\n    seen[x] = seen.get(x, 0) + 1\nreturn pairs",
        "Adding the running count before incrementing counts each pair once: O(n) time.",
    ],
    time="O(n)",
    space="O(n)",
    model=lambda nums: sum(
        1 for i in range(len(nums)) for j in range(i + 1, len(nums)) if nums[i] == nums[j]
    ),
    java="""
        class Solution {
            public int numIdenticalPairs(int[] nums) {
                int[] seen = new int[101];
                int pairs = 0;
                for (int x : nums) pairs += seen[x]++;
                return pairs;
            }
        }
    """,
    tests=[{"nums": [1, 2, 3, 1, 1, 3]}, {"nums": [1, 1, 1, 1]}, {"nums": [1, 2, 3]}],
    gen=lambda r: {"nums": [r.randint(1, 5) for _ in range(r.randint(1, 20))]},
)
