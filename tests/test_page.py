"""assets/page.html, read without a browser: its data blocks, that its script reads every field check_page.py
accepts and heatmap.py writes, that each status has a label and a style, that it makes no request outside
the file, and that the examples in its comment pass check_page.py.

tools/render_pages.py renders pages in headless Chrome, outside the default run.
"""

import json
import os
import re
import unittest

try:
    from . import support
except ImportError:
    import support


def template():
    with open(support.TEMPLATE, encoding="utf-8") as f:
        return f.read()


def script(text):
    """The page's own script: the one that isn't a data block."""
    return re.search(r"<script>(.*?)</script>", text, re.S).group(1)


class Template(unittest.TestCase):

    def setUp(self):
        self.text = template()
        self.script = script(self.text)
        self.check_page = support.load("check_page")

    def test_the_data_blocks(self):
        self.assertEqual(self.text.count('<script type="application/json" id="heatmap">'), 1)
        self.assertEqual(self.text.count('<script type="application/json" id="pass">'), 1)
        self.assertLess(self.text.index('id="heatmap"'), self.text.index('id="pass"'))
        self.assertEqual(json.loads(support.block(self.text, "heatmap")), None)
        blank = json.loads(support.block(self.text, "pass"))
        self.assertEqual(list(blank), list(self.check_page.PASS))
        for key, kind in self.check_page.PASS.items():
            with self.subTest(field=key):
                self.assertEqual(blank[key], {str: "", list: []}.get(kind))

    def test_every_field_check_page_accepts_is_read(self):
        c = self.check_page
        fields = set(c.PASS) | set(c.REFACTOR) | set(c.OTHER) | set(c.COST) | set(c.EARLIER) | set(c.RESULT)
        fields |= {"from", "what", "why", "date", "text"}  # An item's optional field; left_alone's; log's.
        for field in sorted(fields):
            with self.subTest(field=field):
                self.assertRegex(self.script, r"\.%s\b" % field)

    def test_every_status_has_a_label_and_a_style(self):
        labels = re.search(r"const STATUS_LABEL = \{(.*?)\};", self.script).group(1)
        self.assertEqual(re.findall(r"(\w+):", labels), self.check_page.STATUSES)
        style = re.search(r"<style>(.*?)</style>", self.text, re.S).group(1)
        for status in self.check_page.STATUSES:
            with self.subTest(status=status):
                self.assertIn(".chip.status.%s" % status, style)
                self.assertIn('.item[data-status="%s"]' % status, style)
        kinds = re.findall(r'prefix: "(\w)", label: "([^"]+)"', self.script)
        self.assertEqual([k[0] for k in kinds], list(self.check_page.KIND_NAMES))

    def test_no_request_outside_the_file(self):
        text = self.text.lower()
        self.assertNotRegex(text, r"""\bsrc\s*=\s*["']?(?:https?:)?//""")
        self.assertNotRegex(text, r"""<link[^>]*\bhref\s*=\s*["']?(?:https?:)?//""")
        self.assertNotIn("@import", text)
        self.assertNotRegex(text, r"url\(")
        self.assertNotRegex(text, r"<script[^>]*\bsrc\s*=")
        self.assertNotRegex(text, r"\bfetch\(|xmlhttprequest|new\s+image\b")

    def test_the_comments_examples_pass_check_page(self):
        comment = self.text[self.text.index("<!-- The data."):self.text.index("-->", self.text.index("<!-- The data."))]
        examples = re.findall(r'(\{"id": "[A-Z]n".*?\})(?=\s*(?:\{"id"|L and D))', comment, re.S)
        self.assertEqual(len(examples), 2, comment)
        items = []
        for example in examples:
            example = example.replace("\u2026", "something")
            items.append(json.loads(example.replace('"Rn"', '"R1"').replace('"Fn"', '"F1"')))
        earlier = re.search(r'(\{"checklist": .*?\]\})', comment, re.S).group(1)
        earlier = json.loads(earlier.replace("\u2026", "something").replace('"Rn"', '"R1"'))
        data = {"project": "shop", "started": "2026-11-03", "base": "a1b2c3d", "updated": "2026-11-03",
                "summary": "Fine.", "checks": ["`make test`"], "earlier": earlier, "items": items, "left_alone": [],
                "log": []}
        errors, warnings, _ = self.check_page.check(support.page_with(data, heatmap={"head": "a1b2c3d"}))
        self.assertEqual((errors, warnings), ([], []))
        # Dates as the comment writes them, and an item carried over.
        self.assertIn('"from": "2026-11-03"', comment)


class AgainstTheHeatmap(unittest.TestCase):
    """The fields the page's script reads from the heatmap block are ones heatmap.py writes."""

    @classmethod
    def setUpClass(cls):
        repo = support.Repo("fields")
        sizes = {}
        day = 1
        changes = [(["src/a.py", "src/b.py", "src/c.py", "tests/test_x.py"], 5), (["src/d.py", "src/e.py"], 5)]
        for paths, times in changes:
            for _ in range(times):
                files = {}
                for path in paths:
                    sizes[path] = sizes.get(path, 0) + 1
                    files[path] = support.lines(sizes[path])
                repo.commit("2026-01-%02d" % day, "Change", files)
                day += 1
        repo.done()
        page = os.path.join(support.new_folder("page"), "p.html")
        result = support.run("heatmap.py", "-C", repo.path, "--page", page)
        assert result.code == 0, result
        with open(page, encoding="utf-8") as f:
            cls.heat = json.loads(support.block(f.read(), "heatmap"))
        cls.script = script(template())

    def test_the_heatmap_has_what_the_page_reads(self):
        heat = self.heat
        self.assertTrue(heat["groups"] and heat["pairs"] and heat["tests"] and heat["files"])
        reads = {
            "heat": (heat, ["window", "scope", "head", "files", "total_files", "groups", "pairs", "tests", "options"]),
            "w": (heat["window"], ["bots", "excluded_checklists", "excluded_asked", "excluded_ignore_revs",
                                   "excluded_bots", "since", "commits", "oldest", "newest", "newer_half_from",
                                   "tests_aside", "shallow", "too_big_for_pairs"]),
            "f": (heat["files"][0], ["path", "size", "commits", "recent", "last", "growth"]),
            "p": (heat["pairs"][0], ["a", "b", "shared", "degree", "last"]),
            "group": (heat["groups"][0], ["files", "pairs", "shared", "degree", "last"]),
            "t": (heat["tests"][0], ["test", "files"]),
        }
        for name, (value, keys) in reads.items():
            for key in keys:
                with self.subTest(read="%s.%s" % (name, key)):
                    self.assertIn(key, value)
                    self.assertRegex(self.script, r"\.%s\b" % key)
        self.assertIn("max_files", heat["options"])
        self.assertIn("heat.options.max_files", self.script)
        self.assertEqual(sorted(heat["tests"][0]["files"][0]), ["path", "shared"])
        self.assertEqual(sorted(heat["window"]["oldest"]), ["date", "sha", "subject"])


if __name__ == "__main__":
    unittest.main()
