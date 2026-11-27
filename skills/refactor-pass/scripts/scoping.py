# Copyright (c) 2026 Armand Kaufmann. MIT License: https://github.com/armandkaufmann/refactor-pass
"""Which of a repo's files a refactor pass counts, shared by heatmap.py and measure.py.

The scope (folders or globs), the files never worth a refactor, copies of
this skill kept inside the repo, and the tests, which are set
aside by name or folder so that a spec beside its source doesn't swamp the
counts, and in Rust by the mod declarations that bring them in.
"""

import argparse
import difflib
import errno
import os
import bisect
import posixpath
import re
import subprocess
import sys
import traceback

# Never worth a refactor, whatever their churn: lock files, generated or
# minified files, drawings kept as text (SVG images and icon fonts), and the
# sidecars engines write beside each asset (Godot's .uid and .import, Unity's
# .meta).
DEFAULT_IGNORE = [
    "*.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "go.sum",
    "*.min.js", "*.min.css", "*.map", "*.snap", "*.svg", "*.uid", "*.import", "*.meta",
]
# The modes git gives a symbolic link and a submodule, which are left out: a link's file is counted where
# it lives, and a submodule is another repo.
NOT_FILES = ("120000", "160000")
# Test files, named as the common frameworks name them (matched with case),
# and anything inside a folder with one of TEST_FOLDERS' names (in any case).
TEST_NAMES = [
    "*.test.*", "*.spec.*", "*.cy.*", "*_test.*", "*_spec.*", "test_*.*", "tests.py", "conftest.py",
    "*Test.java", "*Tests.java", "*IT.java", "*Test.kt", "*Tests.kt", "*Test.php", "*Test.cs", "*Tests.cs",
    "*Test.swift", "*Tests.swift", "*Spec.scala", "*Test.scala", "*Spec.groovy",
]
TEST_FOLDERS = ["test", "tests", "__tests__", "__mocks__", "spec", "specs", "testdata"]
# A test file's marker, so that Board.spec.ts, test_board.py and BoardTest.php all test Board.
MARKER = re.compile(r"^test_|[._](?:test|spec|cy)(?=\.)|(?:Tests?|IT|Spec)(?=\.[^.]+$)")
# A name that's a test only by a word at its end, such as ABTest.php, which a production class can have too.
WORD_MARKER = re.compile(r"(?:Tests?|IT|Spec)\.[^.]+$")
# A folder of tests by the conventions that put a project's name first: MyApp.Tests, MyAppTests, unit-tests.
TESTS_PROJECT = re.compile(r"(?:[._-](?:[Tt]ests?|[Ss]pecs?)|[a-z0-9](?:Tests?|Specs?))$")
# The parts a feature test drives, which it names without the part's suffix: ShowDashboardTest.php
# tests ShowDashboardController.php.
ENTRY_POINTS = ("controller", "handler", "command")


def safe_output():
    """Never fail on printing a name the console can't show, as on Windows with output piped in its
    own code page: the character becomes a ?."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower().replace("-", "") != "utf8":
            stream.reconfigure(errors="replace")


# git's variables that would point it at another repo, index, object store or history than the one -C names,
# or change what the commands read here print (an external diff, how pathspecs read); left out of every git
# the scripts run. The settings that would change what git log prints are overridden where it's run.
GIT_PLACES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
              "GIT_COMMON_DIR", "GIT_NAMESPACE", "GIT_SHALLOW_FILE", "GIT_GRAFT_FILE", "GIT_REPLACE_REF_BASE",
              "GIT_NO_REPLACE_OBJECTS", "GIT_EXTERNAL_DIFF", "GIT_DIFF_OPTS", "GIT_LITERAL_PATHSPECS",
              "GIT_GLOB_PATHSPECS", "GIT_NOGLOB_PATHSPECS", "GIT_ICASE_PATHSPECS")


def git(repo, *args, **options):
    """Run git in repo as every script here runs it, with none of GIT_PLACES; the finished process, with its
    output as bytes. input, if given, is what git reads."""
    env = dict((k, v) for k, v in os.environ.items() if k.upper() not in GIT_PLACES)
    return subprocess.run(["git", "-C", repo] + list(args), capture_output=True, input=options.get("input"),
                          env=env)


# What a write to a pipe whose reader has gone fails with: EPIPE, or on Windows before Python 3.14, EINVAL.
GONE = (errno.EPIPE, errno.EINVAL)


class Watched(object):
    """The script's output, keeping the error a write or a flush to it failed with: so a reader that has gone
    is told from an error anywhere else, though argparse (from Python 3.12) ignores a failed write of the help,
    and a write too big for the buffer is lost when it fails, so a flush after it succeeds."""

    def __init__(self, stream):
        self.stream, self.error = stream, None

    def write(self, text):
        try:
            return self.stream.write(text)
        except OSError as e:
            self.error = e
            raise

    def flush(self):
        try:
            return self.stream.flush()
        except OSError as e:
            self.error = e
            raise

    def gone(self):
        """Whether its reader has gone: a write or a flush failed as one does then."""
        return self.error is not None and self.error.errno in GONE

    def __getattr__(self, name):
        return getattr(self.stream, name)


def guard(main):
    """Run a script's main. An exception nothing foresaw, a bug in the script, ends it with one plain line that
    says so and where, and exit code 3, so it can't pass for a problem with the repo; a reader that stops
    reading the output, as head does, ends it quietly with exit code 1, as one gone before the script writes a
    line does; and an error the script reports is reported whether the reader has gone or not."""
    for name in ("stdout", "stderr"):
        if getattr(sys, name) is None:  # Closed as it started, as by >&-: what it writes there goes nowhere.
            setattr(sys, name, open(os.devnull, "w", encoding="utf-8"))
    out = sys.stdout = Watched(sys.stdout)
    stopped = None
    try:
        try:
            main()
        except SystemExit as e:
            stopped = e
        if not out.gone():
            out.flush()  # What it wrote, as argparse's --help before it stops.
    except Exception as e:
        if not (isinstance(e, OSError) and e.errno in GONE and out.gone()):  # A bug, not a reader gone.
            try:
                settle(out)
            except OSError:  # The output can't take the rest, as on a full disk: the line comes out anyway.
                os.dup2(os.open(os.devnull, os.O_WRONLY), out.fileno())
            here = os.path.dirname(os.path.abspath(__file__))
            frames = traceback.extract_tb(e.__traceback__)
            where = ([f for f in frames if os.path.dirname(os.path.abspath(f.filename)) == here] or frames)[-1]
            sys.stderr.write("%s: stopped on a bug in the script itself, not a problem with the repo or the "
                             "command: %s: %s (%s, line %d, in %s).\n" % (
                                 os.path.basename(sys.argv[0]), type(e).__name__, " ".join(str(e).split()),
                                 os.path.basename(where.filename), where.lineno, where.name))
            sys.exit(3)
    settle(out)
    if stopped is not None and (stopped.code or not out.gone()):
        raise stopped  # An error it reports, which Python writes, reader or not; or the end it chose.
    if out.gone():
        sys.exit(1)


def settle(out):
    """Flush the output; where its reader has gone, point it at the null device, so the last flush, as Python
    exits, has somewhere to go."""
    try:
        out.flush()
    except OSError:
        if not out.gone():
            raise
    if out.gone():
        os.dup2(os.open(os.devnull, os.O_WRONLY), out.fileno())


def run(repo, *args):
    """A git command's output as text, or None if it failed. Git writes paths in UTF-8 whatever the
    system's code page, so they're read as UTF-8."""
    result = git(repo, *args)
    return result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else None


_FACTS = {}


def facts(start):
    """What git says of start, the folder -C names, from one git: the top of its repo, its path from there
    ("" at the top), the repo's git folder and the one its worktrees share, in full, and whether it's a
    shallow clone; or None outside a repo's working tree."""
    if start not in _FACTS:
        lines = (run(start, "rev-parse", "--show-toplevel", "--show-prefix", "--git-dir", "--git-common-dir",
                     "--is-shallow-repository") or "").split("\n")
        _FACTS[start] = None if len(lines) < 5 or not lines[0] else {
            "top": lines[0], "prefix": lines[1], "git_dir": os.path.realpath(os.path.join(start, lines[2])),
            "common": os.path.realpath(os.path.join(start, lines[3])), "shallow": lines[4] == "true"}
    return _FACTS[start]


def toplevel(start):
    """The top of the repo that start, the folder -C names, is in; or stop with a plain message."""
    if not os.path.isdir(start):
        sys.exit("No such folder: %s" % start)
    top = (facts(start) or {}).get("top")
    if not top:
        if (run(start, "rev-parse", "--is-bare-repository") or "").strip() == "true":
            sys.exit("%s is a bare repo, with no working tree to read; run this in a clone of it." % start)
        sys.exit("Not a git repo: %s" % start)
    return top


def count(least):
    """An argparse type: a whole number, least or more."""
    def parse(text):
        try:
            value = int(text)
        except ValueError:
            raise argparse.ArgumentTypeError("%r isn't a whole number" % text)
        if value < least:
            raise argparse.ArgumentTypeError("must be %d or more, not %d" % (least, value))
        return value
    return parse


_GLOBS = {}
# A **/ that stands for any number of folders: at a glob's start or after a /; elsewhere, as in app**/x, it's
# two stars, as fnmatch reads them.
DOUBLE_STAR = re.compile(r"(?:^|(?<=/))\*\*/")


def glob_piece(text):
    """Part of a glob, between its **/s, as a regular expression: * is any characters, / included, ? any one,
    and [...] one of a set ([!...] one not in it), as fnmatch reads them since Python 3.9, which leaves out a
    range written backwards, such as [z-a], so no Python fails on one."""
    out, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        i += 1
        if c == "*":
            out.append(".*")
        elif c == "?":
            out.append(".")
        elif c != "[":
            out.append(re.escape(c))
        else:
            j = i + (text[i:i + 1] == "!")
            j += text[j:j + 1] == "]"
            j = text.find("]", j)
            if j < 0:
                out.append(re.escape(c))
                continue
            if "-" not in text[i:j]:
                inside = text[i:j].replace("\\", "\\\\")
            else:  # Its ranges, a-z, without those written backwards.
                chunks, k = [], i + 2 if text[i] == "!" else i + 1
                while True:
                    k = text.find("-", k, j)
                    if k < 0:
                        break
                    chunks.append(text[i:k])
                    i, k = k + 1, k + 3
                if text[i:j]:
                    chunks.append(text[i:j])
                else:
                    chunks[-1] += "-"
                for k in range(len(chunks) - 1, 0, -1):
                    if chunks[k - 1][-1] > chunks[k][0]:
                        chunks[k - 1] = chunks[k - 1][:-1] + chunks[k][1:]
                        del chunks[k]
                inside = "-".join(s.replace("\\", "\\\\").replace("-", "\\-") for s in chunks)
            i = j + 1
            if not inside:
                out.append("(?!)")
            elif inside == "!":
                out.append(".")
            else:
                inside = re.sub(r"([&~|])", r"\\\1", inside)
                out.append("[%s]" % ("^" + inside[1:] if inside[0] == "!" else
                                     "\\" + inside if inside[0] in ("^", "[") else inside))
    return "".join(out)


def glob_match(path, pattern, case=True, windows=None):
    """Whether a glob matches a path: * matches across folders, so 'app/*.py' takes app/sub/deep.py, and **/
    at the start or after a / matches any number of folders, none included, so 'app/**/*.py' takes
    app/main.py too. On Windows (windows, by default whether this is it) a glob's \\ is its /, as a path
    there is written, and as fnmatch read --ignore's; and with case False, case is ignored there, as fnmatch
    did."""
    if os.name == "nt" if windows is None else windows:
        pattern = pattern.replace("\\", "/")
        if not case:
            path, pattern = path.lower(), pattern.lower()
    found = _GLOBS.get(pattern)
    if found is None:
        pieces = [glob_piece(p) for p in DOUBLE_STAR.split(pattern)]
        found = _GLOBS[pattern] = re.compile(r"(?s:%s)\Z" % "(?:.*/)?".join(pieces))
    return bool(found.match(path))


def in_scope(path, scopes):
    if not scopes:
        return True
    for scope in scopes:
        if scope == ".":
            return True
        if any(ch in scope for ch in "*?["):
            if glob_match(path, scope, False):
                return True
        elif path == scope or path.startswith(scope + "/"):
            return True
    return False


def ignored(path, patterns):
    name = posixpath.basename(path)
    return any(glob_match(name, p, False) or glob_match(path, p, False) for p in patterns)


def named(path, patterns):
    """Whether a glob, matched with case, names the file or its path."""
    return any(glob_match(posixpath.basename(path), p) or glob_match(path, p) for p in patterns)


def is_test(path, more=(), not_tests=(), modules=()):
    """Whether a file is a test: by its name, or by a folder it's in, or as one of Rust's test modules
    (rust_test_modules), unless not_tests names it."""
    if named(path, not_tests):
        return False
    if any(part.lower() in TEST_FOLDERS for part in path.split("/")[:-1]) or path in modules:
        return True
    return named(path, TEST_NAMES + list(more))


def doubtful_tests(tests, tracked, more=(), modules=()):
    """Of the files set aside as tests, those that may not be, as (what, why), so the eye goes to
    them: a name that's a test only by a word at its end, in no folder of tests; or a folder of
    tests by its name in which no file is named like a test, such as a spec folder of specifications.
    One of Rust's test modules (modules) is a test whatever its name."""
    found, folders = [], {}
    for path in sorted(tests):
        if path in modules:
            continue
        parts = path.split("/")
        by_name = named(path, TEST_NAMES + list(more))
        test_folders = [i for i, part in enumerate(parts[:-1]) if part.lower() in TEST_FOLDERS]
        if by_name and not test_folders and WORD_MARKER.search(parts[-1]) \
                and not any(TESTS_PROJECT.search(part) for part in parts[:-1]):
            found.append((path, "named like a test, in no folder of tests"))
        elif not by_name and test_folders and parts[test_folders[0]].lower() not in ("testdata", "__mocks__"):
            folders.setdefault("/".join(parts[:test_folders[0] + 1]), []).append(path)
    for folder in sorted(folders):
        inside = [p for p in tracked if p.startswith(folder + "/")]
        if not any(named(p, TEST_NAMES + list(more)) or p in modules for p in inside):
            found.append((folder + "/", "a folder named like tests, but none of its %d files is" % len(inside)))
    return found


def stem(path, test):
    """A file's name without its extension and, for a test, its marker; in lower case."""
    name = posixpath.basename(path)
    return os.path.splitext(MARKER.sub("", name, count=1) if test else name)[0].lower()


def flat(name):
    """A stem with its separators gone, so game_state, game-state and GameState read alike."""
    return re.sub(r"[^a-z0-9]", "", name)


def owns(test, path, stems, modules=None, named=False):
    """Whether path is the test's own file: the same name less the test's marker; or, when no file in
    stems (the production files' flat stems) has that name, the same name and an entry point's suffix,
    as ShowDashboardTest.php and ShowDashboardController.php. One of Rust's test modules (modules, as
    rust_test_modules gives them) owns the files whose declarations bring it in too; and only those, whatever their
    names, when it's a test by its declarations alone: not named or in a folder like a test's, nor Cargo's test."""
    if modules and test in modules:
        if path in modules[test][1]:
            return True
        if not named and modules[test][0] != "crate":
            return False
    mine, theirs = flat(stem(test, True)), flat(stem(path, False))
    return theirs == mine or (mine not in stems and any(theirs == mine + part for part in ENTRY_POINTS))


# Rust's test modules in files of their own (#[cfg(test)] mod tests;). A cfg needs test when it holds only where
# test is set (cfg_needs_test), which reads an attribute as measure.py's skeleton has it, its strings written "s".
RUST_CFG = re.compile(r"#\s*(?:!\s*)?\[\s*cfg\s*\(")
RUST_CFG_ATTR = re.compile(r"#\s*\[\s*cfg_attr\s*\(")


def cfg_terms(attribute, opening):
    """Of the cfg predicate in a Rust attribute after the opening matched (cfg's, or a cfg_attr's first), whether it
    holds only where test is set, and whether it holds wherever test isn't: test does the first; all() when one of
    its predicates does, and the second when each does; any() the first when each does, the second when one does;
    not() swaps them. Anything else holds either way, so does neither."""
    words = re.findall(r'\w+|"s*"|[(),=]', attribute[opening.end():]) if opening else []
    frames = [("all", [])]  # Per bracket open, its operator and its predicates' terms.
    for k, word in enumerate(words):
        if words[k + 1:k + 2] == ["("]:
            frames.append((word, []))
        elif word == ")" or (word == "," and len(frames) == 1):  # A cfg_attr's predicate ends at its first ,.
            operator, terms = frames.pop()
            only, without = [t[0] for t in terms], [t[1] for t in terms]
            term = (any(only), all(without)) if operator == "all" else \
                (bool(terms) and all(only), any(without)) if operator == "any" else \
                (without[0], only[0]) if operator == "not" and len(terms) == 1 else (False, False)
            if not frames:
                return term
            frames[-1][1].append(term)
        elif re.match(r"\w", word) and words[k - 1:k] != ["="]:  # A name, or a key given a value (feature = "x").
            frames[-1][1].append((word == "test" and words[k + 1:k + 2] != ["="], False))
    return False, False


def cfg_needs_test(attribute):
    """Whether a Rust attribute, as the skeleton has it, is a cfg that holds only where test is set: cfg(test),
    test among all()'s predicates, each of any()'s needing it, or not() of what holds wherever test isn't
    (not(not(test)))."""
    return cfg_terms(attribute, RUST_CFG.match(attribute))[0]


# What a Rust file's text is read in, past its comments and strings: a comment's or a string's opening, an
# attribute's (#[ or #![, past spaces and comments between), the word mod, a brace, a bracket or a ;; and anything
# else at once, in runs. A string is one of Rust's literals, whatever its prefix (b, c, r and br, cr; r#name is a
# name), and one never closed runs to the end. A file that holds none of RUST_READ isn't read so.
GAP = r"""(?:\s|/\*(?:[^*]|\*(?!/))*\*/|//[^\n]*\n)*"""  # Spaces and comments, a block comment unnested.
RUST_TOKEN = re.compile(r"""(//[^\n]*|/\*)|([bc]?r\#*")|([bc]?"(?:\\.|[^"\\])*(?:"|\\?\Z)|"""
                        r"""b?'(?:\\(?:x[0-9a-fA-F]{2}|u\{[0-9a-fA-F]{1,6}\}|.)|[^'\\\n])')|(\#%s(?:!%s)?\[)|"""
                        r"""(\bmod\b)|([{}\[\];])|"""
                        r"""(?:[^/"'\#{}\[\];\w]+|(?!\bmod\b)(?![bc]?r\#*")(?![bc]?")(?!b?')\w+|/(?![/*])|"""
                        r"""'(?![^'\\\n]'|\\)|\#(?!%s(?:!%s)?\[))+|\w+|.""" % (GAP, GAP, GAP, GAP), re.S)
COMMENTS = re.compile(r"/\*(?:[^*]|\*(?!/))*\*/|//[^\n]*")
# What a file must hold to be read so, each searched for on its own, the word first, so that every search takes time
# in step with the text: mod, not in a word, then a name and a ; or a comment, or a comment, or a $name (mod$m;
# too); an inner cfg, and include!, past comments in their heads (but nested ones), each to its first */, as GAP reads
# them, so a run of them is read one way only.
HEAD_GAP = GAP
RUST_READ = (re.compile(r"mod(?<![\w$]mod)(?:\s+(?:r#)?\w+\s*[;/]|\s*/|\s*\$)"),
             re.compile(r"#%s!%s\[%scfg" % (HEAD_GAP, HEAD_GAP, HEAD_GAP), re.S),
             re.compile(r"include%s!" % HEAD_GAP, re.S))
BLOCK_COMMENT = re.compile(r"/\*|\*/")
KINDS = (None, "comment", "raw", "string", "attribute", "mod", "bracket")
RUST_NAME = re.compile(r"\s*((?:r#)?[A-Za-z_]\w*)\s*$")
MACRO_BEFORE_BRACE = re.compile(r"(?:\w\s*!|macro_rules\s*!\s*(?:r#)?\w+)\s*$")  # pick! {, macro_rules! m {
INCLUDE_AT = re.compile(r"\binclude\s*!\s*(\(\s*)?(\S?)")  # include!, its bracket, and what follows in its run.
INCLUDE_HEAD = re.compile(r"(?<![\w$])include\s*(!\s*)?$")  # include, or include!, before a comment.
# What starts an item or a let, not an expression's part: where an attribute is on one, a , doesn't end it. A word
# Rust keeps only in places (union) starts one only before what it starts there.
ITEM_HEAD = re.compile(r"\s*(?:(?:pub|fn|impl|trait|struct|enum|type|static|const|extern|unsafe|async|use|let)\b|"
                       r"(?:union|default|safe|macro_rules)\s*[\w!])")
BRANCH_BEFORE = re.compile(r"(?<![\w$])if\s*$|\$\(\s*$")  # cfg_if! { if #[cfg(test)] { ... } }, $( #[a] ... )*
ENV_BEFORE = re.compile(r"\benv\s*!\s*\(\s*$")  # Before a string that names a variable, not a path.
ATOM = re.compile(r"\$?(?:r#)?[A-Za-z_]\w*|\w+|[^\s\w]")  # In a run: a word, a $name, a number or a mark.
WORD, WORDS = re.compile(r"\w"), re.compile(r"[A-Za-z_]\w*")


def rust_tokens(text):
    """A Rust file's tokens, as (kind, text), past its comments: a string or a character, whole ("string"), an
    attribute's opening ("attribute"), the word mod ("mod"), a brace, a bracket or a ; ("bracket"), and anything
    else in runs (None)."""
    i = 0
    while i < len(text):
        found = RUST_TOKEN.match(text, i)
        i = found.end()
        kind = KINDS[found.lastindex or 0]
        if kind == "comment":
            if found.group(1) == "/*":  # Rust's block comments nest.
                depth = 1
                for mark in BLOCK_COMMENT.finditer(text, i):
                    depth += 1 if mark.group() == "/*" else -1
                    if not depth:
                        i = mark.end()
                        break
                else:
                    i = len(text)
            continue
        if kind == "attribute":  # As #[ or #![, its comments passed.
            yield kind, "#![" if "!" in COMMENTS.sub("", text[found.start():i]) else "#["
            continue
        if kind == "raw":  # To the quote and as many #s as it opened with.
            hashes = found.group(2).count("#")
            close = text.find('"' + "#" * hashes, i)
            i = close + 1 + hashes if close >= 0 else len(text)
            kind = "string"
        yield kind, text[found.start():i]


def string_text(token):
    """A string token's text, without its quotes or prefix, its escapes read but in a raw string."""
    text = token.lstrip("bcr").strip("#")[1:-1]
    if token.lstrip("bc").startswith("r"):
        return text
    return re.sub(r"\\(.)", lambda escape: ESCAPES.get(escape.group(1), escape.group(1)), text)


ESCAPES = {"n": "\n", "t": "\t", "r": "\r", "0": "\0"}


CFG_ATTR_OPEN = re.compile(r"\bcfg_attr\s*\($")


def opened(text):
    """Text up to the bracket the end of it is in, that bracket included."""
    depth = 0
    for at in range(len(text) - 1, -1, -1):
        depth += {")": 1, "(": -1}.get(text[at], 0)
        if depth < 0:
            return text[:at + 1]
    return ""


def rust_attribute(tokens, opening):
    """An attribute read from tokens after its opening: its text, written for cfg_needs_test (its strings "s"); the
    file a path attribute names (#[path = "x.rs"]), or None; the one a cfg_attr gives (#[cfg_attr(windows,
    path = "win.rs")]), or None; and whether that's in a cfg_attr nested in it, whose cfgs aren't read."""
    parts, depth, parens, path, choice, first, nested = [opening], 1, 0, None, None, True, False
    for kind, token in tokens:
        if kind == "bracket" and token in "[]":
            depth += 1 if token == "[" else -1
            if not depth:
                break
        if kind == "string":
            if first and re.match(r"\s*path\s*=\s*$", "".join(parts[1:])):  # Its first string only.
                path = string_text(token)
            elif choice is None and parens >= 1 and re.search(r",\s*path\s*=\s*$", parts[-1]) and \
                    re.match(r"\s*cfg_attr\s*\(", parts[1]) and CFG_ATTR_OPEN.search(opened("".join(parts[1:]))):
                choice, nested = string_text(token), parens > 1
            token, first = '"s"', False
        elif kind is None:
            parens += token.count("(") - token.count(")")
        parts.append(token)
    return "".join(parts) + "]", path, choice, nested


def rust_modules(text):
    """A Rust file's modules as rustc reads them: (marked, scopes, declared, included). marked: whether the whole
    file needs test, by #![cfg(test)] before anything else in it (past a shebang line). scopes: per block it opens
    where a mod declaration's file is found otherwise, its parent's index and what it is: ("module", name) for an
    inline module, ("path", folder) for one with a #[path], ("block", None) for a function's body or any other block
    that isn't a macro's or a module's, in which a declaration needs a #[path]; scope 0 is the file's own. A macro's
    brackets (pick! { if #[cfg(test)] { mod t; } }) open none: a declaration in them is read as if they weren't
    there, the cfg before their brace counted. An outer attribute is on the block after it only where an item or a
    statement starts (after a ;, a brace or the file's start) or a macro's branch does (after if, or a template's
    $(); on a part of one, as a parameter, an argument or an element, it's that part's, and on what's no item, as a
    match arm or a field, a , outside its brackets ends it. declared: per mod declaration, (name, path, scope, test,
    choices, own): its #[path] or None (the first, which a cfg_attr's path before it may stand in for), the scope
    it's in, whether its cfg or the code it's in needs test, the files its cfg_attrs may name instead, each with its
    cfg's terms (cfg_terms), and whether its own attributes need test. included: outside test code, (path, whole)
    per string an include! holds, whole when the string is all its argument (include!("x.rs")), not when it's a
    part (include!(concat!(..., "/x.rs"))); none of one built on OUT_DIR, the build's output, not the package; one
    string's, and where it holds more than one outside env!, all of them joined. include, its ! and its bracket may
    be apart, as by comments."""
    if text.startswith("\ufeff"):
        text = text[1:]
    if text.startswith("#!") and not re.match(r"#!" + GAP + r"\[", text):  # A shebang line, which rustc passes over.
        text = text[text.find("\n") + 1:] if "\n" in text else ""
    scopes = [(None, None, None)]
    # Per brace open: its scope, whether its code needs test, whether nothing but inner attributes has come in it
    # yet, and whether it's a macro's.
    frames = [[0, False, True, False]]
    declared, included, pending, name, before, tokens = [], [], [], None, "", rust_tokens(text)
    pending_test = False  # Whether an attribute pending, before the item it's on, is a cfg that needs test.
    # Whether an attribute here would be on an item or a statement (after a ;, a brace or the start), or a branch's
    # in a macro; and once one that needs test is, whether what it's on is no item, and the brackets open since it:
    # then a , outside them ends it, as a match arm's or a field's, and the block after isn't its.
    starts, part, opened = True, None, 0
    include = None  # After include!: "open" to its argument, "inside" it past something other than a string, "out"
    start, depth = 0, 0  # in one built on OUT_DIR; where its strings start in included, and its brackets open.
    strings, joins = [], []  # Its strings outside env!; per include! of two or more, where they're joined.
    head = ""  # A run's include or include! at its end, read with the next run, past a comment between.
    for kind, token in tokens:
        test_code = frames[-1][1] or pending_test
        if kind == "attribute":
            attribute, path, choice, nested = rust_attribute(tokens, token)
            if "!" in token:
                if frames[-1][2] and cfg_needs_test(attribute):
                    frames[-1][1] = True
            else:
                pending.append((attribute, path, choice, nested))
                if (starts or BRANCH_BEFORE.search(before)) and not pending_test and cfg_needs_test(attribute):
                    pending_test, part, opened = True, None, 0
                frames[-1][2] = False
            before, head = "", ""
            continue
        if kind is None:
            if not token.strip():
                continue
            if pending_test and part is not False:
                part = part if part is not None else not ITEM_HEAD.match(token)
                for c in token if part else "":
                    opened += 1 if c == "(" else -1 if c == ")" else 0
                    if c == "," and opened <= 0:
                        pending_test = False
                        break
            starts = False
            found = RUST_NAME.match(token) if name == "" else None  # After mod, the module's name.
            name = (found.group(1)[2:] if found.group(1).startswith("r#") else found.group(1)) if found else None
            probe = head + token
            at = INCLUDE_AT.search(probe) if "include" in probe else None
            if at:
                start, strings = len(included), []
                depth = 1 + probe.count("(", at.end(1)) - probe.count(")", at.end(1)) if at.group(1) else 0
                include = ("inside" if at.group(2) else "open") if depth or not at.group(1) else None
            elif include and depth:  # In its argument: done at the bracket that closes it.
                depth += token.count("(") - token.count(")")
                include = None if depth <= 0 else "out" if include == "out" else "inside"
            elif include:  # Nothing else may come between include! and its bracket.
                include = None
            ends = INCLUDE_HEAD.search(probe) if "include" in probe else None
            head = ("include!" if ends.group(1) else "include") if ends else ""
            before = token
            frames[-1][2] = False
            continue
        frames[-1][2] = False
        if pending_test and part is None:  # mod, a string or a [ after it.
            part = kind != "mod"
        starts, head = token in ";{}", ""
        if kind == "mod":
            name, before = "", ""
            continue
        if kind == "string":
            if include == "inside" and string_text(token) == "OUT_DIR":
                del included[start:]  # Built on the build's output folder: no file of the repo's.
                while joins and joins[-1][0] >= start:  # Its own, the last.
                    joins.pop()
                include = "out"
            elif include and include != "out" and not test_code:
                included.append((string_text(token), include == "open"))
                if include == "inside" and not ENV_BEFORE.search(before):
                    strings.append(string_text(token))
                    if len(strings) == 2:  # concat!("gen", ".rs"): gen.rs, once they're all read.
                        included.append(None)
                        joins.append((len(included) - 1, strings))
            include = "out" if include == "out" else "inside" if include else None
        elif token in ";{}":
            test = test_code
            if token == ";":
                if name:
                    # The first #[path] counts; a cfg_attr's path before it stands in for it where its cfg holds.
                    first = next((k for k, (_, p, _, _) in enumerate(pending) if p is not None), len(pending))
                    path = pending[first][1] if first < len(pending) else None
                    # A nested cfg_attr's file is one the declaration may name, as code.
                    choices = [(c, (False, False) if n else cfg_terms(a, RUST_CFG_ATTR.match(a)))
                               for a, _, c, n in pending[:first] if c is not None]
                    declared.append((name, path, frames[-1][0], test, choices, pending_test))
            elif token == "{":
                if name:
                    path = next((p for _, p, _, _ in pending if p is not None), None)
                    scopes.append((frames[-1][0], "module", name) if path is None else (frames[-1][0], "path", path))
                    frames.append([len(scopes) - 1, test, True, False])
                elif frames[-1][3] or MACRO_BEFORE_BRACE.search(before):
                    frames.append([frames[-1][0], test, True, True])
                else:
                    scopes.append((frames[-1][0], "block", None))
                    frames.append([len(scopes) - 1, test, True, False])
            elif len(frames) > 1:
                frames.pop()
            pending, pending_test = [], False
            if include and token != ";":
                depth += 1 if token == "{" else -1
                include = include if depth > 0 else None
            else:
                include = None
        else:  # [ or ]: include![...] opens its argument.
            opened += 1 if token == "[" else -1
            if include:
                depth += 1 if token == "[" else -1
                include = include if depth > 0 else None
        name, before = None, ""
    for k, parts in joins:
        included[k] = ("".join(parts), False)
    return frames[0][1], scopes, declared, included


def rust_macros(text):
    """The macros a Rust file defines, macro_rules! and macro (macros 2.0: macro m($x:ident) { ... }, or with arms),
    read by its tokens, past comments and strings, the body in any bracket: per one, [its name, or None where it can't
    be read (a $name), whether its body holds a mod declaration (mod, any $names, a name or a $name, ;), the words in
    its body but those in a definition inside it, the definition it's in, or None, whether other crates may call it, the
    strings of the path attributes in its body (#[path = "..."], or a cfg_attr's), None for one that isn't a string
    (#[path = $p]) or an attribute a call may give (#[$a]), and the strings in it, both but those in a definition inside
    it]. Others may call a macro 2.0, and a macro_rules! after an attribute that holds macro_export, or in a body that
    does anywhere, or in one others may call. A body holds the mod declarations of those in it. Outside the definitions,
    only their heads, and whole attributes, are read."""
    found, stack, step, name, declaring, export = [], [], 0, None, 0, False  # stack: per bracket, the definition
    tokens = rust_tokens(text)  # it's in; step: into macro_rules ! name; declaring: into mod $names name ;.
    opening, newer, after, attribute = [], False, None, 0  # Per bracket its opening; a macro 2.0's head; one past
    previous, pathed = None, False  # its parameters, before its body; the brackets of attributes open; the atom
    # before; whether it's a path attribute's =.
    for kind, token in tokens:
        current = stack[-1] if stack else None
        if current is None and kind == "attribute" and after is None:
            depth, holds = 1, False
            for inner, part in tokens:
                if inner == "bracket" and part in "[]":
                    depth += 1 if part == "[" else -1
                    if not depth:
                        break
                holds = holds or inner is None and "macro_export" in part
            export, step = export or (holds and "!" not in token), 0
            continue
        if current is None and not step and after is None and (kind is not None or "macro" not in token):
            export = export and kind is None and not token.strip()
            continue
        for atom in ATOM.findall(token) if kind is None else ('""' if kind == "string" else "".join(token.split()),):
            word = atom[0].isalpha() or atom[0] == "_" or atom.startswith("r#")
            if after is not None and atom == "{":  # A macro 2.0's body, after its parameters.
                current, after = after, None
                stack.append(current)
                opening.append(atom)
                continue
            after = None
            if atom in ("(", "[", "{", "#[", "#!["):
                params = step == 3 and newer and atom == "("  # A macro 2.0's parameters, then its body.
                if step == 3:  # A definition's body.
                    found.append([name, False, set(), current, newer or export or current is not None and
                                  found[current][4], [], []])
                    current, step, export = len(found) - 1, 0, False
                stack.append(current)
                opening.append("params" if params else atom)
                attribute += atom in ("#[", "#![")
            elif atom in (")", "]", "}"):
                closed = stack.pop() if stack else None
                kind_of = opening.pop() if opening else None
                attribute -= kind_of in ("#[", "#![")
                current = stack[-1] if stack else None
                after = closed if kind_of == "params" else None
            elif word and current is not None:
                found[current][2].add(atom[2:] if atom.startswith("r#") else atom)
            if kind == "string" and current is not None:
                found[current][6].append(string_text(token))
            if declaring in (2, 3) and atom == ";" and current is not None:
                found[current][1] = True
            if previous == "=" and pathed and current is not None:  # #[path = "x.rs"], or #[path = $p].
                found[current][5].append(string_text(token) if kind == "string" else None)
            if previous in ("#[", "#![") and atom[:1] == "$" and current is not None:  # #[$a], which may be one.
                found[current][5].append(None)
            pathed = atom == "=" and attribute and previous == "path"
            dollar = atom[:1] == "$" and len(atom) > 1
            declaring = 1 if atom == "mod" else (2 if dollar else 3 if word else 0) if declaring in (1, 2) else 0
            head = atom in ("macro_rules", "macro") or step == 1 and atom == "!" or step == 2 and (word or dollar)
            export = export and (head or current is not None)
            if step == 2 and (word or atom[:1] == "$"):
                name, step = (None if atom[:1] == "$" else atom[2:] if atom.startswith("r#") else atom), 3
            else:
                newer = atom == "macro"
                step = 1 if atom == "macro_rules" else 2 if step == 1 and atom == "!" or newer else 0
            previous = atom
    for k in range(len(found) - 1, -1, -1):  # A body holds what one inside it does.
        up = found[k][3]
        if up is not None:
            found[up][1] = found[up][1] or found[k][1]
    top, exported = [], {}  # Per definition the outermost it's in; per outermost, whether its body holds macro_export.
    for k, definition in enumerate(found):
        top.append(k if definition[3] is None else top[definition[3]])
        exported[top[k]] = exported.get(top[k], False) or "macro_export" in definition[2]
    for k, definition in enumerate(found):
        definition[4] = definition[4] or definition[3] is not None and exported[top[k]]
    return found


def cargo_roots(manifests, folder_of, find):
    """The crate roots Cargo's manifests (their texts, by path) name by their paths ([[bin]] path = "...", [package]
    build = "..."), of the .rs files git tracks: (roots, code), code being those it builds other than as tests: a
    library, a binary, an example, a bench or a build script. A path in any other table that names a .rs file, as
    an inline [[bin]]'s, is taken for one too. folder_of(path) gives a manifest's folder; find(folder, path) the
    tracked .rs file a path names from it, or None. roots maps each to its manifest."""
    roots, code = {}, set()
    for manifest, text in sorted(manifests.items()):
        table = ""
        for line in text.splitlines():
            if line.lstrip().startswith("#"):
                continue
            header = re.match(r"\s*\[\[?([^\]]*)\]", line)
            if header:
                table = header.group(1).strip()
                continue
            for key, value, literal in re.findall(r"""\b(path|build)\s*=\s*(?:"((?:\\.|[^"\\])*)"|'([^']*)')""", line):
                if key == "build" and table != "package":
                    continue
                target = find(folder_of(manifest), literal or re.sub(r"\\(.)", r"\1", value))
                if target:
                    roots.setdefault(target, manifest)
                    if table != "test" and not re.match(r"\s*test\s*=", line):
                        code.add(target)
    return roots, code


def aliases(text):
    """The names a file's public use declarations give what they bring in (pub use crate::modules as mods;), as
    (old, new), read by its tokens, past comments and strings: each pub use, wherever it starts, to its ;. Another
    use gives a name only where it is, or in its crate, whose files mention the old one or are compiled with them."""
    found, atoms, previous = [], None, None  # The atoms of the pub use read, and the atom before.
    for kind, token in rust_tokens(text):
        for atom in ATOM.findall(token) if kind in (None, "mod") else ('""' if kind == "string" else token.strip(),):
            if atoms is None:
                atoms = [] if atom == "use" and previous == "pub" else None
            elif atom == ";":
                names = [each[2:] if each.startswith("r#") else each for each in atoms]
                found += [(names[k - 1], names[k + 1]) for k in range(1, len(names) - 1) if names[k] == "as" and
                          WORDS.fullmatch(names[k - 1]) and WORDS.fullmatch(names[k + 1]) and names[k + 1] != "_"]
                atoms = None
            else:
                atoms.append(atom)
            previous = atom
    return found


def mentioning(names):
    """A test of whether a text mentions any of names as a word: each name looked for, or past 16, its words read."""
    if len(names) > 16:
        return lambda text: not names.isdisjoint(WORDS.findall(text))
    words = [(name, re.compile(re.escape(name) + r"(?!\w)")) for name in sorted(names)]

    def holds(text):
        for name, word in words:
            for found in word.finditer(text) if name in text else ():
                at = found.start()  # Not after a word's character either.
                if not at or not (text[at - 1].isalnum() or text[at - 1] == "_"):
                    return True
        return False
    return holds


def spread(names, files, texts, pairs):
    """The names reached from names among files: each pair (old, new) pairs(path) gives a file, read once and only
    where it mentions a name reached (as each holds its old one), adds new where old is reached; past four rounds,
    each file left is found by its words, read once."""
    reached, batch, unread, index, given, rounds = set(names), sorted(names), list(files), None, {}, 0
    while batch:
        rounds += 1
        if index is None and rounds > 4:  # A chain of new names: each file's words read once, from here on.
            index = {}
            for path in unread:
                for word in set(WORDS.findall(texts[path])):
                    index.setdefault(word, []).append(path)
            unread = set(unread)
        if index is None:
            holds = mentioning(set(batch))
            reading = [p for p in unread if holds(texts[p])]
            taken = set(reading)
            unread = [p for p in unread if p not in taken]
        else:
            reading = sorted(set(p for name in batch for p in index.pop(name, ()) if p in unread))
            unread.difference_update(reading)
        for path in reading:
            for old, new in pairs(path):
                given.setdefault(old, set()).add(new)
        batch = sorted(set(new for name in batch for new in given.get(name, ()) if new not in reached))
        reached.update(batch)
    return reached


def past_comments(text, at, ends=None):
    """Where the text after at goes on past spaces and comments, block comments nested as Rust's are; ends, if
    given, keeps where each comment met leads, and where each block comment met ends, those nested in it too, so
    that no comment is passed twice."""
    met = []
    while True:
        at = SPACE.match(text, at).end()
        if ends is not None and at in ends:
            at = ends[at]
            break
        met.append(at)
        if text.startswith("//", at):  # To its line's end, the last one found kept.
            line = ends.get("line") if ends is not None else None
            if not line or not line[0] <= at <= line[1]:
                end = text.find("\n", at)
                line = at, len(text) if end < 0 else end
            at = line[1]
            if ends is not None:
                ends["line"] = line
        elif text.startswith("/*", at) and ends is not None and ("/*", at) in ends:
            at = ends[("/*", at)]
        elif text.startswith("/*", at):
            opened = [at]  # Those open, nested.
            for mark in BLOCK_COMMENT.finditer(text, at + 2):
                if mark.group() == "/*":
                    opened.append(mark.start())
                    continue
                start = opened.pop()
                if ends is not None:
                    ends[("/*", start)] = mark.end()
                if not opened:
                    at = mark.end()
                    break
            else:
                at = len(text)
                for start in opened if ends is not None else ():
                    ends[("/*", start)] = at
        else:
            break
    for each in met if ends is not None else ():
        ends[each] = at
    return at


def macro_head(text):
    """Whether a text holds a macro 2.0's head: the word macro, a name and its bracket, past any comments."""
    at, ends = text.find("macro"), {}
    while at >= 0:
        if not (at and (text[at - 1].isalnum() or text[at - 1] in "_$#")) and not WORD.match(text, at + 5):
            start = past_comments(text, at + 5, ends)
            name = NAME_AT.match(text, start) if start > at + 5 else None
            after = past_comments(text, name.end(), ends) if name else 0
            if name and text[after:after + 1] in ("(", "{"):
                return True
        at = text.find("macro", at + 5)
    return False


SPACE, NAME_AT = re.compile(r"\s*"), re.compile(r"(?:r#)?[A-Za-z_]\w*")


def macro_packages(texts, paths, package, shared=(), lands=None, compiled=None):
    """The packages, as package(path) gives each .rs file's, where a macro may declare modules: each in which a file
    defines a macro whose body holds a mod declaration (rust_macros), a module macro, or mentions the name of one
    that reaches other packages, as a word anywhere in its text; and those a path attribute in a module macro may
    name a file in: lands(path, string) gives the packages a string may name one in from a file's folder, or from
    any (path None). One reaches them when others may call it (rust_macros), or when it's defined in a file another
    package's crate compiles (shared); so does one that reaches them whose body mentions one that does, and the name
    a pub use gives one (pub use modules as mods;). One that reaches no other package keeps only its own. A path
    attribute's string, in its body, names a file from wherever it's called; one a call gives (#[path = $p]), from
    the file of the call: each string in those that mention the macro, or one whose body does, or a name a pub use
    gives either, in its package, or in a file of another its crates compile (compiled(packages)), or in any where
    it reaches others; and each string in those bodies, from wherever they're called."""
    defined = {}

    def defs(path):
        if path not in defined:
            defined[path] = rust_macros(texts[path]) if "macro_rules" in texts[path] or macro_head(texts[path]) \
                else []
        return defined[path]

    reaching = lambda path, definition: definition[4] or path in shared
    found, reach, pathed = set(), set(), []
    for path in paths:  # The files that may hold one, by a mod declaration (RUST_READ's), or one that reaches others.
        text = texts[path]
        if (path in shared or "macro_export" in text or RUST_READ[0].search(text)) and \
                ("macro_rules" in text or macro_head(text)):
            here, outermost, trees = defs(path), [], {}
            for k, definition in enumerate(here):
                outermost.append(k if definition[3] is None else outermost[definition[3]])
                if definition[1]:
                    found.add(package(path))
                    reach.update([definition[0]] if definition[0] and reaching(path, definition) else [])
                tree = trees.setdefault(outermost[k], [[], set(), False])  # Its path strings, names, if it reaches.
                tree[0] += definition[5]
                tree[1].update([definition[0]] if definition[0] else [])
                tree[2] = tree[2] or reaching(path, definition)
            pathed += [(path,) + tuple(tree) for top, tree in sorted(trees.items()) if tree[0] and here[top][1]]

    def calls(path, only_reaching):
        """Per word the body of a macro in a file mentions, the macro's name, or the nearest one's it's in where it
        has none, of those that reach others or of any; and the new names its pub uses give."""
        out, named = [], []
        for definition in defs(path):
            named.append(definition[0] or (named[definition[3]] if definition[3] is not None else None))
            if named[-1] and (reaching(path, definition) or not only_reaching):
                out += [(word, named[-1]) for word in sorted(definition[2])]
        return out + (aliases(texts[path]) if "as" in texts[path] and "use" in texts[path] else [])

    reach = spread(reach, paths, texts, lambda path: calls(path, True))
    holds = mentioning(reach)
    for path in paths:
        if reach and package(path) not in found and holds(texts[path]):
            found.add(package(path))
    # The names whose calls may give a path attribute its string: of those that reach others, and of the rest; and
    # the packages of the rest.
    wanted, near = [set(), set()], set()
    for path, strings, names, reaches in pathed if lands else ():
        for string in strings:
            found.update(lands(None, string) if string is not None else ())
        if None in strings:
            wanted[not reaches].update(names)
            near.update([] if reaches else [package(path)])
    # Their calls: in any file, or for the rest, in one of their packages or of another their crates compile.
    elsewhere = compiled(near) if wanted[1] and compiled else set()
    local = [p for p in paths if package(p) in near or p in elsewhere] if wanted[1] else []
    names = [spread(wanted[0], paths, texts, lambda path: calls(path, False)) if wanted[0] else set(),
             spread(wanted[1], local, texts, lambda path: calls(path, False)) if wanted[1] else set()]
    holds, local = [mentioning(each) for each in names], set(local)
    for caller in paths:
        if names[0] and holds[0](texts[caller]) or caller in local and holds[1](texts[caller]):
            for kind, token in rust_tokens(texts[caller]):
                found.update(lands(caller, string_text(token)) if kind == "string" else ())
            for definition in defs(caller):  # Those in their bodies, from wherever they're called.
                for string in definition[6] if definition[0] in names[0] or definition[0] in names[1] else ():
                    found.update(lands(None, string))
    return found


def rust_test_modules(tracked, read, links=None):
    """Rust's test modules in files of their own: each tracked .rs file every mod declaration of which, in a tracked
    file, needs test, by its cfg or by the code it's in (an inline module compiled only for tests, or a file that's a
    test module itself); and each marked #![cfg(test)] before anything else in it. A file Cargo builds as a crate of
    its own other than as a test (cargo_roots), or one that code outside tests include!s, is never one by its
    declarations, nor is a file or a folder's file that a tracked link names (links: per link, the path it holds),
    which rustc may reach through it; a crate it builds only as a test is one, as are its modules. read(paths)
    gives the files' texts; a file it gives none for, as one deleted, isn't there.
    Per test module, (how, declared): how it's known, "declared", "marked" (#![cfg(test)]) or "crate" (Cargo's test
    crate), and the files whose declarations bring it in. In a package where a macro may declare modules
    (macro_packages, and each whose files the crates of one bring in other than for tests, where its macros may be
    called), no file is one by its declarations, nor passes being one on: its marked files and the roots of its
    test crates are still tests.

    A declaration's file is where rustc finds it: from a crate root's or a mod.rs's folder, or a module file's
    own (src/disk.rs's src/disk/), with each inline module's name, or its #[path], added; name.rs there, or
    name/mod.rs; or in a block (a function's body), only by its #[path]. A #[path] is from the folder, without a
    module file's own, and the file it names is read as a mod.rs. A file reached two ways is read both ways. A
    crate root no manifest names is a file no declaration could bring in; a file no declaration reaches from the
    roots looks in its own folder first, then beside itself."""
    known = set(p for p in tracked if p.endswith(".rs"))
    manifests = [p for p in tracked if posixpath.basename(p) == "Cargo.toml"]
    texts = read(sorted(known) + manifests) if known else {}
    known, manifests = set(p for p in known if p in texts), [p for p in manifests if p in texts]
    links, tree = links or {}, {}  # The links, by their paths' parts, None at each's end.
    for link in links:
        node = tree
        for part in link.split("/"):
            node = node.setdefault(part, {})
        node[None] = link

    def resolve(path):
        """The path a path names past the links on its way, each time the first, or None: out of the repo, rooted,
        or past 40 of them."""
        for _ in range(40):
            node, parts = tree, path.split("/")
            for k, part in enumerate(parts):
                node = node.get(part)
                if node is None or None in node:
                    break
            if node is None or None not in node:
                return path
            target = links[node[None]]
            path = None if re.match(r"/|[A-Za-z]:", target) else posixpath.normpath(
                posixpath.join(posixpath.dirname(node[None]), target, *parts[k + 1:]))
            if path is None or path == ".." or path.startswith("../"):
                return None
        return None

    # A link to a tracked .rs file is that file at the link's own path, as rustc reads it, its declarations read
    # from there too, as code.
    linked = set()
    for link in sorted(links):
        target = resolve(link) if link.endswith(".rs") and link not in known else None
        if target in known:
            linked.add(link)
            texts[link] = texts[target]
    known |= linked
    parsed = dict((p, rust_modules(t)) for p, t in texts.items() if p in known and any(r.search(t) for r in RUST_READ))
    # The folders the tracked files are in, numbered, each with its parent and its files and folders by name. A folder
    # elsewhere is one of these and a count of the folders under it that hold none: (number, count). Numbered in
    # order, each folder's own are below it, up to the last of them (last); and each has its name (names).
    parent, child, files, own, last, names = [None], {}, {}, {}, [0], [None]
    for path in sorted(set(known) | set(manifests)):
        folder = 0
        for part in path.split("/")[:-1]:
            if (folder, part) not in child:
                child[(folder, part)] = len(parent)
                parent.append(folder)
                last.append(len(parent) - 1)
                names.append(part)
            folder = child[(folder, part)]
        own[path] = folder
        if path in known:
            files[(folder, posixpath.basename(path))] = path

    def down(where, name):
        if where is None:
            return None
        if not where[1] and (where[0], name) in child:
            return child[(where[0], name)], 0
        return where[0], where[1] + 1

    def walk(where, path):
        """The folder a path names from where, or None outside the repo or at an absolute path."""
        if path.startswith("/") or re.match(r"[A-Za-z]:", path):
            return None
        for part in path.split("/"):
            if where is None or part in ("", "."):
                continue
            if part != "..":
                where = down(where, part)
            elif where[1]:
                where = where[0], where[1] - 1
            else:
                where = (parent[where[0]], 0) if parent[where[0]] is not None else None
        return where

    def file_in(where, name):
        return files.get((where[0], name)) if where is not None and not where[1] else None

    def find(where, path):
        """The tracked .rs file a path names from where: as it is, as rustc reads it on Unix, else with each \\ a /,
        as on Windows."""
        for each in (path, path.replace("\\", "/")) if "\\" in path else (path,):
            head, _, name = each.rpartition("/")
            found = file_in(walk(where, head), name) if name not in ("", ".", "..") else None
            if found:
                return found
        return None

    manifest_of, code = cargo_roots(dict((p, texts.get(p, "")) for p in manifests), lambda p: (own[p], 0), find)
    manifest_at = dict((own[p], p) for p in manifests)
    has_manifest = set(own[p] for p in manifests)
    covered = [False] * len(parent)  # Per folder, whether a manifest is in it or above it.
    for folder in range(len(parent)):
        covered[folder] = folder in has_manifest or (parent[folder] is not None and covered[parent[folder]])
    package_at = {}

    def package(folder):
        """The folder of the manifest at or above a folder, or None."""
        seen = []
        while folder is not None and folder not in package_at:
            if folder in has_manifest:
                package_at[folder] = folder
                break
            seen.append(folder)
            folder = parent[folder]
        top = package_at[folder] if folder is not None else None
        for each in seen:
            package_at[each] = top
        return top

    # Where Cargo looks for a crate's roots by default, beside its manifest: src/lib.rs, src/main.rs, src/bin/x.rs,
    # src/bin/x/main.rs, build.rs, and x.rs or x/main.rs in the folders examples, benches and tests (tests' roots).
    # A file in one of those places but a test's with no manifest beside or above it, where it can't be known, is
    # taken for a crate's.
    for path in known:
        parts = path.split("/")
        name, folders, tests = parts[-1], parts[:-1], False
        if name == "build.rs":
            up = 0
        elif folders[-1:] == ["src"] and name in ("lib.rs", "main.rs"):
            up = 1
        elif folders[-2:] == ["src", "bin"]:
            up = 2
        elif folders[-1:] in (["examples"], ["benches"], ["tests"]):
            up, tests = 1, folders[-1] == "tests"
        elif name == "main.rs" and folders[-3:-1] == ["src", "bin"]:
            up = 3
        elif name == "main.rs" and folders[-2:-1] in (["examples"], ["benches"], ["tests"]):
            up, tests = 2, folders[-2] == "tests"
        else:
            continue
        top = own[path]
        for _ in range(up):
            top = parent[top]
        if top in has_manifest or not (covered[top] or tests):
            manifest_of.setdefault(path, manifest_at.get(top))
            if not tests:
                code.add(path)
    roots = set(manifest_of) | linked
    code |= linked

    def states(path, kind):
        """Per scope of a file read as a mod.rs or a module file, its folder, the name its own folder adds, and
        whether a declaration without #[path] may be read there."""
        out = [((own[path], 0), posixpath.basename(path)[:-3] if kind == "module" else None, True)]
        for up_scope, what, value in parsed[path][1][1:]:
            where, relative, owned = out[up_scope]
            if what == "module":
                out.append((down(down(where, relative) if owned and relative else where, value), None, owned))
            elif what == "path":
                out.append((walk(where, value), None, True))
            else:
                out.append((where, None, False))
        return out

    def targets(state, declaration):
        """The files a declaration brings in, read in a state, each with how rustc reads it, whether it's brought
        in only for tests, and whether by the declaration's own attributes, not only the code it's in."""
        name, path, scope, test, choices, own = declaration
        where, relative, owned = state[scope]
        found = [(find(where, choice), "mod-rs", test or terms[0], own or terms[0]) for choice, terms in choices]
        default = any(terms[1] for _, terms in choices)  # The default where no cfg_attr's path applies.
        test, own = test or default, own or default
        if path is not None:
            found.append((find(where, path), "mod-rs", test, own))
        elif owned:
            base = down(where, relative) if relative else where
            module = file_in(base, name + ".rs")
            found.append((module, "module", test, own) if module else
                         (file_in(down(base, name), "mod.rs"), "mod-rs", test, own))
        return [f for f in found if f[0]]

    declarations = lambda path: parsed[path][2]

    # A crate root no manifest names: a file no declaration could bring in, read either way. And those a file of
    # another package brings in, whose macros may reach it.
    # Per package, those whose files its crates may compile other than for tests alone (joins); and each file a
    # declaration or an include! brings in from another package's folder, with its file and whether only for tests
    # (crossed). A link's file declares from where the link is.
    maybe, crossing, joins, crossed = set(), set(), {}, []

    def cross(source, target, test=None):
        if package(own[source]) != package(own[target]):
            crossing.add(target)
            crossed.extend([(source, target, test)] if test is not None else [])

    for path in parsed:
        for kind in ("mod-rs", "module"):
            state = states(path, kind)
            for declaration in declarations(path):
                for target in targets(state, declaration):
                    maybe.add(target[0])
                    cross(path, target[0], target[2])
            for k, scope in enumerate(parsed[path][1]):  # An inline module whose #[path] names another's folder.
                if scope[1] == "path" and state[k][0] is not None and package(state[k][0][0]) != package(own[path]):
                    joins.setdefault(package(own[path]), set()).add(package(state[k][0][0]))
    tested = roots - code  # The crates Cargo builds only as tests, whose code is a test's.
    roots |= set(p for p in parsed if p not in maybe)
    # Per folder and first part, the folders that hold it, up from there; per folder, those above it; per name, the
    # folders that hold a file or a folder so named.
    holding, above, holders = {}, {}, {}
    for folder, name in list(child) + list(files):
        holders.setdefault(name, []).append(folder)

    def nearby(folder, path):
        """The tracked files a path names from a folder or any folder above it: looked for only from those that
        hold its first part, found once per folder and first part, as rustc reads it on Unix, else on Windows."""
        found = []
        for each in sorted(set([path, path.replace("\\", "/")])):
            parts, start = each.split("/"), folder
            while parts and parts[0] in (".", ".."):  # From each folder above, ../x is x from the one above that.
                start = parent[start] if parts.pop(0) == ".." and start is not None else start
            if start is None or not parts:
                continue
            key = (start, parts[0])
            if key not in holding:
                if start not in above:  # It and the folders above it, the nearest first, and where each is.
                    chain, up = [], start
                    while up is not None:
                        chain.append(up)
                        up = parent[up]
                    above[start] = (chain, dict((up, k) for k, up in enumerate(chain)))
                chain, ups = above[start]
                held = holders.get(parts[0], ())
                holding[key] = sorted((up for up in held if up in ups), key=ups.get) if len(held) < len(chain) \
                    else [up for up in chain if (up, parts[0]) in child or (up, parts[0]) in files]
            found += [t for t in (find((up, 0), "/".join(parts)) for up in holding[key]) if t]
        return found

    # What code outside tests include!s is code: the file a whole argument names, from the file's folder; and, where
    # the argument is built (concat!(env!("CARGO_MANIFEST_DIR"), "/src/x.rs")), the file one of its strings names
    # from the package's folder, or with no manifest above it, from the file's folder or any folder above it. Its
    # declarations are read as code too, from its own folder, as a mod.rs's, as rustc reads them (inclusions).
    inclusions = set()
    for path in parsed:
        for included, whole in parsed[path][3]:
            found = []
            if whole:
                found = [find((own[path], 0), included)]
            elif included.endswith(".rs"):
                if not included.startswith(("/", "\\")):  # With no root, from the file's folder too, as rustc reads it.
                    found.append(find((own[path], 0), included))
                top = package(own[path])
                found += [find((top, 0), included.lstrip("/\\"))] if top is not None else \
                    nearby(own[path], included.lstrip("/\\"))
            code.update(t for t in found if t)
            inclusions.update(t for t in found if t)
            for target in found:  # Code: rustc finds what they declare from their own folder.
                cross(path, target, False) if target else None
    # What a tracked link names, a file or a folder's files, through any link on its way, not out of the repo, may be
    # brought in through it, so it's code.
    ordered, followed = sorted(known - linked), set()
    for link in sorted(links):
        path = resolve(link)
        if path is None or path in followed:
            continue
        followed.add(path)
        code.update([path] if path in known else [])
        crossing.update([path] if path in known else [])
        under = "" if path == "." else path + "/"
        for k in range(bisect.bisect_left(ordered, under), len(ordered)):
            if not ordered[k].startswith(under):
                break
            code.add(ordered[k])
            crossing.add(ordered[k])
    # The files another package's crate may compile, by a declaration, an include! or a link, and those they bring
    # in: their macros may reach it.
    shared, stack = set(), sorted(crossing)
    while stack:
        path = stack.pop()
        if path not in shared:
            shared.add(path)
            for kind in ("mod-rs", "module") if path in parsed else ():
                state = states(path, kind)
                stack += [t[0] for declaration in declarations(path) for t in targets(state, declaration)]
    for source, target, test in crossed:  # But from a test crate's root (a marked file's all need test).
        if not test and source not in tested:
            joins.setdefault(package(own[source]), set()).add(package(own[target]))
    for folder in range(len(parent) - 1, 0, -1):
        last[parent[folder]] = max(last[parent[folder]], last[folder])
    named, tops, trie, taken = {}, sorted(has_manifest), {}, {}
    for path in sorted(known):  # Per name, the files and folders so named, each with the folder above.
        named.setdefault(posixpath.basename(path), []).append((path, own[path]))
    for (above, name), folder in child.items():
        named.setdefault(name, []).append((folder, above))

    def take(skips, low, high):
        """The numbers from low to below high not taken before, each taken now: one taken points past itself."""
        found, at = [], low
        while True:
            end = at
            while end in skips:
                end = skips[end]
            while at in skips and skips[at] != end:  # The way shortened.
                skips[at], at = end, skips[at]
            if end >= high:
                return found
            found.append(end)
            skips[end], at = end + 1, end + 1

    def under(folder):
        """The packages of the files in a folder and below it: its own, and those of the manifests below it not
        given before."""
        low, high = bisect.bisect_left(tops, folder), bisect.bisect_right(tops, last[folder])
        return set([package(folder)] + [tops[k] for k in take(taken, low, high)])

    def ending(parts):
        """The files and folders whose paths end in parts, by a tree of names from the end, each node opened once:
        a node is [per name, the node one name up, or None till opened; its files and folders, each with the folder
        whose name is next up, or the top; those in folder order, and their folders, once read; and those taken]."""
        node = trie.get(parts[-1])
        if node is None:
            node = trie[parts[-1]] = [None, named.get(parts[-1], []), None, None, {}]
        for part in reversed(parts[:-1]):
            if node[0] is None:
                node[0] = {}
                for target, above in node[1]:
                    if above:
                        node[0].setdefault(names[above], [None, [], None, None, {}])[1].append((target, parent[above]))
            node = node[0].get(part)
            if node is None:
                return None
        return node

    def lands(path, string):
        """The packages a path attribute's string may name a file in, from a file's folder, or from any (path None):
        those of the files, and the folders' files, whose paths end in it, under the folder its leading ..s climb
        to, whatever the inline modules it's in add, each file and folder taken once per path; a rooted one names
        none."""
        found = set()
        for each in set([string, string.replace("\\", "/")]):
            if not each or re.match(r"/|[A-Za-z]:", each):
                continue
            rest, base = posixpath.normpath(each), 0 if path is None else own[path]
            while rest == ".." or rest.startswith("../"):
                rest, base = rest[3:] or ".", parent[base] if base else 0
            if rest == ".":  # The folder itself.
                found |= under(base)
                continue
            node = ending(tuple(rest.split("/")))
            if node is None:
                continue
            if node[2] is None:  # In folder order, once: a file by its folder.
                node[2] = sorted((t if isinstance(t, int) else own[t], str(t), t) for t, _ in node[1])
                node[3] = [entry[0] for entry in node[2]]
            for k in take(node[4], bisect.bisect_left(node[3], base), bisect.bisect_right(node[3], last[base])):
                target = node[2][k][2]
                found |= under(target) if isinstance(target, int) else set([package(own[target])])
        return found

    def compiled(packages):
        """The files of other packages the crates of packages bring in other than for tests, and theirs."""
        found, stack = set(), sorted(t for s, t, test in crossed if not test and package(own[s]) in packages)
        while stack:
            path = stack.pop()
            if path not in found:
                found.add(path)
                for kind in ("mod-rs", "module") if path in parsed else ():
                    state = states(path, kind)
                    stack += [t[0] for declaration in declarations(path) for t in targets(state, declaration)]
        return found

    macro = macro_packages(texts, sorted(known), lambda path: package(own[path]), shared, lands, compiled)
    # And a package another's crate compiles files of, where that one's macros may be called, is one too.
    stack = sorted(macro, key=str)
    while stack:
        for other in sorted(joins.get(stack.pop(), set()) - macro, key=str):
            macro.add(other)
            stack.append(other)
    # Each file is read once per way it's brought in (a reading: the file, and "root", "included", for a file code
    # include!s, read as a mod.rs as code whatever Cargo builds it as, "mod-rs", "module", or None for a file no
    # reading reaches, read as either), each declaration in it pointing to a reading of its file.
    queue = sorted([(p, "root") for p in roots if p in parsed] + [(p, "included") for p in inclusions if p in parsed],
                   reverse=True)
    done = set(queue) | set((p, "root") for p in roots)
    # Per reading brought in, per declaration (the reading it's in, its number), whether it needs test, and whether
    # by its own attributes.
    edges, fresh = {}, []

    def brought(reading):
        """Per declaration of a reading, its number and the files it brings in."""
        path, kind = reading
        found_in = [states(path, "module"), states(path, "mod-rs")] if kind is None and \
            posixpath.basename(path) != "mod.rs" else [states(path, "module" if kind == "module" else "mod-rs")]
        for number, declaration in enumerate(declarations(path)):
            yield number, next((f for f in (targets(s, declaration) for s in found_in) if f), [])

    def drain():
        while queue:
            reading = queue.pop()
            for number, found in brought(reading):
                for target, read_as, test, own in found:
                    declared = edges.setdefault((target, read_as), {})
                    was = declared.get((reading, number), (True, True))
                    declared[(reading, number)] = (was[0] and test, was[1] and own)
                    if target in parsed and (target, read_as) not in done:
                        done.add((target, read_as))
                        queue.append((target, read_as))
                        fresh.append(target)

    drain()
    # A file no reading reaches is read as either, but only once no other such file could bring it in, so that a
    # declaration that does decides how it's read, whatever the files' names; where each one left could be brought
    # in by another (a cycle), each of them is.
    left = set(p for p in parsed if not any((p, kind) in done for kind in ("root", "mod-rs", "module")))
    brings, could = {}, {}  # Per file left, those left it could bring in; and how many could bring it in.
    for path in left:
        brings[path] = set(t[0] for _, found in brought((path, None)) for t in found if t[0] in left and t[0] != path)
        for target in brings[path]:
            could[target] = could.get(target, 0) + 1
    ready = set(p for p in left if not could.get(p))
    while left:
        for path in sorted(ready & left or left):
            done.add((path, None))
            queue.append((path, None))
            fresh.append(path)
        ready = set()
        drain()
        for path in set(fresh) & left:
            left.discard(path)
            for target in brings[path]:
                could[target] -= 1
                if not could[target]:
                    ready.add(target)
        del fresh[:]
    # The readings only for tests: a test crate's root, and each whose declarations all need test or are in such
    # readings, from those up (a marked file's declarations all need test). Another root's isn't.
    marked = set(p for p in parsed if parsed[p][0])
    waiting, unmet = {}, {}
    for target, declared in edges.items():
        unmet[target] = sum(1 for test, _ in declared.values() if not test)
        for (source, _), (test, _) in declared.items():
            if not test:
                waiting.setdefault(source, []).append(target)
    # Where a macro may declare modules, none of its readings is a test's, a test crate's root's but for itself.
    tests = sorted((r for r in done | set(edges) if (not unmet.get(r, 1) or (r[1] == "root" and r[0] in tested)) and
                    package(own[r[0]]) not in macro), key=str)
    seen, k = set(tests), 0
    while k < len(tests):
        for target in waiting.get(tests[k], ()):
            unmet[target] -= 1
            if not unmet[target] and target not in seen and package(own[target[0]]) not in macro:
                seen.add(target)
                tests.append(target)
        k += 1
    # A file is a test when it's marked, or when every reading of it is a test's, and it's no crate's or included.
    readings = {}
    for reading in done | set(edges):
        readings.setdefault(reading[0], []).append(reading)
    found = {}
    for path in sorted(readings):
        if path in marked or (path not in code and all(r in seen or (r == (path, "root") and path in tested)
                                                        for r in readings[path])):
            # Per declaration bringing it in, whether its own attributes need test, not only the code it's in.
            sources = [(source, test and own) for r in readings[path]
                       for (source, _), (test, own) in edges.get(r, {}).items()]
            found[path] = ("marked" if path in marked else "crate" if path in tested else "declared",
                           frozenset(source[0] for source, _ in sources),
                           frozenset(source[0] for source, test in sources if not test))
            if found[path][0] == "crate":
                found[path] = found[path][:2] + (manifest_of.get(path),)
    return found


def and_list(names):
    """Names joined by commas and an and."""
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]


def rust_test_reason(path, modules):
    """Why one of Rust's test modules (rust_test_modules) is one, said of that file: by its own #![cfg(test)], as a
    crate its manifest builds only as a test, or by the declarations that bring it in, each needing test by its
    cfg or by the code it's in, which is then compiled only for tests itself."""
    how, declared, detail = modules[path]
    if how == "marked":
        return "Rust compiled only for tests, by the inner cfg at its top that needs test"
    if how == "crate":
        return "a Rust crate Cargo builds only as a test" + (", by %s" % detail if detail else "")
    by_cfg, in_tests = sorted(declared - detail), sorted(detail)
    return "one of Rust's test modules, " + ", and ".join(
        (["declared only for tests, in " + and_list(by_cfg)] if by_cfg else []) +
        (["declared in %s, in code compiled only for tests" % and_list(in_tests)] if in_tests else []))


def a_few(paths):
    """The first five paths, and how many more."""
    return and_list(paths[:5] + (["%d more" % (len(paths) - 5)] if len(paths) > 5 else []))


def rust_tests_said(found, modules, listed):
    """For the Test files line, the files found that are tests by Rust's declarations and not by their names, a few
    of each kind, and why: by their declarations, by their own #![cfg(test)], or as Cargo's test crates; and listed,
    where to see every one."""
    declared, marked, crates = (sorted(p for p in found if modules[p][0] == how)
                                for how in ("declared", "marked", "crate"))
    parts = [("1 of them a Rust test module in a file of its own, known by its declaration, not its name: "
              if len(declared) == 1 else "%d of them Rust test modules in files of their own, known by their "
              "declarations, not their names: " % len(declared)) + a_few(declared)] if declared else []
    parts += [("1 of them Rust compiled only for tests by the inner cfg at its top that needs test: " if
               len(marked) == 1 else "%d of them Rust compiled only for tests, each by the inner cfg at its top that "
               "needs test: " % len(marked)) +
              a_few(marked)] if marked else []
    parts += [("1 of them a Rust crate Cargo builds only as a test: " if len(crates) == 1 else "%d of them Rust "
               "crates Cargo builds only as tests: " % len(crates)) + a_few(crates)] if crates else []
    return "".join("; " + part for part in parts) + (". " + listed if parts else "")


def test_reason(path, more=(), not_tests=(), modules=()):
    """Why a file is set aside as a test (is_test), or None if it isn't."""
    if named(path, not_tests):
        return None
    folder = next((part for part in path.split("/")[:-1] if part.lower() in TEST_FOLDERS), None)
    if folder:
        return "in a folder named %s" % folder
    pattern = next((p for p in TEST_NAMES + list(more) if named(path, [p])), None)
    if pattern:
        return ("named like a test (%s)" if pattern in TEST_NAMES else "by --test %s") % pattern
    return rust_test_reason(path, modules) if path in modules else None


def rust_read_differs(repo):
    """How many of the tracked .rs files, Cargo.toml manifests and symbolic links the working tree changes against
    HEAD, as measure.py reads them: a rename's two paths each counted, whatever git's diff.renames; a file git takes
    as unchanged (assume-unchanged, or skip-worktree where it's there) that the working tree changes; and a link the
    index changes."""
    found = git(repo, "diff", "--name-only", "-z", "--no-renames", "HEAD", "--", "*.rs", "Cargo.toml", "*/Cargo.toml")
    if found.returncode:
        return 0
    names = set(name for name in found.stdout.decode("utf-8", "replace").split("\0") if name)
    hidden = [entry[2:] for entry in (run(repo, "ls-files", "-v", "-z") or "").split("\0")
              if (entry[:1].islower() or entry[:2] == "S ") and
              (entry.endswith(".rs") or posixpath.basename(entry[2:]) == "Cargo.toml")]
    head = texts_at(repo, "HEAD", hidden) if hidden else {}
    for path in hidden:
        try:
            with open(os.path.join(repo, path), "rb") as f:
                data = f.read()
        except OSError:  # Not there: a sparse checkout's, read from the index, as git's diff does.
            continue
        if head.get(path) != (data.decode("utf-8", errors="replace") if b"\0" not in data[:8000] else None):
            names.add(path)
    now, then = tracked_links(repo), tracked_links(repo, "HEAD")
    names.update(p for p in set(now) | set(then) if now.get(p) != then.get(p))
    return len(names)


OBJECT = re.compile(r"[0-9a-f]{7,64}")


def blobs(repo, names):
    """The texts of the objects git's names give (rev:path, :path for the index's, or a hash), read in one batch:
    per name, its text, or None for one missing, not a file's or binary."""
    if not names:
        return []
    data = git(repo, "cat-file", "--batch", input="".join(n + "\n" for n in names).encode()).stdout
    found, pos = [], 0
    for _ in names:
        end = data.index(b"\n", pos)
        header = data[pos:end].split(b" ")
        pos = end + 1
        if len(header) != 3 or not OBJECT.fullmatch(header[0].decode()) or not header[2].isdigit():
            found.append(None)
            continue
        size = int(header[2])
        blob = data[pos:pos + size]
        pos += size + 1
        found.append(blob.decode("utf-8", errors="replace") if header[1] == b"blob" and b"\0" not in blob[:8000]
                     else None)
    return found


def texts_at(repo, rev, paths):
    """The texts of the files at rev, or in the index for "", of those asked for, read in one batch; one missing
    there, or binary, is left out. One whose name holds a newline, which the batch can't take, by its object."""
    wanted, odd = [p for p in paths if "\n" not in p], set(p for p in paths if "\n" in p)
    found = list(zip(wanted, blobs(repo, ["%s:%s" % (rev, p) for p in wanted])))
    if odd:
        objects = {}
        listing = run(repo, *(["ls-tree", "-r", "-z", rev] if rev else ["ls-files", "-s", "-z"])) or ""
        for entry in listing.split("\0"):
            info, _, path = entry.partition("\t")
            fields = info.split(" ")
            if path in odd and len(fields) == 3:
                objects[path] = fields[2] if rev else fields[1]
        found += list(zip(objects, blobs(repo, list(objects.values()))))
    return dict((p, t) for p, t in found if t is not None)


def tracked_links(repo, rev=None):
    """The symbolic links git tracks, at rev or else in the index, each with the path it holds."""
    command = ["ls-tree", "-r", "-z", rev] if rev else ["ls-files", "-s", "-z"]
    objects = {}
    for entry in (run(repo, *command) or "").split("\0"):
        info, _, path = entry.partition("\t")
        fields = info.split(" ")
        if path and fields[0] == "120000" and len(fields) == 3:
            objects[path] = fields[2] if rev else fields[1]
    return dict((p, t) for p, t in zip(objects, blobs(repo, list(objects.values()))) if t is not None)


def tracked_files(repo, rev=None):
    """The files git tracks: at rev, or else in the index; not symbolic links or submodules."""
    # Each entry is "<mode> <type> <object>\t<path>" from ls-tree, "<mode> <object> <stage>\t<path>" from
    # ls-files, where a file in a merge conflict has an entry per stage.
    command = ["ls-tree", "-r", "-z", rev] if rev else ["ls-files", "-s", "-z"]
    files = []
    for entry in (run(repo, *command) or "").split("\0"):
        info, _, path = entry.partition("\t")
        if path and info.split(" ")[0] not in NOT_FILES:
            files.append(path)
    return list(dict.fromkeys(files))


# Where the skill's own repo keeps it, and the record an installer writes into each copy it makes.
SOURCE = "skills/refactor-pass"
RECORD = ".install.json"


def own_folders(tracked, scopes):
    """The folders that hold a copy of this skill inside the repo, as a project keeps it (such as
    .agents/skills/refactor-pass), known by its files; less any that a scope names, or is inside. Not the
    skill's source: its own repo keeps it in skills/refactor-pass at the top, where an agent's copy never
    is, unless an installer put one there, as its record says. (A copy put there by hand would count.)"""
    marks = ("SKILL.md", "scripts/heatmap.py", "scripts/scoping.py")
    paths = set(tracked)
    folders = sorted(p[:-len("/SKILL.md")] for p in paths if p.endswith("/SKILL.md")
                     and all(p[:-len("SKILL.md")] + m in paths for m in marks[1:]))
    folders = [f for f in folders if f != SOURCE or f + "/" + RECORD in paths]
    return [f for f in folders if not any(s == f or s.startswith(f + "/") for s in scopes)]


def leave_own_out(paths, tracked, scopes):
    """The paths without the copies of this skill in the repo, and the folders that held some of them."""
    folders = own_folders(tracked, scopes)
    kept = [p for p in paths if not any(p.startswith(f + "/") for f in folders)]
    return kept, [f for f in folders if any(p.startswith(f + "/") for p in paths)]


def prefix(start):
    """The folder -C names, from the repo's top, as git rev-parse --show-prefix gives it ("" at the top)."""
    return (facts(start) or {}).get("prefix", "").strip()


def ways_to_read(start, repo, given):
    """The paths from the repo's top that given could mean, likeliest first. It may be written
    ./x or x/, as an absolute path, or from the folder -C names when that's inside the repo.
    Paths are compared as git writes them, with forward slashes, on any system."""
    if os.path.isabs(given):
        try:
            inside = os.path.relpath(os.path.realpath(given), os.path.realpath(repo))
        except ValueError:  # On Windows, another drive: outside the repo.
            inside = os.path.join(os.pardir, os.path.basename(given))
        return [posixpath.normpath(inside.replace(os.sep, "/"))]
    given = given.replace(os.sep, "/")
    under = prefix(start)
    return [posixpath.normpath(way) for way in ([posixpath.join(under, given)] if under else []) + [given]]


def show_path(start, repo, given, tracked):
    """A file named for --show, as a path from the repo's top."""
    ways = ways_to_read(start, repo, given)
    return next((way for way in ways if way in tracked), ways[-1])


# A script element's end tag and its start tag, as HTML's tokenizer reads them in a script's text: in any case,
# followed by a space, a / or a >.
SCRIPT_END = re.compile(r"</script[\t\n\f\r />]", re.I)
SCRIPT_START = re.compile(r"<script[\t\n\f\r />]", re.I)
ESCAPED = re.compile(r"<|-->")


def script_end(text, start):
    """Where a browser ends a script element whose text starts at start, as HTML's tokenizer reads a script's
    text, or -1 if it never does; and where the <!-- and the <script began that hid an end tag before that,
    or None. A script ends at its first end tag (SCRIPT_END), but after a <!--, a <script hides the end tags
    after it, until one of them, or a -->, as the escapes of old scripts did."""
    state, i, hidden, escape_at, double_at = "data", start, None, -1, -1
    while True:
        if state == "data":
            j = text.find("<", i)
            if j < 0:
                return -1, hidden
            if SCRIPT_END.match(text, j):
                return j, hidden
            i = j + 1
            if text.startswith("<!--", j):
                state, escape_at, i = "escaped", j, j + 4
                while text.startswith("-", i):
                    i += 1
                if text.startswith(">", i):  # <!--> and <!---> close at once.
                    state, i = "data", i + 1
            continue
        found = ESCAPED.search(text, i)
        if not found:
            return -1, hidden
        j, i = found.start(), found.start() + 1
        if found.group() == "-->":
            state, i = "data", found.end()
        elif state == "escaped" and SCRIPT_END.match(text, j):
            return j, hidden
        elif state == "escaped" and SCRIPT_START.match(text, j):
            state, double_at, i = "double", j, j + 8
        elif state == "double" and SCRIPT_END.match(text, j):
            hidden = hidden or (escape_at, double_at)
            state, i = "escaped", j + 9


def unknown_file(path, known, repo, where):
    """What to say when --show names a file that's none of known, with the one likeliest meant, if any."""
    near = difflib.get_close_matches(path, sorted(known), n=1, cutoff=0.8)
    return "%s: --show %s names no file git tracks in %s, nor one %s%s" % (
        os.path.basename(sys.argv[0]), path, os.path.basename(repo), where,
        "; did you mean %s?" % near[0] if near else ".")


def resolve(start, repo, scopes, tracked):
    """The scopes as paths from the repo's top. A scope that matches no tracked file stops the run,
    saying what exists instead, so an empty table never passes for a cold one."""
    resolved, problems = [], []
    for given in scopes:
        ways = [way for way in ways_to_read(start, repo, given) if not way.startswith("..")]
        found = next((way for way in ways if any(in_scope(p, [way]) for p in tracked)), None)
        if found:
            resolved.append(found)
            continue
        if not ways:
            problems.append("%s is outside the repo, %s." % (given, repo))
            continue
        near = next((p[:len(way)] for way in ways for p in tracked
                     if p.lower() == way.lower() or p.lower().startswith(way.lower() + "/")), None)
        if near:
            hint = "did you mean %s? Scopes are matched with case." % near
        else:
            folders = sorted(set(p.split("/")[0] for p in tracked if "/" in p))
            hint = "its top-level folders are %s%s." % (", ".join(folders[:20]) or "(none)",
                                                       ", ..." if len(folders) > 20 else "")
        under = " (read from %s, the folder -C names, and from the top)" % prefix(start).rstrip("/") \
            if len(ways) > 1 else ""
        problems.append("%s%s matches no file git tracks in %s; %s" % (given, under, os.path.basename(repo), hint))
    if problems:
        sys.exit("\n".join("%s: the scope %s" % (os.path.basename(sys.argv[0]), p) for p in problems))
    return resolved
