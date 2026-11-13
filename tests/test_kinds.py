"""The whole heatmap over a repo with a file of each kind of path, each taking a road of its own through the code:
its table, pairs, fixes by file, --show and --page. A path is in the pairs, the fixes by file and --max-files's
count exactly where it's a row of the table.
"""

import os
import re
import unittest

try:
    from . import support, test_fixes
except ImportError:
    import support
    import test_fixes

lines = support.lines
fix_rows = test_fixes.fix_rows


SKILL_COPY = ".agents/skills/refactor-pass/"


def build_every_kind():
    """A repo with a file of each kind that takes a road of its own through the heatmap: text (src/a.py); binary
    by its content (img.png); holding NULs but diffed as text by the repo's attributes (zeros.dat); deleted since
    (src/gone.py); renamed in the window (src/old.py, today src/new.py); a test; documentation; a manifest; the
    skill's own copy; a symbolic link; a submodule; and other/out.py, outside a scope of src. The fixes touch
    several of each."""
    repo = support.Repo("kinds")
    every = ["src/a.py", "src/old.py", "src/gone.py", "img.png", "zeros.dat", "tests/test_a.py", "docs/guide.md",
             "package.json", SKILL_COPY + "scripts/heatmap.py", "other/out.py"]

    def content(path, n):
        return b"\x89PNG\x00%d\n" % n if path == "img.png" else b"a\x00%d\nc\n" % n if path == "zeros.dat" else \
            lines(n, path)
    repo.commit("2026-01-01", "Start the shop's files", dict([(p, content(p, 3)) for p in every] + [
        (".gitattributes", "zeros.dat diff\n"), (SKILL_COPY + "SKILL.md", "x\n"),
        (SKILL_COPY + "scripts/scoping.py", "x\n"), ("link.py", support.Link("src/a.py")),
        ("vendor/lib", support.Gitlink("1" * 40))]))
    for day in range(2, 8):
        subject = ("Fix the crash in step %d" if day % 2 else "Add the cart's step %d") % day
        repo.commit("2026-01-%02d" % day, subject, dict(
            [(p, content(p, day + 3)) for p in every] + [("link.py", support.Link("src/old.py" if day % 2 else
                                                                                     "src/a.py")),
                                                          ("vendor/lib", support.Gitlink(str(day) * 40))]))
    repo.commit("2026-01-08", "Move the old module", rename={"src/old.py": "src/new.py"})
    repo.commit("2026-01-09", "Fix the wrong total", {"src/new.py": lines(12, "o"), "src/a.py": lines(12, "a"),
                                                      "zeros.dat": b"a\x00z\nc\n", "img.png": b"\x89PNG\x00z\n"})
    repo.commit("2026-01-10", "Drop the gone module", delete=["src/gone.py"])
    repo.done()
    return repo


class EveryKindOfPath(unittest.TestCase):
    """The whole heatmap, its table, pairs, fixes by file, --show and --page, over a file of each kind: a path is
    in the pairs, the fixes by file and --max-files's count exactly where it's a row of the table."""

    @classmethod
    def setUpClass(cls):
        cls.repo = build_every_kind()
        cls.page = os.path.join(support.new_folder("kinds-page"), "pass.html")
        cls.result = support.run("heatmap.py", "-C", cls.repo.path, "--min-shared", "2", "--min-revs", "2", "--page",
                                 cls.page)

    def test_the_heatmap(self):
        self.assertEqual((self.result.code, self.result.err), (0, ""), self.result)
        rows = support.heatmap_rows(self.result.out)
        self.assertEqual(set(rows), {"src/a.py", "src/new.py", "docs/guide.md", "package.json", "other/out.py",
                                     ".gitattributes"})
        # Fixes by file: of the rows, the code. zeros.dat, img.png, the test, the deleted and the skill's copy
        # are rows of nothing, here or in the pairs (a test has its own list, of what it changes with).
        self.assertEqual(fix_rows(self.result.out), {"src/a.py": (4, 2, 0, 0, 4), "src/new.py": (4, 2, 0, 0, 4),
                                                     "other/out.py": (3, 1, 0, 0, 3)})
        for path in ("zeros.dat", "img.png", "src/gone.py", "test_a.py", SKILL_COPY + "scripts", "link.py",
                     "vendor/lib"):
            self.assertNotIn(path, self.result.out.split("Changed together")[1].split("Tests changed")[0], path)
        self.assertEqual(support.run("check_page.py", self.page).code, 0)
        scoped = support.run("heatmap.py", "-C", self.repo.path, "src", "--min-shared", "2", "--min-revs", "2")
        self.assertEqual((scoped.code, scoped.err), (0, ""), scoped)
        self.assertEqual(set(support.heatmap_rows(scoped.out)), {"src/a.py", "src/new.py"})

    def test_show_each_kind(self):
        paths = ("src/a.py", "src/new.py", "src/old.py", "src/gone.py", "img.png", "zeros.dat", "tests/test_a.py",
                 "docs/guide.md", "package.json", "other/out.py")
        shown = support.run("heatmap.py", "-C", self.repo.path, "--messages",
                            *[arg for path in paths for arg in ("--show", path)])
        self.assertEqual((shown.code, shown.err, shown.out.count("Fix the crash in step 7")), (0, "", 10), shown)
        fix = re.findall(r"(?m)^  ([0-9a-f]{9}) .*Fix the crash in step 7", shown.out)[0]
        for path in ("zeros.dat", "img.png", "src/new.py", "src/gone.py"):
            with self.subTest(path=path):
                diffs = support.run("heatmap.py", "-C", self.repo.path, "--show", path, "--diffs", fix)
                self.assertEqual((diffs.code, diffs.err), (0, ""), diffs)


if __name__ == "__main__":
    unittest.main()
