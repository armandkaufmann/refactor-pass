#!/usr/bin/env python3
"""How long a codebase's files and functions are, against the codebase itself.

For each language in the scope, the 70th, 80th and 90th percentiles of file
length and function length, weighted by lines as Alves et al. do it: the
90th is the length that 90% of the code is in files (or functions) no longer
than. Alves et al. use the three as bands of rising risk, and so does this:
a file or function is in the 70th, 80th or 90th band when it's at least as
long as that percentile and past the floor, over 220 code lines for a file
and 45 for a function (the catalogue's reference points, in its Measuring
section), so that a codebase of small files flags none of them. The 80th
and 90th bands are big; the 70th is worth a closer look. The file or
function a percentile falls in is in its band, since part of its lines are
past it; in a small codebase that's often the biggest few.

When one file holds a tenth of a language's file lines and is half as long
again as any other, the percentiles lean on it: it's its own 90th, and
every cut falls in it, so nothing shorter reaches a band. Then that
language's files are put in bands by the reference points instead: >220 for
over 220 code lines, worth a closer look, and >440 for over 440, big. The
same goes for functions, with >45 and >75. The output says when.

Then, per file, longest first:

  lines     its code lines: blank lines, lines that are only a comment and
            Python's docstrings are left out
  band      its band among the language's files, or - in none
  funcs     the functions found in it
  longest   its longest function, in code lines; its name and line follow
            the file's path
  long      how many of its functions are big: in the 80th or 90th band,
            or >75 where the reference points judge
  deepest   its deepest nesting inside a function, by indentation: 1 is a
            block inside the function's body, such as an if, and 2 a block
            inside that. Indentation tracks the classical complexity
            metrics closely (Hindle et al., 2008)

--show FILE lists that file's functions instead: each one's first and last
line, its code lines, deepest nesting and band. git log -L FIRST,LAST:FILE
then lists the commits that changed that function.

Functions are found by each language's definition keyword (def, func, fn,
fun, function, and Swift's init, deinit and subscript), operators' too
(Ruby's def [], Swift's static func ==); in JavaScript and TypeScript also
as methods, and as arrow functions or function expressions that are given
a name, assigned to a member (named by its last name: send for res.send =
function ..., exports for module.exports = ...) or exported as the default
(named default); and for C, C++, Java and C#, by their shape: a type, a
name, parentheses, then a body, after any annotations (@Test, [Fact]);
and in C++ also a constructor, a destructor or an operator with no type.
A name may carry type arguments (C#'s Get<T>, C++'s List<T>::Add, named
Get and List::Add), a name in backquotes is a name in Kotlin and Swift,
and a .h file is C++ when it holds a class, a namespace or a template. A
signature may run over several lines, and a body may sit on its
signature's line. Each language's strings
are read as it writes them (Ruby's regular expressions, % literals and
heredocs, C#'s @"...", Rust's r#"..."#, C++'s R"(...)"), and C's, C++'s,
C#'s and Swift's #if as their preprocessor does. A function runs to the end
of its body, found by indentation (Python, GDScript, Ruby) or by matching
brackets (the rest). Files in other languages get lines only, and the
output says which.

It points at code to read; it doesn't judge it. What it gets wrong:
  - a nested function counts in its own length and in its parent's;
  - anonymous functions and lambdas aren't functions of their own: their
    lines count in the function around them, or in none at the top level;
  - a function that doesn't start a line, such as a method in an object
    literal written on one line, isn't found;
  - shapes can catch a macro, and miss a function a macro makes; and in
    TypeScript a member typed as a function, in a type written after an =
    (as a generic's default), counts as a function;
  - a brace or a quote in a PHP heredoc, or in a JavaScript regular
    expression that follows a closing bracket or a name (not after an
    operator, an arrow or a word such as return or typeof), can put a
    function's end in the wrong place or lose the function;
  - an arrow function that returns JSX with no brackets around it ends at
    its first line;
  - a line inside a PHP heredoc can count as code or not, depending on how
    it starts;
  - where a function ends by indentation, a line indented less than its
    body ends it there, as a misindented end does in Ruby;
  - between #if and #else, when each branch opens a function's body its
    own way, only the first branch's opening is read;
  - a C function whose name sits indented on a line of its own, under its
    type, isn't found, nor a C++ constructor written in its class when the
    class's name is in capitals (RE()), as a macro's would be;
  - nesting by indentation counts a continuation line (a call or literal
    split over lines) as deeper, except inside brackets left open.

Usage:
  measure.py [options] [SCOPE ...]

SCOPE is a folder or a glob, as for heatmap.py; with none, every file git
tracks. Use the same scope as the heatmap. Test files are set aside as the
heatmap sets them aside, by name or folder, so they stay out of the
percentiles, and the output names any set aside in doubt; --test and
--not-test correct it, and --keep-tests measures them all. Any copy of this
skill a project keeps in the repo is left out, unless a scope names its
folder. Reads the working tree's tracked files only.

Examples:
  measure.py src tests
  measure.py -C /path/to/repo app lib --show app/models/order.rb
"""

import argparse
import os
import re
import sys
from collections import Counter, defaultdict

# The scope, the files left out and the tests, read the same way as heatmap.py reads them. No
# __pycache__ is written, so a run leaves the skill's folder as it was.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scoping  # noqa: E402

MODIFIERS = r"(?:(?:public|private|protected|internal|static|final|abstract|synchronized|native|virtual|override|" \
            r"sealed|async|extern|inline|unsafe|partial|new|const|constexpr|explicit|friend|default|open|" \
            r"extern\s+\"s*\")\s+)*"
# Per language of the C family: the words a statement starts with, so that a line starting with one holds no
# definition (not one that's also a method's modifier, as Java's synchronized; C#'s new starts more lines of
# expressions, as new Options(...) { ... }, than of definitions); and the words it reserves, which never name
# a function. Any other word can: delete names a method in Java, C and C#, await in C#, foreach in Java and C.
C_STATEMENTS = {
    "C": "return|if|for|while|switch|else|do|case|goto|sizeof",
    "C++": "return|if|for|while|switch|catch|else|do|new|throw|case|delete|goto|sizeof|try|using|namespace|"
           "co_await|co_return|co_yield",
    "Java": "return|if|for|while|switch|catch|else|do|new|throw|case|try|assert|yield|import|package",
    "C#": "return|if|for|foreach|while|switch|catch|else|do|new|throw|case|using|lock|goto|sizeof|typeof|nameof|"
          "yield|await|fixed|checked|unchecked|namespace",
}
C_RESERVED = {
    "C": "auto|break|case|char|const|continue|default|do|double|else|enum|extern|float|for|goto|if|inline|int|"
         "long|register|restrict|return|short|signed|sizeof|static|struct|switch|typedef|union|unsigned|void|"
         "volatile|while|alignas|alignof|bool|constexpr|false|nullptr|static_assert|thread_local|true|typeof|"
         "typeof_unqual|_Alignas|_Alignof|_Atomic|_BitInt|_Bool|_Complex|_Generic|_Imaginary|_Noreturn|"
         "_Static_assert|_Thread_local",
    "C++": "alignas|alignof|and|and_eq|asm|auto|bitand|bitor|bool|break|case|catch|char|char8_t|char16_t|"
           "char32_t|class|compl|concept|const|consteval|constexpr|constinit|const_cast|continue|co_await|"
           "co_return|co_yield|decltype|default|delete|do|double|dynamic_cast|else|enum|explicit|export|extern|"
           "false|float|for|friend|goto|if|inline|int|long|mutable|namespace|new|noexcept|not|not_eq|nullptr|"
           "operator|or|or_eq|private|protected|public|register|reinterpret_cast|requires|return|short|signed|"
           "sizeof|static|static_assert|static_cast|struct|switch|template|this|thread_local|throw|true|try|"
           "typedef|typeid|typename|union|unsigned|using|virtual|void|volatile|wchar_t|while|xor|xor_eq",
    "Java": "abstract|assert|boolean|break|byte|case|catch|char|class|const|continue|default|do|double|else|enum|"
            "extends|final|finally|float|for|goto|if|implements|import|instanceof|int|interface|long|native|new|"
            "package|private|protected|public|return|short|static|strictfp|super|switch|synchronized|this|throw|"
            "throws|transient|try|void|volatile|while|true|false|null|_",
    "C#": "abstract|as|base|bool|break|byte|case|catch|char|checked|class|const|continue|decimal|default|"
          "delegate|do|double|else|enum|event|explicit|extern|false|finally|fixed|float|for|foreach|goto|if|"
          "implicit|in|int|interface|internal|is|lock|long|namespace|new|null|object|operator|out|override|params|"
          "private|protected|public|readonly|ref|return|sbyte|sealed|short|sizeof|stackalloc|static|string|struct|"
          "switch|this|throw|true|try|typeof|uint|ulong|unchecked|unsafe|ushort|using|virtual|void|volatile|while",
}


def not_a_type(language):
    return r"(?!(?:%s)\b)" % C_STATEMENTS[language]


def not_a_name(language):
    return r"(?!(?:%s)(?![\w$]))" % C_RESERVED[language]


# A type is words and the punctuation of generics, arrays and pointers, or a tuple such as C#'s (int, string).
# A line that starts with a : (not C++'s ::) or a , goes on from the one before, as a constructor's initializers
# do, or C#'s : base(...).
# The name isn't a reserved word either, as in a labelled statement (again: switch (c) {), and doesn't follow
# class, record or the like, as C#'s class Name(int id) and Java's record Point(int x) do (C's struct x *f()
# can). Each part of a name can take type arguments, as C#'s Get<T>( and C++'s SkipList<Key, Cmp>::Insert( do;
# and in C# a part is an interface's, as in IDisposable.Dispose(. Java's names can hold a $, and C#'s start
# with an @ that makes a reserved word a name.
TYPE_ARGUMENTS = r"(?:<[^<>;(){}=]*(?:<[^<>;(){}=]*>[^<>;(){}=]*)*>)?"
TYPE_WORD = r"(?:[\w<>\[\],.?*&:]+|\([\w<>\[\],.?\s]+\))"
# Before it all, Java's annotations (@Test, @SuppressWarnings("x")) and C#'s attributes ([InlineData(1)]).
ANNOTATIONS = r"(?:@[\w.]+(?:\((?:[^()]|\([^()]*\))*\))?\s+|\[(?:[^\[\]()]|\((?:[^()]|\([^()]*\))*\))*\]\s*)*"
# C++'s template <...> before a definition on its line, whatever its parameters hold (= false, enable_if(...)).
TEMPLATE = r"(?:template\s*<[^;{}]*?>\s*)?"
# After the name and its (: no ; before a body's {, which may hold the whole body, as in int f() { return 1; }.
SIGNATURE_REST = r"[^;{]*(?:\{.*)?$"


def c_name(language):
    letter = r"[\w$~]" if language == "Java" else r"[\w~]"
    first = (r"@?" if language == "C#" else "") + r"(?!\d)" + letter
    return first + letter + "*" + TYPE_ARGUMENTS + r"(?:(?:::~?|\.)" + letter + "+" + TYPE_ARGUMENTS + r")*"


def c_head(language):
    return (r"^\s*(?!:(?!:)|,)" + TEMPLATE + ANNOTATIONS + not_a_type(language) + MODIFIERS + r"(?:" + TYPE_WORD +
            r"\s+)+[*&]*" + not_a_name(language) + r"(?<!\bclass )(?<!\bstruct )(?<!\brecord )(?<!\binterface )"
            r"(?<!\benum )(?<!\bunion )(" + c_name(language) + r")\s*\(")


# Java and C# also write a constructor with no modifier, so with nothing before its name.
CONSTRUCTOR = r"|^\s*" + ANNOTATIONS + r"([A-Z]\w*)\s*\(" + SIGNATURE_REST
# C# also writes a method's body as an expression after =>, on its own line with its ;; and an operator, whose
# name is operator and what follows it (operator ==, implicit operator Money).
CS_SHAPES = (r"^\s*" + ANNOTATIONS + MODIFIERS + r"(?:" + TYPE_WORD + r"\s+)*(operator\s*(?:[^\w\s(]+|true\b|"
             r"false\b|[\w.]+" + TYPE_ARGUMENTS + r"\??))\s*\((?:" + SIGNATURE_REST + r"|[^;]*\)\s*=>)|" +
             c_head("C#") + SIGNATURE_REST + CONSTRUCTOR + "|" + c_head("C#") + r"[^;]*\)\s*=>")
JAVA_SHAPES = c_head("Java") + SIGNATURE_REST + CONSTRUCTOR


# C and C++ also put the type on the line above, with the name at the margin.
def c_shapes(language):
    return (c_head(language) + SIGNATURE_REST + r"|^" + not_a_name(language) + r"(" + c_name(language) +
            r")\s*\(" + SIGNATURE_REST)


# C++ also writes an operator (bool operator==(...), operator int(), auto operator()(...)), whose name is
# operator and what follows it, and a constructor or a destructor in its class with no type (Stats() {,
# virtual ~Rep() {), whose name isn't in capitals, as a macro that annotates a signature is.
CPP_SHAPES = (r"^\s*" + TEMPLATE + MODIFIERS + r"(?:(?:[\w<>\[\],.*&:]+)\s+)*[*&]*(?:\w+" + TYPE_ARGUMENTS + r"::)*"
              r"(operator\s*(?:\(\)|[^\w\s(][^\s(]*|[A-Za-z_][\w\s:<>*&]*?))\s*\(" + SIGNATURE_REST + "|" +
              c_shapes("C++") + r"|^\s*" + TEMPLATE + r"(?:(?:explicit|inline|constexpr|virtual)\s+)*" +
              not_a_type("C++") + not_a_name("C++") + r"(?![A-Z][A-Z0-9_]*\s*\()(~?[A-Za-z_]\w*)\s*\(" +
              SIGNATURE_REST)
# A .h file is C's header or C++'s: C++'s when its code holds what C has none of, as a class, a namespace, a
# template, an access label or std::.
CPP_IN_HEADER = re.compile(r"^\s*(?:template\s*<|namespace(?:\s+[\w:]+)?\s*\{|(?:public|private|protected)\s*:|"
                           r"class\s+\w)|\bstd::", re.M)

# JavaScript and TypeScript: how a definition's line starts, up to the bracket that opens its parameters
# (or its type parameters). What follows the parameters then says whether it's a function (js_function).
# catch can be a method's name too, written with no space before its bracket, unlike the statement's; async
# followed by a space starts an anonymous arrow function, such as a callback's.
JS_FUNCTION = re.compile(r"^\s*(?:export\s+)?(?:default\s+)?(?:declare\s+)?(?:async\s+)?(function)(?![\w$])\s*\*?\s*"
                         r"([\w$]+)")
JS_METHOD = re.compile(r"^\s*(?:(?:public|private|protected|static|async|readonly|override|abstract|get|set|declare|"
                       r"accessor)\s+)*\*?\s*(?!(?:if|for|while|switch|function|return|with|else|do|typeof|void|"
                       r"await|yield|new|case|import|super|instanceof)(?![\w$])|catch(?![\w$(])|async\s)"
                       r"(#?[\w$]+|\[[^\]]*\])\??\s*(?=[(<])")
# Directly in a class's body, where no statement can be, any word names a method, as an iterator's return() and
# throw() do; and in an object literal when no space comes before its bracket, unlike a statement's.
JS_ANY_METHOD = re.compile(r"^\s*(?:(?:public|private|protected|static|async|readonly|override|abstract|get|set|"
                           r"declare|accessor)\s+)*\*?\s*([\w$]+)\??\s*(?=[(<])")
# A name given a value: a variable or a class's property, typed or not; or an object literal's key.
JS_ASSIGNED = re.compile(r"^\s*(?:export\s+)?(?:(?:const|let|var|public|private|protected|static|readonly|declare|"
                         r"override|accessor)\s+)*(#?[\w$]+)\s*!?\s*(?::(?:[^=]|=>)+)?=(?![=>])\s*")
JS_KEY = re.compile(r"^\s*([\w$]+|\[[^\]]*\])\s*:\s*")
# A function given to a member in an assignment, named by the last name (exports, for module.exports = ...);
# and an anonymous one exported as the default, named default.
JS_MEMBER = re.compile(r"^\s*(?:[\w$]+\.)+(#?[\w$]+)\s*=(?![=>])\s*")
JS_DEFAULT = re.compile(r"^\s*export\s+default\s+")
# A declaration typed over several lines, whose = comes after its type (js_after_type).
JS_TYPED = re.compile(r"^\s*(?:export\s+)?(?:(?:const|let|var|public|private|protected|static|readonly|declare|"
                      r"override|accessor)\s+)+(#?[\w$]+)\s*[?!]?\s*:\s*")
# What's assigned: a function written out (its keyword, then an optional * and name), an arrow with one
# bare parameter, or a named function wrapped in a call, such as React.memo(function Card(...) {...}).
# The keyword is a whole word: functional and functionName are names.
JS_EXPRESSION = re.compile(r"(?:async\s+)?function(?![\w$])\s*\*?\s*[\w$]*\s*")
JS_ONE_PARAMETER = re.compile(r"(?:async\s+)?[\w$]+\s*=>")
JS_WRAPPED = re.compile(r"[\w.$]+\s*(?:<[^<>()]*>)?\(\s*(?=function(?![\w$])\s*\*?\s*[\w$]+\s*[(<])")
# A type that goes on past the end of its line (read from its last twelve characters): one that ends the
# line with an operator, an open bracket or an arrow, or that the next line goes on with a union, an
# intersection, a chain or a conditional's ? or :.
TYPE_GOES_ON = re.compile(r"(?:[|&:?.,<(\[{]|=>|\b(?:extends|keyof|typeof|is|as|in))$")
TYPE_GOES_ON_NEXT = re.compile(r"\s*[|&.?:]")
# A statement that declares a type, whose braces hold its members.
JS_TYPE_STATEMENT = re.compile(r"(?:export\s+)?(?:declare\s+)?(?:type|interface)\b")
# A line that is only an object literal's key and its :, as before the { of an object nested in another.
JS_KEY_ONLY = re.compile(r"\s*(?:[\w$]+|\[[^\]]*\]|\"s*\"|'s*')\s*\??\s*:$")
# How far a parameter list or a return type may run: a component's destructured props, with their types, can
# take dozens of lines.
SIGNATURE_LINES = 200


# A file's brackets, worked out once per file (brackets_of).
BRACKETS = {"code": None}
BRACKET = re.compile(r"[()\[\]{}]")


def brackets_of(code):
    """The file's brackets: where each opening one closes; those left open at the start of each line, as
    a linked stack ((line, column, bracket), the rest), so that each line keeps its own without a copy;
    and how many more brackets each line opens than it closes, so a scan can pass a line whole. A closing
    bracket closes the innermost one open, whichever kind it is."""
    if BRACKETS["code"] is not code:
        stacks, closes, net, stack = [], {}, [], None
        for k, line in enumerate(code):
            stacks.append(stack)
            change = 0
            for found in BRACKET.finditer(line):
                if found.group() in OPEN:
                    stack = ((k, found.start(), found.group()), stack)
                    change += 1
                else:
                    change -= 1
                    if stack is not None:
                        closes[stack[0][:2]] = (k, found.end())
                        stack = stack[1]
            net.append(change)
        BRACKETS.clear()
        BRACKETS.update(code=code, stacks=stacks, closes=closes, net=net)
    return BRACKETS


def angle_counts(code):
    """Each line's count of opening and of closing brackets, angle brackets included but not an arrow's >,
    for scanning TypeScript's types and generics; worked out once per file, when first needed."""
    brackets = brackets_of(code)
    if "counts" not in brackets:
        brackets["counts"] = [(sum(line.count(c) for c in "([{<"),
                               sum(line.count(c) for c in ")]}>") - line.count("=>")) for line in code]
    return brackets["counts"]


def js_close(code, i, j, limit):
    """Where the bracket at code[i][j] closes: its line and the column after it, or None if it doesn't
    within limit lines. At a <, angle brackets count too, but not an arrow's >."""
    if code[i][j] != "<":
        end = brackets_of(code)["closes"].get((i, j))
        return end if end and end[0] - i < limit else None
    counts = angle_counts(code)
    depth = 0
    for k in range(i, min(len(code), i + limit)):
        opening, closing = counts[k]
        if k > i and closing < depth:  # It can't close in this line.
            depth += opening - closing
            continue
        line = code[k]
        for col in range(j if k == i else 0, len(line)):
            c = line[col]
            if c in OPEN or c == "<":
                depth += 1
            elif c in CLOSE or (c == ">" and line[col - 1:col] != "="):
                depth -= 1
                if depth <= 0:
                    return k, col + 1
    return None


def js_next(code, i, j, limit=3):
    """The line and column of the first character from code[i][j] on that isn't a space, or None."""
    for k in range(i, min(len(code), i + limit)):
        line = code[k]
        start = j if k == i else 0
        rest = len(line[start:]) - len(line[start:].lstrip())
        if line[start:].strip():
            return k, start + rest
    return None


def js_tail(code, k, col, want):
    """Where a function's body starts, if the parameter list that closed at code[k][col] is a function's:
    after an optional return type, the { of a method's body, or the => of an arrow function, on the same
    line or opening the next. None if something else comes first: a ; ends a declaration, a , or a
    closing bracket an argument or a parameter typed as a function, and a return type that's whole at the
    end of its line an overload or an abstract method, where nothing follows to say so. A { just after
    the type's :, a | or an & or the word is opens an object type, not the body."""
    typed, depth, previous, word = False, 0, "", ""
    counts = angle_counts(code)
    for i in range(k, min(len(code), k + SIGNATURE_LINES)):
        line = code[i]
        if i > k and typed and 0 < depth and counts[i][1] < depth:  # Inside the type's brackets throughout.
            depth += counts[i][0] - counts[i][1]
            last = line.rstrip()
            previous = last[-1:] or previous
            word = re.search(r"[\w$]*$", last).group(0)
            continue
        gap = True
        for j in range(col if i == k else 0, len(line)):
            c = line[j]
            if c.isspace():
                gap = True
                continue
            if not typed:
                if c != ":":
                    return (i, j) if line.startswith(want, j) else None
                typed = True
            elif depth == 0 and line.startswith(want, j) and not (c == "{" and (previous in ":|&" or word == "is")):
                return i, j
            elif line.startswith("=>", j) or line[j - 1:j + 1] == "=>":  # A function type's arrow.
                pass
            elif c in "([{<":
                depth += 1
            elif c in ")]}>":
                depth -= 1
                if depth < 0:
                    return None
            elif depth == 0 and c in ";,=":
                return None
            # The word just before, which a space may separate from what follows.
            letter = c.isalnum() or c in "_$"
            word = (word + c if word and not gap else c) if letter else ""
            previous, gap = c, False
        if typed and depth == 0 and not TYPE_GOES_ON.search(line.rstrip()[-12:]):
            following = next((n for n in range(i + 1, min(len(code), i + 20)) if code[n].strip()), None)
            if following is None:
                return None
            start = len(code[following]) - len(code[following].lstrip())
            if code[following].startswith(want, start):
                return following, start
            if not TYPE_GOES_ON_NEXT.match(code[following]):
                return None
    return None


def js_signature(code, i, j, want, call=True):
    """Where the body starts of a function whose parameters open at code[i][j], or its type parameters
    at a <; None if they aren't a function's. They have to close, and a body or an arrow follow
    (js_tail). Where the line could start a call (call), a list left open at its end must end the way a
    parameter list split over lines does, so a call with a callback (it(..., () => {) isn't followed to
    its end."""
    line = code[i].rstrip()
    end = js_close(code, i, j, SIGNATURE_LINES)
    if call and (end is None or end[0] != i):
        if not (line.endswith(("(", ",", "<", "[", "|", "&")) or
                (line.endswith("{") and line[:-1].rstrip().endswith(("(", ",", ":")))):
            return None
    if code[i][j] == "<":
        if end is None:
            return None
        at = js_next(code, end[0], end[1])
        if at is None or code[at[0]][at[1]] != "(":
            return None
        i, j = at
        end = js_close(code, i, j, SIGNATURE_LINES)
    return js_tail(code, end[0], end[1], want) if end else None


def js_in_braces(code, i):
    """Whether line i starts in braces, or in no brackets, as an object literal's key or a class's property
    does; not in parentheses or square brackets, as a parameter or a tuple's member does."""
    depth = 0
    for k in range(i - 1, max(-1, i - 200), -1):
        for c in reversed(code[k]):
            if c in CLOSE:
                depth += 1
            elif c in OPEN:
                depth -= 1
                if depth < 0:
                    return c == "{"
    return True


def js_opener(code, i, col):
    """The innermost bracket left open before code[i][col], as its line, column and character; None at the
    top level."""
    stack = brackets_of(code)["stacks"][i]
    for at, c in enumerate(code[i][:col]):
        if c in OPEN:
            stack = ((i, at, c), stack)
        elif c in CLOSE and stack is not None:
            stack = stack[1]
    return stack[0] if stack is not None else None


def js_in_object(code, i, col=0, depth=0):
    """Whether code[i][col] is inside an object literal, where a key's value can be a function: in braces
    opened after one of = ( , [ { ?, after return or export default, or after a ternary's : that starts
    its line. Not in an interface, a type, a class's body, a block or a parameter list, where a name typed
    as a function is a type. Braces opened after a key's : are an object literal's only if that key is in
    one."""
    opener = js_opener(code, i, col)
    if opener is None or opener[2] != "{":
        return False
    k, at, _ = opener
    before = code[k][:at].rstrip() or next((line.rstrip() for line in reversed(code[max(0, k - 20):k])
                                           if line.strip()), "")
    if re.search(r"\b(?:interface|class|enum|namespace|declare)\b|^\s*(?:export\s+)?type\b", before):
        return False
    if JS_KEY_ONLY.match(before):
        return depth < 8 and js_in_object(code, k, at, depth + 1)
    if not (before.strip() == ":" or re.search(r"(?:[=(,\[{?]|\|\||&&|\breturn|\bexport\s+default)$", before)) \
            or before.endswith("=>"):
        return False
    # Braces at the top level whose statement is a type or an interface hold its members, as after the > = of
    # generics split over lines, or the ? of a conditional type.
    return js_opener(code, k, at) is not None or not JS_TYPE_STATEMENT.match(js_statement(code, k, 0))


def js_statement(code, k, width):
    """The first line of the statement that line k is part of, at an indentation of width or less: the
    nearest line at or above it, indented no deeper, that starts with something other than a closing
    bracket or an operator."""
    for n in range(k, max(-1, k - 200), -1):
        line = code[n]
        start = line.lstrip()
        if start and len(line) - len(start) <= width and start[0] not in ">)]}?:|&=.,":
            return line
    return ""


def js_after_type(code, i, j):
    """Where the value starts that follows a type running from code[i][j] on, over several lines if need be:
    just after its =. None if the type ends some other way, as a declaration with no value does: with a ;,
    or at the end of a line it doesn't go on from."""
    depth = 0
    counts = angle_counts(code)
    for k in range(i, min(len(code), i + 40)):
        line = code[k]
        if k > i and 0 < depth and counts[k][1] < depth:  # Inside the type's brackets throughout.
            depth += counts[k][0] - counts[k][1]
            continue
        for col in range(j if k == i else 0, len(line)):
            c = line[col]
            if line.startswith("=>", col) or line[col - 1:col + 1] == "=>":  # A function type's arrow.
                continue
            if c in "([{<":
                depth += 1
            elif c in ")]}>":
                depth -= 1
                if depth < 0:
                    return None
            elif depth == 0 and c in ";,=":
                return (k, col + 1) if c == "=" and line[col + 1:col + 2] != "=" else None
        if depth == 0 and line[j if k == i else 0:].strip() and not TYPE_GOES_ON.search(line.rstrip()[-12:]):
            following = next((n for n in range(k + 1, min(len(code), k + 20)) if code[n].strip()), None)
            if following is None or not re.match(r"\s*(?:[|&.]|=(?![=>]))", code[following]):
                return None
    return None


def js_expression(code, i, j):
    """Where the body starts of the function written out from its keyword at code[i][j] on, or None."""
    keyword = JS_EXPRESSION.match(code[i], j)
    at = js_next(code, i, keyword.end()) if keyword else None
    return js_signature(code, at[0], at[1], "{", call=False) if at and code[at[0]][at[1]] in "(<" else None


def js_value(code, i, j):
    """Where the body starts, if the value given from code[i][j] on (or from the next line) is a
    function; else None."""
    at = js_next(code, i, j)
    if at is None:
        return None
    k, j = at
    value = code[k][j:]
    if JS_EXPRESSION.match(value):
        return js_expression(code, k, j)
    if JS_ONE_PARAMETER.match(value):
        return k, j
    wrapped = JS_WRAPPED.match(value)
    if wrapped:
        return js_expression(code, k, j + wrapped.end())
    if re.match(r"async\b", value):
        at = js_next(code, k, j + len("async"))
        if at is None:
            return None
        k, j = at
    return js_signature(code, k, j, "=>") if code[k][j] in "(<" else None


def js_function(code, i):
    """The name of the function a JavaScript or TypeScript definition starts at line i, and where its body
    is looked for from, as a line and a column; or None. A function declaration is one by its keyword, a
    method by a body after its parameters, and a name given a value when that value is a function."""
    match = JS_FUNCTION.match(code[i])
    if match:
        body = js_expression(code, i, match.start(1))
        return (match.group(2), body) if body else None
    match = JS_METHOD.match(code[i])
    if not match:
        match = JS_ANY_METHOD.match(code[i])
        match = match if match and (js_in_class(code, i) or (
            code[i][match.end(1):match.end(1) + 1] in "(<" and js_in_object(code, i))) else None
    if match:
        body = js_signature(code, i, match.end(), "{") if not (match.group(1) == "catch" and js_after_try(code, i)) \
            else None
        return (match.group(1), body) if body else None
    match = JS_DEFAULT.match(code[i])
    if match:
        body = js_value(code, i, match.end())
        return ("default", body) if body else None
    match = JS_ASSIGNED.match(code[i]) or JS_MEMBER.match(code[i])
    body = js_value(code, i, match.end()) if match else None
    if body:
        return match.group(1), body
    match = JS_TYPED.match(code[i])
    at = js_after_type(code, i, match.end()) if match else None
    body = js_value(code, at[0], at[1]) if at else None
    if body and js_in_braces(code, i):  # Not a parameter's default value.
        return match.group(1), body
    # A key given a function is an object literal's; elsewhere, as in an interface, a class's body or a
    # parameter list, a name typed as a function is a type, and so is one whose type ends with a ;.
    match = JS_KEY.match(code[i])
    if match and not code[i].rstrip().endswith(";"):
        body = js_value(code, i, match.end())
        if body and not code[body[0]][body[1]:].rstrip().endswith(";") and js_in_object(code, i):
            return match.group(1), body
        # In a class's body, the name and its type are a property's, as after a modifier (JS_TYPED).
        at = js_after_type(code, i, match.end()) if js_in_class(code, i) else None
        body = js_value(code, at[0], at[1]) if at else None
        if body:
            return match.group(1), body
    return None


def js_after_try(code, i):
    """Whether line i follows the end of a try's block, so a catch( that starts it is the statement's, written
    on its own line, and not a method named catch."""
    k = next((n for n in range(i - 1, max(-1, i - 20), -1) if code[n].strip()), None)
    if k is None or not code[k].rstrip().endswith("}"):
        return False
    opener = js_opener(code, k, len(code[k].rstrip()) - 1)
    if opener is None or opener[2] != "{":
        return False
    before = code[opener[0]][:opener[1]].rstrip() or next(
        (line.rstrip() for line in reversed(code[max(0, opener[0] - 20):opener[0]]) if line.strip()), "")
    return bool(re.search(r"(?<![\w$.])try$", before))


def js_in_class(code, i):
    """Whether line i starts directly in a class's body: in braces that a class's declaration opens."""
    opener = js_opener(code, i, 0)
    if opener is None or opener[2] != "{":
        return False
    line = code[opener[0]]
    return bool(re.search(r"\bclass\b", js_statement(code, opener[0], len(line) - len(line.lstrip()))))


# Per language: its extensions, how a definition's line looks (the name is
# whichever group matched; or, for JavaScript and TypeScript, a function that
# reads the lines), how its body ends, its comment markers, and its quotes:
# "char" when ' quotes one character (so a lone ' is something else, such as
# a Rust lifetime), "spans" when a quoted string can run over lines, "regex"
# when a / can open a regular expression.
LANGUAGES = [
    ("Python", ".py", r"^\s*(?:async\s+)?def\s+(\w+)", "indent", "#", ""),
    ("GDScript", ".gd", r"^\s*(?:static\s+)?func\s+(\w+)", "indent", "#", "spans"),
    # A def after a word, as private def, with a receiver (self., @@cache.) and an operator's name ([], <<).
    ("Ruby", ".rb", r"^\s*(?:[a-z_]\w*\s+)*def\s+(?:(?:self|@@?\w+|[A-Za-z_][\w:]*)\s*\.\s*)?([A-Za-z_]\w*[?!=]?|"
     r"\[\]=?|<=>|===?|=~|!=|!~|<<|>>|<=|>=|\*\*|[+\-~!]@?|[*/%<>^&|`])", "end", "#", "ruby"),
    ("JavaScript", ".js .jsx .mjs .cjs", js_function, "brackets", "// /*", "regex"),
    ("TypeScript", ".ts .tsx .mts .cts", js_function, "brackets", "// /*", "regex"),
    ("Vue", ".vue .svelte", js_function, "brackets", "// /*", "regex"),
    ("PHP", ".php", r"^\s*(?:(?:abstract|final|public|private|protected|static)\s+)*function\s+&?\s*(\w+)",
     "brackets", "// /* #", "spans"),
    ("Go", ".go", r"^func\s+(?:\([^)]*\)\s*)?(\w+)", "brackets", "// /*", "char"),
    # pub(crate) and pub(in path), and a raw name such as r#match, named match.
    ("Rust", ".rs", r"^\s*(?:pub(?:\([\w:\s]+\))?\s+)?(?:(?:default|const|async|unsafe|safe|extern\s+\"\w+\")\s+)*"
     r"fn\s+(?:r#)?(\w+)", "brackets", "// /*", "char"),
    # After annotations (@Test) and modifiers, not a fun interface, which is an interface; maybe with a receiver
    # (Map<K, V>.f) and a name in backquotes (`returns 200`).
    ("Kotlin", ".kt .kts", r"^\s*(?:(?:public|private|protected|internal|override|open|abstract|final|suspend|"
     r"inline|operator|infix|tailrec|external|actual|expect)\s+|@[\w.:]+(?:\((?:[^()]|\([^()]*\))*\))?\s*)*"
     r"fun\s+(?!interface\b)(?:<[^>]*>\s*)?(?:[\w.]+(?:<[^()=]*>)?\??\.)?(\w+|`[^`]+`)", "brackets", "// /*",
     "char"),
    # Swift's declaration modifiers, some with a word in brackets (private(set), nonisolated(unsafe)), and its
    # attributes (@MainActor, @available(...)).
    ("Swift", ".swift", r"^\s*(?:(?:(?:open|public|package|internal|fileprivate|private|static|class|override|final|"
     r"required|convenience|mutating|nonmutating|consuming|borrowing|__consuming|nonisolated|isolated|"
     r"distributed|dynamic|optional|prefix|postfix|infix|lazy|weak|unowned)(?:\(\w+\))?|"
     r"@\w+(?:\((?:[^()]|\([^()]*\))*\))?)\s+)*"
     r"(?:func\s+(\w+|`[^`]+`|[^\s\w(`]+(?=\s*[(<]))|(init)[?!]?\s*[(<]|(deinit)\b|(subscript)\s*[(<])",
     "brackets", "// /*", ""),
    ("Java", ".java", JAVA_SHAPES, "brackets", "// /*", "char"),
    ("C#", ".cs", CS_SHAPES, "brackets", "// /*", "char"),
    ("C", ".c .h", c_shapes("C"), "brackets", "// /*", "char"),
    ("C++", ".cpp .cc .cxx .hpp .hh", CPP_SHAPES, "brackets", "// /*", "char"),
]
BY_EXTENSION = dict((ext, lang) for lang in LANGUAGES for ext in lang[1].split())
OPEN, CLOSE = "([{", ")]}"
# The reference points in the catalogue's Measuring section (smells.md), in code lines: over the first is
# worth a closer look, over the second big. The first is the floor for the bands too: nothing at or below it
# is in one, however the codebase compares.
REFERENCE = {"file": (220, 440), "function": (45, 75)}
PERCENTS = (70, 80, 90)
BIG = set(["80th", "90th"] + [">%d" % strong for _, strong in REFERENCE.values()])
# An operator that an expression goes on after, at the end of a line (read from its last three characters),
# or before, at the start of the next (goes_on). Not a ++ or a --; and a *, /, %, > or ? only after a space,
# unlike a JSX tag's >, a regular expression's closing / or a nullable type's ? (as T?). At the start of a
# line, a > goes on as a comparison does, or closes a type's < left open, as in x as Array<...> split over
# lines.
GOES_ON = re.compile(r"(?:=>?|\|\||&&|\?\?|[:<]|(?<![+-])[+-]|\s[*/%>?])$")
GOES_ON_NEXT = re.compile(r"\s*(?:\|\||&&|\?\?|\?(?!\.)|:|\.(?!\.)|[+-](?![+-])|[|&*%>])")
# The words after which a / opens a regular expression, since only an expression can follow them; as whole
# words, not a member's name such as x.in.
REGEX_AFTER = re.compile(r"(?<![\w$.])(?:return|case|typeof|void|delete|throw|new|await|yield|in|of|do|else)$")
# A JavaScript regular expression: from / to /, past escapes and the / in a class such as [/].
REGEX = re.compile(r"/(?:\\.|\[(?:\\.|[^\]\\])*\]|[^/\\\[])+/")
# A Python statement that is only a string, as a docstring is: documentation, so not a code line.
DOCSTRING = re.compile(r"""\s*[rRuUbBfF]{0,2}("{3}|'{3}|"|')""")


# A character literal, its escape as long as it may be ('\u{1F600}', '\x7f', '\0'), where ' quotes one.
CHARACTER = re.compile(r"'(?:\\(?:u\{[0-9a-fA-F]{1,6}\}|x[0-9a-fA-F]{1,2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|"
                       r"[0-7]{1,3}|.)|[^\\'])'")
# Per language, strings with no escapes, which can hold quotes and run over lines: how one opens, and its
# closing text. C#'s verbatim @"..." (where "" is a quote), Rust's r"..." and r#"..."#, C++'s R"x(...)x",
# Swift's #"..."#.
RAW_STRING = {
    "C#": (re.compile(r'(?:\$+@|@\$*)"'), lambda opened: '"'),
    "Rust": (re.compile(r'b?r(#*)"'), lambda opened: '"' + opened.group(1)),
    "C++": (re.compile(r'(?:u8|[uUL])?R"([^()\\\s]{0,16})\('), lambda opened: ")" + opened.group(1) + '"'),
    "Swift": (re.compile(r'(#+)("""|")'), lambda opened: opened.group(2) + opened.group(1)),
}
# Per language, a preprocessor directive's line and its word, and whether it goes on after a \ at the end.
PREPROCESSED = {
    "C": (re.compile(r"\s*#\s*(\w*)"), True),
    "C++": (re.compile(r"\s*#\s*(\w*)"), True),
    "C#": (re.compile(r"\s*#\s*(if|elif|else|endif|region|endregion|define|undef|pragma|nullable|line|error|"
                      r"warning)\b"), False),
    "Swift": (re.compile(r"\s*#(if|elseif|else|endif)\b"), False),
}
BRACKETS_IN = re.compile(r"[()\[\]{}]")


def preprocessed(lines, code, began_inside, directive, continues):
    """The skeleton's lines with the preprocessor read: a directive's own brackets don't count, nor do those
    of a conditional's later branches (#elif, #else) when its first branch leaves brackets open, as when
    each branch opens a function's body its own way; those branches' lines are then set aside (began_inside),
    so no function is found twice. A first branch that's balanced keeps the others, as alternatives written
    in full. After #if 0 or #if false, the next branch counts instead. A bracket that doesn't count becomes
    an s, so its line stays a code line."""
    result, frames, going_on = [], [], False
    for i, line in enumerate(lines):
        found = directive.match(line) if going_on or not began_inside[i] else None
        if going_on or found:
            word = found.group(1) if found and not going_on else ""
            going_on = continues and line.rstrip().endswith("\\")
            if word in ("if", "ifdef", "ifndef"):
                zero = line.split(word, 1)[1].strip() in ("0", "false")
                frames.append({"skip": zero, "counting": not zero, "net": 0, "zero": zero})
            elif word in ("elif", "elseif", "else") and frames:
                frame = frames[-1]
                if frame["zero"]:
                    frame.update(zero=False, skip=False, counting=True, net=0)
                elif frame["counting"]:
                    frame.update(counting=False, skip=frame["net"] != 0)
            elif word == "endif" and frames:
                frames.pop()
            result.append(BRACKETS_IN.sub("s", code[i]))
        elif any(frame["skip"] for frame in frames):
            result.append(BRACKETS_IN.sub("s", code[i]))
            began_inside[i] = True
        else:
            net = sum(code[i].count(c) for c in OPEN) - sum(code[i].count(c) for c in CLOSE)
            for frame in frames:
                if frame["counting"]:
                    frame["net"] += net
            result.append(code[i])
    return result


def string_holes(language, quotes, quote, before):
    """What opens an interpolation's hole in a string that opens with quote, after the character before
    it; or None."""
    if quote == "`" and quotes == "regex":
        return "${"
    if quote in ('"', '"""'):
        if language == "Kotlin":
            return "${"
        if language == "Swift":
            return "\\("
        if language == "C#" and before == "$":
            return "{"
    return None


def skeleton(lines, comments, quotes, attributes=False, language=None):
    """Each line with its comments taken out and its strings' insides turned to "s", so brackets
    and code lines can be counted; and whether the line began inside a string or comment. With
    attributes, #[ opens an attribute, as in PHP 8, not a comment. The language adds its own strings
    (RAW_STRING) and, for C, C++, C# and Swift, its preprocessor (preprocessed)."""
    markers = comments.split()
    char_quote = quotes == "char"
    out, began_inside = [], []
    state = None  # Inside: a block comment ("*/"), or a string (its closing quote).
    raw = None  # Inside a string with no escapes: its closing text.
    # An interpolation's hole in a string is code, up to the bracket that matches its own, and can hold strings
    # of its own: JavaScript's template literal's ${...}, Kotlin's "${...}", Swift's "\(...)", C#'s $"{...}".
    # Per hole still open: how many of its brackets are open inside it, its brackets, and the string it's in.
    templates = []
    holes = None  # In a string with holes: what opens one (string_holes).
    opens_raw = RAW_STRING.get(language)
    for line in lines:
        began_inside.append(state is not None or bool(templates) or raw is not None)
        code = []
        i = 0
        while i < len(line):
            if raw is not None:
                if raw == '"' and language == "C#" and line.startswith('""', i):  # A verbatim string's quote.
                    code.append("ss")
                    i += 2
                elif line.startswith(raw, i):
                    code.append('"')
                    i, raw = i + len(raw), None
                else:
                    code.append("s")
                    i += 1
            elif state == "*/":
                end = line.find("*/", i)
                if end < 0:
                    break
                i, state = end + 2, None
            elif state:
                if holes == "{" and (line.startswith("{{", i) or line.startswith("}}", i)):
                    code.append("ss")  # C#'s brace written twice is a brace.
                    i += 2
                elif holes and line.startswith(holes, i):
                    code.append("s" * len(holes))  # The hole's own brackets aren't the code's.
                    templates.append([0, holes[-1], ")" if holes[-1] == "(" else "}", state, holes])
                    i, state, holes = i + len(holes), None, None
                elif line[i] == "\\":
                    i += 2
                elif line.startswith(state, i):
                    code.append(state)
                    i, state, holes = i + len(state), None, None
                    while language == "Kotlin" and line.startswith('"', i) and code[-1] == '"""':
                        i += 1  # Kotlin's raw string ends at the last """ of a run of quotes: """a""""
                else:
                    code.append("s")
                    i += 1
            elif "/*" in markers and line.startswith("/*", i):
                state = "*/"
                i += 2
            elif any(line.startswith(m, i) for m in markers if m != "/*") and not (
                    attributes and line.startswith("#[", i)):
                break
            elif opens_raw and opens_raw[0].match(line, i) and not re.match(r"[\w$@]", line[i - 1:i]):
                opened = opens_raw[0].match(line, i)
                raw = opens_raw[1](opened)
                code.append('"')
                i = opened.end()
            elif line.startswith('"""', i) or line.startswith("'''", i):
                state = line[i:i + 3]
                holes = string_holes(language, quotes, state, line[i - 1:i])
                code.append(state)
                i += 3
            elif line[i] == "/" and quotes == "regex" and REGEX.match(line, i) and regex_may_start(code, out):
                literal = REGEX.match(line, i).group(0)  # A regular expression, which can hold quotes and brackets.
                code.append("/" + "s" * (len(literal) - 2) + "/")
                i += len(literal)
            elif line[i] == "'" and char_quote:
                literal = CHARACTER.match(line[i:])  # A character, or else a Rust lifetime.
                code.append("s" if literal else " ")
                i += len(literal.group(0)) if literal else 1
            elif line[i] in "\"'`":
                state = line[i]
                holes = string_holes(language, quotes, state, line[i - 1:i])
                code.append(state)
                i += 1
            elif templates and line[i] == templates[-1][2] and not templates[-1][0]:  # A hole's end: back in
                code.append("s")  # its string.
                _, _, _, state, holes = templates.pop()
                i += 1
            elif templates and line[i] in templates[-1][1:3]:
                templates[-1][0] += 1 if line[i] == templates[-1][1] else -1
                code.append(line[i])
                i += 1
            else:
                code.append(line[i])
                i += 1
        if state in ('"', "'") and quotes != "spans" and not line.rstrip().endswith("\\") and not (
                language == "Rust" and state == '"'):
            state = holes = None  # Most languages end a one-quote string at the line's end; Rust's go on.
        out.append("".join(code))
    if language in PREPROCESSED:
        out = preprocessed(lines, out, began_inside, *PREPROCESSED[language])
    return out, began_inside


# Ruby's literals: a heredoc's opening (<<~ID, <<-ID, <<ID, the ID maybe quoted), a % literal (%w[...],
# %r{...}, %(...)), a global variable whose name is punctuation ($", $'), and an operator's name, as after def
# or in a symbol (:<<, :/, :[]).
RUBY_HEREDOC = re.compile(r"<<([~-])?(?:([\"'`])([^\"'`\n]+)\2|([A-Za-z_]\w*))")
RUBY_PERCENT = re.compile(r"%([qQwWiIrsx]?)([^\w\s])")
RUBY_GLOBAL = re.compile(r"\$(?:[!@&`'+~=/\\,;.<>_*$?:\"]|-\w|\d+)")
RUBY_OPERATOR = r"\[\]=?|<=>|===?|=~|!=|!~|<<|>>|<=|>=|\*\*|[+\-~!]@?|[*/%<>^&|`]"
RUBY_DEF_NAME = re.compile(r"(?<![\w$@.:])def\s+(?:(?:self|@@?\w+|[A-Za-z_][\w:]*)\s*\.\s*)?$")
RUBY_SYMBOL_OPERATOR = re.compile(r":(?:%s)" % RUBY_OPERATOR)
# The words after which a value can start, so that a /, a % or a ? opens a literal.
RUBY_VALUE_AFTER = re.compile(r"(?<![\w$@.:])(?:if|unless|elsif|while|until|and|or|not|when|in|return|then|do|"
                              r"else|case|yield|raise|next|break|puts|print|p|begin)$")
RUBY_PAIRS = {"(": ")", "[": "]", "{": "}", "<": ">"}


def ruby_value_may_start(line, i):
    """Whether a value can start at line[i] in Ruby, so that a /, % or ? there opens a literal rather than
    being an operator: at the start of the line, after an operator, an opening bracket, a comma or a word
    such as if or return; or after a method's name and a space, as in split /,/, when no space follows."""
    before = line[:i].rstrip()
    if not before:
        return True
    if before[-1] in "(,=!&|?:;{[+-*/%<>~^" or RUBY_VALUE_AFTER.search(before):
        return True
    after = line[i + 1:i + 2]
    return (before[-1].isalnum() or before[-1] in "_?!") and i > 0 and line[i - 1].isspace() and \
        bool(after) and not after.isspace() and after != "="


def ruby_skeleton(lines):
    """skeleton() for Ruby, whose literals need more than quotes: regular expressions (/.../, %r{...}), %
    literals (%w[...], %q(...)), heredocs, whose text follows on the lines after the one that opens them,
    #{...} inside strings, characters such as ?", globals such as $", =begin ... =end comments and
    __END__. Each literal's text becomes s, and its delimiters "."""
    out, began_inside = [], []
    stack = []  # What's open: ["literal", closer, opener, nesting, interpolates] or ["code", braces] in #{...}.
    waiting, heredocs = [], []  # Heredocs opened on this line, and those whose text the next lines are.
    comment = ended = False
    for line in lines:
        if ended or comment:
            out.append("")
            began_inside.append(True)
            if comment and re.match(r"=end\b", line):
                comment = False
            continue
        if heredocs:
            out.append("s" * len(line.rstrip()) if line.strip() else "")
            began_inside.append(True)
            closer, indented = heredocs[0]
            if (line.strip() if indented else line.rstrip()) == closer:
                heredocs.pop(0)
            continue
        if not stack and re.match(r"=begin\b", line):
            comment = True
            out.append("")
            began_inside.append(False)
            continue
        if not stack and line.rstrip() == "__END__":
            ended = True
            out.append("")
            began_inside.append(False)
            continue
        began_inside.append(bool(stack))
        code = []
        i, n = 0, len(line)
        while i < n:
            c = line[i]
            top = stack[-1] if stack else None
            if top is not None and top[0] == "literal":
                _, closer, opener, nesting, interpolates = top
                if c == "\\":
                    code.append("s" * len(line[i:i + 2]))
                    i += 2
                elif interpolates and line.startswith("#{", i):
                    code.append("ss")
                    stack.append(["code", 0])
                    i += 2
                elif opener and c == opener:
                    top[3] += 1
                    code.append("s")
                    i += 1
                elif c == closer and nesting:
                    top[3] -= 1
                    code.append("s")
                    i += 1
                elif c == closer:
                    stack.pop()
                    code.append('"')
                    i += 1
                else:
                    code.append("s")
                    i += 1
                continue
            nested = top is not None  # In a #{...}: lexed as code, written as string.
            mark = (lambda text: "s" * len(text)) if nested else (lambda text: text)
            before = line[:i]
            if c == "#":
                break  # A comment, to the end of the line.
            if RUBY_DEF_NAME.search(before):
                name = re.match(RUBY_OPERATOR, line[i:])
                if name and c in "[]<=>!~+-*/%^&|`":
                    code.append(mark(name.group(0)))
                    i += name.end()
                    continue
            symbol = RUBY_SYMBOL_OPERATOR.match(line, i) if c == ":" and not before.endswith(":") else None
            if symbol and not line.startswith("::", i):
                code.append(mark(symbol.group(0)))
                i = symbol.end()
                continue
            if c in "\"'`":
                stack.append(["literal", c, None, 0, c != "'"])
                code.append('"')
                i += 1
                continue
            if c == "$":
                variable = RUBY_GLOBAL.match(line, i)
                if variable:
                    code.append(mark("$v" + "v" * (len(variable.group(0)) - 2)))
                    i = variable.end()
                    continue
            if c == "<" and line.startswith("<<", i):
                heredoc = RUBY_HEREDOC.match(line, i)
                bare = heredoc and not heredoc.group(1) and not heredoc.group(2)
                if heredoc and not (bare and (not heredoc.group(4)[0].isupper() or not ruby_value_may_start(line, i))):
                    waiting.append((heredoc.group(3) or heredoc.group(4), bool(heredoc.group(1))))
                    code.append(mark('""'))
                    i = heredoc.end()
                    continue
            if c == "%" and ruby_value_may_start(line, i):
                literal = RUBY_PERCENT.match(line, i)
                if literal:
                    kind, delimiter = literal.groups()
                    stack.append(["literal", RUBY_PAIRS.get(delimiter, delimiter),
                                  delimiter if delimiter in RUBY_PAIRS else None, 0, kind in "QWIrx"])
                    code.append('"')
                    i = literal.end()
                    continue
            if c == "/" and ruby_value_may_start(line, i):
                stack.append(["literal", "/", None, 0, True])
                code.append('"')
                i += 1
                continue
            if c == "?" and (not before.rstrip() or before.rstrip()[-1] in "(,=[{" or
                             RUBY_VALUE_AFTER.search(before.rstrip())):
                character = re.match(r"\?(?:\\.|[^\s\w])(?!\w)", line[i:])
                if character:
                    code.append(mark("s" * len(character.group(0))))
                    i += character.end()
                    continue
            if nested and c == "{":
                top[1] += 1
            elif nested and c == "}":
                if top[1] == 0:
                    stack.pop()
                    code.append("s")
                    i += 1
                    continue
                top[1] -= 1
            code.append(mark(c))
            i += 1
        if not began_inside[-1] and re.match(r"\s*<<[~-]?[\"'`A-Za-z_]", line) and waiting:
            began_inside[-1] = True  # A heredoc's opening that starts its line, at any indentation, goes on.
        heredocs.extend(waiting)
        waiting = []
        out.append("".join(code))
    return out, began_inside


def regex_may_start(code, out):
    """Whether a / in JavaScript, after the line's code so far (code, as pieces) or else the last line's,
    opens a regular expression rather than dividing: it comes after an operator, an opening bracket or an
    arrow, or after a word that only an expression can follow, such as return or typeof. Only the last
    few characters are read, so a long line stays quick."""
    before = ""
    for piece in reversed(code):
        before = piece + before
        if len(before.strip()) > 8:
            break
    before = before.rstrip() or next((line.rstrip() for line in reversed(out) if line.strip()), "")
    return not before or before[-1] in "(,=:[!&|?{};" or before.endswith("=>") or bool(REGEX_AFTER.search(before))


def indent_of(line):
    """The width of a line's indentation, a tab counting four."""
    line = line.expandtabs(4)
    return len(line) - len(line.lstrip())


def indent_unit(lines, code, starts):
    """The file's step of indentation: the commonest increase after a line that opens a block
    (ending in : or {), or failing that after any code line."""
    after_block, after_any = Counter(), Counter()
    last, opens = 0, False
    for line, skeleton_line, start in zip(lines, code, starts):
        if not skeleton_line.strip() or start:
            continue
        step = indent_of(line) - last
        if 0 < step <= 8:
            (after_block if opens else after_any)[step] += 1
        last, opens = indent_of(line), skeleton_line.rstrip().endswith((":", "{"))
    steps = after_block or after_any
    return steps.most_common(1)[0][0] if steps else 4


def signature_end(code, start):
    """The line where the definition at start closes the brackets it opens: its own, or the last of a
    signature split over lines. If they don't close within 50 lines, its own."""
    depth = 0
    for i in range(start, min(len(code), start + 50)):
        depth += sum(code[i].count(c) for c in OPEN) - sum(code[i].count(c) for c in CLOSE)
        if depth <= 0:
            return i
    return start


def body_by_indent(lines, code, inside, open_brackets, start, with_end):
    """The last line of the function defined at start, by indentation. Its body starts after its
    signature, whose last line a formatter puts at the definition's own indentation, as in ) -> int:.
    A line inside a string, or inside brackets opened after the definition began, continues another, so
    its indentation says nothing; and the brackets the definition is in, as in Class.new { def ... },
    end it when they close."""
    width = indent_of(lines[start])
    last = signature_end(code, start)
    for i in range(last + 1, len(lines)):
        if not code[i].strip():
            continue
        if inside[i] or open_brackets[i] > open_brackets[start]:
            last = i
            continue
        if open_brackets[i] < open_brackets[start]:
            break
        if indent_of(lines[i]) <= width:
            # Its end is at its own indentation: one further out ends the class around a method that has none,
            # written on one line. So are a rescue, an else and an ensure of the whole method's.
            word = re.match(r"(end|rescue|ensure|else)\b", code[i].strip()) if with_end else None
            if word and indent_of(lines[i]) == width:
                last = i
                if word.group(1) != "end":
                    continue
            break
        last = i
    return last


# How a signature goes on past the end of a line, as a return type or a constraint split over lines, at the
# end of that line or at the start of the next (past any preprocessor's lines); or the body's { on a line of
# its own, or a macro in capitals that annotates it (EXCLUSIVE_LOCKS_REQUIRED(mu), SPDLOG_NOEXCEPT), indented
# further than the definition: one at its indentation is a definition of its own, as a macro that makes one.
SIGNATURE_GOES_ON = re.compile(r"(?:[|&:.,<(\[{=]|->|=>|\b(?:where|extends|implements|requires))$")
SIGNATURE_NEXT = re.compile(r"\s*(?:[{:=,.?|&>)\]]|->|=>|(?:where|throws|rethrows|async|noexcept|requires|"
                            r"extends|implements|try)\b)")
SIGNATURE_MACRO = re.compile(r"\s*[A-Z][A-Z0-9_]{2,}\b")


def body_by_brackets(code, inside, start, column=0, initialized=False):
    """The last line of a function's body, by matching brackets from code[start][column] on, where its
    definition starts or, if it's known, its body; None if no body follows, as for a declaration, or if
    its brackets never close. A block ends where its brace closes; an expression, such as an arrow
    function's, at the end of a line outside brackets that it doesn't go on from (goes_on). With
    initialized, as in C++, a constructor's initializers after its : can be braces, as in : size_{n} {,
    which open right after a name or a >, unlike its body's."""
    depth = carried = 0
    initializers = False  # Past a constructor's : in C++, so a { after a name is an initializer's.
    expression = False
    arrow = False  # An arrow ended the last line, so this one says which kind of body it is.
    signed = False  # A parameter list has closed, so a body or the rest of the signature comes next.
    brackets = brackets_of(code)
    closes = brackets["closes"]
    for i in range(start, len(code)):
        offset = column if i == start else 0
        line = code[i][offset:]
        if arrow and line.strip():
            expression, arrow = not line.strip().startswith("{"), False
        scan = line
        if expression:  # An expression from this line's start: only its brackets matter.
            depth += brackets["net"][i]
            scan = ""
        for j, c in enumerate(scan):
            if not expression and depth == 0:
                if c == "{" and not (initializers and re.match(r"[\w>]", line[j - 1:j])):  # A block: it ends
                    end = closes.get((i, j + offset))  # where its brace closes.
                    return end[0] if end else None
                elif c == ":" and initialized and signed and ":" not in (line[j - 1:j], line[j + 1:j + 2]):
                    initializers = True
                elif line.startswith("=>", j):
                    rest = line[j + 2:].strip()
                    expression, arrow = bool(rest) and not rest.startswith("{"), not rest
                elif c == "=" and ")" in line[:j] and line[j - 1:j] not in "=!<>" and \
                        (line[j + 1:j + 2] or " ") not in "=>":
                    expression = True  # Kotlin's fun f() = ..., C++'s = default.
                elif c == ";":
                    return None
            if c in OPEN:
                depth += 1
            elif c in CLOSE:
                depth -= 1
                if depth < 0 and not expression:  # The block around it closed first: a declaration, as a protocol's.
                    return None
                signed = signed or (depth == 0 and c == ")")
        if signed and not expression and not arrow and depth == 0 and not column and line.strip() and \
                not line.lstrip().startswith("#") and not SIGNATURE_GOES_ON.search(line.rstrip()[-12:]):
            # A body's { follows its signature on the same line or the next, unless the next goes on with it
            # (where, throws, ->, :...); else it's a declaration with none, as an interface's method.
            following = next((n for n in code[i + 1:i + 20] if n.strip() and not n.lstrip().startswith("#")), "")
            deeper = len(following) - len(following.lstrip()) > len(code[start]) - len(code[start].lstrip())
            if not SIGNATURE_NEXT.match(following) and not (deeper and SIGNATURE_MACRO.match(following)):
                return None
        if expression and depth <= 0 and line.strip():
            if not goes_on(code, inside, i):
                return i
            # Fifty lines in a row that only go on by their operators, outside brackets, aren't one
            # expression: stop, so a file of such lines isn't read again for each of them.
            carried += 1
            if carried > 50:
                return i
        elif depth > 0:
            carried = 0
        if not expression and i - start > 30:
            return None
    return None


def goes_on(code, inside, i):
    """Whether an expression goes on after line i, which ends outside any brackets: the line ends with an
    operator, as in Kotlin's fun f() = and an arrow function that returns another; or inside a string, such
    as a template literal; or the next line starts with an operator, as a ternary or a chain of calls split
    over lines does."""
    if GOES_ON.search(code[i].rstrip()[-3:]) or (i + 1 < len(inside) and inside[i + 1]):
        return True
    following = next((line for line in code[i + 1:i + 20] if line.strip()), "")
    return bool(GOES_ON_NEXT.match(following))


def docstrings(code, inside, continued):
    """The lines of Python's statements that are only a string, as a docstring is: one that starts a
    line outside any brackets, and has nothing after its closing quote."""
    found = []
    for i, line in enumerate(code):
        match = None if inside[i] or continued[i] else DOCSTRING.match(line)
        if not match or (i and code[i - 1].rstrip().endswith("\\")):
            continue
        # The string's insides are s by now, so the first quote of its kind left closes it.
        quote, end, rest = match.group(1), i, line[match.end():]
        while quote not in rest and end + 1 < len(code) and inside[end + 1]:
            end += 1
            rest = code[end]
        if quote in rest and not rest.split(quote, 1)[1].strip():
            found.extend(range(i, end + 1))
    return found


TYPE_ARGUMENTS_IN = re.compile(r"(?<=\w)" + TYPE_ARGUMENTS[3:-2])


def by_pattern(pattern, listed=False):
    """A language's way of finding its definitions from a regular expression: the name is whichever
    group matched, and the body is looked for from the start of the line. With listed, as in the C family,
    a line after one that ends with a , or with a : after a ) goes on with a list, as a constructor's
    initializers do (: cache_(...),  db_(nullptr),), so it holds no definition; one after public: may."""
    pattern = re.compile(pattern)

    def find(code, i):
        match = pattern.match(code[i])
        name = next((g for g in match.groups() if g), None) if match else None
        if not name:
            return None
        if listed:
            previous = next((code[k].rstrip() for k in range(i - 1, max(-1, i - 4), -1) if code[k].strip()), "")
            before_colon = previous[:-1].rstrip() if previous.endswith(":") else None
            if previous.endswith(",") or before_colon == "" or (before_colon or "").endswith(")"):
                return None
        before = code[i][:next(match.start(n) for n in range(1, len(match.groups()) + 1) if match.group(n))]
        if before.count("[") > before.count("]"):  # Inside an attribute, as C#'s [assembly: Foo()].
            return None
        if re.match(r"\w", name) and not name.startswith("operator"):
            name = TYPE_ARGUMENTS_IN.sub("", name)  # Get<T> is Get, SkipList<Key, Cmp>::Insert SkipList::Insert.
        return name, (i, 0)
    return find


def c_function(pattern, language):
    """C's and C++'s way of finding definitions: by their shapes, and also a name alone at the margin whose
    parameters open the next line, as dtoa.c writes them (jvp_strtod, then (struct ...) below)."""
    find = by_pattern(pattern, listed=True)
    alone = re.compile(r"^" + not_a_name(language) + r"((?!\d)\w+)\s*$")

    def find_c(code, i):
        found = find(code, i)
        name = alone.match(code[i]) if not found else None
        if name:
            following = next((k for k in range(i + 1, min(len(code), i + 3)) if code[k].strip()), None)
            if following is not None and code[following].lstrip().startswith("("):
                return name.group(1), (i, 0)
        return found
    return find_c


FIND = dict((lang[0], lang[2] if callable(lang[2]) else by_pattern(lang[2])) for lang in LANGUAGES)
FIND["C"], FIND["C++"] = c_function(c_shapes("C"), "C"), c_function(CPP_SHAPES, "C++")
FIND["Java"], FIND["C#"] = [by_pattern(dict((lang[0], lang[2]) for lang in LANGUAGES)[name], listed=True)
                            for name in ("Java", "C#")]


def functions(path, text):
    """The file's code lines, its functions as (name, first line, last line, code lines, deepest), and its language."""
    language = BY_EXTENSION.get(os.path.splitext(path)[1].lower())
    lines = text.split("\n")
    comments = language[4] if language else "# //"
    if language and language[0] == "Ruby":
        code, inside = ruby_skeleton(lines)
    else:
        code, inside = skeleton(lines, comments, language[5] if language else "", language and language[0] == "PHP",
                                language and language[0])
        if language and language[0] == "C" and path.lower().endswith(".h") and CPP_IN_HEADER.search("\n".join(code)):
            language = BY_EXTENSION[".hpp"]
            code, inside = skeleton(lines, comments, language[5], False, language[0])
    counted = [bool(c.strip()) for c in code]
    if not language:
        return sum(counted), None, None
    name, _, _, ending, _, _ = language
    find = FIND[name]
    # A line that starts inside open brackets continues the one before, so it says nothing about
    # nesting. Braces are brackets too where indentation makes the blocks.
    opening = "([{" if ending != "brackets" else "(["
    closing = "".join(CLOSE[OPEN.index(c)] for c in opening)
    continued, open_brackets, depth = [], [], 0
    for line in code:
        continued.append(depth > 0)
        open_brackets.append(depth)
        depth = max(0, depth + sum(line.count(c) for c in opening) - sum(line.count(c) for c in closing))
    if name == "Python":  # Docstrings are documentation, as comments are.
        for i in docstrings(code, inside, continued):
            counted[i] = False
    skip = [a or b for a, b in zip(inside, continued)]
    unit = indent_unit(lines, code, skip)
    found = []
    for start in range(len(code)):
        defined = find(code, start) if not inside[start] else None
        if not defined:
            continue
        if defined[0].startswith("`"):  # A name in backquotes, whose text the skeleton has as a string's.
            written = re.search(r"\bfunc?\s+[^`]*(`[^`]+`)", lines[start])
            defined = (written.group(1) if written else defined[0]), defined[1]
        if ending == "brackets":
            last = body_by_brackets(code, inside, *defined[1], initialized=name == "C++")
            if last is None:
                continue
        else:
            last = body_by_indent(lines, code, inside, open_brackets, start, ending == "end")
        base = indent_of(lines[start])
        depths = [(indent_of(lines[i]) - base) // unit - 1 for i in range(start + 1, last + 1)
                  if counted[i] and not inside[i] and not continued[i]]
        found.append((defined[0], start + 1, last + 1, sum(counted[start:last + 1]), max([0] + depths)))
    return sum(counted), found, name


def band(length, cuts, kind):
    """The band a thing of this length is in, or None. Against the percentiles (cuts), the highest of the
    70th, 80th and 90th it reaches past kind's floor; the thing a percentile falls in reaches it, since
    some of its lines are past it. With no cuts, as when the percentiles lean on one thing, the highest of
    the reference points it's over, written >45 or >75 for a function."""
    closer, strong = REFERENCE[kind]
    if length <= closer:
        return None
    if cuts is None:
        return ">%d" % (strong if length > strong else closer)
    reached = [percent for percent, cut in zip(PERCENTS, cuts) if cut and length >= cut]
    return "%dth" % reached[-1] if reached else None


def leaning(things, kind):
    """The thing the percentiles lean on, if any, as (its name, its share of the lines in percent): one past
    kind's floor that holds a tenth of the lines and is half as long again as any other, so that it's its
    own 90th and every cut falls in it. A few things of one length lean on none of them."""
    ranked = sorted(things, reverse=True)
    total = sum(n for n, _ in things)
    if len(ranked) > 1 and ranked[0][0] > REFERENCE[kind][0] and ranked[0][0] * 10 >= total \
            and ranked[0][0] * 2 >= ranked[1][0] * 3:
        return ranked[0][1], 100 * ranked[0][0] // total
    return None


def weighted(lengths, percents=PERCENTS):
    """The lengths that each percent of all the lines are in things no longer than (Alves et al.)."""
    lengths = sorted(lengths)
    total = sum(lengths)
    out = []
    for percent in percents:
        running = 0
        for n in lengths:
            running += n
            if running >= total * percent / 100.0:
                out.append(n)
                break
        else:
            out.append(0)
    return out


def main():
    scoping.safe_output()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__.split("\n\n", 1)[1])
    parser.add_argument("scope", nargs="*", help="directories or globs to measure (default: everything)")
    parser.add_argument("-C", dest="repo", default=".", help="the repo (default: the current directory)")
    parser.add_argument("--ignore", action="append", default=[], metavar="GLOB",
                        help="more file globs to leave out (added to the defaults: %s)"
                             % ", ".join(scoping.DEFAULT_IGNORE))
    parser.add_argument("--test", action="append", default=[], metavar="GLOB",
                        help="more globs naming test files, matched with case against the name or the path "
                             "(added to the defaults: %s, and folders named %s)"
                             % (", ".join(scoping.TEST_NAMES), ", ".join(scoping.TEST_FOLDERS)))
    parser.add_argument("--not-test", action="append", default=[], metavar="GLOB",
                        help="globs naming files that only look like tests, matched as --test's are, such as "
                             "'app/ABTest.php' or 'docs/spec/*': they're measured like the rest")
    parser.add_argument("--keep-tests", action="store_true", help="measure test files like the rest")
    parser.add_argument("--top", type=scoping.count(0), default=25, help="files to print (default 25)")
    parser.add_argument("--show", action="append", default=[], metavar="FILE",
                        help="list this file's functions, with the first and last line of each for git log -L, "
                             "instead of the table of files")
    args = parser.parse_args()

    repo = scoping.toplevel(args.repo)
    tracked = scoping.tracked_files(repo)
    if not tracked:
        sys.exit("%s tracks no files yet, so there's nothing to measure." % os.path.basename(repo))
    args.scope = scoping.resolve(args.repo, repo, args.scope, tracked)
    patterns = scoping.DEFAULT_IGNORE + args.ignore
    shows = [scoping.show_path(args.repo, repo, p, tracked) for p in args.show]
    in_scope = [p for p in tracked if scoping.in_scope(p, args.scope) and not scoping.ignored(p, patterns)]
    paths, own = scoping.leave_own_out(in_scope, tracked, args.scope)
    tests = set() if args.keep_tests else set(p for p in paths if scoping.is_test(p, args.test, args.not_test))
    doubts = scoping.doubtful_tests(tests, paths, args.test)
    paths = [p for p in paths if p not in tests]

    measured, failed, unreadable = {}, [], []
    for path in sorted(set(paths + shows)):
        full = os.path.join(repo, path)
        if not os.path.isfile(full):
            continue
        try:
            data = open(full, "rb").read()
        except OSError:
            unreadable.append(path)
            continue
        if b"\0" in data[:8000]:  # Binary, by git's own test.
            continue
        text = data.decode("utf-8", errors="replace")
        try:
            measured[path] = functions(path, text)
        except Exception:
            # The last line of defence: one file this doesn't foresee never stops a run. It's measured as its
            # non-blank lines, and the output names it, so the bug shows and can be reported.
            measured[path] = (sum(1 for line in text.split("\n") if line.strip()), None, None)
            failed.append(path)
    in_paths = set(paths)

    by_language = defaultdict(lambda: ([], []))  # Per language, its files' lengths and its functions'.
    no_rule = Counter()
    for path, (lines, found, language) in measured.items():
        if path not in in_paths:
            continue
        if language is None:
            if path not in failed:
                no_rule[os.path.splitext(path)[1] or os.path.basename(path)] += 1
            continue
        files, funcs = by_language[language]
        files.append((lines, path))
        funcs.extend((f[3], "%s:%d %s" % (path, f[1], f[0])) for f in found)
    # Per language, the percentiles of its files' lengths and its functions'; and the cuts the bands use,
    # which are None where the percentiles lean on one file or function, so the reference points judge.
    cuts, judged, notes = {}, {}, defaultdict(list)
    for language, (files, funcs) in by_language.items():
        cuts[language] = (weighted([n for n, _ in files]), weighted([n for n, _ in funcs]))
        judged[language] = []
        for kind, things, percentiles in (("file", files, cuts[language][0]), ("function", funcs, cuts[language][1])):
            lean = leaning(things, kind)
            judged[language].append(None if lean else percentiles)
            if lean:
                closer, strong = REFERENCE[kind]
                notes[language].append(
                    "%s %ss: %s holds %d%% of the lines and is half as long again as any other, so the percentiles "
                    "lean on it. These are put in bands by the catalogue's reference points instead: >%d is over "
                    "%d code lines, worth a closer look; >%d is over %d, big."
                    % ((language, kind) + lean + (closer, closer, strong, strong)))

    print("%s, scope: %s" % (os.path.basename(repo), " ".join(args.scope) or "(everything)"))
    print("Lines are code lines: blank lines, lines that are only a comment and Python's docstrings are left out.")
    print("Weighted by lines: 90% of the code is in files, or functions, no longer than the 90th.")
    print("Bands: a file or function at least as long as a percentile, and over the floor of %d lines for a file "
          "and %d for a function, is in its band. The 80th and 90th are big; the 70th, worth a closer look."
          % (REFERENCE["file"][0], REFERENCE["function"][0]))
    if not args.keep_tests:
        print("Test files: %s." % ("%d set aside from the percentiles and the table" % len(tests)
                                   if tests else "none in the scope"))
    if doubts:
        print("Set aside as tests, but maybe not: %s%s. If one isn't a test, --not-test GLOB measures it." % (
            "; ".join("%s (%s)" % d for d in doubts[:5]), "; and %d more" % (len(doubts) - 5)
            if len(doubts) > 5 else ""))
    if own:
        print("This skill's own files, in %s, are left out; a scope naming that folder measures them."
              % " and ".join(f + "/" for f in own))
    print()
    print("%-11s %6s %6s   %-17s   %-17s" % ("", "files", "funcs", "   file lines", " function lines"))
    print("%-11s %6s %6s   %5s %5s %5s   %5s %5s %5s" % ("language", "", "", "70th", "80th", "90th",
                                                         "70th", "80th", "90th"))
    for language, (files, funcs) in sorted(by_language.items(), key=lambda kv: -sum(n for n, _ in kv[1][0])):
        print("%-11s %6d %6d   %5d %5d %5d   %5d %5d %5d" % tuple(
            [language, len(files), len(funcs)] + cuts[language][0] + cuts[language][1]))
    for language in sorted(by_language, key=lambda name: -sum(n for n, _ in by_language[name][0])):
        for note in notes[language]:
            print(note)
    if no_rule:
        print("Lines only, with no rule to find functions: %d file%s (%s)." % (
            sum(no_rule.values()), "" if sum(no_rule.values()) == 1 else "s",
            ", ".join("%s %d" % kv for kv in no_rule.most_common(8))))
    if failed:
        print("Finding the functions failed in %s, so %s measured as non-blank lines only, out of the percentiles: "
              "%s. That's a bug in measure.py, and the %s would help fix it." % (
                  "1 file" if len(failed) == 1 else "%d files" % len(failed),
                  "it's" if len(failed) == 1 else "they're", ", ".join(failed),
                  "file" if len(failed) == 1 else "files"))
    if unreadable:
        print("Couldn't read %s, so %s left out: %s." % (
            "1 file" if len(unreadable) == 1 else "%d files" % len(unreadable),
            "it's" if len(unreadable) == 1 else "they're", ", ".join(unreadable)))
    print()

    def file_band(language, lines):
        return band(lines, judged[language][0], "file") if language in judged else None

    def function_band(language, length):
        return band(length, judged[language][1], "function") if language in judged else None

    if shows:
        for path in shows:
            if path in unreadable:
                print("%s: couldn't read it.\n" % path)
                continue
            if path not in measured:
                print("%s: not a text file in the working tree.\n" % path)
                continue
            lines, found, language = measured[path]
            if path in failed:
                print("%s: %d non-blank lines. Finding its functions failed, so it's measured as lines only; "
                      "that's a bug in measure.py, and this file would help fix it.\n" % (path, lines))
                continue
            if language is None:
                print("%s: %d code lines; no rule to find functions in this language.\n" % (path, lines))
                continue
            leans = language in judged and judged[language][1] is None
            print("%s: %s, %d code lines, band %s, %d functions (%s)" % (
                path, language, lines, file_band(language, lines) or "-", len(found),
                "%s functions: 70th %d, 80th %d, 90th %d lines%s" % (
                    (language,) + tuple(cuts[language][1]) + (
                        "; they lean on one function, so bands are by the reference points" if leans else "",))
                if language in cuts else "no %s file in the scope, so no percentiles to compare with" % language))
            # The first and last lines, as git log -L FIRST,LAST:FILE takes them.
            spans = ["%d-%d" % (f[1], f[2]) for f in found]
            width = max([len("first-last")] + [len(s) for s in spans])
            print("%*s %6s %8s %5s  function" % (width, "first-last", "lines", "deepest", "band"))
            for span, (name, first, last, length, deepest) in zip(spans, found):
                print("%*s %6d %8d %5s  %s" % (width, span, length, deepest,
                                               function_band(language, length) or "-", name))
            print()
        return

    rows = sorted(((p,) + m for p, m in measured.items() if p in in_paths), key=lambda r: (-r[1], r[0]))
    print("%6s %5s %6s %8s %5s %8s  file (its longest function)" % ("lines", "band", "funcs", "longest", "long",
                                                                    "deepest"))
    for path, lines, found, language in rows[:args.top]:
        if language is None:
            print("%6d %5s %6s %8s %5s %8s  %s (lines only)" % (lines, "-", "-", "-", "-", "-", path))
            continue
        longest = max(found, key=lambda f: f[3]) if found else None
        print("%6d %5s %6d %8s %5d %8d  %s%s" % (
            lines, file_band(language, lines) or "-", len(found), longest[3] if longest else "-",
            sum(1 for f in found if function_band(language, f[3]) in BIG), max([0] + [f[4] for f in found]),
            path, " (%s:%d)" % (longest[0], longest[1]) if longest else ""))
    if len(rows) > args.top:
        print("  ... %d more files" % (len(rows) - args.top))


if __name__ == "__main__":
    main()
