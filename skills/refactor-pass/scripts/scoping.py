# Copyright (c) 2026 Armand Kaufmann. MIT License: https://github.com/armandkaufmann/refactor-pass
"""Which of a repo's files a refactor pass counts, shared by heatmap.py and measure.py.

The scope (folders or globs), the files never worth a refactor, copies of
this skill kept inside the repo, and the tests, which are set
aside by name or folder so that a spec beside its source doesn't swamp the
counts.
"""

import argparse
import fnmatch
import os
import posixpath
import re
import subprocess
import sys

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


def run(repo, *args):
    """A git command's output as text, or None if it failed. Git writes paths in UTF-8 whatever the
    system's code page, so they're read as UTF-8."""
    result = git(repo, *args)
    return result.stdout.decode("utf-8", errors="replace") if result.returncode == 0 else None


def toplevel(start):
    """The top of the repo that start, the folder -C names, is in; or stop with a plain message."""
    if not os.path.isdir(start):
        sys.exit("No such folder: %s" % start)
    top = (run(start, "rev-parse", "--show-toplevel") or "").strip()
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
    return (run(start, "rev-parse", "--show-prefix") or "").strip()


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
