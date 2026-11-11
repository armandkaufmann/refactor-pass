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
branch is installed, with a notice, and update moves it to the first release when there is one.

Each copy gets a small .install.json beside SKILL.md: where it came from, its version, and a hash of each
file. A copy whose files were edited since, or that holds files it didn't install, is left alone unless
--force; a folder this installer didn't make (with no .install.json), and a git clone, always are.

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


class Refusal(Exception):
    """A reason to leave a copy as it is."""


class NotOurs(Refusal):
    """A folder this installer didn't make: never changed, and only noted when the user didn't name it."""


class Failure(Exception):
    """A reason the whole run can't go on."""


def say(text=""):
    print(text)
    sys.stdout.flush()


def home():
    return os.path.expanduser("~")


def git(*args, **options):
    """Run git with no prompt (stdin may be this script) and return its output; raise Failure if it fails."""
    env = dict(os.environ, GIT_TERMINAL_PROMPT="0")
    result = subprocess.run(["git"] + list(args), cwd=options.get("cwd"), stdin=subprocess.DEVNULL,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    if result.returncode != 0:
        if options.get("check", True):
            message = result.stderr.decode("utf-8", "replace").strip() or "exit %d" % result.returncode
            raise Failure("git %s: %s" % (" ".join(args[:2]), message))
        return None
    return result.stdout.decode("utf-8", "replace")


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


# Sources and versions.

def normal_source(given):
    """A source as the record keeps it: a local folder as an absolute path, anything else as given."""
    expanded = os.path.expanduser(given)
    return os.path.abspath(expanded) if os.path.isdir(expanded) else given


def version_key(tag):
    return tuple(int(n) for n in RELEASE.match(tag).groups())


def releases(source):
    """The source's release tags, vMAJOR.MINOR.PATCH, each with its commit."""
    found = {}
    for line in git("ls-remote", "--tags", source).splitlines():
        sha, _, ref = line.partition("\t")
        name = ref[len("refs/tags/"):]
        peeled = name.endswith("^{}")
        name = name[:-3] if peeled else name
        if RELEASE.match(name) and (peeled or name not in found):
            found[name] = sha
    return found


class Target(object):
    """What to install: a ref, its version (a release tag, or None), its commit, and a notice to print."""

    def __init__(self, ref, version, commit, notice=None):
        self.ref, self.version, self.commit, self.notice = ref, version, commit, notice

    def label(self):
        return "%s (%s)" % (self.version or self.ref, short(self.commit))


def resolve(source, ref):
    """The Target that ref names on the source; with no ref, the latest release, or else the default branch."""
    if ref:
        # Exact names only, a tag's commit first: a pattern alone would also match a clone's refs/remotes/...
        names = ["refs/tags/%s^{}" % ref, "refs/tags/" + ref, "refs/heads/" + ref] + (["HEAD"] if ref == "HEAD" else [])
        listed = {}
        for line in (git("ls-remote", source, *names, check=False) or "").splitlines():
            sha, _, name = line.partition("\t")
            listed[name] = sha
        commit = next((listed[n] for n in names if n in listed), None)
        if commit is None and re.match(r"^[0-9a-f]{40}$", ref):
            commit = ref
        if commit is None:
            raise Failure("%s has no %s: give a release tag, a branch, or a full 40-character commit." % (source, ref))
        return Target(ref, ref if RELEASE.match(ref) else None, commit)
    tags = releases(source)
    if tags:
        latest = max(tags, key=version_key)
        return Target(latest, latest, tags[latest])
    head = git("ls-remote", "--symref", source, "HEAD")
    branch, commit = "HEAD", None
    for line in head.splitlines():
        if line.startswith("ref: refs/heads/"):
            branch = line[len("ref: refs/heads/"):].split("\t")[0]
        elif line.endswith("\tHEAD"):
            commit = line.split("\t")[0]
    if not commit:
        raise Failure("%s has no commits to install." % source)
    notice = ("There's no release of %s yet (no vMAJOR.MINOR.PATCH tag), so this is its default branch, %s, at "
              "%s. Update will move it to the first release." % (source, branch, short(commit)))
    return Target(branch, None, commit, notice)


def fetch(source, target, into):
    """The skill's files at target, fetched into the folder into: a map from each one's path to its bytes."""
    git("init", "-q", into)
    git("-C", into, "fetch", "-q", "--depth", "1", source, target.ref)
    git("-C", into, "-c", "advice.detachedHead=false", "checkout", "-q", "FETCH_HEAD")
    target.commit = git("-C", into, "rev-parse", "HEAD").strip()
    folder = os.path.join(into, *SKILL.split("/"))
    if not os.path.isfile(os.path.join(folder, "SKILL.md")):
        raise Failure("%s at %s has no %s/SKILL.md: it's older than the installer's layout, so install a "
                      "release from v1.0.0 on." % (source, target.ref, SKILL))
    return dict((path, read_bytes(os.path.join(folder, *path.split("/")))) for path in files_in(folder))


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


def files_in(folder):
    """The files in a skill's folder, as paths with / from it, sorted: not the record, nor bytecode."""
    found = []
    for top, dirs, names in os.walk(folder):
        dirs[:] = sorted(d for d in dirs if d != BYTECODE)
        for name in names:
            path = os.path.relpath(os.path.join(top, name), folder).replace(os.sep, "/")
            if path != RECORD:
                found.append(path)
    return sorted(found)


def digest(data):
    return hashlib.sha256(data).hexdigest()


# The copies.

def read_record(folder):
    path = os.path.join(folder, RECORD)
    if not os.path.isfile(path):
        return None
    try:
        with open(path, encoding="utf-8") as f:
            record = json.load(f)
    except ValueError:
        return None
    return record if isinstance(record, dict) and isinstance(record.get("files"), dict) else None


def changes(folder, record):
    """What changed in a recorded copy since it was installed: files edited or gone, and files added."""
    edited = [p for p, h in sorted(record["files"].items())
              if not os.path.isfile(os.path.join(folder, *p.split("/")))
              or digest(read_bytes(os.path.join(folder, *p.split("/")))) != h]
    added = [p for p in files_in(folder) if p not in record["files"]]
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


def put(folder, get_files, source, target, force, dry_run):
    """Install the files get_files() gives (path to bytes), fetched only once a copy needs them, as the copy in
    folder: built beside it, then swapped in, so a failure leaves the old copy whole. Returns what it did."""
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
    parent = os.path.dirname(folder)
    if not os.path.isdir(parent):
        os.makedirs(parent)
    staging = tempfile.mkdtemp(prefix=STAGING, dir=parent)
    retired = None
    try:
        hashes = {}
        for path in sorted(files, key=lambda p: p == "SKILL.md"):  # SKILL.md last, so a part copy isn't a skill.
            full = os.path.join(staging, *path.split("/"))
            if not os.path.isdir(os.path.dirname(full)):
                os.makedirs(os.path.dirname(full))
            with open(full, "wb") as f:
                f.write(files[path])
            hashes[path] = digest(files[path])
        new_record = {"record": RECORD_FORMAT, "skill": NAME, "source": source, "ref": target.ref,
                      "version": target.version, "commit": target.commit,
                      "installed": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                      "files": hashes}
        with open(os.path.join(staging, RECORD), "w", encoding="utf-8") as f:
            json.dump(new_record, f, indent=2, sort_keys=True)
            f.write("\n")
        if os.path.exists(folder):
            retired = tempfile.mkdtemp(prefix=RETIRED, dir=parent)
            os.rmdir(retired)
            os.rename(folder, retired)
        try:
            os.rename(staging, folder)
        except OSError:
            if retired:
                os.rename(retired, folder)
                retired = None
            raise
    finally:
        if os.path.isdir(staging):
            remove_tree(staging)
    if retired:
        try:
            remove_tree(retired)
        except OSError as error:
            say("Warning: the old copy, moved to %s, couldn't be removed (%s): remove it yourself." % (retired, error))
    return action


def remove_copy(folder, force, dry_run):
    """Remove the files the record in folder lists, the record, Python's bytecode, and the folders left empty."""
    record = examine(folder, force)
    if record is None:
        raise Refusal("%s isn't there." % shown_path(folder))
    kept = [p for p in files_in(folder) if p not in record["files"]]
    if dry_run:
        return "would be removed" + (", but for the files it didn't install: " + ", ".join(kept) if kept else "")
    for path in record["files"]:
        full = os.path.join(folder, *path.split("/"))
        if os.path.isfile(full):
            os.remove(full)
    os.remove(os.path.join(folder, RECORD))
    for top, dirs, names in os.walk(folder, topdown=False):
        if os.path.basename(top) == BYTECODE:
            remove_tree(top)
        elif not os.listdir(top):
            os.rmdir(top)
    if kept:
        return "removed, but for the files it didn't install: " + ", ".join(kept)
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


def project_top():
    top = git("rev-parse", "--show-toplevel", check=False)
    if not top:
        raise Failure("--project needs to run inside a git repo; this folder, %s, isn't in one." % os.getcwd())
    return os.path.normpath(top.strip())


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
    --project name, or else every one in any agent's folders and the current project's."""
    folders = [dir_target(d) for d in args.dir]
    everywhere = not named(args)
    if args.agent or everywhere:
        for agent in args.agent or [a[0] for a in AGENTS]:
            folders += [os.path.join(home(), *f.split("/") + [NAME]) for f in folders_of(agent, "user")]
    if args.project or everywhere:
        top = project_top() if args.project else (git("rev-parse", "--show-toplevel", check=False) or "").strip()
        if top:
            for agent in args.agent or [a[0] for a in AGENTS]:
                folders += [os.path.join(os.path.normpath(top), *f.split("/") + [NAME])
                            for f in folders_of(agent, "project")]
    unique, seen = [], set()
    for folder in folders:
        key = os.path.normcase(os.path.realpath(folder))
        if key not in seen and (os.path.lexists(folder) or not everywhere):
            seen.add(key)
            unique.append(folder)
    return unique


# The commands.

def run_install(args):
    targets = install_targets(args)
    source = normal_source(args.source or SOURCE)
    target = resolve(source, args.ref)
    if target.notice:
        say(target.notice)
    say("%s refactor-pass %s from %s:" % ("Would install" if args.dry_run else "Installing", target.label(), source))
    return put_all([(folder, agents, source) for folder, agents in targets], {source: target}, args)


def put_all(plan, targets, args):
    """Put each (folder, agents, source) of plan at targets[source], fetching each source once."""
    failed = 0
    fetched = {}
    work = tempfile.mkdtemp(prefix="refactor-pass-install-")
    try:
        for folder, agents, source in plan:
            target = targets[source]
            note = " (for %s)" % ", ".join(SHOWN[a] for a in agents) if agents else ""

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


def refused(refusal, args):
    """Print a refusal; return 1 if it counts as a failure: a folder this installer didn't make doesn't, when
    it was only come across while looking in every agent's folders."""
    if isinstance(refusal, NotOurs) and not named(args):
        say("Left alone: %s" % refusal)
        return 0
    say("Refused: %s" % refusal)
    return 1


def run_update(args):
    found = copies(args)
    plan, targets, failed = [], {}, 0
    for folder in found:
        try:
            record = examine(folder, args.force)
        except Refusal as refusal:
            failed += refused(refusal, args)
            continue
        if record is None:
            continue
        source = normal_source(args.source) if args.source else record.get("source") or SOURCE
        if source not in targets:
            targets[source] = resolve(source, args.ref)
            if targets[source].notice:
                say(targets[source].notice)
        plan.append((folder, [], source))
    if not plan:
        say("No copy of refactor-pass that this installer made was found%s." % (
            "" if named(args) else " in the agents' folders or this project"))
        return 1 if failed else 0
    say("%s to the latest:" % ("Would update" if args.dry_run else "Updating"))
    return put_all(plan, targets, args) or (1 if failed else 0)


def run_check(args):
    found = [f for f in copies(args) if os.path.lexists(f)]
    latest, failed, any_copy = {}, 0, False
    for folder in found:
        try:
            record = examine(folder, True)
        except Refusal as refusal:
            failed += refused(refusal, args)
            continue
        any_copy = True
        source = record.get("source") or SOURCE
        if source not in latest:
            latest[source] = resolve(source, args.ref)
        target = latest[source]
        edited, added = changes(folder, record)
        state = "up to date" if record.get("commit") == target.commit else "update brings %s" % target.label()
        if edited or added:
            state += "; edited since it was installed"
        say("%s: %s (%s), from %s; %s." % (shown_path(folder), record.get("version") or record.get("ref"),
                                          short(record.get("commit")), source, state))
    if not any_copy and not failed:
        say("No copy of refactor-pass that this installer made was found.")
    return 1 if failed else 0


def run_uninstall(args):
    failed, done = 0, 0
    for folder in [f for f in copies(args) if os.path.lexists(f)]:
        try:
            say("%s: %s" % (shown_path(folder), remove_copy(folder, args.force, args.dry_run)))
            done += 1
        except Refusal as refusal:
            failed += refused(refusal, args)
    if not done and not failed:
        say("No copy of refactor-pass that this installer made was found.")
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
    parser.add_argument("--source", help="a clone URL or a local folder to install from (default: %s)" % SOURCE)
    parser.add_argument("--force", action="store_true",
                        help="replace or remove a copy whose files were edited, or that holds files it didn't install")
    parser.add_argument("--dry-run", action="store_true", help="print what it would do, and change nothing")
    args = parser.parse_args(argv)
    commands = {"install": run_install, "update": run_update, "check": run_check, "uninstall": run_uninstall}
    try:
        return commands[args.command](args)
    except Failure as failure:
        say(str(failure))
        return 1
    except Refusal as refusal:
        say("Refused: %s" % refusal)
        return 1


if __name__ == "__main__":
    sys.exit(main())
