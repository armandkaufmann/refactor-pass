"""scoping.py's reading of a Rust file, one shape of text at a time: rust_heads, which says whether a file holds an
inner cfg or an include!, and so whether it's read for its modules at all; and what a read file's comments, strings
and attributes make of the declarations after them.
"""

import random
import re
import unittest

try:
    from . import support
except ImportError:
    import support


def modules(files):
    """The test modules of a repo of the files given, as {path: text}: per file, the files that declare it, or how
    it's known otherwise ("marked")."""
    scoping = support.load("scoping")
    found = scoping.rust_test_modules(sorted(files), lambda paths: dict((p, files[p]) for p in paths if p in files))
    return dict((path, sorted(found[path][1]) if found[path][0] == "declared" else found[path][0]) for path in found)


# What rust_heads stands for: round 2's two searches, an inner cfg's head and include!'s, past spaces and comments
# between their parts (a block comment unnested, to its first */; a line comment with its line's end).
GAP = r"""(?:\s|/\*(?:[^*]|\*(?!/))*\*/|//[^\n]*\n)*"""
SEARCHES = (re.compile(r"#%s!%s\[%scfg" % (GAP, GAP, GAP), re.S), re.compile(r"include%s!" % GAP, re.S))
# Texts, and whether each holds one. Spaces of each kind and comments of each kind between the parts, one or more,
# an odd number and an even one; a block comment whose */ starts at the opening's *, or holds a * or a !; a comment
# of each kind in one head; a place in a comment that two searches reach; and what is no head: an outer attribute, a
# word after the !, a cfg that isn't the bracket's, a comment never closed, a ! or a [ missing.
HEADS = [
    ("#![cfg(test)]", True), ("# ![cfg(test)]", True), ("#\t![cfg(test)]", True), ("#\x0c![cfg(test)]", True),
    ("#\n![cfg(test)]", True), ("#\r\n![cfg(test)]", True), ("#! [cfg(test)]", True), ("#![ cfg(test)]", True),
    ("#![cfg (test)]", True), ("#![allow(dead_code)]\n#![cfg(test)]", True), ("#/**/![cfg(test)]", True),
    ("#/**//**/![cfg(test)]", True), ("#/**//**//**/![cfg(test)]", True), ("#//\n![cfg(test)]", True),
    ("#//\n//\n![cfg(test)]", True), ("#//\n//\n//\n![cfg(test)]", True), ("#/*/!*/![cfg(test)]", True),
    ("#/* * */![cfg(test)]", True), ("#/***/![cfg(test)]", True), ("#/* a */ // b\n![cfg(test)]", True),
    ("#// b\n/* a */![cfg(test)]", True), ("#!/* a */[cfg(test)]", True), ("#![// a\ncfg(test)]", True),
    ("// #![cfg(test)]", True), ('include!("t.rs")', True), ('include !("t.rs")', True),
    ('include/**/!("t.rs")', True), ('include//\n!("t.rs")', True), ('include//#/*#//\n/**/ !("t.rs");\n', True),
    ("#[cfg(test)]", False), ("#![allow(x)]", False), ("#!x[cfg(test)]", False), ("#!xcfg(test)", False),
    ("#/**/x[cfg(test)]", False), ("#/* never closed ![cfg(test)]", False), ("#// no line end ![cfg(test)]", False),
    ("#/*/![cfg(test)]", False), ("#! /x[cfg(test)]", False), ("include /x", False), ('include("t.rs")', False),
    ("include/**/x!", False), ("#!" * 8, False), ("#//\n" * 8, False), ("", False), ("#", False), ("include", False),
]
PIECES = ["#", "!", "[", "cfg", "include", " ", "\t", "\n", "\r\n", "/**/", "/* a */", "/*", "*/", "*", "/", "//x\n",
          "//", "x", "/***/", "/*/", "**/", "!*/"]


class RustHeads(unittest.TestCase):

    def test_each_text(self):
        rust_heads = support.load("scoping").rust_heads
        for text, holds in HEADS:
            with self.subTest(text=text):
                self.assertEqual(rust_heads(text), holds)
                self.assertEqual(any(search.search(text) for search in SEARCHES), holds)

    def test_random_texts(self):
        # As the searches it stands for answer, on texts of the pieces they read.
        rust_heads, rng = support.load("scoping").rust_heads, random.Random(20261128)
        for _ in range(4000):
            text = "".join(rng.choice(PIECES) for _ in range(rng.randint(1, 24)))
            with self.subTest(text=text):
                self.assertEqual(rust_heads(text), any(search.search(text) for search in SEARCHES))


class WhatTheTokensMake(unittest.TestCase):
    """An attribute's head past comments of each kind, as a comment that holds a *, a run of them or a !; a first line
    that is a shebang, not an attribute; an attribute over CRLF lines; and a string that a \\ and a line's end go on."""

    def test_declarations(self):
        t = {"src/t.rs": "pub fn f() {}\n"}
        for lib, found in (
                ("#/***/[cfg(test)]\nmod t;\n", {"src/t.rs": ["src/lib.rs"]}),
                ("#/* * **/[cfg(test)]\nmod t;\n", {"src/t.rs": ["src/lib.rs"]}),
                ("#/* * */[cfg(test)]\nmod t;\n", {"src/t.rs": ["src/lib.rs"]}),
                ("#/* ! **/[cfg(test)]\nmod t;\n", {"src/t.rs": ["src/lib.rs"]}),
                ("#/* ! * x */[cfg(test)]\nmod t;\n", {"src/t.rs": ["src/lib.rs"]}),
                ("#// !\n[cfg(test)]\nmod t;\n", {"src/t.rs": ["src/lib.rs"]}),
                ("#\r\n[cfg(test)]\r\nmod t;\r\n", {"src/t.rs": ["src/lib.rs"]}),
                ("#!/* a **/ x /* b */[cfg(test)]\npub mod t;\n", {}), ("#!//[cfg(test)] x\npub mod t;\n", {}),
                ('pub const S: &str = "\\\n;#[cfg(test)] mod t;";\n', {}),
                ('pub const S: &str = "\\t;#[cfg(test)] mod t;";\n', {})):
            with self.subTest(lib=lib):
                self.assertEqual(modules(dict(t, **{"src/lib.rs": lib})), found)

    def test_marked_files(self):
        # Each found by rust_heads, then read: an inner cfg past spaces of each kind or comments.
        for head in ("# ![cfg(test)]", "#\t![cfg(test)]", "#\x0c![cfg(test)]", "#\n![cfg(test)]", "#/**/![cfg(test)]",
                     "#//\n![cfg(test)]", "#/*/!*/![cfg(test)]", "#/* * */![cfg(test)]", "#![cfg (test)]",
                     "#/* a */ // b\n![cfg(test)]", "#![allow(dead_code)]\n#![cfg(test)]"):
            with self.subTest(head=head):
                files = {"src/lib.rs": "pub mod m;\n", "src/m.rs": head + "\npub fn f() {}\n"}
                self.assertEqual(modules(files), {"src/m.rs": "marked"})

    def test_an_include_past_a_place_two_searches_reach(self):
        # a.rs's include!, past a line comment that holds a #/* and a block comment, keeps table.rs code.
        files = {"src/lib.rs": "mod a;\n#[cfg(test)]\n#[path = \"table.rs\"]\nmod table_tests;\n",
                 "src/a.rs": "include//#/*#//\n/**/ !(\"table.rs\");\n", "src/table.rs": "pub fn t() {}\n"}
        self.assertEqual(modules(files), {})


if __name__ == "__main__":
    unittest.main()
