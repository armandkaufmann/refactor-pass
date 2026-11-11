# refactor-pass

A Claude Code skill that finds what in a git repo needs refactoring, and
what doesn't.

Refactoring used to start with a feeling. Code was hard to work on, and the
same feeling told you what to leave alone: ugly code you never touched
never hurt. An agent writing code doesn't feel any of that, and neither
does a developer who mostly reads what the agent wrote, so smells pile up
unnoticed, and when an agent is asked to refactor it tidies whatever looks
untidy. This skill gives that feeling back as three things you can measure:
where changes keep landing, what makes those files hard to change, and what
the next change would cost. It says what to leave alone as well as what to
fix.

## What you get

- **A heatmap** of git history: the files that are both busy and big, how
  much of each was rewritten or grew, the files that keep changing
  together, and the tests tied to other files' internals.
- **The smells**, from a catalogue of the established code smells, each
  with what to count, when it isn't a smell, and its playbook of named
  refactorings.
- **A walkthrough** of the next likely change: every file it would touch
  today, and after the refactor proposed.
- **A ranked checklist**, written as an HTML page in `.refactor-pass/` in
  the repo (kept out of commits through git's local exclude file). It holds
  refactors, small fixes, items for later, decisions for you, and what was
  left alone and why. Claude works through it one item at a time, when you
  name an item, and changes no code until you do.
- **Later passes** build on the last checklist and check its predictions
  against what happened: for each finished refactor, what the next change
  of the kind it eased actually touched.

## Install

For all your projects:

```bash
git clone https://github.com/armandkaufmann/refactor-pass ~/.claude/skills/refactor-pass
```

Or for one project, clone it into that project's
`.claude/skills/refactor-pass`.

It needs git (2.31 or later) and Python 3. The scripts use the standard
library only; they were tested on Python 3.9.

## Use

Ask Claude Code things like:

- "Do a refactor pass."
- "We've made a lot of changes, anything to refactor?"
- "Before we start on the next feature, anything to fix first?"
- "What's the worst part of the codebase?"
- "Should we refactor X?" or "Is this class doing too much?"
- "What's next on the list?" or "Start R4", to carry on with a checklist.

Or invoke it directly with `/refactor-pass`.

## The scripts on their own

Each runs with `--help` for its options.

- `scripts/heatmap.py`: where a repo's changes keep landing, from git
  history.
- `scripts/measure.py`: how long a codebase's files and functions are,
  against the codebase itself.
- `scripts/check_page.py`: checks a checklist page after an edit.

`scripts/scoping.py` is the module the first two share, for which files
count and which are tests.

## What's in the repo

- `SKILL.md`: the skill itself, the steps Claude follows.
- `references/smells.md`: the catalogue of smells and their playbooks.
- `references/review-brief.md`: the brief for reviewing one area of code.
- `references/sources.md`: the books, studies and articles drawn on.
- `scripts/`: the scripts above.
- `assets/page.html`: the template for the checklist page.

## Where the ideas come from

The smells and refactorings come from Fowler and Beck's catalogue in
*Refactoring* and the authors who added to it; the measures and the
priorities come from empirical studies of smells, churn and refactoring.
[references/sources.md](references/sources.md) lists them all.

## Licence

It's under the MIT licence ([LICENSE](LICENSE)), so you're free to use,
change and share it.
