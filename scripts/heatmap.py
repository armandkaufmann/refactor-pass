#!/usr/bin/env python3
"""Where a repo's changes keep landing: a heatmap from git history.

For every file still in the repo at HEAD and inside the scope, over a window
of recent commits:

  commits   how many of the window's commits changed it
  recent    how many of those were in the window's newer half. About half
            its commits means it's as busy as ever; few means it has cooled
  churn     lines added plus lines removed
  rel       churn relative to its size now: 2.0 means twice its lines were
            written or rewritten in the window. Relative churn predicts
            defects far better than absolute churn (Nagappan & Ball, 2005)
  size      its lines at HEAD
  growth    its size now less its size just before the window, under the
            name it had then (0 if it didn't exist)

Files are listed by commits times size, so the top ones are both busy and
big. A small file changed often, like a config, and a big one rarely
changed both come lower.

Test files are set aside, so a spec beside its source doesn't top the list:
those named as the common frameworks name them (Board.spec.ts, test_x.py,
x_test.go, XTest.php, XTests.cs...) and anything in a folder named test,
tests, __tests__, spec or the like. --test adds a pattern; --keep-tests
counts them like the rest.

Then the files that keep changing in the same commits, with two measures:
of the quieter file's commits, the share that changed both (how likely the
busier file changes when the quieter one does), and code-maat's degree,
shared commits over the two files' average. Files that all pair with each
other are one row, a group, when the commits that changed all of them meet
the same thresholds; its measures count those commits. Commits that changed
more than --max-files files, tests aside, are left out of these, and the
count says how many; in a repo that squash-merges, that can be most of them.

Last, the tests that change together with several production files besides
their own (the file of the same name, less the test's marker): each is tied
to their internals, or follows files that already change together.

--show FILE prints a file's commits in the window instead, to read the
reasons it keeps changing.

History is followed across renames, so a file moved or renamed in the window
keeps the changes it had under its old name. Merge commits are skipped, and so
are bots' commits, those the repo lists in .git-blame-ignore-revs (bulk
reformats), and those recorded on the items of the checklists in
.refactor-pass/ (a refactor pass's own work, which would make the files it
just refactored look hot). A recorded commit that isn't reachable from HEAD,
as after a squash merge or a rebase, gets a warning. A left out commit counts
toward nothing but its renames, and growth, being two sizes, includes what
it did. Binary files are left out. In a shallow clone, the commits where its
history stops look as if they add every file, so they are left out too, and
the output says so.

In a linked worktree, which may be removed once its work is done, the
checklists are the main checkout's: they are read from its .refactor-pass/,
and a relative --page path is written there.

Usage:
  heatmap.py [options] [SCOPE ...]

SCOPE is a folder or a glob (src, lib, 'app/**/*.py'), from the repo's top or
from the folder -C names; with none, every file counts. A scope that matches
no tracked file is an error. Reads git and the checklists; writes nothing but
--page's file.

Examples:
  heatmap.py src tests
  heatmap.py -n 300 --exclude-commits 9e1d16e,b7fc306 src lib
  heatmap.py --since v2.0.0 app
  heatmap.py --since "3 months ago" src
  heatmap.py --page .refactor-pass/2026-11-10.html src
  heatmap.py --show src/app/main.py
"""

import argparse
import json
import os
import re
import subprocess
import sys
import time
from collections import Counter, defaultdict
from datetime import datetime, timezone
from itertools import combinations

# The scope, the files left out and the tests, read the same way as measure.py reads them. No
# __pycache__ is written, so a run leaves the skill's folder as it was.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scoping  # noqa: E402

# Authors whose commits are a bot's: dependency bumps and the like.
BOT = re.compile(r"\[bot\]|dependabot|renovate|github-actions", re.I)
SHA = re.compile(r"[0-9a-f]{7,40}")
# The checklist page: its template, and the tag that opens each data block.
TEMPLATE = os.path.join(os.path.dirname(os.path.abspath(__file__)), os.pardir, "assets", "page.html")
BLOCK = '<script type="application/json" id="%s">'


def git(repo, *args):
    result = subprocess.run(["git", "-C", repo] + list(args), capture_output=True)
    if result.returncode != 0:
        sys.exit("git %s failed: %s" % (" ".join(args), result.stderr.decode(errors="replace").strip()))
    return result.stdout.decode("utf-8", errors="replace")


def read_log(repo, revs):
    """The commits in revs, newest first: (sha, time, subject, [(path, old_path, added, removed)], author).
    old_path is the name before a rename, else None; added and removed are None for a binary file."""
    out = git(repo, "log", "--no-merges", "-z", "-M", "--numstat",
              "--format=%x1e%H%x1f%ct%x1f%aN <%aE>%x1f%s", *revs)
    commits = []
    for record in out.split("\x1e")[1:]:
        header, _, body = record.partition("\0")
        sha, stamp, author, subject = header.split("\x1f", 3)
        tokens = body.split("\0")
        changes = []
        i = 0
        while i < len(tokens):
            token = tokens[i].lstrip("\n")
            i += 1
            if not token:
                continue
            added, removed, path = token.split("\t", 2)
            old = None
            if path == "":  # A rename: the old and new names follow.
                old, path = tokens[i], tokens[i + 1]
                i += 2
            binary = added == "-"
            changes.append((path, old, None if binary else int(added), None if binary else int(removed)))
        commits.append((sha, int(stamp), subject, changes, author))
    return commits


def window_revs(repo, since, count):
    """The git log arguments for the window, and the revision just before it if --since named one.
    --since takes a revision, or else a date as git log's own --since does."""
    if not since:
        return ["-n", str(count), "HEAD"], None
    check = subprocess.run(["git", "-C", repo, "rev-parse", "--verify", "--quiet", since + "^{commit}"],
                           capture_output=True)
    if check.returncode == 0:
        return ["%s..HEAD" % since], since
    # git reads almost anything as a date, and what it can't read as now.
    stamp = git(repo, "rev-parse", "--since=" + since).strip().split("=")[-1]
    if not stamp.isdigit() or abs(int(stamp) - time.time()) < 120:
        sys.exit("--since %r is neither a revision here (a tag, branch or commit) nor a date git can read, "
                 "such as '3 months ago' or 2026-06-01." % since)
    return ["--since=" + since, "HEAD"], None


def ignore_revs(repo):
    """The commits the repo asks blame to skip: bulk reformats and the like."""
    configured = subprocess.run(["git", "-C", repo, "config", "blame.ignoreRevsFile"],
                                capture_output=True, text=True).stdout.strip()
    shas = set()
    for name in [configured, ".git-blame-ignore-revs"]:
        path = os.path.join(repo, name) if name else ""
        if path and os.path.isfile(path):
            for line in open(path, errors="replace"):
                line = line.split("#", 1)[0].strip()
                if SHA.fullmatch(line):
                    shas.add(line)
    return shas


def shallow_edge(repo):
    """In a shallow clone, the commits where its history stops, whose parents aren't here; else none."""
    if git(repo, "rev-parse", "--is-shallow-repository").strip() != "true":
        return set()
    path = os.path.join(repo, git(repo, "rev-parse", "--git-path", "shallow").strip())
    return set(open(path).read().split()) if os.path.isfile(path) else set()


def checklist_folder(repo):
    """Where the checklists live, and a note when that isn't plain. In a linked worktree, which may be
    removed once its work is done, it's the main checkout's .refactor-pass/, if there is a main checkout."""
    here = os.path.join(repo, ".refactor-pass")
    git_dir = os.path.realpath(os.path.join(repo, git(repo, "rev-parse", "--git-dir").strip()))
    common = os.path.realpath(os.path.join(repo, git(repo, "rev-parse", "--git-common-dir").strip()))
    if git_dir == common:
        return here, None
    first = git(repo, "worktree", "list", "--porcelain").split("\n\n")[0].split("\n")
    main = first[0][len("worktree "):] if first[0].startswith("worktree ") else ""
    if "bare" in first or not os.path.isdir(main):
        return here, ("This is a linked worktree with no main checkout, so the checklists live in %s, "
                      "which goes when the worktree is removed." % here)
    folder = os.path.join(main, ".refactor-pass")
    return folder, ("This is a linked worktree, so the checklists are the main checkout's, in %s, "
                    "which outlives it." % folder)


def block_span(text, name):
    """Where a checklist page's data block lies: the start and end of the JSON between its tags, or None."""
    start = text.find(BLOCK % name)
    if start < 0:
        return None
    start += len(BLOCK % name)
    end = text.find("</script>", start)
    return (start, end) if end >= 0 else None


def checklist_commits(folder):
    """The commits recorded on the items of the checklists in folder, as (checklist, item, commit),
    and the checklists it couldn't read."""
    records, unreadable = [], []
    names = sorted(os.listdir(folder)) if os.path.isdir(folder) else []
    for name in names:
        if not name.endswith(".html"):
            continue
        text = open(os.path.join(folder, name), encoding="utf-8", errors="replace").read()
        span = block_span(text, "pass")
        try:
            items = json.loads(text[span[0]:span[1]])["items"]
            records += [(name, str(item.get("id")), str(c)) for item in items for c in item.get("commits", [])
                        if SHA.fullmatch(str(c))]
        except (TypeError, ValueError, KeyError, AttributeError):
            unreadable.append(name)
    return records, unreadable


def not_landed(repo, shas):
    """Of the recorded commits, those that aren't commits reachable from HEAD. After a squash merge or
    a rebase, the commit that landed the work has another hash, so the heatmap can't leave it out."""
    shas = sorted(set(shas))
    proc = subprocess.run(["git", "-C", repo, "cat-file", "--batch-check"], capture_output=True,
                          input="".join("%s^{commit}\n" % s for s in shas).encode())
    lost = set()
    for sha, line in zip(shas, proc.stdout.decode(errors="replace").splitlines()):
        found = line.split()
        if len(found) != 3 or found[1] != "commit" or subprocess.run(
                ["git", "-C", repo, "merge-base", "--is-ancestor", found[0], "HEAD"]).returncode != 0:
            lost.add(sha)
    return lost


def line_counts(repo, rev, paths):
    """Lines in each path at rev, read in one batch; a path missing there, or binary, is left out."""
    paths = [p for p in paths if "\n" not in p]
    if not paths:
        return {}
    proc = subprocess.run(["git", "-C", repo, "cat-file", "--batch"],
                          input="".join("%s:%s\n" % (rev, p) for p in paths).encode(), capture_output=True)
    data = proc.stdout
    counts = {}
    pos = 0
    for path in paths:
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
    return counts


def describe(commit):
    sha, stamp, subject = commit[:3]
    when = datetime.fromtimestamp(stamp, timezone.utc).strftime("%Y-%m-%d")
    return {"sha": sha[:9], "date": when, "subject": subject}


def page_json(value):
    """JSON for a page's data block: a line per file and pair, and nothing that could close the script tag."""
    parts = []
    for key, inner in value.items():
        if isinstance(inner, list) and inner:
            inner = "[\n  " + ",\n  ".join(json.dumps(v, ensure_ascii=False) for v in inner) + "\n ]"
        else:
            inner = json.dumps(inner, ensure_ascii=False)
        parts.append("%s: %s" % (json.dumps(key), inner))
    return ("{\n " + ",\n ".join(parts) + "\n}").replace("</", "<\\/")


def write_page(path, heatmap, project):
    """Put the heatmap into a checklist page, made from the template if it doesn't exist yet.
    Only the heatmap block changes, so the items are left as they were."""
    new = not os.path.exists(path)
    text = open(TEMPLATE if new else path, encoding="utf-8").read()
    if new:
        span = block_span(text, "pass")
        data = json.loads(text[span[0]:span[1]])
        # The pass's date: the one in the page's name, as .refactor-pass/2026-11-10.html, or else today.
        named = re.match(r"\d{4}-\d{2}-\d{2}", os.path.basename(path))
        day = named.group(0) if named else datetime.now().strftime("%Y-%m-%d")
        data.update(project=project, started=day, base=heatmap["head"], updated=day)
        text = text[:span[0]] + "\n" + json.dumps(data, indent=1, ensure_ascii=False) + "\n" + text[span[1]:]
    span = block_span(text, "heatmap")
    if not span:
        sys.exit("%s has no heatmap block; is it a checklist made from assets/page.html?" % path)
    text = text[:span[0]] + "\n" + page_json(heatmap) + "\n" + text[span[1]:]
    if os.path.dirname(path):
        os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path + ".tmp", "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(path + ".tmp", path)
    return new


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__.split("\n\n", 1)[1])
    parser.add_argument("scope", nargs="*", help="folders or globs to count (default: everything)")
    parser.add_argument("-C", dest="repo", default=".", help="the repo (default: the current directory)")
    parser.add_argument("-n", "--commits", type=int, default=200,
                        help="the window: this many of the latest non-merge commits (default 200)")
    parser.add_argument("--since", metavar="REV_OR_DATE",
                        help="the window: every commit after REV (a tag, branch or commit, itself not included), "
                             "or since a date, such as '3 months ago' or 2026-06-01")
    parser.add_argument("--exclude-commits", default="", metavar="SHAS",
                        help="comma-separated commits to leave out, such as a mass reformat or a vendored "
                             "import, which would make every file they touched look hot")
    parser.add_argument("--ignore", action="append", default=[], metavar="GLOB",
                        help="more file globs to leave out (added to the defaults: %s)"
                             % ", ".join(scoping.DEFAULT_IGNORE))
    parser.add_argument("--test", action="append", default=[], metavar="GLOB",
                        help="more globs naming test files, matched with case against the name or the path "
                             "(added to the defaults: %s, and folders named %s)"
                             % (", ".join(scoping.TEST_NAMES), ", ".join(scoping.TEST_FOLDERS)))
    parser.add_argument("--keep-tests", action="store_true",
                        help="count test files like the rest, in the table and the pairs")
    parser.add_argument("--top", type=int, default=25, help="files to print, and to put on --page (default 25)")
    parser.add_argument("--pairs", type=int, default=15,
                        help="pairs and groups to print, and tests, and to put on --page (default 15 each)")
    parser.add_argument("--min-shared", type=int, default=5,
                        help="a pair needs at least this many commits together (default 5, as code-maat; "
                             "try 3 on a short history)")
    parser.add_argument("--min-revs", type=int, default=5,
                        help="a pair's files need at least this many commits each (default 5), so a file changed "
                             "three times, each time with a busy file, doesn't score 100%%")
    parser.add_argument("--min-degree", type=int, default=30,
                        help="a pair needs at least this code-maat degree, in percent (default 30)")
    parser.add_argument("--keep-bots", action="store_true", help="count bots' commits too")
    parser.add_argument("--keep-ignore-revs", action="store_true",
                        help="count the commits listed in .git-blame-ignore-revs too")
    parser.add_argument("--keep-pass-commits", action="store_true",
                        help="count the commits recorded on the checklists in .refactor-pass/ too")
    parser.add_argument("--max-files", type=int, default=25,
                        help="commits changing more files than this, tests aside, are left out of the pairs, since "
                             "a sweeping rename or reformat pairs everything with everything (default 25)")
    parser.add_argument("--page", metavar="PATH",
                        help="also put the heatmap into this checklist page (a relative path is in the repo, or in "
                             "the main checkout from a linked worktree), making it from the skill's "
                             "assets/page.html if it doesn't exist; only the page's heatmap block changes")
    parser.add_argument("--show", action="append", default=[], metavar="FILE",
                        help="print this file's commits in the window (its name today), instead of the heatmap")
    args = parser.parse_args()

    repo = git(args.repo, "rev-parse", "--show-toplevel").strip()
    if subprocess.run(["git", "-C", repo, "rev-parse", "--verify", "--quiet", "HEAD"],
                      capture_output=True).returncode != 0:
        sys.exit("%s has no commits yet, so there's no history to read." % os.path.basename(repo))
    head = git(repo, "rev-parse", "--short=9", "HEAD").strip()
    tracked = scoping.tracked_files(repo, "HEAD")
    args.scope = scoping.resolve(args.repo, repo, args.scope, tracked)
    revs, since_rev = window_revs(repo, args.since, args.commits)
    edge = shallow_edge(repo)
    everything = read_log(repo, revs)
    cut = [c for c in everything if c[0] in edge]
    everything = [c for c in everything if c[0] not in edge]
    shallow = ("This is a shallow clone, so its history stops at %s (%s); that commit looks as if it adds "
               "every file, so it's left out. `git fetch --unshallow` fetches the rest of the history."
               % (describe(cut[0])["sha"], describe(cut[0])["date"])) if cut else ""
    if not everything:
        sys.exit("No commits in the window." + (" " + shallow if shallow else ""))

    def matching(prefixes):
        return set(c[0] for c in everything if any(c[0].startswith(p) for p in prefixes))

    folder, where = checklist_folder(repo)
    shown = os.path.relpath(folder, repo) if folder == os.path.join(repo, ".refactor-pass") else folder
    asked = matching([s.strip() for s in args.exclude_commits.split(",") if s.strip()])
    listed = set() if args.keep_ignore_revs else matching(ignore_revs(repo)) - asked
    records, unreadable = ([], []) if args.keep_pass_commits else checklist_commits(folder)
    for name in unreadable:
        print("Couldn't read the items of %s, so its commits are counted." % os.path.join(shown, name),
              file=sys.stderr)
    lost = not_landed(repo, [sha for _, _, sha in records]) if records else set()
    for name, ident in sorted(set((n, i) for n, i, sha in records if sha in lost)):
        shas = sorted(sha for n, i, sha in records if (n, i) == (name, ident) and sha in lost)
        print("%s, %s: %s %s reachable from HEAD, so the heatmap counts that work. If it was squash-merged or "
              "rebased, find the commit that landed it and record that hash instead."
              % (os.path.join(shown, name), ident, " and ".join(shas),
                 "isn't a commit" if len(shas) == 1 else "aren't commits"), file=sys.stderr)
    recorded = matching(set(sha for _, _, sha in records)) - asked - listed
    bots = set() if args.keep_bots else set(c[0] for c in everything if BOT.search(c[4])) - asked - listed - recorded
    excluded = asked | listed | recorded | bots
    commits = [c for c in everything if c[0] not in excluded]
    if not commits:
        sys.exit("Every commit in the window is left out.")
    newer = set(c[0] for c in commits[:(len(commits) + 1) // 2])
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
    files = defaultdict(lambda: {"commits": 0, "recent": 0, "added": 0, "removed": 0})
    sets = []  # Per commit, the files it changed.
    logs = defaultdict(list)  # Per file (in scope or not), the commits that changed it.
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
            if not scoping.in_scope(name, args.scope) or scoping.ignored(name, patterns):
                continue
            stats = files[name]
            if "binary" not in stats:  # Its newest change says whether it's binary now.
                stats["binary"] = added is None
            if name not in touched:
                stats["commits"] += 1
                stats["recent"] += sha in newer
            touched.add(name)
            if added is not None:
                stats["added"] += added
                stats["removed"] += removed
        if sha not in excluded:
            sets.append(touched)

    sizes = line_counts(repo, "HEAD", sorted(files))
    before = {}
    if base:
        then = line_counts(repo, base, sorted(set(earliest.get(p, p) for p in files)))
        before = dict((p, then.get(earliest.get(p, p), 0)) for p in files)
    rows = []
    for path, stats in files.items():
        if path not in sizes or stats["binary"]:  # Gone at HEAD, or binary.
            continue
        row = {"path": path, "commits": stats["commits"], "recent": stats["recent"],
               "churn": stats["added"] + stats["removed"], "added": stats["added"], "removed": stats["removed"],
               "size": sizes[path], "rel": round((stats["added"] + stats["removed"]) / max(sizes[path], 1), 2),
               "size_before": before.get(path, 0), "growth": sizes[path] - before.get(path, 0)}
        rows.append(row)
    rows.sort(key=lambda r: (-r["commits"] * r["size"], -r["commits"], -r["churn"], r["path"]))
    by_path = dict((r["path"], r) for r in rows)
    # Tests have their history read like the rest, but stay out of the table and the pairs.
    tests = set() if args.keep_tests else set(r["path"] for r in rows if scoping.is_test(r["path"], args.test))
    rows = [r for r in rows if r["path"] not in tests]
    alive = set(r["path"] for r in rows)

    shared, with_tests = Counter(), Counter()
    seen_in = defaultdict(set)  # Per file, the commits counted for pairs that changed it.
    too_big = 0
    for index, touched in enumerate(sets):
        mine = sorted(touched & alive)
        if len(mine) > args.max_files:
            too_big += 1
            continue
        shared.update(combinations(mine, 2))
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
            pairs.append(dict(a=a, b=b, **found))
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
            groups.append(dict(files=members, pairs=[min(counts), max(counts)], **measures(members, len(common))))
            grouped.update(combinations(members, 2))
    pairs = [p for p in pairs if (p["a"], p["b"]) not in grouped]
    together = sorted(groups + pairs, key=lambda r: (-r["shared"], -r["degree"], r.get("a") or r["files"][0]))
    together = together[:args.pairs]
    # Tests that change with several production files besides their own.
    tied = defaultdict(list)
    for (test, path), count in with_tests.items():
        if scoping.stem(test, True) != scoping.stem(path, False) and measures([test, path], count):
            tied[test].append({"path": path, "shared": count})
    tied = [{"test": test, "files": sorted(found, key=lambda f: (-f["shared"], f["path"]))}
            for test, found in tied.items() if len(found) > 1]
    tied.sort(key=lambda t: (-len(t["files"]), -sum(f["shared"] for f in t["files"]), t["test"]))

    window = {"commits": len(commits), "newest": describe(commits[0]), "oldest": describe(commits[-1]),
              "newer_half_from": describe(commits[(len(commits) + 1) // 2 - 1])["date"],
              "excluded": len(excluded), "excluded_asked": len(asked), "excluded_ignore_revs": len(listed),
              "excluded_checklists": len(recorded), "excluded_bots": len(bots), "too_big_for_pairs": too_big,
              "since": args.since, "tests_aside": None if args.keep_tests else len(tests), "shallow": bool(cut)}
    if args.show:
        for path in args.show:
            path = scoping.show_path(args.repo, repo, path, tracked)
            print("%s: %d of the %d commits from %s (%s) to %s (%s)" % (
                path, len(logs.get(path, [])), len(commits), window["oldest"]["sha"], window["oldest"]["date"],
                window["newest"]["sha"], window["newest"]["date"]))
            for commit in logs.get(path, []):
                info = describe(commit)
                print("  %s %s %s" % (info["sha"], info["date"], info["subject"]))
            print()
        return
    scope = args.scope or ["(everything)"]
    if args.page:
        options = {"top": args.top, "pairs": args.pairs, "max_files": args.max_files, "min_shared": args.min_shared,
                   "min_revs": args.min_revs, "min_degree": args.min_degree}
        heatmap = {"head": head, "scope": scope, "window": window, "options": options, "total_files": len(rows),
                   "files": rows[:args.top], "groups": [r for r in together if "files" in r],
                   "pairs": [r for r in together if "a" in r], "tests": tied[:args.pairs]}
        page = args.page if os.path.isabs(args.page) else os.path.join(os.path.dirname(folder), args.page)
        made = write_page(page, heatmap, os.path.basename(os.path.dirname(folder)))
        print("%s %s, with the heatmap.\n" % ("Made" if made else "Updated", page))

    print("%s at %s, scope: %s" % (os.path.basename(repo), head, " ".join(scope)))
    left_out = [(len(asked), "asked"), (len(listed), "in .git-blame-ignore-revs"),
                (len(recorded), "recorded on refactor checklists"), (len(bots), "by bots")]
    left_out = ", ".join("%d %s" % (n, why) for n, why in left_out if n)
    print("Window: %d commits, %s (%s) back to %s (%s)%s" % (
        len(commits), window["newest"]["sha"], window["newest"]["date"], window["oldest"]["sha"],
        window["oldest"]["date"], "; left out: " + left_out if left_out else ""))
    print("Newer half from %s. Ordered by commits times size." % window["newer_half_from"])
    if not args.keep_tests:
        print("Test files: %s." % ("%d changed in the window, set aside from the table and the pairs" % len(tests)
                                   if tests else "none in the scope changed in the window"))
    for note in [shallow, where]:
        if note:
            print(note)
    print()
    if rows:
        print("%7s %6s %7s %5s %7s %7s  file" % ("commits", "recent", "churn", "rel", "size", "growth"))
    else:
        print("No file in the scope, tests aside, changed in the window.")
    for row in rows[:args.top]:
        print("%7d %6d %7d %5.1f %7d %+7d  %s" % (row["commits"], row["recent"], row["churn"], row["rel"],
                                                 row["size"], row["growth"], row["path"]))
    if len(rows) > args.top:
        print("  ... %d more files changed in the window" % (len(rows) - args.top))
    print()
    print("Changed together (commits of %d files or fewer, tests aside; files with %d+ commits, %d+ shared, "
          "degree %d%%+):" % (args.max_files, args.min_revs, args.min_shared, args.min_degree))
    if groups:
        print("  A row of three or more files is a group: each pair of them qualifies, and the counts are of the "
              "commits that changed them all.")
    if too_big:
        print("  %d of the %d commits changed more than %d files and %s left out of these; raise --max-files to "
              "count them." % (too_big, len(commits), args.max_files, "is" if too_big == 1 else "are"))
    print("%7s %8s %7s" % ("shared", "quieter", "degree"))
    for row in together:
        # A group's pairs' own counts, when they differ from the commits that changed them all.
        least, most = row.get("pairs", [row["shared"]] * 2)
        spread = "" if least == most == row["shared"] else \
            " (each pair %d)" % least if least == most else " (each pair %d to %d)" % (least, most)
        print("%7d %7.0f%% %6.0f%%  %s%s" % (row["shared"], row["of_quieter"] * 100, row["degree"] * 100,
                                            " + ".join(row.get("files") or [row["a"], row["b"]]), spread))
    if not together:
        print("  none")
    if tests:
        print()
        print("Tests changed together with several production files besides their own (as above; "
              "commits together in brackets):")
        for row in tied[:args.pairs]:
            print("  %s: %d files, %s" % (row["test"], len(row["files"]),
                                          ", ".join("%s (%d)" % (f["path"], f["shared"]) for f in row["files"])))
        if not tied:
            print("  none")


if __name__ == "__main__":
    main()
