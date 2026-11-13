"""check_page.py: a good page, every error and warning it can give from a small broken variant of that page,
and the checklists agents wrote with earlier versions of the skill, which must still pass.

Most variants go through check_page.check, the function that finds the problems; a few run the script, for
its exit code and what it prints.
"""

import json
import os
import unittest

try:
    from . import support
except ImportError:
    import support


def good():
    """A pass block with an item of every kind, a carried-over item, an earlier pass and a log."""
    refactor = {"id": "R2", "status": "done", "title": "Name the states of a checkout",
                "eases": "adding a payment kind",
                "smells": ["Hidden State Machine: 6 flags (`checkout.py:40`)"],
                "cost": {"today": "5 files, 2 switches", "after": "1 file"},
                "plan": ["Pin today's behaviour", "Replace Primitive with Object"],
                "files": ["src/checkout.py"], "size": "M", "risk": "Medium", "verify": "`make test`",
                "commits": ["a1b2c3d", "0123456789abcdef0123456789abcdef01234567"], "outcome": "Done: 40 tests pass.",
                "fixes": [{"file": "src/checkout.py", "read": 12, "newer": 1, "marked": ["a1b2c3d4e"],
                           "found": ["b2c3d4e5f"], "dropped": []}]}
    carried = dict(refactor, id="R3", status="todo", title="Give each report one definition", commits=[], outcome="",
                   fixes=[dict(refactor["fixes"][0], newer=None)], **{"from": "2026-11-03"})
    return {
        "project": "shop", "started": "2026-11-10", "base": "a1b2c3d4e", "updated": "2026-11-11",
        "summary": "Two hot spots; the rest is fine.", "checks": ["`make test`", "the snapshots"],
        "earlier": {"checklist": ".refactor-pass/2026-11-03.html", "results": [
            {"id": "R1", "title": "Pin the receipts", "eases": "adding a receipt line",
             "cost": {"today": "3 files", "after": "1 file"}, "change": "b2c3d4e 2026-11-08 Add a VAT line",
             "actual": "1 file", "note": "Held."}]},
        "items": [refactor, carried,
                  {"id": "F1", "status": "todo", "title": "Refunds keep the fee", "note": "Seen in `orders.py:61`.",
                   "commits": [], "outcome": ""},
                  {"id": "L1", "status": "todo", "title": "The pay functions repeat a tail", "note": "Cold.",
                   "commits": [], "outcome": ""},
                  {"id": "D1", "status": "waiting", "title": "Keep the stock line in code?", "note": "Your call.",
                   "commits": [], "outcome": ""}],
        "left_alone": [{"what": "`legacy_export.py`", "why": "One commit in a year."}],
        "log": [{"date": "2026-11-11", "text": "Started."}],
    }


HEATMAP = {"head": "a1b2c3d4e", "scope": ["src"], "window": {"commits": 1}, "files": []}


def page(data=None, **options):
    return support.page_with(good() if data is None else data, heatmap=options.get("heatmap", HEATMAP))


def problems(text):
    """check_page.check's errors and warnings, each once, as the script prints them."""
    errors, warnings, _ = support.load("check_page").check(text)
    return list(dict.fromkeys(errors)), list(dict.fromkeys(warnings))


def changed(change):
    """The good pass block, changed by change(data)."""
    data = good()
    change(data)
    return page(data)


def item(data, ident):
    return next(i for i in data["items"] if i["id"] == ident)


class Good(unittest.TestCase):

    def test_a_good_page(self):
        self.assertEqual(problems(page()), ([], []))
        path = support.write_text(os.path.join(support.new_folder("good"), "good.html"), page())
        result = support.run("check_page.py", path)
        self.assertEqual(result.code, 0, result)
        self.assertEqual(result.out, "refactors: 2 (1 todo, 1 done)\nsmall fixes: 1 (1 todo)\nlater: 1 (1 todo)\n"
                                     "your call: 1 (1 waiting)\nOK\n")

    def test_a_note_on_cited_fixes(self):
        # Why a mark was dropped, or how the item's other files ran: text the page shows after its sentence.
        fixes = [dict(item(good(), "R2")["fixes"][0], dropped=["c3d4e5f6a"], note="c3d4e5f6a renamed a call.")]
        self.assertEqual(problems(changed(lambda d: item(d, "R2").update(fixes=fixes))), ([], []))

    def test_an_item_all_on_one_line_passes(self):
        # Known behaviour: the skill asks for an item's other fields on the lines after its first, but the
        # check is only that its first line holds its ID and status, once; one line does, so it passes.
        data = good()
        text = page(data)
        one_line = json.dumps(item(data, "R2"), ensure_ascii=False)
        start = text.index('{"id": "R2"')
        end = text.index('{"id": "R3"')
        text = text[:start] + one_line + ",\n  " + text[end:]
        self.assertEqual(problems(text), ([], []))

    def test_old_checklists_still_pass(self):
        # Written by agents in cold runs with an earlier version of the skill, on a made-up shop and on Flask.
        names = sorted(n for n in os.listdir(support.FIXTURES) if n.endswith(".html"))
        self.assertEqual(len(names), 3)
        for name in names:
            with self.subTest(fixture=name):
                result = support.run("check_page.py", os.path.join(support.FIXTURES, name))
                self.assertEqual(result.code, 0, result)
                self.assertTrue(result.out.endswith("OK\n"), result)
                self.assertNotIn("error:", result.out)


class Errors(unittest.TestCase):

    def assertError(self, text, *words):
        errors, _ = problems(text)
        found = [e for e in errors if all(w in e for w in words)]
        self.assertEqual(len(found), 1, "no single error with %r in %r" % (words, errors))
        return errors

    def test_bad_status(self):
        self.assertError(changed(lambda d: item(d, "R2").update(status="started")),
                         "R2: status 'started' isn't one of todo, doing, waiting, done, skipped.")

    def test_bad_size_and_risk(self):
        text = changed(lambda d: item(d, "R2").update(size="XL", risk="Huge"))
        self.assertError(text, "R2's size should be S, M or L, not 'XL'.")
        self.assertError(text, "R2's risk should be Low, Medium or High, not 'Huge'.")

    def test_bad_dates(self):
        def change(data):
            data["started"] = "2026-1-5"
            data["log"][0]["date"] = "11/11/2026"
            item(data, "R3")["from"] = "last week"
        text = changed(change)
        self.assertError(text, "The pass block's started should be a date written as 2026-11-10, not '2026-1-5'.")
        self.assertError(text, "log[0]'s date should be a date written as 2026-11-10, not '11/11/2026'.")
        self.assertError(text, "R3's from should be a date written as 2026-11-10, not 'last week'.")
        self.assertError(changed(lambda d: d.update(updated="2026-02-30")), "updated should be a date")

    def test_unknown_fields(self):
        text = changed(lambda d: (d.update(notes="x"), item(d, "R2").update(priority=1), item(d, "F1").update(
            plan=["x"])))
        self.assertError(text, "The pass block has a field the page doesn't show: 'notes'")
        self.assertError(text, "R2 has a field the page doesn't show: 'priority' (it shows id, status, title, eases, "
                               "smells, cost, plan, files, size, risk, verify, commits, outcome, from if wanted, "
                               "fixes if wanted).")
        self.assertError(text, "F1 has a field the page doesn't show: 'plan'")

    def test_missing_fields(self):
        def change(data):
            del data["summary"]
            del item(data, "R2")["verify"]
            del item(data, "F1")["note"]
            del data["left_alone"][0]["why"]
            del data["earlier"]["results"][0]["note"]
            del data["earlier"]["results"][0]["cost"]["after"]
            del item(data, "R3")["cost"]["after"]
        text = changed(change)
        for words in ("The pass block is missing 'summary'.", "R2 is missing 'verify'.", "F1 is missing 'note'.",
                      "left_alone[0] is missing 'why'.", "earlier.results[0] is missing 'note'.",
                      "earlier.results[0].cost is missing 'after'.", "R3.cost is missing 'after'."):
            with self.subTest(error=words):
                self.assertError(text, words)

    def test_wrong_kinds_of_value(self):
        def change(data):
            data["checks"] = "make test"
            data["earlier"] = []
            item(data, "R2")["smells"] = "too long"
            item(data, "R3")["cost"] = "5 files"
            item(data, "F1")["commits"] = "a1b2c3d"
            data["log"] = ["Started."]
        text = changed(change)
        for words in ("The pass block: 'checks' should be a list.", "The pass block: 'earlier' should be an object or "
                      "null.", "R2: 'smells' should be a list.", "R3: 'cost' should be an object.",
                      "F1: 'commits' should be a list.", "log[0] should be an object."):
            with self.subTest(error=words):
                self.assertError(text, words)
        text = changed(lambda d: (d.update(checks=[1]), item(d, "R2").update(plan=["a", 2])))
        self.assertError(text, "The checks: each should be text.")
        self.assertError(text, "R2's plan: each should be text.")

    def test_bad_commit_hashes(self):
        self.assertError(changed(lambda d: item(d, "R2").update(commits=["abc", "ABCDEF1", "a1b2c3d", "a1b2 c3d"])),
                         "R2: commits are hashes of 7 to 40 hex digits, one per commit; not 'abc', 'ABCDEF1', "
                         "'a1b2 c3d'.")

    def test_a_note_on_cited_fixes_is_text(self):
        fixes = [dict(item(good(), "R2")["fixes"][0], note=["why"])]
        self.assertError(changed(lambda d: item(d, "R2").update(fixes=fixes)), "R2.fixes[0]: 'note' should be text.")

    def test_bad_cited_fixes(self):
        def entry(**change):
            return [dict({"file": "src/a.py", "read": 9, "newer": 0, "marked": ["a1b2c3d"], "found": [], "dropped": []},
                         **change)]
        self.assertError(changed(lambda d: item(d, "R2").update(fixes={"marked": []})),
                         "R2's fixes should be a list, an entry per file.")
        self.assertError(changed(lambda d: item(d, "R2").update(fixes=[{"file": "a.py", "marked": []}])),
                         "R2.fixes[0] is missing 'read'.")
        self.assertError(changed(lambda d: item(d, "R2").update(fixes=entry(read="9"))),
                         "R2.fixes[0]: 'read' should be a whole number.")
        self.assertError(changed(lambda d: item(d, "F1").update(fixes=entry(found=["a1b2", 7]))),
                         "F1.fixes[0]: commits are hashes of 7 to 40 hex digits; not 'a1b2', 7.")
        self.assertError(changed(lambda d: item(d, "R2").update(fixes=entry(dropped=["a1b2c3d"]))),
                         "R2.fixes[0] lists a1b2c3d twice")
        self.assertError(changed(lambda d: item(d, "R2").update(fixes=entry(read=1, found=["b2c3d4e"]))),
                         "R2.fixes[0] lists 2 commits but read 1")
        self.assertError(changed(lambda d: item(d, "R2").update(fixes=entry(newer=2))),
                         "R2.fixes[0] says 2 of its fixes are in the newer half, of the 1 it counts.")
        self.assertError(changed(lambda d: item(d, "R2").update(fixes=entry(newer=True))),
                         "R2.fixes[0]: 'newer' should be a whole number or null.")

    def test_cited_fixes_name_each_commit_and_each_file_once(self):
        def entry(**change):
            return dict({"file": "src/a.py", "read": 9, "newer": 0, "marked": ["a1b2c3d"], "found": [], "dropped": []},
                        **change)
        self.assertError(changed(lambda d: item(d, "R2").update(fixes=[entry(dropped=["a1b2c3d4e"])])),
                         "R2.fixes[0] lists one commit twice, as a1b2c3d and a1b2c3d4e")
        self.assertError(changed(lambda d: item(d, "R2").update(fixes=[entry(file=" ")])),
                         "R2.fixes[0]: 'file' should name the file.")
        self.assertError(changed(lambda d: item(d, "R2").update(fixes=[entry(), entry(marked=["b2c3d4e"])])),
                         "R2's fixes have src/a.py twice: an entry per file.")

    def test_the_fixes_a_heatmap_counts(self):
        facts = {"fixes": 3, "revert": 1, "type": 0, "words": 2, "typed": 0.0, "labels": False, "thin": False,
                 "language": False, "complete": False}
        row = {"path": "src/a.py", "commits": 4, "fixes": 3, "fixes_recent": 1}
        good = dict(HEATMAP, window={"commits": 9, "fixes": facts}, files=[row, {"path": "CHANGES.md", "commits": 2}])
        self.assertEqual(problems(page(heatmap=good)), ([], []))
        for change, words in [(dict(facts, words=1), "counts 3 fixes, but 2 by reverts, types and words"),
                              (dict(facts, labels="no"), "window.fixes: 'labels' should be true or false."),
                              (dict(facts, thin=1), "window.fixes: 'thin' should be true or false."),
                              (dict(facts, typed=True), "window.fixes: 'typed' should be a number."),
                              (dict(facts, more=1), "window.fixes has a field the page doesn't show: 'more'")]:
            with self.subTest(error=words):
                self.assertError(page(heatmap=dict(good, window={"commits": 9, "fixes": change})), words)
        for change, words in [(dict(row, fixes_recent=4), "its 3 fixes, 4 in the newer half, don't fit its 4 commits"),
                              (dict(row, fixes=5, fixes_recent=1), "its 5 fixes, 1 in the newer half, don't fit"),
                              (dict(row, fixes=-1), "its fixes and fixes_recent should be whole numbers, 0 or more")]:
            with self.subTest(error=words):
                self.assertError(page(heatmap=dict(good, files=[change])), "row for src/a.py: " + words)

    @unittest.expectedFailure
    def test_where_a_heatmap_sits_in_time(self):
        # The day it was made, whether nothing had landed for over three months, and the newest commit to change
        # the scope where that isn't the window's newest; a heatmap from before has none of them.
        when = {"today": "2026-11-13", "quiet": True, "scope_newest": {"sha": "a1b2c3d4e", "date": "2026-01-10",
                                                                     "subject": "Change a"}}
        good = dict(HEATMAP, window=dict(HEATMAP["window"], **when))
        self.assertEqual(problems(page(heatmap=good)), ([], []))
        for change, words in [(dict(when, today="13 Nov"), "window.today should be a date written as 2026-11-10"),
                              (dict(when, quiet="no"), "window.quiet should be true or false."),
                              (dict(when, scope_newest="a1b"), "window.scope_newest should be an object or null.")]:
            with self.subTest(error=words):
                self.assertError(page(heatmap=dict(HEATMAP, window=dict(HEATMAP["window"], **change))), words)

    def test_a_heatmap_row_whose_commits_arent_a_number(self):
        row = {"path": "src/a.py", "commits": None, "fixes": 3, "fixes_recent": 1}
        for commits in (None, "4"):
            with self.subTest(commits=commits):
                self.assertError(page(heatmap=dict(HEATMAP, files=[dict(row, commits=commits)])),
                                 "The heatmap's row for src/a.py: its commits should be a whole number.")

    def test_bad_ids_and_items(self):
        text = changed(lambda d: d["items"].extend([{"id": "X1", "status": "todo"}, "R9", {"title": "no id"}]))
        self.assertError(text, "X1: an ID is R, F, L or D and a number, such as R1.")
        self.assertError(text, 'items[6] should be an object with an id such as "R1".')
        self.assertError(text, 'items[7] should be an object with an id such as "R1".')
        self.assertError(changed(lambda d: item(d, "F1").update(id="F0")), "F0: an ID is R, F, L or D")

    def test_a_duplicate_id_is_reported_once(self):
        data = good()
        data["items"].append(dict(item(data, "F1")))
        text = page(data)
        errors = self.assertError(text, "F1 is used twice; an ID always means one item.")
        self.assertFalse([e for e in errors if "start with its ID" in e], errors)
        path = support.write_text(os.path.join(support.new_folder("dup"), "dup.html"), text)
        result = support.run("check_page.py", path)
        self.assertEqual(result.code, 1, result)
        self.assertEqual(result.out.count("F1 is used twice"), 1)

    def test_a_pretty_printed_item(self):
        data = good()
        text = page(data)
        start, end = text.index('{"id": "R2"'), text.index('{"id": "R3"')
        text = text[:start] + json.dumps(item(data, "R2"), indent=1).replace("\n", "\n  ") + ",\n  " + text[end:]
        self.assertError(text, "R2 should start with its ID and status on one line, and nowhere else in the page, so a "
                               'status update is a one-line edit: {"id": "R2", "status": "done", ... Write each '
                               "item's first line like that, with its other fields after it, as in the page's "
                               "comment; a JSON pretty-printer, which puts every field on a line of its own, won't do.")
        two = text[:]
        start, end = two.index('{"id": "R3"'), two.index('{"id": "F1"')
        two = two[:start] + json.dumps(item(data, "R3"), indent=1) + ",\n  " + two[end:]
        self.assertError(two, "R2, R3 should each start with its ID and status on one line")

    def test_an_items_first_line_found_elsewhere_too(self):
        # Not in a text field, where JSON escapes the quotes, but in the page around the blocks.
        text = page().replace("<!-- The data.", '<!-- {"id": "R2", "status": "done", was here.\n     The data.', 1)
        self.assertError(text, "R2 should start with its ID and status on one line, and nowhere else in the page")

    def test_a_trailing_comma(self):
        text = page()
        self.assertIn('"outcome": ""}\n ]', text)
        text = text.replace('"outcome": ""}\n ]', '"outcome": ""},\n ]', 1)
        errors = self.assertError(text, "The pass block doesn't parse, at line", "A trailing comma or an unescaped "
                                  "quote is the usual cause; a text holding </script> must write it <\\/script>.")
        line = int(errors[0].split("at line ")[1].split(" ")[0])
        # The line of the stray comma (Python 3.13 and later) or of the bracket after it (before).
        bracket = text.split("\n").index(" ],") + 1
        self.assertTrue(text.split("\n")[bracket - 2].endswith('"outcome": ""},'))
        self.assertIn(line, (bracket - 1, bracket))

    def test_an_unescaped_script_tag(self):
        text = page().replace("One commit in a year.", "Holds </script> in its text.")
        self.assertError(text, "The pass block doesn't parse")

    def test_missing_blocks(self):
        text = page()
        no_heatmap = text.replace('<script type="application/json" id="heatmap">', "<script>")
        self.assertError(no_heatmap, "No heatmap block: the page should end with the template's two data blocks.")
        no_pass = text.replace('<script type="application/json" id="pass">', "<script>")
        self.assertError(no_pass, "No pass block")

    def test_a_pass_block_that_isnt_an_object(self):
        self.assertError(support.page_with(heatmap=HEATMAP, pass_json="[]"), "The pass block should be an object.")

    def test_the_blank_template(self):
        result = support.run("check_page.py", support.TEMPLATE)
        self.assertEqual(result.code, 1, result)
        self.assertIn("error: This is the blank template, not a checklist yet: heatmap.py --page PATH makes a "
                      "checklist from it, with the project, the dates and the heatmap filled in.", result.out)

    def test_a_missing_file(self):
        path = os.path.join(support.temp_root(), "no-such-page.html")
        result = support.run("check_page.py", path)
        self.assertEqual(result.code, 1, result)
        self.assertIn("There's no %s. heatmap.py --page %s makes it, from the skill's assets/page.html." % (path, path),
                      result.err)

    def test_a_file_that_cant_be_read(self):
        path = os.path.join(support.new_folder("binary"), "page.html")
        with open(path, "wb") as f:
            f.write(b"\xff\xfe\x00 not text")
        result = support.run("check_page.py", path)
        self.assertEqual(result.code, 1, result)
        self.assertIn("Couldn't read %s: " % path, result.err)

    def test_the_cli_exits_1_on_an_error(self):
        path = support.write_text(os.path.join(support.new_folder("bad"), "bad.html"),
                                  changed(lambda d: item(d, "R2").update(status="started")))
        result = support.run("check_page.py", path)
        self.assertEqual(result.code, 1, result)
        self.assertIn("error: R2: status 'started' isn't one of", result.out)
        self.assertNotIn("OK", result.out)


class Warnings(unittest.TestCase):

    def assertWarning(self, text, *words):
        errors, warnings = problems(text)
        self.assertEqual(errors, [])
        found = [w for w in warnings if all(word in w for word in words)]
        self.assertEqual(len(found), 1, "no single warning with %r in %r" % (words, warnings))

    def test_a_dropped_mark_with_no_note(self):
        # Step 4 asks why a mark was dropped: the entry's note says it.
        for note in ({}, {"note": " "}):
            fixes = [dict(item(good(), "R2")["fixes"][0], dropped=["c3d4e5f6a"], **note)]
            self.assertWarning(changed(lambda d: item(d, "R2").update(fixes=fixes)),
                               "R2.fixes[0] drops c3d4e5f6a with no note: say why in it.")

    def test_a_pass_not_written_yet(self):
        data = dict((k, v) for k, v in good().items())
        data.update(summary="", items=[], earlier=None, left_alone=[], log=[], checks=[])
        self.assertWarning(page(data), "The pass block isn't written yet: it has no summary and no items. SKILL.md "
                                       "step 6 says what goes in it.")

    def test_fixes_that_cite_nothing(self):
        self.assertWarning(changed(lambda d: item(d, "F1").update(fixes=[])),
                           "F1's fixes cite nothing: leave the field out where an item cites no fixes.")

    def test_no_heatmap_yet(self):
        self.assertWarning(support.page_with(good()), "No heatmap yet: heatmap.py --page puts it in.")

    def test_no_summary(self):
        self.assertWarning(changed(lambda d: d.update(summary=" ")), "The pass block has no summary: say the overall "
                                                                      "state in two or three sentences.")

    def test_empty_fields(self):
        text = changed(lambda d: (item(d, "R2").update(plan=[], verify=""), item(d, "R3").update(
            eases="", files=[""], cost={"today": "x", "after": ""}), item(d, "F1").update(note="")))
        self.assertWarning(text, "R2 has plan and verify empty: fill them in, as SKILL.md step 5 says.")
        self.assertWarning(text, "R3 has eases, cost and files empty: fill them in")
        self.assertWarning(text, "F1 has note empty: fill it in")

    def test_done_without_commits_or_outcome(self):
        def change(data):
            item(data, "R3").update(status="done")
            item(data, "F1").update(status="skipped")
            item(data, "D1").update(status="done", outcome="Kept in code.")
        text = changed(change)
        self.assertWarning(text, "R3 is done with no commits, so a later pass will count its work in the heatmap.")
        self.assertWarning(text, "R3 is done with no outcome: say what happened, with the checks' numbers.")
        self.assertWarning(text, "F1 is skipped with no outcome")
        _, warnings = problems(text)
        self.assertFalse([w for w in warnings if w.startswith("D1")], warnings)

    def test_items_in_progress_at_once(self):
        text = changed(lambda d: [item(d, i).update(status="doing") for i in ("R3", "F1", "L1")])
        self.assertWarning(text, "R3, F1 and L1 are in progress at once; the list is worked one item at a time, so set "
                                 "the others back to todo, or to waiting if they wait on the user.")
        _, warnings = problems(changed(lambda d: item(d, "R3").update(status="doing")))
        self.assertEqual(warnings, [])

    def test_warnings_exit_0(self):
        path = support.write_text(os.path.join(support.new_folder("warn"), "warn.html"),
                                  changed(lambda d: d.update(summary="")))
        result = support.run("check_page.py", path)
        self.assertEqual(result.code, 0, result)
        self.assertTrue(result.out.endswith("warning: The pass block has no summary: say the overall state in two or "
                                            "three sentences.\nOK\n"), result)


# Text in a data block that a browser reads as HTML: a </script, in any case and followed by a space, a / or a
# >, ends the block there; and after a <!--, a <script hides its end, as HTML's escapes of old scripts do,
# until a -->. Each of these breaks the page; the ones after are harmless.
BREAKS = ["`layout.html:12` still opens with `<!-- legacy` and loads an inline `<script>` block", "a </SCRIPT> tag",
          "</script >", "</Script/x", "<!--<SCRIPT src", "<!-- <script> </script> <script>", "<!-- </SCRIPT>"]
FINE = ["<!-- alone", "<script> alone", "<!-- <script> -->", "<!-- <script> </script>", "<!--<scripts>",
        "</scripts>", "a < b", "<!--> <script>", "x <!---> <script>", "<!- <script>"]


class TextBrowsersReadAsHtml(unittest.TestCase):

    def test_text_that_moves_or_hides_a_blocks_end(self):
        for text in BREAKS:
            with self.subTest(text=text):
                data = good()
                item(data, "F1")["note"] = text
                errors, _ = problems(page(data))
                self.assertTrue(any("can't be read by a browser" in e for e in errors), errors)

    def test_what_it_says(self):
        data = good()
        item(data, "F1")["note"] = BREAKS[0]
        text = page(data)
        line = text[:text.index("<!-- legacy")].count("\n") + 1
        self.assertIn("The pass block can't be read by a browser: <!-- at line %d, and then <script at line %d, keep "
                      "it from seeing where the block ends. Write each < in the block's text as \\u003c, which JSON "
                      "reads as <." % (line, line), problems(text)[0])
        item(data, "F1")["note"] = "a </SCRIPT> tag"
        text = page(data)
        line = text[:text.index("</SCRIPT>")].count("\n") + 1
        self.assertIn("The pass block can't be read by a browser: the </SCRIPT at line %d ends the block there. Write "
                      "each < in the block's text as \\u003c, which JSON reads as <." % line, problems(text)[0])

    def test_the_same_text_written_with_u003c(self):
        for text in BREAKS:
            with self.subTest(text=text):
                data = good()
                item(data, "F1")["note"] = text
                written = support.page_with(pass_json=support.pass_text(data).replace("<", "\\u003c"),
                                            heatmap=HEATMAP)
                self.assertEqual(problems(written), ([], []))

    def test_harmless_text(self):
        for text in FINE:
            with self.subTest(text=text):
                data = good()
                item(data, "F1")["note"] = text
                self.assertEqual(problems(page(data)), ([], []))

    def test_the_heatmap_block_too(self):
        heat = dict(HEATMAP, window={"commits": 1, "newest": {"sha": "a1b2c3d4e", "date": "2026-11-10",
                                                              "subject": "odd <!-- <script>alert(1)"}})
        text = support.page_with(good(), heatmap_json=json.dumps(heat))
        self.assertTrue(any(e.startswith("The heatmap block can't be read by a browser") for e in problems(text)[0]))


if __name__ == "__main__":
    unittest.main()
