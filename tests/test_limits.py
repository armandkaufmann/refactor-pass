"""What measure.py's help says it gets wrong, under "What it gets wrong", one test per limit.

Where the help calls something wrong, the test asserts what would be right and is marked expectedFailure:
if a change to measure.py fixes the limit, the test passes unexpectedly, the run fails, and the help needs
the line taken out. Where a limit is a choice the help describes (a nested function counted twice, an
anonymous function counted in the one around it), the test asserts today's behaviour, so the help stays
true. The last test checks the help still lists each of them.
"""

import unittest

try:
    from . import support
except ImportError:
    import support

# Each case: the file's name, which picks its language, and its text.
CASES = {
    "nested": ("a.py", "def outer():\n    def inner():\n        return 1\n    return inner\n"),
    "anonymous": ("a.js", "function outer(items) {\n  items.forEach(function (x) {\n    use(x);\n  });\n}\n"
                          "items.map((x) => {\n  return x;\n});\n"),
    "lambda": ("a.py", "def f(items):\n    return sorted(items, key=lambda x: (\n        x.a,\n    ))\n"),
    "mid-line": ("a.js", "const o = { a() { return 1 }, b() { return 2 } };\n"),
    "quoted key": ("a.js", "const routes = {\n  'GET /orders': function (req) {\n    return list(req);\n  },\n};\n"),
    "macro": ("a.c", "FOR_EACH(item, list) {\n    use(item);\n}\n\nint main(void) {\n    return 0;\n}\n"),
    "generic default": ("a.ts", "function h<T = {\n  onStart: () => void,\n}>(x: T) {\n  return x\n}\n"),
    "heredoc brace": ("a.php", "<?php\nfunction page() {\n    return <<<HTML\n<div>}</div>\nHTML;\n}\n\n"
                               "function next() {\n    return 1;\n}\n"),
    "regex after bracket": ("a.js", "function f(s) {\n  if (ok(s)) /}/.test(s)\n  return 1\n}\n"
                                    "function g() {\n  return 2\n}\n"),
    "heredoc comment": ("a.php", "<?php\nfunction f() {\n    $sql = <<<SQL\nSELECT 1\n# not a comment\nSQL;\n"
                                 "    return $sql;\n}\n"),
    "misindented": ("a.rb", "class App\n  def call(env)\n    raise 'bzzzt' if @called > 0\n  @called += 1\n"
                            "    [200, {}, ['OK']]\n  end\nend\n"),
    "alternatives": ("a.c", "#ifdef _WIN32\nint umain(void) {\n#else\nint main(void) {\n#endif\n  return 0;\n}\n"),
    "name on its own line": ("a.c", " static Bigint *\n Balloc(int k)\n{\n  return 0;\n}\n"),
    "class in capitals": ("a.cc", "class RE {\n public:\n  RE(const char* regex) { Init(regex); }\n};\n"),
    "made by a macro": ("a.cc", "GTEST_REPEATER_METHOD_(OnTestStart, TestInfo)\n"
                                "GTEST_REPEATER_METHOD_(OnTestEnd, TestInfo)\n"),
    "continuation": ("a.py", "def f(a, b):\n    total = a + \\\n            b\n    return total\n"),
    "bare jsx": ("a.tsx", "const Row = () =>\n  <tr>\n    <td>a</td>\n  </tr>\nconst next = 1\n"),
}


def measured(case):
    """measure.functions on a case: its code lines, and its functions as [name, first, last, code lines,
    deepest]."""
    name, text = CASES[case]
    lines, functions, _ = support.load("measure").functions(name, text)
    return lines, [list(f) for f in functions or []]


def spans(case):
    return [f[:4] for f in measured(case)[1]]


class KnownLimits(unittest.TestCase):

    def test_a_nested_function_counts_in_its_own_length_and_its_parents(self):
        # Known limit, by design: today's behaviour.
        self.assertEqual(spans("nested"), [["outer", 1, 4, 4], ["inner", 2, 3, 2]])

    def test_anonymous_functions_count_in_the_function_around_them(self):
        # Known limit, by design: today's behaviour. A callback or a lambda is no function of its own; its
        # lines are the enclosing function's, and at the top level they're in no function.
        self.assertEqual(spans("anonymous"), [["outer", 1, 5, 5]])
        self.assertEqual(spans("lambda"), [["f", 1, 4, 4]])

    @unittest.expectedFailure
    def test_a_function_that_does_not_start_a_line(self):
        self.assertEqual([f[0] for f in spans("mid-line")], ["a", "b"])

    @unittest.expectedFailure
    def test_a_quoted_key_holding_a_function(self):
        self.assertEqual([f[1:3] for f in spans("quoted key")], [[2, 4]])

    @unittest.expectedFailure
    def test_a_macro_shaped_like_a_function(self):
        self.assertEqual([f[0] for f in spans("macro")], ["main"])

    @unittest.expectedFailure
    def test_a_member_typed_as_a_function_in_a_generics_default(self):
        self.assertEqual(spans("generic default"), [["h", 1, 5, 5]])

    @unittest.expectedFailure
    def test_a_brace_in_a_heredoc(self):
        self.assertEqual(spans("heredoc brace"), [["page", 2, 6, 5], ["next", 8, 10, 3]])

    @unittest.expectedFailure
    def test_a_regular_expression_after_a_closing_bracket(self):
        self.assertEqual(spans("regex after bracket"), [["f", 1, 4, 4], ["g", 5, 7, 3]])

    @unittest.expectedFailure
    def test_a_line_in_a_heredoc_that_looks_like_a_comment(self):
        # Each line of the string is code, as a multi-line string's lines are; one that starts like a
        # comment is taken for one.
        self.assertEqual(spans("heredoc comment"), [["f", 2, 8, 7]])

    @unittest.expectedFailure
    def test_a_line_indented_less_than_the_body(self):
        self.assertEqual(spans("misindented"), [["call", 2, 6, 5]])

    def test_between_alternatives_the_last_is_read(self):
        # Known limit, by design: today's behaviour. Each branch opens main's body its own way; the last is
        # read, wherever the program is built.
        self.assertEqual(spans("alternatives"), [["main", 4, 7, 4]])

    @unittest.expectedFailure
    def test_a_c_function_whose_name_sits_indented_on_its_own_line(self):
        self.assertEqual(spans("name on its own line"), [["Balloc", 2, 5, 4]])

    @unittest.expectedFailure
    def test_a_constructor_in_its_class_whose_name_is_in_capitals(self):
        self.assertEqual(spans("class in capitals"), [["RE", 3, 3, 1]])

    @unittest.expectedFailure
    def test_functions_a_macro_makes(self):
        self.assertEqual([f[1] for f in spans("made by a macro")], [1, 2])

    @unittest.expectedFailure
    def test_nesting_of_a_continuation_line(self):
        self.assertEqual([f[4] for f in measured("continuation")[1]], [0])

    @unittest.expectedFailure
    def test_an_arrow_returning_jsx_with_no_brackets_around_it(self):
        # The body ends at its first line, since a JSX tag isn't an operator that an expression goes on after.
        # Brackets around the JSX, as formatters write it, are read right.
        self.assertEqual(spans("bare jsx"), [["Row", 1, 4, 4]])

    def test_each_case_runs_without_an_error(self):
        # An expected failure would hide an exception, so each case runs here on its own too.
        for case in CASES:
            with self.subTest(case=case):
                measured(case)

    def test_the_help_still_lists_them(self):
        measure = support.load("measure")
        limits = measure.__doc__.split("What it gets wrong:", 1)[1].split("\n\n", 1)[0]
        flat = " ".join(limits.split())
        for words in ("a nested function counts in its own length and in its parent's",
                      "anonymous functions and lambdas aren't functions of their own",
                      "a function that doesn't start a line",
                      "shapes can catch a macro, and miss a function a macro makes",
                      "in a type written after an = (as a generic's default)", "a brace or a quote in a PHP heredoc",
                      "follows a closing bracket or a name", "a line inside a PHP heredoc can count as code or not",
                      "an arrow function that returns JSX with no brackets around it ends at its first line",
                      "a line indented less than its body ends it there",
                      "only the last branch is read",
                      "a C function whose name sits indented on a line of its own",
                      "a C++ constructor written in its class when the class's name is in capitals",
                      "nesting by indentation counts a continuation line"):
            with self.subTest(limit=words):
                self.assertIn(words, flat)


if __name__ == "__main__":
    unittest.main()
