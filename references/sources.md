# Sources

The books, studies and articles quoted in [smells.md](smells.md), the
skill's catalogue of smells, and in its scripts.

## Smells and refactorings

- Fowler & Beck, *Refactoring*, 2nd ed. (2018), ch. 3 "Bad Smells in Code"
  (publisher's excerpt):
  https://www.informit.com/articles/article.aspx?p=2952392. Catalog of
  refactorings: https://refactoring.com/catalog/
- Fowler, "Code Smell" (bliki): https://martinfowler.com/bliki/CodeSmell.html;
  "Flag Argument": https://martinfowler.com/bliki/FlagArgument.html
- Mäntylä & Lassenius, taxonomy of smells:
  https://mmantyla.github.io/BadCodeSmellsTaxonomy
- Kerievsky, *Refactoring to Patterns* (2004):
  https://www.informit.com/store/refactoring-to-patterns-9780321213358
- Martin, *Clean Code* (2008), ch. 17 "Smells and Heuristics".
- Wake, *Refactoring Workbook* (2003).
- Demeyer, Ducasse & Nierstrasz, *Object-Oriented Reengineering Patterns*,
  "Factor out State".
- Feathers, *Working Effectively with Legacy Code* (2004).
- Meszaros, *xUnit Test Patterns: Refactoring Test Code* (2007).

## Measures

- Lanza & Marinescu, *Object-Oriented Metrics in Practice* (2006), ch. 5:
  https://scg.unibe.ch/assets/files/47/mgckdeptwnul3k6wzkurax86qichae/Lanz06a-OOMIP-Chapter5.pdf
- Alves, Ypma & Visser, "Deriving Metric Thresholds from Benchmark Data"
  (ICSM 2010): https://doi.org/10.1109/ICSM.2010.5609747. Its table IV
  gives the thresholds quoted: unit size 30, 44 and 74 lines and McCabe 6,
  8 and 14 at the 70th, 80th and 90th percentiles; unit interfacing 2, 3
  and 4 parameters at the 80th, 90th and 95th.
- Oliveira, Valente & Lima, "Extracting Relative Thresholds for Source Code
  Metrics" (CSMR-WCRE 2014).
- Hindle, Godfrey & Holt, "Reading Beside the Lines: Indentation as a Proxy
  for Complexity Metrics" (ICPC 2008).
- PMD's design rules and their defaults:
  https://docs.pmd-code.org/latest/pmd_rules_java_design.html
- Checkstyle's ParameterNumber check, whose default maximum is 7, so it
  flags more than 7:
  https://checkstyle.sourceforge.io/checks/sizes/parameternumber.html
- Nagappan & Ball, "Use of Relative Code Churn Measures to Predict System
  Defect Density" (ICSE 2005).
- Tornhill, code-maat: https://github.com/adamtornhill/code-maat

## Studies of smells and refactoring

- Bavota et al., "When Does a Refactoring Induce Bugs? An Empirical Study"
  (SCAM 2012).
- Sjøberg et al., "Quantifying the Effect of Code Smells on Maintenance
  Effort" (TSE 2013).
- Palomba et al., "On the Diffuseness and the Impact on Maintainability of
  Code Smells" (EMSE 2018).
- Tufano et al., "When and Why Your Code Starts to Smell Bad (and Whether
  the Smells Go Away)" (TSE 2017), the extension of their ICSE 2015 paper
  "When and Why Your Code Starts to Smell Bad". The figures quoted come from
  the 2017 paper, which added how long smells survive and how they're
  removed.
- Palomba et al., "Mining Version Histories for Detecting Code Smells"
  (HIST; TSE 2015).

## AI-written code

- Huang et al., "More Code, Less Reuse" (2026): https://arxiv.org/abs/2601.21276
- He et al., "Speed at the Cost of Quality" (2025):
  https://arxiv.org/abs/2511.04427
- Beck, "Augmented Coding & Design" (May 2025):
  https://newsletter.kentbeck.com/p/augmented-coding-and-design
- Böckeler, "Harness engineering for coding agent users" (Apr 2026):
  https://martinfowler.com/articles/harness-engineering.html
- Rosenfeld Rosas, "AI agents and the refactoring that never happens" (Sep
  2026):
  https://www.rosenfeld.page/articles/programming/2026_09_02_ai_agents_and_the_refactoring_that_never_happens/
- Ottenhof, Penner, Hindle & Lutellier, "How do Agents Refactor: An
  Empirical Study" (MSR 2026): https://arxiv.org/abs/2601.20160. It finds
  that "agents are not introducing more code smells in refactoring commits
  than developers", Cursor the exception, counting smells with
  DesigniteJava. It isn't evidence that agents add needless layers: its
  Unnecessary Abstraction is among the agents' three commonest smells, but
  it gives no developers' figure for it, and DesigniteJava's rule for it is
  a class with no methods and at most five fields:
  https://github.com/tushartushar/DesigniteJava/blob/master/src/Designite/smells/designSmells/AbstractionSmellDetector.java
- Two vendors' guidance for their own models, quoted as evidence of what
  those models tend to do:
  - Anthropic, prompting best practices for Claude:
    https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/claude-prompting-best-practices;
    Claude Code best practices: https://code.claude.com/docs/en/best-practices
  - OpenAI, Codex prompting guide:
    https://developers.openai.com/cookbook/examples/gpt-5/codex_prompting_guide
