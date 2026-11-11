"""heatmap.py's table, window and scopes, on repos whose every number is worked out by hand.

The "town" repo has ten commits, a day apart, each at noon UTC. Its files: big.py grows in most of them,
shrink.py shrinks, new.py is born in the window, old_name.py is renamed to renamed.py in it, gone.py is
deleted, cold.py never changes after the first commit, and docs/guide.md changes once. The last commit's
author date is weeks before its commit date, as after a rebase: the heatmap goes by commit dates.
"""

import json
import os
import unittest

try:
    from . import support
except ImportError:
    import support

lines = support.lines


def numbered(first, last, word):
    return "".join("%s %d\n" % (word, n) for n in range(first, last + 1))


def build_town():
    repo = support.Repo("town")
    marks = {}
    marks[1] = repo.commit("2026-01-01", "Start", {
        "src/big.py": lines(10, "big"), "src/shrink.py": lines(30, "s"), "src/old_name.py": lines(5, "o"),
        "src/gone.py": lines(4, "g"), "src/cold.py": lines(50, "c"), "docs/guide.md": lines(3, "guide")})
    marks[2] = repo.commit("2026-01-02", "Grow big", {"src/big.py": lines(12, "big")})
    marks[3] = repo.commit("2026-01-03", "Grow big, shrink shrink", {"src/big.py": lines(15, "big"),
                                                                     "src/shrink.py": lines(20, "s")})
    marks[4] = repo.commit("2026-01-04", "Add new", {"src/new.py": lines(8, "n"), "src/big.py": lines(16, "big")})
    marks[5] = repo.commit("2026-01-05", "Rename", rename={"src/old_name.py": "src/renamed.py"})
    marks[6] = repo.commit("2026-01-06", "Grow renamed", {"src/renamed.py": lines(7, "o"),
                                                          "src/big.py": lines(18, "big")})
    marks[7] = repo.commit("2026-01-07", "Remove gone, grow new", {"src/new.py": lines(9, "n")},
                           delete=["src/gone.py"])
    marks[8] = repo.commit("2026-01-08", "Change new", {"src/new.py": "changed\n" + numbered(2, 9, "n"),
                                                        "src/big.py": lines(19, "big")})
    marks[9] = repo.commit("2026-01-09", "Change shrink", {"src/shrink.py": "x\ny\n" + numbered(3, 20, "s"),
                                                           "docs/guide.md": lines(4, "guide")})
    marks[10] = repo.commit("2026-01-10", "Grow both", {"src/big.py": lines(20, "big"),
                                                        "src/new.py": "changed\n" + numbered(2, 11, "n")},
                            authored="2025-12-01")
    repo.done()
    return repo, marks


def page_heatmap(repo, *args):
    """Run the heatmap with --page, to a page outside the repo, and return its output and the page's
    heatmap block."""
    page = os.path.join(support.new_folder("page"), "page.html")
    result = support.run("heatmap.py", "-C", repo, "--page", page, *args)
    if result.code != 0:
        raise AssertionError(str(result))
    with open(page, encoding="utf-8") as f:
        return result, json.loads(support.block(f.read(), "heatmap"))


class Columns(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.repo, cls.marks = build_town()
        cls.result = support.run("heatmap.py", "-C", cls.repo.path, "-n", "8")
        cls.rows = support.heatmap_rows(cls.result.out)

    def test_runs(self):
        self.assertEqual(self.result.code, 0, self.result)
        self.assertEqual(self.result.err, "")

    def test_each_column(self):
        # Over the last 8 commits (3 to 10), whose newer half is commits 7 to 10, and before the window the
        # files as commit 2 left them.
        self.assertEqual(self.rows["src/big.py"], dict(commits=5, recent=2, last="2026-01-10", churn=8, rel=0.4,
                                                       size=20, growth=8))
        self.assertEqual(self.rows["src/new.py"], dict(commits=4, recent=3, last="2026-01-10", churn=13, rel=1.2,
                                                       size=11, growth=11))
        self.assertEqual(self.rows["src/shrink.py"], dict(commits=2, recent=1, last="2026-01-09", churn=14,
                                                          rel=0.7, size=20, growth=-10))
        self.assertEqual(self.rows["src/renamed.py"], dict(commits=2, recent=0, last="2026-01-06", churn=2,
                                                           rel=0.3, size=7, growth=2))
        self.assertEqual(self.rows["docs/guide.md"], dict(commits=1, recent=1, last="2026-01-09", churn=1,
                                                          rel=0.2, size=4, growth=1))

    def test_deleted_and_unchanged_files_are_not_listed(self):
        self.assertEqual(set(self.rows), {"src/big.py", "src/new.py", "src/shrink.py", "src/renamed.py",
                                          "docs/guide.md"})
        self.assertNotIn("old_name", self.result.out)

    def test_ordered_by_commits_times_size(self):
        # 5 x 20, 4 x 11, 2 x 20, 2 x 7, 1 x 4.
        self.assertEqual(list(self.rows), ["src/big.py", "src/new.py", "src/shrink.py", "src/renamed.py",
                                           "docs/guide.md"])

    def test_window(self):
        out = self.result.out
        self.assertIn("town at %s, scope: (everything)" % self.repo.short(self.marks[10]), out)
        self.assertIn("Window: 8 commits, %s (2026-01-10) back to %s (2026-01-03)\n" % (
            self.repo.short(self.marks[10]), self.repo.short(self.marks[3])), out)
        self.assertIn("Newer half from 2026-01-07. Ordered by commits times size.", out)
        self.assertIn("Test files: none in the scope changed in the window.", out)

    def test_page_data(self):
        _, heat = page_heatmap(self.repo.path, "-n", "8")
        by_path = dict((f["path"], f) for f in heat["files"])
        self.assertEqual(by_path["src/new.py"], {
            "path": "src/new.py", "commits": 4, "recent": 3, "last": "2026-01-10", "churn": 13, "added": 12,
            "removed": 1, "size": 11, "rel": 1.18, "size_before": 0, "growth": 11})
        self.assertEqual([by_path[p]["rel"] for p in ("src/big.py", "src/new.py", "src/shrink.py", "src/renamed.py",
                                                      "docs/guide.md")], [0.4, 1.18, 0.7, 0.29, 0.25])
        self.assertEqual((by_path["src/new.py"]["added"], by_path["src/new.py"]["removed"]), (12, 1))
        self.assertEqual((by_path["src/shrink.py"]["added"], by_path["src/shrink.py"]["removed"]), (2, 12))
        self.assertEqual([by_path[p]["size_before"] for p in ("src/big.py", "src/new.py", "src/shrink.py",
                                                              "src/renamed.py")], [12, 0, 30, 5])
        window = heat["window"]
        self.assertEqual(window["commits"], 8)
        self.assertEqual(window["newest"], {"sha": self.repo.short(self.marks[10]), "date": "2026-01-10",
                                            "subject": "Grow both"})
        self.assertEqual(window["oldest"]["date"], "2026-01-03")
        self.assertEqual(window["newer_half_from"], "2026-01-07")
        self.assertEqual((window["excluded"], window["bots"], window["too_big_for_pairs"], window["since"],
                          window["tests_aside"], window["shallow"]), (0, [], 0, None, 0, False))
        self.assertEqual(heat["head"], self.repo.short(self.marks[10]))
        self.assertEqual(heat["total_files"], 5)
        self.assertEqual(heat["options"], {"top": 25, "pairs": 15, "max_files": 25, "min_shared": 5, "min_revs": 5,
                                           "min_degree": 30})

    def test_an_odd_window_puts_the_middle_commit_in_the_newer_half(self):
        # 7 commits (4 to 10): the newer half is 4 of them, 7 to 10, so new.py's commit 7 is recent.
        result, heat = page_heatmap(self.repo.path, "-n", "7")
        by_path = dict((f["path"], f) for f in heat["files"])
        self.assertEqual((by_path["src/new.py"]["commits"], by_path["src/new.py"]["recent"]), (4, 3))
        self.assertEqual(heat["window"]["newer_half_from"], "2026-01-07")
        self.assertIn("Newer half from 2026-01-07.", result.out)
        # Before the window is commit 3 now.
        self.assertEqual((by_path["src/big.py"]["churn"], by_path["src/big.py"]["growth"],
                          by_path["src/big.py"]["rel"]), (5, 5, 0.25))
        self.assertEqual((by_path["src/shrink.py"]["commits"], by_path["src/shrink.py"]["growth"]), (1, 0))

    def test_the_whole_history(self):
        # With no -n, the window is every commit (fewer than 200); the first has no parent, so every file's
        # size before it is 0.
        rows = support.heatmap_rows(support.run("heatmap.py", "-C", self.repo.path).out)
        # big.py: commits 1, 2, 3, 4, 6, 8 and 10; of the newer half, 6 to 10, three.
        self.assertEqual(rows["src/big.py"], dict(commits=7, recent=3, last="2026-01-10", churn=20, rel=1.0,
                                                  size=20, growth=20))
        self.assertEqual(rows["src/cold.py"]["growth"], 50)

    def test_show(self):
        result = support.run("heatmap.py", "-C", self.repo.path, "-n", "8", "--show", "src/big.py", "--show",
                             "src/renamed.py")
        self.assertEqual(result.code, 0, result)
        short = self.repo.short
        self.assertIn("src/big.py: 5 of the 8 commits from %s (2026-01-03) to %s (2026-01-10)\n"
                      "  %s 2026-01-10 Grow both\n  %s 2026-01-08 Change new\n  %s 2026-01-06 Grow renamed\n"
                      "  %s 2026-01-04 Add new\n  %s 2026-01-03 Grow big, shrink shrink\n" % (
                          short(self.marks[3]), short(self.marks[10]), short(self.marks[10]), short(self.marks[8]),
                          short(self.marks[6]), short(self.marks[4]), short(self.marks[3])), result.out)
        self.assertIn("src/renamed.py: 2 of the 8 commits", result.out)
        self.assertIn("  %s 2026-01-05 Rename\n" % short(self.marks[5]), result.out)
        self.assertNotIn("commits recent", result.out)

    def test_top(self):
        result = support.run("heatmap.py", "-C", self.repo.path, "-n", "8", "--top", "2")
        self.assertEqual(list(support.heatmap_rows(result.out)), ["src/big.py", "src/new.py"])
        self.assertIn("  ... 3 more files changed in the window", result.out)


class Scopes(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.repo, _ = build_town()

    def paths(self, *args, **options):
        result = support.run("heatmap.py", "-n", "8", *args, **options)
        self.assertEqual(result.code, 0, result)
        return set(support.heatmap_rows(result.out))

    def test_a_folder(self):
        src = {"src/big.py", "src/new.py", "src/shrink.py", "src/renamed.py"}
        self.assertEqual(self.paths("-C", self.repo.path, "src"), src)
        self.assertEqual(self.paths("-C", self.repo.path, "./src/"), src)

    def test_a_glob(self):
        self.assertEqual(self.paths("-C", self.repo.path, "src/*n*.py"), {"src/new.py", "src/shrink.py",
                                                                          "src/renamed.py"})

    def test_a_subfolder_named_by_c(self):
        src = os.path.join(self.repo.path, "src")
        self.assertEqual(self.paths("-C", src, "."), {"src/big.py", "src/new.py", "src/shrink.py",
                                                      "src/renamed.py"})
        self.assertEqual(self.paths("-C", src, "big.py"), {"src/big.py"})
        self.assertEqual(self.paths("-C", src, "docs"), {"docs/guide.md"})  # Read from the top as well.

    def test_an_absolute_path(self):
        self.assertEqual(self.paths("-C", self.repo.path, os.path.join(self.repo.path, "docs")), {"docs/guide.md"})

    def test_the_current_directory(self):
        self.assertEqual(self.paths("docs", cwd=self.repo.path), {"docs/guide.md"})

    def test_wrong_case(self):
        result = support.run("heatmap.py", "-C", self.repo.path, "SRC")
        self.assertEqual(result.code, 1, result)
        self.assertIn("heatmap.py: the scope SRC matches no file git tracks in town; did you mean src? Scopes are "
                      "matched with case.", result.err)

    def test_no_match(self):
        result = support.run("heatmap.py", "-C", self.repo.path, "lib")
        self.assertEqual(result.code, 1, result)
        self.assertIn("the scope lib matches no file git tracks in town; its top-level folders are docs, src.",
                      result.err)

    def test_outside_the_repo(self):
        other = support.new_folder("elsewhere")
        result = support.run("heatmap.py", "-C", self.repo.path, other)
        self.assertEqual(result.code, 1, result)
        self.assertIn(support.slashes("the scope %s is outside the repo, %s." % (other, self.repo.path)),
                      support.slashes(result.err))

    def test_measure_reads_scopes_the_same_way(self):
        result = support.run("measure.py", "-C", os.path.join(self.repo.path, "src"), "big.py")
        self.assertIn("town, scope: src/big.py", result.out)
        wrong = support.run("measure.py", "-C", self.repo.path, "SRC")
        self.assertIn("measure.py: the scope SRC matches no file git tracks in town; did you mean src?", wrong.err)


class History(unittest.TestCase):

    def test_merges_are_skipped(self):
        repo = support.Repo("merges")
        start = repo.commit("2026-01-01", "Start", {"a.py": lines(3), "b.py": lines(3)})
        side = repo.commit("2026-01-02", "Side", {"b.py": lines(5)}, branch="side", parent=start)
        repo.commit("2026-01-03", "Main", {"a.py": lines(4)})
        repo.commit("2026-01-04", "Merge side", {"b.py": lines(5)}, merge=side)
        repo.done()
        result = support.run("heatmap.py", "-C", repo.path)
        self.assertIn("Window: 3 commits", result.out)
        rows = support.heatmap_rows(result.out)
        self.assertEqual((rows["b.py"]["commits"], rows["b.py"]["churn"]), (2, 5))
        self.assertEqual(rows["b.py"]["last"], "2026-01-02")

    def test_odd_file_names(self):
        NAIVE = "src/na" + chr(0xEF) + "ve.py"
        # Read from git alone, so no file system needs to hold them: no checkout.
        repo = support.Repo("odd")
        names = ["src/with space.py", NAIVE, "src/-dash.py"]
        if not support.WINDOWS:  # Git for Windows refuses what a Windows name can't hold (core.protectNTFS):
            names += ['src/quote"d.py', "src/back\\slash.py"]  # a backslash, or any of " : < > | ? *.
        repo.commit("2026-01-01", "Start", dict((name, lines(2)) for name in names))
        repo.commit("2026-01-02", "Grow", dict((name, lines(3)) for name in names))
        repo.commit("2026-01-03", "Move", rename={"src/with space.py": "src/still spaced.py"})
        repo.done(checkout=False)
        result = support.run("heatmap.py", "-C", repo.path, "-n", "2")
        self.assertEqual(result.code, 0, result)
        rows = support.heatmap_rows(result.out)
        self.assertEqual(rows["src/still spaced.py"], dict(commits=2, recent=1, last="2026-01-03", churn=1,
                                                           rel=0.3, size=3, growth=1))
        for name in names[1:]:
            with self.subTest(name=name):
                self.assertEqual(rows[name], dict(commits=1, recent=0, last="2026-01-02", churn=1, rel=0.3, size=3,
                                                  growth=1))
        shown = support.run("heatmap.py", "-C", repo.path, "-n", "2", "--show", NAIVE)
        self.assertIn(NAIVE + ": 1 of the 2 commits", shown.out)

    def test_links_and_submodules_are_left_out(self):
        repo = support.Repo("links")
        repo.commit("2026-01-01", "Start", {"src/a.py": lines(3), "src/b.py": lines(3),
                                            "link.py": support.Link("src/a.py"),
                                            "vendor/lib": support.Gitlink("1" * 40)})
        repo.commit("2026-01-02", "Point elsewhere", {"src/a.py": lines(4), "link.py": support.Link("src/b.py"),
                                                      "vendor/lib": support.Gitlink("2" * 40)})
        repo.done(checkout=False)
        result = support.run("heatmap.py", "-C", repo.path)
        self.assertEqual(result.code, 0, result)
        self.assertEqual(set(support.heatmap_rows(result.out)), {"src/a.py", "src/b.py"})

    def test_a_shallow_clone(self):
        town, marks = build_town()
        clone = os.path.join(support.new_folder("shallow"), "town")
        uri = "file://" + ("/" if support.WINDOWS else "") + town.path.replace("\\", "/")
        support.git(support.temp_root(), "clone", "-q", "--depth", "3", uri, clone)
        result = support.run("heatmap.py", "-C", clone)
        self.assertEqual(result.code, 0, result)
        self.assertIn("This is a shallow clone, so its history stops at %s (2026-01-08); that commit looks as if it "
                      "adds every file, so it's left out. `git fetch --unshallow` fetches the rest of the history."
                      % town.short(marks[8]), result.out)
        self.assertIn("Window: 2 commits", result.out)
        rows = support.heatmap_rows(result.out)
        self.assertEqual(rows["src/big.py"], dict(commits=1, recent=1, last="2026-01-10", churn=1, rel=0.1, size=20,
                                                  growth=1))
        self.assertEqual(set(rows), {"src/big.py", "src/new.py", "src/shrink.py", "docs/guide.md"})

    def test_a_shallow_clone_with_nothing_else(self):
        town, marks = build_town()
        clone = os.path.join(support.new_folder("shallow1"), "town")
        uri = "file://" + ("/" if support.WINDOWS else "") + town.path.replace("\\", "/")
        support.git(support.temp_root(), "clone", "-q", "--depth", "1", uri, clone)
        result = support.run("heatmap.py", "-C", clone)
        self.assertEqual(result.code, 0, result)
        self.assertIn("No commits in the window. This is a shallow clone, so its history stops at %s"
                      % town.short(marks[10]), result.out)


class Unusual(unittest.TestCase):

    def test_no_commits(self):
        repo = support.Repo("fresh")
        result = support.run("heatmap.py", "-C", repo.path)
        self.assertEqual(result.code, 1, result)
        self.assertIn("fresh has no commits yet, so there's no history to read.", result.err)
        listed = support.run("heatmap.py", "-C", repo.path, "--checklists")
        self.assertEqual(listed.code, 0, listed)
        self.assertIn("No checklist yet", listed.out)

    def test_a_bare_repo(self):
        path = os.path.join(support.new_folder("bare"), "bare.git")
        support.git(support.temp_root(), "init", "-q", "--bare", path)
        for script in ("heatmap.py", "measure.py"):
            with self.subTest(script=script):
                result = support.run(script, "-C", path)
                self.assertEqual(result.code, 1, result)
                self.assertIn("%s is a bare repo, with no working tree to read; run this in a clone of it." % path,
                              result.err)

    def test_not_a_repo(self):
        path = support.new_folder("plain")
        for script in ("heatmap.py", "measure.py"):
            with self.subTest(script=script):
                result = support.run(script, "-C", path)
                self.assertEqual(result.code, 1, result)
                self.assertIn("Not a git repo: %s" % path, result.err)

    def test_no_such_folder(self):
        path = os.path.join(support.temp_root(), "missing")
        for script in ("heatmap.py", "measure.py"):
            with self.subTest(script=script):
                result = support.run(script, "-C", path)
                self.assertEqual(result.code, 1, result)
                self.assertIn("No such folder: %s" % path, result.err)

    def test_bad_numbers(self):
        repo = support.Repo("numbers")
        repo.commit("2026-01-01", "Start", {"a.py": lines(3)})
        repo.done()
        for args, message in ((["-n", "0"], "argument -n/--commits: must be 1 or more, not 0"),
                              (["-n", "x"], "argument -n/--commits: 'x' isn't a whole number"),
                              (["--top", "-1"], "argument --top: must be 0 or more, not -1"),
                              (["--pairs", "many"], "argument --pairs: 'many' isn't a whole number")):
            with self.subTest(args=args):
                result = support.run("heatmap.py", "-C", repo.path, *args)
                self.assertEqual(result.code, 2, result)
                self.assertIn(message, result.err)
        result = support.run("measure.py", "-C", repo.path, "--top", "-2")
        self.assertEqual(result.code, 2, result)
        self.assertIn("argument --top: must be 0 or more, not -2", result.err)
        result = support.run("heatmap.py", "-C", repo.path, "--top", "0", "--pairs", "0")
        self.assertEqual(result.code, 0, result)


if __name__ == "__main__":
    unittest.main()
