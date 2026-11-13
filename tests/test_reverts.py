"""heatmap.py's reading of reverts: a revert of another author's commit is a fix, of its own author's a withdrawal,
of a change to the docs or a chore no fix; a re-landing (Reapply "X", a revert of a revert) is nothing; a revert
without git's line reads by its own words, and one whose hash a rebase rewrote is found by its subject.
"""

import unittest

try:
    from . import support, test_fixes
except ImportError:
    import support
    import test_fixes

lines = support.lines
fixes_lines, marks_of = test_fixes.fixes_lines, test_fixes.marks_of


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

    def test_a_relanding_reads_as_nothing(self):
        marks = self.marks
        self.assertEqual(marks['Revert "Revert "Fix the crash in a""'], "not a fix: re-lands a change")
        self.assertEqual(marks['Revert "Revert "Add a hat to b""'], "not a fix: re-lands a change")
        # The reverts themselves: of another author's commits.
        self.assertEqual(marks['Revert "Fix the crash in a"'], "fix, revert: reverts %s, 4 days after it"
                         % self.repo.short(self.crash))
        self.assertEqual(marks['Revert "Add a hat to b"'], "fix, revert: reverts %s, 4 days after it"
                         % self.repo.short(self.hat))

    def test_a_relanding_whose_revert_is_outside_the_window(self):
        self.assertEqual(self.marks['Revert "Revert "Fix the crash in c""'], "not a fix: re-lands a change")
        self.assertEqual(self.marks['Revert "Revert "Add a hat""'], "not a fix: re-lands a change")

    def test_reverts_as_github_writes_them_and_without_their_line(self):
        marks = self.marks
        self.assertEqual(marks['Revert "Fix the crash in d (#12)" (#14)'],
                         "fix, revert: reverts %s, 4 days after it" % self.repo.short(self.github))
        # Without the line, only its words outside the quotes are read: the quoted ones are the reverted change's.
        self.assertEqual(marks['Revert "Add coupons (#13)"'], "")
        self.assertEqual(marks['Revert "Fix the crash in d (#12)"'], "")
        self.assertEqual(marks['Revert "docs: say more"'], "not a fix: reverts a change that isn't to the code")
        self.assertEqual(marks['Revert "Reword the readme"'], "not a fix: reverts a change that isn't to the code")

    def test_a_relanding_anywhere_in_a_chain_reads_as_nothing(self):
        # A revert of a revert re-lands a change, whatever it re-lands, as git's Reapply "X" does.
        repo = support.Repo("chain")
        repo.commit("2026-01-01", "Start", {"a.py": lines(3, "a"), "b.py": lines(3, "b")})
        land = repo.commit("2026-01-02", "Speed up the cart", {"a.py": lines(4, "a")}, author=support.BOB)
        other = repo.commit("2026-01-02", "Speed up b", {"b.py": lines(4, "b")})
        repo.done()
        quoted, target, marks = "Speed up the cart", land, {}
        for day, author in (("03", support.ANN), ("04", support.BOB), ("05", support.ANN), ("06", support.ANN)):
            quoted = 'Revert "%s"' % quoted
            target = marks[day] = repo.commit("2026-01-%s" % day, "%s\n\nThis reverts commit %s.\n" % (
                quoted, repo.sha(target)), {"a.py": lines(int(day), "a")}, author=author)
            repo.done()
        repo.commit("2026-01-07", 'Reapply "Speed up the cart"\n\nThis reverts commit %s.\n' % repo.sha(marks["03"]),
                    {"a.py": lines(7, "a")})
        repo.commit("2026-01-08", 'Revert "Speed up b"\n\nThis reverts commit %s.\n' % repo.sha(other),
                    {"b.py": lines(8, "b")}, author=support.BOB)
        repo.done()
        shown = marks_of(support.run("heatmap.py", "-C", repo.path, "--show", "a.py", "--show", "b.py").out)
        revert, cart = 'Revert "%s"', "Speed up the cart"
        self.assertEqual(shown[revert % cart], "fix, revert: reverts %s, 1 day after it" % repo.short(land))
        for subject in (revert % (revert % cart), revert % (revert % (revert % cart)),
                        revert % (revert % (revert % (revert % cart))), 'Reapply "Speed up the cart"'):
            self.assertEqual(shown[subject], "not a fix: re-lands a change", subject)
        header = fixes_lines(support.run("heatmap.py", "-C", repo.path).out)[0]
        self.assertTrue(header.endswith("2 reverts (of commits that had stood 1 day and 6 days)."), header)

    def test_a_revert_whose_hash_was_rewritten(self):
        # Rebased and merged, a revert names a hash the repo hasn't: the commit with its quoted subject is it.
        repo = support.Repo("rewritten")
        repo.commit("2026-01-01", "Start", {"a.py": lines(3, "a")})
        mine = repo.commit("2026-01-02", "Speed up a", {"a.py": lines(4, "a")})
        repo.done()
        repo.commit("2026-01-03", 'Revert "Speed up a"\n\nThis reverts commit %s.\n' % ("b" * 40),
                    {"a.py": lines(3, "a")})
        repo.done()
        marks = marks_of(support.run("heatmap.py", "-C", repo.path, "--show", "a.py").out)
        self.assertEqual(marks['Revert "Speed up a"'], "not a fix: its author withdraws %s" % repo.short(mine))

    def test_a_revert_of_a_commit_before_the_window(self):
        # Read from the repo, where the window doesn't reach it: who made it and when. One the repo hasn't, as a
        # shallow clone's, can't say whose change it undid, nor when, and isn't counted.
        repo = support.Repo("before")
        repo.commit("2026-01-01", "Start", {"a.py": lines(3, "a")})
        old = repo.commit("2026-01-02", "Speed up a", {"a.py": lines(4, "a")}, author=support.BOB)
        own = repo.commit("2026-01-03", "Add b", {"b.py": lines(4, "b")})
        repo.done()
        repo.commit("2026-03-04", 'Revert "Speed up a"\n\nThis reverts commit %s.\n' % repo.sha(old),
                    {"a.py": lines(3, "a")})
        repo.commit("2026-03-05", "Revert the new b\n\nThis reverts commit %s.\n" % repo.sha(own)[:10],
                    {"b.py": lines(3, "b")})
        repo.commit("2026-03-06", 'Revert "Speed up c"\n\nThis reverts commit %s.\n' % ("a" * 40),
                    {"a.py": lines(5, "a")})
        repo.done()
        whole = marks_of(support.run("heatmap.py", "-C", repo.path, "--show", "a.py").out)
        cut = marks_of(support.run("heatmap.py", "-C", repo.path, "-n", "3", "--show", "a.py", "--show", "b.py").out)
        for marks in (whole, cut):
            self.assertEqual(marks['Revert "Speed up a"'], "fix, revert: reverts %s, 2 months after it"
                             % repo.short(old))
            self.assertEqual(marks['Revert "Speed up c"'], "not a fix: reverts aaaaaaaaa, which isn't in the repo")
        self.assertEqual(cut["Revert the new b"], "not a fix: its author withdraws %s" % repo.short(own))
        header = fixes_lines(support.run("heatmap.py", "-C", repo.path, "-n", "3").out)
        self.assertEqual(header[0], "Fixes, a lead and not a verdict: at least 1 of the 3 commits fixed a defect in "
                                    "the project's own code, as their messages say: 1 a revert (of a commit that had "
                                    "stood 2 months). 1 more revert, of its author's own commit, withdraws it and "
                                    "isn't counted. 1 more revert, of a commit not in the repo, isn't counted.")


class Outside(unittest.TestCase):

    def test_a_reverted_commit_outside_the_window_is_read_without_its_changes(self):
        # Its author, time, subject and body are what the trace reads of it: not its numstat, nor renames.
        heatmap = support.load("heatmap")
        repo = support.Repo("outside")
        old = repo.commit("2026-01-01", "Speed up a", {"a.py": lines(3, "a")}, author=support.BOB)
        repo.done()
        repo.commit("2026-01-02", 'Revert "Speed up a"\n\nThis reverts commit %s.\n' % repo.sha(old),
                    {"a.py": lines(2, "a")})
        repo.done()
        window = heatmap.read_log(repo.path, ["-n", "1", "HEAD"])
        asked, git = [], heatmap.git
        heatmap.git = lambda path, *args: asked.append(args) or git(path, *args)
        try:
            found = heatmap.outside_window(repo.path, window, window)
        finally:
            heatmap.git = git
        self.assertEqual([c[0] for c in found.values()], [repo.sha(old)])
        self.assertNotIn("--numstat", asked[0])


class OneCommit(unittest.TestCase):

    def setUp(self):
        self.heatmap = support.load("heatmap")

    def test_a_revert_without_gits_line_reads_by_its_own_words(self):
        heatmap = self.heatmap
        commits = [("%040d" % n, n, subject, [("a.py", None, 1, 0)], "Ann <a@b>", "") for n, subject in enumerate(
            ['Revert "feat: add error handling page"', 'Reapply "feat: add error handling page"'])]
        trace = heatmap.fix_trace(commits, commits, True)
        self.assertEqual([trace[c[0]] for c in commits], [(0, "", None), (0, "re-lands a change", None)])

    def test_a_revert_says_so_at_its_subjects_start(self):
        # A squash merge of a feature about reverting, whose body carries a branch commit's revert line, isn't one.
        heatmap = self.heatmap
        land = ("1" * 40, 1, "Add the migrations", [("a.py", None, 1, 0)], "Bob <b@c>", "")
        merge = ("2" * 40, 2, "Add ability to revert a migration (#12)", [("a.py", None, 1, 0)], "Ann <a@b>",
                 "* Revert it\n\nThis reverts commit %s.\n" % land[0])
        self.assertEqual(heatmap.fix_trace([merge], [merge, land], False)[merge[0]], (0, "", None))

    def test_a_revert_after_the_issue_it_closes(self):
        # As Django writes one: Fixed #37 -- Reverted "...".
        heatmap = self.heatmap
        land = ("1" * 40, 1, "Fixed #36 -- Added a check", [("a.py", None, 1, 0)], "Bob <b@c>", "")
        back = ("2" * 40, 2, 'Fixed #37 -- Reverted "Fixed #36 -- Added a check".', [("a.py", None, 1, 0)],
                "Ann <a@b>", "This reverts commit %s.\n" % land[0])
        self.assertEqual(heatmap.fix_trace([back], [back, land], False)[back[0]], (1, "reverts 111111111", 1))

    def test_a_revert_of_several_commits(self):
        # A withdrawal only where every commit it names is its author's own; another's makes it a revert.
        heatmap = self.heatmap

        def commit(n, subject, author, body=""):
            return (str(n) * 40, n, subject, [("a.py", None, 1, 0)], author, body)
        own, others, again = commit(1, "Add a hat", "Ann <a@b>"), commit(2, "Add a cap", "Bob <b@c>"), \
            commit(3, "Add a scarf", "Ann <a@b>")
        both = commit(5, "Revert the hats", "Ann <a@b>", "This reverts commit %s.\nThis reverts commit %s.\n"
                      % (own[0], others[0]))
        mine = commit(6, "Revert the hats again", "Ann <a@b>", "This reverts commit %s.\nThis reverts commit %s.\n"
                      % (own[0], again[0]))
        trace = heatmap.fix_trace([both, mine], [mine, both, again, others, own], False)
        self.assertEqual(trace[both[0]], (1, "reverts 111111111, 222222222", 3))
        self.assertEqual(trace[mine[0]], (0, "its author withdraws 111111111, 333333333", None))

    def test_a_fix_type_outranks_what_the_reverted_commit_says(self):
        # Its author typed it a fix: so it reads, with git's line or without, though the commit it names is its
        # author's own or isn't in the repo. Where types aren't read as labels, the withdrawal stands.
        heatmap = self.heatmap

        def commit(n, subject, body=""):
            return (str(n) * 40, n, subject, [("a.py", None, 1, 0)], "Ann <a@b>", body)
        land = commit(1, "feat: add caching")
        back = commit(2, 'fix: revert "feat: add caching"', "This reverts commit %s.\n" % land[0])
        bare = commit(3, 'fix: revert "feat: add caching"')
        gone = commit(4, 'fix(cache): revert "feat: add logging"', "This reverts commit %s.\n" % ("9" * 40))
        typed = heatmap.fix_trace([back, bare, gone], [gone, bare, back, land], True)
        self.assertEqual([typed[c[0]] for c in (back, bare, gone)], [(2, "fix:", None), (2, "fix:", None),
                                                                    (2, "fix(cache):", None)])
        self.assertEqual(heatmap.fix_trace([back], [back, land], False)[back[0]],
                         (0, "its author withdraws 111111111", None))

    def test_a_revert_dated_before_the_commit_it_names(self):
        # As a rebase or a clock can date them: how long that commit stood isn't said, nor counted in the header.
        heatmap = self.heatmap

        def commit(n, stamp, subject, author, body=""):
            return (str(n) * 40, stamp, subject, [("a.py", None, 1, 0)], author, body)
        hat, cap = commit(1, 4000, "Add a hat", "Bob <b@c>"), commit(2, 0, "Add a cap", "Bob <b@c>")
        early = commit(3, 3600, 'Revert "Add a hat"', "Ann <a@b>", "This reverts commit %s.\n" % hat[0])
        later = commit(4, 7200, 'Revert "Add a cap"', "Ann <a@b>", "This reverts commit %s.\n" % cap[0])
        trace = heatmap.fix_trace([later, early], [later, hat, early, cap], False)
        self.assertEqual(trace[early[0]], (1, "reverts 111111111", None))
        self.assertEqual(heatmap.fix_mark(trace[early[0]]), "  [fix, revert: reverts 111111111]")
        lines, _ = heatmap.fix_summary([later, early], trace, 0.0)
        self.assertEqual(lines[0], "Fixes, a lead and not a verdict: at least 2 of the 2 commits fixed a defect in the "
                                   "project's own code, as their messages say: 2 reverts (of a commit that had stood "
                                   "2 hours).")

    def test_a_revert_of_a_commit_not_in_the_repo(self):
        # Whose change it undid can't be told, so it isn't counted, unless another commit it names is another's.
        heatmap = self.heatmap

        def commit(n, subject, author, body=""):
            return (str(n) * 40, n * 3600, subject, [("a.py", None, 1, 0)], author, body)
        own, others = commit(1, "Add a hat", "Ann <a@b>"), commit(2, "Add a cap", "Bob <b@c>")
        gone = "9" * 40
        alone = commit(5, "Revert the scarf", "Ann <a@b>", "This reverts commit %s.\n" % gone)
        mine = commit(6, "Revert the hat and the scarf", "Ann <a@b>", "This reverts commit %s.\nThis reverts "
                      "commit %s.\n" % (own[0], gone))
        theirs = commit(7, "Revert the cap and the scarf", "Ann <a@b>", "This reverts commit %s.\nThis reverts "
                        "commit %s.\n" % (others[0], gone))
        commits = [theirs, mine, alone]
        trace = heatmap.fix_trace(commits, commits + [others, own], False)
        self.assertEqual(trace[alone[0]], (0, "reverts 999999999, which isn't in the repo", None))
        self.assertEqual(trace[mine[0]], (0, "reverts 111111111, 999999999, of which 999999999 isn't in the repo",
                                          None))
        self.assertEqual(trace[theirs[0]], (1, "reverts 222222222, 999999999", 5 * 3600))
        self.assertEqual(heatmap.fix_mark(trace[alone[0]]), "  [not a fix: reverts 999999999, which isn't in the repo]")
        lines, _ = heatmap.fix_summary(commits, trace, 0.0)
        self.assertEqual(lines[0], "Fixes, a lead and not a verdict: at least 1 of the 3 commits fixed a defect in the "
                                   "project's own code, as their messages say: 1 a revert (of a commit that had stood "
                                   "5 hours). 2 more reverts, of commits not in the repo, aren't counted.")


if __name__ == "__main__":
    unittest.main()
