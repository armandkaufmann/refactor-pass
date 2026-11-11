"""Which of a repo's files a refactor pass counts, shared by heatmap.py and measure.py.

The scope (folders or globs), the files never worth a refactor, and the
tests, which are set
aside by name or folder so that a spec beside its source doesn't swamp the
counts.
"""

import fnmatch
import os
import posixpath
import re
import subprocess
import sys

# Never worth a refactor, whatever their churn: lock files, generated or
# minified files, and the sidecars engines write beside each asset (Godot's
# .uid and .import, Unity's .meta).
DEFAULT_IGNORE = [
    "*.lock", "package-lock.json", "pnpm-lock.yaml", "yarn.lock", "go.sum",
    "*.min.js", "*.min.css", "*.map", "*.snap", "*.uid", "*.import", "*.meta",
]
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


def run(repo, *args):
    """A git command's output as text, or None if it failed. Git writes paths in UTF-8 whatever the
    system's code page, so they're read as UTF-8."""
    result = subprocess.run(["git", "-C", repo] + list(args), capture_output=True)
    return result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else None


def in_scope(path, scopes):
    if not scopes:
        return True
    for scope in scopes:
        if scope == ".":
            return True
        if any(ch in scope for ch in "*?["):
            if fnmatch.fnmatch(path, scope):
                return True
        elif path == scope or path.startswith(scope + "/"):
            return True
    return False


def ignored(path, patterns):
    name = posixpath.basename(path)
    return any(fnmatch.fnmatch(name, p) or fnmatch.fnmatch(path, p) for p in patterns)


def named(path, patterns):
    """Whether a glob, matched with case, names the file or its path."""
    return any(fnmatch.fnmatchcase(posixpath.basename(path), p) or fnmatch.fnmatchcase(path, p) for p in patterns)


def is_test(path, more=(), not_tests=()):
    """Whether a file is a test: by its name, or by a folder it's in, unless not_tests names it."""
    if named(path, not_tests):
        return False
    if any(part.lower() in TEST_FOLDERS for part in path.split("/")[:-1]):
        return True
    return named(path, TEST_NAMES + list(more))


def doubtful_tests(tests, tracked, more=()):
    """Of the files set aside as tests, those that may not be, as (what, why), so the eye goes to
    them: a name that's a test only by a word at its end, in no folder of tests; or a folder of
    tests by its name in which no file is named like a test, such as a spec folder of specifications."""
    found, folders = [], {}
    for path in sorted(tests):
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
        if not any(named(p, TEST_NAMES + list(more)) for p in inside):
            found.append((folder + "/", "a folder named like tests, but none of its %d files is" % len(inside)))
    return found


def stem(path, test):
    """A file's name without its extension and, for a test, its marker; in lower case."""
    name = posixpath.basename(path)
    return os.path.splitext(MARKER.sub("", name, count=1) if test else name)[0].lower()


def flat(name):
    """A stem with its separators gone, so game_state, game-state and GameState read alike."""
    return re.sub(r"[^a-z0-9]", "", name)


def owns(test, path, stems):
    """Whether path is the test's own file: the same name less the test's marker; or, when no file in
    stems (the production files' flat stems) has that name, the same name and an entry point's suffix,
    as ShowDashboardTest.php and ShowDashboardController.php."""
    mine, theirs = flat(stem(test, True)), flat(stem(path, False))
    return theirs == mine or (mine not in stems and any(theirs == mine + part for part in ENTRY_POINTS))


def tracked_files(repo, rev=None):
    """The files git tracks: at rev, or else in the index."""
    command = ["ls-tree", "-r", "-z", "--name-only", rev] if rev else ["ls-files", "-z"]
    out = subprocess.run(["git", "-C", repo] + command, capture_output=True).stdout
    return [p for p in out.decode("utf-8", errors="replace").split("\0") if p]


def prefix(start):
    """The folder -C names, from the repo's top, as git rev-parse --show-prefix gives it ("" at the top)."""
    return subprocess.run(["git", "-C", start, "rev-parse", "--show-prefix"],
                          capture_output=True, text=True).stdout.strip()


def ways_to_read(start, repo, given):
    """The paths from the repo's top that given could mean, likeliest first. It may be written
    ./x or x/, as an absolute path, or from the folder -C names when that's inside the repo."""
    if os.path.isabs(given):
        return [os.path.normpath(os.path.relpath(os.path.realpath(given), os.path.realpath(repo)))]
    under = prefix(start)
    return [os.path.normpath(way) for way in ([os.path.join(under, given)] if under else []) + [given]]


def show_path(start, repo, given, tracked):
    """A file named for --show, as a path from the repo's top."""
    ways = ways_to_read(start, repo, given)
    return next((way for way in ways if way in tracked), ways[-1])


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
