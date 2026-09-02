# COMPAS Workflow

Native C# Grasshopper plugin plus a Python studio backend, for robotic
formwork-free funicular vaulting. Every line here is loaded on every turn of
every session and subagent, so keep it short and keep it true.

## Standing constraints

- **No em dashes, ever.** Plain British prose in documents and comments.
- **Never add Co-Authored-By, AI attribution or generated-by lines** to any
  commit, file or document. Param owns this work.
- **Commit locally after every fix.** Never push. Pushing is Param's explicit
  call, every time.
- **`git add` by explicit path only.** Never `git add -A`, never `git add <dir>`.
- **Forces are kN unless stated otherwise.** Every conversion goes through
  `MonitorMath.ToNewtons`.
- **Build and install with Rhino CLOSED.** Verify it is not running first. After
  installing, tell Param to restart Rhino: an open session keeps the old `.gha`.
- **Always compile the Grasshopper csproj to scratch.** The test suite excludes it.
- **The `native_smoke` harness must be green** at the end of every task.

## The OneDrive clash trap

This repo syncs through OneDrive. A sync conflict during a write leaves a
`(# Name clash ... #)` copy beside the original, and **the build still passes**,
so it is a false-clean mechanism.

Before every build and every commit:

```
find . -name "*Name clash*" -not -path "./.git/*"
```

`ls **/*"Name clash"*` does NOT find them in subdirectories under Git Bash. Use
the `find` form.

**Resolve by CONTENT, never by which side carries the clash name.** Both
orderings occur and have been observed on this repo. Short source edits tend to
leave the NEW content in the clash file; long agent-authored documents tend to
leave a STALE snapshot there. Decide with: mtime, then line count, then grep for
a marker string from the most recent known edit. Move the loser to scratch
rather than deleting it.

## Subagents report evidence, not verdicts

Subagents here are collectors, not judges. The orchestrator does the reasoning.

**Re-derive before you check.** The failure mode of a collector is agreeing with
its brief, and quoting evidence does not prevent it. Work the answer out
yourself before looking at what the brief asserts. A result that contradicts the
brief is a blocking finding and the most valuable thing you can return.

**Run it rather than read it.** Where a claim can be tested by building, by
driving a function directly, or by counting output, do that instead of reasoning
about the source. This single rule accounts for most of what has been caught on
this project.

**Quote, do not summarise.** A description of code is not evidence; the code is.
Every `file:line` you give must actually contain the text you quote.

**Never report "no issues found."** Report what you read and what you saw.
Absence of a verdict is fine; a false all-clear is not.

**No confidence language.** No "looks correct", "should be fine", "properly
handled", "this is safe". Those words hide a judgement and destroy the
orchestrator's ability to make it.

**Report what you could not do.** Truncated reads, timeouts, files skipped for
size, permission failures. These are findings.

**Stay in scope.** Do not fix or refactor while collecting; it loses the evidence.

End every report with:

```
METHOD:            ran it / drove the function / read the source
COVERAGE:          files read, commands run, paths traversed
NOT CHECKED:       what you did not reach, and why
UNCERTAIN:         what you could not resolve, with the specific question
CONTRADICTS BRIEF: what disagrees with what you were told, or "nothing"
```

## Named checks

Cheap models lose most ground on unstated criteria and close most of the gap
when criteria are explicit. State the relevant ones in every dispatch. The
failure modes that actually recur here:

- a behavioural claim citing a `file:line` that does not say that
- a port or field referenced that does not exist
- a tolerance measured against a global median where it should be span-local
- tree alignment assumed rather than traced to the code that builds it
- a test that passes because the harness never exercised the new path
- an OneDrive clash file making a build false-green
- a port description that asserts a downstream behaviour nobody verified

## Dispatch and review discipline

Settled 2026-09-02 after the columns wave, where six blocking defects survived
per-task review. Each rule has a measured mechanism behind it, not a preference.

**1. A TASK REVIEWER ALWAYS GETS ITS BRIEF.** Never dispatch a reviewer told to
read the diff and not the brief. It was tried, to save tokens, and it cost three
real engine defects in one task. All three were DEVIATIONS FROM THE BRIEF: a
removed `Union`, a raw pre-guard snap, and a weld-tolerance skip that silently
broke a mirror gate. A reviewer whose job is "does this match the brief" cannot
do it without the brief. Measured: the tasks whose reviewers held the brief took
two fix rounds each and caught their own brief's contradictions; the task whose
reviewer did not took zero rounds and shipped three defects.

**2. GIVE EVERY IMPLEMENTER ITS INFRASTRUCTURE.** Free, and large. Grep once
before dispatching and put in the prompt: the exact line and anchor string where
a harness check belongs, and the verbatim build and run commands. This took the
last four tasks of a wave from twenty agents to five at no quality cost. An agent
left to find its own way around a 17,000-line file spends its turns on search,
and every turn resends the whole context.

**3. A NEW CHECK MUST BE PROVED ABLE TO FAIL.** Implementer AND reviewer both:
mutate the engine line the check covers, build, run, see RED, revert, verify the
revert by hash, and report the mutation with the message it produced.

  This is the highest-value rule here and NEITHER the cheap nor the expensive
  review had it before. In one wave a verifier widened a clearance by nearly
  double, another displaced every singular convergence by 1.4 kilometres, and a
  third disabled an entire engine pass. In all three cases the output stayed
  byte-identical and all 87 checks passed. GREEN MEANS ONLY THAT NOTHING TESTED
  WHAT YOU BROKE.

  Watch especially for a fixture that cannot discriminate what its own message
  claims. Three candidates at (-0.1, 0), (0, 0) and (0.1, 0) are collinear and
  symmetric, so a check asserting "the MEAN, not the bounding-box centre" passes
  identically under either, while reading as though it proved something.

**4. THE WHOLE-BRANCH REVIEW IS NOT NEGOTIABLE.** Strongest model, high effort,
three independent lenses, then a SEPARATE adversarial verifier per finding whose
default is to refute and which must REPRODUCE the failure to confirm it. Per-task
review has never caught what this catches. If a budget forces a choice, cut
TASKS, never this.

**5. NEVER RUN TWO AGENTS THAT MUTATE ONE TREE.** Parallel mutation testing
corrupted a working copy mid-wave and one agent watched a file change under it,
which could have falsified findings in either direction. Fan out for READING;
serialise anything that writes.

## Orchestrator responsibility

- Read the excerpts directly rather than trusting any `NOTE:` field.
- Treat every `NOT CHECKED:` and `UNCERTAIN:` as an open item. Decide explicitly
  whether to follow up or accept the gap on the record.
- A report containing no excerpts is a FAILED run, not a clean one. Re-dispatch
  with a narrower scope.
- Do the cross-file reasoning yourself. Collectors see fragments by design; the
  connections between fragments cannot be delegated.
- **Any number that determines a structural decision gets measured, not
  estimated.** Token counts, file sizes, percentages of a window, task counts.

## Context discipline

- **Never read a spec whole.** These run to 30,000 words. Grep for the section
  and read by offset. Whole-file reads belong to subagents, which each have their
  own window.
- **Every ruling hits a file and is committed before anything else proceeds.**
  The ledger is the memory, not a safety net. The documented worst failure of
  this pattern is a controller re-dispatching work already done.
- Subagents get the narrowest brief that makes the task possible. Never forward
  session context into a collector.

## Where things are

- Plugin source: `plugin/native_v02/Components/`
- Harness: the `native_smoke` project, `Program.cs`
- Specs: `docs/superpowers/specs/`
- Plans: `docs/superpowers/plans/`
- SDD ledgers: `.superpowers/sdd/<plan-basename>/progress.md` (git-ignored)
