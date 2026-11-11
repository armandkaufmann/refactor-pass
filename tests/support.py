"""What the test modules share: where the scripts under test are, how to run them, how to build small git
repos whose every commit, author and date is fixed in advance, and how to write checklist pages.

The scripts tested are those in the scripts/ folder beside tests/, with the page template in assets/. To
test another copy, such as an older commit's (git archive <commit> scripts assets | tar -x -C <folder>),
set the REFACTOR_PASS_SCRIPTS environment variable to its scripts/ folder: its assets/ folder is the one
beside it, as heatmap.py finds its template.

Everything a test makes goes in one temporary folder, removed when the run ends, and git runs with no
user or system configuration, so the user's settings can't change a result.
"""

import atexit
import calendar
import importlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
from datetime import datetime

# Importing the scripts, as the tests of their functions do, writes no __pycache__ into their folder.
sys.dont_write_bytecode = True

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCRIPTS = os.path.abspath(os.environ.get("REFACTOR_PASS_SCRIPTS") or os.path.join(ROOT, "scripts"))
ASSETS = os.path.join(os.path.dirname(SCRIPTS), "assets")
TEMPLATE = os.path.join(ASSETS, "page.html")
SAMPLES = os.path.join(HERE, "samples")
FIXTURES = os.path.join(HERE, "fixtures")
WINDOWS = os.name == "nt"

# People and bots who write the test repos' commits, as "Name <email>".
ANN = "Ann Dev <ann@example.com>"
BOB = "Bob Dev <bob@example.com>"

_temp = {}


def temp_root():
    """The run's one temporary folder, made on first use and removed at exit. It's a real path (on macOS,
    /private/var rather than /var), as git gives a repo's top."""
    if "root" not in _temp:
        root = os.path.realpath(tempfile.mkdtemp(prefix="refactor-pass-tests-"))
        _temp["root"] = root
        _temp["count"] = 0
        open(os.path.join(root, "gitconfig"), "w").close()
        atexit.register(remove, root)
    return _temp["root"]


def new_folder(name="t"):
    """A new empty folder in the run's temporary folder."""
    root = temp_root()
    _temp["count"] += 1
    path = os.path.join(root, "%03d-%s" % (_temp["count"], name))
    os.makedirs(path)
    return path


def remove(path):
    """Remove a folder, read-only files included (git makes its objects read-only, which Windows won't
    delete as they are)."""
    def make_writable(function, target, *_):
        os.chmod(target, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        function(target)
    for folder, dirs, _ in os.walk(path):  # Folders a test made unreadable or unwritable.
        for name in dirs:
            try:
                os.chmod(os.path.join(folder, name), 0o755)
            except OSError:
                pass
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=make_writable)
    else:
        shutil.rmtree(path, onerror=make_writable)


def environment(**extra):
    """The environment the scripts and git run in: UTF-8 output, no bytecode written, no git configuration
    but the run's own empty one, and no repo found above the temporary folder."""
    env = dict(os.environ)
    for key in list(env):
        if key.startswith("GIT_") or key in ("REFACTOR_PASS_SCRIPTS",):
            del env[key]
    root = temp_root()
    env.update(PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1", GIT_CONFIG_NOSYSTEM="1",
               GIT_CONFIG_GLOBAL=os.path.join(root, "gitconfig"), GIT_CEILING_DIRECTORIES=os.path.dirname(root),
               GIT_TERMINAL_PROMPT="0")
    env.update(extra)
    return env


class Result(object):
    """A finished run: its exit code, and its output and errors as text with \\n line ends."""

    def __init__(self, code, out, err):
        self.code, self.out, self.err = code, out, err

    def __repr__(self):
        return "exit %d\n--- stdout\n%s--- stderr\n%s" % (self.code, self.out, self.err)


def _text(data):
    return data.decode("utf-8", errors="replace").replace("\r\n", "\n")


def run(script, *args, **options):
    """Run one of the scripts (heatmap.py, measure.py, check_page.py) with this Python. Options: cwd, env
    (added to the environment above), timeout (seconds, default 60)."""
    command = [sys.executable, os.path.join(SCRIPTS, script)] + [str(a) for a in args]
    result = subprocess.run(command, cwd=options.get("cwd") or temp_root(), capture_output=True,
                            env=environment(**options.get("env", {})), timeout=options.get("timeout", 60))
    return Result(result.returncode, _text(result.stdout), _text(result.stderr))


def run_python(code, *args, **options):
    """Run Python code in a new process, with the scripts' folder first on its path: for a test that
    changes one of the scripts' functions before running its main."""
    command = [sys.executable, "-c", code] + [str(a) for a in args]
    result = subprocess.run(command, cwd=options.get("cwd") or temp_root(), capture_output=True,
                            env=environment(REFACTOR_PASS_SCRIPTS=SCRIPTS, **options.get("env", {})),
                            timeout=options.get("timeout", 60))
    return Result(result.returncode, _text(result.stdout), _text(result.stderr))


def git(repo, *args, **options):
    """Run git in repo and return its output as text; raise if it fails, unless check=False."""
    result = subprocess.run(["git", "-C", repo] + list(args), capture_output=True, env=environment(),
                            input=options.get("input"))
    if options.get("check", True) and result.returncode != 0:
        raise AssertionError("git %s failed: %s" % (" ".join(args), _text(result.stderr)))
    return _text(result.stdout)


_modules = {}


def load(name):
    """One of the scripts imported as a module (measure, heatmap, scoping, check_page), from the copy under
    test."""
    if name not in _modules:
        if SCRIPTS not in sys.path:
            sys.path.insert(0, SCRIPTS)
        module = importlib.import_module(name)
        if os.path.dirname(os.path.abspath(module.__file__)) != SCRIPTS:
            raise ImportError("%s came from %s, not %s" % (name, module.__file__, SCRIPTS))
        _modules[name] = module
    return _modules[name]


def stamp(day, hour=12):
    """The Unix time of a day written 2026-01-05, at noon UTC unless hour says otherwise: far enough from
    midnight that the date is the same in nearly every time zone."""
    return calendar.timegm(datetime.strptime(day, "%Y-%m-%d").replace(hour=hour).timetuple())


def local_day(seconds):
    """The local date of a Unix time, as the scripts write dates."""
    return datetime.fromtimestamp(seconds).strftime("%Y-%m-%d")


def lines(count, word="line"):
    """Text of count numbered lines, each ending with a newline."""
    return "".join("%s %d\n" % (word, n) for n in range(1, count + 1))


class Link(object):
    """A symbolic link's entry in a commit, pointing at target."""

    def __init__(self, target):
        self.target = target


class Gitlink(object):
    """A submodule's entry in a commit, at another repo's commit."""

    def __init__(self, sha):
        self.sha = sha


def _quote(path):
    """A path as git fast-import reads it: in double quotes, C-style."""
    escaped = path.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\t", "\\t")
    return ('"%s"' % escaped).encode("utf-8")


def _data(content):
    """A data command: its length, then the bytes; the newline that ends the command follows it."""
    data = content.encode("utf-8") if isinstance(content, str) else content
    return b"data %d\n" % len(data) + data


class Repo(object):
    """A git repo built with git fast-import, whose commits have fixed authors, dates and contents.

    repo = Repo("name")
    first = repo.commit("2026-01-05", "Start", {"src/a.py": lines(10)})
    repo.commit("2026-01-06", "Move it", rename={"src/a.py": "src/b.py"}, delete=["old.txt"])
    repo.done()          # imports the commits and checks the files out
    repo.sha(first)      # the first commit's hash
    """

    def __init__(self, name="repo", path=None, branch="main"):
        self.path = path or os.path.join(new_folder(name), name)
        os.makedirs(self.path, exist_ok=True)
        git(self.path, "init", "-q")
        git(self.path, "symbolic-ref", "HEAD", "refs/heads/" + branch)
        self.branch = branch
        self.stream = []
        self.marks = 0
        self.tips = {}  # Per branch, its latest commit: a mark or a hash.
        self.shas = {}

    def commit(self, day, message, files=None, delete=(), rename=None, author=ANN, committer=None,
               branch=None, parent=None, merge=None, when=None, authored=None):
        """Add a commit, made at noon UTC on day (or at the Unix time when), and return its mark. files maps
        a path to its new content (text, bytes, a Link or a Gitlink); rename maps an old path to a new one,
        done before files are written; delete lists paths to remove. It goes on branch (the repo's own by
        default), after parent if given, else after that branch's latest commit; merge names a second
        parent. authored, a day, gives it an author date of its own, as a rebase leaves."""
        branch = branch or self.branch
        self.marks += 1
        mark = ":%d" % self.marks
        seconds = when if when is not None else stamp(day)
        committer = committer or author
        out = [b"commit refs/heads/" + branch.encode(), b"mark " + mark.encode(),
               b"author " + author.encode("utf-8") + b" %d +0000" % (stamp(authored) if authored else seconds),
               b"committer " + committer.encode("utf-8") + b" %d +0000" % seconds,
               _data(message + "\n")]
        before = parent if parent is not None else self.tips.get(branch)
        if before:
            out.append(b"from " + str(before).encode())
        if merge:
            out.append(b"merge " + str(merge).encode())
        for old, new in (rename or {}).items():
            out.append(b"R " + _quote(old) + b" " + _quote(new))
        for path in delete:
            out.append(b"D " + _quote(path))
        for path, content in (files or {}).items():
            if isinstance(content, Link):
                out.append(b"M 120000 inline " + _quote(path))
                out.append(_data(content.target))
            elif isinstance(content, Gitlink):
                out.append(b"M 160000 " + content.sha.encode() + b" " + _quote(path))
            else:
                out.append(b"M 100644 inline " + _quote(path))
                out.append(_data(content))
        self.stream.append(b"\n".join(out) + b"\n\n")
        self.tips[branch] = mark
        return mark

    def done(self, checkout=True):
        """Import the commits added so far and, unless checkout is False, check the branch out."""
        if self.stream:
            marks = os.path.join(self.path, ".git", "test-marks")
            git(self.path, "fast-import", "--quiet", "--done", "--import-marks-if-exists=" + marks,
                "--export-marks=" + marks, input=b"".join(self.stream) + b"done\n")
            self.stream = []
            with open(marks) as f:
                found = f.read().splitlines()
            for line in found:
                mark, sha = line.split()
                self.shas[mark] = sha
            for branch, tip in self.tips.items():
                self.tips[branch] = self.shas.get(tip, tip)
        if checkout:
            git(self.path, "reset", "-q", "--hard")
        return self

    def sha(self, mark):
        """A commit's full hash, from its mark."""
        return self.shas[mark]

    def short(self, mark):
        """A commit's hash as the heatmap prints it: its first nine characters."""
        return self.shas[mark][:9]

    def write(self, path, content):
        """Write a file into the working tree, outside any commit."""
        full = os.path.join(self.path, *path.split("/"))
        os.makedirs(os.path.dirname(full), exist_ok=True)
        with open(full, "wb") as f:
            f.write(content.encode("utf-8") if isinstance(content, str) else content)
        return full


# Checklist pages.

def block(text, name):
    """The JSON text of a page's data block, as heatmap.py and check_page.py find it."""
    tag = '<script type="application/json" id="%s">' % name
    start = text.index(tag) + len(tag)
    return text[start:text.index("</script>", start)]


def item_text(item):
    """An item as the skill asks for it: its ID and status first, with the next field, on its first line,
    and its other fields on the lines after it."""
    if "id" not in item or "status" not in item:
        return json.dumps(item, ensure_ascii=False)
    keys = [k for k in item if k not in ("id", "status")]
    first = '{"id": %s, "status": %s' % (json.dumps(item["id"]), json.dumps(item["status"]))
    if not keys:
        return first + "}"
    parts = ["%s: %s" % (json.dumps(k), json.dumps(item[k], ensure_ascii=False)) for k in keys]
    return first + ", " + parts[0] + "".join(",\n   " + p for p in parts[1:]) + "}"


def pass_text(data):
    """A pass block's JSON, with its items written as item_text writes them."""
    parts = []
    for key, value in data.items():
        if key == "items" and isinstance(value, list) and value:
            value_text = "[\n  " + ",\n  ".join(item_text(i) if isinstance(i, dict) else json.dumps(i)
                                                for i in value) + "\n ]"
        else:
            value_text = json.dumps(value, ensure_ascii=False)
        parts.append(" %s: %s" % (json.dumps(key), value_text))
    return "{\n" + ",\n".join(parts) + "\n}"


def page_with(pass_data=None, heatmap=None, template=None, pass_json=None, heatmap_json=None):
    """A checklist page: the template with its pass block and its heatmap block replaced."""
    with open(template or TEMPLATE, encoding="utf-8") as f:
        text = f.read()
    for name, json_text in (("heatmap", heatmap_json if heatmap_json is not None else
                             json.dumps(heatmap, ensure_ascii=False).replace("</", "<\\/")),
                            ("pass", pass_json if pass_json is not None else
                             pass_text(pass_data) if pass_data is not None else None)):
        if json_text is None:
            continue
        old = block(text, name)
        tag = '<script type="application/json" id="%s">' % name
        start = text.index(tag) + len(tag)
        text = text[:start] + "\n" + json_text + "\n" + text[start + len(old):]
    return text


def write_text(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    return path


def heatmap_rows(out):
    """The heatmap's table, from its output: per file, its columns as a dict."""
    rows, table = {}, False
    for line in out.splitlines():
        if re.match(r"\s*commits\s+recent\s+last\s+churn\s+rel\s+size\s+growth\s+file", line):
            table = True
            continue
        if table:
            match = re.match(r"\s*(\d+)\s+(\d+)\s+(\S+)\s+(\d+)\s+([\d.]+)\s+(\d+)\s+([+-]\d+)\s\s(.+)$", line)
            if not match:
                break
            rows[match.group(8)] = dict(commits=int(match.group(1)), recent=int(match.group(2)),
                                        last=match.group(3), churn=int(match.group(4)), rel=float(match.group(5)),
                                        size=int(match.group(6)), growth=int(match.group(7)))
    return rows


def ordered_paths(out):
    """The files in the heatmap's table, in the order printed."""
    return list(heatmap_rows(out))
