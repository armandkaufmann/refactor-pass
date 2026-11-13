"""What heatmap.py leaves out of its window, and how --since sets the window.

Housekeeping bots' commits are left out and named with their counts; coding agents' commits count. The
identities are the ones these bots and agents really commit under.
"""

import hashlib
import json
import os
import re
import unittest
from datetime import datetime, timezone

try:
    from . import support
except ImportError:
    import support

lines = support.lines

DEPENDABOT = "dependabot[bot] <49699333+dependabot[bot]@users.noreply.github.com>"
RENOVATE = "renovate[bot] <29139614+renovate[bot]@users.noreply.github.com>"
ACTIONS = "github-actions[bot] <41898282+github-actions[bot]@users.noreply.github.com>"
PRE_COMMIT = "pre-commit-ci[bot] <66853113+pre-commit-ci[bot]@users.noreply.github.com>"
AGENTS = ["copilot-swe-agent[bot] <198982749+Copilot@users.noreply.github.com>",
          "Devin AI <158243242+devin-ai-integration[bot]@users.noreply.github.com>",
          "google-labs-jules[bot] <161369871+google-labs-jules[bot]@users.noreply.github.com>",
          "claude[bot] <209825114+claude[bot]@users.noreply.github.com>",
          "Cursor Agent <cursoragent@cursor.com>"]


class Bots(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        repo = support.Repo("bots")
        sizes = {"package.json": 3, "src/app.py": 5, "src/agent_work.py": 5, "CHANGELOG.md": 0}
        files = dict((path, lines(n)) for path, n in sizes.items() if n)
        repo.commit("2026-01-01", "Start", files)
        authors = [DEPENDABOT, AGENTS[0], RENOVATE, DEPENDABOT, AGENTS[1], ACTIONS, RENOVATE, AGENTS[2], DEPENDABOT,
                   AGENTS[3], PRE_COMMIT, RENOVATE, AGENTS[4], ACTIONS, DEPENDABOT, support.ANN, support.ANN]
        changes = {DEPENDABOT: "package.json", RENOVATE: "package.json", ACTIONS: "CHANGELOG.md",
                   PRE_COMMIT: "src/app.py", support.ANN: "src/app.py"}
        for day, author in enumerate(authors, start=2):
            path = changes.get(author, "src/agent_work.py")
            sizes[path] += 1
            repo.commit("2026-01-%02d" % day, "Change %s" % path, {path: lines(sizes[path])}, author=author)
        repo.done()
        cls.repo = repo.path
        cls.result = support.run("heatmap.py", "-C", repo.path)

    def test_housekeeping_bots_are_left_out_and_named(self):
        self.assertEqual(self.result.code, 0, self.result)
        self.assertIn("Window: 8 commits", self.result.out)
        self.assertIn("; left out: 10 by housekeeping bots (dependabot[bot] 4, renovate[bot] 3, github-actions[bot] "
                      "2, pre-commit-ci[bot] 1)\n", self.result.out)

    def test_coding_agents_count(self):
        rows = support.heatmap_rows(self.result.out)
        self.assertEqual(rows["src/agent_work.py"]["commits"], 6)  # Its first commit and the five agents'.
        self.assertEqual(rows["src/app.py"]["commits"], 3)  # Not pre-commit-ci's.
        self.assertEqual(rows["package.json"]["commits"], 1)
        self.assertNotIn("CHANGELOG.md", rows)  # Only a bot changed it.

    def test_page_names_the_bots(self):
        page = os.path.join(support.new_folder("page"), "p.html")
        support.run("heatmap.py", "-C", self.repo, "--page", page)
        with open(page, encoding="utf-8") as f:
            window = json.loads(support.block(f.read(), "heatmap"))["window"]
        self.assertEqual(window["bots"], [["dependabot[bot]", 4], ["renovate[bot]", 3], ["github-actions[bot]", 2],
                                          ["pre-commit-ci[bot]", 1]])
        self.assertEqual((window["excluded"], window["excluded_bots"]), (10, 10))

    def test_bot_adds_one(self):
        result = support.run("heatmap.py", "-C", self.repo, "--bot", "DEVIN")
        self.assertIn("Window: 7 commits", result.out)
        self.assertIn("left out: 11 by housekeeping bots (dependabot[bot] 4, renovate[bot] 3, github-actions[bot] 2, ",
                      result.out)
        self.assertIn("Devin AI 1", result.out)
        self.assertEqual(support.heatmap_rows(result.out)["src/agent_work.py"]["commits"], 5)

    def test_a_blank_bot_is_an_error(self):
        for value in ("", "  "):
            with self.subTest(value=value):
                result = support.run("heatmap.py", "-C", self.repo, "--bot", value)
                self.assertEqual(result.code, 2, result)
                self.assertIn("argument --bot: a bot's name can't be blank: it would match every commit", result.err)

    def test_keep_bots(self):
        result = support.run("heatmap.py", "-C", self.repo, "--keep-bots")
        self.assertIn("Window: 18 commits", result.out)
        self.assertNotIn("left out", result.out)
        rows = support.heatmap_rows(result.out)
        self.assertEqual((rows["package.json"]["commits"], rows["CHANGELOG.md"]["commits"]), (8, 2))


def twins(repo):
    """Two commits on HEAD whose hashes start with the same four characters, on branches of their own, found
    by trying messages: as many commits as a hash's first four characters can tell apart need only a few
    hundred tries to share them. Returns their hashes, in order."""
    tree = support.git(repo, "rev-parse", "HEAD^{tree}").strip()
    parent = support.git(repo, "rev-parse", "HEAD").strip()
    seen = {}
    for n in range(100000):
        body = ("tree %s\nparent %s\nauthor %s 1767268800 +0000\ncommitter %s 1767268800 +0000\n\nTry %d\n"
                % (tree, parent, support.ANN, support.ANN, n)).encode()
        sha = hashlib.sha1(b"commit %d\0" % len(body) + body).hexdigest()
        if sha[:4] in seen:
            pair = []
            for found in (seen[sha[:4]], body):
                made = support.git(repo, "hash-object", "-t", "commit", "-w", "--stdin", input=found).strip()
                support.git(repo, "branch", "twin-%d" % len(pair), made)
                pair.append(made)
            return sorted(pair)
        seen[sha[:4]] = body
    raise AssertionError("no two commits shared a prefix")


class Reformats(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        repo = support.Repo("reformat")
        cls.marks = marks = {}
        marks[1] = repo.commit("2026-01-01", "Start", {"src/a.py": lines(10, "a"), "src/b.py": lines(10, "b")})
        marks[2] = repo.commit("2026-01-02", "Reformat everything", {"src/a.py": lines(10, "A"),
                                                                     "src/b.py": lines(10, "B")})
        marks[3] = repo.commit("2026-01-03", "Grow a", {"src/a.py": lines(11, "A")})
        repo.done(checkout=False)
        ignore = "# Bulk reformats\n%s\n" % repo.sha(marks[2])
        marks[4] = repo.commit("2026-01-04", "List the reformat", {".git-blame-ignore-revs": ignore})
        marks[5] = repo.commit("2026-01-05", "Rename a variable everywhere", {"src/b.py": lines(10, "C")})
        marks[6] = repo.commit("2026-01-06", "Grow a again", {"src/a.py": lines(12, "A")})
        repo.done()
        cls.repo = repo

    def run_heatmap(self, *args):
        result = support.run("heatmap.py", "-C", self.repo.path, *args)
        self.assertEqual(result.code, 0, result)
        return result, support.heatmap_rows(result.out)

    def test_ignore_revs(self):
        result, rows = self.run_heatmap()
        self.assertIn("Window: 5 commits", result.out)
        self.assertIn("; left out: 1 in .git-blame-ignore-revs\n", result.out)
        self.assertEqual((rows["src/a.py"]["commits"], rows["src/b.py"]["commits"]), (3, 2))
        # A left-out commit counts toward nothing but growth, being two sizes.
        self.assertEqual((rows["src/a.py"]["churn"], rows["src/a.py"]["growth"]), (12, 12))

    def test_keep_ignore_revs(self):
        result, rows = self.run_heatmap("--keep-ignore-revs")
        self.assertIn("Window: 6 commits", result.out)
        self.assertNotIn("left out", result.out)
        self.assertEqual(rows["src/a.py"]["commits"], 4)

    def test_exclude_commits(self):
        result, rows = self.run_heatmap("--exclude-commits", self.repo.sha(self.marks[5])[:7])
        self.assertIn("; left out: 1 asked, 1 in .git-blame-ignore-revs\n", result.out)
        self.assertEqual(rows["src/b.py"]["commits"], 1)
        both = "%s,%s" % (self.repo.short(self.marks[2]), self.repo.short(self.marks[5]))
        result, rows = self.run_heatmap("--exclude-commits", both)
        self.assertIn("; left out: 2 asked\n", result.out)  # Asked first, so not counted twice.

    def test_an_asked_commit_by_a_tag_a_branch_or_in_capitals(self):
        support.git(self.repo.path, "tag", "-f", "rename-all", self.repo.sha(self.marks[5]))
        for value in ("rename-all", self.repo.sha(self.marks[5])[:9].upper(), "HEAD~1"):
            with self.subTest(value=value):
                result, rows = self.run_heatmap("--exclude-commits", value)
                self.assertIn("; left out: 1 asked, 1 in .git-blame-ignore-revs\n", result.out)
                self.assertEqual(rows["src/b.py"]["commits"], 1)

    def test_an_asked_commit_outside_the_window_is_named(self):
        result, _ = self.run_heatmap("-n", "2", "--exclude-commits", self.repo.short(self.marks[1]))
        self.assertNotIn("asked", result.out)
        self.assertEqual(result.err, "heatmap.py: --exclude-commits %s (%s, 2026-01-01) isn't in the window, so "
                                     "leaving it out changes nothing.\n" % (self.repo.short(self.marks[1]),
                                                                           self.repo.short(self.marks[1])))

    def test_an_asked_merge_is_named(self):
        repo = support.Repo("merged")
        start = repo.commit("2026-01-01", "Start", {"a.py": lines(3)})
        side = repo.commit("2026-01-02", "Side", {"b.py": lines(3)}, branch="side", parent=start)
        repo.commit("2026-01-03", "Main", {"a.py": lines(4)})
        merge = repo.commit("2026-01-04", "Merge side", {"b.py": lines(3)}, merge=side)
        repo.done()
        result = support.run("heatmap.py", "-C", repo.path, "--exclude-commits", repo.short(merge))
        self.assertEqual(result.code, 0, result)
        self.assertEqual(result.err, "heatmap.py: --exclude-commits %s (%s, 2026-01-04) is a merge, which the "
                                     "heatmap leaves out anyway.\n" % (repo.short(merge), repo.short(merge)))

    def test_a_value_that_names_no_commit_is_an_error(self):
        for value, why in (("c", "is too short to name a commit: give 7 or more characters of its hash"),
                           ("no-such-thing", "isn't a commit here: give a commit's hash, a tag or a branch"),
                           ("--all", "isn't a commit here: give a commit's hash, a tag or a branch"),
                           ("a..b", "isn't a commit here: give a commit's hash, a tag or a branch")):
            with self.subTest(value=value):
                result = support.run("heatmap.py", "-C", self.repo.path, "--exclude-commits=%s,HEAD" % value)
                self.assertEqual(result.code, 1, result)
                self.assertEqual(result.err, "heatmap.py: --exclude-commits %s %s.\n" % (value, why))
                self.assertEqual(result.out, "")

    def test_a_prefix_two_commits_share_is_an_error(self):
        repo = support.Repo("twins")
        repo.commit("2026-01-01", "Start", {"a.py": lines(3)})
        repo.done()
        first, second = twins(repo.path)
        result = support.run("heatmap.py", "-C", repo.path, "--exclude-commits", first[:4])
        self.assertEqual(result.code, 1, result)
        self.assertEqual(result.err, "heatmap.py: --exclude-commits %s names more than one commit here (%s and %s): "
                                     "give more characters of its hash.\n" % (first[:4], first[:9], second[:9]))

    def test_everything_left_out(self):
        result, _ = self.run_heatmap("-n", "1", "--exclude-commits", self.repo.short(self.marks[6]))
        self.assertEqual(result.out.strip(), "Nothing to count: the window's commit is left out: 1 asked. To count "
                                             "them, drop them from --exclude-commits.")
        result, _ = self.run_heatmap("-n", "2", "--exclude-commits", self.repo.short(self.marks[6]) + "," +
                                     self.repo.short(self.marks[5]))
        self.assertIn("the window's 2 commits are all left out: 2 asked.", result.out)


class Since(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        repo = support.Repo("since")
        cls.marks = marks = {}
        marks[1] = repo.commit("2026-01-01", "One", {"a.py": lines(3)})
        marks[2] = repo.commit("2026-01-02", "Two", {"a.py": lines(4)})
        marks[3] = repo.commit("2026-01-03", "Three", {"a.py": lines(5)})
        marks[10] = repo.commit("2026-01-10", "Ten", {"a.py": lines(6), "b.py": lines(2)})
        marks[11] = repo.commit("2026-01-11", "Eleven", {"b.py": lines(3)})
        repo.done()
        support.git(repo.path, "tag", "v1", repo.sha(marks[2]))
        cls.repo = repo

    def window(self, since):
        result = support.run("heatmap.py", "-C", self.repo.path, "--since", since)
        self.assertEqual(result.code, 0, result)
        return result, support.heatmap_rows(result.out)

    def test_a_tag(self):
        result, rows = self.window("v1")
        self.assertIn("Window: 3 commits, %s (2026-01-11) back to %s (2026-01-03)" % (
            self.repo.short(self.marks[11]), self.repo.short(self.marks[3])), result.out)
        self.assertEqual((rows["a.py"]["commits"], rows["a.py"]["growth"]), (2, 2))  # From 4 lines at v1.

    def test_growth_is_against_the_revision(self):
        result, _ = self.window("v1")
        self.assertIn("Growth is against %s (2026-01-02), just before the window.\n" % self.repo.short(self.marks[2]),
                      result.out)

    def test_a_commit(self):
        result, rows = self.window(self.repo.sha(self.marks[3])[:8])
        self.assertIn("Window: 2 commits", result.out)
        self.assertEqual(rows["a.py"]["growth"], 1)

    def test_a_date(self):
        result, rows = self.window("2026-01-06")
        self.assertIn("Window: 2 commits", result.out)
        # Before the window is the oldest commit's parent.
        self.assertEqual((rows["a.py"]["commits"], rows["a.py"]["growth"], rows["b.py"]["growth"]), (1, 1, 3))

    def refused(self, since):
        result = support.run("heatmap.py", "-C", self.repo.path, "--since", since)
        self.assertEqual((result.code, result.out), (1, ""), result)
        return result.err

    def test_a_bad_value(self):
        # git reads almost anything as a date, never as nothing; these it reads as 1969, now, and 1 May.
        for since in ("zzz-no-such-thing", "never", "a week ago", "1.5 days ago"):
            with self.subTest(since=since):
                self.assertEqual(self.refused(since), "--since %r is neither a revision here (a tag, branch or commit) "
                                 "nor a date in a form this reads, such as '3 months ago', 3.days.ago, yesterday, last "
                                 "week or 2026-06-01.\n" % since)

    def test_a_hash_that_isnt_here(self):
        # As a pass's recorded base after a rebase or a squash, or in another clone.
        for since in ("abc1234", "0123abc", "deadbeef1", "2025"):
            with self.subTest(since=since):
                self.assertEqual(self.refused(since), "--since %s names no commit here, as after a rebase or a squash, "
                                 "or in another clone. Give a commit, tag or branch that's here, or a date such as "
                                 "'3 months ago' or 2026-06-01.\n" % since)

    def test_a_tag_or_branch_that_isnt_here(self):
        for since in ("HEAD~3000000", "origin/mian2", "v1.9.0", "v3.2.0-rc1", "2.0.0", "1.2", "v9.9"):
            with self.subTest(since=since):
                self.assertEqual(self.refused(since), "--since %s names no commit, tag or branch here. Give one that's "
                                 "here, or a date such as '3 months ago' or 2026-06-01.\n" % since)

    def test_a_date_that_isnt_a_real_one(self):
        for since in ("2025-13-45", "2026-02-30", "2026-01-06 25:00", "13/45/2026"):
            with self.subTest(since=since):
                self.assertEqual(self.refused(since), "--since %s isn't a real date.\n" % since)

    def test_a_date_in_each_form_says_how_it_was_read(self):
        # A date with no time is read from the start of that day, local time, not at the time of day it is now.
        utc = datetime(2026, 1, 6, 12, 30, tzinfo=timezone.utc).astimezone().strftime("%Y-%m-%d %H:%M")
        for since, read in (("2026-01-06", "2026-01-06 00:00"), ("2026-1-6", "2026-01-06 00:00"),
                            ("2026-01-06 12:30", "2026-01-06 12:30"), ("2026-01-06T12:30:00", "2026-01-06 12:30"),
                            ("2026-01-06T12:30:00Z", utc), ("2026.01.06", "2026-01-06 00:00"),
                            ("01/06/2026", "2026-01-06 00:00"), ("06.01.2026", "2026-01-06 00:00")):
            with self.subTest(since=since):
                result, _ = self.window(since)
                self.assertIn("Window: 2 commits", result.out)
                self.assertIn("\n--since %s reads as %s, local time.\n" % (since, read), result.out)
        for since in ("1 minute ago", "30 seconds ago", "3.days.ago", "2 weeks 3 days ago", "two weeks ago",
                      "3 Months Ago", "yesterday", "last week", "last month", "now", "today"):
            with self.subTest(since=since):
                result, _ = self.window(since)
                self.assertRegex(result.out, r"^Nothing has landed since %s \(\d{4}-\d\d-\d\d \d\d:\d\d, local time\): "
                                             r"the window has no commits\.\n$" % re.escape(since))

    def test_an_empty_window(self):
        page = os.path.join(support.new_folder("page"), "2026-01-11.html")
        result = support.run("heatmap.py", "-C", self.repo.path, "--since", "HEAD", "--page", page)
        self.assertEqual(result.code, 0, result)
        self.assertEqual(result.out, "Nothing has landed since HEAD: the window has no commits.\n"
                                     "No heatmap to put on %s, so it isn't made.\n" % page)
        self.assertFalse(os.path.exists(page))
        support.write_text(page, "unchanged")
        result = support.run("heatmap.py", "-C", self.repo.path, "--since", "HEAD", "--page", page)
        self.assertIn("No heatmap to put on %s, so it's left as it was." % page, result.out)
        with open(page, encoding="utf-8") as f:
            self.assertEqual(f.read(), "unchanged")

    def test_a_window_of_only_a_passs_own_commits(self):
        repo = support.Repo("own-work")
        base = repo.commit("2026-01-01", "Start", {"a.py": lines(3)})
        first = repo.commit("2026-01-02", "Refactor one", {"a.py": lines(4)})
        second = repo.commit("2026-01-03", "Refactor two", {"a.py": lines(5)})
        repo.done()
        items = [{"id": "R1", "status": "done", "title": "One", "eases": "x", "smells": ["x"],
                  "cost": {"today": "2", "after": "1"}, "plan": ["x"], "files": ["a.py"], "size": "S", "risk": "Low",
                  "verify": "x", "commits": [repo.sha(first)[:7], repo.sha(second)], "outcome": "Done."}]
        repo.write(".refactor-pass/2026-01-01.html", support.page_with(checklist(items)))
        result = support.run("heatmap.py", "-C", repo.path, "--since", repo.sha(base)[:7])
        self.assertEqual(result.code, 0, result)
        self.assertEqual(result.out, "Nothing else has landed since %s: the window's 2 commits are all left out: 2 "
                                     "recorded on refactor checklists. To count them, --keep-pass-commits.\n"
                         % repo.sha(base)[:7])
        kept = support.run("heatmap.py", "-C", repo.path, "--since", repo.sha(base)[:7], "--keep-pass-commits")
        self.assertIn("Window: 2 commits", kept.out)


def checklist(items, started="2026-01-01"):
    """A pass block with the given items, the rest filled in."""
    return {"project": "x", "started": started, "base": "abc1234", "updated": started, "summary": "A pass.",
            "checks": ["the tests"], "earlier": None, "items": items, "left_alone": [], "log": []}



class InTime(unittest.TestCase):
    """Where the window sits in time: what day it is, how old the newest commit is, and how long the window
    spans; and, where nothing has landed for over three months, that the work it counts has gone quiet. The day
    is REFACTOR_PASS_NOW's, a Unix time, which the suite sets; else the clock's."""

    @classmethod
    def setUpClass(cls):
        repo = cls.repo = support.Repo("in-time")
        repo.commit("2026-01-01", "Start", {"src/a.py": lines(3), "docs/guide.md": lines(2)})
        for day in range(2, 11):
            repo.commit("2026-01-%02d" % day, "Change a on day %d" % day, {"src/a.py": lines(2 + day)})
        repo.commit("2026-03-01", "Change the guide", {"docs/guide.md": lines(3)})
        repo.done()

    def said(self, day, *args):
        """The header's lines on time, as of noon UTC on day (None: the clock's time)."""
        result = support.run("heatmap.py", "-C", self.repo.path, *args,
                             env={"REFACTOR_PASS_NOW": "" if day is None else str(support.stamp(day))})
        self.assertEqual(result.code, 0, result)
        found = result.out.split("\n")
        start = [i for i, line in enumerate(found) if line.startswith("Today is ")]
        self.assertEqual(len(start), 1, result.out)
        return found[start[0]:start[0] + 2]

    def test_the_newest_commits_age_and_the_windows_span(self):
        today = "Today is %s: the newest commit is " % support.local_day(support.stamp("2026-03-03"))
        self.assertEqual(self.said("2026-03-03")[0], today + "2 days old, and the window spans 59 days.")

    def test_nothing_landed_for_over_three_months(self):
        self.assertEqual(self.said("2026-11-13"), [
            "Today is %s: the newest commit is 8 months old, and the window spans 59 days." % support.local_day(
                support.NOW), "Nothing has landed for over three months: the work it counts has gone quiet."])
        self.assertFalse(self.said("2026-05-29")[1].startswith("Nothing"))  # 89 days.

    def test_a_quiet_scope(self):
        # Where the newest commit didn't change the scope, the newest that did is said too, and judged.
        said = self.said("2026-03-03", "src")
        self.assertEqual(said[0], "Today is %s: the newest commit is 2 days old, and the newest to change the "
                                  "scope 52 days old; the window spans 59 days." % support.local_day(
                                      support.stamp("2026-03-03")))
        self.assertFalse(said[1].startswith("Nothing"), said)
        self.assertEqual(self.said("2026-04-15", "src")[1], "Nothing has landed in the scope for over three months: "
                                                           "the work it counts there has gone quiet.")
        self.assertEqual(self.said("2026-03-03", "docs")[0], "Today is %s: the newest commit is 2 days old, and "
                         "the window spans 59 days." % support.local_day(support.stamp("2026-03-03")))

    def test_the_clocks_day_where_none_is_given(self):
        before = datetime.now().strftime("%Y-%m-%d")
        said = self.said(None)[0]
        self.assertIn(said[len("Today is "):len("Today is 2026-11-13")], (before, datetime.now().strftime("%Y-%m-%d")))

    def test_the_page_carries_it(self):
        page = os.path.join(support.new_folder("in-time"), "p.html")
        for args, scope_newest, quiet in (([], None, True), (["src"], "2026-01-10", True)):
            result = support.run("heatmap.py", "-C", self.repo.path, "--page", page, *args)
            self.assertEqual(result.code, 0, result)
            with open(page, encoding="utf-8") as f:
                window = json.loads(support.block(f.read(), "heatmap"))["window"]
            self.assertEqual(window["today"], support.local_day(support.NOW))
            self.assertEqual(window["quiet"], quiet)
            self.assertEqual((window["scope_newest"] or {}).get("date"), scope_newest and support.local_day(
                support.stamp(scope_newest)))


if __name__ == "__main__":
    unittest.main()
