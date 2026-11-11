"""Count what measure.py gets wrong without a parser to say so, on public repos pinned to exact commits, for
the languages with none to compare with here (Kotlin, C#, Rust, Java, GDScript), outside the default run;
and fail where a set has more than its recorded ceilings.

Two counts. A function runs on when another function measure.py finds starts inside it at the same
indentation as its own first line, or further out: a nested function is indented deeper. A definition goes
unreported when a line holds one by a looser rule than measure.py's (Kotlin's fun, Rust's fn, GDScript's
func; in C# and Java a type, a name and a ( at a line's start), with a body after its parameters, and
measure.py finds no function there. The looser rule also takes in a few lines that aren't definitions (a
record, an attribute's line, a declaration followed by another's body), so its ceiling isn't zero. Neither
count sees a function that ends early; compare_parsers.py checks that where a parser is at hand. The
ceilings were recorded on 2026-11-11, and the repos are found or fetched as compare_parsers.py finds them.
It tests the scripts beside tests/, or those REFACTOR_PASS_SCRIPTS names.

Examples:
  run_ons.py --repos-dir ~/code
  run_ons.py --only okhttp --verbose
"""

import argparse
import os
import re
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compare_parsers  # noqa: E402

support = compare_parsers.support


class Set(object):
    """A repo pinned to a commit, the extensions read, and the most run-ons and unreported definitions allowed."""

    def __init__(self, name, language, url, sha, extensions, ceilings, folder=None):
        self.name, self.language, self.url, self.sha = name, language, url, sha
        self.ceilings = dict(zip(("run on", "unreported"), ceilings))
        self.extensions = tuple(extensions.split())
        self.folder = folder or name


# The ceilings: run-ons, and unreported definitions (today's count and a tenth more, at least two more).
SETS = [
    Set("okhttp", "Kotlin", "https://github.com/square/okhttp", "4162e9da32f636442bc789a7576144fe5972d0a5",
        ".kt .kts", (0, 31)),
    Set("kotlinpoet", "Kotlin", "https://github.com/square/kotlinpoet", "f4e88d3655b0f5f795186ea8cf3cb5a8ceb6db01",
        ".kt .kts", (0, 19)),
    Set("Exposed", "Kotlin", "https://github.com/JetBrains/Exposed", "0957638c87e7a6ffae3835b0e11414ab2c8c65ac",
        ".kt .kts", (0, 37)),
    Set("Newtonsoft.Json", "C#", "https://github.com/JamesNK/Newtonsoft.Json",
        "52fa3aef1f2cadcd3a3f874251eddc98d3efbbaa", ".cs", (0, 56)),
    Set("Dapper", "C#", "https://github.com/DapperLib/Dapper", "eb47546a408bbf6c178bda4f04dc205bc51ffbfe", ".cs",
        (0, 20)),
    Set("Polly", "C#", "https://github.com/App-vNext/Polly", "98eaf1220c5e4ab58e0b4170eed8827f81e12cc3", ".cs",
        (0, 114)),
    Set("ripgrep", "Rust", "https://github.com/BurntSushi/ripgrep", "178cc027e283fd965cb72d0a7395b219eada170c",
        ".rs", (0, 2)),
    Set("serde", "Rust", "https://github.com/serde-rs/serde", "aa7913ad0211fef960df68e7812a6211145a888c", ".rs",
        (0, 4)),
    Set("bat", "Rust", "https://github.com/sharkdp/bat", "8cf33bdde9a6e4c11d0f866415b1fc867df0cd40", ".rs",
        (0, 3)),
    Set("gson", "Java", "https://github.com/google/gson", "a961b0fe088f8558d00cc1b56e506a3656907a91", ".java",
        (0, 35)),
    Set("jsoup", "Java", "https://github.com/jhy/jsoup", "d90d57521d931db7bf7ee464a4c0a1a9293db088", ".java",
        (0, 2)),
    Set("javapoet", "Java", "https://github.com/square/javapoet", "b9017a9503b76e11b4ad4c1a9f050e2d29112cb0",
        ".java", (0, 2)),
    Set("godot-demo-projects", "GDScript", "https://github.com/godotengine/godot-demo-projects",
        "b761b4cd5718a7118f2c95eb55f181d0a5f004f1", ".gd", (0, 2)),
    Set("beehave", "GDScript", "https://github.com/bitbrain/beehave", "fe589153fa780a3f88989578ceb5f539afffb7c2",
        ".gd", (0, 2)),
    Set("phantom-camera", "GDScript", "https://github.com/ramokz/phantom-camera",
        "9874dfe6882724362ee10b15788f7811beb6371a", ".gd", (0, 2)),
]

# The looser rule for a definition, per language, read on a line's code (its strings and comments taken out).
DEFINITION = {
    "Kotlin": re.compile(r"\bfun\s+(?:<[^>]*>\s*)?(?:[\w.<>?]+\.)?`?\w+`?\s*\("),
    "Rust": re.compile(r"\bfn\s+\w+\s*[<(]"),
    "GDScript": re.compile(r"^\s*(?:static\s+)?func\s+\w+\s*\("),
    "C#": re.compile(r"^\s*(?:\[[^\]]*\]\s*)*(?:\w+\s+)*[\w<>\[\],.?()]+\s+(?!(?:static|async|new|return|throw|"
                     r"in|is|as|when|case|await)\b)[\w.]+(?:<[^()]*>)?\s*\("),
    "Java": re.compile(r"^\s*(?:@\w+(?:\([^)]*\))?\s+)*(?:\w+\s+)*(?:<[^>]*>\s+)?[\w<>\[\],.?]+\s+(?!(?:new|return|"
                       r"throw|case|instanceof)\b)\w+\s*\("),
}
STATEMENT = re.compile(r"\s*(?:return|if|for|foreach|while|switch|catch|else|do|new|throw|case|using|lock|await|var|"
                       r"yield)\b")
# After the parameters' ), what comes first: a body's { or = or =>, or a ; (none), within a few lines.
BODY = re.compile(r"\)[^;{}=]*?(\{|;|=>|=(?!=)|$)")


def indent(line):
    return len(line) - len(line.lstrip())


def check(measure, repo, extensions, language):
    """The functions found, those that run on (lines, path, first, last, name, where the other starts), and
    the definitions unreported (path, line, its code)."""
    count, run_on, unreported = 0, [], []
    for path in compare_parsers.files_under(repo, ["."], extensions):
        with open(os.path.join(repo, path), "rb") as f:
            text = f.read().decode("utf-8", errors="replace")
        lines = text.split("\n")
        functions = measure.functions(path, text)[1] or []
        count += len(functions)
        starts = sorted(f[1] for f in functions)
        for name, first, last in [f[:3] for f in functions]:
            inside = next((s for s in starts
                           if first < s <= last and indent(lines[s - 1]) <= indent(lines[first - 1])), None)
            if inside:
                run_on.append((last - first + 1, path, first, last, name, inside))
        kind = measure.BY_EXTENSION[os.path.splitext(path)[1].lower()]
        try:
            code, inside = measure.skeleton(lines, kind[4], kind[5], False, kind[0])
        except TypeError:  # An older measure.py, whose skeleton() takes no language.
            code, inside = measure.skeleton(lines, kind[4], kind[5], False)
        found = set(starts)
        for i, line in enumerate(code):
            if inside[i] or i + 1 in found or STATEMENT.match(line) or not DEFINITION[language].search(line):
                continue
            body = BODY.search(" ".join(code[i:i + 6]))
            if language == "GDScript" or (body and body.group(1) in ("{", "=", "=>")):
                unreported.append((path, i + 1, line.strip()[:100]))
    return count, sorted(run_on, reverse=True), unreported


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__.split("\n\n", 1)[1])
    parser.add_argument("--repos-dir", action="append", default=[], metavar="DIR",
                        help="a folder holding clones, each in a folder named as the set's (repeatable)")
    parser.add_argument("--cache", default=os.path.join(tempfile.gettempdir(), "refactor-pass-parsers"),
                        help="where to fetch the sets not found on disk")
    parser.add_argument("--no-fetch", action="store_true", help="skip the sets not found on disk")
    parser.add_argument("--only", action="append", default=[], metavar="NAME", help="check only this set")
    parser.add_argument("--verbose", action="store_true", help="print each set's longest run-ons and some unreported")
    args = parser.parse_args()
    unknown = set(args.only) - set(s.name for s in SETS)
    if unknown:
        parser.error("no such set: %s (the sets: %s)" % (", ".join(sorted(unknown)), ", ".join(s.name for s in SETS)))
    measure = support.load("measure")
    print("Testing %s" % support.SCRIPTS)
    failed, skipped = [], []
    for one in SETS:
        if args.only and one.name not in args.only:
            continue
        repo, how = compare_parsers.clone(one, args.repos_dir, args.cache, not args.no_fetch)
        if not repo:
            skipped.append(one.name)
            print("%s: skipped, %s." % (one.name, how))
            continue
        count, run_on, unreported = check(measure, repo, one.extensions, one.language)
        over = [k for k, got in (("run on", run_on), ("unreported", unreported)) if len(got) > one.ceilings[k]]
        print("%s (%s at %s, %s): %d functions; %d run on (ceiling %d); %d unreported (ceiling %d)%s" % (
            one.name, one.language, one.sha[:9], how, count, len(run_on), one.ceilings["run on"], len(unreported),
            one.ceilings["unreported"], "  OVER: " + ", ".join(over) if over else ""))
        if args.verbose or over:
            for row in run_on[:5]:
                print("    run on: %d lines, %s:%d-%d %s, past the function at line %d" % row)
            for row in unreported[::max(1, len(unreported) // 5)][:5]:
                print("    unreported: %s:%d %s" % row)
        if over:
            failed.append(one.name)
    print("%d over their ceilings%s; %d skipped%s." % (
        len(failed), " (%s)" % ", ".join(failed) if failed else "", len(skipped),
        " (%s)" % ", ".join(skipped) if skipped else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
