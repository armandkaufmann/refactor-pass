"""heatmap.py's fixes trace: which commits read as fixes from their messages, and where they landed.

The "shop" repo has no types in its subjects. Its commits, a day apart: features, fixes said in words (English
and Chinese), fixes that aren't (a typo, documentation only, an issue closed), a revert of another author's
commit, a revert of the author's own, and a squash merge whose body carries a revert from its branch. The
"typed" repo's subjects carry Conventional Commits types, a [tag] or a gitmoji.
"""

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
        "CHANGES.md": lines(2, "change"), "tests/test_app.py": lines(4, "test")})
    repo.commit("2026-01-02", "Add the cart", {"app.py": lines(12, "app")})
    marks["crash"] = repo.commit("2026-01-03", "Fix the crash when the cart is empty", {
        "app.py": lines(13, "app"), "tests/test_app.py": lines(6, "test"), "CHANGES.md": lines(3, "change")})
    repo.commit("2026-01-04", "Fix the guide's wrong example", {"docs/guide.md": lines(4, "guide")})
    repo.commit("2026-01-05", "Fix typo in a comment", {"util.py": lines(11, "util")})
    repo.commit("2026-01-06", "Fixed #12 -- Added coupons", {"app.py": lines(14, "app")})
    repo.commit("2026-01-07", "Rename fix_price to fixed_price", {"util.py": lines(12, "util")})
    repo.commit("2026-01-07", "Fix: bump left-pad", {"package.json": "{}\n"}, author=BOT)
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
    for line in out.splitlines()[1:]:
        match = re.match(r"  [0-9a-f]{9} \d{4}-\d{2}-\d{2} (.*?)(?:  \[(.*)\])?$", line)
        if match:
            found[match.group(1)] = match.group(2) or ""
    return found


class Shop(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.repo, cls.marks = build_shop()
        cls.result = support.run("heatmap.py", "-C", cls.repo.path)
        assert cls.result.code == 0, cls.result

    def test_the_header_says_how_many_read_as_fixes_and_how(self):
        # 15 commits counted (the bot's is left out): the crash, the negative total and the Chinese one by their
        # words, and the revert of Bob's commit. The guide's fix changed documentation only.
        self.assertEqual(fixes_lines(self.result.out), [
            "Fixes, a lead and not a verdict: 4 of the 15 commits read as fixes from their messages, 1 a revert (of "
            "a commit that had stood 1 day) and 3 by their words. 1 more revert, of its author's own commit, "
            "withdraws it and isn't counted.",
            "0% of the subjects carry a type, too few to read types as labels. 1 more commit closes an issue "
            "without saying what kind of change."])

    def test_fixes_by_file(self):
        # util.py: the negative total, the Chinese fix and the revert, all in the newer half (its 8 newest
        # commits). app.py: the crash, in the older half. Documentation and tests are aside.
        self.assertEqual(fix_rows(self.result.out), {"util.py": (3, 3, 1, 0, 2), "app.py": (1, 0, 0, 0, 1)})
        self.assertIn("Fixes by file: of each file's commits, those that read as fixes, and how many of them were in "
                      "the newer half (documentation and tests aside):\n", self.result.out)

    def test_the_table_of_files_is_as_it_was(self):
        rows = support.heatmap_rows(self.result.out)
        self.assertEqual((rows["util.py"]["commits"], rows["app.py"]["commits"]), (9, 6))

    def test_show_marks_each_commit(self):
        result = support.run("heatmap.py", "-C", self.repo.path, "--show", "util.py", "--show", "app.py",
                             "--show", "docs/guide.md")
        self.assertEqual(result.code, 0, result)
        marks = marks_of(result.out)
        self.assertEqual(marks['Revert "Speed up totals"'], "fix, revert: reverts %s, 1 day after it"
                         % self.repo.short(self.marks["speed"]))
        self.assertEqual(marks['Revert "Try a cache"'], "not a fix: its author withdraws %s"
                         % self.repo.short(self.marks["cache"]))
        self.assertEqual(marks["Prevent a negative total"], "fix, words: prevent")
        self.assertEqual(marks["修复价格计算错误的问题"], "fix, words: 修复, 错误, 问题")
        self.assertEqual(marks["Fix the crash when the cart is empty"], "fix, words: fix, crash")
        self.assertEqual(marks["Fix typo in a comment"], "not a fix: says typo")
        self.assertEqual(marks["Fix the guide's wrong example"], "not a fix: changes documentation only")
        # An issue closed, an identifier, words that start like fix, a squash merge's branch revert: nothing.
        for subject in ["Fixed #12 -- Added coupons", "Rename fix_price to fixed_price",
                        "Add the prefix and fixture helpers", "Make totals faster (#7)", "Add the cart", "Start"]:
            self.assertEqual(marks[subject], "", subject)

    def test_left_out_commits_dont_count(self):
        # The bot's "Fix: bump left-pad" is left out by default, so package.json has no fixes; and a fix left out
        # with --exclude-commits counts toward nothing.
        self.assertNotIn("package.json", fix_rows(self.result.out))
        result = support.run("heatmap.py", "-C", self.repo.path, "--exclude-commits",
                             self.repo.short(self.marks["crash"]))
        self.assertEqual(result.code, 0, result)
        self.assertTrue(fixes_lines(result.out)[0].startswith(
            "Fixes, a lead and not a verdict: 3 of the 14 commits read as fixes"), result.out)
        # 14 commits now, so the newer half is the 7 newest, which leaves out the negative total's fix.
        self.assertEqual(fix_rows(result.out), {"util.py": (3, 2, 1, 0, 2)})

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


def build_typed(subjects):
    """A repo whose commits, a day apart, each change app.py, with the subjects given."""
    repo = support.Repo("typed")
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
            "Fixes, a lead and not a verdict: 4 of the 11 commits read as fixes from their messages, 3 by their "
            "type and 1 by their words.",
            "91% of the subjects carry a type, so a type is read as a label."])
        self.assertEqual(fix_rows(heatmap.out), {"app.py": (4, 3, 0, 3, 1)})

    def test_types_read_as_words_where_few_subjects_carry_one(self):
        plain = ["Add the cart", "Add coupons", "Speed up totals", "Split the cart", "Tidy the totals", "Add a hat",
                 "Add a scarf", "Add shoes", "Add a coat", "Add gloves", "Add socks"]
        repo = build_typed(plain + ["fix(cart): the total ignores discounts", "docs: fix the docstring of total",
                                    "[fix] crash on an empty cart"])
        result = support.run("heatmap.py", "-C", repo.path, "--show", "app.py")
        marks = marks_of(result.out)
        self.assertEqual(marks["fix(cart): the total ignores discounts"], "fix, words: fix")
        self.assertEqual(marks["docs: fix the docstring of total"], "not a fix: says docs")
        self.assertEqual(marks["[fix] crash on an empty cart"], "fix, words: fix, crash")
        # 4 of the 15 subjects carry a type, with "feat: start".
        self.assertEqual(fixes_lines(support.run("heatmap.py", "-C", repo.path).out)[1],
                         "27% of the subjects carry a type, too few to read types as labels.")


class Reverts(unittest.TestCase):

    def test_a_revert_of_a_revert_reads_as_what_it_relands(self):
        repo = support.Repo("relands")
        repo.commit("2026-01-01", "Start", {"a.py": lines(3, "a"), "b.py": lines(3, "b")})
        crash = repo.commit("2026-01-02", "Fix the crash in a", {"a.py": lines(4, "a")})
        hat = repo.commit("2026-01-03", "Add a hat to b", {"b.py": lines(4, "b")}, author=support.BOB)
        repo.done()
        back = repo.commit("2026-01-04", 'Revert "Fix the crash in a"\n\nThis reverts commit %s.\n'
                           % repo.sha(crash), {"a.py": lines(3, "a")}, author=support.BOB)
        undo = repo.commit("2026-01-05", 'Revert "Add a hat to b"\n\nThis reverts commit %s.\n' % repo.sha(hat),
                           {"b.py": lines(3, "b")})
        repo.done()
        repo.commit("2026-01-06", 'Revert "Revert "Fix the crash in a""\n\nThis reverts commit %s.\n'
                    % repo.sha(back), {"a.py": lines(4, "a")})
        repo.commit("2026-01-07", 'Revert "Revert "Add a hat to b""\n\nThis reverts commit %s.\n'
                    % repo.sha(undo), {"b.py": lines(4, "b")}, author=support.BOB)
        repo.done()
        result = support.run("heatmap.py", "-C", repo.path, "--show", "a.py", "--show", "b.py")
        marks = marks_of(result.out)
        self.assertEqual(marks['Revert "Revert "Fix the crash in a""'], "fix, words: re-lands fix, crash")
        self.assertEqual(marks['Revert "Revert "Add a hat to b""'], "not a fix: re-lands a change that wasn't a fix")
        # The reverts themselves: of another author's commits, each a day after it.
        self.assertEqual(marks['Revert "Fix the crash in a"'], "fix, revert: reverts %s, 2 days after it"
                         % repo.short(crash))
        self.assertEqual(marks['Revert "Add a hat to b"'], "fix, revert: reverts %s, 2 days after it"
                         % repo.short(hat))

    def test_a_relanding_whose_revert_is_outside_the_window_reads_by_its_words(self):
        repo = support.Repo("relands-outside")
        repo.commit("2026-01-01", "Start", {"a.py": lines(3, "a")})
        repo.commit("2026-01-02", 'Revert "Revert "Fix the crash in a""\n\nThis reverts commit %s.\n' % ("d" * 40),
                    {"a.py": lines(4, "a")})
        repo.commit("2026-01-03", 'Revert "Revert "Add a hat""\n\nThis reverts commit %s.\n' % ("e" * 40),
                    {"a.py": lines(5, "a")})
        repo.done()
        marks = marks_of(support.run("heatmap.py", "-C", repo.path, "--show", "a.py").out)
        self.assertEqual(marks['Revert "Revert "Fix the crash in a""'], "fix, words: re-lands fix, crash")
        self.assertEqual(marks['Revert "Revert "Add a hat""'], "not a fix: re-lands a change that wasn't a fix")

    def test_reverts_as_github_writes_them_and_without_their_line(self):
        repo = support.Repo("github")
        repo.commit("2026-01-01", "Start", {"a.py": lines(3, "a")})
        crash = repo.commit("2026-01-02", "Fix the crash in a (#12)", {"a.py": lines(4, "a")}, author=support.BOB)
        coupons = repo.commit("2026-01-03", "Add coupons (#13)", {"a.py": lines(5, "a")}, author=support.BOB)
        repo.done()
        repo.commit("2026-01-04", 'Revert "Fix the crash in a (#12)" (#14)\n\nThis reverts commit %s.\n'
                    % repo.sha(crash), {"a.py": lines(6, "a")})
        # Without the line, a subject that starts with Revert reads by its words at most.
        repo.commit("2026-01-05", 'Revert "Add coupons (#13)"', {"a.py": lines(7, "a")})
        repo.commit("2026-01-06", 'Revert "Fix the crash in a (#12)"', {"a.py": lines(8, "a")})
        # A revert of a change to the docs, or of a chore, isn't a fix of the code.
        repo.commit("2026-01-07", 'Revert "docs: say more"\n\nThis reverts commit %s.\n' % repo.sha(coupons),
                    {"a.py": lines(9, "a")})
        repo.commit("2026-01-08", 'Revert "Reword the readme"\n\nThis reverts commit %s.\n' % ("f" * 40),
                    {"a.py": lines(10, "a")})
        repo.done()
        result = support.run("heatmap.py", "-C", repo.path, "--show", "a.py")
        marks = marks_of(result.out)
        self.assertEqual(marks['Revert "Fix the crash in a (#12)" (#14)'], "fix, revert: reverts %s, 2 days after it"
                         % repo.short(crash))
        self.assertEqual(marks['Revert "Add coupons (#13)"'], "")
        self.assertEqual(marks['Revert "Fix the crash in a (#12)"'], "fix, words: fix, crash")
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
        self.assertEqual(header[0], "Fixes, a lead and not a verdict: 1 of the 2 commits read as fixes from their "
                                    "messages, 1 a revert.")


class Thin(unittest.TestCase):

    def test_subjects_of_a_word_or_two_cant_support_the_trace(self):
        repo = build_typed(["wip", "update", "fix", "more", "Fix the crash in the cart", "stuff", "fix it", "Add a "
                            "hat to the shop"])
        result = support.run("heatmap.py", "-C", repo.path)
        self.assertEqual(result.code, 0, result)
        # 9 commits, 7 of them a word or two: "feat: start" carries a type, but few do, so its words count.
        self.assertEqual(fixes_lines(result.out)[1], "Most subjects here are a word or two (7 of the 9), too little "
                         "to tell a fix from anything else, so the fixes by file aren't listed. 11% of the subjects "
                         "carry a type, too few to read types as labels.")
        self.assertNotIn("Fixes by file", result.out)


class Words(unittest.TestCase):
    """The words read, one subject at a time."""

    def setUp(self):
        self.heatmap = support.load("heatmap")

    def test_fix_words_and_the_words_that_say_otherwise(self):
        says = self.heatmap.says
        self.assertEqual(says("Fix the crash, and an overflow"), (["fix", "crash", "overflow"], []))
        self.assertEqual(says("Fixed typos in the docs"), (["fix"], ["typo", "docs"]))
        self.assertEqual(says("Better error messages for vararg-table fields"), (["error"], ["error message"]))
        self.assertEqual(says("Prevented a CVE"), (["cve", "prevent"], []))
        self.assertEqual(says("修复注释中的错误"), (["修复", "错误"], ["注释"]))

    def test_issue_references_identifiers_and_code_say_nothing(self):
        says = self.heatmap.says
        for subject in ["Fixed #12 -- Added coupons", "Closes gh-7", "Add should_ignore_error", "Use `fix()` here",
                        "Call Data.Fix() now", "Rename isFixed", "Addressing Issue 1809", "Add the prefix fixture",
                        "Add a regression test for totals"]:
            self.assertEqual(says(subject), ([], []), subject)

    def test_types(self):
        type_of = self.heatmap.type_of
        self.assertEqual(type_of("fix(router)!: x"), ("fix", "fix(router)!:"))
        self.assertEqual(type_of("hotfix: x"), ("fix", "hotfix:"))
        self.assertEqual(type_of("Bugfix: x"), ("fix", "Bugfix:"))
        self.assertEqual(type_of("fix\uff1a\u4fee\u590d"), ("fix", "fix\uff1a"))
        self.assertEqual(type_of("fix(deps): bump x"), ("chore", "fix(deps):"))
        self.assertEqual(type_of("[Fix] x"), ("fix", "[Fix]"))
        self.assertEqual(type_of("[docs] x"), ("other", "[docs]"))
        self.assertEqual(type_of(":bug: x"), ("fix", ":bug:"))
        self.assertEqual(type_of("\U0001F680 release"), ("other", "\U0001F680"))
        self.assertEqual(type_of("feat: x"), ("other", "feat:"))
        self.assertIsNone(type_of("ignore: respect the filters"))  # An area, as ripgrep's, not a type.
        self.assertIsNone(type_of("Fix the crash"))

    @unittest.expectedFailure
    def test_one_person_by_name_or_email_but_not_by_an_empty_one(self):
        same = self.heatmap.same_person
        self.assertTrue(same("Ann Dev <ann@example.com>", "ann dev <ann@work.example>"))
        self.assertTrue(same("Ann <ann@example.com>", "Ann Dev <ANN@example.com>"))
        self.assertFalse(same("Ann Dev <ann@example.com>", "Bob Dev <bob@example.com>"))
        # A blank name, or a blank email, is no one's: two such authors aren't one person by it.
        self.assertFalse(same(" <ann@example.com>", " <bob@example.com>"))
        self.assertFalse(same("Ann Dev <>", "Bob Dev <>"))

    def test_how_long(self):
        how_long = self.heatmap.how_long
        self.assertEqual([how_long(s) for s in (30, 600, 7200, 86400, 86400 * 45, 86400 * 400, 86400 * 900)],
                         ["1 minute", "10 minutes", "2 hours", "1 day", "45 days", "13 months", "2 years"])


if __name__ == "__main__":
    unittest.main()
