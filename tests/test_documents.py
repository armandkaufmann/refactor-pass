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
            cls.help[script] = support.run(script, "--help")
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
        for result in list(self.help.values()) + list(self.tool_help.values()):
            known |= usage_options(result.out)
        documents = [(path, read(path)) for path in markdown_files()] + [(support.TEMPLATE, page_text())]
        for path, text in documents:
            with self.subTest(document=os.path.basename(path)):
                self.assertEqual(set(OPTION.findall(text)) - NOT_OURS - known, set())

    def test_the_heatmaps_columns_are_its_helps(self):
        doc = ast.get_docstring(ast.parse(read(os.path.join(support.SCRIPTS, "heatmap.py"))))
        columns = re.findall(r"(?m)^  (\w+)  ", doc)
        self.assertEqual(columns, ["commits", "recent", "last", "churn", "rel", "size", "growth"])
        source = read(os.path.join(support.SCRIPTS, "heatmap.py"))
        self.assertIn('("commits", "recent", "last", "churn", "rel", "size", "growth")', source)
        doc = ast.get_docstring(ast.parse(read(os.path.join(support.SCRIPTS, "measure.py"))))
        self.assertEqual(re.findall(r"(?m)^  (\w+)  ", doc), ["lines", "band", "funcs", "longest", "long", "deepest"])


class Skill(unittest.TestCase):

    def test_frontmatter(self):
        text = read(os.path.join(SKILL, "SKILL.md"))
        self.assertTrue(text.startswith("---\n"))
        front = text[4:text.index("\n---\n", 4)]
        fields = dict(line.split(": ", 1) for line in front.split("\n"))
        self.assertEqual(sorted(fields), ["description", "name"])
        self.assertRegex(fields["name"], r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(fields["name"]), 64)
        self.assertEqual(fields["name"], "refactor-pass")
        self.assertTrue(fields["description"].strip())
        self.assertLessEqual(len(fields["description"]), 1024)
        self.assertNotRegex(fields["description"], r"[<>]")

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

    def test_the_words_skill_md_quotes_are_the_scripts(self):
        text = read(os.path.join(SKILL, "SKILL.md"))
        vocabulary = set()
        check_page = support.load("check_page")
        for shape in (check_page.PASS, check_page.REFACTOR, check_page.OTHER, check_page.COST, check_page.EARLIER,
                      check_page.RESULT):
            vocabulary |= set(shape)
        vocabulary |= set(check_page.STATUSES) | {"from", "what", "why", "date", "text"}
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

    def test_documents_agents_load(self):
        names = {"unittest", "test suite", "REFACTOR_PASS_SCRIPTS", "tests/", "the skill's tests",
                 "this skill's tests", "the suite"}
        for folder, dirs, files in os.walk(support.HERE):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            names.update(n for n in files if n.endswith(".py") and n != "__init__.py")
        for path in loaded_by_agents():
            text = read(path)
            for name in sorted(names):
                with self.subTest(document=os.path.basename(path), name=name):
                    self.assertNotIn(name, text)

    def test_no_instructions_for_agents_in_the_suite(self):
        for folder, dirs, files in os.walk(support.HERE):
            for name in files + dirs:
                with self.subTest(name=os.path.join(folder, name)):
                    self.assertNotIn(name.upper(), ("SKILL.MD", "AGENTS.MD", "CLAUDE.MD", "README.MD", "GEMINI.MD"))

    def test_the_suite_stays_small(self):
        total, biggest = 0, (0, "")
        for folder, dirs, files in os.walk(support.HERE):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                size = os.path.getsize(os.path.join(folder, name))
                total += size
                biggest = max(biggest, (size, name))
        self.assertLess(total, 400 * 1024)
        self.assertLess(biggest[0], 60 * 1024, biggest[1])

    def test_a_copy_by_hand_takes_only_the_skill(self):
        readme = read(os.path.join(ROOT, "README.md"))
        install = readme[readme.index("## Install"):readme.index("## Use")]
        copies = re.findall(r"(?m)^cp -R (\S+) (\S+)$", install)
        self.assertTrue(copies)
        for source, target in copies:
            self.assertTrue(source.endswith("/skills/refactor-pass"), source)


class Hygiene(unittest.TestCase):

    def python_files(self):
        files = [os.path.join(support.SCRIPTS, n) for n in sorted(os.listdir(support.SCRIPTS)) if n.endswith(".py")]
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
