"""install.py, against small source repos built here with release tags, and a home folder of its own in the
run's temporary folder for every run: what it installs and where, which version, update, check and
uninstall, every refusal leaving the target as it was, and a copy that works. No network: the source is
always a local repo, given with --source.
"""

import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import unittest

try:
    from . import support
except ImportError:
    import support

INSTALLER = os.path.join(support.ROOT, "install.py")
RECORD = ".install.json"


def read(path):
    with open(path, "rb") as f:
        return f.read()


def tree(folder):
    """Every file under folder, hidden ones too, as a map from its path with / to its bytes."""
    found = {}
    for top, dirs, names in os.walk(folder):
        for name in names:
            path = os.path.join(top, name)
            found[os.path.relpath(path, folder).replace(os.sep, "/")] = read(path)
    return found


def skill_files():
    """The skill's files as this checkout has them."""
    return dict((path, data) for path, data in tree(support.SKILL).items() if "__pycache__" not in path)


def source_repo(name, versions, tagged=True):
    """A source repo whose commits each hold skills/refactor-pass (plus or less some files) and files an
    installed copy must never get, tagged as versions says: [(tag or None, extra files, dropped files)]."""
    repo = support.Repo(name)
    marks = []
    for day, (tag, extra, dropped) in enumerate(versions, 1):
        files = dict(("skills/refactor-pass/" + p, d) for p, d in skill_files().items() if p not in dropped)
        files.update(("skills/refactor-pass/" + p, d) for p, d in extra.items())
        files.update({"README.md": "# refactor-pass\n", "LICENSE": "MIT\n", "tests/test_x.py": "x = 1\n",
                      ".github/workflows/tests.yml": "name: tests\n", "install.py": "print(1)\n"})
        delete = ["skills/refactor-pass/" + p for p in dropped]
        marks.append((tag, repo.commit("2026-01-%02d" % day, "Release %s" % tag, files, delete=delete)))
    repo.done()
    for tag, mark in marks:
        if tag and tagged:
            support.git(repo.path, "-c", "user.name=A", "-c", "user.email=a@example.com", "tag", "-a", tag,
                        "-m", tag, repo.sha(mark))
    return repo


class Run(object):
    """A finished installer run, with its home, project and temporary folders."""

    def __init__(self, result, home, temp):
        self.code, self.out, self.home, self.temp = result.code, result.out, home, temp

    def __repr__(self):
        return "exit %d\n%s" % (self.code, self.out)


def install(*args, **options):
    """Run install.py with a home and a temporary folder of its own, both in the run's temporary folder: from
    the checkout, or piped on stdin as the one-line install runs it. Options: home, cwd, piped."""
    home = options.get("home") or support.new_folder("home")
    temp = support.new_folder("tmp")
    assert home.startswith(support.temp_root()) and temp.startswith(support.temp_root()), (home, temp)
    env = support.environment(HOME=home, USERPROFILE=home, TMPDIR=temp, TEMP=temp, TMP=temp)
    for key in ("XDG_CONFIG_HOME", "CODEX_HOME", "CLAUDE_CONFIG_DIR", "COPILOT_HOME"):
        env.pop(key, None)
    if options.get("piped"):
        command, given = [sys.executable, "-"] + list(args), read(INSTALLER)
    else:
        command, given = [sys.executable, INSTALLER] + list(args), None
    result = subprocess.run(command, cwd=options.get("cwd") or temp, input=given, capture_output=True, env=env,
                            timeout=120)
    return Run(support.Result(result.returncode, support._text(result.stdout), support._text(result.stderr)),
               home, temp)


def home_with(*agents):
    """A home folder where these agents' own folders are, as if installed."""
    home = support.new_folder("home")
    for folder in agents:
        os.makedirs(os.path.join(home, *folder.split("/")))
    return home


def record(folder):
    with open(os.path.join(folder, RECORD), encoding="utf-8") as f:
        return json.load(f)


class Sources(object):
    """The source repos the tests install from, built once: releases v1.2.0, v1.9.0 and v1.10.0, then an
    unreleased commit on main; v1.10.0 drops references/old.md, and main adds references/new.md."""

    built = {}

    @classmethod
    def tagged(cls):
        if "tagged" not in cls.built:
            cls.built["tagged"] = source_repo("source", [
                ("v1.2.0", {"references/old.md": "old\n"}, []),
                ("v1.9.0", {"references/old.md": "old 9\n"}, []),
                ("v1.10.0", {}, ["references/old.md"]),
                (None, {"references/new.md": "new\n"}, [])]).path
        return cls.built["tagged"]

    @classmethod
    def untagged(cls):
        if "untagged" not in cls.built:
            cls.built["untagged"] = source_repo("untagged", [("v0", {}, []), (None, {"references/new.md": "x\n"}, [])],
                                                tagged=False).path
        return cls.built["untagged"]


def expected(extra=(), dropped=()):
    files = dict(skill_files())
    files.update(extra)
    for path in dropped:
        files.pop(path, None)
    return files


class Installs(unittest.TestCase):

    def assertCopy(self, folder, files, version):
        found = tree(folder)
        self.assertEqual(sorted(found), sorted(list(files) + [RECORD]))
        self.assertEqual(dict((p, d) for p, d in found.items() if p != RECORD), files)
        self.assertEqual(record(folder)["version"], version)

    def assertNoLeftovers(self, run, *folders):
        self.assertEqual(os.listdir(run.temp), [], "the temporary folder")
        for folder in folders:
            parent = os.path.dirname(folder)
            if os.path.isdir(parent):
                self.assertEqual([n for n in os.listdir(parent) if n.startswith(".refactor-pass")], [], parent)

    def test_only_the_skill_is_installed_at_the_latest_release(self):
        run = install("--source", Sources.tagged(), "--agent", "claude-code")
        self.assertEqual(run.code, 0, run)
        copy = os.path.join(run.home, ".claude", "skills", "refactor-pass")
        # v1.10.0 is newer than v1.9.0, though it sorts before it as text; and newer than main's tip isn't a release.
        self.assertCopy(copy, expected(), "v1.10.0")
        for name in ("README.md", "LICENSE", "tests", ".github", ".git", "install.py"):
            self.assertFalse(os.path.exists(os.path.join(copy, name)), name)
        self.assertIn("refactor-pass v1.10.0", run.out)
        where = os.path.join("~", ".claude", "skills", "refactor-pass")
        self.assertIn(where + ": installed (for Claude Code)", run.out)
        entry = record(copy)
        self.assertEqual((entry["source"], entry["ref"]), (Sources.tagged(), "v1.10.0"))
        self.assertEqual(sorted(entry["files"]), sorted(expected()))
        self.assertNoLeftovers(run, copy)

    def test_a_pinned_ref(self):
        skills = support.new_folder("skills")
        run = install("--source", Sources.tagged(), "--dir", skills, "--ref", "v1.2.0")
        self.assertEqual(run.code, 0, run)
        self.assertCopy(os.path.join(skills, "refactor-pass"), expected({"references/old.md": b"old\n"}), "v1.2.0")
        tip = support.new_folder("skills")
        main = install("--source", Sources.tagged(), "--dir", tip, "--ref", "main")
        self.assertEqual(main.code, 0, main)
        self.assertCopy(os.path.join(tip, "refactor-pass"), expected({"references/new.md": b"new\n"}), None)

    def test_no_release_yet_installs_the_default_branch_with_a_notice(self):
        skills = support.new_folder("skills")
        run = install("--source", Sources.untagged(), "--dir", skills)
        self.assertEqual(run.code, 0, run)
        self.assertIn("There's no release of %s yet" % Sources.untagged(), run.out)
        copy = os.path.join(skills, "refactor-pass")
        self.assertCopy(copy, expected({"references/new.md": b"x\n"}), None)
        self.assertEqual(record(copy)["ref"], "main")

    def test_detection(self):
        none = install("--source", Sources.tagged())
        self.assertEqual(none.code, 1, none)
        self.assertIn("No coding agent was found on this machine, so nothing was installed", none.out)
        self.assertIn("--agent claude-code", none.out)
        self.assertEqual(os.listdir(none.home), [])
        one = install("--source", Sources.tagged(), home=home_with(".claude"))
        self.assertEqual(sorted(os.listdir(os.path.join(one.home, ".claude", "skills"))), ["refactor-pass"])
        self.assertFalse(os.path.exists(os.path.join(one.home, ".agents")))
        # Codex, Gemini CLI and opencode all read ~/.agents/skills: one copy there serves them.
        shared = install("--source", Sources.tagged(), home=home_with(".codex", ".gemini", ".config/opencode"))
        self.assertEqual(shared.out.count(": installed"), 1, shared)
        self.assertIn("(for Codex, Gemini CLI, opencode)", shared.out)
        self.assertTrue(os.path.isfile(os.path.join(shared.home, ".agents", "skills", "refactor-pass", "SKILL.md")))
        # Claude Code reads only its own folder; Cursor reads both, and is told so.
        both = install("--source", Sources.tagged(), home=home_with(".claude", ".codex", ".cursor"))
        self.assertEqual(both.out.count(": installed"), 2, both)
        self.assertIn("Cursor reads more than one of these folders", both.out)

    def test_dir_and_project(self):
        named = support.new_folder("mine")
        run = install("--source", Sources.tagged(), "--dir", os.path.join(named, "refactor-pass"))
        self.assertEqual(run.code, 0, run)
        self.assertTrue(os.path.isfile(os.path.join(named, "refactor-pass", "SKILL.md")))
        project = support.Repo("project")
        project.commit("2026-01-01", "Start", {"src/app.py": support.lines(3), ".claude/settings.json": "{}\n"})
        project.done()
        found = install("--source", Sources.tagged(), "--project", cwd=os.path.join(project.path, "src"))
        self.assertEqual(found.code, 0, found)
        self.assertTrue(os.path.isfile(os.path.join(project.path, ".claude", "skills", "refactor-pass", "SKILL.md")))
        chosen = install("--source", Sources.tagged(), "--project", "--agent", "codex", cwd=project.path)
        self.assertTrue(os.path.isfile(os.path.join(project.path, ".agents", "skills", "refactor-pass", "SKILL.md")))
        self.assertEqual(chosen.code, 0, chosen)
        outside = install("--source", Sources.tagged(), "--project", "--agent", "codex")
        self.assertEqual(outside.code, 1, outside)
        self.assertIn("--project needs to run inside a git repo", outside.out)

    def test_piped_as_the_one_line_install_runs_it(self):
        run = install("--source", Sources.tagged(), "--agent", "amp", piped=True)
        self.assertEqual(run.code, 0, run)
        self.assertCopy(os.path.join(run.home, ".agents", "skills", "refactor-pass"), expected(), "v1.10.0")
        self.assertNoLeftovers(run)
        dry = install("--source", Sources.tagged(), "--agent", "amp", "--dry-run", piped=True)
        self.assertIn(": would be installed (for Amp)", dry.out)
        self.assertEqual(os.listdir(dry.home), [])

    def test_this_repo_installs_its_own_skill(self):
        if support.git(support.ROOT, "rev-parse", "--is-inside-work-tree", check=False).strip() != "true":
            self.skipTest("not a git checkout")
        skills = support.new_folder("skills")
        run = install("--source", support.ROOT, "--ref", "HEAD", "--dir", skills)
        self.assertEqual(run.code, 0, run)
        listed = support.git(support.ROOT, "ls-tree", "-r", "--name-only", "HEAD", "skills/refactor-pass").split()
        committed = dict((p[len("skills/refactor-pass/"):],
                          subprocess.run(["git", "-C", support.ROOT, "show", "HEAD:" + p], capture_output=True,
                                         env=support.environment()).stdout) for p in listed)
        copy = os.path.join(skills, "refactor-pass")
        self.assertCopy(copy, committed, None)
        if not support.WINDOWS:  # A folder as mkdir makes one, and each file's mode as git has it.
            mask = os.umask(0)
            os.umask(mask)
            self.assertEqual(stat.S_IMODE(os.stat(copy).st_mode), 0o777 & ~mask)
            modes = dict((line.split("\t")[1][len("skills/refactor-pass/"):], line.split()[0]) for line in
                         support.git(support.ROOT, "ls-tree", "-r", "HEAD", "skills/refactor-pass").splitlines())
            self.assertIn("100755", modes.values())
            for path, mode in modes.items():
                executable = bool(os.stat(os.path.join(copy, *path.split("/"))).st_mode & stat.S_IXUSR)
                self.assertEqual(executable, mode == "100755", path)


class Updates(unittest.TestCase):

    def test_update_check_and_uninstall(self):
        home = home_with(".claude", ".codex")
        skills = support.new_folder("skills")
        first = install("--source", Sources.tagged(), "--ref", "v1.9.0", home=home)
        self.assertEqual(first.code, 0, first)
        install("--source", Sources.tagged(), "--ref", "v1.2.0", "--dir", skills, home=home)
        copies = [os.path.join(home, ".claude", "skills", "refactor-pass"),
                  os.path.join(home, ".agents", "skills", "refactor-pass"), os.path.join(skills, "refactor-pass")]
        self.assertTrue(all(os.path.isfile(os.path.join(c, "references", "old.md")) for c in copies))
        before = dict((c, tree(c)) for c in copies)
        checked = install("check", "--dir", skills, home=home)
        self.assertEqual(checked.code, 0, checked)
        self.assertIn("v1.2.0 (", checked.out)
        self.assertIn("update brings v1.10.0", checked.out)
        everywhere = install("check", home=home)
        self.assertEqual(everywhere.out.count("update brings v1.10.0"), 2, everywhere)
        self.assertEqual(dict((c, tree(c)) for c in copies), before)
        # Update finds the agents' copies by itself, and the --dir one when named; v1.10.0 dropped old.md.
        updated = install("update", home=home)
        self.assertEqual(updated.code, 0, updated)
        self.assertEqual(updated.out.count(": replaced v1.9.0"), 2, updated)
        named = install("update", "--dir", skills, home=home)
        self.assertIn(": replaced v1.2.0", named.out)
        for copy in copies:
            self.assertEqual(sorted(p for p in tree(copy) if p != RECORD), sorted(expected()), copy)
            self.assertEqual(record(copy)["version"], "v1.10.0")
        again = install("update", home=home)
        self.assertEqual(again.out.count("already at v1.10.0"), 2, again)
        # Uninstall: a bytecode folder the scripts left goes too; the folders around the copy stay.
        bytecode = os.path.join(copies[0], "scripts", "__pycache__")
        os.makedirs(bytecode)
        with open(os.path.join(bytecode, "heatmap.cpython-39.pyc"), "wb") as f:
            f.write(b"x")
        removed = install("uninstall", "--agent", "claude-code", home=home)
        self.assertEqual(removed.code, 0, removed)
        self.assertFalse(os.path.exists(copies[0]))
        self.assertTrue(os.path.isdir(os.path.dirname(copies[0])))
        self.assertTrue(os.path.isdir(copies[1]))
        rest = install("uninstall", "--dir", skills, home=home)
        self.assertEqual((rest.code, os.listdir(skills)), (0, []), rest)

    def test_update_from_the_default_branch_to_the_first_release(self):
        skills = support.new_folder("skills")
        repo = support.Repo("later")
        files = dict(("skills/refactor-pass/" + p, d) for p, d in skill_files().items())
        mark = repo.commit("2026-01-01", "First", files)
        repo.done()
        install("--source", repo.path, "--dir", skills)
        self.assertIsNone(record(os.path.join(skills, "refactor-pass"))["version"])
        support.git(repo.path, "tag", "v1.0.0", repo.sha(mark))
        updated = install("update", "--dir", skills)
        self.assertEqual(updated.code, 0, updated)
        self.assertEqual(record(os.path.join(skills, "refactor-pass"))["version"], "v1.0.0")


class Refusals(unittest.TestCase):
    """Each leaves the target byte for byte as it was, and nothing behind in the temporary folder or beside it."""

    def assertLeftAlone(self, run, folder, before, says):
        self.assertEqual(run.code, 1, run)
        self.assertIn(says, run.out)
        self.assertEqual(tree(folder), before)
        Installs.assertNoLeftovers(self, run, folder)

    template = None

    def installed(self):
        """A copy of v1.9.0, as installed, in a skills folder of its own: installed once, then copied."""
        if Refusals.template is None:
            skills = support.new_folder("skills")
            run = install("--source", Sources.tagged(), "--ref", "v1.9.0", "--dir", skills)
            self.assertEqual(run.code, 0, run)
            Refusals.template = os.path.join(skills, "refactor-pass")
        skills = support.new_folder("skills")
        shutil.copytree(Refusals.template, os.path.join(skills, "refactor-pass"))
        return skills, os.path.join(skills, "refactor-pass")

    def test_a_folder_it_didnt_make(self):
        skills = support.new_folder("skills")
        copy = os.path.join(skills, "refactor-pass")
        os.makedirs(copy)
        with open(os.path.join(copy, "SKILL.md"), "w") as f:
            f.write("---\nname: refactor-pass\n---\nmine\n")
        before = tree(copy)
        for args in ([], ["--force"]):
            with self.subTest(args=args):
                run = install("--source", Sources.tagged(), "--dir", skills, *args)
                self.assertLeftAlone(run, copy, before, "a copy of a skill that this installer didn't make")
                self.assertIn("Move or delete it yourself", run.out)

    def test_a_git_clone_is_never_deleted(self):
        skills = support.new_folder("skills")
        copy = os.path.join(skills, "refactor-pass")
        support.git(skills, "init", "-q", "refactor-pass")
        with open(os.path.join(copy, RECORD), "w") as f:
            f.write('{"files": {}}\n')
        before = tree(copy)
        for command in (["install"], ["update", "--force"], ["uninstall", "--force"]):
            with self.subTest(command=command):
                run = install(*(command + ["--source", Sources.tagged(), "--dir", skills]))
                self.assertLeftAlone(run, copy, before, "is a git clone: left alone, and never deleted")
        # Found while looking in every agent's folder, it's only noted.
        home = home_with(".claude")
        support.git(os.path.join(home, ".claude"), "init", "-q", os.path.join("skills", "refactor-pass"))
        noted = install("update", home=home)
        self.assertEqual(noted.code, 0, noted)
        self.assertIn("Left alone:", noted.out)

    def test_an_edited_copy_and_one_with_files_it_didnt_install(self):
        for change in ("edit", "add"):
            with self.subTest(change=change):
                skills, copy = self.installed()
                if change == "edit":
                    with open(os.path.join(copy, "SKILL.md"), "ab") as f:
                        f.write(b"\nmy notes\n")
                else:
                    with open(os.path.join(copy, "references", "mine.md"), "w") as f:
                        f.write("mine\n")
                before = tree(copy)
                says = "edited since it was installed" if change == "edit" else "holding files it didn't install"
                for command in ("install", "update", "uninstall") if change == "edit" else ("update",):
                    run = install(command, "--source", Sources.tagged(), "--dir", skills)
                    self.assertLeftAlone(run, copy, before, says)
                forced = install("update", "--dir", skills, "--force")
                self.assertEqual(forced.code, 0, forced)
                self.assertEqual(record(copy)["version"], "v1.10.0")
                self.assertEqual(sorted(p for p in tree(copy) if p != RECORD), sorted(expected()))

    @unittest.skipIf(support.WINDOWS, "a symbolic link needs extra rights on Windows")
    def test_a_link_is_left_alone(self):
        skills, copy = self.installed()
        linked = support.new_folder("linked")
        os.symlink(copy, os.path.join(linked, "refactor-pass"))
        before = tree(copy)
        for command in ("install", "update", "uninstall"):
            run = install(command, "--source", Sources.tagged(), "--dir", linked, "--force")
            self.assertLeftAlone(run, copy, before, "is a link, to")
        self.assertTrue(os.path.islink(os.path.join(linked, "refactor-pass")))

    def test_uninstall_removes_only_what_it_installed(self):
        skills, copy = self.installed()
        with open(os.path.join(copy, "references", "mine.md"), "w") as f:
            f.write("mine\n")
        run = install("uninstall", "--dir", skills, "--force")
        self.assertEqual(run.code, 0, run)
        self.assertIn("removed, but for the files it didn't install: references/mine.md", run.out)
        self.assertEqual(tree(copy), {"references/mine.md": b"mine\n"})

    def test_a_failed_run_changes_nothing(self):
        skills, copy = self.installed()
        before = tree(copy)
        missing = install("update", "--dir", skills, "--ref", "v9.9.9")
        self.assertLeftAlone(missing, copy, before, "has no v9.9.9")
        # A ref older than the skills/ layout: fetched, refused, and the fetch removed.
        old = support.Repo("old-layout")
        old.commit("2026-01-01", "Before skills/", {"SKILL.md": "---\nname: refactor-pass\n---\n"})
        old.done()
        support.git(old.path, "tag", "v0.1.0", "main")
        stale = install("update", "--dir", skills, "--source", old.path, "--force")
        self.assertLeftAlone(stale, copy, before, "has no skills/refactor-pass/SKILL.md")


class Untrusted(unittest.TestCase):
    """A record, and a source's contents, are input someone else may have written: a project's copy is
    committed, so its .install.json is the project author's text, read by check, update and uninstall."""

    def assertQuietRefusal(self, run, says):
        self.assertIn(says, run.out)
        self.assertNotIn("Traceback", run.out)
        self.assertNotIn("Traceback", repr(run))

    def write_record(self, copy, **changes):
        entry = record(copy)
        entry.update(changes)
        with open(os.path.join(copy, RECORD), "w", encoding="utf-8") as f:
            json.dump(entry, f)

    def test_a_record_naming_a_file_outside_the_copy(self):
        for name in ("../victim.txt", "/victim.txt", "..\\victim.txt", "C:victim.txt", "a/../../victim.txt"):
            with self.subTest(name=name):
                skills, copy = Refusals.installed(self)
                victim = os.path.join(skills, "victim.txt")
                with open(victim, "wb") as f:
                    f.write(b"keep me\n")
                files = record(copy)["files"]
                files[name] = hashlib.sha256(b"keep me\n").hexdigest()
                self.write_record(copy, files=files)
                before = tree(copy)
                for command in (["uninstall"], ["uninstall", "--force"], ["update", "--force"], ["check"]):
                    run = install(*(command + ["--dir", skills]))
                    self.assertEqual(run.code, 1, run)
                    self.assertQuietRefusal(run, "can't act on (it lists a file it can't have installed")
                    self.assertEqual(read(victim), b"keep me\n")
                    self.assertEqual(tree(copy), before)

    def test_a_malformed_record_is_a_refusal(self):
        for changes in ({"files": ["SKILL.md"]}, {"files": {}}, {"files": {"SKILL.md": 5}}, {"version": 5},
                        {"commit": "abc"}, {"source": 7}, {"ref": "--upload-pack=x"}, {"skill": "other"}):
            with self.subTest(changes=changes):
                skills, copy = Refusals.installed(self)
                self.write_record(copy, **changes)
                run = install("uninstall", "--dir", skills)
                self.assertEqual(run.code, 1, run)
                self.assertQuietRefusal(run, "this installer can't act on")
                self.assertTrue(os.path.isfile(os.path.join(copy, "SKILL.md")))
        skills, copy = Refusals.installed(self)
        with open(os.path.join(copy, RECORD), "w") as f:
            f.write("{not json")
        self.assertQuietRefusal(install("check", "--dir", skills), "(it isn't JSON)")

    def test_a_source_never_reaches_git_as_an_option(self):
        pwned = os.path.join(support.new_folder("pwned"), "PWNED")
        command = "--upload-pack=touch %s;" % pwned
        project = support.Repo("project")
        project.commit("2026-01-01", "Start", {"src/app.py": "x = 1\n"})
        project.done()
        install("--source", Sources.tagged(), "--project", "--agent", "codex", cwd=project.path)
        copy = os.path.join(project.path, ".agents", "skills", "refactor-pass")
        self.write_record(copy, source=command)
        for args in (["check"], ["update"], ["update", "--force"]):
            run = install(*args, cwd=project.path)
            self.assertIn("names a source, %r, that isn't an https, ssh or git URL" % command, run.out)
            self.assertFalse(os.path.exists(pwned), args)
        for args in (["--source=" + command], ["--source", "ext::sh -c touch% " + pwned], ["--ref=" + command],
                     ["--source", "ssh://-oProxyCommand=touch%20" + pwned + "/x"], ["--source", "http://example.com/x"],
                     ["--source", Sources.tagged(), "--ref", "v1..0"]):
            run = install(*(args + ["--dir", support.new_folder("skills")]))
            self.assertEqual(run.code, 1, run)
            self.assertFalse(os.path.exists(pwned), args)
            self.assertNotIn("Traceback", repr(run))
        # A source other than this repo on GitHub is shown beside each copy it updates or checks.
        self.write_record(copy, source=Sources.tagged())
        shown = install("check", cwd=project.path)
        self.assertIn("from %s" % Sources.tagged(), shown.out)

    def test_a_link_or_a_submodule_in_the_source(self):
        secret = os.path.join(support.new_folder("secret"), "secret.txt")
        with open(secret, "w") as f:
            f.write("my secret\n")
        for name, entry in (("link", support.Link(secret)), ("submodule", support.Gitlink("1" * 40))):
            with self.subTest(entry=name):
                repo = support.Repo("bad-" + name)
                files = dict(("skills/refactor-pass/" + p, d) for p, d in skill_files().items())
                files["skills/refactor-pass/references/notes.md"] = entry
                mark = repo.commit("2026-01-01", "Release", files)
                repo.done(checkout=False)
                support.git(repo.path, "tag", "v1.0.0", repo.sha(mark))
                skills = support.new_folder("skills")
                run = install("--source", repo.path, "--dir", skills)
                self.assertEqual(run.code, 1, run)
                self.assertIn("references/notes.md in skills/refactor-pass, which isn't a plain file", run.out)
                self.assertEqual(os.listdir(skills), [])
                self.assertEqual(os.listdir(run.temp), [])

    def test_line_ends_from_a_checkout_are_not_edits(self):
        skills, copy = Refusals.installed(self)
        for path in ("SKILL.md", "scripts/heatmap.py"):
            full = os.path.join(copy, *path.split("/"))
            with open(full, "rb") as f:
                text = f.read()
            with open(full, "wb") as f:
                f.write(text.replace(b"\n", b"\r\n"))
        checked = install("check", "--dir", skills)
        self.assertEqual(checked.code, 0, checked)
        self.assertNotIn("edited", checked.out)
        updated = install("update", "--dir", skills)
        self.assertEqual(updated.code, 0, updated)
        self.assertIn("replaced v1.9.0", updated.out)


class InstalledCopy(unittest.TestCase):
    """An installed copy works: its scripts run, the page template is found, and in a project it's left out."""

    def test_the_scripts_run_from_it(self):
        project = support.Repo("project")
        project.commit("2026-01-01", "Start", {"src/app.py": support.lines(30), ".claude/settings.json": "{}\n"})
        project.commit("2026-01-02", "Grow", {"src/app.py": support.lines(40)})
        project.done()
        run = install("--source", Sources.tagged(), "--project", cwd=project.path)
        self.assertEqual(run.code, 0, run)
        copy = os.path.join(project.path, ".claude", "skills", "refactor-pass")
        files = dict((".claude/skills/refactor-pass/" + p, d) for p, d in tree(copy).items())
        project.commit("2026-01-03", "Add the skill", files)
        project.done()
        env = support.environment()
        heatmap = subprocess.run([sys.executable, os.path.join(copy, "scripts", "heatmap.py"), "-C", project.path],
                                 capture_output=True, env=env)
        out = support._text(heatmap.stdout)
        self.assertEqual(heatmap.returncode, 0, out + support._text(heatmap.stderr))
        self.assertIn("This skill's own files, in .claude/skills/refactor-pass/, are left out", out)
        self.assertNotIn(".claude/skills/refactor-pass/scripts", out)
        measure = subprocess.run([sys.executable, os.path.join(copy, "scripts", "measure.py"), "-C", project.path],
                                 capture_output=True, env=env)
        self.assertEqual(measure.returncode, 0, support._text(measure.stderr))
        self.assertIn("are left out; a scope naming that folder measures them", support._text(measure.stdout))
        page = subprocess.run([sys.executable, os.path.join(copy, "scripts", "heatmap.py"), "-C", project.path,
                               "--page", ".refactor-pass/2026-01-03.html"], capture_output=True, env=env)
        self.assertEqual(page.returncode, 0, support._text(page.stderr) + support._text(page.stdout))
        written = [n for n in os.listdir(os.path.join(project.path, ".refactor-pass")) if n.endswith(".html")]
        self.assertEqual(len(written), 1)
        checked = subprocess.run([sys.executable, os.path.join(copy, "scripts", "check_page.py"),
                                  os.path.join(project.path, ".refactor-pass", written[0])],
                                 capture_output=True, env=env)
        self.assertIn(checked.returncode, (0, 1), support._text(checked.stderr))
        self.assertNotIn("Traceback", support._text(checked.stderr))


if __name__ == "__main__":
    unittest.main()
