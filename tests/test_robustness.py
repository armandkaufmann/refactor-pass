"""measure.py's function finder on broken and extreme input: it never raises, and never takes long.

A short fuzz with a fixed seed mutates the samples a few hundred times: cut short, a line deleted, a
bracket or a quote dropped or added, two files joined, a keyword glued onto a word. Then hand-made extremes:
huge lines, deep nesting, thousands of unclosed lists. tools/stress.py runs a longer fuzz, the extremes at
full size and every file of a folder, outside the default run.
"""

import errno
import os
import posixpath
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


def check(test, name, text, seconds, what, aside=None):
    """With aside, a list, the code compiled only for tests is set aside in it, as measure.py's run asks."""
    measure = support.load("measure")
    try:
        with Limit(seconds) as limit:
            lines, functions, language = measure.functions(name, text, *([] if aside is None else [aside]))
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
    parts = sorted(aside or [])
    for part in parts:
        test.assertTrue(1 <= part[0] <= part[1] <= count and 0 <= part[2] <= part[1] - part[0] + 1,
                        "%s: %r set aside (%s)" % (name, part, what))
    for part, after in zip(parts, parts[1:]):
        test.assertLess(part[1], after[0], "%s: %r and %r overlap (%s)" % (name, part, after, what))
    for found in functions or []:
        test.assertFalse(any(part[0] <= found[1] <= part[1] for part in parts),
                         "%s: %r found in a part set aside (%s)" % (name, found, what))


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


# Rust's tests inside files, looked for where measure.py's run sets them aside: modules never closed, nested,
# after thousands of attributes, and a cfg nested thousands deep.
TESTS_INSIDE = [
    ("open.rs", "#[cfg(test)]\nmod a {\n" * 5000),
    ("nested.rs", "#[cfg(test)] mod a {\n" * 5000 + "}\n" * 5000),
    ("attributes.rs", "#[a]\n" * 20000 + "mod a {\n}\n"),
    ("cfg.rs", "#[cfg(" + "all(" * 5000 + "test" + ")" * 5001 + "]\nmod a {\n}\n"),
]


class Extremes(unittest.TestCase):

    def test_extremes(self):
        for name, text in EXTREMES:
            with self.subTest(case=name):
                check(self, name, text, 10, "an extreme")

    def test_tests_inside_files(self):
        for name, text in TESTS_INSIDE:
            with self.subTest(case=name):
                check(self, name, text, 10, "an extreme", [])
        rng = random.Random(SEED)
        files = [f for f in samples() if f[0].endswith(".rs")] + [
            ("lib.rs", "#[cfg(all(test, unix))]\nmod tests {\n    #![allow(unused)]\n    #[test]\n    fn a() {\n"
                       "        let _ = ('}', \"{\");\n    }\n}\nfn b() {\n}\n")]
        for n in range(100):
            name, text = files[n % len(files)]
            mutated, what = mutate(rng, name, text, files)
            check(self, name, mutated, 5, what, [])


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


# Files whose reading once took a time that grew with the square of their size, or faster. Each is made at a size
# and at SCALE times it, and read at both, three times over: at the larger, its fastest reading must take under
# RATIO times as long as its fastest at the smaller, where a time that grows with the size takes about SCALE times
# as long and one that grows with its square about SCALE * SCALE times, however fast the machine; and under LIMIT
# seconds. The time is the processor's, spent on the reading alone, which a busy machine doesn't stretch, though it
# stretches a long reading's time on the clock more than a short one's. On Windows, whose processor time advances in
# ticks of about 15.6 ms, too coarse for readings of 7 to 80 ms, it's the clock's, so a busy Windows machine can
# still make a case seem to grow too fast. A case that seems to is timed once more, as a reading slower per
# character on a large text can also make it seem to; and one whose readings take over TIMEOUT seconds on the clock
# fails. A case can name the step of measure.py it times, given the text's lines, where the rest of the reading
# would hide it; "modules", Rust's test modules of the files it makes, as {path: text}; or "message", the heatmap's
# reading for fixes of a commit whose subject is the text's first line and whose body the rest. Unclosed definitions,
# nested ones each indented one more (sized by their lines' indents), and #if blocks never closed, each branch of
# which opens a function's body. Rust's tests inside a file, each set aside, as measure.py's run asks: thousands of
# test modules, a run of thousands of cfgs on one item or on none, of attributes before a module's inner cfgs, of
# statics with no ;; thousands of test items on one line, or of inner cfgs, #![cfg(test)], in one module, in none,
# in functions' bodies or each first in a module of its own; and a # and thousands of spaces on a line that says
# cfg. A header's line of thousands of Objective-C messages, [[x y] z], none a C23 attribute, or of thousands of [[
# before one ;.
GROWING = {
    "unclosed.py": (1100, lambda n: "def f(\n" * n),
    "unclosed.gd": (1100, lambda n: "func a(\n" * n),
    "nested.py": (100000, lambda n: "".join(" " * i + "def f%d():\n" % i for i in range(int((2 * n) ** 0.5)))),
    "nested.rb": (280000, lambda n: "".join(" " * i + "def f%d\n" % i for i in range(int((2 * n) ** 0.5)))),
    "open-ifs.c": (640, lambda n: "#if A\nint f() {\n#else\n" * n),
    "tests.rs": (820, lambda n: "#[cfg(test)]\nmod t {\n    fn f() {}\n}\n" * n),
    "attributes.rs": (1100, lambda n: "#[cfg(test)]\n" * n + "fn g() {}\n"),
    "attributes-alone.rs": (1100, lambda n: "#[cfg(test)]\n" * n),
    "inner-cfgs.rs": (550, lambda n: "#[a]\n" * n + "mod t {\n" + "    #![cfg(test)]\n" * n + "}\n"),
    "line-of-fns.rs": (570, lambda n: "#[cfg(test)] fn t() { let b = [2]; } " * n + "\n"),
    "line-of-mods.rs": (750, lambda n: "#[cfg(test)] mod m { } " * n + "\n"),
    "messages.h": (3100, lambda n: "void g(void) { " + "[[x y] z]; " * n + "}\n"),
    "statics.rs": (550, lambda n: "#[cfg(test)]\nstatic B: u16 = 2\n" * n),
    "openings.h": (35000, lambda n: "int x = " + "[[" * n + ";\n"),
    "line-of-inner-cfgs.rs": (1050, lambda n: "mod m { " + "#![cfg(test)] " * n + "}\n"),
    "inner-cfgs-alone.rs": (1050, lambda n: "#![cfg(test)] " * n + "\n"),
    "line-of-test-mods.rs": (380, lambda n: "mod m { #![cfg(test)] fn t() {} } " * n + "\n"),
    "line-of-fn-cfgs.rs": (440, lambda n: "fn g() { #![cfg(test)] } " * n + "\n"),
    "inner-after-attributes.rs": (350, lambda n: "mod m { #![allow(x)] #![cfg(test)] } " * n + "\n"),
    "two-inner-cfgs.rs": (300, lambda n: "mod m { #![cfg(test)] #![cfg(test)] } " * n + "\n"),
    "outer-and-inner.rs": (270, lambda n: "#[cfg(test)] mod m { #![cfg(test)] } " * n + "\n"),
    "nested-test-mods.rs": (200, lambda n: "mod a { #![cfg(test)] mod b { #![cfg(test)] } } " * n + "\n"),
    "hash-then-spaces.rs": (150000, lambda n: "let cfg = 1; x #" + " " * n + "y\n"),
    # Test items between long runs of text on one line, set aside on their own: each copied the rest of the line.
    "tests-in-a-long-line": (1500000, lambda n: " " + "x" * n + " " + "#[cfg(test)] fn f() {} " * (n // 1000) +
                             "x" * n + " ", "rust_test_items"),
    # Thousands of /* on one line, in a language whose block comments nest.
    "comment-openers.rs": (31000, lambda n: "/* " * n + "\n"),
    # A header's #ifdefs nested thousands deep around thousands of lines, its evidence of C++ read on its own.
    "deep-ifdefs.h": (4000, lambda n: "#ifdef A\n" * n + "int x;\n" * n + "#endif\n" * n, "cpp_header"),
    # A ! and thousands of spaces in a header's #if on __cplusplus.
    "bang-then-spaces.h": (110000, lambda n: "#if !" + " " * n + "x && __cplusplus\nint a;\n#endif\n"),
    # A header of thousands of blank lines, which its evidence of C++ read on from each.
    "blank-lines.h": (2700, lambda n: "int a;\n" + "\n" * n + "int b;\n"),
    # In C#, thousands of $ before a string; and a raw string opened by thousands of quotes, holding runs of one fewer.
    "dollars.cs": (8500, lambda n: "var s = " + "$" * n + '"{a}";\n'),
    # Rust test type aliases left open after a , in their generics.
    "open-aliases.rs": (480, lambda n: "#[cfg(test)]\ntype A<T,\n" * n),
    "quote-runs.cs": (300000, lambda n: "var s = " + '"' * n + "\n" + ('"' * (n - 1) + "x") * 4 + "\n" + '"' * n +
                      ";\n"),
    # Rust's test modules in files of their own, of a repo's files, each sized so that the steps named in brackets,
    # made to grow with the square, fail it on both Pythons: thousands of declarations in one file (the tracked files,
    # or the readings found tests, kept in a list); crate roots no manifest names, each declaring one (the files a
    # declaration could bring in kept in a list; the files no reading reaches searched from the start); a chain of
    # modules each bringing in the next through #[path] (the readings done kept in a list; tests found by passes); a
    # cycle of them (one read again, which never ends); modules nested thousands deep, a declaration in each (each
    # scope's folder found again per declaration, or by its way up; the cfg from every block open); a file thousands
    # of crates bring in through #[path], at the head of a chain of them (its declaring files carried down); a
    # string never closed, of thousands of \" (read again from each); a cfg of thousands of strings (the attribute
    # joined per string; its words sliced to the end); and declarations in blocks thousands deep (the declarations,
    # the brackets open or the scopes copied per block).
    "mod-lines": (2400, lambda n: rust_files(["src/lib.rs"], n), "modules"),
    "crate-roots": (3000, lambda n: dict([("gen/t%d.rs" % k, "#[cfg(test)]\nmod m%d;\n" % k) for k in range(n)] +
                                        [("gen/m%d.rs" % k, "") for k in range(n)]), "modules"),
    "module-chain": (1600, lambda n: rust_chain(n, n + 1), "modules"),
    "module-cycle": (1000, lambda n: rust_chain(n, 0), "modules"),
    "nested-modules": (500, lambda n: {"src/lib.rs": "".join("mod m%d {\n#[cfg(test)]\nmod t%d;\n" % (k, k)
                                                            for k in range(n)) + "}\n" * n}, "modules"),
    "shared-chain": (2000, lambda n: dict([("c%d/src/lib.rs" % k, "#[cfg(test)]\n#[path = \"../../s/s0.rs\"]\nmod s;\n")
                                          for k in range(n)] + [("s/s%d.rs" % k, "#[path = \"s%d.rs\"]\nmod next;\n"
                                                                 % (k + 1)) for k in range(n)]), "modules"),
    "unclosed-string": (200000, lambda n: {"src/lib.rs": 'mod a;\n"' + '\\"' * n}, "modules"),
    "cfg-strings": (2500, lambda n: {"src/lib.rs": "#[cfg(any(" + 'feature = "x", ' * n + "))]\nmod a;\n",
                                     "src/a.rs": ""}, "modules"),
    "deep-blocks": (6000, lambda n: {"src/lib.rs": "{" * n + "mod a;" * n + "}" * n, "src/a.rs": ""}, "modules"),
    # Comments after a word ending in mod, a line of slashes and a run of /**/, which a reading of a file's comments
    # that could split them many ways split in every one (exponential, on a doc comment's URL); and a manifest's [
    # before thousands of spaces.
    "comment-runs": (20000, lambda n: {"src/lib.rs": ("// dynamodb\n" + "/" * 48 + "\nmodb " + "/**/" * 32 + "\n") * n,
                                      "src/a.rs": ""}, "modules"),
    "manifest-header": (2000000, lambda n: {"Cargo.toml": "[" + " " * n + "\n", "src/lib.rs": "mod a;\n",
                                            "src/a.rs": ""}, "modules"),
    # Where a file may declare a module: lines of globs, each a word holding mod, then /*; mod over and over, in no
    # word; mod, a name and /*, again and again; and lines of // mod x /*. Each was read from every mod to the end.
    "glob-lines": (150000, lambda n: {"src/lib.rs": '    "node_modules/*",\n' * n}, "modules"),
    "mod-words": (300000, lambda n: {"src/lib.rs": "mod" * n}, "modules"),
    "mod-comments": (40000, lambda n: {"src/lib.rs": "mod x /*" * n}, "modules"),
    "mod-comment-names": (40000, lambda n: {"src/lib.rs": "mod /*" * n}, "modules"),
    # Thousands of exported macros in files of their own, each mentioning the one before, the first declaring modules:
    # a chain of forwarders; thousands of definitions nested, each mentioning it: each walked those it's in; and
    # thousands of exported macros that declare modules, past what's looked for one by one, and as many packages
    # that name none: each file was searched for every one's name.
    "forwarder-chain": (1000, lambda n: dict(
        [("src/lib.rs", EXPORTED % ("m0", "pub mod $x;") + "".join("m%d!(u%d);\n" % (k, k) for k in range(n)))] +
        [("src/f%d.rs" % k, EXPORTED % ("m%d" % k, "m%d!($x);" % (k - 1))) for k in range(1, n)]), "modules"),
    "nested-forwarders": (1500, lambda n: {"src/lib.rs": EXPORTED % ("m0", "mod $x;") + "#[macro_export]\n" +
                                           "macro_rules! m { () => { m0!(a); " * n}, "modules"),
    "module-macros": (1000, lambda n: dict(
        [("src/lib.rs", "".join(EXPORTED % ("m%d" % k, "mod $x;") + "m%d!(q%d);\n" % (k, k) for k in range(n)))] +
        [("z%d/Cargo.toml" % k, "[package]\n") for k in range(n)] +
        [("z%d/src/lib.rs" % k, "fn f() { println!(\"{}\", 1); }\n") for k in range(n)]), "modules"),
    # An include! of thousands of strings: they were joined again at each; and thousands of include!s, each of two
    # strings joined, then one built on OUT_DIR: those to join were copied at each.
    "include-strings": (3000, lambda n: {"src/lib.rs": "mod zz;\ninclude!(concat!(" + "\"s\", " * n + "));\n"},
                        "modules"),
    "out-dir-includes": (2000, lambda n: {"src/lib.rs": "mod zz;\n" + "".join(
        "include!(concat!(\"gen\", \"%d.rs\"));\ninclude!(concat!(env!(\"OUT_DIR\"), \"/x%d.rs\"));\n" % (k, k)
        for k in range(n))}, "modules"),
    "mod-line-comments": (10000, lambda n: {"src/lib.rs": "// mod x /*\n" * n}, "modules"),
    # Files thousands of folders deep, with no manifest, and a built include!: the path each file's name ends in,
    # from each of its folders, was taken to look the include up by.
    "deep-built-include": (4000, lambda n: dict([("/".join("d%d" % k for k in range(n)) + "/x%d.rs" % j, "")
                                                for j in range(4)] +
                                               [("/".join("d%d" % k for k in range(n)) + "/lib.rs",
                                                 "include!(concat!(env!(\"X\"), \"/x0.rs\"));\n")]), "modules"),
    # Thousands of built include!s in a file hundreds of folders deep, with no manifest: each looked for its file
    # from every folder above it, and each folder's package was found again; and as many, each from a first folder
    # of its own: each such folder was looked for in every folder above.
    "deep-built-includes": (2000, lambda n: {"/".join(["d"] * (n // 10)) + "/lib.rs": "".join(
        "include!(concat!(env!(\"CARGO_MANIFEST_DIR\"), \"/src/f%d.rs\"));\n" % k for k in range(n))}, "modules"),
    "deep-distinct-firsts": (1000, lambda n: {"/".join(["d"] * (n // 10)) + "/lib.rs": "".join(
        "include!(concat!(env!(\"CARGO_MANIFEST_DIR\"), \"/f%d/x.rs\"));\n" % k for k in range(n))}, "modules"),
    # And as many, each of one first part that as many folders elsewhere hold: each looked for them again.
    "repeated-firsts": (2000, lambda n: dict([("/".join(["a"] * (n // 10)) + "/lib.rs", "".join(
        "include!(concat!(env!(\"S\"), \"/p/f%d.rs\"));\n" % k for k in range(n)))] +
        [("x%d/p/g.rs" % k, "") for k in range(n)]), "modules"),
    # Thousands of comments that say macro: each read again past those after it; thousands of module macros, each's
    # #[path] of one file's name, each looking through all files so named; thousands of calls in as many packages of
    # one whose call gives its #[path], each of one string, each taking again all files it names; and a chain of
    # thousands of packages, each's crate bringing in the next's file, the first's macros declaring modules.
    "macro-comments": (20000, lambda n: {"src/lib.rs": "/// the macro\n" * n + "mod x;\n"}, "modules"),
    "path-strings": (1000, lambda n: dict([("src/lib.rs", "".join(
        "macro_rules! m%d { () => { #[path = \"d%d/x.rs\"] mod x; } }\n" % (k, k) for k in range(n)))] +
        [("src/d%d/x.rs" % k, "") for k in range(n)]), "modules"),
    "path-calls": (1000, lambda n: dict(
        [("a/Cargo.toml", "[package]\n"), ("a/src/lib.rs", "#[macro_export]\nmacro_rules! import { ($p:literal) => "
          "{ #[path = $p] mod x; } }\n")] + [("p%d/Cargo.toml" % k, "[package]\n") for k in range(n)] +
        [("p%d/src/lib.rs" % k, "a::import!(\"../../x.rs\");\n") for k in range(n)] +
        [("q%d/x.rs" % k, "") for k in range(n)]), "modules"),
    "joined-chain": (1000, lambda n: dict(
        [("p%d/Cargo.toml" % k, "[package]\n") for k in range(n)] +
        [("p%d/src/lib.rs" % k, "#[cfg(test)]\nmod t;\n" if k else
          "macro_rules! m { () => { mod q; } }\n#[path = \"../../p1/src/x.rs\"]\nmod x;\n") for k in range(n)] +
        [("p%d/src/x.rs" % k, "#[path = \"../../p%d/src/x.rs\"]\nmod x;\n" % (k + 1)) for k in range(1, n - 1)] +
        [("p%d/src/t.rs" % k, "") for k in range(1, n)]), "modules"),
    # Round 14's: macro words in comments nested thousands deep, each passed to the end of its own; in a line comment,
    # each passed to the line's end; doc lines that name a macro, the rest of the text copied at each; links to a
    # folder thousands deep, the prefixes of each one's way joined again; and a macro whose call gives its #[path],
    # the strings of its file each ".", each taking all packages again.
    "macro-nested-comments": (8000, lambda n: {"src/lib.rs": "mod a;\n/* " + "macro /* " * n + " */" * (n + 1) + "\n"},
                              "modules"),
    "macro-line-comment": (10000, lambda n: {"src/lib.rs": "mod a;\n// " + "macro // " * n + "\n"}, "modules"),
    "macro-prose": (10000, lambda n: {"src/lib.rs": "mod a;\n" + "/// a macro that the docs name\n" * n}, "modules"),
    "deep-links": (400, lambda n: ({"src/lib.rs": "mod a;\n", "src/a.rs": "", "src/" + "d/" * n + "f.rs": ""},
                                   dict(("links/l%d" % k, "../src/" + "d/" * n) for k in range(1500))), "modules"),
    "dot-paths": (1000, lambda n: dict([("p%d/Cargo.toml" % k, "[package]\n") for k in range(n)] +
        [("p%d/src/lib.rs" % k, "#[cfg(test)]\nmod tests;\n") for k in range(n)] + [("p%d/src/tests.rs" % k, "")
                                                                                   for k in range(n)] +
        [("m.rs", "macro_rules! m { ($p:literal) => { #[path = $p] mod x; } }\nm!(\"x.rs\");\n"
                  "const S: [&str; %d] = [%s];\n" % (n, ", ".join(['"."'] * n)))]), "modules"),
    # Thousands of macro_rules! opened, each inside the last: each looked for the scope it's in below all the others.
    "nested-macro-rules": (2000, lambda n: {"src/lib.rs": "mod zz;\n" + "macro_rules! m {" * n}, "modules"),
    # Files no reading reaches, each read in a round of its own, as s_k reaches r_k as a mod.rs, whose module reading
    # alone could bring in s_k+1: those ready were found again from every file left, each round.
    "unreached-rounds": (1000, lambda n: dict([("src/lib.rs", "pub fn f() {}\n"), ("src/b0.rs", "pub mod s;\n"),
                                               ("src/b0/s.rs", "#[path = \"r0.rs\"]\nmod x;\n")] +
                                              [("src/b0/r%d.rs" % k, "mod s;\n") for k in range(n)] +
                                              [("src/b0/r%d/s.rs" % k, "#[path = \"../r%d.rs\"]\nmod x;\n" % (k + 1))
                                               for k in range(n)]), "modules"),
    # A JavaScript name and thousands of spaces after it, which a name given a value, or a type, split every way
    # around the ! or ? that may follow it.
    "name-then-spaces.js": (75000, lambda n: "function f() {\n  return 1;\n}\nconst name" + " " * n +
                            "\nconst b = 2;\n"),
    # A run of thousands of # in Swift, which no quote follows, read for a raw string from each #; and after a name.
    "hashes.swift": (500000, lambda n: "func f() {\n    return\n}\nlet s = " + "#" * n + "\n"),
    "glued-hashes.swift": (500000, lambda n: "func f() {\n    return\n}\nlet s = x" + "#" * n + "\n"),
    # A commit's subject that says fix, or a line of its body fixes, then thousands of spaces, read for the issue it
    # may close by a split of the spaces around the : that may follow, in every way.
    "fix-then-spaces": (70000, lambda n: "fix" + " " * n + "x", "message"),
    "fixes-then-spaces": (150000, lambda n: "a change\n\nfixes" + " " * n + "x", "message"),
    # JavaScript's other definitions split around an optional part, as they read thousands of spaces: after function,
    # where a * may come; before a name, and after a modifier, where a * may come before it; after a wrapped function's
    # keyword; and before an object's { on a line of a key and its ? and :. And a long word inside a function's return
    # type, whose last word was looked for from each of its characters.
    "function-then-spaces.js": (57000, lambda n: "function f() {\n  return 1;\n}\nfunction" + " " * n + "(\n"),
    "spaces-then-name.js": (17000, lambda n: "function f() {\n  return 1;\n}\n" + " " * n + "x\n"),
    "modifier-then-spaces.ts": (28000, lambda n: "class A {\n  static" + " " * n + "x\n}\n"),
    "wrapped-then-spaces.js": (100000, lambda n: "const a = memo(function" + " " * n + ")\n"),
    "key-then-spaces.js": (36000, lambda n: "x" + " " * n + "y {\n  a: () => 1,\n}\n"),
    "type-word.ts": (40000, lambda n: "function f(): {\n  " + "a" * n + ";\n} {\n}\n"),
    # A line of thousands of / and [ in JavaScript, each / read for a regular expression to the end of the class its [
    # opens: none closed, all closed by one ] at the end, and then text after it.
    "regex-classes.js": (4000, lambda n: "x = " + "/[" * n + "\n"),
    "regex-classes-closed.js": (4000, lambda n: "x = " + "/[" * n + "]\n"),
    "regex-class-then-text.js": (4000, lambda n: "x = " + "/[" * n + "]" + "a" * (2 * n) + "\n"),
    # Thousands of spaces in a C++ conversion operator's name, before which its ( was looked for from each; and around
    # the & that may come after PHP's function.
    "operator-then-spaces.cpp": (17000, lambda n: "int f() {\n}\nbool operator x" + " " * n + "y\n"),
    "function-amp-spaces.php": (60000, lambda n: "<?php\nfunction" + " " * n + "&" + " " * n + "\n"),
    # A line of Ruby of thousands of operators, each read for a def before it from the line's start; of thousands of
    # % and of ?, each read for the word before it in a copy of all the line before it.
    "operators.rb": (9000, lambda n: "x = " + "a + " * n + "\n"),
    "percents.rb": (4000, lambda n: "x = " + "a % " * n + "\n"),
    "questions.rb": (6500, lambda n: "x = " + "?" * n + "\n"),
    # Thousands of spaces in a JavaScript template's hole before a /, each a piece of the line's code, which was joined
    # again and stripped at each piece read back; thousands of = after a definition's name, before each of which the
    # line was copied for a ); and a commit's subject of thousands of tags, the rest of it copied after each.
    "hole-spaces.js": (8000, lambda n: "x = `${" + " " * n + "/a/}`\n"),
    "equals.kt": (17500, lambda n: "fun f" + " =" * n + "\n"),
    "tags": (16000, lambda n: "[a]" * n, "message"),
    # A PHP heredoc's name of thousands of letters past ASCII, bare or quoted, that doesn't end its line, and a git
    # conflict marker's: each letter could be read two ways, a time that doubled with each.
    "heredoc-name.php": (150000, lambda n: "<?php\n$x = <<<" + "\u00e9" * n + ";\n"),
    "nowdoc-name.php": (30000, lambda n: "<?php\n$x = <<<'" + "\u4e2d" * n + " x\n"),
    "conflict-marker.php": (150000, lambda n: "<?php\n<<<<<<< " + "\u4e2d" * n + " (x)\n"),
    # A JavaScript line of thousands of \/ after a division, each / read for a regular expression to the line's end:
    # alone, in a template's hole and after a regular expression.
    "escaped-slashes.js": (5000, lambda n: "x = y / " + "\\/" * n + "\n"),
    "escaped-slashes-hole.js": (4000, lambda n: "x = `${y / " + "\\/" * n + "}`\n"),
    "escaped-slashes-after.js": (5000, lambda n: "if (x) /a/ / " + "\\/" * n + "\n"),
    # A JavaScript object opened at the end of a line of thousands of characters, then thousands of lines in it: of keys
    # given functions, of if (x) {}, of keys given values, each of which read its line again for what opened it.
    "object-keys.js": (20000, lambda n: "x = " + "a" * (n // 2) + " + {\n" + "  k: function () {},\n" * (n // 40) +
                       "}\n"),
    "object-ifs.js": (30000, lambda n: "x = " + "a" * (n // 2) + " + {\n" + "  if(x){}\n" * (n // 40) + "}\n"),
    "object-values.js": (35000, lambda n: "x = " + "a" * (n // 2) + " + {\n" + "  k: 1,\n" * (n // 40) + "}\n"),
    # Lines of the C family that can be split in every way between a template's <...>, annotations, modifiers and a
    # type's words: thousands of > after template <, of [a] or [], of > and ?, with no ( or before one.
    "template-words.cpp": (70000, lambda n: "template<" + "a> " * n + "\n"),
    "template-types.cpp": (24000, lambda n: "template <typename T> " + "A<B<C>> " * n + "\n"),
    "template-marks.c": (100000, lambda n: "template <" + "?>" * n + "\n"),
    "template-marks.java": (100000, lambda n: "template <" + "?>" * n + "\n"),
    "attributes.cs": (50000, lambda n: "[a] " * n + "\n"),
    "brackets.c": (100000, lambda n: "[]" * n + "\n"),
    "brackets-after-quote.cs": (100000, lambda n: "'" + "[]" * n + "\n"),
    "template-then-if.cpp": (550, lambda n: "template<" + "a> " * n + "if (\n"),
    "attributes-then-call.cs": (480, lambda n: "[a] " * n + "= f(\n"),
    "modifiers-then-call.java": (1800, lambda n: "public " * n + "= f(\n"),
    "brackets-then-call.c": (7000, lambda n: "[]" * n + " = f(\n"),
    # A Rust file's # before thousands of spaces, line ends or comments, read for an attribute's #[ or #![ by a split of
    # them around the ! that may come, in every way.
    "attribute-spaces": (130000, lambda n: {"src/lib.rs": "mod a;\n#" + " " * n, "src/a.rs": ""}, "modules"),
    "attribute-lines": (130000, lambda n: {"src/lib.rs": "mod a;\n#" + "\n" * n, "src/a.rs": ""}, "modules"),
    "attribute-comments": (5500, lambda n: {"src/lib.rs": "mod a;\n#" + "/**/ " * n, "src/a.rs": ""}, "modules"),
    # A subject of thousands of fix-, a body of thousands of closes- or fixes., each read for an issue's org/repo#12 to
    # the run's end; and a revert's body of thousands of lines of spaces, each read from every line's start before it.
    "fix-dashes": (5500, lambda n: "fix-" * n, "message"),
    "closes-dashes": (6300, lambda n: "a change\n\n" + "closes-" * n, "message"),
    "fixes-dots": (6600, lambda n: "a change\n\n" + "fixes." * n, "message"),
    "revert-spaces": (170000, lambda n: "Revert \"a\"\n\n" + " \n" * n + "x", "message"),
    # Thousands of PHP heredocs opened, none closed by any line, each looked for its closing line.
    "unclosed-heredocs.php": (1000, lambda n: "<?php\n" + "$x = <<<A\n" * n),
}


EXPORTED = "#[macro_export]\nmacro_rules! %s { ($x:ident) => { %s } }\n"


def rust_files(declaring, n):
    """Rust files, each of those declaring bringing in n test modules of its own."""
    files = {}
    for path in declaring:
        files[path] = "".join("#[cfg(test)]\nmod m%d;\n" % k for k in range(n))
        files.update((posixpath.join(posixpath.dirname(path), "m%d.rs" % k), "") for k in range(n))
    return files


def rust_chain(n, last):
    """n Rust files, the first a test module, each bringing in the next through #[path]; the last the one named."""
    files = dict(("src/k%d.rs" % k, "#[path = \"k%d.rs\"]\nmod next;\n" % (k + 1 if k < n - 1 else last))
                 for k in range(n))
    files["src/lib.rs"] = "#[cfg(test)]\n#[path = \"k0.rs\"]\nmod k0;\n"
    return files
SCALE, RATIO, LIMIT, TIMEOUT = 8, 24, 5, 60
TIME = """
import gc, sys, time
import measure
from test_robustness import GROWING, LIMIT, SCALE
name = sys.argv[1]
n, make = GROWING[name][:2]
step = GROWING[name][2] if len(GROWING[name]) > 2 else None
if step == "modules":  # Of {path: text}, as if git tracked them all, or that and links.
    import scoping
    read = lambda made: scoping.rust_test_modules(
        sorted(made[0] if isinstance(made, tuple) else made),
        lambda paths: dict((p, (made[0] if isinstance(made, tuple) else made)[p]) for p in paths),
        made[1] if isinstance(made, tuple) else None)
elif step == "message":
    import heatmap
    def read(text):
        subject, _, body = text.partition("\\n")
        commits = [("0" * 40, 0, subject, [("a.py", None, 1, 0)], "A <a@example.com>", body, [])]
        heatmap.fix_summary(commits, heatmap.fix_trace(commits, commits, False), 0.0)
elif step:
    read = (lambda found: lambda text: found(text.split("\\n")))(getattr(measure, step))
else:
    read = lambda text: measure.functions(name, text, [])
texts = make(n), make(SCALE * n)
clock = time.perf_counter if sys.platform == "win32" else time.process_time
def timed(text):
    gc.collect()
    gc.disable()
    start = clock()
    read(text)
    took = clock() - start
    gc.enable()
    if took > LIMIT:  # Too slow already.
        print("%.3f %.3f" % (took, took))
        sys.exit()
    return took
runs = [(timed(texts[0]), timed(texts[1])) for _ in range(3)]
print("%.3f %.3f" % (min(small for small, _ in runs), min(large for _, large in runs)))
"""


class Growing(unittest.TestCase):

    def test_files_of_many_definitions(self):
        code = "import sys; sys.path[:0] = [%r, %r]\n" % (support.SCRIPTS, support.HERE) + TIME
        for name in sorted(GROWING):
            with self.subTest(case=name):
                for _ in range(2):  # Once more if it seems to grow too fast.
                    try:
                        result = support.run_python(code, name, timeout=TIMEOUT)
                    except subprocess.TimeoutExpired:
                        self.fail("%s took over %d seconds" % (name, TIMEOUT))
                    self.assertEqual(result.code, 0, result)
                    small, large = (float(t) for t in result.out.split())
                    if large < LIMIT and large < RATIO * small:
                        break
                self.assertLess(large, LIMIT, name)
                self.assertLess(large, RATIO * small, "%s: %.3f seconds at its size, %.3f at %d times it" % (
                    name, small, large, SCALE))


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


# A script's main under the guard: it prints a line, which waits in the output's buffer, and then ends as given.
GUARDED = """
import errno, os, sys
sys.path.insert(0, os.environ["REFACTOR_PASS_SCRIPTS"])
import scoping
def main():
    print("a line")
    {end}
scoping.guard(main)
"""
# A script run as from the command line.
SCRIPT = """
import os, runpy, sys
sys.argv = [os.path.join(os.environ["REFACTOR_PASS_SCRIPTS"], sys.argv[1])] + sys.argv[2:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""
BUG = (r"^-c: stopped on a bug in the script itself, not a problem with the repo or the command: %s "
       r"\(\S+, line \d+, in \w+\)\.\n$")


# A pipe whose reader has gone, as Windows tells it before Python 3.14: a write fails with EINVAL, not EPIPE, and
# one too big for the 8 KiB buffer, its lines ending in \r\n, is lost with it, so a flush after it succeeds.
# From Python 3.12 argparse ignores a failed write of the help, so on 3.13 the script ends as if all were well,
# as it did on Linux too; 3.14's 128 KiB buffer keeps a help whole, so a flush of it fails. Once the script
# points its output at the null device, as it does when it sees the reader gone, writes go through.
GONE_ON_WINDOWS = """
import errno, io, os, runpy, sys
class Gone(io.RawIOBase):
    reader_gone = True
    def __init__(self):
        super().__init__()
        self.fd = os.dup(1)
    def writable(self):
        return True
    def fileno(self):
        return self.fd
    def write(self, data):
        if Gone.reader_gone:
            raise OSError(errno.EINVAL, "Invalid argument")
        return len(data)
dup2 = os.dup2
def to_devnull(fd, fd2, *args):
    Gone.reader_gone = False
    return dup2(fd, fd2, *args)
os.dup2 = to_devnull
sys.stdout = io.TextIOWrapper(io.BufferedWriter(Gone(), buffer_size=8192), encoding="utf-8", newline="\\r\\n")
sys.argv = [os.path.join(os.environ["REFACTOR_PASS_SCRIPTS"], sys.argv[1])] + sys.argv[2:]
runpy.run_path(sys.argv[0], run_name="__main__")
"""


class LastLineOfDefence(unittest.TestCase):
    """An exception a script doesn't foresee ends it with one plain line that says it's a bug in the script,
    and where, not a traceback; and a reader that stops reading, as head does, isn't one."""

    @classmethod
    def setUpClass(cls):
        repo = support.Repo("defence")
        repo.commit("2026-01-01", "Start", {"a.py": "def f():\n    return 1\n"})
        repo.commit("2026-01-02", "Return two", {"a.py": "def f():\n    return 2\n"})
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

    def gone(self, script, *args):
        """What a script (or, for -c, Python code) writes to stderr, and its exit code, when the reader of its
        output is gone before it starts: its output is a pipe whose reading end is already closed, so no write
        can get in first."""
        read, write = os.pipe()
        os.close(read)
        try:
            process = subprocess.Popen([sys.executable, script if script == "-c" else
                                        os.path.join(support.SCRIPTS, script)] + list(args), stdout=write,
                                       stderr=subprocess.PIPE, env=support.environment(
                                           REFACTOR_PASS_SCRIPTS=support.SCRIPTS))
        finally:
            os.close(write)
        # Read what it writes to stderr and wait: communicate() would start a thread for it.
        err = support._text(process.stderr.read())  # As the suite reads output: Windows ends its lines \r\n.
        process.stderr.close()
        return err, process.wait(timeout=60)

    def test_a_reader_that_stops_reading(self):
        for script in ("heatmap.py", "measure.py"):
            with self.subTest(script=script):
                self.assertEqual(self.gone(script, "-C", self.repo)[0], "")

    def test_a_reader_gone_before_the_help(self):
        for script in ("heatmap.py", "measure.py", "check_page.py"):
            with self.subTest(script=script):
                self.assertEqual(self.gone(script, "--help"), ("", 1))

    def test_a_reader_gone_as_windows_says_it(self):
        for args in (["heatmap.py", "--help"], ["measure.py", "--help"], ["check_page.py", "--help"],
                     ["heatmap.py", "-C", self.repo]):
            with self.subTest(args=args[:2]):
                result = support.run_python(GONE_ON_WINDOWS, *args)
                self.assertEqual((result.err, result.code), ("", 1))

    def test_an_error_is_reported_though_the_reader_is_gone(self):
        # sys.exit with a message: the message, even where flushing what was printed before it fails.
        self.assertEqual(self.gone("-c", GUARDED.format(end="sys.exit('heatmap.py: couldn\\'t write the page.')")),
                         ("heatmap.py: couldn't write the page.\n", 1))

    def test_a_bug_is_one_line_though_the_reader_is_gone(self):
        err, code = self.gone("-c", GUARDED.format(end="raise RuntimeError('boom')"))
        self.assertEqual(code, 3)
        self.assertRegex(err, BUG % "RuntimeError: boom")

    def test_a_bug_is_one_line_though_the_output_fails_otherwise(self):
        # An output on a full disk: the flush fails with ENOSPC, not as a reader gone, and the line still comes.
        code = GONE_ON_WINDOWS.replace('errno.EINVAL, "Invalid argument"', 'errno.ENOSPC, "No space left"').split(
            "sys.argv =")[0] + \
            GUARDED.format(end="raise RuntimeError('boom')").split("import scoping", 1)[1]
        result = support.run_python("import os, sys\nsys.path.insert(0, os.environ['REFACTOR_PASS_SCRIPTS'])\n"
                                    "import scoping\n" + code)
        self.assertEqual(result.code, 3, result)
        self.assertRegex(result.err, BUG % "RuntimeError: boom")

    def test_a_broken_pipe_of_its_own_is_a_bug(self):
        # Not the output's: a reader of the output that's still there sees the bug.
        result = support.run_python(GUARDED.format(end="raise BrokenPipeError(errno.EPIPE, 'a pipe of its own')"))
        self.assertEqual((result.code, result.out), (3, "a line\n"))
        self.assertRegex(result.err, BUG % r"BrokenPipeError: \[Errno %d\] a pipe of its own" % errno.EPIPE)

    def closed(self, fd, code, *args):
        """Python code run with its output (fd 1) or its errors (fd 2) closed as it starts, as by >&- or 2>&-,
        which leaves Python's stream for it None: what it writes to the other, and its exit code. Windows can't
        start a process so, so there the code closes it and sets the stream None first."""
        options = {}
        if os.name == "nt":
            code = "import os, sys\nos.close(%d)\nsys.%s = None\n%s" % (fd, ("stdout", "stderr")[fd - 1], code)
        else:
            options["preexec_fn"] = lambda: os.close(fd)
        result = subprocess.run([sys.executable, "-c", code] + list(args), capture_output=True, timeout=60,
                                cwd=support.temp_root(), env=support.environment(REFACTOR_PASS_SCRIPTS=support.SCRIPTS),
                                **options)
        return support._text(result.stderr if fd == 1 else result.stdout), result.returncode

    def test_output_closed(self):
        # No output to write to: no traceback, and what the script says on stderr, and how it ends, as with one.
        self.assertEqual(self.closed(1, SCRIPT, "heatmap.py", "-C", self.repo), ("", 0))
        missing = os.path.join(support.new_folder("closed"), "missing.html")
        result = support.run("check_page.py", missing)
        self.assertEqual((result.code, result.out), (1, ""))
        self.assertEqual(self.closed(1, SCRIPT, "check_page.py", missing), (result.err, 1))
        self.assertEqual(self.closed(1, GUARDED.format(end="sys.exit('heatmap.py: no page.')")),
                         ("heatmap.py: no page.\n", 1))
        err, code = self.closed(1, GUARDED.format(end="raise RuntimeError('boom')"))
        self.assertEqual(code, 3)
        self.assertRegex(err, BUG % "RuntimeError: boom")

    def test_errors_closed(self):
        # Nowhere to say what went wrong: the output is what it is with somewhere, with none of the errors in it.
        args = ["-C", self.repo, "-n", "1", "--exclude-commits", "HEAD~1"]  # Outside the window: it warns.
        result = support.run("heatmap.py", *args)
        self.assertEqual(result.code, 0, result)
        self.assertIn("isn't in the window", result.err)
        self.assertEqual(self.closed(2, SCRIPT, "heatmap.py", *args), (result.out, 0))
        missing = os.path.join(support.new_folder("closed"), "missing.html")
        self.assertEqual(self.closed(2, SCRIPT, "check_page.py", missing), ("", 1))
        self.assertEqual(self.closed(2, GUARDED.format(end="raise RuntimeError('boom')")), ("a line\n", 3))

    def test_skill_md_says_what_to_do(self):
        with open(os.path.join(os.path.dirname(support.SCRIPTS), "SKILL.md"), encoding="utf-8") as f:
            text = " ".join(f.read().split())
        self.assertIn("If a script stops on a bug in the script itself, as it says, tell the user what it said, "
                      "and go on without it", text)


if __name__ == "__main__":
    unittest.main()
