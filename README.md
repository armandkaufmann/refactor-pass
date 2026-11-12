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
  coding agents' commits count. It counts the commits whose messages say
  they fixed a defect in each file, at least that many, and the agent reads
  the rest of the commits for the few files it recommends.
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

The skill is the `skills/refactor-pass` folder in this repo. The installer,
`install.py`, puts that folder, and nothing else from the repo, where your
coding agents look for skills. It needs Python 3.7 or later and git, and
runs piped, with nothing to download first. On macOS or Linux:

```bash
curl -fsSL https://raw.githubusercontent.com/armandkaufmann/refactor-pass/main/install.py | python3 -
```

In Windows PowerShell:

```powershell
irm https://raw.githubusercontent.com/armandkaufmann/refactor-pass/main/install.py | python -
```

It looks for the agents below by their folders in your home, installs the
latest release once in each skills folder they read (one copy serves every
agent that shares a folder), and prints what it did and where. If it finds
none, it installs nothing and lists the choices. Flags go after the `-`,
as in `| python3 - --agent claude-code`, or after `install.py` when you run
it from a clone; `--dry-run` prints what it would do, and `--help` lists
the rest.

- `--agent NAME` (repeatable): install for these agents, found or not.
- `--dir DIR` (repeatable): install in `DIR/refactor-pass`, any place (or
  in `DIR` itself if it's named `refactor-pass`).
- `--project`: put a copy in the current git repo, to commit, for the
  agents named with `--agent`, else those whose folders the repo has, else
  those found in your home. The scripts leave the copy's own files out of
  what they count.
- `--ref REF`: a release tag such as `v1.0.0`, a branch, or a full commit,
  instead of the latest release.
- `--source URL_OR_FOLDER`: install from another clone, by an https, ssh
  or git URL, or from a folder (as `--source . --ref HEAD` installs your
  clone's last commit). It reads the files from the commit, not from a
  checkout, and installs only plain files, never a link.

Later, with the same one line, or `install.py`, and a command after it, as
in `curl -fsSL .../install.py | python3 - update`:

- `update`: brings every copy it made, in the agents' folders and the
  current project's, to the latest release (and any `--dir` you name).
- `check`: prints each copy's version against the latest, changing nothing.
- `uninstall`: removes the copies it made, only the files it installed.

The latest release is the highest `vMAJOR.MINOR.PATCH` tag; until there is
one, it installs the default branch and says so, and `update` moves it to
the first release. Each copy holds a small `.install.json` with its source,
version and a hash of each file, which these commands read (a checkout's
CRLF line ends don't count as an edit). A copy whose files were edited
since, or that holds files it didn't install, is left alone unless you add
`--force`. A folder it didn't make, one whose `.install.json` it can't
trust (as one naming a file outside the copy), a git clone and a link are
always left alone. A new copy is built beside the old one and swapped
in, so a failed run leaves the old copy whole.

Where each agent reads skills, from its own documentation:

| Agent | `--agent` | Found by | User folders it reads | Project folders it reads |
| - | - | - | - | - |
| [Claude Code](https://code.claude.com/docs/en/skills) | `claude-code` | [`~/.claude`](https://code.claude.com/docs/en/settings) | `~/.claude/skills` | `.claude/skills` |
| [Codex](https://learn.chatgpt.com/docs/build-skills) | `codex` | `~/.codex` | `~/.agents/skills` | `.agents/skills` |
| [Cursor](https://cursor.com/docs/context/skills) | `cursor` | [`~/.cursor`](https://cursor.com/docs/context/mcp) | `~/.agents/skills`, `~/.cursor/skills`, and `~/.claude/skills`, `~/.codex/skills` | `.agents/skills`, `.cursor/skills`, `.claude/skills`, `.codex/skills` |
| [Gemini CLI](https://geminicli.com/docs/cli/skills/) | `gemini-cli` | [`~/.gemini`](https://geminicli.com/docs/reference/configuration/) | `~/.agents/skills`, `~/.gemini/skills` | `.agents/skills`, `.gemini/skills` |
| [GitHub Copilot](https://docs.github.com/en/copilot/concepts/agents/about-agent-skills) | `github-copilot` | [`~/.copilot`](https://docs.github.com/en/copilot/how-tos/copilot-cli/set-up-copilot-cli/configure-copilot-cli) | `~/.agents/skills`, `~/.copilot/skills` | `.agents/skills`, `.github/skills`, `.claude/skills` |
| [opencode](https://opencode.ai/docs/skills/) | `opencode` | [`~/.config/opencode`](https://opencode.ai/docs/config/) | `~/.agents/skills`, `~/.config/opencode/skills`, `~/.claude/skills` | `.agents/skills`, `.opencode/skills`, `.claude/skills` |
| [Amp](https://ampcode.com/docs/customize/skills) | `amp` | [`~/.config/amp`](https://ampcode.com/docs/cli/settings) | `~/.agents/skills`, `~/.config/agents/skills`, `~/.config/amp/skills`, `~/.claude/skills` | `.agents/skills`, `.claude/skills` |

So `~/.agents/skills` serves every agent but Claude Code, and
`~/.claude/skills` serves Claude Code, Cursor, opencode and Amp: with
Claude Code and another agent, the installer makes one copy in each, and
says which agents may then list the skill twice. The Codex page names
`~/.codex/config.toml`; Copilot is found by the CLI's folder, so name it
with `--agent` for VS Code alone. The pages give no Windows paths for
Codex, Cursor, Gemini CLI or opencode; the installer uses the same folders
under your user folder there. Folders moved by an environment variable
(`CLAUDE_CONFIG_DIR`, `COPILOT_HOME`) aren't followed: use `--dir`.

To install by hand instead, copy the skill's folder where your agent looks,
and do the same again to update it:

```bash
git clone --depth 1 https://github.com/armandkaufmann/refactor-pass /tmp/refactor-pass
mkdir -p ~/.agents/skills
cp -R /tmp/refactor-pass/skills/refactor-pass ~/.agents/skills/
rm -rf /tmp/refactor-pass
```

If you installed it before by cloning this repo into a skills folder, that
clone no longer has `SKILL.md` at its top after a pull, so agents stop
seeing the skill. The installer leaves a clone alone, so remove it
yourself (`rm -rf ~/.claude/skills/refactor-pass`, or your folder), then
install. `npx skills add armandkaufmann/refactor-pass`, from the
[skills](https://github.com/vercel-labs/skills) tool, should also work: its
documentation says it finds a repo's `skills/<name>/SKILL.md`, and leaves
`.git` and `__pycache__` out of what it copies. We haven't tried it.

With any other agent, put the folder anywhere and ask the agent to read
its `SKILL.md` and follow it ("Read ~/refactor-pass/SKILL.md and do a
refactor pass"); point it there again when you carry on in a new session.

The scripts need git (2.15 or later, for
`git rev-parse --is-shallow-repository`) and Python 3.7 or later, with the
standard library only. Their tests run on every push on Linux, macOS and
Windows, with Python 3.9, 3.13 and 3.14 on each, and 3.7 and 3.8 on Linux.
On Windows the command may be `python` or `py` rather than `python3`.

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

They're in the skill's `scripts/` folder, need no agent, only Python and
git, and each runs with `--help` for its options:

```bash
python3 skills/refactor-pass/scripts/heatmap.py -C ~/code/my-app src tests
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

- `skills/refactor-pass/`: the skill, all that an agent needs:
  - `SKILL.md`: the skill itself, the steps the agent follows.
  - `references/smells.md`: the catalogue of smells and their playbooks.
  - `references/review-brief.md`: the brief for reviewing one area of
    code.
  - `references/sources.md`: the books, studies and articles drawn on.
  - `scripts/`: the scripts above.
  - `assets/page.html`: the template for the checklist page.
- `install.py`: the installer, which copies only `skills/refactor-pass`.
- `tests/`: the tests, for contributors (see [Tests](#tests)).
- `.github/workflows/tests.yml`: runs the tests on every push.

## Tests

For contributors; an installed copy doesn't need them. The suite in
`tests/` uses Python's standard library and git, builds the small repos it
reads in a temporary folder, and runs in under a minute on macOS and Linux
and in under three on Windows. It tries the installer against source repos
it builds there too, never the network, with a home folder of its own. `-B`
keeps Python from writing bytecode into the skill's folder:

```bash
python3 -B -m unittest discover -s tests -t .
```

Run it from the repo's top, or from anywhere with both paths:
`-s <repo>/tests -t <repo>`. To test another copy of the scripts, such as
an older commit's, set `REFACTOR_PASS_SCRIPTS` to its `scripts/` folder.
A GitHub Actions workflow, `.github/workflows/tests.yml`, runs it on Linux,
macOS and Windows with several versions of Python.

Outside that run, `tests/tools/` holds five checks to run by hand:

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
- `measure_fixes.py` measures the heatmap's count of fixes against 1,023
  commits of ten pinned repos labelled fix or not by reading each one's
  message and diff (`tests/fixes_labels.txt`), and fails where a repo's
  precision or recall falls below its recorded floors.
- `render_pages.py` renders checklist pages in headless Chrome, today's and
  those of earlier releases, and checks that each shows what its data
  holds.
- `stress.py` runs a longer fuzz, the extreme inputs at full size, and
  every file in the folders it's given.

## Where the ideas come from

The smells and refactorings come from Fowler and Beck's catalogue in
*Refactoring* and the authors who added to it; the measures and the
priorities come from empirical studies of smells, churn and refactoring.
[references/sources.md](skills/refactor-pass/references/sources.md) lists them all.

## Licence

It's under the MIT licence ([LICENSE](LICENSE)), so you're free to use,
change and share it.

## Releasing

The installer takes the highest `vMAJOR.MINOR.PATCH` tag, so a release is a
tag on `main`:

1. Check that the tests passed on `main`'s last commit, on every system,
   in GitHub Actions.
2. Tag that commit, then push the tag:

   ```bash
   git tag -a v1.0.0 -m "refactor-pass v1.0.0"
   git push origin v1.0.0
   ```

`update` brings everyone's copies to it from then on. The installer itself
is always fetched from `main`, while the skill comes from a tag, so
`install.py` on `main` must install every release from the first on. Keep
the whole skill in `skills/refactor-pass`, with `SKILL.md` in it; keep
reading the `.install.json` that older installers wrote (its `record`
number says which form it is); and after changing `install.py`, install
the first release with it (`python3 install.py --dir /tmp/try --ref v1.0.0`).

