"""heatmap.py's table, window and scopes, on repos whose every number is worked out by hand.

The "town" repo has ten commits, a day apart, each at noon UTC. Its files: big.py grows in most of them,
shrink.py shrinks, new.py is born in the window, old_name.py is renamed to renamed.py in it, gone.py is
deleted, cold.py never changes after the first commit, and docs/guide.md changes once. The last commit's
author date is weeks before its commit date, as after a rebase: the heatmap goes by commit dates.
"""

import json
import os
import re
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

    def test_growth_names_the_commit_it_is_against(self):
        self.assertIn("Growth is against %s (2026-01-02), just before the window.\n" % self.repo.short(self.marks[2]),
                      self.result.out)
        whole = support.run("heatmap.py", "-C", self.repo.path)
        self.assertIn("Growth is from nothing: the window starts at the first commit.\n", whole.out)
        help_text = " ".join(support.run("heatmap.py", "--help").out.split())
        self.assertIn("Just before the window is one commit: --since's revision, or else the first parent of the "
                      "window's oldest commit. Where the history has merges, other branches' work can sit on either "
                      "side of it, so growth can differ from what the window's own commits added and removed",
                      help_text)

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
        # The window's newer half is its 4 newest commits, from the 7th.
        self.assertIn("src/big.py: 5 of the 8 commits from %s (2026-01-03) to %s (2026-01-10); newer: in the "
                      "window's newer half, from 2026-01-07.\n"
                      "  %s 2026-01-10 newer  Grow both\n  %s 2026-01-08 newer  Change new\n"
                      "  %s 2026-01-06 older  Grow renamed\n  %s 2026-01-04 older  Add new\n"
                      "  %s 2026-01-03 older  Grow big, shrink shrink\n" % (
                          short(self.marks[3]), short(self.marks[10]), short(self.marks[10]), short(self.marks[8]),
                          short(self.marks[6]), short(self.marks[4]), short(self.marks[3])), result.out)
        self.assertIn("src/renamed.py: 2 of the 8 commits", result.out)
        self.assertIn("  %s 2026-01-05 older  Rename\n" % short(self.marks[5]), result.out)
        self.assertNotIn("commits recent", result.out)

    def test_show_a_file_no_commit_or_tree_knows_is_an_error(self):
        result = support.run("heatmap.py", "-C", self.repo.path, "-n", "8", "--show", "src/big.py", "--show",
                             "src/bgi.py")
        self.assertEqual(result.code, 1, result)
        self.assertEqual(result.out, "")
        self.assertEqual(result.err, "heatmap.py: --show src/bgi.py names no file git tracks in town, nor one "
                                     "changed in the window; did you mean src/big.py?\n")
        nothing = support.run("heatmap.py", "-C", self.repo.path, "--show", "zzz/qqq.c")
        self.assertEqual(nothing.err, "heatmap.py: --show zzz/qqq.c names no file git tracks in town, nor one "
                                      "changed in the window.\n")

    def test_show_a_name_a_file_had_before_a_rename(self):
        result = support.run("heatmap.py", "-C", self.repo.path, "-n", "8", "--show", "src/old_name.py")
        self.assertEqual(result.code, 0, result)
        self.assertIn("src/renamed.py, src/old_name.py before it was renamed in the window: 2 of the 8 commits",
                      result.out)

    def test_show_a_file_deleted_in_the_window_or_not_changed_in_it(self):
        result = support.run("heatmap.py", "-C", self.repo.path, "-n", "8", "--show", "src/gone.py", "--show",
                             "src/cold.py")
        self.assertEqual(result.code, 0, result)
        self.assertIn("src/gone.py: 1 of the 8 commits", result.out)
        self.assertIn("  %s 2026-01-07 newer  Remove gone, grow new\n" % self.repo.short(self.marks[7]), result.out)
        self.assertIn("src/cold.py: 0 of the 8 commits", result.out)

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


class Globs(unittest.TestCase):
    """How a glob reads, in a scope, --ignore and --test: * matches across folders, and **/ matches any number
    of folders, none included."""

    @classmethod
    def setUpClass(cls):
        repo = support.Repo("globs")
        files = ["top.py", "app/main.py", "app/sub/deep.py", "app/sub/deeper/x.py", "gen/made.py", "app/gen/made.py",
                 "app/readme.md"]
        repo.commit("2026-01-01", "Start", dict((p, lines(3, "a")) for p in files))
        repo.commit("2026-01-02", "Grow", dict((p, lines(4, "a")) for p in files))
        repo.done()
        cls.repo = repo

    def paths(self, script, *args):
        result = support.run(script, "-C", self.repo.path, *args)
        self.assertEqual(result.code, 0, result)
        if script == "heatmap.py":
            return set(support.heatmap_rows(result.out))
        return set(line.split()[6] for line in result.out.split("\n") if re.match(r"\s*\d+ ", line))

    def test_a_double_star_matches_no_folder_too(self):
        for script in ("heatmap.py", "measure.py"):
            with self.subTest(script=script):
                self.assertEqual(self.paths(script, "app/**/*.py"), {"app/main.py", "app/sub/deep.py",
                                                                     "app/sub/deeper/x.py", "app/gen/made.py"})
                self.assertEqual(self.paths(script, "**/made.py"), {"gen/made.py", "app/gen/made.py"})
                self.assertEqual(self.paths(script, "app/**/deep.py"), {"app/sub/deep.py"})

    def test_a_double_star_is_any_folders_only_at_a_start_or_after_a_slash(self):
        # Elsewhere it's two stars, as fnmatch reads them: app**/main.py needs a / after app.
        match = support.load("scoping").glob_match
        for path, pattern, want in (("appmain.py", "app**/main.py", False), ("app/main.py", "app**/main.py", True),
                                    ("appx/y/main.py", "app**/main.py", True), ("main.py", "**/main.py", True),
                                    ("a/main.py", "a/**/main.py", True), ("a/b/c/main.py", "a/**/main.py", True),
                                    ("amain.py", "a/**/main.py", False), ("xmain.py", "x**/main.py", False)):
            with self.subTest(path=path, pattern=pattern):
                self.assertEqual(match(path, pattern), want)

    def test_a_backslash_on_windows(self):
        # On Windows a glob's \\ is its /, as fnmatch read --ignore's before: the system is passed in, so this runs
        # everywhere; --test and --not-test read it the same way.
        match = support.load("scoping").glob_match
        for path, pattern, case in (("gen/x.py", "gen\\*.py", False), ("Gen/X.py", "gen\\*.py", False),
                                    ("tests/fixtures/a.json", "tests\\fixtures\\*", True),
                                    ("a/b/c.py", "**\\c.py", True)):
            with self.subTest(path=path, pattern=pattern):
                self.assertTrue(match(path, pattern, case, windows=True))
                self.assertFalse(match(path, pattern, case, windows=False))

    @unittest.skipUnless(support.WINDOWS, "a glob's backslash is its / only on Windows")
    def test_a_backslash_in_ignore_and_test_on_windows(self):
        self.assertEqual(self.paths("heatmap.py", "--ignore", "**\\gen\\*"), {
            "top.py", "app/main.py", "app/sub/deep.py", "app/sub/deeper/x.py", "app/readme.md"})
        result = support.run("heatmap.py", "-C", self.repo.path, "--test", "app\\sub\\*")
        self.assertIn("Test files: 2 changed in the window", result.out)

    def test_a_star_matches_across_folders(self):
        # The lenient reading the help gives: app/*.py takes app/sub/deep.py too.
        self.assertEqual(self.paths("heatmap.py", "app/*.py"), {"app/main.py", "app/sub/deep.py",
                                                                "app/sub/deeper/x.py", "app/gen/made.py"})

    def test_ignore_and_test_globs_read_the_same_way(self):
        self.assertEqual(self.paths("heatmap.py", "--ignore", "**/gen/*"), {
            "top.py", "app/main.py", "app/sub/deep.py", "app/sub/deeper/x.py", "app/readme.md"})
        result = support.run("heatmap.py", "-C", self.repo.path, "--test", "**/top.py")
        self.assertNotIn("top.py", support.heatmap_rows(result.out))
        self.assertIn("Test files: 1 changed in the window", result.out)

    def test_a_range_written_backwards_matches_nothing(self):
        # As fnmatch reads one since Python 3.9; before, it failed.
        result = support.run("heatmap.py", "-C", self.repo.path, "--ignore", "[z-a]", "app/[z-a]*.py")
        self.assertEqual(result.code, 1, result)
        self.assertIn("the scope app/[z-a]*.py matches no file git tracks in globs", result.err)
        self.assertEqual(self.paths("measure.py", "--ignore", "[z-a]*", "app/*.md"), {"app/readme.md"})

    def test_the_help_says_how_a_glob_reads(self):
        for script in ("heatmap.py", "measure.py"):
            with self.subTest(script=script):
                text = " ".join(support.run(script, "--help").out.split())
                self.assertIn("In a glob, * matches across folders too, so 'app/*.py' takes app/sub/deep.py; and "
                              "**/ matches any number of folders, none included, so 'app/**/*.py' takes "
                              "app/main.py too.", text)


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


def build_settings():
    """A repo whose history each of git's settings below would read differently: a.py added in the root
    commit and changed twice, with a subject past ASCII; a change that git's own diff counts as 3 lines added
    and 4 removed, and its patience diff as 4 and 5; two files renamed and changed in one commit, which a
    rename limit of 1 leaves as two removed and two added; a commit signed with a signature that's no good,
    made by hand, since fast-import can't sign on every git; and one after it, so that what git prints on
    checking the signature comes between two commits; h.txt, whose change git counts as 3 lines added and 7
    removed, and as 4 and 8 with diff.context=0, where git cuts the files' common end before it diffs them.
    Then a fix, its message's body past ASCII, and another
    author's revert of it, whose body names it: the fixes trace reads bodies; and --diffs shows the revert's
    change to g.py, whose context holds blank lines."""
    repo = support.Repo("settings")
    tail = lines(50, "a line of the tail")
    repo.commit("2026-01-01", "Start", {"a.py": lines(3, "a"), "b.txt": "{\nx\nx\n}\n}\nz\n", "c.py": lines(4, "c"),
                                        "d.py": lines(4, "d"), "h.txt": lines(6, "h") + "\nh 7\n" + tail})
    repo.commit("2026-01-02", "Grow a, caf\u00e9", {"a.py": lines(5, "a")})
    repo.commit("2026-01-03", "Shuffle b", {"b.txt": "z\n}\n{\n}\n{\n", "a.py": lines(6, "a"),
                                            "h.txt": "\n" * 4 + tail})
    repo.commit("2026-01-04", "Move c and d", {"e.py": lines(5, "c"), "f.py": lines(5, "d")},
                rename={"c.py": "e.py", "d.py": "f.py"})
    last = repo.commit("2026-01-05", "Signed", {"e.py": lines(6, "c")})
    repo.done()
    commit = support.git(repo.path, "cat-file", "commit", repo.sha(last))
    header, message = commit.split("\n\n", 1)
    signed = header + ("\ngpgsig -----BEGIN PGP SIGNATURE-----\n \n iQEzBAABCAAdFiEE\n -----END PGP SIGNATURE-----"
                       "\n\n") + message
    sha = support.git(repo.path, "hash-object", "-t", "commit", "-w", "--stdin", input=signed.encode()).strip()
    support.git(repo.path, "update-ref", "refs/heads/main", sha)
    repo.commit("2026-01-06", "After", {"f.py": lines(6, "d")}, parent=sha)
    fix = repo.commit("2026-01-07", "Fix the crash in g\n\nThe caf\u00e9's g crashed.\n",
                      {"g.py": "g 1\n\ng 2\ng 3\n\ng 4\n"})
    repo.done()
    repo.commit("2026-01-08", 'Revert "Fix the crash in g"\n\nThis reverts commit %s.\n' % repo.sha(fix),
                {"g.py": "g 1\n\ng 2\ng three\n\ng 4\n"}, author=support.BOB)
    repo.done()
    return repo


def outputs(repo, env=None):
    """The heatmap, --show for each of its files, --diffs, and a window of the revert alone, whose reverted commit
    is read from the repo, as run with env added to the environment: each as its exit code, its output and its
    errors."""
    env = env or {}
    shas = support.git(repo.path, "rev-list", "HEAD").split()  # Newest first: the revert, the fix, ...
    found = [support.run("heatmap.py", "-C", repo.path, env=env),
             support.run("heatmap.py", "-C", repo.path, "--show", "a.py", "--show", "b.txt", "--show", "e.py",
                         "--show", "f.py", "--show", "g.py", "--messages", env=env),
             support.run("heatmap.py", "-C", repo.path, "--show", "g.py", "--diffs", ",".join(shas[:2]), env=env),
             support.run("heatmap.py", "-C", repo.path, "--show", "e.py", "--diffs", shas[4], env=env),
             support.run("heatmap.py", "-C", repo.path, "-n", "1", "--show", "g.py", env=env)]  # The fix read too.
    return [(r.code, r.out, r.err) for r in found]


def user_config(text):
    """A git config file of the user's, holding text."""
    return support.write_text(os.path.join(support.new_folder("home"), "gitconfig"), text)


class GitSettings(unittest.TestCase):
    """What git prints for the heatmap is the same whatever the user's or the repo's config says, and
    whatever git's variables point at."""

    @classmethod
    def setUpClass(cls):
        cls.plain = outputs(build_settings())
        for code, out, err in cls.plain:
            assert code == 0 and not err, (out, err)

    def test_plain(self):
        rows = support.heatmap_rows(self.plain[0][1])
        self.assertEqual(rows["a.py"], dict(commits=3, recent=0, last="2026-01-03", churn=6, rel=1.0, size=6,
                                            growth=6))
        self.assertEqual(rows["b.txt"]["churn"], 3 + 4 + 6)
        self.assertEqual(rows["h.txt"]["churn"], 58 + 3 + 7)
        self.assertEqual((rows["e.py"]["commits"], rows["e.py"]["churn"]), (3, 4 + 1 + 1))
        self.assertEqual((rows["f.py"]["commits"], rows["f.py"]["churn"]), (3, 4 + 1 + 1))
        self.assertIn("Grow a, caf\u00e9", self.plain[1][1])
        self.assertIn("      @@ -1,6 +1,6 @@\n       g 1\n       \n       g 2\n      -g 3\n      +g three\n       \n"
                      "       g 4\n", self.plain[2][1])
        self.assertIn("Move c and d\n      (rename from c.py)\n      @@ -2,3 +2,4 @@ c 1\n", self.plain[3][1])
        self.assertIn("Fixes, a lead and not a verdict: at least 2 of the 8 commits fixed a defect in the project's "
                      "own code, as their messages say: 1 a revert (of a commit that had stood 1 day) and 1 by their "
                      "words.", self.plain[0][1])

    def test_a_signature_check_in_the_repos_config(self):
        repo = build_settings()
        support.git(repo.path, "config", "log.showSignature", "true")
        support.git(repo.path, "config", "gpg.program", "git")  # Prints its usage, as gpg would its verdict.
        self.assertEqual(outputs(repo), self.plain)

    def test_the_root_commits_changes_whatever_log_showroot_says(self):
        found = outputs(build_settings(), {"GIT_CONFIG_GLOBAL": user_config("[log]\n\tshowRoot = false\n")})
        self.assertEqual(support.heatmap_rows(found[0][1])["a.py"], support.heatmap_rows(self.plain[0][1])["a.py"])
        self.assertEqual(found, self.plain)

    def test_a_big_file_threshold(self):
        # Above it git's diff reads a file as binary; at 1 byte, every file.
        found = outputs(build_settings(), {"GIT_CONFIG_GLOBAL": user_config("[core]\n\tbigFileThreshold = 1\n")})
        self.assertEqual(found, self.plain)

    def test_files_attributes_mark_binary_though_text_are_named(self):
        repo = support.Repo("attributes")
        repo.commit("2026-01-01", "Start", {".gitattributes": "*.py -diff\n", "a.py": lines(3), "b.py": lines(3),
                                            "c.txt": lines(3), "d.bin": b"\x00\x01\n"})
        repo.commit("2026-01-02", "Change", {"a.py": lines(4), "b.py": lines(4), "c.txt": lines(4),
                                             "d.bin": b"\x00\x02\n"})
        repo.done()
        result = support.run("heatmap.py", "-C", repo.path)
        self.assertEqual(result.code, 0, result)
        self.assertEqual(set(support.heatmap_rows(result.out)), {".gitattributes", "c.txt"})
        self.assertIn("Git's attributes mark 2 files that changed in the window as binary, though they're text at "
                      "HEAD, so they're left out: a.py and b.py.\n", result.out)
        # The user's attributes, as the repo's.
        plain = support.Repo("attributes-of-the-user")
        plain.commit("2026-01-01", "Start", {"a.py": lines(3), "c.txt": lines(3)})
        plain.commit("2026-01-02", "Change", {"a.py": lines(4), "c.txt": lines(4)})
        plain.done()
        home = support.new_folder("home")
        attributes = support.write_text(os.path.join(home, "attributes"), "*.py binary\n")
        mine = support.run("heatmap.py", "-C", plain.path, env={"GIT_CONFIG_GLOBAL": user_config(
            "[core]\n\tattributesFile = %s\n" % attributes.replace("\\", "/"))})
        self.assertIn("Git's attributes mark 1 file that changed in the window as binary, though it's text at HEAD, "
                      "so it's left out: a.py.\n", mine.out)

    @unittest.expectedFailure
    def test_no_setting_or_variable_changes_the_output(self):
        repo = build_settings()
        home = support.new_folder("home")
        order = support.write_text(os.path.join(home, "order"), "f.py\ne.py\nb.txt\na.py\n")
        attributes = support.write_text(os.path.join(home, "attributes"), "*.py diff=conv\n*.txt diff=conv\n")
        settings = {
            "log": ["showSignature = true", "showRoot = false", "decorate = full", "abbrevCommit = true",
                    "date = relative", "follow = true"],
            "gpg": ["program = git"],
            "diff": ["algorithm = patience", "renameLimit = 1", "renames = copies", "noprefix = true",
                     "mnemonicPrefix = true", "srcPrefix = x/", "dstPrefix = y/", "relative = true",
                     "orderFile = " + order.replace("\\", "/"),
                     "external = git hash-object", "indentHeuristic = false", "suppressBlankEmpty = true",
                     "context = 0", "interHunkContext = 20", "colorMoved = zebra"],
            'diff "conv"': ["textconv = git hash-object"],
            "i18n": ["logOutputEncoding = ISO-8859-1"],
            "format": ["pretty = oneline"],
            "color": ["ui = always", "diff = always"],
            "core": ["quotePath = true", "abbrev = 5", "attributesFile = " + attributes.replace("\\", "/"),
                     "bigFileThreshold = 1"],
            "notes": ["displayRef = refs/notes/*"],
        }
        text = "".join("[%s]\n%s" % (name, "".join("\t%s\n" % s for s in values)) for name, values in settings.items())
        support.git(repo.path, "-c", "user.name=Ann", "-c", "user.email=ann@example.com", "notes", "add", "-m",
                    "a note", "HEAD~2")
        with open(os.path.join(repo.path, ".git", "config"), "a", encoding="utf-8") as f:
            f.write("[log]\n\tshowRoot = false\n[diff]\n\talgorithm = histogram\n")
        other = support.Repo("other")
        other.commit("2026-02-01", "Elsewhere", {"z.py": lines(9, "z")})
        other.done()
        variables = {"GIT_CONFIG_GLOBAL": user_config(text), "GIT_DIR": os.path.join(other.path, ".git"),
                     "GIT_WORK_TREE": other.path, "GIT_INDEX_FILE": os.path.join(home, "no-index"),
                     "GIT_EXTERNAL_DIFF": "git hash-object", "GIT_CONFIG_COUNT": "1",
                     "GIT_CONFIG_KEY_0": "log.showRoot", "GIT_CONFIG_VALUE_0": "false"}
        self.assertEqual(outputs(repo, variables), self.plain)
        plain = support.run("measure.py", "-C", build_settings().path)
        hostile = support.run("measure.py", "-C", repo.path, env=variables)
        self.assertEqual((hostile.code, hostile.out, hostile.err), (plain.code, plain.out, plain.err))

    def test_a_subject_or_author_holding_any_character(self):
        repo = support.Repo("odd")
        repo.commit("2026-01-01", "Start", {"a.py": lines(3, "a")})
        repo.commit("2026-01-02", "Tidy up", {"a.py": lines(4, "a")}, author="Odd\x1fName <odd@example.com>")
        repo.commit("2026-01-03", "odd\x1esubject\x1fhere", {"a.py": lines(5, "a")})
        repo.commit("2026-01-04", "red \x1b[31malert\x7f", {"a.py": lines(6, "a")})
        repo.done()
        result = support.run("heatmap.py", "-C", repo.path, "--show", "a.py")
        self.assertEqual(result.code, 0, result)
        # A control character is written as its escape, so a subject can't drive the terminal.
        shown = [re.sub(r"^  \S+ \S+ (?:newer|older)  ", "", line) for line in result.out.split("\n")[1:]
                 if line.strip()]
        self.assertEqual(shown, ["red \\x1b[31malert\\x7f", "odd\\x1esubject\\x1fhere", "Tidy up", "Start"])


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
