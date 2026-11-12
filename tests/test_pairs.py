"""heatmap.py's files that change together: pairs, groups, overlapping groups, their thresholds and dates,
and the tests that change with several production files besides their own.

Each commit in these repos adds a line to every file it changes, one commit a day, so which files changed
together, how often and when is known in advance.
"""

import json
import os
import re
import unittest
from datetime import date, timedelta

try:
    from . import support
except ImportError:
    import support


class Builder(object):
    """Commits that each add a line to the files they name, a day apart from 2026-01-01."""

    def __init__(self, name):
        self.repo = support.Repo(name)
        self.sizes = {}
        self.day = date(2026, 1, 1)
        self.days = []  # The date of each commit, in order.
        self.count = 0

    def change(self, *paths, **options):
        times = options.get("times", 1)
        for _ in range(times):
            files = {}
            for path in paths:
                self.sizes[path] = self.sizes.get(path, 0) + 1
                files[path] = support.lines(self.sizes[path])
            stamp = self.day.strftime("%Y-%m-%d")
            self.repo.commit(stamp, "Change %s" % ", ".join(paths), files)
            self.days.append(stamp)
            self.day += timedelta(days=1)
            self.count += 1
        return self.days[-1]

    def done(self):
        self.repo.done()
        return self.repo.path


def together_rows(out):
    """The rows under "Changed together", as (shared, quieter, degree, last, files, spread, in an area)."""
    rows = []
    section = out.split("Changed together", 1)[1]
    for line in section.splitlines():
        match = re.match(r"\s*(\d+)\s+(\d+)%\s+(\d+)%\s+(\S+)  ( *)(\S.*?)(?: \(each pair ([^)]*)\))?$", line)
        if match:
            rows.append((int(match.group(1)), int(match.group(2)), int(match.group(3)), match.group(4),
                         match.group(6), match.group(7), bool(match.group(5))))
        elif line.startswith("Tests changed together"):
            break
    return rows


class Pairs(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        b = Builder("pairs")
        p = lambda *names: ["src/%s.py" % n for n in names]  # noqa: E731
        b.change(*p("k"), times=25)
        cls.kl_last = b.change(*p("k", "l"), times=5)  # k 30 commits, l 5: degree 5 / 17.5, under 30%.
        b.change(*p("i", "j"), times=4)  # 4 together: under 5 shared.
        b.change(*p("i"))
        b.change(*p("j"))
        cls.abc_last = b.change(*p("a", "b", "c"), times=6)
        cls.def_last = b.change(*p("d", "e", "f"), times=5)
        b.change(*p("d", "e"), times=2)  # d and e: 7 commits each and 7 together; f: 5.
        cls.gh_last = b.change(*p("g", "h"), times=5)
        cls.g_last = b.change(*p("g"), times=3)  # g: 8 commits, its last after the pair's last.
        cls.mno_last = b.change(*p("m", "n", "o"), times=5)
        cls.mnp_last = b.change(*p("m", "n", "p"), times=5)
        cls.qrst_last = b.change(*p("q", "r", "s", "t"), times=5)
        cls.commits = b.count
        cls.repo = b.done()
        cls.result = support.run("heatmap.py", "-C", cls.repo)
        cls.rows = together_rows(cls.result.out)

    def test_runs(self):
        self.assertEqual(self.result.code, 0, self.result)
        self.assertEqual(self.commits, 72)
        self.assertIn("Window: 72 commits", self.result.out)

    def test_groups_in_a_window_short_of_the_first_commit(self):
        # The window's base, whose date the output gives, and groups, which the output lists, together.
        result = support.run("heatmap.py", "-C", self.repo, "-n", "50")
        self.assertEqual(result.code, 0, result)
        self.assertIn("Growth is against ", result.out)
        self.assertIn("src/q.py + src/r.py + src/s.py + src/t.py", result.out)

    def test_pairs_and_groups(self):
        self.assertEqual(self.rows, [
            (6, 100, 100, self.abc_last, "src/a.py + src/b.py + src/c.py", None, False),
            (5, 100, 100, self.qrst_last, "src/q.py + src/r.py + src/s.py + src/t.py", None, False),
            # f's 5 commits are the ones that changed all three: 5 over the average of 7, 7 and 5 is 79%.
            (5, 100, 79, self.def_last, "src/d.py + src/e.py + src/f.py", "5 to 7", False),
            # 5 together over the average of 8 and 5 is 77%.
            (5, 100, 77, self.gh_last, "src/g.py + src/h.py", None, False),
            (5, 100, 60, self.mno_last, "src/m.py + src/n.py + src/o.py", "5 to 10", True),
            (5, 100, 60, self.mnp_last, "src/m.py + src/n.py + src/p.py", "5 to 10", True),
        ])

    def test_headings(self):
        out = self.result.out
        self.assertIn("Changed together (commits of 25 files or fewer, tests aside; files with 5+ commits, 5+ shared, "
                      "degree 30%+):", out)
        self.assertIn("  A row of three or more files is a group: each pair of them qualifies, and the counts are of "
                      "the commits that changed them all.", out)
        self.assertRegex(out, r"(?m)^ shared  quieter  degree       last$")
        self.assertIn("  One area: these 2 groups overlap, each sharing two files or more with another, 4 files in "
                      "all, though no commit need have changed them all:", out)

    def test_a_pairs_last_date_is_when_they_last_changed_together(self):
        self.assertEqual(support.heatmap_rows(self.result.out)["src/g.py"]["last"], self.g_last)
        self.assertNotEqual(self.gh_last, self.g_last)

    def test_page_data(self):
        page = os.path.join(support.new_folder("page"), "p.html")
        support.run("heatmap.py", "-C", self.repo, "--page", page)
        with open(page, encoding="utf-8") as f:
            heat = json.loads(support.block(f.read(), "heatmap"))
        self.assertEqual(heat["pairs"], [{"a": "src/g.py", "b": "src/h.py", "last": self.gh_last, "shared": 5,
                                          "of_quieter": 1.0, "degree": 0.77}])
        groups = dict((" ".join(g["files"]), g) for g in heat["groups"])
        self.assertEqual(groups["src/d.py src/e.py src/f.py"], {
            "files": ["src/d.py", "src/e.py", "src/f.py"], "pairs": [5, 7], "last": self.def_last, "shared": 5,
            "of_quieter": 1.0, "degree": 0.79})
        self.assertEqual(groups["src/m.py src/n.py src/o.py"]["cluster"], 1)
        self.assertEqual(groups["src/m.py src/n.py src/p.py"]["cluster"], 1)
        self.assertNotIn("cluster", groups["src/a.py src/b.py src/c.py"])

    def test_thresholds(self):
        def rows(*args):
            return [r[4] for r in together_rows(support.run("heatmap.py", "-C", self.repo, *args).out)]
        self.assertIn("src/i.py + src/j.py", rows("--min-shared", "4"))
        self.assertIn("src/k.py + src/l.py", rows("--min-degree", "28"))
        # With 6 commits each, f and h are too quiet: d and e are a pair of their own, and g and h nothing.
        fewer = rows("--min-revs", "6")
        self.assertIn("src/d.py + src/e.py", fewer)
        self.assertFalse([r for r in fewer if "src/f.py" in r or "src/h.py" in r])

    def test_max_files(self):
        result = support.run("heatmap.py", "-C", self.repo, "--max-files", "3")
        self.assertIn("  5 of the 72 commits changed more than 3 files and are left out of these; raise --max-files "
                      "to count them.", result.out)
        self.assertNotIn("src/q.py + src/r.py", result.out)
        self.assertIn("src/a.py + src/b.py + src/c.py", result.out)

    def test_pairs_limit(self):
        result = support.run("heatmap.py", "-C", self.repo, "--pairs", "2")
        self.assertEqual([r[4] for r in together_rows(result.out)], ["src/a.py + src/b.py + src/c.py",
                                                                     "src/q.py + src/r.py + src/s.py + src/t.py"])

    def test_none(self):
        result = support.run("heatmap.py", "-C", self.repo, "--min-shared", "50")
        self.assertIn("  none", result.out)
        self.assertNotIn("A row of three or more files is a group", result.out)


class TestsThatChangeWithSeveralFiles(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        b = Builder("tied")
        b.change("tests/test_core.py", "src/core.py", "src/x.py", "src/y.py", times=5)
        b.change("tests/Feature/ShowDashboardTest.php", "app/Http/ShowDashboardController.php", "app/A.php",
                 "app/B.php", times=5)
        # A file named ShowReport.php is the test's own, so its controller is just another file.
        b.change("tests/Feature/ShowReportTest.php", "app/ShowReport.php", "app/Http/ShowReportController.php",
                 "app/C.php", times=5)
        b.change("tests/PlaceOrderTest.php", "app/PlaceOrderHandler.php", "app/D.php", "app/E.php", times=5)
        b.change("tests/SyncTest.php", "app/SyncCommand.php", "app/F.php", "app/G.php", times=5)
        b.change("tests/test_lonely.py", "src/lonely.py", "src/other.py", times=5)  # One file besides its own.
        b.change("src/ABTest.php", "src/x_check.py")
        cls.repo = b.done()
        cls.result = support.run("heatmap.py", "-C", cls.repo)

    def test_tied_tests(self):
        section = self.result.out.split("Tests changed together with several production files besides their own (as "
                                        "above; commits together in brackets). Each is a lead to check: a test that "
                                        "reaches into their private members or internal paths is tied to their "
                                        "internals; a broad test that follows features isn't:\n", 1)[1]
        self.assertEqual(section.splitlines(), [
            "  tests/Feature/ShowDashboardTest.php: 2 files, app/A.php (5), app/B.php (5)",
            "  tests/Feature/ShowReportTest.php: 2 files, app/C.php (5), app/Http/ShowReportController.php (5)",
            "  tests/PlaceOrderTest.php: 2 files, app/D.php (5), app/E.php (5)",
            "  tests/SyncTest.php: 2 files, app/F.php (5), app/G.php (5)",
            "  tests/test_core.py: 2 files, src/x.py (5), src/y.py (5)",
        ])

    def test_tests_are_set_aside(self):
        out = self.result.out
        self.assertIn("Test files: 7 changed in the window, set aside from the table and the pairs.", out)
        rows = support.heatmap_rows(out)
        self.assertFalse([p for p in rows if "test" in p.lower()])
        self.assertIn("src/x_check.py", rows)
        self.assertIn("Set aside as tests, but maybe not: src/ABTest.php (named like a test, in no folder of tests). "
                      "If one isn't a test, --not-test GLOB counts it.", out)
        self.assertIn("Changed together (commits of 25 files or fewer, tests aside;", out)

    def test_test_and_not_test(self):
        result = support.run("heatmap.py", "-C", self.repo, "--test", "src/*_check.py", "--not-test",
                             "src/ABTest.php")
        rows = support.heatmap_rows(result.out)
        self.assertIn("src/ABTest.php", rows)
        self.assertNotIn("src/x_check.py", rows)
        self.assertIn("Test files: 7 changed in the window", result.out)
        self.assertNotIn("Set aside as tests, but maybe not", result.out)

    def test_keep_tests(self):
        result = support.run("heatmap.py", "-C", self.repo, "--keep-tests")
        rows = support.heatmap_rows(result.out)
        self.assertIn("tests/test_core.py", rows)
        self.assertNotIn("Test files:", result.out)
        self.assertNotIn("Tests changed together", result.out)
        self.assertIn("src/core.py + src/x.py + src/y.py + tests/test_core.py", result.out)
        self.assertIn("Changed together (commits of 25 files or fewer; files", result.out)


if __name__ == "__main__":
    unittest.main()
