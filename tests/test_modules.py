"""Rust's test modules in files of their own (#[cfg(test)] mod tests;), known by the mod declarations that bring
them in: where a declaration points, as rustc finds a module's file; when every declaration of a file needs test;
the crates Cargo builds, which never are; and the two scripts setting the same files aside."""

import os
import re
import unittest

try:
    from . import support
except ImportError:
    import support


def modules(files, tracked=None):
    """The files of a repo, given as {path: text}, that are tests by Rust's declarations, each with the files whose
    declarations bring it in, or "marked" for one marked #![cfg(test)] at its top, "crate" for a crate Cargo builds
    only as a test; tracked, if given, is what git tracks."""
    scoping = support.load("scoping")
    found = scoping.rust_test_modules(sorted(files if tracked is None else tracked),
                                      lambda paths: dict((p, files[p]) for p in paths if p in files))
    return dict((path, sorted(found[path][1]) if found[path][0] == "declared" else found[path][0]) for path in found)


def tests_in(files):
    """Only which files of a repo, given as {path: text}, are tests by Rust's declarations."""
    scoping = support.load("scoping")
    return sorted(scoping.rust_test_modules(sorted(files), lambda paths: dict((p, files[p]) for p in paths)))


class WhereADeclarationPoints(unittest.TestCase):
    """As rustc finds a module's file: beside a crate root or a mod.rs, name.rs or name/mod.rs in its folder; from
    any other file, in the folder of its name; an inline module adds its name, or its #[path], to the folder; and
    #[path] on the declaration."""

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

    def test_a_module_file_named_lib_rs(self):
        # Declared as a module, it's a module file: its modules are in a/lib/, not beside it.
        files = {"src/lib.rs": "mod a;\n", "src/a.rs": "mod lib;\n", "src/a/lib.rs": "#[cfg(test)]\nmod helper;\n",
                 "src/a/lib/helper.rs": "", "src/a/helper.rs": ""}
        self.assertEqual(modules(files), {"src/a/lib/helper.rs": ["src/a/lib.rs"]})

    def test_a_crate_root_with_another_name(self):
        # A binary's, an example's, a file no declaration could bring in: its modules are beside it, even where
        # a folder of its name holds a file of the module's name too.
        files = {"src/bin/tool.rs": "#[cfg(test)]\nmod checks;\n", "src/bin/checks/mod.rs": "",
                 "src/bin/tool/checks.rs": "", "examples/demo.rs": "#[cfg(test)]\nmod scene;\n",
                 "examples/scene/mod.rs": "", "gen/run.rs": "#[cfg(test)]\nmod part;\n", "gen/part.rs": "",
                 "gen/run/part.rs": ""}
        self.assertEqual(modules(files), {"src/bin/checks/mod.rs": ["src/bin/tool.rs"],
                                          "examples/scene/mod.rs": ["examples/demo.rs"], "gen/part.rs": ["gen/run.rs"]})

    def test_a_file_no_known_file_reaches(self):
        # x.rs is where disk.rs's x could have been, but isn't: its own folder's first, as a module file's.
        files = {"src/lib.rs": "mod disk;\n", "src/disk.rs": "#[cfg(test)]\nmod x;\n", "src/disk/x.rs": "",
                 "src/x.rs": "#[cfg(test)]\nmod y;\n", "src/x/y.rs": "", "src/y.rs": ""}
        self.assertEqual(modules(files), {"src/disk/x.rs": ["src/disk.rs"], "src/x/y.rs": ["src/x.rs"]})
        # A mod.rs is read as one.
        files = {"src/lib.rs": "mod a;\n", "src/a.rs": "mod x;\n", "src/x/mod.rs": "#[cfg(test)]\nmod y;\n",
                 "src/x/y.rs": "", "src/x/mod/y.rs": ""}
        self.assertEqual(modules(files), {"src/x/y.rs": ["src/x/mod.rs"]})

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
        # folder its modules go in, from the file's folder, without a module file's own.
        files = {"src/lib.rs": "mod disk;\nmod outer {\n    #[cfg(test)]\n    #[path = \"x.rs\"]\n    mod inner;\n}\n"
                               "#[path = \"other\"]\nmod named {\n    #[cfg(test)]\n    mod inner;\n}\n",
                 "src/disk.rs": "#[cfg(test)]\n#[path = \"checks/all.rs\"]\nmod checks;\n"
                                "#[cfg(test)]\n#[path = \"..\\\\shared\\\\probe.rs\"]\nmod probe;\n"
                                "#[cfg(test)]\n#[path = \"one.rs\"]\n#[path = \"two.rs\"]\nmod twice;\n"
                                "#[cfg(test)]\n#[path = \"p\"]\nmod inline {\n    mod helper;\n}\n"
                                "#[cfg(test)]\n#[path = \"notes/../via.rs\"]\nmod via;\n"
                                "#[cfg(test)]\n#[path = \"/src/far.rs\"]\nmod far;\n",
                 "shared/probe.rs": "", "src/one.rs": "", "src/two.rs": "", "src/p/helper.rs": "", "src/via.rs": "",
                 "via.rs": "", "src/src/far.rs": "", "src/far.rs": "",
                 "src/disk/p/helper.rs": "",
                 "src/checks/all.rs": "mod sub;\n", "src/checks/sub.rs": "", "src/checks/all/sub.rs": "",
                 "src/outer/x.rs": "", "src/other/inner.rs": ""}
        self.assertEqual(modules(files), {"src/checks/all.rs": ["src/disk.rs"],
                                          "src/checks/sub.rs": ["src/checks/all.rs"],
                                          "src/outer/x.rs": ["src/lib.rs"], "src/other/inner.rs": ["src/lib.rs"],
                                          "shared/probe.rs": ["src/disk.rs"], "src/one.rs": ["src/disk.rs"],
                                          "src/p/helper.rs": ["src/disk.rs"], "src/via.rs": ["src/disk.rs"]})

    def test_one_file_reached_two_ways(self):
        # Read as a module file and as the file a #[path] names, a.rs brings in a helper each way; and shared.rs, a
        # library's module and a binary's #[path], the same.
        files = {"src/lib.rs": "mod a;\n#[path = \"a.rs\"]\nmod a2;\nmod shared;\n",
                 "src/a.rs": "#[cfg(test)]\nmod helper;\n",
                 "src/a/helper.rs": "", "src/helper.rs": "", "src/shared.rs": "#[cfg(test)]\nmod probe;\n",
                 "src/shared/probe.rs": "", "src/probe.rs": "",
                 "src/bin/tool.rs": "#[path = \"../shared.rs\"]\nmod shared;\n"}
        self.assertEqual(modules(files), dict((p, [d]) for p, d in [
            ("src/a/helper.rs", "src/a.rs"), ("src/helper.rs", "src/a.rs"), ("src/shared/probe.rs", "src/shared.rs"),
            ("src/probe.rs", "src/shared.rs")]))

    def test_in_a_functions_body(self):
        # A block takes a module file's own folder away, and a declaration there needs a #[path].
        files = {"src/lib.rs": "mod a;\n", "src/a.rs": "pub fn f() {\n    mod m {\n        #[cfg(test)]\n"
                                                         "        #[path = \"x.rs\"]\n        mod x;\n    }\n"
                                                         "    #[cfg(test)]\n    mod y;\n}\n",
                 "src/m/x.rs": "", "src/a/m/x.rs": "", "src/a/y.rs": "", "src/y.rs": ""}
        self.assertEqual(modules(files), {"src/m/x.rs": ["src/a.rs"]})

    def test_cfg_attr_paths(self):
        # The file a cfg_attr names is brought in where its cfg holds, and the declaration's own where it doesn't.
        files = {"src/lib.rs": "#[cfg_attr(test, path = \"fake.rs\")]\nmod real;\n#[cfg(test)]\n"
                               "#[cfg_attr(windows, path = \"win.rs\")]\nmod probe;\n"
                               "#[cfg_attr(not(test), path = \"live.rs\")]\nmod mock;\n"
                               "#[cfg_attr(not(test), path = \"same/mod.rs\")]\nmod same;\n"
                               "#[cfg(test)]\n#[tool(kind, path = \"other.rs\")]\nmod kept;\n",
                 "src/real.rs": "", "src/fake.rs": "", "src/probe.rs": "", "src/win.rs": "", "src/live.rs": "",
                 "src/mock.rs": "", "src/same/mod.rs": "", "src/kept.rs": "", "src/other.rs": ""}
        self.assertEqual(modules(files), dict((p, ["src/lib.rs"]) for p in (
            "src/fake.rs", "src/probe.rs", "src/win.rs", "src/mock.rs", "src/kept.rs")))

    def test_raw_names_and_what_isnt_a_declaration(self):
        # mod r#match; is match.rs, and mod name; name.rs, a comment or two before its ; or not. Comments, nested
        # ones too, strings, raw ones holding a quote, a macro's pattern and an inline module declare nothing; a
        # character's brace closes no module.
        files = {"src/lib.rs": "#[cfg(test)]\nmod r#match;\n// #[cfg(test)] mod note;\n/* #[cfg(test)] mod old; */\n"
                               "/* /* */ #[cfg(test)] mod older; */\nconst S: &str = \"#[cfg(test)] mod text;\";\n"
                               "const R: &str = r#\"a\" #[cfg(test)] mod quoted; \"#;\n"
                               "macro_rules! m { ($text:ident) => { #[cfg(test)] mod $text; } }\n"
                               "#[cfg(test)]\nmod inline {\n}\n#[cfg(test)]\nmod name /* x */ ;\n"
                               "#[cfg(test)] mod late // y\n;\n"
                               "mod outer {\n    const C: char = '}';\n    #[cfg(test)]\n    mod inner;\n}\n",
                 "src/match.rs": "", "src/note.rs": "", "src/old.rs": "", "src/older.rs": "", "src/text.rs": "",
                 "src/quoted.rs": "", "src/inline.rs": "", "src/name.rs": "", "src/late.rs": "",
                 "src/net/mod.rs": "#[cfg(test)]\nmod r#type;\n",
                 "src/net/type.rs": "", "src/outer/inner.rs": "", "src/inner.rs": ""}
        self.assertEqual(modules(files), dict([(p, ["src/lib.rs"]) for p in (
            "src/match.rs", "src/name.rs", "src/late.rs", "src/outer/inner.rs")] +
            [("src/net/type.rs", ["src/net/mod.rs"])]))
        # A file whose one declaration has a comment before its ; is read too.
        self.assertEqual(modules({"src/lib.rs": "#[cfg(test)]\nmod a /* x */ ;\n", "src/a.rs": ""}),
                         {"src/a.rs": ["src/lib.rs"]})
        self.assertEqual(modules({"src/lib.rs": "#[cfg(test)]\nmod /* x */ a;\n", "src/a.rs": ""}),
                         {"src/a.rs": ["src/lib.rs"]})

    def test_every_literal_prefix(self):
        # A string is one whatever its prefix, b, c, r, br or cr, so a { in it opens nothing: p.rs is code.
        files = {"src/lib.rs": "static C: &CStr = cr#\"x\"{\"#;\nconst D: &CStr = c\"a{\";\n"
                               "const E: &[u8] = br#\"\"{\"#;\n"
                               "const F: &[u8] = b\"{\";\nconst G: &str = r\"{\";\nconst H: u8 = b'{';\n"
                               "#[path = \"p.rs\"]\nmod p;\n#[cfg(test)]\nmod t;\n", "src/p.rs": "", "src/t.rs": ""}
        self.assertEqual(modules(files), {"src/t.rs": ["src/lib.rs"]})

    def test_a_paths_backslash_and_its_order(self):
        # A \ is the file's own name where one is so named, as rustc reads it on Unix, else a folder's end, as on
        # Windows; and a #[path] before a cfg_attr's is the one that counts.
        declared = ("#[cfg(test)]\n#[path = \"sub\\\\t.rs\"]\nmod t;\n"
                    "#[path = \"b.rs\"]\n#[cfg_attr(test, path = \"a.rs\")]\nmod x;\n")
        self.assertEqual(modules({"src/lib.rs": declared, "src/sub\\t.rs": "", "src/sub/t.rs": "", "src/a.rs": "",
                                  "src/b.rs": ""}), {"src/sub\\t.rs": ["src/lib.rs"]})
        self.assertEqual(modules({"src/lib.rs": declared, "src/sub/t.rs": ""}), {"src/sub/t.rs": ["src/lib.rs"]})
        # A raw string's \ is no escape.
        raw = "#[cfg(test)]\n#[path = r\"sub\\t.rs\"]\nmod t;\n"
        self.assertEqual(modules({"src/lib.rs": raw, "src/sub\\t.rs": ""}), {"src/sub\\t.rs": ["src/lib.rs"]})

    def test_untracked_or_missing(self):
        # A declaration whose file isn't tracked, or isn't there, changes nothing; a file git doesn't track
        # declares nothing.
        files = {"src/lib.rs": "#[cfg(test)]\nmod gone;\n#[cfg(test)]\nmod loose;\n", "src/loose.rs": "",
                 "src/extra.rs": "#[cfg(test)]\nmod kept;\n", "src/kept.rs": ""}
        self.assertEqual(modules(files, ["src/lib.rs", "src/kept.rs"]), {})


class WhenItsATest(unittest.TestCase):
    """Every declaration that brings a file in needs test, by its cfg as cfg_needs_test reads it, or by the code
    it's in: an inline module compiled only for tests, a file that's a test by its declarations, or one marked
    #![cfg(test)] at its top. Never a crate Cargo builds, nor what code include!s."""

    def test_by_the_cfg(self):
        files = {"src/lib.rs": "#[cfg(all(test, unix))]\nmod probe;\n#[cfg(not(test))]\nmod live;\n"
                               "#[cfg(any(test, feature = \"testing\"))]\npub mod testing;\n"
                               "#[cfg(any(test))]\nmod mock;\n#[cfg(not(not(test)))]\nmod twice;\n"
                               "#[cfg(not(any(not(test), unix)))]\nmod rare;\n"
                               "#[cfg(not(all(not(test), unix)))]\nmod wide;\n"
                               "#[cfg(any())]\nmod never;\n"
                               "#[cfg(test)]\n#[allow(dead_code)]\npub(crate) mod regression;\n"
                               "enum Mode {\n    Real,\n    #[cfg(test)]\n    Fake\n}\nmod normal;\n",
                 "src/probe.rs": "", "src/live.rs": "", "src/testing.rs": "", "src/mock.rs": "", "src/twice.rs": "",
                 "src/rare.rs": "", "src/regression.rs": "", "src/normal.rs": "", "src/wide.rs": "", "src/never.rs": ""}
        self.assertEqual(modules(files), dict((p, ["src/lib.rs"]) for p in (
            "src/probe.rs", "src/mock.rs", "src/twice.rs", "src/rare.rs", "src/regression.rs")))

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
        # As far down as they go, each with the file that declares it; and under an inline test module.
        files = {"src/lib.rs": "mod disk;\n",
                 "src/disk.rs": "#[cfg(test)]\nmod tests;\n#[cfg(test)]\nmod checks {\n    mod helper;\n}\n"
                                "mod plain {\n    #![cfg(test)]\n    mod inner;\n}\n",
                 "src/disk/tests.rs": "mod helpers;\n", "src/disk/tests/helpers.rs": "pub mod deep;\n",
                 "src/disk/tests/helpers/deep.rs": "", "src/disk/checks/helper.rs": "", "src/disk/plain/inner.rs": ""}
        self.assertEqual(modules(files), {
            "src/disk/tests.rs": ["src/disk.rs"], "src/disk/tests/helpers.rs": ["src/disk/tests.rs"],
            "src/disk/tests/helpers/deep.rs": ["src/disk/tests/helpers.rs"],
            "src/disk/checks/helper.rs": ["src/disk.rs"],
            "src/disk/plain/inner.rs": ["src/disk.rs"]})

    def test_a_file_compiled_only_for_tests(self):
        # #![cfg(test)] first in it, after its comments, a BOM or a shebang line: a test, and so are its modules.
        files = {"src/lib.rs": "mod mock;\nmod later;\nmod fake;\nmod bom;\nmod script;\n",
                 "src/mock.rs": "//! A mock.\n#![cfg(test)]\nmod parts;\n", "src/mock/parts.rs": "",
                 "src/later.rs": "fn f() {}\n#![cfg(test)]\n", "src/fake.rs": "#![cfg(test)]\nfn f() {}\n",
                 "src/bom.rs": "\ufeff#![cfg(test)]\n", "src/script.rs": "#!/usr/bin/env run\n#![cfg(test)]\n"}
        self.assertEqual(modules(files), {"src/mock.rs": "marked", "src/mock/parts.rs": ["src/mock.rs"],
                                          "src/fake.rs": "marked", "src/bom.rs": "marked", "src/script.rs": "marked"})

    def test_crates_cargo_builds(self):
        # A binary, a build script, an example: Cargo builds each as a crate of its own, so it's code whatever
        # else brings it in for tests, and read as a crate root; by its manifest's paths or where it looks by
        # default. A file in no such place in a package isn't one. A test's crate, in tests or by [[test]], is a
        # test, and so are its modules.
        files = {"Cargo.toml": "[package]\nname = \"k\"\n# path = \"src/fixture.rs\"\n\n[[bin]]\nname = \"k\"\n"
                               "path = \"src/entry.rs\"\n\n[[test]]\nname = \"it\"\npath = \"checks/it.rs\"\n\n"
                               "[[test]]\nname = \"bare\"\npath = \"checks/bare.rs\"\n\n"
                               "[[example]]\nname = \"run\"\npath = 'demo/run.rs'\n\n"
                               "[package.metadata]\nbuild = \"src/fixture.rs\"\n\n"
                               "[dependencies]\nlocal = { path = \"../local\" }\n",
                 "src/lib.rs": "#[cfg(test)]\nmod entry;\n#[cfg(test)]\n#[path = \"../build.rs\"]\nmod build_checks;\n"
                               "#[cfg(test)]\n#[path = \"../examples/demo.rs\"]\nmod demo;\n"
                               "#[cfg(test)]\nmod fixture;\n"
                               "#[cfg(test)]\n#[path = \"../tests/common.rs\"]\nmod common;\n"
                               "#[cfg(test)]\n#[path = \"../sub/src/main.rs\"]\nmod sub;\n"
                               "#[cfg(test)]\n#[path = \"../demo/run.rs\"]\nmod run;\n#[cfg(test)]\n"
                               "#[path = \"bin/tool.rs\"]\nmod tool;\n",
                 "src/entry.rs": "#[cfg(test)]\nmod t;\nmod parts;\n", "src/t.rs": "", "src/entry/t.rs": "",
                 "src/parts.rs": "", "src/entry/parts.rs": "", "build.rs": "mod gen;\n", "gen.rs": "",
                 "examples/demo.rs": "",
                 "src/fixture.rs": "", "tests/common.rs": "", "sub/src/main.rs": "", "checks/it.rs": "mod part;\n",
                 "demo/run.rs": "", "src/bin/tool.rs": "", "checks/bare.rs": "fn main() {}\n", "tests/smoke.rs": "",
                 "checks/part.rs": ""}
        self.assertEqual(modules(files), dict([(p, ["src/lib.rs"]) for p in ("src/fixture.rs", "sub/src/main.rs")] + [
            ("tests/common.rs", "crate"), ("checks/it.rs", "crate"), ("checks/part.rs", ["checks/it.rs"]),
            ("checks/bare.rs", "crate"), ("tests/smoke.rs", "crate"),
            ("src/t.rs", ["src/entry.rs"]), ("src/entry/t.rs", ["src/entry.rs"]),
            ("src/entry/parts.rs", ["src/entry.rs"])]))
        scoping = support.load("scoping")
        found = scoping.rust_test_modules(sorted(files), lambda paths: dict((p, files[p]) for p in paths))
        self.assertEqual(scoping.rust_test_reason("tests/smoke.rs", found),
                         "a Rust crate Cargo builds only as a test, by Cargo.toml")
        # With no manifest it can't be known, and a file in one of those places is taken for a crate's.
        files = {"src/lib.rs": "#[cfg(test)]\n#[path = \"main.rs\"]\nmod main_for_tests;\n", "src/main.rs": ""}
        self.assertEqual(modules(files), {})

    def test_what_code_includes(self):
        # A file include!d outside test code is compiled with it, the include! read from its own file's folder,
        # whatever module it's in; one include!d only for tests stays a test.
        files = {"src/lib.rs": "mod disk;\nmod net;\n#[cfg(test)]\nmod shared;\n#[cfg(test)]\nmod extra;\n"
                               "#[cfg(test)]\nmod probe;\n#[cfg(test)]\nfn t() {\n    include!(\"probe.rs\");\n}\n"
                               "const NAME: &str = \"probe.rs\";\n",
                 "src/disk.rs": "pub fn f() {\n    include!(\"extra.rs\");\n}\n",
                 "src/net.rs": "#[cfg(test)]\nmod shared;\npub mod p {\n    include!(\"shared.rs\");\n}\n",
                 "src/shared.rs": "", "src/net/shared.rs": "", "src/extra.rs": "", "src/probe.rs": ""}
        self.assertEqual(modules(files), {"src/probe.rs": ["src/lib.rs"], "src/net/shared.rs": ["src/net.rs"]})
        # In brackets or braces too; and where its path is built, the file a string of it names in the package.
        files = {"Cargo.toml": "[package]\nname = \"k\"\n", "src/lib.rs": "#[cfg(test)]\nmod b;\n#[cfg(test)]\nmod c;\n"
                 "#[cfg(test)]\n#[path = \"gen.rs\"]\nmod gen;\ninclude![\"b.rs\"];\ninclude! {\"c.rs\"}\n"
                 "pub fn f() {\n"
                 "    include!(concat!(env!(\"CARGO_MANIFEST_DIR\"), \"/src/gen.rs\"));\n}\n",
                 "src/b.rs": "", "src/c.rs": "", "src/gen.rs": "", "other/Cargo.toml": "[package]\nname = \"o\"\n",
                 "other/src/lib.rs": "#[cfg(test)]\nmod gen;\n", "other/src/gen.rs": ""}
        self.assertEqual(modules(files), {"other/src/gen.rs": ["other/src/lib.rs"]})

    def test_what_a_macro_declares(self):
        # A macro_rules! that declares the modules it's given declares them where it's called, with brackets or
        # braces: util.rs and disk/store.rs are the library's, though the binary brings util.rs in only for tests.
        files = {"src/lib.rs": "macro_rules! modules { ($($m:ident),*) => { $(pub mod $m;)* } }\nmodules!(util, net);\n"
                               "mod disk;\n#[cfg(test)]\n#[path = \"disk/store.rs\"]\nmod store;\n",
                 "src/disk.rs": "modules! { store }\n",
                 "src/main.rs": "#[cfg(test)]\nmod util;\n#[cfg(test)]\nmod probe;\n",
                 "src/util.rs": "", "src/net.rs": "", "src/disk/store.rs": "", "src/probe.rs": ""}
        self.assertEqual(modules(files), {"src/probe.rs": ["src/main.rs"]})
        # Called in test code, it declares for tests; and a macro whose mod $name has a body declares no file.
        files = {"src/lib.rs": "macro_rules! modules { ($($m:ident),*) => { $(pub mod $m;)* } }\n#[cfg(test)]\n"
                               "modules!(probe);\n#[cfg(test)]\n#[path = \"probe.rs\"]\nmod again;\nmod disk;\n"
                               "macro_rules! wrap { ($m:ident) => { mod $m {} } }\n#[cfg(test)]\n"
                               "#[path = \"disk/inner.rs\"]\nmod inner;\n", "src/disk.rs": "wrap!(inner);\n",
                 "src/probe.rs": "", "src/disk/inner.rs": ""}
        self.assertEqual(modules(files), {"src/probe.rs": ["src/lib.rs"], "src/disk/inner.rs": ["src/lib.rs"]})
        # Defined in a file that declares nothing else.
        files = {"src/lib.rs": "#[macro_use]\nmod macros;\nmodules!(util);\n",
                 "src/main.rs": "#[cfg(test)]\nmod util;\n", "src/util.rs": "",
                 "src/macros.rs": "macro_rules! modules { ($($m:ident),*) => { $(pub mod $m;)* } }\n"}
        self.assertEqual(modules(files), {})

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
# folder named tests, though in no doubt), by its own #![cfg(test)] (mock.rs), and code named like a test.
CRATE = {"src/lib.rs": "pub mod disk;\npub mod commands;\n#[cfg(test)]\nmod fixture;\n#[cfg(test)]\nmod tests;\n"
                       "mod mock;\n",
         "src/tests/mod.rs": "fn s() {\n}\n", "src/mock.rs": "#![cfg(test)]\nmod parts;\nfn m() {\n}\n",
         "src/mock/parts.rs": "fn p() {\n}\n",
         "src/disk.rs": "pub fn read() {\n}\n#[cfg(test)]\nmod checks;\n",
         "src/disk/checks.rs": "mod helper;\n" + "fn t() {\n    f();\n}\n" * 40,
         "src/disk/checks/helper.rs": "fn h() {\n}\n", "src/fixture.rs": "fn mock() {\n    f();\n}\n" * 10,
         "src/cache_test.rs": "fn c() {\n}\n", "src/commands/mod.rs": "pub mod test;\n",
         "src/commands/test.rs": "pub fn run() {\n    go();\n}\n"}
NAMED = ("; 4 of them Rust test modules in files of their own, known by their declarations, not their names: "
         "src/disk/checks.rs, src/disk/checks/helper.rs, src/fixture.rs and src/mock/parts.rs; 1 of them Rust "
         "compiled only for tests by the #![cfg(test)] at its top: src/mock.rs. %s.")


def rows(out):
    """The table's files, in measure.py's output or the heatmap's."""
    return set(re.findall(r"(?m)^ +\d.*\s(src/\S+)(?: \(.*\))?$", out))


class BothScripts(unittest.TestCase):
    """measure.py and heatmap.py set the same files aside, and name them, each with why."""

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
        self.assertIn("Test files: 7 set aside from the percentiles and the table" +
                      NAMED % "--list-tests lists every one, with why", result.out)
        self.assertNotIn("measured unless named as a test", result.out)
        self.assertNotIn("maybe not", result.out)

    def test_heatmap(self):
        result = support.run("heatmap.py", "-C", self.repo, "--top", "20")
        self.assertEqual(result.code, 0, result)
        self.assertEqual(rows(result.out), {"src/lib.rs", "src/disk.rs", "src/commands/mod.rs", "src/commands/test.rs"})
        self.assertIn("Test files: 7 changed in the window, set aside from the table and the pairs" +
                      NAMED % "measure.py --list-tests lists every one in the scope, with why", result.out)
        self.assertNotIn("maybe not", result.out)

    def test_a_scope_that_leaves_the_declaration_out(self):
        for script in ("measure.py", "heatmap.py"):
            with self.subTest(script=script):
                result = support.run(script, "-C", self.repo, "src/disk")
                self.assertEqual(result.code, 0, result)
                self.assertIn("Test files: 2 ", result.out)
                self.assertEqual(rows(result.out), set())
                result = support.run(script, "-C", self.repo, "src/fixture.rs")
                self.assertIn("; 1 of them a Rust test module in a file of its own, known by its declaration, not "
                              "its name: src/fixture.rs. ", result.out)

    def test_the_users_word_wins(self):
        # A file the user says isn't a test is measured; its own modules are still tests by their declarations.
        for script in ("measure.py", "heatmap.py"):
            with self.subTest(script=script):
                result = support.run(script, "-C", self.repo, "--not-test", "src/disk/checks.rs", "--top", "20")
                self.assertIn("src/disk/checks.rs", rows(result.out))
                self.assertIn("Test files: 6 ", result.out)
        for script in ("measure.py", "heatmap.py"):
            with self.subTest(script=script):
                result = support.run(script, "-C", self.repo, "--keep-tests", "--top", "20")
                self.assertNotIn("Test files:", result.out)
                self.assertIn("src/fixture.rs", rows(result.out))

    def test_show_says_why_of_that_file(self):
        result = support.run("measure.py", "-C", self.repo, "--show", "src/fixture.rs", "--show", "src/mock.rs",
                             "--show", "src/mock/parts.rs", "--show", "src/disk/checks/helper.rs")
        self.assertEqual(result.code, 0, result)
        self.assertIn("src/fixture.rs: Rust, 30 code lines, band -, 10 functions", result.out)
        for path, why in [("src/fixture.rs", "one of Rust's test modules, declared only for tests, in src/lib.rs"),
                          ("src/mock.rs", "Rust compiled only for tests, by the #![cfg(test)] at its top"),
                          ("src/mock/parts.rs", "one of Rust's test modules, declared in src/mock.rs, in code "
                                                "compiled only for tests"),
                          ("src/disk/checks/helper.rs", "one of Rust's test modules, declared in src/disk/checks.rs, "
                                                        "in code compiled only for tests")]:
            self.assertRegex(result.out, r"(?m)^%s: Rust,.*\nA test file: %s; measured whole here\.$" % (
                re.escape(path), re.escape(why)))

    def test_a_few_named_and_where_every_one_is(self):
        # Five of each kind at most, as the doubts are, and where to see every one, with why.
        scoping = support.load("scoping")
        found = dict([("src/m%d.rs" % k, ("declared", frozenset(["src/lib.rs"]), frozenset())) for k in range(6)] + [
            ("src/mock.rs", ("marked", frozenset(), None)), ("it.rs", ("crate", frozenset(), "Cargo.toml")),
            ("a.rs", ("crate", frozenset(), "Cargo.toml"))])
        self.assertEqual(scoping.rust_tests_said(sorted(found), found, "THERE"), "; 6 of them Rust test modules in "
                         "files of their own, known by their declarations, not their names: src/m0.rs, src/m1.rs, "
                         "src/m2.rs, src/m3.rs, src/m4.rs and 1 more; 1 of them Rust compiled only for tests by the "
                         "#![cfg(test)] at its top: src/mock.rs; 2 of them Rust crates Cargo builds only as tests: "
                         "a.rs and it.rs. THERE")
        self.assertEqual(scoping.rust_test_reason("it.rs", found),
                         "a Rust crate Cargo builds only as a test, by Cargo.toml")

    def test_list_tests(self):
        result = support.run("measure.py", "-C", self.repo, "--list-tests")
        self.assertEqual(result.code, 0, result)
        self.assertIn("Test files set aside: 7, each with why:\n"
                      "  src/cache_test.rs: named like a test (*_test.*)\n"
                      "  src/disk/checks.rs: one of Rust's test modules, declared only for tests, in src/disk.rs\n"
                      "  src/disk/checks/helper.rs: one of Rust's test modules, declared in src/disk/checks.rs, in "
                      "code compiled only for tests\n", result.out)
        self.assertIn("  src/tests/mod.rs: in a folder named tests\n", result.out)
        self.assertNotIn("lines  band", result.out)


class TwoReadings(unittest.TestCase):
    """measure.py reads the working tree and the heatmap HEAD, so each says when they differ in what decides Rust's
    test modules; and measure.py's reader of Rust's literals and comments agrees with the one that finds modules."""

    def test_the_working_tree_against_head(self):
        repo = support.Repo("two-readings")
        repo.commit("2026-01-05", "Start", {"src/lib.rs": "#[cfg(test)]\nmod probe;\n",
                                             "src/probe.rs": "fn p() {\n}\n"})
        repo.done()
        for script in ("measure.py", "heatmap.py"):
            with self.subTest(script=script):
                self.assertNotIn("may set aside different files", support.run(script, "-C", repo.path).out)
        repo.write("src/lib.rs", "mod probe;\n")
        self.assertIn("Rust's test modules are read here from the working tree, which differs from HEAD in 1 .rs or "
                      "Cargo.toml file; the heatmap reads HEAD, so the two may set aside different files.",
                      support.run("measure.py", "-C", repo.path).out)
        self.assertIn("Rust's test modules are read here at HEAD, and the working tree, which measure.py reads, "
                      "differs from it in 1 .rs or Cargo.toml file, so the two may set aside different files.",
                      support.run("heatmap.py", "-C", repo.path).out)

    def test_the_two_readers_agree(self):
        # The brackets each sees outside literals and comments, on every literal Rust has.
        measure, scoping = support.load("measure"), support.load("scoping")
        for text in ['static C: &CStr = cr#"x"{"#; fn g() {}', 'let c = c"a\\"{"; {}', 'let s = b"x\\"{";',
                     'x = br##"a"#{"##;', 'let r = r"{"; {}', "let x = '{'; let y = b'}'; fn h<'a>(x: &'a u8) {}",
                     "let q = '\\''; {}", "'\\u{7d}';", '/* { /* } */ */ {}', '// {\n{}', 'm!(r#match); fn r#fn() {}',
                     '#[cfg(test)] mod a;', '"\\\\"; {}']:
            with self.subTest(text=text):
                lines, _ = measure.skeleton(text.split("\n"), "// /*", "char", False, "Rust")
                seen = "".join(c for line in lines for c in line if c in "{}[];")
                found = "".join(t if k == "bracket" else "[" for k, t in scoping.rust_tokens(text)
                                if k in ("bracket", "attribute"))
                self.assertEqual(found, seen)


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


class Corners(unittest.TestCase):
    """Text rustc reads its own way, or refuses, read as it reads it or with nothing lost."""

    def test_what_reads_as_a_test(self):
        for name, text in [("include_str", "#![doc = include_str![\"note.md\"]]\n#![cfg(test)]\n"),
                           ("spaced", "#![ cfg(test) ]\n"), ("after allow", "#![allow(dead_code)]\n#![cfg(test)]\n"),
                           ("crlf", "//! A mock.\r\n#![cfg(test)]\r\n")]:
            with self.subTest(case=name):
                self.assertEqual(tests_in({"src/lib.rs": "mod mock;\n", "src/mock.rs": text}), ["src/mock.rs"])
        for name, text in [("raw path", "#[cfg(test)]\n#[path = r\"probe.rs\"]\nmod fixture;\n"),
                           ("space before ;", "#[cfg(test)]\nmod probe ;\n"), ("# [", "# [cfg(test)]\nmod probe;\n"),
                           ("any of alls", "#[cfg(any(all(test, unix), all(test, windows)))]\nmod probe;\n"),
                           ("a stray }", "}\n#[cfg(test)]\nmod probe;\n"),
                           ("a byte's brace", "mod outer {\n    const B: u8 = b'}';\n}\n#[cfg(test)]\nmod probe;\n")]:
            with self.subTest(case=name):
                self.assertIn("src/probe.rs", tests_in({"src/lib.rs": text, "src/probe.rs": ""}))
        found = tests_in({"src/lib.rs": "#[cfg(test)]\n#[cfg_attr(windows, path = \"win.rs\")]\nmod probe;\n",
                          "src/probe.rs": ""})
        self.assertEqual(found, ["src/probe.rs"])

    def test_what_doesnt(self):
        for name, text in [("not Rust", "#[cfg(test)]\n#[path = \"gen.py\"]\nmod gen;\n"),
                           ("raw bytes", "const B: &[u8] = br#\"x\" #[cfg(test)] mod probe; \"#;\nmod probe;\n"),
                           ("a comment never closed", "/* open\n#[cfg(test)]\nmod probe;\n"),
                           ("an attribute before", "#[allow(x)]\n#![cfg(test)]\nmod probe;\n"),
                           ("a module never closed", "mod probe;\n#[cfg(test)]\nmod t {\n"),
                           ("test as a key", "#[cfg(test = \"x\")]\nmod probe;\n")]:
            with self.subTest(case=name):
                self.assertEqual(tests_in({"src/lib.rs": text, "src/probe.rs": "", "src/gen.py": ""}), [])
        # A crate root's module is beside it, never in a folder of its name.
        self.assertEqual(tests_in({"src/lib.rs": "#[cfg(test)]\nmod probe;\n", "src/lib/probe.rs": ""}), [])
        # A file a test module and code both bring in through #[path], plainly or not, is code.
        for declared in ("#[cfg(test)]\n#[path = \"shared.rs\"]\nmod shared;\n",
                         "#[path = \"shared.rs\"]\nmod shared;\n"):
            with self.subTest(declared=declared):
                files = {"src/lib.rs": "#[cfg(test)]\nmod t1;\nmod util;\n", "src/t1.rs": declared,
                         "src/util.rs": "#[path = \"shared.rs\"]\nmod shared;\n", "src/shared.rs": ""}
                self.assertEqual(tests_in(files), ["src/t1.rs"])


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
