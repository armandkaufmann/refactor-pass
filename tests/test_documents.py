"""The skill's documents against its scripts: every option they name exists, every relative link and anchor
resolves, SKILL.md's frontmatter is valid, the words SKILL.md quotes from the scripts' output are the
scripts' words, and nothing an agent loads mentions this suite.

Also the scripts' own hygiene: each one's --help runs and names only options it has, each parses as Python
3.7, no line is over 120 characters, and the suite stays small and holds nothing that looks like
instructions to an agent.
"""

import ast
import os
import re
import subprocess
import sys
import unittest

try:
    from . import support
except ImportError:
    import support

ROOT = support.ROOT
SKILL = support.SKILL
SCRIPTS = ["heatmap.py", "measure.py", "check_page.py"]
TOOLS = os.path.join(support.HERE, "tools")
# Options of other commands that the documents quote: git's.
NOT_OURS = {"--date", "--depth", "--format", "--init", "--is-shallow-repository", "--stat", "--unshallow"}
OPTION = re.compile(r"(?<![\w-])--[a-z][a-z0-9-]*")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def markdown_files():
    names = [os.path.join(SKILL, "SKILL.md"), os.path.join(ROOT, "README.md")]
    references = os.path.join(SKILL, "references")
    names += [os.path.join(references, n) for n in sorted(os.listdir(references)) if n.endswith(".md")]
    return names


def loaded_by_agents():
    """What an agent can load: SKILL.md and the files it points to."""
    references = os.path.join(SKILL, "references")
    return ([os.path.join(SKILL, "SKILL.md"), support.TEMPLATE] +
            [os.path.join(references, n) for n in sorted(os.listdir(references))])


def page_text():
    """page.html without its style sheet, whose custom properties look like options."""
    return re.sub(r"var\(--[\w-]+\)", "", re.sub(r"<style>.*?</style>", "", read(support.TEMPLATE), flags=re.S))


def usage_options(help_text):
    usage = help_text.split("\n\n", 1)[0]
    return set(OPTION.findall(usage)) | {"--help"}


def slug(heading):
    """A heading's anchor, as GitHub makes it."""
    text = re.sub(r"[^\w\- ]", "", heading.strip().lower())
    return text.replace(" ", "-")


def anchors(path):
    found, seen = set(), {}
    in_code = False
    for line in read(path).split("\n"):
        if line.startswith("```"):
            in_code = not in_code
        match = re.match(r"(#{1,6})\s+(.*)", line)
        if match and not in_code:
            base = slug(match.group(2))
            name = base if base not in seen else "%s-%d" % (base, seen[base])
            seen[base] = seen.get(base, 0) + 1
            found.add(name)
    return found


class Help(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.help = {}
        for script in SCRIPTS:
            cls.help[script] = support.run(script, "--help", env={"COLUMNS": "80"})  # argparse wraps to it.
        installer = subprocess.run([sys.executable, os.path.join(ROOT, "install.py"), "--help"], capture_output=True,
                                   env=support.environment())
        cls.installer_help = support.Result(installer.returncode, support._text(installer.stdout),
                                            support._text(installer.stderr))
        cls.tool_help = {}
        for name in sorted(os.listdir(TOOLS)):
            if name.endswith(".py"):
                cls.tool_help[name] = support.run_python(
                    "import runpy, sys\nsys.argv = [sys.argv[1], '--help']\nrunpy.run_path(sys.argv[0], "
                    "run_name='__main__')", os.path.join(TOOLS, name))

    def test_help_runs(self):
        for script, result in sorted(self.help.items()):
            with self.subTest(script=script):
                self.assertEqual(result.code, 0, result)
                self.assertTrue(result.out.startswith("usage: %s" % script), result.out[:200])
                first = ast.get_docstring(ast.parse(read(os.path.join(support.SCRIPTS, script)))).split("\n")[0]
                self.assertIn(first, result.out)
        for tool, result in sorted(self.tool_help.items()):
            with self.subTest(tool=tool):
                self.assertEqual(result.code, 0, result)
                self.assertIn("usage:", result.out)
        self.assertEqual(self.installer_help.code, 0, self.installer_help)
        self.assertTrue(self.installer_help.out.startswith("usage: install.py"), self.installer_help.out[:200])

    def test_the_heatmaps_help_stays_short(self):
        # An agent pays for it each time it reads it: it keeps what a reader of the output needs, and the account
        # of how the fixes trace was measured is in the references. v1.0.1's was 12,675 characters.
        self.assertLess(len(self.help["heatmap.py"].out), 16000)

    def test_docstrings_name_only_real_options(self):
        # A script's docstring may name another script's option, as check_page.py names heatmap.py --page.
        known = set()
        for result in self.help.values():
            known |= usage_options(result.out)
        for script in SCRIPTS:
            with self.subTest(script=script):
                doc = ast.get_docstring(ast.parse(read(os.path.join(support.SCRIPTS, script))))
                self.assertEqual(set(OPTION.findall(doc)) - NOT_OURS - known, set())
        doc = ast.get_docstring(ast.parse(read(os.path.join(support.SCRIPTS, "heatmap.py"))))
        self.assertEqual(set(OPTION.findall(doc)) - NOT_OURS - usage_options(self.help["heatmap.py"].out),
                         set())

    def test_documents_name_only_real_options(self):
        known = set()
        for result in list(self.help.values()) + list(self.tool_help.values()) + [self.installer_help]:
            known |= usage_options(result.out)
        documents = [(path, read(path)) for path in markdown_files()] + [(support.TEMPLATE, page_text())]
        for path, text in documents:
            with self.subTest(document=os.path.basename(path)):
                self.assertEqual(set(OPTION.findall(text)) - NOT_OURS - known, set())

    def test_the_heatmaps_columns_are_its_helps(self):
        doc = ast.get_docstring(ast.parse(read(os.path.join(support.SCRIPTS, "heatmap.py"))))
        columns = re.findall(r"(?m)^  (\w+)  ", doc)
        # The table's columns, then the ways a commit reads as a fix, the fixes table's columns after its counts.
        self.assertEqual(columns, ["commits", "recent", "last", "churn", "rel", "size", "growth", "revert", "type",
                                   "words"])
        source = read(os.path.join(support.SCRIPTS, "heatmap.py"))
        self.assertIn('("commits", "recent", "last", "churn", "rel", "size", "growth")', source)
        self.assertIn('("fixes", "recent", "revert", "type", "words")', source)
        doc = ast.get_docstring(ast.parse(read(os.path.join(support.SCRIPTS, "measure.py"))))
        self.assertEqual(re.findall(r"(?m)^  (\w+)  ", doc), ["lines", "band", "funcs", "longest", "long", "deepest"])


class Skill(unittest.TestCase):

    def test_frontmatter(self):
        text = read(os.path.join(SKILL, "SKILL.md"))
        self.assertTrue(text.startswith("---\n"))
        front = text[4:text.index("\n---\n", 4)]
        fields = dict(line.split(": ", 1) for line in front.split("\n"))
        self.assertEqual(sorted(fields), ["description", "license", "name"])
        self.assertEqual(fields["license"], "MIT")
        self.assertRegex(fields["name"], r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(fields["name"]), 64)
        self.assertEqual(fields["name"], "refactor-pass")
        self.assertTrue(fields["description"].strip())
        self.assertLessEqual(len(fields["description"]), 1024)
        self.assertNotRegex(fields["description"], r"[<>]")

    def test_each_script_names_its_licence(self):
        copyright_line = next(line for line in read(os.path.join(ROOT, "LICENSE")).split("\n") if "Copyright" in line)
        notice = "# %s. MIT License: https://github.com/armandkaufmann/refactor-pass" % copyright_line
        for name in sorted(os.listdir(support.SCRIPTS)):
            if name.endswith(".py"):
                with self.subTest(script=name):
                    head = read(os.path.join(support.SCRIPTS, name)).split("\n")[:2]
                    self.assertIn(notice, head)

    def test_links_and_anchors(self):
        for path in markdown_files():
            text = re.sub(r"```.*?```", "", read(path), flags=re.S)
            for target in re.findall(r"\]\(([^)\s]+)\)", text):
                if re.match(r"[a-z]+:", target):
                    continue
                with self.subTest(document=os.path.basename(path), link=target):
                    file_part, _, anchor = target.partition("#")
                    linked = os.path.normpath(os.path.join(os.path.dirname(path), file_part)) if file_part else path
                    self.assertTrue(os.path.exists(linked), linked)
                    if anchor:
                        self.assertIn(anchor, anchors(linked))

    def test_step_4_shows_with_step_1s_window_scope_and_options(self):
        # --show's marks count a commit's files by the scope and --max-files: the same as step 1's, or they differ.
        text = " ".join(read(os.path.join(SKILL, "SKILL.md")).split())
        self.assertIn("`heatmap.py -C <repo> --show <file> --messages`, with step 1's window, scope and options,", text)
        help_text = " ".join(support.run("heatmap.py", "--help").out.split())
        self.assertIn("the heatmap's window, scope and options", help_text)

    def test_skill_md_acts_on_the_header_saying_the_work_has_gone_quiet(self):
        text = " ".join(read(os.path.join(SKILL, "SKILL.md")).split())
        self.assertIn("Where it says the work has gone quiet, nothing has landed there for over three months", text)
        self.assertIn("Where it says this checkout is behind its upstream, or that its history has gone quiet while "
                      "another ref's work goes on, tell the user what it says. Stop and ask", text)
        script = read(os.path.join(support.SCRIPTS, "heatmap.py"))
        for said in ("the work it counts%s has gone quiet.", "This checkout is behind %s by",
                     "This checkout's history has gone quiet%s, but %s's newest commit"):
            self.assertIn(said, script)

    def test_skill_md_accounts_for_the_newest_work(self):
        text = " ".join(read(os.path.join(SKILL, "SKILL.md")).split())
        self.assertIn("Every area on the heatmap's newest-work list is in an item or here", text)
        self.assertIn('"Newest work outside the table: files past its top', read(os.path.join(support.SCRIPTS,
                                                                                              "heatmap.py")))

    def test_the_words_skill_md_quotes_are_the_scripts(self):
        text = read(os.path.join(SKILL, "SKILL.md"))
        vocabulary = set()
        check_page = support.load("check_page")
        for shape in (check_page.PASS, check_page.REFACTOR, check_page.OTHER, check_page.COST, check_page.EARLIER,
                      check_page.RESULT, check_page.FIXES):
            vocabulary |= set(shape)
        vocabulary |= set(check_page.STATUSES) | {"from", "fixes", "what", "why", "date", "text"}
        vocabulary |= {"commits", "recent", "last", "churn", "rel", "size", "growth"}  # The heatmap's columns.
        others = {"heatmap", "pass", "null", "app", "py", "python", "python3"}  # Block names, a scope, commands.
        for word in sorted(set(re.findall(r"`([a-z_0-9]+)`", text))):
            with self.subTest(word=word):
                self.assertIn(word, vocabulary | others)
        measure_help = support.run("measure.py", "--help").out
        for band in sorted(set(re.findall(r"`(>\d+)`", text))):
            with self.subTest(band=band):
                self.assertIn(band, measure_help)
        self.assertTrue(re.search(r"listed together as one\s+area", text))
        self.assertIn("One area: these %d groups overlap", read(os.path.join(support.SCRIPTS, "heatmap.py")))


class NothingAboutTheSuite(unittest.TestCase):
    """What agents load never mentions this suite, and the suite holds nothing an agent would take for
    instructions."""

    def names(self):
        names = {"unittest", "test suite", "REFACTOR_PASS_SCRIPTS", "tests/", "the skill's tests",
                 "this skill's tests", "the suite", "install.py", ".install.json"}
        for folder, dirs, files in os.walk(support.HERE):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            names.update(n for n in files if n.endswith(".py") and n != "__init__.py")
        return names

    def test_documents_agents_load(self):
        names = self.names()
        for path in loaded_by_agents():
            text = read(path)
            for name in sorted(names):
                with self.subTest(document=os.path.basename(path), name=name):
                    self.assertNotIn(name, text)

    def test_the_scripts(self):
        # An installed copy has the skill alone: a script names nothing of the suite, in a comment either. It
        # can name the record an installed copy holds, which scoping.py looks for.
        names = self.names() - {".install.json"}
        for name in sorted(os.listdir(support.SCRIPTS)):
            if name.endswith(".py"):
                text = read(os.path.join(support.SCRIPTS, name))
                for found in sorted(n for n in names if n in text):
                    with self.subTest(script=name, name=found):
                        self.fail("%s names %s" % (name, found))

    def test_no_instructions_for_agents_in_the_suite(self):
        for folder, dirs, files in os.walk(support.HERE):
            for name in files + dirs:
                with self.subTest(name=os.path.join(folder, name)):
                    self.assertNotIn(name.upper(), ("SKILL.MD", "AGENTS.MD", "CLAUDE.MD", "README.MD", "GEMINI.MD"))

    def test_the_suite_stays_small(self):
        # Its size as git keeps it: a checkout with core.autocrlf (Git for Windows's default) writes each line's
        # end as CRLF, which isn't in the blob.
        total, biggest = 0, (0, "")
        for folder, dirs, files in os.walk(support.HERE):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                with open(os.path.join(folder, name), "rb") as f:
                    size = len(f.read().replace(b"\r\n", b"\n"))
                total += size
                biggest = max(biggest, (size, name))
        self.assertLess(total, 600000)
        self.assertLess(biggest[0], 60 * 1024, biggest[1])

    def test_a_copy_by_hand_takes_only_the_skill(self):
        readme = read(os.path.join(ROOT, "README.md"))
        install = readme[readme.index("## Install"):readme.index("## Use")]
        copies = re.findall(r"(?m)^cp -R (\S+) (\S+)$", install)
        self.assertTrue(copies)
        for source, target in copies:
            self.assertTrue(source.endswith("/skills/refactor-pass"), source)


class Install(unittest.TestCase):
    """The README's install part against install.py: the one-line installs, and the table of agents."""

    def setUp(self):
        self.readme = read(os.path.join(ROOT, "README.md"))
        self.install = self.readme[self.readme.index("## Install"):self.readme.index("## Use")]

    def test_the_one_line_installs(self):
        url = "https://raw.githubusercontent.com/armandkaufmann/refactor-pass/main/install.py"
        self.assertIn("curl -fsSL %s | python3 -" % url, self.install)
        self.assertIn("irm %s | python -" % url, self.install)

    def test_the_installer_is_ascii(self):
        # Piped, it passes through the shell as text: Windows PowerShell 5.1 pipes ASCII to a program by default.
        with open(os.path.join(ROOT, "install.py"), "rb") as f:
            f.read().decode("ascii")

    def test_the_table_of_agents_is_the_installers(self):
        import runpy
        agents = runpy.run_path(os.path.join(ROOT, "install.py"))["AGENTS"]
        rows = [line.split("|")[1:-1] for line in self.install.split("\n") if line.startswith("| [")]
        table = dict((re.search(r"`([\w-]+)`", row[1]).group(1),
                      (re.findall(r"`([^`]+)`", row[2])[0], sorted(re.findall(r"`([^`]+)`", row[3])),
                       sorted(re.findall(r"`([^`]+)`", row[4])))) for row in rows)
        self.assertEqual(table, dict((name, ("~/" + found, sorted("~/" + f for f in user), sorted(project)))
                                     for name, _, found, user, project in agents))


class Hygiene(unittest.TestCase):

    def python_files(self):
        files = [os.path.join(support.SCRIPTS, n) for n in sorted(os.listdir(support.SCRIPTS)) if n.endswith(".py")]
        files.append(os.path.join(ROOT, "install.py"))
        for folder, dirs, names in os.walk(support.HERE):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            files += [os.path.join(folder, n) for n in sorted(names) if n.endswith(".py")]
        return files

    def test_python_3_7(self):
        for path in self.python_files():
            with self.subTest(file=os.path.relpath(path, ROOT)):
                source = read(path)
                if sys.version_info >= (3, 8):
                    ast.parse(source, filename=path, feature_version=(3, 7))
                else:
                    ast.parse(source, filename=path)

    def test_line_length(self):
        for path in self.python_files():
            if os.sep + "samples" + os.sep in path:
                continue
            with self.subTest(file=os.path.relpath(path, ROOT)):
                long_lines = [n for n, line in enumerate(read(path).split("\n"), 1) if len(line) > 120]
                self.assertEqual(long_lines, [])


if __name__ == "__main__":
    unittest.main()
