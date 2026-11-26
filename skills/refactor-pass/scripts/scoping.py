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
# attribute's (#[ or #![), the word mod, a brace, a bracket or a ;; and anything else at once, in runs. A string is
# one of Rust's literals, whatever its prefix (b, c, r and br, cr; r#name is a name), and one never closed runs to
# the end. A file that holds none of RUST_READ isn't read so.
RUST_TOKEN = re.compile(r"""(//[^\n]*|/\*)|([bc]?r\#*")|([bc]?"(?:\\.|[^"\\])*(?:"|\\?\Z)|"""
                        r"""b?'(?:\\(?:x[0-9a-fA-F]{2}|u\{[0-9a-fA-F]{1,6}\}|.)|[^'\\\n])')|(\#!?\s*\[)|"""
                        r"""(\bmod\b)|([{}\[\];])|"""
                        r"""(?:[^/"'\#{}\[\];\w]+|(?!\bmod\b)(?![bc]?r\#*")(?![bc]?")(?!b?')\w+|/(?![/*])|"""
                        r"""'(?![^'\\\n]'|\\)|\#(?!!?\s*\[))+|\w+|.""", re.S)
# What a file must hold to be read so, each searched for on its own, the word first, so that every search takes time
# in step with the text: mod, not in a word, then a name and a ; or a comment, or a comment, or a macro's $name; an
# inner cfg; include!. A file that only calls a macro that declares modules is read too, once one is found.
RUST_READ = (re.compile(r"mod(?<![\w$]mod)(?:\s+(?:r#)?\w+\s*[;/]|\s*/|\s+\$)"), re.compile(r"#\s*!\s*\[\s*cfg"),
             re.compile(r"include\s*!"))
BLOCK_COMMENT = re.compile(r"/\*|\*/")
KINDS = (None, "comment", "raw", "string", "attribute", "mod", "bracket")
RUST_NAME = re.compile(r"\s*((?:r#)?[A-Za-z_]\w*)\s*$")
MACRO_BEFORE_BRACE = re.compile(r"(?:\w\s*!|macro_rules\s*!\s*(?:r#)?\w+)\s*$")  # pick! {, macro_rules! m {
MACRO_DEFINED = re.compile(r"\bmacro_rules\s*!\s*(?:r#)?(\w+)\s*$")
INCLUDE_AT = re.compile(r"\binclude\s*!\s*(\(\s*)?(\S?)")  # include!, its bracket, and what follows in its run.
# A macro called with words for arguments, as a macro that declares modules is (modules!(util, net)); the words.
MACRO_CALL = re.compile(r"(?<![\w$])([A-Za-z_]\w*)\s*!\s*\(([\w\s,]*)\)")
CALLED_AT = re.compile(r"(?<![\w$])([A-Za-z_]\w*)\s*!\s*$")
MACRO_NAMED = re.compile(r"(?<![\w$])([A-Za-z_]\w*)\s*!")  # A macro's name, where a file calls one.


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


def rust_attribute(tokens, opening):
    """An attribute read from tokens after its opening: its text, written for cfg_needs_test (its strings "s"); the
    file a path attribute names (#[path = "x.rs"]), or None; and the one a cfg_attr gives (#[cfg_attr(windows,
    path = "win.rs")]), or None."""
    parts, depth, parens, path, choice, first = [opening], 1, 0, None, None, True
    for kind, token in tokens:
        if kind == "bracket" and token in "[]":
            depth += 1 if token == "[" else -1
            if not depth:
                break
        if kind == "string":
            if first and re.match(r"\s*path\s*=\s*$", "".join(parts[1:])):  # Its first string only.
                path = string_text(token)
            elif choice is None and parens == 1 and re.search(r",\s*path\s*=\s*$", parts[-1]) and \
                    re.match(r"\s*cfg_attr\s*\(", parts[1]):
                choice = string_text(token)
            token, first = '"s"', False
        elif kind is None:
            parens += token.count("(") - token.count(")")
        parts.append(token)
    return "".join(parts) + "]", path, choice


def rust_modules(text):
    """A Rust file's modules as rustc reads them: (marked, scopes, declared, included, macros). marked: whether the
    whole file needs test, by #![cfg(test)] before anything else in it (past a shebang line). scopes: per block it
    opens where a mod declaration's file is found otherwise, its parent's index and what it is: ("module", name) for
    an inline module, ("path", folder) for one with a #[path], ("block", None) for a function's body or any other
    block that isn't a macro's or a module's, in which a declaration needs a #[path]; scope 0 is the file's own. A
    macro's brackets (pick! { if #[cfg(test)] { mod t; } }) open none: a declaration in them is read as if they
    weren't there, the cfg before their brace counted. declared: per mod declaration, (name, path, scope, test,
    choices, own): its #[path] or None (the first, which a cfg_attr's path before it may stand in for), the scope
    it's in, whether its cfg or the code it's in needs test, the files its cfg_attrs may name instead, each with its
    cfg's terms (cfg_terms), and whether its own attributes need test. included: outside test code, (path, whole)
    per string an include! holds, whole when the string is all its argument (include!("x.rs")), not when it's a
    part (include!(concat!(..., "/x.rs"))); none of one built on OUT_DIR, the build's output, not the package.
    macros: (defined, called): per macro_rules! it defines that declares a module of a name it's given (mod $m;),
    whether every such declaration in it needs test, and whether the macro_rules! is itself in test code; and per
    macro it calls with words (modules!(util, net)), (macro, words, scope, whether the code it's in needs test,
    whether its own cfg does)."""
    if text.startswith("\ufeff"):
        text = text[1:]
    if text.startswith("#!") and not re.match(r"#!\s*\[", text):  # A shebang line, which rustc passes over.
        text = text[text.find("\n") + 1:] if "\n" in text else ""
    scopes = [(None, None, None)]
    # Per bracket open: its scope, whether its code needs test, whether nothing but inner attributes has come in it
    # yet, whether it's a macro's, and the macro_rules! it's in, with whether that's in test code, or None.
    frames = [[0, False, True, False, None]]
    declared, included, pending, name, before, tokens = [], [], [], None, "", rust_tokens(text)
    defined, called = {}, []
    pending_test = False  # Whether an attribute pending, before the item it's on, is a cfg that needs test.
    include = None  # After include!: "open" to its argument, "inside" it past something other than a string, "out"
    start = 0  # in one built on OUT_DIR; and where its strings start in included.
    templated = None  # After mod in a macro_rules!, a $name: that macro, till the ; that makes it a declaration.
    for kind, token in tokens:
        test_code = frames[-1][1] or pending_test
        if kind == "attribute":
            attribute, path, choice = rust_attribute(tokens, token)
            if "!" in token:
                if frames[-1][2] and cfg_needs_test(attribute):
                    frames[-1][1] = True
            else:
                pending.append((attribute, path, choice))
                pending_test = pending_test or cfg_needs_test(attribute)
                frames[-1][2] = False
            before = ""
            continue
        if kind is None:
            if not token.strip():
                continue
            templated = frames[-1][4] if name == "" and frames[-1][4] and re.match(r"\s*\$\w+\s*$", token) else None
            found = RUST_NAME.match(token) if name == "" else None  # After mod, the module's name.
            name = (found.group(1)[2:] if found.group(1).startswith("r#") else found.group(1)) if found else None
            if "!" in token:
                called.extend((m.group(1), re.findall(r"\w+", m.group(2)), frames[-1][0], test_code, pending_test)
                              for m in MACRO_CALL.finditer(token))
            if len(frames[-1]) > 5 and re.match(r"[\w\s,]*$", token):
                frames[-1][5].extend(re.findall(r"\w+", token))
            at = INCLUDE_AT.search(token) if "include" in token else None
            start = len(included) if at else start
            include = ("inside" if at.group(2) else "open") if at else "out" if include == "out" else \
                "inside" if include else None
            before = token
            frames[-1][2] = False
            continue
        frames[-1][2] = False
        if kind == "mod":
            name, before = "", ""
            continue
        if kind == "string":
            if include == "inside" and string_text(token) == "OUT_DIR":
                del included[start:]  # Built on the build's output folder: no file of the repo's.
                include = "out"
            elif include and include != "out" and not test_code:
                included.append((string_text(token), include == "open"))
            include = "out" if include == "out" else "inside" if include else None
        elif token in ";{}":
            test = test_code
            if token == ";" and templated:  # mod $name; in a macro_rules!: it declares the modules it's given.
                was = defined.get(templated[0], (True, True))
                defined[templated[0]] = (was[0] and test, was[1] and templated[1])
            if token == ";":
                if name:
                    # The first #[path] counts; a cfg_attr's path before it stands in for it where its cfg holds.
                    first = next((k for k, (_, p, _) in enumerate(pending) if p is not None), len(pending))
                    path = pending[first][1] if first < len(pending) else None
                    choices = [(c, cfg_terms(a, RUST_CFG_ATTR.match(a))) for a, _, c in pending[:first]
                               if c is not None]
                    declared.append((name, path, frames[-1][0], test, choices, pending_test))
            elif token == "{":
                if name:
                    path = next((p for _, p, _ in pending if p is not None), None)
                    scopes.append((frames[-1][0], "module", name) if path is None else (frames[-1][0], "path", path))
                    frames.append([len(scopes) - 1, test, True, False, frames[-1][4]])
                elif frames[-1][3] or MACRO_BEFORE_BRACE.search(before):
                    macro = MACRO_DEFINED.search(before)
                    frames.append([frames[-1][0], test, True, True, (macro.group(1), test) if macro else frames[-1][4]])
                    call = CALLED_AT.search(before)
                    if call and not macro and call.group(1) != "include":  # modules! { util, net }
                        called.append((call.group(1), [], frames[-1][0], test, pending_test))
                        frames[-1].append(called[-1][1])
                else:
                    scopes.append((frames[-1][0], "block", None))
                    frames.append([len(scopes) - 1, test, True, False, frames[-1][4]])
            elif len(frames) > 1:
                frames.pop()
            pending, pending_test = [], False
            include = include if token == "{" and include == "open" else None
        else:  # [ or ]: include![...] opens its argument.
            include = include if token == "[" and include == "open" else None
        name, before, templated = None, "", None
    return frames[0][1], scopes, declared, included, (defined, called)


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


def rust_test_modules(tracked, read):
    """Rust's test modules in files of their own: each tracked .rs file every mod declaration of which, in a tracked
    file, needs test, by its cfg or by the code it's in (an inline module compiled only for tests, or a file that's a
    test module itself); and each marked #![cfg(test)] before anything else in it. A file Cargo builds as a crate of
    its own other than as a test (cargo_roots), or one that code outside tests include!s, is never one by its
    declarations; a crate it builds only as a test is one, as are its modules. read(paths) gives the files' texts.
    Per test module, (how, declared): how it's known, "declared", "marked" (#![cfg(test)]) or "crate" (Cargo's test
    crate), and the files whose declarations bring it in.

    A declaration's file is where rustc finds it: from a crate root's or a mod.rs's folder, or a module file's
    own (src/disk.rs's src/disk/), with each inline module's name, or its #[path], added; name.rs there, or
    name/mod.rs; or in a block (a function's body), only by its #[path]. A #[path] is from the folder, without a
    module file's own, and the file it names is read as a mod.rs. A file reached two ways is read both ways. A
    crate root no manifest names is a file no declaration could bring in; a file no declaration reaches from the
    roots looks in its own folder first, then beside itself."""
    known = set(p for p in tracked if p.endswith(".rs"))
    manifests = [p for p in tracked if posixpath.basename(p) == "Cargo.toml"]
    texts = read(sorted(known) + manifests) if known else {}
    parsed = dict((p, rust_modules(t)) for p, t in texts.items() if p in known and any(r.search(t) for r in RUST_READ))
    module_macros = set(m for p in parsed for m in parsed[p][4][0])  # The macros that declare modules, by name.
    if module_macros:  # A file that calls one is read too, for its calls. A few are each searched for by name; past
        # that, each macro a file calls is looked up once, so the time doesn't grow with the number of macros.
        few = sorted(module_macros) if len(module_macros) <= 16 else None
        calls = few and re.compile(r"(?<![\w$])(?:%s)\s*!" % "|".join(few))
        parsed.update((p, rust_modules(t)) for p, t in texts.items()
                      if p in known and p not in parsed and "!" in t and (
                          any(macro in t for macro in few) and calls.search(t) if few else
                          any(call.group(1) in module_macros for call in MACRO_NAMED.finditer(t))))
    # The folders the tracked files are in, numbered, each with its parent and its files and folders by name. A folder
    # elsewhere is one of these and a count of the folders under it that hold none: (number, count).
    parent, child, files, own = [None], {}, {}, {}
    for path in sorted(known) + manifests:
        folder = 0
        for part in path.split("/")[:-1]:
            if (folder, part) not in child:
                child[(folder, part)] = len(parent)
                parent.append(folder)
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
    roots = set(manifest_of)

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

    # The macros that declare modules where a call may be to them, as far as can be told: in their package, or, with
    # no manifest above, in their file's folder and those under it; per (package, or ("folder", folder)), macro, and
    # whether only those outside test code count, whether every module they declare needs test. A call outside test
    # code can't be to a macro_rules! that's only in test code.
    defined = {}
    for path in parsed:
        top = package(own[path])
        for macro, (test, gated) in parsed[path][4][0].items():
            for outside in (False,) if gated else (False, True):
                key = (top if top is not None else ("folder", own[path]), macro, outside)
                defined[key] = defined.get(key, True) and test
    reach = {}

    def for_tests(path, macro, outside):
        """Whether every macro of that name a call in path may be to declares only for tests; not where none may."""
        top = package(own[path])
        if top is not None:
            return defined.get((top, macro, outside), False)
        key = (own[path], macro, outside)
        if key not in reach:
            found, folder = [], own[path]
            while folder is not None:
                found += [defined[k] for k in [(("folder", folder), macro, outside)] if k in defined]
                folder = parent[folder]
            reach[key] = bool(found) and all(found)
        return reach[key]

    # Per file, its mod declarations, and the words it gives a macro that declares modules, each one of them, for
    # tests where the call is in test code or every macro it may be to declares only for tests.
    every = dict((path, parsed[path][2] + [(word, None, scope, test or template, [], own or template)
                                           for macro, words, scope, test, own in parsed[path][4][1]
                                           if macro in module_macros
                                           for template in [for_tests(path, macro, not test)] for word in words])
                 for path in parsed)
    declarations = every.__getitem__

    # A crate root no manifest names: a file no declaration could bring in, read either way.
    maybe = set()
    for path in parsed:
        for kind in ("mod-rs", "module"):
            state = states(path, kind)
            for declaration in declarations(path):
                maybe.update(t[0] for t in targets(state, declaration))
    tested = roots - code  # The crates Cargo builds only as tests, whose code is a test's.
    roots |= set(p for p in parsed if p not in maybe)
    holding = {}

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
                holding[key], up = [], start
                while up is not None:
                    holding[key] += [up] if (up, parts[0]) in child or (up, parts[0]) in files else []
                    up = parent[up]
            found += [t for t in (find((up, 0), "/".join(parts)) for up in holding[key]) if t]
        return found

    # What code outside tests include!s is code: the file a whole argument names, from the file's folder; and, where
    # the argument is built (concat!(env!("CARGO_MANIFEST_DIR"), "/src/x.rs")), the file one of its strings names
    # from the package's folder, or with no manifest above it, from the file's folder or any folder above it.
    for path in parsed:
        for included, whole in parsed[path][3]:
            if whole:
                code.update(t for t in [find((own[path], 0), included)] if t)
            elif included.endswith(".rs"):
                top = package(own[path])
                if top is not None:
                    code.update(t for t in [find((top, 0), included.lstrip("/\\"))] if t)
                else:
                    code.update(nearby(own[path], included.lstrip("/\\")))
    # Each file is read once per way it's brought in (a reading: the file, and "root", "mod-rs", "module", or None
    # for a file no reading reaches, read as either), each declaration in it pointing to a reading of its file.
    queue = sorted(((p, "root") for p in roots if p in parsed), reverse=True)
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
    tests = sorted((r for r in done | set(edges) if not unmet.get(r, 1) or (r[1] == "root" and r[0] in tested)),
                   key=str)
    seen, k = set(tests), 0
    while k < len(tests):
        for target in waiting.get(tests[k], ()):
            unmet[target] -= 1
            if not unmet[target] and target not in seen:
                seen.add(target)
                tests.append(target)
        k += 1
    # A file is a test when it's marked, or when every reading of it is a test's, and it's no crate's or included.
    readings = {}
    for reading in done | set(edges):
        readings.setdefault(reading[0], []).append(reading)
    found = {}
    for path in sorted(readings):
        if path in marked or (path not in code and all(r in seen for r in readings[path])):
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
        return "Rust compiled only for tests, by the #![cfg(test)] at its top"
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
    parts += [("1 of them Rust compiled only for tests by the #![cfg(test)] at its top: " if len(marked) == 1 else
               "%d of them Rust compiled only for tests, each by the #![cfg(test)] at its top: " % len(marked)) +
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
    """How many of the tracked .rs files and Cargo.toml manifests the working tree changes against HEAD, a rename's
    two paths each counted, whatever git's diff.renames."""
    found = git(repo, "diff", "--name-only", "--no-renames", "HEAD", "--", "*.rs", "Cargo.toml", "*/Cargo.toml")
    return len([line for line in found.stdout.decode("utf-8", "replace").splitlines() if line]) \
        if found.returncode == 0 else 0


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
