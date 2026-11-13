#!/usr/bin/env python3
# Copyright (c) 2026 Armand Kaufmann. MIT License: https://github.com/armandkaufmann/refactor-pass
"""Check a refactor checklist page after an edit to its pass block.

It checks that both data blocks parse, that every field is one the page
shows, with the right kind of value, that each item has a unique ID and a
known status, and that each item starts with its ID and status on one line,
so a status update stays a one-line edit:

  {"id": "R4", "status": "todo", ...   becomes   {"id": "R4", "status": "doing", ...

It checks too that dates are written 2026-11-10, and that a refactor's size
is S, M or L and its risk Low, Medium or High, as the page shows them. An
item that cites fixes has them per file: how many of its newest commits
were read (the sample), how many of its fixes are in the newer half (or
null), the fixes counted that the heatmap marked, those it didn't, and those
it marked that were left out, each a hash once, no more than were read. The
heatmap block is heatmap.py's to write; where it counts fixes (a heatmap
from before it did has none), those counts are checked too.

It prints a line per kind of item, then any problems: errors (the page or a
later pass would go wrong) and warnings (something the skill asks for is
missing or left empty, such as a refactor's plan, an item's note or the
whole pass block, or more than one item in progress). It exits 1 on an
error, and
says so plainly for a page that doesn't exist or is still the blank
template, which heatmap.py --page fills in. Reads the page only.

Usage:
  check_page.py PAGE
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime

# No __pycache__ is written, so a run leaves the skill's folder as it was.
sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scoping  # noqa: E402

BLOCK = '<script type="application/json" id="%s">'
STATUSES = ["todo", "doing", "waiting", "done", "skipped"]
SIZES = ["S", "M", "L"]
RISKS = ["Low", "Medium", "High"]
# The fields of the pass block and of each thing in it, with the kind of value
# each takes. An item's "from" is optional: the date of the checklist it was
# carried over from.
PASS = {"project": str, "started": str, "base": str, "updated": str, "summary": str, "checks": list,
        "earlier": (dict, type(None)), "items": list, "left_alone": list, "log": list}
REFACTOR = {"id": str, "status": str, "title": str, "eases": str, "smells": list, "cost": dict, "plan": list,
            "files": list, "size": str, "risk": str, "verify": str, "commits": list, "outcome": str}
OTHER = {"id": str, "status": str, "title": str, "note": str, "commits": list, "outcome": str}
COST = {"today": str, "after": str}
EARLIER = {"checklist": str, "results": list}
RESULT = {"id": str, "title": str, "eases": str, "cost": dict, "change": str, "actual": str, "note": str}
# An item's fixes, per file: how many of its newest commits were read (the sample), how many of its fixes are in
# the window's newer half (null where nearly all the sample is), the fixes counted that the heatmap marked, those
# it didn't (found by reading), and those it marked that weren't fixes of the file.
FIXES = {"file": str, "read": int, "newer": (int, type(None)), "marked": list, "found": list, "dropped": list}
# The fixes trace's facts in the heatmap block's window, as heatmap.py writes them.
FIX_FACTS = {"fixes": int, "revert": int, "type": int, "words": int, "typed": (int, float), "labels": bool,
             "closing": int, "withdrawn": int, "thin": bool, "language": bool, "complete": bool}
KIND_NAMES = {"R": "refactors", "F": "small fixes", "L": "later", "D": "your call"}
WORDS = {str: "text", list: "a list", dict: "an object", int: "a whole number", bool: "true or false",
         (int, float): "a number", (int, type(None)): "a whole number or null"}


def parse(text, name, errors):
    """A data block's value, read as a browser reads it: up to where the browser ends the block."""
    start = text.find(BLOCK % name)
    end, hidden = scoping.script_end(text, start + len(BLOCK % name)) if start >= 0 else (-1, None)
    if end < 0 and not hidden:
        errors.append("No %s block: the page should end with the template's two data blocks." % name)
        return None
    start += len(BLOCK % name)
    try:
        if end < 0:
            raise ValueError("it never ends")
        return json.loads(text[start:end])
    except ValueError as e:
        def line(at):
            return text[:at].count("\n") + 1
        if hidden or not text.startswith("</script>", end):
            why = ("<!-- at line %d, and then <script at line %d, keep it from seeing where the block ends"
                   % (line(hidden[0]), line(hidden[1])) if hidden else
                   "the %s at line %d ends the block there" % (text[end:end + 8], line(end)))
            errors.append("The %s block can't be read by a browser: %s. Write each < in the block's text as "
                          "\\u003c, which JSON reads as <." % (name, why))
        else:
            errors.append("The %s block doesn't parse, at line %d of the page: %s. A trailing comma or an "
                          "unescaped quote is the usual cause; a text holding </script> must write it <\\/script>."
                          % (name, text[:start].count("\n") + getattr(e, "lineno", 1), getattr(e, "msg", e)))
        return None


def fields(where, value, shape, errors, optional=()):
    """Check value has exactly shape's fields, each of the right kind."""
    if not isinstance(value, dict):
        errors.append("%s should be an object." % where)
        return False
    for key in value:
        if key not in shape and key not in optional:
            errors.append("%s has a field the page doesn't show: %r (it shows %s)."
                          % (where, key, ", ".join(list(shape) + ["%s if wanted" % o for o in optional])))
    for key, kind in shape.items():
        if key not in value:
            errors.append("%s is missing %r." % (where, key))
        elif not isinstance(value[key], kind) or (isinstance(value[key], bool) and kind is not bool):
            errors.append("%s: %r should be %s." % (where, key, WORDS.get(kind, "an object or null")))
    return True


def texts(where, values, errors):
    if isinstance(values, list) and not all(isinstance(v, str) for v in values):
        errors.append("%s: each should be text." % where)


def date(where, value, errors):
    """Check a date is written as 2026-11-10, which the page shows as 10 Nov 2026."""
    try:
        datetime.strptime(value, "%Y-%m-%d")
        right = bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))  # strptime alone takes 2026-1-5.
    except (TypeError, ValueError):
        right = False
    if not right:
        errors.append("%s should be a date written as 2026-11-10, not %r." % (where, value))


def filled(value):
    """Whether a field holds something: text that isn't blank, a list with something in it, or an object (a
    cost) with every value filled."""
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, list):
        return any(filled(v) for v in value)
    if isinstance(value, dict):
        return bool(value) and all(filled(v) for v in value.values())
    return value is not None


def one_of(where, value, allowed, errors):
    if value not in allowed:
        errors.append("%s should be %s or %s, not %r." % (where, ", ".join(allowed[:-1]), allowed[-1], value))


def is_hash(value):
    """Whether value is a commit's hash as an item records it: 7 to 40 of its hex digits, in lower case."""
    return isinstance(value, str) and bool(re.fullmatch(r"[0-9a-f]{7,40}", value))


def check_fixes(ident, entries, errors):
    """An item's fixes: a list with an entry per file, each of the right fields, each commit once, at whatever
    length, and no more commits listed than were read."""
    if not isinstance(entries, list):
        errors.append("%s's fixes should be a list, an entry per file." % ident)
        return
    files = [e.get("file") for e in entries if isinstance(e, dict) and isinstance(e.get("file"), str)]
    for name in sorted(set(f for f in files if f.strip() and files.count(f) > 1)):
        errors.append("%s's fixes have %s twice: an entry per file." % (ident, name))
    for i, entry in enumerate(entries):
        where = "%s.fixes[%d]" % (ident, i)
        if not fields(where, entry, FIXES, errors):
            continue
        if isinstance(entry.get("file"), str) and not entry["file"].strip():
            errors.append("%s: 'file' should name the file." % where)
        cited = [c for key in ("marked", "found", "dropped") if isinstance(entry.get(key), list) for c in entry[key]]
        bad = [c for c in cited if not is_hash(c)]
        if bad:
            errors.append("%s: commits are hashes of 7 to 40 hex digits; not %s."
                          % (where, ", ".join(repr(c) for c in bad)))
        hashes = [c for c in cited if is_hash(c)]
        twice = sorted(set("%s twice" % c if c == d else "one commit twice, as %s and %s" % tuple(sorted((c, d)))
                           for j, c in enumerate(hashes) for d in hashes[:j] if c.startswith(d) or d.startswith(c)))
        if twice:
            errors.append("%s lists %s: a commit read is one of marked, found or dropped, or none."
                          % (where, "; ".join(twice)))
        read, newer = entry.get("read"), entry.get("newer")
        if isinstance(read, int) and not isinstance(read, bool) and read < len(cited):
            errors.append("%s lists %d commits but read %d: read counts every commit read, newest first."
                          % (where, len(cited), read))
        counted = len(entry["marked"] if isinstance(entry.get("marked"), list) else []) + \
            len(entry["found"] if isinstance(entry.get("found"), list) else [])
        if isinstance(newer, int) and not isinstance(newer, bool) and not 0 <= newer <= counted:
            errors.append("%s says %d of its fixes are in the newer half, of the %d it counts."
                          % (where, newer, counted))


def check_item(item, page, seen, errors, warnings, spread):
    ident = item["id"]
    if not re.fullmatch(r"[RFLD][1-9][0-9]*", ident):
        errors.append("%s: an ID is R, F, L or D and a number, such as R1." % ident)
        return
    if ident in seen:
        errors.append("%s is used twice; an ID always means one item." % ident)
    seen[ident] = seen.get(ident, 0) + 1
    fields(ident, item, REFACTOR if ident[0] == "R" else OTHER, errors, optional=("from", "fixes"))
    if "from" in item:
        date("%s's from" % ident, item["from"], errors)
    if "fixes" in item:
        check_fixes(ident, item["fixes"], errors)
    if item.get("fixes") == []:  # The page shows nothing for it.
        warnings.append("%s's fixes cite nothing: leave the field out where an item cites no fixes." % ident)
    if ident[0] == "R":
        one_of("%s's size" % ident, item.get("size"), SIZES, errors)
        one_of("%s's risk" % ident, item.get("risk"), RISKS, errors)
    status = item.get("status")
    if status not in STATUSES:
        errors.append("%s: status %r isn't one of %s." % (ident, status, ", ".join(STATUSES)))
    elif page.count('{"id": "%s", "status": "%s"' % (ident, status)) != 1:
        spread.append(ident)
    if isinstance(item.get("cost"), dict):
        fields(ident + ".cost", item["cost"], COST, errors)
    for key in ("smells", "plan", "files"):
        texts("%s's %s" % (ident, key), item.get(key), errors)
    commits = item.get("commits") if isinstance(item.get("commits"), list) else []
    bad = [c for c in commits if not is_hash(c)]
    if bad:
        errors.append("%s: commits are hashes of 7 to 40 hex digits, one per commit; not %s."
                      % (ident, ", ".join(repr(c) for c in bad)))
    # Fields left empty: the page would show a blank where the skill asks for something.
    wanted = ("title", "eases", "smells", "cost", "plan", "files", "verify") if ident[0] == "R" else ("title", "note")
    empty = [key for key in wanted if key in item and not filled(item[key])]
    if empty:
        warnings.append("%s has %s empty: fill %s in, as SKILL.md step 5 says."
                        % (ident, " and ".join([", ".join(empty[:-1]), empty[-1]] if len(empty) > 1 else empty),
                           "it" if len(empty) == 1 else "them"))
    if status == "done" and not commits and ident[0] != "D":  # A decision can be done without a commit.
        warnings.append("%s is done with no commits, so a later pass will count its work in the heatmap." % ident)
    if status in ("done", "skipped") and not item.get("outcome"):
        warnings.append("%s is %s with no outcome: say what happened, with the checks' numbers." % (ident, status))


def check_heatmap(heatmap, errors):
    """The fixes counted in a heatmap block, where it counts them: its window's facts, and each file's count,
    the commits that say they fixed a defect and changed it, and how many of those were in the newer half."""
    window = heatmap.get("window") if isinstance(heatmap.get("window"), dict) else {}
    if "fixes" in window and fields("The heatmap's window.fixes", window["fixes"], FIX_FACTS, errors):
        facts = window["fixes"]
        counts = [facts.get(k) for k in ("revert", "type", "words")]
        if all(isinstance(c, int) for c in counts + [facts.get("fixes")]) and sum(counts) != facts["fixes"]:
            errors.append("The heatmap's window.fixes counts %d fixes, but %d by reverts, types and words: run "
                          "heatmap.py --page again rather than editing its block." % (facts["fixes"], sum(counts)))
    for row in heatmap.get("files") if isinstance(heatmap.get("files"), list) else []:
        if not isinstance(row, dict) or "fixes" not in row and "fixes_recent" not in row:
            continue
        where = "The heatmap's row for %s" % row.get("path")
        fixes, recent = row.get("fixes"), row.get("fixes_recent")
        commits = row.get("commits", fixes)
        if not all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in (fixes, recent)):
            errors.append("%s: its fixes and fixes_recent should be whole numbers, 0 or more." % where)
        elif not isinstance(commits, int) or isinstance(commits, bool):
            errors.append("%s: its commits should be a whole number." % where)
        elif recent > fixes or fixes > commits:
            errors.append("%s: its %d fixes, %d in the newer half, don't fit its %s commits."
                          % (where, fixes, recent, row.get("commits")))


def check(text):
    """The errors, the warnings, and the items."""
    errors, warnings = [], []
    heatmap = parse(text, "heatmap", errors)
    if isinstance(heatmap, dict):
        check_heatmap(heatmap, errors)
    data = parse(text, "pass", errors)
    if heatmap is None and not errors:
        warnings.append("No heatmap yet: heatmap.py --page puts it in.")
    if data is None:
        return errors, warnings, []
    if heatmap is None and not errors and isinstance(data, dict) and not data.get("items") \
            and not any(data.get(k) for k in ("project", "started", "base", "updated")):
        return ["This is the blank template, not a checklist yet: heatmap.py --page PATH makes a checklist "
                "from it, with the project, the dates and the heatmap filled in."], [], []
    if not fields("The pass block", data, PASS, errors):
        return errors, warnings, []
    if not filled(data.get("summary")) and not data.get("items"):
        warnings.append("The pass block isn't written yet: it has no summary and no items. SKILL.md step 6 says "
                        "what goes in it.")
    elif not filled(data.get("summary")):
        warnings.append("The pass block has no summary: say the overall state in two or three sentences.")
    texts("The checks", data.get("checks"), errors)
    for key in ("started", "updated"):
        date("The pass block's " + key, data.get(key), errors)
    for i, entry in enumerate(data.get("left_alone") if isinstance(data.get("left_alone"), list) else []):
        fields("left_alone[%d]" % i, entry, {"what": str, "why": str}, errors)
    for i, entry in enumerate(data.get("log") if isinstance(data.get("log"), list) else []):
        if fields("log[%d]" % i, entry, {"date": str, "text": str}, errors):
            date("log[%d]'s date" % i, entry.get("date"), errors)
    earlier = data.get("earlier")
    if isinstance(earlier, dict) and fields("earlier", earlier, EARLIER, errors):
        for i, result in enumerate(earlier.get("results") if isinstance(earlier.get("results"), list) else []):
            if fields("earlier.results[%d]" % i, result, RESULT, errors) and isinstance(result.get("cost"), dict):
                fields("earlier.results[%d].cost" % i, result["cost"], COST, errors)
    items = data.get("items") if isinstance(data.get("items"), list) else []
    seen, spread = {}, []
    for i, item in enumerate(items):
        if isinstance(item, dict) and isinstance(item.get("id"), str):
            check_item(item, text, seen, errors, warnings, spread)
        else:
            errors.append("items[%d] should be an object with an id such as \"R1\"." % i)
    # An ID used twice has its own error; its first line is then rightly found twice.
    spread = [ident for ident in spread if seen.get(ident) == 1]
    if spread:
        status = next(i for i in items if isinstance(i, dict) and i.get("id") == spread[0]).get("status")
        errors.append('%s should%s start with its ID and status on one line, and nowhere else in the page, so a '
                      'status update is a one-line edit: {"id": "%s", "status": "%s", ... Write each item\'s first '
                      "line like that, with its other fields after it, as in the page's comment; a JSON "
                      "pretty-printer, which puts every field on a line of its own, won't do."
                      % (", ".join(spread), "" if len(spread) == 1 else " each", spread[0], status))
    doing = [str(i.get("id")) for i in items if isinstance(i, dict) and i.get("status") == "doing"]
    if len(doing) > 1:
        warnings.append("%s are in progress at once; the list is worked one item at a time, so set the others "
                        "back to todo, or to waiting if they wait on the user."
                        % " and ".join([", ".join(doing[:-1]), doing[-1]]))
    return errors, warnings, [i for i in items if isinstance(i, dict)]


def main():
    scoping.safe_output()
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__.split("\n\n", 1)[1])
    parser.add_argument("page", help="the checklist page")
    args = parser.parse_args()
    try:
        text = open(args.page, encoding="utf-8").read()
    except FileNotFoundError:
        sys.exit("There's no %s. heatmap.py --page %s makes it, from the skill's assets/page.html."
                 % (args.page, args.page))
    except (OSError, UnicodeDecodeError) as e:
        sys.exit("Couldn't read %s: %s." % (args.page, getattr(e, "strerror", None) or e))
    errors, warnings, items = check(text)
    errors, warnings = list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))  # Once each, in order.
    for prefix in "RFLD":
        mine = [i for i in items if str(i.get("id", "")).startswith(prefix)]
        if mine:
            counts = ", ".join("%d %s" % (sum(i.get("status") == s for i in mine), s)
                               for s in STATUSES if any(i.get("status") == s for i in mine))
            print("%s: %d (%s)" % (KIND_NAMES[prefix], len(mine), counts))
    for message in errors:
        print("error: " + message)
    for message in warnings:
        print("warning: " + message)
    if not errors:
        print("OK")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    scoping.guard(main)
