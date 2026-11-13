"""The scripts' test suite, standard library only.

  test_functions.py   measure.py's function finder on samples/functions/, against answers read by hand and,
                      for Python, against the ast module
  test_limits.py      the limits measure.py's help admits to, each as a test
  test_measure.py     percentiles, bands and the rest of measure.py's output
  test_heatmap.py     heatmap.py's columns, window and scopes
  test_pairs.py       files that change together, and the tests that change with several
  test_window.py      bots, reformats, asked commits and --since
  test_fixes.py       the fixes trace: which commits say they fixed a defect, read by type and by words
  test_reverts.py     the trace's reading of reverts, withdrawals and re-landings
  test_kinds.py       the whole heatmap over a repo with a file of each kind of path
  test_diffs.py       --show FILE --diffs: a file's changes in the commits given
  test_checklists.py  --checklists, --page, recorded commits, worktrees and a copy kept in a project
  test_check_page.py  check_page.py's errors and warnings, and old checklists (fixtures/)
  test_page.py        assets/page.html, read without a browser
  test_robustness.py  a short fuzz and extreme inputs, and the scripts' last line of defence
  test_documents.py   the documents against the scripts, and the code's hygiene
  test_install.py     install.py, from source repos built here: what it installs and where, which version,
                      update, check and uninstall, and every refusal leaving the target as it was
  test_tools.py       the clone the tools in tools/ share
  support.py          what they share: the scripts' folder, running them, and building git repos

Run it with python3 -B, which keeps Python from writing bytecode beside the tests and scripts. This file
stops that too, for every module imported after it, but not for itself.

tools/ holds what the default run leaves out: the comparison with real parsers on pinned public repos, the
counts of run-on functions and unreported definitions where there's no parser, the headless-Chrome check of
rendered pages, and a longer stress run.
"""

import sys

sys.dont_write_bytecode = True
