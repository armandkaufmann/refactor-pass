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
past it; in a small codebase that's often the biggest few. Then, per file,
longest first:

  lines     its code lines: blank lines and lines that are only a comment
            are left out
  band      its band among the language's files, or - below the 70th
  funcs     the functions found in it
  longest   its longest function, in code lines; its name and line follow
            the file's path
  long      how many of its functions are in the 80th or 90th band
  deepest   its deepest nesting inside a function, by indentation: 1 is a
            block inside the function's body, such as an if, and 2 a block
            inside that. Indentation tracks the classical complexity
            metrics closely (Hindle et al., 2008)

--show FILE lists that file's functions instead, with each one's line,
length, deepest nesting and band.

Functions are found by each language's definition keyword (def, func, fn,
fun, function, and Swift's init, deinit and subscript) or, for C, C++, Java
and C#, by their shape: a type, a name, parentheses, then a body. A function
runs to the end of its body, found by indentation (Python, GDScript, Ruby)
or by matching brackets (the rest). Files in other languages get lines only,
and the output says which.

It points at code to read; it doesn't judge it. What it gets wrong:
  - a nested function counts in its own length and in its parent's;
  - anonymous functions and lambdas aren't functions of their own: their
    lines count in the function around them, or in none at the top level;
  - shapes miss some methods (a parameter list holding parentheses) and can
    catch a macro or a call split over lines;
  - a brace in a regular expression or a heredoc can end a function early
    or late;
  - a line inside a multi-line string or a block comment's text can count
    as code or not, depending on how it starts;
  - nesting by indentation counts a continuation line (a call or literal
    split over lines) as deeper, except inside brackets left open;
  - in a small codebase one long file or function can hold a tenth of the
    lines and so be its own 90th; the output says when, and then the
    catalogue's reference points are a better guide than the bands.

Usage:
  measure.py [options] [SCOPE ...]

SCOPE is a folder or a glob, as for heatmap.py; with none, every file git
tracks. Use the same scope as the heatmap. Test files are set aside as the
heatmap sets them aside, by name or folder, so they stay out of the
percentiles; --keep-tests measures them too. Reads the working tree's
tracked files only.

Examples:
  measure.py src tests
  measure.py -C /path/to/repo app lib --show app/models/order.rb
"""

import argparse
import os
import re
import subprocess
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
JS = (r"^\s*(?:export\s+)?(?:default\s+)?(?:async\s+)?function\s*\*?\s*(\w+)"
      r"|^\s*(?:export\s+)?(?:(?:const|let|var|public|private|protected|static|readonly)\s+)*(\w+)\s*(?::[^=]+)?="
      r"\s*(?:async\s+)?(?:function\b|\([^()]*\)\s*(?::[^=]+)?=>|\w+\s*=>)"
      r"|^\s*(?:(?:public|private|protected|static|async|readonly|override|abstract|get|set)\s+)*\*?\s*"
      r"(?!(?:if|for|while|switch|catch|function|return|with)\b)(\w+)\s*(?:<[^>]*>)?\([^()]*\)\s*(?::\s*[^{;]+)?\{\s*$"
      r"|^\s*(\w+)\s*:\s*(?:async\s+)?(?:function\b|\([^()]*\)\s*=>|\w+\s*=>)")
C_SHAPE = (r"^\s*" + NOT_A_TYPE + MODIFIERS + r"(?:[\w<>\[\],.?*&:]+\s+)+[*&]*([A-Za-z_~][\w~]*(?:::~?\w+)*)"
           r"\s*\([^;]*$")
# C and C++ also put the type on the line above, with the name at the margin.
C_SHAPES = C_SHAPE + r"|^" + NOT_A_TYPE + r"([A-Za-z_][\w~]*(?:::~?\w+)*)\s*\([^;]*$"
# Per language: its extensions, how a definition's line looks (the name is
# whichever group matched), how its body ends, its comment markers, and its
# quotes: "char" when ' quotes one character (so a lone ' is something else,
# such as a Rust lifetime), "spans" when a quoted string can run over lines.
LANGUAGES = [
    ("Python", ".py", r"^\s*(?:async\s+)?def\s+(\w+)", "indent", "#", ""),
    ("GDScript", ".gd", r"^\s*(?:static\s+)?func\s+(\w+)", "indent", "#", ""),
    ("Ruby", ".rb", r"^\s*def\s+(?:self\.)?([\w?!=]+)", "end", "#", "spans"),
    ("JavaScript", ".js .jsx .mjs .cjs", JS, "brackets", "// /*", ""),
    ("TypeScript", ".ts .tsx .mts .cts", JS, "brackets", "// /*", ""),
    ("Vue", ".vue .svelte", JS, "brackets", "// /*", ""),
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
    ("Java", ".java", C_SHAPE, "brackets", "// /*", "char"),
    ("C#", ".cs", C_SHAPE, "brackets", "// /*", "char"),
    ("C", ".c .h", C_SHAPES, "brackets", "// /*", "char"),
    ("C++", ".cpp .cc .cxx .hpp .hh", C_SHAPES, "brackets", "// /*", "char"),
]
BY_EXTENSION = dict((ext, lang) for lang in LANGUAGES for ext in lang[1].split())
OPEN, CLOSE = "([{", ")]}"
# The floors, in code lines: the "Look closer" reference points in the catalogue's Measuring section
# (smells.md). Nothing at or below them is in a band, however the codebase compares.
FLOOR = {"file": 220, "function": 45}
PERCENTS = (70, 80, 90)


def skeleton(lines, comments, quotes):
    """Each line with its comments taken out and its strings' insides turned to "s", so brackets
    and code lines can be counted; and whether the line began inside a string or comment."""
    markers = comments.split()
    char_quote = quotes == "char"
    out, began_inside = [], []
    state = None  # Inside: a block comment ("*/"), or a string (its closing quote).
    for line in lines:
        began_inside.append(state is not None)
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
                elif line.startswith(state, i):
                    code.append(state)
                    i, state = i + len(state), None
                else:
                    code.append("s")
                    i += 1
            elif "/*" in markers and line.startswith("/*", i):
                state = "*/"
                i += 2
            elif any(line.startswith(m, i) for m in markers if m != "/*"):
                break
            elif line.startswith('"""', i) or line.startswith("'''", i):
                state = line[i:i + 3]
                code.append(state)
                i += 3
            elif line[i] == "'" and char_quote:
                literal = re.match(r"'(?:\\.|[^\\'])'", line[i:])  # A character, or else a Rust lifetime.
                code.append("s" if literal else " ")
                i += len(literal.group(0)) if literal else 1
            elif line[i] in "\"'`":
                state = line[i]
                code.append(state)
                i += 1
            else:
                code.append(line[i])
                i += 1
        if state in ('"', "'") and quotes != "spans" and not line.rstrip().endswith("\\"):
            state = None  # Most languages end a one-quote string at the line's end.
        out.append("".join(code))
    return out, began_inside


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


def body_by_indent(lines, code, inside, start, with_end):
    """The last line of the function defined at start, by indentation."""
    width = indent_of(lines[start])
    last = start
    for i in range(start + 1, len(lines)):
        if not code[i].strip() or inside[i]:
            continue
        if indent_of(lines[i]) <= width:
            if with_end and code[i].strip() == "end":
                last = i
            break
        last = i
    return last


def body_by_brackets(code, start):
    """The last line of the function defined at start, by matching brackets; None if no body follows,
    as for a declaration, or if its brackets never close."""
    depth = 0
    body = None  # "{" for a block; "=" for an expression, such as an arrow function's.
    arrow = False  # An arrow ends the line, so the next line says which kind of body it is.
    for i in range(start, len(code)):
        line = code[i]
        if arrow and body is None and line.strip():
            body = "{" if line.strip().startswith("{") else "="
        for j, c in enumerate(line):
            if body is None and depth == 0:
                if c == "{":
                    body = "{"
                elif line.startswith("=>", j):
                    rest = line[j + 2:].strip()
                    if rest:
                        body = "{" if rest.startswith("{") else "="
                    arrow = not rest
                elif c == "=" and ")" in line[:j] and line[j - 1:j] not in "=!<>" and line[j + 1:j + 2] not in "=>":
                    body = "="  # Kotlin's fun f() = ..., C++'s = default.
                elif c == ";":
                    return None
            if c in OPEN:
                depth += 1
            elif c in CLOSE:
                depth -= 1
                if depth == 0 and body == "{" and c == "}":
                    return i
                if depth < 0 and body is None:  # The block around it closed first: a declaration, such as a protocol's.
                    return None
        if body == "=" and depth <= 0:
            return i
        if body is None and i - start > 20:
            return None
    return None


def functions(path, text):
    """The file's code lines, its functions as (name, first line, last line, code lines, deepest), and its language."""
    language = BY_EXTENSION.get(os.path.splitext(path)[1].lower())
    lines = text.split("\n")
    comments = language[4] if language else "# //"
    code, inside = skeleton(lines, comments, language[5] if language else "")
    counted = [bool(c.strip()) for c in code]
    if not language:
        return sum(counted), None, None
    name, _, pattern, ending, _, _ = language
    pattern = re.compile(pattern)
    # A line that starts inside open brackets continues the one before, so it says nothing about
    # nesting. Braces are brackets too where indentation makes the blocks.
    opening = "([{" if ending != "brackets" else "(["
    closing = "".join(CLOSE[OPEN.index(c)] for c in opening)
    continued, depth = [], 0
    for line in code:
        continued.append(depth > 0)
        depth = max(0, depth + sum(line.count(c) for c in opening) - sum(line.count(c) for c in closing))
    unit = indent_unit(lines, code, [a or b for a, b in zip(inside, continued)])
    found = []
    for start, line in enumerate(code):
        match = pattern.match(line) if not inside[start] else None
        if not match:
            continue
        if ending == "brackets":
            last = body_by_brackets(code, start)
            if last is None:
                continue
        else:
            last = body_by_indent(lines, code, inside, start, ending == "end")
        base = indent_of(lines[start])
        depths = [(indent_of(lines[i]) - base) // unit - 1 for i in range(start + 1, last + 1)
                  if counted[i] and not inside[i] and not continued[i]]
        found.append((next(g for g in match.groups() if g), start + 1, last + 1, sum(counted[start:last + 1]),
                      max([0] + depths)))
    return sum(counted), found, name


def band(length, cuts, kind):
    """The highest of the 70th, 80th and 90th percentiles (cuts) that length reaches, past kind's floor,
    or None. The thing a percentile falls in reaches it, since some of its lines are past it."""
    if length <= FLOOR[kind]:
        return None
    reached = [percent for percent, cut in zip(PERCENTS, cuts) if cut and length >= cut]
    return reached[-1] if reached else None


def band_name(percent):
    return "%dth" % percent if percent else "-"


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
    parser.add_argument("--keep-tests", action="store_true", help="measure test files like the rest")
    parser.add_argument("--top", type=int, default=25, help="files to print (default 25)")
    parser.add_argument("--show", action="append", default=[], metavar="FILE",
                        help="list this file's functions, instead of the table of files")
    args = parser.parse_args()

    result = subprocess.run(["git", "-C", args.repo, "rev-parse", "--show-toplevel"], capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit("Not a git repo: %s" % args.repo)
    repo = result.stdout.strip()
    tracked = scoping.tracked_files(repo)
    if not tracked:
        sys.exit("%s tracks no files yet, so there's nothing to measure." % os.path.basename(repo))
    args.scope = scoping.resolve(args.repo, repo, args.scope, tracked)
    patterns = scoping.DEFAULT_IGNORE + args.ignore
    shows = [scoping.show_path(args.repo, repo, p, tracked) for p in args.show]
    paths = [p for p in tracked if scoping.in_scope(p, args.scope) and not scoping.ignored(p, patterns)]
    tests = set() if args.keep_tests else set(p for p in paths if scoping.is_test(p, args.test))
    paths = [p for p in paths if p not in tests]

    measured = {}
    for path in sorted(set(paths + shows)):
        full = os.path.join(repo, path)
        if not os.path.isfile(full):
            continue
        data = open(full, "rb").read()
        if b"\0" in data[:8000]:  # Binary, by git's own test.
            continue
        measured[path] = functions(path, data.decode("utf-8", errors="replace"))
    in_paths = set(paths)

    by_language = defaultdict(lambda: ([], []))  # Per language, its files' lengths and its functions'.
    no_rule = Counter()
    for path, (lines, found, language) in measured.items():
        if path not in in_paths:
            continue
        if language is None:
            no_rule[os.path.splitext(path)[1] or os.path.basename(path)] += 1
            continue
        files, funcs = by_language[language]
        files.append((lines, path))
        funcs.extend((f[3], "%s:%d %s" % (path, f[1], f[0])) for f in found)
    # Per language, the percentiles of its files' lengths and its functions'.
    cuts = dict((language, (weighted([n for n, _ in files]), weighted([n for n, _ in funcs])))
                for language, (files, funcs) in by_language.items())

    def lopsided(language, kind, things):
        """A note when one file or function holds a tenth of the lines, and so is its own 90th."""
        total = sum(n for n, _ in things)
        if len(things) > 1 and max(things)[0] * 10 >= total:
            return ("%s: %s holds %d%% of the %s lines, so the percentiles lean on it; judge by the reference "
                    "points in the catalogue's Measuring section too." % (language, max(things)[1],
                                                                         100 * max(things)[0] // total, kind))

    print("%s, scope: %s" % (os.path.basename(repo), " ".join(args.scope) or "(everything)"))
    print("Lines are code lines: blank lines and lines that are only a comment are left out.")
    print("Weighted by lines: 90% of the code is in files, or functions, no longer than the 90th.")
    print("Bands: a file or function at least as long as a percentile, and over the floor of %d lines for a file "
          "and %d for a function, is in its band. The 80th and 90th are big; the 70th, worth a closer look."
          % (FLOOR["file"], FLOOR["function"]))
    if not args.keep_tests:
        print("Test files: %s." % ("%d set aside from the percentiles and the table" % len(tests)
                                   if tests else "none in the scope"))
    print()
    print("%-11s %6s %6s   %-17s   %-17s" % ("", "files", "funcs", "   file lines", " function lines"))
    print("%-11s %6s %6s   %5s %5s %5s   %5s %5s %5s" % ("language", "", "", "70th", "80th", "90th",
                                                         "70th", "80th", "90th"))
    notes = []
    for language, (files, funcs) in sorted(by_language.items(), key=lambda kv: -sum(n for n, _ in kv[1][0])):
        print("%-11s %6d %6d   %5d %5d %5d   %5d %5d %5d" % tuple(
            [language, len(files), len(funcs)] + cuts[language][0] + cuts[language][1]))
        notes += [lopsided(language, "file", files), lopsided(language, "function", funcs)]
    for note in notes:
        if note:
            print(note)
    if no_rule:
        print("Lines only, with no rule to find functions: %d file%s (%s)." % (
            sum(no_rule.values()), "" if sum(no_rule.values()) == 1 else "s",
            ", ".join("%s %d" % kv for kv in no_rule.most_common(8))))
    print()

    def file_band(language, lines):
        return band(lines, cuts[language][0], "file") if language in cuts else None

    def function_band(language, length):
        return band(length, cuts[language][1], "function") if language in cuts else None

    if shows:
        for path in shows:
            if path not in measured:
                print("%s: not a text file in the working tree.\n" % path)
                continue
            lines, found, language = measured[path]
            if language is None:
                print("%s: %d code lines; no rule to find functions in this language.\n" % (path, lines))
                continue
            print("%s: %s, %d code lines, band %s, %d functions (%s)" % (
                path, language, lines, band_name(file_band(language, lines)), len(found),
                "%s functions: 70th %d, 80th %d, 90th %d lines" % ((language,) + tuple(cuts[language][1]))
                if language in cuts else "no %s file in the scope, so no percentiles to compare with" % language))
            print("%6s %6s %8s %5s  function" % ("line", "lines", "deepest", "band"))
            for name, first, last, length, deepest in found:
                print("%6d %6d %8d %5s  %s" % (first, length, deepest,
                                               band_name(function_band(language, length)), name))
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
            lines, band_name(file_band(language, lines)), len(found), longest[3] if longest else "-",
            sum(1 for f in found if (function_band(language, f[3]) or 0) >= 80), max([0] + [f[4] for f in found]),
            path, " (%s:%d)" % (longest[0], longest[1]) if longest else ""))
    if len(rows) > args.top:
        print("  ... %d more files" % (len(rows) - args.top))


if __name__ == "__main__":
    main()
