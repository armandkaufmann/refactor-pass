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
fun, function, and Swift's init, deinit and subscript); in JavaScript and
TypeScript also as methods, and as arrow functions or function expressions
that are given a name, assigned to a member (named by its last name: send
for res.send = function ..., exports for module.exports = ...) or exported
as the default (named default); and for C, C++, Java and C#, by their
shape: a type, a name, parentheses, then a body. A signature may run over
several lines. A function runs to the end of its body, found by indentation
(Python, GDScript, Ruby) or by matching brackets (the rest). Files in other
languages get lines only, and the output says which.

It points at code to read; it doesn't judge it. What it gets wrong:
  - a nested function counts in its own length and in its parent's;
  - anonymous functions and lambdas aren't functions of their own: their
    lines count in the function around them, or in none at the top level;
  - a function that doesn't start a line, such as a method in an object
    literal written on one line, isn't found;
  - shapes can catch a macro, and in TypeScript a member typed as a
    function, in a type written after an = (as a generic's default), counts
    as a function;
  - a brace or a quote in a heredoc, or in a JavaScript regular expression
    that follows a closing bracket or a name (not after an operator, an arrow
    or a word such as return or typeof), can put a function's end in the
    wrong place or lose the function;
  - a line inside a multi-line string or a block comment's text can count
    as code or not, depending on how it starts;
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
            r"sealed|async|extern|inline|unsafe|partial|new|const|constexpr|explicit|friend|default|open)\s+)*"
NOT_A_TYPE = r"(?!(?:return|if|for|foreach|while|switch|catch|else|do|new|throw|case|delete|await|using|lock|goto|" \
             r"sizeof|typeof|nameof|yield|import|package|namespace)\b)"
# A type is words and the punctuation of generics, arrays and pointers, or a tuple such as C#'s (int, string).
# A line that starts with a : (not C++'s ::) or a , goes on from the one before, as a constructor's initializers
# do, or C#'s : base(...).
C_HEAD = (r"^\s*(?!:(?!:)|,)" + NOT_A_TYPE + MODIFIERS + r"(?:(?:[\w<>\[\],.?*&:]+|\([\w<>\[\],.?\s]+\))\s+)+"
          r"[*&]*([A-Za-z_~][\w~]*(?:::~?\w+)*)\s*\(")
C_SHAPE = C_HEAD + r"[^;]*$"
# C# also writes a method's body as an expression after =>, on its own line with its ;.
EXPRESSION_BODIED = r"|" + C_HEAD + r"[^;]*\)\s*=>"
# Java and C# also write a constructor with no modifier, so with nothing before its name.
CONSTRUCTOR = r"|^\s*([A-Z]\w*)\s*\([^;]*$"
# C and C++ also put the type on the line above, with the name at the margin.
C_SHAPES = C_SHAPE + r"|^" + NOT_A_TYPE + r"([A-Za-z_][\w~]*(?:::~?\w+)*)\s*\([^;]*$"

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
    ("GDScript", ".gd", r"^\s*(?:static\s+)?func\s+(\w+)", "indent", "#", ""),
    ("Ruby", ".rb", r"^\s*def\s+(?:self\.)?([\w?!=]+)", "end", "#", "spans"),
    ("JavaScript", ".js .jsx .mjs .cjs", js_function, "brackets", "// /*", "regex"),
    ("TypeScript", ".ts .tsx .mts .cts", js_function, "brackets", "// /*", "regex"),
    ("Vue", ".vue .svelte", js_function, "brackets", "// /*", "regex"),
    ("PHP", ".php", r"^\s*(?:(?:abstract|final|public|private|protected|static)\s+)*function\s+&?\s*(\w+)",
     "brackets", "// /* #", "spans"),
    ("Go", ".go", r"^func\s+(?:\([^)]*\)\s*)?(\w+)", "brackets", "// /*", "char"),
    ("Rust", ".rs", r"^\s*(?:pub(?:\([\w:]+\))?\s+)?(?:(?:const|async|unsafe|extern\s+\"\w+\")\s+)*fn\s+(\w+)",
     "brackets", "// /*", "char"),
    ("Kotlin", ".kt .kts", r"^\s*(?:(?:public|private|protected|internal|override|open|abstract|final|suspend|"
     r"inline|operator|infix|tailrec|external)\s+)*fun\s+(?:<[^>]*>\s*)?(?:[\w.]+\.)?(\w+)", "brackets", "// /*",
     "char"),
    ("Swift", ".swift", r"^\s*(?:(?:public|private|fileprivate|internal|open|static|class|override|final|mutating|"
     r"nonmutating|convenience|required|nonisolated|dynamic|@\w+(?:\([^()]*\))?)\s+)*"
     r"(?:func\s+(\w+)|(init)[?!]?\s*[(<]|(deinit)\b|(subscript)\s*[(<])", "brackets", "// /*", ""),
    ("Java", ".java", C_SHAPE + CONSTRUCTOR, "brackets", "// /*", "char"),
    ("C#", ".cs", C_SHAPE + CONSTRUCTOR + EXPRESSION_BODIED, "brackets", "// /*", "char"),
    ("C", ".c .h", C_SHAPES, "brackets", "// /*", "char"),
    ("C++", ".cpp .cc .cxx .hpp .hh", C_SHAPES, "brackets", "// /*", "char"),
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
# or before, at the start of the next (goes_on). Not a ++ or a --; and a *, /, % or > only after a space,
# unlike a JSX tag's > or a regular expression's closing /. At the start of a line, a > goes on as a
# comparison does, or closes a type's < left open, as in x as Array<...> split over lines.
GOES_ON = re.compile(r"(?:=>?|\|\||&&|\?\?|[?:<]|(?<![+-])[+-]|\s[*/%>])$")
GOES_ON_NEXT = re.compile(r"\s*(?:\|\||&&|\?\?|\?(?!\.)|:|\.(?!\.)|[+-](?![+-])|[|&*%>])")
# The words after which a / opens a regular expression, since only an expression can follow them; as whole
# words, not a member's name such as x.in.
REGEX_AFTER = re.compile(r"(?<![\w$.])(?:return|case|typeof|void|delete|throw|new|await|yield|in|of|do|else)$")
# A JavaScript regular expression: from / to /, past escapes and the / in a class such as [/].
REGEX = re.compile(r"/(?:\\.|\[(?:\\.|[^\]\\])*\]|[^/\\\[])+/")
# A Python statement that is only a string, as a docstring is: documentation, so not a code line.
DOCSTRING = re.compile(r"""\s*[rRuUbBfF]{0,2}("{3}|'{3}|"|')""")


def skeleton(lines, comments, quotes, attributes=False):
    """Each line with its comments taken out and its strings' insides turned to "s", so brackets
    and code lines can be counted; and whether the line began inside a string or comment. With
    attributes, #[ opens an attribute, as in PHP 8, not a comment."""
    markers = comments.split()
    char_quote = quotes == "char"
    out, began_inside = [], []
    state = None  # Inside: a block comment ("*/"), or a string (its closing quote).
    # In JavaScript, a template literal's ${...} is code, up to the } that matches its {, and can hold strings
    # and templates of its own: per ${ still open, how many braces are open inside it.
    templates = []
    for line in lines:
        began_inside.append(state is not None or bool(templates))  # A template's ${...} is inside it too.
        code = []
        i = 0
        while i < len(line):
            if state == "*/":
                end = line.find("*/", i)
                if end < 0:
                    break
                i, state = end + 2, None
            elif state:
                if line[i] == "\\":
                    i += 2
                elif state == "`" and quotes == "regex" and line.startswith("${", i):
                    code.append("ss")  # The template's own brackets aren't the code's.
                    templates.append(0)
                    i, state = i + 2, None
                elif line.startswith(state, i):
                    code.append(state)
                    i, state = i + len(state), None
                else:
                    code.append("s")
                    i += 1
            elif "/*" in markers and line.startswith("/*", i):
                state = "*/"
                i += 2
            elif any(line.startswith(m, i) for m in markers if m != "/*") and not (
                    attributes and line.startswith("#[", i)):
                break
            elif line.startswith('"""', i) or line.startswith("'''", i):
                state = line[i:i + 3]
                code.append(state)
                i += 3
            elif line[i] == "/" and quotes == "regex" and REGEX.match(line, i) and regex_may_start(code, out):
                literal = REGEX.match(line, i).group(0)  # A regular expression, which can hold quotes and brackets.
                code.append("/" + "s" * (len(literal) - 2) + "/")
                i += len(literal)
            elif line[i] == "'" and char_quote:
                literal = re.match(r"'(?:\\.|[^\\'])'", line[i:])  # A character, or else a Rust lifetime.
                code.append("s" if literal else " ")
                i += len(literal.group(0)) if literal else 1
            elif line[i] in "\"'`":
                state = line[i]
                code.append(state)
                i += 1
            elif templates and line[i] == "}" and not templates[-1]:  # The end of a ${...}: back in its template.
                code.append("s")
                templates.pop()
                i, state = i + 1, "`"
            elif templates and line[i] in "{}":
                templates[-1] += 1 if line[i] == "{" else -1
                code.append(line[i])
                i += 1
            else:
                code.append(line[i])
                i += 1
        if state in ('"', "'") and quotes != "spans" and not line.rstrip().endswith("\\"):
            state = None  # Most languages end a one-quote string at the line's end.
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


def body_by_indent(lines, code, skip, start, with_end):
    """The last line of the function defined at start, by indentation. Its body starts after its
    signature, whose last line a formatter puts at the definition's own indentation, as in ) -> int:.
    A line in skip continues a string or open brackets, so its indentation says nothing."""
    width = indent_of(lines[start])
    last = signature_end(code, start)
    for i in range(last + 1, len(lines)):
        if not code[i].strip():
            continue
        if skip[i]:
            last = i
            continue
        if indent_of(lines[i]) <= width:
            # Its end is at its own indentation: one further out ends the class around a method that has none,
            # written on one line.
            if with_end and code[i].strip() == "end" and indent_of(lines[i]) == width:
                last = i
            break
        last = i
    return last


def body_by_brackets(code, inside, start, column=0):
    """The last line of a function's body, by matching brackets from code[start][column] on, where its
    definition starts or, if it's known, its body; None if no body follows, as for a declaration, or if
    its brackets never close. A block ends where its brace closes; an expression, such as an arrow
    function's, at the end of a line outside brackets that it doesn't go on from (goes_on)."""
    depth = carried = 0
    expression = False
    arrow = False  # An arrow ended the last line, so this one says which kind of body it is.
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
                if c == "{":  # A block: it ends where its brace closes.
                    end = closes.get((i, j + offset))
                    return end[0] if end else None
                elif line.startswith("=>", j):
                    rest = line[j + 2:].strip()
                    expression, arrow = bool(rest) and not rest.startswith("{"), not rest
                elif c == "=" and ")" in line[:j] and line[j - 1:j] not in "=!<>" and line[j + 1:j + 2] not in "=>":
                    expression = True  # Kotlin's fun f() = ..., C++'s = default.
                elif c == ";":
                    return None
            if c in OPEN:
                depth += 1
            elif c in CLOSE:
                depth -= 1
                if depth < 0 and not expression:  # The block around it closed first: a declaration, as a protocol's.
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


def by_pattern(pattern):
    """A language's way of finding its definitions from a regular expression: the name is whichever
    group matched, and the body is looked for from the start of the line."""
    pattern = re.compile(pattern)

    def find(code, i):
        match = pattern.match(code[i])
        name = next((g for g in match.groups() if g), None) if match else None
        return (name, (i, 0)) if name else None
    return find


FIND = dict((lang[0], lang[2] if callable(lang[2]) else by_pattern(lang[2])) for lang in LANGUAGES)


def functions(path, text):
    """The file's code lines, its functions as (name, first line, last line, code lines, deepest), and its language."""
    language = BY_EXTENSION.get(os.path.splitext(path)[1].lower())
    lines = text.split("\n")
    comments = language[4] if language else "# //"
    code, inside = skeleton(lines, comments, language[5] if language else "", language and language[0] == "PHP")
    counted = [bool(c.strip()) for c in code]
    if not language:
        return sum(counted), None, None
    name, _, _, ending, _, _ = language
    find = FIND[name]
    # A line that starts inside open brackets continues the one before, so it says nothing about
    # nesting. Braces are brackets too where indentation makes the blocks.
    opening = "([{" if ending != "brackets" else "(["
    closing = "".join(CLOSE[OPEN.index(c)] for c in opening)
    continued, depth = [], 0
    for line in code:
        continued.append(depth > 0)
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
        if ending == "brackets":
            last = body_by_brackets(code, inside, *defined[1])
            if last is None:
                continue
        else:
            last = body_by_indent(lines, code, skip, start, ending == "end")
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
