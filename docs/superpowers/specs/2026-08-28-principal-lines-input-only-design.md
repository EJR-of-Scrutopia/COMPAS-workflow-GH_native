# Principal lines are input only, and Pattern alone previews them

Date: 2026-08-28. Sub-project 2 of 6 from the mould rework brainstorm of
2026-08-27. Branch feature/principal-lines-input off plugin main 803b8ab.
Implements section 10, first paragraph, of
docs/superpowers/specs/2026-08-27-res-spine-design.md, which is binding
on this document.

## 1. Why

A principal line is a decision. Param draws where the notched bars go;
the anchors do not decide it for him. The derivation on Supports was a
second author of the same fact: it ran whenever Pattern carried no runs,
so a definition that forgot its curves quietly got bars it never asked
for, and a definition that drew them badly got nothing and no word why.
Two authors of one fact is the failure the RES spine was built to end.

The red bars also drew nine times over. Pattern, Supports, Loads, TNA
Relax, TNA Solve, FD Solve, Display, Animate and Columns each painted the
same runs in the same red at the same weight, and with the solver's own
preview underneath, two components on one canvas showed each bar twice.
That is the "dual lining" Param saw. One owner, one drawing.

## 2. Decisions (binding)

1. Pattern's Principal Lines input `P` is the only way a principal run
   enters the contract. `PrincipalRunFinder.DeriveFromAnchors` and its
   private helpers (Adjacency, Strips, Order, StartsAlong, WalkAcross,
   Plan) are deleted. `FromCurves` and `Deduplicate` stay; Deduplicate is
   the safety net for two curves that snap to one run.
2. `P` flattens (`GH_DataMapping.Flatten`), exactly as Geometry `G` does,
   so curves referenced from a Rhino layer as a tree arrive as one list.
3. Pattern reports the match in three ways and no other:
   - No curves wired: no message. The FD path never sees any of this.
   - Curves wired, none matched: an Error, and Pattern emits nothing.
     A pattern whose bars were asked for and could not be placed is not
     the pattern that was asked for; a grey chain is louder than a red
     badge on one component. Param chose this over emitting the pattern
     with no runs.
   - Curves wired, some unmatched: a Warning naming how many of how many
     were dropped, and the pattern is emitted with the runs that matched.
   - Two or more curves snapped to the same run: a Remark saying that
     Deduplicate merged them into one bar. Today this case produced the
     "dropped" warning with the wrong explanation.
   The mapping from counts to severity and message is one pure function,
   `PrincipalRunFinder.Outcome(int supplied, int unmatched, int kept)`,
   returning `PrincipalOutcome(string Severity, string Message)` with
   Severity in `none`, `remark`, `warning`, `error`. `FromCurves` gains
   `out int unmatched`, the number of curves that caught fewer than two
   nodes, so the caller can tell a drop from a merge.
4. Pattern's message line shows the run count: `Mesh - 441V/840E, 2
   principal lines` (singular at one), unchanged when there are none.
5. Supports loses its Ribs `RB` input. It is the last input, so `PAT`,
   `A` and `Tol` keep their slots and no wire on a saved canvas moves; a
   wire into `RB` is dropped on load. The derive block goes, the anchored
   pattern carries the source pattern unchanged, and the message line is
   `N explicit anchors` only.
6. Pattern is the only component that previews principal runs. The red
   bars leave Supports, Loads, TNA Relax, TNA Solve, FD Solve, Display,
   Animate and Columns. Their `_previewPrincipal` / `_principalPreview`
   fields and the code filling them are deleted, and
   `TnaWorkflowPreview.ResultPrincipalLines` goes with them.
   `TnaWorkflowPreview.PrincipalLines` and `TopologyPrincipalLines` stay
   for Pattern. Animate and Columns still hand the bars out as their
   Principal Lines tree output, so the bars remain visible on the moving
   frame through Grasshopper's own output preview; what goes is the second
   red copy painted on top. `MouldGeometry.PrincipalRuns`, which reads the
   runs off a Result for the mould components, is untouched.
7. Every message that told the author to "set Ribs on Supports" now says
   only to draw Principal Lines on Pattern: Columns' no-runs warning,
   Animate's no-runs warning, and the `columns.principal_source`
   diagnostic ("resolved upstream by Pattern"). Doc comments on
   `PrincipalRunFinder` and `TnaWorkflowPreview` say one way in.
8. Component GUIDs, port order and every other port are unchanged.
   `ContractSchema.Current` and `ResultDto.ResultSchema` are unchanged;
   this sub-project touches no contract type.

## 3. Testing (binding)

Every check runs in the reflection smoke harness in tests/native_smoke
without launching Rhino. Four are added and two tables change:

- `SpineComponentContracts` expects Supports inputs `PAT`, `A`, `Tol`.
- `FlattenedInputs` expects Pattern inputs `0` and `4` flattened.
- `ValidateDerivationRemoved`: `PrincipalRunFinder` has no method named
  `DeriveFromAnchors` under any binding flags, and
  `TnaWorkflowPreview` has no method named `ResultPrincipalLines`. A guard
  against either creeping back.
- `ValidatePrincipalPreviewOwner`: over every component type the harness
  instantiates, an instance field of type `List<Line>` whose name contains
  "Principal" (ordinal, case-insensitive) exists on `PatternComponent`
  and on no other. This is the mechanical form of decision 6.
- `ValidatePrincipalOutcome`: drives `PrincipalRunFinder.Outcome` through
  reflection. `(0,0,0)` is `none`; `(3,1,2)` is `warning` and its message
  contains `1 of 3`; `(3,0,2)` is `remark` and its message contains
  `merged`; `(2,2,0)` is `error` and its message contains `No Pattern`;
  `(2,0,2)` is `none`.
- `ValidatePrincipalLineSnapping` and `ValidateRunDeduplication` keep
  passing unchanged; the persistent parameter count stays 12.

## 4. What breaks on the canvas

Only a definition that relied on derived lines. After install it shows
Columns' `columns.no_principal_runs` (and Diagnose's cross-check) until
principal lines are drawn into Pattern. A wire that ran into Supports'
`RB` port is dropped when the document loads. Nothing else moves.

## 5. Out of scope

Everything in sections 9 and 10 of the RES spine spec beyond its first
paragraph: the column sliders, Animate's frame-zero columns and perimeter
curves, Monitor's document 07 output set, Skin, Export. Any change to the
Python worker, the wire, or `DecodeAnalysisTopology`, which still carries
runs across the TNA path guarded by vertex count.

## 6. Constraints

No em dashes anywhere. Full absolute Windows paths in any reply. No
Co-Authored-By or AI attribution. Commit locally after every task; push
only on Param's word. Rebuild and install as the final step with Rhino
closed and tell Param to restart Rhino. Check for OneDrive name-clash
files before every build and commit. Another session holds an uncommitted
edit to plugin/native_v02/Components/DeliveryComponents.cs: never stage
that file, and add by explicit path only.
