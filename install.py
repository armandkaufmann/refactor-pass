#!/usr/bin/env python3
# Copyright (c) 2026 Armand Kaufmann. MIT License: https://github.com/armandkaufmann/refactor-pass
"""Install the refactor-pass skill where your coding agents look for skills, and update, check or remove it.

Commands:
  install    (the default) put the skill in the user-level skills folder of every agent found on this
             machine, one copy per folder when agents share one; or where --agent, --dir or --project say
  update     bring every copy this installer made (in the agents' folders, the current project's, any
             --dir) to the latest release
  check      print each copy's version against the latest, changing nothing
  uninstall  remove the copies this installer made (or those --agent, --dir or --project name), only the
             files it installed

The latest release is the highest vMAJOR.MINOR.PATCH tag on the source. With no such tag yet, the default
branch is installed, with a notice, and update moves it to the first release when there is one. A source is
an https, ssh or git URL, or a folder that exists; files are read from its commits, not from a checkout, and
only plain files are installed.

Each copy gets a small .install.json beside SKILL.md: where it came from, its version, and a hash of each
file (of its text with CRLF line ends read as LF, so a checkout's line ends aren't an edit). A copy whose
files were edited since, or that holds files it didn't install, is left alone unless --force; a folder this
installer didn't make, one whose .install.json it can't trust, a git clone and a link always are.

It runs with Python 3.7 or later and git, from a checkout or piped, as one line:
  curl -fsSL https://raw.githubusercontent.com/armandkaufmann/refactor-pass/main/install.py | python3 -
  curl -fsSL .../install.py | python3 - update
  irm https://raw.githubusercontent.com/armandkaufmann/refactor-pass/main/install.py | python -   (PowerShell)

Examples:
  install.py                                 every agent found here
  install.py --agent claude-code             one agent, found or not
  install.py --dir ~/my-skills               ~/my-skills/refactor-pass
  install.py --project --agent codex         in this git repo, to commit
  install.py --ref v1.2.0                    a pinned version
  install.py --source ~/code/refactor-pass --ref HEAD    a local clone's last commit
  install.py update --dry-run
"""

import argparse
import datetime
import hashlib
import itertools
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile

NAME = "refactor-pass"
SKILL = "skills/refactor-pass"  # Where every release keeps the skill, from v1.0.0 on.
RECORD = ".install.json"
RECORD_FORMAT = 1
SOURCE = "https://github.com/armandkaufmann/refactor-pass"
RELEASE = re.compile(r"^v(\d+)\.(\d+)\.(\d+)$")
STAGING, RETIRED = ".refactor-pass.new-", ".refactor-pass.old-"  # Beside a copy, only while it's swapped.
BYTECODE = "__pycache__"  # What Python may write beside the scripts: never recorded, never a reason to refuse.

# What a source, a ref and a path may be. A source and a ref never start with -, so git can't read one as an
# option, nor does a URL's host or user (as ssh://-oProxyCommand=... would have it), and a source is never a
# remote helper's <transport>::<address>; a path is a plain relative one that every system can hold, so a
# record or a commit can't name a file outside the copy.
URL = re.compile(r"^(?:https|ssh|git)://[A-Za-z0-9]\S*$|"
                 r"^[A-Za-z0-9][A-Za-z0-9._-]*@[A-Za-z0-9][A-Za-z0-9.-]*:(?!:)\S+$")
REF = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._/+-]*$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")
DIGEST = re.compile(r"^[0-9a-f]{64}$")
RESERVED = re.compile(r"(?i)^(?:con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\..*)?$")

# The agents, from each one's own documentation: its name here, its name to show, the folder in the home
# that shows it's installed, then the user-level and the project-level skills folders it reads, from the
# home and from the project's top. The README cites the page for each row.
AGENTS = [
    ("claude-code", "Claude Code", ".claude", [".claude/skills"], [".claude/skills"]),
    ("codex", "Codex", ".codex", [".agents/skills"], [".agents/skills"]),
    ("cursor", "Cursor", ".cursor", [".agents/skills", ".cursor/skills", ".claude/skills", ".codex/skills"],
     [".agents/skills", ".cursor/skills", ".claude/skills", ".codex/skills"]),
    ("gemini-cli", "Gemini CLI", ".gemini", [".agents/skills", ".gemini/skills"], [".agents/skills", ".gemini/skills"]),
    ("github-copilot", "GitHub Copilot", ".copilot", [".agents/skills", ".copilot/skills"],
     [".agents/skills", ".github/skills", ".claude/skills"]),
    ("opencode", "opencode", ".config/opencode", [".agents/skills", ".config/opencode/skills", ".claude/skills"],
     [".agents/skills", ".opencode/skills", ".claude/skills"]),
    ("amp", "Amp", ".config/amp", [".agents/skills", ".config/agents/skills", ".config/amp/skills", ".claude/skills"],
     [".agents/skills", ".claude/skills"]),
]
SHOWN = dict((a[0], a[1]) for a in AGENTS)
# In a project, the folder at its top that shows an agent is used there.
PROJECT_MARKS = [(".claude", "claude-code"), (".codex", "codex"), (".cursor", "cursor"), (".gemini", "gemini-cli"),
                 (".github/skills", "github-copilot"), (".opencode", "opencode"), (".agents", "codex")]
# Where a copy goes when several folders would do: the folder most agents share, then Claude Code's.
PREFERRED = [".agents/skills", ".claude/skills"]
# The environment variables that would point git at another repo than the one each call names.
GIT_PLACES = ("GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE", "GIT_OBJECT_DIRECTORY", "GIT_ALTERNATE_OBJECT_DIRECTORIES",
              "GIT_COMMON_DIR", "GIT_NAMESPACE")


class Refusal(Exception):
    """A reason to leave a copy as it is."""


class NotOurs(Refusal):
    """A folder this installer didn't make, or can't trust: never changed, and only noted when the user didn't
    name it."""


class Failure(Exception):
    """A reason the whole run can't go on."""


def say(text=""):
    print(text)
    sys.stdout.flush()


def safe_output():
    """Never fail on printing a path the console can't show, as on Windows with the output piped in its own
    code page: the character becomes a ?."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure") and (stream.encoding or "").lower().replace("-", "") != "utf8":
            stream.reconfigure(errors="replace")


def home():
    return os.path.expanduser("~")


def git(*args, **options):
    """Run git with no prompt (stdin may be this script, so git gets only the bytes given as input), only the
    transports a source may use, and none of the user's variables that would point it at another repo; return
    its output as text, or as bytes with raw=True; raise Failure if it fails, or return None with check=False."""
    env = dict((k, v) for k, v in os.environ.items() if k not in GIT_PLACES)
    env.update(GIT_TERMINAL_PROMPT="0", GIT_PROTOCOL_FROM_USER="0", GIT_ALLOW_PROTOCOL="file:git:https:ssh")
    result = subprocess.run(["git"] + list(args), cwd=options.get("cwd"), input=options.get("input", b""),
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if result.returncode != 0:
        if options.get("check", True):
            message = result.stderr.decode("utf-8", "replace").strip() or "exit %d" % result.returncode
            raise Failure("git %s: %s" % (" ".join(a for a in args[:3] if not a.startswith("/")), message))
        return None
    return result.stdout if options.get("raw") else result.stdout.decode("utf-8", "replace")


def remove_tree(path):
    """Remove a folder, read-only files included (git makes its objects read-only, which Windows won't
    delete as they are)."""
    def writable(function, target, *_):
        os.chmod(target, stat.S_IWRITE | stat.S_IREAD | stat.S_IEXEC)
        function(target)
    if sys.version_info >= (3, 12):
        shutil.rmtree(path, onexc=writable)
    else:
        shutil.rmtree(path, onerror=writable)


def short(commit):
    return (commit or "")[:7]


def shown_path(path):
    """A path as the output shows it: ~ for the home, so that a reader sees where it is at a glance."""
    top = home()
    if path == top or path.startswith(top + os.sep):
        return "~" + path[len(top):]
    return path


def from_where(source):
    """The source, for the output, when it isn't this repo on GitHub."""
    return "" if source == SOURCE else " from %s" % source


# What may be trusted: sources, refs and paths, from the command line, a record or a commit.

def checked_source(given, where="--source"):
    """A source as the record keeps it, a folder as an absolute path; raise Failure if it's none of the kinds
    a source may be."""
    if isinstance(given, str) and given and not given.startswith("-"):
        if URL.match(given):
            return given
        expanded = os.path.expanduser(given)
        if os.path.isdir(expanded):
            return os.path.abspath(expanded)
    raise Failure("%s %r isn't an https, ssh or git URL, nor a folder that exists, so nothing is fetched from it."
                  % (where, given))


def checked_ref(ref):
    if not REF.match(ref) or ".." in ref or ref.endswith((".lock", "/", ".")):
        raise Failure("--ref %r isn't a release tag, a branch or a full commit." % ref)
    return ref


def path_problem(path):
    """Why a path from a record or a commit can't name a file in a copy; None if it can."""
    if not isinstance(path, str) or not path or path.startswith("/") or "\\" in path:
        return "%r isn't a relative path with / between its parts" % (path,)
    for part in path.split("/"):
        if part in ("", ".", "..") or part.lower() == ".git":
            return "%r has a part, %r, that would leave the copy or reach outside a plain folder" % (path, part)
        if any(c in part for c in ':*?"<>|') or any(ord(c) < 32 for c in part) or part[-1] in " ." or \
                RESERVED.match(part):
            return "%r has a name, %r, that some systems can't hold as a file" % (path, part)
    return None


def record_problem(record):
    """Why a copy's .install.json isn't one this installer wrote, or can't be acted on; None if it's sound."""
    if not isinstance(record, dict):
        return "it isn't a JSON object"
    if record.get("skill") != NAME or not isinstance(record.get("record"), int):
        return "it doesn't say it's %s's, in a form this installer reads" % NAME
    files = record.get("files")
    if not isinstance(files, dict) or not files:
        return "its list of files is missing or empty"
    for path, digest_ in sorted(files.items(), key=lambda item: str(item[0])):
        problem = path_problem(path)
        if problem:
            return "it lists a file it can't have installed: " + problem
        if not isinstance(digest_, str) or not DIGEST.match(digest_):
            return "the hash it gives for %r isn't a sha256" % path
    for field, form in (("source", URL), ("ref", REF), ("version", RELEASE), ("commit", COMMIT)):
        value = record.get(field)
        if value is not None and (not isinstance(value, str) or (field != "source" and not form.match(value))):
            return "its %s, %r, isn't one this installer writes" % (field, value)
    if not isinstance(record.get("source"), str):
        return "it names no source"
    return None


# Sources and versions.

def version_key(tag):
    return tuple(int(n) for n in RELEASE.match(tag).groups())


def remote_refs(source, *names):
    """A map from each ref the source has to its commit (git ls-remote), with only well-formed commits."""
    found = {}
    for line in git("ls-remote", "--", source, *names).splitlines():
        sha, _, name = line.partition("\t")
        if COMMIT.match(sha):
            found[name] = sha
    return found


def releases(source):
    """The source's release tags, vMAJOR.MINOR.PATCH, each with its commit."""
    found = {}
    for ref, sha in remote_refs(source, "refs/tags/*").items():
        name = ref[len("refs/tags/"):]
        peeled = name.endswith("^{}")
        name = name[:-3] if peeled else name
        if RELEASE.match(name) and (peeled or name not in found):
            found[name] = sha
    return found


class Target(object):
    """What to install: a ref to fetch, the name to show and record for it, its version (a release tag, or
    None), its commit, and a notice to print."""

    def __init__(self, ref, version, commit, notice=None, shown=None):
        self.ref, self.version, self.commit, self.notice = ref, version, commit, notice
        self.shown = shown or ref

    def label(self):
        return "%s (%s)" % (self.version or self.shown, short(self.commit))


def resolve(source, ref):
    """The Target that ref names on the source; with no ref, the latest release, or else the default branch."""
    if ref:
        checked_ref(ref)
        # Exact names only, a tag's commit first: a pattern alone would also match a clone's refs/remotes/...
        names = ["refs/tags/%s^{}" % ref, "refs/tags/" + ref, "refs/heads/" + ref] + (["HEAD"] if ref == "HEAD" else [])
        listed = remote_refs(source, *names)
        commit = next((listed[n] for n in names if n in listed), ref if COMMIT.match(ref) else None)
        if commit is None:
            raise Failure("%s has no %s: give a release tag, a branch, or a full 40-character commit." % (source, ref))
        return Target(ref, ref if RELEASE.match(ref) else None, commit)
    tags = releases(source)
    if tags:
        latest = max(tags, key=version_key)
        return Target(latest, latest, tags[latest])
    head = git("ls-remote", "--symref", "--", source, "HEAD")
    branch, commit = "HEAD", None
    for line in head.splitlines():
        if line.startswith("ref: refs/heads/"):
            name = line[len("ref: refs/heads/"):].split("\t")[0]
            branch = name if REF.match(name) else branch
        elif line.endswith("\tHEAD") and COMMIT.match(line.split("\t")[0]):
            commit = line.split("\t")[0]
    if not commit:
        raise Failure("%s has no commits to install." % source)
    notice = ("There's no release of %s yet (no vMAJOR.MINOR.PATCH tag), so this is its default branch, %s, at "
              "%s. Update will move it to the first release." % (source, branch, short(commit)))
    return Target("HEAD", None, commit, notice, shown=branch)


def fetch(source, target, into):
    """The skill's files at target, read from the commit's objects in the folder into, not from a checkout:
    a map from each one's path to its bytes and whether it's executable. Only plain files: a link or a
    submodule in the skill's folder is refused, as is a path a copy can't safely hold."""
    git("init", "-q", "--", into)
    git("-C", into, "fetch", "-q", "--depth", "1", "--", source, target.ref)
    commit = git("-C", into, "rev-parse", "--verify", "-q", "FETCH_HEAD^{commit}").strip()
    if not COMMIT.match(commit):
        raise Failure("%s at %s gave no commit." % (source, target.shown))
    target.commit = commit
    where = "%s at %s" % (source, target.label())
    entries, seen = [], {}
    for entry in git("-C", into, "ls-tree", "-r", "-z", commit, "--", SKILL + "/", raw=True).split(b"\0"):
        if not entry:
            continue
        meta, _, raw_path = entry.partition(b"\t")
        mode, kind, sha = meta.decode("ascii", "replace").split(" ")
        path = raw_path.decode("utf-8", "replace")[len(SKILL) + 1:]
        problem = path_problem(path)
        if problem:
            raise Failure("%s holds a file it won't install: %s." % (where, problem))
        if mode not in ("100644", "100755") or kind != "blob":
            raise Failure("%s has %s in %s, which isn't a plain file (a link or a submodule), so nothing was installed."
                          % (where, path, SKILL))
        if path.lower() in seen:
            raise Failure("%s has both %s and %s, which one folder can't hold apart on every system."
                          % (where, seen[path.lower()], path))
        seen[path.lower()] = path
        entries.append((path, sha, mode == "100755"))
    files = read_blobs(into, entries, where)
    if "SKILL.md" not in files:
        raise Failure("%s has no %s/SKILL.md: it's older than the installer's layout, so install a release from "
                      "v1.0.0 on." % (where, SKILL))
    if not re.search(br"(?m)^name:\s*" + NAME.encode() + br"\s*$", files["SKILL.md"][0].split(b"\n---", 1)[0]):
        raise Failure("%s has a SKILL.md that isn't %s's, so nothing was installed." % (where, NAME))
    return files


def read_blobs(repo, entries, where):
    """The blobs that entries (path, hash, executable) name, read with one git cat-file --batch: a map from
    each path to its bytes and whether it's executable."""
    out = git("-C", repo, "cat-file", "--batch", raw=True, input="".join(sha + "\n" for _, sha, _ in entries).encode())
    files, at = {}, 0
    for path, sha, executable in entries:
        end = out.find(b"\n", at)
        header = out[at:end].decode("ascii", "replace").split(" ")
        if end < 0 or len(header) != 3 or header[0] != sha or header[1] != "blob" or not header[2].isdigit():
            raise Failure("%s: git couldn't read %s." % (where, path))
        size = int(header[2])
        data, at = out[end + 1:end + 1 + size], end + 1 + size + 1
        if len(data) != size or out[at - 1:at] != b"\n":
            raise Failure("%s: git couldn't read %s." % (where, path))
        files[path] = (data, executable)
    return files


def digest(data):
    """A file's hash: of its text with CRLF line ends read as LF, so that a checkout's line ends (Git for
    Windows's, by default) don't make it an edit."""
    return hashlib.sha256(data.replace(b"\r\n", b"\n")).hexdigest()


# The copies.

def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def files_in(folder):
    """The files in a copy, as paths with / from it, sorted: not the record, nor bytecode. Raise NotOurs if
    the folder holds a link (or, on Windows, a junction), which this installer never makes."""
    found, real = [], os.path.realpath(folder)
    for top, dirs, names in os.walk(folder):
        for name in dirs + names:
            full = os.path.join(top, name)
            if os.path.islink(full) or not os.path.realpath(full).startswith(real + os.sep):
                raise NotOurs("%s holds a link, %s, which this installer never makes: left alone."
                              % (shown_path(folder), os.path.relpath(full, folder)))
        dirs[:] = sorted(d for d in dirs if d != BYTECODE)
        for name in names:
            path = os.path.relpath(os.path.join(top, name), folder).replace(os.sep, "/")
            if path != RECORD:
                found.append(path)
    return sorted(found)


def read_record(folder):
    """The copy's record, checked; None if it has none; raise NotOurs if it can't be trusted."""
    path = os.path.join(folder, RECORD)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            record = json.load(f)
    except (ValueError, UnicodeDecodeError):
        record = "unreadable"
    problem = "it isn't JSON" if record == "unreadable" else record_problem(record)
    if problem:
        raise NotOurs("%s has an %s this installer can't act on (%s): left alone. Move or delete the copy yourself."
                      % (shown_path(folder), RECORD, problem))
    return record


def changes(folder, record):
    """What changed in a recorded copy since it was installed: files edited or gone, and files added."""
    present = files_in(folder)
    edited = [p for p, h in sorted(record["files"].items())
              if p not in present or digest(read_bytes(os.path.join(folder, *p.split("/")))) != h]
    added = [p for p in present if p not in record["files"]]
    return edited, added


def examine(folder, force):
    """The record of the copy in folder, None if there's none yet; raise Refusal if it isn't one this installer
    may change."""
    if os.path.islink(folder):
        raise NotOurs("%s is a link, to %s: left alone. Install into the folder it points to, or remove the "
                      "link." % (shown_path(folder), os.path.realpath(folder)))
    if not os.path.exists(folder):
        return None
    if not os.path.isdir(folder):
        raise NotOurs("%s is a file, not a folder: left alone. Move it away, then run this again."
                      % shown_path(folder))
    if os.path.exists(os.path.join(folder, ".git")):
        raise NotOurs("%s is a git clone: left alone, and never deleted. To keep using it, pull in it; to install "
                      "instead, move it out of the skills folder first." % shown_path(folder))
    record = read_record(folder)
    if record is None:
        kind = "a copy of a skill" if os.path.isfile(os.path.join(folder, "SKILL.md")) else "a folder"
        raise NotOurs("%s is %s that this installer didn't make (it has no %s): left alone. Move or delete it "
                      "yourself, then run this again." % (shown_path(folder), kind, RECORD))
    edited, added = changes(folder, record)
    if (edited or added) and not force:
        kinds = (("edited since it was installed", edited), ("holding files it didn't install", added))
        what = [kind + ": " + ", ".join(paths[:5]) + (" ..." if len(paths) > 5 else "")
                for kind, paths in kinds if paths]
        raise Refusal("%s is %s. Left alone; --force replaces or removes them."
                      % (shown_path(folder), "; and ".join(what)))
    return record


def umask():
    mask = os.umask(0)
    os.umask(mask)
    return mask


def put(folder, get_files, source, target, force, dry_run):
    """Install the files get_files() gives, fetched only once a copy needs them, as the copy in folder: built
    beside it, then swapped in, so a failure leaves the old copy whole. Returns what it did."""
    record = examine(folder, force)
    if record and (record.get("commit"), record.get("version")) == (target.commit, target.version) and \
            changes(folder, record) == ([], []):
        return "already at %s" % target.label()
    if record:
        action = "%s %s (%s)" % ("would replace" if dry_run else "replaced", record.get("version") or record.get("ref"),
                                 short(record.get("commit")))
    else:
        action = "would be installed" if dry_run else "installed"
    if dry_run:
        return action
    files = get_files()
    mask = umask()
    parent = os.path.dirname(folder)
    if not os.path.isdir(parent):
        os.makedirs(parent)
    staging = tempfile.mkdtemp(prefix=STAGING, dir=parent)
    retired = None
    try:
        hashes = {}
        for path in sorted(files, key=lambda p: p == "SKILL.md"):  # SKILL.md last, so a part copy isn't a skill.
            data, executable = files[path]
            full = os.path.join(staging, *path.split("/"))
            if not os.path.isdir(os.path.dirname(full)):
                os.makedirs(os.path.dirname(full))
            with open(full, "wb") as f:
                f.write(data)
            if executable:
                os.chmod(full, 0o777 & ~mask)
            hashes[path] = digest(data)
        new_record = {"record": RECORD_FORMAT, "skill": NAME, "source": source, "ref": target.shown,
                      "version": target.version, "commit": target.commit,
                      "installed": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "files": hashes}
        with open(os.path.join(staging, RECORD), "w", encoding="utf-8") as f:
            json.dump(new_record, f, indent=2, sort_keys=True)
            f.write("\n")
        os.chmod(staging, 0o777 & ~mask)  # As a folder mkdir makes, not mkdtemp's owner-only one.
        try:
            if os.path.exists(folder):
                retired = tempfile.mkdtemp(prefix=RETIRED, dir=parent)
                os.rmdir(retired)
                os.rename(folder, retired)
            os.rename(staging, folder)
        except BaseException:  # An error or an interrupt: the old copy goes back in its place.
            if retired and os.path.isdir(retired) and not os.path.exists(folder):
                os.rename(retired, folder)
                retired = None
            elif retired and os.path.isdir(retired):
                say("The old copy is in %s: remove it yourself, as an agent may load it as a second copy."
                    % shown_path(retired))
            raise
    finally:
        if os.path.isdir(staging):
            remove_tree(staging)
    if retired:
        try:
            remove_tree(retired)
        except OSError as error:
            say("Warning: the old copy, moved to %s, couldn't be removed (%s): remove it yourself, as an agent may "
                "load it as a second copy." % (retired, error.strerror or error))
    return action


def remove_copy(folder, force, dry_run):
    """Remove the files the record in folder lists, the record, Python's bytecode, and the folders left empty:
    the copy is moved aside first, so if that fails nothing has changed. Files it didn't install (only with
    --force) are put back."""
    record = examine(folder, force)
    if record is None:
        raise Refusal("%s isn't there." % shown_path(folder))
    kept = [p for p in files_in(folder) if p not in record["files"]]
    if dry_run:
        return "would be removed" + (", but for the files it didn't install: " + ", ".join(kept) if kept else "")
    retired = tempfile.mkdtemp(prefix=RETIRED, dir=os.path.dirname(folder))
    os.rmdir(retired)
    os.rename(folder, retired)
    try:
        for path in record["files"]:
            full = os.path.join(retired, *path.split("/"))
            if os.path.isfile(full):
                os.remove(full)
        os.remove(os.path.join(retired, RECORD))
        for top, dirs, names in os.walk(retired, topdown=False):
            if os.path.basename(top) == BYTECODE:
                remove_tree(top)
            elif not os.listdir(top):
                os.rmdir(top)
        if kept:
            os.rename(retired, folder)
            return "removed, but for the files it didn't install: " + ", ".join(kept)
    except BaseException as error:  # An error or an interrupt: what's left goes back, or the output says where.
        try:
            os.rename(retired, folder)
            left = "what's left of it is back in its place"
        except OSError:
            left = ("what's left of it is in %s: remove that folder yourself, as an agent may load it as a second "
                    "copy" % shown_path(retired))
        if isinstance(error, OSError):
            raise OSError(error.errno, "%s; %s." % (error.strerror or error, left))
        say("%s: stopped; %s." % (shown_path(folder), left))
        raise
    return "removed"


# Where the copies go.

def detected():
    """The agents installed on this machine, known by their folders in the home."""
    return [a[0] for a in AGENTS if os.path.isdir(os.path.join(home(), *a[2].split("/")))]


def folders_of(agent, kind):
    row = next(a for a in AGENTS if a[0] == agent)
    return row[3] if kind == "user" else row[4]


def choose(agents, kind):
    """The skills folders to install into for these agents: each agent reads one; as few as read two copies;
    then as few copies as can be; then the folders most agents share. With the agents each serves."""
    order = PREFERRED + [f for a in AGENTS for f in (a[3] if kind == "user" else a[4]) if f not in PREFERRED]
    candidates = sorted(set(f for a in agents for f in folders_of(a, kind)), key=order.index)
    best = None
    for size in range(1, len(candidates) + 1):
        for chosen in itertools.combinations(candidates, size):
            reads = [sum(f in folders_of(a, kind) for f in chosen) for a in agents]
            if min(reads) == 0:
                continue
            key = (sum(r > 1 for r in reads), size, [order.index(f) for f in chosen])
            if best is None or key < best[0]:
                best = (key, chosen)
    return [(f, [a for a in agents if f in folders_of(a, kind)]) for f in best[1]]


def project_top(required=True):
    top = git("rev-parse", "--show-toplevel", check=False)
    if not top:
        if required:
            raise Failure("--project needs to run inside a git repo; this folder, %s, isn't in one." % os.getcwd())
        return None
    return os.path.normpath(top.strip())


def in_project(folder, top):
    """Whether a folder in the project is in it once links are followed: a link out of the project (as a
    committed .agents that points into your home) never takes a copy out of it."""
    real = os.path.realpath(top)
    return os.path.realpath(folder).startswith(real + os.sep)


def project_agents(top):
    found = []
    for mark, agent in PROJECT_MARKS:
        if os.path.exists(os.path.join(top, *mark.split("/"))) and agent not in found:
            found.append(agent)
    return found


def dir_target(given):
    """--dir: a skills folder, the copy going in it as refactor-pass; or the copy's own folder, so named."""
    path = os.path.abspath(os.path.expanduser(given))
    return path if os.path.basename(path) == NAME else os.path.join(path, NAME)


def install_targets(args):
    """Where install puts copies: a list of (folder, the agents it's for)."""
    targets = [(dir_target(d), []) for d in args.dir]
    if args.project:
        top = project_top()
        agents = args.agent or project_agents(top) or detected()
        if not agents:
            raise Failure(no_agents("in this project or on this machine"))
        targets += [(os.path.join(top, *f.split("/") + [NAME]), a) for f, a in choose(agents, "project")]
    elif args.agent or not args.dir:
        agents = args.agent or detected()
        if not agents:
            raise Failure(no_agents("on this machine"))
        targets += [(os.path.join(home(), *f.split("/") + [NAME]), a) for f, a in choose(agents, "user")]
    return targets


def no_agents(where):
    lines = ["No coding agent was found %s, so nothing was installed. Name one or more with --agent:" % where]
    lines += ["  --agent %-15s %s, in ~/%s" % (a[0], a[1], a[3][0]) for a in AGENTS]
    lines.append("or name any skills folder with --dir, or put a copy in the current git repo with --project.")
    return "\n".join(lines)


def copies(args):
    """The copies this installer made that update, check and uninstall work on: those --agent, --dir and
    --project name, or else every one in any agent's folders and the current project's. A project's folder
    that a link takes out of the project is left out."""
    folders = [dir_target(d) for d in args.dir]
    everywhere = not named(args)
    if args.agent or everywhere:
        for agent in args.agent or [a[0] for a in AGENTS]:
            folders += [os.path.join(home(), *f.split("/") + [NAME]) for f in folders_of(agent, "user")]
    if args.project or everywhere:
        top = project_top(required=bool(args.project))
        if top:
            for agent in args.agent or [a[0] for a in AGENTS]:
                folders += [f for f in (os.path.join(top, *p.split("/") + [NAME]) for p in folders_of(agent, "project"))
                            if in_project(f, top)]
    unique, seen = [], set()
    for folder in folders:
        key = os.path.normcase(os.path.realpath(folder))
        if key not in seen and (os.path.lexists(folder) or not everywhere):
            seen.add(key)
            unique.append(folder)
    return unique


# The commands.

def run_install(args):
    source = checked_source(args.source or SOURCE)
    targets = install_targets(args)
    if args.project:
        top = project_top()
        for folder, _ in targets:
            if not in_project(folder, top):
                raise Failure("%s leads out of this project through a link, so nothing was installed there."
                              % shown_path(folder))
    target = resolve(source, args.ref)
    if target.notice:
        say(target.notice)
    say("%s refactor-pass %s from %s:" % ("Would install" if args.dry_run else "Installing", target.label(), source))
    return put_all([(folder, agents, source) for folder, agents in targets], {source: target}, args, False)


def put_all(plan, targets, args, show_source):
    """Put each (folder, agents, source) of plan at targets[source], fetching each source once, and only when a
    copy needs it. A copy that can't be written is a line of its own, and the others are still done."""
    failed = 0
    fetched = {}
    work = tempfile.mkdtemp(prefix="refactor-pass-install-")
    try:
        for folder, agents, source in plan:
            target = targets[source]
            note = " (for %s)" % ", ".join(SHOWN[a] for a in agents) if agents else ""
            note += from_where(source) if show_source else ""

            def get_files(source=source, target=target):
                if source not in fetched:
                    fetched[source] = fetch(source, target, os.path.join(work, str(len(fetched))))
                return fetched[source]
            try:
                say("  %s: %s%s" % (shown_path(folder), put(folder, get_files, source, target, args.force,
                                                            args.dry_run), note))
            except Refusal as refusal:
                failed += 1
                say("  Refused: %s" % refusal)
            except OSError as error:
                failed += 1
                say("  %s: couldn't write it: %s" % (shown_path(folder), error.strerror or error))
    finally:
        remove_tree(work)
    twice = [a for a in set(a for _, agents, _ in plan for a in agents)
             if sum(a in agents for _, agents, _ in plan) > 1]
    for agent in sorted(twice):
        say("Note: %s reads more than one of these folders, so it may list the skill twice." % SHOWN[agent])
    return 1 if failed else 0


def named(args):
    """Whether the copies to work on were named (--agent, --dir, --project), rather than looked for."""
    return bool(args.agent or args.dir or args.project)


def refused(refusal, args, seen):
    """Print a refusal, and count it in seen; return 1 if it counts as a failure: a folder this installer
    didn't make doesn't, when it was only come across while looking in every agent's folders."""
    seen.append(refusal)
    if isinstance(refusal, NotOurs) and not named(args):
        say("Left alone: %s" % refusal)
        return 0
    say("Refused: %s" % refusal)
    return 1


def none_done(what, seen, args):
    """What to say when no copy was acted on: that nothing was, if some were left alone; else that none was
    found."""
    if seen:
        return "Nothing was %s." % what
    return "No copy of refactor-pass that this installer made was found%s." % (
        "" if named(args) else " in the agents' folders or this project")


def source_of(record, args, folder):
    """The source to update or check a copy against: --source, or the one its record names, if that may be one."""
    if args.source:
        return checked_source(args.source)
    try:
        return checked_source(record["source"])
    except Failure:
        raise NotOurs("%s's %s names a source, %r, that isn't an https, ssh or git URL, nor a folder that exists: "
                      "left alone, and nothing fetched from it." % (shown_path(folder), RECORD, record["source"]))


def run_update(args):
    plan, targets, failed, seen = [], {}, 0, []
    for folder in copies(args):
        try:
            record = examine(folder, args.force)
            if record is None:
                continue
            source = source_of(record, args, folder)
        except Refusal as refusal:
            failed += refused(refusal, args, seen)
            continue
        if source not in targets:
            targets[source] = resolve(source, args.ref)
            if targets[source].notice:
                say(targets[source].notice)
        plan.append((folder, [], source))
    if not plan:
        say(none_done("updated", seen, args))
        return 1 if failed else 0
    say("%s to %s:" % ("Would update" if args.dry_run else "Updating", args.ref or "the latest"))
    return put_all(plan, targets, args, True) or (1 if failed else 0)


def run_check(args):
    latest, failed, any_copy, seen = {}, 0, False, []
    for folder in [f for f in copies(args) if os.path.lexists(f)]:
        try:
            record = examine(folder, True)
            source = source_of(record, args, folder)
        except Refusal as refusal:
            failed += refused(refusal, args, seen)
            continue
        any_copy = True
        if source not in latest:
            latest[source] = resolve(source, args.ref)
        target = latest[source]
        edited, added = changes(folder, record)
        state = "up to date" if record.get("commit") == target.commit else "update brings %s" % target.label()
        if edited or added:
            state += "; edited since it was installed"
        say("%s: %s (%s)%s; %s." % (shown_path(folder), record.get("version") or record.get("ref"),
                                   short(record.get("commit")), from_where(source), state))
    if not any_copy:
        say(none_done("checked", seen, args))
    return 1 if failed else 0


def run_uninstall(args):
    failed, done, seen = 0, 0, []
    for folder in [f for f in copies(args) if os.path.lexists(f)]:
        try:
            say("%s: %s" % (shown_path(folder), remove_copy(folder, args.force, args.dry_run)))
            done += 1
        except Refusal as refusal:
            failed += refused(refusal, args, seen)
        except OSError as error:
            failed += 1
            seen.append(error)
            say("%s: couldn't remove it: %s" % (shown_path(folder), error.strerror or error))
    if not done:
        say(none_done("removed", seen, args))
    return 1 if failed else 0


def main(argv=None):
    parser = argparse.ArgumentParser(prog="install.py", description=__doc__.split("\n\n")[0],
                                     formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog=__doc__.split("\n\n", 1)[1])
    parser.add_argument("command", nargs="?", default="install", choices=["install", "update", "check", "uninstall"])
    parser.add_argument("--agent", action="append", default=[], choices=[a[0] for a in AGENTS], metavar="NAME",
                        help="an agent to install for, instead of those found (repeatable): " +
                        ", ".join(a[0] for a in AGENTS))
    parser.add_argument("--dir", action="append", default=[], metavar="DIR",
                        help="a skills folder anywhere, for DIR/refactor-pass (repeatable)")
    parser.add_argument("--project", action="store_true",
                        help="the current git repo's skills folder, for its agents, to commit")
    parser.add_argument("--ref", help="a release tag, a branch or a full commit, instead of the latest release")
    parser.add_argument("--source", help="an https, ssh or git URL, or a local folder, to install from "
                        "(default: %s)" % SOURCE)
    parser.add_argument("--force", action="store_true",
                        help="replace or remove a copy whose files were edited, or that holds files it didn't install")
    parser.add_argument("--dry-run", action="store_true", help="print what it would do, and change nothing")
    args = parser.parse_args(argv)
    safe_output()
    commands = {"install": run_install, "update": run_update, "check": run_check, "uninstall": run_uninstall}
    try:
        if args.ref:
            checked_ref(args.ref)
        return commands[args.command](args)
    except Failure as failure:
        say(str(failure))
        return 1
    except Refusal as refusal:
        say("Refused: %s" % refusal)
        return 1
    except OSError as error:
        say("Couldn't go on: %s%s" % (error.strerror or error, " (%s)" % error.filename if error.filename else ""))
        return 1


if __name__ == "__main__":
    sys.exit(main())
