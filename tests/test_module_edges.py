"""Rust's test modules on the scripts' edges: --show of one, --keep-tests and --not-test, a binary file, a file
the scripts can't read, a path holding a newline, and the fixes trace and the pairs, which leave them out."""

import os
import unittest

try:
    from . import support
    from .test_modules import rows
except ImportError:
    import support
    from test_modules import rows


class ScriptsOnTheEdges(unittest.TestCase):
    """What the scripts say, or don't, of a test module that --show names, --keep-tests or --not-test keeps, a file
    they can't read, and the fixes trace and the pairs, which leave it out."""

    @classmethod
    def setUpClass(cls):
        repo = support.Repo("module-edges")
        files = {"src/lib.rs": "mod a;\n#[cfg(test)]\nmod probe;\n#[cfg(test)]\nmod probe_test;\n#[cfg(test)]\n"
                               "mod shared;\n", "src/a.rs": "fn a() {\n    go();\n}\n",
                 "src/bin/tool.rs": "#[cfg(test)]\n#[path = \"../shared.rs\"]\nmod shared;\nfn main() {\n}\n",
                 "src/shared.rs": "fn s() {\n}\n", "src/probe_test.rs": "fn p() {\n}\n",
                 "src/probe.rs": "fn p1() {\n    a();\n}\n#[cfg(test)]\nfn p2() {\n    b();\n}\n",
                 "src/bin/check.rs": "#![cfg(test)]\nfn c() {\n}\n", "docs/notes.md": "Notes.\n",
                 "src/blob.rs": b"\0\n#[cfg(test)]\nmod packed;\n", "src/packed.rs": "fn k() {\n}\n"}
        repo.commit("2026-01-05", "Start", files)
        for n in range(1, 6):
            repo.commit("2026-01-%02d" % (5 + n), "Fix a crash in probe %d" % n, {
                "src/probe.rs": files["src/probe.rs"] + "\n" * n, "src/a.rs": files["src/a.rs"] + "\n" * n})
        repo.done()
        cls.repo = repo.path

    def test_show(self):
        result = support.run("measure.py", "-C", self.repo, "docs", "--show", "src/probe.rs", "--show", "src/shared.rs",
                             "--show", "src/bin/check.rs", "--show", "src/probe_test.rs")
        self.assertEqual(result.code, 0, result)
        self.assertRegex(result.out, r"src/probe\.rs: Rust, 7 code lines, band -, 2 functions.*\nA test file: ")
        self.assertRegex(result.out, r"\nA test file: .*src/bin/tool\.rs and src/lib\.rs; measured whole here\.\n")
        self.assertIn("\nA test file: Rust compiled only for tests, by the #![cfg(test)] at its top; measured whole "
                      "here.\n", result.out)
        self.assertEqual(result.out.count("A test file: "), 3)
        for args in (["--keep-tests"], ["--not-test", "src/probe.rs"]):
            with self.subTest(args=args):
                result = support.run("measure.py", "-C", self.repo, "--show", "src/probe.rs", *args)
                self.assertEqual(result.code, 0, result)
                self.assertNotIn("A test file", result.out)

    def test_a_binary_file_declares_nothing(self):
        for script in ("measure.py", "heatmap.py"):
            with self.subTest(script=script):
                self.assertIn("src/packed.rs", rows(support.run(script, "-C", self.repo, "--top", "20").out))

    def test_left_out_of_the_fixes_and_the_pairs(self):
        result = support.run("heatmap.py", "-C", self.repo, "--min-shared", "3", "--min-revs", "3")
        self.assertEqual(result.code, 0, result)
        fixes, pairs = result.out.split("Fixes by file")[1].split("Changed together")
        self.assertIn("src/a.rs", fixes)
        self.assertNotIn("src/probe.rs", fixes + pairs)

    @unittest.skipIf(support.WINDOWS or (hasattr(os, "geteuid") and os.geteuid() == 0), "a file anyone can read")
    def test_a_file_it_cant_read(self):
        repo = support.Repo("unreadable")
        repo.commit("2026-01-05", "Start", {"src/lib.rs": "mod a;\n", "src/a.rs": "fn a() {\n}\n"})
        repo.done()
        os.chmod(os.path.join(repo.path, "src", "a.rs"), 0)
        try:
            result = support.run("measure.py", "-C", repo.path)
        finally:
            os.chmod(os.path.join(repo.path, "src", "a.rs"), 0o644)
        self.assertEqual(result.code, 0, result)
        self.assertIn("Couldn't read 1 file", result.out)

    @unittest.skipIf(support.WINDOWS, "a file's name can't hold a newline on Windows")
    def test_a_path_holding_a_newline(self):
        repo = support.Repo("newline")
        repo.commit("2026-01-05", "Start", {"odd\nname.rs": "fn o() {\n}\n", "src/lib.rs": "#[cfg(test)]\nmod b;\n",
                                             "src/b.rs": "fn b() {\n}\n"})
        repo.done()
        result = support.run("heatmap.py", "-C", repo.path)
        self.assertEqual(rows(result.out), {"src/lib.rs"})


if __name__ == "__main__":
    unittest.main()
