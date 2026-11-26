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
                (plain + "mod a { }\nmodules!(util);\n", "util.rs")):
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
        self.assertIn("differs from HEAD in 1 .rs or Cargo.toml file;", support.run("measure.py", "-C", repo.path).out)
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

    def test_a_leading_backslash(self):
        # In the package, as Windows reads it: src/util.rs.
        files = {"Cargo.toml": "[package]\nname = \"k\"\n", "src/util.rs": "",
                 "src/lib.rs": "include!(concat!(env!(\"CARGO_MANIFEST_DIR\"), \"\\\\src\\\\util.rs\"));\n"
                               "#[cfg(test)]\n#[path = \"util.rs\"]\nmod t;\n"}
        self.assertEqual(modules(files), {})


if __name__ == "__main__":
    unittest.main()
