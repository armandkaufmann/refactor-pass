---
name: refactor-pass
description: Find what in a git repo needs refactoring, and what doesn't, the way developers used to feel it while coding by hand. It measures where changes keep landing (a heatmap of git history), what makes those files hard to change (code smells, each with its playbook of named refactorings) and what the next change would cost, then ranks refactors on a checklist worked through one item at a time. Use it whenever the user asks for a refactor pass; asks about tech debt, code health, hot spots or cleaning up; asks for refactor opportunities, or code that's cleaner, more maintainable, scalable or SOLID; asks what the worst part of the codebase is; says "we've made a lot of changes, anything to refactor?" or "before we start on the next feature, anything to fix first?"; or asks about one area ("should we refactor X?", "is this class doing too much?"). Use it even when they don't mention smells or churn. Also use it to carry on with a checklist this skill made ("what's next on the list", "start R4").
license: MIT
---

# Refactor pass

Refactoring used to start with a feeling. Code was hard to work on: a class
you scrolled through to find where the new thing went, a function you held
in your head to change one branch, a feature that meant visiting eight
files. The same feeling told you what to leave alone. Ugly code you never
touched never hurt, so you let it be.

An agent writing code doesn't feel any of that, and neither does a developer
who mostly reads what the agent wrote. So smells pile up unnoticed. An agent
will add a thirtieth branch to a function without complaint. And when it's
asked to refactor, it tidies whatever looks untidy, including code nobody
touches. This skill gives back both halves of the feeling, as three things
you can measure:

1. **Where you'd feel it: the heatmap.** Friction only matters where changes
   keep landing. Across studies, file size and how often a file changes
   predict maintenance trouble better than any single smell.
2. **What you'd feel: the smells.** The established catalogue of smells,
   each translated into what to count, when it *isn't* a smell, and the
   playbook of named refactorings that decades of practice built for it:
   [references/smells.md](references/smells.md).
3. **How much you'd feel it: the walkthrough.** Take the next change that's
   coming, planned or likely, and list everything it would touch.

Then the verdict combines where and what:

| | Smells | Doesn't smell |
|---|---|---|
| **Changes often** | Refactor | Say it's fine |
| **Rarely changes** | Leave it; at most a "Later" note | Nothing |

The "say it's fine" box matters as much as the "refactor" one. It's the
restraint half of the intuition, and the report shows it.

**Two sizes of question.** A pass covers the whole repo: steps 1 to 7. A
question about one area ("should we refactor X?") runs the same steps on
that area only. It skips the checklist unless there are several items, and
its answer can be "no". Either way, first run step 1's script with
`--checklists` alone: if it lists a checklist from an earlier pass, read
[After an earlier pass](#after-an-earlier-pass) first.

## 1. Where: the heatmap

```bash
python3 <this skill's directory>/scripts/heatmap.py -C <repo> <scope ...>
```

`<this skill's directory>` is the folder that holds this SKILL.md. Where
`python3` isn't the command, as often on Windows, use `python` or `py`.
If a script stops on a bug in the script itself, as it says, tell the user
what it said, and go on without it, from `git log` and the code.

- **Scope**: the source folders and the tests' folders, such as `src tests`
  or `app`, not docs or assets. Read the project's README, a directory
  listing and any agent instructions (`AGENTS.md`, `CLAUDE.md`) to decide.
  Test files, known by name (`Board.spec.ts`, `test_x.py`, `XTest.php`...)
  or folder, stay out of the table and pairs, and are listed apart when
  they change with several files. Add `--test GLOB` for other test names,
  `--not-test GLOB` for a file that only looks like one (the heatmap names
  any it doubts), and `--ignore GLOB` for generated files.
- **Window**: by default the last 200 commits. `--since` sets it instead
  when the user names a starting point ("since v2.0", "since we added
  billing", "the last three months"): a tag, branch or commit, or a date.
  Left out automatically: housekeeping bots' commits (dependencies,
  releases, formatting; the output names them, and `--bot NAME` adds one),
  the bulk reformats a repo lists in `.git-blame-ignore-revs`, and the
  commits recorded on earlier checklists. Coding agents' commits count.
  `--exclude-commits` leaves out others that would make everything they
  touched look hot, such as a vendored import. Dates are commit dates, as
  `git log --date=short-local --format='%h %cd %s'` shows them, not the
  author dates plain `git log` shows.
- **Too thin?** With fewer than about 30 commits in the window, the counts
  can't tell hot files from cold ones. Widen the window, or say the history
  is too short to point anywhere and judge by the smells alone. A shallow
  clone (the heatmap says so) needs `git fetch --unshallow`; ask the user.

`--help` explains every column and option.

### Reading it

- **A hot spot** has many commits and is also big, so the list puts those
  first: it's ordered by commits times size. Many commits on a small file is
  often fine, like a config edited for each feature. A big file nobody
  touches is cheap to leave alone.
- **Still hot?** `recent` counts its commits in the window's newer half
  (half the commits, not half the time), and `last` is the date of its
  latest. Read both against the window's dates: eight `recent` commits, all
  on the day the newer half starts, are a burst that has cooled. A file
  that shrank may already have been dealt with.
- **`rel`** is lines changed over the file's size. Relative churn predicts
  defects far better than absolute churn. Well above 1 means the file was
  rewritten or grew in the window. Read it with **growth**: a file that only
  grows, commit after commit, is
  [Additive-Only Growth](references/smells.md#additive-only-growth). A file
  born in the window has growth equal to its size.
- **Pairs** are files that keep changing in the same commits. A **group**
  is three or more that all pair with each other, counted by the commits
  that changed them all; groups that overlap are listed together as one
  area. A row's `last` is when its files last changed together: one whose
  last shared commit came before a refactor that took it apart is history,
  not coupling you'd feel today.
  - Files from different layers that pair strongly, or a group across
    layers, usually mean one feature spread across them (Shotgun Surgery).
  - Check what links each pair. An import, a call, or a contract something
    names (a route, a schema, the type file between a controller and its
    page) is a visible dependency: one feature across a boundary. Files
    that change together with no such link, such as two copies of a rule
    or two lists kept in step by hand, have a hidden dependency, the
    strongest kind of coupling.
  - A file that pairs with many others is a hub every change passes through.
  - A test listed as changing with several files besides its own is a lead
    to read: one that reaches their private members or internal paths is
    tied to their internals and will block refactoring; a broad test that
    follows features through them, or only follows a group, isn't.
  - If many commits were too big to pair (`--max-files`), as in a repo that
    squash-merges, raise it or read the pairs as partial.
- **Why it changes.** Read the top few files' commit messages (`--show`)
  and group them by feature. Many unrelated reasons to change one file is
  Divergent Change, and it shows here more directly than in any count.
- **Fixes** count the commits whose messages say they fixed a defect in the
  project's own code, so there are at least that many. Where most subjects
  carry a type, the count is close to complete; elsewhere it's a floor, and
  step 4 counts the rest for the files you'll recommend.

## 2. What: the smells

- **Measure the hot files** against the codebase itself, within one
  language. `python3 <this skill's directory>/scripts/measure.py -C <repo>
  <scope ...>` puts each file in a band by its language's 70th, 80th and
  90th percentiles, and `--show <file>` each of its functions, with their
  first and last lines. Big is the 80th or 90th band (past the catalogue's
  floor); the 70th is worth a closer look. Where the percentiles lean on
  one big file or function, it says so and bands by the catalogue's
  reference points instead: `>75` or `>440` is big, `>45` or `>220` worth
  a closer look. [Measuring](references/smells.md#measuring) says how to
  count the rest (branches, parameters, cohesion, a function's history),
  or to use the project's linter.
- **Read the top two or three core files yourself.** Numbers point; reading
  decides.
- **Review the other hot areas.** If you can run sub-agents, give two or
  three of them an area each (a layer or a directory, so each reads a whole
  area once) and run them in parallel. Brief each from
  [references/review-brief.md](references/review-brief.md). Without
  sub-agents, review the areas yourself, one at a time, against the same
  brief.
- **Name each smell with its established name** (Long Function, Shotgun
  Surgery, Repeated Switches…), and check it against the entry's "Not a smell
  when" before it counts. The name is the index to its playbook.
- **Look for the missing idea.** Smells travel in clusters, and a cluster
  usually points at one thing the code uses all the time but never named: a
  state, a kind's definition, a single source for a setting. See
  [Smells travel together](references/smells.md#smells-travel-together).
- **Check what tests reach the hot code**: see
  [Untested Code](references/smells.md#untested-code).
- **Bugs you notice** go on the list as F items, not fixed now. A bug not
  yet reproduced is a suspicion: title it as one ("Check: edits skip the
  weekend rule"), with the evidence in its note. Its first step is a
  failing test; if none fails, it's skipped, with what you found. A
  behaviour you reproduced that may be intended is the user's call: an F
  item, `waiting`, titled by what happens ("Refunds keep the fee"), with
  the question in its note; it's fixed if they say it's a bug, and skipped
  with their answer if not.

## 3. How much: the walkthrough

This is the closest thing to the old feeling. It's also what makes an item
convincing.

1. Find the next changes. A planned change beats an inferred one, so take
   them first from what the user said is coming ("before we start on chunk
   7"), then from the project's plan or roadmap, if it has one, then from
   what the code announces (a deprecation notice, a TODO that names a
   version), then from the commit messages: the kinds of change that come
   up most often ("add a new report type", "add a setting", "add a
   screen"). Take the two or three commonest kinds, not just one.
2. For each kind, take the latest real commit of it and list what it
   touched (`git show --stat`). If it's older than the window, use it all
   the same and give its date; the walkthrough, on today's code, shows what
   has moved since. If the project's docs or agent instructions have a
   recipe for that change, count its steps. A five-step recipe for adding
   one thing is an admission.
3. Walk through the next one, without writing it. List every file you'd
   have to read, every place you'd edit, and every copy you'd keep in step.
4. Write down the count today and the count after the refactor you'd
   propose: "a new report type touches 7 files and 3 switches today, and
   would touch 1 file after".

A cold file that planned work will land in is no longer cold: put it in the
table's top row, since the next change pays whatever it costs. If the next
change is cheap today, the smell is costing little, whatever it looks like.

## 4. Check every finding

A reviewer's finding is a lead, not a fact, and the same goes for your own
first impressions. Before anything goes on the list, open the cited lines,
re-run the counts, and drop or correct what doesn't hold. Say in the report
what you checked. A wrong item that sends the user into a refactor costs far
more than the minute it takes to check it.

**Count the fixes in the files you'll recommend**, at most five.
`heatmap.py -C <repo> --show <file> --messages`, with step 1's window, lists
each file's newest 12 commits, a sample, with their messages, a line of what
each changed, whether it's in the window's newer half, and the script's
reading. Judge every commit from its message; where that doesn't settle one,
get its changes before counting on, all of a file's unsettled ones in one
call: `--show <file> --diffs <hash>,<hash>`.

- **A fix corrects a defect in the project's own code**: wrong behaviour, a
  crash, a security hole, a regression, a compile or type error. Many don't
  say "fix": one that answers a report ("Fixes #12", "Reported-by:") is
  likely one, though an issue can ask for a feature. Many that say "fix"
  aren't: a "fix" of a typo, the docs, a test, the CI, or the build's
  manifests and dependencies. A fix may add something (an option, a check)
  to cure a defect; a new capability nothing lacked isn't one. Guards and
  the other edges: [Counting fixes](references/smells.md#counting-fixes).
- **Count a commit for each file whose change is part of its fix.** One fix
  can count for two files; one that touches a file in passing (a renamed
  call, an import) doesn't count for it, even where the script marked it.
- **The line of what changed is a hint, not a verdict**: a commit that
  changed a test too is a fix about twice as often as one that didn't; one
  of hundreds of lines, or titled Bump, Update or Release, rarely is; a line
  or two here among many files is likely in passing: no diff needed.

Within the sample the count is a count, not a floor: evidence that the file
breaks when it's touched, to weigh with its churn, size and smells, never an
item on its own. An item that cites it says "7 of its newest 12 commits
fixed a defect in it, 5 of them in the newer half" ("of its 11 commits in
the window" where it has fewer), and, where the files differ much, how the
others ran ("the other four ran 2 to 4 of 12"). It records each file in
`fixes`: the sample's size (`read`), how many fixes are in the newer half
(`newer`; null, and not said, where nearly all the sample is in it), and, as
lists of short hashes, the fixes you count that the script marked (`marked`)
or didn't (`found`), and those it marked that you don't (`dropped`), saying
why. Where the header says the messages can't be read, say nothing of fixes.

Then apply the restraint. A reviewer asked to find problems will always find
something, and fixing every finding leaves extra layers and tests for cases
that can't happen. Leave out what's cold, what the "Not a smell when" lines
excuse, and what the walkthrough says is cheap.

## 5. Rank

Give every item a stable ID, because the user will name items by it ("start
R4"), possibly in a later session. IDs are names, not ranks: a carried-over
item keeps its own, so a new R4 can come before R3, and the page lists items
in the order you write them. The names in brackets are the item's fields on
the checklist (step 6); F, L and D items say theirs in a `note`.

- **R1, R2…** Refactors, in the suggested order. For each:
  - a title naming the missing idea, as an outcome ("Name the states of a
    checkout", not "Refactor CheckoutController") (`title`);
  - the smells by name, with numbers and `file:line` (`smells`);
  - the kind of change it eases, from step 3 (`eases`), and that change's
    cost (`cost`: `today` and `after`);
  - the plan, as the playbook's steps (`plan`);
  - the files, size (S, M or L) and risk (Low, Medium or High) (`files`,
    `size`, `risk`);
  - the fixes it cites, if any, from step 4 (`fixes`), an entry per file
    with its `file`;
  - how to check that behaviour didn't change (`verify`).
- **F1…** Small fixes found along the way, each its own commit.
- **L1…** Later: smelly but cold, or worth doing when the code nearby is next
  touched.
- **D1…** The user's call: changes to how they work, such as a docs
  convention that makes every change costly. Lay out the trade-off, not a
  decision.

Rank by payoff against risk. Payoff is how much the change eases future
work: the heatmap and the walkthrough are the evidence. The smells'
priorities say which kinds tend to matter. Long and complex code, and
change spread across files, matter most. Coupling smells such as Feature
Envy and Middle Man matter least, and are
[fixed in passing](references/smells.md#fix-in-passing). A healthy codebase
gets a short list: one refactor, or none, is a result, and "nothing worth
refactoring now" is a finding to report as plainly as any other.

Order the list so that:
- blockers come first: tests tied to internals that would make every later
  step look like it broke something, and code no test covers, whose item
  starts with pinning tests or says plainly it can't be checked (step 7);
- the small items that remove a copy-paste path come next;
- large moves come after, since they often need a seam first;
- anything you can't verify yourself (how it sounds, feels or looks) comes
  last, because the user has to check it.

## 6. Write the checklist and report

Run step 1's command again with `--page` and the name `--checklists` gave:
today's date (`.refactor-pass/2026-11-11.html`, or `2026-11-11-2.html` for a
second pass that day). It makes the checklist from
[assets/page.html](assets/page.html) and writes the heatmap into its
`heatmap` block; on a checklist that exists, it refreshes the heatmap and
nothing else, and says so. You write the `pass` block below it, whose
`project`, `started`, `base` and `updated` are already filled in:

- `summary`: the overall state in two or three sentences;
- `items`: every item, in the suggested order, with step 5's fields, a
  `status` (`todo`, `doing`, `waiting` on the user, `done`, or `skipped`
  with the reason in its outcome), and `commits` and `outcome`, empty for a
  new item; a carried-over item keeps its `from`. An item's first line
  holds its ID and status, `{"id": "R1", "status": "todo",` and its title;
  its other fields go on the lines after, as the comment above the blocks
  shows. Not the whole item on one line, nor a JSON pretty-printer's
  layout: step 7's status updates edit that first line;
- `left_alone`: each with `what` and `why`;
- `checks`: the project's checks, from its instructions, or what you'll
  check by hand if it has none;
- `earlier`: after an earlier pass, `checklist`, its path as
  `--checklists` prints it, and `results`, one per refactor finished on it
  (one that only added pinning tests too): its `id`, `title`, `eases` and
  `cost` as it had them; `change`, the first real change of that kind
  since, as hash, date and subject, and `actual`, what that touched, from
  `git show --stat`, both empty if none has come yet; and a `note` on how
  the prediction held. Otherwise `null`;
- `log`: each with a `date` and `text`, newest first.

After each edit, run `python3 <this skill's directory>/scripts/check_page.py
<page>`, which catches a broken bracket, a misspelt field, a duplicate ID or
an item whose first line isn't its ID and status, and warns of a field left
empty. If your environment can publish or preview HTML pages, publish the
same file and give the link; otherwise give the path to open in a browser.

**Where it lives.** `.refactor-pass/` is at the repo's top, with a
`.gitignore` the heatmap writes, so the folder is never committed and the
project's own `.gitignore` stays untouched. In a linked worktree, a relative
`--page` path is the main checkout's, which outlives the worktree. If a
sandbox won't let you write there, the heatmap says what to do. If the
checklist will go with a worktree or a cloud sandbox, tell the user.

Then reply with:

- after an earlier pass, how its finished items' predictions held;
- two or three sentences on the overall state, good parts included;
- the top three to five hot spots as a small table (file, lines as the
  heatmap's `size` gives them, commits);
- the R items as a numbered list: title, smells, size, risk, and the next
  change's cost today and after;
- the F and D items in brief;
- what you left alone and why, in a line or two;
- the suggested order, and where the checklist is;
- a question: which item should you start with?

Don't change any code until the user picks.

## 7. Working through the list

- **One item at a time, when the user names it.** Read the newest checklist
  first (`--checklists` finds it), including when you're picking up in a
  new session: its plans may be days old.
- **Two hats.** A refactoring step changes structure and no behaviour. Never
  mix it with a fix or a feature, in the same commit or the same step. If you
  find a bug, note it as an F item.
- **Make the change easy, then make the easy change** (Kent Beck). When an
  item exists to make a coming feature easy, finish the refactor before
  starting the feature.
- **Pin untested code first.** Before refactoring code no test covers, write
  characterization tests (Feathers): tests that record what it does now,
  right or wrong, through what its callers use. Commit them on their own. If
  it can't be pinned, say so in the outcome, with the risk; don't call it
  verified.
- **Follow the playbook in small steps.** Use the named refactorings, one at
  a time, with the tests passing after each, and the editor's or language
  tools' automated refactorings where they exist. If the tests stay failing
  for more than a few minutes, go back to the last passing state and take a
  smaller step.
- **Leave alone what you don't need to change**, and wait for the third copy
  before merging copies.
- **Behaviour doesn't change.** Check each step with the project's own
  checks: tests, linters, snapshot or simulation tools, whatever its
  instructions name. Take extra care with hierarchy refactorings (pulling
  methods up, extracting subclasses), which induce bugs most often.
- **Check the smells again after an item.** A refactor can leave a smell
  behind or make a new one: a class that took on moved methods can turn into
  a Large Class.
- **Commit exactly as the project's and the user's rules say.** Some users
  want to approve every commit first.
- **When the plan changes**, because a finding was wrong, a step was dropped
  or something was found on the way, write that in the item's outcome. Don't
  quietly leave it out.
- **After each step, update the checklist** in small edits: the item's
  status (an edit to its first line: `{"id": "R4", "status": "todo"` becomes
  `"doing"`); its `commits`, every hash as it landed on the branch the user
  keeps (after a squash merge or a rebase, the new hashes), so a later pass
  can leave them out; its outcome, with the checks' numbers and the next
  change's cost now; a dated log entry; `updated`; and any `file:line` in
  other items that the step moved. Then run `check_page.py`, and republish
  the page if it was published.
- **Asked "what's next?"**, answer from the checklist. Don't start the work.

## After an earlier pass

`heatmap.py --checklists` lists every checklist, the main checkout's and
any worktree's, newest first by the date in its name and then its number,
and gives the name a new one takes.

1. **Build on the newest.** The heatmap leaves out the commits recorded on
   every checklist, so the refactoring just done doesn't make its own files
   look hot. If it warns that a recorded commit isn't reachable from HEAD
   and the work was squash-merged or rebased, record the hash that landed it
   instead, and run the heatmap again before reading it.
2. **See what has landed since.** `--since <its base>` shows it; when
   that's nothing but the pass's own work, it says so, and so should you.
   Growth, being two sizes, still counts the pass's own commits: a file a
   refactor made or shrank shows growth its churn doesn't explain.
3. **Start a new checklist** under the name `--checklists` gives, even on
   the same day; `--page` on the old one would only refresh its heatmap.
4. **Carry items over.** Items still `todo`, `doing` or `waiting` carry
   over, checked again as any finding is ([step 4](#4-check-every-finding)),
   keeping their IDs and `from`, the date of the checklist they first
   appeared on. Done and skipped items stay behind; done refactors appear in
   `earlier` instead. A Later item that has turned hot becomes a new R item.
   New items number on from the highest ID of each letter.
5. **Check the predictions.** For each refactor finished on the newest
   checklist, find the first real change of the kind it eased after its
   last commit (never one recorded on a checklist), list what it touched
   (`git show --stat`), and set that beside the cost the item predicted, in
   `earlier`. That is the "it's easier now" half of the feeling, so the
   report leads with it, misses included.
