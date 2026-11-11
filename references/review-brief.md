# Brief for a review

Each review covers one area of the code: a few hot files, or the layer they
belong to. Fill in the angle brackets and leave out what doesn't apply. A
sub-agent knows nothing but this brief, so it has to carry everything: what
the owner values, what's read-only, the project's intended design, the
evidence from the heatmap, the catalogue to judge by, and the shape of the
report. If a sub-agent can't read files outside the repo, paste in the
entries of smells.md it needs. Reviewing an area yourself, use it as the
checklist.

---

You are reviewing <the project: language, framework, what it is> at <absolute
repo path>, for a refactor pass. The owner values <their words: maintainable,
scalable, SOLID...>. They want to know where refactoring would make future
work easier, and just as much, what looks bad but isn't worth touching.

This is READ-ONLY. Don't edit, create or delete any file in the repo, and
don't run the app, its tests or its scripts. Only read files and search them
(read-only commands such as searches, line counts, git log and git show are
fine, and so is `python3 <absolute path to this skill's scripts/measure.py>
-C <repo> <scope> --show <file>`, which lists a file's functions with their
first and last lines, lengths, nesting and bands;
`git log -L <first>,<last>:<file>` then lists the commits that changed one
of them).

**Judge by the catalogue.** Read <absolute path to this skill's
references/smells.md> first. Each smell there has five parts: what it felt
like to work on, what to count, when it is *not* a smell, its playbook of
named refactorings, and its priority. Use the established names, count
before you claim, and check every finding against its "Not a smell when"
before you report it. The smells in its "Fix in passing" table are never
findings of their own.

**The intended design.** <Where the intended design is written down, such as
an architecture doc's principles and the contributor or agent instructions;
the few rules that matter most, in a line each.> Read those too, and judge
the code against them.

**Why your area.** <The heatmap's rows for these files: commits in the
window and in its newer half, the date of the last, churn, relative churn,
size and growth; the pairs and groups that change together, and any test
listed as changing with several of them; and the changes coming next, from
the user, the project's plans or the commonest kinds in the commit
messages.> A file that
nearly every change edits, or two files that always change together, is
where the next change will hurt. Find out why changes keep landing here.

**The size of the codebase.** <measure.py's percentiles for this language:
file and function length at the 70th, 80th and 90th, and any note that
they lean on one file or function.> Call something big when it reaches the
80th and is past the floor, over 45 code lines for a function and 220 for a
file; worth a closer look at the 70th. measure.py's bands apply that rule.
Where the percentiles lean on one file or function, its bands for that
language are smells.md's reference points instead: `>75` (a function) or
`>440` (a file) is big, `>45` or `>220` worth a closer look. Lengths are
code lines, without blank lines, comment-only lines or Python's docstrings.

**Your scope:** <the files or directories>.

**For each finding, report:**
1. The smells, by name, and the missing idea behind them if they cluster
   (an unnamed state, a kind's definition, a single source for a setting).
2. The evidence: files, line numbers, and the counts.
3. The cost: walk through <the coming change, or the two or three commonest
   kinds> and say how many files, places and copies it touches today, and
   how many after the refactor.
4. The playbook steps you'd take, by their names (Extract Function, Replace
   Conditional with Polymorphism…).
5. Size (S, M or L), risk (Low, Medium or High), and how it could be
   checked to change nothing (<the project's checks: tests, snapshots, a
   simulation...>). Say which tests reach the code; if none do, the first
   step is pinning tests.

Rank the findings by payoff (how much they'd ease future work) against risk.
Then add a short list of what you looked at and judged fine or not worth
touching, and why. Bugs you notice go in their own short list; don't fix
them. Stay under about 1,500 words, specific and evidence-based, with no
generic advice.
