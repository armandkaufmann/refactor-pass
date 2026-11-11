"""measure.py's function finder on broken and extreme input: it never raises, and never takes long.

A short fuzz with a fixed seed mutates the samples a few hundred times: cut short, a line deleted, a
bracket or a quote dropped or added, two files joined, a keyword glued onto a word. Then hand-made extremes:
huge lines, deep nesting, thousands of unclosed lists. tools/stress.py runs a longer fuzz, the extremes at
full size and every file of a folder, outside the default run.
"""

import os
import random
import signal
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


if __name__ == "__main__":
    unittest.main()
