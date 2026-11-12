"""Render checklist pages in headless Chrome and check what each page shows against its data, outside the
default run, since it needs a browser.

A page fails if its error box shows, or if it shows a different number of items than its pass block holds,
of file rows than its heatmap block's files, of pair and group rows than its pairs and groups, or of tests
than its tests. The pages: one heatmap.py makes in a small repo, as made and with a pass written; the
suite's fixture checklists, their data in today's template; a page whose heatmap is in an older format,
with no last dates, no bots and no dates on pairs; and one heatmap.py makes from commits whose subjects hold
<!-- and <script. Then, for each text test_check_page.py tries in a pass block that a browser might read as
HTML, a page with it written as it is and one with each < written \u003c: check_page.py must find an error
in the page exactly when the browser shows its error box. It exits 0 with a message when Chrome isn't found.

It uses the skill's scripts and template, or those REFACTOR_PASS_SCRIPTS names, and git.

Examples:
  render_pages.py
  render_pages.py --chrome /usr/bin/chromium --keep /tmp/pages
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile

sys.dont_write_bytecode = True
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import support  # noqa: E402

CANDIDATES = [
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Chromium.app/Contents/MacOS/Chromium",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
]


def find_chrome(given):
    if given:
        return given
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser", "chrome"):
        found = shutil.which(name)
        if found:
            return found
    return next((path for path in CANDIDATES if os.path.exists(path)), None)


def render(chrome, path, profile):
    """The page's DOM once its script has run."""
    uri = "file://" + ("/" if os.name == "nt" else "") + os.path.abspath(path).replace("\\", "/")
    result = subprocess.run([chrome, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
                             "--user-data-dir=" + profile, "--virtual-time-budget=5000", "--dump-dom", uri],
                            capture_output=True, timeout=120)
    return result.stdout.decode("utf-8", errors="replace")


def problems(dom, text):
    """What the rendered page gets wrong, against the data in its source."""
    found = []
    dom = re.sub(r"<script.*?</script>", "", dom, flags=re.S)  # The page's own script holds the same markup.
    error = re.search(r'<div class="error" id="error"([^>]*)>(.*?)</div>', dom, re.S)
    if not error:
        found.append("no error box in the rendered page: did its script run?")
    elif "hidden" not in error.group(1):
        found.append("the error box shows: %s" % error.group(2).strip())
    data = json.loads(support.block(text, "pass"))
    heat = json.loads(support.block(text, "heatmap") or "null")
    shown = len(re.findall(r'<li class="item[^"]*" data-status="', dom))
    if shown != len(data.get("items") or []):
        found.append("%d items shown, %d in the pass block" % (shown, len(data.get("items") or [])))
    if heat:
        rows = len(re.findall(r'<td class="path">', dom))
        if rows != len(heat["files"]):
            found.append("%d file rows shown, %d in the heatmap" % (rows, len(heat["files"])))
        together = len(heat.get("groups") or []) + len(heat.get("pairs") or [])
        start = dom.find('id="pairs"')
        listed = dom[start:dom.find('id="tied-wrap"', start)] if start >= 0 else ""
        if len(re.findall(r", degree \d+%", listed)) != together:
            found.append("%d pair and group rows shown, %d in the heatmap" % (
                len(re.findall(r", degree \d+%", listed)), together))
        tests = len(re.findall(r"production files besides its own", dom))
        if tests != len(heat.get("tests") or []):
            found.append("%d tests shown, %d in the heatmap" % (tests, len(heat.get("tests") or [])))
    title = re.search(r"<title>(.*?)</title>", dom)
    if data.get("project") and (not title or data["project"] not in title.group(1)):
        found.append("the title doesn't name the project")
    return found


def made_pages(folder):
    """A page heatmap.py makes in a small repo with a group, a pair and a test that changes with several files,
    and the same page with a pass written."""
    repo = support.Repo("render", path=os.path.join(folder, "repo"))
    sizes, day = {}, 1
    for paths in [["src/a.py", "src/b.py", "src/c.py", "tests/test_x.py"]] * 5 + [["src/d.py", "src/e.py"]] * 5:
        files = {}
        for path in paths:
            sizes[path] = sizes.get(path, 0) + 1
            files[path] = support.lines(sizes[path])
        repo.commit("2026-01-%02d" % day, "Change %s" % ", ".join(paths), files)
        day += 1
    repo.done()
    made = os.path.join(folder, "made.html")
    result = support.run("heatmap.py", "-C", repo.path, "--page", made)
    if result.code != 0:
        raise SystemExit("heatmap.py failed:\n%s" % result)
    with open(made, encoding="utf-8") as f:
        text = f.read()
    data = json.loads(support.block(text, "pass"))
    data.update(summary="Fine.", checks=["the tests"], items=[
        {"id": "R1", "status": "doing", "title": "Name it", "eases": "x", "smells": ["Long Function"],
         "cost": {"today": "2", "after": "1"}, "plan": ["Extract Function"], "files": ["src/a.py"], "size": "S",
         "risk": "Low", "verify": "the tests", "commits": [], "outcome": ""},
        {"id": "F1", "status": "done", "title": "Fix it", "note": "x", "commits": ["a1b2c3d"], "outcome": "Done."},
        {"id": "D1", "status": "waiting", "title": "Your call", "note": "x", "commits": [], "outcome": ""}],
        log=[{"date": "2026-01-11", "text": "Started."}], left_alone=[{"what": "x", "why": "y"}])
    written = os.path.join(folder, "written.html")
    support.write_text(written, support.page_with(data, template=made, heatmap_json=support.block(text, "heatmap")))
    return [made, written]


def html_subjects(folder):
    """A page heatmap.py makes from commits whose subjects hold <!-- and <script, as the window's newest and
    oldest."""
    repo = support.Repo("html", path=os.path.join(folder, "html-repo"))
    for day, subject in ((1, "odd names <!-- <script>alert(1)</script>"), (2, "Plain"),
                         (3, "odd <!-- names <SCRIPT src=x>")):
        repo.commit("2026-01-%02d" % day, subject, {"a.py": support.lines(day + 2)})
    repo.done()
    page = os.path.join(folder, "html-subjects.html")
    result = support.run("heatmap.py", "-C", repo.path, "--page", page)
    if result.code != 0:
        raise SystemExit("heatmap.py failed:\n%s" % result)
    return page


def html_texts(folder, made):
    """Pages whose pass block holds a text a browser might read as HTML, written as it is and with each <
    written \\u003c, with the heatmap of the page made, each with whether check_page.py finds an error in it."""
    import test_check_page
    check = support.load("check_page").check
    with open(made, encoding="utf-8") as f:
        heatmap = support.block(f.read(), "heatmap")
    pages = []
    for n, text in enumerate(test_check_page.BREAKS + test_check_page.FINE):
        data = test_check_page.good()
        test_check_page.item(data, "F1")["note"] = text
        for kind, pass_json in (("as-is", support.pass_text(data)),
                                ("u003c", support.pass_text(data).replace("<", "\\u003c"))):
            path = os.path.join(folder, "text-%02d-%s.html" % (n, kind))
            page = support.page_with(pass_json=pass_json, heatmap_json=heatmap)
            support.write_text(path, page)
            pages.append((path, text, bool(check(page)[0])))
    return pages


def older_format(folder, made):
    """The made page with its heatmap as an earlier version wrote it: no last dates, no bots, no pair dates."""
    with open(made, encoding="utf-8") as f:
        text = f.read()
    heat = json.loads(support.block(text, "heatmap"))
    for row in heat["files"] + heat["pairs"] + heat["groups"]:
        row.pop("last", None)
    heat["window"].pop("bots", None)
    path = os.path.join(folder, "older.html")
    support.write_text(path, support.page_with(template=made, heatmap=heat))
    return path


def fixtures(folder):
    """The fixture checklists' data in today's template."""
    pages = []
    for name in sorted(os.listdir(support.FIXTURES)):
        if name.endswith(".html"):
            with open(os.path.join(support.FIXTURES, name), encoding="utf-8") as f:
                text = f.read()
            path = os.path.join(folder, name)
            support.write_text(path, support.page_with(pass_json=support.block(text, "pass"),
                                                       heatmap_json=support.block(text, "heatmap")))
            pages.append(path)
    return pages


def main():
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__.split("\n\n", 1)[1])
    parser.add_argument("--chrome", metavar="PATH", help="the browser to run (default: Chrome or Chromium, found)")
    parser.add_argument("--keep", metavar="DIR", help="write the pages and their rendered DOM here, and keep them")
    args = parser.parse_args()
    chrome = find_chrome(args.chrome)
    if not chrome:
        print("No Chrome or Chromium found, so no page was rendered; --chrome PATH names one.")
        return
    folder = args.keep or tempfile.mkdtemp(prefix="refactor-pass-pages-")
    os.makedirs(folder, exist_ok=True)
    profile = tempfile.mkdtemp(prefix="refactor-pass-chrome-")
    failed = 0
    try:
        made = made_pages(folder)
        for path in made + [older_format(folder, made[0]), html_subjects(folder)] + fixtures(folder):
            with open(path, encoding="utf-8") as f:
                text = f.read()
            dom = render(chrome, path, profile)
            if args.keep:
                support.write_text(path + ".dom.html", dom)
            found = problems(dom, text) if dom.strip() else ["Chrome rendered nothing"]
            failed += bool(found)
            print("%s: %s" % (os.path.basename(path), "; ".join(found) if found else "ok"))
        agreed = 0
        texts = html_texts(folder, made[0])
        for path, text, flagged in texts:
            dom = re.sub(r"<script.*?</script>", "", render(chrome, path, profile), flags=re.S)
            error = re.search(r'<div class="error" id="error"([^>]*)>', dom)
            shown = bool(error) and "hidden" not in error.group(1)
            if shown == flagged:
                agreed += 1
            else:
                failed += 1
                print("%s: %r: check_page.py %s, the browser %s" % (
                    os.path.basename(path), text, "finds an error" if flagged else "finds none",
                    "shows its error box" if shown else "shows the page"))
        print("check_page.py and the browser agree on %d of the %d pages of text read as HTML." % (agreed, len(texts)))
    finally:
        shutil.rmtree(profile, ignore_errors=True)
        if not args.keep:
            shutil.rmtree(folder, ignore_errors=True)
    print("%d of the pages failed." % failed if failed else "Every page rendered as its data says.")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
