"""heatmap.py's checklists: --checklists, --page, the commits recorded on checklists, linked worktrees, a
copy of the skill kept in a repo, and that a run writes nothing but the page and its .gitignore.
"""

import json
import os
import unittest
from datetime import datetime

try:
    from . import support
except ImportError:
    import support

lines = support.lines
FOLDER = ".refactor-pass"


def refactor(ident, status="todo", commits=(), outcome=""):
    return {"id": ident, "status": status, "title": "Name the states", "eases": "adding a state",
            "smells": ["Hidden State Machine"], "cost": {"today": "5 files", "after": "1 file"}, "plan": ["Pin it"],
            "files": ["src/a.py"], "size": "S", "risk": "Low", "verify": "the tests", "commits": list(commits),
            "outcome": outcome}


def checklist(items, started="2026-01-20", updated=None, base="abc1234"):
    return {"project": "pass", "started": started, "base": base, "updated": updated or started,
            "summary": "A pass.", "checks": ["the tests"], "earlier": None, "items": items, "left_alone": [],
            "log": []}


def today():
    return datetime.now().strftime("%Y-%m-%d")


def build(name="pass"):
    repo = support.Repo(name)
    marks = {}
    marks[1] = repo.commit("2026-01-01", "Start", {"src/a.py": lines(5), "src/b.py": lines(5)})
    marks[2] = repo.commit("2026-01-02", "Change a", {"src/a.py": lines(6)})
    marks[3] = repo.commit("2026-01-03", "Refactor b", {"src/b.py": lines(4)})
    repo.done()
    return repo, marks


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class Listing(unittest.TestCase):

    def test_none(self):
        repo, _ = build()
        result = support.run("heatmap.py", "-C", repo.path, "--checklists")
        self.assertEqual(result.code, 0, result)
        self.assertEqual(result.out, "No checklist yet: none in %s.\nA new pass gets a new checklist: --page %s makes "
                                     "it in %s (today's date).\n" % (
                                         FOLDER + os.sep, os.path.join(FOLDER, today() + ".html"), FOLDER + os.sep))

    def test_newest_first_by_name_not_by_time(self):
        repo, _ = build()
        names = ["2026-01-05.html", "2026-01-05-2.html", "2026-01-05-10.html", "2026-01-10.html", "notes.html",
                 "broken.html"]
        for n, name in enumerate(names):
            if name == "broken.html":
                path = repo.write(FOLDER + "/" + name, support.page_with(pass_json="{ not json"))
            else:
                started = "2026-01-07" if name == "notes.html" else name[:10]
                path = repo.write(FOLDER + "/" + name, support.page_with(checklist(
                    [refactor("R1")], started=started, updated="2026-01-12")))
            os.utime(path, (1700000000 + 1000 * (len(names) - n),) * 2)  # The oldest name is the newest file.
        result = support.run("heatmap.py", "-C", repo.path, "--checklists")
        self.assertEqual(result.code, 0, result)
        listed = [line.split(":")[0].strip() for line in result.out.splitlines() if line.startswith("  ")]
        self.assertEqual(listed, [os.path.join(FOLDER, n) for n in ("2026-01-10.html", "notes.html",
                                                                     "2026-01-05-10.html", "2026-01-05-2.html",
                                                                     "2026-01-05.html", "broken.html")])
        self.assertIn("  %s: started 2026-01-10, updated 2026-01-12, from abc1234; refactors 1 (1 todo)\n"
                      % os.path.join(FOLDER, "2026-01-10.html"), result.out)
        self.assertIn("  %s: its pass block doesn't parse; check_page.py says where.\n"
                      % os.path.join(FOLDER, "broken.html"), result.out)
        self.assertIn("The newest is %s.\n" % os.path.join(FOLDER, "2026-01-10.html"), result.out)

    def test_the_first_free_name_today(self):
        repo, _ = build()
        repo.write(FOLDER + "/%s.html" % today(), support.page_with(checklist([], started=today())))
        result = support.run("heatmap.py", "-C", repo.path, "--checklists")
        self.assertIn("A new pass gets a new checklist: --page %s makes it in %s (today's date, and a number, since "
                      "today already has one)." % (os.path.join(FOLDER, today() + "-2.html"), FOLDER + os.sep),
                      result.out)
        repo.write(FOLDER + "/%s-2.html" % today(), support.page_with(checklist([], started=today())))
        result = support.run("heatmap.py", "-C", repo.path, "--checklists")
        self.assertIn("--page %s makes it" % os.path.join(FOLDER, today() + "-3.html"), result.out)
        self.assertIn("no items yet", result.out)


class Pages(unittest.TestCase):

    def test_making_and_refreshing_a_page(self):
        repo, marks = build()
        relative = FOLDER + "/2026-01-20.html"
        page = os.path.join(repo.path, FOLDER, "2026-01-20.html")
        made = support.run("heatmap.py", "-C", repo.path, "--page", relative)
        self.assertEqual(made.code, 0, made)
        self.assertTrue(support.slashes(made.out).startswith(support.slashes(
            "Made %s, with the heatmap. Wrote a .gitignore beside it, so git leaves the checklists out of commits.\n\n"
            % page)), made.out)
        self.assertEqual(read(os.path.join(repo.path, FOLDER, ".gitignore")),
                         "# Written by the refactor-pass skill: keeps its checklists out of commits.\n*\n")
        text = read(page)
        data = support.block(text, "pass")
        self.assertEqual(json.loads(data), {"project": "pass", "started": "2026-01-20", "base": repo.short(marks[3]),
                                            "updated": "2026-01-20", "summary": "", "checks": [], "earlier": None,
                                            "items": [], "left_alone": [], "log": []})
        checked = support.run("check_page.py", page)
        self.assertEqual(checked.code, 0, checked)
        self.assertIn("warning: The pass block isn't written yet", checked.out)

        # The pass is written, its work recorded; a refresh changes the heatmap block and nothing else.
        written = support.page_with(checklist([refactor("R1", "done", [repo.short(marks[3])], "Done.")],
                                              base=repo.short(marks[3])), template=page)
        written = written.replace(support.block(written, "heatmap"), support.block(text, "heatmap"))
        support.write_text(page, written)
        refreshed = support.run("heatmap.py", "-C", repo.path, "--page", relative)
        self.assertEqual(refreshed.code, 0, refreshed)
        self.assertIn("Updated the heatmap on %s, and nothing else: it's the checklist started 2026-01-20 from %s, "
                      "with refactors 1 (1 done). A new pass needs a checklist of its own: --page %s.\n" % (
                          os.path.join(FOLDER, "2026-01-20.html"), repo.short(marks[3]),
                          os.path.join(FOLDER, today() + ".html")), refreshed.out)
        after = read(page)
        self.assertEqual(support.block(after, "pass"), support.block(written, "pass"))
        heat_before, heat_after = support.block(written, "heatmap"), support.block(after, "heatmap")
        self.assertEqual(after.replace(heat_after, ""), written.replace(heat_before, ""))
        self.assertNotEqual(heat_before, heat_after)  # The recorded commit is left out now.
        self.assertIn("left out: 1 recorded on refactor checklists", refreshed.out)

    def test_nothing_is_written_but_the_page_and_its_gitignore(self):
        repo, _ = build()
        before = sorted(os.listdir(support.SCRIPTS))
        for args in (["--page", FOLDER + "/2026-01-20.html"], ["--checklists"], []):
            support.run("heatmap.py", "-C", repo.path, *args)
        support.run("measure.py", "-C", repo.path)
        self.assertEqual(support.git(repo.path, "status", "--porcelain"), "")
        self.assertEqual(support.git(repo.path, "status", "--porcelain", "--ignored"), "!! %s/\n" % FOLDER)
        self.assertEqual(sorted(os.listdir(os.path.join(repo.path, FOLDER))), [".gitignore", "2026-01-20.html"])
        self.assertEqual(sorted(os.listdir(support.SCRIPTS)), before)

    def test_no_gitignore_where_the_folder_holds_tracked_files(self):
        repo = support.Repo("tracked")
        repo.commit("2026-01-01", "Start", {"a.py": lines(3), FOLDER + "/old.html": "<p>kept</p>\n"})
        repo.done()
        result = support.run("heatmap.py", "-C", repo.path, "--page", FOLDER + "/2026-01-20.html")
        self.assertEqual(result.code, 0, result)
        folder = os.path.join(repo.path, FOLDER)
        self.assertIn("%s holds files git tracks, so it's left without a .gitignore: new checklists in it will show in "
                      "git status." % folder, result.out)
        self.assertFalse(os.path.exists(os.path.join(folder, ".gitignore")))

    @unittest.skipIf(support.WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "a folder can't be made unwritable here")
    def test_a_folder_that_cant_be_written(self):
        repo, _ = build()
        folder = os.path.join(repo.path, FOLDER)
        os.makedirs(folder)
        os.chmod(folder, 0o555)
        try:
            if os.access(folder, os.W_OK):
                self.skipTest("the folder is still writable")
            result = support.run("heatmap.py", "-C", repo.path, "--page", FOLDER + "/2026-01-20.html")
        finally:
            os.chmod(folder, 0o755)
        self.assertEqual(result.code, 1, result)
        self.assertIn("Couldn't write %s: Permission denied.\nIf a sandbox keeps you out of that folder, ask the user "
                      "to let you write there, or give --page a path you can write and tell them where it is."
                      % os.path.join(folder, "2026-01-20.html"), result.err)


    def test_a_page_that_isnt_utf_8(self):
        repo, _ = build()
        page = repo.write(FOLDER + "/2026-01-20.html", support.page_with().encode("utf-8").replace(b"<title>",
                                                                                                    b"<title>\xff"))
        with open(page, "rb") as f:
            before = f.read()
        result = support.run("heatmap.py", "-C", repo.path, "--page", FOLDER + "/2026-01-20.html")
        self.assertEqual(result.code, 1, result)
        self.assertEqual(result.out, "")
        self.assertEqual(result.err, "heatmap.py: couldn't read %s, so it's left as it was: it isn't UTF-8 text, at "
                                     "byte %d. check_page.py says the same.\n" % (page, before.index(b"\xff")))
        with open(page, "rb") as f:
            self.assertEqual(f.read(), before)


    @unittest.skipIf(support.WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0),
                     "a file can't be made unreadable here")
    def test_a_page_that_cant_be_read(self):
        repo, _ = build()
        page = repo.write(FOLDER + "/2026-01-20.html", support.page_with())
        os.chmod(page, 0)
        try:
            result = support.run("heatmap.py", "-C", repo.path, "--page", FOLDER + "/2026-01-20.html")
        finally:
            os.chmod(page, 0o644)
        self.assertEqual(result.code, 1, result)
        self.assertIn("heatmap.py: couldn't read %s, so it's left as it was: Permission denied.\n" % page, result.err)
        self.assertNotIn("bug", result.err)


class HtmlInText(unittest.TestCase):
    """What heatmap.py writes into a page's data blocks holds no <, which a browser could read as HTML: a commit's
    subject or the project's name can hold <!-- and <script."""

    def test_a_subject_with_html(self):
        repo = support.Repo("html")
        for day, subject in ((1, "odd names <!-- <script>alert(1)</script>"), (2, "Plain"),
                             (3, "odd names <!-- <script>alert(1)</script>")):
            repo.commit("2026-01-%02d" % day, subject, {"a.py": lines(day + 2)})
        repo.done()
        page = os.path.join(support.new_folder("page"), "2026-01-20.html")
        result = support.run("heatmap.py", "-C", repo.path, "--page", page)
        self.assertEqual(result.code, 0, result)
        with open(page, encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn("<", support.block(text, "heatmap"))
        self.assertEqual(json.loads(support.block(text, "heatmap"))["window"]["newest"]["subject"],
                         "odd names <!-- <script>alert(1)</script>")
        checked = support.run("check_page.py", page)
        self.assertEqual(checked.code, 0, checked)

    @unittest.skipIf(support.WINDOWS, "a folder's name can't hold < on Windows")
    def test_a_project_named_with_html(self):
        repo = support.Repo("a<!--<script>b")
        repo.commit("2026-01-01", "Start", {"a.py": lines(3)})
        repo.done()
        page = os.path.join(support.new_folder("page"), "2026-01-20.html")
        result = support.run("heatmap.py", "-C", repo.path, "--page", page)
        self.assertEqual(result.code, 0, result)
        with open(page, encoding="utf-8") as f:
            text = f.read()
        self.assertNotIn("<", support.block(text, "pass"))
        self.assertEqual(json.loads(support.block(text, "pass"))["project"], "a<!--<script>b")


    def test_a_checklist_a_browser_reads_is_read(self):
        # Its </script> is hidden from a browser by the <!-- and <script before it, so the block goes on.
        repo, marks = build()
        repo.write(FOLDER + "/2026-01-20.html", support.page_with(checklist(
            [refactor("R1", "done", [repo.short(marks[3])], "Done: dropped `<!-- <script> </script>` from it.")])))
        result = support.run("heatmap.py", "-C", repo.path)
        self.assertEqual(result.err, "")
        self.assertIn("; left out: 1 recorded on refactor checklists\n", result.out)


class RecordedCommits(unittest.TestCase):

    def test_recorded_commits_are_left_out(self):
        repo, marks = build()
        repo.write(FOLDER + "/2026-01-20.html", support.page_with(checklist(
            [refactor("R1", "done", [repo.short(marks[3])], "Done.")])))
        result = support.run("heatmap.py", "-C", repo.path)
        self.assertIn("Window: 2 commits", result.out)
        self.assertIn("; left out: 1 recorded on refactor checklists\n", result.out)
        self.assertEqual(support.heatmap_rows(result.out)["src/b.py"]["commits"], 1)
        kept = support.run("heatmap.py", "-C", repo.path, "--keep-pass-commits")
        self.assertIn("Window: 3 commits", kept.out)
        self.assertEqual(support.heatmap_rows(kept.out)["src/b.py"]["commits"], 2)

    def test_a_hash_that_isnt_reachable(self):
        repo, marks = build()
        side = repo.commit("2026-01-04", "Not merged", {"src/c.py": lines(2)}, branch="side", parent=repo.sha(marks[3]))
        repo.done()
        repo.write(FOLDER + "/2026-01-20.html", support.page_with(checklist(
            [refactor("R1", "done", ["deadbee"], "Done."), refactor("R2", "done", [repo.sha(side)], "Done.")])))
        result = support.run("heatmap.py", "-C", repo.path)
        self.assertEqual(result.code, 0, result)
        page = os.path.join(FOLDER, "2026-01-20.html")
        self.assertIn("%s, R1: deadbee isn't reachable from HEAD. If that work was squash-merged or rebased onto this "
                      "branch, the heatmap counts it under the hash that landed it: record that hash instead. If it's "
                      "on a branch not merged yet, none of it is counted here.\n" % page, result.err)
        self.assertIn("%s, R2: %s isn't reachable from HEAD." % (page, repo.sha(side)), result.err)
        self.assertIn("Window: 3 commits", result.out)

    def test_an_unreadable_checklist(self):
        repo, _ = build()
        repo.write(FOLDER + "/2026-01-20.html", support.page_with(pass_json='{"items": [}'))
        result = support.run("heatmap.py", "-C", repo.path)
        self.assertEqual(result.code, 0, result)
        self.assertIn("Couldn't read the items of %s, so its commits are counted; check_page.py says why."
                      % os.path.join(FOLDER, "2026-01-20.html"), result.err)


class Worktrees(unittest.TestCase):

    def test_a_linked_worktree(self):
        repo, marks = build()
        tree = os.path.join(support.new_folder("worktree"), "feature")
        support.git(repo.path, "worktree", "add", "-q", "-b", "feature", tree)
        result = support.run("heatmap.py", "-C", tree, "--page", FOLDER + "/2026-01-21.html")
        self.assertEqual(result.code, 0, result)
        main_folder = os.path.join(repo.path, FOLDER)
        page = os.path.join(main_folder, "2026-01-21.html")
        self.assertTrue(os.path.exists(page))
        self.assertFalse(os.path.exists(os.path.join(tree, FOLDER)))
        out = support.slashes(result.out)
        self.assertIn(support.slashes("Made %s, with the heatmap." % page), out)
        self.assertIn(support.slashes("This is a linked worktree, so a relative --page path is written in the main "
                                      "checkout's %s, which outlives it." % main_folder), out)

        # A checklist kept in the worktree is read from the main checkout too.
        support.write_text(os.path.join(tree, FOLDER, "2026-01-22.html"), support.page_with(checklist(
            [refactor("R1", "done", [repo.short(marks[3])], "Done.")], started="2026-01-22")))
        result = support.run("heatmap.py", "-C", repo.path)
        self.assertIn("; left out: 1 recorded on refactor checklists\n", result.out)
        self.assertIn(support.slashes("The checklists in %s are read too." % os.path.join(tree, FOLDER)),
                      support.slashes(result.out))
        listed = support.run("heatmap.py", "-C", repo.path, "--checklists")
        self.assertIn(support.slashes("  %s: started 2026-01-22" % os.path.join(tree, FOLDER, "2026-01-22.html")),
                      support.slashes(listed.out))
        self.assertIn("  %s: started 2026-01-21" % os.path.join(FOLDER, "2026-01-21.html"), listed.out)
        from_tree = support.run("heatmap.py", "-C", tree, "--checklists")
        self.assertIn(support.slashes("The newest is %s." % os.path.join(tree, FOLDER, "2026-01-22.html")),
                      support.slashes(from_tree.out))


SKILL_FILES = ["SKILL.md", "scripts/heatmap.py", "scripts/scoping.py", "scripts/measure.py", "references/smells.md",
               "tests/test_heatmap.py", "tests/samples/functions/a.ts", "tests/support.py"]


class VendoredCopy(unittest.TestCase):
    """A copy of the skill committed into a project, as its README's per-project install makes one, tests and
    all: built here from a few lines per file, since its files are known by their names."""

    @classmethod
    def setUpClass(cls):
        repo = support.Repo("project")
        copy = ".agents/skills/refactor-pass/"
        files = dict((copy + path, "def f():\n" + "    x = 1\n" * 300) for path in SKILL_FILES)
        files["src/app.py"] = lines(5)
        for day in range(1, 7):
            files = dict((path, text + "x = %d\n" % day) for path, text in files.items())
            repo.commit("2026-01-%02d" % day, "Change everything", files)
        repo.done()
        cls.repo = repo.path
        cls.copy = copy

    def test_the_heatmap_leaves_it_out(self):
        result = support.run("heatmap.py", "-C", self.repo)
        self.assertEqual(result.code, 0, result)
        self.assertIn("This skill's own files, in %s, are left out; a scope naming that folder counts them."
                      % self.copy, result.out)
        self.assertEqual(list(support.heatmap_rows(result.out)), ["src/app.py"])
        self.assertIn("Test files: none in the scope changed in the window.", result.out)
        self.assertNotIn("maybe not", result.out)
        named = support.run("heatmap.py", "-C", self.repo, self.copy.rstrip("/"))
        self.assertIn(self.copy + "scripts/heatmap.py", support.heatmap_rows(named.out))
        self.assertIn("Test files: 3 changed in the window", named.out)

    def test_measure_leaves_it_out(self):
        result = support.run("measure.py", "-C", self.repo)
        self.assertEqual(result.code, 0, result)
        self.assertIn("This skill's own files, in %s, are left out; a scope naming that folder measures them."
                      % self.copy, result.out)
        self.assertIn("Test files: none in the scope.", result.out)
        self.assertNotIn(self.copy + "scripts", result.out)
        named = support.run("measure.py", "-C", self.repo, self.copy)
        self.assertIn(self.copy + "scripts/heatmap.py", named.out)
        self.assertIn("Test files: 3 set aside", named.out)

    def test_own_folders(self):
        scoping = support.load("scoping")
        tracked = [self.copy + p for p in SKILL_FILES] + ["src/app.py"]
        self.assertEqual(scoping.own_folders(tracked, []), [self.copy.rstrip("/")])
        self.assertEqual(scoping.own_folders(tracked, [self.copy.rstrip("/")]), [])
        kept, folders = scoping.leave_own_out(tracked, tracked, [])
        self.assertEqual((kept, folders), (["src/app.py"], [self.copy.rstrip("/")]))
        # The skill's own repo keeps them all, with its files at the top or in skills/refactor-pass.
        self.assertEqual(scoping.own_folders(SKILL_FILES, []), [])
        source = ["skills/refactor-pass/" + p for p in SKILL_FILES if not p.startswith("tests/")]
        self.assertEqual(scoping.own_folders(source + ["README.md", "tests/support.py"], []), [])
        # A copy there that an installer made, as its record says, is a copy; so is one anywhere else.
        recorded = source + ["skills/refactor-pass/.install.json"]
        self.assertEqual(scoping.own_folders(recorded, []), ["skills/refactor-pass"])
        vendored = ["vendor/" + p for p in source] + [self.copy + ".install.json"]
        self.assertEqual(scoping.own_folders(vendored, []), ["vendor/skills/refactor-pass"])


class SourceRepo(unittest.TestCase):
    """The skill's own repo, with the skill in skills/refactor-pass: its files are its code, so they count;
    the same folder with an installer's record in it is a copy, left out."""

    def build(self, name, extra):
        repo = support.Repo(name)
        files = dict(("skills/refactor-pass/" + path, lines(20)) for path in SKILL_FILES
                     if not path.startswith("tests/"))
        files.update(extra)
        files["tests/support.py"] = lines(20)
        repo.commit("2026-01-01", "Start", files)
        repo.commit("2026-01-02", "Grow", dict((path, lines(25)) for path in files))
        repo.done()
        return repo.path

    def test_the_source_counts(self):
        repo = self.build("source", {})
        for script in ("heatmap.py", "measure.py"):
            with self.subTest(script=script):
                result = support.run(script, "-C", repo)
                self.assertEqual(result.code, 0, result)
                self.assertNotIn("This skill's own files", result.out)
                self.assertIn("skills/refactor-pass/scripts/heatmap.py", result.out)

    def test_an_installed_copy_there_is_left_out(self):
        repo = self.build("installed", {"skills/refactor-pass/.install.json": "{}\n"})
        result = support.run("heatmap.py", "-C", repo)
        self.assertIn("This skill's own files, in skills/refactor-pass/, are left out", result.out)
        self.assertNotIn("skills/refactor-pass/scripts/heatmap.py", result.out)


if __name__ == "__main__":
    unittest.main()
