"""Compare measure.py's functions with real parsers' on public repos pinned to exact commits, outside the
default run, and fail where a set falls below its recorded floors.

For each set, the truth comes from a real parser: Python's ast (Python 3.8 or later), TypeScript's compiler
through Node for JavaScript and TypeScript (parsers/ts_truth.js), PHP's tokenizer (parsers/php_truth.php)
and Go's parser (parsers/go_truth.go). A function is found when measure.py reports one starting on the same
line. Four measures, each with a floor recorded from the numbers of the day it was set, a hair under them:

  found     the share of the parser's functions measure.py finds
  long      the share of those over 45 lines it finds
  ends      of those found, the share whose last line is the parser's
  extras    a ceiling on functions it reports that the parser doesn't have

A set whose parser isn't installed is skipped with a message, not failed. A clone already on disk at the
pinned commit is used where --repos-dir finds it (DIR/<its folder>); any other is fetched, at that commit
only, into the cache folder (default: refactor-pass-parsers in the system's temporary folder). The files
compared are read, never run. It tests the scripts beside tests/, or those REFACTOR_PASS_SCRIPTS names.

Examples:
  compare_parsers.py --repos-dir ~/code
  compare_parsers.py --only click --only flask
  compare_parsers.py --record
"""

import argparse
import ast
import fnmatch
import json
import os
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import support  # noqa: E402

PARSERS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "parsers")


class Set(object):
    """A repo pinned to a commit: its language, the folders read, the files left out, and the floors."""

    def __init__(self, name, language, url, sha, folders, floors, folder=None, leave_out=()):
        self.name, self.language, self.url, self.sha, self.folders = name, language, url, sha, folders
        self.floors = dict(zip(("found", "long", "ends", "extras"), floors))
        self.folder = folder or name
        self.leave_out = leave_out


# The floors: found %, long found %, ends right %, and the most extras. Recorded on 2026-11-11 from that day's
# numbers, a hair under them.
SETS = [
    Set("flask", "Python", "https://github.com/pallets/flask", "49943b5a94413a530761350f04e896f76e8d620e",
        ["src"], (99.8, 99.5, 99.8, 2)),
    Set("django", "Python", "https://github.com/django/django", "95636a4d7e8827832a8574dfcb9ae3d301c58d32",
        ["django"], (99.8, 99.5, 99.8, 2)),
    Set("requests", "Python", "https://github.com/psf/requests", "3c7baaa05ab4aa49cc819ce3a819d260de19c157",
        ["src"], (99.8, 99.5, 99.8, 2)),
    Set("click", "Python", "https://github.com/pallets/click", "8abb77a8432e03ed14a95f972b44f905279415a7",
        ["src"], (99.8, 99.5, 99.8, 2)),
    Set("nest", "TypeScript", "https://github.com/nestjs/nest", "f5a84c2ca3a76d830b733c8307ceeea82be54c18",
        ["packages"], (96.4, 99.5, 99.8, 5)),
    Set("taxonomy", "TypeScript", "https://github.com/shadcn-ui/taxonomy", "298a8857c7128a0d121e7f699dfd729f23b3966d",
        ["app", "components", "lib", "hooks", "config", "pages"], (99.8, 99.5, 99.8, 2)),
    Set("typeorm", "TypeScript", "https://github.com/typeorm/typeorm", "5a572a40bae2f85a1d5f7b87a0aa88bbbaec5ab3",
        ["packages"], (95.9, 99.5, 99.8, 2)),
    Set("excalidraw", "TypeScript", "https://github.com/excalidraw/excalidraw",
        "701b901a0f1ba3d0b390d9cdf63d112e25abac4b", ["packages", "excalidraw-app"], (99.4, 99.5, 99.7, 9)),
    Set("vue", "TypeScript", "https://github.com/vuejs/core", "7ef6817112bb420ef47a7252821b37caae016ac9",
        ["packages"], (96.9, 99.5, 99.8, 3), folder="core"),
    Set("trpc", "TypeScript", "https://github.com/trpc/trpc", "8eff9ff0ddf4be4a682bf205fb66b00a26901075",
        ["packages"], (98.3, 99.5, 99.7, 7)),
    Set("express", "JavaScript", "https://github.com/expressjs/express", "43fca52d28a422c8be48fd489cbd4f2d6152bab6",
        ["lib", "test"], (96.7, 99.5, 99.8, 5)),
    Set("hono", "TypeScript", "https://github.com/honojs/hono", "f6fbaf0299c48eea9e656e03e2ffe7ac755e8823",
        ["src"], (97.2, 99.5, 99.8, 9)),
    Set("query", "TypeScript", "https://github.com/TanStack/query", "8f6da1e2a1b5e9afd774cd12bd3865df5c432984",
        ["packages"], (98.0, 99.5, 99.8, 11)),
    Set("fastify", "JavaScript", "https://github.com/fastify/fastify", "0b076ca595d19951c536daf515c778b38cf6ba69",
        ["lib", "test"], (96.8, 99.5, 99.8, 4)),
    Set("kit", "JavaScript", "https://github.com/sveltejs/kit", "014dfec3df98be8edf6e217e98309c12ba51b4cf",
        ["packages"], (98.1, 99.5, 99.8, 3)),
    Set("mongoose", "JavaScript", "https://github.com/Automattic/mongoose", "6f90b9b1b2dcd8e3335773998601de20ae1549f7",
        ["lib"], (99.8, 99.5, 99.8, 9)),
    Set("axios", "JavaScript", "https://github.com/axios/axios", "4ee8d46fc463770b8f5da718d5449a5b027b2c08",
        ["lib"], (99.8, 99.5, 99.8, 10)),
    # Bundled and minified copies of the library's own code are left out, as a project's --ignore would.
    Set("socket.io", "JavaScript", "https://github.com/socketio/socket.io", "e94e021452b1020172fe2b7bafb646f38e96427c",
        ["packages"], (99.4, 99.5, 99.8, 7), leave_out=("*/client-dist/*", "*/dist/*", "*.min.js")),
    # Vendored libraries are left out.
    Set("lodash", "JavaScript", "https://github.com/lodash/lodash", "2b5e6f7399a7b48005140b5d5c6bc6c0e62919a8",
        ["."], (92.9, 94.5, 99.8, 3), leave_out=("vendor/*",)),
    Set("laravel", "PHP", "https://github.com/laravel/framework", "9e04882929e11f1a263f4009aa618e7107bf240b",
        ["src"], (99.7, 99.5, 99.8, 81)),
    Set("gin", "Go", "https://github.com/gin-gonic/gin", "0f09c3a9b4626d9fe9979cf4d0521d6ae32ab646",
        ["."], (99.8, 99.5, 99.7, 2)),
]


def run(command, **options):
    return subprocess.run(command, capture_output=True, **options)


def head(repo):
    result = run(["git", "-C", repo, "rev-parse", "HEAD"])
    return result.stdout.decode().strip() if result.returncode == 0 else None


def clone(one, repos_dirs, cache, fetch):
    """The folder holding the set's files at its pinned commit, and how it was found; or None and why not."""
    for folder in repos_dirs:
        for name in dict.fromkeys([one.folder, one.name]):
            path = os.path.join(folder, name)
            if os.path.isdir(path):
                at = head(path)
                if at == one.sha:
                    return path, "on disk"
    path = os.path.join(cache, "%s-%s" % (one.name, one.sha[:12]))
    if head(path) == one.sha:
        return path, "cached"
    if not fetch:
        return None, "no clone at %s, and fetching is off" % one.sha[:12]
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path)
    for command in (["git", "init", "-q", path],
                    ["git", "-C", path, "fetch", "-q", "--depth", "1", one.url, one.sha],
                    ["git", "-C", path, "-c", "advice.detachedHead=false", "checkout", "-q", "FETCH_HEAD"]):
        result = run(command)
        if result.returncode != 0:
            return None, "fetching it failed: %s" % result.stderr.decode(errors="replace").strip()
    return path, "fetched"


def find_typescript(given):
    """TypeScript's compiler, typescript.js: as given, or next to the tsc on the PATH."""
    if given:
        return given if os.path.isfile(given) else None
    tsc = shutil.which("tsc")
    if tsc:
        found = os.path.join(os.path.dirname(os.path.realpath(tsc)), os.pardir, "lib", "typescript.js")
        if os.path.isfile(found):
            return os.path.normpath(found)
    return None


def python_truth(repo, folders):
    if sys.version_info < (3, 8):
        raise LookupError("Python's ast gives a function's last line from 3.8 on")
    out = {}
    for sub in folders:
        for folder, dirs, names in os.walk(os.path.join(repo, sub)):
            dirs[:] = sorted(d for d in dirs if d not in (".git", "node_modules"))
            for name in sorted(names):
                if name.endswith(".py"):
                    path = os.path.join(folder, name)
                    with open(path, "rb") as f:
                        try:
                            tree = ast.parse(f.read())
                        except (SyntaxError, ValueError):
                            continue
                    out[os.path.relpath(path, repo).replace(os.sep, "/")] = [
                        [n.name, n.lineno, n.end_lineno] for n in ast.walk(tree)
                        if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
    return out


def tool_truth(command):
    result = run(command)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode(errors="replace").strip()[:500])
    return json.loads(result.stdout.decode("utf-8"))


def truth(one, repo, typescript):
    """The parser's functions, per path: or LookupError when its parser isn't installed."""
    if one.language == "Python":
        found = python_truth(repo, one.folders)
    elif one.language in ("JavaScript", "TypeScript"):
        if not shutil.which("node"):
            raise LookupError("node isn't installed")
        if not typescript:
            raise LookupError("TypeScript's compiler isn't found: give --typescript PATH/typescript.js")
        found = tool_truth(["node", os.path.join(PARSERS, "ts_truth.js"), typescript, repo] + one.folders)
    elif one.language == "PHP":
        if not shutil.which("php"):
            raise LookupError("php isn't installed")
        found = {}
        for sub in one.folders:
            found.update(tool_truth(["php", os.path.join(PARSERS, "php_truth.php"), repo, sub]))
    elif one.language == "Go":
        if not shutil.which("go"):
            raise LookupError("go isn't installed")
        found = tool_truth(["go", "run", os.path.join(PARSERS, "go_truth.go"), repo])
    else:
        raise LookupError("no parser for %s" % one.language)
    found = dict((path.replace(os.sep, "/"), rows) for path, rows in found.items())
    return dict((path, rows) for path, rows in found.items()
                if not any(fnmatch.fnmatch(path, pattern) for pattern in one.leave_out))


def compare(measure, repo, truth_by_path):
    """The four measures, with the counts behind them and the worst cases."""
    total = found = long_total = long_found = ends = extras = 0
    missed, extra, wrong = [], [], []
    for path, functions in sorted(truth_by_path.items()):
        with open(os.path.join(repo, path), "rb") as f:
            text = f.read().decode("utf-8", errors="replace")
        _, got, _ = measure.functions(path, text)
        got = got or []
        by_first = dict((g[1], g) for g in got)
        firsts = set()
        for name, first, last in functions:
            span = last - first + 1
            total += 1
            long_total += span > 45
            firsts.add(first)
            mine = by_first.get(first)
            if mine:
                found += 1
                long_found += span > 45
                if mine[2] == last:
                    ends += 1
                else:
                    wrong.append((abs(mine[2] - last), "%s:%d %s ends at %d, not %d"
                                  % (path, first, name, mine[2], last)))
            else:
                missed.append((span, "%s:%d %s (%d lines)" % (path, first, name, span)))
        for g in got:
            if g[1] not in firsts:
                extras += 1
                extra.append((g[3], "%s:%d %s (%d lines)" % (path, g[1], g[0], g[3])))
    share = lambda part, whole: 100.0 * part / whole if whole else 100.0  # noqa: E731
    return {"files": len(truth_by_path), "total": total, "found": share(found, total), "long_total": long_total,
            "long_found": long_found, "long": share(long_found, long_total), "ends": share(ends, found),
            "extras": extras, "missed": sorted(missed, reverse=True)[:5], "extra": sorted(extra, reverse=True)[:5],
            "wrong": sorted(wrong, reverse=True)[:5]}


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__.split("\n\n", 1)[1])
    parser.add_argument("--repos-dir", action="append", default=[], metavar="DIR",
                        help="a folder holding clones, each in a folder named as the set's (repeatable)")
    parser.add_argument("--cache", default=os.path.join(tempfile.gettempdir(), "refactor-pass-parsers"),
                        help="where to fetch the sets not found on disk")
    parser.add_argument("--no-fetch", action="store_true", help="skip the sets not found on disk")
    parser.add_argument("--typescript", metavar="PATH", help="TypeScript's typescript.js (default: beside tsc)")
    parser.add_argument("--only", action="append", default=[], metavar="NAME", help="compare only this set")
    parser.add_argument("--record", action="store_true", help="print floors a hair under today's numbers")
    parser.add_argument("--verbose", action="store_true", help="print each set's worst misses and extras")
    args = parser.parse_args()
    unknown = set(args.only) - set(s.name for s in SETS)
    if unknown:
        parser.error("no such set: %s (the sets: %s)" % (", ".join(sorted(unknown)), ", ".join(s.name for s in SETS)))
    measure = support.load("measure")
    typescript = find_typescript(args.typescript)
    print("Testing %s" % support.SCRIPTS)
    failed, skipped = [], []
    for one in SETS:
        if args.only and one.name not in args.only:
            continue
        repo, how = clone(one, args.repos_dir, args.cache, not args.no_fetch)
        if not repo:
            skipped.append(one.name)
            print("%s: skipped, %s." % (one.name, how))
            continue
        try:
            functions = truth(one, repo, typescript)
        except LookupError as e:
            skipped.append(one.name)
            print("%s: skipped, %s." % (one.name, e))
            continue
        got = compare(measure, repo, functions)
        floors = one.floors
        below = [k for k in ("found", "long", "ends") if got[k] < floors[k]]
        below += ["extras"] if got["extras"] > floors["extras"] else []
        print("%s (%s at %s, %s): %d functions in %d files; found %.1f%% (floor %.1f); over 45 lines %d of %d, "
              "%.1f%% (floor %.1f); ends right %.1f%% (floor %.1f); %d the parser doesn't have (ceiling %d)%s" % (
                  one.name, one.language, one.sha[:9], how, got["total"], got["files"], got["found"], floors["found"],
                  got["long_found"], got["long_total"], got["long"], floors["long"], got["ends"], floors["ends"],
                  got["extras"], floors["extras"], "  BELOW: " + ", ".join(below) if below else ""))
        if args.verbose or below:
            for label in ("missed", "extra", "wrong"):
                for _, text in got[label]:
                    print("    %s: %s" % (label, text))
        if args.record:
            print("    floors: (%.1f, %.1f, %.1f, %d)" % (
                max(0.0, int(got["found"] * 10) / 10.0 - 0.2), max(0.0, int(got["long"] * 10) / 10.0 - 0.5),
                max(0.0, int(got["ends"] * 10) / 10.0 - 0.2), got["extras"] + max(2, got["extras"] // 10)))
        if below:
            failed.append(one.name)
    print("%d below their floors%s; %d skipped%s." % (
        len(failed), " (%s)" % ", ".join(failed) if failed else "", len(skipped),
        " (%s)" % ", ".join(skipped) if skipped else ""))
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
