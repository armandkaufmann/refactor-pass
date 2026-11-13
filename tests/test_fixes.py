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

    def test_fixes_by_file_at_least(self):
        # util.py: the negative total and the Chinese fix, older, and the revert, in the newer half (the 9
        # newest). app.py: the crash, older, and the rounding. package.json had the rounding too, but it's a
        # dependency file, set aside like documentation and tests.
        self.assertEqual(fix_rows(self.result.out), {"util.py": (3, 1, 1, 0, 2), "app.py": (2, 1, 0, 0, 2)})
        self.assertIn("Fixes by file, at least: of each file's commits, those whose messages say they fixed a "
                      "defect in it, and how many of those were in the newer half; documentation, tests, and CI, "
                      "build and dependency files aside. A floor, not a count: --show FILE --messages gives each "
                      "commit's message, to read the ones left unmarked.\n", self.result.out)

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
        result = support.run("heatmap.py", "-C", self.repo.path, "--diffs", "a1b2c3d", "--show", "a.py", "--show",
                             "app.py")
        self.assertEqual(result.code, 2, result)
        self.assertIn("--diffs goes with one --show: --show FILE --diffs SHA,SHA", result.err)

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
                                                   "labels": False, "closing": 1, "withdrawn": 1, "thin": False})
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
        # 10 of the 11 subjects carry a type: all but the one that reads by its words.
        self.assertEqual(fixes_lines(heatmap.out), [
            "Fixes, a lead and not a verdict: at least 4 of the 11 commits fixed a defect in the project's own "
            "code, as their messages say: 3 by their type and 1 by their words.",
            "91% of the subjects carry a type, read as a label, so the count is close to complete."])
        self.assertEqual(fix_rows(heatmap.out), {"app.py": (4, 3, 0, 3, 1)})

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
        # 4 of the 15 subjects carry a type, with "feat: start".
        self.assertTrue(fixes_lines(support.run("heatmap.py", "-C", repo.path).out)[1].startswith(
            "27% of the subjects carry a type, too few to read as labels, so the count is a floor"))

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


class Reverts(unittest.TestCase):
    """One repo: reverts of reverts, whose original is in the window (a.py, b.py) or isn't (c.py), and reverts
    as GitHub writes them and without their line (d.py)."""

    @classmethod
    def setUpClass(cls):
        repo = cls.repo = support.Repo("reverts")
        repo.commit("2026-01-01", "Start", {"a.py": lines(3, "a"), "b.py": lines(3, "b"), "c.py": lines(3, "c"),
                                           "d.py": lines(3, "d")})
        cls.crash = repo.commit("2026-01-02", "Fix the crash in a", {"a.py": lines(4, "a")})
        cls.hat = repo.commit("2026-01-03", "Add a hat to b", {"b.py": lines(4, "b")}, author=support.BOB)
        cls.github = repo.commit("2026-01-04", "Fix the crash in d (#12)", {"d.py": lines(4, "d")},
                                 author=support.BOB)
        cls.coupons = repo.commit("2026-01-05", "Add coupons (#13)", {"d.py": lines(5, "d")}, author=support.BOB)
        repo.done()
        back = repo.commit("2026-01-06", 'Revert "Fix the crash in a"\n\nThis reverts commit %s.\n'
                           % repo.sha(cls.crash), {"a.py": lines(3, "a")}, author=support.BOB)
        undo = repo.commit("2026-01-07", 'Revert "Add a hat to b"\n\nThis reverts commit %s.\n' % repo.sha(cls.hat),
                           {"b.py": lines(3, "b")})
        repo.commit("2026-01-08", 'Revert "Fix the crash in d (#12)" (#14)\n\nThis reverts commit %s.\n'
                    % repo.sha(cls.github), {"d.py": lines(6, "d")})
        # Without the line, a subject that starts with Revert reads by its words at most.
        repo.commit("2026-01-09", 'Revert "Add coupons (#13)"', {"d.py": lines(7, "d")})
        repo.commit("2026-01-10", 'Revert "Fix the crash in d (#12)"', {"d.py": lines(8, "d")})
        # A revert of a change to the docs, or of a chore, isn't a fix of the code.
        repo.commit("2026-01-11", 'Revert "docs: say more"\n\nThis reverts commit %s.\n' % repo.sha(cls.coupons),
                    {"d.py": lines(9, "d")})
        repo.commit("2026-01-12", 'Revert "Reword the readme"\n\nThis reverts commit %s.\n' % ("f" * 40),
                    {"d.py": lines(10, "d")})
        # Re-landings of what was reverted outside the window: read by their words.
        repo.commit("2026-01-13", 'Revert "Revert "Fix the crash in c""\n\nThis reverts commit %s.\n' % ("d" * 40),
                    {"c.py": lines(4, "c")})
        repo.commit("2026-01-14", 'Revert "Revert "Add a hat""\n\nThis reverts commit %s.\n' % ("e" * 40),
                    {"c.py": lines(5, "c")})
        repo.done()
        repo.commit("2026-01-15", 'Revert "Revert "Fix the crash in a""\n\nThis reverts commit %s.\n'
                    % repo.sha(back), {"a.py": lines(4, "a")})
        repo.commit("2026-01-16", 'Revert "Revert "Add a hat to b""\n\nThis reverts commit %s.\n' % repo.sha(undo),
                    {"b.py": lines(4, "b")}, author=support.BOB)
        repo.done()
        result = support.run("heatmap.py", "-C", repo.path, *[a for f in "abcd" for a in ("--show", f + ".py")])
        assert result.code == 0, result
        cls.marks = marks_of(result.out)

    def test_a_revert_of_a_revert_reads_as_what_it_relands(self):
        marks = self.marks
        self.assertEqual(marks['Revert "Revert "Fix the crash in a""'], "fix, words: re-lands fix, crash")
        self.assertEqual(marks['Revert "Revert "Add a hat to b""'], "not a fix: re-lands a change that wasn't a fix")
        # The reverts themselves: of another author's commits.
        self.assertEqual(marks['Revert "Fix the crash in a"'], "fix, revert: reverts %s, 4 days after it"
                         % self.repo.short(self.crash))
        self.assertEqual(marks['Revert "Add a hat to b"'], "fix, revert: reverts %s, 4 days after it"
                         % self.repo.short(self.hat))

    def test_a_relanding_whose_revert_is_outside_the_window_reads_by_its_words(self):
        self.assertEqual(self.marks['Revert "Revert "Fix the crash in c""'], "fix, words: re-lands fix, crash")
        self.assertEqual(self.marks['Revert "Revert "Add a hat""'], "not a fix: re-lands a change that wasn't a fix")

    def test_reverts_as_github_writes_them_and_without_their_line(self):
        marks = self.marks
        self.assertEqual(marks['Revert "Fix the crash in d (#12)" (#14)'],
                         "fix, revert: reverts %s, 4 days after it" % self.repo.short(self.github))
        self.assertEqual(marks['Revert "Add coupons (#13)"'], "")
        self.assertEqual(marks['Revert "Fix the crash in d (#12)"'], "fix, words: fix, crash")
        self.assertEqual(marks['Revert "docs: say more"'], "not a fix: reverts a change that isn't to the code")
        self.assertEqual(marks['Revert "Reword the readme"'], "not a fix: reverts a change that isn't to the code")

    def test_a_revert_of_a_commit_before_the_window(self):
        repo = support.Repo("before")
        repo.commit("2026-01-01", "Start", {"a.py": lines(3, "a")})
        old = repo.commit("2026-01-02", "Speed up a", {"a.py": lines(4, "a")}, author=support.BOB)
        repo.commit("2026-01-03", "Add b", {"b.py": lines(4, "b")})
        repo.done()
        repo.commit("2026-03-04", 'Revert "Speed up a"\n\nThis reverts commit %s.\n' % repo.sha(old),
                    {"a.py": lines(3, "a")})
        repo.done()
        whole = support.run("heatmap.py", "-C", repo.path, "--show", "a.py")
        self.assertEqual(marks_of(whole.out)['Revert "Speed up a"'], "fix, revert: reverts %s, 2 months after it"
                         % repo.short(old))
        cut = support.run("heatmap.py", "-C", repo.path, "-n", "2", "--show", "a.py")
        self.assertEqual(marks_of(cut.out)['Revert "Speed up a"'], "fix, revert: reverts %s, from before the window"
                         % repo.short(old))
        header = fixes_lines(support.run("heatmap.py", "-C", repo.path, "-n", "2").out)
        self.assertEqual(header[0], "Fixes, a lead and not a verdict: at least 1 of the 2 commits fixed a defect in "
                                    "the project's own code, as their messages say: 1 a revert.")


class Diffs(unittest.TestCase):
    """--show FILE --diffs: a file's changes in several commits, under the name it had in each, cut at 60 lines."""

    @classmethod
    def setUpClass(cls):
        repo = cls.repo = support.Repo("diffs")
        first = "".join("a %d\n" % n for n in range(1, 101))
        repo.commit("2026-01-01", "Start", {"old/a.py": first, "img.png": b"\x00\x01\n", "other.py": "x\n"})
        fix = repo.commit("2026-01-02", "Fix a's first line", {"old/a.py": first.replace("a 1\n", "a one\n", 1),
                                                                 "other.py": "y\n", "img.png": b"\x00\x02\n"})
        moved = first.replace("a 1\n", "a one\n", 1).replace("a 50\n", "a fifty\n")
        move = repo.commit("2026-01-03", "Move a", {"new/a.py": moved}, rename={"old/a.py": "new/a.py"})
        rewrite = repo.commit("2026-01-04", "Rewrite a", {"new/a.py": "".join("b %d\n" % n for n in range(1, 101))})
        other = repo.commit("2026-01-05", "Change other", {"other.py": "z\n"})
        repo.done()
        cls.marks = dict(fix=fix, move=move, rewrite=rewrite, other=other)

    def test_a_files_changes_under_its_names_cut_at_sixty_lines(self):
        repo = self.repo
        shas = [repo.short(self.marks[m]) for m in ("fix", "move", "rewrite")]
        result = support.run("heatmap.py", "-C", repo.path, "--show", "new/a.py", "--diffs", ",".join(shas))
        self.assertEqual(result.code, 0, result)
        out = result.out.split("\n")
        self.assertEqual(out[0], "new/a.py: its changes in 3 of its commits, each cut at 60 lines")
        # Before the move, its changes as old/a.py, and nothing of other.py's or img.png's.
        self.assertEqual(out[1:7], ["  %s 2026-01-02 older  Fix a's first line  [fix, words: fix]" % shas[0],
                                    "      @@ -1,4 +1,4 @@", "      -a 1", "      +a one", "       a 2", "       a 3"])
        self.assertEqual(out[8:12], ["  %s 2026-01-03 newer  Move a" % shas[1], "      (rename from old/a.py)",
                                     "      @@ -47,7 +47,7 @@ a 46", "       a 47"])
        rewritten = out[out.index("  %s 2026-01-04 newer  Rewrite a" % shas[2]) + 1:-2]
        self.assertEqual(len(rewritten), 60)
        self.assertEqual(rewritten[-1], "      (142 more lines: git show %s -- new/a.py)" % shas[2])
        binary = support.run("heatmap.py", "-C", repo.path, "--show", "img.png", "--diffs", shas[0])
        self.assertIn("      (Binary files a/img.png and b/img.png differ)\n", binary.out)

    def test_the_lines_a_file_gives(self):
        # As file_diffs reads git show's output: one call for several commits, each commit's section of the file.
        heatmap = support.load("heatmap")
        fix, other = self.repo.sha(self.marks["fix"]), self.repo.sha(self.marks["other"])
        found = heatmap.file_diffs(self.repo.path, [(fix, "other.py", None), (other, "other.py", None),
                                                    (fix, "new/a.py", None)], most=3)
        self.assertEqual(found[(other, "other.py")], ["@@ -1 +1 @@", "-y", "+z"])
        self.assertEqual(found[(fix, "other.py")], ["@@ -1 +1 @@", "-x", "+y"])
        # In that commit new/a.py was old/a.py: under a name it didn't have, no change, not another file's.
        self.assertEqual(found[(fix, "new/a.py")], ["(no change to new/a.py in this commit)"])


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
        for path, kind in [("docs/conf.py", "documentation"), ("CHANGES.rst", "documentation"),
                           ("tests/test_app.py", "tests"), (".github/workflows/ci.yml", chore), ("go.mod", chore),
                           ("src/Makefile", chore), ("packages/core/package.json", chore), ("pyproject.toml", chore),
                           ("Dockerfile", chore), ("vite.config.ts", chore), ("src/app.py", None),
                           ("lib/build.py", None), ("src/server.c", None), ("ci/check.py", None)]:
            self.assertEqual(not_code(path, test), kind, path)

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

    def test_how_long(self):
        how_long = self.heatmap.how_long
        self.assertEqual([how_long(s) for s in (30, 600, 7200, 86400, 86400 * 45, 86400 * 400, 86400 * 900)],
                         ["1 minute", "10 minutes", "2 hours", "1 day", "45 days", "13 months", "2 years"])


if __name__ == "__main__":
    unittest.main()
