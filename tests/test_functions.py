"""measure.py's function finder, on small samples with known answers.

Each file in samples/functions/ has its functions written in expected.json beside it, as [name, first line,
last line, code lines], read from the sample by hand. Python's are checked against the ast module as well,
and so are this skill's own scripts: a function's span from the parser, and its code lines as that span
less blank lines, lines that are only a comment, and docstrings (statements that are only a string).
"""

import ast
import io
import json
import os
import sys
import tokenize
import unittest

try:
    from . import support
except ImportError:
    import support

FUNCTIONS = os.path.join(support.SAMPLES, "functions")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def found(name, text):
    """measure.functions' answer for a file: its functions as [name, first, last, code lines]."""
    measure = support.load("measure")
    _, functions, _ = measure.functions(name, text)
    return [[f[0], f[1], f[2], f[3]] for f in functions or []]


class Samples(unittest.TestCase):
    """Every sample's functions, exactly: none missed, none extra, each one's span and code lines right."""

    @classmethod
    def setUpClass(cls):
        cls.expected = json.loads(read(os.path.join(FUNCTIONS, "expected.json")))

    def test_every_sample_has_an_answer(self):
        samples = sorted(n for n in os.listdir(FUNCTIONS) if n != "expected.json")
        self.assertEqual(samples, sorted(k for k in self.expected if not k.startswith("_")))

    def test_every_language_has_a_sample(self):
        measure = support.load("measure")
        covered = set(os.path.splitext(n)[1].lower() for n in self.expected)
        for language in measure.LANGUAGES:
            with self.subTest(language=language[0]):
                self.assertTrue(covered & set(language[1].split()), "no sample for %s" % language[0])

    def test_samples(self):
        for name, want in sorted(self.expected.items()):
            if name.startswith("_"):
                continue
            with self.subTest(sample=name):
                self.assertEqual(found(name, read(os.path.join(FUNCTIONS, name))), want)

    def test_a_byte_order_mark(self):
        # As Visual Studio starts a file by default: it changes nothing, not even the first line.
        measure = support.load("measure")
        for name in sorted(self.expected):
            if not name.startswith("_"):
                with self.subTest(sample=name):
                    text = read(os.path.join(FUNCTIONS, name))
                    self.assertEqual(measure.functions(name, "\ufeff" + text), measure.functions(name, text))

    def test_a_byte_order_mark_in_a_repo(self):
        repo = support.Repo("bom")
        repo.commit("2026-01-01", "Start", {"Main.cs": b"\xef\xbb\xbfint Main() {\n    return 0;\n}\n"})
        repo.done()
        result = support.run("measure.py", "-C", repo.path, "--show", "Main.cs")
        self.assertIn("Main.cs: C#, 3 code lines, band -, 1 functions", result.out)
        self.assertRegex(result.out, r"(?m)^\s*1-3\s+3\s+0\s+-\s+Main$")

    def test_cpp_by_its_other_extensions(self):
        # Templates' and inline definitions, and modules; an .inl is C++ as a .h is, by what its code holds.
        measure = support.load("measure")
        text = "template <typename T>\nT twice(T v) {\n    return v + v;\n}\n"
        for extension in (".inl", ".hxx", ".ipp", ".tpp", ".tcc", ".txx", ".h++", ".c++", ".ixx", ".cppm"):
            with self.subTest(extension=extension):
                _, functions, language = measure.functions("a" + extension, text)
                self.assertEqual((language, [f[:3] for f in functions or []]), ("C++", [("twice", 2, 4)]))
        self.assertEqual(measure.functions("a.inl", "static int one(void) {\n    return 1;\n}\n")[2], "C")

    def test_an_inl_or_h_by_what_its_code_holds(self):
        # C++ by a name qualified by its class, an operator's definition or noexcept, as in definitions written
        # out of their class in a namespace that the header including them opens; C++ in a macro, or a C23
        # attribute's vendor (gnu::), isn't the code's own.
        measure = support.load("measure")
        members = ("inline Path Path::operator/(const Path& p) const noexcept\n{\n    return Join(*this, p);\n}\n"
                   "inline bool Path::empty() const noexcept\n{\n    return size == 0;\n}\n")
        for name, text, want in (
                ("a.inl", members, ("C++", 2)), ("a.h", members, ("C++", 2)), ("A.INL", members, ("C++", 2)),
                ("b.inl", "inline float lerp(float a, float t) noexcept\n{\n    return a * t;\n}\n", ("C++", 1)),
                ("c.inl", "inline int Grid::size() const\n{\n    return n;\n}\n", ("C++", 1)),
                ("d.inl", "inline Grid operator+(Grid a, Grid b)\n{\n    return a;\n}\n", ("C++", 1)),
                ("m.h", "#define CALL(x) \\\n    (void)(x), \\\n    ns::call(x)\nint one(void) {\n    return 1;\n}\n",
                 ("C", 1)),
                ("n.h", "[[gnu::always_inline]] static inline int one(void) {\n    return 1;\n}\n", ("C", 1)),
                ("o.h", "[[gnu::cold,\n  gnu::noinline]]\nstatic inline int one(void) {\n    return 1;\n}\n",
                 ("C", 1)),
                # An Objective-C message's [[ isn't an attribute that a ]] far on closes, past a ; or a brace.
                ("p.h", "void g(void) { [[x y] z]; }\ninline int Grid::size() const { return n; }\nint v = a[b[0]];\n",
                 ("C++", 2)),
                ("q.h", "void f(void) {\n    if ([[p q] r]) { Shape::area(m[n[0]]); }\n}\n", ("C++", 1)),
                # What starts a line, as main reads it, after spaces.
                ("r.h", "  template <typename T>\nT twice(T v) {\n    return v;\n}\n", ("C++", 1))):
            with self.subTest(name=name):
                _, functions, language = measure.functions(name, text)
                self.assertEqual((language, len(functions)), want)

    def test_cpp_offered_to_cpp_callers(self):
        # A C header's code for C++ callers, under __cplusplus to its #else or #endif, is no evidence of the new
        # kinds; after the guard it is, and what main took for C++ (a namespace) still is.
        measure = support.load("measure")
        for text, want in (
                ("vec2 vec2_add(vec2 a, vec2 b);\n#if defined(__cplusplus) && !defined(PLAIN)\n"
                 "inline vec2 operator+(vec2 a, vec2 b) {\n    return vec2_add(a, b);\n}\n#endif\n", "C"),
                ("#ifndef __cplusplus\nint pick(int a);\n#else\nint pick(int a) noexcept;\n#endif\n", "C"),
                ("#ifdef __cplusplus\n#if 1\nint f() noexcept;\n#endif\nint g() noexcept;\n#endif\n", "C"),
                ("#ifdef __cplusplus\n#endif\ninline int Grid::size() const {\n    return n;\n}\n", "C++"),
                ("#ifdef __cplusplus\nnamespace ns {\n}\n#endif\n", "C++"),
                # Not C++ only: !defined, an #elif after #ifndef, ||, the #else of #ifdef.
                ("#if !defined(__cplusplus)\nint pick(int a);\n#else\nint pick(int a) noexcept;\n#endif\n", "C"),
                ("#ifndef __cplusplus\nint pick(int a);\n#elif defined(FAST)\nint pick(int a) noexcept;\n#endif\n",
                 "C"),
                ("#if defined(__cplusplus) || defined(OTHER)\nint f() noexcept;\n#endif\n", "C++"),
                ("#ifdef __cplusplus\n#else\nint f() noexcept;\n#endif\n", "C++"),
                # C++'s only by an #elif after a plain #if; the #else of a plain #if is anyone's; a stray #endif.
                ("#if defined(PLAIN_C)\nint area(int s);\n#elif defined(__cplusplus)\nint area(int s) noexcept;\n"
                 "#endif\n", "C"),
                ("#ifdef SMALL\nint w;\n#else\ninline int Shape::area() const { return n; }\n#endif\n", "C++"),
                ("int x;\n#endif\n", "C"),
                # Not C++, in brackets, which the skeleton writes as s, or with no defined: its #else is C++'s only.
                ("#if !(defined(__cplusplus))\nint pick(int a);\n#else\nint pick(int a) noexcept;\n#endif\n", "C"),
                ("#if !__cplusplus\nint pick(int a);\n#else\nint pick(int a) noexcept;\n#endif\n", "C"),
                ("#if ! __cplusplus\nint pick(int a);\n#else\nint pick(int a) noexcept;\n#endif\n", "C"),
                ("#if !(defined __cplusplus)\nint pick(int a);\n#else\nint pick(int a) noexcept;\n#endif\n", "C"),
                # The #else after an #elif that's C's only.
                ("#if defined(PLAIN)\nint pick(int a);\n#elif !defined(__cplusplus)\nint pick(int a);\n#else\n"
                 "int pick(int a) noexcept;\n#endif\n", "C")):
            with self.subTest(text=text):
                self.assertEqual(measure.functions("v.h", text)[2], want)

    def test_an_operator_is_the_whole_word(self):
        # operator, then (), a symbol, or a space and a type's name then (), as a conversion takes no parameters;
        # or new, delete, co_await or an operator spelt as a word (and, not_eq...), which take them. Not a C
        # function whose name starts with it, nor one whose type is named operator.
        measure = support.load("measure")
        # None qualified, as a qualified one counts by its :: alone (Mesh::operator bool() const).
        words = ("and", "and_eq", "bitand", "bitor", "compl", "not", "not_eq", "or", "or_eq", "xor", "xor_eq")
        for text in ("operator bool()", "operator bool() const", "operator Color4()", "operator==(", "operator!=(",
                     "operator,(", "operator ()(", "operator() (", "operator[ ](", "operator new(size_t)",
                     "operator new[](size_t)", "operator delete[](void*)", 'operator""_km(', 'operator"" _px(',
                     "operator const char*()", "operator string_view()", "operator T&()", "operator co_await()",
                     "operator Task<int(long)>() const", "operator co_await(Task t)", "operator bool( ) const",
                     "operator delete [] (void* p)") + tuple("operator %s(Flag a, Flag b)" % word for word in words):
            with self.subTest(text=text):
                self.assertTrue(measure.CPP_IN_CODE.search(text))
                self.assertNotIn("::", text)
        for text in ("operator_rank(", "operator_kind (", "operators()", "my_operator(", "operator lookup(int key)",
                     "operator pick(void)"):
            with self.subTest(text=text):
                self.assertFalse(measure.CPP_IN_CODE.search(text))
        text = "int operator_rank(int op);\nstatic inline int operator_kind(int op)\n{\n    return op;\n}\n"
        self.assertEqual(measure.functions("rank.h", text)[2], "C")
        # A member named operator, a pointer to a function, or used after -> or . with an operator and a bracket;
        # an enum's tag so named; and a type.
        for text in ("struct rule {\n    int (*operator)(long, long);\n};\nint run(const struct rule *r);\n",
                     "struct step { int operator; };\nvoid assign(struct step *s, long x) { s->operator = (int)x; }\n",
                     "struct step { int operator; };\nint plus(struct step s) { return s.operator == ('+'); }\n",
                     "struct step { int operator; };\nint get(struct step *s) { return s -> operator + (1); }\n",
                     "enum operator { OP_A };\nenum operator read_operator(const char *s);\n",
                     "struct operator { int a; };\nstruct operator fresh();\n",
                     "union operator { int a; };\nunion operator blank();\n",
                     "typedef int operator;\noperator lookup(const char *key, int n);\n",
                     "typedef int operator;\noperator *latest();\n"):
            with self.subTest(text=text):
                self.assertEqual(measure.functions("rule.h", text)[2], "C")

    def test_language_of_each_sample(self):
        measure = support.load("measure")
        names = {".vue": "Vue", ".svelte": "Vue", ".tsx": "TypeScript", ".mjs": "JavaScript", ".jsx": "JavaScript"}
        for name in ("Counter.vue", "Greeting.svelte", "components.tsx", "default-async-generator.mjs",
                     "default-named.jsx"):
            with self.subTest(sample=name):
                _, _, language = measure.functions(name, read(os.path.join(FUNCTIONS, name)))
                self.assertEqual(language, names[os.path.splitext(name)[1]])


# The truth from Python's own parser.

def _is_text(node):
    """Whether an expression is only a string: what a docstring is."""
    if isinstance(node, ast.JoinedStr):
        return True
    if sys.version_info >= (3, 8):
        return isinstance(node, ast.Constant) and isinstance(node.value, (str, bytes))
    return isinstance(node, (ast.Str, ast.Bytes))


def python_truth(text):
    """The file's code lines and its functions as [name, first, last, code lines], from ast and tokenize:
    a line is code unless it's blank, only a comment, or part of a statement that is only a string."""
    tree = ast.parse(text)
    source = text.split("\n")
    code = set()
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type in (tokenize.COMMENT, tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT,
                          tokenize.ENDMARKER):
            continue
        code.update(range(token.start[0], token.end[0] + 1))
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and _is_text(node.value):
            code.difference_update(range(node.lineno, node.end_lineno + 1))
    code = set(n for n in code if n <= len(source) and source[n - 1].strip())
    functions = sorted([n.name, n.lineno, n.end_lineno, len([k for k in code if n.lineno <= k <= n.end_lineno])]
                       for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)))
    return len(code), sorted(functions, key=lambda f: (f[1], f[2]))


@unittest.skipIf(sys.version_info < (3, 8), "the ast module gives a node's last line from Python 3.8 on")
class AgainstPythonsParser(unittest.TestCase):
    """Python files against ast: the samples and the skill's own scripts."""

    def check(self, path):
        measure = support.load("measure")
        text = read(path)
        lines, functions, language = measure.functions(os.path.basename(path), text)
        truth_lines, truth = python_truth(text)
        self.assertEqual(language, "Python")
        self.assertEqual([[f[0], f[1], f[2], f[3]] for f in functions], truth)
        self.assertEqual(lines, truth_lines)

    def test_samples(self):
        for name in sorted(os.listdir(FUNCTIONS)):
            if name.endswith(".py"):
                with self.subTest(sample=name):
                    self.check(os.path.join(FUNCTIONS, name))

    def test_the_skills_own_scripts(self):
        names = sorted(n for n in os.listdir(support.SCRIPTS) if n.endswith(".py"))
        self.assertTrue(names)
        for name in names:
            with self.subTest(script=name):
                self.check(os.path.join(support.SCRIPTS, name))

    def test_the_hand_written_answers_agree_with_the_parser(self):
        expected = json.loads(read(os.path.join(FUNCTIONS, "expected.json")))
        for name in sorted(expected):
            if name.endswith(".py"):
                with self.subTest(sample=name):
                    self.assertEqual(python_truth(read(os.path.join(FUNCTIONS, name)))[1], expected[name])


class Docstrings(unittest.TestCase):
    """Docstrings are documentation; a string that's assigned, passed or returned is code."""

    def test_module_class_and_function_docstrings_are_left_out(self):
        text = read(os.path.join(FUNCTIONS, "docstrings.py"))
        lines, _, _ = support.load("measure").functions("docstrings.py", text)
        # 36 lines: 8 blank, 1 comment, and 11 of docstrings (2 + 1 + 1 + 4 + 1 + 1 + 1) leave 16.
        self.assertEqual(lines, 16)

    def test_strings_that_are_code(self):
        text = 'def f():\n    x = """a\nb"""\n    g("""c\nd""")\n    return """e\nf"""\n'
        self.assertEqual(found("s.py", text), [["f", 1, 7, 7]])

    def test_docstring_alone(self):
        text = 'def f():\n    """Only a docstring.\n\n    More.\n    """\n'
        self.assertEqual(found("s.py", text), [["f", 1, 5, 1]])


class Preprocessor(unittest.TestCase):
    """C's, C++'s, C#'s and Swift's #if and #define, read as their preprocessor reads them."""

    def test_a_define_and_if_zero(self):
        # Neither a #define's brace nor one under #if 0 counts, so f ends at its own closing brace.
        text = ("#define OPEN_BLOCK {\nint f(void) {\n#if 0\n    if (x) {\n#endif\n    return 0;\n}\n"
                "int g(void) {\n    return 1;\n}\n")
        _, functions, _ = support.load("measure").functions("a.c", text)
        self.assertEqual([f[:3] for f in functions], [("f", 2, 7), ("g", 8, 10)])


# Methods whose type arguments hold an annotation, as guava writes them; structs specialized on a function's
# type, as abseil and nlohmann/json write them, which aren't functions; and Kotlin's and C#'s type arguments.
ANNOTATED = [("public static <T extends @Nullable Object> T getLast(Iterator<T> iterator) {", "getLast"),
             ("public Set<Entry<Class<? extends @NonNull B>, B>> entrySet() {", "entrySet"),
             ("public <K extends @Nullable Object, V> Map<K, @Nullable V> make(K key) {", "make")]
STRUCTS = ["template <typename T, typename R, typename... P>\nstruct GiveQualifiersToFunImpl<T&&, R(P...)> {\n"
           "  using type = R(P...);\n};\n",
           "template <typename D, typename V, typename Ret, typename... Args>\n"
           "struct MockSingleOverload<D, V, Ret(MockingBitGen&, Args...)> {\n  int x;\n};\n",
           "template<typename F>\n"
           "struct is_binary64 : std::integral_constant<bool, has_binary64_format<F>()> {};\n"]
OTHERS = [("a.kt", "fun <T : @Anno Any> first(list: List<@Anno T>): Map<String, @Anno Int> {\n  return mapOf()\n}\n",
           "first"),
          ("a.kt", "fun <T> List<@UnsafeVariance T>.second(): T {\n  return this[1]\n}\n", "second"),
          ("A.cs", "class A {\n  public Dictionary<string, List<int?>> Get() {\n    return null;\n  }\n}\n", "Get"),
          ("A.cs", "class A {\n  public IEnumerable<(string Name, int Age)> People() {\n    return null;\n  }\n}\n",
           "People")]


class TypeArguments(unittest.TestCase):
    """What a type's arguments can hold: an annotation, and spaces, as guava's methods write them; a struct
    specialized on a function's type isn't a function."""

    def names(self, name, text):
        return [f[0] for f in support.load("measure").functions(name, text)[1]]

    def test_annotations_in_java_type_arguments(self):
        for line, name in ANNOTATED:
            with self.subTest(line=line):
                self.assertEqual(self.names("A.java", "class A {\n  %s\n    return null;\n  }\n}\n" % line), [name])

    def test_structs_specialized_on_a_functions_type(self):
        for text in STRUCTS:
            with self.subTest(text=text.split("\n")[1]):
                self.assertEqual(self.names("a.hpp", text), [])

    def test_kotlin_and_cs_type_arguments(self):
        # As v1.0.0 read them too.
        for name, text, want in OTHERS:
            with self.subTest(text=text.split("\n")[0]):
                self.assertEqual(self.names(name, text), [want])


class Caps(unittest.TestCase):
    """How far a definition's line is read, where a line that isn't one can be split between its parts in every way:
    in the C family, sixteen annotations, a template's first seventeen > and eight modifiers, one more of which loses
    the definition (a limit, as v1.6.0 had none); and JavaScript's object literals nine deep, as v1.6.0 read them."""

    def names(self, name, text):
        return [f[0] for f in found(name, text)]

    def test_annotations(self):
        for count, names in ((16, ["f"]), (17, [])):
            with self.subTest(count=count):
                text = "class K {\n  %s void f() {\n    g();\n  }\n}\n" % " ".join("@A%d" % k for k in range(count))
                self.assertEqual(self.names("K.java", text), names)

    def test_a_templates_closings(self):
        # Its default's type arguments' > before its own, the first sixteen read.
        for count, names in ((16, ["f"]), (17, [])):
            with self.subTest(count=count):
                text = "template <class T> struct A {};\ntemplate <class T = %sint%s, class B = int> void f() {\n" \
                       "  g();\n}\n" % ("A<" * count, ">" * count)
                self.assertEqual(self.names("a.cpp", text), names)

    def test_modifiers(self):
        # A modifier a type's word can't be, extern "C", after seven or eight others.
        for count, names in ((7, ["f"]), (8, [])):
            with self.subTest(count=count):
                self.assertEqual(self.names("a.cpp", "inline " * count + 'extern "C" int f() {\n  g();\n}\n'), names)

    def test_object_keys(self):
        # f0 to f8, each in an object one deeper than the last, f8's nine deep, and m in a tenth: past the cap, though
        # node reads m as a function too.
        text = "x = {\n"
        for k, name in enumerate(["f%d" % k for k in range(9)] + ["m"]):
            pad = "  " * (k + 1)
            text += pad + name + ": function () {\n" + pad + "  return 1;\n" + pad + "},\n"
            text += pad + "abcdefghi"[k] + ": {\n" if k < 9 else ""
        text += "".join("  " * k + "},\n" for k in range(9, 0, -1)) + "};\n"
        self.assertEqual(self.names("a.js", text), ["f%d" % k for k in range(9)])


def set_aside(text):
    """measure.functions' answer for a Rust file with its tests set aside, as measure.py's run asks: its code
    lines, its functions as [name, first, last, code lines], and each part set aside as [first, last, code lines,
    functions]."""
    aside = []
    lines, functions, _ = support.load("measure").functions("lib.rs", text, aside)
    return lines, [list(f[:4]) for f in functions], [list(part) for part in aside]


# A library with its tests in a module, as cargo writes one: 11 code lines, 8 of them the module's.
RUST = ("pub fn add(a: i32) -> i32 {\n    a + 1\n}\n\n#[cfg(test)]\nmod tests {\n    use super::*;\n\n    #[test]\n"
        "    fn adds() {\n        assert_eq!(add(1), 2);\n    }\n}\n")


class TestsInsideFiles(unittest.TestCase):
    """Rust's items compiled only for tests, set aside as test files are."""

    def test_a_test_module(self):
        self.assertEqual(set_aside(RUST), (3, [["add", 1, 3, 3]], [[5, 13, 8, 1]]))
        # With nothing to set it aside in, it's measured, as with --keep-tests.
        self.assertEqual(found("lib.rs", RUST), [["add", 1, 3, 3], ["adds", 10, 12, 3]])

    def test_only_a_cfg_that_needs_test(self):
        for cfg, aside in (('all(test, feature = "std")', 1), ("all(unix, all(not(miri), test))", 1),
                           ("any(all(test, a), all(test, b))", 1), ("all(\n    test,\n)", 1), ("not(test)", 0),
                           ('any(test, feature = "x")', 0), ("any()", 0), ('all(feature = "test")', 0)):
            with self.subTest(cfg=cfg):
                lines, _, parts = set_aside(RUST.replace("(test)", "(%s)" % cfg))
                self.assertEqual((lines, len(parts)), (3, 1) if aside else (11 + cfg.count("\n"), 0))
        self.assertEqual(set_aside(RUST.replace("cfg(test)", "cfg_attr(test, derive(Debug))"))[2], [])

    def test_where_a_module_starts_and_ends(self):
        for text, want in (
                # Other attributes, comments and blank lines between; any name, after pub(crate).
                (RUST.replace("mod tests", "#[allow(unused)]\n// A.\n\n/// B.\npub(crate) mod fakes"),
                 (3, [["add", 1, 3, 3]], [[5, 17, 9, 1]])),
                # Nested: the outermost.
                ("mod a {\n    #[cfg(test)]\n    mod t {\n        #[cfg(test)]\n        mod u {\n"
                 "            fn a() {}\n        }\n    }\n}\n", (2, [], [[2, 8, 7, 1]])),
                # Past braces in strings, characters and comments, after a lifetime.
                ("#[cfg(test)]\nmod t {\n    fn t<'a>(s: &'a str) {\n"
                 "        f(\"}\", r#\"}\"#, b'}', '}'); /* } */ // }\n    }\n}\nfn b() {\n}\n",
                 (2, [["b", 7, 8, 2]], [[1, 6, 6, 1]])),
                # An inner attribute, first in its body, after others; a raw name; a function just before.
                ("mod t {\n    //! A.\n    #![cfg(test)]\n    fn a() {\n    }\n}\n", (0, [], [[1, 6, 5, 1]])),
                ("mod r#t {\n    //! A.\n    //! B.\n    //! C.\n    #![allow(unused)]\n    #![cfg(test)]\n}\n",
                 (0, [], [[1, 7, 4, 0]])),
                ("fn a() {}\n#[cfg(test)]\nmod r#tests {\n    fn b() {}\n}\n", (1, [["a", 1, 1, 1]], [[2, 5, 4, 1]])),
                # Attributes before the cfg, lines of comments after it, and pub(crate) before a module's head.
                ("#[allow(dead_code)]\n#[inline]\n#[cfg(test)]\nfn f() {\n}\n", (0, [], [[1, 5, 5, 1]])),
                # An inner attribute before it is the file's, not the item's.
                ("#![allow(dead_code)]\n#[cfg(test)]\nfn f() {\n}\n", (1, [], [[2, 4, 3, 1]])),
                # Indented attributes before it, a method's, by spaces or tabs.
                ("impl S {\n    #[inline]\n    #[cfg(test)]\n    fn f() {}\n}\n", (2, [], [[2, 4, 3, 1]])),
                ("impl S {\n\t#[inline]\n\t#[cfg(test)]\n\tfn f() {}\n}\n", (2, [], [[2, 4, 3, 1]])),
                ("#[cfg(test)]\n// A.\n// B.\n// C.\nfn f() {\n}\n", (0, [], [[1, 6, 3, 1]])),
                ("pub(crate) mod t {\n    #![cfg(test)]\n}\n", (0, [], [[1, 3, 3, 0]])),
                # A longer pub(in ...); the innermost module an inner cfg is first in; a # and a ! apart from their [.
                ("pub(in crate::parse) mod t {\n    #![cfg(test)]\n}\n", (0, [], [[1, 3, 3, 0]])),
                ("mod a {\n    fn f() {}\n    mod t {\n        #![cfg(test)]\n        fn g() {}\n    }\n}\n",
                 (3, [["f", 2, 2, 1]], [[3, 6, 4, 1]])),
                ("# [cfg(test)]\nfn f() {}\nmod t {\n    # ! [cfg(test)]\n}\n", (0, [], [[1, 2, 2, 1], [3, 5, 3, 0]])),
                # A declaration, whose module is a file of its own; a use's attribute, not the module's after it.
                ("#[cfg(test)]\nmod t;\nmod a {\n}\n#[cfg(test)]\nuse b::c;\nmod d {\n}\n", (6, [], [[5, 6, 2, 0]]))):
            with self.subTest(text=text):
                self.assertEqual(set_aside(text), want)


    def test_items_besides_modules(self):
        # A function, an impl and its methods, a use, a constant and a struct; not a statement in a function's
        # body, which is the function's.
        text = ("fn keep() {\n    #[cfg(test)]\n    let x = 1;\n}\n#[cfg(test)]\npub fn mock() {\n    f();\n}\n"
                "#[cfg(test)]\nimpl Store {\n    fn a() {}\n    fn b() {}\n}\n#[cfg(test)]\nuse std::fmt;\n"
                "#[cfg(test)]\nconst SIZES: [u8; 3] = [1, 2, 3];\n#[cfg(test)]\nstruct Fake {\n    x: u8,\n}\n")
        self.assertEqual(set_aside(text), (4, [["keep", 1, 4, 4]], [[5, 8, 4, 1], [9, 13, 5, 2], [14, 15, 2, 0],
                                                                    [16, 17, 2, 0], [18, 21, 4, 0]]))
        # A use's group and a constant's struct, whose } the item's ; follows on its line.
        text = "#[cfg(test)]\nuse a::{b, c};\n#[cfg(test)]\nconst S: Size = Size {\n    w: 1,\n};\n"
        self.assertEqual(set_aside(text)[2], [[1, 2, 2, 0], [3, 6, 4, 0]])
        # A ; after a body's }, a space between; and a line the body's end shares with one more character.
        for text, want in (("#[cfg(test)]\nstruct S {\n    a: u8,\n} ;\nfn g() {}\n",
                            (1, [["g", 5, 5, 1]], [[1, 4, 4, 0]])),
                           ("mod t {\n    #[cfg(test)]\n    struct S {\n    };}\n", (2, [], [[2, 3, 2, 0]])),
                           ("mod t {\n    #[cfg(test)]\n    fn f() {\n    }}\n", (2, [], [[2, 3, 2, 1]]))):
            with self.subTest(text=text):
                self.assertEqual(set_aside(text), want)
        # A cfg on a parameter, or on a match arm with no block, is that part's: the function keeps its body.
        for text in ("fn run(#[cfg(test)] hook: u8, n: u8) -> u8 {\n    n\n}\n",
                     "fn pick(v: u8) -> u8 {\n    match v {\n        #[cfg(test)]\n        0 => 0,\n        _ => {\n"
                     "            v\n        }\n    }\n}\n"):
            with self.subTest(text=text):
                self.assertEqual(set_aside(text)[2], [])
        # union is a keyword only before a union's name: a variable so named starts a statement.
        for text in ("fn join(mut union: Vec<u8>) -> Vec<u8> {\n    #[cfg(test)]\n    union.push(2);\n    union\n}\n",
                     "fn clear(mut union: u16) -> u16 {\n    #[cfg(test)]\n    union = 0;\n    union\n}\n"):
            with self.subTest(text=text):
                self.assertEqual(set_aside(text), (5, [[text[3:text.index("(")], 1, 5, 5]], []))
        for text in ("#[cfg(test)]\nunion Bits {\n    a: u8,\n}\n", "#[cfg(test)]\nunion r#type {\n    a: u8,\n}\n",
                     "#[cfg(test)]\nunion Cell<T: Copy> {\n    a: T,\n}\n"):
            with self.subTest(text=text):
                self.assertEqual(set_aside(text)[2], [[1, 4, 4, 0]])


    def test_where_an_item_ends(self):
        # A constant's braces are its value's, to its ;; an impl's or a struct's in a type's arguments, as a const
        # generic's, are not its body.
        for text, want in (
                ("#[cfg(test)]\nconst MAX: u8 = if cfg!(unix) {\n    1\n} else {\n    2\n};\nfn next() {\n}\n",
                 (2, [["next", 7, 8, 2]], [[1, 6, 6, 0]])),
                ("#[cfg(test)]\nconst MIN: u8 = if cfg!(unix) { 1 } else { 2 };\n", (0, [], [[1, 2, 2, 0]])),
                ("#[cfg(test)]\nstatic SIDE: u8 = if cfg!(unix) { 1 } else { 2 };\n", (0, [], [[1, 2, 2, 0]])),
                # An arrow's > closes no type's arguments; a union's body may open on the next line.
                ("#[cfg(test)]\nfn grid() -> Grid<{ 2 }> {\n    Grid\n}\n", (0, [], [[1, 4, 4, 1]])),
                ("#[cfg(test)]\nunion Bits\n{\n    a: u8,\n}\n", (0, [], [[1, 5, 5, 0]])),
                ("#[cfg(test)]\nimpl Fixed for Grid<{ 2 * 3 }> {\n    fn width(&self) -> u8 {\n        6\n    }\n}\n"
                 "fn after() {\n}\n", (2, [["after", 7, 8, 2]], [[1, 6, 6, 1]])),
                ("#[cfg(test)]\nstruct Wide<const N: usize = { 1 + 1 }> {\n    a: [u8; N],\n}\n",
                 (0, [], [[1, 4, 4, 0]])),
                # Type parameters over lines, the > that closes them starting its line.
                ("#[cfg(test)]\nimpl<\n    T: Clone,\n> Shelf for T {\n}\n", (0, [], [[1, 5, 5, 0]])),
                # A generic parameter's attributes, in the item's own generics, aren't the next item's.
                ("#[cfg(test)]\nunsafe impl<#[may_dangle] T> Drop for Ring<T> {\n    fn drop(&mut self) {}\n}\n"
                 "fn after() {\n}\n", (2, [["after", 5, 6, 2]], [[1, 4, 4, 1]])),
                ("#[cfg(test)]\nfn pair<#[cfg(unix)] T, #[a] #[b] U>(a: U) {\n}\n", (0, [], [[1, 3, 3, 1]])),
                ("#[cfg(test)]\nfn width<#[a] const N: usize>() {\n}\n", (0, [], [[1, 3, 3, 1]])),
                ("#[cfg(test)]\ntype Pair<#[cfg(unix)] T> = (T, T);\nfn after() {}\n", (1, [["after", 3, 3, 1]],
                                                                                    [[1, 2, 2, 0]])),
                # A cfg on a const generic parameter, after a < or a ,, is the parameter's: no item follows a < or a ,.
                ("pub fn width<#[cfg(test)] const N: usize>() -> usize {\n    let a = 1;\n    a + 2\n}\n"
                 "pub static LIMIT: u8 = 1;\n", (5, [["width", 1, 4, 4]], [])),
                ("fn pair<T, #[a] #[cfg(test)] const M: usize>() {\n}\nconst SIZE: u8 = 2;\n",
                 (3, [["pair", 1, 2, 2]], [])),
                # A test item after it on its line is still read, whether a ; ends the struct the parameter's in or not.
                ("fn span<#[cfg(test)] const N: usize>() {} #[cfg(test)] mod probes {\n    fn first() {}\n"
                 "    fn second() {}\n}\nfn later() {}\n",
                 (2, [["span", 1, 1, 1], ["later", 5, 5, 1]], [[2, 4, 3, 2]])),
                ("struct Mark<#[cfg(test)] const N: usize>; #[cfg(test)] mod probes {\n    fn first() {}\n"
                 "    fn second() {}\n}\nfn later() {}\n", (2, [["later", 5, 5, 1]], [[2, 4, 3, 2]]))):
            with self.subTest(text=text):
                self.assertEqual(set_aside(text), want)

    def test_a_long_value_and_a_long_head(self):
        # A constant goes on to its ;, however many lines its value holds; an item's head may run over several.
        for text, want in (
                ("#[cfg(test)]\nconst ROWS: &[u32] = &[\n" + "    1,\n" * 250 + "];\nfn tail() {\n}\n",
                 (2, [["tail", 254, 255, 2]], [[1, 253, 253, 0]])),
                ("#[cfg(test)]\nstatic TEXT: &str = \"\n" + "x\n" * 250 + "\";\n", (0, [], [[1, 253, 253, 0]])),
                ("#[cfg(test)]\nimpl<T> Grid for Shelf<T>\nwhere\n    T: Clone,\n    T: Copy,\n    T: Send,\n{\n}\n",
                 (0, [], [[1, 8, 8, 0]]))):
            with self.subTest(text=text[:40]):
                self.assertEqual(set_aside(text), want)

    def test_a_line_it_shares_with_other_code(self):
        # Stays counted, with its functions, whether that code comes before the item's attribute or after its end.
        for text, want in (("fn b() {} #[cfg(test)]\nmod t {\n    fn c() {}\n}\nfn d() {}\n",
                            (2, [["b", 1, 1, 1], ["d", 5, 5, 1]], [[2, 4, 3, 1]])),
                           ("mod a {\n} #[cfg(test)] mod u {\n    fn x() {}\n}\nfn d() {}\n",
                            (3, [["d", 5, 5, 1]], [[3, 4, 2, 1]])),
                           ("#[cfg(test)]\nmod t {\n    fn c() {}\n} fn d() {}\n",
                            (1, [], [[1, 3, 3, 1]])),
                           # A module whose inner cfg says so, its head after other code; a } with no {.
                           ("fn keep() {} mod inner { #![cfg(test)]\n    fn gone() {}\n}\nfn after() {}\n",
                            (2, [["keep", 1, 1, 1], ["after", 4, 4, 1]], [[2, 3, 2, 1]])),
                           ("fn one() {}\n} #[cfg(test)] fn two() {}\n", (2, [["one", 1, 1, 1]], []))):
            with self.subTest(text=text):
                self.assertEqual(set_aside(text), want)


    def test_not_in_a_macros_text(self):
        # Code that a macro writes, as quote! {...} and macro_rules! hold it, is the text of the code around it.
        for text, want in (("fn quoting() -> Tokens {\n    quote! {\n        #[cfg(test)]\n        mod tests {\n"
                             "            fn t() {}\n        }\n    }\n}\n",
                            (8, [["quoting", 1, 8, 8], ["t", 5, 5, 1]], [])),
                           ("macro_rules! tests {\n    () => {\n        #[cfg(test)]\n        mod t {}\n    };\n}\n",
                            (6, [], [])),
                           # A macro's name of 150 characters before its bracket.
                           ("macro_rules! " + "long_" * 30 + "name {\n    () => {\n        #[cfg(test)]\n"
                            "        mod t {}\n    };\n}\n", (6, [], [])),
                           # After a test item of its own: each cfg's brackets are its line's.
                           ("#[cfg(test)]\nfn a() {}\nfn q() -> T {\n    quote! {\n        #[cfg(test)]\n"
                            "        mod t {}\n    }\n}\n", (6, [["q", 3, 8, 6]], [[1, 2, 2, 1]]))):
            with self.subTest(text=text):
                self.assertEqual(set_aside(text), want)


class Strings(unittest.TestCase):
    """Strings, which can hold brackets and quotes, read as each language writes them."""

    def test_cs(self):
        # Each in A's body, before B: A ends at its own brace. Raw strings that open with four quotes or more,
        # holes of two braces, quotes in a verbatim string's holes.
        for string in ('""""\n        has """ in it {\n        """"', '$$"""\n        {"a": {{x}}\n        """',
                       '$"""\n        a {F("}")} b\n        """', '$@"a {d["}"]} b"', '@$"a {d["}"]} b"',
                       '$@"a\n{d["}"]} "" }} b"', '$@"x {d["k"]} {{ y"', '$"a {d["}"]} b"', '$@"{F(@"}""")}"',
                       '""""C:\\""""', '$""""\n        {x // """"\n        }\n        """"',
                       '$$"""\n        {{x // """\n        }}\n        """', '\n$"a {d["}"]} b"'):
            with self.subTest(string=string):
                n = string.count("\n")
                text = "class R {\n    string A() {\n        return %s;\n    }\n    int B() {\n        return 1;\n" \
                       "    }\n}\n" % string
                self.assertEqual([f[:3] for f in found("R.cs", text)], [["A", 2, 4 + n], ["B", 5 + n, 7 + n]])


    def test_four_quotes_in_python_and_kotlin(self):
        # Three quotes open the string and the fourth is in it, as in C# it would not be.
        self.assertEqual(found("a.py", 'x = """"a" b"""\ndef f():\n    return 1\n'), [["f", 2, 3, 2]])
        self.assertEqual(found("a.kt", 'val x = """"a" b"""\nfun f() {\n}\n'), [["f", 2, 3, 2]])


    def test_ruby_operator_names_after_undef_and_alias(self):
        # Each a method's name, as after def, not a literal's opening, as Ruby's parser has them: undef's, each of its
        # list, and alias's two.
        # And none after a word that ends in undef or alias, or a method of that name, nor more than alias's two; and
        # each kind of name in a list, a symbol, one ending in ?, an operator's, one past ASCII, one before a space.
        for line in ("undef `", "undef x, `", "undef `, :`", "alias ` run", "alias run `", "alias / div", "undef /",
                     "my_alias `ls`", "aliases `ls`", "x.alias `ls`", "alias a b if `x`", "undef :x, `", "undef a?, `",
                     "undef +, `", "undef \u00e9, `", "undef x , `", "undef a, b, `"):
            with self.subTest(line=line):
                text = "class A\n  %s\nend\n\ndef g\n  \"a\"\nend\n" % line
                self.assertEqual([f[:3] for f in found("a.rb", text)], [["g", 5, 7]])

    def test_ruby_def_after_a_word_that_ends_in_it(self):
        # mydef is a method's name, and what follows it its argument: no def opens there.
        text = "class A\n  def f\n    mydef `ls`\n  end\n\n  def g\n    1\n  end\nend\n"
        self.assertEqual([f[:3] for f in found("a.rb", text)], [["f", 2, 4], ["g", 6, 8]])

    def test_ruby_heredocs_end_in_the_order_they_open(self):
        text = "def f\n  x = [<<A, <<B]\n  a\nA\n  b }\nB\n  x\nend\n\ndef g\n  1\nend\n"
        self.assertEqual([f[:3] for f in found("a.rb", text)], [["f", 1, 8], ["g", 10, 12]])

    def test_a_regular_expression_on_each_line(self):
        # Each line's read of its own, though the same column of the next holds a / too.
        text = "function a() {\n  let r = /abcdefgh/;\n  let s = /x/, t = {};\n  return s;\n}\nfunction b() {\n" \
               "  return 1;\n}\n"
        self.assertEqual([f[:3] for f in found("a.js", text)], [["a", 1, 5], ["b", 6, 8]])

    def test_rust_raw_strings_after_an_at(self):
        # An @ before a raw string is a macro's token or a binding's, as inline snapshots write: @r#"..."#, @r"...".
        for string in ('@r#"say("(")"#', '@r"C:\\"', '@br"(\\"'):
            with self.subTest(string=string):
                text = "fn a() {\n    check!(run(), %s);\n}\nfn b() {\n}\n" % string
                self.assertEqual([f[:3] for f in found("a.rs", text)], [["a", 1, 3], ["b", 4, 5]])
        text = "#[cfg(test)]\nmod tests {\n    fn s() {\n        check!(run(), @r#\"f(\"(\")\"#);\n    }\n}\n"
        self.assertEqual(set_aside(text)[2], [[1, 6, 6, 1]])


# PHP's heredocs and nowdocs, each in a's body, before b and c, as PHP's tokenizer reads them (PHP 8.4): their text
# runs to the first line that starts with their name, after any spaces or tabs and before no letter, digit or _.
HEREDOCS = ["$t = <<<EOT\nan open { brace\nEOT;", "$t = <<<'EOT'\nan open { brace\nEOT;", "$t = <<<\"EOT\"\n{\nEOT;",
            "$t = <<< EOT\na close } brace\nEOT;", "$t = <<<EOT\n    an open { brace\n    EOT;",
            "$t = <<<'EOT'\n\tit's a \" quote\n\tEOT;", "$t = f(<<<EOT\na ( and a ' and {\nEOT);",
            "$t = f(<<<EOT\n[ ( {\nEOT, 2);", "$t = [<<<EOT\n[ {\nEOT];", "$t = <<<EOT\n{ \"\nEOT . '{' . f(1);",
            "$t = f(<<<A\n{ a\nA, <<<'B'\n} ' b\n  B);", "$t = <<<A\n{ a\nA . <<<B\n( b\nB;",
            "$t = <<<EOT\nEOTS {\nXEOT {\nx EOT; {\nEOT_ {\nEOT1 {\nEOTé {\nEOT;",
            "$t = <<<EOT\n{$x} ${y} {$a['}']} {$o->f(\"{\")} {$a[\"{\"]} {\nEOT;", "$t = <<<EOT\nEOT;",
            "$t = b<<<EOT\n{\nEOT;", "$t = <<<ÉTÉ\n{\nÉTÉ;", "$t = <<<A\U0001d400\n}\nA\U0001d400;",
            "$t = <<<A\x80\n}\nA\x80;", "$t = <<<EOT\n\x0cEOT\n}\nEOT;",
            # And <<< in a string or a comment, opening none; and one that no line closes, which PHP doesn't compile,
            # read as code, losing no function.
            "$t = \"<<<EOT\n{\";\nif ($t) {\n    EOT;\n}", "// <<<EOT\nif ($t) {\n    EOT;\n}",
            "# <<<EOT\nif ($t) {\n    EOT;\n}", "/* <<<EOT\n */ if ($t) {\n    EOT;\n}", "$t = <<<EOT"]


class Heredocs(unittest.TestCase):

    def test_heredocs_and_nowdocs(self):
        for heredoc in HEREDOCS:
            for end in ("\n", "\r\n"):
                with self.subTest(heredoc=heredoc, end=end):
                    n = heredoc.count("\n")
                    text = "<?php\nfunction a() {\n    %s\n    return $t;\n}\nfunction b() {\n    return 1;\n}\n" \
                           "function c() {\n    return 2;\n}\n" % heredoc
                    self.assertEqual([f[:3] for f in found("a.php", text.replace("\n", end))],
                                     [["a", 2, 5 + n], ["b", 6 + n, 8 + n], ["c", 9 + n, 11 + n]])

    def test_a_run_of_lt_signs(self):
        # PHP reads << where no heredoc opens, so a run of an odd number before a name opens one and of an even
        # number none, as its tokenizer has them.
        for run, last in ((4, 4), (5, 7), (6, 4), (7, 7)):
            with self.subTest(run=run):
                text = "<?php\nfunction a() {\n    $t = 1 %sEOT\n}\nEOT;\n    return $t;\n}\nfunction b() {\n" \
                       "    return 1;\n}\n" % ("<" * run)
                self.assertEqual([f[:3] for f in found("a.php", text)], [["a", 2, last], ["b", 8, 10]])

    def test_only_in_phps_code(self):
        # Not in HTML, where a line can end with <<<Name: before <?php, or after a ?> in code or ending a line
        # comment, up to the next <?php or <?=, in any case. A ?> in a block comment or a string ends nothing, and
        # <?phpx opens nothing, nor <? alone, as where PHP's short_open_tag is off.
        b = "function b() {\n    return 2;\n}\n"
        for text, a, after in (
                ("function a() {\n    ?>\n    <p>Go back <<< Home\n    <?php\n    return 1;\n}\n\n" + b +
                 "?>\nHome, sweet home.\n", 7, 9),
                ("function a() { // note ?>\n<b>it<<<X\n<?php\n    return 1;\n}\n" + b + "?>\nX marks\n", 6, 7),
                ("function a() { # note ?>\n<b>it<<<X\n<?php\n    return 1;\n}\n" + b + "?>\nX marks\n", 6, 7),
                ("function a() {\n    ?>\n    <p><<<Home\n    <?= 1 ?>\n    <p><<<Home\n    <?PHP\n    $t = <<<Home\n"
                 "{\nHome;\n    return 1;\n}\n" + b + "?>\nHome, sweet home.\n", 12, 13),
                ("function a() { // x ?> y <?php $t = 1;\n    $u = <<<X\n{\nX;\n    return 1;\n}\n" + b, 7, 8),
                ("function a() { /* ?> */\n    $u = <<<X\n{\nX;\n    return 1;\n}\n" + b, 7, 8),
                ("function a() { $s = '?>';\n    $u = <<<X\n{\nX;\n    return 1;\n}\n" + b, 7, 8),
                ("function a() {\n    ?>\n    <?phpx <<<X\n    <? <<<X\n    <?php\n    return 1;\n}\n" + b + "?>\nX\n",
                 8, 9),
                ("function a() {\n    ?>\n<?= <<<X\n}\nX ?>\n<?php\n    return 1;\n}\n" + b, 9, 10),
                ("function a() { // x ?> y <?php ?> z\n<p><<<X\n<?php\n    return 1;\n}\n" + b + "?>\nX\n", 6, 7)):
            with self.subTest(text=text):
                self.assertEqual([f[:3] for f in found("a.php", "<?php\n" + text)], [["a", 2, a], ["b", after,
                                                                                                    after + 2]])
        text = "<p>Back <<<X\n<?php\nfunction a() {\n    $t = <<<X\n{\nX;\n    return 1;\n}\n" + b
        self.assertEqual([f[:3] for f in found("a.php", text)], [["a", 3, 8], ["b", 9, 11]])

    def test_holes_over_lines(self):
        # A heredoc's {$...} and ${...} are code, over lines too, where a line that starts with its name is code, or a
        # string's, a comment's or a heredoc's of its own of the same name; \{$x} and {\$x} are none, nor a nowdoc's.
        b = "function b() {\n    return 2;\n}\n"
        for text, a in (("$t = <<<EOT\n{$f(\nEOT\n)} {\nEOT;", 9), ("$t = <<<EOT\n${f(\nEOT\n)} {\nEOT;", 9),
                        ("$t = <<<EOT\n{$f(<<<EOT\n{\nEOT\n)} {\nEOT;", 10),
                        ("$t = <<<EOT\n{$f('\nEOT\n')} {\nEOT;", 9),
                        ("$t = <<<EOT\n{$f(\"\nEOT\n\")} {\nEOT;", 9), ("$t = <<<EOT\n{$f( // }\nEOT\n)} {\nEOT;", 9),
                        ("$t = <<<EOT\n{$a[f(function () {\nEOT\n})]} {\nEOT;", 9),
                        ("$t = <<<EOT\n\\{$x} {\\$x} \\${x} {\n  EOT;", 7), ("$t = <<<EOT\n\\{$x {\nEOT;", 7),
                        ("$t = <<<EOT\nx ${f(\nEOT\n)} {\nEOT;", 9), ("$t = <<<EOT\nx {$f(\nEOT\n)} {\nEOT;", 9),
                        ("$t = <<<EOT\n\\\\{$x[\nEOT\n]}\nEOT;", 9),
                        ("$t = <<<'EOT'\n{$f(\nEOT;\n    $u = ')}';", 8)):
            with self.subTest(text=text):
                text = "<?php\nfunction a() {\n    %s\n    return $t;\n}\n%s" % (text, b)
                self.assertEqual([f[:3] for f in found("a.php", text)], [["a", 2, a], ["b", a + 1, a + 3]])

    def test_code_after_its_end(self):
        # A ${ after the heredoc's end is code's, no hole: the function's if is nested once.
        text = "<?php\nfunction a() {\n    $t = <<<EOT\n    x\n    EOT; ${\n        \"v\" . f(function () {\n" \
               "            if (1) {\n                return 1;\n            }\n        })\n    } = 1;\n" \
               "    return $t;\n}\n"
        self.assertEqual(support.load("measure").functions("a.php", text)[1], [("a", 2, 13, 12, 1)])

    def test_in_a_class_and_a_default(self):
        text = "<?php\nclass K {\n    public function a() {\n        $t = <<<EOT\nif (x) {\nEOT;\n" \
               "        return $t;\n    }\n    public function b() {\n        return 1;\n    }\n}\n"
        self.assertEqual([f[:3] for f in found("a.php", text)], [["a", 3, 8], ["b", 9, 11]])
        text = "<?php\nfunction page($x = <<<HTML\n<div>}</div>\nHTML) {\n    return $x;\n}\n\nfunction next() {\n" \
               "    return 1;\n}\n"
        self.assertEqual(found("a.php", text), [["page", 2, 6, 5], ["next", 8, 10, 3]])

    def test_its_lines(self):
        # Each line of its text is code, as a line of a multi-line string is, though it starts like a comment, and
        # one blank is blank; and its indentation is the text's, not the function's nesting.
        text = "<?php\nfunction f() {\n    $sql = <<<SQL\nSELECT 1\n# not a comment\n\n// nor this\n  \n" \
               "                        x\nSQL;\n    return $sql;\n}\n"
        lines, functions, _ = support.load("measure").functions("a.php", text)
        self.assertEqual((lines, functions), (10, [("f", 2, 12, 9, 0)]))


class Comments(unittest.TestCase):

    def test_block_comments_that_nest(self):
        # Rust's, Swift's and Kotlin's, as C's don't: a brace after the inner one's end is the comment's.
        for name, text in (("a.rs", "fn a() {\n    /* a /* b */ { */\n}\nfn b() {\n}\n"),
                           ("a.swift", "func a() {\n    /* a /* b */ { */\n}\nfunc b() {\n}\n"),
                           ("a.kt", "fun a() {\n    /* a /* b */ { */\n}\nfun b() {\n}\n")) + tuple(
                (name, "%s a() {\n    /* a /* b */\n}\n%s b() {\n}\n" % (word, word)) for name, word in (
                    ("a.c", "int"), ("a.cpp", "int"), ("A.java", "int"), ("A.cs", "int"), ("a.js", "function"),
                    ("a.ts", "function"), ("a.go", "func"), ("a.php", "function"))):
            with self.subTest(name=name):
                php = name.endswith(".php")  # Its code after <?php, a line down.
                self.assertEqual([f[:3] for f in found(name, "<?php\n" * php + text)],
                                 [["a", 1 + php, 3 + php], ["b", 4 + php, 5 + php]])

    def test_nesting_from_where_each_opens(self):
        # Two comments on one line don't nest; an inner one opens on a line with no */, or at its start.
        for text in ("fn a() {\n    f(/* x */ 1, /* y */ 2);\n}\nfn b() {\n}\n",
                     "fn a() {\n    /* x\n    /* y\n    */ { */\n}\nfn b() {\n}\n",
                     "fn a() {\n/* x\n/* y */ {\n*/\n}\nfn b() {\n}\n"):
            with self.subTest(text=text):
                n = text.count("\n")
                self.assertEqual([f[:3] for f in found("a.rs", text)], [["a", 1, n - 2], ["b", n - 1, n]])


    def test_an_inner_comment_that_opens_on_a_star(self):
        # /*/ opens one, as the compiler reads from the left, so the first */ after it closes that one; /**/ opens
        # one and closes it.
        for name, word in (("a.rs", "fn"), ("a.swift", "func")):
            with self.subTest(name=name):
                text = "/* a src/*/\n   b */\n%s hidden() {\n}\n*/\n%s after() {\n}\n/* c /**/ d */\n%s two() {\n}\n"
                self.assertEqual([f[:3] for f in found(name, text % (word, word, word))],
                                 [["after", 6, 7], ["two", 9, 10]])


class CodeLines(unittest.TestCase):
    """What counts as a code line in a file, in each kind of language."""

    def check(self, name, text, want):
        lines, _, _ = support.load("measure").functions(name, text)
        self.assertEqual(lines, want)

    def test_comments_and_blank_lines(self):
        self.check("a.js", "// one\n\n/* two\n   three */\nlet x = 1; // four\n  \n", 1)
        self.check("a.py", "# one\n\nx = 1  # two\n", 1)
        self.check("a.rb", "# one\nx = 1\n", 1)
        self.check("a.php", "<?php\n# one\n// two\n#[Attr]\nfunction f() {}\n", 3)

    def test_rubys_block_comments(self):
        # =begin ... =end is a comment, whatever its lines start with; and after __END__ comes data.
        self.check("a.rb", "def f\n  1\nend\n=begin\nnotes about f\n# more notes\n=end\nx = 1\n__END__\ndata\n", 4)

    def test_a_line_of_only_an_escape_in_a_string(self):
        # A line of the string, as any other is, so code; a docstring's is left out with the rest of it.
        for name, text, want in (("a.py", 'x = """a\n\\n\nb"""\n', 3), ("a.js", "x = `a\n\\t\nb`\n", 3),
                                 ("a.rs", 'let x = "a\n\\n\nb";\n', 3), ("a.swift", 'let x = """\n\\n\n"""\n', 3),
                                 ("A.java", 'String x = """\n\\n\n""";\n', 3), ("a.php", '<?php\n$x = "\n\\n\n";\n', 4),
                                 ("a.gd", 'var x = """a\n\\t\nb"""\n', 3), ("a.c", 'char *x = "a\\\n\\n\\\n";\n', 3),
                                 ("a.py", '"""a\n\\n\n"""\nx = 1\n', 1)):
            with self.subTest(name=name, text=text):
                self.check(name, text, want)

    def test_a_blank_line_in_a_string(self):
        # Blank, as any other is, whatever ends it: a checkout on Windows ends each line with \r\n.
        for name, text in (("a.py", 'x = """a\n   \nb"""\n'), ("a.js", "x = `a\n\nb`\n"), ("a.rb", 'x = "a\n  \nb"\n'),
                           ("a.cs", 'var x = @"a\n\nb";\n'), ("a.rs", 'let x = r#"a\n\nb"#;\n')):
            for end in ("\n", "\r\n"):
                with self.subTest(name=name, end=end):
                    self.check(name, text.replace("\n", end), 2)

    def test_a_language_with_no_rule_counts_lines(self):
        measure = support.load("measure")
        lines, functions, language = measure.functions("notes.txt", "a\n\n# b\n// c\nd\n")
        self.assertEqual((lines, functions, language), (2, None, None))


if __name__ == "__main__":
    unittest.main()
