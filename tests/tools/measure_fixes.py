"""Measure the heatmap's fixes trace against commits labelled by hand, on public repos pinned to exact commits,
outside the default run, and fail where a set falls below its recorded floors.

Each commit in tests/fixes_labels.txt was labelled fix or not by one reader, from its message and its diff,
before the rules were written: a fix corrects a defect in the repo as it stood (wrong behaviour, a crash, a
security hole, a regression, wrong public types, a build or a test that was broken, a revert of a change that
broke something); features, refactors, performance work, documentation, formatting, lint, CI and tooling,
dependency bumps, releases and changes for a new version of a dependency or a platform are not. The trace's
own definition is narrower, a fix of the project's own code, so a commit counts as a fix here only if it's
labelled one and changed a file of the project's code: not documentation, tests, or CI, build or dependency
files, as the heatmap tells them apart. --broad counts every commit labelled fix, as the reader did. Its sets:

  dev       the latest commits of each development repo, people's only (as the heatmap counts them),
            which the rules were written from
  revert    commits of the development repos whose subject or body speaks of a revert, from further back
  word      commits of the development repos drawn for one word or exclusion each, to measure it
  aside     the latest commits of three repos kept aside from the rule-writing and labelled after it
  tagged    every third of the latest 90 commits of three repos that put tags in brackets, labelled after
            the tags were read: one by component (react), one by ticket (calcite), one by type (mmengine)

Each commit is read as the heatmap reads it: in a window of the repo's latest commits reaching back to the
oldest labelled one, its type read as a label where at least half the latest 200 people's subjects carry one.
For each repo and set, precision (of the commits read as fixes, the share labelled fix) and recall (of
those labelled fix, the share read as one), each with a floor recorded from the numbers of the day it was
set, a hair under them; and per tier, its precision. --words drops each word and exclusion in turn and
says what it brought. A clone on disk at the pinned commit is used where --repos-dir finds it; any other is
fetched with enough history into the cache folder. Nothing is run but git. It tests the skill's scripts, or
those REFACTOR_PASS_SCRIPTS names.

Examples:
  measure_fixes.py --repos-dir ~/code
  measure_fixes.py --only flask --errors
  measure_fixes.py --words
  measure_fixes.py --record
"""

import argparse
import os
import sys
import tempfile
from collections import Counter, defaultdict

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from compare_parsers import clone, support  # noqa: E402

LABELS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "fixes_labels.txt")


class Repo(object):
    """A repo pinned to a commit, the commits read back from it, and per set its floors: (precision, recall)."""

    def __init__(self, name, url, sha, window, floors):
        self.name, self.url, self.sha, self.window, self.floors = name, url, sha, window, floors


# The floors, in percent: per set, precision and recall of fixes of the project's own code. Recorded on
# 2026-11-12 from that day's numbers, two points under them; the tagged set's on 2026-11-13, django's dev recall
# then, when code in a docs folder became code, and the revert set's of gin, pinia and hutool, when a re-landing
# came to read as nothing and a revert without git's line by its own words.
REPOS = [
    Repo("flask", "https://github.com/pallets/flask", "49943b5a94413a530761350f04e896f76e8d620e", 4000,
         {"dev": (83, 48), "revert": (48, 18), "word": (78, 73)}),
    Repo("gin", "https://github.com/gin-gonic/gin", "0f09c3a9b4626d9fe9979cf4d0521d6ae32ab646", 2500,
         {"dev": (91, 85), "revert": (86, 86), "word": (98, 98)}),
    Repo("pinia", "https://github.com/vuejs/pinia", "4817135a25431172d363bd928476db7cdbf875c4", 3000,
         {"dev": (98, 90), "revert": (98, 73)}),
    Repo("django", "https://github.com/django/django", "a0f2e29e0a98ee14aa808ebe38ec5fb79c8af71f", 800,
         {"dev": (91, 58), "revert": (98, 64), "word": (91, 91)}),
    Repo("lua", "https://github.com/lua/lua", "8cb93bada561977eb370819e39d7d644e5fd0a3f", 4000,
         {"dev": (92, 56), "word": (73, 73)}),
    Repo("ripgrep", "https://github.com/BurntSushi/ripgrep", "178cc027e283fd965cb72d0a7395b219eada170c", 2500,
         {"dev": (98, 31), "revert": (98, 48), "word": (98, 98)}),
    Repo("hutool", "https://github.com/chinabugotech/hutool", "87ec11862baae72914df703e25939eb44a8a843c", 4000,
         {"dev": (94, 78), "revert": (98, 0), "word": (92, 88)}),
    Repo("requests", "https://github.com/psf/requests", "3c7baaa05ab4aa49cc819ce3a819d260de19c157", 1000,
         {"aside": (98, 36)}),
    Repo("nest", "https://github.com/nestjs/nest", "afa6e3d3801f58750dc80ad0970c0bc52850ed2a", 1000,
         {"aside": (94, 98)}),
    Repo("redis", "https://github.com/redis/redis", "df10f323951f024df7f3a9a86274ef2fab7a7fa1", 1000,
         {"aside": (91, 46)}),
    Repo("react", "https://github.com/facebook/react", "df6aa4ec76cff5b3adde531c6fe8c36099e0469b", 200,
         {"tagged": (98, 40)}),
    Repo("calcite", "https://github.com/apache/calcite", "838ec33a020f9823b95a275fee959f4b6d04dcee", 200,
         {"tagged": (98, 19)}),
    Repo("mmengine", "https://github.com/open-mmlab/mmengine", "f8a8b1b3b3051175a8babe5df9c753a981919087", 200,
         {"tagged": (53, 98)}),
]
SETS = ["dev", "revert", "word", "aside", "tagged"]
TIERS = {1: "revert", 2: "type", 3: "words"}


def read_labels(path=LABELS):
    """Per (repo, set), the labelled commits: [(short hash, is a fix, the tier recorded, the words)]."""
    found, key = defaultdict(list), None
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("@ "):
                key = tuple(line[2:].split())
            elif line and not line.startswith("#"):
                sha, label, tier, words = line.split(" ", 3)
                found[key].append((sha, label == "f", int(tier), words))
    return found


def record_tiers(now, path=LABELS):
    """Write each commit's tier as read now beside its label, where it was read."""
    out, repo = [], None
    with open(path, encoding="utf-8") as f:
        for line in f:
            if line.startswith("@ "):
                repo = line.split()[1]
            elif line.strip() and not line.startswith("#"):
                sha, label, tier, words = line.rstrip("\n").split(" ", 3)
                line = "%s %s %d %s\n" % (sha, label, now.get((repo, sha), int(tier)), words)
            out.append(line)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write("".join(out))


def load(heatmap, one, path, labelled):
    """The repo's window as the heatmap reads it, whether its types read as labels, its labelled commits, and per
    labelled short hash whether it changed a file of the project's own code."""
    window = heatmap.read_log(path, ["-n", str(one.window), "HEAD"])
    people = [c for c in window if not heatmap.HOUSEKEEPING.search(c[4])]
    typed = heatmap.typed_share(people[:200]) >= heatmap.LABELLED
    by_short = dict((c[0][:9], c) for c in people)
    missing = [sha for sha in labelled if sha not in by_short]
    if missing:
        raise LookupError("%d labelled commits aren't among its latest %d: %s" % (
            len(missing), one.window, ", ".join(missing[:5])))
    chosen = [by_short[sha] for sha in labelled]

    def is_test(path):
        return heatmap.scoping.is_test(path, [], [])

    tops = heatmap.package_tops(heatmap.scoping.tracked_files(path, "HEAD"))
    code = dict((c[0][:9], any(not heatmap.not_code(change[0], is_test, tops) for change in c[3])) for c in chosen)
    return window, typed, chosen, code, tops


def read_repo(heatmap, loaded):
    """Per labelled short hash, how the heatmap reads it: (tier, what said so, whether it changed the project's
    own code)."""
    window, typed, chosen, code, tops = loaded
    trace = heatmap.fix_trace(chosen, window, typed, lambda path: heatmap.scoping.is_test(path, [], []), tops=tops)
    return dict((c[0][:9], trace[c[0]][:2] + (code[c[0][:9]],)) for c in chosen)


def scores(pairs):
    """(precision, recall, right, called, fixes) over (is a fix, read as one) pairs, in percent."""
    right = sum(1 for fix, read in pairs if fix and read)
    called = sum(1 for fix, read in pairs if read)
    fixes = sum(1 for fix, read in pairs if fix)
    return (100.0 * right / called if called else 100.0, 100.0 * right / fixes if fixes else 100.0,
            right, called, fixes)


def ablate(heatmap, reread):
    """For each word, exclusion and rule, what it brings: the right and wrong calls lost or gained without it."""
    base = reread()
    rows = []

    def without(kind, name, change, undo):
        change()
        try:
            after = reread()
        finally:
            undo()
        rows.append((kind, name, base[0] - after[0], base[1] - after[1]))

    for name in list(heatmap.FIX_WORDS):
        forms = heatmap.FIX_WORDS[name]
        without("word", name, lambda: heatmap.FIX_WORDS.pop(name), lambda: heatmap.FIX_WORDS.__setitem__(name, forms))
    for word in list(heatmap.FIX_CHINESE):
        place = heatmap.FIX_CHINESE.index(word)
        without("word", word, lambda: heatmap.FIX_CHINESE.remove(word),
                lambda: heatmap.FIX_CHINESE.insert(place, word))
    for table in (heatmap.NOT_FIX_WORDS, heatmap.NOT_FIX_PHRASES):
        for name in list(table):
            forms = table[name]
            without("exclusion", name, lambda: table.pop(name), lambda: table.__setitem__(name, forms))
    for word in list(heatmap.NOT_FIX_CHINESE):
        place = heatmap.NOT_FIX_CHINESE.index(word)
        without("exclusion", word, lambda: heatmap.NOT_FIX_CHINESE.remove(word),
                lambda: heatmap.NOT_FIX_CHINESE.insert(place, word))
    for name, module, function in (("documentation only", heatmap, "is_doc"),
                                   ("CI, build, deps only", heatmap, "is_chore"),
                                   ("tests only", heatmap.scoping, "is_test")):
        kept = getattr(module, function)
        without("exclusion", name, lambda: setattr(module, function, lambda *given: False),
                lambda: setattr(module, function, kept))
    return base, rows


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__.split("\n\n", 1)[1])
    parser.add_argument("--repos-dir", action="append", default=[], metavar="DIR",
                        help="a folder holding clones, each in a folder named as the repo (repeatable)")
    parser.add_argument("--cache", default=os.path.join(tempfile.gettempdir(), "refactor-pass-fixes"),
                        help="where to fetch the repos not found on disk")
    parser.add_argument("--no-fetch", action="store_true", help="skip the repos not found on disk")
    parser.add_argument("--only", action="append", default=[], metavar="NAME", help="measure only this repo")
    parser.add_argument("--errors", action="store_true", help="print each commit read the other way")
    parser.add_argument("--words", action="store_true",
                        help="print what each word and exclusion brings, over the dev, revert and word sets")
    parser.add_argument("--record", action="store_true", help="print floors a hair under today's numbers")
    parser.add_argument("--broad", action="store_true",
                        help="count every commit labelled fix as one, tests, build and CI fixes included, as the "
                             "reader labelled them, not only those that changed the project's own code")
    parser.add_argument("--record-tiers", action="store_true",
                        help="write each commit's tier as read today beside its label in tests/fixes_labels.txt")
    args = parser.parse_args()
    unknown = set(args.only) - set(r.name for r in REPOS)
    if unknown:
        parser.error("no such repo: %s (the repos: %s)" % (", ".join(sorted(unknown)),
                                                          ", ".join(r.name for r in REPOS)))
    heatmap = support.load("heatmap")
    labels = read_labels()
    print("Testing %s" % support.SCRIPTS)
    failed, skipped, changed = [], [], []
    every = defaultdict(list)  # Per set, (is a fix, tier read) for each commit.
    loaded = {}  # Per repo, its window and labelled commits, for --words.
    now = {}  # Per (repo, short hash), its tier as read today, for --record-tiers.
    for one in REPOS:
        if args.only and one.name not in args.only:
            continue
        path, how = clone(one, args.repos_dir, args.cache, not args.no_fetch, one.window + 100)
        if not path:
            skipped.append(one.name)
            print("%s: skipped, %s." % (one.name, how))
            continue
        mine = dict(((s, row[0]), row) for s in SETS for row in labels.get((one.name, s), []))
        try:
            loaded[one.name] = load(heatmap, one, path, sorted(set(sha for _, sha in mine)))
        except LookupError as e:
            failed.append(one.name)
            print("%s: %s." % (one.name, e))
            continue
        typed = loaded[one.name][1]
        read = read_repo(heatmap, loaded[one.name])
        now.update(((one.name, sha), found[0]) for sha, found in read.items())
        parts = []
        for name in SETS:
            rows = labels.get((one.name, name), [])
            if not rows:
                continue
            rows = [(sha, fix and (args.broad or read[sha][2]), tier, words) for sha, fix, tier, words in rows]
            pairs = [(fix, read[sha][0]) for sha, fix, _, _ in rows]
            every[name] += pairs
            precision, recall, right, called, fixes = scores(pairs)
            floor = one.floors.get(name, (0, 0))
            below = precision < floor[0] or recall < floor[1]
            parts.append("%s %d commits, %d fixes: precision %.0f%% (%d of %d; floor %d), recall %.0f%% (floor %d)%s"
                         % (name, len(rows), fixes, precision, right, called, floor[0], recall, floor[1],
                            "  BELOW" if below else ""))
            if below and one.name + " " + name not in failed:
                failed.append(one.name + " " + name)
            for sha, fix, tier, words in rows:
                if read[sha][0] != tier:
                    changed.append("%s %s: recorded %d, now %d (%s)" % (one.name, sha, tier, read[sha][0],
                                                                       read[sha][1]))
                if args.errors and bool(read[sha][0]) != fix:
                    print("    %s %s %s, %s: %s" % ("missed" if fix else "wrongly read as a fix:", one.name, sha,
                                                    words, read[sha][1] or "nothing said"))
            if args.record:
                parts[-1] += "  floors (%d, %d)" % (max(0, int(precision) - 2), max(0, int(recall) - 2))
        print("%s at %s (%s; %s): %s" % (one.name, one.sha[:9], how, "typed" if typed else "untyped",
                                         "; ".join(parts)))
    for name in SETS:
        pairs = every.get(name)
        if not pairs:
            continue
        precision, recall, right, called, fixes = scores(pairs)
        tiers = Counter(t for _, t in pairs if t)
        good = Counter(t for fix, t in pairs if t and fix)
        print("%s, all: %d commits, %d fixes; precision %.1f%% (%d of %d), recall %.1f%%; by tier: %s" % (
            name, len(pairs), fixes, precision, right, called, recall, ", ".join(
                "%s %d of %d" % (TIERS[t], good[t], tiers[t]) for t in sorted(tiers))))
    if changed:
        print("%d commits read differently from the tier recorded beside their label:" % len(changed))
        for line in changed:
            print("  " + line)
    if args.record_tiers:
        record_tiers(now)
    if args.words and loaded:

        def reread():
            right = wrong = 0
            for name, window in loaded.items():
                read = read_repo(heatmap, window)
                for kind in ("dev", "revert", "word"):
                    for sha, fix, _, _ in labels.get((name, kind), []):
                        fix = fix and (args.broad or read[sha][2])
                        if read[sha][0]:
                            right, wrong = right + fix, wrong + (not fix)
            return right, wrong

        base, rows = ablate(heatmap, reread)
        print("What each brings, over the dev, revert and word sets (%d right and %d wrong calls with all):"
              % base)
        for kind, name, right, wrong in rows:
            if kind == "word":
                print("  word %-20s %3d right, %3d wrong" % (name, right, wrong))
            else:
                print("  exclusion %-15s %3d wrong calls saved, %3d right ones lost" % (name, -wrong, -right))
    print("%d below their floors%s; %d skipped%s." % (
        len(failed), " (%s)" % ", ".join(failed) if failed else "", len(skipped),
        " (%s)" % ", ".join(skipped) if skipped else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
