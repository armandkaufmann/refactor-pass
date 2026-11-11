"""Stress measure.py's function finder on real code, outside the default run: none of its calls may raise
or hang.

  fuzz FOLDER...     damages files picked from the folders (JavaScript and TypeScript first, then some of
                     every other language), and times each call: cut short, a line deleted, a bracket or
                     quote dropped or added, two files joined, a line of another put in, a keyword glued
                     to the front of a word. The same seed gives the same run.
  extremes           hand-made extreme inputs at full size (the default run has the slow ones at a quarter)
  sweep FOLDER...    every file with a language measure.py knows, once each

Each prints its failures and slowest calls, and exits 1 if a call raised or ran past --limit. It tests the
skill's scripts, or those REFACTOR_PASS_SCRIPTS names. The time limit needs a system with SIGALRM.

Examples:
  stress.py fuzz ~/code/some-repo --seed 1
  stress.py extremes
  stress.py sweep ~/code/some-repo ~/code/another
"""

import argparse
import os
import random
import signal
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import support  # noqa: E402

BRACKETS = "()[]{}<>\"'`/"
# Keywords the finders look for, glued to a word or put before it.
KEYWORDS = ["function", "function ", "async", "async ", "catch", "def", "def ", "func", "fn", "fun", "of", "in",
            "get", "set ", "static ", "export ", "default ", "abstract ", "declare ", "interface", "type", "class",
            "init", "subscript", "public ", "new", "return", "=> ", "@"]
EXTREMES = {
    "spaces.ts": lambda: "x = 1" + " " * 200000 + "\nfoo(" + " " * 200000,
    "long-line.js": lambda: "const a = " + "b / c / " * 60000 + "d;",
    "regex-ish.js": lambda: "x = (" + "/a/ " * 50000 + ")",
    "deep.ts": lambda: "foo(" * 5000 + ")" * 5000,
    "open-calls.ts": lambda: "\n".join("foo%d(" % i for i in range(20000)),
    "open-arrows.ts": lambda: "\n".join("const f%d = (" % i for i in range(20000)),
    "keys.ts": lambda: "const o = {\n" + "\n".join("  k%d: (a: string) =>" % i for i in range(20000)) + "\n}",
    "typed.ts": lambda: "\n".join("let x%d: Array<" % i for i in range(20000)),
    "py-sig.py": lambda: "def f(\n" + "    a,\n" * 50000 + "):\n    pass",
    "docstrings.py": lambda: '"""' * 30001,
    "c-tokens.cs": lambda: "public " + "a " * 50000 + "(",
    "empty.ts": lambda: "",
    "nul-ish.ts": lambda: "\x00\x01\x02 function f() {}",
}


class Hang(Exception):
    pass


def on_alarm(signum, frame):
    raise Hang()


def timed(measure, name, text, limit):
    """One call: its time, and its failure or None."""
    if hasattr(signal, "setitimer"):
        signal.signal(signal.SIGALRM, on_alarm)
        signal.setitimer(signal.ITIMER_REAL, limit)
    start = time.time()
    failure = None
    try:
        measure.functions(name, text)
    except Hang:
        failure = "hang: over %.0fs" % limit
    except Exception as e:
        failure = "%s: %s" % (type(e).__name__, e)
    finally:
        if hasattr(signal, "setitimer"):
            signal.setitimer(signal.ITIMER_REAL, 0)
    return time.time() - start, failure


def files_under(folders, by_extension):
    """Every file under the folders with a language measure.py knows, by language, in a stable order."""
    found = {}
    for top in folders:
        for folder, dirs, names in os.walk(top):
            dirs[:] = sorted(d for d in dirs if d not in (".git", "node_modules"))
            for name in sorted(names):
                language = by_extension.get(os.path.splitext(name)[1].lower())
                if language and os.path.isfile(os.path.join(folder, name)):
                    found.setdefault(language[0], []).append(os.path.join(folder, name))
    return found


def read(path):
    with open(path, "rb") as f:
        data = f.read()
    return None if b"\0" in data[:8000] else data.decode("utf-8", errors="replace")


def damage(rng, text, other):
    """A damaged copy of text, and what was done to it."""
    lines = text.split("\n")
    kind = rng.choice(["truncate", "delete line", "drop bracket", "add bracket", "join", "insert line",
                       "keyword"])
    if kind == "truncate":
        at = rng.randrange(len(lines) + 1)
        return "\n".join(lines[:at]), "%s at line %d" % (kind, at)
    if kind == "delete line":
        at = rng.randrange(len(lines))
        return "\n".join(lines[:at] + lines[at + 1:]), "%s %d" % (kind, at + 1)
    if kind == "drop bracket":
        spots = [i for i, c in enumerate(text) if c in BRACKETS]
        if not spots:
            return text, "unchanged"
        at = rng.choice(spots)
        return text[:at] + text[at + 1:], "%s at offset %d" % (kind, at)
    if kind == "add bracket":
        at = rng.randrange(len(text) + 1)
        c = rng.choice(BRACKETS)
        return text[:at] + c + text[at:], "%s %r at offset %d" % (kind, c, at)
    if kind == "keyword":
        words = [i for i, line in enumerate(lines) if line.strip()]
        if not words:
            return text, "unchanged"
        at = rng.choice(words)
        indent = len(lines[at]) - len(lines[at].lstrip())
        word = rng.choice(KEYWORDS)
        lines[at] = lines[at][:indent] + word + lines[at][indent:]
        return "\n".join(lines), "%s %r before line %d" % (kind, word, at + 1)
    other_lines = other.split("\n")
    if kind == "insert line":
        at, line = rng.randrange(len(lines) + 1), rng.choice(other_lines)
        return "\n".join(lines[:at] + [line] + lines[at:]), "%s %r at %d" % (kind, line.strip()[:40], at + 1)
    a, b = rng.randrange(len(lines) + 1), rng.randrange(len(other_lines) + 1)
    return "\n".join(lines[:a] + other_lines[b:]), "%s: lines 1-%d, then another file from line %d" % (kind, a, b + 1)


def report(failures, times, label):
    times.sort(reverse=True)
    print("%s: %d calls, %d failures" % (label, len(times), len(failures)))
    for failure in failures[:30]:
        print("  " + failure)
    print("slowest: %s" % "; ".join("%.2fs %s" % (t, what) for t, what in times[:5]))
    print("over 2s: %d" % sum(1 for t in times if t[0] > 2))
    return 1 if failures else 0


def fuzz(measure, args):
    rng = random.Random(args.seed)
    found = files_under(args.folders, measure.BY_EXTENSION)
    picked = []
    for language in sorted(found):
        want = args.js if language in ("JavaScript", "TypeScript", "Vue") else args.others
        pool = found[language]
        picked += [p for p in rng.sample(pool, min(want, len(pool)))]
    texts = [(path, read(path)) for path in picked]
    texts = [t for t in texts if t[1] is not None]
    failures, times = [], []
    for path, text in texts:
        for round_ in range(args.rounds):
            damaged, what = damage(rng, text, rng.choice(texts)[1])
            took, failure = timed(measure, os.path.basename(path), damaged, args.limit)
            times.append((took, "%s (%s)" % (os.path.basename(path), what)))
            if failure:
                failures.append("%s, round %d (%s): %s" % (path, round_, what, failure))
    return report(failures, times, "seed %d, %d files" % (args.seed, len(texts)))


def extremes(measure, args):
    failures, times = [], []
    for name, make in EXTREMES.items():
        took, failure = timed(measure, name, make(), args.limit)
        print("%-15s %6.2fs %s" % (name, took, failure or "ok"), flush=True)
        times.append((took, name))
        if failure:
            failures.append("%s: %s" % (name, failure))
    return report(failures, times, "extremes")


def sweep(measure, args):
    failures, times = [], []
    found = files_under(args.folders, measure.BY_EXTENSION)
    for language in sorted(found):
        for path in found[language]:
            text = read(path)
            if text is None:
                continue
            took, failure = timed(measure, os.path.basename(path), text, args.limit)
            times.append((took, path))
            if failure:
                failures.append("%s: %s" % (path, failure))
    print("files by language: %s" % ", ".join("%s %d" % (k, len(v)) for k, v in sorted(found.items())))
    return report(failures, times, "sweep")


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__.split("\n\n", 1)[1])
    parser.add_argument("what", choices=["fuzz", "extremes", "sweep"])
    parser.add_argument("folders", nargs="*", help="the folders to read, for fuzz and sweep")
    parser.add_argument("--seed", type=int, default=20261111, help="fuzz's random seed (default 20261111)")
    parser.add_argument("--js", type=int, default=300, help="fuzz: JavaScript and TypeScript files to pick")
    parser.add_argument("--others", type=int, default=25, help="fuzz: files to pick of every other language")
    parser.add_argument("--rounds", type=int, default=8, help="fuzz: damaged copies of each file")
    parser.add_argument("--limit", type=float, default=10.0, help="seconds after which a call counts as a hang")
    args = parser.parse_args()
    if args.what != "extremes" and not args.folders:
        parser.error("%s needs at least one folder" % args.what)
    measure = support.load("measure")
    print("Testing %s" % support.SCRIPTS)
    sys.exit({"fuzz": fuzz, "extremes": extremes, "sweep": sweep}[args.what](measure, args))


if __name__ == "__main__":
    main()
