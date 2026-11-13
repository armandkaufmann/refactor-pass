#!/usr/bin/env python3
# Copyright (c) 2026 Armand Kaufmann. MIT License: https://github.com/armandkaufmann/refactor-pass
"""Where a repo's changes keep landing: a heatmap from git history.

For every file still in the repo at HEAD and inside the scope, over a window
of recent commits:

  commits   how many of the window's commits changed it
  recent    how many of those were in the window's newer half, which is
            half the commits, not half the time. About half its commits
            means it's as busy as ever; few means it has cooled
  last      the date of its latest commit. Read it with recent and the
            window's dates: a file changed in a burst just as the newer
            half began counts every commit as recent, yet has gone quiet
  churn     lines added plus lines removed
  rel       churn relative to its size now: 2.0 means twice its lines were
            written or rewritten in the window. Relative churn predicts
            defects far better than absolute churn (Nagappan & Ball, 2005)
  size      its lines at HEAD
  growth    its size now less its size just before the window, under the
            name it had then (0 if it didn't exist). Just before the window
            is one commit: --since's revision, or else the first parent of
            the window's oldest commit. Where the history has merges, other
            branches' work can sit on either side of it, so growth can
            differ from what the window's own commits added and removed

Files are listed by commits times size, so the top ones are both busy and
big. A small file changed often, like a config, and a big one rarely
changed both come lower. Dates are commit dates, as the local date where
this runs, like the checklist page's own dates. git log shows author dates
by default, which a rebase or a cherry-pick keeps from the first commit
while the commit date moves on. This shows the dates given here:

  git log --date=short-local --format='%h %cd %s'

Test files are set aside, so a spec beside its source doesn't top the list:
those named as the common frameworks name them (Board.spec.ts, test_x.py,
x_test.go, XTest.php, XTests.cs...) and anything in a folder named test,
tests, __tests__, spec or the like. --test adds a pattern, --not-test keeps
a file that only looks like a test, and --keep-tests counts them all like
the rest. The output names any set aside in doubt: a name such as
ABTest.php in no folder of tests, or a spec folder in which no file is
named like a test.

Then the files that keep changing in the same commits, with two measures:
of the quieter file's commits, the share that changed both (how likely the
busier file changes when the quieter one does), and code-maat's degree,
shared commits over the two files' average. last is the date of the latest
commit that changed them together, which a refactor that took them apart
leaves in the past. Files that all pair with each
other are one row, a group, when the commits that changed all of them meet
the same thresholds; its measures count those commits. Groups that share
two files or more are listed together, as one area that keeps changing,
though no commit need have changed all of its files. Commits that
changed more than --max-files files are left out of these, and the count
says how many; in a repo that squash-merges, that can be most of them.

Last, the tests that change together with several production files besides
their own: the file of the same name less the test's marker or, when there
is none, the controller, handler or command of that name, as a feature test
names it (ShowDashboardTest.php and ShowDashboardController.php). Each is a
lead, not a verdict: a test that reaches into those files' private members
or internal paths is tied to their internals, while a broad test that
follows features through them, or follows files that already change
together, isn't.

And the fixes: of the window's counted commits, those that fixed a defect in
the project's own code, as their messages say, and per file how many of its
commits did and how many of those were in the newer half, most first. A fix
here corrects a defect in the project's own code: wrong behaviour, a crash, a
security hole, a regression; a compile or type error in the code; a guard
against a failure that could happen as the code stood; something callers
already relied on that was missing, even where the fix adds something new.
Code that builds or packages the project is its code; its manifests, CI and
dependency files aren't. A commit that changed only documentation, tests, or
CI, build or dependency files never counts, and the table of fixes by file
sets those files aside. The counts are at least that
many: many fixes don't say so, and the rest are among the commits --show
leaves unmarked. It's a lead, not a verdict. A commit counts once, the
strongest way it reads:

  revert  its subject says revert, and its body "This reverts commit <hash>"
          as git writes it, of another author's commit. A revert of a commit
          by its own author withdraws it and isn't counted; a revert of a
          revert re-lands a change and reads as that change does; a revert of
          a change to the docs or of a chore isn't a fix
  type    its subject's type says fix (fix:, fix(scope)!:, hotfix:, bugfix:,
          [fix], the bug emoji), read only where at least half the window's
          subjects carry a type, as with Conventional Commits. There another
          type (feat:, docs:, [Feature], a gitmoji ...) says it isn't a fix,
          and so do fix(deps):, fix(ci): and fix(docs):. A tag in brackets
          that isn't a type ([clang], [SPARK-1], [hotfix]) is passed over, and
          the subject read without it; an emoji that isn't a gitmoji is no type
  words   its subject says fix, bug, error, wrong, correct, crash, overflow,
          CVE, prevent, problem or mistake, in any of their forms, or 修复,
          修正, 漏洞, 问题, 越界 or 空指针; and not typo, formatting, lint,
          docs, warning, release, error message, 注释 or 文档. An issue closed
          or named (Fixed #12 --, issue #12) and code (in backticks, or an
          identifier such as should_ignore_error) say nothing

The header says how many commits read each way; the share of subjects with a
type, and so whether the count is close to complete (where 90% or more carry
one) or a floor; and how many
more close an issue without saying what kind of change, as Django's Fixed #12
does. Where most subjects are a word or two, it says the messages can't be
read for fixes, and lists no files. --no-fixes leaves it all out.

How far it goes, as measured on commits labelled by reading their message and
diff: 1,023 commits of ten public repos, labelled by one reader, and 252 of
nine others, labelled by two readers who agreed on 248. Of the commits it
reads as fixes, about 9 in 10 are fixes of the project's code (95% of the 490
the rules were written from, 96% of 180 kept aside, 91% of those that touch
the code in the nine others). How many of the fixes it finds depends on how a
repo writes its messages: nearly all where subjects carry a type (88% to 100%
in four such repos); typically a third to a half where they don't (33% to
64% in six of seven such repos, 80% in one whose subjects nearly always say
fix); 35% over the nine others, one of them typed; and none of 14 in one
whose subjects name the area and the new behaviour, and whose bodies say what
was wrong. Reading closes most of the gap: in one measurement, an agent given
those 252 commits and the definition found 72% of the fixes from their
subjects (43 of its 44 calls right) and 83% from their whole messages (all 50
calls right), and wanted the diff for 21 commits; reading as SKILL.md's step
4 does, with the diffs where the messages fell short, it found 56 of the 60
(56 of its 57 calls right), overruling four of the script's marks, and with
each file's own changes from --diffs, 55 of the 60 (55 of 56 right), reading
less than half as much. The labels it was scored against came from the same
kind of model reading the diffs, which flatters agreement: one measurement,
not an accuracy. On five of a busy project's files, judging up to 12 commits
of each (55 in all, 15 of them with their diffs) took about 60,000 tokens and
two minutes; a file's listing is a few thousand bytes (8,678 for redis's
src/server.c, whose 99 commits in an 800-commit window take 65,878).

--show FILE prints a file's commits in the window instead, newest first, to
read the reasons it keeps changing: each with its hash as git show takes it,
its date, newer or older (in the window's newer half or not), its subject,
and how it reads as a fix, or why not where it might have. --messages lists
the file's newest 12 commits, a sample to judge whole (--newest N for
another number; the first line says how many more there are), and under each
what it changed (lines added and removed in the file, and how many other
files, how many of them tests) and its message without who signed, reviewed
or co-wrote it, cut at 12 lines, so they can be read without running git
once each. Facts, not a verdict; on the commits the trace leaves unmarked,
one that changed a test too was a fix about twice as often as one that
didn't (45% against 24% in the labelled commits), and one of over 200 lines
rarely (1 of 20). --diffs SHA,SHA, with one --show, gives just those of the
commits --messages lists, each with its changes to the file under the name
it had then, cut at 60 lines, in one call. The file is one git tracks,
or one a commit in the window changed, as one deleted in it; a name a file
had before a rename in the window means it as it's named today. Any other is
an error, as a scope is.

History is followed across renames, so a file moved or renamed in the window
keeps the changes it had under its old name. Merge commits are skipped, and so
are housekeeping bots' commits (dependency updates, releases and formatting, by
dependabot, renovate, github-actions, pre-commit-ci and the like; the output
names them, and --bot NAME adds another), those the repo lists in
.git-blame-ignore-revs (bulk reformats), and those recorded on the items of the
checklists (a refactor pass's own work, which would make the files it just
refactored look hot). Any other bot counts, coding agents such as Copilot,
Claude, Devin and Jules among them: theirs are the changes a pass is about.
A recorded commit that isn't reachable from HEAD, as after a squash merge or
a rebase, gets a warning. A left out commit counts toward nothing but its
renames, and growth, being two sizes, includes what it did. Binary files,
symbolic links and submodules are left out, and so is any copy of this skill
a project keeps in the repo, unless a scope names its folder. In a shallow
clone, the commits where its history stops look as if they add every file,
so they are left out too, and the output says so. A window left empty, as with --since a pass's base just
after the pass, is a result, not an error: the output says what was left
out, and --page leaves the page as it was.

The checklists live in .refactor-pass/ at the top of the repo. In a linked
worktree, which may be removed once its work is done, a relative --page path
is written in the main checkout's .refactor-pass/, which outlives it. Every
worktree's .refactor-pass/ is read, wherever this runs, since a sandbox may
have kept a pass out of the main checkout. --checklists lists them all,
newest first, by the date in each one's name and then its number (a second
pass on one day is 2026-11-10-2.html), and names the one a new pass should
make: today's date, or the first number after it that's free. --page on a
checklist that exists refreshes its heatmap and nothing else, and says
which checklist that is. --page also writes a .gitignore into
a .refactor-pass/ folder that has none and holds nothing git tracks, so the
checklists stay out of commits and the project's own .gitignore is left
alone. If the page can't be written, as in a sandbox, it says what to do.

Usage:
  heatmap.py [options] [SCOPE ...]

SCOPE is a folder or a glob (src, lib, 'app/**/*.py'), from the repo's top or
from the folder -C names; with none, every file counts. In a glob, * matches
across folders too, so 'app/*.py' takes app/sub/deep.py; and **/ matches any
number of folders, none included, so 'app/**/*.py' takes app/main.py too.
--ignore, --test and --not-test read their globs the same way. A scope that
matches no tracked file is an error. Reads git and the checklists; writes nothing but
--page's file and that .gitignore.

Examples:
  heatmap.py src tests
  heatmap.py -n 300 --exclude-commits 9e1d16e,b7fc306 src lib
  heatmap.py --since v2.0.0 app
  heatmap.py --since "3 months ago" src
  heatmap.py --page .refactor-pass/2026-11-10.html src
  heatmap.py --show src/app/main.py
  heatmap.py --checklists
"""

import argparse
import email.utils
import json
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from itertools import combinations

# The scope, the files left out and the tests, read the same way as measure.py reads them. No
# __pycache__ is written, so a run leaves the skill's folder as it was.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scoping  # noqa: E402

# Housekeeping bots, whose commits are left out: dependency updates, releases and formatting. Matched against
# "Name <email>". Any other bot counts, coding agents among them (copilot-swe-agent[bot], claude[bot]...).
HOUSEKEEPING = re.compile(r"dependabot|renovate|github-actions|<action@github\.com>|pre-commit-ci|greenkeeper|"
                          r"snyk-bot|imgbot|all-?contributors|semantic-release-bot|release-please|depfu|pyup-bot|"
                          r"autofix-ci|restyled-io", re.I)
SHA = re.compile(r"[0-9a-f]{7,40}")
# The checklist page: its template, and the tag that opens each data block.
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "assets", "page.html")
BLOCK = '<script type="application/json" id="%s">'
FOLDER = ".refactor-pass"
# A checklist's name: the day its pass started, and a number after it for the day's second pass and on.
PAGE_NAME = re.compile(r"(\d{4}-\d{2}-\d{2})(?:-(\d+))?\.html$")
KIND_NAMES = {"R": "refactors", "F": "small fixes", "L": "later", "D": "your call"}


def git(repo, *args):
    result = scoping.git(repo, *args)
    if result.returncode != 0:
        sys.exit("git %s failed: %s" % (" ".join(args), result.stderr.decode(errors="replace").strip()))
    return result.stdout.decode("utf-8", errors="replace")


# git log as read_log reads it, whatever the user's or the repo's config says: the root commit's changes shown
# (log.showRoot), no signature checked, whose output would come first (log.showSignature), git's own diff and
# limit on renames, which change the counts (diff.algorithm, diff.renameLimit), and the subjects in UTF-8
# (i18n.logOutputEncoding), and git's own size past which a file is read as binary (core.bigFileThreshold).
# No text conversion, external diff, notes or colour either, though git leaves them
# out of --numstat today. Each commit is its hash, time, author, subject and body (the message after the
# subject, which says what a revert reverts), each after a NUL, which no message or name can hold; then its
# numstat lines, each ending with a NUL, a rename's followed by its old and its new name.
LOG = ["-c", "core.bigFileThreshold=512m", "log", "--no-merges", "-z", "-M", "-l1000", "--numstat", "--root",
       "--no-show-signature", "--no-textconv", "--no-ext-diff", "--diff-algorithm=myers", "--no-notes", "--no-color",
       "--encoding=UTF-8", "--format=%x00%H%x00%ct%x00%aN <%aE>%x00%s%x00%b"]
# git show as file_diffs reads it, whatever the config says: each commit's patch of the paths given, after a
# NUL and its hash; git's own diff, context and renames; paths quoted as git does by default, with a/ and b/
# whatever diff.noprefix, diff.mnemonicPrefix, diff.srcPrefix and diff.dstPrefix say; blank context lines as a
# space; nothing run or converted, and no colour, notes or signature; and the paths given read as names, not
# as pathspecs, so a name such as :weird.py is the file's.
DIFF = ["--literal-pathspecs", "-c", "core.bigFileThreshold=512m", "-c", "core.quotePath=true",
        "-c", "diff.suppressBlankEmpty=false", "-c", "diff.indentHeuristic=true", "-c", "diff.interHunkContext=0",
        "-c", "diff.relative=false", "-c", "diff.noprefix=false", "-c", "diff.mnemonicPrefix=false", "show",
        "--no-color", "--no-ext-diff", "--no-textconv", "--diff-algorithm=myers", "-M", "-l1000", "-U3", "--no-notes",
        "--no-show-signature", "--encoding=UTF-8", "--src-prefix=a/", "--dst-prefix=b/", "--format=%x00%H",
        "--patch"]
COMMIT = re.compile(r"[0-9a-f]{40}(?:[0-9a-f]{24})?\Z")  # A full hash, of SHA-1 or SHA-256.
NUMSTAT = re.compile(r"(\d+|-)\t(\d+|-)\t")


def read_log(repo, revs, merges=False):
    """The commits in revs, newest first: (sha, time, subject, [(path, old_path, added, removed)], author, body).
    old_path is the name before a rename, else None; added and removed are None for a binary file. Read by
    position, so a message or an author can hold any character. Merges are left out unless merges is true."""
    tokens = git(repo, *([a for a in LOG if not merges or a != "--no-merges"] + revs)).split("\0")
    commits = []
    i = 0
    while i < len(tokens):
        token = tokens[i].lstrip("\n")
        i += 1
        if not token:
            continue
        stat = NUMSTAT.match(token)
        if stat and commits:
            added, removed = stat.groups()
            path, old = token[stat.end():], None
            if path == "":  # A rename: the old and new names follow.
                old, path = tokens[i], tokens[i + 1]
                i += 2
            binary = added == "-"
            commits[-1][3].append((path, old, None if binary else int(added), None if binary else int(removed)))
        elif COMMIT.match(token) and i + 4 <= len(tokens):
            stamp, author, subject, body = tokens[i:i + 4]
            i += 4
            commits.append((token, int(stamp), subject, [], author, body))
        else:
            raise ValueError("git log printed something read_log doesn't read: %r" % token[:80])
    return commits


def bot_name(text):
    """An argparse type: a bot's name, which can't be blank, since every author's name holds a blank one."""
    if not text.strip():
        raise argparse.ArgumentTypeError("a bot's name can't be blank: it would match every commit")
    return text


# The dates --since reads, known by their form, since git reads almost anything as a date: a mistyped hash
# as now, never as 1970, 1.2 as the first of February, a week ago as now. Relative ones as git writes them
# (3 months ago, 3.days.ago, two weeks ago, last week), and the forms git's documentation gives: ISO 8601,
# with or without a time and a zone; YYYY.MM.DD, MM/DD/YYYY and DD.MM.YYYY; and RFC 2822.
RELATIVE = re.compile(r"(?:(?:\d+|one|two|three|four|five|six|seven|eight|nine|ten)[ .]+"
                      r"(?:second|minute|hour|day|week|month|year)s?[ .]+)+ago\Z|last[ .]+(?:week|month|year)\Z|"
                      r"(?:now|yesterday)\Z", re.I)
ISO_DATE = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[T ](\d{1,2}):(\d{2})(?::(\d{2})(?:\.\d+)?)?"
                      r"(?: ?(?:Z|[+-]\d{2}:?\d{2}))?)?\Z")
DAYS = [(re.compile(r"(\d{4})\.(\d{1,2})\.(\d{1,2})\Z"), (1, 2, 3)),
        (re.compile(r"(\d{1,2})/(\d{1,2})/(\d{4})\Z"), (3, 1, 2)),
        (re.compile(r"(\d{1,2})\.(\d{1,2})\.(\d{4})\Z"), (3, 2, 1))]
RFC_2822 = re.compile(r"(?:[A-Za-z]{3}, )?\d{1,2} [A-Za-z]{3} \d{4} \d{1,2}:\d{2}(?::\d{2})? [+-]\d{4}\Z")
HASH = re.compile(r"[0-9a-fA-F]{4,40}\Z|[0-9a-fA-F]{64}\Z")
# A name of a revision: one with a path, an ancestry or a reflog in it, or a version's number, as a tag's.
REF_LIKE = re.compile(r".*[/~^@:{}]|v?\d+(?:\.\d+)+(?:[-+.][\w.-]*)?\Z")


def since_date(since):
    """--since as a date for git to read, if it's one in a form this reads: as given, but a day with no time
    from its start, local time, as git would read it at the time of day it is now; or None. Stop if it's
    in such a form but isn't a real date."""
    text = since.strip()
    if RELATIVE.match(text) or (RFC_2822.match(text) and email.utils.parsedate_tz(text)):
        return text
    if text.lower() == "today":
        return "midnight"
    try:
        found = ISO_DATE.match(text)
        if found:
            numbers = [int(n) for n in found.groups() if n is not None]
            datetime(*numbers)
            return text if found.group(4) else "%04d-%02d-%02d 00:00:00" % tuple(numbers)
        for pattern, order in DAYS:
            found = pattern.match(text)
            if found:
                day = datetime(*[int(found.group(n)) for n in order])
                return day.strftime("%Y-%m-%d 00:00:00")
    except ValueError:
        sys.exit("--since %s isn't a real date." % since)
    return None


def window_revs(repo, since, count):
    """The git log arguments for the window; the commit just before it if --since named a revision; and the
    local time --since came to, as 2026-06-01 00:00, if it's a date. --since takes a revision, or else a
    date in a form since_date reads."""
    if not since:
        return ["-n", str(count), "HEAD"], None, None
    check = scoping.git(repo, "rev-parse", "--verify", "--quiet", since + "^{commit}")
    if check.returncode == 0:
        return ["%s..HEAD" % since], check.stdout.decode().strip(), None
    date = since_date(since)
    if date is None:
        later = "Give a commit, tag or branch that's here, or a date such as '3 months ago' or 2026-06-01."
        sys.exit("--since %s names no commit here, as after a rebase or a squash, or in another clone. %s"
                 % (since, later) if HASH.match(since.strip()) else
                 "--since %s names no commit, tag or branch here. Give one that's here, or a date such as "
                 "'3 months ago' or 2026-06-01." % since if REF_LIKE.match(since.strip()) else
                 "--since %r is neither a revision here (a tag, branch or commit) nor a date in a form this reads, "
                 "such as '3 months ago', 3.days.ago, yesterday, last week or 2026-06-01." % since)
    stamp = git(repo, "rev-parse", "--since=" + date).strip().split("=")[-1]
    read = datetime.fromtimestamp(int(stamp)).strftime("%Y-%m-%d %H:%M") if stamp.isdigit() else "?"
    return ["--since=" + date, "HEAD"], None, read


def and_list(words):
    return words[0] if len(words) == 1 else "%s and %s" % (", ".join(words[:-1]), words[-1])


def asked_commits(repo, given):
    """The commits --exclude-commits names, as a map from each value to its commit's full hash; or stop, saying
    what each value that names none is. A hash is read in any case, from its first 4 characters on, as git
    reads one; a value can be a tag or a branch too."""
    found, problems = {}, []
    for value in [v.strip() for v in given.split(",") if v.strip()]:
        hexadecimal = bool(re.match(r"[0-9a-fA-F]+\Z", value))
        for way in ([] if value.startswith("-") else dict.fromkeys([value, value.lower()] if hexadecimal else [value])):
            result = scoping.git(repo, "rev-parse", "--verify", "--quiet", way + "^{commit}")
            if result.returncode == 0:
                found[value] = result.stdout.decode().strip()
                break
        else:
            shared = commits_starting(repo, value.lower()) if hexadecimal and len(value) >= 4 else []
            problems.append("%s is too short to name a commit: give 7 or more characters of its hash" % value
                            if hexadecimal and len(value) < 4 else
                            "%s names more than one commit here (%s): give more characters of its hash"
                            % (value, and_list([s[:9] for s in shared])) if len(shared) > 1 else
                            "%s isn't a commit here: give a commit's hash, a tag or a branch" % value)
    if problems:
        sys.exit("\n".join("heatmap.py: --exclude-commits %s." % p for p in problems))
    return found


def commits_starting(repo, prefix):
    """The commits whose hashes start with prefix, of 4 characters or more, in order."""
    shas = (scoping.run(repo, "rev-parse", "--disambiguate=" + prefix) or "").split()
    kinds = scoping.git(repo, "cat-file", "--batch-check", input="".join(s + "\n" for s in shas).encode())
    return sorted(line.split()[0] for line in kinds.stdout.decode(errors="replace").splitlines()
                  if line.split()[1:2] == ["commit"])


def raw_commit(repo, sha):
    """A commit as git stores it, read whatever the config says: its committer's time and its parents."""
    header = (scoping.run(repo, "cat-file", "commit", sha) or "").split("\n\n", 1)[0].split("\n")
    stamp = next((line.split()[-2] for line in header if line.startswith("committer ")), "0")
    return int(stamp) if stamp.isdigit() else 0, [line.split()[1] for line in header if line.startswith("parent ")]


def ignore_revs(repo):
    """The commits the repo asks blame to skip: bulk reformats and the like."""
    configured = (scoping.run(repo, "config", "blame.ignoreRevsFile") or "").strip()
    shas = set()
    for name in [configured, ".git-blame-ignore-revs"]:
        path = os.path.join(repo, name) if name else ""
        if path and os.path.isfile(path):
            for line in open(path, encoding="utf-8", errors="replace"):
                line = line.split("#", 1)[0].strip()
                if SHA.fullmatch(line):
                    shas.add(line)
    return shas


def shallow_edge(repo, folders):
    """In a shallow clone, the commits where its history stops, whose parents aren't here; else none."""
    if not folders[2]:
        return set()
    path = os.path.join(repo, git(repo, "rev-parse", "--git-path", "shallow").strip())
    return set(open(path).read().split()) if os.path.isfile(path) else set()


def checklist_places(repo, folders):
    """Where a relative --page path goes, every worktree's .refactor-pass/ folder, and a note when the
    first isn't plain. In a linked worktree, which may be removed once its work is done, a new checklist
    goes in the main checkout, if there is one; the others are read too, since a sandbox may have kept a
    pass out of the main checkout."""
    git_dir, common = folders[:2]
    trees, main = [], None
    for index, entry in enumerate(git(repo, "worktree", "list", "--porcelain").split("\n\n")):
        lines = entry.strip().split("\n")
        if not lines[0].startswith("worktree ") or "bare" in lines:
            continue
        path = lines[0][len("worktree "):]
        if os.path.isdir(path):
            trees.append(path)
            main = path if index == 0 else main
    home, note = repo, None
    if git_dir != common:
        if main:
            home = main
            note = ("This is a linked worktree, so a relative --page path is written in the main checkout's "
                    "%s, which outlives it." % os.path.normpath(os.path.join(main, FOLDER)))
        else:
            note = ("This is a linked worktree with no main checkout, so a relative --page path is written in "
                    "%s, which goes when the worktree is removed." % os.path.normpath(os.path.join(repo, FOLDER)))
    folders, seen = [], set()
    for top in [home, repo] + trees:
        folder = os.path.join(top, FOLDER)
        if os.path.realpath(folder) not in seen:
            seen.add(os.path.realpath(folder))
            folders.append(folder)
    return home, folders, note


def checklist_pages(folders):
    """The checklist pages in the folders, in order."""
    pages = []
    for folder in folders:
        if os.path.isdir(folder):
            pages += [os.path.join(folder, n) for n in sorted(os.listdir(folder)) if n.endswith(".html")]
    return pages


def shown(path, home, repo):
    """A path as the output gives it: from the repo's top when it's inside, as in a plain checkout; in
    full from a linked worktree, where a relative --page path means the main checkout's."""
    if os.path.realpath(home) != os.path.realpath(repo):
        return os.path.abspath(path)
    try:
        inside = os.path.relpath(path, repo)
    except ValueError:  # On Windows, another drive.
        return path
    return path if inside == os.pardir or inside.startswith(os.pardir + os.sep) else inside


def block_span(text, name):
    """Where a checklist page's data block lies: the start and end of the JSON between its tags, or None."""
    start = text.find(BLOCK % name)
    if start < 0:
        return None
    start += len(BLOCK % name)
    end = text.find("</script>", start)
    return (start, end) if end >= 0 else None


def read_pass(page):
    """A checklist page's pass block, read as a browser reads it, or None if it can't be read."""
    try:
        text = open(page, encoding="utf-8", errors="replace").read()
        start = text.index(BLOCK % "pass") + len(BLOCK % "pass")
        data = json.loads(text[start:scoping.script_end(text, start)[0]])
    except (OSError, TypeError, ValueError):
        return None
    return data if isinstance(data, dict) and isinstance(data.get("items"), list) else None


def checklist_commits(pages):
    """The commits recorded on the items of the checklist pages, as (page, item, commit), and the pages
    whose items couldn't be read."""
    records, unreadable = [], []
    for page in pages:
        data = read_pass(page)
        if data is None:
            unreadable.append(page)
            continue
        records += [(page, str(item.get("id")), str(c)) for item in data["items"] if isinstance(item, dict)
                    for c in (item.get("commits") if isinstance(item.get("commits"), list) else [])
                    if SHA.fullmatch(str(c))]
    return records, unreadable


def page_order(page, data):
    """Where a checklist comes among the others, oldest first: by the date in its name (or else the day
    its pass started), then the number after that date, as 2026-11-10-2.html is that day's second."""
    named = PAGE_NAME.match(os.path.basename(page))
    if named:
        return named.group(1), int(named.group(2) or 1), page
    return str((data or {}).get("started") or ""), 1, page


def new_page_name(folders):
    """The name a new checklist takes: today's date, or the first number after it that no checklist in
    any of the folders has."""
    taken = set(os.path.basename(p) for p in checklist_pages(folders))
    today = datetime.now().strftime("%Y-%m-%d")
    number = 1
    while ("%s.html" % today if number == 1 else "%s-%d.html" % (today, number)) in taken:
        number += 1
    return "%s.html" % today if number == 1 else "%s-%d.html" % (today, number)


def item_counts(data):
    """A checklist's items, per kind, with their statuses: "refactors 3 (1 todo, 2 done); ..."."""
    items = [i for i in data.get("items", []) if isinstance(i, dict)]
    kinds = []
    for prefix in "RFLD":
        mine = [str(i.get("status")) for i in items if str(i.get("id", "")).startswith(prefix)]
        if mine:
            counts = Counter(mine)
            kinds.append("%s %d (%s)" % (KIND_NAMES[prefix], len(mine),
                                         ", ".join("%d %s" % (n, s) for s, n in sorted(counts.items()))))
    return "; ".join(kinds) or "no items yet"


def list_checklists(home, folders, repo):
    """Print every checklist, newest first, with its dates and its items' statuses, and the name a new
    one takes."""
    rows = []
    for page in checklist_pages(folders):
        data = read_pass(page) or {}
        rows.append((page_order(page, data), page, data))
    rows.sort(reverse=True)
    if not rows:
        print("No checklist yet: none in %s." % " or ".join(shown(f, home, repo) + os.sep for f in folders))
    else:
        print("Checklists, newest first:")
    for _, page, data in rows:
        if not data:
            print("  %s: its pass block doesn't parse; check_page.py says where." % shown(page, home, repo))
            continue
        print("  %s: started %s, updated %s, from %s; %s" % (
            shown(page, home, repo), data.get("started") or "?", data.get("updated") or "?",
            data.get("base") or "?", item_counts(data)))
    if rows:
        print("The newest is %s." % shown(rows[0][1], home, repo))
    name = new_page_name(folders)
    print("A new pass gets a new checklist: --page %s makes it in %s (today's date%s)." % (
        os.path.join(FOLDER, name), shown(os.path.join(home, FOLDER), home, repo) + os.sep,
        ", and a number, since today already has one" if PAGE_NAME.match(name).group(2) else ""))


def not_landed(repo, shas):
    """Of the recorded commits, those that aren't commits reachable from HEAD. After a squash merge or
    a rebase, the commit that landed the work has another hash, so the heatmap can't leave it out."""
    shas = sorted(set(shas))
    proc = scoping.git(repo, "cat-file", "--batch-check", input="".join("%s^{commit}\n" % s for s in shas).encode())
    lost = set()
    for sha, line in zip(shas, proc.stdout.decode(errors="replace").splitlines()):
        found = line.split()
        if len(found) != 3 or found[1] != "commit" or \
                scoping.git(repo, "merge-base", "--is-ancestor", found[0], "HEAD").returncode != 0:
            lost.add(sha)
    return lost


def line_counts(repo, wanted):
    """Lines in each (rev, path) wanted, read in one batch; a path missing at its rev, or binary, is left
    out. A (rev, None) asks for the commit itself: its committer's time."""
    wanted = list(dict.fromkeys(w for w in wanted if w[1] is None or "\n" not in w[1]))
    if not wanted:
        return {}
    proc = scoping.git(repo, "cat-file", "--batch", input="".join(
        ("%s:%s\n" % w) if w[1] is not None else w[0] + "\n" for w in wanted).encode())
    data = proc.stdout
    counts = {}
    pos = 0
    for path in wanted:
        end = data.index(b"\n", pos)
        header = data[pos:end].split(b" ")
        pos = end + 1
        # "<sha> <type> <size>", then the object; or "<what was asked> missing", which may hold spaces.
        if len(header) != 3 or not SHA.fullmatch(header[0].decode()) or not header[2].isdigit():
            continue
        size = int(header[2])
        blob = data[pos:pos + size]
        pos += size + 1  # The object, then its newline.
        if header[1] == b"blob" and b"\0" not in blob[:8000]:  # git's own test for binary.
            counts[path] = blob.count(b"\n")
        elif header[1] == b"commit" and path[1] is None:
            stamp = re.search(br"(?m)^committer .* (\d+) [+-]\d{4}$", blob.split(b"\n\n", 1)[0])
            counts[path] = int(stamp.group(1)) if stamp else 0
    return counts


# The fixes trace: which commits fixed a defect in the project's own code, as their messages say. Each rule
# here was measured on commits labelled fix or not by reading their messages and diffs
# (tests/tools/measure_fixes.py), and a word or an exclusion stays only where, dropped alone, it took away
# more right calls than wrong ones (修复, fix, at one each, shares most commits with 问题).
#
# A type at the start of a subject: Conventional Commits' (fix(scope)!: ..., or with a full-width colon), a
# type in brackets ([Fix], as open-mmlab writes them), or a gitmoji. A tag in brackets whose word isn't a type
# names an area or a ticket ([clang], [SPARK-1]), and Flink's [hotfix] a change made without one: they're passed
# over, a type may follow them, and the subject's words are read without them.
CONVENTIONAL = re.compile(r"\s*(?P<type>[A-Za-z]+)(?:\((?P<scope>[^)]*)\))?!?\s*[:\uff1a]")
TAG = re.compile(r"\s*\[(?P<tag>[^\]]*)\]")
TYPES = {"feat", "feature", "fix", "docs", "doc", "chore", "refactor", "perf", "test", "tests", "style", "build",
         "ci", "revert", "release", "deps", "hotfix", "bugfix", "bug", "wip", "i18n", "types"}
BRACKET_TYPES = TYPES - {"hotfix"} | {"enhance", "enhancement", "improvement"}
FIX_TYPES = {"fix", "hotfix", "bugfix", "bug"}
# Gitmoji's emoji, as gitmoji.dev lists them, without the variation selector some are written with, and their
# codes; any other emoji isn't a type.
GITMOJI = set(("\U0001F3A8 \u26a1 \U0001F525 \U0001F41B \U0001F691 \u2728 \U0001F4DD \U0001F680 \U0001F484 "
               "\U0001F389 \u2705 \U0001F512 \U0001F510 \U0001F516 \U0001F6A8 \U0001F6A7 \U0001F49A \u2b07 \u2b06 "
               "\U0001F4CC \U0001F477 \U0001F4C8 \u267b \u2795 \u2796 \U0001F527 \U0001F528 \U0001F310 \u270f "
               "\U0001F4A9 \u23ea \U0001F500 \U0001F4E6 \U0001F47D \U0001F69A \U0001F4C4 \U0001F4A5 \U0001F371 "
               "\u267f \U0001F4A1 \U0001F37B \U0001F4AC \U0001F5C3 \U0001F50A \U0001F507 \U0001F465 \U0001F6B8 "
               "\U0001F3D7 \U0001F4F1 \U0001F921 \U0001F95A \U0001F648 \U0001F4F8 \u2697 \U0001F50D \U0001F3F7 "
               "\U0001F331 \U0001F6A9 \U0001F945 \U0001F4AB \U0001F5D1 \U0001F6C2 \U0001FA79 \U0001F9D0 \u26b0 "
               "\U0001F9EA \U0001F454 \U0001FA7A \U0001F9F1 \U0001F9D1\u200d\U0001F4BB \U0001F4B8 \U0001F9F5 "
               "\U0001F9BA \u2708 \U0001F996").split())
GITMOJI_CODES = set(("art zap fire bug ambulance sparkles memo rocket lipstick tada white_check_mark lock "
                     "closed_lock_with_key bookmark rotating_light construction green_heart arrow_down arrow_up "
                     "pushpin construction_worker chart_with_upwards_trend recycle heavy_plus_sign heavy_minus_sign "
                     "wrench hammer globe_with_meridians pencil2 poop rewind twisted_rightwards_arrows package alien "
                     "truck page_facing_up boom bento wheelchair bulb beers speech_balloon card_file_box loud_sound "
                     "mute busts_in_silhouette children_crossing building_construction iphone clown_face egg "
                     "see_no_evil camera_flash alembic mag label seedling triangular_flag_on_post goal_net dizzy "
                     "wastebasket passport_control adhesive_bandage monocle_face coffin test_tube necktie "
                     "stethoscope bricks technologist money_with_wings thread safety_vest airplane t-rex").split())
FIX_EMOJI = {"\U0001F41B", ":bug:", "\U0001F691", ":ambulance:", "\U0001FA79", ":adhesive_bandage:"}
# Scopes that make a fix type a chore: renovate's fix(deps), and fixes to CI or the docs.
CHORE_SCOPES = {"deps", "deps-dev", "dev-deps", "ci", "docs", "doc"}
# The types of a reverted change that isn't the code's, whose revert isn't a fix.
CHORE_TYPES = {"docs", "doc", "chore", "ci", "build", "style", "test", "tests", "release", "deps"}
# A revert, as git writes one: its subject says revert, and its body names the commit. Squash merges carry
# their branch's reverts in their bodies, so the subject has to say it too.
REVERT_LINE = re.compile(r"(?m)^\s*This reverts commit ([0-9a-fA-F]{7,64})")
REVERT_WORD = re.compile(r"\brevert(?:s|ed|ing)?\b", re.I)
QUOTED = re.compile(r'\brevert(?:s|ed)?\s*"(.*)"', re.I)
# Issue references, whose words name the tracker, not the change: "Fixed #12 --" closes an issue of any kind.
CLOSER = re.compile(r"\b(?:fix(?:e[sd])?|close[sd]?|resolve[sd]?)\s*:?\s*(?:#|gh-|[\w.-]+/[\w.-]+#)\w+", re.I)
REFERENCE = re.compile(r"\b(?:issues?|pr|pull|ticket)\s*(?:#\w+|\d+\b)", re.I)
# The words, each with the forms that count as it. A subject's code (in backticks, or an identifier such as
# should_ignore_error or Data.Render) isn't read; "regression test" names a test.
FIX_WORDS = {"fix": "fix fixes fixed fixing hotfix", "bug": "bug bugs bugfix bugfixes buggy",
             "error": "error errors erroneous", "wrong": "wrong wrongly",
             "correct": "correct corrects corrected correction corrections", "crash": "crash crashes crashed crashing",
             "overflow": "overflow overflows underflow underflows", "cve": "cve",
             "prevent": "prevent prevents prevented preventing", "problem": "problem problems",
             "mistake": "mistake mistakes mistaken mistakenly"}
FIX_CHINESE = ["修复", "修正", "漏洞", "问题", "越界", "空指针"]
NOT_FIX_WORDS = {"typo": "typo typos spelling grammar grammatical wording", "formatting": "formatting reformat",
                 "lint": "lint linting linter clippy eslint codespell mypy pylint flake8",
                 "docs": "docs doc documentation readme changelog docstring docstrings javadoc",
                 "warning": "warning warnings", "release": "release"}
NOT_FIX_PHRASES = {"error message": ("error message", "error messages")}
NOT_FIX_CHINESE = ["注释", "文档"]
# Documentation by its name: a changelog, a readme, a licence and the like, with no extension, a documentation
# one or one in capitals (COPYING.LESSER), as against src/history.ts or news.py; or Markdown and the like.
DOC_NAMES = re.compile(r"(?:changelog|changes|history|news|authors|contributors|readme|license|copying|contributing|"
                       r"code_of_conduct)(?:[._-][\w.-]*)?$", re.I)
DOC_EXTENSIONS = {"md", "markdown", "rst", "txt", "text", "adoc", "asciidoc", "rdoc", "org", "pod"}
DOC_FILES = re.compile(r".*\.(?:md|markdown|rst|adoc|asciidoc|rdoc)$", re.I)


# CI, build and dependency files: what a project runs its checks with, builds and packages itself with, and
# names its dependencies in. A fix in them isn't a fix of the project's code.
CI_FOLDERS = {".github", ".circleci", ".buildkite", ".gitlab", ".azure-pipelines"}
CHORE_FILES = re.compile(
    r"(?:\.gitlab-ci\.yml|\.travis\.yml|appveyor\.yml|\.appveyor\.yml|azure-pipelines\.yml|Jenkinsfile|\.cirrus\.yml|"
    r"\.pre-commit-config\.yaml|\.?codecov\.ya?ml|renovate\.json5?|\.readthedocs\.ya?ml|"
    r"Makefile|makefile|GNUmakefile|[\w.-]+\.mk|CMakeLists\.txt|[\w.-]+\.cmake|meson\.build|BUILD(?:\.bazel)?|"
    r"WORKSPACE|"
    r"SConstruct|configure\.ac|Makefile\.am|build\.xml|build\.gradle(?:\.kts)?|settings\.gradle(?:\.kts)?|"
    r"gradle\.properties|pom\.xml|[\w.-]+\.(?:csproj|fsproj|vbproj|vcxproj|sln)|Directory\.(?:Build|Packages)\.props|"
    r"Dockerfile|docker-compose\.ya?ml|make\.bat|"
    r"go\.mod|go\.sum|go\.work|pyproject\.toml|setup\.py|setup\.cfg|MANIFEST\.in|requirements[\w.-]*\.(?:txt|in)|"
    r"Pipfile|Pipfile\.lock|poetry\.lock|uv\.lock|tox\.ini|noxfile\.py|package\.json|package-lock\.json|"
    r"npm-shrinkwrap\.json|yarn\.lock|pnpm-lock\.yaml|pnpm-workspace\.yaml|bun\.lockb?|lerna\.json|"
    r"tsconfig[\w.-]*\.json|(?:vite|vitest|rollup|webpack|babel|jest|tsup|esbuild)\.config\.[cm]?[jt]s|"
    r"Cargo\.toml|Cargo\.lock|Gemfile|Gemfile\.lock|[\w.-]+\.gemspec|composer\.json|composer\.lock|mix\.exs|"
    r"mix\.lock|Package\.swift|Package\.resolved|Podfile|Podfile\.lock|packages\.config)$")


def is_doc(path):
    """Whether a file is documentation: in a docs folder, a changelog, a readme, or Markdown and the like."""
    name = path.split("/")[-1]
    _, dot, extension = name.rpartition(".")
    named = DOC_NAMES.match(name) and (not dot or extension.lower() in DOC_EXTENSIONS or extension.isupper())
    return bool(named or DOC_FILES.match(name) or set(path.lower().split("/")[:-1]) & {"doc", "docs", "documentation"})


def is_chore(path):
    """Whether a file is CI, build or dependency config: a CI folder's, a Makefile, a package's manifest, a lock
    file and the like."""
    parts = path.split("/")
    return bool(set(parts[:-1]) & CI_FOLDERS or CHORE_FILES.match(parts[-1]))


def not_code(path, is_test):
    """What a file is if it isn't the project's own code, as the fixes trace says it: documentation, tests, or
    CI, build or dependency files; or None."""
    return ("documentation" if is_doc(path) else "tests" if is_test(path) else
            "CI, build or dependency files" if is_chore(path) else None)


def fix_words(text):
    """The words a subject says, lower case: no issue references, code in backticks or identifiers."""
    text = re.sub(r"`[^`]*`", " ", REFERENCE.sub(" ", CLOSER.sub(" ", text)))
    text = re.sub(r"(?i)\bregression[ -](?=tests?\b)", " ", text)
    found = []
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_]*(?:'[a-z]+)?(?:\.[A-Za-z_]\w*)*(?:\(\))?", text):
        if not ("_" in token or "." in token or "(" in token or re.search(r"[a-z][A-Z]", token)):
            found.append(token.lower())
    return found, text


def says(text):
    """(the fix words a subject says, the words that say it isn't one), each as its family's name."""
    found, plain = fix_words(text)
    words, joined = set(found), " %s " % " ".join(found)
    fixes = [name for name, forms in FIX_WORDS.items() if words & set(forms.split())]
    fixes += [w for w in FIX_CHINESE if w in plain]
    nots = [name for name, forms in NOT_FIX_WORDS.items() if words & set(forms.split())]
    nots += [name for name, forms in NOT_FIX_PHRASES.items() if any(" %s " % f in joined for f in forms)]
    nots += [w for w in NOT_FIX_CHINESE if w in plain]
    return fixes, nots


def untagged(subject):
    """A subject without the tags at its start that aren't types, as its words are read."""
    while True:
        tag = TAG.match(subject)
        if not tag or tag.group("tag").strip().lower() in BRACKET_TYPES:
            return subject
        subject = subject[tag.end():]


def type_of(subject):
    """The type a subject carries at its start, after any tags that aren't types, as (its kind, how it's
    written), or None. Its kind is fix, chore (a fix of the dependencies, CI or docs) or other."""
    rest = untagged(subject)
    tag = TAG.match(rest)
    if tag:
        return ("fix" if tag.group("tag").strip().lower() in FIX_TYPES else "other"), tag.group(0).strip()
    found = CONVENTIONAL.match(rest)
    if found:
        kind = found.group("type").lower()
        if kind not in TYPES:
            return None
        written = found.group(0).strip()
        if kind in FIX_TYPES:
            return ("chore" if (found.group("scope") or "").strip().lower() in CHORE_SCOPES else "fix"), written
        return "other", written
    rest = rest.lstrip()
    code = re.match(r":([a-z0-9_+-]+):", rest)
    emoji = code.group(0) if code and code.group(1) in GITMOJI_CODES else next(
        (rest[:len(e) + (rest[len(e):len(e) + 1] == "\ufe0f")] for e in GITMOJI if rest.startswith(e)), None)
    if emoji:
        return ("fix" if emoji.rstrip("\ufe0f") in FIX_EMOJI else "other"), emoji
    return None


def same_person(one, other):
    """Whether two "Name <email>" authors are one person: the same name or the same email, a blank one being
    no one's."""
    (name, _, email), (other_name, _, other_email) = [x.rpartition(" <") for x in (one, other)]
    name, other_name = name.strip().lower(), other_name.strip().lower()
    email, other_email = email.rstrip(">").strip().lower(), other_email.rstrip(">").strip().lower()
    return bool(name) and name == other_name or bool(email) and email == other_email


def how_long(seconds):
    """A span of time in words, to the unit that suits it: 40 minutes, 5 hours, 12 days, 3 months, 2 years."""
    for unit, size, below in (("minute", 60, 3600), ("hour", 3600, 86400), ("day", 86400, 60 * 86400),
                              ("month", 2629746, 730 * 86400), ("year", 31556952, None)):
        if below is None or seconds < below:
            count = max(1, int(round(seconds / float(size))))
            return "%d %s%s" % (count, unit, "" if count == 1 else "s")


def read_fix(subject, typed):
    """A subject read as a fix by its type, where the window's subjects carry types, else by its words: (2 or 3,
    what said so), (0, why not), or (0, "") when it says nothing either way."""
    kind = type_of(subject) if typed else None
    fixes, nots = says(untagged(subject))
    if kind:
        # Another type says it isn't a fix; worth saying only where its words say fix.
        return (2, kind[1]) if kind[0] == "fix" else (0, "labelled %s" % kind[1] if fixes or kind[0] == "chore"
                                                      else "")
    if fixes and not nots:
        return 3, ", ".join(fixes)
    return 0, ("says " + ", ".join(nots)) if fixes else ""


def reverted(commit):
    """The hash a revert names, if the commit is one: its subject says revert and its body names the commit."""
    line = REVERT_LINE.search(commit[5])
    return line.group(1) if line and REVERT_WORD.search(commit[2]) else None


def find_commit(commits, prefix):
    """The one commit of commits whose hash starts with prefix, or None."""
    prefix = prefix.lower()
    found = [c for c in commits if c[0].startswith(prefix)]
    return found[0] if len(found) == 1 else None


def outside_window(repo, commits, window):
    """The commits the reverts in commits name that the window doesn't hold, read from the repo in one git
    call, as read_log reads them, merges too; by the name the revert gives. One the repo hasn't, as a shallow
    clone's, is left out."""
    names = sorted(set(n for n in (reverted(c) for c in commits) if n and not find_commit(window, n)))
    read = read_log(repo, ["--no-walk=unsorted", "--ignore-missing"] + names, merges=True) if names else []
    return dict((n, find_commit(read, n)) for n in names if find_commit(read, n))


def fix_trace(commits, window, typed, is_test=None, outside=None):
    """Per commit, how it reads: (tier, what said so, the seconds a reverted commit stood or None). Tier 1 is a
    revert, 2 a fix by its type, 3 by its words; 0 not a fix, with why not, or "" when nothing said either way.
    window is every commit read, newest first, where a reverted commit is looked for, and outside those named
    from outside it (outside_window); is_test tells a test."""
    is_test = is_test or (lambda path: scoping.is_test(path, [], []))
    by_sha = dict((c[0], c) for c in window)
    outside = outside or {}

    def find(prefix):
        found = by_sha.get(prefix.lower()) or find_commit(window, prefix)
        return found or outside.get(prefix)

    def read(commit, depth=0):
        """How a commit reads; but one that changed none of the project's own code isn't a fix of it."""
        found = reads(commit, depth)
        kinds = [not_code(c[0], is_test) for c in commit[3]]
        if found[0] and kinds and all(kinds):
            return 0, "changes only %s" % and_list(sorted(set(kinds))), None
        return found

    def reads(commit, depth):
        sha, stamp, subject, changes, author, body = commit
        target = reverted(commit)
        if not target:
            return read_fix(subject, typed) + (None,)
        before = find(target)
        quoted = QUOTED.search(subject)
        inner = quoted.group(1) if quoted else (before[2] if before else "")
        # A revert of a revert re-lands a change, and reads as that change did.
        if (before and reverted(before)) or re.match(r"(?:[A-Za-z]+(?:\([^)]*\))?!?:\s*)?revert", inner, re.I):
            original = find(reverted(before)) if before and reverted(before) else None
            if original and depth < 20:
                tier, what, _ = read(original, depth + 1)
            else:
                while QUOTED.search(inner):
                    inner = QUOTED.search(inner).group(1)
                tier, what = read_fix(inner, typed)
            return (tier, "re-lands %s" % what, None) if tier else (0, "re-lands a change that wasn't a fix", None)
        if before and same_person(before[4], author):
            return 0, "its author withdraws %s" % before[0][:9], None
        typed_inner = CONVENTIONAL.match(inner)
        if says(inner)[1] or (typed_inner and (typed_inner.group("type") or "").lower() in CHORE_TYPES):
            return 0, "reverts a change that isn't to the code", None
        return 1, "reverts %s" % target[:9], (stamp - before[1]) if before else None

    return dict((c[0], read(c)) for c in commits)


def fix_mark(found):
    """--show's mark of how a commit reads, after its subject: [fix: ...], [not a fix: ...], or nothing where
    nothing said either way."""
    if not found or not found[1]:
        return ""
    tier, what, stood = found
    if tier == 1 and stood is not None:
        what += ", %s after it" % how_long(stood)
    elif tier == 1:
        what += ", from before the window"
    return "  [%s: %s]" % (("fix, " + {1: "revert", 2: "type", 3: "words"}[tier]) if tier else "not a fix",
                           printable(what))


# Where the count is close to complete: where nearly all subjects carry a type, as in every typed repo measured
# (97% to 100%). Between a half and that, the subjects without one are read by their words, which find a third
# to a half of the fixes.
NEARLY_ALL = 0.9


def fix_summary(commits, fixes, typed):
    """The header's two lines on the fixes trace, and its facts for the page. The first: how many commits read
    as fixes and how, at least, since many fixes don't say so. The second: where the subjects can't tell a fix
    from anything else, that; the share of subjects with a type, and so how near complete the count is; and how
    many more commits close an issue without saying what kind of change."""
    tiers = Counter(found[0] for found in fixes.values())
    stood = [found[2] for found in fixes.values() if found[0] == 1]
    known = sorted(t for t in stood if t is not None)
    reverts = "1 a revert" if tiers[1] == 1 else "%d reverts" % tiers[1]
    if len(known) == 1:
        reverts += " (of a commit that had stood %s" % how_long(known[0])
    elif known:
        reverts += " (of commits that had stood %s" % (and_list([how_long(t) for t in known]) if len(known) <= 3
                                                       else "a median %s" % how_long(known[len(known) // 2]))
    if known:
        reverts += "%s)" % ("; %d from before the window" % (len(stood) - len(known)) if len(known) < len(stood)
                            else "")
    withdrawn = sum(1 for found in fixes.values() if found[1].startswith("its author withdraws"))
    ways = [way for count, way in ((tiers[1], reverts), (tiers[2], "%d by their type" % tiers[2]),
                                   (tiers[3], "%d by their words" % tiers[3])) if count]
    counted = sum(tiers[t] for t in (1, 2, 3))
    of = "%d commit%s" % (len(commits), "" if len(commits) == 1 else "s")
    first = ("Fixes, a lead and not a verdict: at least %d of the %s fixed a defect in the project's own code, as "
             "their messages say: %s." % (counted, of, and_list(ways)) if counted else
             "Fixes, a lead and not a verdict: none of the %s says in its message that it fixed a defect in the "
             "project's own code." % of)
    if withdrawn:
        first += " %s, of %s author's own commit%s, %s." % (
            "1 more revert" if withdrawn == 1 else "%d more reverts" % withdrawn, "its" if withdrawn == 1 else
            "their", "" if withdrawn == 1 else "s", "withdraws it and isn't counted" if withdrawn == 1 else
            "withdraw them and aren't counted")
    labelled = typed >= 0.5
    # Commits that close an issue and say nothing else either way: not one read as no fix for a reason.
    closing = sum(1 for c in commits if fixes[c[0]][:2] == (0, "") and (CLOSER.search(c[2]) or CLOSER.search(c[5]))
                  and not (labelled and type_of(c[2])))
    # Subjects of a word or two (Details, wip, update), with no type to read, can't say what a change was; where
    # most of the commits have one, the count can't be read.
    short = sum(1 for c in commits if not (labelled and type_of(c[2])) and
                len(re.findall(r"[A-Za-z]+|[\u4e00-\u9fff]{1,2}", c[2])) < 3)
    thin = short * 2 > len(commits)
    share = "%d%% of the subjects carry a type" % int(round(typed * 100))
    if thin:
        second = "Most subjects here are a word or two (%d of the %d), too little to tell a fix from anything " \
                 "else, so the count can't be read and the fixes by file aren't listed. %s." % (
                     short, len(commits), share)
    elif labelled and round(typed, 2) >= NEARLY_ALL:
        second = "%s, read as a label, so the count is close to complete." % share
    elif labelled:
        second = "%s, read as a label; those without one are read by their words, so the count is a floor: such " \
                 "subjects typically say so for a third to a half of their fixes, and the rest are among the " \
                 "commits --show leaves unmarked." % share
    else:
        second = "%s, too few to read as labels, so the count is a floor: subjects without a type typically say " \
                 "so for a third to a half of the fixes, and the rest are among the commits --show leaves " \
                 "unmarked." % share
    if closing:
        second += " %d more commit%s close%s an issue without saying what kind of change." % (
            closing, "" if closing == 1 else "s", "s" if closing == 1 else "")
    facts = {"fixes": counted, "revert": tiers[1], "type": tiers[2], "words": tiers[3],
             "typed": round(typed, 2), "labels": labelled, "closing": closing, "withdrawn": withdrawn, "thin": thin}
    return [first, second], facts


# Trailers that say who signed, reviewed or co-wrote a commit, which tell a reader nothing of what it fixed.
# Reported-by, Fixes, Closes and Bug lines stay.
IDENTITY = re.compile(r"\s*(?:signed-off-by|co-authored-by|reviewed-by|reviewed-on|acked-by|tested-by|cc|change-id|"
                      r"helped-by|suggested-by|approved-by|assisted-by)\s*:", re.I)


DIFF_LINES = 60  # --diffs's lines per commit: the whole change to the file, for four commits in five.
# --show --messages's commits: a file's newest 12, a sample a reader judges whole. At a fix in four, the rate in
# untyped repos' unmarked commits, 12 shows about three, enough to set apart a file that keeps breaking from
# one that doesn't, at a few thousand bytes of messages.
SAMPLE = 12


def message_lines(body, most=12):
    """A commit's message after its subject, for --show --messages: indented under its line, without who signed,
    reviewed or co-wrote it, its blank lines run together, and cut at most lines, saying how many more git show
    has; or None if it has none."""
    lines = []
    for line in body.strip().split("\n"):
        if IDENTITY.match(line):
            continue
        if line.strip() or (lines and lines[-1]):
            lines.append(printable(line.rstrip()))
    while lines and not lines[-1]:
        lines.pop()
    if len(lines) > most:
        lines = lines[:most - 1] + ["(%d more lines)" % (len(lines) - most + 1)]
    return "\n".join("      " + line if line else "" for line in lines) if lines else None


def change_hint(commit, change, is_test):
    """--show --messages's facts on what a commit changed: in this file, lines added and removed (or that it's
    binary) and a rename; and how many other files, and how many of them tests."""
    path, old, added, removed = change
    here = "binary" if added is None else "+%d -%d" % (added, removed)
    others = sorted(set(c[0] for c in commit[3]) - {path})
    tests = sum(1 for p in others if is_test(p))
    return "      [%s in this file%s; %s%s]" % (
        here, ", renamed from %s" % printable(old) if old else "",
        "no other file" if not others else "1 other file" if len(others) == 1 else "%d other files" % len(others),
        "" if not tests else ", a test" if len(others) == 1 else ", 1 of them a test" if tests == 1 else
        ", %d of them tests" % tests)


def file_diffs(repo, wanted, most=60):
    """One file's changes in several commits, in one git call: for each (hash, its path in that commit, its
    path before, if the commit renamed it), the hunks of that file only, cut at most lines, as a list of lines
    with a last one saying how many more there are; keyed by (hash, path). Each commit is one that changed the
    file, so where none of its change is found, the lines say it couldn't be read."""
    names = sorted(set(n for _, path, old in wanted for n in (path, old) if n))
    shas = sorted(set(sha for sha, _, _ in wanted))
    out = git(repo, *(DIFF + shas + ["--"] + names))
    # Each commit's part starts with a NUL, its hash and a newline: split there, as a change git diffs as text
    # can hold a NUL.
    parts = re.split("\0(%s)\n" % "|".join(shas), out)
    found = dict(zip(parts[1::2], parts[2::2]))
    result = {}
    for sha, path, old in wanted:
        sections = [x for x in re.split(r"(?m)^(?=diff --git )", found.get(sha, "")) if x.strip()]
        mine = set("%s %s/%s" % (side, prefix, n) for n in (path, old) if n for side, prefix in (("---", "a"),
                                                                                                  ("+++", "b")))
        mine |= set("rename %s %s" % (way, n) for n in (path, old) if n for way in ("from", "to"))
        mine |= {"diff --git a/%s b/%s" % (old or path, path)}  # A binary file's, or a mode's, has only this.
        # A section is the file's where its header names it. A name git quotes, as one with a tab or past ASCII,
        # is matched by being the only quoted one.
        kept = [x for x in sections if mine & set(x.split("\n")[:8])]
        quoted = [x for x in sections if re.search(r'(?m)^(?:---|\+\+\+) "', "\n".join(x.split("\n")[:8]))]
        kept = kept or (quoted if len(quoted) == 1 else [])
        lines = []
        for section in kept:
            body = section.split("\n")
            start = next((i for i, line in enumerate(body) if line.startswith("@@")), len(body))
            notes = [line for line in body[1:start] if line.startswith(("rename from", "new file", "deleted file",
                                                                        "Binary files", "old mode"))]
            lines += ["(%s)" % printable(n) for n in notes] + [printable(line) for line in body[start:]]
        while lines and not lines[-1]:
            lines.pop()
        if not lines:  # It's asked only for commits that changed the file: none found is a gap in reading git.
            lines = ["(its change to %s couldn't be read here: git show %s -- %s shows it)" % (
                printable(path), sha[:9], printable(path))]
        if len(lines) > most:
            lines = lines[:most - 1] + ["(%d more lines: git show %s -- %s)" % (
                len(lines) - most + 1, sha[:9], printable(path))]
        result[(sha, path)] = lines
    return result


def half_of(commit, newer):
    """Whether a commit is in the window's newer half, as --show says it, the same width either way."""
    return "newer" if commit[0] in newer else "older"


def show_diffs(repo, show, given, listed, changed_as, fixes, newer):
    """--show FILE --diffs SHAS: those of the commits --show FILE --messages lists, each with its changes to the
    file. A hash that names none of them, or more than one, is an error, which says which."""
    path, title = show
    chosen, problems = [], []
    for value in given:
        matches = [c for c in listed if re.match(r"[0-9a-fA-F]{4,}\Z", value) and c[0].startswith(value.lower())]
        if len(matches) == 1:
            chosen.append(matches[0])
        else:
            problems.append("%s %s" % (value, "is more than one of them" if matches else "isn't one of them"))
    if problems or not chosen:
        sys.exit("--diffs: %s. Give hashes of the %d commits --show %s --messages lists%s." % (
            "; ".join(problems) or "no commit given", len(listed), path,
            ", or widen it with --newest" if len(listed) == SAMPLE else ""))
    diffs = file_diffs(repo, [(c[0], changed_as[(c[0], path)][0], changed_as[(c[0], path)][1]) for c in chosen],
                       DIFF_LINES)
    print("%s: its changes in %d of its commits, each cut at %d lines" % (title, len(chosen), DIFF_LINES))
    for commit in chosen:
        info = describe(commit)
        print("  %s %s %s  %s%s" % (info["sha"], info["date"], half_of(commit, newer), printable(info["subject"]),
                                    fix_mark(fixes.get(commit[0]))))
        print("\n".join("      " + line for line in diffs[(commit[0], changed_as[(commit[0], path)][0])]))
    print()


def typed_share(commits):
    """The share of the commits whose subjects carry a type: Conventional Commits', one in brackets or a
    gitmoji."""
    return sum(1 for c in commits if type_of(c[2])) / float(len(commits)) if commits else 0.0


def printable(text):
    """Text from a commit, as the output writes it: a control character as its escape, as \\x1b, so a subject
    or a name can't drive the terminal the output goes to."""
    return re.sub(r"[\x00-\x08\x0b-\x1f\x7f]", lambda found: "\\x%02x" % ord(found.group()), text)


def describe(commit):
    """A commit's short hash, its local date (as the checklist page's dates are) and its subject."""
    sha, stamp, subject = commit[:3]
    return {"sha": sha[:9], "date": datetime.fromtimestamp(stamp).strftime("%Y-%m-%d"), "subject": subject}


def page_json(value):
    """JSON for a page's data block: a line per file and pair, and no <, which a browser could read as HTML (as
    a </script, or a <!-- and then a <script), but \\u003c, which JSON reads as <."""
    parts = []
    for key, inner in value.items():
        if isinstance(inner, list) and inner:
            inner = "[\n  " + ",\n  ".join(json.dumps(v, ensure_ascii=False) for v in inner) + "\n ]"
        else:
            inner = json.dumps(inner, ensure_ascii=False)
        parts.append("%s: %s" % (json.dumps(key), inner))
    return ("{\n " + ",\n ".join(parts) + "\n}").replace("<", "\\u003c")


def write_page(path, heatmap, project):
    """Put the heatmap into a checklist page, made from the template if it doesn't exist yet.
    Only the heatmap block changes, so the items are left as they were. In a .refactor-pass folder
    with no .gitignore, and nothing git tracks, write one that keeps the folder out of commits."""
    new = not os.path.exists(path)
    try:
        with open(TEMPLATE if new else path, "rb") as f:
            data = f.read()
        text = data.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")  # As text mode reads it.
    except OSError as e:
        sys.exit("heatmap.py: couldn't read %s, so it's left as it was: %s." % (path, e.strerror or e))
    except UnicodeDecodeError as e:
        sys.exit("heatmap.py: couldn't read %s, so it's left as it was: it isn't UTF-8 text, at byte %d. "
                 "check_page.py says the same." % (path, e.start))
    if new:
        span = block_span(text, "pass")
        data = json.loads(text[span[0]:span[1]])
        # The pass's date: the one in the page's name, as .refactor-pass/2026-11-10.html, or else today.
        named = re.match(r"\d{4}-\d{2}-\d{2}", os.path.basename(path))
        day = named.group(0) if named else datetime.now().strftime("%Y-%m-%d")
        data.update(project=project, started=day, base=heatmap["head"], updated=day)
        text = text[:span[0]] + "\n" + json.dumps(data, indent=1, ensure_ascii=False).replace("<", "\\u003c") + \
            "\n" + text[span[1]:]
    span = block_span(text, "heatmap")
    if not span:
        sys.exit("%s has no heatmap block; is it a checklist made from assets/page.html?" % path)
    text = text[:span[0]] + "\n" + page_json(heatmap) + "\n" + text[span[1]:]
    folder = os.path.dirname(os.path.abspath(path))
    os.makedirs(folder, exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(path + ".tmp", path)
    ignore = os.path.join(folder, ".gitignore")
    wrote = False
    if os.path.basename(folder) == FOLDER and not os.path.exists(ignore):
        if scoping.run(folder, "ls-files", "--", "."):
            print("%s holds files git tracks, so it's left without a .gitignore: new checklists in it will show "
                  "in git status." % folder)
        else:
            with open(ignore, "w", encoding="utf-8") as f:
                f.write("# Written by the refactor-pass skill: keeps its checklists out of commits.\n*\n")
            wrote = True
    return new, wrote


def main():
    scoping.safe_output()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__.split("\n\n", 1)[1])
    parser.add_argument("scope", nargs="*", help="folders or globs to count (default: everything)")
    parser.add_argument("-C", dest="repo", default=".", help="the repo (default: the current directory)")
    parser.add_argument("-n", "--commits", type=scoping.count(1), default=200,
                        help="the window: this many of the latest non-merge commits (default 200)")
    parser.add_argument("--since", metavar="REV_OR_DATE",
                        help="the window: every commit after REV (a tag, branch or commit, itself not included), "
                             "or since a date: 2026-06-01 (from the start of that day), 2026-06-01 14:30, "
                             "'3 months ago', 3.days.ago, yesterday or last week, and the other forms git's "
                             "documentation gives. The output says how it read a date; anything else is an error")
    parser.add_argument("--exclude-commits", default="", metavar="SHAS",
                        help="comma-separated commits to leave out, such as a mass reformat or a vendored "
                             "import, which would make every file they touched look hot: each a hash (7 or more "
                             "of its characters, in any case), a tag or a branch. One that names no commit is an "
                             "error, and one outside the window is named")
    parser.add_argument("--ignore", action="append", default=[], metavar="GLOB",
                        help="more file globs to leave out (added to the defaults: %s)"
                             % ", ".join(scoping.DEFAULT_IGNORE))
    parser.add_argument("--test", action="append", default=[], metavar="GLOB",
                        help="more globs naming test files, matched with case against the name or the path "
                             "(added to the defaults: %s, and folders named %s)"
                             % (", ".join(scoping.TEST_NAMES), ", ".join(scoping.TEST_FOLDERS)))
    parser.add_argument("--not-test", action="append", default=[], metavar="GLOB",
                        help="globs naming files that only look like tests, matched as --test's are, such as "
                             "'app/ABTest.php' or 'docs/spec/*': they count like the rest")
    parser.add_argument("--keep-tests", action="store_true",
                        help="count test files like the rest, in the table and the pairs")
    parser.add_argument("--top", type=scoping.count(0), default=25,
                        help="files to print, and to put on --page (default 25)")
    parser.add_argument("--pairs", type=scoping.count(0), default=15,
                        help="pairs and groups to print, and tests, and to put on --page (default 15 each)")
    parser.add_argument("--min-shared", type=int, default=5,
                        help="a pair needs at least this many commits together (default 5, as code-maat; "
                             "try 3 on a short history)")
    parser.add_argument("--min-revs", type=int, default=5,
                        help="a pair's files need at least this many commits each (default 5), so a file changed "
                             "three times, each time with a busy file, doesn't score 100%%")
    parser.add_argument("--min-degree", type=int, default=30,
                        help="a pair needs at least this code-maat degree, in percent (default 30)")
    parser.add_argument("--keep-bots", action="store_true",
                        help="count housekeeping bots' commits too (dependabot, renovate, github-actions, "
                             "pre-commit-ci and the like, which are left out by default)")
    parser.add_argument("--bot", action="append", default=[], metavar="NAME", type=bot_name,
                        help="leave out another bot's commits too: those whose author's name or email holds NAME, "
                             "in any case, such as a translation or release bot the output doesn't name")
    parser.add_argument("--keep-ignore-revs", action="store_true",
                        help="count the commits listed in .git-blame-ignore-revs too")
    parser.add_argument("--keep-pass-commits", action="store_true",
                        help="count the commits recorded on the checklists too")
    parser.add_argument("--max-files", type=int, default=25,
                        help="commits changing more files than this (tests aside, unless kept) are left out of the "
                             "pairs, since a sweeping rename or reformat pairs everything with everything "
                             "(default 25)")
    parser.add_argument("--page", metavar="PATH",
                        help="also put the heatmap into this checklist page (a relative path is from the repo's "
                             "top, or the main checkout's from a linked worktree), making it from the skill's "
                             "assets/page.html if it doesn't exist; only the page's heatmap block changes")
    parser.add_argument("--show", action="append", default=[], metavar="FILE",
                        help="print this file's commits in the window (its name today), instead of the heatmap")
    parser.add_argument("--messages", action="store_true",
                        help="with --show, each commit's message after its subject too, under its line, to read "
                             "without running git once per commit, with what it changed in the file and in others")
    parser.add_argument("--newest", type=scoping.count(1), metavar="N",
                        help="with --show, list only the file's newest N commits in the window (with --messages, "
                             "the newest %d unless given), and with --diffs take only those" % SAMPLE)
    parser.add_argument("--diffs", metavar="SHAS",
                        help="with one --show FILE, only these of its commits (comma-separated hashes, as --show "
                             "prints them), each with its changes to that file, under the name it had then, cut at "
                             "%d lines: one call for the commits whose messages don't settle what they were"
                             % DIFF_LINES)
    parser.add_argument("--no-fixes", action="store_true",
                        help="leave out the fixes trace: the header's count of the commits that read as fixes, the "
                             "table of fixes by file, and --show's marks")
    parser.add_argument("--checklists", action="store_true",
                        help="list the checklists in every worktree's .refactor-pass/, newest first, with their "
                             "items' statuses, and the name a new one takes, and stop; needs no scope")
    args = parser.parse_args()
    if args.messages and not args.show:
        parser.error("--messages goes with --show: --show FILE --messages")
    if args.diffs is not None and len(args.show) != 1:
        parser.error("--diffs goes with one --show: --show FILE --diffs SHA,SHA")

    repo = scoping.toplevel(args.repo)
    known = scoping.facts(args.repo)
    places = (known["git_dir"], known["common"], known["shallow"])
    home, folders, where = checklist_places(repo, places)
    if args.checklists:
        list_checklists(home, folders, repo)
        return
    found = scoping.git(repo, "rev-parse", "--verify", "--quiet", "--short=9", "HEAD")
    if found.returncode != 0:
        sys.exit("%s has no commits yet, so there's no history to read." % os.path.basename(repo))
    head = found.stdout.decode().strip()
    tracked = scoping.tracked_files(repo, "HEAD")
    args.scope = scoping.resolve(args.repo, repo, args.scope, tracked)
    own = scoping.own_folders(tracked, args.scope)  # Copies of this skill kept in the repo.
    named = asked_commits(repo, args.exclude_commits)
    revs, since_rev, since_read = window_revs(repo, args.since, args.commits)
    # How --since was read, when it's a date, so a misreading shows.
    since_said = "%s (%s, local time)" % (args.since, since_read) if since_read else args.since
    edge = shallow_edge(repo, places)
    everything = read_log(repo, revs)
    cut = [c for c in everything if c[0] in edge]
    everything = [c for c in everything if c[0] not in edge]
    shallow = ("This is a shallow clone, so its history stops at %s (%s); that commit looks as if it adds "
               "every file, so it's left out. `git fetch --unshallow` fetches the rest of the history."
               % (describe(cut[0])["sha"], describe(cut[0])["date"])) if cut else ""

    def matching(prefixes):
        return set(c[0] for c in everything if any(c[0].startswith(p) for p in prefixes))

    pages = checklist_pages(folders)
    others = sorted(set(os.path.dirname(p) for p in pages) - {os.path.join(home, FOLDER)})
    if others:
        where = ((where + " ") if where else "") + "The checklists in %s are read too." % " and ".join(
            "this worktree's %s" % FOLDER if f == os.path.join(repo, FOLDER) else os.path.normpath(f) for f in others)
    window_shas = set(c[0] for c in everything)
    asked = set(named.values()) & window_shas
    for value, sha in named.items():
        if sha not in window_shas:
            stamp, parents = raw_commit(repo, sha)
            print("heatmap.py: --exclude-commits %s (%s, %s) %s" % (
                value, sha[:9], datetime.fromtimestamp(stamp).strftime("%Y-%m-%d"),
                "is a merge, which the heatmap leaves out anyway." if len(parents) > 1 else
                "isn't in the window, so leaving it out changes nothing."), file=sys.stderr)
    listed = set() if args.keep_ignore_revs else matching(ignore_revs(repo)) - asked
    records, unreadable = ([], []) if args.keep_pass_commits else checklist_commits(pages)
    for page in unreadable:
        print("Couldn't read the items of %s, so its commits are counted; check_page.py says why."
              % shown(page, home, repo), file=sys.stderr)
    lost = not_landed(repo, [sha for _, _, sha in records]) if records else set()
    for page, ident in sorted(set((p, i) for p, i, sha in records if sha in lost)):
        shas = sorted(sha for p, i, sha in records if (p, i) == (page, ident) and sha in lost)
        print("%s, %s: %s %s reachable from HEAD. If that work was squash-merged or rebased onto this branch, "
              "the heatmap counts it under the hash that landed it: record that hash instead. If it's on a "
              "branch not merged yet, none of it is counted here." % (
                  shown(page, home, repo), ident, " and ".join(shas), "isn't" if len(shas) == 1 else "aren't"),
              file=sys.stderr)
    recorded = matching(set(sha for _, _, sha in records)) - asked - listed
    named = [n.lower() for n in args.bot]
    bots = set() if args.keep_bots else set(
        c[0] for c in everything if HOUSEKEEPING.search(c[4]) or any(n in c[4].lower() for n in named)) \
        - asked - listed - recorded
    # Who the bots were, so a wrong guess shows: each author's name, with their count.
    bot_names = Counter(c[4].rsplit(" <", 1)[0] for c in everything if c[0] in bots).most_common()
    excluded = asked | listed | recorded | bots
    commits = [c for c in everything if c[0] not in excluded]
    left_out = [(len(asked), "asked", ""), (len(listed), "in .git-blame-ignore-revs", "--keep-ignore-revs"),
                (len(recorded), "recorded on refactor checklists", "--keep-pass-commits"),
                (len(bots), "by housekeeping bots (%s)" % ", ".join("%s %d" % (printable(name), n)
                                                                    for name, n in bot_names), "--keep-bots")]
    page = None
    if args.page:
        # In the system's form, as the output names it: git gives a repo's top with / on Windows too.
        page = os.path.normpath(args.page if os.path.isabs(args.page) else os.path.join(home, args.page))

    if not commits:
        # Nothing left to count is a result, as just after a pass with --since its base: say what was left out.
        if not everything:
            print(("Nothing has landed since %s: the window has no commits." % since_said if args.since
                   else "No commits in the window.") + (" " + shallow if shallow else ""))
        else:
            reasons = "; ".join("%d %s" % (n, why) for n, why, _ in left_out if n)
            flags = [flag for n, _, flag in left_out if n and flag] + (["drop them from --exclude-commits"]
                                                                        if asked else [])
            print("%s: the window's %s left out: %s. To count them, %s." % (
                "Nothing else has landed since %s" % since_said if args.since else "Nothing to count",
                "commit is" if len(everything) == 1 else "%d commits are all" % len(everything), reasons,
                " or ".join(flags)))
        if page:
            print("No heatmap to put on %s, so %s." % (
                page, "it's left as it was" if os.path.exists(page) else "it isn't made"))
        return

    newer = set(c[0] for c in commits[:(len(commits) + 1) // 2])
    # The fixes trace, of the commits counted: types are read as labels where most subjects carry one.
    typed = typed_share(commits)
    def is_test(path):
        return scoping.is_test(path, args.test, args.not_test)

    fixes = {} if args.no_fixes else fix_trace(commits, everything, typed >= 0.5, is_test,
                                                 outside_window(repo, commits, everything))
    fix_lines, fix_facts = fix_summary(commits, fixes, typed) if fixes else ([], None)
    # Just before the window: --since's revision, or the oldest commit's parent (none at the root).
    base = since_rev or git(repo, "rev-list", "--parents", "-n", "1", everything[-1][0]).split()[1:2]
    base = base if isinstance(base, str) else (base[0] if base else None)
    # Newest first, so a rename is met before the older commits that used the
    # old name: from then on the old name means the file's name today. And the
    # oldest name met for a file is its name just before the window.
    current = {}
    earliest = {}

    def today(path):
        return current.get(path, path)

    patterns = scoping.DEFAULT_IGNORE + args.ignore
    files = defaultdict(lambda: {"commits": 0, "recent": 0, "added": 0, "removed": 0, "fixes": [0, 0, 0, 0],
                                 "fixes_recent": 0})
    sets, set_dates = [], []  # Per commit, newest first, the files it changed and its date.
    logs = defaultdict(list)  # Per file (in scope or not), the commits that changed it.
    changed_as = {}  # Per commit and file, the file's change in it, under its name in that commit.
    own_left_out = set()
    for commit in everything:
        sha, changes = commit[0], commit[3]
        touched = set()
        for path, old, added, removed in changes:
            name = today(path)
            if old is not None:
                current[old] = name
                earliest[name] = old
            if sha in excluded:
                continue
            if not logs[name] or logs[name][-1] is not commit:
                logs[name].append(commit)
                changed_as[(sha, name)] = (path, old, added, removed)
            if not scoping.in_scope(name, args.scope) or scoping.ignored(name, patterns):
                continue
            mine = [f for f in own if name.startswith(f + "/")]
            if mine:
                own_left_out.update(mine)
                continue
            stats = files[name]
            if "binary" not in stats:  # Its newest change says whether it's binary now, and when it was.
                stats["binary"] = added is None
                stats["last"] = describe(commit)["date"]
            if name not in touched:
                stats["commits"] += 1
                stats["recent"] += sha in newer
                tier = fixes.get(sha, (0,))[0]
                if tier:  # Counted once, the strongest way it reads as a fix; fixes[0] counts them all.
                    stats["fixes"][tier] += 1
                    stats["fixes"][0] += 1
                    stats["fixes_recent"] += sha in newer
            touched.add(name)
            if added is not None:
                stats["added"] += added
                stats["removed"] += removed
        if sha not in excluded:
            sets.append(touched)
            set_dates.append(describe(commit)["date"])

    read = line_counts(repo, [("HEAD", p) for p in sorted(files)] + ([(base, None)] if base else []) +
                       [(base, earliest.get(p, p)) for p in sorted(files) if base])
    sizes = dict((p, read[("HEAD", p)]) for p in files if ("HEAD", p) in read)
    before = dict((p, read.get((base, earliest.get(p, p)), 0)) for p in files) if base else {}
    base_time = read.get((base, None), 0)
    rows = []
    at_head = set(tracked)  # Not symbolic links or submodules.
    # Files git's diff reads as binary though they're text at HEAD: the repo's attributes (-diff, binary), or
    # the user's, say so. They're left out as git says, and the output names them.
    marked = sorted(p for p, s in files.items() if s["binary"] and p in sizes and p in at_head)
    for path, stats in files.items():
        if path not in sizes or stats["binary"] or path not in at_head:  # Gone at HEAD, binary, or not a file.
            continue
        row = {"path": path, "commits": stats["commits"], "recent": stats["recent"], "last": stats["last"],
               "churn": stats["added"] + stats["removed"], "added": stats["added"], "removed": stats["removed"],
               "size": sizes[path], "rel": round((stats["added"] + stats["removed"]) / max(sizes[path], 1), 2),
               "size_before": before.get(path, 0), "growth": sizes[path] - before.get(path, 0)}
        rows.append(row)
    rows.sort(key=lambda r: (-r["commits"] * r["size"], -r["commits"], -r["churn"], r["path"]))
    # For the page: each file's fixes, at least, where the trace counts them; documentation, tests, and CI,
    # build and dependency files aside, as in the table of fixes by file.
    for row in rows:
        if fix_facts and not fix_facts["thin"] and not not_code(row["path"], is_test):
            row.update(fixes=files[row["path"]]["fixes"][0], fixes_recent=files[row["path"]]["fixes_recent"])
    by_path = dict((r["path"], r) for r in rows)
    # Tests have their history read like the rest, but stay out of the table and the pairs.
    tests = set() if args.keep_tests else set(r["path"] for r in rows
                                              if scoping.is_test(r["path"], args.test, args.not_test))
    rows = [r for r in rows if r["path"] not in tests]
    alive = set(r["path"] for r in rows)
    in_scope = [p for p in tracked if scoping.in_scope(p, args.scope) and not scoping.ignored(p, patterns)]
    doubts = scoping.doubtful_tests(tests, in_scope, args.test)
    # Each production file's name, so a test's own file is found even where it isn't in the window.
    stems = set(scoping.flat(scoping.stem(p, False)) for p in in_scope
                if not scoping.is_test(p, args.test, args.not_test))

    shared, with_tests = Counter(), Counter()
    seen_in = defaultdict(set)  # Per file, the commits counted for pairs that changed it.
    newest = {}  # Per pair, the newest commit that changed both: the first met.
    too_big = 0
    for index, touched in enumerate(sets):
        mine = sorted(touched & alive)
        if len(mine) > args.max_files:
            too_big += 1
            continue
        shared.update(combinations(mine, 2))
        for pair in combinations(mine, 2):
            newest.setdefault(pair, index)
        for path in mine:
            seen_in[path].add(index)
        with_tests.update((test, path) for test in touched & tests for path in mine)

    def measures(paths, together):
        """How strongly files change together, or None if they fall short of a pair's thresholds."""
        revs = [by_path[p]["commits"] for p in paths]
        # code-maat's degree: shared commits over the files' average.
        degree = together / (sum(revs) / float(len(revs)))
        if together < args.min_shared or min(revs) < args.min_revs or degree * 100 < args.min_degree:
            return None
        # Of the commits that changed the quietest of them, the share that changed them all.
        return {"shared": together, "of_quieter": round(together / min(revs), 2), "degree": round(degree, 2)}

    pairs = []
    for (a, b), count in shared.items():
        found = measures([a, b], count)
        if found:
            pairs.append(dict(a=a, b=b, last=set_dates[newest[(a, b)]], **found))
    pairs.sort(key=lambda p: (-p["shared"], -p["degree"], p["a"], p["b"]))
    # Files that all pair with each other are one row, grown from the strongest pair left: add the file
    # that pairs with every one of them and keeps the most commits that changed them all, while those
    # commits meet a pair's thresholds. A chain, a with b and b with c but not a with c, stays two pairs.
    partners = defaultdict(set)
    for pair in pairs:
        partners[pair["a"]].add(pair["b"])
        partners[pair["b"]].add(pair["a"])
    groups, grouped = [], set()
    for pair in pairs:
        if (pair["a"], pair["b"]) in grouped:
            continue
        members, common = [pair["a"], pair["b"]], seen_in[pair["a"]] & seen_in[pair["b"]]
        while True:
            options = sorted(set.intersection(*(partners[m] for m in members)) - set(members))
            options = [f for f in options if measures(members + [f], len(common & seen_in[f]))]
            if not options:
                break
            best = max(options, key=lambda f: len(common & seen_in[f]))
            members, common = members + [best], common & seen_in[best]
        if len(members) > 2:
            members.sort()
            # Its pairs' own counts too, so a strong pair inside a weaker group still shows.
            counts = [shared[p] for p in combinations(members, 2)]
            groups.append(dict(files=members, pairs=[min(counts), max(counts)], last=set_dates[min(common)],
                               **measures(members, len(common))))
            grouped.update(combinations(members, 2))
    pairs = [p for p in pairs if (p["a"], p["b"]) not in grouped]
    together = sorted(groups + pairs, key=lambda r: (-r["shared"], -r["degree"], r.get("a") or r["files"][0]))
    together = together[:args.pairs]
    # Groups that share two files or more are one cluster, listed together at the place of its strongest:
    # one area that keeps changing, though no commit need have changed all of its files.
    shown_groups = [r for r in together if "files" in r]
    root = list(range(len(shown_groups)))

    def top(i):
        while root[i] != i:
            i = root[i]
        return i

    for i, j in combinations(range(len(shown_groups)), 2):
        if len(set(shown_groups[i]["files"]) & set(shown_groups[j]["files"])) >= 2:
            root[top(j)] = top(i)
    members = defaultdict(list)
    for i, row in enumerate(shown_groups):
        members[top(i)].append(row)
    ordered, placed, clusters = [], set(), 0
    for row in together:
        if "files" not in row:
            ordered.append(row)
            continue
        mine = members[top(shown_groups.index(row))]
        if id(mine) in placed:
            continue
        placed.add(id(mine))
        if len(mine) > 1:
            clusters += 1
            for member in mine:
                member["cluster"] = clusters
        ordered += mine
    together = ordered
    # Tests that change with several production files besides their own.
    tied = defaultdict(list)
    for (test, path), count in with_tests.items():
        if not scoping.owns(test, path, stems) and measures([test, path], count):
            tied[test].append({"path": path, "shared": count})
    tied = [{"test": test, "files": sorted(found, key=lambda f: (-f["shared"], f["path"]))}
            for test, found in tied.items() if len(found) > 1]
    tied.sort(key=lambda t: (-len(t["files"]), -sum(f["shared"] for f in t["files"]), t["test"]))

    window = {"commits": len(commits), "newest": describe(commits[0]), "oldest": describe(commits[-1]),
              "newer_half_from": describe(commits[(len(commits) + 1) // 2 - 1])["date"],
              "excluded": len(excluded), "excluded_asked": len(asked), "excluded_ignore_revs": len(listed),
              "excluded_checklists": len(recorded), "excluded_bots": len(bots), "bots": bot_names,
              "too_big_for_pairs": too_big,
              "since": args.since, "tests_aside": None if args.keep_tests else len(tests), "shallow": bool(cut)}
    if fix_facts:
        window["fixes"] = fix_facts
    if args.show:
        # A file git tracks, or one changed in the window, as a file deleted in it; or a name a file had before
        # it was renamed in the window, read as its name today. Any other is a mistake, as a scope's would be.
        shows, known = [], set(tracked) | set(logs)
        for given in args.show:
            path = scoping.show_path(args.repo, repo, given, tracked)
            if path not in known and today(path) in known:
                shows.append((today(path), "%s, %s before it was renamed in the window" % (today(path), path)))
            elif path in known:
                shows.append((path, path))
            else:
                sys.exit(scoping.unknown_file(path, known, repo, "changed in the window"))
        # With --messages, a file's newest commits, a sample: the ones --diffs takes.
        limit = args.newest or (SAMPLE if args.messages or args.diffs is not None else None)
        if args.diffs is not None:
            show_diffs(repo, shows[0], [v.strip() for v in args.diffs.split(",") if v.strip()],
                       logs.get(shows[0][0], [])[:limit], changed_as, fixes, newer)
            return
        for path, title in shows:
            mine = logs.get(path, [])
            listed = mine[:limit]
            print("%s: %s from %s (%s) to %s (%s); newer: in the window's newer half, from %s.%s" % (
                title, "the newest %d of its %d commits, of the %d" % (len(listed), len(mine), len(commits))
                if len(listed) < len(mine) else "%d of the %d commits" % (len(mine), len(commits)),
                window["oldest"]["sha"], window["oldest"]["date"], window["newest"]["sha"], window["newest"]["date"],
                window["newer_half_from"], " %d more: --newest %d lists them all." % (len(mine) - len(listed),
                                                                                      len(mine))
                if len(listed) < len(mine) else ""))
            for commit in listed:
                info = describe(commit)
                print("  %s %s %s  %s%s" % (info["sha"], info["date"], half_of(commit, newer),
                                            printable(info["subject"]), fix_mark(fixes.get(commit[0]))))
                if args.messages:
                    print(change_hint(commit, changed_as[(commit[0], path)], is_test))
                    if message_lines(commit[5]):
                        print(message_lines(commit[5]))
            print()
        return
    scope = args.scope or ["(everything)"]
    if page:
        options = {"top": args.top, "pairs": args.pairs, "max_files": args.max_files, "min_shared": args.min_shared,
                   "min_revs": args.min_revs, "min_degree": args.min_degree}
        heatmap = {"head": head, "scope": scope, "window": window, "options": options, "total_files": len(rows),
                   "files": rows[:args.top], "groups": [r for r in together if "files" in r],
                   "pairs": [r for r in together if "a" in r], "tests": tied[:args.pairs]}
        earlier = read_pass(page) if os.path.exists(page) else None
        try:
            made, ignore = write_page(page, heatmap, os.path.basename(home))
        except OSError as e:
            sandboxed = ("ask the user to let you write there, or give --page an absolute path in this worktree, "
                         "such as %s, and tell the user the checklist goes when the worktree is removed unless "
                         "they copy it out" % os.path.normpath(os.path.join(repo, FOLDER, os.path.basename(page)))) \
                if os.path.realpath(home) != os.path.realpath(repo) else \
                "ask the user to let you write there, or give --page a path you can write and tell them where it is"
            sys.exit("Couldn't write %s: %s.\nIf a sandbox keeps you out of that folder, %s." % (
                page, e.strerror or e, sandboxed))
        if made:
            print("Made %s, with the heatmap.%s\n" % (page, " Wrote a .gitignore beside it, so git leaves the "
                                                            "checklists out of commits." if ignore else ""))
        else:
            # A checklist that exists keeps its pass: say which one it is, in case a new pass meant to make its own.
            print("Updated the heatmap on %s, and nothing else: it's the checklist started %s from %s, with %s. "
                  "A new pass needs a checklist of its own: --page %s.\n" % (
                      shown(page, home, repo), (earlier or {}).get("started") or "?",
                      (earlier or {}).get("base") or "?", item_counts(earlier) if earlier else "items that don't "
                      "parse", os.path.join(FOLDER, new_page_name(folders))))

    print("%s at %s, scope: %s" % (os.path.basename(repo), head, " ".join(scope)))
    reasons = ", ".join("%d %s" % (n, why) for n, why, _ in left_out if n)
    print("Window: %d commits, %s (%s) back to %s (%s)%s" % (
        len(commits), window["newest"]["sha"], window["newest"]["date"], window["oldest"]["sha"],
        window["oldest"]["date"], "; left out: " + reasons if reasons else ""))
    if since_read:
        print("--since %s reads as %s, local time." % (args.since, since_read))
    print("Newer half from %s. Ordered by commits times size." % window["newer_half_from"])
    if base:
        print("Growth is against %s (%s), just before the window." % (
            base[:9], datetime.fromtimestamp(base_time).strftime("%Y-%m-%d")))
    else:
        print("Growth is from nothing: the window starts at the first commit.")
    if not args.keep_tests:
        print("Test files: %s." % ("%d changed in the window, set aside from the table and the pairs" % len(tests)
                                   if tests else "none in the scope changed in the window"))
    if doubts:
        print("Set aside as tests, but maybe not: %s%s. If one isn't a test, --not-test GLOB counts it." % (
            "; ".join("%s (%s)" % d for d in doubts[:5]), "; and %d more" % (len(doubts) - 5)
            if len(doubts) > 5 else ""))
    if own_left_out:
        print("This skill's own files, in %s, are left out; a scope naming that folder counts them."
              % " and ".join(f + "/" for f in sorted(own_left_out)))
    for line in fix_lines:
        print(line)
    if marked:
        named = marked[:5] + (["%d more" % (len(marked) - 5)] if len(marked) > 5 else [])
        print("Git's attributes mark %s that changed in the window as binary, though %s text at HEAD, so %s left "
              "out: %s." % ("1 file" if len(marked) == 1 else "%d files" % len(marked),
                            "it's" if len(marked) == 1 else "they're", "it's" if len(marked) == 1 else "they're",
                            and_list(named)))
    for note in [shallow, where]:
        if note:
            print(note)
    print()
    if rows:
        print("%7s %6s %10s %7s %5s %7s %7s  file" % ("commits", "recent", "last", "churn", "rel", "size", "growth"))
    else:
        print("No file in the scope%s changed in the window." % ("" if args.keep_tests else ", tests aside,"))
    for row in rows[:args.top]:
        print("%7d %6d %10s %7d %5.1f %7d %+7d  %s" % (row["commits"], row["recent"], row["last"], row["churn"],
                                                      row["rel"], row["size"], row["growth"], row["path"]))
    if len(rows) > args.top:
        print("  ... %d more files changed in the window" % (len(rows) - args.top))
    print()
    if fix_facts and not fix_facts["thin"]:
        # Fixes by file: where the commits that read as fixes landed, each counted once, its strongest way.
        place = dict((r["path"], i) for i, r in enumerate(rows))
        fixed = sorted((p for p in place if files[p]["fixes"][0] and not not_code(p, is_test)),
                       key=lambda p: (-files[p]["fixes"][0], -files[p]["fixes_recent"], place[p]))
        print("Fixes by file, at least: of each file's commits, those whose messages say they fixed a defect in "
              "it, and how many of those were in the newer half; documentation, tests, and CI, build and "
              "dependency files aside. A floor, not a count: --show FILE --messages gives each commit's message, "
              "to read the ones left unmarked.")
        if fixed:
            print("%7s %6s %6s %5s %5s  file" % ("fixes", "recent", "revert", "type", "words"))
        for path in fixed[:args.top]:
            counts = files[path]["fixes"]
            print("%7d %6d %6d %5d %5d  %s" % (counts[0], files[path]["fixes_recent"], counts[1], counts[2],
                                              counts[3], path))
        if len(fixed) > args.top:
            print("  ... %d more files with fixes" % (len(fixed) - args.top))
        if not fixed:
            print("  none")
        print()
    print("Changed together (commits of %d files or fewer%s; files with %d+ commits, %d+ shared, degree %d%%+):"
          % (args.max_files, "" if args.keep_tests else ", tests aside", args.min_revs, args.min_shared,
             args.min_degree))
    if groups:
        print("  A row of three or more files is a group: each pair of them qualifies, and the counts are of the "
              "commits that changed them all.")
    if too_big:
        print("  %d of the %d commits changed more than %d files and %s left out of these; raise --max-files to "
              "count them." % (too_big, len(commits), args.max_files, "is" if too_big == 1 else "are"))
    print("%7s %8s %7s %10s" % ("shared", "quieter", "degree", "last"))
    for row in together:
        if row.get("cluster") and row is next(r for r in together if r.get("cluster") == row["cluster"]):
            mine = [r for r in together if r.get("cluster") == row["cluster"]]
            print("  One area: these %d groups overlap, each sharing two files or more with another, %d files in "
                  "all, though no commit need have changed them all:" % (
                      len(mine), len(set(f for r in mine for f in r["files"]))))
        # A group's pairs' own counts, when they differ from the commits that changed them all.
        least, most = row.get("pairs", [row["shared"]] * 2)
        spread = "" if least == most == row["shared"] else \
            " (each pair %d)" % least if least == most else " (each pair %d to %d)" % (least, most)
        print("%7d %7.0f%% %6.0f%% %10s  %s%s%s" % (row["shared"], row["of_quieter"] * 100, row["degree"] * 100,
                                                    row["last"], "  " if row.get("cluster") else "",
                                                    " + ".join(row.get("files") or [row["a"], row["b"]]), spread))
    if not together:
        print("  none")
    if tests:
        print()
        print("Tests changed together with several production files besides their own (as above; commits "
              "together in brackets). Each is a lead to check: a test that reaches into their private members or "
              "internal paths is tied to their internals; a broad test that follows features isn't:")
        for row in tied[:args.pairs]:
            print("  %s: %d files, %s" % (row["test"], len(row["files"]),
                                          ", ".join("%s (%d)" % (f["path"], f["shared"]) for f in row["files"])))
        if not tied:
            print("  none")


if __name__ == "__main__":
    scoping.guard(main)
