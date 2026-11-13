# Smells

Before AI agents, a refactor started with a feeling: code that was hard to
work on, and, just as much, the sense to leave alone ugly code nobody
touched. Kent Beck named that feeling a smell, and Beck and Martin Fowler
catalogued the smells with a playbook of named refactorings for each; other
authors added more. Beck's own caveat still holds: "no set of metrics
rivals informed human intuition." This catalogue tries to give that
intuition back to an agent, which writes code without feeling any of it,
and to a person who now reads more code than they type.

Each smell has five parts:

- **Felt like**: what working on it was like by hand. If you'd feel that
  making the next change, the smell matters.
- **Count**: what to measure, so the case rests on numbers, not taste.
- **Not a smell when**: the look-alikes and the authors' own caveats. This is
  the restraint half.
- **Playbook**: the named refactorings, in the order to reach for them.
- **Priority**: what the evidence says about how much it matters.

Use the established names, in the list and in the report. Each one is the
index to a playbook that the refactoring literature, and so most agents and
developers, already know. "Replace Conditional with Polymorphism" brings its
mechanics with it; a name invented for the occasion brings nothing. The
names of refactorings are those of Fowler's second edition (2018), as in
[refactoring.com/catalog](https://refactoring.com/catalog/).

## Contents

- [What the evidence says](#what-the-evidence-says)
- [Measuring](#measuring)
- [Counting fixes](#counting-fixes)
- Bloaters: [Long Function](#long-function), [Large Class](#large-class),
  [Long Parameter List](#long-parameter-list), [Data Clumps](#data-clumps),
  [Primitive Obsession](#primitive-obsession)
- Change preventers: [Divergent Change](#divergent-change),
  [Shotgun Surgery](#shotgun-surgery), [Repeated Switches](#repeated-switches)
- State: [Hidden State Machine](#hidden-state-machine),
  [Global Data and Mutable Data](#global-data-and-mutable-data),
  [Tramp Data](#tramp-data)
- Couplers: [Insider Trading](#insider-trading)
- Duplication: [Duplicated Code](#duplicated-code),
  [Oddball Solution](#oddball-solution)
- Knowledge in the wrong place: [Misplaced Responsibility](#misplaced-responsibility),
  [Magic Literal](#magic-literal)
- Dispensables: [Speculative Generality](#speculative-generality),
  [Dead Code](#dead-code)
- [Fix in passing](#fix-in-passing): Feature Envy, Message Chains, Middle Man,
  Data Class, Refused Bequest, Comments
- Tests: [Untested Code](#untested-code),
  [Tests Tied to Internals](#tests-tied-to-internals)
- [Smells of AI-written code](#smells-of-ai-written-code):
  [Additive-Only Growth](#additive-only-growth),
  [Defence in the Wrong Place](#defence-in-the-wrong-place)
- [Smells travel together](#smells-travel-together)
- Sources: [sources.md](sources.md)

## What the evidence says

Studies of real codebases agree on a few things, and they shape every
priority below.

- **Size and change explain most of it.** Sjøberg et al. measured
  professional developers' effort on four equivalent systems: "None of the 12
  investigated smells was significantly associated with increased effort
  after we adjusted for file size and the number of changes." That's why the
  heatmap (size and changes) comes first and the smells second. The smells
  explain why a hot file is hard to change, and their playbooks say how to
  fix it.
- **Code nobody changes is fine.** Lanza and Marinescu, who defined the
  metric rules for God Class: "a class that has the structural
  characteristics of a God Class but that resides in a stable and untouched
  part of the system does not pose a problem!"
- **Long and complex code matters most; several smells together matter
  more.** Palomba et al. checked 13 smells across 395 releases of 30
  projects. Long Method was in 84% of releases, Message Chains in 13%. Smelly
  classes had a median of 32 changes against 12, and 9 bug fixes against 3,
  and "the higher the number of smells affecting a class the higher its
  change- and fault-proneness." Feature Envy, Lazy Class, Message Chains and
  Middle Man were rare. Removing a smell didn't measurably reduce faults, so
  the smell travels with the trouble rather than causing it alone.
- **Most smells are there from the start.** Tufano et al., over 200
  projects: "most of the smell instances are introduced when an artifact is
  created and not as a result of its evolution"; "80% of smells survive";
  and of those removed, "only 9%" go through refactoring. New code is where a
  smell is cheapest to catch.
- **Refactoring has its own risk.** Bavota et al. traced bug fixes back to
  refactorings in three open-source systems. 15% of refactored classes were
  later fixed for a bug the refactoring brought in. Refactorings involving
  hierarchies "tend to induce faults very frequently": Pull Up Method and
  Extract Subclass did so about 40% of the time, and even Extract Method
  about 21%. Others, such as Hide Delegate and Remove Middle Man, almost
  never did. So take small steps with the tests passing after each, don't
  start a hierarchy refactoring without tests, and check for smells again
  afterwards.
- **A file that keeps needing fixes breaks when it's touched, but messages
  undercount the fixes.** That's what the heatmap's fixes count, and it
  counts them from commit messages, as Mockus and Votta did: "If fix, bug,
  error, fixup, fail are present, the change is classified as corrective".
  Words miss fixes and mislabel changes. Their rule and the developers who
  wrote the changes agreed only so often: "More than 61% of the time, both
  the developer and the program ... put changes in the same class". A
  study reproducing one that sorted commits this way found a "false
  positive rate of 36%", and "The false negative rate was 11%" (Berger et
  al.), and even issue trackers' own labels are often wrong: Herzig et
  al. found "33.8% of all bug reports to be misclassified". Reverts are
  rare: "1%-5% of the commits in the studied systems are reverted"
  (Shimagaki et al.). So read
  the count as a floor, and read the commits it leaves unmarked before
  citing it. And a count alone changes nothing: when Google deployed a bug
  predictor to its developers, there was "no identifiable change in
  developer behavior" (Lewis et al.). A fix count is evidence that backs an
  item with a reason, never an item by itself.

## Measuring

Judge sizes against the codebase, within one language, not against a rule
from a book. Metric distributions differ a lot between languages and
projects, and they have long tails, so some code will always be big. The
established method (Alves et al.) derives thresholds from upper percentiles
of a benchmark's code, weighted by lines: the 70th, 80th and 90th, which
mark bands of moderate, high and very high risk. Here the codebase is its
own benchmark. So: find its percentiles for the measure (tests left out),
and call something big when it reaches the 80th, very big at the 90th, and
worth a closer look at the 70th. Keep an absolute floor too, the "Look
closer" column below, so a codebase of tiny functions doesn't flag a
25-line one.

Don't make the 90th the only line. Weighted by lines, the code past it is a
tenth of the whole, so in a small codebase that's a file or two, and the
next biggest can sit just under it. For the same reason, the file a
percentile falls in reaches it, since some of its lines are past it. Where
one file holds a tenth of a language's lines and is half as long again as
any other, the percentiles lean on it: it's its own 90th, every cut falls
in it, and nothing shorter reaches a band. Then judge that language's files
by the reference points below instead: over 220 lines is worth a closer
look, over 440 big. Where one function stands out among its language's
functions that way, judge them by over 45 and over 75.

Reference points, mostly from Java benchmarks, for a floor or a small
codebase:

| Measure | Look closer | Strong | Source |
|---|---|---|---|
| Function length | over 45 lines | over 75 | Alves et al.: 44 and 74 lines at the 80th and 90th percentile |
| Branches (cyclomatic) | over 10 | over 14 | McCabe's 10; PMD's default 10; Alves et al.'s 90th percentile 14 |
| Cognitive complexity | over 15 | | PMD's default 15 |
| Nesting | 3 inside a long function | 4 anywhere | Lanza & Marinescu's Brain Method; ESLint's default 4 |
| Parameters | over 4 | over 7 | Alves et al.: 4 at the 95th percentile; Checkstyle's default maximum, 7 |
| Methods in a class | over 16 | | Oliveira et al.: 80% of classes have 16 or fewer |
| Lines in a class | over 220 | over 440 | Oliveira et al.: 75% of classes have 222 or fewer |

Lanza and Marinescu's rule for a **Brain Method** is a good composite: long
(more than half a large class's lines, about 65 for Java), branching
heavily, nested at least 3 deep, and using many variables (more than about
7). Their **God Class** uses more than a few other classes' data, is very
complex overall, and isn't cohesive (fewer than a third of its method pairs
share a field). The Java figures come from their benchmark of 45 systems,
so treat them as anchors, not limits.

Measure with what the project already has. If its linter reports
complexity, use that; don't install new tools without asking. Otherwise this
skill's `scripts/measure.py` measures length, in any of the common
languages:

```bash
python3 <this skill's directory>/scripts/measure.py -C <repo> <scope ...> [--show <file>]
```

Give it the heatmap's scope; it sets test files aside as the heatmap does,
so they stay out of the percentiles. It gives each language's 70th, 80th
and 90th percentiles of file and function length, weighted by lines as
Alves et al. do, then each file's code lines (blank lines, comment-only
lines and Python's docstrings left out) and band, functions, longest
function and deepest nesting. The bands apply the rules above, floor
included; where the percentiles lean on one file or function, they're the
reference points, shown as `>220` and `>440` for a file, `>45` and `>75`
for a function. Nesting is measured by indentation, which tracks the
classical complexity metrics closely (Hindle et al.) and is free in any
language. `--show` lists one file's functions, each with its first and last
line. It finds functions by each language's keyword or shape, so it misses
some and miscounts a few; its `--help` says how. Read a function before
calling it long.

The rest takes plain commands:

- **branches:** the `if`, `else if`, `case`, `match` arms and loops within a
  function's lines;
- **parameters:** count them at the definition;
- **cohesion (LCOM4):** list the fields each method uses, link methods that
  share a field or call each other, and count the islands. One island is
  cohesive. Two or more are classes waiting to get out;
- **one function's history:** `git log -L <first>,<last>:<file>`, with the
  lines `measure.py --show` gives, lists the commits that changed those
  lines. `git log -L :<function>:<file>` finds a function by its name only
  where git's diff driver can: by default, a definition that starts its
  line, so not an indented method, unless the repo's `.gitattributes` gives
  the language a driver (`*.py diff=python`). Otherwise it stops with "no
  match";
- **length, without the script:** `wc -l`, and `grep -n` with the
  language's function keyword for an outline, or your shell's equivalents.
  A function's length is then the gap to the next definition.

These are cheap and rough, which is fine: they point you at code to read,
and you read it before saying anything.

## Counting fixes

How to judge a commit's change to a file when counting the file's fixes
(SKILL.md step 4):

- **A fix corrects a defect in the project's own code** as it stood: wrong
  behaviour, a crash, a security hole, a regression, a compile or type
  error.
- **A guard** is a fix when it stops a failure that could happen as the
  code stood: a crash or a wrong result in the project's code. One against
  a failure only a caller misusing the API reaches counts only where the
  API took that input before and then failed later or gave a wrong result,
  not where its documentation ruled the input out. One that moves a failure
  earlier (an error at the call where a crash came later) counts on the
  same terms, when the later failure was a crash or a wrong result in the
  project's code. A guard for a case nothing reaches isn't a fix.
- **Something missing** that callers or an interface already relied on is a
  fix, even where curing it adds something new (an option, a control); a
  capability nothing lacked is a feature.
- **An opt-in option** that cures an overload or a slow path, the default
  unchanged, isn't a fix unless the old behaviour was a failure: a hang, a
  crash, data lost.
- **Building and packaging**: code whose job is to build or package the
  project, such as a script in its source that generates code, is its code,
  and a fix to it counts. A change only to its manifests, lock files, CI or
  build configuration doesn't.
- **A report** the commit answers ("Fixes #12", "Reported-by:", a ticket)
  is evidence of a defect, but an issue can also ask for a feature: read
  what it says was wrong.
- **A revert** of another author's commit is a fix: the change broke
  something. One of its author's own commits is a withdrawal, and one of a
  commit the repo hasn't (as a shallow clone's) can't say whose change it
  undid: the script counts neither, unless the revert's type says fix
  (`fix: revert "..."`) where types are read as labels.
- **One fix, two files**: a commit counts for each file whose change is part
  of the fix, and not for one it touches only in passing (a renamed call,
  an import).
- **A cut diff**: `--diffs` shows at most 60 lines of a commit's change to
  the file, and its last line names the `git show <hash> -- <file>` that
  shows the rest. A count rarely needs it.

**How far the script's marks go**, as measured on commits labelled by
reading their message and diff: 1,023 commits of ten public repos, labelled
by one reader, and 252 of nine others, labelled by two readers who agreed on
248. Of the commits it reads as fixes, about 9 in 10 are fixes of the
project's code (95% of the 490 the rules were written from, 96% of 180 kept
aside, 91% of those that touch the code in the nine others). How many of the
fixes it finds depends on how a repo writes its messages: nearly all where
subjects carry a type (88% to 100% in four such repos); typically a third to
a half where they don't (33% to 64% in six of seven such repos, 80% in one
whose subjects nearly always say fix); 35% over the nine others, one of them
typed; and none of 14 in one whose subjects name the area and the new
behaviour, and whose bodies say what was wrong. Of 90 commits of three repos
that put tags in brackets, labelled after the tags were read, 16 of its 20
calls were right and it found 38% of the fixes: 43% and 22% in two whose tags
name an area or a ticket and are passed over, and all 5 in one whose tags
are types, where 4 of its 9 calls were a lint, a CI change or changes for a
new version of a dependency, labelled [Fix]. On the commits it leaves
unmarked, one that changed a test too was a fix about twice as often as one
that didn't (45% against 24% in the labelled commits), and one of over 200
lines rarely (1 of 20).

Reading closes most of the gap: in one measurement, an agent given those 252
commits and the definition found 72% of the fixes from their subjects (43 of
its 44 calls right) and 83% from their whole messages (all 50 calls right),
and wanted the diff for 21 commits; reading as step 4 does, with the diffs
where the messages fell short, it found 56 of the 60 (56 of its 57 calls
right), overruling four of the script's marks, and with each file's own
changes from `--diffs`, 55 of the 60 (55 of 56 right), reading less than
half as much. The labels it was scored against came from the same kind of
model reading the diffs, which flatters agreement: one measurement, not an
accuracy. On five of a busy project's files, judging up to 12 commits of
each (55 in all, 15 of them with their diffs) took about 60,000 tokens and
two minutes; a file's listing is a few thousand bytes (8,678 for redis's
`src/server.c`, whose 99 commits in an 800-commit window take 65,878).

## Bloaters

### Long Function

*Fowler & Beck. Long Method in the first edition.*

- **Felt like:** you held the whole function in your head to change one
  branch. A fix in one branch broke another. You scrolled up to remember what
  a variable meant by now.
- **Count:** length, branches, deepest nesting and variables, against the
  codebase's bands (see [Measuring](#measuring)). Also: blocks with
  a comment saying what they do, loops doing two things, and how often
  `git log -L <first>,<last>:<file>` shows the function changing (see
  [Measuring](#measuring)).
- **Not a smell when:** it reads top to bottom. "The key here is not function
  length but the semantic distance between what the method does and how it
  does it." A flat sequence of steps, a dispatcher of one line per case, code
  that lays out a screen and a test can all be long and fine. Fowler: "Some
  long methods are just fine."
- **Playbook:**
  1. "Ninety-nine percent of the time", Extract Function. A block with a
     comment becomes a function named after the comment.
  2. If temporary variables or parameters get in the way: Replace Temp with
     Query, Introduce Parameter Object, Preserve Whole Object.
  3. For conditionals, Decompose Conditional; for a loop that does two
     things, Split Loop.
  4. If the same switch shows up elsewhere: Replace Conditional with
     Polymorphism (see [Repeated Switches](#repeated-switches)). If branches
     test the object's mode, see [Hidden State Machine](#hidden-state-machine).
  5. If it still won't come apart: Replace Function with Command, Fowler's
     "heavy artillery". Kerievsky's Compose Method describes the end state:
     a function that reads as a list of steps at one level of detail.
- **Priority:** high. It is the most widespread smell and the one developers
  recognise most. Extract Function is the usual first move, but it isn't free:
  one study traced a bug to about a fifth of Extract Methods. Extract in
  small steps, with the tests passing after each.

### Large Class

*Fowler & Beck; God Class or Blob in the metrics literature.*

- **Felt like:** every feature landed here, and you scrolled to find where
  the new piece went. You couldn't say what the class was for in one
  sentence without "and". Its tests needed the whole world set up.
- **Count:**
  - lines, methods and fields, against the codebase;
  - cohesion as LCOM4 islands (see [Measuring](#measuring)). Fowler: "When a
    class is trying to do too much, it often shows up as too many fields";
  - fields sharing a prefix or suffix, a sign of a group;
  - "Look at whether clients use a subset of the features of the class."
    Each subset is a candidate class;
  - the reasons in its commit messages (see
    [Divergent Change](#divergent-change)).
- **Not a smell when:**
  - it's big because it's data: a catalogue of definitions, a table,
    translations;
  - it's generated, or a test file of independent tests;
  - it's big but nobody changes it (Lanza and Marinescu, above);
  - it's the place that wires everything together. Knowing about many
    things is its job; the smell there is when it also holds their logic.
- **Playbook:**
  1. First "eliminate redundancy in the class itself": duplicated code
     inside it often accounts for much of the size.
  2. Extract Class along each island of methods and their fields.
  3. Extract Superclass, or Replace Type Code with Subclasses when the
     islands are variants of one thing.

  If the code already has a pattern for such a split (a controller, a
  service, a component), follow it, so the next agent copies the right
  thing.
- **Priority:** high when it's hot; leave it when it's cold. God Class had
  the largest change-proneness of any smell Palomba et al. measured.

### Long Parameter List

*Fowler & Beck; Flag Arguments from Martin's* Clean Code *(F3) and
Fowler's bliki.*

- **Felt like:** every call needed the same five arguments in the right
  order, and adding one meant editing every caller. A `true` at a call site
  told you nothing.
- **Count:**
  - parameters per function: over 4 is past the 95th percentile of
    benchmark code;
  - true/false parameters that switch the function between behaviours.
    Fowler defines a flag argument as "a kind of function argument that
    tells the function to carry out a different operation depending on its
    value."
- **Not a smell when:**
  - it's a value object's constructor, or arguments named at the call site;
  - the callee deliberately shouldn't depend on the bigger object;
  - a boolean is data passed through, such as a checkbox's state, rather than
    the caller choosing behaviour (Fowler).
- **Playbook:**
  - Replace Parameter with Query;
  - Preserve Whole Object;
  - Introduce Parameter Object;
  - Remove Flag Argument;
  - when several functions share the same values, Combine Functions into
    Class.
- **Priority:** medium.

### Data Clumps

*Fowler & Beck.*

- **Felt like:** the same three or four values went everywhere together, and
  each new function took all of them again.
- **Count:** groups of three or more values passed together or stored side
  by side in several places. Fowler's test: delete one of the values. If the
  others no longer make sense alone, they're one thing.
- **Not a smell when:** the values only meet once.
- **Playbook:** Extract Class, then Introduce Parameter Object or Preserve
  Whole Object. Don't worry if the new object uses only some of the fields at
  first.
- **Priority:** medium. It's often the missing idea behind a long parameter
  list.

### Primitive Obsession

*Fowler & Beck.*

- **Felt like:** money as a bare number, a status as a string compared in a
  dozen places, a range checked as `a > low && a < high` everywhere. A typo
  in one string broke something far away.
- **Count:**
  - strings or numbers standing for a kind or a status ("type codes"),
    compared in how many places;
  - the same check or formatting of one such value repeated.
- **Not a smell when:** the value really is just a number or a string, with
  no rules of its own.
- **Playbook:** Replace Primitive with Object. When a type code drives
  conditionals: Replace Type Code with Subclasses, then Replace Conditional
  with Polymorphism.
- **Priority:** medium. High when the type code drives switches in several
  places.

## Change preventers

These show in the history, not in one file. A snapshot of the code can't
reveal them, and history-based detection (Palomba et al.'s HIST) finds them
far more reliably than structure.

### Divergent Change

*Fowler & Beck.*

- **Felt like:** every unrelated feature needed you in the same file, and
  that's where the merge conflicts were. Fowler's example: "I will have to
  change these three functions every time I get a new database; I have to
  change these four functions every time there is a new financial
  instrument."
- **Count:** read the file's commit messages in the window (the heatmap's
  `--show`) and group them by the feature each is about. Many groups mean
  many reasons to change. Within the file, `git log -L <first>,<last>:<file>`
  per function, with the lines from `measure.py --show`, shows whether
  separate groups of functions change for separate reasons.
- **Not a smell when:** the file is a list by design (a registry, a
  changelog) where each change is one entry; or it only wires things
  together. Fowler notes it usually shows only after a few variations,
  because boundaries are unclear early in a program. So it's a smell of
  history, not of a first draft.
- **Playbook:**
  - when the two kinds of work form a sequence, Split Phase;
  - otherwise, Move Function into separate modules, after Extract Function
    where a function mixes both;
  - Extract Class when the module is a class.
- **Priority:** high. It's what makes a hot spot hot.

### Shotgun Surgery

*Fowler & Beck; Solution Sprawl in Kerievsky's catalogue.*

- **Felt like:** "every time you make a change, you have to make a lot of
  little edits to a lot of different classes." You missed one and found out
  at runtime.
- **Count:**
  - the heatmap's pairs, especially across layers, and files that pair with
    many others;
  - for the walkthrough's kind of change, the files a real recent commit of
    that kind touched (`git show --stat`);
  - recipes in the project's docs or agent instructions that list five or
    more steps to add one thing. A recipe like that is an admission.
- **Not a smell when:** the files are one feature with its own test and
  docs; or the pair is a boundary meant to be explicit, like an interface and
  its implementation changed together on purpose.
- **Playbook:**
  - Move Function and Move Field, to gather the scattered pieces into one
    module;
  - Combine Functions into Class, or Combine Functions into Transform;
  - Split Phase;
  - Inline Function or Inline Class, to pull pieces together first. Fowler:
    "we aren't afraid of creating something large as an intermediate step to
    reorganization."

  The usual end state is one place each feature declares itself, such as a
  registry or a definition that carries its own behaviour. For creation
  knowledge, Kerievsky's Move Creation Knowledge to Factory.
- **Priority:** high. Scattered changes are also what makes a task hard for
  an agent.

### Repeated Switches

*Fowler & Beck, second edition; Switch Statements in the first.*

- **Felt like:** adding a new kind meant hunting down every switch on it.
  "Whenever you add a clause, you have to find all the switches and update
  them."
- **Count:**
  - switches, `match`es or `if` cascades on the same kind, type or enum,
    across files;
  - type checks (`is X`, `instanceof`) outside the place that creates the
    objects;
  - in the history, how often new kinds are added.
- **Not a smell when:** there's one. Fowler narrowed the smell in the second
  edition: a switch "isn't the simple red flag that it often was fifteen
  years ago"; the smell is the same switch repeated. Martin's "one switch"
  rule (*Clean Code* G23) allows one switch per kind of selection, if its
  cases create the objects that replace the others.
- **Playbook:**
  - Replace Conditional with Polymorphism, or put each kind's data on its
    definition;
  - when the switch dispatches requests to actions, Kerievsky's Replace
    Conditional Dispatcher with Command;
  - when it picks an algorithm, Replace Conditional Logic with Strategy.

  Keep one factory.
- **Priority:** high when the history shows kinds being added; low
  otherwise. The cost is the effort each new kind takes, so with no new
  kinds there's nothing to save.

## State

### Hidden State Machine

*No established name. It's made of Temporary Field (Fowler & Beck), Hidden
Temporal Couplings (Martin, G31) and Kerievsky's Conditional Complexity.*

- **Felt like:** every new case meant another `if … and not X`, and
  rereading the whole function to make sure the other cases still worked.
  Bugs turned up in combinations nobody had thought of. A field was "set
  only in certain circumstances", and "trying to understand why a field is
  there when it doesn't seem to be used can drive you nuts" (Temporary
  Field). Calls had to happen in an order nothing enforced (Hidden Temporal
  Couplings).
- **Count:**
  - true/false fields, nullable fields, or a mode stored as a string or
    number, that conditions combine (`if loading and not paused`);
  - how many places set each one;
  - pairs that are never true together. Flags that exclude each other are
    states without names;
  - long functions that open with checks on those fields;
  - fixes in the history that add "and not X" to a condition.
- **Not a smell when:**
  - the flags are independent (every combination is valid), or there are
    only two;
  - one state field and one place switch on it already;
  - it's a table-driven machine, such as a parser, which is well understood
    as it is. Demeyer et al. warn that factoring out state objects there can
    make the code harder to read.
- **Playbook:**
  1. Name the states: one enum or state field instead of the flags (Replace
     Primitive with Object), with the old flags as questions about it.
  2. Put the transitions in one method that refuses illegal moves.
  3. For fields that only mean something in some states: Extract Class to
     give them a home, and Introduce Special Case for when they're not valid.
  4. If each state behaves very differently, and the transitions are
     complex and spread across methods: Kerievsky's Replace State-Altering
     Conditionals with State (the State pattern). Its stated cost is that it
     complicates a design whose transitions are already easy to follow, so
     stop at step 2 when that's enough.
  5. For calls that must happen in order, make each step return what the
     next needs, so the order can't be got wrong (Martin, G31).
- **Priority:** medium; high in a hot function whose history shows the "and
  not X" fixes.

### Global Data and Mutable Data

*Fowler & Beck, second edition.*

- **Felt like:** something changed a value, and nothing could tell you what
  or when.
- **Count:**
  - globals, singletons and static mutable fields, with how many files write
    each one;
  - fields written from many places;
  - variables reused for different things in one function.
- **Not a smell when:** the data is set once at start-up and never changes,
  which is relatively safe if the language can enforce it; or the variable's
  scope is a few lines.
- **Playbook:**
  - for global data: Encapsulate Variable, so every write goes through one
    place you can watch;
  - for mutable data: Split Variable, Separate Query from Modifier, Remove
    Setting Method, Replace Derived Variable with Query, Combine Functions
    into Class, and Change Reference to Value.
- **Priority:** medium; high when bugs in the history come from unexpected
  writes.

### Tramp Data

*A term from structured design: data passed through layers that don't use
it.*

- **Felt like:** adding one setting meant threading it through every layer
  between where it's set and where it's used. You missed one, and that thing
  ignored the setting.
- **Count:** references to the setting's name, in how many files; files that
  only receive it and pass it on; setters for it on many classes.
- **Not a smell when:** it's two or three layers, explicit on purpose
  (dependency injection by design); or it's hot code where a lookup would
  cost.
- **Playbook:** one source that users ask, with a notice when it changes.
  That's Encapsulate Variable on a deliberate, controlled global, plus an
  override for tests.
- **Priority:** medium. It tends to show up as a bug where one place ignores
  the setting.

## Couplers

### Insider Trading

*Fowler & Beck, second edition; Inappropriate Intimacy in the first.*

- **Felt like:** renaming a private field broke three other files and a dozen
  tests.
- **Count:**
  - uses of another object's private members (by the language's rules or its
    naming convention, such as `_x`, `#x`, `m_x`);
  - subclasses that know too much about their parents;
  - tools and tests calling private methods.

  Count the distinct members reached, and from where.
- **Not a smell when:** one deliberate test seam exposes them in one place;
  or the language makes privacy per module and the reach stays inside it.
- **Playbook:** Move Function, Move Field, Hide Delegate, and Replace
  Subclass with Delegate or Replace Superclass with Delegate. For tests and
  tools, route every reach through one seam, so a rename breaks one file.
- **Priority:** medium; a blocker when tests do it (see
  [Tests Tied to Internals](#tests-tied-to-internals)).

Feature Envy, Message Chains and Middle Man are in
[Fix in passing](#fix-in-passing).

## Duplication

### Duplicated Code

*Fowler & Beck.*

- **Felt like:** you fixed a bug, then met the same bug in its copy a week
  later. The copies had drifted slightly, so you weren't sure which one was
  right.
- **Count:**
  - `diff` two suspect functions or files and count the lines that differ;
  - the same body in how many places;
  - classes in parallel pairs, one pair per kind;
  - **semantic copies:** functions that do the same job under different code
    and names. Diffs and clone detectors miss these. For each function added
    in the window, search the codebase by what it does (its verb, its inputs
    and outputs) for one that already did it.
- **Not a smell when:**
  - there are two copies and they might diverge. The rule of three: wait for
    the third, since acting early risks the wrong abstraction;
  - code looks alike but changes for different reasons. Merging it ties two
    features together;
  - it's tests, where repetition keeps each test readable on its own.
- **Playbook:**
  - Extract Function, after Slide Statements to line the copies up;
  - Pull Up Method across subclasses;
  - for a semantic copy, delete it and call the original (Substitute
    Algorithm where the two differ).
- **Priority:** high for semantic copies in agent-written code (see
  [Smells of AI-written code](#smells-of-ai-written-code)); medium
  otherwise.

### Oddball Solution

*Kerievsky; Alternative Classes with Different Interfaces (Fowler & Beck) is
its class-level form; Inconsistency is Martin's G11.*

- **Felt like:** you couldn't remember which of the three ways was the
  current one, so you added a fourth.
- **Count:** the distinct ways one job is done (three ways to draw the same
  outline, two styles of passing a setting), and which is newest; classes
  that do the same job behind different method names.
- **Not a smell when:** the ways serve different needs.
- **Playbook:**
  1. Pick the best way.
  2. Move the others to it: Substitute Algorithm; Change Function
     Declaration and Move Function to unify interfaces, or Kerievsky's Unify
     Interfaces with Adapter.
  3. Say in the project's contributor or agent instructions which one to
     copy.
- **Priority:** medium, and rising. An agent copies whichever way it finds
  first, so every extra way spreads.

## Knowledge in the wrong place

### Misplaced Responsibility

*Martin's* Clean Code *G17; in layered code, domain rules in the view.*

- **Felt like:** after a change, the number shown on screen and the number
  actually charged differed. A simulation imported a view to learn a rule.
- **Count:**
  - domain rules (thresholds, formulas, limits) defined in views,
    controllers or handlers;
  - the same formula computed in two layers;
  - tools or tests importing a view to read a rule.
- **Not a smell when:** it's a presentation rule (layout, animation timing,
  colours) in a view.
- **Playbook:** Move Function to the domain layer and have the view ask it.
  Split Phase where one function both calculates and presents.
- **Priority:** medium; high when the two copies of a rule have already
  disagreed.

### Magic Literal

*Fowler's Replace Magic Literal; Magic Number in Wake's catalogue; Martin's
G25.*

- **Felt like:** changing a value meant a search and replace that caught some
  copies and missed others, including a label with "half price" typed into
  it.
- **Count:**
  - the same literal, meaning the same thing, in several files;
  - text that states a value ("1%", "x2", "30 days") beside code that holds
    it.
- **Not a smell when:** the same literal means different things (0, 1,
  common sizes), or two values are equal by coincidence.
- **Playbook:** Replace Magic Literal with a named constant or a field on the
  definition, and format the text from the value.
- **Priority:** low, and cheap; fix it alongside other work.

## Dispensables

### Speculative Generality

*Fowler & Beck; Kerievsky's refactorings away from patterns.*

- **Felt like:** to follow one call you went through an interface, a factory
  and an abstract base, each with one implementation, and changing one
  behaviour meant editing four files.
- **Count:**
  - interfaces or abstract classes with one implementation;
  - options never passed anything but their default;
  - layers that only forward;
  - configuration for things that never vary;
  - "the only users of a function or class are test cases."
- **Not a smell when:** the second case exists and is used, even if it's a
  fake in tests; it's the boundary to an outside system; or it's an extension
  point the project documents and uses. "If all this machinery were being
  used, it would be worth it. But if it isn't, it isn't."
- **Playbook:**
  - Collapse Hierarchy;
  - Inline Function and Inline Class (and so Lazy Element: a function or
    class that isn't earning its keep);
  - Change Function Declaration, to drop unused parameters;
  - Remove Dead Code;
  - Kerievsky's Inline Singleton.
- **Priority:** medium, and it applies to your own proposals too. Don't
  propose a layer for a second case that doesn't exist yet. Some models are
  prone to it: Anthropic's prompting guide says two of its own, Claude Opus
  4.5 and 4.6, "have a tendency to overengineer by creating extra files,
  adding unnecessary abstractions, or building in flexibility that wasn't
  requested."

### Dead Code

*Mäntylä's taxonomy; Martin's G9 and F4.*

- **Felt like:** you kept a function working through three changes, then
  found that nothing called it.
- **Count:**
  - functions with no callers. Search for the name across code, tests and
    tools, and as a string too;
  - flags that are always set the same way;
  - commented-out blocks;
  - scaffolding left from a task: debug output, temporary files, unused
    helpers.
- **Not a smell when:** it's public API used outside the repo; it's called by
  name through reflection, configuration or framework hooks; or it's an
  entry point.
- **Playbook:** Remove Dead Code.
- **Priority:** low effort, so do it when found, each removal checked by
  searching for callers.

## Fix in passing

The evidence ranks these lowest. Feature Envy, Message Chains and Middle Man
were rare in Palomba et al.'s releases, Feature Envy showed no measured
effect on effort, and one study found Refused Bequest went with *less*
effort. So none is ever an item of its own: fix one inside a method or class
you're already changing, with its playbook, and otherwise leave it. All are
Fowler & Beck's.

| Smell | Looks like | Not a smell when | Playbook |
|---|---|---|---|
| **Feature Envy** | a method that uses another object's data more than its own | it's a pattern that splits behaviour from data on purpose, such as Strategy or Visitor; the rule underneath is "Put things together that change together" | Move Function; or Extract Function on the envious part, then move that |
| **Message Chains** | `a.b().c().d()`, so a change anywhere in the chain breaks the caller | it's a fluent interface or a builder: one object returning itself | Hide Delegate; or Extract Function on what the chain's end is used for, then Move Function down the chain |
| **Middle Man** | a class whose methods only pass calls on, gaining one each time the class behind it does | it's a deliberate front for a subsystem, with few methods, that rarely changes; or an adapter for an outside API | Remove Middle Man; Inline Function. It's Message Chains' inverse: fixing one can produce the other |
| **Data Class** | fields and accessors with no behaviour, whose clients each repeat the same logic about them | it's a record on purpose: a data transfer object, a message, or the immutable result of one step of a Split Phase | Encapsulate Record; Remove Setting Method; then Move Function to bring the clients' logic in |
| **Refused Bequest** | a subclass overriding half its parent's methods to do nothing | usually: "Nine times out of ten this smell is too faint to be worth cleaning." It's strong only when the subclass doesn't want the parent's interface | Push Down Method and Push Down Field; Replace Subclass with Delegate or Replace Superclass with Delegate |
| **Comments** | a comment saying *what* a block does, or one the code contradicts | it says *why*, marks uncertainty, or documents an API | Extract Function named after the comment; Change Function Declaration; Introduce Assertion for a stated assumption |

## Tests

### Untested Code

*Feathers,* Working Effectively with Legacy Code *(2004), for whom legacy
code is "simply code without tests". A test that passes whatever the code
does is Meszaros's Neverfail Test.*

- **Felt like:** you changed one line and couldn't tell what else you'd
  broken, so you changed as little as you could and left the rest alone.
- **Count:**
  - for each hot file, the tests that reach it: search the tests for its
    module, class and function names, or use the project's coverage report
    if it has one;
  - its public functions that no test calls;
  - tests that can't fail: no assertion, an assertion loosened in the same
    commit as the code it checks (the heatmap's `--show` lists a test's
    commits too), or a test skipped for now.
- **Not a smell when:** another check the project trusts covers the change,
  such as snapshot comparisons or a simulation; the step is one the editor's
  automated refactorings make safely, such as a rename in a typed language;
  or the code is cold.
- **Playbook:** Feathers' order for changing code without tests: find the
  change points and the test points, break the dependencies in the way,
  write the tests, then change and refactor.
  1. Write characterization tests: run the code and assert what it does now,
     right or wrong, through what its callers use. They pin today's
     behaviour, so a bug they pin goes on the list as a small fix, not into
     the refactor.
  2. Where the code can't be put under test, break the dependency in the way
     with the smallest safe edit, such as Feathers' Extract Interface or
     Parameterize Constructor, using automated refactorings where they
     exist.
  3. For broad output (a report, a rendered screen, a file written), a
     snapshot of today's output is a quick pin.
- **Priority:** a blocker. An item on untested code starts with its pinning
  tests as its own first step, in their own commit; or it says plainly that
  its result can't be checked, and carries that risk. Pins matter most
  before a hierarchy refactoring, the kind Bavota et al. found brings in
  bugs most often (above).

### Tests Tied to Internals

*Fragile Test, from Meszaros's* xUnit Test Patterns*; Beck's test
desiderata call for tests that are "structure-insensitive".*

- **Felt like:** a refactor that changed no behaviour broke forty tests, so
  you stopped refactoring.
- **Count:**
  - tests calling private methods or reading private fields;
  - tests reaching nodes or objects by internal paths;
  - a test the heatmap lists as changing with several production files
    besides its own: a lead, not a finding. Read it. Calls to their private
    members or paths into their internals make it one; a broad test that
    follows features through those files, or a group it only follows,
    isn't;
  - a test that changes in most refactoring commits;
  - mocks with long lists of expected calls.
- **Not a smell when:** one deliberate seam, used by every test, holds the
  reach.
- **Playbook:** make the tests do what a user or caller does, through public
  behaviour. Route what's left through one seam, so a rename breaks one file.
  If private logic needs its own tests, Extract Class and test its public
  interface.
- **Priority:** a blocker. Clear it before the refactor it blocks, as its own
  step, or every later step will look like it broke something.

## Smells of AI-written code

Others have named the problem this catalogue answers. Kent Beck: "That giant
function? I just added another 20 lines to it." Birgitta Böckeler: an agent
has "no aesthetic disgust at a 300-line function, no intuition that 'we
don't do it that way here.'" Rodrigo Rosenfeld Rosas: "The agent never gets
lost, so the signal never fires."

Two studies have measured some of these so far: Huang et al. the first and
He et al. the third. The rest come from practitioners' reports and from what
two vendors, Anthropic and OpenAI, tell their own models to avoid, so take
the order as rough. And treat them as things to look for, not a verdict on
agents' code: in one study of agents' refactoring commits in 86 Java
projects, the agents brought in no more smells than developers did, as a
static analyser (DesigniteJava) counted them, with one agent, Cursor, the
exception (Ottenhof et al., 2026).

1. **Reimplemented helpers.** Agents "frequently disregard code reuse
   opportunities, resulting in higher levels of redundancy compared to human
   developers", while reviewers react to those pull requests *more*
   favourably than to people's (Huang et al., 2026). See the semantic copies
   under [Duplicated Code](#duplicated-code).
2. **[Additive-Only Growth](#additive-only-growth)**, below.
3. **Long functions and large files.** See [Long Function](#long-function)
   and [Large Class](#large-class). After projects took up Cursor, code
   complexity and static-analysis warnings rose and stayed up, and that
   complexity drove a later slowdown (He et al., 2025).
4. **Unrequested abstraction.** See
   [Speculative Generality](#speculative-generality).
5. **[Defence in the Wrong Place](#defence-in-the-wrong-place)**, below.
6. **Copied legacy patterns.** An agent copies the nearest example, good or
   bad, and it's asked to: OpenAI's guide for its Codex models says "follow
   existing patterns, helpers, naming, formatting". So a pattern not to copy
   has to be named, as Anthropic's guide for Claude Code asks projects to do
   in the agent's instructions: "an old pattern that's everywhere but that
   new code must not copy." See [Oddball Solution](#oddball-solution).
7. **Leftover scaffolding.** See [Dead Code](#dead-code).
8. **Tests that can't fail:** an assertion loosened to pass, or a test with
   none. See [Untested Code](#untested-code).

### Additive-Only Growth

- **Felt like:** nothing, and that's the trouble. By hand, the third time you
  added a branch to the same function you'd have stopped and restructured
  it. An agent adds the thirtieth.
- **Count:**
  - files and functions whose window commits are nearly all additions:
    lines added far above lines removed (`--show` and the heatmap's churn);
  - new branches or cases added to the same function in commit after commit
    (`git log -L <first>,<last>:<file>`, with the lines from
    `measure.py --show`);
  - no commit in the window that moved or extracted code out of it.
- **Not a smell when:** the file is a list by design, such as a table of
  definitions; or it's a new feature still being written.
- **Playbook:** whatever smell the growth has produced: usually
  [Long Function](#long-function), [Large Class](#large-class) or
  [Repeated Switches](#repeated-switches). The habit to build: make the
  change easy before the next addition (Beck's "make the change easy, then
  make the easy change").
- **Priority:** high in a hot file. It's the pattern behind most of the
  rest.

### Defence in the Wrong Place

- **Felt like:** a bug that should have crashed loudly was swallowed, and
  turned up far away as a wrong value. Meanwhile real input from outside went
  unchecked.
- **Count:**
  - `catch`/`except` blocks that swallow the error or return a default;
  - null checks on values that can't be null inside the code;
  - validation repeated at every layer;
  - entry points (input parsing, API handlers, file loading) with no
    validation.
- **Not a smell when:** the check is at a real boundary; or the error is
  documented and recoverable, and the caller is told.
- **Playbook:** remove checks for impossible cases (Introduce Assertion where
  the invariant matters); move validation to the boundary; let unexpected
  errors propagate to one handler that reports them. Two vendors tell their
  own models the same. OpenAI, for Codex: "do not add broad try/catch blocks
  or success-shaped fallbacks; propagate or surface errors explicitly rather
  than swallowing them." Anthropic, for Claude: trust internal code and
  framework guarantees, and only validate at system boundaries.
- **Priority:** medium; high where the history shows bugs that were hidden
  by a swallowed error.

## Smells travel together

They rarely come alone, and a cluster usually points at one missing idea:
something the code uses all the time but never named.

- A Long Function with flags is usually a Hidden State Machine. The missing
  idea is the state.
- Repeated Switches come with Shotgun Surgery. The missing idea is the
  kind's definition, carrying its own behaviour.
- A Large Class with Divergent Change often has a partner it always changes
  with. The missing idea is whatever the two keep exchanging.
- Tramp Data lacks a single source to ask.
- Data Clumps and Long Parameter Lists lack the type the values make
  together.

Name the missing idea in the item's title. "Name the states of a checkout"
says more than "Refactor CheckoutController", and it tells the next agent
what to copy.

The books and studies quoted here are listed in [sources.md](sources.md).
