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

    def test_a_language_with_no_rule_counts_lines(self):
        measure = support.load("measure")
        lines, functions, language = measure.functions("notes.txt", "a\n\n# b\n// c\nd\n")
        self.assertEqual((lines, functions, language), (2, None, None))


if __name__ == "__main__":
    unittest.main()
