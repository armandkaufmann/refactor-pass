"""Rust's test modules on the scripts' edges: --show of one, --keep-tests and --not-test, a binary file, a file
the scripts can't read, a path holding a newline, the fixes trace and the pairs, which leave them out, the heatmap's
tests' own files, and a link, a sparse checkout and a deleted file; and on the rule's: what an include! holds, what a
cfg is on, which macros may declare modules, and with no manifest, how far a built include! reaches."""

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
        self.assertIn("\nA test file: Rust compiled only for tests, by the inner cfg at its top that needs test; "
                      "measured whole here.\n", result.out)
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
        # Both scripts read such a file: src/old\ncopy.rs declares src/t.rs plainly, so it's code in both.
        repo = support.Repo("newline-declarer")
        files = {"src/lib.rs": "#[cfg(test)]\nmod t;\n", "src/t.rs": "fn f() {\n}\n", "src/old\ncopy.rs": "mod t;\n"}
        repo.commit("2026-01-05", "Start", files)
        repo.commit("2026-01-06", "Change", {"src/t.rs": "fn f() {\n}\n\n", "src/lib.rs": files["src/lib.rs"] + "\n"})
        repo.done()
        for script in ("measure.py", "heatmap.py"):
            with self.subTest(script=script):
                self.assertIn("src/t.rs", rows(support.run(script, "-C", repo.path).out))



class WhatTheCheckoutHolds(unittest.TestCase):
    """A tracked link, a file a sparse checkout leaves out and a deleted one, as rustc would see them: what comes in
    through a link, or a declaration in a file left out, is code, in both scripts; and a deleted test module isn't
    there."""

    def test_through_a_link(self):
        # app's lib brings src/helper.rs in through a link to it, and src/shared/mod.rs through a link to its
        # folder, where src/lib.rs declares each only for tests; a link out of the repo is followed nowhere.
        files = {"src/lib.rs": "#[cfg(test)]\nmod helper;\n#[cfg(test)]\nmod shared;\n#[cfg(test)]\nmod probe;\n",
                 "src/helper.rs": "fn h() {\n}\n", "src/shared/mod.rs": "fn s() {\n}\n",
                 "src/probe.rs": "fn p() {\n}\n", "app/src/lib.rs": "mod helper;\nmod shared;\n",
                 "app/src/helper.rs": support.Link("../../src/helper.rs"),
                 "app/src/shared": support.Link("../../src/shared"), "app/up": support.Link("../..")}
        repo = support.Repo("links")
        repo.commit("2026-01-05", "Start", files)
        repo.commit("2026-01-06", "Change", dict((p, t + "\n") for p, t in files.items() if p.startswith("src/")))
        repo.done()
        for script in ("measure.py", "heatmap.py"):
            with self.subTest(script=script):
                self.assertEqual(rows(support.run(script, "-C", repo.path).out),
                                 {"src/lib.rs", "src/helper.rs", "src/shared/mod.rs"})

    def test_a_linked_files_declarations(self):
        # rustc reads src/current.rs, a link to v2/mod.rs, from where the link is: its mod helpers; is src/helpers.rs,
        # which src/lib.rs declares only for tests, and code. Both scripts; and the same where a staged link is
        # the only change, which the working tree's line counts.
        files = {"src/lib.rs": "#[path = \"current.rs\"]\nmod current;\n#[cfg(test)]\nmod helpers;\n",
                 "src/current.rs": support.Link("v2/mod.rs"), "src/v2/mod.rs": "mod helpers;\n",
                 "src/v2/helpers.rs": "fn v() {\n}\n", "src/helpers.rs": "fn h() {\n}\n"}
        repo = support.Repo("linked-declarer")
        repo.commit("2026-01-05", "Start", files)
        repo.commit("2026-01-06", "Change", {"src/helpers.rs": "fn h() {\n}\n\n",
                                              "src/lib.rs": files["src/lib.rs"] + "\n"})
        repo.done()
        for script in ("measure.py", "heatmap.py"):
            with self.subTest(script=script):
                self.assertIn("src/helpers.rs", rows(support.run(script, "-C", repo.path).out))
        # Read so as code, though only a test declares the link: a declaration it holds makes nothing a test.
        files = {"src/lib.rs": "#[cfg(test)]\n" + files["src/lib.rs"], "src/v2/mod.rs": "mod helpers;\n",
                 "src/helpers.rs": ""}
        scoping = support.load("scoping")
        self.assertEqual(scoping.rust_test_modules(sorted(files), lambda paths: dict((p, files[p]) for p in paths),
                                                   {"src/current.rs": "v2/mod.rs"}), {})
        repo = support.Repo("staged-link")
        repo.commit("2026-01-05", "Start", {"a/Cargo.toml": "[package]\n", "a/src/lib.rs": "mod shared;\n",
                                             "b/Cargo.toml": "[package]\n", "b/src/shared/mod.rs": "fn s() {\n}\n",
                                             "b/src/lib.rs": "#[cfg(test)]\nmod shared;\n"})
        repo.done()
        os.symlink("../../b/src/shared", os.path.join(repo.path, "a/src/shared"))
        support.git(repo.path, "add", "a/src/shared")
        self.assertIn("from the working tree, which differs from HEAD in 1 ",
                      support.run("measure.py", "-C", repo.path).out)

    def test_a_sparse_checkout_and_a_deleted_file(self):
        # shared/lib.rs, which brings src/fixtures.rs in plainly, is left out of the working tree as a sparse
        # checkout leaves it, and read from git's index; src/tests.rs, deleted, isn't there to be a test module.
        repo = support.Repo("left-out")
        repo.commit("2026-01-05", "Start", {"src/lib.rs": "#[cfg(test)]\nmod fixtures;\n#[cfg(test)]\nmod tests;\n",
                                             "src/fixtures.rs": "fn d() {\n}\n", "src/tests.rs": "fn t() {\n}\n",
                                             "shared/lib.rs": "#[path = \"../src/fixtures.rs\"]\npub mod fixtures;\n"})
        repo.done()
        support.git(repo.path, "update-index", "--skip-worktree", "shared/lib.rs")
        for path in ("shared/lib.rs", "src/tests.rs"):
            os.remove(os.path.join(repo.path, path))
        out = support.run("measure.py", "-C", repo.path).out
        self.assertIn("\nTest files: none in the scope.\n", out)
        self.assertIn("\nNot in the working tree, so not measured: 1 file a sparse checkout leaves out "
                      "(shared/lib.rs), and 1 deleted and not committed (src/tests.rs).\n", out)
        self.assertIn("src/fixtures.rs", rows(support.run("heatmap.py", "-C", repo.path).out))

    def test_what_git_takes_as_unchanged(self):
        # A file git takes as unchanged, by assume-unchanged or skip-worktree, that the working tree changes:
        # measure.py reads the change, so the working tree's line counts it, in both scripts.
        repo = support.Repo("hidden-change")
        repo.commit("2026-01-05", "Start", {"Cargo.toml": "[package]\n", "src/lib.rs": "#[cfg(test)]\nmod helper;\n",
                                             "src/helper.rs": "fn h() {\n}\n"})
        repo.done()
        for flag in ("--assume-unchanged", "--skip-worktree"):
            with self.subTest(flag=flag):
                support.git(repo.path, "update-index", flag, "src/lib.rs")
                repo.write("src/lib.rs", "mod helper;\n")
                for script, words in (("measure.py", "from the working tree, which differs from HEAD in 1 "),
                                      ("heatmap.py", "which measure.py reads, differs from it in 1 ")):
                    self.assertIn(words, support.run(script, "-C", repo.path).out)
                support.git(repo.path, "update-index", flag.replace("--", "--no-"), "src/lib.rs")
                support.git(repo.path, "checkout", "--", "src/lib.rs")


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
        # And one --test names, declared only for tests too.
        repo = support.Repo("tied-given")
        for n in range(1, 6):
            repo.commit("2026-01-%02d" % n, "Change %d" % n, {
                "src/lib.rs": "pub mod checks;\npub mod parser;\npub mod lexer;\n", "src/parser.rs": support.lines(n),
                "src/lexer.rs": support.lines(n), "src/checks.rs": "#[cfg(test)]\nmod parser;\n",
                "src/checks/parser.rs": support.lines(n)})
        repo.done()
        out = support.run("heatmap.py", "-C", repo.path, "--test", "src/checks/*").out
        self.assertNotIn("parser", out.split("Tests changed together")[1])


class WhatAnIncludeHolds(unittest.TestCase):
    """An include!'s strings, and a #[path]'s, read as rustc reads them: each file is named by a test's #[path] or
    declaration too, so only the include! keeps it code."""

    def test_an_escape_in_a_path(self):
        # A \n in a #[path]'s string is a newline, as in a file so named.
        files = {"src/lib.rs": "#[cfg(test)]\n#[path = \"a\\nb.rs\"]\nmod t;\n", "src/a\nb.rs": "", "src/anb.rs": ""}
        self.assertEqual(modules(files), {"src/a\nb.rs": ["src/lib.rs"]})

    def test_an_include_past_a_comment(self):
        for include in ('include! /* generated */ ("util.rs");\n', 'include! // generated\n("util.rs");\n',
                        'include /* a */ ! /* b */ ("util.rs");\n', 'include /* a */ !("util.rs");\n',
                        'include! /* c */ ["util.rs"];\n'):
            with self.subTest(include=include):
                self.assertEqual(modules({"src/lib.rs": include + "#[cfg(test)]\nmod util;\n", "src/util.rs": ""}), {})

    def test_an_included_files_declarations(self):
        # rustc reads what code include!s from its own folder, as a mod.rs, though a test's #[path] names it too:
        # src/lexer.rs and src/util.rs are code.
        files = {"Cargo.toml": "[package]\nname = \"k\"\n", "src/lib.rs": "include!(\"parser.rs\");\n",
                 "src/parser.rs": "mod lexer;\npub fn parse() { lexer::lex() }\n", "src/lexer.rs": "pub fn lex() {}\n",
                 "tests/parse.rs": "#[path = \"../src/parser.rs\"]\nmod parser;\n#[test]\nfn t() { parser::parse() }\n"}
        self.assertEqual(modules(files), {"tests/parse.rs": "crate"})
        files = {"src/lib.rs": "include!(\"gen.rs\");\n#[cfg(test)]\n#[path = \"gen.rs\"]\nmod gen_tests;\n",
                 "src/gen.rs": "mod util;\n", "src/util.rs": "pub fn u() {}\n"}
        self.assertEqual(modules(files), {})
        # And though Cargo builds the file, or the one that includes it, as a test's root too: build.rs brings
        # tests/it.rs in, which includes tests/inc.rs, whose src/m32.rs is code; the lib brings tests/it.rs in,
        # whose tests/inc.rs brings tests/q.rs in, code where Cargo builds it as a test too (AA).
        man, it = "[package]\nname = \"k\"\n", "include!(\"inc.rs\");\n"
        for files in ({"Cargo.toml": man, "build.rs": "#[path = \"tests/it.rs\"]\nmod m30;\nfn main() {}\n",
                       "tests/it.rs": it, "tests/inc.rs": "#[path = \"../src/m32.rs\"]\nmod m57;\n",
                       "src/lib.rs": "#[cfg(test)]\nmod m32;\n", "src/m32.rs": "pub fn f() {}\n"},
                      {"Cargo.toml": man, "src/lib.rs": "#[path = \"../tests/it.rs\"]\nmod m;\n", "tests/it.rs": it,
                       "tests/inc.rs": "#[path = \"q.rs\"]\nmod q;\n", "tests/q.rs": "pub fn q() {}\n"}):
            with self.subTest(files=files):
                self.assertEqual(modules(files), {})
        # Only so: gen.rs's mod util; is src/util.rs, not src/gen/util.rs, which only a test declares.
        files = {"src/lib.rs": "include!(\"gen.rs\");\n#[cfg(test)]\n#[path = \"gen/util.rs\"]\nmod gu;\n",
                 "src/gen.rs": "mod util;\n", "src/util.rs": "", "src/gen/util.rs": ""}
        self.assertEqual(modules(files), {"src/gen/util.rs": ["src/lib.rs"]})

    def test_an_include_alone_in_its_file(self):
        # Past a comment between include and its !, in a file that holds nothing else; an inner cfg past a comment,
        # a marked file; and a #[path] past one between its # and [, which rustc reads.
        for include in ('include /* generated */ !("table.rs");\n', 'include // generated\n!("table.rs");\n'):
            with self.subTest(include=include):
                files = {"src/lib.rs": "mod a;\n#[cfg(test)]\n#[path = \"table.rs\"]\nmod table_tests;\n",
                         "src/a.rs": include, "src/table.rs": "pub fn t() {}\n"}
                self.assertEqual(modules(files), {})
        for marked in ("#! /* c */ [cfg(test)]\n", "#![ /* c */ cfg(test)]\n"):
            with self.subTest(marked=marked):
                self.assertEqual(modules({"src/lib.rs": "pub mod m;\n", "src/m.rs": marked + "pub fn f() {}\n"}),
                                 {"src/m.rs": "marked"})
        files = {"src/lib.rs": "# /* c */ [path = \"x.rs\"]\nmod m;\n" + WhatMakesAMacroPackage.TESTS % "x.rs",
                 "src/x.rs": ""}
        self.assertEqual(modules(files), {})
        # An outer one, though its comment holds a !.
        files = {"src/lib.rs": "pub mod m;\n", "src/m.rs": "# /* hi! */ [cfg(test)]\nmod t;\n", "src/m/t.rs": ""}
        self.assertEqual(modules(files), {"src/m/t.rs": ["src/m.rs"]})

    def test_a_built_includes_strings(self):
        # From the including file's folder, as one string or joined, and through a brace in its argument.
        for include in ('include!(concat!("util.rs"));\n', 'include!(concat!("ut", "il.rs"));\n',
                        'include!(concat!{env!("CARGO_MANIFEST_DIR"), "/src/util.rs"});\n',
                        'include!(concat!(env!("CARGO_MANIFEST_DIR"), stringify!(), stringify!(), "/src/util.rs"));\n',
                        'include!(concat!(env!("CARGO_MANIFEST_DIR"), "/src/gen/", "util.rs"));\n'):
            with self.subTest(include=include):
                at = "gen/util.rs" if "gen/" in include else "util.rs"
                files = {"Cargo.toml": "[package]\nname = \"k\"\n", "src/" + at: "",
                         "src/lib.rs": include + "#[cfg(test)]\n#[path = \"%s\"]\nmod t1;\n" % at}
                self.assertEqual(modules(files), {})


class WhatACfgIsOn(unittest.TestCase):
    """A cfg makes the block after it test code only where it's on the item or statement the block is: on a part of
    one, a parameter, an argument, an element, a field or a match arm, it's that part's. Each answer rustc's."""

    def test_a_part_of_an_item(self):
        imp = "#[path = \"imp.rs\"] mod imp;"
        for code in ("pub fn run(#[cfg(test)] _hook: u8, n: u8) -> u8 { %s n }", "pub fn run<#[cfg(test)] T>() { %s }",
                     "impl<#[cfg(test)] 'a> X<u8> { fn f() { %s } }",
                     "pub fn run<T>(n: u8, #[cfg(test)] _x: T) where T: Copy { %s }",
                     "pub fn run() { let f = |#[cfg(test)] _x: u8| { %s }; }",
                     "pub fn run() { go(#[cfg(test)] 1, { %s 2 }); }",
                     "pub fn run() { let a = [#[cfg(test)] 1, { %s 2 }]; }",
                     "pub fn run() { let t = (#[cfg(test)] 1, { %s 2 }); }",
                     "pub fn run() { let s = S { #[cfg(test)] a: 1, b: { %s 2 } }; }",
                     "pub fn pick(v: u8) -> u8 { match v { #[cfg(test)] 0 => 0, _ => { %s 1 } } }"):
            with self.subTest(code=code):
                self.assertEqual(modules({"src/lib.rs": code % imp, "src/imp.rs": ""}), {})
        # An item's own block, past the , in its generics, a statement's, a match arm's or a field's, is test code.
        for test in ("#[cfg(test)] fn f<A, B>() { %s }", "pub fn run() { let x = 1; #[cfg(test)] let y = { %s 2 }; }",
                     "pub fn pick(v: u8) -> u8 { match v { #[cfg(test)] 0 => { %s 0 } _ => 1 } }",
                     "pub fn run() { let s = S { #[cfg(test)] a: { %s 1 }, b: 2 }; }"):
            with self.subTest(test=test):
                self.assertEqual(modules({"src/lib.rs": test % imp, "src/imp.rs": ""}), {"src/imp.rs": ["src/lib.rs"]})


class WhatMakesAMacroPackage(unittest.TestCase):
    """Which macro_rules! may declare modules, so that no file of their package is a test by its declarations, each
    answer rustc's: a test's #[path] names util.rs too, so only a macro's declaring it keeps it code."""

    TESTS = "#[cfg(test)]\n#[path = \"%s\"]\nmod t;\n"

    def check(self, lib, at, expected):
        files = {"src/lib.rs": lib + self.TESTS % at, "src/" + at: ""}
        self.assertEqual(modules(files), {"src/" + at: ["src/lib.rs"]} if expected == "test" else {})

    def test_what_isnt_one(self):
        # An inline module's mod $m {}, a $name that isn't after mod, a body that declares nothing.
        for lib in ("macro_rules! wrap { ($m:ident) => { pub mod $m {} }; }\nwrap!(util);\n",
                    "macro_rules! touch { ($e:ident) => { pub fn touched() { let $e = 1; $e; } }; }\ntouch! { util }\n",
                    "macro_rules! noop { ($e:ident) => {}; }\nnoop! { util }\n",
                    "macro_rules! items { ($($i:item)*) => { $($i)* } }\nitems! { pub fn util() {} }\n"):
            with self.subTest(lib=lib):
                self.check(lib, "util.rs", "test")

    def test_what_is(self):
        # Its body in any bracket, a comment anywhere in its head; mod past a comment or no space; a #[path] on the
        # declaration, or on the inline module around it; an inline module named by a $name; a fixed name; a raw
        # name; attributes, a visibility, tts, mod in its pattern; one a macro defines; and whatever the calls: past
        # a comment, spaced, by a path, in another macro's call, in [ ], with a string, a ; or an expression.
        plain = "macro_rules! modules { ($($m:ident),* $(,)?) => { $(pub mod $m;)* }; ($($m:ident),* ; $e:expr) => " \
                "{ $(pub mod $m;)* }; ($($m:ident => $s:literal),*) => { $(pub mod $m;)* } }\n"
        for lib, at in (
                ("macro_rules! m ( ($x:ident) => { pub mod $x; } );\nm!(util);\n", "util.rs"),
                ("macro_rules! m [ ($x:ident) => { pub mod $x; } ];\nm!(util);\n", "util.rs"),
                ("macro_rules! m /* c */ ( ($x:ident) => { pub mod $x; } );\nm!(util);\n", "util.rs"),
                ("macro_rules! /* c */ m { ($x:ident) => { pub mod $x; } }\nm!(util);\n", "util.rs"),
                ("macro_rules /* c */ ! m { ($x:ident) => { pub mod $x; } }\nm!(util);\n", "util.rs"),
                ("macro_rules! m { ($x:ident) => { pub mod /* c */ $x; } }\nm!(util);\n", "util.rs"),
                ("macro_rules! m { ($x:ident) => { pub mod // c\n $x; } }\nm!(util);\n", "util.rs"),
                ("macro_rules! m { ($x:ident) => { pub mod$x; } }\nm!(util);\n", "util.rs"),
                ("macro_rules! m { ($x:ident) => { #[path = \"gen/x.rs\"] pub mod $x; } }\nm!(util);\n", "gen/x.rs"),
                ("macro_rules! m { ($x:ident) => { #[path = \"p\"] pub mod o { pub mod $x; } } }\nm!(util);\n",
                 "p/util.rs"),
                ("macro_rules! m { ($o:ident, $x:ident) => { pub mod $o { pub mod $x; } } }\nm!(outer, util);\n",
                 "outer/util.rs"),
                ("macro_rules! m { ($x:ident) => { pub mod outer { pub mod $x; } }; }\nm!(util);\n", "outer/util.rs"),
                ("macro_rules! m { () => { pub mod util; } }\nm!();\n", "util.rs"),
                ("macro_rules! r#modules { ($($m:ident),*) => { $(pub mod $m;)* } }\nmodules!(util);\n", "util.rs"),
                ("macro_rules! modules { ($($(#[$a:meta])* $m:ident),*) => { $($(#[$a])* mod $m;)* } }\n"
                 "modules!(#[allow(dead_code)] util);\n", "util.rs"),
                ("macro_rules! modules { ($($v:vis $m:ident),*) => { $($v mod $m;)* } }\nmodules!(pub util);\n",
                 "util.rs"),
                ("macro_rules! modules { ($($t:tt)*) => { $(pub mod $t;)* } }\nmodules!(util);\n", "util.rs"),
                ("macro_rules! modules { ($(mod $m:ident;)*) => { $(pub mod $m;)* } }\nmodules! { mod util; }\n",
                 "util.rs"),
                ("macro_rules! make { () => { macro_rules! modules { ($m:ident) => { pub mod $m; } } } }\nmake!();\n"
                 "modules!(util);\n", "util.rs"),
                (plain + "modules! /* c */ (util);\n", "util.rs"), (plain + "modules ! ( util ) ;\n", "util.rs"),
                ("#[macro_export]\n" + plain + "crate::modules!(util);\n", "util.rs"),
                ("#[macro_export]\n" + plain + "self::modules! { util }\n", "util.rs"),
                (plain + "macro_rules! wrap { ($($t:tt)*) => { $($t)* } }\nwrap! { modules!(util); }\n", "util.rs"),
                (plain + "modules![util];\n", "util.rs"), (plain + "modules!(util => \"x\");\n", "util.rs"),
                (plain + "modules!(util; 1 + 1);\n", "util.rs"), (plain + "modules!(\n    util, // helpers\n);\n",
                                                                  "util.rs"),
                (plain + "modules!(\n    util, /* helpers */\n);\n", "util.rs"),
                (plain + "modules!(r#util);\n", "util.rs"),
                (plain + "mod a { }\nmodules!(util);\n", "util.rs"),
                ("macro_rules! make { ($d:tt) => { macro_rules! modules { ($d m:ident) => { pub mod $d m; } } } }\n"
                 "make!($);\nmodules!(util);\n", "util.rs"),
                ("#![feature(decl_macro)]\nmacro modules($m:ident) { pub mod $m; }\nmodules!(util);\n", "util.rs"),
                ("#![feature(decl_macro)]\nmacro /* c */ modules { ($m:ident) => { pub mod $m; } }\nmodules!(util);\n",
                 "util.rs")):
            with self.subTest(lib=lib):
                self.check(lib, at, "code")
        # Read for its mod$m alone (templated_nospace): rustc compiles a/helper.rs for tests alone, the limit.
        files = {"src/lib.rs": "macro_rules! modules { ($($m:ident),*) => { $(pub mod$m;)* }; }\n"
                               "modules!(a, helper);\n", "src/a.rs": "#[cfg(test)]\nmod helper;\n", "src/helper.rs": "",
                 "src/a/helper.rs": ""}
        self.assertEqual(modules(files), {})

    def test_forwarders_new_names_and_calls_in_tests(self):
        # A forwarder (w_forwarder_helper), a new name (w_renamed_import); and the limit: a call in test code or in
        # a test module (w_calls_in_test_code), whose files rustc compiles for tests alone, as probe.rs, stay measured.
        decl = "macro_rules! decl { ($m:ident) => { pub mod $m; } }\n"
        files = {"src/lib.rs": decl + "macro_rules! decls { ($($m:ident),*) => { $( decl!($m); )* } }\n"
                               "decls!(util, net);\n", "src/net.rs": "", "src/util.rs": "",
                 "src/main.rs": "#[cfg(test)]\n#[path = \"util.rs\"]\nmod util;\nfn main() {}\n"}
        self.assertEqual(modules(files), {})
        self.check(decl + "use decl as mods;\nmods!(util);\n", "util.rs", "code")
        files = {"src/lib.rs": decl + "#[cfg(test)]\nmod checks {\n    decl!(inline_helper);\n}\n"
                               "#[cfg(test)]\nmod probe;\n",
                 "src/probe.rs": "decl!(file_helper);\n", "src/checks/inline_helper.rs": "",
                 "src/probe/file_helper.rs": ""}
        self.assertEqual(modules(files), {})

    MAN, EXP = "[package]\nname = \"%s\"\n", "#[macro_export]\nmacro_rules! modules { ($m:ident) => { pub mod $m; } }\n"
    LOCAL, NEWER = "macro_rules! modules { ($m:ident) => { pub mod $m; } }\n", "#![feature(decl_macro)]\n"
    IMPORT = "macro_rules! import { ($p:literal, $m:ident) => { #[path = $p] pub mod $m; } }\n"
    KEPT = {"b/src/util.rs": ["b/src/lib.rs"]}  # A test, by rustc too.

    def packages(self, cases):
        # Per case, a's lib, b's and other files, and the tests: b/src/util.rs, named only by a test's #[path] in
        # b's lib, is code where nothing else is said.
        for a, b, more, expected in cases:
            files = {"a/Cargo.toml": self.MAN % "a", "a/src/lib.rs": a, "b/Cargo.toml": self.MAN % "b",
                     "b/src/lib.rs": b + self.TESTS % "util.rs", "b/src/util.rs": ""}
            files.update(more)
            with self.subTest(files=files):
                self.assertEqual(modules(files), expected)

    def test_names_another_package_calls(self):
        # Each rustc's: a pub use wherever it starts, past comments, in a module, of raw names, in a group (V1); a
        # macro_rules! exported in another's body, two deep, by $d (V2); a macro 2.0, with arms, past comments,
        # one that calls a private one, by its path, from a module of its own (V3).
        exp, newer, kept = self.EXP, self.NEWER, self.KEPT
        pub = "#[macro_export]\nmacro_rules! fwd { ($m:ident) => { modules!($m); } }\n"
        self.packages([(a, b, more, {}) for a, b, more in (
            (exp + "mod x {} pub use modules as mods;\n", "a::mods!(util);\n", {}),
            (exp + "pub /* c */ use crate::modules /* c */ as // d\n mods;\n", "a::mods!(util);\n", {}),
            (exp + "#[doc(hidden)] pub use crate::modules as mods;\n", "a::mods!(util);\n", {}),
            (exp + "pub mod re { pub use crate::modules as mods; }\n", "a::re::mods!(util);\n", {}),
            (exp + "pub use crate::r#modules as r#mods;\n", "a::mods!(util);\n", {}),
            (exp + "pub use crate::{modules as mods, modules as more};\n", "a::more!(util);\n", {}),
            ("macro_rules! make { () => { #[macro_export] macro_rules! modules { ($m:ident) => { pub mod $m; } } } }\n"
             "make!();\n", "a::modules!(util);\n", {}),
            ("macro_rules! make { () => { macro_rules! mk2 { () => { #[macro_export] macro_rules! modules { ($m:ident) "
             "=> { pub mod $m; } } } } mk2!(); } }\nmake!();\n", "a::modules!(util);\n", {}),
            ("macro_rules! make { ($d:tt) => { #[macro_export] macro_rules! modules { ($d m:ident) => { pub mod $d m; "
             "} } } }\nmake!($);\n", "a::modules!(util);\n", {}),
            (newer + "pub macro modules($m:ident) { pub mod $m; }\n", newer + "a::modules!(util);\n", {}),
            (newer + "pub macro modules { ($m:ident) => { pub mod $m; } }\n", newer + "a::modules!(util);\n", {}),
            (newer + "pub macro /* c */ modules /* c */ ($m:ident) /* c */ { pub mod $m; }\n",
             newer + "a::modules!(util);\n", {}),
            (newer + "macro modules($m:ident) { pub mod $m; }\npub macro fwd($m:ident) { modules!($m); }\n",
             newer + "a::fwd!(util);\n", {}),
            (newer + "pub(crate) macro modules($m:ident) { pub mod $m; }\npub macro fwd($m:ident) "
             "{ crate::modules!($m); }\n", newer + "a::fwd!(util);\n", {}),
            (newer + "mod m;\npub use m::fwd;\n", newer + "a::fwd!(util);\n", {"a/src/m.rs": "macro modules($m:ident) "
             "{ pub mod $m; }\npub macro fwd($m:ident) { modules!($m); }\n"}))] + [
            # A macro an exported one makes, named by the call, calling one that declares.
            (exp + "#[macro_export]\nmacro_rules! maker { ($n:ident) => { macro_rules! $n { ($m:ident) => { "
             "$crate::modules!($m); } } } }\n", "a::maker!(fwd2);\nfwd2!(util);\n", {}, {})] + [
            # And what rustc compiles for tests alone: b only names an exported macro whose call of a module macro
            # of a's no other crate may make, a name a use gives, which only its own file has, or one as _ gives,
            # or a word that holds the name.
            (self.LOCAL + pub, "pub fn fwd() {}\n", {}, kept),
            (exp, "pub fn m3() {}\n", {"c/Cargo.toml": self.MAN % "c", "c/src/lib.rs": "use a::modules as m3;\n"},
             kept),
            (exp + "pub use crate::modules as _;\n", "pub fn f() { let _ = 1; }\n", {}, kept),
            (exp, "pub fn my_modules() {}\n", {}, kept)])
        # A rename of a rename, in a third package.
        files = {"a/Cargo.toml": self.MAN % "a", "a/src/lib.rs": exp, "b/Cargo.toml": self.MAN % "b",
                 "b/src/lib.rs": "pub use a::modules as m2;\n", "c/Cargo.toml": self.MAN % "c",
                 "c/src/lib.rs": "b::m2!(util);\n" + self.TESTS % "util.rs", "c/src/util.rs": ""}
        self.assertEqual(modules(files), {})

    def test_files_another_package_compiles(self):
        # Each rustc's: a's crate brings in b's x.rs by a #[path], or an include!, and b's y.rs through it; the
        # module a's macro declares there is b's (V4). Not by a declaration for tests alone, whose file is a test,
        # from a marked file or from a test crate's root, nor through a link, whose file declares from where the
        # link is.
        local, x, kept = self.LOCAL, {"b/src/x.rs": "modules!(util);\n"}, self.KEPT
        self.packages([
            (local + "#[path = \"../../b/src/x.rs\"]\nmod x;\n", "", x, {}),
            (local + "include!(\"../../b/src/x.rs\");\n", "", x, {}),
            (local + "#[path = \"../../b/src/x.rs\"]\nmod x;\n", "", {"b/src/x.rs": "mod y;\n", "b/src/y.rs":
             "modules!(util);\n", "b/src/y/util.rs": "", "b/src/lib.rs": self.TESTS % "y/util.rs"}, {}),
            (local + "#[cfg(test)]\n#[path = \"../../b/src/x.rs\"]\nmod x;\n", "", x,
             {**kept, "b/src/x.rs": ["a/src/lib.rs"]}),
            (local + "mod m;\n", "", dict(x, **{"a/src/m.rs": "#![cfg(test)]\n#[path = \"../../b/src/x.rs\"]\nmod x;\n"
                                                 }),
             {**kept, "a/src/m.rs": "marked", "b/src/x.rs": ["a/src/m.rs"]}),
            (local, "", dict(x, **{"a/tests/it.rs": "#[path = \"../../b/src/x.rs\"]\nmod x;\n"}),
             {**kept, "a/tests/it.rs": "crate"})])
        files = {"a/Cargo.toml": self.MAN % "a", "a/src/lib.rs": local + "mod x;\n", "a/src/x/util.rs": "",
                 "a/src/x.rs": support.Link("../../b/src/x.rs"), "b/Cargo.toml": self.MAN % "b", "b/src/util.rs": "",
                 "b/src/x.rs": "modules!(util);\n", "b/src/lib.rs": "#[cfg(test)]\nmod util;\n"}
        repo = support.Repo("macro-link")
        repo.commit("2026-01-05", "Start", files)
        repo.done()
        found = support.load("scoping").rust_test_modules(
            sorted(files), lambda paths: dict((p, files[p]) for p in paths if isinstance(files[p], str)),
            support.load("scoping").tracked_links(repo.path, "HEAD"))
        self.assertEqual(sorted(found), ["b/src/util.rs"])
        # An inline module whose #[path] names b's folder, a call of a's macro in it (Z1).
        files = {"a/Cargo.toml": self.MAN % "a", "a/src/lib.rs": local + "#[path = \"../../b/src\"]\nmod reach {\n    "
                 "modules!(util);\n}\n", "b/Cargo.toml": self.MAN % "b", "b/src/lib.rs": "#[cfg(test)]\nmod util;\n",
                 "b/src/util.rs": ""}
        self.assertEqual(modules(files), {})
        # A workspace's root package, and a second hop from b to c.
        files = {"Cargo.toml": self.MAN % "root",
                 "src/lib.rs": local + "#[path = \"../m/src/shared.rs\"]\nmod shared;\n",
                 "m/Cargo.toml": self.MAN % "m", "m/src/shared.rs": "modules!(util);\n", "m/src/util.rs": "",
                 "m/src/lib.rs": "#[cfg(test)]\nmod util;\n"}
        self.assertEqual(modules(files), {})
        files = {"a/Cargo.toml": self.MAN % "a", "a/src/lib.rs": local + "#[path = \"../../b/src/x.rs\"]\nmod x;\n",
                 "b/Cargo.toml": self.MAN % "b", "b/src/x.rs": "#[path = \"../../c/src/y.rs\"]\nmod y;\n",
                 "b/src/lib.rs": "", "c/Cargo.toml": self.MAN % "c", "c/src/y.rs": "modules!(util);\n",
                 "c/src/util.rs": "", "c/src/lib.rs": "#[cfg(test)]\nmod util;\n"}
        self.assertEqual(modules(files), {})

    def test_paths_in_module_macros(self):
        # Each rustc's: a #[path] in a module macro's body, by a cfg_attr, on an inline module; one a call gives,
        # through a forwarder's call or its body, or as an attribute (V5); and one an exported macro's call gives in b,
        # plainly or by the name a pub use gives it, or a call of a's in b's file a's crate brings in, naming c's file.
        imp, b_util, kept = self.IMPORT, "../../b/src/util.rs", self.KEPT
        fwd = "macro_rules! fwd { () => { import!(\"%s\", util); } }\n" % b_util
        self.packages([(a, "", more, {}) for a, more in (
            ("macro_rules! modules { ($($m:ident),*) => { $(#[path = \"%s\"] pub mod $m;)* } }\nmodules!(util);\n"
             % b_util, {}),
            ("macro_rules! modules { ($m:ident) => { #[cfg_attr(not(test), path = \"%s\")] pub mod $m; } }\n"
             "modules!(util);\n" % b_util, {"a/src/util.rs": ""}),
            ("macro_rules! modules { ($m:ident) => { #[path = \"../../b/src\"] pub mod o { pub mod $m; } } }\n"
             "modules!(util);\n", {}),
            (imp + "import!(\"%s\", util);\n" % b_util, {}),
            (imp + "macro_rules! fwd { ($p:literal) => { import!($p, util); } }\nfwd!(\"%s\");\n" % b_util, {}),
            (imp + fwd + "fwd!();\n", {}), ("#[macro_use]\nmod defs;\nfwd!();\n", {"a/src/defs/mod.rs": imp + fwd}),
            ("macro_rules! modules { ($(#[$a:meta])* $m:ident) => { $(#[$a])* pub mod $m; } }\n"
             "modules!(#[path = \"%s\"] util);\n" % b_util, {}),
            ("macro_rules! modules { ($m:ident) => { #[path = \"../..\"] pub mod o { pub mod b { pub mod src { "
             "pub mod $m; } } } } }\nmodules!(util);\n", {}))] + [
            # And for tests alone: path = in a body's code, or a #[path] on an inline module that holds no module.
            ("macro_rules! modules { ($m:ident) => { pub mod $m; pub fn f() -> &'static str { let path = \"%s\"; path "
             "} } }\nmodules!(x);\n" % b_util, "", {"a/src/x.rs": ""}, kept),
            ("macro_rules! m { () => { #[path = \"../../b/src\"] pub mod o { pub fn f() {} } } }\nm!();\nmod x;\n", "",
             {"a/src/x.rs": ""}, kept)])
        for rename, name in (("", "import"), ("pub use import as imp;\n", "imp")):
            files = {"a/Cargo.toml": self.MAN % "a", "a/src/lib.rs": "#[macro_export]\n" + imp + rename,
                     "b/Cargo.toml": self.MAN % "b", "b/src/lib.rs": "a::%s!(\"../../c/src/util.rs\", util);\n" % name,
                     "c/Cargo.toml": self.MAN % "c", "c/src/lib.rs": "#[cfg(test)]\nmod util;\n", "c/src/util.rs": ""}
            with self.subTest(rename=rename):
                self.assertEqual(modules(files), {})
        files.update({"a/src/lib.rs": imp + "#[path = \"../../b/src/x.rs\"]\nmod x;\n", "b/src/lib.rs": "",
                      "b/src/x.rs": "import!(\"../../c/src/util.rs\", util);\n"})
        self.assertEqual(modules(files), {})
        # But not where a's crate brings it in for tests alone.
        files.update({"a/src/lib.rs": imp + "mod t;\n",
                      "a/src/t.rs": "#[cfg(test)]\n#[path = \"../../b/src/x.rs\"]\nmod x;\n"})
        self.assertEqual(modules(files), {"b/src/x.rs": ["a/src/t.rs"], "c/src/util.rs": ["c/src/lib.rs"]})
        # A module in inline ones in a folder a #[path] names, in a package below that folder.
        files = {"a/Cargo.toml": self.MAN % "a", "w/b/Cargo.toml": self.MAN % "b", "w/b/src/util.rs": "",
                 "a/src/lib.rs": "macro_rules! modules { ($m:ident) => { #[path = \"../../w\"] pub mod o { pub mod b { "
                                 "pub mod src { pub mod $m; } } } } }\nmodules!(util);\n",
                 "w/b/src/lib.rs": "#[cfg(test)]\nmod util;\n"}
        self.assertEqual(modules(files), {})

    def test_a_nested_cfg_attr(self):
        # Its path is a file the declaration may name, code: not(test) holds outside tests.
        files = {"src/lib.rs": "#[cfg_attr(not(test), cfg_attr(not(windows), path = \"real.rs\"))]\nmod fake;\n"
                               "#[cfg(test)]\n#[path = \"real.rs\"]\nmod real_again;\n", "src/real.rs": "",
                 "src/fake.rs": ""}
        self.assertEqual(modules(files), {})


class WhatTheyPrint(unittest.TestCase):
    """The reasons, the Test files line and when the working tree's line is printed, by the rule."""

    def test_the_words(self):
        scoping = support.load("scoping")
        found = {"x.rs": ("declared", frozenset(["a.rs", "b.rs"]), frozenset(["b.rs"]))}
        self.assertEqual(scoping.rust_test_reason("x.rs", found), "one of Rust's test modules, declared only for "
                         "tests, in a.rs, and declared in b.rs, in code compiled only for tests")
        found = dict([("m%d.rs" % k, ("marked", frozenset(), None)) for k in range(6)] +
                     [("c%d.rs" % k, ("crate", frozenset(), "Cargo.toml")) for k in range(6)])
        said = scoping.rust_tests_said(sorted(found), found, "THERE")
        self.assertIn("m3.rs, m4.rs and 1 more; ", said)
        self.assertIn("c3.rs, c4.rs and 1 more. THERE", said)
        self.assertEqual(scoping.test_reason("Tests/cap.rs"), "in a folder named Tests")
        # Five doubts named, then how many more.
        doubts = [("d%d.php" % k, "why") for k in range(6)]
        self.assertNotIn("more", support.load("measure").doubts_said(doubts[:5]))
        self.assertIn("d4.php (why); and 1 more.", support.load("measure").doubts_said(doubts))

    def test_list_tests_with_none(self):
        repo = support.Repo("none-listed")
        repo.commit("2026-01-05", "Start", {"src/lib.rs": "pub fn f() {\n}\n"})
        repo.done()
        self.assertEqual(support.run("measure.py", "-C", repo.path, "--list-tests").out,
                         "none-listed, scope: (everything)\nTest files set aside: none in the scope.\n")

    def test_when_the_working_tree_line_is_printed(self):
        repo = support.Repo("tree-lines")
        repo.commit("2026-01-05", "Start", {"src/lib.rs": "#[cfg(test)]\nmod probe;\n", "src/probe.rs": "fn p() {\n}\n",
                                             "Cargo.toml": "[package]\n", "Cargo.lock": "", "rustfmt.toml": "",
                                             "app.py": "x = 1\n"})
        repo.done()
        line = "Rust's test modules are read here"
        for path in ("Cargo.lock", "rustfmt.toml"):  # Neither decides which files are tests.
            with self.subTest(path=path):
                repo.write(path, "changed\n")
                self.assertNotIn(line, support.run("measure.py", "-C", repo.path).out)
                support.git(repo.path, "checkout", "--", path)
        repo.write("Cargo.toml", "[package]\nname = \"x\"\n")
        self.assertIn("differs from HEAD in 1 .rs, Cargo.toml or symlink file;",
                      support.run("measure.py", "-C", repo.path).out)
        # Where no Rust is read, as for a scope of app.py, neither says so.
        for script in ("measure.py", "heatmap.py"):
            with self.subTest(script=script):
                self.assertNotIn(line, support.run(script, "-C", repo.path, "app.py").out)
        # Nor where there's no HEAD to differ from.
        bare = support.new_folder("no-head")
        support.git(bare, "init", "-q")
        for path, text in (("src/lib.rs", "#[cfg(test)]\nmod probe;\n"), ("src/probe.rs", "fn p() {\n}\n")):
            os.makedirs(os.path.dirname(os.path.join(bare, path)), exist_ok=True)
            open(os.path.join(bare, path), "w").write(text)
        support.git(bare, "add", "-A")
        self.assertNotIn(line, support.run("measure.py", "-C", bare).out)


class WhatTheMutantsChanged(unittest.TestCase):
    """Answers the tests review's mutants of round 10's code changed and no test noticed, each rustc's, or the rule's
    where rustc compiles none of the files."""

    T, MAN = "#[cfg(test)]\n#[path = \"%s\"]\nmod t;\n", "[package]\nname = \"k\"\n"

    def check(self, cases):
        for files, expected in cases:
            with self.subTest(files=files):
                self.assertEqual(modules(files), expected)

    def test_includes(self):
        t, man, built = self.T, self.MAN, 'include!(concat!(env!("CARGO_MANIFEST_DIR"), "/src/%s"));\n'
        self.check([
            # Each include!'s strings its own; a ) that closes its argument, the string after it the code's; OUT_DIR
            # only in one; a join before one on OUT_DIR kept.
            ({"src/lib.rs": 'include!(concat!("x", ".rs"));\ninclude!(concat!("ut", "il.rs"));\n' + t % "util.rs",
              "src/x.rs": "", "src/util.rs": ""}, {}),
            ({"Cargo.toml": man, "src/n.rs": "", "src/util.rs": "", "src/lib.rs": "pub fn f() -> usize {\n    " +
              built.strip()[:-1] % "n.rs" + ' + "util.rs".len()\n}\n' + t % "util.rs"},
             {"src/util.rs": ["src/lib.rs"]}),
            ({"Cargo.toml": man, "src/gen.rs": "", "src/lib.rs": built % "gen.rs" + "pub fn out() -> Option<&'static "
              "str> {\n    option_env!(\"OUT_DIR\")\n}\n" + t % "gen.rs"}, {}),
            ({"Cargo.toml": man, "src/util.rs": "", "src/lib.rs": 'include!(concat!("ut", "il.rs"));\npub mod gen '
              '{\n    include!(concat!(env!("OUT_DIR"), "/gen.rs"));\n}\n' + t % "util.rs"}, {}),
            # include![...]: its ] closes it, and its [ ] count in its depth.
            ({"src/n.rs": "", "src/util.rs": "", "src/lib.rs": "pub fn f() -> &'static str {\n    match "
              "include![\"n.rs\"] {\n        1 => \"util.rs\",\n        _ => \"\",\n    }\n}\n" + t % "util.rs"},
             {"src/util.rs": ["src/lib.rs"]}),
            ({"Cargo.toml": man, "src/x.rs": "", "src/lib.rs": "include![" + built.strip()[9:-2] % "x.rs" + "];\n" +
              t % "x.rs"}, {}),
            # A built path from its own package's folder; with none, past ./, and up a ..
            ({"Cargo.toml": man, "src/lib.rs": "#[cfg(test)]\nmod x;\n", "src/x.rs": "", "crates/a/Cargo.toml": man,
              "crates/a/src/x.rs": "", "crates/a/src/lib.rs": built % "x.rs"}, {"src/x.rs": ["src/lib.rs"]}),
            ({"a/src/lib.rs": 'include!(concat!(env!("SRC"), "/./x.rs"));\n', "a/src/x.rs": "",
              "b/lib.rs": t % "../a/src/x.rs"}, {}),
            ({"a/src/lib.rs": 'include!(concat!(env!("SRC"), "/../x.rs"));\n', "a/x.rs": "", "a/src/x.rs": "",
              "b/lib.rs": t % "../a/src/x.rs"}, {"a/src/x.rs": ["b/lib.rs"]})])

    def test_cfg_attrs_and_rounds(self):
        # The default's file, by its cfg, declared only for tests; test where neither of two cfg_attrs' holds.
        scoping = support.load("scoping")
        files = {"src/lib.rs": "#[cfg_attr(not(test), path = \"live.rs\")]\nmod mock;\n", "src/mock.rs": "",
                 "src/live.rs": ""}
        found = scoping.rust_test_modules(sorted(files), lambda paths: dict((p, files[p]) for p in paths))
        self.assertEqual(scoping.rust_test_reason("src/mock.rs", found),
                         "one of Rust's test modules, declared only for tests, in src/lib.rs")
        # In test code, two cfg_attrs naming one file, in either order: only that code needs test, not the
        # declaration, which is there either way (M092).
        pair = ("#[cfg_attr(not(test), path = \"x.rs\")]\n", "#[cfg_attr(test, path = \"x.rs\")]\n")
        for first, second in (pair, pair[::-1]):
            files = {"src/lib.rs": "#[cfg(test)]\nmod tests {\n" + first + second + "mod m;\n}\n", "src/tests/x.rs": ""}
            found = scoping.rust_test_modules(sorted(files), lambda paths: dict((p, files[p]) for p in paths))
            self.assertEqual(scoping.rust_test_reason("src/tests/x.rs", found), "one of Rust's test modules, "
                             "declared in src/lib.rs, in code compiled only for tests")
        pair = ("#[cfg_attr(not(test), path = \"a.rs\")]\n", "#[cfg_attr(feature = \"x\", path = \"b.rs\")]\n")
        self.check([({"src/lib.rs": first + second + "mod m;\n", "src/a.rs": "", "src/b.rs": "", "src/m.rs": ""},
                     {"src/m.rs": ["src/lib.rs"]}) for first, second in (pair, pair[::-1])] + [
            # Files no reading reaches: a cycle, each read; one ready only once no other could bring it in; and a
            # file's declaration of itself no other's.
            ({"src/lib.rs": "", "src/x.rs": "#[cfg(test)]\n#[path = \"y.rs\"]\nmod y;\n",
              "src/y.rs": "#[path = \"x.rs\"]\nmod x;\n"}, {}),
            ({"src/lib.rs": "", "src/b.rs": "pub mod s;\n", "src/b/s.rs": "#[path = \"r.rs\"]\nmod r;\n",
              "src/b/r.rs": "mod l;\nmod t;\n", "src/b/r/l.rs": "#[cfg(test)]\n#[path = \"t.rs\"]\nmod tt;\n",
              "src/b/r/t.rs": "mod zz;\n"}, {"src/b/r/t.rs": ["src/b/r/l.rs"]}),
            ({"src/lib.rs": "", "src/x.rs": "#[path = \"x.rs\"]\nmod me;\n#[cfg(test)]\n#[path = \"z1.rs\"]\nmod z1;\n",
              "src/z1.rs": "#[cfg(test)]\n#[path = \"z2.rs\"]\nmod z2;\n",
              "src/z2.rs": "#[cfg(test)]\n#[path = \"z1.rs\"]\nmod z1;\n"},
             {"src/z1.rs": ["src/x.rs", "src/z2.rs"], "src/z2.rs": ["src/z1.rs"]})])


    def test_a_word_and_a_macro_body(self):
        # mod in a longer word declares nothing (tk10); a macro_rules! body's brackets open no block, so the mod in
        # one, in a module whose #[path] names b's folder, is b's (rm39). Each rustc's.
        self.check([({"src/lib.rs": "#![allow(non_upper_case_globals)]\nconst modx: u8 = 1;\npub const A: [u8; 2] = "
                                    "[modx; 2];\n#[cfg(test)]\nmod x;\n", "src/x.rs": ""},
                     {"src/x.rs": ["src/lib.rs"]}),
                    ({"a/Cargo.toml": self.MAN, "a/src/lib.rs": "#[path = \"../../b/src\"]\nmod o {\n    macro_rules! "
                      "m { () => { mod y; } }\n    m!();\n}\n", "b/Cargo.toml": self.MAN, "b/src/y.rs": "",
                      "b/src/lib.rs": "#[cfg(test)]\nmod y;\n"}, {})])


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
        # Each folder above that holds it, the repo's top too.
        files = {"a/src/lib.rs": "include!(concat!(env!(\"SRC\"), \"/x.rs\"));\n", "a/src/x.rs": "", "a/x.rs": "",
                 "x.rs": "", "b/lib.rs": "".join("#[cfg(test)]\n#[path = \"%s\"]\nmod t%d;\n" % (p, k) for k, p in
                                               enumerate(("../a/src/x.rs", "../a/x.rs", "../x.rs")))}
        self.assertEqual(modules(files), {})
        # Where more folders hold its first part than lie above it.
        files = {"a/src/lib.rs": "include!(concat!(env!(\"SRC\"), \"/shared/x.rs\"));\n", "a/shared/x.rs": "",
                 "e/lib.rs": "#[cfg(test)]\n#[path = \"../a/shared/x.rs\"]\nmod x;\n"}
        files.update(("%s/shared/y.rs" % k, "") for k in "bcd")
        self.assertEqual(modules(files), {})

    def test_a_leading_backslash(self):
        # In the package, as Windows reads it: src/util.rs.
        files = {"Cargo.toml": "[package]\nname = \"k\"\n", "src/util.rs": "",
                 "src/lib.rs": "include!(concat!(env!(\"CARGO_MANIFEST_DIR\"), \"\\\\src\\\\util.rs\"));\n"
                               "#[cfg(test)]\n#[path = \"util.rs\"]\nmod t;\n"}
        self.assertEqual(modules(files), {})


if __name__ == "__main__":
    unittest.main()
