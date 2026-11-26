"""Rust's test modules on the scripts' edges: --show of one, --keep-tests and --not-test, a binary file, a file
the scripts can't read, a path holding a newline, the fixes trace and the pairs, which leave them out, and the
heatmap's tests' own files; and on the rule's: which macro a call is to, what a call or an include! holds, and with
no manifest, how far a built include! reaches."""

import os
import unittest

try:
    from . import support
    from .test_modules import modules, rows
except ImportError:
    import support
    from test_modules import modules, rows


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



class TiedTests(unittest.TestCase):
    """A test module's own files are those whose declarations bring it in, whatever their names, and only those:
    they aren't among the production files it changes with, and a file of its name elsewhere is."""

    def test_its_own_file(self):
        repo = support.Repo("tied-modules")
        for n in range(1, 6):
            repo.commit("2026-01-%02d" % n, "Change %d" % n, {
                "src/lib.rs": "mod disk;\nmod a;\nmod b;\nmod importer;\n" + support.lines(n),
                "src/importer.rs": support.lines(n),
                "src/disk.rs": "#[cfg(test)]\nmod checks;\n" + support.lines(n),
                "src/disk/checks.rs": support.lines(n), "src/a.rs": support.lines(n), "src/b.rs": support.lines(n),
                "crates/x/src/lib.rs": "#![cfg(test)]\n" + support.lines(n),
                "crates/y/src/lib.rs": "#[cfg(test)]\nmod importer;\n", "crates/y/src/importer.rs": support.lines(n)})
        repo.done()
        result = support.run("heatmap.py", "-C", repo.path)
        self.assertIn("  src/disk/checks.rs: 4 files, src/a.rs (5), src/b.rs (5), src/importer.rs (5), "
                      "src/lib.rs (5)\n",
                      result.out)
        self.assertIn("  crates/x/src/lib.rs: 5 files,", result.out)
        self.assertRegex(result.out, r"crates/y/src/importer\.rs: 5 files,.* src/importer\.rs \(5\)")

    def test_a_test_by_name_keeps_its_own_by_name(self):
        # A test by its name, or Cargo's test crate, keeps its own file by name too: each changes with one more
        # production file only, and isn't listed.
        repo = support.Repo("tied-named")
        for n in range(1, 6):
            repo.commit("2026-01-%02d" % n, "Change %d" % n, {
                "Cargo.toml": "[package]\nname = \"x\"\n\n[[test]]\nname = \"p\"\npath = \"checks/parser.rs\"\n",
                "src/lib.rs": "mod parser;\nmod lexer;\n#[cfg(test)]\nmod parser_test;\n",
                "src/parser.rs": support.lines(n), "src/lexer.rs": support.lines(n),
                "checks/parser.rs": support.lines(n),
                "src/parser_test.rs": support.lines(n), "tests/parser.rs": "mod common;\n" + support.lines(n),
                "tests/common/mod.rs": ""})
        repo.done()
        tied = support.run("heatmap.py", "-C", repo.path).out.split("Tests changed together")[1]
        self.assertNotIn("parser", tied)
        # And a test by its folder that's no crate of Cargo's, src/tests/parser.rs.
        repo = support.Repo("tied-folder")
        for n in range(1, 6):
            repo.commit("2026-01-%02d" % n, "Change %d" % n, {
                "src/lib.rs": "pub mod parser;\npub mod lexer;\n#[cfg(test)]\nmod tests;\n",
                "src/parser.rs": support.lines(n), "src/lexer.rs": support.lines(n),
                "src/tests/mod.rs": "mod parser;\n", "src/tests/parser.rs": support.lines(n)})
        repo.done()
        self.assertNotIn("parser", support.run("heatmap.py", "-C", repo.path).out.split("Tests changed together")[1])


class WhatACallOrAnIncludeHolds(unittest.TestCase):
    """A call's words and an include!'s strings, read across what else is in its brackets, as rustc reads them: each
    file is named by a test's #[path] too, so only the plain call or the include! keeps it code."""

    MACRO = ("macro_rules! modules { ($($m:ident),* $(,)?) => { $(pub mod $m;)* };\n"
             "    ($($m:ident),* ; $e:expr) => { $(pub mod $m;)* }; }\n")
    TESTS = "#[cfg(test)]\n#[path = \"util.rs\"]\nmod t1;\n#[cfg(test)]\n#[path = \"net.rs\"]\nmod t2;\n"

    def test_a_calls_words(self):
        # Past a comment, over lines; past a ; and an expression; in square brackets.
        for call in ("modules!(\n    util, // helpers\n    net,\n);\n", "modules!(util, net; 1 + 1);\n",
                     "modules!(\n    util, /* helpers */\n    net,\n);\n", "modules![util, net];\n"):
            with self.subTest(call=call):
                files = {"src/lib.rs": self.MACRO + call + self.TESTS, "src/util.rs": "", "src/net.rs": ""}
                self.assertEqual(modules(files), {})

    def test_where_a_template_declares(self):
        # m!(util) declares outer::util, src/outer/util.rs, code; src/util.rs only the test's #[path] names.
        files = {"src/lib.rs": "macro_rules! m { ($x:ident) => { pub mod outer { pub mod $x; } }; }\nm!(util);\n" +
                 self.TESTS.replace("net.rs", "outer/util.rs"), "src/util.rs": "", "src/outer/util.rs": ""}
        self.assertEqual(modules(files), {"src/util.rs": ["src/lib.rs"]})

    def test_a_built_includes_strings(self):
        # From the including file's folder, as one string or joined, and through a brace in its argument.
        for include in ('include!(concat!("util.rs"));\n', 'include!(concat!("ut", "il.rs"));\n',
                        'include!(concat!{env!("CARGO_MANIFEST_DIR"), "/src/util.rs"});\n'):
            with self.subTest(include=include):
                files = {"Cargo.toml": "[package]\nname = \"k\"\n", "src/util.rs": "",
                         "src/lib.rs": include + "#[cfg(test)]\n#[path = \"util.rs\"]\nmod t1;\n"}
                self.assertEqual(modules(files), {})


class WhichMacroACallIsTo(unittest.TestCase):
    """A call outside test code takes a macro's test-only-ness only from the macro_rules! rustc's textual scope gives
    it in its own file: the last of its name before it in a scope still open there, past any only in test code.
    Another of that name there, one that declares no module this can read, or none at all, makes the call plain.
    Each answer is rustc's, but where the macro is in another file, which leaves a test measured."""

    TEST_ONLY = "macro_rules! modules { ($($m:ident),*) => { $(#[cfg(test)] mod $m;)* } }\n"
    FORWARD = ("macro_rules! inner { ($m:ident) => { pub mod $m; } }\n"
               "macro_rules! modules { ($($t:tt)*) => { inner!($($t)*); } }\n")

    def check(self, lib, expected, more=()):
        files = dict({"Cargo.toml": "[package]\nname = \"s\"\n", "src/lib.rs": lib, "src/util.rs": "",
                      "src/fixtures.rs": "", "src/a/fixtures.rs": "", "src/macros.rs": self.FORWARD}, **dict(more))
        self.assertEqual(modules(files), expected)

    def test_its_own_files(self):
        # y's call is to y's forwarder, so util.rs is code; x's is to x's test-only macro.
        self.check("mod x;\nmod y;\n", {"src/x/fixtures.rs": ["src/x.rs"]},
                   {"src/x.rs": self.TEST_ONLY + "modules!(fixtures);\n", "src/x/fixtures.rs": "",
                    "src/y.rs": self.FORWARD + "modules!(util);\n", "src/y/util.rs": ""})

    def test_a_scope_that_has_closed(self):
        # The test-only macro in mod a, or in a function's body, is out of scope after its }: util.rs is code.
        self.check("#[macro_use]\nmod macros;\nmod a {\n    %s    modules!(fixtures);\n}\nmodules!(util);\n"
                   % self.TEST_ONLY, {"src/a/fixtures.rs": ["src/lib.rs"]})
        self.check("#[macro_use]\nmod macros;\nfn f() {\n    %s}\nmodules!(util);\n" % self.TEST_ONLY, {})

    def test_the_last_one_before_the_call(self):
        for lib in (self.FORWARD + "modules!(util);\n" + self.TEST_ONLY + "modules!(fixtures);\n",
                    self.TEST_ONLY + "modules!(fixtures);\n" + self.FORWARD + "modules!(util);\n"):
            with self.subTest(lib=lib):
                self.check(lib, {"src/fixtures.rs": ["src/lib.rs"]})

    def test_in_a_macros_brackets_or_body(self):
        # One a macro's brackets hold is in the scope around them; one another macro_rules! holds is made only where
        # that one is called, never here, so the call is to the forwarder #[macro_use] mod macros; brings in.
        wrap = "macro_rules! wrap { ($($i:item)*) => { $($i)* } }\n"
        self.check(wrap + "wrap! {\n%s}\nmodules!(fixtures);\n" % self.TEST_ONLY, {"src/fixtures.rs": ["src/lib.rs"]})
        self.check("#[macro_use]\nmod macros;\nmacro_rules! outer { () => { %s } }\nmodules!(util);\n"
                   % self.TEST_ONLY.strip(), {})

    def test_macro_use(self):
        # #[macro_use] mod macros; brings in macros this doesn't read, after the test-only one, and an inline module's
        # keep its own past its }: either way the call is to the forwarder.
        self.check(self.TEST_ONLY + "#[macro_use]\nmod macros;\nmodules!(util);\n", {})
        self.check(self.TEST_ONLY + "#[macro_use]\nmod a {\n%s}\nmodules!(util);\n" % self.FORWARD, {})
        # The limit: a test-only macro in another file, which rustc compiles util.rs for tests alone by, is never
        # taken for the one called, so util.rs stays measured.
        self.check("#[macro_use]\nmod macros;\nmodules!(util);\n", {}, {"src/macros.rs": self.TEST_ONLY})


class WithNoManifest(unittest.TestCase):
    """Where no manifest says which package a file is in, a built include! names its file from the including
    file's folder or one above it."""

    def test_a_built_includes_reach(self):
        # Past a leading .., and with a \ read as Windows reads it where no file is so named.
        for built in ("/../shared/x.rs", "\\..\\shared\\x.rs"):
            with self.subTest(built=built):
                files = {"a/src/lib.rs": "include!(concat!(env!(\"SRC\"), \"%s\"));\n" % built.replace("\\", "\\\\"),
                         "a/shared/x.rs": "",
                         "b/src/lib.rs": "#[cfg(test)]\n#[path = \"../../a/shared/x.rs\"]\nmod x;\n"}
                self.assertEqual(modules(files), {})
        files["a/src/lib.rs"] = "pub fn f() {}\n"
        self.assertEqual(modules(files), {"a/shared/x.rs": ["b/src/lib.rs"]})


if __name__ == "__main__":
    unittest.main()
