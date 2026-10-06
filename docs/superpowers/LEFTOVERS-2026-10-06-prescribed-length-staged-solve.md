# Prescribed-length staged solve: what is left over

Written 2026-10-06 when the branch work finished. The implementation is in git;
this file holds what git history does not: the open decisions, the findings that
were deliberately deferred, and what the follow-on plan has to pick up.

Branch work: bc2a833..430fabf on feature/studio-finish, 19 commits, 16 files,
about 2,900 insertions. Suite 1097 passed, 5 skipped.

## Open decisions for the candidate

1. **The spool rope check is inert unless you set its breaking load.**
   `spool_rope_mbl` defaults to null meaning "same as the net cable", and because
   lead tension can never exceed cable tension, the net cable check always fires
   first, so the spool check cannot bind for any brief that omits the field. The
   trade study header nonetheless states that spool rope tension was checked.
   Either set the field in the real brief, which is the right answer since the
   spool rope is a different rope from the net cable, or make the defaulted case
   announce itself in the written file. Until then a spool rope thinner than the
   net cable is bought on a check that did no work.

2. **Confirm the two-rope architecture.** The capacity module now assumes the
   net cable is dead-ended at the sliding carriage and never passes through the
   reeve, while a separate spool rope carries the lead tension. That is what the
   Seven Spools design document describes. If the net cable is itself reeved, the
   net cable check is wrong and the pulley decision inherits the error.

3. **Four commits carry AI co-authorship trailers** (5a70149, a0d8755, fc3a2ca,
   93f8134), against your standing rule. They were made before the rule reached
   the subagents' briefs. Rewriting four unpushed commit messages is a history
   pass over a working tree that also holds another strand's uncommitted work, so
   it waits for you.

## Deferred, with reasons

- Task 1: minor (deferred): tension_for and rest_length_for use a bare float() so None or a
  string raises TypeError/ValueError rather than CableError, inconsistent with
  _finite_positive. Plan-mandated code.
- Task 1: minor (deferred): no error-path tests for tension_for, rest_length_for, or the
  rest_length/length validation inside force_density.
- Task 1: minor (deferred): the module docstring names "strain" as a conversion it owns but
  no strain function exists. Reword or add one if a later task needs it.
- Task 2: Ruling 7: the plan mandated a damped fixed-point update (q += damping * (target - q))
  and the implementer showed it diverges on the plan's own first test case, at damping 0.5,
--
- Task 2: minor (deferred): the report's stated safeguard against the fully slack false
  convergence is not the operative one; the np.any(slack) check is what refuses it, not the
  residual, so deleting that check would reintroduce the bug (prescribed.py:115-120).
- Task 2: minor (deferred): prescribed.py:87 uses the literal 1e-6 where _FLOOR exists.
- Task 2: minor (deferred): `damping` keeps its name, default and position but no longer means
  what the brief's rule meant, and the module docstring still describes the naive scheme with
  no mention of the step scaling, the Anderson mixing or that convergence is not guaranteed.
  Flag to the final review: a public parameter whose meaning silently changed.
- Task 2: minor (deferred): no test asserts units, tensions, lengths, iterations or movement,
  and units is a spec requirement; the EA and non-convergence refusals are untested.
- Task 2: minor (deferred): _RESIDUAL_TOLERANCE is the binding convergence condition but is
  private and unoverridable while the slacker movement_tolerance is exposed.
- Task 2: minor (deferred): prescribed.py:100 raises without `from error`, losing the cause chain.
- Task 2: minor (deferred): dead `session = None`; max_iterations=0 reports "moving inf mm per
  step"; a float budget prints as "10.7 iterations".
- Task 2: minor (deferred): solve_prescribed_lengths is ~110 lines; the Anderson block would read
  better as a private helper and would then be unit-testable without a solver.
- Task 2: counter-evidence recorded by the reviewer: heavier loads are fine (100, 1000, 10000 N
  per node converged in 12, 18, 27 iterations, worst per-member error 3e-10 or better; a soft
--
- Task 2: minor (deferred): _SLACK_PATIENCE = 50 is a hard-coded, undocumented, non-overridable
  heuristic; a valid net needing more than 50 consecutive slack iterations to recover would be
  refused as slack. No concrete failing net was shown.
- Task 2: fix round 2/5 (1 addressed, 0 open; commits fc3a2ca..93f8134)
- Task 2: minor (deferred): the slack advice always says "Shorten the rest lengths of the first
  set"; if registered_slack is empty the first set is the symptom set, so the advice misleads.
- Task 2: minor (deferred): "members 0 are" is plural for a single member, and the test hard-codes
  that wording.
- Task 2: complete (commits 5a70149..93f8134, review clean after 2 fix rounds)
- Task 3: review 1: spec gap (missing definition-of-record comment) + Important AI co-author
--
- Task 3: minor (deferred): no test covers the not-in-tension refusal, the ea size-mismatch
  refusal, or the reel_commands size-mismatch refusal; these are the safety-relevant branches.
- Task 3: minor (deferred): reel_commands docstring says "states" without saying they are rest
  lengths.
- Task 3: complete (commits 93f8134..93add58, review clean after 2 fix rounds)
- Task 4: review 1: spec compliant, 2 Important (untested u-endpoint branch of the equilibrium
--
- Task 4: minor (deferred): the residual is an L2 norm over the largest single load component
  rather than norm-to-norm, so it is blind to a small out-of-balance at a lightly loaded node.
- Task 4: minor (deferred): no test checks tensions, residual or units; the doubling test checks
  linearity only and would pass if the answer were wrong by a constant factor.
- Task 4: fix round 1/5 (3 addressed, 0 open; commits b856135..81fc98c). The re-reviewer
  independently re-derived the hand values (node at (500,0,-500) gives q = [1.5, 0.5]) and
--
- Task 4: minor (deferred): the redundant-net test checks the alternative state's vertical
  balance in code but its horizontal balance only by hand.
- Task 4: complete (commits 93add58..81fc98c, review clean after 1 fix round)
- Task 5: controller resolved the implementer's concern 3 (that tests only passed with
--
- Task 5: minor (deferred): CorrectionResult.residual_predicted defaults to 0.0, so a hand-built
  result reads as a perfect forecast; it should be required.
- Task 5: minor (deferred): the commanded-length slack path has no test.
- Task 5: minor (deferred): the RED command line is given only partially in the report (full
  pytest line shown for GREEN, not RED).
- Task 5: complete (commits 81fc98c..cb5fceb, review clean after 1 fix round)
- Task 6: complete (commits cb5fceb..23acf8b, review clean first pass, spec compliant, formula,
--
- Task 6: minor (deferred) FLAG TO FINAL REVIEW, higher value than its grade suggests because
  this module sets the acceptance line every other stage is judged against:
  (a) the deflection test recomputes the same formula longhand, so it would pass with a wrong
      formula or a wrong units convention provided the test repeated the mistake. The reviewer
--
- Task 6: minor (deferred): non-numeric input raises TypeError or a plain ValueError rather than
  FalseworkError, so a caller catching FalseworkError misses it.
- Task 6: minor (deferred): a zero load gives an acceptance line of exactly 0.0, which no net can
  meet; rib_deflection is right to allow it but acceptance_line should say so or refuse.
- Task 6: minor (deferred): Rib does not validate at construction; acceptance_line validates
  limit_ratio only after computing the deflection.
- Task 6: the implementer's report states the worked example as 5.25 mm where the inputs give
  4.32 mm. The code is right and the report is wrong, which is a reminder that report arithmetic
--
- Task 7: minor (deferred): the test helper _run_unloaded_no_target actually applies a 100 N load;
  only the target is absent, so the name misleads.
- Task 7: complete (commits 23acf8b..851b517, review clean after 1 fix round)
- Task 8: review 1: 4 Important (3 plan-mandated), task quality Needs fixes. The reviewer
--
- Task 8: minor (deferred): the slack/numerical-failure split is a string match on the
  PrescribedError text. It is correct today, but rewording _slack_message silently turns every
  slack outcome into "numerical failure" and no test asserts the slack binding. A PrescribedError
  subclass or a `kind` attribute would remove it.
- Task 8: minor (deferred): NaN or infinite `steps` raises ValueError/OverflowError from int(), and
  non-numeric input raises TypeError, escaping the RuntimeError rule.
- Task 8: minor (deferred): no test covers the "net went slack" or "numerical failure" bindings,
  nor breaching_factor being None for the "none" outcome.
- Task 8: INTERFACE CHANGE for Task 9: Capacity.limit_load is now limit_factor, and Capacity also
  carries breaching_factor, steps, max_factor, torque_margin, safety_factor and sheave_efficiency.
--
- Task 9: minor (deferred) FLAG TO FINAL REVIEW, two one-line tightenings the re-reviewer called
  optional: the JSON warning should say in plain words that a recommended row may fail rope bend
  fatigue or not fit the drum (today the reader must infer it from the checks_not_performed
  list), and the limit_factor unit note should say a 0 may mean "below one walk step" rather
--
- Task 9: minor (deferred): _check_grid consumes a generator grid value with len(list(...)), so a
  library caller passing an iterator gets an empty sweep with no complaint; the CLI always passes
  lists. The broad except in the script turns an internal bug into a one-line message. A NaN grid
  value aborts the write with a message that does not name the field.

## What the follow-on plan picks up

1. **The three adapters the spec names and this plan deliberately left out:** a
   Grasshopper component in `src/ananke_equilibrium` for designing on the sited
   Rhino model, and a studio runner extending `bench/studio/solve_stage.py` so
   Vaulted plays a staged run and exports the same register.

2. **The four geometric constraints the trade study discloses but does not check:**
   D over d (rope bend fatigue), drum width for single-layer winding, fleet angle,
   and carriage travel within the frame. None is computable from what `Mechanism`
   carries today: there is no rope diameter, no pulley or sheave diameter, no drum
   width and no frame geometry. Two of the three trade fronts drive toward the
   smallest drum with the most falls, which is exactly the corner those four
   constraints exist to forbid, so until they exist the sweep narrows a shortlist
   and cannot be the last word before ordering.

3. **The register is about half of what the spec describes.** Per cable it is
   missing turns at the drum, lead tension after the reeve, drum torque, motor
   torque after ratio and efficiency, the prestress floor and ceiling, and the
   slack flag. The whole per-node block is absent: target position, modelled
   position, deviation, and the column left for the measured position from the
   node markers, which is what the digital twin reads. This was a gap in the plan
   I wrote, not something the task reviews could catch, because each judged its
   own brief.

4. **The capacity sweep re-solves the identical nets for every grid row,** about
   0.55 s a row on a two-cable net, because nothing the walk solves depends on the
   mechanism. Solve once, cache per load factor, evaluate every mechanism against
   the cache. Replacing the linear walk with a bisection would also remove the
   quantisation that makes `limit_factor` 0 ambiguous.

5. **Three unverified figures from the spec** that must be settled before anything
   is ordered: the falsework deflection limits in ACI 347 and BS 5975, the minimum
   D over d against ISO 4308-1, and the fleet angle limit for the chosen drum.
   The sheave efficiency default of 0.98 is optimistic and should be measured on
   the rig.
