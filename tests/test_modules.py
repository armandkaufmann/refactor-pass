"""Rust's test modules in files of their own (#[cfg(test)] mod tests;), known by the mod declarations that bring
them in: where a declaration points, as rustc finds a module's file; when every declaration of a file needs test;
and the two scripts setting the same files aside."""

import re
import unittest

try:
    from . import support
except ImportError:
    import support


def modules(files, tracked=None):
    """The files of a repo, given as {path: text}, that are tests by their declarations, each with the files
    that aren't tests whose declarations bring it in (its own files); tracked, if given, is what git tracks."""
    scoping = support.load("scoping")
    found = scoping.rust_test_modules(sorted(files if tracked is None else tracked),
                                      lambda paths: dict((p, files[p]) for p in paths if p in files))
    return dict((path, sorted(owners)) for path, owners in found.items())


class WhereADeclarationPoints(unittest.TestCase):
    """As the Reference's Module source filenames have it: beside a mod.rs, lib.rs or main.rs, name.rs or
    name/mod.rs in its folder; from any other file, in the folder of its name; an inline module adds its name, or
    its #[path], to the folder; and #[path] on the declaration."""

    def test_from_a_crate_root_and_from_mod_rs(self):
        files = {"src/lib.rs": "mod net;\nmod disk;\n#[cfg(test)]\nmod fixture;\n", "src/fixture.rs": "",
                 "src/net/mod.rs": "#[cfg(test)]\nmod probe;\n", "src/net/probe.rs": "",
                 "src/disk.rs": "#[cfg(test)]\nmod tests;\n", "src/disk/tests/mod.rs": ""}
        self.assertEqual(modules(files), {"src/fixture.rs": ["src/lib.rs"], "src/net/probe.rs": ["src/net/mod.rs"],
                                          "src/disk/tests/mod.rs": ["src/disk.rs"]})

    def test_a_module_file_looks_in_its_own_folder(self):
        # disk.rs, which lib.rs declares, is no crate root: its mod util; is disk/util.rs, not lib.rs's util.rs
        # beside it, which is code; and where disk/util.rs is missing, it's no file at all.
        files = {"src/lib.rs": "mod disk;\nmod util;\nmod cache;\n", "src/util.rs": "", "src/disk.rs":
                 "#[cfg(test)]\nmod util;\n", "src/disk/util.rs": "", "src/cache.rs": "#[cfg(test)]\nmod util;\n"
                 "#[cfg(test)]\nmod spare;\n", "src/spare.rs": ""}
        self.assertEqual(modules(files), {"src/disk/util.rs": ["src/disk.rs"]})

    def test_a_crate_root_with_another_name(self):
        # A binary's, an example's, a file no declaration could bring in: its modules are beside it, even where
        # a folder of its name holds a file of the module's name too.
        files = {"src/bin/tool.rs": "#[cfg(test)]\nmod checks;\n", "src/bin/checks.rs": "",
                 "src/bin/tool/checks.rs": "", "examples/demo.rs": "#[cfg(test)]\nmod scene;\n",
                 "examples/scene/mod.rs": ""}
        self.assertEqual(modules(files), {"src/bin/checks.rs": ["src/bin/tool.rs"],
                                          "examples/scene/mod.rs": ["examples/demo.rs"]})

    def test_a_file_no_known_file_reaches(self):
        # x.rs is where disk.rs's x could have been, but isn't: its own folder's first, as a module file's.
        files = {"src/lib.rs": "mod disk;\n", "src/disk.rs": "#[cfg(test)]\nmod x;\n", "src/disk/x.rs": "",
                 "src/x.rs": "#[cfg(test)]\nmod y;\n", "src/x/y.rs": "", "src/y.rs": ""}
        self.assertEqual(modules(files), {"src/disk/x.rs": ["src/disk.rs"], "src/x/y.rs": ["src/x.rs"]})

    def test_inline_modules_on_the_way(self):
        files = {"src/lib.rs": "mod disk;\npub mod outer {\n    #[cfg(test)]\n    mod inner;\n}\n",
                 "src/outer/inner.rs": "",
                 "src/disk.rs": "mod outer {\n    mod deeper {\n        #[cfg(test)]\n        mod inner;\n    }\n}\n",
                 "src/disk/outer/deeper/inner.rs": ""}
        self.assertEqual(modules(files), {"src/outer/inner.rs": ["src/lib.rs"],
                                          "src/disk/outer/deeper/inner.rs": ["src/disk.rs"]})

    def test_path_attributes(self):
        # On the declaration, from the file's own folder, the first of two, and the file it names is read as a
        # mod.rs, as rustc reads it; inside an inline module, from the module's folder; on an inline module, the
        # folder its modules go in.
        files = {"src/lib.rs": "mod disk;\nmod outer {\n    #[cfg(test)]\n    #[path = \"x.rs\"]\n    mod inner;\n}\n"
                               "#[path = \"other\"]\nmod named {\n    #[cfg(test)]\n    mod inner;\n}\n",
                 "src/disk.rs": "#[cfg(test)]\n#[path = \"checks/all.rs\"]\nmod checks;\n"
                                "#[cfg(test)]\n#[path = \"..\\\\shared\\\\probe.rs\"]\nmod probe;\n"
                                "#[cfg(test)]\n#[path = \"one.rs\"]\n#[path = \"two.rs\"]\nmod twice;\n",
                 "shared/probe.rs": "", "src/one.rs": "", "src/two.rs": "",
                 "src/checks/all.rs": "mod sub;\n", "src/checks/sub.rs": "", "src/checks/all/sub.rs": "",
                 "src/outer/x.rs": "", "src/other/inner.rs": ""}
        self.assertEqual(modules(files), {"src/checks/all.rs": ["src/disk.rs"], "src/checks/sub.rs": ["src/disk.rs"],
                                          "src/outer/x.rs": ["src/lib.rs"], "src/other/inner.rs": ["src/lib.rs"],
                                          "shared/probe.rs": ["src/disk.rs"], "src/one.rs": ["src/disk.rs"]})

    def test_raw_names_and_what_isnt_a_declaration(self):
        # mod r#match; is match.rs, and mod name; name.rs. Comments, nested ones too, strings, raw ones holding a
        # quote, a macro's pattern and an inline module declare nothing; a character's brace closes no module.
        files = {"src/lib.rs": "#[cfg(test)]\nmod r#match;\n// #[cfg(test)] mod note;\n/* #[cfg(test)] mod old; */\n"
                               "/* /* */ #[cfg(test)] mod older; */\nconst S: &str = \"#[cfg(test)] mod text;\";\n"
                               "const R: &str = r#\"a\" #[cfg(test)] mod quoted; \"#;\n"
                               "macro_rules! m { ($text:ident) => { #[cfg(test)] mod $text; } }\n"
                               "#[cfg(test)]\nmod inline {\n}\n#[cfg(test)]\nmod name;\n"
                               "mod outer {\n    const C: char = '}';\n    #[cfg(test)]\n    mod inner;\n}\n",
                 "src/match.rs": "", "src/note.rs": "", "src/old.rs": "", "src/older.rs": "", "src/text.rs": "",
                 "src/quoted.rs": "", "src/inline.rs": "", "src/name.rs": "",
                 "src/net/mod.rs": "#[cfg(test)]\nmod r#type;\n",
                 "src/net/type.rs": "", "src/outer/inner.rs": "", "src/inner.rs": ""}
        self.assertEqual(modules(files), {"src/match.rs": ["src/lib.rs"], "src/name.rs": ["src/lib.rs"],
                                          "src/net/type.rs": ["src/net/mod.rs"], "src/outer/inner.rs": ["src/lib.rs"]})

    def test_untracked_or_missing(self):
        # A declaration whose file isn't tracked, or isn't there, changes nothing; a file git doesn't track
        # declares nothing.
        files = {"src/lib.rs": "#[cfg(test)]\nmod gone;\n#[cfg(test)]\nmod loose;\n", "src/loose.rs": "",
                 "src/extra.rs": "#[cfg(test)]\nmod kept;\n", "src/kept.rs": ""}
        self.assertEqual(modules(files, ["src/lib.rs", "src/kept.rs"]), {})


class WhenItsATest(unittest.TestCase):
    """Every declaration that brings a file in needs test, by its cfg as cfg_needs_test reads it, or by the code
    it's in: an inline module compiled only for tests, a file that's a test by its declarations, or one marked
    #![cfg(test)] at its top."""

    def test_by_the_cfg(self):
        files = {"src/lib.rs": "#[cfg(all(test, unix))]\nmod probe;\n#[cfg(not(test))]\nmod live;\n"
                               "#[cfg(any(test, feature = \"testing\"))]\npub mod testing;\n"
                               "#[cfg(any(test))]\nmod mock;\n"
                               "#[cfg(test)]\n#[allow(dead_code)]\npub(crate) mod regression;\n"
                               "enum Mode {\n    Real,\n    #[cfg(test)]\n    Fake\n}\nmod normal;\n",
                 "src/probe.rs": "", "src/live.rs": "", "src/testing.rs": "", "src/mock.rs": "",
                 "src/regression.rs": "", "src/normal.rs": ""}
        self.assertEqual(modules(files), {"src/probe.rs": ["src/lib.rs"], "src/mock.rs": ["src/lib.rs"],
                                          "src/regression.rs": ["src/lib.rs"]})

    def test_in_a_macros_block(self):
        # As if the block weren't there, its cfg before the block's brace: a macro's that picks by cfg, another's.
        files = {"src/lib.rs": "pick! {\n    if #[cfg(test)] {\n        mod mockup;\n    } else {\n"
                               "        mod real;\n    }\n}\nwith_feature! {\n    mod plainly;\n}\n"
                               "#[cfg(test)]\nmod plainly;\n",
                 "src/mockup.rs": "", "src/real.rs": "", "src/plainly.rs": ""}
        self.assertEqual(modules(files), {"src/mockup.rs": ["src/lib.rs"]})

    def test_named_like_a_test_but_declared_plainly(self):
        files = {"src/lib.rs": "pub mod commands;\n", "src/commands/mod.rs": "pub mod test;\nmod run_tests;\n",
                 "src/commands/test.rs": "", "src/commands/run_tests.rs": ""}
        self.assertEqual(modules(files), {})

    def test_declared_twice(self):
        # Once for tests and once not: code. Twice for tests: a test.
        files = {"src/lib.rs": "#[cfg(test)]\nmod shared;\n#[cfg(test)]\nmod probe;\n",
                 "src/bin/tool.rs": "#[path = \"../shared.rs\"]\nmod shared;\n#[cfg(test)]\n#[path = \"../probe.rs\"]\n"
                                    "mod probe;\n", "src/shared.rs": "", "src/probe.rs": ""}
        self.assertEqual(modules(files), {"src/probe.rs": ["src/bin/tool.rs", "src/lib.rs"]})

    def test_a_test_modules_own_modules(self):
        # As far down as they go, each with the file whose test module it's in; and under an inline test module.
        files = {"src/lib.rs": "mod disk;\n",
                 "src/disk.rs": "#[cfg(test)]\nmod tests;\n#[cfg(test)]\nmod checks {\n    mod helper;\n}\n"
                                "mod plain {\n    #![cfg(test)]\n    mod inner;\n}\n",
                 "src/disk/tests.rs": "mod helpers;\n", "src/disk/tests/helpers.rs": "pub mod deep;\n",
                 "src/disk/tests/helpers/deep.rs": "", "src/disk/checks/helper.rs": "", "src/disk/plain/inner.rs": ""}
        self.assertEqual(modules(files), dict((p, ["src/disk.rs"]) for p in (
            "src/disk/tests.rs", "src/disk/tests/helpers.rs", "src/disk/tests/helpers/deep.rs",
            "src/disk/checks/helper.rs", "src/disk/plain/inner.rs")))

    def test_a_file_compiled_only_for_tests(self):
        # #![cfg(test)] first in it, after its comments: a test, and so are its modules.
        files = {"src/lib.rs": "mod mock;\nmod later;\nmod fake;\n",
                 "src/mock.rs": "//! A mock.\n#![cfg(test)]\nmod parts;\n", "src/mock/parts.rs": "",
                 "src/later.rs": "fn f() {}\n#![cfg(test)]\n", "src/fake.rs": "#![cfg(test)]\nfn f() {}\n"}
        self.assertEqual(modules(files), {"src/mock.rs": ["src/lib.rs"], "src/mock/parts.rs": ["src/lib.rs"],
                                          "src/fake.rs": ["src/lib.rs"]})

    def test_in_no_doubt(self):
        # The heatmap doubts a name that's a test only by a word at its end (by --test here), or a folder of tests
        # in which no file is named like one: not one of Rust's test modules, nor a folder that holds one.
        scoping, more = support.load("scoping"), ["*Test.rs"]
        modules = ["src/CheckTest.rs", "src/tests/mod.rs"]
        tests = modules + ["src/tests/data.json"]
        self.assertEqual([d[0] for d in scoping.doubtful_tests(tests, tests, more)], ["src/CheckTest.rs", "src/tests/"])
        self.assertEqual(scoping.doubtful_tests(tests, tests, more, dict.fromkeys(modules)), [])

    def test_a_cycle_through_path(self):
        # b.rs is declared for tests and from c.rs, which only b.rs declares: neither is shown to be a test,
        # as rustc would refuse the cycle anyway; the reading ends.
        files = {"src/lib.rs": "mod a;\n", "src/a.rs": "#[cfg(test)]\n#[path = \"b.rs\"]\nmod b;\n",
                 "src/b.rs": "#[path = \"a.rs\"]\nmod a;\n#[path = \"c.rs\"]\nmod c;\n",
                 "src/c.rs": "#[path = \"b.rs\"]\nmod b;\n"}
        self.assertEqual(modules(files), {})


# A crate whose tests are in files of their own: by their declarations (disk/checks.rs, its own module, and
# fixture.rs, names nothing else would take for tests), by name (cache_test.rs), by both (tests/mod.rs, in a
# folder named tests, though in no doubt), and code named like a test.
CRATE = {"src/lib.rs": "pub mod disk;\npub mod commands;\n#[cfg(test)]\nmod fixture;\n#[cfg(test)]\nmod tests;\n",
         "src/tests/mod.rs": "fn s() {\n}\n",
         "src/disk.rs": "pub fn read() {\n}\n#[cfg(test)]\nmod checks;\n",
         "src/disk/checks.rs": "mod helper;\n" + "fn t() {\n    f();\n}\n" * 40,
         "src/disk/checks/helper.rs": "fn h() {\n}\n", "src/fixture.rs": "fn mock() {\n    f();\n}\n" * 10,
         "src/cache_test.rs": "fn c() {\n}\n", "src/commands/mod.rs": "pub mod test;\n",
         "src/commands/test.rs": "pub fn run() {\n    go();\n}\n"}


def rows(out):
    """The table's files, in measure.py's output or the heatmap's."""
    return set(re.findall(r"(?m)^ +\d.*\s(src/\S+)(?: \(.*\))?$", out))


class BothScripts(unittest.TestCase):
    """measure.py and heatmap.py set the same files aside, and say which by their declarations."""

    @classmethod
    def setUpClass(cls):
        repo = support.Repo("modules")
        repo.commit("2026-01-05", "Start", CRATE)
        repo.commit("2026-01-06", "Change them all", dict((p, t + "\n") for p, t in CRATE.items()))
        repo.done()
        cls.repo = repo.path

    def test_measure(self):
        result = support.run("measure.py", "-C", self.repo)
        self.assertEqual(result.code, 0, result)
        self.assertEqual(rows(result.out), {"src/lib.rs", "src/disk.rs", "src/commands/mod.rs", "src/commands/test.rs"})
        self.assertIn("Test files: 5 set aside from the percentiles and the table, 3 of them Rust test modules in "
                      "files of their own, known by their declarations, not their names: src/disk/checks.rs, "
                      "src/disk/checks/helper.rs and src/fixture.rs.", result.out)
        self.assertNotIn("measured unless named as a test", result.out)
        self.assertNotIn("maybe not", result.out)

    def test_heatmap(self):
        result = support.run("heatmap.py", "-C", self.repo, "--top", "20")
        self.assertEqual(result.code, 0, result)
        self.assertEqual(rows(result.out), {"src/lib.rs", "src/disk.rs", "src/commands/mod.rs", "src/commands/test.rs"})
        self.assertIn("Test files: 5 changed in the window, set aside from the table and the pairs, 3 of them Rust "
                      "test modules in files of their own, known by their declarations.", result.out)
        self.assertNotIn("maybe not", result.out)

    def test_a_scope_that_leaves_the_declaration_out(self):
        for script in ("measure.py", "heatmap.py"):
            with self.subTest(script=script):
                result = support.run(script, "-C", self.repo, "src/disk")
                self.assertEqual(result.code, 0, result)
                self.assertIn("Test files: 2 ", result.out)
                self.assertEqual(rows(result.out), set())
                result = support.run(script, "-C", self.repo, "src/fixture.rs")
                self.assertIn(", 1 of them a Rust test module in a file of its own, known by its declaration",
                              result.out)

    def test_the_users_word_wins(self):
        # A file the user says isn't a test is measured; its own modules are still tests by their declarations.
        for script in ("measure.py", "heatmap.py"):
            with self.subTest(script=script):
                result = support.run(script, "-C", self.repo, "--not-test", "src/disk/checks.rs", "--top", "20")
                self.assertIn("src/disk/checks.rs", rows(result.out))
                self.assertIn("Test files: 4 ", result.out)
        for script in ("measure.py", "heatmap.py"):
            with self.subTest(script=script):
                result = support.run(script, "-C", self.repo, "--keep-tests", "--top", "20")
                self.assertNotIn("Test files:", result.out)
                self.assertIn("src/fixture.rs", rows(result.out))

    def test_show_names_how_it_was_known(self):
        result = support.run("measure.py", "-C", self.repo, "--show", "src/fixture.rs")
        self.assertEqual(result.code, 0, result)
        self.assertIn("src/fixture.rs: Rust, 30 code lines, band -, 10 functions", result.out)
        self.assertIn("A test file: one of Rust's test modules, compiled only for the tests of src/lib.rs; measured "
                      "whole here.", result.out)
        result = support.run("measure.py", "-C", self.repo, "--show", "src/disk/checks/helper.rs")
        self.assertIn("compiled only for the tests of src/disk.rs;", result.out)


class TiedTests(unittest.TestCase):
    """A test module's own file is the one whose declaration brings it in, whatever their names: it isn't
    among the production files a test changes with."""

    def test_its_own_file(self):
        repo = support.Repo("tied-modules")
        for n in range(1, 6):
            repo.commit("2026-01-%02d" % n, "Change %d" % n, {
                "src/lib.rs": "mod disk;\nmod a;\nmod b;\n", "src/disk.rs": "#[cfg(test)]\nmod checks;\n" +
                support.lines(n), "src/disk/checks.rs": support.lines(n), "src/a.rs": support.lines(n),
                "src/b.rs": support.lines(n)})
        repo.done()
        result = support.run("heatmap.py", "-C", repo.path)
        self.assertIn("  src/disk/checks.rs: 2 files, src/a.rs (5), src/b.rs (5)\n", result.out)


if __name__ == "__main__":
    unittest.main()
