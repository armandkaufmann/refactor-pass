"""measure.py: its percentiles and bands, worked out by hand, and its output on small repos.

The repos are built in a temporary folder, so every number below is known in advance: each function is
written to a set length of code lines.
"""

import os
import re
import unittest

try:
    from . import support
except ImportError:
    import support

from_lines = support.lines


def function(name, length, nested=False):
    """A Python function of exactly length code lines; with nested, two of them are an if and its block."""
    body = ["    x = 1\n"] * (length - 1)
    if nested and length >= 3:
        body[-2:] = ["    if x:\n", "        x = 2\n"]
    return "def %s():\n%s" % (name, "".join(body))


def functions(*specs):
    return "".join(function(*spec) if isinstance(spec, tuple) else function("f%d" % spec, spec) for spec in specs)


class Percentiles(unittest.TestCase):
    """weighted, band and leaning, called directly."""

    def setUp(self):
        self.measure = support.load("measure")

    def test_weighted_percentiles(self):
        # 1 to 20 add up to 210. 70% of it is 147, reached at 17 (1 + ... + 17 = 153); 80% is 168, reached at
        # 18 (171); 90% is 189, reached at 19 (190).
        self.assertEqual(self.measure.weighted(list(range(20, 0, -1))), [17, 18, 19])
        # A thing's own share counts: one of 100 and nine of 1 put every percentile in the 100.
        self.assertEqual(self.measure.weighted([100] + [1] * 9), [100, 100, 100])
        self.assertEqual(self.measure.weighted([]), [0, 0, 0])

    def test_band_is_reached_at_least_as_long_as_the_percentile(self):
        band = self.measure.band
        cuts = [50, 60, 70]
        self.assertEqual(band(49, cuts, "function"), None)
        self.assertEqual(band(50, cuts, "function"), "70th")
        self.assertEqual(band(59, cuts, "function"), "70th")
        self.assertEqual(band(60, cuts, "function"), "80th")
        self.assertEqual(band(70, cuts, "function"), "90th")
        self.assertEqual(band(500, cuts, "function"), "90th")

    def test_floors(self):
        band = self.measure.band
        self.assertEqual(self.measure.REFERENCE, {"file": (220, 440), "function": (45, 75)})
        # Nothing at or below the floor is in a band, however the codebase compares.
        self.assertEqual(band(45, [10, 20, 30], "function"), None)
        self.assertEqual(band(46, [10, 20, 30], "function"), "90th")
        self.assertEqual(band(220, [100, 150, 200], "file"), None)
        self.assertEqual(band(221, [100, 150, 200], "file"), "90th")

    def test_reference_points_when_the_percentiles_lean_on_one(self):
        band = self.measure.band
        self.assertEqual([band(n, None, "function") for n in (45, 46, 75, 76)], [None, ">45", ">45", ">75"])
        self.assertEqual([band(n, None, "file") for n in (220, 221, 440, 441)], [None, ">220", ">220", ">440"])
        self.assertEqual(self.measure.BIG, {"80th", "90th", ">75", ">440"})

    def test_leaning(self):
        leaning = self.measure.leaning
        # 100 of 170 lines, and half as long again as 60: 58%.
        self.assertEqual(leaning([(100, "a"), (60, "b"), (10, "c")], "function"), ("a", 58))
        # Exactly half as long again, and exactly a tenth of the lines, still lean.
        self.assertEqual(leaning([(90, "a"), (60, "b")] + [(50, "x")] * 15, "function"), ("a", 10))
        # Not quite half as long again; not quite a tenth; not past the floor.
        self.assertIsNone(leaning([(89, "a"), (60, "b")], "function"))
        self.assertIsNone(leaning([(90, "a"), (60, "b")] + [(51, "x")] * 15, "function"))
        self.assertIsNone(leaning([(45, "a"), (10, "b")], "function"))
        self.assertIsNone(leaning([(220, "a"), (10, "b")], "file"))
        self.assertEqual(leaning([(221, "a"), (10, "b")], "file"), ("a", 95))
        # A handful of files of one length, or one file alone, lean on none of them.
        self.assertIsNone(leaning([(300, "a"), (300, "b"), (300, "c")], "file"))
        self.assertIsNone(leaning([(900, "a")], "file"))


def table(out):
    """measure's table of files: per path, (lines, band, funcs, longest, long, deepest)."""
    rows = {}
    for line in out.splitlines():
        match = re.match(r"\s*(\d+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)\s+(\S+)  (\S+)", line)
        if match and not line.strip().startswith("lines"):
            rows[match.group(7)] = match.groups()[:6]
    return rows


class Sizes(unittest.TestCase):
    """A repo whose percentiles are worked out by hand, with tests, odd entries and files to leave out."""

    @classmethod
    def setUpClass(cls):
        repo = support.Repo("sizes")
        # Functions of 50, 60, 75 and 80 code lines in a.py (265 in all), and twenty of 10 in b.py (200).
        # Weighted, the functions' 465 lines put 70% (325.5) and 80% (372) in the 75, and 90% (418.5) in the
        # 80: cuts of 75, 75 and 80. The files' are 265, 265 and 265.
        files = {
            "src/a.py": functions(50, 60, 75, ("f80", 80, True)),
            "src/b.py": functions(*[("g%d" % n, 10) for n in range(20)]),
            "src/check_x.py": "x = 1\n" * 5,
            "src/latin.py": b"x = '\xe9'\n",  # Not UTF-8.
            "src/ABTest.php": "<?php\nclass ABTest {}\n",
            "tests/test_a.py": functions(300),
            "docs/spec/rules.md": "one\ntwo\n",
            "docs/spec/more.md": "three\n",
            "README.md": "# Sizes\n\nA repo.\n",
            "scripts/run.sh": "#!/bin/sh\necho one\necho two\n",
            "icon.svg": "<svg>\n</svg>\n" * 400,
            "package-lock.json": "{}\n" * 400,
            "app.min.js": "function a(){}\n" * 400,
            "yarn.lock": "x\n" * 400,
            "data.bin": b"\x00\x01\x02" + b"y\n" * 400,
            "link.py": support.Link("src/a.py"),
            "vendor/lib": support.Gitlink("1" * 40),
        }
        repo.commit("2026-01-05", "Start", files)
        repo.done()
        cls.repo = repo.path
        cls.result = support.run("measure.py", "-C", repo.path)
        cls.rows = table(cls.result.out)

    def test_runs(self):
        self.assertEqual(self.result.code, 0, self.result)

    def test_percentiles_line(self):
        self.assertRegex(self.result.out, r"(?m)^Python\s+4\s+24\s+265\s+265\s+265\s+75\s+75\s+80$")

    def test_bands_and_long_functions(self):
        # a.py: 90th; its 80-line function is in the 90th band and its 75-line one in the 80th, so 2 long; its
        # deepest nesting is the if's block, 1.
        self.assertEqual(self.rows["src/a.py"], ("265", "90th", "4", "80", "2", "1"))
        # b.py is under the floor of 220 lines, so in no band, whatever the percentiles.
        self.assertEqual(self.rows["src/b.py"], ("200", "-", "20", "10", "0", "0"))
        self.assertIn("src/a.py (f80:186)", self.result.out)

    def test_show_lists_first_and_last_lines(self):
        result = support.run("measure.py", "-C", self.repo, "--show", "src/a.py")
        self.assertEqual(result.code, 0, result)
        self.assertIn("src/a.py: Python, 265 code lines, band 90th, 4 functions (Python functions: 70th 75, "
                      "80th 75, 90th 80 lines)", result.out)
        rows = [line.split() for line in result.out.splitlines() if re.match(r"\s*\d+-\d+ ", line)]
        self.assertEqual(rows, [["1-50", "50", "0", "-", "f50"], ["51-110", "60", "0", "-", "f60"],
                                ["111-185", "75", "0", "80th", "f75"], ["186-265", "80", "1", "90th", "f80"]])
        self.assertRegex(result.out, r"(?m)^first-last\s+lines\s+deepest\s+band\s+function$")
        self.assertNotIn("src/b.py", result.out.split("\n\n", 2)[-1])

    def test_show_other_kinds_of_file(self):
        result = support.run("measure.py", "-C", self.repo, "--show", "scripts/run.sh", "--show", "data.bin",
                             "--show", "tests/test_a.py")
        self.assertEqual(result.code, 0, result)
        self.assertIn("scripts/run.sh: 2 code lines; no rule to find functions in this language.", result.out)
        self.assertIn("data.bin: not a text file in the working tree.", result.out)
        # A test is set aside from the percentiles, but --show still lists its functions against them.
        self.assertIn("tests/test_a.py: Python, 300 code lines, band 90th, 1 functions", result.out)

    def test_show_a_file_neither_tracked_nor_in_the_tree_is_an_error(self):
        result = support.run("measure.py", "-C", self.repo, "--show", "src/a.py", "--show", "src/aa.py")
        self.assertEqual(result.code, 1, result)
        self.assertEqual(result.out, "")
        self.assertEqual(result.err, "measure.py: --show src/aa.py names no file git tracks in sizes, nor one in its "
                                     "working tree; did you mean src/a.py?\n")

    def test_tests_are_set_aside(self):
        self.assertIn("Test files: 4 set aside from the percentiles and the table.", self.result.out)
        self.assertNotIn("tests/test_a.py", self.rows)
        self.assertNotIn("src/ABTest.php", self.rows)

    def test_doubtful_tests_are_named(self):
        self.assertIn("Set aside as tests, but maybe not: src/ABTest.php (named like a test, in no folder of "
                      "tests); docs/spec/ (a folder named like tests, but none of its 2 files is). If one isn't "
                      "a test, --not-test GLOB measures it.", self.result.out)

    def test_keep_tests(self):
        result = support.run("measure.py", "-C", self.repo, "--keep-tests")
        rows = table(result.out)
        self.assertEqual(rows["tests/test_a.py"][:4], ("300", "90th", "1", "300"))
        self.assertNotIn("Test files:", result.out)
        # The test's 300-line function is now most of the Python functions' lines: they lean on it.
        self.assertIn("Python functions: tests/test_a.py:1 f300 holds 39% of the lines", result.out)

    def test_test_and_not_test(self):
        result = support.run("measure.py", "-C", self.repo, "--test", "src/check_*.py", "--not-test",
                             "src/ABTest.php")
        rows = table(result.out)
        self.assertNotIn("src/check_x.py", rows)
        self.assertIn("src/ABTest.php", rows)
        self.assertIn("Test files: 4 set aside", result.out)  # check_x.py in, ABTest.php out.
        self.assertNotIn("src/ABTest.php (named like a test", result.out)

    def test_lines_only_languages(self):
        self.assertIn("Lines only, with no rule to find functions: 2 files (.md 1, .sh 1).", self.result.out)
        self.assertEqual(self.rows["scripts/run.sh"], ("2", "-", "-", "-", "-", "-"))
        self.assertIn("scripts/run.sh (lines only)", self.result.out)

    def test_left_out(self):
        # Files never worth a refactor, a symbolic link, a submodule and a binary file.
        for path in ("icon.svg", "package-lock.json", "app.min.js", "yarn.lock", "link.py", "vendor/lib",
                     "data.bin"):
            with self.subTest(path=path):
                self.assertNotIn(path, self.result.out)

    def test_a_file_that_is_not_utf8_is_measured(self):
        self.assertEqual(self.rows["src/latin.py"][:3], ("1", "-", "0"))

    def test_ignore(self):
        result = support.run("measure.py", "-C", self.repo, "--ignore", "src/b.py")
        self.assertNotIn("src/b.py", result.out)
        self.assertRegex(result.out, r"(?m)^Python\s+3\s+4\s")

    def test_top(self):
        result = support.run("measure.py", "-C", self.repo, "--top", "2")
        self.assertEqual(list(table(result.out)), ["src/a.py", "src/b.py"])
        self.assertIn("  ... 4 more files", result.out)

    def test_scope(self):
        result = support.run("measure.py", "-C", self.repo, "src/a.py")
        self.assertEqual(list(table(result.out)), ["src/a.py"])
        self.assertIn("sizes, scope: src/a.py", result.out)

    def test_a_planted_failure_in_the_finder_is_survived(self):
        code = ("import os, sys\nsys.dont_write_bytecode = True\n"
                "sys.path.insert(0, os.environ['REFACTOR_PASS_SCRIPTS'])\n"
                "import measure\nreal = measure.functions\n"
                "def broken(path, text):\n    if path == 'src/b.py':\n        raise IndexError('planted')\n"
                "    return real(path, text)\n"
                "measure.functions = broken\nsys.argv = ['measure.py'] + sys.argv[1:]\nmeasure.main()\n")
        result = support.run_python(code, "-C", self.repo)
        self.assertEqual(result.code, 0, result)
        self.assertIn("Finding the functions failed in 1 file, so it's measured as non-blank lines only, out of "
                      "the percentiles: src/b.py. That's a bug in measure.py, and the file would help fix it.",
                      result.out)
        self.assertEqual(table(result.out)["src/b.py"], ("200", "-", "-", "-", "-", "-"))
        self.assertRegex(result.out, r"(?m)^Python\s+3\s+4\s")  # Out of the percentiles.
        shown = support.run_python(code, "-C", self.repo, "--show", "src/b.py")
        self.assertEqual(shown.code, 0, shown)
        self.assertIn("src/b.py: 200 non-blank lines. Finding its functions failed, so it's measured as lines "
                      "only; that's a bug in measure.py, and this file would help fix it.", shown.out)


class Lopsided(unittest.TestCase):
    """One file and one function far longer than the rest: bands by the reference points."""

    @classmethod
    def setUpClass(cls):
        repo = support.Repo("lopsided")
        # Files of 500, 300, 150 and 50 lines: the 500 holds half of the 1,000 and is over 1.5 times the 300.
        # Functions of 100, 50 and five of 10: the 100 holds 50% of the 200 and is twice the 50.
        repo.commit("2026-01-05", "Start", {
            "src/huge_file.py": "x = 1\n" * 500,
            "src/mid_file.py": "x = 1\n" * 300,
            "src/big.py": functions(("huge", 100), ("mid", 50)),
            "src/small.py": functions(*[("s%d" % n, 10) for n in range(5)]),
        })
        repo.done()
        cls.repo = repo.path
        cls.result = support.run("measure.py", "-C", repo.path)

    def test_notes(self):
        out = " ".join(self.result.out.split())
        self.assertIn("Python files: src/huge_file.py holds 50% of the lines and is half as long again as any "
                      "other, so the percentiles lean on it. These are put in bands by the catalogue's reference "
                      "points instead: >220 is over 220 code lines, worth a closer look; >440 is over 440, big.",
                      out)
        self.assertIn("Python functions: src/big.py:1 huge holds 50% of the lines and is half as long again as any "
                      "other, so the percentiles lean on it. These are put in bands by the catalogue's reference "
                      "points instead: >45 is over 45 code lines, worth a closer look; >75 is over 75, big.", out)

    def test_bands(self):
        rows = table(self.result.out)
        self.assertEqual(rows["src/huge_file.py"][:2], ("500", ">440"))
        self.assertEqual(rows["src/mid_file.py"][:2], ("300", ">220"))
        self.assertEqual(rows["src/big.py"], ("150", "-", "2", "100", "1", "0"))  # Only >75 is long.

    def test_show(self):
        result = support.run("measure.py", "-C", self.repo, "--show", "src/big.py")
        rows = [line.split() for line in result.out.splitlines() if re.match(r"\s*\d+-\d+ ", line)]
        self.assertEqual(rows, [["1-100", "100", "0", ">75", "huge"], ["101-150", "50", "0", ">45", "mid"]])
        self.assertIn("they lean on one function, so bands are by the reference points", result.out)

    def test_equal_files_lean_on_none(self):
        repo = support.Repo("equal")
        repo.commit("2026-01-05", "Start", dict(("src/f%d.py" % n, functions(("f", 300))) for n in range(3)))
        repo.done()
        result = support.run("measure.py", "-C", repo.path)
        self.assertNotIn("lean on it", result.out)
        self.assertEqual(table(result.out)["src/f0.py"], ("300", "90th", "1", "300", "1", "0"))


class Unusual(unittest.TestCase):

    def test_a_repo_with_no_files(self):
        repo = support.Repo("empty")
        result = support.run("measure.py", "-C", repo.path)
        self.assertNotEqual(result.code, 0)
        self.assertIn("empty tracks no files yet, so there's nothing to measure.", result.err)

    @unittest.skipIf(support.WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "a file can't be made unreadable here")
    def test_an_unreadable_file(self):
        repo = support.Repo("unreadable")
        repo.commit("2026-01-05", "Start", {"src/a.py": functions(10), "src/b.py": functions(20)})
        repo.done()
        path = os.path.join(repo.path, "src", "b.py")
        os.chmod(path, 0)
        try:
            if os.access(path, os.R_OK):
                self.skipTest("the file is still readable")
            result = support.run("measure.py", "-C", repo.path)
            shown = support.run("measure.py", "-C", repo.path, "--show", "src/b.py")
        finally:
            os.chmod(path, 0o644)
        self.assertEqual(result.code, 0, result)
        self.assertIn("Couldn't read 1 file, so it's left out: src/b.py.", result.out)
        self.assertNotIn("src/b.py", table(result.out))
        self.assertIn("src/b.py: couldn't read it.", shown.out)


if __name__ == "__main__":
    unittest.main()
