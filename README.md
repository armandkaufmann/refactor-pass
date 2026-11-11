# refactor-pass

A skill for coding agents that finds what in a git repo needs refactoring,
and what doesn't. It's in the open [Agent Skills](https://agentskills.io)
format, so it works in any agent that loads skills, and nothing in it
depends on one agent or one model.

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
  together and when they last did, and the tests that change with several
  other files, as leads to check. Housekeeping bots' commits are left out;
  coding agents' commits count.
- **The smells**, from a catalogue of the established code smells, each
  with what to count, when it isn't a smell, and its playbook of named
  refactorings.
- **A walkthrough** of the next likely change: every file it would touch
  today, and after the refactor proposed.
- **A ranked checklist**, written as an HTML page in `.refactor-pass/` in
  the repo (kept out of commits by a `.gitignore` inside that folder, so
  your own `.gitignore` is left alone). It holds
  refactors, small fixes, items for later, decisions for you, and what was
  left alone and why. Your agent works through it one item at a time, when
  you name an item, and changes no code until you do.
- **Later passes** build on the last checklist and check its predictions
  against what happened: for each finished refactor, what the next change
  of the kind it eased actually touched.

## Install

It's a folder with a `SKILL.md` in it, so installing it means cloning it
where your agent looks for skills. For all your projects, with Codex,
Cursor, Gemini CLI, GitHub Copilot, opencode or Amp, which all look in
`~/.agents/skills`:

```bash
git clone https://github.com/armandkaufmann/refactor-pass ~/.agents/skills/refactor-pass
```

With Claude Code, which looks in its own folder:

```bash
git clone https://github.com/armandkaufmann/refactor-pass ~/.claude/skills/refactor-pass
```

For one project, so that everyone who clones it has the skill, commit a
copy of it in the project's `.agents/skills/refactor-pass`, or
`.claude/skills/refactor-pass` for Claude Code. A plain clone there won't
do: git records a repo inside a repo as a pointer, and the project's clones
get an empty folder. So clone it, then delete the `.git` folder the clone
made, and the `tests` folder, which the skill doesn't need:

```bash
git clone --depth 1 https://github.com/armandkaufmann/refactor-pass .agents/skills/refactor-pass
rm -rf .agents/skills/refactor-pass/.git .agents/skills/refactor-pass/tests
```

In PowerShell, the second line is
`Remove-Item -Recurse -Force .agents/skills/refactor-pass/.git, .agents/skills/refactor-pass/tests`.

To update it, delete the folder and do the same again. A git submodule
would keep the link to this repo, but a clone, and the fresh worktree many
agents work in, starts with the folder empty until someone runs
`git submodule update --init`, so a copy is the safer choice. The scripts
leave the copy's own files out of what they count.

With any other agent, clone it anywhere and ask the agent to read
`SKILL.md` and follow it ("Read ~/refactor-pass/SKILL.md and do a refactor
pass"); point it there again when you carry on in a new session.

It needs git (2.15 or later, for `git rev-parse --is-shallow-repository`)
and Python 3.7 or later, with the standard library only. The scripts were
tested with Python 3.9 and 3.14 on macOS; they're written to work on
Windows too, where the command may be `python` or `py` rather than
`python3`, but haven't been tested there.

## Use

Ask your agent things like:

- "Do a refactor pass."
- "We've made a lot of changes, anything to refactor?"
- "Before we start on the next feature, anything to fix first?"
- "What's the worst part of the codebase?"
- "Should we refactor X?" or "Is this class doing too much?"
- "What's next on the list?" or "Start R4", to carry on with a checklist.

Or call it by name: `/refactor-pass` in Claude Code, Cursor or Copilot CLI,
`$refactor-pass` in Codex, `@refactor-pass` in opencode.

## The scripts on their own

They need no agent, only Python and git, and each runs with `--help` for
its options:

```bash
python3 scripts/heatmap.py -C ~/code/my-app src tests
```

- `scripts/heatmap.py`: where a repo's changes keep landing, from git
  history; with `--checklists`, where the checklists are and the name a new
  one takes.
- `scripts/measure.py`: how long a codebase's files and functions are,
  against the codebase itself. It finds functions in Python, JavaScript,
  TypeScript, Vue, Svelte, PHP, Go, Ruby, Java, C#, C, C++, Kotlin, Swift,
  Rust and GDScript; other files get their lines only.
- `scripts/check_page.py`: checks a checklist page after an edit.

`scripts/scoping.py` is the module the first two share, for which files
count and which are tests.

## What's in the repo

- `SKILL.md`: the skill itself, the steps the agent follows.
- `references/smells.md`: the catalogue of smells and their playbooks.
- `references/review-brief.md`: the brief for reviewing one area of code.
- `references/sources.md`: the books, studies and articles drawn on.
- `scripts/`: the scripts above.
- `assets/page.html`: the template for the checklist page.
- `tests/`: the scripts' tests, for contributors (see [Tests](#tests)).

## Tests

For contributors; an installed copy doesn't need them. The suite in
`tests/` uses Python's standard library and git, builds the small repos it
reads in a temporary folder, and runs in well under a minute. `-B` keeps
Python from writing bytecode into the skill's folder:

```bash
python3 -B -m unittest discover -s tests -t .
```

Run it from the repo's top, or from anywhere with both paths:
`-s <repo>/tests -t <repo>`. To test another copy of the scripts, such as
an older commit's, set `REFACTOR_PASS_SCRIPTS` to its `scripts/` folder.

Outside that run, `tests/tools/` holds four checks to run by hand:

- `compare_parsers.py` compares the functions `measure.py` finds with
  real parsers' (Python's `ast`, TypeScript's compiler, PHP's tokenizer,
  Go's parser, Ruby's own, `swiftc` and `clang`) on 40 public repos pinned
  to exact commits, and fails where one falls below its recorded floors.
  It fetches each at its commit, or uses clones on disk (`--repos-dir`),
  and skips a language whose parser isn't installed.
- `run_ons.py` checks Kotlin, C#, Rust, Java and GDScript, which have no
  parser to compare with here, on 15 pinned repos: it counts the functions
  that run on past their end, and the definitions a looser rule finds that
  `measure.py` doesn't, against recorded ceilings.
- `render_pages.py` renders checklist pages in headless Chrome and checks
  that each shows what its data holds.
- `stress.py` runs a longer fuzz, the extreme inputs at full size, and
  every file in the folders it's given.

## Where the ideas come from

The smells and refactorings come from Fowler and Beck's catalogue in
*Refactoring* and the authors who added to it; the measures and the
priorities come from empirical studies of smells, churn and refactoring.
[references/sources.md](references/sources.md) lists them all.

## Licence

It's under the MIT licence ([LICENSE](LICENSE)), so you're free to use,
change and share it.
