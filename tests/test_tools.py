"""The tools outside the default run: compare_parsers.py's clone, which measure_fixes.py and run_ons.py take too."""

import os
import sys
import unittest

try:
    from . import support
except ImportError:
    import support

sys.path.insert(0, os.path.join(support.HERE, "tools"))
import compare_parsers  # noqa: E402


class Pinned(object):

    def __init__(self, name, url, sha):
        self.name, self.url, self.sha = name, url, sha


class Clone(unittest.TestCase):

    def test_a_clone_too_shallow_is_fetched_again(self):
        # A depth-1 clone left in the cache by one tool isn't enough for another that wants more history.
        repo = support.Repo("pinned")
        for day in range(1, 6):
            repo.commit("2026-01-%02d" % day, "Change %d" % day, {"a.py": support.lines(day)})
        repo.done()
        sha = support.git(repo.path, "rev-parse", "HEAD").strip()
        one = Pinned("pinned", "file://" + ("/" if support.WINDOWS else "") + repo.path.replace("\\", "/"), sha)
        cache = support.new_folder("cache")
        path, how = compare_parsers.clone(one, [], cache, True)
        self.assertEqual((how, support.git(path, "rev-list", "--count", "HEAD").strip()), ("fetched", "1"))
        path, how = compare_parsers.clone(one, [], cache, True, depth=4)
        self.assertEqual(int(support.git(path, "rev-list", "--count", "HEAD").strip()), 4, how)


if __name__ == "__main__":
    unittest.main()
