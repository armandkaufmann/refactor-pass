"""measure.py's function finder on broken and extreme input: it never raises, and never takes long.

A short fuzz with a fixed seed mutates the samples a few hundred times: cut short, a line deleted, a
bracket or a quote dropped or added, two files joined, a keyword glued onto a word. Then hand-made extremes:
huge lines, deep nesting, thousands of unclosed lists. tools/stress.py runs a longer fuzz, the extremes at
full size and every file of a folder, outside the default run.
"""

import os
import random
import re
import signal
import subprocess
import sys
import time
import unittest

try:
    from . import support
except ImportError:
    import support

FUNCTIONS = os.path.join(support.SAMPLES, "functions")
SEED = 20261111
MUTATIONS = 400
KEYWORDS = ["function", "def", "func", "fn", "fun", "async", "export default", "catch", "class", "=>", "return /"]


class TooSlow(Exception):
    pass


def samples():
    found = []
    for name in sorted(os.listdir(FUNCTIONS)):
        if name != "expected.json":
            with open(os.path.join(FUNCTIONS, name), encoding="utf-8") as f:
                found.append((name, f.read()))
    return found


def mutate(rng, name, text, others):
    """One random change to a sample's text, and a description of it."""
    kind = rng.randrange(7)
    lines = text.split("\n")
    if kind == 0 and text:
        at = rng.randrange(len(text))
        return text[:at], "cut at %d" % at
    if kind == 1 and lines:
        at = rng.randrange(len(lines))
        return "\n".join(lines[:at] + lines[at + 1:]), "line %d deleted" % (at + 1)
    if kind == 2:
        brackets = [i for i, c in enumerate(text) if c in "()[]{}<>\"'`"]
        if brackets:
            at = rng.choice(brackets)
            return text[:at] + text[at + 1:], "%r at %d dropped" % (text[at], at)
    if kind == 3:
        at = rng.randrange(len(text) + 1)
        c = rng.choice("()[]{}<>\"'`/")
        return text[:at] + c + text[at:], "%r added at %d" % (c, at)
    if kind == 4:
        other_name, other = rng.choice(others)
        return text + other, "joined with %s" % other_name
    if kind == 5:
        words = [i for i in range(1, len(text)) if text[i - 1] == " " and text[i].isalpha()]
        if words:
            at = rng.choice(words)
            keyword = rng.choice(KEYWORDS)
            return text[:at] + keyword + text[at:], "%r glued at %d" % (keyword, at)
    at = rng.randrange(len(lines) + 1)
    return "\n".join(lines[:at] + [rng.choice(lines or [""])] + lines[at:]), "a line repeated at %d" % (at + 1)


class Limit(object):
    """A time limit on one call: an alarm where the system has one, else only a check afterwards."""

    def __init__(self, seconds):
        self.seconds = seconds
        self.alarm = hasattr(signal, "setitimer")

    def __enter__(self):
        self.start = time.time()
        if self.alarm:
            def stop(signum, frame):
                raise TooSlow()
            self.previous = signal.signal(signal.SIGALRM, stop)
            signal.setitimer(signal.ITIMER_REAL, self.seconds)
        return self

    def __exit__(self, *exc):
        if self.alarm:
            signal.setitimer(signal.ITIMER_REAL, 0)
            signal.signal(signal.SIGALRM, self.previous)
        self.elapsed = time.time() - self.start
        return False


def check(test, name, text, seconds, what):
    measure = support.load("measure")
    try:
        with Limit(seconds) as limit:
            lines, functions, language = measure.functions(name, text)
    except TooSlow:
        test.fail("%s took over %ds: %s" % (name, seconds, what))
    except Exception as e:
        test.fail("%s raised %s: %s (%s)" % (name, type(e).__name__, e, what))
    test.assertLess(limit.elapsed, seconds, "%s: %s" % (name, what))
    count = len(text.split("\n"))
    test.assertTrue(0 <= lines <= count, "%s: %s" % (name, what))
    for found in functions or []:
        test.assertTrue(1 <= found[1] <= found[2] <= count and 0 <= found[3] <= found[2] - found[1] + 1,
                        "%s: %r (%s)" % (name, found, what))


class Fuzz(unittest.TestCase):

    def test_mutated_samples(self):
        rng = random.Random(SEED)
        files = samples()
        self.assertGreater(len(files), 20)
        for n in range(MUTATIONS):
            name, text = files[n % len(files)]
            mutated, what = mutate(rng, name, text, files)
            check(self, name, mutated, 5, what)

    def test_each_sample_in_every_language(self):
        # A file read by another language's rules: Python as C, Go as Ruby, and so on.
        measure = support.load("measure")
        extensions = [lang[1].split()[0] for lang in measure.LANGUAGES]
        for name, text in samples():
            for extension in extensions:
                check(self, "sample" + extension, text, 5, "%s read as %s" % (name, extension))


# Hand-made extremes: (file name, text). The slower ones are at a quarter of tools/stress.py's sizes.
EXTREMES = [
    ("spaces.ts", "x = 1" + " " * 200000 + "\nfoo(" + " " * 200000),
    ("deep.ts", "foo(" * 5000 + ")" * 5000),
    ("open-calls.ts", "\n".join("foo%d(" % i for i in range(20000))),
    ("py-sig.py", "def f(\n" + "    a,\n" * 50000 + "):\n    pass"),
    ("docstrings.py", '"""' * 30001),
    ("c-tokens.cs", "public " + "a " * 50000 + "("),
    ("empty.ts", ""),
    ("nul-ish.ts", "\x00\x01\x02 function f() {}"),
    ("long-line.js", "const a = " + "b / c / " * 15000 + "d;"),
    ("regex-ish.js", "x = (" + "/a/ " * 12500 + ")"),
    ("open-arrows.ts", "\n".join("const f%d = (" % i for i in range(5000))),
    ("keys.ts", "const o = {\n" + "\n".join("  k%d: (a: string) =>" % i for i in range(5000)) + "\n}"),
    ("typed.ts", "\n".join("let x%d: Array<" % i for i in range(5000))),
]


class Extremes(unittest.TestCase):

    def test_extremes(self):
        for name, text in EXTREMES:
            with self.subTest(case=name):
                check(self, name, text, 10, "an extreme")


# Lines of many generic types that aren't a definition, each of which once took a time that doubled with each
# type: a C-family line can be read as types in more ways than one, and every way was tried before giving up.
def generic_lines(k):
    return [
        "Map<String, List<Integer>> " * k,
        "Map<String, List<Integer>> " * k + "= f(x);",
        " ".join("a%d<b%d>" % (i, i) for i in range(k)) + " ;",
        "template <" + "a<b>, " * k + " x",
        "    public static <" + ", ".join("T%d extends Comparable<T%d>" % (i, i) for i in range(k)) + "> void sort;",
        "    std::tuple<" + ", ".join("A%d<int>" % i for i in range(k)) + "> t;",
        "    private final " + "Map<String, " * k + "Integer" + ">" * k + " cache = new HashMap<>();",
        "    public (" + ", ".join("List<int> a%d" % i for i in range(k)) + ") Pairs;",
        "    " + " ".join("List<A%d>" % i for i in range(k)) + " x",
        "    public void M<T>() " + " ".join("where T%d : IFoo<T%d>" % (i, i) for i in range(k)),
        "@A(" * k + "x",
        "public " * k + "x;(",
    ]


GENERICS = """
import sys, time
import measure
from test_robustness import generic_lines
start = time.time()
for extension in (".java", ".cs", ".cpp", ".c", ".h"):
    for line in generic_lines(200):
        measure.functions("a" + extension, line + "\\n")
print("%.1f" % (time.time() - start))
"""


class Generics(unittest.TestCase):

    def test_long_lines_of_generic_types(self):
        code = "import sys; sys.path[:0] = [%r, %r]\n" % (support.SCRIPTS, support.HERE) + GENERICS
        try:
            result = support.run_python(code, timeout=60)
        except subprocess.TimeoutExpired:
            self.fail("measuring lines of 200 generic types took over a minute")
        self.assertEqual(result.code, 0, result)
        self.assertLess(float(result.out), 10, result)


# Files of many definitions whose ends were each looked for to the end of the file, once taking a time that
# grew with the square of their length or faster: unclosed definitions, nested ones each indented one more, and
# #if blocks never closed, each branch of which opens a function's body.
GROWING = {
    "unclosed.py": lambda: "def f(\n" * 20000,
    "unclosed.gd": lambda: "func a(\n" * 20000,
    "nested.py": lambda: "".join(" " * i + "def f%d():\n" % i for i in range(3000)),
    "nested.rb": lambda: "".join(" " * i + "def f%d\n" % i for i in range(3000)),
    "open-ifs.c": lambda: "#if A\nint f() {\n#else\n" * 10000,
}
TIME = """
import sys, time
import measure
from test_robustness import GROWING
text = GROWING[sys.argv[1]]()
start = time.time()
measure.functions(sys.argv[1], text)
print("%.2f" % (time.time() - start))
"""


class Growing(unittest.TestCase):

    def test_files_of_many_definitions(self):
        code = "import sys; sys.path[:0] = [%r, %r]\n" % (support.SCRIPTS, support.HERE) + TIME
        for name in sorted(GROWING):
            with self.subTest(case=name):
                try:
                    result = support.run_python(code, name, timeout=30)
                except subprocess.TimeoutExpired:
                    self.fail("%s took over 30 seconds" % name)
                self.assertEqual(result.code, 0, result)
                self.assertLess(float(result.out), 5, name)


# A script run with one of the functions it calls replaced by one that raises, as a bug would.
CRASH = """
import json, os, runpy, sys
sys.path.insert(0, os.environ["REFACTOR_PASS_SCRIPTS"])
import scoping
def boom(*args, **kwargs):
    raise RuntimeError("boom")
setattr({module}, {name!r}, boom)
sys.argv = [os.path.join(os.environ["REFACTOR_PASS_SCRIPTS"], {script!r})] + sys.argv[1:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


class LastLineOfDefence(unittest.TestCase):
    """An exception a script doesn't foresee ends it with one plain line that says it's a bug in the script,
    and where, not a traceback; and a reader that stops reading, as head does, isn't one."""

    @classmethod
    def setUpClass(cls):
        repo = support.Repo("defence")
        repo.commit("2026-01-01", "Start", {"a.py": "def f():\n    return 1\n"})
        repo.done()
        cls.repo = repo.path

    def test_a_bug_is_one_plain_line(self):
        page = support.write_text(os.path.join(support.new_folder("page"), "page.html"), support.page_with())
        for script, module, name, args in (("heatmap.py", "scoping", "toplevel", ["-C", self.repo]),
                                           ("measure.py", "scoping", "tracked_files", ["-C", self.repo]),
                                           ("check_page.py", "json", "loads", [page])):
            with self.subTest(script=script):
                result = support.run_python(CRASH.format(module=module, name=name, script=script), *args)
                self.assertEqual(result.code, 3, result)
                self.assertNotIn("Traceback", result.err)
                self.assertRegex(result.err, r"^%s: stopped on a bug in the script itself, not a problem with the "
                                             r"repo or the command: RuntimeError: boom \(%s, line \d+, in \w+\)\.\n$"
                                 % (re.escape(script), re.escape(script)))

    def test_a_reader_that_stops_reading(self):
        for script in ("heatmap.py", "measure.py"):
            with self.subTest(script=script):
                process = subprocess.Popen([sys.executable, os.path.join(support.SCRIPTS, script), "-C", self.repo],
                                           stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=support.environment())
                process.stdout.close()
                err = process.communicate(timeout=60)[1].decode("utf-8", "replace")
                self.assertEqual(err, "")

    def test_skill_md_says_what_to_do(self):
        with open(os.path.join(os.path.dirname(support.SCRIPTS), "SKILL.md"), encoding="utf-8") as f:
            text = " ".join(f.read().split())
        self.assertIn("If a script stops on a bug in the script itself, as it says, tell the user what it said, "
                      "and go on without it", text)


if __name__ == "__main__":
    unittest.main()
