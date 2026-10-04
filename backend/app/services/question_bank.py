"""Question bank with randomised generators.

Each template produces a fresh *instance* per session from a seeded RNG: parameters, names, numbers
and option order change between sessions, so an agent cannot replay a memorised script. Answer keys
live only in the instance's ``answer_key`` and are stripped before anything is sent to a client.
"""

from __future__ import annotations

import math
import random
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

Instance = dict[str, Any]
Generator = Callable[[random.Random], Instance]


@dataclass(frozen=True)
class Template:
    id: str
    kind: str  # mcq|true_false|multi_select|numerical|text|coding|image|table
    group: str  # composition bucket: mcq|numerical|multi_select|coding|text|image|table
    topic: str
    difficulty: int
    parametric: bool
    gen: Generator


TEMPLATES: dict[str, Template] = {}


def template(id: str, kind: str, topic: str, difficulty: int = 2, parametric: bool = False, group: str = ""):
    def deco(fn: Generator) -> Generator:
        TEMPLATES[id] = Template(id, kind, group or kind, topic, difficulty, parametric, fn)
        return fn

    return deco


# ---------------------------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------------------------


def _choice_q(prompt: str, correct: str, distractors: list[str], **extra: Any) -> Instance:
    opts = [correct, *distractors]
    return {"prompt": prompt, "_options": opts, "_correct": [correct], **extra}


def _multi_q(prompt: str, correct: list[str], wrong: list[str], **extra: Any) -> Instance:
    return {"prompt": prompt, "_options": correct + wrong, "_correct": list(correct), **extra}


def _num_key(value: float, decimals: int) -> dict[str, Any]:
    return {"type": "numeric", "value": round(value, decimals), "tolerance": 0.51 * 10 ** (-decimals) + 1e-9}


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    return all(n % p for p in range(2, int(math.isqrt(n)) + 1))


def _unique_distractors(rng: random.Random, correct: Any, candidates: list[Any], k: int = 3) -> list[str]:
    out: list[str] = []
    for c in candidates:
        s = str(c)
        if s != str(correct) and s not in out:
            out.append(s)
    while len(out) < k:
        cand = str(int(float(correct)) + rng.choice([-1, 1]) * rng.randint(1, 9))
        if cand != str(correct) and cand not in out:
            out.append(cand)
    rng.shuffle(out)
    return out[:k]


FIRST_NAMES = ["Mira", "Tomas", "Aiko", "Lena", "Ravi", "Noor", "Elias", "Sofia", "Kwame", "Ines", "Yuki", "Omar"]
CITIES = ["Lisbon", "Oslo", "Nairobi", "Kyoto", "Lima", "Tallinn", "Hanoi", "Porto", "Bergen", "Quito", "Accra"]
WORDS = [
    "Apple", "Rocket", "Tiger", "Ocean", "Maple", "Violet", "Copper", "Lantern", "Harbor", "Ember",
    "Nimbus", "Quartz", "Willow", "Falcon", "Garnet", "Saffron", "Juniper", "Delta", "Indigo", "Kestrel",
]

# ---------------------------------------------------------------------------------------------
# MCQ — static conceptual items (options shuffled per session)
# ---------------------------------------------------------------------------------------------

STATIC_MCQ: list[tuple[str, str, str, list[str]]] = [
    ("ds-lifo", "data structures", "Which data structure follows Last-In-First-Out (LIFO) order?",
     ["Stack", "Queue", "Heap", "Linked list"]),
    ("algo-bsearch", "algorithms", "What is the worst-case time complexity of binary search on a sorted array of n elements?",
     ["O(log n)", "O(n)", "O(n log n)", "O(1)"]),
    ("sql-having", "databases", "Which SQL clause filters groups produced by GROUP BY?",
     ["HAVING", "WHERE", "ORDER BY", "LIMIT"]),
    ("algo-heapsort", "algorithms", "Which sorting algorithm is in-place and has worst-case O(n log n) running time?",
     ["Heapsort", "Quicksort", "Merge sort", "Counting sort"]),
    ("chem-sodium", "science", "What is the chemical symbol for sodium?", ["Na", "So", "Sd", "S"]),
    ("net-tcp", "networking", "Which transport-layer protocol guarantees in-order, reliable delivery?",
     ["TCP", "UDP", "ICMP", "ARP"]),
    ("py-div", "python", "In Python 3, what is the type of the result of the expression 7 / 2?",
     ["float", "int", "decimal.Decimal", "fractions.Fraction"]),
    ("java-prim", "java", "Which of the following is NOT a primitive type in Java?",
     ["String", "int", "boolean", "char"]),
    ("db-3nf", "databases", "Which normal form removes transitive dependencies of non-key attributes on the key?",
     ["Third normal form (3NF)", "First normal form (1NF)", "Second normal form (2NF)", "Fourth normal form (4NF)"]),
    ("ll-head", "data structures", "What is the time complexity of inserting a node at the head of a singly linked list?",
     ["O(1)", "O(n)", "O(log n)", "O(n^2)"]),
    ("bio-co2", "science", "Which gas do plants primarily absorb from the atmosphere for photosynthesis?",
     ["Carbon dioxide", "Oxygen", "Nitrogen", "Hydrogen"]),
    ("calc-sin", "mathematics", "What is the derivative of sin(x) with respect to x?", ["cos(x)", "-cos(x)", "-sin(x)", "tan(x)"]),
    ("os-deadlock", "operating systems", "Which of these is one of the four Coffman conditions necessary for deadlock?",
     ["Circular wait", "Preemption", "Starvation", "Paging"]),
    ("http-404", "web", "What does the HTTP status code 404 indicate?",
     ["The requested resource was not found", "The server encountered an internal error",
      "The request was successful", "The client must authenticate"]),
    ("git-rebase", "tools", "Which git command re-applies commits on top of another base commit?",
     ["git rebase", "git merge", "git stash", "git revert"]),
    ("graph-bfs", "algorithms", "Which traversal finds the shortest path (fewest edges) in an unweighted graph?",
     ["Breadth-first search", "Depth-first search", "In-order traversal", "Topological sort"]),
    ("phys-unit", "science", "What is the SI unit of force?", ["Newton", "Joule", "Watt", "Pascal"]),
    ("hash-collide", "data structures", "In a hash table, what is it called when two keys map to the same bucket?",
     ["A collision", "An overflow", "A rehash", "A probe"]),
]


def _make_static(key: str, prompt: str, opts: list[str]) -> Generator:
    def gen(rng: random.Random) -> Instance:
        return _choice_q(prompt, opts[0], opts[1:])

    return gen


for _key, _topic, _prompt, _opts in STATIC_MCQ:
    template(f"mcq-{_key}", "mcq", _topic, difficulty=1, group="mcq")(_make_static(_key, _prompt, _opts))


# ---------------------------------------------------------------------------------------------
# MCQ — parametric
# ---------------------------------------------------------------------------------------------


@template("mcq-code-output", "mcq", "python", difficulty=2, parametric=True, group="mcq")
def _mcq_code_output(rng: random.Random) -> Instance:
    nums = [rng.randint(2, 19) for _ in range(rng.randint(4, 6))]
    k = rng.randint(2, 5)
    code = (
        f"nums = {nums}\n"
        "total = 0\n"
        "for i, n in enumerate(nums):\n"
        "    if i % 2 == 0:\n"
        f"        total += n * {k}\n"
        "    else:\n"
        "        total -= n\n"
        "print(total)"
    )
    total = sum(n * k if i % 2 == 0 else -n for i, n in enumerate(nums))
    alt1 = sum(n * k if i % 2 == 1 else -n for i, n in enumerate(nums))
    alt2 = sum(n if i % 2 == 0 else -n for i, n in enumerate(nums))
    alt3 = sum(n * k for n in nums)
    return _choice_q("What does the following Python program print?", str(total),
                     _unique_distractors(rng, total, [alt1, alt2, alt3]), code=code)


@template("mcq-prime", "mcq", "number theory", difficulty=2, parametric=True, group="mcq")
def _mcq_prime(rng: random.Random) -> Instance:
    prime = rng.choice([p for p in range(53, 400) if _is_prime(p)])
    composites: list[int] = []
    while len(composites) < 3:
        c = rng.randrange(51, 400, 2)
        if not _is_prime(c) and c % 5 and c not in composites:
            composites.append(c)
    return _choice_q("Which of the following numbers is prime?", str(prime), [str(c) for c in composites])


@template("mcq-binary", "mcq", "number systems", difficulty=1, parametric=True, group="mcq")
def _mcq_binary(rng: random.Random) -> Instance:
    v = rng.randint(65, 250)
    return _choice_q(f"What is the decimal value of the binary number {v:b}?", str(v),
                     _unique_distractors(rng, v, [v + 1, v - 2, v ^ 4, v + 16]))


@template("mcq-gcd", "mcq", "number theory", difficulty=2, parametric=True, group="mcq")
def _mcq_gcd(rng: random.Random) -> Instance:
    g = rng.choice([6, 8, 9, 12, 14, 15, 18, 21])
    a, b = g * rng.choice([5, 7, 11, 13]), g * rng.choice([4, 6, 9, 10])
    real = math.gcd(a, b)
    return _choice_q(f"What is the greatest common divisor of {a} and {b}?", str(real),
                     _unique_distractors(rng, real, [real * 2, real // 2 if real % 2 == 0 else real + 3, real + g]))


@template("mcq-passage", "mcq", "reading", difficulty=1, parametric=True, group="mcq")
def _mcq_passage(rng: random.Random) -> Instance:
    name = rng.choice(FIRST_NAMES)
    c1, c2, c3, c4 = rng.sample(CITIES, 4)
    y1 = rng.randint(2001, 2012)
    gap = rng.randint(2, 6)
    passage = (
        f"{name} grew up in {c3}. After finishing university, {name} spent {gap} years working in {c1} "
        f"before relocating to {c2} in {y1 + gap}. A short sabbatical in {c4} followed much later."
    )
    return _choice_q(f"According to the passage, where did {name} live immediately before moving to {c2}?",
                     c1, [c3, c4, c2], passage=passage)


@template("mcq-complexity", "mcq", "algorithms", difficulty=2, parametric=True, group="mcq")
def _mcq_complexity(rng: random.Random) -> Instance:
    snippets = [
        ("for i in range(n):\n    j = 1\n    while j < n:\n        j *= 2", "O(n log n)"),
        ("for i in range(n):\n    for j in range(i, n):\n        pass", "O(n^2)"),
        ("i = n\nwhile i > 1:\n    i //= 2", "O(log n)"),
        ("for i in range(n):\n    for j in range(n):\n        for k in range(n):\n            pass", "O(n^3)"),
        ("total = 0\nfor i in range(n):\n    total += i\nfor j in range(n):\n    total -= j", "O(n)"),
    ]
    code, ans = rng.choice(snippets)
    pool = ["O(n log n)", "O(n^2)", "O(log n)", "O(n^3)", "O(n)", "O(2^n)"]
    wrong = [p for p in pool if p != ans]
    rng.shuffle(wrong)
    return _choice_q("What is the time complexity of the following code as a function of n?", ans, wrong[:3], code=code)


@template("mcq-modpow", "mcq", "number theory", difficulty=2, parametric=True, group="mcq")
def _mcq_modpow(rng: random.Random) -> Instance:
    a, b, m = rng.randint(3, 9), rng.randint(5, 12), rng.choice([7, 11, 13, 17])
    real = pow(a, b, m)
    cands = [(real + d) % m for d in (1, 2, m - 1, 3)]
    return _choice_q(f"What is ({a}^{b}) mod {m}?", str(real), _unique_distractors(rng, real, cands))


@template("tf-float", "true_false", "python", difficulty=1, group="mcq")
def _tf_float(rng: random.Random) -> Instance:
    return _choice_q("True or False: In Python, the expression 0.1 + 0.2 == 0.3 evaluates to True.", "False", ["True"])


@template("tf-bst", "true_false", "data structures", difficulty=1, group="mcq")
def _tf_bst(rng: random.Random) -> Instance:
    return _choice_q("True or False: An in-order traversal of a binary search tree visits keys in sorted order.",
                     "True", ["False"])


@template("tf-divisible", "true_false", "number theory", difficulty=1, parametric=True, group="mcq")
def _tf_div(rng: random.Random) -> Instance:
    d = rng.choice([7, 11, 13])
    n = d * rng.randint(20, 90) + (0 if rng.random() < 0.5 else rng.randint(1, d - 1))
    truth = n % d == 0
    return _choice_q(f"True or False: {n} is divisible by {d}.", "True" if truth else "False",
                     ["False" if truth else "True"])


# ---------------------------------------------------------------------------------------------
# multi-select
# ---------------------------------------------------------------------------------------------


@template("ms-primes", "multi_select", "number theory", difficulty=2, parametric=True)
def _ms_primes(rng: random.Random) -> Instance:
    primes = rng.sample([p for p in range(20, 200) if _is_prime(p)], rng.randint(2, 3))
    comps: list[int] = []
    while len(comps) < 6 - len(primes):
        c = rng.randrange(21, 200, 2)
        if not _is_prime(c) and c not in comps:
            comps.append(c)
    return _multi_q("Select ALL of the numbers below that are prime.", [str(p) for p in primes], [str(c) for c in comps])


@template("ms-div6", "multi_select", "number theory", difficulty=2, parametric=True)
def _ms_div6(rng: random.Random) -> Instance:
    good = rng.sample([6 * k for k in range(4, 40)], rng.randint(2, 3))
    bad: list[int] = []
    while len(bad) < 6 - len(good):
        c = rng.randint(20, 240)
        if c % 6 and c not in bad and (c % 2 == 0 or c % 3 == 0):
            bad.append(c)
    return _multi_q("Select ALL numbers that are divisible by both 2 and 3.", [str(g) for g in good], [str(b) for b in bad])


@template("ms-squares", "multi_select", "number theory", difficulty=1, parametric=True)
def _ms_squares(rng: random.Random) -> Instance:
    good = [k * k for k in rng.sample(range(11, 30), 2)]
    bad: list[int] = []
    while len(bad) < 4:
        c = rng.randint(120, 900)
        if math.isqrt(c) ** 2 != c and c not in bad:
            bad.append(c)
    return _multi_q("Select ALL perfect squares.", [str(g) for g in good], [str(b) for b in bad])


@template("ms-stable-sorts", "multi_select", "algorithms", difficulty=2)
def _ms_stable(rng: random.Random) -> Instance:
    stable = ["Merge sort", "Insertion sort", "Bubble sort", "Counting sort"]
    unstable = ["Heapsort", "Selection sort", "Quicksort (Lomuto partition)", "Shell sort"]
    good = rng.sample(stable, rng.randint(2, 3))
    return _multi_q("Select ALL sorting algorithms that are stable in their standard implementation.",
                    good, rng.sample(unstable, 6 - len(good)))


@template("ms-identifiers", "multi_select", "python", difficulty=1)
def _ms_ident(rng: random.Random) -> Instance:
    valid = ["_count", "total2", "maxValue", "__init__", "row_index", "x"]
    invalid = ["2fast", "my-var", "class", "for", "a b", "$price"]
    good = rng.sample(valid, rng.randint(2, 3))
    return _multi_q("Select ALL strings that are valid Python identifiers (usable as variable names).",
                    good, rng.sample(invalid, 6 - len(good)))


# ---------------------------------------------------------------------------------------------
# numerical
# ---------------------------------------------------------------------------------------------


@template("num-prob-red", "numerical", "probability", difficulty=2, parametric=True)
def _num_prob(rng: random.Random) -> Instance:
    r, b = rng.randint(3, 9), rng.randint(2, 8)
    p = (r / (r + b)) * ((r - 1) / (r + b - 1))
    return {"prompt": f"A bag contains {r} red and {b} blue marbles. Two marbles are drawn at random without "
                      f"replacement. What is the probability that both are red? Give your answer rounded to 4 "
                      f"decimal places.", "answer_key": _num_key(p, 4)}


@template("num-compound", "numerical", "finance", difficulty=2, parametric=True)
def _num_compound(rng: random.Random) -> Instance:
    principal, rate, years = rng.choice([1000, 2500, 5000, 1200]), rng.choice([3, 4, 5, 6, 7.5]), rng.randint(3, 10)
    v = principal * (1 + rate / 100) ** years
    return {"prompt": f"${principal} is invested at {rate}% annual interest, compounded annually. What is the "
                      f"balance after {years} years? Round to 2 decimal places.", "answer_key": _num_key(v, 2)}


@template("num-arith-series", "numerical", "algebra", difficulty=1, parametric=True)
def _num_series(rng: random.Random) -> Instance:
    a, d, n = rng.randint(2, 20), rng.randint(2, 9), rng.randint(15, 60)
    s = n * (2 * a + (n - 1) * d) // 2
    return {"prompt": f"An arithmetic sequence starts at {a} and increases by {d} each term. What is the sum of "
                      f"its first {n} terms?", "answer_key": _num_key(s, 0)}


@template("num-committee", "numerical", "combinatorics", difficulty=2, parametric=True)
def _num_committee(rng: random.Random) -> Instance:
    n, k = rng.randint(8, 14), rng.randint(3, 5)
    name = rng.choice(FIRST_NAMES)
    v = math.comb(n - 1, k - 1)
    return {"prompt": f"A committee of {k} people is chosen from a group of {n}, which includes {name}. In how "
                      f"many ways can the committee be chosen if {name} must be on it?", "answer_key": _num_key(v, 0)}


@template("num-speed", "numerical", "unit conversion", difficulty=1, parametric=True)
def _num_speed(rng: random.Random) -> Instance:
    kmh = rng.randint(37, 197)
    return {"prompt": f"A train travels at {kmh} km/h. What is its speed in metres per second? Round to 2 "
                      f"decimal places.", "answer_key": _num_key(kmh / 3.6, 2)}


@template("num-log", "numerical", "logarithms", difficulty=2, parametric=True)
def _num_log(rng: random.Random) -> Instance:
    base, n = rng.choice([2, 3, 5]), rng.randint(50, 900)
    return {"prompt": f"Solve for x: {base}^x = {n}. Round x to 3 decimal places.",
            "answer_key": _num_key(math.log(n) / math.log(base), 3)}


@template("num-stats", "numerical", "statistics", difficulty=2, parametric=True)
def _num_stats(rng: random.Random) -> Instance:
    data = [rng.randint(10, 99) for _ in range(rng.choice([7, 8, 9]))]
    which = rng.choice(["mean", "median", "population standard deviation"])
    if which == "mean":
        v = sum(data) / len(data)
    elif which == "median":
        s = sorted(data)
        m = len(s) // 2
        v = s[m] if len(s) % 2 else (s[m - 1] + s[m]) / 2
    else:
        mu = sum(data) / len(data)
        v = math.sqrt(sum((x - mu) ** 2 for x in data) / len(data))
    return {"prompt": f"Compute the {which} of the data set: {', '.join(map(str, data))}. Round to 2 decimal places.",
            "answer_key": _num_key(v, 2)}


@template("num-pct-change", "numerical", "arithmetic", difficulty=1, parametric=True)
def _num_pct(rng: random.Random) -> Instance:
    a = rng.randint(40, 400)
    b = a + rng.choice([-1, 1]) * rng.randint(5, a // 2)
    return {"prompt": f"A price changes from {a} to {b}. What is the percentage change? Give a signed value "
                      f"(negative for a decrease), rounded to 2 decimal places, without the % sign.",
            "answer_key": _num_key((b - a) / a * 100, 2)}


# ---------------------------------------------------------------------------------------------
# text
# ---------------------------------------------------------------------------------------------


def _text_q(prompt: str, accepted: list[str]) -> Instance:
    return {"prompt": prompt, "answer_key": {"type": "text", "accepted": accepted}}


@template("text-http", "text", "web", difficulty=1)
def _text_http(rng: random.Random) -> Instance:
    return _text_q("What does the acronym HTTP stand for?", ["hypertext transfer protocol"])


@template("text-capital-au", "text", "geography", difficulty=1)
def _text_capital(rng: random.Random) -> Instance:
    return _text_q("What is the capital city of Australia? (one word)", ["canberra"])


@template("text-photosynthesis", "text", "science", difficulty=1)
def _text_photo(rng: random.Random) -> Instance:
    return _text_q("Name the process by which green plants convert light energy into chemical energy. (one word)",
                   ["photosynthesis"])


@template("text-py-def", "text", "python", difficulty=1)
def _text_def(rng: random.Random) -> Instance:
    return _text_q("Which Python keyword is used to define a function? (one word)", ["def"])


@template("text-reverse", "text", "strings", difficulty=1, parametric=True)
def _text_reverse(rng: random.Random) -> Instance:
    w = rng.choice(WORDS).lower() + rng.choice(WORDS).lower()
    return _text_q(f"Write the string \"{w}\" reversed (characters in reverse order).", [w[::-1]])


@template("text-acrostic", "text", "strings", difficulty=1, parametric=True)
def _text_acrostic(rng: random.Random) -> Instance:
    ws = rng.sample(WORDS, rng.randint(4, 6))
    return _text_q(f"Write the word formed by taking the first letter of each of these words, in order: "
                   f"{', '.join(ws)}.", ["".join(w[0] for w in ws).lower()])


# ---------------------------------------------------------------------------------------------
# coding — problems with hidden tests computed by server-side reference solutions
# ---------------------------------------------------------------------------------------------


def _coding(title: str, statement: str, input_format: str, output_format: str,
            tests: list[tuple[str, str]], n_examples: int = 2) -> Instance:
    examples = [{"input": i, "output": o} for i, o in tests[:n_examples]]
    return {
        "prompt": title,
        "coding": {
            "title": title,
            "statement": statement,
            "input_format": input_format,
            "output_format": output_format,
            "examples": examples,
            "languages": ["python", "cpp", "java"],
        },
        "answer_key": {"type": "coding", "tests": [{"input": i, "output": o} for i, o in tests]},
    }


def _fmt_arr(a: list[int]) -> str:
    return " ".join(map(str, a))


@template("code-lis-run", "coding", "arrays", difficulty=3, parametric=True)
def _code_lis(rng: random.Random) -> Instance:
    def ref(a: list[int]) -> int:
        best = cur = 1 if a else 0
        for i in range(1, len(a)):
            cur = cur + 1 if a[i] > a[i - 1] else 1
            best = max(best, cur)
        return best

    arrays = [[1, 2, 2, 3, 4, 5, 1], [5, 4, 3, 2, 1], [7], [3, 3, 3, 3]]
    arrays += [[rng.randint(-50, 50) for _ in range(rng.randint(2, 30))] for _ in range(6)]
    arrays += [list(range(1, 50001)), [rng.randint(-10**9, 10**9) for _ in range(100000)]]
    tests = [(f"{len(a)}\n{_fmt_arr(a)}\n", f"{ref(a)}\n") for a in arrays]
    return _coding(
        "Longest Increasing Run",
        "Given an array of n integers, find the length of the longest contiguous subarray in which every element "
        "is strictly greater than the element before it.",
        "The first line contains n (1 <= n <= 100000). The second line contains n space-separated integers "
        "(each between -10^9 and 10^9).",
        "Print a single integer: the length of the longest strictly increasing contiguous run.",
        tests,
    )


@template("code-exact-k", "coding", "strings", difficulty=2, parametric=True)
def _code_exact_k(rng: random.Random) -> Instance:
    k = rng.randint(2, 4)

    def ref(s: str) -> int:
        return sum(1 for v in Counter(s).values() if v == k)

    letters = "abcdefghijklmnopqrstuvwxyz"
    strings = ["aabbbcc" * (k // 2 + 1), "a", "abcabcabcabc"[: 3 * k], "zzzz"]
    strings += ["".join(rng.choice(letters[: rng.randint(3, 10)]) for _ in range(rng.randint(5, 40))) for _ in range(6)]
    strings += ["".join(rng.choice(letters) for _ in range(200000))]
    tests = [(f"{s}\n", f"{ref(s)}\n") for s in strings]
    return _coding(
        f"Characters Appearing Exactly {k} Times",
        f"Given a string of lowercase English letters, count how many distinct characters occur exactly {k} "
        f"times in the string.",
        "A single line containing the string s (1 <= |s| <= 200000), lowercase letters only.",
        f"Print a single integer: the number of distinct characters that occur exactly {k} times.",
        tests,
    )


@template("code-pair-sum", "coding", "hashing", difficulty=3, parametric=True)
def _code_pairs(rng: random.Random) -> Instance:
    def ref(a: list[int], t: int) -> int:
        seen: Counter[int] = Counter()
        cnt = 0
        for x in a:
            cnt += seen[t - x]
            seen[x] += 1
        return cnt

    cases = [([1, 5, 7, -1, 5], 6), ([2, 2, 2, 2], 4), ([1], 2), ([0, 0, 0], 1)]
    cases += [([rng.randint(-20, 20) for _ in range(rng.randint(2, 40))], rng.randint(-10, 10)) for _ in range(6)]
    cases += [([rng.randint(1, 1000) for _ in range(100000)], 1000)]
    tests = [(f"{len(a)} {t}\n{_fmt_arr(a)}\n", f"{ref(a, t)}\n") for a, t in cases]
    return _coding(
        "Count Target Pairs",
        "Given an array a of n integers and a target T, count the number of index pairs (i, j) with i < j such "
        "that a[i] + a[j] = T. The answer may exceed 32-bit range.",
        "The first line contains n and T (1 <= n <= 100000, |T| <= 10^9). The second line contains n integers "
        "(|a[i]| <= 10^9).",
        "Print a single integer: the number of valid pairs.",
        tests,
    )


@template("code-brackets", "coding", "stacks", difficulty=2)
def _code_brackets(rng: random.Random) -> Instance:
    def ref(s: str) -> str:
        pairs, st = {")": "(", "]": "[", "}": "{"}, []
        for ch in s:
            if ch in "([{":
                st.append(ch)
            elif not st or st.pop() != pairs[ch]:
                return "NO"
        return "YES" if not st else "NO"

    def rand_balanced(n: int) -> str:
        out, st = [], []
        for _ in range(n):
            if st and rng.random() < 0.5:
                out.append({"(": ")", "[": "]", "{": "}"}[st.pop()])
            else:
                c = rng.choice("([{")
                st.append(c)
                out.append(c)
        out.extend({"(": ")", "[": "]", "{": "}"}[c] for c in reversed(st))
        return "".join(out)

    strings = ["([]{})", "([)]", "(", "}{", "{[()()]}"]
    strings += [rand_balanced(rng.randint(3, 30)) for _ in range(3)]
    strings += ["".join(rng.choice("()[]{}") for _ in range(rng.randint(2, 20))) for _ in range(3)]
    strings += [rand_balanced(100000)]
    tests = [(f"{s}\n", f"{ref(s)}\n") for s in strings]
    return _coding(
        "Balanced Brackets",
        "Determine whether a string consisting only of the characters ()[]{} is balanced: every opening bracket "
        "is closed by the same type of bracket in the correct order.",
        "A single line containing the string s (1 <= |s| <= 200000).",
        "Print YES if the string is balanced, otherwise print NO.",
        tests,
    )


@template("code-recurrence", "coding", "math", difficulty=2, parametric=True)
def _code_recurrence(rng: random.Random) -> Instance:
    a, b, m, s = rng.randint(2, 9), rng.randint(1, 20), rng.choice([1_000_003, 998_244_353, 1_000_000_007]), rng.randint(0, 9)

    def ref(n: int) -> int:
        v = s
        for _ in range(n):
            v = (a * v + b) % m
        return v

    ns = [0, 1, 5, 10] + [rng.randint(2, 1000) for _ in range(5)] + [1_000_000]
    tests = [(f"{n}\n", f"{ref(n)}\n") for n in ns]
    return _coding(
        "Linear Recurrence",
        f"A sequence is defined by f(0) = {s} and f(n) = ({a} * f(n-1) + {b}) mod {m} for n >= 1. Given n, "
        f"compute f(n).",
        "A single integer n (0 <= n <= 1000000).",
        "Print f(n).",
        tests,
        n_examples=3,
    )


# ---------------------------------------------------------------------------------------------
# image (rendered server-side; the page only gets an opaque PNG)
# ---------------------------------------------------------------------------------------------


@template("img-bar-value", "image", "charts", difficulty=2, parametric=True)
def _img_bar(rng: random.Random) -> Instance:
    labels = rng.sample(["North", "South", "East", "West", "Central", "Coastal", "Alpine"], 5)
    values = [rng.randrange(10, 95, 5) for _ in labels]
    target = rng.randrange(len(labels))
    return {
        "prompt": f"The bar chart shows units sold per region. How many units were sold in the {labels[target]} "
                  f"region? Answer with a number.",
        "image": {"kind": "bar_chart", "labels": labels, "values": values, "title": "Units sold by region",
                  "seed": rng.randint(0, 10**6)},
        "answer_key": _num_key(values[target], 0),
    }


@template("img-count-shapes", "image", "visual counting", difficulty=2, parametric=True)
def _img_shapes(rng: random.Random) -> Instance:
    target_color, target_shape = rng.choice(["red", "blue", "green"]), rng.choice(["circle", "square", "triangle"])
    n_target = rng.randint(3, 8)
    shapes = [{"shape": target_shape, "color": target_color} for _ in range(n_target)]
    others = [(s, c) for s in ["circle", "square", "triangle"] for c in ["red", "blue", "green"]
              if (s, c) != (target_shape, target_color)]
    for _ in range(rng.randint(5, 10)):
        s, c = rng.choice(others)
        shapes.append({"shape": s, "color": c})
    rng.shuffle(shapes)
    return {
        "prompt": f"How many {target_color} {target_shape}s are shown in the image? Answer with a number.",
        "image": {"kind": "shapes", "shapes": shapes, "seed": rng.randint(0, 10**6)},
        "answer_key": _num_key(n_target, 0),
    }


# ---------------------------------------------------------------------------------------------
# table
# ---------------------------------------------------------------------------------------------


@template("table-revenue", "table", "data analysis", difficulty=2, parametric=True)
def _table_revenue(rng: random.Random) -> Instance:
    products = rng.sample(["Widget", "Gadget", "Sprocket", "Gizmo", "Doohickey", "Bracket", "Flange"], 4)
    regions = ["North", "South", "East"]
    rows = []
    for p in products:
        for r in rng.sample(regions, 2):
            rows.append([p, r, rng.randint(3, 60), rng.choice([4, 5, 8, 10, 12, 15, 20])])
    rng.shuffle(rows)
    region = rng.choice(sorted({r[1] for r in rows}))
    total = sum(u * pr for _, rg, u, pr in rows if rg == region)
    return {
        "prompt": f"Using the table, what is the total revenue (Units × Unit Price) for the {region} region? "
                  f"Answer with a number.",
        "table": {"columns": ["Product", "Region", "Units", "Unit Price"], "rows": rows},
        "answer_key": _num_key(total, 0),
    }


@template("table-scores", "table", "data analysis", difficulty=2, parametric=True)
def _table_scores(rng: random.Random) -> Instance:
    names = rng.sample(FIRST_NAMES, 6)
    rows = [[n, rng.randint(40, 100), rng.randint(40, 100), rng.randint(40, 100)] for n in names]
    thr = rng.randint(65, 80)
    count = sum(1 for _, a, b, c in rows if (a + b + c) / 3 > thr)
    return {
        "prompt": f"Using the table, how many students have an average score across the three tests strictly "
                  f"greater than {thr}? Answer with a number.",
        "table": {"columns": ["Student", "Test 1", "Test 2", "Test 3"], "rows": rows},
        "answer_key": _num_key(count, 0),
    }


# ---------------------------------------------------------------------------------------------
# instance assembly
# ---------------------------------------------------------------------------------------------

DEFAULT_COMPOSITION = {"mcq": 10, "numerical": 3, "multi_select": 2, "coding": 2, "text": 2, "image": 1, "table": 1}
POINTS = {"coding": 3.0}


def finalize(tpl: Template, raw: Instance, rng: random.Random, shuffle_options: bool) -> Instance:
    inst: Instance = {
        "uid": f"{rng.getrandbits(64):016x}",
        "template": tpl.id,
        "kind": tpl.kind,
        "topic": tpl.topic,
        "difficulty": tpl.difficulty,
        "points": POINTS.get(tpl.kind, 1.0),
        "prompt": raw["prompt"],
    }
    for k in ("code", "passage", "table", "image", "coding"):
        if k in raw:
            inst[k] = raw[k]
    if "_options" in raw:
        texts = list(raw["_options"])
        if shuffle_options and tpl.kind != "true_false":
            rng.shuffle(texts)
        elif tpl.kind == "true_false":
            texts = ["True", "False"]
        options = [{"id": f"opt-{rng.getrandbits(32):08x}", "text": t} for t in texts]
        inst["options"] = options
        correct_ids = [o["id"] for o in options if o["text"] in raw["_correct"]]
        inst["answer_key"] = {"type": "choice", "correct": correct_ids, "multi": tpl.kind == "multi_select"}
    else:
        inst["answer_key"] = raw["answer_key"]
    return inst


def generate_question_set(seed: int, composition: dict[str, int] | None = None, pool: list[str] | None = None,
                          shuffle_questions: bool = True, shuffle_options: bool = True) -> list[Instance]:
    rng = random.Random(seed)
    composition = composition or DEFAULT_COMPOSITION
    eligible = [TEMPLATES[t] for t in (pool or list(TEMPLATES))]
    out: list[Instance] = []
    for group, count in composition.items():
        candidates = [t for t in eligible if t.group == group]
        if len(candidates) < count:
            raise ValueError(f"not enough templates for group {group}: {len(candidates)} < {count}")
        for tpl in rng.sample(candidates, count):
            out.append(finalize(tpl, tpl.gen(rng), rng, shuffle_options))
    if shuffle_questions:
        rng.shuffle(out)
    return out


def public_view(inst: Instance, index: int, total: int) -> Instance:
    """What the candidate's browser is allowed to see."""
    hidden = {"answer_key", "template", "difficulty", "topic"}
    view = {k: v for k, v in inst.items() if k not in hidden}
    view["number"] = index + 1
    view["total"] = total
    if "image" in view:
        view["image"] = {"alt": "Question figure"}  # params stay server-side
    return view
