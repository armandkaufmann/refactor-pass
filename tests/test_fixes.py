"""heatmap.py's fixes trace: which commits fixed a defect in the project's own code, as their messages say, and
where they landed.

The "shop" repo has no types in its subjects. Its commits, a day apart: features; fixes said in words (English
and Chinese); fixes that aren't of the project's code, or aren't fixes (documentation, tests or CI only, a
typo, an issue closed); a revert of another author's commit, a revert of the author's own, and a squash merge
whose body carries a revert from its branch. The "typed" repo's subjects carry Conventional Commits types, a
[tag] or a gitmoji. Each repo is built once, and each run of the heatmap read by the tests that need it.
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
BOT = "dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>"


def build_shop():
    repo = support.Repo("shop")
    marks = {}
    marks["start"] = repo.commit("2026-01-01", "Start", {
        "app.py": lines(10, "app"), "util.py": lines(10, "util"), "docs/guide.md": lines(3, "guide"),
        "CHANGES.md": lines(2, "change"), "tests/test_app.py": lines(4, "test"), "package.json": "{}\n",
        ".github/workflows/ci.yml": lines(3, "ci")})
    repo.commit("2026-01-02", "Add the cart", {"app.py": lines(12, "app")})
    marks["crash"] = repo.commit("2026-01-03", "Fix the crash when the cart is empty", {
        "app.py": lines(13, "app"), "tests/test_app.py": lines(6, "test"), "CHANGES.md": lines(3, "change")})
    repo.commit("2026-01-04", "Fix the guide's wrong example", {"docs/guide.md": lines(4, "guide")})
    repo.commit("2026-01-05", "Fix typo in a comment", {"util.py": lines(11, "util")})
    repo.commit("2026-01-06", "Fixed #12 -- Added coupons", {"app.py": lines(14, "app")})
    repo.commit("2026-01-07", "Rename fix_price to fixed_price", {"util.py": lines(12, "util")})
    repo.commit("2026-01-07", "Fix: bump left-pad", {"package.json": "{ }\n"}, author=BOT)
    repo.commit("2026-01-08", "Prevent a negative total", {"util.py": lines(13, "util")})
    repo.commit("2026-01-09", "修复价格计算错误的问题", {"util.py": lines(14, "util")})
    repo.commit("2026-01-10", "Add the prefix and fixture helpers", {"util.py": lines(15, "util")})
    marks["speed"] = repo.commit("2026-01-11", "Speed up totals", {"util.py": lines(16, "util")},
                                 author=support.BOB)
    marks["cache"] = repo.commit("2026-01-12", "Try a cache", {"app.py": lines(15, "app")})
    repo.done()
    marks["revert"] = repo.commit("2026-01-12", 'Revert "Speed up totals"\n\nThis reverts commit %s.\n'
                                  % repo.sha(marks["speed"]), {"util.py": lines(15, "util")})
    repo.commit("2026-01-13", 'Revert "Try a cache"\n\nThis reverts commit %s.\n' % repo.sha(marks["cache"]),
                {"app.py": lines(14, "app")})
    repo.commit("2026-01-14", "Make totals faster (#7)\n\n* Speed up\n\n* Revert it\n\nThis reverts commit %s.\n"
                % repo.sha(marks["start"]), {"util.py": lines(16, "util")})
    repo.commit("2026-01-15", "Fix the flaky cart test", {"tests/test_app.py": lines(7, "test")})
    repo.commit("2026-01-16", "Fix the CI workflow", {".github/workflows/ci.yml": lines(4, "ci")})
    rounding = "Fix the total's rounding\n\nIt rounded half down.\n\nReported-by: Cy <cy@example.com>\n" \
               "Signed-off-by: Ann Dev <ann@example.com>\n"
    marks["rounding"] = repo.commit("2026-01-17", rounding, {"app.py": lines(15, "app") + "total = round(x)\n",
                                                            "package.json": "{\n}\n"})
    repo.done()
    return repo, marks


def fixes_lines(out):
    """The header's lines on the fixes trace."""
    found = out.split("\n")
    start = [i for i, line in enumerate(found) if line.startswith("Fixes, a lead")]
    return found[start[0]:start[0] + 2] if start else []


def fix_rows(out):
    """The table of fixes by file: per file, (fixes, recent, revert, type, words)."""
    rows, table = {}, False
    for line in out.splitlines():
        if re.match(r"\s*fixes\s+recent\s+revert\s+type\s+words\s+file$", line):
            table = True
            continue
        if table:
            match = re.match(r"\s*(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s\s(.+)$", line)
            if not match:
                break
            rows[match.group(6)] = tuple(int(match.group(n)) for n in range(1, 6))
    return rows


def marks_of(out):
    """--show's lines: per subject, its mark or ''."""
    found = {}
    for line in out.splitlines():
        match = re.match(r"  [0-9a-f]{9} \d{4}-\d{2}-\d{2} (?:newer|older)  (.*?)(?:  \[(.*)\])?$", line)
        if match:
            found[match.group(1)] = match.group(2) or ""
    return found


class Shop(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.repo, cls.marks = build_shop()
        cls.page = os.path.join(support.new_folder("shop-page"), "pass.html")
        cls.result = support.run("heatmap.py", "-C", cls.repo.path, "--page", cls.page)
        cls.shown = support.run("heatmap.py", "-C", cls.repo.path, "--messages", *[
            arg for name in ("util.py", "app.py", "docs/guide.md", "tests/test_app.py", ".github/workflows/ci.yml")
            for arg in ("--show", name)])
        assert cls.result.code == 0 and cls.shown.code == 0, (cls.result, cls.shown)

    def test_the_header_says_how_many_at_least_and_how(self):
        # 18 commits counted (the bot's is left out): the crash, the negative total, the Chinese one and the
        # rounding by their words, and the revert of Bob's commit. The fixes of the guide, the cart's test and
        # the CI changed none of the project's code.
        self.assertEqual(fixes_lines(self.result.out), [
            "Fixes, a lead and not a verdict: at least 5 of the 18 commits fixed a defect in the project's own "
            "code, as their messages say: 1 a revert (of a commit that had stood 1 day) and 4 by their words. 1 "
            "more revert, of its author's own commit, withdraws it and isn't counted.",
            "0% of the subjects carry a type, too few to read as labels, so the count is a floor: subjects without "
            "a type typically say so for a third to a half of the fixes, and the rest are among the commits --show "
            "leaves unmarked. 1 more commit closes an issue without saying what kind of change."])

    def test_fixes_by_file(self):
        # util.py: the negative total and the Chinese fix, older, and the revert, in the newer half (the 9
        # newest). app.py: the crash, older, and the rounding. package.json had the rounding too, but it's a
        # dependency file, set aside like documentation and tests.
        self.assertEqual(fix_rows(self.result.out), {"util.py": (3, 1, 1, 0, 2), "app.py": (2, 1, 0, 0, 2)})
        # Neither a floor nor a count of each file's fixes: the commits that say they fixed something, by file.
        self.assertIn("Fixes by file: of each file's commits, those whose messages say they fixed a defect, and how "
                      "many of those were in the newer half; documentation, tests, and CI, build and dependency "
                      "files aside. A lead, not a count of each file's fixes: a fix elsewhere can touch a file in "
                      "passing, and many fixes don't say so. --show FILE --messages gives each commit's message, to "
                      "judge.\n", self.result.out)

    def test_a_commit_of_more_files_than_max_files_adds_to_no_files_number(self):
        # As it adds to no pair: one fix that renames an import in 29 other files isn't a fix of each. The pairs'
        # count is of the files in the table, so files since deleted don't make a commit too big.
        repo = support.Repo("sweep")
        files = dict(("src/m%02d.py" % n, lines(3, "m%d" % n)) for n in range(30))
        gone = dict(("old/g%02d.py" % n, lines(3, "g%d" % n)) for n in range(10))
        repo.commit("2026-01-01", "Start", dict(files, **gone))
        crash = repo.commit("2026-01-02", "Fix the crash on startup", dict((p, lines(4, p)) for p in files))
        repo.commit("2026-01-03", "Fix the wrong total", dict((p, lines(5, p)) for p in list(files)[:20] + list(gone)))
        repo.commit("2026-01-04", "Drop the old modules", delete=list(gone))
        repo.done()
        out = support.run("heatmap.py", "-C", repo.path, "--top", "40").out
        self.assertIn("at least 2 of the 4 commits fixed a defect", out)
        self.assertEqual((len(fix_rows(out)), fix_rows(out)["src/m00.py"]), (20, (1, 1, 0, 0, 1)))
        self.assertIn("dependency files aside, and 1 fix commit of more than 25 files, as the pairs leave it out.",
                      out)
        shown = marks_of(support.run("heatmap.py", "-C", repo.path, "--show", "src/m00.py").out)
        self.assertEqual(shown["Fix the crash on startup"], "fix, words: fix, crash; not counted by file: it changed "
                                                            "30 files")
        wide = support.run("heatmap.py", "-C", repo.path, "--max-files", "40", "--top", "40").out
        self.assertEqual((len(fix_rows(wide)), fix_rows(wide)["src/m00.py"]), (30, (2, 1, 0, 0, 2)))
        self.assertIn("  %s 2026-01-02 older  Fix the crash on startup  [fix, words: fix, crash]\n" % repo.short(crash),
                      support.run("heatmap.py", "-C", repo.path, "--max-files", "40", "--show", "src/m00.py").out)

    def test_the_table_of_files_is_as_it_was(self):
        rows = support.heatmap_rows(self.result.out)
        self.assertEqual((rows["util.py"]["commits"], rows["app.py"]["commits"], rows["package.json"]["commits"]),
                         (9, 7, 2))

    def test_show_marks_each_commit(self):
        marks = marks_of(self.shown.out)
        self.assertEqual(marks['Revert "Speed up totals"'], "fix, revert: reverts %s, 1 day after it"
                         % self.repo.short(self.marks["speed"]))
        self.assertEqual(marks['Revert "Try a cache"'], "not a fix: its author withdraws %s"
                         % self.repo.short(self.marks["cache"]))
        self.assertEqual(marks["Prevent a negative total"], "fix, words: prevent")
        self.assertEqual(marks["修复价格计算错误的问题"], "fix, words: 修复, 问题")
        self.assertEqual(marks["Fix the crash when the cart is empty"], "fix, words: fix, crash")
        self.assertEqual(marks["Fix typo in a comment"], "not a fix: says typo")
        self.assertEqual(marks["Fix the guide's wrong example"], "not a fix: changes only documentation")
        self.assertEqual(marks["Fix the flaky cart test"], "not a fix: changes only tests")
        self.assertEqual(marks["Fix the CI workflow"], "not a fix: changes only CI, build or dependency files")
        # An issue closed, an identifier, words that start like fix, a squash merge's branch revert: nothing.
        for subject in ["Fixed #12 -- Added coupons", "Rename fix_price to fixed_price",
                        "Add the prefix and fixture helpers", "Make totals faster (#7)", "Add the cart", "Start"]:
            self.assertEqual(marks[subject], "", subject)

    def test_show_gives_each_message_and_a_hash_git_show_takes(self):
        out = self.shown.out
        # The message without who signed it; who reported it stays.
        self.assertIn("  %s 2026-01-17 newer  Fix the total's rounding  [fix, words: fix]\n      [+2 -0 in this file; "
                      "1 other file]\n      It rounded half down.\n\n      Reported-by: Cy <cy@example.com>\n  "
                      % self.repo.short(self.marks["rounding"]), out)
        self.assertNotIn("Signed-off-by", out)
        self.assertIn("Fix the crash when the cart is empty  [fix, words: fix, crash]\n      [+1 -0 in this file; 2 "
                      "other files, 1 of them a test]\n", out)
        self.assertIn("Make totals faster (#7)\n      [+1 -0 in this file; no other file]\n      * Speed up\n\n      "
                      "* Revert it\n\n      This reverts commit", out)
        self.assertIn("Add the cart\n      [+2 -0 in this file; no other file]\n  ", out)  # No message past it.
        for sha in re.findall(r"(?m)^  ([0-9a-f]{9}) ", out):
            self.assertEqual(support.git(self.repo.path, "rev-parse", "--verify", "-q", sha + "^{commit}")[:9], sha)

    def test_a_message_is_cut_at_twelve_lines_without_identity_trailers(self):
        heatmap = support.load("heatmap")
        shown = heatmap.message_lines("\n".join("line %d" % n for n in range(1, 31)) + "\n\n\n\nend\n")
        self.assertEqual(shown.split("\n")[-2:], ["      line 11", "      (21 more lines)"])
        self.assertEqual(heatmap.message_lines("  \n\n"), None)
        self.assertEqual(heatmap.message_lines("a\n\n\n\nb\x1b"), "      a\n\n      b\\x1b")
        trailers = "Fixes: 1a2b3c4 (\"x\")\nCloses #12\nBug: 99\nReported-by: Cy <c@y>\nSigned-off-by: A <a@b>\n" \
                   "Co-authored-by: B <b@c>\nreviewed-by: C <c@d>\nCc: D <d@e>\nChange-Id: I12ab\n"
        self.assertEqual(heatmap.message_lines("It broke.\n\n" + trailers).split("\n"), [
            "      It broke.", "", "      Fixes: 1a2b3c4 (\"x\")", "      Closes #12", "      Bug: 99",
            "      Reported-by: Cy <c@y>"])
        self.assertIsNone(heatmap.message_lines("Signed-off-by: A <a@b>\n"))

    def test_messages_goes_with_show(self):
        result = support.run("heatmap.py", "-C", self.repo.path, "--messages")
        self.assertEqual(result.code, 2, result)
        self.assertIn("--messages goes with --show: --show FILE --messages", result.err)
        result = support.run("heatmap.py", "-C", self.repo.path, "--diffs", "a1b2c3d")
        self.assertEqual(result.code, 2, result)
        self.assertIn("--diffs goes with --show: --show FILE --diffs SHA,SHA", result.err)

    def test_newest_goes_with_show_and_a_commit_given_twice_is_shown_once(self):
        result = support.run("heatmap.py", "-C", self.repo.path, "--newest", "3")
        self.assertEqual(result.code, 2, result)
        self.assertIn("--newest goes with --show: --show FILE --newest N", result.err)
        rounding = self.repo.short(self.marks["rounding"])
        twice = support.run("heatmap.py", "-C", self.repo.path, "--show", "app.py", "--diffs",
                            "%s,%s" % (rounding, rounding[:7]))
        self.assertTrue(twice.out.startswith("app.py: its changes in 1 of its commits"), twice)
        self.assertEqual(twice.out.count("Fix the total's rounding"), 1)

    def test_show_reads_no_files_sizes_before_the_window(self):
        # --show lists a file's commits: it reads the files at HEAD, which say the table's rows its marks count,
        # but not the sizes before the window, which only the table's growth needs.
        code = ("import os, sys\nsys.path.insert(0, os.environ['REFACTOR_PASS_SCRIPTS'])\nimport heatmap\n"
                "counts = heatmap.line_counts\ndef at_head(repo, wanted):\n"
                "    if any(rev != 'HEAD' for rev, _ in wanted):\n        raise RuntimeError('read the sizes before')\n"
                "    return counts(repo, wanted)\nheatmap.line_counts = at_head\n"
                "sys.argv = ['heatmap.py'] + sys.argv[1:]\nheatmap.main()\n")
        for args in (["--messages"], ["--diffs", self.repo.short(self.marks["crash"])]):
            result = support.run_python(code, "-C", self.repo.path, "--show", "app.py", *args)
            self.assertEqual((result.code, result.err), (0, ""), result)

    def test_diffs_give_each_commits_changes_to_the_file_only(self):
        rounding, crash = self.repo.short(self.marks["rounding"]), self.repo.short(self.marks["crash"])
        result = support.run("heatmap.py", "-C", self.repo.path, "--show", "app.py", "--diffs",
                             "%s, %s" % (rounding, crash[:7]))
        self.assertEqual(result.code, 0, result)
        self.assertEqual(result.out, "app.py: its changes in 2 of its commits, each cut at 60 lines\n"
                         "  %s 2026-01-17 newer  Fix the total's rounding  [fix, words: fix]\n"
                         "      @@ -12,3 +12,5 @@ app 11\n       app 12\n       app 13\n       app 14\n"
                         "      +app 15\n      +total = round(x)\n"
                         "  %s 2026-01-03 older  Fix the crash when the cart is empty  [fix, words: fix, crash]\n"
                         "      @@ -10,3 +10,4 @@ app 9\n       app 10\n       app 11\n       app 12\n      +app 13\n\n"
                         % (rounding, crash))
        wrong = support.run("heatmap.py", "-C", self.repo.path, "--show", "app.py", "--diffs", "%s,zz,%s" % (
            self.repo.short(self.marks["speed"]), rounding))
        self.assertEqual(wrong.code, 1, wrong)
        self.assertIn("--diffs: %s isn't one of them; zz isn't one of them. Give hashes of the 7 commits --show "
                      "app.py --messages lists." % self.repo.short(self.marks["speed"]), wrong.err)

    def test_the_page_carries_the_fixes(self):
        with open(self.page, encoding="utf-8") as f:
            heat = json.loads(support.block(f.read(), "heatmap"))
        self.assertEqual(heat["window"]["fixes"], {"fixes": 5, "revert": 1, "type": 0, "words": 4, "typed": 0.0,
                                                   "labels": False, "thin": False, "language": False,
                                                   "complete": False})
        with open(support.TEMPLATE, encoding="utf-8") as f:  # Where no commit says it fixed a defect, it says so.
            self.assertIn("None of the commits says in its message that it fixed a defect", f.read())
        rows = dict((r["path"], r) for r in heat["files"])
        self.assertEqual((rows["app.py"]["fixes"], rows["app.py"]["fixes_recent"]), (2, 1))
        self.assertEqual((rows["util.py"]["fixes"], rows["util.py"]["fixes_recent"]), (3, 1))
        for aside in ("package.json", "CHANGES.md", "docs/guide.md", ".github/workflows/ci.yml"):
            self.assertNotIn("fixes", rows[aside], aside)
        self.assertEqual(support.run("check_page.py", self.page).code, 0)

    def test_left_out_commits_dont_count(self):
        # The bot's "Fix: bump left-pad" is left out by default; and a fix left out with --exclude-commits
        # counts toward nothing.
        result = support.run("heatmap.py", "-C", self.repo.path, "--exclude-commits",
                             self.repo.short(self.marks["crash"]))
        self.assertEqual(result.code, 0, result)
        self.assertTrue(fixes_lines(result.out)[0].startswith(
            "Fixes, a lead and not a verdict: at least 4 of the 17 commits fixed"), result.out)
        self.assertEqual(fix_rows(result.out), {"util.py": (3, 1, 1, 0, 2), "app.py": (1, 1, 0, 0, 1)})

    def test_no_fixes_leaves_it_all_out(self):
        result = support.run("heatmap.py", "-C", self.repo.path, "--no-fixes")
        self.assertEqual(result.code, 0, result)
        self.assertNotIn("Fixes", result.out)
        shown = support.run("heatmap.py", "-C", self.repo.path, "--no-fixes", "--show", "util.py")
        self.assertNotIn("[", shown.out)
        # The rest is as it was.
        self.assertEqual(support.heatmap_rows(result.out), support.heatmap_rows(self.result.out))


TYPED = [("feat: add the cart", "", ""), ("fix(cart)!: the total ignores discounts", "fix, type: fix(cart)!:", "fix"),
         ("docs: fix the docstring of total", "not a fix: labelled docs:", ""),
         ("fix(deps): bump left-pad", "not a fix: labelled fix(deps):", ""),
         ("[fix] crash on an empty cart", "fix, type: [fix]", "fix"),
         ("\U0001F41B wrong rounding", "fix, type: \U0001F41B", "fix"),
         ("Correct the rounding of totals", "fix, words: correct", "fix"),
         ("refactor: split the cart", "", ""), ("chore: release 1.0", "", ""), ("perf: cache totals", "", "")]
MOSTLY_TYPED = ["fix: the total ignores discounts", "feat: add the cart", "wip", "fix(cart): empty carts crash",
                "feat: coupons", "refactor: split the cart", "v1.2.3", "fix: wrong rounding", "docs: the guide",
                "chore: release 1.0", "fix: coupons apply twice", "perf: cache totals", "Update deps",
                "test: the cart", "fix: tax on shipping"]
PLAIN = ["Add the cart", "Add the coupons", "Speed up totals", "Split the cart", "Tidy the totals", "Add a red hat",
         "Add a blue scarf", "Add the shoes", "Add a coat", "Add the gloves", "Add the socks"]


def build_typed(subjects, name="typed"):
    """A repo whose commits, a day apart, each change app.py, with the subjects given."""
    repo = support.Repo(name)
    repo.commit("2026-01-01", "feat: start", {"app.py": lines(5, "app")})
    for day, subject in enumerate(subjects, 2):
        repo.commit("2026-01-%02d" % day, subject, {"app.py": lines(5 + day, "app")})
    repo.done()
    return repo


class Typed(unittest.TestCase):

    def test_types_read_as_labels_where_most_subjects_carry_one(self):
        repo = build_typed([t[0] for t in TYPED])
        result = support.run("heatmap.py", "-C", repo.path, "--show", "app.py")
        self.assertEqual(result.code, 0, result)
        marks = marks_of(result.out)
        self.assertEqual(dict((t[0], marks[t[0]]) for t in TYPED), dict((t[0], t[1]) for t in TYPED))
        heatmap = support.run("heatmap.py", "-C", repo.path)
        # 10 of the 11 subjects carry a type, 90% rounded down: all but the one that reads by its words.
        self.assertEqual(fixes_lines(heatmap.out), [
            "Fixes, a lead and not a verdict: at least 4 of the 11 commits fixed a defect in the project's own "
            "code, as their messages say: 3 by their type and 1 by their words.",
            "90% of the subjects carry a type, read as a label, so the count is close to complete."])
        self.assertEqual(fix_rows(heatmap.out), {"app.py": (4, 3, 0, 3, 1)})

    def test_messages_say_how_much_of_the_sample_is_in_the_newer_half(self):
        # Where nearly all of it is, a count of its fixes there says nothing new: the line says it isn't said.
        repo = support.Repo("halves")
        for day, files in enumerate([("a.py", "b.py"), ("a.py",), ("b.py",), ("b.py",), ("a.py",), ("c.py",),
                                     ("c.py", "d.py"), ("a.py", "c.py")], 1):
            repo.commit("2026-01-%02d" % day, "Change %s on day %d" % (" and ".join(files), day),
                        dict((f, lines(day, f[0])) for f in files))
        repo.done()
        said = dict((name, support.run("heatmap.py", "-C", repo.path, "--show", name, "--messages").out.split(
            "\n")[1]) for name in ("a.py", "b.py", "c.py", "d.py"))
        null = ", so how many of its fixes are there isn't said (newer: null)."
        self.assertEqual(said, {"a.py": "In the newer half: 2 of these 4.", "b.py": "In the newer half: none of these "
                                "3.", "c.py": "In the newer half: all 3" + null,
                                "d.py": "In the newer half: this one" + null})
        self.assertEqual(support.load("heatmap").newer_line(11, 12), "In the newer half: 11 of these 12, nearly all"
                         + null)
        self.assertEqual(support.load("heatmap").newer_line(10, 12), "In the newer half: 10 of these 12.")
        plain = support.run("heatmap.py", "-C", repo.path, "--show", "a.py").out.split("\n")
        self.assertRegex(plain[1], r"^  [0-9a-f]{9} ")  # Only the sample --messages lists has it.

    def test_types_read_as_words_where_few_subjects_carry_one(self):
        repo = build_typed(PLAIN + ["fix(cart): the total ignores discounts", "docs: fix the docstring of total",
                                    "[fix] crash on an empty cart"], "untyped")
        result = support.run("heatmap.py", "-C", repo.path, "--show", "app.py")
        # --messages lists its newest 12 of 15, and --diffs takes only those, unless --newest widens it.
        sample = support.run("heatmap.py", "-C", repo.path, "--show", "app.py", "--messages")
        self.assertIn("app.py: the newest 12 of its 15 commits, of the 15 from ", sample.out.split("\n")[0])
        self.assertTrue(sample.out.split("\n")[0].endswith("3 more: --newest 15 lists them all."), sample.out)
        self.assertEqual(len(re.findall(r"(?m)^  [0-9a-f]{9} ", sample.out)), 12)
        oldest = re.findall(r"(?m)^  ([0-9a-f]{9}) ", result.out)[-1]
        narrow = support.run("heatmap.py", "-C", repo.path, "--show", "app.py", "--diffs", oldest)
        self.assertIn("isn't one of them. Give hashes of the 12 commits --show app.py --messages lists, or widen it "
                      "with --newest.", narrow.err)
        wide = support.run("heatmap.py", "-C", repo.path, "--show", "app.py", "--diffs", oldest, "--newest", "15")
        self.assertEqual(wide.code, 0, wide)
        marks = marks_of(result.out)
        self.assertEqual(marks["fix(cart): the total ignores discounts"], "fix, words: fix")
        self.assertEqual(marks["docs: fix the docstring of total"], "not a fix: says docs")
        self.assertEqual(marks["[fix] crash on an empty cart"], "fix, words: fix, crash")
        # 4 of the 15 subjects carry a type, with "feat: start": 26%, rounded down.
        self.assertTrue(fixes_lines(support.run("heatmap.py", "-C", repo.path).out)[1].startswith(
            "26% of the subjects carry a type, too few to read as labels, so the count is a floor"))

    def test_tags_that_arent_types_read_by_their_words(self):
        # Component and ticket tags are areas, not types: none of these subjects carries one but "feat: start".
        repo = build_typed(["[clang] Fix crash when parsing templates", "[driver] Fix wrong default for the flag",
                            "[lld] Prevent overflow in section sizes", "[clang] Add the flag",
                            "[JIRA-123] Fix the bug in the parser when input is empty", "[lld][ELF] Speed up linking"],
                           "tagged")
        result = support.run("heatmap.py", "-C", repo.path)
        self.assertEqual(fixes_lines(result.out)[0], "Fixes, a lead and not a verdict: at least 4 of the 7 commits "
                         "fixed a defect in the project's own code, as their messages say: 4 by their words.")
        self.assertTrue(fixes_lines(result.out)[1].startswith("14% of the subjects carry a type"), result.out)
        self.assertEqual(fix_rows(result.out), {"app.py": (4, 2, 0, 0, 4)})


class Thin(unittest.TestCase):

    def test_subjects_of_a_word_or_two_cant_support_the_trace(self):
        repo = build_typed(["wip", "update", "fix", "more", "Fix the crash in the cart", "stuff", "fix it", "Add a "
                            "hat to the shop"], "thin")
        result = support.run("heatmap.py", "-C", repo.path)
        self.assertEqual(result.code, 0, result)
        # 9 commits, 7 of them a word or two: "feat: start" carries a type, but few do, so its words count.
        self.assertEqual(fixes_lines(result.out)[1], "Most subjects here are a word or two (7 of the 9), too little "
                         "to tell a fix from anything else, so the count can't be read and the fixes by file aren't "
                         "listed. 11% of the subjects carry a type.")
        self.assertNotIn("Fixes by file", result.out)

    def test_short_subjects_are_weighed_against_all_the_commits(self):
        # 16 commits, 13 of them typed and 5 of those fix:; the 3 without a type are a word or two.
        repo = build_typed(MOSTLY_TYPED, "mostly-typed")
        result = support.run("heatmap.py", "-C", repo.path)
        self.assertTrue(fixes_lines(result.out)[0].startswith("Fixes, a lead and not a verdict: at least 5 of the 16 "
                                                              "commits"), result.out)
        self.assertNotIn("Most subjects", result.out)
        self.assertEqual(fix_rows(result.out)["app.py"][::3], (5, 5))


class Words(unittest.TestCase):
    """The words read, one subject at a time, and the files that aren't the project's code."""

    def setUp(self):
        self.heatmap = support.load("heatmap")

    def test_fix_words_and_the_words_that_say_otherwise(self):
        says = self.heatmap.says
        self.assertEqual(says("Fix the crash, and an overflow"), (["fix", "crash", "overflow"], []))
        self.assertEqual(says("Fixed typos in the docs"), (["fix"], ["typo", "docs"]))
        self.assertEqual(says("Better error messages for vararg-table fields"), (["error"], ["error message"]))
        self.assertEqual(says("Prevented a CVE"), (["cve", "prevent"], []))
        self.assertEqual(says("修复注释中的错误"), (["修复"], ["注释"]))

    def test_issue_references_identifiers_and_code_say_nothing(self):
        says = self.heatmap.says
        for subject in ["Fixed #12 -- Added coupons", "Closes gh-7", "Add should_ignore_error", "Use `fix()` here",
                        "Call Data.Fix() now", "Rename isFixed", "Addressing Issue 1809", "Add the prefix fixture",
                        "Add a regression test for totals"]:
            self.assertEqual(says(subject), ([], []), subject)

    def test_files_that_arent_the_projects_code(self):
        not_code = self.heatmap.not_code

        def test(path):
            return path.startswith("tests/")
        chore = "CI, build or dependency files"
        for path, kind in [("docs/conf.py", None), ("CHANGES.rst", "documentation"),
                           ("tests/test_app.py", "tests"), (".github/workflows/ci.yml", chore), ("go.mod", chore),
                           ("src/Makefile", chore), ("packages/core/package.json", chore), ("pyproject.toml", chore),
                           ("Dockerfile", chore), ("vite.config.ts", chore), ("src/app.py", None),
                           ("lib/build.py", None), ("src/server.c", None), ("ci/check.py", None)]:
            self.assertEqual(not_code(path, test), kind, path)

    def test_a_documentation_name_with_a_code_extension_is_code(self):
        not_code, doc, chore = self.heatmap.not_code, "documentation", "CI, build or dependency files"
        for path, kind in [("src/history.ts", None), ("news.py", None), ("lib/authors.rb", None), ("changes.js", None),
                           ("app/controllers/news_controller.rb", None), ("license_checker.go", None),
                           ("build.rs", None), ("ci.py", None), ("setup.py", chore), ("HISTORY.md", doc),
                           ("NEWS", doc), ("LICENSE-MIT", doc), ("COPYING.LESSER", doc), ("LICENSE.APACHE2", doc),
                           ("AUTHORS.txt", doc), ("README.zh-CN.md", doc), ("Changes", doc)]:
            self.assertEqual(not_code(path, lambda p: False), kind, path)

    def test_a_program_named_for_documentation(self):
        # Without an extension, a name with more after the documentation word is documentation only where that
        # word is in capitals, as LICENSE-MIT and README_zh: license-checker is a program.
        is_doc = self.heatmap.is_doc
        for path in ("bin/license-checker", "scripts/history-cleanup", "src/changes_tracker", "tools/changelog-gen",
                     "authors-update"):
            self.assertFalse(is_doc(path), path)
        for path in ("LICENSE-MIT", "COPYING.LESSER", "README_zh", "NEWS", "AUTHORS", "CHANGELOG", "changelog"):
            self.assertTrue(is_doc(path), path)

    def test_code_in_a_docs_folder_and_a_setup_py_at_no_packages_top(self):
        # In a docs folder, only what isn't code by its extension is documentation: cobra's doc/ is a package of
        # the library. setup.py is a manifest at a package's top, where its manifests are: the repo's, or beside
        # a pyproject.toml or a setup.cfg. Beside a package folder isn't: src/setup.py in a src layout is code.
        heatmap, doc, chore = self.heatmap, "documentation", "CI, build or dependency files"
        for path, kind in [("docs/guide.md", doc), ("docs/images/flow.png", doc), ("docs/Makefile", doc),
                           ("doc/man_docs.go", None), ("tokio/src/doc/mod.rs", None), ("apps/docs/src/search.ts", None),
                           ("docs/conf.py", None)]:
            self.assertEqual(heatmap.not_code(path, lambda p: False), kind, path)
        tops = heatmap.package_tops(["setup.py", "python/setup.py", "python/pyproject.toml", "sdk/setup.py",
                                     "sdk/client/__init__.py", "src/setup.py", "src/shop/__init__.py"])
        self.assertEqual(tops, {"", "python"})
        for path, kind in [("setup.py", chore), ("python/setup.py", chore), ("sdk/setup.py", None),
                           ("src/setup.py", None)]:
            self.assertEqual(heatmap.not_code(path, lambda p: False, tops), kind, path)

    def test_a_requirements_folder_names_dependencies(self):
        # As open-mmlab keeps them: requirements/runtime.txt, requirements/tests.txt.
        chore = "CI, build or dependency files"
        for path, kind in [("requirements/tests.txt", chore), ("requirements/runtime.in", chore),
                           ("requirements/check.py", None)]:
            self.assertEqual(self.heatmap.not_code(path, lambda p: False), kind, path)

    def test_a_fix_type_before_an_issue_number(self):
        # fix: #482 says fix by its type's word; Fix #482:, Fixes #12, Fixes: #12 and Django's Fixed #12 -- close an
        # issue and say nothing else.
        heatmap = self.heatmap
        self.assertEqual([heatmap.read_fix(s, False) for s in (
            "fix: #482 handle empty payload", "fix: #846 (#847)", "Fix #482: handle empty payload", "Fixes #12",
            "Fixes: #12", "Fixed #12 -- Added X")], [(3, "fix"), (3, "fix"), (0, ""), (0, ""), (0, ""), (0, "")])
        commits = [("%040d" % n, n, s, [("a.py", None, 1, 0)], "Ann <a@b>", "") for n, s in enumerate(
            ["fix: #482 handle empty payload", "Fixes: #12 in the cart", "Fix #13: handle the rest of it"])]
        lines, _ = heatmap.fix_summary(commits, heatmap.fix_trace(commits, commits, False), 0.0)
        self.assertTrue(lines[1].endswith(" 2 more commits close an issue without saying what kind of change."), lines)

    def test_a_fix_word_in_camelcase_or_by_a_bracket_is_a_word(self):
        # BugFix and HotFix are fix words, not identifiers, as isFixed is one; and a tag's bracket ends a word.
        # [HotFix] is passed over, as Flink's [hotfix] is.
        read_fix = self.heatmap.read_fix
        subjects = ("[BugFix] thing", "[Fix] thing", "[bugfix] thing", "[HotFix] x", "[Fix]Crash on start",
                    "[BugFix]Handle null", "BugFix: handle null", "HotFix for login", "Rename isFixed")
        self.assertEqual([read_fix(s, False) for s in subjects], [(3, "bug"), (3, "fix"), (3, "bug"), (0, ""),
                                                                 (3, "fix, crash"), (3, "bug"), (3, "bug"), (3, "fix"),
                                                                 (0, "")])

    def test_gitmojis_lock_is_a_fix(self):
        # Gitmoji's "fix security or privacy issues".
        for subject in ("\U0001F512 fix xss in the comment form", "\U0001F512\ufe0f x", ":lock: x"):
            self.assertEqual(self.heatmap.type_of(subject)[0], "fix", subject)

    def test_a_type_after_a_gitmoji(self):
        # Where a type follows the emoji, that word is the type: one may say what the other doesn't.
        type_of = self.heatmap.type_of
        self.assertEqual(type_of("⚡️ fix(parser): x"), ("fix", "fix(parser):"))
        self.assertEqual(type_of(":zap: fix: crash"), ("fix", "fix:"))
        self.assertEqual(type_of("\U0001F527 fix: config loading wrong"), ("fix", "fix:"))
        self.assertEqual(type_of("\U0001F41B feat: x"), ("other", "feat:"))
        self.assertEqual(type_of(":bug: fix(deps): bump x"), ("chore", "fix(deps):"))
        self.assertEqual(type_of("\U0001F527 config: x"), ("other", "\U0001F527"))  # Not a type: the emoji is.
        self.assertEqual(self.heatmap.read_fix(":zap: fix: crash", True), (2, "fix:"))

    def test_open_mmlabs_types_in_brackets(self):
        # As mmengine writes them: [Fix], [Feature], [Enhance], [Improve], [Refactor], [Docs], [Test].
        for word in ("Feature", "Enhance", "Improve", "Refactor", "Docs", "Test"):
            self.assertEqual(self.heatmap.type_of("[%s] x" % word), ("other", "[%s]" % word), word)

    def test_types(self):
        type_of = self.heatmap.type_of
        self.assertEqual(type_of("fix(router)!: x"), ("fix", "fix(router)!:"))
        self.assertEqual(type_of("hotfix: x"), ("fix", "hotfix:"))
        self.assertEqual(type_of("Bugfix: x"), ("fix", "Bugfix:"))
        self.assertEqual(type_of("fix：修复"), ("fix", "fix："))
        self.assertEqual(type_of("fix(deps): bump x"), ("chore", "fix(deps):"))
        self.assertEqual(type_of("[Fix] x"), ("fix", "[Fix]"))
        self.assertEqual(type_of("[docs] x"), ("other", "[docs]"))
        self.assertEqual(type_of(":bug: x"), ("fix", ":bug:"))
        self.assertEqual(type_of("\U0001F680 release"), ("other", "\U0001F680"))
        self.assertEqual(type_of("feat: x"), ("other", "feat:"))
        self.assertIsNone(type_of("ignore: respect the filters"))  # An area, as ripgrep's, not a type.
        self.assertIsNone(type_of("Fix the crash"))

    def test_a_tag_or_an_emoji_is_a_type_only_where_its_word_is_one(self):
        type_of, read_fix = self.heatmap.type_of, self.heatmap.read_fix
        for subject in ["[clang] Fix crash", "[SPARK-1][SQL] Fix the join", "[hotfix] Fix log levels", "[] x",
                        "\U0001F600 Fix it", "[JIRA-123] Fix the bug"]:
            self.assertIsNone(type_of(subject), subject)
        self.assertEqual(type_of("[PROJ-123][Fix] the removal"), ("fix", "[Fix]"))
        self.assertEqual(type_of("[Fix][PROJ-123] the removal"), ("fix", "[Fix]"))
        self.assertEqual(type_of("[Enhance] x"), ("other", "[Enhance]"))
        self.assertEqual(type_of("[SQL] fix: x"), ("fix", "fix:"))
        self.assertEqual(type_of("\u267b\ufe0f split"), ("other", "\u267b\ufe0f"))
        self.assertEqual(type_of(":t-rex: x"), ("other", ":t-rex:"))
        self.assertEqual(type_of("\U0001F691\ufe0f x"), ("fix", "\U0001F691\ufe0f"))
        # The rest of the subject read by its words, without the tags that aren't types: Flink's [hotfix] is
        # a change made without a ticket.
        self.assertEqual(read_fix("[hotfix] Fix typo in a comment", True), (0, "says typo"))
        self.assertEqual(read_fix("[hotfix] Update the example URL", True), (0, ""))
        self.assertEqual(read_fix("[hotfix][runtime] Fix log levels", True), (3, "fix"))
        self.assertEqual(read_fix("[PROJ-123] Fix the removal of the cache for upgrades", True), (3, "fix"))
        self.assertEqual(read_fix("[BUG-12] Add a hat", False), (0, ""))

    def test_one_person_by_name_or_email_but_not_by_an_empty_one(self):
        same = self.heatmap.same_person
        self.assertTrue(same("Ann Dev <ann@example.com>", "ann dev <ann@work.example>"))
        self.assertTrue(same("Ann <ann@example.com>", "Ann Dev <ANN@example.com>"))
        self.assertFalse(same("Ann Dev <ann@example.com>", "Bob Dev <bob@example.com>"))
        # A blank name, or a blank email, is no one's: two such authors aren't one person by it.
        self.assertFalse(same(" <ann@example.com>", " <bob@example.com>"))
        self.assertFalse(same("Ann Dev <>", "Bob Dev <>"))

    def test_a_window_where_no_message_says_fix(self):
        heatmap = support.load("heatmap")
        commits = [("%040d" % n, n, "Add the shop's %d hats" % n, [("a.py", None, 1, 0)], "Ann <a@b>", "")
                   for n in (1, 2)]
        lines, facts = heatmap.fix_summary(commits, heatmap.fix_trace(commits, commits, False), 0.0)
        self.assertEqual(lines, ["Fixes, a lead and not a verdict: none of the 2 commits says in its message that it "
                                 "fixed a defect in the project's own code.", "0% of the subjects carry a type, too "
                                 "few to read as labels, so the count is a floor: subjects without a type typically "
                                 "say so for a third to a half of the fixes, and the rest are among the commits "
                                 "--show leaves unmarked."])
        self.assertEqual((facts["fixes"], facts["thin"]), (0, False))

    def test_close_to_complete_only_where_nearly_all_subjects_carry_a_type(self):
        heatmap = support.load("heatmap")
        commits = [("%040d" % n, n, subject, [("a.py", None, 1, 0)], "Ann <a@b>", "")
                   for n, subject in enumerate(["fix: the total", "Add the shop's hats"])]
        trace = heatmap.fix_trace(commits, commits, True)
        self.assertEqual(heatmap.fix_summary(commits, trace, 0.5)[0][1], "50% of the subjects carry a type, read as a "
                         "label; those without one are read by their words, so the count is a floor: such subjects "
                         "typically say so for a third to a half of their fixes, and the rest are among the commits "
                         "--show leaves unmarked.")
        lines, facts = heatmap.fix_summary(commits, trace, heatmap.NEARLY_ALL)
        self.assertTrue(lines[1].endswith("so the count is close to complete."), lines[1])
        self.assertEqual((facts["labels"], facts["complete"]), (True, True))
        self.assertEqual(heatmap.fix_summary(commits, trace, heatmap.LABELLED)[1]["complete"], False)
        with open(support.TEMPLATE, encoding="utf-8") as f:  # The page says what the facts say, deciding nothing.
            template = f.read()
        self.assertNotIn("fx.typed >=", template)
        self.assertIn("fx.complete", template)

    def test_an_issue_closed_counts_only_where_nothing_says_what_it_was(self):
        heatmap = support.load("heatmap")
        commits = [("%040d" % n, n, subject, [("a.py", None, 1, 0)], "Ann <a@b>", "") for n, subject in enumerate(
            ["Fixed #12 -- Corrected a typo in the guide", "Fixed #13 -- Added coupons", "Fixed #14 -- Fixed a crash"])]
        lines, facts = heatmap.fix_summary(commits, heatmap.fix_trace(commits, commits, False), 0.0)
        self.assertEqual(facts["fixes"], 1)
        self.assertTrue(lines[1].endswith(" 1 more commit closes an issue without saying what kind of change."))

    def test_an_issue_is_a_number(self):
        # #include, #ifdef and #define are code, not issues: an issue is #12, gh-12 or org/repo#12.
        heatmap = self.heatmap
        for subject in ["Fix #include order that broke the build on Windows", "Fix #ifdef guard around the socket code",
                        "Fixes #define of MAX_PATH on old compilers"]:
            self.assertEqual(heatmap.says(subject)[0], ["fix"], subject)
        commits = [("%040d" % n, n, subject, [("a.c", None, 1, 0)], "Ann <a@b>", body) for n, (subject, body) in
                   enumerate([("Fix #include order that broke the build", ""), ("Add hats", "Fixes #define of MAX"),
                              ("Fixed #12 -- Added coupons", ""), ("Add a hat", "Closes org/shop#7")])]
        lines, facts = heatmap.fix_summary(commits, heatmap.fix_trace(commits, commits, False), 0.0)
        self.assertEqual(facts["fixes"], 1)
        self.assertTrue(lines[1].endswith(" 2 more commits close an issue without saying what kind of change."))

    def test_the_share_with_a_type_is_one_number(self):
        # Printed as the decision is made from it: 99 of 200 is 49%, too few; 179 of 200 is 89%, not nearly all.
        heatmap = self.heatmap
        for count, share, said in ((99, 0.49, "49% of the subjects carry a type, too few to read as labels"),
                                   (179, 0.89, "89% of the subjects carry a type, read as a label; those without")):
            commits = [("%040d" % n, n, "feat: a hat" if n < count else "Add a hat to the shop",
                        [("a.py", None, 1, 0)], "Ann <a@b>", "") for n in range(200)]
            typed = heatmap.typed_share(commits)
            self.assertEqual(typed, share)
            trace = heatmap.fix_trace(commits, commits, typed >= heatmap.LABELLED)
            line = heatmap.fix_summary(commits, trace, typed)[0][1]
            self.assertTrue(line.startswith(said), line)

    def test_subjects_in_a_language_the_trace_doesnt_read(self):
        heatmap = self.heatmap
        subjects = ["Исправлена ошибка при сохранении файла", "Добавлена поддержка новых форматов",
                    "設定ファイルの読み込みを修正しました", "ログの出力形式を変更しました", "파일 저장 시 오류를 수정했습니다",
                    "Add the cart to the shop"]
        commits = [("%040d" % n, n, s, [("a.py", None, 1, 0)], "Ann <a@b>", "") for n, s in enumerate(subjects)]
        lines, facts = heatmap.fix_summary(commits, heatmap.fix_trace(commits, commits, False), 0.0)
        self.assertEqual(lines[1], "Most subjects here are in a language the trace doesn't read, which reads English "
                                   "and Chinese (5 of the 6), so the count can't be read and the fixes by file aren't "
                                   "listed. 0% of the subjects carry a type.")
        self.assertEqual((facts["thin"], facts["language"]), (True, True))
        # Words in any script: a run of letters, or a character or two of Chinese or Japanese.
        self.assertEqual([heatmap.words(s) for s in ("Исправлена ошибка при сохранении", "파일 저장 시 오류를 수정했습니다",
                                                     "修复价格计算错误", "wip", "v1.2.3", "Update deps")], [4, 5, 4, 1, 1, 2])


    def test_only_a_fix_has_its_files_told_apart(self):
        # Which files are the project's code matters only for a commit that reads as a fix.
        heatmap = self.heatmap
        commits = [("%040d" % n, n, subject, [("f%d.py" % k, None, 1, 0) for k in range(50)], "Ann <a@b>", "")
                   for n, subject in enumerate(["Add a hat", "Fix the crash"])]
        told, kept = [], heatmap.not_code
        heatmap.not_code = lambda path, *args: told.append(path) or kept(path, *args)
        try:
            heatmap.fix_trace(commits, commits, False)
        finally:
            heatmap.not_code = kept
        self.assertEqual(len(told), 1)  # The fix's first file is code: that settles it.

    def test_a_commit_that_changed_no_file_fixed_nothing(self):
        # As git commit --allow-empty -m 'Empty fix for crash' makes.
        heatmap = self.heatmap
        commits = [("%040d" % 1, 1, "Empty fix for crash", [], "Ann <a@b>", "")]
        self.assertEqual(heatmap.fix_trace(commits, commits, False)[commits[0][0]], (0, "changes no file", None))




    def test_how_long(self):
        how_long = self.heatmap.how_long
        self.assertEqual([how_long(s) for s in (30, 600, 7200, 86400, 86400 * 45, 86400 * 400, 86400 * 900)],
                         ["1 minute", "10 minutes", "2 hours", "1 day", "45 days", "13 months", "2 years"])


if __name__ == "__main__":
    unittest.main()
