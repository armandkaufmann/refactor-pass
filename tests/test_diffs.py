"""heatmap.py --show FILE --diffs: a file's changes in the commits given, under the name it had in each, each cut
at 60 lines, from one git call; and the names, bytes and lines git writes in a way of its own.
"""

import unittest

try:
    from . import support
except ImportError:
    import support

lines = support.lines


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

    @unittest.expectedFailure
    def test_a_file_of_one_commit_or_none(self):
        # One commit listed: its hash, said once. None: nothing to give.
        repo = support.Repo("one-commit")
        start = repo.commit("2026-01-01", "Start", {"a.py": lines(3, "a"), "b.py": lines(3, "b")})
        repo.commit("2026-01-02", "Change b", {"b.py": lines(4, "b")})
        repo.done()
        for given, err in (("zzzz", "--diffs: zzzz isn't the one commit --show a.py --messages lists, %s.\n"),
                           (",", "--diffs: no commit given. The one commit --show a.py --messages lists is %s.\n")):
            result = support.run("heatmap.py", "-C", repo.path, "--show", "a.py", "--diffs", given)
            self.assertEqual((result.code, result.err), (1, err % repo.short(start)))
        none = support.run("heatmap.py", "-C", repo.path, "-n", "1", "--show", "a.py", "--diffs", "zzzz")
        self.assertEqual((none.code, none.err), (1, "--diffs: a.py has no commit in the window, so there's no change "
                                                    "to show.\n"))

    @unittest.skipIf(support.WINDOWS, "a file's name can't start with a colon on Windows")
    def test_a_name_git_would_read_as_pathspec_magic(self):
        repo = support.Repo("colon")
        repo.commit("2026-01-01", "Start", {":weird.py": lines(3, "w")})
        drop = repo.commit("2026-01-02", "Drop a line", {":weird.py": lines(2, "w")})
        repo.done()
        result = support.run("heatmap.py", "-C", repo.path, "--show", ":weird.py", "--diffs", repo.short(drop))
        self.assertIn("\n      -w 3\n", result.out)

    def test_a_nul_in_a_change_git_diffs_as_text(self):
        # Named so Windows can hold them: NUL, with or without an extension, is a device there.
        repo = support.Repo("zero-bytes")
        repo.commit("2026-01-01", "Start", {".gitattributes": "zeros.dat diff\n", "zeros.dat": b"a\x00b\nc\n"})
        one = repo.commit("2026-01-02", "Change it", {"zeros.dat": b"a\x00B\nc\n"})
        two = repo.commit("2026-01-03", "Change it again", {"zeros.dat": b"a\x00B\nC\n"})
        repo.done()
        result = support.run("heatmap.py", "-C", repo.path, "--show", "zeros.dat", "--diffs",
                             "%s,%s" % (repo.short(two), repo.short(one)))
        self.assertIn("Change it again\n      @@ -1,2 +1,2 @@\n       a\\x00B\n      -c\n      +C\n", result.out)
        self.assertIn("Change it\n      @@ -1,2 +1,2 @@\n      -a\\x00b\n      +a\\x00B\n       c\n", result.out)

    def test_a_long_subject_is_cut(self):
        # Git's subject is the message's first paragraph, which can run on: each is cut at 200 characters.
        repo = support.Repo("long")
        repo.commit("2026-01-01", "Start " + "x" * 400, {"a.py": lines(3)})
        crash = repo.commit("2026-01-02", "Fix the crash\nwhen the cart\nis empty, " + "y" * 300, {"a.py": lines(4)})
        repo.done()
        for args in (["--diffs", repo.short(crash)], ["--messages"]):
            out = support.run("heatmap.py", "-C", repo.path, "--show", "a.py", *args).out
            self.assertIn("Fix the crash when the cart is empty, %s... (138 more characters)  [fix, words: fix, crash]"
                          % ("y" * 162), out)
        self.assertIn("Start %s... (206 more characters)\n" % ("x" * 194), out)  # As --messages lists it.

    def test_a_files_crlf_line_ends_arent_shown(self):
        # Four characters of noise a line, \x0d, for nothing a reader needs.
        repo = support.Repo("crlf")
        repo.commit("2026-01-01", "Start", {"a.txt": b"a\r\nb\r\nc\r\n"})
        change = repo.commit("2026-01-02", "Change b", {"a.txt": b"a\r\nB\r\nc\r\n"})
        repo.done()
        result = support.run("heatmap.py", "-C", repo.path, "--show", "a.txt", "--diffs", repo.short(change))
        self.assertIn("Change b\n      @@ -1,3 +1,3 @@\n       a\n      -b\n      +B\n       c\n", result.out)

    def test_a_long_line_is_cut_as_a_subject_is(self):
        # A minified file's one line, and a message's: each cut at 200 characters, saying how many more.
        repo = support.Repo("one-line")
        repo.commit("2026-01-01", "Start", {"long.js": "x" * 300000 + "\n"})
        change = repo.commit("2026-01-02", "Rewrite the bundle\n\n" + "y" * 50000, {"long.js": "z" * 300000 + "\n"})
        repo.done()
        diffs = support.run("heatmap.py", "-C", repo.path, "--show", "long.js", "--diffs", repo.short(change)).out
        self.assertIn("      -%s... (299801 more characters)\n" % ("x" * 199), diffs)
        self.assertLess(len(diffs), 2000)
        messages = support.run("heatmap.py", "-C", repo.path, "--show", "long.js", "--messages").out
        self.assertIn("      %s... (49800 more characters)\n" % ("y" * 200), messages)
        self.assertLess(len(messages), 2000)

    def test_a_quoted_name_with_no_lines_of_change(self):
        # A name git quotes, past ASCII: a pure rename, and a binary file's change, have only its diff --git line.
        repo = support.Repo("quoted")
        repo.commit("2026-01-01", "Start", {"src/\u00e9.py": lines(3), "src/\u00e9.bin": b"\x00\x01\n"})
        move = repo.commit("2026-01-02", "Move it", rename={"src/\u00e9.py": "src/\u00e8.py"})
        change = repo.commit("2026-01-03", "Change it", {"src/\u00e9.bin": b"\x00\x02\n"})
        repo.done()
        moved = support.run("heatmap.py", "-C", repo.path, "--show", "src/\u00e8.py", "--diffs", repo.short(move)).out
        self.assertIn('      (rename from "src/\\303\\251.py")\n', moved)
        changed = support.run("heatmap.py", "-C", repo.path, "--show", "src/\u00e9.bin", "--diffs",
                              repo.short(change)).out
        self.assertIn("      (Binary files ", changed)

    def test_the_lines_a_file_gives(self):
        # As file_diffs reads git show's output: one call for several commits, each commit's section of the file.
        heatmap = support.load("heatmap")
        fix, other = self.repo.sha(self.marks["fix"]), self.repo.sha(self.marks["other"])
        found = heatmap.file_diffs(self.repo.path, [(fix, "other.py", None), (other, "other.py", None),
                                                    (fix, "new/a.py", None)], most=3)
        self.assertEqual(found[(other, "other.py")], ["@@ -1 +1 @@", "-y", "+z"])
        self.assertEqual(found[(fix, "other.py")], ["@@ -1 +1 @@", "-x", "+y"])
        # In that commit new/a.py was old/a.py: under a name it didn't have, not another file's change. --diffs
        # asks only for the commits that changed the file, so finding none is a gap in reading git, said as one.
        self.assertEqual(found[(fix, "new/a.py")], ["(its change to new/a.py couldn't be read here: git show %s -- "
                                                    "new/a.py shows it)" % fix[:9]])


if __name__ == "__main__":
    unittest.main()
