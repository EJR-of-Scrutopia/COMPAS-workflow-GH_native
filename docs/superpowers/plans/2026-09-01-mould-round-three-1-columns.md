# Mould plugin, round three: columns, skin and the readers merge

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to
> implement this plan task-by-task. Steps use checkbox syntax for tracking.

**Goal:** Land the mould plugin's third round on one branch, in one order: the columns engine decides a span's feet first, from that span's own notches, by one ladder of symmetry; the skin becomes buildable, with the rim, the seam, the crown cap and the force-aligned pattern all cut in the net's own terms; and Frame and Deconstruct merge into a single reader while Diagnose learns to read the whole document.

**Architecture:** Three phases on one branch, each of them self-contained in its own files and each ending green on the same reflection-driven `native_smoke` harness. Columns lives in `ColumnPlacement.cs`, one new function beside `MouldGeometry.BarLoads`, and `ColumnsComponent.cs`; skin lives in `SkinPatterns.cs`, `SkinComponents.cs` and `DeliveryComponents.cs`; the readers merge folds `FrameComponents.cs` into `VisualiseComponents.cs` and reshapes Diagnose, Import Pieces and Export. The readers merge lands LAST because it changes port names, port counts and GUIDs on the very components the columns and skin phases feed, and `ParameterIdentity.Mismatch` compares archived port NAMES as well as counts, so landing it earlier would make every intermediate build of the other two phases warn on Param's saved definitions for reasons that are about to change again.

**Tech Stack:** C# 12 (`LangVersion latest`, `Nullable enable`, `ImplicitUsings disable`) on .NET 8 targeting `net8.0-windows`, built with `UseWindowsForms` and `UseSystemDrawing`, deterministic, output as `Ananke.COMPAS.gha` version 0.2.0; RhinoCommon 8, Grasshopper and GH_IO referenced from `C:\Program Files\Rhino 8` and never copied local; icons embedded as resources from `plugin\icons\*.png`; and the Rhino-free reflection smoke harness `tests\native_smoke\Ananke.COMPAS.NativeSmoke.csproj`, a `net8.0-windows` console executable built with `TreatWarningsAsErrors`.

**Specs:**

- `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\docs\superpowers\specs\2026-09-01-columns-priority-design.md`
- `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\docs\superpowers\specs\2026-09-01-skin-buildability-design.md`
- `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\docs\superpowers\specs\2026-09-01-readers-merge-design.md`

## Global Constraints

Copied verbatim and binding on every task in this plan:

- Never add Co-Authored-By, AI attribution or generated-by lines to any commit, file or document.
- Commit locally after every task. Never push. Pushing is Param's explicit call alone.
- git add BY EXPLICIT PATH only. Never git add a directory, never git add -A.
- Before every build and every commit, scan for OneDrive clash files with
  find . -name "*Name clash*" -not -path "./.git/*"
  and resolve any found by CONTENT, not by which side carries the clash name. Both orderings occur.
- The plugin is built and installed with Rhino CLOSED. Verify Rhino is not running before installing.
- Forces are in kN unless stated otherwise. Every conversion goes through MonitorMath.ToNewtons.
- The native_smoke harness must be green at the end of every task. A task that leaves it red is not done.
- Always compile the Grasshopper csproj to scratch; the test suite excludes it.
- Prose in any document: plain British prose, no em dashes, no AI attribution.

## The three phases and the order between them

The forty-seven tasks below run in one continuous sequence, and that sequence is three phases.

- **Phase one, columns, Tasks 1 to 11.** The ladder of symmetry, the span's own terms, the foot groups, the crossings, the common mode and the merge, in `ColumnPlacement.cs`, `MouldComponents.cs` and `ColumnsComponent.cs`.
- **Phase two, skin, Tasks 12 to 32.** The rim and the force edges, the tracer, band splitting, the crown cap, the seam, the native line field, the force-aligned pattern and Skin's own ports, in `SkinPatterns.cs`, `SkinComponents.cs` and `DeliveryComponents.cs`.
- **Phase three, the readers merge, Tasks 33 to 47.** Frame and Deconstruct become one fifteen-port reader on a new GUID, Diagnose reads the whole document, and Import Pieces' and Export's diagnostics text becomes runtime messages, in `VisualiseComponents.cs`, `FrameComponents.cs`, `DiagnoseComponents.cs` and `DeliveryComponents.cs`.

Phases one and two touch disjoint files and neither depends on the other, so the only hard ordering between them is that they are not interleaved: finish one, leave the harness green, then start the next. Phase three must come after both. It retires two GUIDs, deletes a file, and changes port names and counts on components the first two phases hand geometry to, and the load-protection warning compares archived port names as well as counts, so a readers merge landed early would make every build of the columns and skin work warn on saved definitions about ports that are about to move again.

### The install policy, stated once

The phases do not close alike, and rather than leave that to be inferred from four scattered steps, every install in this plan is named here and no other task installs anything. There are FOUR, and each has a different reason.

1. **Task 11, after phase one, run by the CONTROLLER and not by the implementer of Tasks 1 to 10.** It runs after the whole-branch review of the columns work, so the installed `.gha` is the reviewed one. It is a hand-over as much as an install.
2. **Task 32 step 6, after phase two.** The skin wave writes its own walk list and Param reads it in Rhino, so the walk needs an installed plugin to walk. Phase two's standing commands say that no task inside Tasks 12 to 31 installs, and Task 32 is the exception the sentence points forward to.
3. **Task 44 step 1, inside phase three.** This one is not a delivery at all: Task 44 is a MANUAL MEASUREMENT in Rhino whose answer decides the message level in Tasks 45 and 46, and the measurement cannot be taken without a running Rhino holding the current build. It installs a mid-phase plugin knowingly.
4. **After Task 47, the final install and hand-over**, which is Task 47's own step 5 below. It is the one that matters to Param, because it carries the merged reader, the two retired GUIDs and the fifteen ports, and without it the branch's last `.gha` never reaches him.

Every one of the four runs with RHINO CLOSED and every one is followed by telling Param to restart Rhino, because an open session keeps the old `.gha` and the old worker.

## Phase one: columns, Tasks 1 to 11

**Goal:** A span's feet are decided first, from the span's own notches and the Type, by one ladder of symmetry; the common mode goes by subtraction rather than by a test; a crossing takes no notch away from either line and its load is counted once and in full; every tolerance is a formula in the span's own terms and the net median is gone from the engine's signature.

**Architecture:** All of it lives in `ColumnPlacement`, its only caller `ColumnsComponent`, one new function beside `MouldGeometry.BarLoads`, and the reflection-driven smoke harness. `Group` is replaced by the ladder of spec section 6. `Place` loses `medianPlanEdge` and gains the net's edge list, the untransversed pull per bar position and the whole incident pull per node. Bands are deleted entirely: `BuildLevel` cuts a span's trees into FOOT GROUPS by the ladder and places each group's foot at the plan mean of its nearest-to-centre candidate notches. `Symmetrise` subtracts each span's mean along-chord pull unconditionally, locates the aim mirror from the residual's sign change, pairs per tree by chord parameter and reports the residual. `MergeFeet` becomes weld, same-span central pair, and cross-line merge by connected components with the least-squares convergence.

**Tech Stack:** C# 12 on .NET 8 (`net8.0-windows`), Grasshopper/RhinoCommon 8 (managed only in tests), the Rhino-free reflection smoke harness in `tests/native_smoke`.

**Spec:** `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\docs\superpowers\specs\2026-09-01-columns-priority-design.md` (binding). It amends `docs/superpowers/specs/2026-08-30-columns-symmetric-type-design.md` sections 3.3, 3.4, 3.5 and 3.7 and, through it, `docs/superpowers/specs/2026-08-28-columns-two-sliders-design.md` sections 3.5 and 3.7. Everything in those two not amended stands, and spec section 2 lists what may not move at all.

**Position in the build order:** FIRST. This lands before the skin buildability work and well before the readers merge.

And, binding for this plan:

- The component GUID `c47a1e93-8b25-4d60-a1f7-6e29b3c05d84` never changes, nor do its name, its three ports, its preview or its colour. The Type value list keeps its six items and their VALUES and its item TEXT verbatim: `0 · own feet`, `1 · one central foot`, `2 · two feet`, `3 · three feet`, `4 · four feet`, `Auto` at `-1`.
- `MouldGeometry.AimFrom`, `MouldGeometry.MaxLeanDegrees = 60.0`, `MouldGeometry.LeanFromVertical`, `MouldGeometry.BarLoads` and `MouldGeometry.BarTransverse` are READ ONLY. Nothing in this plan edits them. Spec section 19 puts them out of scope; section 16 adds `NodeLoads` BESIDE `BarLoads`.
- `ColumnPlacement.ForkFraction = 0.65`, `PlumbDegrees = 2.0`, `AlignmentDegrees = 30.0`, `MaxGround = 4`, `MaxBranching = 3` keep their names and values.
- `plugin/native_v02/Contracts/MouldContracts.cs` is NOT edited. `GroundAsked`, `GroundPlaced`, `ForkFraction` and `ForksRaised = 0` keep their wire names and shapes in the block.
- Every member leaves the engine LOWER END FIRST, settled in `AddMember`. The fork lies ON the foot-to-main segment, lowered to `ForkFraction` of the tree's lowest notch height where the spec height would sit at or above it.
- Nothing in `ColumnPlacement.cs` may touch `Mesh`, `Curve` or `Vector3d.Unitize`: they P/Invoke `rhcommon_c` and the harness runs without Rhino. `Point3d`, `Vector3d`, `Vector3d.ZAxis`, `Length`, `DistanceTo` and the operators are managed and fine.
- Spec section 19 is out of scope: skin buildability, Animate, Frame, Deconstruct, the readers, Export, Skin, the icons, the panels, the component count, the ring tree's own rule, the shape of the two collision tests, the block contract, and the `tools/tree_forest` Python twin.

### File structure

| Path (relative to `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow`) | Responsibility |
| --- | --- |
| `plugin/native_v02/Components/ColumnPlacement.cs` (modify) | The ladder, the span frame, the foot groups, the convergence, the peel, the shared-node rule, the common mode, the merge, every new `Placement` and `Level` field. |
| `plugin/native_v02/Components/MouldComponents.cs` (modify, one addition) | `NodeLoads` beside `BarLoads`. Nothing else in this file changes. |
| `plugin/native_v02/Components/ColumnsComponent.cs` (modify) | The new `Place` call, the diagnostics of spec section 16, the Message, the two tooltips. |
| `tests/native_smoke/Program.cs` (modify) | `ValidateColumnPlacement`: the new fixtures of spec section 17 and every disposition of section 17.1. |

### The shared gate

Every "run the gate" step means exactly this, from PowerShell. It refuses a OneDrive clash file first, builds the plugin, then builds and runs the harness against the freshly built `.gha`.

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
$clash = Get-ChildItem -Path "$repo\plugin","$repo\tests","$repo\docs" -Recurse -Filter "*Name clash*" -ErrorAction SilentlyContinue
if ($clash) { $clash | ForEach-Object { $_.FullName }; throw "OneDrive clash file in the tree; resolve by CONTENT before building" }
dotnet build "$repo\plugin\native_v02\Ananke.COMPAS.Native.csproj" -c Release -v quiet --nologo
dotnet run --project "$repo\tests\native_smoke\Ananke.COMPAS.NativeSmoke.csproj" -c Release -- "$repo\plugin\native_v02\bin\Release\net8.0-windows\Ananke.COMPAS.gha"
```

A passing gate prints `0 warnings`, `Components discovered: 19`, `Parameters discovered: 12`, a `PASS` line for every check with no `FAIL`, and ends with `Native component smoke test passed; Rhino was not launched.` at exit code 0.

Commit messages follow the repo's `type(scope): sentence` style. Every `git add` names explicit paths.

### Spec coverage for this phase

| Spec section | Task |
| --- | --- |
| 2, what is preserved | Global Constraints, and Task 10's preservation pins |
| 3, order of operations | Task 3 (steps 1 and 3), Task 6 (step 4), Task 4 (steps 5 and 8), Task 7 (steps 6 and 7), Task 8 (step 10) |
| 4, the span's own terms and every tolerance | Task 3 |
| 5, the ladder | Task 1 |
| 6, notches into trees | Task 1 |
| 7, trees into foot groups | Task 4 |
| 8, where a foot stands | Task 4 (one span), Task 8 (the multi-span convergence, the guard, the merged snap) |
| 9, the common mode, the mirror, the pairing, the families, the residual | Task 7 |
| 10, where two lines touch | Task 2 (NodeLoads), Task 6 |
| 11, the peel | Task 4 (never moves a foot), Task 5 (as a pair), Task 8 (judged twice) |
| 12, welding, merging, standing close | Task 8 |
| 13, what the forces decide | no code: section 18.2 closed it, and Task 4's inversion is what honours it |
| 14, Type 0 and Auto | unchanged in rule; Task 3 replaces the Auto collision fixture, Task 8 brings Type 0 feet into the new merge |
| 15, degenerate spans | Task 5 |
| 16, engine surface, diagnostics and the component | Task 3 (signature), Task 9 (diagnostics, Message, tooltips) |
| 17, harness | Tasks 1 to 10, each fixture in the task that turns it green |
| 17.1, every existing case | Task 1 (the Branching 3 fork case), Task 3 (the collision-rule check, the Auto fixture), Task 4 (6817, 6962, 7002, 7047), Task 6 (6732 deleted, 6897, 7341), Task 7 (6566 and every AsymmetricSpans line), Task 8 (6860, 7092, 7115) |
| 18, what was ruled | Task 1 (fewest strays), Task 4 (the central column), Task 6 (the load fixed properly), Task 10 (the value-list inaccuracy named) |
| 19, out of scope | nothing in this plan touches it |
| 20, constraints | Global Constraints |

The items this phase's spec leaves open are gathered at the end of this plan, under "What the three specs leave open for Param".

---

### Task 1: The ladder, and where the strays sit

Spec section 6. `ColumnPlacement.Group` keeps its signature and the shape of its answer and is re-derived to FEWEST STRAYS, which is Param's ruling of 2026-09-01. Four rows move at Branching 3, m = 3, m = 7, m = 9 and m = 13, and none at Branching 1 or 2.

**Files:**
- Modify: `plugin/native_v02/Components/ColumnPlacement.cs:209-267` (the `Group` doc comment and body)
- Test: `tests/native_smoke/Program.cs`, inside `ValidateColumnPlacement`, in the `// ---- Grouping.` block at lines 5911 to 5937 (the `Grouped` and `Show` local functions stay; the pinned tables are appended after the `Grouped(0, 2)` case at line 5937)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `public static (int[][] Groups, int[] Mains) ColumnPlacement.Group(int count, int branching)` unchanged in signature, new in answer. Tasks 4 and 6 read its groups and mains.

- [ ] **Step 1: Write the pinned tables, red**

In `tests/native_smoke/Program.cs`, immediately after the existing

```csharp
        (int[][] none, _) = Grouped(0, 2);
        if (none.Length != 0)
            throw new InvalidOperationException("No notches group into nothing.");
```

insert:

```csharp
        // ---- THE LADDER TABLES (spec section 6), pinned verbatim for
        // B = 1, 2 and 3 and m = 1 to 13. Sizes are read along the span from
        // one anchor to the other. Fewest strays is PARAM'S RULING of
        // 2026-09-01; the ENGINE's own row is printed beside the spec's for
        // every count, so the rows that move are numbers in the record and
        // not a claim. A size of 1 is a stray at B = 2 and B = 3, where it is
        // a REMAINDER; at B = 1 it is the whole tree the slider asked for and
        // is not counted as one.
        string[] ladderOne = Enumerable.Range(1, 13)
            .Select(m => string.Join(",", Enumerable.Repeat(1, m))).ToArray();
        string[] ladderTwo =
        {
            "1", "1,1", "1,1,1", "2,2", "2,1,2", "1,2,2,1", "1,2,1,2,1",
            "2,2,2,2", "2,2,1,2,2", "1,2,2,2,2,1", "1,2,2,1,2,2,1",
            "2,2,2,2,2,2", "2,2,2,1,2,2,2",
        };
        string[] ladderThree =
        {
            "1", "1,1", "3", "2,2", "2,1,2", "3,3", "2,3,2", "1,3,3,1",
            "3,3,3", "2,3,3,2", "2,3,1,3,2", "3,3,3,3", "2,3,3,3,2",
        };
        // The SHIPPED engine's rows at Branching 3, for the record. Its rule
        // is "always take the smallest admissible k", so it never builds a
        // centre tree of three at all.
        string[] shippedThree =
        {
            "1", "1,1", "1,1,1", "2,2", "2,1,2", "3,3", "3,1,3", "1,3,3,1",
            "1,3,1,3,1", "2,3,3,2", "2,3,1,3,2", "3,3,3,3", "3,3,1,3,3",
        };
        string Sizes(int[][] g) => string.Join(",", g.Select(x => x.Length));
        int Strays(int[][] g, int branching) =>
            branching == 1 ? 0 : g.Count(x => x.Length == 1);
        var moved = new List<int>();
        for (int m = 1; m <= 13; m++)
        {
            foreach ((int branching, string[] table) in new[]
                { (1, ladderOne), (2, ladderTwo), (3, ladderThree) })
            {
                (int[][] g, int[] mains) = Grouped(m, branching);
                string got = Sizes(g);
                if (got != table[m - 1])
                {
                    throw new InvalidOperationException(
                        $"Branching {branching}, m = {m}: the ladder of spec section 6 lays the span out as [{table[m - 1]}]; "
                        + $"the engine laid it out as [{got}]. The shipped engine's row was [{(branching == 3 ? shippedThree[m - 1] : table[m - 1])}].");
                }
                if (g.Sum(x => x.Length) != m || g.SelectMany(x => x).Distinct().Count() != m)
                    throw new InvalidOperationException($"Branching {branching}, m = {m}: every notch is in exactly one tree; [{got}] is not a partition of {m}.");
                var reversed = g.Select(x => x.Length).Reverse().ToArray();
                if (!reversed.SequenceEqual(g.Select(x => x.Length)))
                    throw new InvalidOperationException($"Branching {branching}, m = {m}: the tree sizes are a PALINDROME about the row centre by index; [{got}] is not.");
                for (int j = 0; j < g.Length; j++)
                {
                    if (!g[j].Contains(mains[j]))
                        throw new InvalidOperationException($"Branching {branching}, m = {m}: the main of group {j} is one of its own notches.");
                }
                if (branching == 3 && table[m - 1] != shippedThree[m - 1])
                    moved.Add(m);
            }
        }
        if (!moved.SequenceEqual(new[] { 3, 7, 9, 13 }))
        {
            throw new InvalidOperationException(
                $"Fewest strays moves FOUR rows at Branching 3, m = 3, 7, 9 and 13, and none at Branching 1 or 2; it moved [{string.Join(",", moved)}]. "
                + "A future criterion change must not quietly move a fifth.");
        }
        // No changed row's stray count RISES: that is the property his ruling
        // was chosen for, and the retired "fewest remainder trees" failed it
        // at m = 5 and m = 11.
        foreach (int m in moved)
        {
            int before = shippedThree[m - 1].Split(',').Count(s => s == "1");
            int after = ladderThree[m - 1].Split(',').Count(s => s == "1");
            if (after > before)
                throw new InvalidOperationException($"Branching 3, m = {m}: the stray count rose from {before} to {after}; fewest strays never raises it.");
        }
        // The MAINS at m = 7 and m = 13 at Branching 3, because at those two
        // counts the TREE COUNT does not change and the mains are the whole
        // of what moves: 1, 3, 5 against the engine's 2, 3, 4, and
        // 1, 4, 6, 8, 11 against its 2, 5, 6, 7, 10.
        (_, int[] mainsSeven) = Grouped(7, 3);
        if (!mainsSeven.SequenceEqual(new[] { 1, 3, 5 }))
            throw new InvalidOperationException($"Branching 3, m = 7 lays out [2,3,2], whose mains are 1, 3, 5 against the engine's 2, 3, 4; got [{string.Join(",", mainsSeven)}].");
        (_, int[] mainsThirteen) = Grouped(13, 3);
        if (!mainsThirteen.SequenceEqual(new[] { 1, 4, 6, 8, 11 }))
            throw new InvalidOperationException($"Branching 3, m = 13 lays out [2,3,3,3,2], whose mains are 1, 4, 6, 8, 11 against the engine's 2, 5, 6, 7, 10; got [{string.Join(",", mainsThirteen)}].");

        // ---- HIS THREE CASES BY NAME (spec section 5, quoted). One stray
        // defers to the CENTRE notch; two strays are the two END notches with
        // nothing at the centre; three are the two ends AND the centre.
        void RequireStrays(int m, int branching, int[] expectedStrayGroups, string why)
        {
            (int[][] g, _) = Grouped(m, branching);
            int[] got = Enumerable.Range(0, g.Length).Where(j => g[j].Length == 1).ToArray();
            if (!got.SequenceEqual(expectedStrayGroups))
            {
                throw new InvalidOperationException(
                    $"Branching {branching}, m = {m}: {why}; the strays stand at group(s) [{string.Join(",", expectedStrayGroups)}] "
                    + $"and stand at [{string.Join(",", got)}].");
            }
        }
        RequireStrays(5, 2, new[] { 1 }, "ONE stray defers directly to the centre node and every other notch lies in a mirrored pair of trees");
        RequireStrays(6, 2, new[] { 0, 3 }, "TWO strays are the two end nodes and NOTHING sits in the centre");
        RequireStrays(7, 2, new[] { 0, 2, 4 }, "THREE strays are the two end nodes plus the centre");
        RequireStrays(5, 3, new[] { 1 }, "ONE stray at the centre: k = 1 leaves rem 2 and one stray, k = 3 leaves rem 1 and two");
        RequireStrays(8, 3, new[] { 0, 3 }, "TWO strays at the ends and nothing at the centre: m is even, so k is 0 and the half remainder is 1");
        // THREE strays is UNREACHABLE at Branching 3, and the check says why:
        // three strays needs k = 1 with a half remainder of one, and at every
        // such count k = 3 leaves none and wins (case r = 1 of the derivation).
        for (int m = 1; m <= 13; m++)
        {
            (int[][] g, _) = Grouped(m, 3);
            if (Strays(g, 3) >= 3)
                throw new InvalidOperationException($"Three strays is unreachable at Branching 3: it needs k = 1 with a half remainder of one, and at every such count k = 3 leaves NO stray and wins. m = {m} left {Strays(g, 3)}.");
        }
```

- [ ] **Step 2: Run the gate and read the failure**

Run the gate. It must fail with `Branching 3, m = 3: the ladder of spec section 6 lays the span out as [3]; the engine laid it out as [1,1,1].` That is the shipped rule "always take the smallest admissible k" being caught.

- [ ] **Step 3: Replace `Group`**

In `plugin/native_v02/Components/ColumnPlacement.cs`, replace the whole of `Group` (lines 209 to 267, doc comment included) with:

```csharp
        /// <summary>
        /// Positions 0..count-1, in BAR ORDER along the span, grouped into
        /// trees by THE LADDER of spec section 5: a span's stations are the
        /// CENTRE, then the outermost mirrored pair, then the next pair
        /// inward, and when n things are placed the centre station is
        /// occupied if and only if n is odd.
        ///
        /// Two properties constrain the layout before any counting begins,
        /// and neither reads a coordinate. The sequence of tree sizes is a
        /// PALINDROME about the row centre by index, so tree i and tree
        /// T-1-i hold the same number of notches. And a tree that STRADDLES
        /// the row centre has ODD size, because a straddling tree of even
        /// size has two equally inner notches and the choice between them is
        /// a coin toss that puts the fork off the centre.
        ///
        /// The centre tree size k is then chosen by FEWEST STRAYS, which is
        /// Param's ruling of 2026-09-01. A stray is a REMAINDER tree of one
        /// notch, not merely a tree of one notch: at Branching 1 every tree
        /// holds one notch and none of them is a stray. Where two admissible
        /// k leave equally few strays the SMALLER wins, which is what the
        /// shipped engine always picked, so on a tie no column moves; the
        /// tie is unreachable for Branching 1 to 3 and the clause is there
        /// for totality. Anyone raising Branching past three must revisit
        /// this method rather than leaning on the ladder's fourth rung.
        ///
        /// The MAIN notch of a group is its innermost, the one nearest the
        /// row centre by index, so mirrored groups have mirrored mains.
        /// </summary>
        public static (int[][] Groups, int[] Mains) Group(int count, int branching)
        {
            branching = Math.Min(Math.Max(branching, 1), MaxBranching);
            if (count <= 0)
                return (Array.Empty<int[]>(), Array.Empty<int>());

            int[] sizes = Layout(count, branching);
            var groups = new int[sizes.Length][];
            var mains = new int[sizes.Length];
            double rowCentre = (count - 1) / 2.0;
            int at = 0;
            for (int g = 0; g < sizes.Length; g++)
            {
                groups[g] = Enumerable.Range(at, sizes[g]).ToArray();
                int main = groups[g][0];
                double best = Math.Abs(main - rowCentre);
                foreach (int p in groups[g])
                {
                    double d = Math.Abs(p - rowCentre);
                    if (d < best - 1.0e-12)
                    {
                        best = d;
                        main = p;
                    }
                }
                mains[g] = main;
                at += sizes[g];
            }
            return (groups, mains);
        }

        /// <summary>
        /// The tree sizes along the span, anchor to anchor. Each half is
        /// tiled from the CENTRE OUTWARD with trees of size B and the
        /// leftover rem notches at the ANCHOR END form one tree of size rem,
        /// which is a stray when rem is 1. The remainder trees therefore land
        /// on the ladder's stations by construction: the centre tree when k
        /// is 1, and the two anchor-end trees when rem is not zero. There are
        /// at most three of them, which is why the ladder is never asked for
        /// four.
        /// </summary>
        private static int[] Layout(int count, int branching)
        {
            if (branching == 1)
                return Enumerable.Repeat(1, count).ToArray();

            // Admissible centre tree sizes: 0 when the count is even, 1 when
            // it is odd, and 3 when it is odd, B is at least 3 and there are
            // at least three notches to hold.
            var admissible = new List<int>();
            if ((count % 2) == 0)
                admissible.Add(0);
            else
                admissible.Add(1);
            if ((count % 2) == 1 && branching >= 3 && count >= 3)
                admissible.Add(3);

            int chosen = -1;
            int fewest = int.MaxValue;
            foreach (int k in admissible)
            {
                int halfLength = (count - k) / 2;
                int remainder = halfLength % branching;
                int strays = (k == 1 ? 1 : 0) + (remainder == 1 ? 2 : 0);
                if (strays < fewest || (strays == fewest && k < chosen))
                {
                    fewest = strays;
                    chosen = k;
                }
            }

            int hlf = (count - chosen) / 2;
            int rem = hlf % branching;
            var left = new List<int>();
            if (rem > 0)
                left.Add(rem);
            for (int i = 0; i < hlf / branching; i++)
                left.Add(branching);

            var sizes = new List<int>(left);
            if (chosen > 0)
                sizes.Add(chosen);
            for (int i = left.Count - 1; i >= 0; i--)
                sizes.Add(left[i]);
            return sizes.ToArray();
        }
```

- [ ] **Step 4: Run the gate green**

Run the gate. Every check passes. The three existing grouping pins are untouched by the change and stay green: `Grouped(9, 2)` is still `[0,1] [2,3] [4] [5,6] [7,8]` with mains `1,3,4,5,7`, `Grouped(8, 3)` is still `[0] [1,2,3] [4,5,6] [7]`, and `Grouped(5, 1)` is still five singles.

- [ ] **Step 5: Check the one fixture whose internals move**

`tests/native_smoke/Program.cs:7221` drives `Arch(9, 8.0, 5.0, 1.0)` at Branching 3, which is seven free notches: `[3,1,3]` becomes `[2,3,2]` with mains at bar positions 2, 4 and 6. Its two assertions are generic (every member lower end first; no node that is only ever a lower end stands above the ground) and both still hold, and the case it exists for still fires: the anchor-end tree now holds bar positions 1 and 2 with main 2 at z 3.75, so the spec's fork height is z 2.4375 while position 1 sits at z 2.1875, under it. Update the comment at line 7209 to read `Group(7,3) gives {0,1} with main 1 at z 3.75` in the span's own indexing and to name the new layout, then run the gate again.

- [ ] **Step 6: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/ColumnPlacement.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(columns): the ladder lays out a span by fewest strays"
```

---

### Task 2: The whole incident pull per node

Spec sections 10 and 16. A function BESIDE `BarLoads`, not a change to it: spec section 19 keeps `BarLoads` out of scope, which is why the head pull of section 10 is expressed as arithmetic over what the two return.

**Files:**
- Modify: `plugin/native_v02/Components/MouldComponents.cs`, inserted immediately after `BarLoads` ends at line 1594 and before the `MaxLeanDegrees` doc comment at line 1596
- Test: `tests/native_smoke/Program.cs`, a new block at the head of `ValidateColumnPlacement` after the `MethodInfo` lookups at line 5909

**Interfaces:**
- Consumes: `MouldGeometry.EdgeKey(int a, int b) -> long` (public static, already present at line 1625).
- Produces: `public static Vector3d[] MouldGeometry.NodeLoads(Point3d[] nodes, List<(int Other, double Force)>[] incident)`, one entry per net node whether or not any bar reaches it. Task 3 passes its output into `Place`; Task 6 does the head-pull arithmetic with it.

- [ ] **Step 1: Write the check, red**

In `tests/native_smoke/Program.cs`, after

```csharp
        double alignmentCap = (double)engine.GetField("AlignmentDegrees")!.GetValue(null)!;
```

insert:

```csharp
        // ---- MouldGeometry.NodeLoads (spec sections 10 and 16): the same
        // sum BarLoads takes, over every incident edge WITH NO EXCLUSIONS at
        // all. BarLoads leaves out the edges running ALONG the bar, on the
        // ground that a beam does not load itself; NodeLoads takes the node's
        // whole pull, which is what makes the head load at a shared node
        // countable exactly once. A function BESIDE BarLoads, never a change
        // to it.
        {
            MethodInfo nodeLoads = RequirePublicStatic(geometry, "NodeLoads");
            MethodInfo barLoads = RequirePublicStatic(geometry, "BarLoads");
            // Node 0 at the origin, a bar running 0-1 along +x, and two
            // infill cables to 2 at +y and 3 at -z. Every edge unit length,
            // every force 1, so each contributes a unit vector.
            Array netNodes = Array.CreateInstance(point3d, 4);
            netNodes.SetValue(P(0.0, 0.0, 0.0), 0);
            netNodes.SetValue(P(1.0, 0.0, 0.0), 1);
            netNodes.SetValue(P(0.0, 1.0, 0.0), 2);
            netNodes.SetValue(P(0.0, 0.0, -1.0), 3);
            Type pairType = typeof(ValueTuple<int, double>);
            Type listType = typeof(List<>).MakeGenericType(pairType);
            Array incident = Array.CreateInstance(listType, 4);
            for (int i = 0; i < 4; i++)
                incident.SetValue(Activator.CreateInstance(listType)!, i);
            void Join(int a, int b, double force)
            {
                object left = incident.GetValue(a)!;
                object right = incident.GetValue(b)!;
                left.GetType().GetMethod("Add")!.Invoke(left, new[] { Activator.CreateInstance(pairType, b, force) });
                right.GetType().GetMethod("Add")!.Invoke(right, new[] { Activator.CreateInstance(pairType, a, force) });
            }
            Join(0, 1, 1.0);
            Join(0, 2, 1.0);
            Join(0, 3, 1.0);
            var bar = new List<int> { 0, 1 };
            object whole = nodeLoads.Invoke(null, new object?[] { netNodes, incident })!;
            object excluded = barLoads.Invoke(null, new object?[] { bar, netNodes, incident })!;
            object wholeAtZero = ((Array)whole).GetValue(0)!;
            object excludedAtZero = ((Array)excluded).GetValue(0)!;
            if (((Array)whole).Length != 4)
                throw new InvalidOperationException($"NodeLoads is indexed by NET NODE, one entry for every node whether or not a bar reaches it; it returned {((Array)whole).Length} entries against 4 nodes.");
            if (Math.Abs(VX(wholeAtZero) - 1.0) > 1.0e-12 || Math.Abs(VY(wholeAtZero) - 1.0) > 1.0e-12 || Math.Abs(VZ(wholeAtZero) + 1.0) > 1.0e-12)
            {
                throw new InvalidOperationException(
                    $"NodeLoads takes the node's WHOLE incident pull with no exclusions: three unit cables to +x, +y and -z sum to (1, 1, -1); it read "
                    + $"({VX(wholeAtZero):0.#########}, {VY(wholeAtZero):0.#########}, {VZ(wholeAtZero):0.#########}).");
            }
            if (Math.Abs(VX(excludedAtZero)) > 1.0e-12 || Math.Abs(VY(excludedAtZero) - 1.0) > 1.0e-12 || Math.Abs(VZ(excludedAtZero) + 1.0) > 1.0e-12)
            {
                throw new InvalidOperationException(
                    $"BarLoads is unchanged and still leaves out the edges running ALONG the bar, so it reads (0, 1, -1); it read "
                    + $"({VX(excludedAtZero):0.#########}, {VY(excludedAtZero):0.#########}, {VZ(excludedAtZero):0.#########}). Spec section 19 keeps BarLoads out of scope.");
            }
            object isolated = ((Array)whole).GetValue(1)!;
            if (Math.Abs(VX(isolated) + 1.0) > 1.0e-12)
                throw new InvalidOperationException("Every node gets its own entry; node 1's single edge back to the origin pulls it (-1, 0, 0).");
        }
```

The `P`, `V`, `VX`, `VY` and `VZ` local functions are declared further down the method at lines 5942 to 5982. Move this block to sit immediately AFTER `double VZ(object v) => ...` at line 5982 rather than before them, so the locals are in scope.

- [ ] **Step 2: Run the gate and read the failure**

Run the gate. It must fail inside `RequirePublicStatic(geometry, "NodeLoads")` because no such method exists.

- [ ] **Step 3: Add `NodeLoads`**

In `plugin/native_v02/Components/MouldComponents.cs`, insert between the close of `BarLoads` at line 1594 and the `MaxLeanDegrees` doc comment at line 1596:

```csharp
        /// <summary>
        /// The node's WHOLE incident pull, taken once, with no exclusions at
        /// all: the same sum <see cref="BarLoads"/> takes over the node's
        /// incident edges, but over EVERY one of them, the edges running
        /// along a bar included.
        ///
        /// This exists so that the head load at a node held by several bars
        /// can be counted exactly once and in full. BarLoads excludes only
        /// its OWN bar's along edges, so at a node shared by bars A and B the
        /// two pulls each carry the infill plus the other bar's along edges,
        /// and their naive sum counts the infill TWICE. Given this whole
        /// pull, the head pull is the bars' pulls summed less (k - 1) times
        /// it, which recovers the node's infill exactly once.
        ///
        /// A function BESIDE BarLoads, never a change to it: spec section 19
        /// keeps BarLoads and BarTransverse out of scope.
        /// </summary>
        public static Vector3d[] NodeLoads(
            Point3d[] nodes,
            List<(int Other, double Force)>[] incident)
        {
            var pull = new Vector3d[nodes.Length];
            for (int i = 0; i < nodes.Length; i++)
            {
                var total = Vector3d.Zero;
                if (i < incident.Length && incident[i] is not null)
                {
                    foreach ((int other, double force) in incident[i])
                    {
                        if (other < 0 || other >= nodes.Length)
                            continue;
                        Vector3d step = nodes[other] - nodes[i];
                        double length = step.Length;
                        if (length <= 1.0e-12)
                            continue;
                        // MAGNITUDE, for the reason recorded in BarLoads: a
                        // Result's sign convention is not fixed and a TNA
                        // thrust network is the compression mirror of the net
                        // that will be built.
                        total += (Math.Abs(force) / length) * step;
                    }
                }
                pull[i] = total;
            }
            return pull;
        }
```

- [ ] **Step 4: Run the gate green**

- [ ] **Step 5: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/MouldComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(columns): NodeLoads, the node's whole incident pull taken once"
```

---

### Task 3: The span's own terms, and the engine's signature

Spec section 4 and the signature of section 16. `medianPlanEdge` is REMOVED so it cannot be read by accident; the net's edge list, the untransversed pull per bar position and the whole incident pull per node come in; every tolerance becomes a formula in the terms of the span, or the pair of spans, it applies to.

`pull` and `nodePull` are threaded and GUARDED here and are first READ in Task 6. Neither is optional and neither has a default: a null or short array is a programming error and not a fallback, because the head-pull arithmetic has no answer without them.

**Files:**
- Modify: `plugin/native_v02/Components/ColumnPlacement.cs` (`ClearanceFraction` doc at 53-54; a new `SpanFrame` class and `Frame` method after `Span` ends at line 73; `Placement.Clearance` at 157; `Place` at 637-750; `BuildLevel` signature at 921-928 and its clearance uses; `MergeFeet` at 1384-1453; `CountCollisions` at 1483-1541)
- Modify: `plugin/native_v02/Components/ColumnsComponent.cs:332-371` (keep the `BarLoads` array, call `NodeLoads`, pass `edges`, drop `MedianEdgeLength`)
- Test: `tests/native_smoke/Program.cs`: the `Run` local at 5963-5969, the `CountCollisions` block at 7404-7466, the Auto collision fixture at 7556-7591, and three new blocks

**Interfaces:**
- Consumes: Task 2's `MouldGeometry.NodeLoads(Point3d[], List<(int, double)>[]) -> Vector3d[]`; `MouldGeometry.ValidEdges(EquilibriumResultDto, int, out int[]) -> (int, int)[]` (already called in `ColumnsComponent` at line 256).
- Produces, and Tasks 4 to 10 all depend on these exact names:
  - ```csharp
    public static Placement Place(
        Point3d[] nodes,
        int[][] bars,
        (int, int)[] edges,
        int[] anchors,
        Vector3d[][] across,
        Vector3d[][] pull,
        Vector3d[] nodePull,
        int[][] perimeterLoops,
        double ground,
        int branching,
        int groundAsked)
    ```
  - `public sealed class SpanFrame` with public fields `Point3d P0, P1, M`, `double L, D, H, G`, `Vector3d C, N`, `int[] Positions`, `int[] Nodes`, `double[] Sigma`, `bool ChordZero`, `bool OneParameter`, and `double TauSnap`.
  - `public static SpanFrame Frame(Point3d[] nodes, int[][] bars, Span span, IReadOnlyList<int> freePositions)`
  - `public static int CountCollisions(Level level, Point3d[] netNodes, HashSet<int> anchors, double[] memberClearance)`
  - `Placement.Frames` (public `List<SpanFrame>`, aligned with `Placement.Spans`).
  - `Placement.Clearance` is GONE.

- [ ] **Step 1: Write the signature and span-local checks, red**

In `tests/native_smoke/Program.cs`, replace the `Run` local function at lines 5963 to 5969 with the new arity, and add the three checks. First the `Run` replacement:

```csharp
        object Run((Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) net, int[][] loops, int branching, int ground)
        {
            // The untransversed pull per bar and bar position, and the whole
            // incident pull per node, built so that the two stand in the
            // relation a REAL net puts them in, because spec section 10's
            // arithmetic reads both and cancels one against the other.
            //
            // The node's WHOLE pull is what the fixture declares at that node
            // in total, which is the SUM of the bar declarations there: a
            // notch held by two bars, each declaring a unit, carries two.
            // Each bar's UNTRANSVERSED pull at a node is that same whole pull,
            // because BarLoads excludes only the edges running ALONG that bar
            // and a hand-built fixture declares no force along one. So
            // pull[b][k] is nodePull[bars[b][k]] and NOT across[b][k].
            //
            // At a notch held by ONE bar the two are identical and equal to
            // the transverse array, so k is 1, the (k - 1) term vanishes, the
            // head pull is that bar's own untransversed pull unchanged, and
            // NO number in this file moves. At a notch held by two the head
            // pull comes out (pull_A + pull_B) - nodePull = nodePull, which is
            // the node's whole pull counted exactly ONCE and IN FULL, which is
            // the ruling of 2026-09-01. Setting pull[b][k] to across[b][k]
            // instead would make the two bars' pulls sum to the whole and the
            // (k - 1) term subtract the whole, leaving a head pull of ZERO at
            // every crossing in this file.
            Array nodePull = Array.CreateInstance(vector3d, net.Nodes.Length);
            for (int i = 0; i < net.Nodes.Length; i++)
                nodePull.SetValue(V(0.0, 0.0, 0.0), i);
            for (int b = 0; b < net.Bars.Length; b++)
            {
                Array barAcross = (Array)net.Across.GetValue(b)!;
                for (int k = 0; k < net.Bars[b].Length; k++)
                {
                    int node = net.Bars[b][k];
                    object had = nodePull.GetValue(node)!;
                    object add = barAcross.GetValue(k)!;
                    nodePull.SetValue(V(VX(had) + VX(add), VY(had) + VY(add), VZ(had) + VZ(add)), node);
                }
            }
            Array pull = Array.CreateInstance(vector3d.MakeArrayType(), net.Bars.Length);
            for (int b = 0; b < net.Bars.Length; b++)
            {
                Array barPull = Array.CreateInstance(vector3d, net.Bars[b].Length);
                for (int k = 0; k < net.Bars[b].Length; k++)
                    barPull.SetValue(nodePull.GetValue(net.Bars[b][k])!, k);
                pull.SetValue(barPull, b);
            }
            return place.Invoke(null, new object?[]
            {
                net.Nodes, net.Bars, net.Edges, net.Anchors, net.Across, pull, nodePull, loops, 0.0, branching, ground,
            })!;
        }
```

Then update every one of the 27 `Run(...)` call sites listed by `grep -n "Run(" tests/native_smoke/Program.cs` to drop the median argument: `Run(arch, Array.Empty<int[]>(), 1.0, 1, 0)` becomes `Run(arch, Array.Empty<int[]>(), 1, 0)`, and so on for each. The medians dropped are 1.0, 4.0, 2.0/3.0, 1.5, 2.0, 0.75 and 24.0.

Then insert, after the `InSpanFrame` local at line 6075:

```csharp
        // ---- THE SIGNATURE NO LONGER ACCEPTS A MEDIAN (spec section 4).
        // That is the strongest possible form of the span-local rule: a
        // tolerance scaled by the net's median plan edge is a median over
        // every edge in BOTH mesh directions and stands in no fixed ratio to
        // the notch spacing along any one bar. On a mesh refined along its
        // principal lines the bound became several whole notch spacings and
        // stopped discriminating; on one refined across them it collapsed to
        // exact coincidence.
        {
            string[] names = place.GetParameters().Select(p => p.Name!).ToArray();
            string[] wanted =
            {
                "nodes", "bars", "edges", "anchors", "across", "pull", "nodePull",
                "perimeterLoops", "ground", "branching", "groundAsked",
            };
            if (!names.SequenceEqual(wanted))
            {
                throw new InvalidOperationException(
                    $"ColumnPlacement.Place reads ({string.Join(", ", wanted)}); it reads ({string.Join(", ", names)}). "
                    + "medianPlanEdge is REMOVED so it cannot be read by accident, edges comes after bars so the call reads net first, "
                    + "and pull and nodePull sit immediately after across because they are the same measurement at three levels of exclusion.");
            }
            if (names.Any(n => n.Contains("median", StringComparison.OrdinalIgnoreCase)))
                throw new InvalidOperationException("No argument of Place may name a median.");
        }
```

- [ ] **Step 2: Add the two-density and the scale checks, still red**

Immediately after the block from Step 1, insert:

```csharp
        // ---- TOLERANCES ARE SPAN-LOCAL (spec section 4). One net holding
        // two spans of very different notch density, five notches over ten
        // metres and twenty-one over ten metres. Each span's answer must be
        // bit-identical to the same span placed ALONE, which no net-median
        // tolerance can manage.
        {
            (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) Row(int count, double y)
            {
                Array nodes = Array.CreateInstance(point3d, count);
                Array acrossBar = Array.CreateInstance(vector3d, count);
                var edges = new List<(int, int)>();
                for (int i = 0; i < count; i++)
                {
                    double s = (double)i / (count - 1);
                    nodes.SetValue(P(10.0 * s, y, 2.5 * 4.0 * s * (1.0 - s)), i);
                    acrossBar.SetValue(V(0.0, 0.0, -1.0), i);
                    if (i > 0)
                        edges.Add((i - 1, i));
                }
                Array across = Array.CreateInstance(vector3d.MakeArrayType(), 1);
                across.SetValue(acrossBar, 0);
                return (nodes, new[] { Enumerable.Range(0, count).ToArray() }, new[] { 0, count - 1 }, across, edges.ToArray());
            }
            double[] FeetAlone(int count, int type)
            {
                object placed = Run(Row(count, 0.0), Array.Empty<int[]>(), 1, type);
                object built = Get<object>(placed, "Built");
                var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
                var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
                int[] footNode = FootOfTree(built, trees.Length);
                return footNode.Select(f => X(levelNodes[f])).ToArray();
            }
            // The two spans on ONE net, five notches at y = 0 and twenty-one
            // at y = 40, far enough apart that no merge and no collision can
            // reach across.
            const int coarse = 7;
            const int fine = 23;
            Array bothNodes = Array.CreateInstance(point3d, coarse + fine);
            Array bothAcross = Array.CreateInstance(vector3d.MakeArrayType(), 2);
            var bothBars = new int[2][];
            var bothAnchors = new List<int>();
            var bothEdges = new List<(int, int)>();
            int offset = 0;
            foreach ((int count, double y, int b) in new[] { (coarse, 0.0, 0), (fine, 40.0, 1) })
            {
                Array acrossBar = Array.CreateInstance(vector3d, count);
                var bar = new int[count];
                for (int i = 0; i < count; i++)
                {
                    double s = (double)i / (count - 1);
                    bothNodes.SetValue(P(10.0 * s, y, 2.5 * 4.0 * s * (1.0 - s)), offset + i);
                    acrossBar.SetValue(V(0.0, 0.0, -1.0), i);
                    bar[i] = offset + i;
                    if (i > 0)
                        bothEdges.Add((offset + i - 1, offset + i));
                }
                bothBars[b] = bar;
                bothAcross.SetValue(acrossBar, b);
                bothAnchors.Add(offset);
                bothAnchors.Add(offset + count - 1);
                offset += count;
            }
            var together = (bothNodes, bothBars, bothAnchors.ToArray(), bothAcross, bothEdges.ToArray());
            foreach (int type in new[] { 0, 1, 2, 3, 4 })
            {
                object placed = Run(together, Array.Empty<int[]>(), 1, type);
                object built = Get<object>(placed, "Built");
                var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
                var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
                int[] footNode = FootOfTree(built, trees.Length);
                double[] alone = FeetAlone(coarse, type).Concat(FeetAlone(fine, type)).ToArray();
                for (int t = 0; t < trees.Length; t++)
                {
                    if (Math.Abs(X(levelNodes[footNode[t]]) - alone[t]) > 1.0e-12)
                    {
                        throw new InvalidOperationException(
                            $"Type {type}: a span's answer is a function of ITS OWN notches and nothing else, so a five-notch span placed beside a "
                            + $"twenty-one-notch one is bit-identical to the same span placed alone; tree {t} stands at {X(levelNodes[footNode[t]]):0.#########} "
                            + $"together against {alone[t]:0.#########} alone.");
                    }
                }
            }
            // And no absolute number has crept in: the same shape a thousand
            // times bigger puts every foot a thousand times further out.
            object small = Run(Row(11, 0.0), Array.Empty<int[]>(), 1, 2);
            Array bigNodes = Array.CreateInstance(point3d, 11);
            Array bigAcrossBar = Array.CreateInstance(vector3d, 11);
            var bigEdges = new List<(int, int)>();
            for (int i = 0; i < 11; i++)
            {
                double s = i / 10.0;
                bigNodes.SetValue(P(10000.0 * s, 0.0, 2500.0 * 4.0 * s * (1.0 - s)), i);
                bigAcrossBar.SetValue(V(0.0, 0.0, -1.0), i);
                if (i > 0)
                    bigEdges.Add((i - 1, i));
            }
            Array bigAcross = Array.CreateInstance(vector3d.MakeArrayType(), 1);
            bigAcross.SetValue(bigAcrossBar, 0);
            object large = Run((bigNodes, new[] { Enumerable.Range(0, 11).ToArray() }, new[] { 0, 10 }, bigAcross, bigEdges.ToArray()),
                Array.Empty<int[]>(), 1, 2);
            object smallBuilt = Get<object>(small, "Built");
            object largeBuilt = Get<object>(large, "Built");
            var smallNodes = ((IEnumerable)Get<object>(smallBuilt, "Nodes")).Cast<object>().ToArray();
            var largeNodes = ((IEnumerable)Get<object>(largeBuilt, "Nodes")).Cast<object>().ToArray();
            int[] smallFeet = FootOfTree(smallBuilt, 9);
            int[] largeFeet = FootOfTree(largeBuilt, 9);
            for (int t = 0; t < 9; t++)
            {
                double scaled = X(smallNodes[smallFeet[t]]) * 1000.0;
                if (Math.Abs(X(largeNodes[largeFeet[t]]) - scaled) > 1.0e-9 * Math.Max(Math.Abs(scaled), 1.0))
                    throw new InvalidOperationException($"Scaling the whole net by 1000 scales every foot by 1000; tree {t} stands at {X(largeNodes[largeFeet[t]]):0.###} against {scaled:0.###}.");
            }
        }
```

- [ ] **Step 3: Run the gate and read the failure**

Run the gate. It must fail on the signature check, naming the eleven parameters the spec states against the nine the engine has.

- [ ] **Step 4: Add the span frame to the engine**

In `plugin/native_v02/Components/ColumnPlacement.cs`, insert after the `Span` class closes at line 73:

```csharp
        /// <summary>
        /// One span read in its OWN terms, which is where every tolerance in
        /// this engine now comes from. Nothing here reads the net's median
        /// plan edge, and the argument that carried it is gone from
        /// <see cref="Place"/> so that it cannot be read by accident.
        /// </summary>
        public sealed class SpanFrame
        {
            /// <summary>Plan positions of the span's first and last node.</summary>
            public Point3d P0;
            public Point3d P1;
            /// <summary>Chord length in plan.</summary>
            public double L;
            /// <summary>Unit chord direction in plan.</summary>
            public Vector3d C;
            /// <summary>Plan normal to the chord.</summary>
            public Vector3d N;
            /// <summary>
            /// The chord midpoint. A coordinate origin and nothing more: no
            /// rule places a foot at it or measures a symmetry about it.
            /// </summary>
            public Point3d M;
            /// <summary>
            /// Plan bounding box diagonal over the two cut nodes and all the
            /// free notches, which is a length the span always has even when
            /// its chord has none.
            /// </summary>
            public double D;
            /// <summary>Bar positions of the free notches, in bar order.</summary>
            public int[] Positions = Array.Empty<int>();
            /// <summary>Net vertices of the free notches, in bar order.</summary>
            public int[] Nodes = Array.Empty<int>();
            /// <summary>Chord parameter per free notch, aligned with Nodes.</summary>
            public double[] Sigma = Array.Empty<double>();
            /// <summary>The span spacing in chord parameter.</summary>
            public double H;
            /// <summary>The same spacing as a LENGTH, H * L.</summary>
            public double G;
            /// <summary>L is zero by the bound of spec section 4.</summary>
            public bool ChordZero;
            /// <summary>Every notch falls at one chord parameter.</summary>
            public bool OneParameter;
            /// <summary>
            /// The chord parameter within which two candidate notches count
            /// as equidistant from a target: 1e-6 * H.
            /// </summary>
            public double TauSnap;
            /// <summary>
            /// The plan distance within which two feet of THIS span are the
            /// same point and become one node: 1e-9 * L.
            /// </summary>
            public double TauWeld;
        }

        /// <summary>
        /// The span's own frame. The chord parameters are NOT assumed to rise
        /// with bar order: a bar that is not plan-monotone disagrees, and
        /// nothing below reads an index where a parameter is meant or a
        /// parameter where an index is meant.
        ///
        /// The spacing is MEASURED rather than assumed, because a crossing, a
        /// free end or a crest that crowds its neighbours leaves the notches
        /// unevenly spread and the measured mean is then the span's own
        /// answer. It agrees exactly with the old 0.25 / (count + 1) form
        /// wherever the notches are uniform between the cuts.
        /// </summary>
        public static SpanFrame Frame(
            Point3d[] nodes, int[][] bars, Span span, IReadOnlyList<int> freePositions)
        {
            int[] bar = bars[span.Bar];
            var frame = new SpanFrame
            {
                P0 = nodes[bar[span.First]],
                P1 = nodes[bar[span.Last]],
                Positions = freePositions.ToArray(),
            };
            frame.Nodes = frame.Positions.Select(p => bar[p]).ToArray();

            double minX = Math.Min(frame.P0.X, frame.P1.X);
            double maxX = Math.Max(frame.P0.X, frame.P1.X);
            double minY = Math.Min(frame.P0.Y, frame.P1.Y);
            double maxY = Math.Max(frame.P0.Y, frame.P1.Y);
            foreach (int node in frame.Nodes)
            {
                minX = Math.Min(minX, nodes[node].X);
                maxX = Math.Max(maxX, nodes[node].X);
                minY = Math.Min(minY, nodes[node].Y);
                maxY = Math.Max(maxY, nodes[node].Y);
            }
            frame.D = Math.Sqrt(((maxX - minX) * (maxX - minX)) + ((maxY - minY) * (maxY - minY)));

            double dx = frame.P1.X - frame.P0.X;
            double dy = frame.P1.Y - frame.P0.Y;
            frame.L = Math.Sqrt((dx * dx) + (dy * dy));
            // A span's CHORD LENGTH IS ZERO when L <= 1e-9 * D. Where D is
            // itself zero, so that every node stands at one plan point, the
            // span is degenerate by the same rule.
            frame.ChordZero = frame.L <= 1.0e-9 * frame.D;
            if (frame.ChordZero)
            {
                frame.C = new Vector3d(1.0, 0.0, 0.0);
                frame.N = new Vector3d(0.0, 1.0, 0.0);
            }
            else
            {
                frame.C = new Vector3d(dx / frame.L, dy / frame.L, 0.0);
                frame.N = new Vector3d(-frame.C.Y, frame.C.X, 0.0);
            }
            frame.M = new Point3d(
                0.5 * (frame.P0.X + frame.P1.X), 0.5 * (frame.P0.Y + frame.P1.Y), 0.0);

            int m = frame.Nodes.Length;
            frame.Sigma = new double[m];
            for (int i = 0; i < m; i++)
            {
                frame.Sigma[i] = frame.ChordZero
                    ? 0.5
                    : (((nodes[frame.Nodes[i]].X - frame.P0.X) * frame.C.X)
                        + ((nodes[frame.Nodes[i]].Y - frame.P0.Y) * frame.C.Y)) / frame.L;
            }
            double smallest = m > 0 ? frame.Sigma.Min() : 0.0;
            double largest = m > 0 ? frame.Sigma.Max() : 0.0;
            frame.OneParameter = (largest - smallest) <= 1.0e-9;
            frame.H = (m >= 2 && !frame.OneParameter)
                ? (largest - smallest) / (m - 1)
                : 1.0 / (m + 1);
            frame.G = frame.H * (frame.ChordZero ? frame.D : frame.L);
            frame.TauSnap = 1.0e-6 * frame.H;
            frame.TauWeld = 1.0e-9 * (frame.ChordZero ? frame.D : frame.L);
            return frame;
        }
```

Note the two `ChordZero` fallbacks: a span with no chord still needs a length to scale G and TauWeld by, and its plan bounding box diagonal is the length it always has. Spec section 15 gives that span ONE foot at the plan mean of its free notches whatever the Type, which Task 5 builds; here the frame merely has to be finite.

- [ ] **Step 5: Change the signature and the clearances**

In `Place`, replace the parameter list and the clearance line:

```csharp
        public static Placement Place(
            Point3d[] nodes,
            int[][] bars,
            (int, int)[] edges,
            int[] anchors,
            Vector3d[][] across,
            Vector3d[][] pull,
            Vector3d[] nodePull,
            int[][] perimeterLoops,
            double ground,
            int branching,
            int groundAsked)
        {
            // Neither pull nor nodePull is optional and neither has a
            // default: a null or short array is a programming error and not a
            // fallback, because the head-pull arithmetic of spec section 10
            // has no answer without them.
            if (pull is null || pull.Length != bars.Length)
                throw new ArgumentException("pull is the untransversed pull per bar and bar position, one array per bar.", nameof(pull));
            if (nodePull is null || nodePull.Length != nodes.Length)
                throw new ArgumentException("nodePull is the whole incident pull per NET NODE, one entry for every node.", nameof(nodePull));
            if (edges is null)
                throw new ArgumentException("edges is the net's edge list, which decides which spans are adjacent.", nameof(edges));

            branching = Math.Min(Math.Max(branching, 1), MaxBranching);
            var anchorSet = new HashSet<int>(anchors);
            var placement = new Placement { GroundAsked = groundAsked };
```

Delete the `Clearance` field from `Placement` (line 157) and the `Clearance = clearance,` initialiser. Add to `Placement`:

```csharp
            /// <summary>
            /// Each span's own frame, aligned with <see cref="Spans"/>. Every
            /// tolerance in this engine is a formula in these terms.
            /// </summary>
            public List<SpanFrame> Frames = new();
```

In the span loop, build the frame beside the trees:

```csharp
            placement.Spans = Spans(bars, anchorSet, held);
            for (int s = 0; s < placement.Spans.Count; s++)
            {
                Span span = placement.Spans[s];
                int[] free = span.Free.Where(p => !held.Contains(bars[span.Bar][p])).ToArray();
                SpanFrame frame = Frame(nodes, bars, span, free);
                placement.Frames.Add(frame);
                (int[][] groups, int[] mains) = Group(free.Length, branching);
                for (int g = 0; g < groups.Length; g++)
                {
                    int[] positions = groups[g].Select(i => free[i]).ToArray();
                    int mainPosition = free[mains[g]];
                    var ordered = new List<int> { mainPosition };
                    ordered.AddRange(positions.Where(p => p != mainPosition));
                    var tree = new Tree
                    {
                        Bar = span.Bar,
                        Span = s,
                        Nodes = ordered.Select(p => bars[span.Bar][p]).ToArray(),
                        Load = ordered.Select(p => Math.Abs(across[span.Bar][p].Z)).ToArray(),
                    };
                    Vector3d sum = Vector3d.Zero;
                    foreach (int p in ordered)
                        sum += across[span.Bar][p];
                    tree.Resultant = sum;
                    foreach (int node in tree.Nodes)
                        held.Add(node);
                    placement.Trees.Add(tree);
                }
            }
```

Then replace every `clearance` argument passed to `BuildLevel` with nothing, and inside `BuildLevel` derive the per-tree spacing:

```csharp
        /// <summary>
        /// The tree's own span spacing as a LENGTH. The ring tree has no
        /// span, so its scale R is the smallest plan distance between two of
        /// its own rim notches, which is in its own terms and needs no net
        /// median.
        /// </summary>
        private static double SpacingOf(Placement placement, Point3d[] nodes, int tree)
        {
            Tree t = placement.Trees[tree];
            if (!t.Ring && t.Span >= 0 && t.Span < placement.Frames.Count)
                return placement.Frames[t.Span].G;
            double smallest = double.MaxValue;
            for (int i = 0; i < t.Nodes.Length; i++)
            {
                for (int j = i + 1; j < t.Nodes.Length; j++)
                {
                    double d = Math.Sqrt(MouldGeometry.PlanDistanceSquared(nodes[t.Nodes[i]], nodes[t.Nodes[j]]));
                    if (d > 0.0)
                        smallest = Math.Min(smallest, d);
                }
            }
            return smallest < double.MaxValue ? smallest : 1.0;
        }
```

and build the per-member clearance array before judging:

```csharp
            // The COLLISION CLEARANCE is 0.05 * g of the tree whose member is
            // being judged, and 0.05 * min(g_A, g_B) where two members of
            // different spans are judged against one another, which is the
            // minimum of their two clearances. This is a knowing change to a
            // measure that is not a placement rule: it will move collision
            // counts and with them Auto's choice on some nets.
            var memberClearance = new double[result.Members.Count];
            for (int mm = 0; mm < result.Members.Count; mm++)
                memberClearance[mm] = ClearanceFraction * SpacingOf(placement, nodes, result.MemberTree[mm]);
            result.Collisions = CountCollisions(result, nodes, anchors, memberClearance);
```

Change `CountCollisions` to take `double[] memberClearance`, using `Math.Min(memberClearance[i], memberClearance[j])` for the member-to-member test and `memberClearance[m]` for the net test. Update its doc comment to say the clearance is now the span's own and that the SHAPE of the two tests is unchanged, which spec section 19 puts out of scope.

- [ ] **Step 6: Make the feet-close clearance a per-pair number**

In `MergeFeet`, replace the single `clearance` with a per-foot spacing. The merge and weld rules themselves are Task 8's; here only the SCALE changes and the mirrored-pair merge keeps its present shape:

```csharp
        private static int[] MergeFeet(
            Placement placement,
            Point3d[] nodes,
            Point3d[] foot,
            double[] spacing,
            List<Point3d> levelNodes,
            List<double> footSpacing,
            out int merged,
            out int close)
```

with `spacing[t]` the tree's own g from `SpacingOf`, the mirrored-pair merge testing `gap <= 0.25 * Math.Min(spacing[t], spacing[partner])`, and `close` counting pairs of BUILT feet inside `0.25 * min` of the two feet's own spacings. Record the spacing of each built foot in `footSpacing` so the pairwise loop has both numbers; `footSpacing` is a `List<double>` and not a `List<int>` because a spacing is a length and `SpacingOf` returns a `double`.

THE WELD TEST is `gap <= tau * tau` on the SQUARED plan distance, with `tau` taken as `placement.Frames[tree.Span].TauWeld` for two feet of ONE span and `Math.Min(placement.Frames[a].TauWeld, placement.Frames[b].TauWeld)` for feet of two spans. Nothing here computes a tolerance out of `spacing` and a span's `h`: `SpanFrame.TauWeld` is already `1e-9 * L`, or `1e-9 * D` on a span whose chord is zero, which is exactly the number Task 8's welding rule names, and reading it off the frame keeps the one definition in one place.

- [ ] **Step 7: Update the component**

This is TWO separate replacements inside `plugin/native_v02/Components/ColumnsComponent.cs`, and the block BETWEEN them stands untouched. Lines 347 to 360, which compute `thrust`, `neighbours`, `perimeterIds`, `grouping` and `loops` for the free-rim test, are not edited: `loops` is passed to the new `Place` call and `thrust` is defined at 351 and read again at 394, so replacing the whole 332 to 371 span in one go would leave both undefined and the file would not compile.

FIRST REPLACEMENT, lines 332 to 345:

```csharp
                double alongToAnchors = 0.0;
                double acrossToColumns = 0.0;
                var across = new Vector3d[bars.Count][];
                var barPull = new Vector3d[bars.Count][];
                for (int b = 0; b < bars.Count; b++)
                {
                    // The untransversed pull is KEPT rather than discarded
                    // after BarTransverse: spec section 10 threads it through
                    // so the head load at a shared node is counted exactly
                    // once and in full.
                    Vector3d[] pull = MouldGeometry.BarLoads(bars[b], nodes, incident);
                    Vector3d[] transverse = MouldGeometry.BarTransverse(bars[b], nodes, pull);
                    for (int k = 0; k < bars[b].Count; k++)
                    {
                        alongToAnchors += (pull[k] - transverse[k]).Length;
                        acrossToColumns += transverse[k].Length;
                    }
                    barPull[b] = pull;
                    across[b] = transverse;
                }
                Vector3d[] nodePull = MouldGeometry.NodeLoads(nodes, incident);
```

The perimeter-loop block at lines 347 to 360 STANDS UNCHANGED.

SECOND REPLACEMENT, lines 361 to 371, the median line and the call itself, with `MouldGeometry.MedianEdgeLength` no longer computed for this component:

```csharp
                ColumnPlacement.Placement placement = ColumnPlacement.Place(
                    nodes,
                    bars.Select(b => b.ToArray()).ToArray(),
                    edges,
                    anchors.ToArray(),
                    across,
                    barPull,
                    nodePull,
                    loops.Select(l => l.ToArray()).ToArray(),
                    groundLevel,
                    branching,
                    type);
```

- [ ] **Step 8: Rewrite the collision-rule check and replace the Auto collision fixture**

At `tests/native_smoke/Program.cs:7404-7466`, the `Collisions` local passes a scalar. Change it to build and pass an array, one entry per member:

```csharp
            int Collisions(object level, double[][] netVertices, double clearance)
            {
                Array netNodes = Array.CreateInstance(point3d, netVertices.Length);
                for (int i = 0; i < netVertices.Length; i++)
                    netNodes.SetValue(P(netVertices[i][0], netVertices[i][1], netVertices[i][2]), i);
                object memberList = levelType.GetField("Members")!.GetValue(level)!;
                int count = (int)memberList.GetType().GetProperty("Count")!.GetValue(memberList)!;
                var perMember = new double[count];
                for (int i = 0; i < count; i++)
                    perMember[i] = clearance;
                return (int)countCollisions.Invoke(null, new object?[]
                {
                    level, netNodes, new HashSet<int>(), perMember,
                })!;
            }
```

Every assertion in that block stays exactly as it is. Then REPLACE the Auto collision fixture at lines 7556 to 7591 entire. Spec section 17 states plainly that it cannot survive: it drives a nine node arch eight wide at a median of 24 precisely so that 0.05 of the median is 1.2, and with the median gone that span's g is 1.0, the clearance is 0.05, and seven members a unit apart never collide. The replacement geometry is the spec's:

```csharp
        // ---- Auto prefers the level that does not collide (spec sections
        // 14 and 17). The OLD fixture cannot be built: it drove this arch at
        // a median plan edge of 24 so that 0.05 of the median was 1.2 and
        // seven plumb Type 0 members a unit apart collided six times. With
        // the median gone the span's g is 1.0, the clearance is 0.05, and
        // they never collide; the fixture's premise died with the median.
        //
        // The replacement is spec section 17's own geometry: the same arch
        // with two neighbouring interior notches crowded to 0.02 * g apart in
        // plan, a mesh the author can really produce, so that their two plumb
        // Type 0 members stand inside 0.05 * g and collide, while at Type 1
        // they share a foot, share an end and cannot. Type 0 still carries
        // the shortest load path, being plumb throughout, so Auto's
        // preference for the collision-free level is still what is measured.
        {
            var arch = Arch(9, 8.0, 5.0, 1.0);
            // Notches at bar positions 4 and 5 crowded to a fiftieth of the
            // spacing apart. g here is 1.0: seven free notches from chord
            // parameter 1/8 to 7/8 on a chord of 8, so h = (7/8 - 1/8) / 6
            // and g = h * 8 = 1.
            object node4 = arch.Nodes.GetValue(4)!;
            object node5 = arch.Nodes.GetValue(5)!;
            arch.Nodes.SetValue(P(X(node5) - 0.02, Y(node5), Z(node4)), 4);
            object placed = Run(arch, Array.Empty<int[]>(), 1, -1);
            var tried = ((IEnumerable)Get<object>(placed, "Tried")).Cast<object>().ToArray();
            if (tried.Length != 5)
                throw new InvalidOperationException($"Auto builds all five levels; it built {tried.Length}.");
            object AtLevel(int level) =>
                tried.FirstOrDefault(t => Get<int>(t, "Ground") == level)
                ?? throw new InvalidOperationException($"Auto must build every level; {level} is missing.");
            object zero = AtLevel(0);
            object one = AtLevel(1);
            if (Get<int>(zero, "Collisions") == 0)
                throw new InvalidOperationException("This fixture wants Type 0 to collide: two plumb members 0.02 * g apart, inside a clearance of 0.05 * g.");
            if (Get<bool>(zero, "Feasible"))
                throw new InvalidOperationException("Feasible means no collision, and Type 0 collides here.");
            if (Get<string>(zero, "Rule") != "collision")
                throw new InvalidOperationException($"A colliding level names the collision as its worst measure; it names '{Get<string>(zero, "Rule")}'.");
            if (Get<int>(one, "Collisions") != 0)
                throw new InvalidOperationException($"At Type 1 the crowded pair shares a foot and shares an end, so nothing can collide; it reports {Get<int>(one, "Collisions")}.");
            if (tried.Any(t => Get<double>(t, "LoadPath") < Get<double>(zero, "LoadPath")))
                throw new InvalidOperationException("Type 0 carries the shortest load path here, or the preference for a collision-free level is not being tested at all.");
            int winner = AutoWinner(tried);
            if (winner == 0)
                throw new InvalidOperationException("The recomputed winner is a collision-free level, and Type 0 is not one.");
            if (Get<int>(placed, "GroundPlaced") != winner)
                throw new InvalidOperationException($"Auto places the shortest load path among the levels with no collision, ties to the higher; that is {winner} and it placed {Get<int>(placed, "GroundPlaced")}.");
            Console.WriteLine($"      collision clearance 0.05 * g = 0.05 here against 0.05 * median = 1.2 before; Type 0 collisions {Get<int>(zero, "Collisions")}, Auto chose {winner}.");
        }
```

Spec section 17 also requires the cross-span case, two spans whose members come within `0.05 * min(g_A, g_B)` of one another, because at a twentieth of a spacing two members of ONE span can barely collide at all. Add it as a second block: two parallel nine-notch arches whose chords stand `0.03 * g` apart in plan, at Type 0, asserting the collision count the check computes itself from the two spacings.

- [ ] **Step 9: Record the feet-close scale change**

At the narrow bay fixture, `tests/native_smoke/Program.cs:7092-7113`, the FEET-CLOSE CLEARANCE is now `0.25 * g = 0.1667` against the old `0.05 * median = 0.0333`, a factor of five. That span is `SkewArch(7, 4.0, ...)`: five free notches at chord parameters 1/6 to 5/6 on a chord of 4, so h = 1/6 and g = 2/3. Add to the block:

```csharp
            const double bayG = 2.0 / 3.0;
            const double bayFeetClose = 0.25 * bayG;
            const double bayOldClearance = 0.05 * (2.0 / 3.0);
            Console.WriteLine($"      narrow bay feet-close clearance {bayFeetClose:0.###} (0.25 * g) against {bayOldClearance:0.###} (0.05 * median) before; FeetClose {Get<int>(built, "FeetClose")}.");
            if (Get<int>(built, "FeetClose") < 1)
                throw new InvalidOperationException("Feet that stand within the FEET-CLOSE clearance and stay two are counted, so the author can raise Type or space the lines; none was.");
```

- [ ] **Step 10: Run the gate green**

- [ ] **Step 11: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/ColumnPlacement.cs" "plugin/native_v02/Components/ColumnsComponent.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "refactor(columns): every tolerance in the span's own terms, and the net median gone from the signature"
```

---

### Task 4: Trees into foot groups, and where a foot stands on one span

Spec sections 7, 8.1, 8.3 (the single-span branch), 8.5 and 8.6. THE BANDS GO ENTIRELY. A foot's position becomes a function of the span's own notch positions, the span's tree count and the Type, and no tree's aim, load or resultant is consulted anywhere in it. That is the inversion the whole wave rests on.

The multi-span least-squares convergence of 8.2 to 8.4 is NOT built here. Spec section 8.3 uses the plan mean where the candidates come from ONE span only, and spec section 12 says the least-squares intersection is used for a span foot in exactly one place, the cross-line merge, which is Task 8.

**Files:**
- Modify: `plugin/native_v02/Components/ColumnPlacement.cs` (`Level.Banded` at 121-130; `BuildLevel` at 921-1121, the bands and the rebuild loop deleted; `BandIndex` at 1344-1357 deleted; the private `ChordParameter(Point3d[], Placement, int[][], Tree)` at 1314-1327 deleted with it)
- Modify: `plugin/native_v02/Components/ColumnsComponent.cs:416` and `:581` (`built.Banded` becomes `built.Gathered`)
- Test: `tests/native_smoke/Program.cs`: the band fixtures at 6817-6858, 6962-6993, 7002-7045 and 7047-7090, plus five new blocks

**Interfaces:**
- Consumes: Task 1's `Group`; Task 3's `Placement.Frames`, `SpanFrame` and `SpacingOf`.
- Produces, and Tasks 5, 8, 9 and 10 depend on these exact names:
  - `public static (int[][] Groups, int Central) FootGroups(int treeCount, int type)`, the groups holding TREE indices in bar order, `Central` the index of the tree extracted to stand alone or -1.
  - `Level.Gathered` (public `int`, RENAMED from `Banded`, counting the trees a level ASSIGNED to a shared foot BEFORE the peel runs).
  - `Level.CentralColumns` (public `int`, defined BY CONSTRUCTION as the trees `FootGroups` extracts by its "T is ODD and N is EVEN" clause, never by testing a distance to a plane).
  - `Level.SnapWorst` (public `double`, the largest snap distance as a fraction of its own span's g).
  - `private static Point3d GroupFoot(Point3d[] nodes, SpanFrame frame, IReadOnlyList<int> notchIndices, double ground, out double snapDistance)`

- [ ] **Step 1: Pin the foot group table, red**

Insert into `ValidateColumnPlacement`, after the ladder tables of Task 1:

```csharp
        // ---- THE FOOT GROUP TABLE (spec section 7), pinned for every T from
        // 1 to 13 against every N from 1 to 4. Pure counting, and what a
        // future change to the rule will trip over. Sizes are read along the
        // span; the CENTRAL column, the tree an ODD row at an EVEN Type
        // leaves standing alone, is a group of one in its own place and
        // Central names its tree index.
        {
            MethodInfo footGroups = RequirePublicStatic(engine, "FootGroups");
            (int[] Sizes, int Central) Groups(int trees, int type)
            {
                object r = footGroups.Invoke(null, new object?[] { trees, type })!;
                Type rt = r.GetType();
                return (((int[][])rt.GetField("Item1")!.GetValue(r)!).Select(g => g.Length).ToArray(),
                    (int)rt.GetField("Item2")!.GetValue(r)!);
            }
            (int T, int N, string Sizes, int Central)[] table =
            {
                (1, 1, "1", -1), (1, 2, "1", -1), (1, 3, "1", -1), (1, 4, "1", -1),
                (2, 1, "2", -1), (2, 2, "1,1", -1), (2, 3, "1,1", -1), (2, 4, "1,1", -1),
                (3, 1, "3", -1), (3, 2, "1,1,1", 1), (3, 3, "1,1,1", -1), (3, 4, "1,1,1", -1),
                (4, 1, "4", -1), (4, 2, "2,2", -1), (4, 3, "1,2,1", -1), (4, 4, "1,1,1,1", -1),
                (5, 1, "5", -1), (5, 2, "2,1,2", 2), (5, 3, "2,1,2", -1), (5, 4, "1,1,1,1,1", 2),
                (6, 1, "6", -1), (6, 2, "3,3", -1), (6, 3, "2,2,2", -1), (6, 4, "2,1,1,2", -1),
                (7, 1, "7", -1), (7, 2, "3,1,3", 3), (7, 3, "2,3,2", -1), (7, 4, "2,1,1,1,2", 3),
                (8, 1, "8", -1), (8, 2, "4,4", -1), (8, 3, "3,2,3", -1), (8, 4, "2,2,2,2", -1),
                (9, 1, "9", -1), (9, 2, "4,1,4", 4), (9, 3, "3,3,3", -1), (9, 4, "2,2,1,2,2", 4),
                (10, 1, "10", -1), (10, 2, "5,5", -1), (10, 3, "3,4,3", -1), (10, 4, "3,2,2,3", -1),
                (11, 1, "11", -1), (11, 2, "5,1,5", 5), (11, 3, "4,3,4", -1), (11, 4, "3,2,1,2,3", 5),
                (12, 1, "12", -1), (12, 2, "6,6", -1), (12, 3, "4,4,4", -1), (12, 4, "3,3,3,3", -1),
                (13, 1, "13", -1), (13, 2, "6,1,6", 6), (13, 3, "4,5,4", -1), (13, 4, "3,3,1,3,3", 6),
            };
            foreach ((int T, int N, string sizes, int central) in table)
            {
                (int[] got, int gotCentral) = Groups(T, N);
                string gotText = string.Join(",", got);
                if (gotText != sizes || gotCentral != central)
                {
                    throw new InvalidOperationException(
                        $"T = {T} at Type {N}: spec section 7 cuts the row into [{sizes}] with the central column at tree {central}; "
                        + $"the engine cut it into [{gotText}] with {gotCentral}. If T is at most N every tree is a group of one; if T is ODD and "
                        + "N is EVEN the middle tree by index is taken out as a group of ONE; then q is T2 / N, s is T2 mod N, s = 1 puts the "
                        + "extra on the CENTRE group and s = 2 puts one on each END group.");
                }
                if (got.Sum() != T)
                    throw new InvalidOperationException($"T = {T} at Type {N}: every tree stands in exactly one group; [{gotText}] holds {got.Sum()}.");
                if (!got.Reverse().SequenceEqual(got))
                    throw new InvalidOperationException($"T = {T} at Type {N}: the group sizes are a PALINDROME, so group j and group N-1-j take mirror-image feet; [{gotText}] is not.");
                int gathered = got.Where(x => x > 1).Sum();
                if (central >= 0 && got.Count(x => x == 1) < 1)
                    throw new InvalidOperationException($"T = {T} at Type {N}: the central column is a group of ONE in its own place; [{gotText}] holds none.");
            }
        }
```

A reader checking the T = 9, N = 2 row against the control arch should read `4,1,4` as the two shared feet of four trees each and the centre tree's own column between them, which is the three feet the harness has always pinned.

EVERY ROW OF THE N = 3 COLUMN WAS RE-DERIVED BY HAND against section 7's q and s before this table was written, because three of them were wrong in an earlier draft and all three were in that one column. The derivation, for the reader who wants to repeat it: T = 4 is even so nothing is extracted, q = 4 / 3 = 1 and s = 4 mod 3 = 1, so s = 1 puts the extra on the CENTRE group and the row is `1,2,1`, not the `2,1,1` an earlier draft carried, which is not even a palindrome and would have failed the assertion five lines below on its own data. T = 10 is even, q = 3 and s = 1, so the row is `3,4,3` and not `4,2,4`. T = 11 is odd but N = 3 is odd too, so no central tree is taken out; q = 3 and s = 2, so s = 2 puts one on EACH END group and the row is `4,3,4` and not `3,5,3`. The rest of the column checks out: 1, 2 and 3 fall to the T at most N branch; T = 5 gives q = 1, s = 2 and `2,1,2`; T = 6 gives q = 2, s = 0 and `2,2,2`; T = 7 gives q = 2, s = 1 and `2,3,2`; T = 8 gives q = 2, s = 2 and `3,2,3`; T = 9 gives q = 3, s = 0 and `3,3,3`; T = 12 gives q = 4, s = 0 and `4,4,4`; T = 13 gives q = 4, s = 1 and `4,5,4`.

Then, beside `FootOfTree` in the same method, declare the two helpers that Steps 5, 7 and 8 of this task and Steps 2 and 7 of Task 7 all call. `ExpectedFootGroups` is an INDEPENDENT reimplementation of spec section 7's counting, written out here rather than described, so that every fixture using it is comparing the engine against the spec and not against itself; `MouldLean` is `MouldGeometry.LeanFromVertical` reached by reflection, so a check can tell a peeled foot from a group foot without reimplementing the lean:

```csharp
        // Spec section 7's counting, reimplemented in the check. It must NOT
        // call the engine's FootGroups: three separate fixtures compare their
        // own expectation against the placed feet, and an expectation read
        // off the engine would agree with any engine at all. The table pinned
        // above is the third party both are measured against.
        int[][] ExpectedFootGroups(int treeCount, int type)
        {
            if (treeCount <= 0)
                return Array.Empty<int[]>();
            int n = Math.Min(Math.Max(type, 1), 4);
            if (treeCount <= n)
                return Enumerable.Range(0, treeCount).Select(i => new[] { i }).ToArray();
            int central = -1;
            int t2 = treeCount;
            if ((treeCount % 2) == 1 && (n % 2) == 0)
            {
                central = treeCount / 2;
                t2 = treeCount - 1;
            }
            int q = t2 / n;
            int s = t2 % n;
            var sizes = Enumerable.Repeat(q, n).ToArray();
            if (s == 1)
            {
                sizes[n / 2] += 1;
            }
            else if (s == 2)
            {
                sizes[0] += 1;
                sizes[n - 1] += 1;
            }
            var groups = new List<int[]>();
            int at = 0;
            for (int j = 0; j < n; j++)
            {
                if (central >= 0 && j == n / 2)
                    groups.Add(new[] { central });
                var members = new List<int>();
                while (members.Count < sizes[j])
                {
                    if (at == central)
                        at++;
                    members.Add(at);
                    at++;
                }
                groups.Add(members.ToArray());
            }
            return groups.ToArray();
        }

        MethodInfo leanFromVertical = RequirePublicStatic(geometry, "LeanFromVertical");
        double MouldLean(object foot, object notch) =>
            (double)leanFromVertical.Invoke(null, new[] { foot, notch })!;
```

`ExpectedFootGroups` returns TREE indices in bar order, exactly as the engine's does, and the check above pins the two against each other for every T and N, so a divergence between the two implementations is caught in one place rather than in whichever fixture happens to notice it. Assert that directly, immediately after the table loop:

```csharp
            for (int T = 1; T <= 13; T++)
            {
                for (int N = 1; N <= 4; N++)
                {
                    (int[] engineSizes, _) = Groups(T, N);
                    int[] mineSizes = ExpectedFootGroups(T, N).Select(g => g.Length).ToArray();
                    if (!engineSizes.SequenceEqual(mineSizes))
                        throw new InvalidOperationException($"T = {T} at Type {N}: the check's own reimplementation of section 7 reads [{string.Join(",", mineSizes)}] against the engine's [{string.Join(",", engineSizes)}]. The two must agree, or every fixture built on the reimplementation is measuring nothing.");
                }
            }
```

- [ ] **Step 2: Run the gate and read the failure**

Run the gate. It must fail inside `RequirePublicStatic(engine, "FootGroups")` because no such method exists.

- [ ] **Step 3: Add `FootGroups`**

In `plugin/native_v02/Components/ColumnPlacement.cs`, insert after `Layout`:

```csharp
        /// <summary>
        /// A span's T trees, IN BAR ORDER, cut into contiguous FOOT GROUPS by
        /// the ladder. Every tree of a group stands on that group's one foot.
        /// Nothing about a tree except its position in the row is read, and
        /// the row is the row <see cref="Group"/> built, so on a bar that is
        /// not plan-monotone the groups follow the bar and not the chord
        /// parameter.
        ///
        /// A span with fewer trees than the Type asks for places one foot per
        /// tree and no more; a foot with no tree is not built. A span of ODD
        /// tree count at an EVEN Type takes its middle tree out as a group of
        /// ONE, standing straight on its own foot, which is PARAM'S RULING of
        /// 2026-09-01: he objected to "just moving the standing coloumn for
        /// symmetry reasons away from center when it shold obviously default
        /// to center". Type names the number of GATHERED feet per span, so
        /// such a span shows N gathered feet and one further column.
        ///
        /// The returned Central is that tree's index, or -1 where the clause
        /// did not fire. It is defined BY CONSTRUCTION, never by testing a
        /// distance to a plane, because on an asymmetric notch row that foot
        /// is not on the plane and a positional test would need a bound
        /// nothing has given it.
        /// </summary>
        public static (int[][] Groups, int Central) FootGroups(int treeCount, int type)
        {
            if (treeCount <= 0)
                return (Array.Empty<int[]>(), -1);
            int n = Math.Min(Math.Max(type, 1), MaxGround);
            if (treeCount <= n)
                return (Enumerable.Range(0, treeCount).Select(i => new[] { i }).ToArray(), -1);

            int central = -1;
            int t2 = treeCount;
            if ((treeCount % 2) == 1 && (n % 2) == 0)
            {
                central = treeCount / 2;
                t2 = treeCount - 1;
            }

            int q = t2 / n;
            int s = t2 % n;
            var sizes = new int[n];
            for (int j = 0; j < n; j++)
                sizes[j] = q;
            if (s == 1)
            {
                // Only reachable at an ODD N, where there IS a centre station.
                sizes[n / 2] += 1;
            }
            else if (s == 2)
            {
                sizes[0] += 1;
                sizes[n - 1] += 1;
            }

            // Lay the groups along the span, stepping over the central tree
            // and inserting it as its own group at the middle of the row,
            // which is the only station a single thing can occupy without
            // choosing a side.
            var groups = new List<int[]>();
            int at = 0;
            for (int j = 0; j < n; j++)
            {
                if (central >= 0 && j == n / 2)
                    groups.Add(new[] { central });
                var members = new List<int>();
                while (members.Count < sizes[j])
                {
                    if (at == central)
                        at++;
                    members.Add(at);
                    at++;
                }
                groups.Add(members.ToArray());
            }
            return (groups.ToArray(), central);
        }
```

- [ ] **Step 4: Add the group foot and delete the bands**

Insert beside `FootGroups`:

```csharp
        /// <summary>
        /// Where a group's foot stands, on ONE span. Param's rule, quoted:
        /// "best is to take the closest points to center from the principle
        /// lines and then get them to all point inwards where they touch".
        ///
        /// THE GROUP'S CENTRE is (t_min + t_max) / 2, the midpoint of the
        /// stretch of chord the group's own notches occupy. Not the mean of
        /// all its parameters, not the middle index, and not any plane of the
        /// span: the midpoint of the stretch is the centre of the group's own
        /// piece of the principal line, which is what his phrase names, and
        /// it commutes with the mirror.
        ///
        /// THE CANDIDATES are the notches nearest that centre: one notch
        /// where it is nearer than every other by more than TauSnap, and
        /// every notch within TauSnap of the nearest distance otherwise. The
        /// foot is their plan MEAN. There is no further tie-break, because
        /// the mean of any set of tied candidates is well defined, is
        /// independent of the order they are listed in, and commutes with the
        /// mirror. On an evenly spaced row this reduces to the familiar
        /// answer: an ODD count gives one candidate, the middle notch; an
        /// EVEN count gives two, tied to the last bit.
        ///
        /// The least-squares system of spec section 8.3 is NOT solved,
        /// because the candidates come from one span. A single line does not
        /// need to be intersected with itself to find its own middle, and on
        /// a bar that curves gently in plan the two central notches' tangents
        /// are nearly parallel and meet hundreds of metres away toward the
        /// centre of curvature.
        ///
        /// A group with two tied candidates stands at their midpoint and is
        /// NOT snapped to either: snapping would move the foot half a notch
        /// spacing to a side chosen by nothing, and on the centre group it
        /// would move the one column Param ruled must stand straight. That is
        /// the single stated departure from the letter of his snap ruling and
        /// spec section 18.3 leaves it open for him.
        ///
        /// Every notch of the group is listed, whether it is OWNED or
        /// BORROWED at a shared node, because a borrowed notch is still a
        /// point on this line.
        /// </summary>
        private static Point3d GroupFoot(
            Point3d[] nodes,
            SpanFrame frame,
            IReadOnlyList<int> notchIndices,
            double ground,
            out double snapDistance)
        {
            double smallest = double.MaxValue;
            double largest = double.MinValue;
            foreach (int i in notchIndices)
            {
                smallest = Math.Min(smallest, frame.Sigma[i]);
                largest = Math.Max(largest, frame.Sigma[i]);
            }
            double centre = 0.5 * (smallest + largest);

            double nearest = double.MaxValue;
            foreach (int i in notchIndices)
                nearest = Math.Min(nearest, Math.Abs(frame.Sigma[i] - centre));

            double sumX = 0.0;
            double sumY = 0.0;
            int taken = 0;
            foreach (int i in notchIndices)
            {
                if (Math.Abs(frame.Sigma[i] - centre) > nearest + frame.TauSnap)
                    continue;
                sumX += nodes[frame.Nodes[i]].X;
                sumY += nodes[frame.Nodes[i]].Y;
                taken++;
            }
            var foot = new Point3d(sumX / taken, sumY / taken, ground);

            // The SNAP DISTANCE: how far the foot stands from the nearest
            // candidate notch, so that a coarse bar shows up as a coarse bar
            // rather than as a surprise.
            snapDistance = double.MaxValue;
            foreach (int i in notchIndices)
            {
                if (Math.Abs(frame.Sigma[i] - centre) > nearest + frame.TauSnap)
                    continue;
                snapDistance = Math.Min(snapDistance,
                    Math.Sqrt(MouldGeometry.PlanDistanceSquared(foot, nodes[frame.Nodes[i]])));
            }
            return foot;
        }
```

Then in `BuildLevel`, delete the whole `else` branch of `if (level == 0)`, from `var band = new int[trees.Count];` through the closing brace of the rebuild `while (true)` loop, and put in its place:

```csharp
            else
            {
                // THE INVERSION (spec section 3, step 8). No tree's aim, load
                // or resultant is consulted anywhere in here: a foot's
                // position is a function of the span's own notch positions,
                // the span's tree count and the Type. That is what makes a
                // foot stable under a solve change, and it is why the band
                // rule that rebuilt a foot from its surviving trees is gone
                // along with the bands.
                var spanTrees = new List<int>[placement.Spans.Count];
                for (int s = 0; s < spanTrees.Length; s++)
                    spanTrees[s] = new List<int>();
                for (int t = 0; t < trees.Count; t++)
                {
                    Tree tree = trees[t];
                    if (tree.FixedFoot is Point3d ringFoot)
                    {
                        foot[t] = ringFoot;
                        continue;
                    }
                    if (tree.Span >= 0 && tree.Span < spanTrees.Length)
                        spanTrees[tree.Span].Add(t);
                }

                for (int s = 0; s < spanTrees.Length; s++)
                {
                    List<int> row = spanTrees[s];
                    if (row.Count == 0)
                        continue;
                    SpanFrame frame = placement.Frames[s];
                    (int[][] groups, int central) = FootGroups(row.Count, level);
                    if (central >= 0)
                        result.CentralColumns++;
                    var notchIndex = new Dictionary<int, int>();
                    for (int i = 0; i < frame.Nodes.Length; i++)
                        notchIndex[frame.Nodes[i]] = i;
                    foreach (int[] group in groups)
                    {
                        var indices = new List<int>();
                        foreach (int j in group)
                        {
                            foreach (int node in trees[row[j]].Nodes)
                            {
                                if (notchIndex.TryGetValue(node, out int at))
                                    indices.Add(at);
                            }
                        }
                        if (indices.Count == 0)
                            continue;
                        Point3d placedFoot = GroupFoot(nodes, frame, indices, ground, out double snap);
                        foreach (int j in group)
                        {
                            foot[row[j]] = placedFoot;
                            // Gathered counts the trees the level ASSIGNED to
                            // a SHARED foot, BEFORE the peel runs, which is
                            // exactly what Banded counted. The centre tree
                            // standing alone takes no shared foot and is not
                            // one of them, which is what lets the component
                            // tell "some trunks stepped off" from "nothing
                            // gathered at all".
                            if (group.Length > 1)
                                result.Gathered++;
                        }
                        if (frame.G > 1.0e-12)
                            result.SnapWorst = Math.Max(result.SnapWorst, snap / frame.G);
                    }
                }

                // THE PEEL (spec section 11). A tree whose trunk from its
                // assigned foot to its main notch leans past the cap stands
                // instead on its Type 0 foot. A peel NEVER MOVES A FOOT: a
                // foot's position does not depend on the trees standing on
                // it, so the rebuild-and-rejudge loop the band rule needed is
                // gone with the bands, and a foot left with no trees is not
                // built.
                for (int t = 0; t < trees.Count; t++)
                {
                    if (trees[t].FixedFoot is not null)
                        continue;
                    double lean = MouldGeometry.LeanFromVertical(foot[t], nodes[trees[t].Nodes[0]]);
                    if (lean <= MouldGeometry.MaxLeanDegrees + 1.0e-9)
                        continue;
                    foot[t] = own[t];
                    result.Peeled++;
                }
            }
```

Rename `Level.Banded` to `Level.Gathered`, rewrite its doc comment to the paragraph above, and add beside it:

```csharp
            /// <summary>
            /// Trees standing alone in the middle of an ODD row at an EVEN
            /// Type, by the clause of spec section 7. Counted BY
            /// CONSTRUCTION and never by testing a distance to a plane.
            /// </summary>
            public int CentralColumns;
            /// <summary>The largest snap distance as a fraction of its own span's g.</summary>
            public double SnapWorst;
```

In `ColumnsComponent.cs`, change `built.Banded` to `built.Gathered` at lines 416 and 581 so the file compiles; the diagnostic wording is Task 9's.

The peel here does NOT yet take its mirror partner with it. That is Task 5, whose fixture is written against exactly this state.

- [ ] **Step 5: Re-pin the four band fixtures**

Four dispositions from spec section 17.1, each edited in place.

1. `tests/native_smoke/Program.cs:6817-6858`, the plan-curved bar at Type 2. RE-PINNED to a number this spec states: eight trees, two groups of four, each group's two TIED CENTRAL NOTCHES meaning to chord `(-2, 128/81)` and `(2, 128/81)`. Replace `centroidAcross = 40.0 / 27.0` with `const double groupAcross = 128.0 / 81.0;`, use it in both comparisons, and rewrite the message to say the old pin was the CENTROID OF FOUR MAINS and that a group centre is not that.

   THE SINGLE-SPAN CONVERGENCE NEVER SOLVES A LEAST-SQUARES SYSTEM, and spec section 17 asks that to be asserted rather than described. Add to this block, and to the Type 1 block of item 2 below, the assertion that the placed foot equals the plan MEAN of its own candidates EXACTLY. The check computes the candidates itself from the notch row, by the nearest-to-centre rule of 8.1, so it is not comparing the engine with itself; a version that intersected a curved bar's own tangents instead would miss the mean by up to one notch spacing on this fixture, which is what makes the assertion worth taking:

```csharp
            // 8.3's rule, asserted and not described: the candidates come
            // from ONE span, so the foot is their plan MEAN and no system is
            // solved. On a bar curving in plan the two central notches'
            // tangents are nearly parallel and meet hundreds of metres away
            // toward the centre of curvature, so a version that intersected
            // them would land nowhere near this number.
            void RequireFootIsCandidateMean(
                (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) net,
                object placed, int type, int tree)
            {
                object built = Get<object>(placed, "Built");
                var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
                var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
                int[] footNode = FootOfTree(built, trees.Length);
                int[][] groups = ExpectedFootGroups(trees.Length, Math.Max(type, 1));
                int[] group = groups.First(g => g.Contains(tree));
                double[] sigma = group
                    .Select(j => ChordParameterOfTree(placed, net, j))
                    .ToArray();
                double centre = 0.5 * (sigma.Min() + sigma.Max());
                double nearest = sigma.Min(s => Math.Abs(s - centre));
                int[] candidates = Enumerable.Range(0, group.Length)
                    .Where(k => Math.Abs(sigma[k] - centre) <= nearest + 1.0e-12)
                    .Select(k => group[k]).ToArray();
                double meanX = candidates.Average(j => PlanXOfTreeMain(placed, net, j));
                double meanY = candidates.Average(j => PlanYOfTreeMain(placed, net, j));
                if (Math.Abs(X(levelNodes[footNode[tree]]) - meanX) > 1.0e-12 ||
                    Math.Abs(Y(levelNodes[footNode[tree]]) - meanY) > 1.0e-12)
                {
                    throw new InvalidOperationException(
                        $"Type {type}: the group foot is the plan MEAN of its candidates EXACTLY, ({meanX:0.############}, {meanY:0.############}); "
                        + $"it stands at ({X(levelNodes[footNode[tree]]):0.############}, {Y(levelNodes[footNode[tree]]):0.############}). "
                        + "A single line does not need to be intersected with itself to find its own middle, and a least-squares solve over this "
                        + "bar's own tangents would miss by up to a notch spacing.");
                }
            }
```

   `RequireFootIsCandidateMean` is declared beside `FootOfTree` so both blocks can call it, item 1's as `RequireFootIsCandidateMean(curved, placed, 2, 0)` and item 2's Type 1 block as `RequireFootIsCandidateMean(curved, placed, 1, 3)`. `ChordParameterOfTree`, `PlanXOfTreeMain` and `PlanYOfTreeMain` are three one-line locals beside it: the first is `InSpanFrame`'s along part of the tree's main notch divided by the span's chord length, and the other two read that notch's plan X and Y straight off the fixture's node array through `Get<int[]>(trees[j], "Nodes")[0]`.

   AND THE ODD-COUNT CASE, which spec section 17 asks for as a SEPARATE fixture because `PlanCurved` has ten nodes and eight free notches and cannot carry it. Build `PlanCurvedOdd()` beside `PlanCurved`: the same bar with ONE node added, eleven nodes and NINE free notches, the added node placed so the row stays symmetric about the crown. At Type 1 the one group of nine has an ODD count, so its nearest-to-centre candidate is a single notch, the crown notch, and the foot is that notch's own plan position:

```csharp
        // ---- THE PLAN-CURVED BAR, ODD COUNT (spec section 17). Nine free
        // notches, so the one group at Type 1 has an ODD count and exactly
        // ONE candidate, the crown notch. Its foot is that notch's own plan
        // position, which is the crown-notch assertion the even-count fixture
        // cannot carry.
        {
            var odd = PlanCurvedOdd();
            object placed = Run(odd, Array.Empty<int[]>(), 1, 1);
            object built = Get<object>(placed, "Built");
            var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            if (trees.Length != 9)
                throw new InvalidOperationException($"This fixture only carries the odd-count claim while it holds NINE free notches; it holds {trees.Length}.");
            int[] footNode = FootOfTree(built, trees.Length);
            int crownTree = 4;
            object crownNotch = odd.Nodes.GetValue(Get<int[]>(trees[crownTree], "Nodes")[0])!;
            object crownFoot = levelNodes[footNode[crownTree]];
            if (Math.Abs(X(crownFoot) - X(crownNotch)) > 1.0e-12 ||
                Math.Abs(Y(crownFoot) - Y(crownNotch)) > 1.0e-12)
            {
                throw new InvalidOperationException(
                    $"At Type 1 an ODD group has ONE candidate, its crown notch, so the foot stands at that notch's own plan position "
                    + $"({X(crownNotch):0.#########}, {Y(crownNotch):0.#########}); it stands at ({X(crownFoot):0.#########}, {Y(crownFoot):0.#########}).");
            }
            if (footNode.Distinct().Count() != 1)
                throw new InvalidOperationException("At Type 1 all nine trees take the one group's one foot before any peel; they took several.");
        }
```

2. `tests/native_smoke/Program.cs:6962-6993`, the band rebuilding its foot from the survivors of a peel, pinned at chord `(0, 832/486)`. DELETED WITH ITS RULE. Its replacement asserts the opposite on the same fixture:

```csharp
        // ---- A PEEL NEVER MOVES A FOOT (spec section 11), on the
        // plan-curved bar at Type 1. All eight trees take the one group,
        // whose foot is the plan mean of its two tied central candidates at
        // chord u = -0.5 and 0.5, both across at v = 160/81: chord
        // (0, 160/81). The outermost trunk on each flank leans past the cap
        // to it and peels onto its own foot. The foot DOES NOT MOVE, because
        // a foot's position is a function of the span's notches and not of
        // the trees standing on it; the old rule rebuilt it from the six
        // survivors and walked it to (0, 832/486).
        {
            var curved = PlanCurved(0.15);
            object placed = Run(curved, Array.Empty<int[]>(), 1, 1);
            object built = Get<object>(placed, "Built");
            var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            var spans = ((IEnumerable)Get<object>(placed, "Spans")).Cast<object>().ToArray();
            if (Get<int>(built, "Peeled") != 2)
                throw new InvalidOperationException($"The outermost trunk on each flank leans past the cap to the group foot and peels; {Get<int>(built, "Peeled")} peeled.");
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (feet.Length != 3)
                throw new InvalidOperationException($"One group foot and two peeled feet is three; {feet.Length} built.");
            int[] footNode = FootOfTree(built, trees.Length);
            (double Along, double Across) group = InSpanFrame(curved.Nodes, curved.Bars[0], spans[0], levelNodes[footNode[3]]);
            const double groupAcross = 160.0 / 81.0;
            if (Math.Abs(group.Along) > 1.0e-9 || Math.Abs(group.Across - groupAcross) > 1.0e-9)
            {
                throw new InvalidOperationException(
                    $"The group foot is the plan mean of its own two central notches, chord (0, {groupAcross:0.#########}), and a peel does not move it; "
                    + $"it stands at ({group.Along:0.#########}, {group.Across:0.#########}). Rebuilt from the six survivors it would read (0, {832.0 / 486.0:0.#########}), "
                    + "a foot positioned in part by two trunks that have walked away.");
            }
        }
```

3. `tests/native_smoke/Program.cs:7002-7045`, Type 1 on the control arch. STAYS GREEN in every number: `Peeled 4`, five feet, the shared foot at x = 5. Change `Banded` to `Gathered` and its message to say that at Type 1 every one of the nine trees takes the ONE shared foot, so `Gathered` is 9, counted before the peel.

4. `tests/native_smoke/Program.cs:7047-7090`, Type 2 on the control arch. STAYS GREEN: three feet, the centre tree on its own foot at x = 5, the two shared feet at 2.5 and 7.5. Change `Banded 8` to `Gathered 8`, rewrite its message from "band" to "group", and add:

```csharp
            if (Get<int>(built, "CentralColumns") != 1)
                throw new InvalidOperationException($"An ODD tree row at an EVEN Type leaves its middle tree standing alone and plumb, counted BY CONSTRUCTION; CentralColumns is {Get<int>(built, "CentralColumns")}.");
```

- [ ] **Step 6: Pin the control arch entire**

Spec section 17 requires the control arch stated in full wherever its numbers are quoted, because the earlier draft quoted them against an arch it never named and got the Type 1 row wrong. Insert a new block:

```csharp
        // ---- THE CONTROL NUMBERS (spec section 17). THE CONTROL ARCH IS
        // ELEVEN NODES, TEN METRES WIDE, RISE 2.5, ANCHORED AT BOTH ENDS,
        // UNIT DOWNWARD PULL AT EVERY NODE, BRANCHING 1: nine free notches
        // one metre apart at chord parameters 0.1 to 0.9. These are the
        // MEASURED numbers of the engine as it stands, so on a clean
        // symmetric span the redesign does not move one column. Any deviation
        // is a change to a clean span and must be argued before it is
        // accepted. The two-peel answer belongs to an arch of RISE 5 and must
        // not be written against this one.
        {
            (int Type, double[] Feet)[] control =
            {
                (0, new[] { -4.0, -3.0, -2.0, -1.0, 0.0, 1.0, 2.0, 3.0, 4.0 }),
                (1, new[] { -4.0, -3.0, 0.0, 0.0, 0.0, 0.0, 0.0, 3.0, 4.0 }),
                (2, new[] { -2.5, -2.5, -2.5, -2.5, 0.0, 2.5, 2.5, 2.5, 2.5 }),
                (3, new[] { -3.0, -3.0, -3.0, 0.0, 0.0, 0.0, 3.0, 3.0, 3.0 }),
                (4, new[] { -3.5, -3.5, -1.5, -1.5, 0.0, 1.5, 1.5, 3.5, 3.5 }),
            };
            foreach ((int type, double[] expected) in control)
            {
                object placed = Run(Arch(11, 10.0, 2.5, 1.0), Array.Empty<int[]>(), 1, type);
                object built = Get<object>(placed, "Built");
                var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
                int[] footNode = FootOfTree(built, 9);
                for (int t = 0; t < 9; t++)
                {
                    double got = X(levelNodes[footNode[t]]) - 5.0;
                    if (Math.Abs(got - expected[t]) > 1.0e-9)
                    {
                        throw new InvalidOperationException(
                            $"The control arch at Type {type} stands its feet at [{string.Join(" ", expected)}] metres from the plan midpoint; "
                            + $"tree {t} stands at {got:0.#########} against {expected[t]:0.#}.");
                    }
                }
                int distinct = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().Count();
                int wanted = expected.Distinct().Count();
                if (distinct != wanted)
                    throw new InvalidOperationException($"The control arch at Type {type} builds {wanted} distinct feet; it built {distinct}.");
            }
        }
```

- [ ] **Step 7: The central column stands straight**

Param's ruling of 2026-09-01 needs a check of its own rather than riding on the control arch's foot list:

```csharp
        // ---- THE CENTRAL COLUMN STANDS STRAIGHT (spec sections 5, 7 and
        // 18.1, Param's ruling of 2026-09-01). On a span of ODD tree count at
        // Types 2 and 4 the middle tree by index is extracted as a group of
        // ONE, CentralColumns counts it, its foot is its OWN group's central
        // notch and not the nearer flank group's, and its trunk stands PLUMB
        // within PlumbDegrees of vertical wherever the notch row is
        // symmetric.
        //
        // The REJECTED ALTERNATIVE is computed here rather than described:
        // the centre tree could have joined the flank group whose foot is
        // nearer, ties to the lower chord parameter, and the middle column
        // would then lean to a side. That is exactly the move he named, and
        // the check asserts the engine does not take it.
        foreach (int type in new[] { 2, 4 })
        {
            object placed = Run(Arch(11, 10.0, 2.5, 1.0), Array.Empty<int[]>(), 1, type);
            object built = Get<object>(placed, "Built");
            var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            int[] footNode = FootOfTree(built, trees.Length);
            if (Get<int>(built, "CentralColumns") != 1)
                throw new InvalidOperationException($"Type {type}: nine trees is an ODD row at an EVEN Type, so ONE tree stands alone; CentralColumns is {Get<int>(built, "CentralColumns")}.");
            object centreFoot = levelNodes[footNode[4]];
            if (Math.Abs(X(centreFoot) - 5.0) > 1.0e-9)
                throw new InvalidOperationException($"Type {type}: the centre tree's foot is its own group's central notch, x = 5; it stands at {X(centreFoot):0.#########}.");
            if (footNode[4] == footNode[3] || footNode[4] == footNode[5])
                throw new InvalidOperationException($"Type {type}: the centre tree stands on its OWN foot and joins NEITHER flank group. Joining the nearer flank is the move Param named and refused.");
            double flankFoot = X(levelNodes[footNode[3]]);
            if (Math.Abs(flankFoot - 5.0) < 1.0e-9)
                throw new InvalidOperationException($"Type {type}: this check only measures anything while the nearer flank foot DIFFERS from the central one; it is at {flankFoot:0.#########}.");
            // THE REJECTED ALTERNATIVE, COMPUTED. The centre tree could have
            // joined the flank group whose foot is nearer, ties to the lower
            // chord parameter. The check builds that group itself from the
            // notch row, takes its nearest-to-centre candidates by the rule of
            // 8.1, and asserts the placed foot is NOT that point and differs
            // from it by the flank group's own offset from the centre notch.
            // Describing the alternative would leave the reader to trust it;
            // computing it makes the refusal a measurement.
            int[][] flankGroups = ExpectedFootGroups(9, type);
            int[] nearerFlank = flankGroups
                .Where(g => !g.Contains(4))
                .OrderBy(g => Math.Abs(g.Average(j => 1.0 + j) - 5.0))
                .ThenBy(g => g.Min())
                .First();
            int[] joined = nearerFlank.Concat(new[] { 4 }).OrderBy(j => j).ToArray();
            double joinedCentre = 0.5 * ((1.0 + joined.Min()) + (1.0 + joined.Max()));
            double joinedNearest = joined.Min(j => Math.Abs(1.0 + j - joinedCentre));
            double wouldBe = joined
                .Where(j => Math.Abs(1.0 + j - joinedCentre) <= joinedNearest + 1.0e-12)
                .Average(j => 1.0 + j);
            double offset = Math.Abs(wouldBe - 5.0);
            if (offset < 1.0e-9)
                throw new InvalidOperationException($"Type {type}: this check only measures anything while joining the nearer flank would MOVE the centre column; the two answers coincide at x = {wouldBe:0.#########}.");
            if (Math.Abs(X(centreFoot) - wouldBe) < 1.0e-9)
            {
                throw new InvalidOperationException(
                    $"Type {type}: the centre tree joined the nearer flank group and its column stands at x = {wouldBe:0.#########}, which is the move Param named "
                    + "and refused: \"just moving the standing coloumn for symmetry reasons away from center when it shold obviously default to center\".");
            }
            if (Math.Abs(Math.Abs(X(centreFoot) - wouldBe) - offset) > 1.0e-9)
            {
                throw new InvalidOperationException(
                    $"Type {type}: the placed central foot differs from the joined-flank answer by the flank group's OWN offset, {offset:0.#########} m; "
                    + $"it differs by {Math.Abs(X(centreFoot) - wouldBe):0.#########}.");
            }
            var members = MembersOf(built);
            int[] memberTree = ((IEnumerable)Get<object>(built, "MemberTree")).Cast<int>().ToArray();
            var feetSet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToHashSet();
            for (int k = 0; k < members.Length; k++)
            {
                if (memberTree[k] != 4 || !feetSet.Contains(members[k].Lower))
                    continue;
                double lean = AngleDeg(
                    X(levelNodes[members[k].Upper]) - X(levelNodes[members[k].Lower]),
                    Y(levelNodes[members[k].Upper]) - Y(levelNodes[members[k].Lower]),
                    Z(levelNodes[members[k].Upper]) - Z(levelNodes[members[k].Lower]),
                    0.0, 0.0, 1.0);
                if (lean > 2.0)
                    throw new InvalidOperationException($"Type {type}: on a symmetric notch row the central column stands PLUMB within PlumbDegrees of vertical; it leans {lean:0.####} degrees.");
            }
        }
```

And the same ruling on a notch row that is NOT symmetric, where spec section 8.6 makes a deliberately WEAKER claim and where an implementer reading only the block above would be tempted to strengthen it. The off-centre crest is the fixture 8.6 names by name, and what it asks is that the central foot stands at its own notch and is off the plane of symmetry by exactly however far that notch is, with no step projecting it onto the plane, because projecting would move a column nothing asked to move. `CrestArch` is built in Step 8; this block goes after it:

```csharp
        // ---- THE CENTRAL COLUMN ON A LOPSIDED ROW (spec section 8.6). The
        // notch row of an equal-arc arch whose crest sits at chord parameter
        // 0.584 is NOT symmetric about the chord midpoint, so the central
        // foot is NOT at x = 5 and must not be pushed there. What 8.6 claims
        // is weaker and exact: the foot stands at its own group's central
        // notch, and it is off the plane by however far that notch is.
        foreach (int type in new[] { 2, 4 })
        {
            var crest = CrestArch(11, 10.0, 2.5, crest: 0.584);
            object placed = Run(crest, Array.Empty<int[]>(), 1, type);
            object built = Get<object>(placed, "Built");
            var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            int[] footNode = FootOfTree(built, trees.Length);
            if (Get<int>(built, "CentralColumns") != 1)
                throw new InvalidOperationException($"Type {type}: nine trees is an ODD row at an EVEN Type on a lopsided arch too; CentralColumns is {Get<int>(built, "CentralColumns")}.");
            object ownNotch = crest.Nodes.GetValue(Get<int[]>(trees[4], "Nodes")[0])!;
            object placedFoot = levelNodes[footNode[4]];
            if (Math.Abs(X(placedFoot) - X(ownNotch)) > 1.0e-9 || Math.Abs(Y(placedFoot) - Y(ownNotch)) > 1.0e-9)
            {
                throw new InvalidOperationException(
                    $"Type {type}: the central foot stands at its OWN group's central notch, ({X(ownNotch):0.#########}, {Y(ownNotch):0.#########}); "
                    + $"it stands at ({X(placedFoot):0.#########}, {Y(placedFoot):0.#########}).");
            }
            double offPlane = Math.Abs(X(ownNotch) - 5.0);
            if (offPlane < 1.0e-6)
                throw new InvalidOperationException($"This fixture only measures anything while the central notch is measurably OFF the chord midpoint; it is {offPlane:0.#########} m from it.");
            if (Math.Abs(Math.Abs(X(placedFoot) - 5.0) - offPlane) > 1.0e-9)
            {
                throw new InvalidOperationException(
                    $"Type {type}: the central foot is off the plane by exactly however far its own notch is, {offPlane:0.#########} m, and NO step projects it onto the "
                    + $"plane; it stands {Math.Abs(X(placedFoot) - 5.0):0.#########} m off. Projecting would move a column nothing asked to move (spec section 8.6).");
            }
        }
```

- [ ] **Step 8: The coarse net and the bar that is not plan-monotone**

Add the `CrestArch` fixture builder beside `SkewArch` at line 6010, then two blocks. `CrestArch` places its notches at equal ARC LENGTH along an arch whose crest sits at a stated chord parameter, which is what a relaxed cable net actually gives and what every evenly-spaced-in-x fixture in this file is blind to:

```csharp
        (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) CrestArch(
            int count, double width, double rise, double crest)
        {
            double Height(double s) => s <= crest
                ? rise * (1.0 - (((s / crest) - 1.0) * ((s / crest) - 1.0)))
                : rise * (1.0 - ((((s - crest) / (1.0 - crest))) * (((s - crest) / (1.0 - crest)))));
            const int fine = 20000;
            var lengths = new double[fine + 1];
            for (int i = 1; i <= fine; i++)
            {
                double s0 = (double)(i - 1) / fine;
                double s1 = (double)i / fine;
                double dx = width * (s1 - s0);
                double dz = Height(s1) - Height(s0);
                lengths[i] = lengths[i - 1] + Math.Sqrt((dx * dx) + (dz * dz));
            }
            double total = lengths[fine];
            Array nodes = Array.CreateInstance(point3d, count);
            Array acrossBar = Array.CreateInstance(vector3d, count);
            var edges = new List<(int, int)>();
            int at = 0;
            for (int k = 0; k < count; k++)
            {
                double want = total * k / (count - 1);
                while (at < fine && lengths[at + 1] < want)
                    at++;
                double s = (double)at / fine;
                nodes.SetValue(P(width * s, 0.0, Height(s)), k);
                acrossBar.SetValue(V(0.0, 0.0, -1.0), k);
                if (k > 0)
                    edges.Add((k - 1, k));
            }
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 1);
            across.SetValue(acrossBar, 0);
            return (nodes, new[] { Enumerable.Range(0, count).ToArray() }, new[] { 0, count - 1 }, across, edges.ToArray());
        }
```

```csharp
        // ---- A COARSE NET WHOSE NODES ARE FAR APART (spec section 17). One
        // geometry, a crest at chord parameter 0.60 at rise over span 0.25,
        // sampled at 3, 5, 9 and 17 notches. The present engine passes its
        // symmetry test at 3 and 5 and FAILS it at 9 and 17: the geometric
        // defect barely moves from 0.0284 to 0.0300 while the tolerance falls
        // from 0.0625 to 0.0139, so refining a mesh on unchanged geometry
        // pushed the span over the cliff. Under this spec the layout is the
        // table's row at every density, the feet are at the group centres,
        // no span is ever placed unmirrored, and the foot positions CONVERGE
        // as the density rises rather than jumping between them.
        {
            var previous = new Dictionary<int, double>();
            foreach (int notches in new[] { 3, 5, 9, 17 })
            {
                var net = CrestArch(notches + 2, 10.0, 2.5, crest: 0.60);
                foreach (int type in new[] { 1, 2, 3, 4 })
                {
                    object placed = Run(net, Array.Empty<int[]>(), 1, type);
                    object built = Get<object>(placed, "Built");
                    var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
                    var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
                    int[] footNode = FootOfTree(built, trees.Length);
                    if (notches == 3 && type == 4)
                    {
                        int distinct = footNode.Distinct().Count();
                        if (distinct != 3)
                        {
                            throw new InvalidOperationException(
                                $"Three trees at Type 4: T is at most N, so every tree is a group of one and the span places THREE feet, not four. "
                                + $"A foot with no tree is not built. It built {distinct}.");
                        }
                    }
                    // THE LAYOUT IS THE TABLE'S ROW at every density. At
                    // Branching 1 the ladder gives one tree per notch, so the
                    // tree count IS the notch count and the foot groups are
                    // section 7's row for that count and that Type. Asserted
                    // rather than assumed, because the whole point of this
                    // fixture is that refining the mesh used to change the
                    // answer.
                    int[][] wanted = ExpectedFootGroups(notches, type);
                    if (trees.Length != notches)
                        throw new InvalidOperationException($"Type {type} at {notches} notches: Branching 1 gives one tree per notch; it gave {trees.Length}.");
                    if (wanted.Sum(g => g.Length) != notches)
                        throw new InvalidOperationException($"Type {type} at {notches} notches: section 7's row is not a partition of the tree count.");
                    for (int j = 0; j < wanted.Length; j++)
                    {
                        if (wanted[j].Length != wanted[wanted.Length - 1 - j].Length)
                            throw new InvalidOperationException($"Type {type} at {notches} notches: group {j} and its mirror hold the same number of trees.");
                    }
                    // THE FEET ARE AT THE GROUP CENTRES, computed here from
                    // the notch row by the nearest-to-centre rule of 8.1 and
                    // not read off the engine, so the check is not comparing
                    // the engine with itself. Peeled trees are skipped: a
                    // peeled foot is aim-derived by section 11.
                    double[] sigma = Enumerable.Range(1, notches)
                        .Select(i => X(net.Nodes.GetValue(i)!) / 10.0).ToArray();
                    foreach (int[] group in wanted)
                    {
                        double lo = group.Min(j => sigma[j]);
                        double hi = group.Max(j => sigma[j]);
                        double centre = 0.5 * (lo + hi);
                        double nearest = group.Min(j => Math.Abs(sigma[j] - centre));
                        double expected = group
                            .Where(j => Math.Abs(sigma[j] - centre) <= nearest + 1.0e-12)
                            .Average(j => X(net.Nodes.GetValue(j + 1)!));
                        foreach (int j in group)
                        {
                            if (MouldLean(levelNodes[footNode[j]], net.Nodes.GetValue(j + 1)!) > 60.0 + 1.0e-9)
                                continue;
                            if (Math.Abs(X(levelNodes[footNode[j]]) - expected) > 1.0e-9)
                            {
                                throw new InvalidOperationException(
                                    $"Type {type} at {notches} notches: the foot of the group holding trees [{string.Join(",", group)}] is the plan mean of its "
                                    + $"nearest-to-centre candidates, x = {expected:0.#########}; tree {j} stands at {X(levelNodes[footNode[j]]):0.#########}.");
                            }
                        }
                    }
                    // NO SPAN IS EVER PLACED UNMIRRORED, which is the claim
                    // the present engine fails at 9 and 17 notches on this
                    // very geometry: the defect barely moves from 0.0284 to
                    // 0.0300 while the old tolerance falls from 0.0625 to
                    // 0.0139. UnpairedTrees replaces AsymmetricSpans in
                    // Task 7 and this line moves with it.
                    if (Get<int>(placed, "UnpairedTrees") != 0)
                    {
                        throw new InvalidOperationException(
                            $"Type {type} at {notches} notches: no span is placed unmirrored at ANY density; UnpairedTrees is "
                            + $"{Get<int>(placed, "UnpairedTrees")}. Refining a mesh on unchanged geometry used to push this span over a cliff.");
                    }
                    double outermost = X(levelNodes[footNode[0]]);
                    if (previous.TryGetValue(type, out double before) && notches >= 9 &&
                        Math.Abs(outermost - before) > 10.0 / notches)
                    {
                        throw new InvalidOperationException(
                            $"Type {type}: refining from the previous density moved the outermost foot from {before:0.####} to {outermost:0.####}, "
                            + "further than one notch spacing. The feet CONVERGE as the density rises; they do not jump between densities.");
                    }
                    previous[type] = outermost;
                }
            }
        }

        // ---- NOT PLAN-MONOTONE (spec sections 4, 6 and 7). A bar whose
        // chord parameter does NOT rise with its node order, which the
        // engine's own comment records as a real case. The layout, the trees,
        // the mains and the foot groups follow BAR ORDER, so Branching still
        // means NEIGHBOURING notches. The check computes both readings and
        // asserts they DIFFER on this bar, so a version reading the parameter
        // where the index is meant goes red rather than green.
        {
            double[] xs = { 0.0, 1.0, 2.0, 4.0, 3.0, 5.0, 6.0, 7.0, 8.0 };
            Array nodes = Array.CreateInstance(point3d, xs.Length);
            Array acrossBar = Array.CreateInstance(vector3d, xs.Length);
            var edges = new List<(int, int)>();
            for (int i = 0; i < xs.Length; i++)
            {
                double s = xs[i] / 8.0;
                nodes.SetValue(P(xs[i], 0.0, 2.5 * 4.0 * s * (1.0 - s)), i);
                acrossBar.SetValue(V(0.0, 0.0, -1.0), i);
                if (i > 0)
                    edges.Add((i - 1, i));
            }
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 1);
            across.SetValue(acrossBar, 0);
            var bent = (nodes, new[] { Enumerable.Range(0, xs.Length).ToArray() }, new[] { 0, xs.Length - 1 }, across, edges.ToArray());
            if (xs[3] <= xs[4])
                throw new InvalidOperationException("This fixture only measures anything while its chord parameter falls between two consecutive bar positions.");
            object placed = Run(bent, Array.Empty<int[]>(), 3, 0);
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            int[] first = Get<int[]>(trees[0], "Nodes").OrderBy(n => n).ToArray();
            if (!first.SequenceEqual(new[] { 1, 2 }))
                throw new InvalidOperationException($"Seven free notches at Branching 3 lay out [2,3,2] BY BAR ORDER, so tree 0 holds bar positions 1 and 2; it holds [{string.Join(",", first)}].");
            int[] middle = Get<int[]>(trees[1], "Nodes").OrderBy(n => n).ToArray();
            if (!middle.SequenceEqual(new[] { 3, 4, 5 }))
                throw new InvalidOperationException($"Branching means NEIGHBOURING notches along the bar, so the middle tree holds positions 3, 4 and 5 whatever their chord parameters; it holds [{string.Join(",", middle)}].");

            // BOTH READINGS ARE COMPUTED AND ASSERTED TO DIFFER. Asserting
            // the bar-order answer alone would go green against a version
            // that read the parameter where the index is meant, because on
            // nine notches out of ten fixtures in this file the two readings
            // coincide. Here they do not: sorted by chord parameter the free
            // notches run 1, 2, 4, 3, 5, 6, 7, so a parameter-ordered layout
            // at Branching 3 puts 4 and 3 in different trees from the ones
            // bar order gives.
            int[] freeByBar = { 1, 2, 3, 4, 5, 6, 7 };
            int[] freeByParameter = freeByBar.OrderBy(p => xs[p]).ToArray();
            int[][] barLayout = { new[] { 1, 2 }, new[] { 3, 4, 5 }, new[] { 6, 7 } };
            var parameterLayout = new[]
            {
                freeByParameter.Take(2).ToArray(),
                freeByParameter.Skip(2).Take(3).ToArray(),
                freeByParameter.Skip(5).Take(2).ToArray(),
            };
            bool same = barLayout.Length == parameterLayout.Length &&
                Enumerable.Range(0, barLayout.Length).All(g =>
                    barLayout[g].OrderBy(p => p).SequenceEqual(parameterLayout[g].OrderBy(p => p)));
            if (same)
                throw new InvalidOperationException("This fixture only measures anything while the BAR-ORDER layout and the PARAMETER-ORDER layout DIFFER; on this bar they agree, so nothing is being tested.");
            for (int g = 0; g < barLayout.Length; g++)
            {
                int[] got = Get<int[]>(trees[g], "Nodes").OrderBy(n => n).ToArray();
                if (got.SequenceEqual(parameterLayout[g].OrderBy(p => p)) &&
                    !got.SequenceEqual(barLayout[g].OrderBy(p => p)))
                {
                    throw new InvalidOperationException(
                        $"Tree {g} holds [{string.Join(",", got)}], which is the PARAMETER-ordered reading and not the BAR-ordered one, [{string.Join(",", barLayout[g])}]. "
                        + "Section 6 reads the bar order and nothing else; a version reading the parameter where the index is meant goes red here rather than green.");
                }
            }

            // THE TIE CASE. Two notches at ONE chord parameter, listed in
            // both orders, giving the same layout and the same feet. A
            // parameter-ordered reading has no answer here at all, because
            // the sort is not defined between them, and a stable sort would
            // hand back a different layout for a different listing order.
            double[] tied = { 0.0, 1.0, 2.0, 3.0, 3.0, 5.0, 6.0, 7.0, 8.0 };
            (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) Tie(bool swap)
            {
                Array nodesHere = Array.CreateInstance(point3d, tied.Length);
                Array acrossHere = Array.CreateInstance(vector3d, tied.Length);
                var edgesHere = new List<(int, int)>();
                var order = Enumerable.Range(0, tied.Length).ToArray();
                if (swap)
                    (order[3], order[4]) = (order[4], order[3]);
                for (int i = 0; i < tied.Length; i++)
                {
                    double x = tied[order[i]];
                    double s = x / 8.0;
                    // The two tied notches differ ACROSS the chord so they
                    // are distinct points, and share the chord parameter
                    // exactly, which is the case the rule has to answer.
                    double y = order[i] == 3 ? -0.25 : order[i] == 4 ? 0.25 : 0.0;
                    nodesHere.SetValue(P(x, y, 2.5 * 4.0 * s * (1.0 - s)), i);
                    acrossHere.SetValue(V(0.0, 0.0, -1.0), i);
                    if (i > 0)
                        edgesHere.Add((i - 1, i));
                }
                Array acrossAll = Array.CreateInstance(vector3d.MakeArrayType(), 1);
                acrossAll.SetValue(acrossHere, 0);
                return (nodesHere, new[] { Enumerable.Range(0, tied.Length).ToArray() },
                    new[] { 0, tied.Length - 1 }, acrossAll, edgesHere.ToArray());
            }
            foreach (int type in new[] { 0, 1, 2, 3, 4 })
            {
                object one = Run(Tie(false), Array.Empty<int[]>(), 3, type);
                object two = Run(Tie(true), Array.Empty<int[]>(), 3, type);
                object builtOne = Get<object>(one, "Built");
                object builtTwo = Get<object>(two, "Built");
                var treesOne = ((IEnumerable)Get<object>(one, "Trees")).Cast<object>().ToArray();
                var treesTwo = ((IEnumerable)Get<object>(two, "Trees")).Cast<object>().ToArray();
                if (treesOne.Length != treesTwo.Length)
                    throw new InvalidOperationException($"Type {type}: two notches at ONE chord parameter give the same LAYOUT in either listing order; {treesOne.Length} trees against {treesTwo.Length}.");
                var nodesOne = ((IEnumerable)Get<object>(builtOne, "Nodes")).Cast<object>().ToArray();
                var nodesTwo = ((IEnumerable)Get<object>(builtTwo, "Nodes")).Cast<object>().ToArray();
                double[] feetOne = FootOfTree(builtOne, treesOne.Length).Select(f => X(nodesOne[f])).OrderBy(v => v).ToArray();
                double[] feetTwo = FootOfTree(builtTwo, treesTwo.Length).Select(f => X(nodesTwo[f])).OrderBy(v => v).ToArray();
                for (int t = 0; t < feetOne.Length; t++)
                {
                    if (Math.Abs(feetOne[t] - feetTwo[t]) > 1.0e-12)
                    {
                        throw new InvalidOperationException(
                            $"Type {type}: the layout and the feet are UNCHANGED by the order the two tied notches are listed in; foot {t} stands at "
                            + $"{feetOne[t]:0.#########} one way and {feetTwo[t]:0.#########} the other. A parameter-ordered reading has no answer here at all.");
                    }
                }
            }
        }
```

- [ ] **Step 9: Stability under noise**

```csharp
        // ---- STABILITY UNDER NOISE (spec section 17). Place a symmetric
        // arch, displace every node by a pseudo-random offset of 1e-6 times
        // the chord length, place it again. Every tree keeps the same group,
        // no foot moves by more than 1e-5 times the chord, and no diagnostic
        // count changes. BAND ARITHMETIC FAILS THIS whenever a main notch
        // sits near a boundary, which is what the centre notch of a uniform
        // arch does at every EVEN Type.
        foreach (int type in new[] { 1, 2, 3, 4 })
        {
            var clean = Arch(11, 10.0, 2.5, 1.0);
            var noisy = Arch(11, 10.0, 2.5, 1.0);
            int seed = 1;
            for (int i = 0; i < 11; i++)
            {
                seed = unchecked((seed * 1103515245) + 12345);
                double a = (((seed >> 8) & 0xFFFF) / 65536.0) - 0.5;
                seed = unchecked((seed * 1103515245) + 12345);
                double b = (((seed >> 8) & 0xFFFF) / 65536.0) - 0.5;
                object p = noisy.Nodes.GetValue(i)!;
                noisy.Nodes.SetValue(P(X(p) + (1.0e-5 * a), Y(p) + (1.0e-5 * b), Z(p)), i);
            }
            object placedClean = Run(clean, Array.Empty<int[]>(), 1, type);
            object placedNoisy = Run(noisy, Array.Empty<int[]>(), 1, type);
            object builtClean = Get<object>(placedClean, "Built");
            object builtNoisy = Get<object>(placedNoisy, "Built");
            var nodesClean = ((IEnumerable)Get<object>(builtClean, "Nodes")).Cast<object>().ToArray();
            var nodesNoisy = ((IEnumerable)Get<object>(builtNoisy, "Nodes")).Cast<object>().ToArray();
            int[] footClean = FootOfTree(builtClean, 9);
            int[] footNoisy = FootOfTree(builtNoisy, 9);
            for (int t = 0; t < 9; t++)
            {
                double moved = Math.Sqrt(
                    Math.Pow(X(nodesNoisy[footNoisy[t]]) - X(nodesClean[footClean[t]]), 2.0) +
                    Math.Pow(Y(nodesNoisy[footNoisy[t]]) - Y(nodesClean[footClean[t]]), 2.0));
                if (moved > 1.0e-4)
                    throw new InvalidOperationException($"Type {type}: a millionth of the chord of noise moved tree {t}'s foot by {moved:0.#########}, which is a boundary flip and not a solve.");
            }
            foreach (string field in new[] { "Peeled", "Gathered", "CentralColumns", "FeetMerged", "FeetClose" })
            {
                if (Get<int>(builtClean, field) != Get<int>(builtNoisy, field))
                    throw new InvalidOperationException($"Type {type}: noise of a millionth of the chord changed {field} from {Get<int>(builtClean, field)} to {Get<int>(builtNoisy, field)}.");
            }
        }
```

- [ ] **Step 10: Run the gate green, then commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/ColumnPlacement.cs" "plugin/native_v02/Components/ColumnsComponent.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(columns): the bands go, and a group's foot is its own central notches"
```

---

### Task 5: The peel as a mirror pair, and the degenerate spans

Spec section 11 (all but the second pass, which needs the merge of Task 8) and section 15 entire. Every degenerate case is a RULE here, not an exception to be discovered in the field.

**Files:**
- Modify: `plugin/native_v02/Components/ColumnPlacement.cs` (the peel block added in Task 4; the `own` array at 946-961; a new degenerate branch in the `BuildLevel` span loop; `Placement`)
- Test: `tests/native_smoke/Program.cs`, four new blocks

**Interfaces:**
- Consumes: Task 4's `FootGroups`, `GroupFoot`, `Level.Gathered`, `Level.Peeled`; Task 3's `SpanFrame.ChordZero` and `SpanFrame.OneParameter`.
- Produces: `Placement.SpanDegenerate` (public `int`), read by Task 9's `columns.span_degenerate`.

- [ ] **Step 1: Write the pair peel check, red**

```csharp
        // ---- THE PEEL, AS A PAIR (spec section 11). A tree that peels takes
        // its mirror PARTNER with it, whether or not the partner is over the
        // cap; both feet are then Type 0 feet and are mirror images, and both
        // members count in Peeled. The wide flat span at Type 1 is the
        // measured control: FOUR trees of the nine-notch rise-2.5 arch peel,
        // the flank trunks leaning 77.3 and 61.9 degrees to the central foot
        // while the next one in leans 43.6 and stays.
        {
            object placed = Run(Arch(11, 10.0, 2.5, 1.0), Array.Empty<int[]>(), 1, 1);
            object built = Get<object>(placed, "Built");
            var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            int[] footNode = FootOfTree(built, 9);
            int[] partner = Get<int[]>(placed, "Partner");
            int shared = footNode[4];
            int[] peeledSet = Enumerable.Range(0, 9).Where(t => footNode[t] != shared).ToArray();
            if (Get<int>(built, "Peeled") != peeledSet.Length)
                throw new InvalidOperationException($"Peeled counts the members that stepped off; it reads {Get<int>(built, "Peeled")} against {peeledSet.Length} trees standing off the shared foot.");
            foreach (int t in peeledSet)
            {
                int mate = partner[t];
                if (mate < 0 || mate == t)
                    continue;
                if (!peeledSet.Contains(mate))
                    throw new InvalidOperationException($"A tree that peels takes its mirror PARTNER with it, whether or not the partner is over the cap; tree {t} peeled and {mate} did not.");
                double sum = X(levelNodes[footNode[t]]) + X(levelNodes[footNode[mate]]);
                if (Math.Abs(sum - 10.0) > 1.0e-9)
                    throw new InvalidOperationException($"Both feet of a peeling pair are Type 0 feet and are mirror images; trees {t} and {mate} stand at {X(levelNodes[footNode[t]]):0.#########} and {X(levelNodes[footNode[mate]]):0.#########}, summing to {sum:0.#########} rather than 10.");
            }
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (feet.Any(f => !footNode.Contains(f)))
                throw new InvalidOperationException("A foot left with NO trees standing on it is not built.");
        }
```

- [ ] **Step 2: Write the degenerate-span checks, red**

```csharp
        // ---- A SPAN OF ONE TREE (spec sections 15 and 17). One free notch,
        // at chord parameter 0.44 and again at 0.43, which is the MEASURED
        // boundary of the self-pairing test on the engine as it stands: 0.44
        // passed it, 0.43 failed it, and 0.43 dropped Families to 0 and
        // disabled the whole span. Under this spec THE TWO PARAMETERS GIVE
        // THE SAME ANSWER IN EVERY RESPECT, which is the strongest form the
        // fixture can take: the mean of one along part is that along part, so
        // 9.1 zeroes it unconditionally, and s_mirror falls back to the row
        // centre by parameter, which for one notch IS that notch. Its h is
        // the fallback 1 / (m + 1) = 0.5.
        {
            (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) Lone(double parameter)
            {
                Array nodes = Array.CreateInstance(point3d, 3);
                nodes.SetValue(P(0.0, 0.0, 0.0), 0);
                nodes.SetValue(P(10.0 * parameter, 0.0, 2.5), 1);
                nodes.SetValue(P(10.0, 0.0, 0.0), 2);
                Array acrossBar = Array.CreateInstance(vector3d, 3);
                acrossBar.SetValue(V(0.0, 0.0, 0.0), 0);
                acrossBar.SetValue(V(0.2, 0.0, -1.0), 1);
                acrossBar.SetValue(V(0.0, 0.0, 0.0), 2);
                Array across = Array.CreateInstance(vector3d.MakeArrayType(), 1);
                across.SetValue(acrossBar, 0);
                return (nodes, new[] { new[] { 0, 1, 2 } }, new[] { 0, 2 }, across, new[] { (0, 1), (1, 2) });
            }
            foreach (int type in new[] { 0, 1, 2, 3, 4, -1 })
            {
                object high = Run(Lone(0.44), Array.Empty<int[]>(), 1, type);
                object low = Run(Lone(0.43), Array.Empty<int[]>(), 1, type);
                foreach ((object placed, double parameter) in new[] { (high, 0.44), (low, 0.43) })
                {
                    object built = Get<object>(placed, "Built");
                    var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
                    var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
                    if (feet.Length != 1)
                        throw new InvalidOperationException($"Type {type}, notch at {parameter}: T is 1 and T is at most N, so the tree is a group of one and the span places exactly ONE foot; it built {feet.Length}. An EVEN Type on a span of one tree places one foot, not two and not three, and no central foot is added anywhere.");
                    if (type >= 1 && Math.Abs(X(levelNodes[feet[0]]) - (10.0 * parameter)) > 1.0e-9)
                        throw new InvalidOperationException($"Type {type}: the one foot stands at that notch's own plan position, x = {10.0 * parameter:0.###}; it stands at {X(levelNodes[feet[0]]):0.#########}.");
                }
                object builtHigh = Get<object>(high, "Built");
                object builtLow = Get<object>(low, "Built");
                foreach (string field in new[] { "Peeled", "Gathered", "CentralColumns", "FeetMerged", "FeetClose" })
                {
                    if (Get<int>(builtHigh, field) != Get<int>(builtLow, field))
                        throw new InvalidOperationException($"Type {type}: the placements at 0.44 and 0.43 are IDENTICAL in every diagnostic count; {field} reads {Get<int>(builtHigh, field)} against {Get<int>(builtLow, field)}. Today the 0.43 case drops Families to 0 and disables the span.");
                }
                if (Get<int>(high, "Families") != Get<int>(low, "Families"))
                    throw new InvalidOperationException($"Type {type}: Families reads {Get<int>(high, "Families")} at 0.44 against {Get<int>(low, "Families")} at 0.43.");
                if (!Get<int[]>(high, "Partner").SequenceEqual(Get<int[]>(low, "Partner")))
                    throw new InvalidOperationException($"Type {type}: Partner differs between 0.44 and 0.43; the tree is self-paired either way.");
            }
        }

        // ---- A SPAN OF TWO FREE NOTCHES at Branching 1 (spec section 15).
        // At Type 1 they form ONE group of two, whose two candidates are its
        // two notches, so the foot is their MIDPOINT. At Types 2 to 4, T is
        // at most N and each tree is a group of one standing under its own
        // notch.
        {
            Array nodes = Array.CreateInstance(point3d, 4);
            nodes.SetValue(P(0.0, 0.0, 0.0), 0);
            nodes.SetValue(P(3.0, 0.0, 2.0), 1);
            nodes.SetValue(P(7.0, 0.0, 2.0), 2);
            nodes.SetValue(P(10.0, 0.0, 0.0), 3);
            Array acrossBar = Array.CreateInstance(vector3d, 4);
            for (int i = 0; i < 4; i++)
                acrossBar.SetValue(V(0.0, 0.0, i == 0 || i == 3 ? 0.0 : -1.0), i);
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 1);
            across.SetValue(acrossBar, 0);
            var pairSpan = (nodes, new[] { new[] { 0, 1, 2, 3 } }, new[] { 0, 3 }, across, new[] { (0, 1), (1, 2), (2, 3) });
            object one = Run(pairSpan, Array.Empty<int[]>(), 1, 1);
            object builtOne = Get<object>(one, "Built");
            var nodesOne = ((IEnumerable)Get<object>(builtOne, "Nodes")).Cast<object>().ToArray();
            int[] footOne = FootOfTree(builtOne, 2);
            if (footOne[0] != footOne[1] || Math.Abs(X(nodesOne[footOne[0]]) - 5.0) > 1.0e-9)
                throw new InvalidOperationException($"Two free notches at Type 1 form ONE group of two whose foot is the midpoint of its two candidates, x = 5; they stand at {X(nodesOne[footOne[0]]):0.###} and {X(nodesOne[footOne[1]]):0.###}.");
            foreach (int type in new[] { 2, 3, 4 })
            {
                object placed = Run(pairSpan, Array.Empty<int[]>(), 1, type);
                object built = Get<object>(placed, "Built");
                var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
                int[] footNode = FootOfTree(built, 2);
                if (Math.Abs(X(levelNodes[footNode[0]]) - 3.0) > 1.0e-9 || Math.Abs(X(levelNodes[footNode[1]]) - 7.0) > 1.0e-9)
                    throw new InvalidOperationException($"Type {type}: T is at most N, so each tree is a group of one standing under its own notch at x = 3 and x = 7; they stand at {X(levelNodes[footNode[0]]):0.###} and {X(levelNodes[footNode[1]]):0.###}.");
            }
        }

        // ---- A SPAN WHOSE CHORD LENGTH IS ZERO (spec section 15). A bar
        // whose two cut nodes coincide in plan. It still gets its LAYOUT and
        // its MAINS from section 6, which read only the bar order and the
        // count, so it still builds trees and members; a span with no layout
        // could build nothing at all. Every tree of it is unpaired, there is
        // no common mode to remove because there is no chord to read one
        // along, and it takes ONE foot at the plan mean of its free notches
        // whatever the Type. A stated answer rather than a division by zero.
        {
            Array nodes = Array.CreateInstance(point3d, 5);
            nodes.SetValue(P(0.0, 0.0, 0.0), 0);
            nodes.SetValue(P(1.0, 0.0, 2.0), 1);
            nodes.SetValue(P(0.0, 2.0, 3.0), 2);
            nodes.SetValue(P(-1.0, 0.0, 2.0), 3);
            nodes.SetValue(P(0.0, 0.0, 0.0), 4);
            Array acrossBar = Array.CreateInstance(vector3d, 5);
            for (int i = 0; i < 5; i++)
                acrossBar.SetValue(V(0.0, 0.0, i == 0 || i == 4 ? 0.0 : -1.0), i);
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 1);
            across.SetValue(acrossBar, 0);
            var loop = (nodes, new[] { new[] { 0, 1, 2, 3, 4 } }, new[] { 0, 4 }, across, new[] { (0, 1), (1, 2), (2, 3), (3, 4) });
            const double meanX = (1.0 + 0.0 - 1.0) / 3.0;
            const double meanY = (0.0 + 2.0 + 0.0) / 3.0;
            foreach (int type in new[] { 0, 1, 2, 3, 4 })
            {
                object placed = Run(loop, Array.Empty<int[]>(), 1, type);
                object built = Get<object>(placed, "Built");
                var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
                var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
                if (Get<int>(placed, "SpanDegenerate") != 1)
                    throw new InvalidOperationException($"A span whose two cut nodes coincide in plan raises columns.span_degenerate; SpanDegenerate is {Get<int>(placed, "SpanDegenerate")}.");
                if (feet.Length != 1)
                    throw new InvalidOperationException($"Type {type}: a chord of no length takes ONE foot at the plan mean of its free notches whatever the Type; it built {feet.Length}.");
                if (Math.Abs(X(levelNodes[feet[0]]) - meanX) > 1.0e-9 || Math.Abs(Y(levelNodes[feet[0]]) - meanY) > 1.0e-9)
                    throw new InvalidOperationException($"That one foot is the plan mean ({meanX:0.###}, {meanY:0.###}); it stands at ({X(levelNodes[feet[0]]):0.###}, {Y(levelNodes[feet[0]]):0.###}).");
                if (Get<int>(placed, "GroundPlaced") != type)
                    throw new InvalidOperationException($"Nothing refuses the level: Type {type} asked is Type {type} placed on a degenerate span; it placed {Get<int>(placed, "GroundPlaced")}.");
            }
        }

        // ---- A SPAN WHOSE NOTCHES ALL FALL AT ONE CHORD PARAMETER (spec
        // section 15), which is a bar that doubles back in plan. It takes h
        // from the fallback 1 / (m + 1) and is otherwise an ORDINARY span:
        // its layout, its trees and its mains come from section 6 BY INDEX in
        // bar order, which needs no parameter at all, and its group centre is
        // then one parameter, so every notch of the group is a tied candidate
        // and the foot is their plan mean. It raises span_degenerate at
        // warning and nothing refuses the level.
        {
            Array nodes = Array.CreateInstance(point3d, 5);
            nodes.SetValue(P(0.0, 0.0, 0.0), 0);
            nodes.SetValue(P(5.0, 1.0, 2.0), 1);
            nodes.SetValue(P(5.0, 3.0, 3.0), 2);
            nodes.SetValue(P(5.0, -1.0, 2.0), 3);
            nodes.SetValue(P(10.0, 0.0, 0.0), 4);
            Array acrossBar = Array.CreateInstance(vector3d, 5);
            for (int i = 0; i < 5; i++)
                acrossBar.SetValue(V(0.0, 0.0, i == 0 || i == 4 ? 0.0 : -1.0), i);
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 1);
            across.SetValue(acrossBar, 0);
            var doubled = (nodes, new[] { new[] { 0, 1, 2, 3, 4 } }, new[] { 0, 4 }, across, new[] { (0, 1), (1, 2), (2, 3), (3, 4) });
            object placed = Run(doubled, Array.Empty<int[]>(), 1, 1);
            object built = Get<object>(placed, "Built");
            var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (Get<int>(placed, "SpanDegenerate") != 1)
                throw new InvalidOperationException($"Every notch at one chord parameter raises span_degenerate; SpanDegenerate is {Get<int>(placed, "SpanDegenerate")}.");
            if (feet.Length != 1 || Math.Abs(X(levelNodes[feet[0]]) - 5.0) > 1.0e-9 || Math.Abs(Y(levelNodes[feet[0]]) - 1.0) > 1.0e-9)
                throw new InvalidOperationException($"At Type 1 the one group's centre is that one parameter, so every notch is a tied candidate and the foot is their plan mean, (5, 1); it built {feet.Length} feet, the first at ({X(levelNodes[feet[0]]):0.###}, {Y(levelNodes[feet[0]]):0.###}).");
        }
```

- [ ] **Step 3: Run the gate and read the failures**

Run the gate. The pair-peel check fails because Task 4's peel takes trees singly; the degenerate checks fail on the missing `Placement.SpanDegenerate` and on the divide by a zero chord.

- [ ] **Step 4: Make the peel take its partner**

Replace the peel loop added in Task 4 with:

```csharp
                // A tree that peels takes its mirror PARTNER with it, whether
                // or not the partner is over the cap. Both feet are then Type
                // 0 feet, and they are mirror images wherever the two main
                // notches are, because the pair step made the two aims mirror
                // images. Both members count in Peeled. An unpaired tree
                // peels alone. A self-paired tree peels onto its own Type 0
                // foot, which has no along-chord component because the pair
                // step set its along aim to zero, so it stands directly under
                // its own notch along the chord; it lies on the span's plane
                // of symmetry exactly when that notch does, and no step
                // projects it there.
                //
                // The loop cannot cascade: peeling is one-way, a peeled tree
                // never rejoins a shared foot, and no foot moves on account
                // of a peel.
                var stepped = new bool[trees.Count];
                for (int t = 0; t < trees.Count; t++)
                {
                    if (trees[t].FixedFoot is not null || stepped[t])
                        continue;
                    double lean = MouldGeometry.LeanFromVertical(foot[t], nodes[trees[t].Nodes[0]]);
                    if (lean <= MouldGeometry.MaxLeanDegrees + 1.0e-9)
                        continue;
                    stepped[t] = true;
                    int mate = t < placement.Partner.Length ? placement.Partner[t] : -1;
                    if (mate >= 0 && mate < trees.Count && mate != t && trees[mate].FixedFoot is null)
                        stepped[mate] = true;
                }
                for (int t = 0; t < trees.Count; t++)
                {
                    if (!stepped[t])
                        continue;
                    foot[t] = own[t];
                    result.Peeled++;
                }
```

- [ ] **Step 5: Add the degenerate branch and the counter**

Add to `Placement`:

```csharp
            /// <summary>
            /// Spans of the two degenerate kinds of spec section 15: a chord
            /// of no length, and a notch row that falls at one chord
            /// parameter. Reported as columns.span_degenerate at warning;
            /// nothing refuses the level.
            /// </summary>
            public int SpanDegenerate;
```

Count it in `Place` as each frame is built:

```csharp
                SpanFrame frame = Frame(nodes, bars, span, free);
                placement.Frames.Add(frame);
                if (free.Length > 0 && (frame.ChordZero || frame.OneParameter))
                    placement.SpanDegenerate++;
```

and in `BuildLevel`, ABOVE the `if (level == 0)` split and not inside its `else`. This placement is load-bearing and is the reason the fixture above drives Types 0 to 4 and not 1 to 4: spec section 15 gives a chord-zero span ONE foot at the plan mean of its free notches WHATEVER THE TYPE, and Type 0 is a Type. Written inside the `else`, the branch would never run at level 0, each of the fixture's three trees would take its own vertical aim foot at (1, 0), (0, 2) and (-1, 0), `feet.Length` would be 3 rather than 1, and the plan-mean assertion would fail against an engine that was doing what the spec asked everywhere else. So the loop runs first, over every span, and the trees it answers for are excluded from both branches below:

```csharp
            // A span whose CHORD LENGTH is zero has no chord direction and no
            // parameter. It takes ONE foot at the plan mean of its free
            // notches WHATEVER THE TYPE, Type 0 included, which is why this
            // runs before the level split rather than inside its else. The
            // one-parameter span needs no branch at all: its group centre is
            // that one parameter, so every notch of the group is a tied
            // candidate and GroupFoot already returns their plan mean.
            var chordZeroTree = new bool[trees.Count];
            for (int s = 0; s < placement.Spans.Count; s++)
            {
                SpanFrame frame = placement.Frames[s];
                if (!frame.ChordZero || frame.Nodes.Length == 0)
                    continue;
                double sumX = 0.0;
                double sumY = 0.0;
                foreach (int node in frame.Nodes)
                {
                    sumX += nodes[node].X;
                    sumY += nodes[node].Y;
                }
                var oneFoot = new Point3d(
                    sumX / frame.Nodes.Length, sumY / frame.Nodes.Length, ground);
                for (int t = 0; t < trees.Count; t++)
                {
                    if (trees[t].FixedFoot is not null || trees[t].Span != s)
                        continue;
                    foot[t] = oneFoot;
                    chordZeroTree[t] = true;
                }
            }
```

The `if (level == 0)` branch then skips a tree whose `chordZeroTree` flag is set, and the span loop in the `else` skips a span whose frame reports `ChordZero`, so neither branch overwrites the answer. THE PEEL STILL RUNS over these trees: a chord-zero span's one foot can be out of reach of a notch just as any other foot can, and nothing in section 15 exempts it.

Add one sentence to the doc comment above the `own` array in `BuildLevel`: a tree whose main notch is at or below GROUND cannot meet the lean cap from any foot, so it peels, with its partner, and its Type 0 foot lies directly under that notch because the aim ray has no rise to travel. `ownRise` is already clamped at zero, so the case is recorded rather than discovered.

- [ ] **Step 6: Run the gate green, then commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/ColumnPlacement.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(columns): the peel takes its mirror partner, and every degenerate span has a stated answer"
```

---

### Task 6: Where two principal lines touch

Spec section 10 entire. BOTH LINES HOLD THE NOTCH. The owner is decided by the SPANS and not by the trace, and the load at a shared node is counted exactly once and in full, which is Param's ruling of 2026-09-01 made arithmetic.

**Files:**
- Modify: `plugin/native_v02/Components/ColumnPlacement.cs` (`Tree` at 75-96; `Place`'s span loop; `BuildLevel`'s `own` array and the member build at 1134-1189; the peel of Task 5; `Placement`)
- Test: `tests/native_smoke/Program.cs`: the crossing fixtures at 6732-6815, 6897-6960 and 7341-7386, plus three new blocks

**Interfaces:**
- Consumes: Task 2's `MouldGeometry.NodeLoads`; Task 3's `Place` arguments `pull` and `nodePull` and `Placement.Frames`; Task 4's `GroupFoot`, which already lists every notch of a group whether owned or borrowed.
- Produces, and Tasks 7, 8, 9 and 10 depend on these exact names:
  - `Tree.Owned` (public `bool[]`, aligned with `Tree.Nodes`: whether this tree builds a member to that notch).
  - `Tree.HeadMain` (public `int`, the index into `Nodes` of the tree's innermost OWNED notch, 0 on every tree that owns its main, -1 on a tree with no owned notch).
  - `Placement.SharedNotches` (public `int`, the notches held by two spans at once).
  - `public static Vector3d HeadPull(Point3d[] nodes, int[][] bars, Vector3d[][] pull, Vector3d[] nodePull, int node, IReadOnlyList<(int Bar, int Position)> holders)`

- [ ] **Step 1: Write the head-pull arithmetic check, red**

```csharp
        // ---- THE LOAD AT A SHARED NODE (spec section 10, Param's ruling of
        // 2026-09-01). Summing the bars' TRANSVERSE pulls at a shared node
        // DOUBLE COUNTS: BarLoads sums every member incident on a node except
        // the edges running ALONG that bar, so at a node shared by bars A and
        // B, pull_A is the infill plus B's along-bar edges and pull_B is the
        // infill plus A's, and their sum is the infill TWICE. On any real
        // vault the infill dominates, so the naive fix comes out close to
        // DOUBLE. The head pull is instead
        //     headPull = (pull_1 + ... + pull_k) - (k - 1) * total
        // with total the node's whole incident pull taken once, which is the
        // node's infill pull exactly once.
        {
            MethodInfo headPull = RequirePublicStatic(engine, "HeadPull");
            Type holderType = typeof(ValueTuple<int, int>);
            Type holderList = typeof(List<>).MakeGenericType(holderType);
            object Holders(params (int Bar, int Position)[] pairs)
            {
                object list = Activator.CreateInstance(holderList)!;
                MethodInfo add = holderList.GetMethod("Add")!;
                foreach ((int bar, int position) in pairs)
                    add.Invoke(list, new[] { Activator.CreateInstance(holderType, bar, position) });
                return list;
            }
            // One node at the origin. Bar 0 runs along x, bar 1 along y, bar
            // 2 along z. Infill of (0, 0, -6) at the node; each bar's own
            // along edges pull it (2, 0, 0), (0, 2, 0) and (0, 0, 2). The
            // node's whole pull is the infill plus all three.
            Array nodes = Array.CreateInstance(point3d, 7);
            nodes.SetValue(P(0.0, 0.0, 0.0), 0);
            nodes.SetValue(P(-1.0, 0.0, 0.0), 1);
            nodes.SetValue(P(1.0, 0.0, 0.0), 2);
            nodes.SetValue(P(0.0, -1.0, 0.0), 3);
            nodes.SetValue(P(0.0, 1.0, 0.0), 4);
            nodes.SetValue(P(0.0, 0.0, -1.0), 5);
            nodes.SetValue(P(0.0, 0.0, 1.0), 6);
            var barsHere = new[] { new[] { 1, 0, 2 }, new[] { 3, 0, 4 }, new[] { 5, 0, 6 } };
            Array pullArray = Array.CreateInstance(vector3d.MakeArrayType(), 3);
            // BarLoads-shaped: the infill plus every OTHER bar's along edges.
            (double X, double Y, double Z)[] barPull =
            {
                (0.0, 2.0, -4.0), (2.0, 0.0, -4.0), (2.0, 2.0, -6.0),
            };
            for (int b = 0; b < 3; b++)
            {
                Array bar = Array.CreateInstance(vector3d, 3);
                bar.SetValue(V(0.0, 0.0, 0.0), 0);
                bar.SetValue(V(barPull[b].X, barPull[b].Y, barPull[b].Z), 1);
                bar.SetValue(V(0.0, 0.0, 0.0), 2);
                pullArray.SetValue(bar, b);
            }
            Array wholeNode = Array.CreateInstance(vector3d, 7);
            for (int i = 0; i < 7; i++)
                wholeNode.SetValue(V(0.0, 0.0, 0.0), i);
            wholeNode.SetValue(V(2.0, 2.0, -4.0), 0);

            // k = 1: an ordinary unshared notch. The head pull is that bar's
            // OWN untransversed pull unchanged, so the (k - 1) term is
            // demonstrated to vanish rather than assumed to.
            object single = headPull.Invoke(null, new object?[] { nodes, barsHere, pullArray, wholeNode, 0, Holders((0, 1)) })!;
            if (Math.Abs(VX(single)) > 1.0e-12 || Math.Abs(VY(single) - 2.0) > 1.0e-12 || Math.Abs(VZ(single) + 4.0) > 1.0e-12)
                throw new InvalidOperationException($"At k = 1 the head pull is that bar's own untransversed pull unchanged, (0, 2, -4); it read ({VX(single):0.#####}, {VY(single):0.#####}, {VZ(single):0.#####}).");

            // k = 2: two pulls less one whole pull, which recovers the node's
            // infill exactly once: (0,2,-4) + (2,0,-4) - (2,2,-4) = (0,0,-4).
            object twoBars = headPull.Invoke(null, new object?[] { nodes, barsHere, pullArray, wholeNode, 0, Holders((0, 1), (1, 1)) })!;
            if (Math.Abs(VX(twoBars)) > 1.0e-12 || Math.Abs(VY(twoBars)) > 1.0e-12 || Math.Abs(VZ(twoBars) + 4.0) > 1.0e-12)
            {
                throw new InvalidOperationException(
                    $"At k = 2 the head pull is the two pulls less ONE whole pull, (0, 0, -4); it read ({VX(twoBars):0.#####}, {VY(twoBars):0.#####}, {VZ(twoBars):0.#####}). "
                    + "The naive sum of the two would read (2, 2, -8), which counts the node's infill TWICE.");
            }

            // k = 3: three pulls less TWICE the node's whole pull, so the
            // general form is exercised and not only the two-bar case:
            // (0,2,-4)+(2,0,-4)+(2,2,-6) - 2*(2,2,-4) = (0,0,-6).
            object threeBars = headPull.Invoke(null, new object?[] { nodes, barsHere, pullArray, wholeNode, 0, Holders((0, 1), (1, 1), (2, 1)) })!;
            if (Math.Abs(VX(threeBars)) > 1.0e-12 || Math.Abs(VY(threeBars)) > 1.0e-12 || Math.Abs(VZ(threeBars) + 6.0) > 1.0e-12)
                throw new InvalidOperationException($"At k = 3 the head pull is the three pulls less TWICE the node's whole pull, (0, 0, -6); it read ({VX(threeBars):0.#####}, {VY(threeBars):0.#####}, {VZ(threeBars):0.#####}).");

            // A RUN TRACED TWICE counts once, which is what keeps
            // columns.overlap true: two bars are the same run at a node when
            // they reach it through the same two neighbouring net vertices,
            // in either order.
            var traced = new[] { new[] { 1, 0, 2 }, new[] { 2, 0, 1 }, new[] { 5, 0, 6 } };
            object doubled = headPull.Invoke(null, new object?[] { nodes, traced, pullArray, wholeNode, 0, Holders((0, 1), (1, 1)) })!;
            if (Math.Abs(VY(doubled) - 2.0) > 1.0e-12 || Math.Abs(VZ(doubled) + 4.0) > 1.0e-12)
                throw new InvalidOperationException($"One bar traced twice is ONE distinct bar at the node, so k is 1 and the head pull is its own pull; it read ({VX(doubled):0.#####}, {VY(doubled):0.#####}, {VZ(doubled):0.#####}).");
        }
```

- [ ] **Step 2: Add `HeadPull` and run the gate green on it**

In `plugin/native_v02/Components/ColumnPlacement.cs`:

```csharp
        /// <summary>
        /// The pull the HEAD at a shared node actually carries, counted
        /// exactly once and in full. PARAM RULED ON 2026-09-01 that this is
        /// to be fixed properly, and the arithmetic is stated because the
        /// obvious form is wrong.
        ///
        /// Summing the bars' transverse pulls DOUBLE COUNTS.
        /// <c>MouldGeometry.BarLoads</c> sums every member incident on a node
        /// except the edges running ALONG that bar, so at a node shared by
        /// bars A and B, pull_A is the infill plus B's along-bar edges and
        /// pull_B is the infill plus A's, and their sum is the infill TWICE.
        /// On any real vault the infill dominates, so the head load at a
        /// crossing would come out close to double, and with it the axial
        /// force, the load path and Auto's choice.
        ///
        /// Let the node be held by k DISTINCT bars, two bars being the same
        /// run at a node when they reach it through the same two neighbouring
        /// net vertices in either order, so a run traced twice counts once.
        /// Then headPull = (pull_1 + ... + pull_k) - (k - 1) * total, which
        /// is the node's infill pull exactly once, since each pull_i is total
        /// less that bar's own along-bar contribution. For k = 1 it is
        /// pull_1 and nothing changes anywhere.
        ///
        /// The head pull is then projected off every distinct bar tangent at
        /// the node in turn, by Gram-Schmidt, a tangent being dropped when
        /// its residual norm falls to 1e-9 of its own length because it is
        /// parallel to one already taken. For k = 1 that is BarTransverse
        /// exactly, so every single-bar number in the harness is untouched.
        /// Where the surviving tangents span all three dimensions the residue
        /// is zero, AimFrom returns vertical, and the column stands plumb,
        /// which is the honest answer for a node whose every direction is
        /// already carried to an anchor.
        /// </summary>
        public static Vector3d HeadPull(
            Point3d[] nodes,
            int[][] bars,
            Vector3d[][] pull,
            Vector3d[] nodePull,
            int node,
            IReadOnlyList<(int Bar, int Position)> holders)
        {
            // Distinct runs, keyed on the two neighbouring net vertices in
            // either order.
            var seen = new HashSet<(int, int)>();
            var distinct = new List<(int Bar, int Position)>();
            foreach ((int b, int p) in holders)
            {
                int[] bar = bars[b];
                int before = bar[Math.Max(p - 1, 0)];
                int after = bar[Math.Min(p + 1, bar.Length - 1)];
                (int, int) key = before <= after ? (before, after) : (after, before);
                if (seen.Add(key))
                    distinct.Add((b, p));
            }

            var summed = Vector3d.Zero;
            foreach ((int b, int p) in distinct)
                summed += pull[b][p];
            int k = distinct.Count;
            Vector3d head = summed - ((k - 1) * nodePull[node]);

            // Project off every distinct bar tangent in turn.
            var taken = new List<Vector3d>();
            foreach ((int b, int p) in distinct)
            {
                int[] bar = bars[b];
                Vector3d tangent = nodes[bar[Math.Min(p + 1, bar.Length - 1)]]
                    - nodes[bar[Math.Max(p - 1, 0)]];
                double length = tangent.Length;
                if (length <= 1.0e-12)
                    continue;
                tangent = new Vector3d(tangent.X / length, tangent.Y / length, tangent.Z / length);
                foreach (Vector3d already in taken)
                {
                    double dot = (tangent.X * already.X) + (tangent.Y * already.Y) + (tangent.Z * already.Z);
                    tangent -= dot * already;
                }
                double residual = tangent.Length;
                if (residual <= 1.0e-9)
                    continue;
                tangent = new Vector3d(tangent.X / residual, tangent.Y / residual, tangent.Z / residual);
                taken.Add(tangent);
                double along = (head.X * tangent.X) + (head.Y * tangent.Y) + (head.Z * tangent.Z);
                head -= along * tangent;
            }
            return head;
        }
```

Run the gate. The head-pull block goes green; everything else is unchanged because nothing calls `HeadPull` yet.

- [ ] **Step 3: Write the crossing fixture, red**

Delete `tests/native_smoke/Program.cs:6732-6815` entire, the case that asserts a crossed span is placed UNMIRRORED. Spec section 17.1 is explicit: DELETED WITH ITS RULE, and the replacement must assert the OPPOSITE, which is the clearest possible demonstration that the rule changed. Insert in its place:

```csharp
        // ---- A SPAN WHOSE NOTCH IS CLAIMED BY A CROSSING (spec sections 10
        // and 17). A pillow surface ten metres square: an arch of eleven
        // nodes along X at y = 5 and a rib of eleven nodes along Y at x = 3,
        // both anchored at their ends, meeting at ONE shared node at the
        // arch's position 3, which is off centre.
        //
        // Both spans therefore hold NINE free notches AND equal chords, which
        // is deliberate: it drives the owner rule past both of its first two
        // clauses onto the geometric keys, where the arch's endpoint pair
        // begins at (0, 5) and the rib's at (3, 0), so the ARCH owns by the
        // lower X. Every regularly ribbed vault, cross vault and dome of
        // equal ribs and hoops reaches that tie, so this is the normal case
        // and not a contrivance.
        {
            (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) Pillow(bool withRib)
            {
                int count = withRib ? 21 : 11;
                Array nodes = Array.CreateInstance(point3d, count);
                var edges = new List<(int, int)>();
                Array archBar = Array.CreateInstance(vector3d, 11);
                for (int i = 0; i < 11; i++)
                {
                    double s = i / 10.0;
                    nodes.SetValue(P(10.0 * s, 5.0, 2.5 * 4.0 * s * (1.0 - s)), i);
                    archBar.SetValue(V(0.0, 0.0, -1.0), i);
                    if (i > 0)
                        edges.Add((i - 1, i));
                }
                if (!withRib)
                {
                    Array only = Array.CreateInstance(vector3d.MakeArrayType(), 1);
                    only.SetValue(archBar, 0);
                    return (nodes, new[] { Enumerable.Range(0, 11).ToArray() }, new[] { 0, 10 }, only, edges.ToArray());
                }
                // The rib runs along Y at x = 3 through the arch's node 3,
                // which is the arch's bar position 3 and stands at x = 3
                // exactly. Its own ten other nodes take ids 11 to 20.
                var ribNodes = new List<int>();
                Array ribBar = Array.CreateInstance(vector3d, 11);
                for (int i = 0; i < 11; i++)
                {
                    double s = i / 10.0;
                    ribBar.SetValue(V(0.0, 0.0, -1.0), i);
                    if (i == 5)
                    {
                        ribNodes.Add(3);
                        continue;
                    }
                    int id = 11 + (i < 5 ? i : i - 1);
                    nodes.SetValue(P(3.0, 10.0 * s, 2.5 * 4.0 * s * (1.0 - s)), id);
                    ribNodes.Add(id);
                }
                for (int i = 1; i < 11; i++)
                    edges.Add((ribNodes[i - 1], ribNodes[i]));
                Array across = Array.CreateInstance(vector3d.MakeArrayType(), 2);
                across.SetValue(archBar, 0);
                across.SetValue(ribBar, 1);
                return (nodes, new[] { Enumerable.Range(0, 11).ToArray(), ribNodes.ToArray() },
                    new[] { 0, 10, ribNodes[0], ribNodes[10] }, across, edges.ToArray());
            }

            var crossed = Pillow(withRib: true);
            var control = Pillow(withRib: false);
            foreach (int type in new[] { 1, 2, 3, 4 })
            {
                object placedCrossed = Run(crossed, Array.Empty<int[]>(), 1, type);
                object placedControl = Run(control, Array.Empty<int[]>(), 1, type);
                object builtCrossed = Get<object>(placedCrossed, "Built");
                object builtControl = Get<object>(placedControl, "Built");
                var trees = ((IEnumerable)Get<object>(placedCrossed, "Trees")).Cast<object>().ToArray();
                var archTrees = trees.Where(t => Get<int>(t, "Bar") == 0).ToArray();
                int freeCount = archTrees.Sum(t => Get<int[]>(t, "Nodes").Length);
                if (freeCount != 9)
                    throw new InvalidOperationException($"BOTH lines hold a shared notch, so the arch's free notch count is 9 and NOT 8; it is {freeCount}. Neither span acquires a hole, so neither span's symmetry can be broken by a crossing.");
                var crossedNodes = ((IEnumerable)Get<object>(builtCrossed, "Nodes")).Cast<object>().ToArray();
                var controlNodes = ((IEnumerable)Get<object>(builtControl, "Nodes")).Cast<object>().ToArray();
                int[] crossedFeet = FootOfTree(builtCrossed, trees.Length);
                int[] controlFeet = FootOfTree(builtControl, 9);
                for (int t = 0; t < 9; t++)
                {
                    if (Math.Abs(X(crossedNodes[crossedFeet[t]]) - X(controlNodes[controlFeet[t]])) > 1.0e-9)
                    {
                        throw new InvalidOperationException(
                            $"Type {type}: the crossed arch places the same LAYOUT, the same groups and the same FEET as the uncrossed control, because none "
                            + $"of that arithmetic reads a force; tree {t} stands at {X(crossedNodes[crossedFeet[t]]):0.#########} against the control's {X(controlNodes[controlFeet[t]]):0.#########}.");
                    }
                }
                if (Get<int>(placedCrossed, "SharedNotches") != 1)
                    throw new InvalidOperationException($"One notch is held by two spans at once; SharedNotches is {Get<int>(placedCrossed, "SharedNotches")}.");
                // Count heads and members from the BUILT MEMBER SET and the
                // block's heads, never from Tree.Nodes: under section 10 both
                // spans' trees LIST the shared node and only one builds to it.
                var members = MembersOf(builtCrossed);
                var levelNodes = crossedNodes;
                object shared = crossed.Nodes.GetValue(3)!;
                int heads = members.Count(m =>
                    Math.Abs(X(levelNodes[m.Upper]) - X(shared)) < 1.0e-9 &&
                    Math.Abs(Y(levelNodes[m.Upper]) - Y(shared)) < 1.0e-9 &&
                    Math.Abs(Z(levelNodes[m.Upper]) - Z(shared)) < 1.0e-9);
                if (heads != 1)
                    throw new InvalidOperationException($"The shared node is one point in space and carries EXACTLY ONE column head; {heads} members end at it.");
                object owner = trees.First(t => Get<int[]>(t, "Nodes").Contains(3) && Get<bool[]>(t, "Owned")[Array.IndexOf(Get<int[]>(t, "Nodes"), 3)]);
                if (Get<int>(owner, "Bar") != 0)
                    throw new InvalidOperationException("The ARCH owns this head, by the lower X of its endpoint pair's first point, (0, 5) against the rib's (3, 0). Both spans tie on free notch count and on chord length, which is what every regularly ribbed vault gives.");
            }
            // And the answer is IDENTICAL with the bars handed over in the
            // other order, which is the assertion the present engine fails
            // most alarmingly and which a tie-break ending in the bar index
            // could never satisfy on this net.
            var swapped = (crossed.Nodes, new[] { crossed.Bars[1], crossed.Bars[0] }, crossed.Anchors,
                SwapBars(crossed.Across), crossed.Edges);
            foreach (int type in new[] { 0, 1, 2, 3, 4 })
            {
                object a = Run(crossed, Array.Empty<int[]>(), 1, type);
                object b = Run(swapped, Array.Empty<int[]>(), 1, type);
                object builtA = Get<object>(a, "Built");
                object builtB = Get<object>(b, "Built");
                var feetA = ((IEnumerable)Get<object>(builtA, "Nodes")).Cast<object>()
                    .Select(n => (X(n), Y(n), Z(n))).OrderBy(p => p.Item1).ThenBy(p => p.Item2).ThenBy(p => p.Item3).ToArray();
                var feetB = ((IEnumerable)Get<object>(builtB, "Nodes")).Cast<object>()
                    .Select(n => (X(n), Y(n), Z(n))).OrderBy(p => p.Item1).ThenBy(p => p.Item2).ThenBy(p => p.Item3).ToArray();
                if (feetA.Length != feetB.Length)
                    throw new InvalidOperationException($"Type {type}: the two bar orders build {feetA.Length} and {feetB.Length} nodes. The owner rule reads only properties of the SPAN, so every notch shared between the same two spans resolves the same way.");
                for (int i = 0; i < feetA.Length; i++)
                {
                    if (Math.Abs(feetA[i].Item1 - feetB[i].Item1) > 1.0e-12 ||
                        Math.Abs(feetA[i].Item2 - feetB[i].Item2) > 1.0e-12 ||
                        Math.Abs(feetA[i].Item3 - feetB[i].Item3) > 1.0e-12)
                    {
                        throw new InvalidOperationException($"Type {type}: the placement is identical to 1e-12 with the bars handed over in either order; node {i} differs.");
                    }
                }
                foreach (string field in new[] { "SharedNotches", "SpansWithTrees", "Families" })
                {
                    if (Get<int>(a, field) != Get<int>(b, field))
                        throw new InvalidOperationException($"Type {type}: {field} reads {Get<int>(a, field)} one way round and {Get<int>(b, field)} the other. Nothing in the model tells the author which order Pattern traced.");
                }
            }
        }
```

with a small local helper beside `InSpanFrame`:

```csharp
        Array SwapBars(Array across)
        {
            Array swapped = Array.CreateInstance(across.GetType().GetElementType()!, across.Length);
            for (int i = 0; i < across.Length; i++)
                swapped.SetValue(across.GetValue(across.Length - 1 - i)!, i);
            return swapped;
        }
```

- [ ] **Step 4: Write the eighteen-units check, red**

```csharp
        // ---- THE EIGHTEEN UNITS COME BACK AS EIGHTEEN (spec sections 10, 17
        // and 18.1). The investigation applied eighteen units of vertical
        // pull to a net whose two bars share one node and measured SEVENTEEN
        // counted, the missing unit being the other bar's share at the
        // crossing. Under Param's ruling of 2026-09-01 this is an EQUALITY,
        // not a bound, and the seventeen is printed beside it so the fix is a
        // number in the record.
        {
            // THE NET THAT ACTUALLY APPLIES EIGHTEEN. Two bars of ELEVEN
            // sharing one node: 22 bar positions less the four anchors is
            // EIGHTEEN free bar positions, each declaring one unit of
            // downward pull, over SEVENTEEN distinct free nodes. That is the
            // investigation's own arithmetic and it is the reason the number
            // is eighteen: the seventeenth node, the crossing, is declared by
            // BOTH bars and carries two units, and the engine as it stands
            // counts one of them.
            //
            // An earlier draft of this item built two bars of FIVE and then
            // asserted eighteen against them. That net has ten bar positions,
            // six free ones and five distinct free nodes, so its counted total
            // can only ever be five or six and the check could never pass
            // against any engine at all. The geometry is restated to the net
            // the measurement was taken on.
            const int span = 11;
            Array nodes = Array.CreateInstance(point3d, (2 * span) - 1);
            var archBar = new int[span];
            var ribBar = new int[span];
            Array acrossA = Array.CreateInstance(vector3d, span);
            Array acrossB = Array.CreateInstance(vector3d, span);
            var netEdges = new List<(int, int)>();
            for (int i = 0; i < span; i++)
            {
                double s = i / (double)(span - 1);
                nodes.SetValue(P(-5.0 + (10.0 * s), 0.0, 3.0 * 4.0 * s * (1.0 - s)), i);
                archBar[i] = i;
                acrossA.SetValue(V(0.0, 0.0, -1.0), i);
                if (i > 0)
                    netEdges.Add((i - 1, i));
            }
            int crossing = span / 2;   // the arch's own middle node, id 5
            for (int i = 0; i < span; i++)
            {
                double s = i / (double)(span - 1);
                acrossB.SetValue(V(0.0, 0.0, -1.0), i);
                if (i == crossing)
                {
                    ribBar[i] = crossing;
                    continue;
                }
                int id = span + (i < crossing ? i : i - 1);
                nodes.SetValue(P(0.0, -5.0 + (10.0 * s), 3.0 * 4.0 * s * (1.0 - s)), id);
                ribBar[i] = id;
            }
            for (int i = 1; i < span; i++)
                netEdges.Add((ribBar[i - 1], ribBar[i]));
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 2);
            across.SetValue(acrossA, 0);
            across.SetValue(acrossB, 1);
            var anchorSet = new[] { archBar[0], archBar[span - 1], ribBar[0], ribBar[span - 1] };
            var net = (nodes, new[] { archBar, ribBar }, anchorSet, across, netEdges.ToArray());

            // APPLIED is COMPUTED from the fixture rather than written as a
            // literal, so the check cannot drift away from its own geometry
            // the way the earlier draft did: it is the sum of the declared
            // vertical pull over every free bar position of both bars.
            double applied = 0.0;
            for (int b = 0; b < 2; b++)
            {
                Array barAcross = (Array)across.GetValue(b)!;
                int[] bar = b == 0 ? archBar : ribBar;
                for (int k = 0; k < span; k++)
                {
                    if (!anchorSet.Contains(bar[k]))
                        applied += Math.Abs(VZ(barAcross.GetValue(k)!));
                }
            }
            if (Math.Abs(applied - 18.0) > 1.0e-12)
                throw new InvalidOperationException($"This fixture is the eighteen-unit net of the investigation; it applies {applied:0.###}.");

            object placed = Run(net, Array.Empty<int[]>(), 1, 1);
            var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
            double counted = trees.Sum(t => Get<double[]>(t, "Load").Sum());
            if (Math.Abs(counted - applied) > 1.0e-12)
            {
                throw new InvalidOperationException(
                    $"Eighteen units of vertical pull applied to this net come back as EIGHTEEN counted; head_load_total reads {counted:0.#########}. "
                    + "The engine as it stands read 17: the other bar's share at the crossing was never counted, and the undercount propagated into "
                    + "the aim, the axial force, the load path and Auto's choice. This is an EQUALITY and not a bound.");
            }
            Console.WriteLine($"      head_load_total {counted:0.###} applied {applied:0.###}; the engine as it stands read 17.");

            // And the borrowed notch carries ZERO rather than a second copy:
            // sixteen unshared notches at one unit each and the crossing at
            // two is eighteen, and the crossing's two units sit on ONE tree.
            object owner = trees.First(t => Get<int[]>(t, "Nodes").Contains(crossing) && Get<bool[]>(t, "Owned")[Array.IndexOf(Get<int[]>(t, "Nodes"), crossing)]);
            double ownerHead = Get<double[]>(owner, "Load")[Array.IndexOf(Get<int[]>(owner, "Nodes"), crossing)];
            if (Math.Abs(ownerHead - 2.0) > 1.0e-12)
                throw new InvalidOperationException($"The shared node's head carries the node's WHOLE pull, both ribs' units, ONCE: two units. It carries {ownerHead:0.#########}.");
            object borrower = trees.First(t => Get<int[]>(t, "Nodes").Contains(crossing) && !Get<bool[]>(t, "Owned")[Array.IndexOf(Get<int[]>(t, "Nodes"), crossing)]);
            if (Math.Abs(Get<double[]>(borrower, "Load")[Array.IndexOf(Get<int[]>(borrower, "Nodes"), crossing)]) > 1.0e-12)
                throw new InvalidOperationException("A BORROWED notch enters Load with a load of zero; its head is not that tree's to carry, and a second copy here would be the double count arriving by another road.");

            // A rib carrying a deliberately large ALONG-BAR tension must not
            // raise the head load, which is the check that catches the double
            // count: the along-bar contribution belongs to the anchors. The
            // bound is the PLAIN run's own head load rather than a literal, so
            // the assertion says what it means whatever the fixture's units.
            Array heavyB = Array.CreateInstance(vector3d, span);
            for (int i = 0; i < span; i++)
                heavyB.SetValue(V(0.0, 0.0, -1.0), i);
            heavyB.SetValue(V(0.0, 50.0, -1.0), crossing);
            Array heavy = Array.CreateInstance(vector3d.MakeArrayType(), 2);
            heavy.SetValue(acrossA, 0);
            heavy.SetValue(heavyB, 1);
            object placedHeavy = Run((nodes, net.Item2, net.Item3, heavy, net.Item5), Array.Empty<int[]>(), 1, 1);
            var heavyTrees = ((IEnumerable)Get<object>(placedHeavy, "Trees")).Cast<object>().ToArray();
            object headTree = heavyTrees.First(t => Get<int[]>(t, "Nodes").Contains(crossing) && Get<bool[]>(t, "Owned")[Array.IndexOf(Get<int[]>(t, "Nodes"), crossing)]);
            double headLoad = Get<double[]>(headTree, "Load")[Array.IndexOf(Get<int[]>(headTree, "Nodes"), crossing)];
            if (Math.Abs(headLoad - ownerHead) > 1.0e-9)
                throw new InvalidOperationException($"A large ALONG-BAR tension on the rib must NOT change the head load at the shared node; it read {headLoad:0.#####} against the plain run's {ownerHead:0.#####}. The along-bar contribution belongs to the anchors and the Gram-Schmidt projection is what removes it.");
        }
```

- [ ] **Step 5: Write the two-lines-that-touch check, red**

```csharp
The net is written out as a builder, exactly as `Pillow` is in Step 3, rather than described in prose: the earlier draft left `touching` undefined and the four cases below could not be run at all. The arch is eleven nodes along X at y = 5, anchored at both ends, the same shape the crossing fixture uses. A rib runs along Y at a stated x, rising to meet the arch, its LAST node BEING the arch node it touches, and it is anchored at its FIRST node only, so its far end is a free notch of kind `end`.

```csharp
        // ---- TWO PRINCIPAL LINES THAT TOUCH (spec sections 10 and 17). The
        // rib runs UP to the arch and stops on it, so the shared node is the
        // rib's END and is neither an anchor nor a rim notch. The expected
        // owner is computed FROM THE RULE and not assumed: with eleven rib
        // nodes anchored at ONE end the rib holds TEN free notches against the
        // arch's nine and THE RIB OWNS by the first clause, the greater free
        // notch count. (The earlier draft of this item asserted the arch,
        // which is the rule read backwards.)
        {
            // The arch, and one or more ribs. Each rib is given by the arch
            // bar position it lands on and its own node count; it runs along
            // Y at that arch node's x, from y = -5 up to the arch node, and
            // is anchored at its first node only.
            (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) Touching(
                params (int At, int Count)[] ribs)
            {
                int total = 11 + ribs.Sum(r => r.Count - 1);
                Array nodes = Array.CreateInstance(point3d, total);
                Array archBar = Array.CreateInstance(vector3d, 11);
                var edges = new List<(int, int)>();
                var bars = new List<int[]>();
                var anchors = new List<int> { 0, 10 };
                for (int i = 0; i < 11; i++)
                {
                    double s = i / 10.0;
                    nodes.SetValue(P(10.0 * s, 5.0, 2.5 * 4.0 * s * (1.0 - s)), i);
                    archBar.SetValue(V(0.0, 0.0, -1.0), i);
                    if (i > 0)
                        edges.Add((i - 1, i));
                }
                bars.Add(Enumerable.Range(0, 11).ToArray());
                Array across = Array.CreateInstance(vector3d.MakeArrayType(), 1 + ribs.Length);
                across.SetValue(archBar, 0);
                int next = 11;
                for (int r = 0; r < ribs.Length; r++)
                {
                    (int landsAt, int count) = ribs[r];
                    double x = X(nodes.GetValue(landsAt)!);
                    double top = Z(nodes.GetValue(landsAt)!);
                    var bar = new int[count];
                    Array ribAcross = Array.CreateInstance(vector3d, count);
                    for (int i = 0; i < count; i++)
                    {
                        double s = i / (double)(count - 1);
                        ribAcross.SetValue(V(0.0, 0.0, -1.0), i);
                        if (i == count - 1)
                        {
                            bar[i] = landsAt;
                            continue;
                        }
                        nodes.SetValue(P(x, -5.0 + (10.0 * s), top * s), next);
                        bar[i] = next;
                        next++;
                    }
                    for (int i = 1; i < count; i++)
                        edges.Add((bar[i - 1], bar[i]));
                    // ANCHORED AT ITS FIRST NODE ONLY: its far end is the
                    // shared node and its near end is the springing.
                    anchors.Add(bar[0]);
                    bars.Add(bar);
                    across.SetValue(ribAcross, r + 1);
                }
                return (nodes, bars.ToArray(), anchors.ToArray(), across, edges.ToArray());
            }

            // The owner rule's own keys, recomputed in the check from the two
            // spans' endpoint pairs, so the expected answer is derived rather
            // than asserted. Free notch count first, then chord length, then
            // the endpoint pair sorted lexicographically by X then Y.
            int OwnerByRule(
                (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) net,
                object placed, int barA, int barB)
            {
                var spans = ((IEnumerable)Get<object>(placed, "Spans")).Cast<object>().ToArray();
                var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
                int Count(int bar) => trees.Where(t => Get<int>(t, "Bar") == bar).Sum(t => Get<int[]>(t, "Nodes").Length);
                (double X, double Y)[] Ends(int bar)
                {
                    object span = spans.First(s => Get<int>(s, "Bar") == bar);
                    int[] barNodes = net.Bars[bar];
                    object p0 = net.Nodes.GetValue(barNodes[Get<int>(span, "First")])!;
                    object p1 = net.Nodes.GetValue(barNodes[Get<int>(span, "Last")])!;
                    return new[] { (X(p0), Y(p0)), (X(p1), Y(p1)) }
                        .OrderBy(p => p.Item1).ThenBy(p => p.Item2).ToArray();
                }
                double Chord(int bar)
                {
                    (double X, double Y)[] e = Ends(bar);
                    double dx = e[1].X - e[0].X;
                    double dy = e[1].Y - e[0].Y;
                    return Math.Sqrt((dx * dx) + (dy * dy));
                }
                if (Count(barA) != Count(barB))
                    return Count(barA) > Count(barB) ? barA : barB;
                double tolerance = 1.0e-9 * Math.Min(Chord(barA), Chord(barB));
                if (Math.Abs(Chord(barA) - Chord(barB)) > tolerance)
                    return Chord(barA) > Chord(barB) ? barA : barB;
                (double X, double Y)[] ea = Ends(barA);
                (double X, double Y)[] eb = Ends(barB);
                for (int k = 0; k < 2; k++)
                {
                    if (Math.Abs(ea[k].X - eb[k].X) > tolerance)
                        return ea[k].X < eb[k].X ? barA : barB;
                    if (Math.Abs(ea[k].Y - eb[k].Y) > tolerance)
                        return ea[k].Y < eb[k].Y ? barA : barB;
                }
                return Math.Min(barA, barB);
            }

            void RequireOwner(
                (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) net,
                int shared, int expectedBar, string why)
            {
                object placed = Run(net, Array.Empty<int[]>(), 1, 2);
                var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
                int derived = OwnerByRule(net, placed, 0, 1);
                if (derived != expectedBar)
                    throw new InvalidOperationException($"The check's own reading of the owner rule gives bar {derived} where the item states bar {expectedBar}: {why}. One of the two is wrong and it must be settled before the engine is judged.");
                object ownerTree = trees.First(t =>
                    Get<int[]>(t, "Nodes").Contains(shared) &&
                    Get<bool[]>(t, "Owned")[Array.IndexOf(Get<int[]>(t, "Nodes"), shared)]);
                if (Get<int>(ownerTree, "Bar") != expectedBar)
                    throw new InvalidOperationException($"Bar {expectedBar} owns the head at node {shared}: {why}. Bar {Get<int>(ownerTree, "Bar")} built the member.");
                foreach (object other in trees.Where(t => Get<int>(t, "Bar") != expectedBar && Get<int[]>(t, "Nodes").Contains(shared)))
                {
                    if (Get<bool[]>(other, "Owned")[Array.IndexOf(Get<int[]>(other, "Nodes"), shared)])
                        throw new InvalidOperationException($"The other line HOLDS the notch for the layout and the pairing and builds NO member to it; bar {Get<int>(other, "Bar")} built one at node {shared}.");
                }
            }

            // 1. THE RIB OWNS, by the greater free notch count: ten against
            //    nine, because the rib is anchored at one end only and its
            //    free end is a free notch of kind end.
            RequireOwner(
                Touching((At: 5, Count: 11)), 5, 1,
                "the rib holds TEN free notches against the arch's nine, which is the FIRST clause");

            // 2. THE ARCH OWNS, the counts deliberately unequal the other
            //    way, so the count clause is exercised on its own.
            RequireOwner(
                Touching((At: 5, Count: 5)), 5, 0,
                "a rib of five nodes anchored at one end holds FOUR free notches against the arch's nine");

            // 3. COUNTS EQUAL AND CHORDS EQUAL, so the GEOMETRIC KEYS decide.
            //    A rib of ten nodes anchored at one end holds nine free
            //    notches, and its chord from (5, -5) to (5, 5) is ten, the
            //    arch's own. The endpoint pairs then separate them: the
            //    arch's begins at (0, 5) and the rib's at (5, -5), so the
            //    ARCH owns by the lower X of the first point.
            RequireOwner(
                Touching((At: 5, Count: 10)), 5, 0,
                "counts tie at nine and chords tie at ten, so the endpoint pairs decide and the arch's begins at (0, 5) against the rib's (5, -5)");

            // 4. TWO RIBS AT MIRRORED POSITIONS. Both shared nodes resolve to
            //    the SAME owner, because every key of the rule is a property
            //    of the SPAN and not of the node, and the arch's feet come
            //    back exactly mirrored. That is what keeps a regularly ribbed
            //    vault symmetric, and it is what a rule reading the more
            //    central notch could not promise.
            {
                var mirrored = Touching((At: 3, Count: 11), (At: 7, Count: 11));
                object placed = Run(mirrored, Array.Empty<int[]>(), 1, 2);
                var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
                int OwnerOfNode(int shared) => Get<int>(
                    trees.First(t =>
                        Get<int[]>(t, "Nodes").Contains(shared) &&
                        Get<bool[]>(t, "Owned")[Array.IndexOf(Get<int[]>(t, "Nodes"), shared)]),
                    "Bar");
                if (OwnerOfNode(3) == 0 || OwnerOfNode(7) == 0)
                    throw new InvalidOperationException("Each rib holds ten free notches against the arch's nine, so each rib owns its own head.");
                object built = Get<object>(placed, "Built");
                var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
                var archTrees = Enumerable.Range(0, trees.Length).Where(t => Get<int>(trees[t], "Bar") == 0).ToArray();
                int[] footNode = FootOfTree(built, trees.Length);
                double[] archFeet = archTrees.Select(t => X(levelNodes[footNode[t]])).OrderBy(v => v).ToArray();
                for (int i = 0; i < archFeet.Length / 2; i++)
                {
                    double sum = archFeet[i] + archFeet[archFeet.Length - 1 - i];
                    if (Math.Abs(sum - 10.0) > 1.0e-9)
                        throw new InvalidOperationException($"Two ribs touching at mirrored positions leave the arch's feet exactly mirrored; feet {i} and {archFeet.Length - 1 - i} sum to {sum:0.#########} rather than 10.");
                }
            }

            // 5. THE BORROWING TREE'S OWN ANSWER. On the first fixture the
            //    arch's tree holding node 5 borrows it. Where a borrowed
            //    notch is a tree's MAIN, its trunk runs to its HEAD MAIN and
            //    its fork lies on that segment; and a tree ALL of whose
            //    notches are borrowed builds nothing, carries no load, is
            //    unpaired, leaves its candidate partner unpaired, and is
            //    still counted in its span's layout so the palindrome stands.
            {
                var one = Touching((At: 5, Count: 11));
                object placed = Run(one, Array.Empty<int[]>(), 1, 0);
                var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
                object borrower = trees.First(t => Get<int>(t, "Bar") == 0 && Get<int[]>(t, "Nodes").Contains(5));
                int at = Array.IndexOf(Get<int[]>(borrower, "Nodes"), 5);
                bool[] owned = Get<bool[]>(borrower, "Owned");
                int headMain = Get<int>(borrower, "HeadMain");
                if (owned.All(o => !o))
                {
                    if (headMain != -1)
                        throw new InvalidOperationException("A tree with NO owned notch has no head main; HeadMain is -1.");
                    if (Get<double[]>(borrower, "Load").Any(l => Math.Abs(l) > 1.0e-12))
                        throw new InvalidOperationException("A tree with no owned notch carries no load.");
                }
                else
                {
                    if (headMain < 0 || !owned[headMain])
                        throw new InvalidOperationException($"The head main is the tree's innermost OWNED notch; HeadMain is {headMain} and Owned there is {(headMain >= 0 ? owned[headMain] : false)}.");
                    if (at == 0 && headMain == 0)
                        throw new InvalidOperationException("The borrowed notch IS this tree's main, so the head main must be a different, owned notch.");
                }
                // The span's palindrome stands whatever is borrowed, because
                // every notch enters the layout.
                int[] sizes = trees.Where(t => Get<int>(t, "Bar") == 0).Select(t => Get<int[]>(t, "Nodes").Length).ToArray();
                if (!sizes.Reverse().SequenceEqual(sizes))
                    throw new InvalidOperationException($"A borrowed notch stays in Tree.Nodes, so the span's tree sizes are still a PALINDROME; they read [{string.Join(",", sizes)}].");
            }
        }
```

- [ ] **Step 6: Add `Tree.Owned`, `Tree.HeadMain` and the owner rule**

Add to `Tree`:

```csharp
            /// <summary>
            /// Whether this tree builds a member to that notch, aligned with
            /// <see cref="Nodes"/>. Spec section 10's three lists are not the
            /// same list: ALL notches enter the layout, the pairing, the
            /// group construction and the candidate set; only OWNED notches
            /// enter Load and Resultant; only owned notches receive a member.
            /// A borrowed notch enters Load with a load of zero because its
            /// head is not this tree's to carry.
            /// </summary>
            public bool[] Owned = Array.Empty<bool>();
            /// <summary>
            /// The index into <see cref="Nodes"/> of the tree's innermost
            /// OWNED notch, ties to the lower bar position. 0 on every tree
            /// that owns its main, which is every tree on a net with no
            /// crossing, and -1 on a tree with no owned notch, which builds
            /// nothing at all.
            /// </summary>
            public int HeadMain;
```

and to `Placement`:

```csharp
            /// <summary>Notches held by two spans at once.</summary>
            public int SharedNotches;
```

In `Place`, replace the free-notch line so a notch shared with another bar is NO LONGER skipped:

```csharp
                // A notch shared with another bar is NOT taken away from
                // either span (spec section 10): both lines hold it, so
                // neither span acquires a hole and the bar order cannot
                // change any layout. The held set keeps its OTHER job
                // unchanged, which is the ring tree's: a rim notch held by
                // the ring tree still cuts the spans and is still no span's
                // free notch.
                int[] free = span.Free.Where(p => !ringHeld.Contains(bars[span.Bar][p])).ToArray();
```

`ringHeld` is the set the ring tree filled; the per-tree `held.Add(node)` calls that used to claim a notch for the first bar go entirely.

Then, after every span's frame and free list exist and before the trees are built, decide the owner of every shared notch:

```csharp
        /// <summary>
        /// Which span builds the member to a shared notch. THE OWNER IS
        /// DECIDED BY THE SPANS, NOT BY THE TRACE, and the rule must not end
        /// in bar order: a regularly ribbed vault, a cross vault and a dome
        /// of equal ribs and hoops all give two spans of equal notch count
        /// and equal chord, and ending on the bar index would make the answer
        /// depend on which curve Pattern traced first, which is the very
        /// finding this rule answers.
        ///
        /// A span's ENDPOINT PAIR is its two cut nodes' plan positions sorted
        /// lexicographically by X then Y, which is node-order invariant. The
        /// owner is the first of these that separates the spans, each
        /// compared within 1e-9 * min(L_A, L_B) except the last: the greater
        /// FREE NOTCH COUNT; then the longer CHORD LENGTH; then the lower X
        /// of the endpoint pair's first point, then its lower Y; then the
        /// same for the second point; then the lower mean Z of the span's
        /// free notches; then, and only then, the lower bar index and span
        /// index, which is reached only when the two spans are the same
        /// segment in space to within a billionth of their own length.
        ///
        /// Every key is a property of the SPAN and not of the node, so every
        /// notch shared between the same two spans resolves the same way,
        /// which is what keeps a symmetric pair of crossings symmetric. The
        /// more central notch was considered and rejected for exactly that
        /// reason: it reads the node, and it can hand two mirrored shared
        /// notches to different owners.
        /// </summary>
        private static int OwnerOf(Placement placement, Point3d[] nodes, int a, int b)
```

implemented as a comparison returning the winning span index, with `Frame` supplying `L`, `Nodes` and the endpoint pair built from `P0` and `P1` sorted by X then Y.

Build each tree's `Owned` from that map, set `Load` to zero on a borrowed notch, compute `Resultant` over owned notches only, and set `HeadMain` to the index into `Nodes` of the innermost owned notch.

Where a notch is held by ONE bar the head pull is that bar's own untransversed pull unchanged, so keep using `across[b][p]` there and every existing harness number is untouched. Where a notch is held by more than one, use `HeadPull` and take `Load` as the magnitude of the vertical component and `Resultant` as the vector sum over the tree's owned notches.

- [ ] **Step 7: Run the trunk, the fork and the peel to the head main**

In `BuildLevel`, replace every `trees[t].Nodes[0]` that means "the notch the trunk runs to" with `trees[t].Nodes[trees[t].HeadMain]`: the `own` array, the fork's segment and its lowering rule, the peel's lean measure, and the member build. Skip a tree whose `HeadMain` is -1 entirely: it builds no member and no foot at all, carries no load, has a zero resultant, and is still counted in its span's layout so that the palindrome stands. Build a member only where `Owned[k]` is true.

Where the tree owns its main, which is every tree on a net with no crossing, the head main IS the main and every number is unchanged.

- [ ] **Step 8: Re-pin the two remaining crossing fixtures**

`tests/native_smoke/Program.cs:6897-6960`, the plan-curved bar crossed. RE-PINNED per spec 17.1: the curved bar keeps its EIGHT free notches, the trees become nine, and the placement's layout and Types 1 to 4 feet equal the uncrossed control's. The `AsymmetricSpans 1` assertion becomes `AsymmetricSpans 0` here and is renamed to `UnpairedTrees 0` in Task 7.

`tests/native_smoke/Program.cs:7341-7386`, the crossing held once by the lower bar. REWRITTEN: the head count comes from the BUILT MEMBERS and the block's heads and not from `Tree.Nodes`, since both spans now list the shared node; the trees go from five to six; the owner is still bar 0, but now BY THE GEOMETRIC KEYS, the arch's endpoint pair beginning at (-4, 0) against the rib's (0, -4), and the check must say so rather than saying "the lower-indexed bar"; the Type 1 feet still weld to one node and `FeetMerged` is still 0.

- [ ] **Step 9: Run the gate green, then commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/ColumnPlacement.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(columns): both lines hold a shared notch, and its load is counted once and in full"
```

---

### Task 7: The common mode, the mirror, the pairing, the families and the residual

Spec section 9 entire, plus the four hostile fixtures whose assertions this task turns green. THE COMMON MODE GOES FIRST, BY SUBTRACTION, NOT BY PAIRING. There is no longer any state in which a span is placed unmirrored, so `AsymmetricSpans` is retired.

**Files:**
- Modify: `plugin/native_v02/Components/ColumnPlacement.cs` (`Symmetrise` at 272-632 entire; `Placement.AsymmetricSpans` at 177-184)
- Modify: `plugin/native_v02/Components/ColumnsComponent.cs:436-438` and `:624-635` (`AsymmetricSpans` becomes `UnpairedTrees`, enough to compile)
- Test: `tests/native_smoke/Program.cs`: every case naming `AsymmetricSpans`, which spec 17.1 lists at lines 6566, 6567, 6742, 6781, 6782, 6813, 6814, 6941, 6945, 6946 and 7146, plus four new fixtures

**Interfaces:**
- Consumes: Task 6's `Tree.Owned` and `Tree.HeadMain`; Task 3's `SpanFrame.Sigma`, `H`, `L` and `ChordZero`; Task 1's palindromic layout, which is what makes the pairing's same-notch-count condition free.
- Produces, and Tasks 9 and 10 depend on these exact names:
  - `Placement.UnpairedTrees` (public `int`, REPLACING `AsymmetricSpans`).
  - `Placement.ClosedSpans` (public `int`, the spans every tree of which is paired or self-paired).
  - `Placement.CommonModeResidual` (public `double`, the largest surviving along-chord common mode as a fraction of its own span's mean pull).
  - `Placement.Partner` keeps its name and its three values; `Placement.CentreTrees` keeps its name and now counts SELF-PAIRED trees.

- [ ] **Step 1: Write the residual fixture, red**

```csharp
        // ---- THE RESIDUAL ITSELF (spec sections 9.5 and 17). A span whose
        // pulls carry a genuine along-chord COMMON MODE and not merely a
        // mirrored bend, which the existing SkewArch fixture provides through
        // its skew parameter, driven on a span holding at least one unpaired
        // tree.
        //
        // AsymmetryRemoved is the trap this exists to answer: the
        // investigation measured it FALLING from 75.40 degrees to 1.81 the
        // moment the mirror rule stopped running, because an unmirrored
        // span's aim is never moved, so the number reads most reassuringly
        // exactly when the machinery has been bypassed. The RESIDUAL reads
        // ZERO when the rule worked and large exactly when it did not.
        {
            const double skew = 0.0174550649282176;   // tan(1 degree)
            var arch = SkewArch(11, 10.0, 2.5, bend: 0.25, skew: skew, flank: 1.1);
            object placed = Run(arch, Array.Empty<int[]>(), 1, 0);
            double residual = Get<double>(placed, "CommonModeResidual");
            if (Math.Abs(residual) > 1.0e-12)
                throw new InvalidOperationException($"AFTER PLACEMENT, EVERY SPAN'S MEAN ALONG-CHORD COMPONENT IS ZERO; CommonModeResidual reads {residual:0.############}.");
            object built = Get<object>(placed, "Built");
            var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            int[] footNode = FootOfTree(built, 9);
            for (int i = 0; i < 4; i++)
            {
                double sum = X(levelNodes[footNode[i]]) + X(levelNodes[footNode[8 - i]]);
                if (Math.Abs(sum - 10.0) > 1.0e-9)
                    throw new InvalidOperationException($"Every foot is mirrored to 1e-9; trees {i} and {8 - i} sum to {sum:0.#########} rather than 10.");
            }
            // The number is DEMONSTRATED to move rather than asserted to.
            // With the mean subtraction of 9.1 disabled in the check's own
            // copy of the arithmetic, the residual goes above 0.1 and the
            // feet are not mirrored, while AsymmetryRemoved FALLS.
            double DisabledResidual()
            {
                // Read the raw resultants, pair them exactly as 9.3 does but
                // WITHOUT the 9.1 subtraction, and report the surviving mean.
                var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
                double[] along = trees.Select(t => VX(Get<object>(t, "RawResultant"))).ToArray();
                double magnitude = trees.Select(t =>
                {
                    object r = Get<object>(t, "RawResultant");
                    return Math.Sqrt((VX(r) * VX(r)) + (VY(r) * VY(r)) + (VZ(r) * VZ(r)));
                }).Average();
                return Math.Abs(along.Average()) / magnitude;
            }
            double disabled = DisabledResidual();
            if (disabled <= 0.1)
                throw new InvalidOperationException($"This fixture only measures anything while the UNSUBTRACTED common mode is above 0.1 of the span's own mean pull; it is {disabled:0.####}. Raise the skew.");
            Console.WriteLine($"      CommonModeResidual {residual:0.############} placed against {disabled:0.####} with the 9.1 subtraction removed; AsymmetryRemoved {Get<double>(placed, "AsymmetryRemoved"):0.##} degrees.");
        }
```

- [ ] **Step 2: Write the off-centre crest fixture, red**

```csharp
        // ---- AN OFF-CENTRE CREST (spec section 17). A single arch of nine
        // notches placed at equal ARC LENGTH along an arch whose crest sits
        // at chord parameter 0.584 at rise over span 0.25, which is the
        // measured FIRST FAILING crest for that notch count and the geometry
        // a relaxed cable net actually gives. The present engine reports
        // AsymmetricSpans 1 on it, a notch defect of 0.0251 against a
        // tolerance of 0.025, and unmirrored feet at every Type. The
        // tolerance is 0.025 under the old formula and 0.025 under the new
        // one as well, because these notches span 0.1 to 0.9 whichever way it
        // is read; the check prints both.
        {
            var crest = CrestArch(11, 10.0, 2.5, crest: 0.584);
            const double oldTolerance = 0.25 / 10.0;
            const double newTolerance = 0.25 * (0.9 - 0.1) / 8.0;
            Console.WriteLine($"      off-centre crest tolerance: old 0.25 / (m + 1) = {oldTolerance:0.#####}, new 0.25 * (s_max - s_min) / (m - 1) = {newTolerance:0.#####}.");
            foreach (int type in new[] { 1, 2, 3, 4 })
            {
                object placed = Run(crest, Array.Empty<int[]>(), 1, type);
                if (Math.Abs(Get<double>(placed, "CommonModeResidual")) > 1.0e-12)
                    throw new InvalidOperationException($"Type {type}: CommonModeResidual is zero to 1e-12 on an off-centre crest; it reads {Get<double>(placed, "CommonModeResidual"):0.############}.");
                // The feet are at the parameters the GROUP CONSTRUCTION
                // predicts, computed here from the notch row and NOT copied
                // from the engine, and computed by the NEAREST-TO-CENTRE rule
                // of 8.1, which on this unevenly spaced row DIFFERS from the
                // middle notch by index and would go green under either if
                // the row were uniform.
                object built = Get<object>(placed, "Built");
                var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
                var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
                int[] footNode = FootOfTree(built, trees.Length);
                double[] sigma = Enumerable.Range(1, 9)
                    .Select(i => X(crest.Nodes.GetValue(i)!) / 10.0).ToArray();
                foreach (int[] group in ExpectedFootGroups(9, type))
                {
                    double lo = group.Min(j => sigma[j]);
                    double hi = group.Max(j => sigma[j]);
                    double centre = 0.5 * (lo + hi);
                    double nearest = group.Min(j => Math.Abs(sigma[j] - centre));
                    int[] candidates = group.Where(j => Math.Abs(sigma[j] - centre) <= nearest + 1.0e-12).ToArray();
                    double expected = candidates.Average(j => X(crest.Nodes.GetValue(j + 1)!));
                    foreach (int j in group)
                    {
                        double got = X(levelNodes[footNode[j]]);
                        double lean = MouldLean(levelNodes[footNode[j]], crest.Nodes.GetValue(j + 1)!);
                        if (lean > 60.0 + 1.0e-9)
                            continue;   // peeled: its foot is aim-derived
                        if (Math.Abs(got - expected) > 1.0e-9)
                        {
                            throw new InvalidOperationException(
                                $"Type {type}: the foot of the group holding notches [{string.Join(",", group)}] is the plan mean of its NEAREST-TO-CENTRE "
                                + $"candidates, x = {expected:0.#########}; tree {j} stands at {got:0.#########}. On this equal-arc row the nearest notch to "
                                + "the group centre is NOT the middle notch by index.");
                        }
                    }
                }
                // Every group and its mirror hold the same number of trees.
                int[][] groups = ExpectedFootGroups(9, type);
                for (int j = 0; j < groups.Length; j++)
                {
                    if (groups[j].Length != groups[groups.Length - 1 - j].Length)
                        throw new InvalidOperationException($"Type {type}: group {j} and its mirror hold the same number of trees.");
                }
            }
            // The tree at the CREST is the self-paired one and stands PLUMB
            // along the chord, and the tree at the chord MIDPOINT does not.
            // That is the direct test of section 9.2 and the exact inversion
            // of the 7.4 degree defect the design input measured: the input
            // recorded the crest being made to lean 7.4 degrees while the
            // chord midpoint was made plumb.
            {
                object atZero = Run(crest, Array.Empty<int[]>(), 1, 0);
                int[] partner = Get<int[]>(atZero, "Partner");
                var trees = ((IEnumerable)Get<object>(atZero, "Trees")).Cast<object>().ToArray();
                double[] sigma = Enumerable.Range(0, 9)
                    .Select(t => X(crest.Nodes.GetValue(Get<int[]>(trees[t], "Nodes")[0])!) / 10.0).ToArray();
                int crestTree = Enumerable.Range(0, 9).OrderBy(t => Math.Abs(sigma[t] - 0.584)).First();
                int midTree = Enumerable.Range(0, 9).OrderBy(t => Math.Abs(sigma[t] - 0.5)).First();
                if (crestTree == midTree)
                    throw new InvalidOperationException("This fixture only measures anything while the crest tree and the chord-midpoint tree are DIFFERENT trees.");
                if (partner[crestTree] != crestTree)
                    throw new InvalidOperationException($"The aim mirror is located where the along-chord pull changes SIGN, which on this arch is the CREST, so the crest tree is the self-paired one; Partner[{crestTree}] is {partner[crestTree]}.");
                if (partner[midTree] == midTree)
                    throw new InvalidOperationException($"The tree at the CHORD MIDPOINT is not the self-paired one: the span's first and last node are an artefact of where the anchor cluster stops, and the physical mirror is the crest.");
                object crestAim = Get<object>(trees[crestTree], "Resultant");
                if (Math.Abs(VX(crestAim)) > 1.0e-9)
                    throw new InvalidOperationException($"A self-paired tree has its along-chord part set to ZERO, so the crest tree stands plumb along the chord; its along part is {VX(crestAim):0.#########}.");
                object midAim = Get<object>(trees[midTree], "Resultant");
                if (Math.Abs(VX(midAim)) <= 1.0e-9)
                    throw new InvalidOperationException("The chord-midpoint tree is NOT zeroed: it is not the mirror plane, and a mirror taken from the cuts would have zeroed it instead of the crest.");
            }
        }
```

The last brace closes the block opened at the head of this fixture. An earlier draft closed only the inner one and the block would not have compiled.

Two further parts of the same fixture, each stated so that the restriction on it is deliberate rather than convenient:

- **THE FLANK SCALE.** Scale the pull vectors by 1.1 on ONE FLANK alone and assert that NO FOOT OF A TREE THAT DID NOT PEEL MOVES AT ALL. The restriction to unpeeled trees is on purpose: a peeled tree's foot IS aim-derived by section 11, so scaling a flank moves it, and the earlier draft's unrestricted form would have failed on its own control, where the Type 1 row has four peels in range. Then scale BOTH flanks together and assert the PEEL SET is unchanged, and that both members of every peeling pair peel, which is the property section 11 actually claims.
- **THE SWEEP.** Sweep the crest from 0.5 to 0.75 in steps of 0.0005, placing at each step, and assert that no foot of an UNPEELED tree jumps by more than one notch spacing between two consecutive steps, which is the continuity claim of section 7 and which band arithmetic fails by construction. The restriction is again deliberate: the sixty degree cap is a hard switch from the group foot to the Type 0 foot, four metres away on this arch, so a tree crossing the cap during the sweep jumps by far more than a spacing and always will. For the peel assert instead that the SET of peeled trees changes by at most one mirror PAIR between consecutive steps and that it is mirror-symmetric at every step.

`ExpectedFootGroups` and `MouldLean` are the two locals TASK 4 STEP 1 already declared beside `FootOfTree`, and they are written out there as code: the first reimplements spec section 7's counting independently of the engine, so no fixture is comparing the engine with itself, and Task 4 pins the two implementations against each other for every T and N so that a divergence is caught in one place; the second is `MouldGeometry.LeanFromVertical` invoked by reflection. Nothing is redeclared here.

- [ ] **Step 3: Write the unequal anchor cluster and the raised springing, red**

Both come from the design input's own measurements and were missing from the earlier draft entirely. Each is a net on which every PRESENT diagnostic reads clean.

- AN UNEQUAL ANCHOR CLUSTER. One bar of thirteen nodes with THREE anchors at one end and ONE at the other, so the span is cut at the innermost anchor and its chord no longer runs between the springings. The input records what happens today: the span still PASSES the symmetry test, its chord runs from the innermost anchor, the mirror plane sits off the crown, the pairing is off by one, and the column that should stand plumb stands half a notch from the crest. Assert: the span's `s_mirror` sits at the CREST, located from the sign change of the residual along-chord pull, and not at the chord midpoint; the self-paired tree is the crest tree; that tree's along-chord aim is zero and its Type 0 foot stands directly under its own notch along the chord; `CommonModeResidual` is zero; and the layout, the groups and the Types 1 to 4 feet are the ones the group construction predicts from the notch row. Then assert that MOVING one anchor, so the cluster becomes equal, moves no foot by more than the notch it moved.
- A RAISED SPRINGING. The same bar with one springing raised above the other, which the input records as doing the same thing as an off-centre crest. Assert the same list, and assert in particular that the plumb column stands at the CREST and NOT at the chord midpoint, which is the assertion that fails against a mirror taken from the cuts.

- [ ] **Step 4: Run the gate and read the failures**

Run the gate. Every new fixture fails on the missing `CommonModeResidual`, and the crest and anchor-cluster cases fail on a mirror taken from the cuts.

- [ ] **Step 5: Rewrite `Symmetrise`**

Replace the whole method. Its shape, in the order of spec section 9:

1. **9.1, the common mode goes first, by subtraction, not by pairing.** Read every non-ring tree's resultant in its own span's frame as (along, across, down). For each span let A be the MEAN of the along parts over the span's trees that carry a resultant at all, and subtract A from every one of them. Unconditionally: for a span of one tree, for a span with a free end, for a span whose every tree is unpaired, for a span with a crossing, for a closed span where it will make no difference, and for every other span. There is no test to fail and no state in which the step is skipped. Trees that carry NO resultant, which is a tree all of whose notches are borrowed, take no part in the mean and are not moved by it. The ring tree is not in this at all.
2. **9.2, the aim mirror from the structure.** Take the span's trees SORTED BY THEIR MAIN NOTCH'S CHORD PARAMETER, which is the one place in this engine that reads parameter order rather than bar order, ties to the lower bar position. Each tree carries its residual along part `a`; `A_mag` is the mean of `|resultant|` over those trees; a residual is DEEMED ZERO when `|a| <= 1e-9 * A_mag`, and where `A_mag` is itself zero every residual is deemed zero. A SIGN CHANGE stands between two consecutive trees whose residuals are deemed non-zero and have opposite signs, its parameter found by linear interpolation on the two residuals; a tree whose residual is deemed zero is itself a sign change at its own parameter, which is the exact limit of the interpolation so the plane moves continuously. One sign change gives `s_mirror`; several give the one nearest the ROW CENTRE BY PARAMETER, ties to the smaller; none gives the row centre by parameter itself, as does a span of fewer than two trees. `s_mirror` is NOT clamped to the chord.
3. **9.3, the pairing, per tree, by parameter.** The reflection of tree i is `r_i = 2 * s_mirror - s_i` with `s_i` its MAIN notch's chord parameter. Its candidate partner is the tree whose main notch parameter is nearest `r_i`, ties to `T - 1 - i` and then to the lower index in bar order. The pair is ACCEPTED when the mismatch `|s_i + s_j - 2 * s_mirror|` is at most `h / 4`, the pairing is MUTUAL, and the two trees hold the SAME NUMBER of notches. A tree is SELF-PAIRED when it is its own nearest, its self-mismatch `|2 * (s_i - s_mirror)|` being at most `h / 4`. Everything else is UNPAIRED and keeps what 9.1 left it. A tree with NO OWNED NOTCH takes no part: it is unpaired, its candidate partner is unpaired too and keeps its own across and down, and it joins no family.
4. **9.4, symmetrise and the invariant.** An accepted pair has its along parts made equal and opposite about their mean difference and its across and down replaced by the pair's means; a self-paired tree has its along set to zero; the family averaging runs; THE SPAN MEAN IS SUBTRACTED ONCE MORE, because the pair step can put a common mode back on a span holding unpaired trees; and only then does the dead band apply. The idempotence guard, keyed on the flag AND on the tree count, stays exactly as it is.
5. **9.5, the families.** Only a CLOSED span, one in which every tree is paired or self-paired, may join a family. The rest of the family rule is unchanged: alike in free notch count, in Branching, and in chord length within a tenth of the family LEAD's; ALONG and DOWN shared by tree index, every span keeping its OWN across; the guard that drops a family whose spans disagree on tree count stays.
6. **9.5, the residual.** For each span take the along parts of its non-ring trees AS PLACED, excluding trees the dead band moved and excluding trees with no owned notch; let their mean be `A_S` and the mean of their `|resultant|` be `A_mag`. The span's residual is `|A_S| / A_mag`, zero where the set is empty or `A_mag` is zero. `CommonModeResidual` is the LARGEST over the net.

Replace `Placement.AsymmetricSpans` with:

```csharp
            /// <summary>
            /// Trees that found no mirror partner. It REPLACES
            /// AsymmetricSpans, because no span is placed unmirrored any
            /// more: the common mode goes by subtraction before any pairing
            /// runs, and an unpaired tree now costs only the sharing of one
            /// partner's across and down.
            /// </summary>
            public int UnpairedTrees;
            /// <summary>Spans every tree of which is paired or self-paired.</summary>
            public int ClosedSpans;
            /// <summary>
            /// The largest along-chord common mode still standing after
            /// placement, as a fraction of its own span's mean pull. It reads
            /// ZERO when the rule ran and large exactly when it did not, which
            /// is why it and not AsymmetryRemoved is the number to look at:
            /// the investigation measured AsymmetryRemoved FALLING from 75.40
            /// degrees to 1.81 the moment the mirror rule stopped running.
            /// </summary>
            public double CommonModeResidual;
```

- [ ] **Step 6: Re-pin every case that names `AsymmetricSpans`**

Spec 17.1 lists them: lines 6566, 6567, 6742, 6781, 6782, 6813, 6814, 6941, 6945, 6946 and 7146. Line 6742's case was deleted in Task 6. The rest become `UnpairedTrees 0`, and line 6566's case, the three ribs of one family, gains `CommonModeResidual 0` beside it; its `Families 1` assertion, its crown-bar across assertion and its profile assertions stay green untouched.

Then extend that same three-arch fixture per spec section 17: three identical arches with a three degree solver residue on the middle one and one family. Assert `AsymmetryRemoved` is 3 both WITH and WITHOUT a rib crossing the middle arch, that `CommonModeResidual` is zero in both runs, and that the middle arch's layout, groups and Types 1 to 4 feet match its two neighbours'. The present engine drops `AsymmetryRemoved` to 0 and moves that arch's feet off its neighbours' when the crossing is added. `AsymmetryRemoved` is pinned here as a PRESERVATION and not as evidence that the rule ran.

Add the FAMILIES case of section 17: a family of closed spans shares along and down as before; a span holding ONE unpaired tree is its own family and does NOT take another's profile; and the crown rib lying in the structure's own mirror plane keeps its own across and its feet stand under its own notches across the chord, which is the existing fixture and must stay green.

Add NODE ORDER AND ROTATION INVARIANCE: four congruent ribs, one traced backwards, one turned through 180 degrees in plan with its pulls turned with it, and one translated. Assert identical feet in the world to 1e-9 at Types 0, 2 and 3, and identical member sets.

- [ ] **Step 7: A FREE BAR END**

```csharp
        // ---- A FREE BAR END (spec section 17). A bar anchored at ONE end
        // only, eleven nodes, so the span is of kind end to anchor, its first
        // notch sits at chord parameter 0 and it holds TEN free notches. The
        // present engine reports AsymmetricSpans 1, a defect of 0.1 against a
        // tolerance of 0.0227, and Families 0, so the span joins no family at
        // all. THE TOLERANCE MOVES HERE and the check prints both: the old
        // formula 0.25 / (m + 1) gives 0.0227 and the new measured one,
        // 0.25 * (0.9 - 0) / 9, gives 0.025.
        {
            const double oldBound = 0.25 / 11.0;
            const double newBound = 0.25 * (0.9 - 0.0) / 9.0;
            Console.WriteLine($"      free bar end tolerance: old {oldBound:0.#####}, new {newBound:0.#####}.");
            // Eleven nodes of the ordinary parabolic arch, anchored at the
            // LAST node only, so the span runs end to anchor and its first
            // notch sits at chord parameter 0. Ten free notches, positions 0
            // to 9.
            var freeEnd = Arch(11, 10.0, 2.5, 1.0);
            freeEnd = (freeEnd.Nodes, freeEnd.Bars, new[] { 10 }, freeEnd.Across, freeEnd.Edges);
            foreach (int type in new[] { 0, 1, 2, 3, 4 })
            {
                object placed = Run(freeEnd, Array.Empty<int[]>(), 1, type);
                if (Math.Abs(Get<double>(placed, "CommonModeResidual")) > 1.0e-12)
                    throw new InvalidOperationException($"Type {type}: CommonModeResidual is zero on a span with a free end; it reads {Get<double>(placed, "CommonModeResidual"):0.############}.");
                if (Get<int>(placed, "GroundPlaced") != Math.Max(type, 0))
                    throw new InvalidOperationException($"The span is placed at every Type without any fallback; Type {type} placed {Get<int>(placed, "GroundPlaced")}.");
                var trees = ((IEnumerable)Get<object>(placed, "Trees")).Cast<object>().ToArray();
                if (trees.Sum(t => Get<int[]>(t, "Nodes").Length) != 10)
                    throw new InvalidOperationException($"The span places its FULL layout, ten free notches; it holds {trees.Sum(t => Get<int[]>(t, "Nodes").Length)}.");
                int[][] groups = ExpectedFootGroups(trees.Length, Math.Max(type, 1));
                for (int j = 0; j < groups.Length; j++)
                {
                    if (groups[j].Length != groups[groups.Length - 1 - j].Length)
                        throw new InvalidOperationException($"Type {type}: the groups are PALINDROMIC; group {j} holds {groups[j].Length} against its mirror's {groups[groups.Length - 1 - j].Length}.");
                }
                // UnpairedTrees is the HAND-COMPUTED count and not every
                // tree. Today this span reports AsymmetricSpans 1 and
                // Families 0, so it joins no family at all and every one of
                // its trees keeps its raw aim, common mode included.
                int unpaired = Get<int>(placed, "UnpairedTrees");
                if (unpaired >= trees.Length)
                    throw new InvalidOperationException($"A free bar end no longer disables a span: UnpairedTrees is {unpaired} against {trees.Length} trees, which is every one of them.");
            }
        }
```

The hand-computed unpaired count is the trees whose reflection about the located `s_mirror` finds no mutual partner within `h / 4`, which the check computes from the notch parameters and the residual sign change rather than reading off the engine.

- [ ] **Step 8: Run the gate green, then commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/ColumnPlacement.cs" "plugin/native_v02/Components/ColumnsComponent.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(columns): the common mode goes by subtraction, and the residual is reported"
```

---

### Task 8: Welding, the central pair, cross-line merging, the convergence, and the second peel pass

Spec sections 8.2, 8.3 (the multi-span branch), 8.4, 8.5 (the merged-foot snap), 11 (the second pass) and 12 entire. FOUR distinct things happen to feet once they are placed and they are not the same thing.

**Files:**
- Modify: `plugin/native_v02/Components/ColumnPlacement.cs` (`MergeFeet` at 1384-1453 entire; `BuildLevel`'s call to it; `Level`)
- Test: `tests/native_smoke/Program.cs`: the central-pair fixtures at 6860-6895 and 7115-7153, the narrow bay at 7092-7113, plus four new blocks

**Interfaces:**
- Consumes: Task 3's `SpanFrame.G`, `SpanFrame.TauWeld` and the `edges` argument; Task 4's `FootGroups` group indices and `GroupFoot`; Task 6's `Tree.Owned`; Task 7's `Placement.Partner`.
- Produces, and Tasks 9 and 10 depend on these exact names:
  - `Level.MergeRefused` (public `int`), `Level.ConvergenceFallback` (public `int`).
  - `Level.FeetMerged` keeps its name and now counts accepted merge GROUPS OF BOTH KINDS, the same-span central pair and the cross-line component.
  - `private static Point3d Converge(Point3d[] nodes, IReadOnlyList<(SpanFrame Frame, int NotchIndex)> candidates, double guard, double ground, out bool fellBack)`

- [ ] **Step 1: Write the convergence check, red**

```csharp
        // ---- THE CONVERGENCE ITSELF (spec sections 8.2 to 8.4 and 17).
        // Param's rule, quoted: "best is to take the closest points to center
        // from the principle lines and then get them to all point inwards
        // where they touch, maybe this will give the exact placement for that
        // all branching from center point."
        //
        // POINTING INWARD IS THE GUARD, AND NOTHING ELSE. A line has no
        // direction and the least-squares form is built from the projector
        // (I - d d^T), which is identical for d and for -d, so orienting each
        // tangent toward the company would be a step no later step reads.
        // Inwardness is expressed once, as a stated proximity rule: the
        // converged point must lie within the CONVERGENCE GUARD of the CONVEX
        // HULL of the candidate points, and otherwise the plan mean is used.
        {
            // Three ribs of a dome, joined by net edges, whose central
            // notches are distinct points and whose plan tangents genuinely
            // meet. The merged foot must be the LEAST-SQUARES point, which
            // the check solves independently: A is the sum of (I - d d^T) and
            // b the sum of (I - d d^T) p, accepted when
            // |det A| > 1e-9 * max(trace(A)^2, 1e-12), which is the ring
            // tree's own scale-free conditioning test reused verbatim.
            (double X, double Y) LeastSquares((double PX, double PY, double DX, double DY)[] lines)
            {
                double a11 = 0.0, a12 = 0.0, a22 = 0.0, b1 = 0.0, b2 = 0.0;
                foreach ((double px, double py, double dx, double dy) in lines)
                {
                    double length = Math.Sqrt((dx * dx) + (dy * dy));
                    double ux = dx / length;
                    double uy = dy / length;
                    double m11 = 1.0 - (ux * ux);
                    double m12 = -ux * uy;
                    double m22 = 1.0 - (uy * uy);
                    a11 += m11;
                    a12 += m12;
                    a22 += m22;
                    b1 += (m11 * px) + (m12 * py);
                    b2 += (m12 * px) + (m22 * py);
                }
                double det = (a11 * a22) - (a12 * a12);
                double trace = a11 + a22;
                if (Math.Abs(det) <= 1.0e-9 * Math.Max(trace * trace, 1.0e-12))
                    throw new InvalidOperationException("This fixture wants a system the determinant test ACCEPTS; its tangents are parallel.");
                return (((a22 * b1) - (a12 * b2)) / det, ((a11 * b2) - (a12 * b1)) / det);
            }

            // The three ribs, their central notches within a quarter of the
            // tighter spacing of one another, their plan tangents fanning
            // inward at 30 degrees to each other.
            var dome = DomeRibs(spread: 0.1, fan: 30.0);
            object placed = Run(dome, Array.Empty<int[]>(), 1, 1);
            object built = Get<object>(placed, "Built");
            var levelNodes = ((IEnumerable)Get<object>(built, "Nodes")).Cast<object>().ToArray();
            var feet = ((IEnumerable)Get<object>(built, "Feet")).Cast<int>().ToArray();
            if (feet.Length != 1)
                throw new InvalidOperationException($"Three adjacent ribs whose feet fall inside a quarter of the tighter spacing become ONE column at the convergence of all three, taken once as a CONNECTED COMPONENT and not pairwise; {feet.Length} feet built.");
            if (Get<int>(built, "FeetMerged") != 1)
                throw new InvalidOperationException($"One accepted merge GROUP, not three pairwise merges; FeetMerged is {Get<int>(built, "FeetMerged")}.");
            (double X, double Y) expected = LeastSquares(DomeCandidateLines(dome));
            if (Math.Abs(X(levelNodes[feet[0]]) - expected.X) > 1.0e-9 ||
                Math.Abs(Y(levelNodes[feet[0]]) - expected.Y) > 1.0e-9)
            {
                throw new InvalidOperationException(
                    $"The merged foot is the least-squares point of the candidates' own plan tangent lines, ({expected.X:0.#########}, {expected.Y:0.#########}); "
                    + $"it stands at ({X(levelNodes[feet[0]]):0.#########}, {Y(levelNodes[feet[0]]):0.#########}).");
            }
            if (Get<int>(built, "ConvergenceFallback") != 0)
                throw new InvalidOperationException("This convergence lies within the guard of the hull and is ACCEPTED, not fallen back.");

            // Flatten the ribs until the tangents are parallel to 1e-7. The
            // foot falls back to the plan MEAN and ConvergenceFallback counts
            // it, rather than flying off to the far intersection: a small
            // change of tangent moves that intersection a long way, and
            // taking it would be following noise a hundred metres out.
            var flat = DomeRibs(spread: 0.1, fan: 1.0e-7);
            object placedFlat = Run(flat, Array.Empty<int[]>(), 1, 1);
            object builtFlat = Get<object>(placedFlat, "Built");
            var flatNodes = ((IEnumerable)Get<object>(builtFlat, "Nodes")).Cast<object>().ToArray();
            var flatFeet = ((IEnumerable)Get<object>(builtFlat, "Feet")).Cast<int>().ToArray();
            if (Get<int>(builtFlat, "ConvergenceFallback") < 1)
                throw new InvalidOperationException("Near-parallel tangents fall back to the plan MEAN, counted in ConvergenceFallback; none was counted.");
            (double X, double Y) mean = DomeCandidateMean(flat);
            if (Math.Abs(X(flatNodes[flatFeet[0]]) - mean.X) > 1.0e-9 || Math.Abs(Y(flatNodes[flatFeet[0]]) - mean.Y) > 1.0e-9)
                throw new InvalidOperationException($"The fallback is the plan MEAN of the candidate points, ({mean.X:0.#########}, {mean.Y:0.#########}); it stands at ({X(flatNodes[flatFeet[0]]):0.#########}, {Y(flatNodes[flatFeet[0]]):0.#########}). The mean commutes with any reflection, which the centre of an axis-aligned bounding box does not.");

            // Two ribs crossing at a shared node: the merged foot snaps to
            // that node EXACTLY. Standing the column on the shared node is
            // both tidier and what the author drew.
            var sharing = DomeRibsSharingANode();
            object placedShared = Run(sharing, Array.Empty<int[]>(), 1, 1);
            object builtShared = Get<object>(placedShared, "Built");
            var sharedNodes = ((IEnumerable)Get<object>(builtShared, "Nodes")).Cast<object>().ToArray();
            var sharedFeet = ((IEnumerable)Get<object>(builtShared, "Feet")).Cast<int>().ToArray();
            object crossingNode = sharing.Nodes.GetValue(SharedNodeId)!;
            if (Math.Abs(X(sharedNodes[sharedFeet[0]]) - X(crossingNode)) > 1.0e-12 ||
                Math.Abs(Y(sharedNodes[sharedFeet[0]]) - Y(crossingNode)) > 1.0e-12)
            {
                throw new InvalidOperationException($"Where the merging spans share a net node and the convergence lands within the merge clearance of it, the merged foot snaps to that node exactly.");
            }
        }
```

`DomeRibs`, `DomeCandidateLines`, `DomeCandidateMean`, `DomeRibsSharingANode` and `SharedNodeId` are local fixture builders declared beside `PlanCurved`, and they are written out here rather than described, because every number the block above asserts is a number this geometry decides:

```csharp
        // Three straight ribs in plan, five nodes each, anchored at both
        // ends, so each holds THREE free notches and at Branching 1 three
        // trees. At Type 1 the one group of three has an ODD count, so its
        // single nearest-to-centre candidate is its middle notch and the
        // rib's step 8 foot IS that notch. The three middle notches stand
        // `spread` apart in plan and the three plan tangents are fanned by
        // `fan` degrees, which is what makes the convergence a real
        // intersection at 30 degrees and a singular system at 1e-7.
        //
        // The ribs are joined by NET EDGES between their middle notches, and
        // by nothing else, so the spans are adjacent under section 12's rule
        // and the adjacency is exact rather than a distance.
        //
        // The chord of each rib is 4, so its four notch gaps are 1 apart in
        // chord parameter terms: h is (3/4 - 1/4) / 2 and g is h * 4 = 1.
        // The merge clearance is therefore 0.25 and a spread of 0.1 is
        // comfortably inside it, while the FEET-CLOSE clearance is the same
        // number, so the moved-apart case of Step 2 needs a spread above 0.25.
        (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) DomeRibs(
            double spread, double fan)
        {
            const int perRib = 5;
            Array nodes = Array.CreateInstance(point3d, 3 * perRib);
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 3);
            var bars = new int[3][];
            var anchors = new List<int>();
            var edges = new List<(int, int)>();
            for (int r = 0; r < 3; r++)
            {
                double turn = (r - 1) * fan * Math.PI / 180.0;
                double ux = Math.Sin(turn);
                double uy = Math.Cos(turn);
                double cx = (r - 1) * spread;
                Array ribAcross = Array.CreateInstance(vector3d, perRib);
                var bar = new int[perRib];
                for (int i = 0; i < perRib; i++)
                {
                    double along = i - 2.0;                    // -2 .. 2
                    double s = (i / (double)(perRib - 1));
                    int id = (r * perRib) + i;
                    nodes.SetValue(
                        P(cx + (ux * along), uy * along, 2.5 * 4.0 * s * (1.0 - s)), id);
                    ribAcross.SetValue(V(0.0, 0.0, -1.0), i);
                    bar[i] = id;
                    if (i > 0)
                        edges.Add((id - 1, id));
                }
                anchors.Add(bar[0]);
                anchors.Add(bar[perRib - 1]);
                bars[r] = bar;
                across.SetValue(ribAcross, r);
            }
            // Adjacency, and only adjacency: middle notch to middle notch.
            edges.Add(((0 * perRib) + 2, (1 * perRib) + 2));
            edges.Add(((1 * perRib) + 2, (2 * perRib) + 2));
            return (nodes, bars, anchors.ToArray(), across, edges.ToArray());
        }

        // Each rib's own candidate point and its plan tangent, read straight
        // off the fixture. The tangent is the rule's own: the unit plan
        // vector from the bar position BEFORE the notch to the one AFTER it.
        (double PX, double PY, double DX, double DY)[] DomeCandidateLines(
            (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) net)
        {
            var lines = new List<(double, double, double, double)>();
            foreach (int[] bar in net.Bars)
            {
                object at = net.Nodes.GetValue(bar[2])!;
                object before = net.Nodes.GetValue(bar[1])!;
                object after = net.Nodes.GetValue(bar[3])!;
                lines.Add((X(at), Y(at), X(after) - X(before), Y(after) - Y(before)));
            }
            return lines.ToArray();
        }

        (double X, double Y) DomeCandidateMean(
            (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) net) =>
            (net.Bars.Average(bar => X(net.Nodes.GetValue(bar[2])!)),
             net.Bars.Average(bar => Y(net.Nodes.GetValue(bar[2])!)));

        // Two ribs of SEVEN nodes that genuinely SHARE a net node. Both are
        // straight in plan and both pass through one point S, fanned by two
        // degrees either side of +y, and S is bar position 1 of each, so S is
        // a free notch of BOTH spans and neither an anchor nor a rim notch.
        //
        // Each rib holds five free notches, positions 1 to 5, so at Type 1
        // its one group of five is odd and its foot is its own position 3
        // notch, two spacings up the rib from S. The two feet are therefore
        // 4a sin(2 degrees), about 0.14 of a spacing, apart: inside the merge
        // clearance of 0.25 g and well outside the weld tolerance of 1e-9 L,
        // so this fixture exercises the MERGE and not the weld. And because
        // both ribs are straight lines through S, the two candidates' plan
        // tangent lines meet AT S exactly, so the convergence lands on the
        // shared node and the snap of section 12 is what is being measured.
        const int SharedNodeId = 1;
        (Array Nodes, int[][] Bars, int[] Anchors, Array Across, (int, int)[] Edges) DomeRibsSharingANode()
        {
            const int perRib = 7;
            const double a = 1.0;
            Array nodes = Array.CreateInstance(point3d, (2 * perRib) - 1);
            Array across = Array.CreateInstance(vector3d.MakeArrayType(), 2);
            var bars = new int[2][];
            var anchors = new List<int>();
            var edges = new List<(int, int)>();
            int next = 2;
            for (int r = 0; r < 2; r++)
            {
                double turn = (r == 0 ? -2.0 : 2.0) * Math.PI / 180.0;
                double ux = Math.Sin(turn);
                double uy = Math.Cos(turn);
                Array ribAcross = Array.CreateInstance(vector3d, perRib);
                var bar = new int[perRib];
                for (int i = 0; i < perRib; i++)
                {
                    double along = a * (i - 1.0);      // S sits at i = 1
                    double s = i / (double)(perRib - 1);
                    ribAcross.SetValue(V(0.0, 0.0, -1.0), i);
                    if (i == 1)
                    {
                        bar[i] = SharedNodeId;
                        if (r == 0)
                            nodes.SetValue(P(0.0, 0.0, 2.5 * 4.0 * s * (1.0 - s)), SharedNodeId);
                        continue;
                    }
                    int id = i == 0 ? (r == 0 ? 0 : next++) : next++;
                    nodes.SetValue(P(ux * along, uy * along, 2.5 * 4.0 * s * (1.0 - s)), id);
                    bar[i] = id;
                }
                for (int i = 1; i < perRib; i++)
                    edges.Add((bar[i - 1], bar[i]));
                anchors.Add(bar[0]);
                anchors.Add(bar[perRib - 1]);
                bars[r] = bar;
                across.SetValue(ribAcross, r);
            }
            return (nodes, bars, anchors.ToArray(), across, edges.ToArray());
        }
```

The shared-node case asserts its own premises before it asserts anything about the engine, so an implementer who moves the geometry sees a plain message rather than a silent pass:

```csharp
            (double PX, double PY, double DX, double DY)[] sharedLines = DomeCandidateLines(sharing);
            (double X, double Y) sharedMeet = LeastSquares(sharedLines);
            object sharedNode = sharing.Nodes.GetValue(SharedNodeId)!;
            if (Math.Abs(sharedMeet.X - X(sharedNode)) > 1.0e-9 || Math.Abs(sharedMeet.Y - Y(sharedNode)) > 1.0e-9)
                throw new InvalidOperationException("This fixture only measures the SNAP while the two candidates' tangent lines meet at the shared node itself; move the ribs back onto it.");
```

`DomeCandidateLines` for the shared-node fixture reads bar position 3 rather than 2, since those ribs hold seven nodes; write it to take the candidate position as an argument rather than hard-coding 2, and pass 2 for `DomeRibs` and 3 for `DomeRibsSharingANode`.

- [ ] **Step 2: Write the cross-line sharing checks, red**

Spec section 17's CROSS-LINE SHARING item, built as one block of six cases so that each rule of section 12 is caught by a fixture rather than by a reading. Every case below is a call on the `DomeRibs` builder Step 1 writes out, with one thing changed: case 1 is `DomeRibs(spread: 0.1, fan: 30.0)`; case 2 is `DomeRibs(spread: 0.4, fan: 30.0)`, whose spread is outside the 0.25 clearance; case 3 is the same net with the two joining edges DELETED from its edge list, which is the only thing that decides adjacency; cases 4, 5 and 6 each move one rib's own notches, and case 7 offers the same net's candidate pairs in three orders. Nothing here needs a new builder.

1. Three parallel ribs joined by net edges, the outer two moved so their feet fall inside a quarter of the tighter spacing of the middle rib's: ONE column at the convergence of all three, taken once as a CONNECTED COMPONENT and not pairwise, and `FeetMerged` 1.
2. The same three moved apart: three columns, and `FeetClose` counting the near pairs.
3. Two ribs with NO net edge between them whose feet coincide within the clearance: they must NOT merge. Adjacency is by net EDGE, which is exact, invariant under a rotation of the model and under any remesh that does not change the topology, and needs no distance scale of its own.
4. A MIRROR-REFUSED case: two adjacent ribs converging at one end so that one mirrored merge is inside the clearance and its mirror is not. Nothing merges and `MergeRefused` counts it, with THE MIRROR TAKEN BY GROUP INDEX and the check computing the mirror candidate itself: the mirror of the candidate joining group j of span A to group j' of span B is the candidate joining group `N_A - 1 - j` of A to group `N_B - 1 - j'` of B.
5. A MIXED case where one foot is central on its span and the other is not, which is what a rib meeting an arch at the crown gives: the mirror of the candidate is the candidate joining the same central foot to the flank group's mirror, and the ordinary rule decides.
6. A LEAN-REFUSED case where the converged foot would put one participating trunk past sixty degrees: the merge is refused and counted, because a merge that hands a tree a foot it cannot reach has bought tidiness with a peel and the peel would then undo the merge.
7. An ORDER case: the same net with the candidate pairs offered in three different orders, asserting the merged set is IDENTICAL, which is what reading the step 8 feet rather than already-merged ones buys.

- [ ] **Step 3: Rewrite `MergeFeet`**

Four rules, in this order, each with its own clearance in the span's own terms:

- **WELDING.** Two feet whose plan distance is at most `TAU_weld`, and whose heights agree to the same bound, are ONE node. Positional identity and not a decision: two groups of one span that converged to the same notch, two spans whose feet landed on a shared crossing notch, the ring tree's foot coinciding with a span foot. NOT counted as a merge, and it moves nothing. `TAU_weld` is `1e-9 * L` for two feet of one span, `1e-9 * min(L_A, L_B)` for feet of two spans, `1e-9 * min(L_S, R)` where the ring tree's fixed foot is one of the two, and `1e-9 * R` for the impossible two-ring case. Since every foot stands at the ground level, the height clause is trivial between two span feet and is live only where the ring tree's fixed foot is one of the two.
- **THE CENTRAL PAIR OF AN EVEN TREE ROW.** Where a span's tree count is EVEN there is no centre tree, so its two innermost trees are a mirror pair straddling the middle of the row with nothing between them. When their two feet lie within `0.25 * g` of that span they stand on ONE foot at the MEAN of the two. Not the span's chord midpoint: a pair's two feet differ only in their along-chord part, so the clearance says nothing about how far OFF the chord they sit, and on a bar that curves in plan merging onto the chord midpoint moved the pair sideways by the plan sagitta, out from under its own bar. No OTHER pair of one span merges, and an ODD row merges nothing, which is what keeps a centre column and its two leaning neighbours three columns rather than one; welding those was what turned leaning neighbours into accidental V's and X's on the review arch.
- **CROSS-LINE MERGING.** Two spans are ADJACENT when a free notch of one is joined by a net EDGE to a free notch of the other, or when they share a notch. Two feet of adjacent spans A and B are a MERGE CANDIDATE when their plan distance is at most `0.25 * min(g_A, g_B)`. A candidate is ACCEPTED only if its MIRROR BY GROUP INDEX is also a candidate, or where BOTH its feet are the central foot of their own span, and REFUSED where either span has no group at the mirrored index. The mirror test READS THE FEET AS STEP 8 PLACED THEM, never a foot another merge in the same pass has already moved. A candidate is also REFUSED where the foot it would converge to puts any participating trunk past `MaxLeanDegrees`. Accepted candidates are resolved as CONNECTED COMPONENTS and not pairwise in sequence. The merged foot is the CONVERGENCE over all the candidate points of all the merging groups with their own tangents, its guard at `0.25 * min(g)` over the spans taking part, and the plan mean as its fallback; where the merging spans share a net node and the convergence lands within the merge clearance of it, the merged foot SNAPS to that node. The ring tree's foot never merges.
- **STANDING CLOSE BUT APART.** Any two built feet within the FEET-CLOSE CLEARANCE that did not merge, whether because their spans are not adjacent, or because the mirror refused it, or because they are two feet of one span that are not its central pair, are counted in `Level.FeetClose`. That clearance is `0.25 * min(g_A, g_B)` between spans and `0.25 * g` within one span.

The tangent at a candidate notch is the unit plan vector from the bar position BEFORE it to the bar position AFTER it, normalised; at a bar end the single one-sided segment is used. Where the plan separation of the two points it is taken between is at most `1e-9 * L`, or `1e-9 * D` where L is zero, the span's chord direction `c` is used instead. A bound rather than an exact-coincidence test, because exact coincidence never occurs in a solved net, so a test for it would never fire and would leave a near-zero vector to be normalised, which is the failure the clause exists to prevent.

Written out, because four rules described in prose are four rules an implementer guesses at. `TangentAt` first:

```csharp
        /// <summary>
        /// The plan tangent at one of a span's free notches: the unit plan
        /// vector from the bar position BEFORE it to the one AFTER it, or the
        /// single one-sided segment at a bar end, falling back to the span's
        /// own chord direction where the two points it is taken between are
        /// within 1e-9 of its own scale.
        /// </summary>
        private static Vector3d TangentAt(
            Point3d[] nodes, int[][] bars, Span span, SpanFrame frame, int notchIndex)
        {
            int[] bar = bars[span.Bar];
            int position = frame.Positions[notchIndex];
            int before = bar[Math.Max(position - 1, 0)];
            int after = bar[Math.Min(position + 1, bar.Length - 1)];
            double dx = nodes[after].X - nodes[before].X;
            double dy = nodes[after].Y - nodes[before].Y;
            double length = Math.Sqrt((dx * dx) + (dy * dy));
            double scale = frame.ChordZero ? frame.D : frame.L;
            if (length <= 1.0e-9 * Math.Max(scale, 1.0e-12))
                return frame.C;
            return new Vector3d(dx / length, dy / length, 0.0);
        }
```

and `Converge` itself:

```csharp
        /// <summary>
        /// The plan point nearest every candidate's own plan tangent line at
        /// once: the same least-squares intersection the ring tree already
        /// uses for the bars' end tangents.
        ///
        ///     minimise, over x in plan, the sum over candidates of
        ///     |(I - d d^T) (x - p)|^2
        ///
        /// The sign of d is immaterial, since it enters only through the
        /// projector. SINGULAR, which is what parallel tangents give on a
        /// planar arch or two parallel ribs, falls back to the plan MEAN;
        /// OUT OF REACH, where the solution lies further than the guard from
        /// the convex hull of the candidate points, falls back to the plan
        /// mean and is counted in ConvergenceFallback; ACCEPTED takes the
        /// point. The mean is the fallback everywhere because the mean
        /// commutes with any reflection, whatever the chords' directions,
        /// which the centre of an axis-aligned bounding box does not.
        ///
        /// The conditioning test is the ring tree's own, verbatim and
        /// scale-free: |det A| > 1e-9 * max(trace(A)^2, 1e-12).
        /// </summary>
        private static Point3d Converge(
            Point3d[] nodes,
            IReadOnlyList<(Point3d Point, Vector3d Tangent)> candidates,
            double guard,
            double ground,
            out bool fellBack)
        {
            fellBack = false;
            double meanX = candidates.Average(c => c.Point.X);
            double meanY = candidates.Average(c => c.Point.Y);
            var mean = new Point3d(meanX, meanY, ground);
            if (candidates.Count == 0)
                return mean;

            double a11 = 0.0, a12 = 0.0, a22 = 0.0, b1 = 0.0, b2 = 0.0;
            foreach ((Point3d point, Vector3d tangent) in candidates)
            {
                double length = Math.Sqrt((tangent.X * tangent.X) + (tangent.Y * tangent.Y));
                if (length <= 1.0e-12)
                    continue;
                double ux = tangent.X / length;
                double uy = tangent.Y / length;
                double m11 = 1.0 - (ux * ux);
                double m12 = -ux * uy;
                double m22 = 1.0 - (uy * uy);
                a11 += m11;
                a12 += m12;
                a22 += m22;
                b1 += (m11 * point.X) + (m12 * point.Y);
                b2 += (m12 * point.X) + (m22 * point.Y);
            }
            double det = (a11 * a22) - (a12 * a12);
            double trace = a11 + a22;
            if (Math.Abs(det) <= 1.0e-9 * Math.Max(trace * trace, 1.0e-12))
            {
                // SINGULAR. Parallel tangents on a planar arch or two
                // parallel ribs. Not counted as a fallback of the guard's
                // kind, because nothing was out of reach; there was simply no
                // intersection to take.
                return mean;
            }
            double x = ((a22 * b1) - (a12 * b2)) / det;
            double y = ((a11 * b2) - (a12 * b1)) / det;

            // OUT OF REACH. The distance from the solution to the CONVEX HULL
            // of the candidate points, which for the two-point case is the
            // segment and for one point is that point. Computed as the
            // largest distance to any candidate less the hull's own diameter
            // is not good enough on three collinear ribs, so the hull is taken
            // properly: the point-to-hull distance is zero inside and the
            // nearest point-to-segment distance over the hull's edges outside.
            double reach = PlanDistanceToHull(candidates.Select(c => c.Point).ToArray(), x, y);
            if (reach > guard)
            {
                fellBack = true;
                return mean;
            }
            return new Point3d(x, y, ground);
        }
```

`PlanDistanceToHull` is an ordinary convex-hull-in-plan helper beside it: build the hull of the candidate points by monotone chain, return 0 where the point lies inside or on it, and otherwise the smallest point-to-segment distance over the hull's edges. With one candidate it is the plan distance to that point and with two it is the distance to their segment, which are the two cases every fixture in this task actually reaches.

And `MergeFeet`, the four rules in the order stated above:

```csharp
        private static int[] MergeFeet(
            Placement placement,
            Point3d[] nodes,
            int[][] bars,
            (int, int)[] edges,
            Point3d[] foot,
            double[] spacing,
            List<Point3d> levelNodes,
            List<double> footSpacing,
            out int merged,
            out int refused,
            out int fallbacks,
            out int close)
        {
            merged = 0;
            refused = 0;
            fallbacks = 0;
            close = 0;
            int treeCount = placement.Trees.Count;
            var node = new int[treeCount];
            for (int t = 0; t < treeCount; t++)
                node[t] = -1;

            // The feet AS STEP 8 PLACED THEM, kept apart from the working
            // copy, because every mirror test below reads the placed feet and
            // never a foot another merge in this same pass has moved.
            var placed = (Point3d[])foot.Clone();

            // ---- RULE 1, WELDING. Positional identity, not a decision, and
            // not counted as a merge. Two feet within TAU_weld in plan and in
            // height are ONE node.
            double WeldTolerance(int a, int b)
            {
                double ta = ToleranceOf(placement, a);
                double tb = ToleranceOf(placement, b);
                return Math.Min(ta, tb);
            }

            // ---- RULE 2, THE CENTRAL PAIR OF AN EVEN TREE ROW. Only a span
            // whose TREE COUNT is even has a central pair, and only that pair
            // merges within one span. An ODD row merges nothing, which is what
            // keeps a centre column and its two leaning neighbours three
            // columns rather than one.
            var group = new int[treeCount];
            for (int t = 0; t < treeCount; t++)
                group[t] = t;
            int Find(int t) => group[t] == t ? t : group[t] = Find(group[t]);
            void Union(int a, int b)
            {
                int ra = Find(a);
                int rb = Find(b);
                if (ra != rb)
                    group[Math.Max(ra, rb)] = Math.Min(ra, rb);
            }
            var spanTrees = new List<int>[placement.Spans.Count];
            for (int s = 0; s < spanTrees.Length; s++)
                spanTrees[s] = new List<int>();
            for (int t = 0; t < treeCount; t++)
            {
                if (!placement.Trees[t].Ring && placement.Trees[t].Span >= 0)
                    spanTrees[placement.Trees[t].Span].Add(t);
            }
            for (int s = 0; s < spanTrees.Count(); s++)
            {
                List<int> row = spanTrees[s];
                if (row.Count == 0 || (row.Count % 2) != 0)
                    continue;
                int left = row[(row.Count / 2) - 1];
                int right = row[row.Count / 2];
                double gap = Math.Sqrt(MouldGeometry.PlanDistanceSquared(placed[left], placed[right]));
                if (gap > 0.25 * Math.Min(spacing[left], spacing[right]))
                    continue;
                var mean = new Point3d(
                    0.5 * (placed[left].X + placed[right].X),
                    0.5 * (placed[left].Y + placed[right].Y),
                    placed[left].Z);
                foot[left] = mean;
                foot[right] = mean;
                Union(left, right);
                merged++;
            }

            // ---- RULE 3, CROSS-LINE MERGING. Adjacency is by net EDGE or by
            // a shared notch, both exact and both invariant under a rotation
            // of the model. Candidates are collected against the PLACED feet,
            // the mirror test is taken BY GROUP INDEX, and the accepted ones
            // are resolved as CONNECTED COMPONENTS rather than pairwise in
            // sequence, so the answer does not depend on the order the pairs
            // were offered in.
            bool[,] adjacent = SpansAdjacent(placement, bars, edges);
            var candidates = new List<(int A, int B)>();
            for (int a = 0; a < treeCount; a++)
            {
                for (int b = a + 1; b < treeCount; b++)
                {
                    if (placement.Trees[a].Ring || placement.Trees[b].Ring)
                        continue;                                  // the ring tree never merges
                    int sa = placement.Trees[a].Span;
                    int sb = placement.Trees[b].Span;
                    if (sa < 0 || sb < 0 || sa == sb || !adjacent[sa, sb])
                        continue;
                    double gap = Math.Sqrt(MouldGeometry.PlanDistanceSquared(placed[a], placed[b]));
                    if (gap > 0.25 * Math.Min(spacing[a], spacing[b]))
                        continue;
                    candidates.Add((a, b));
                }
            }
            var accepted = new List<(int A, int B)>();
            foreach ((int a, int b) in candidates)
            {
                if (!MirrorAccepts(placement, placed, spacing, adjacent, a, b))
                {
                    refused++;
                    continue;
                }
                accepted.Add((a, b));
            }
            foreach ((int a, int b) in accepted)
                Union(a, b);

            // The converged foot per component, over ALL the candidate
            // notches of ALL the merging groups, with their own tangents.
            foreach (IGrouping<int, int> component in Enumerable.Range(0, treeCount)
                .Where(t => !placement.Trees[t].Ring)
                .GroupBy(Find))
            {
                int[] members = component.ToArray();
                if (members.Length < 2)
                    continue;
                var points = new List<(Point3d Point, Vector3d Tangent)>();
                double guard = double.MaxValue;
                foreach (int t in members)
                {
                    int s = placement.Trees[t].Span;
                    if (s < 0)
                        continue;
                    SpanFrame frame = placement.Frames[s];
                    guard = Math.Min(guard, 0.25 * spacing[t]);
                    foreach (int index in CandidateNotchesOf(placement, t))
                        points.Add((PlanOf(nodes, frame, index), TangentAt(nodes, bars, placement.Spans[s], frame, index)));
                }
                if (points.Count == 0)
                    continue;
                Point3d where = Converge(nodes, points, guard, foot[members[0]].Z, out bool fellBack);
                if (fellBack)
                    fallbacks++;
                // THE SNAP. Where the merging spans share a net node and the
                // convergence lands within the merge clearance of it, the
                // merged foot snaps to that node exactly: standing the column
                // on the shared node is both tidier and what the author drew.
                foreach (int shared in SharedNotchesOf(placement, members))
                {
                    if (Math.Sqrt(MouldGeometry.PlanDistanceSquared(where, nodes[shared])) <= guard)
                    {
                        where = new Point3d(nodes[shared].X, nodes[shared].Y, where.Z);
                        break;
                    }
                }
                // A merge whose converged foot would put a participating
                // trunk past the cap is REFUSED and counted: it has bought
                // tidiness with a peel, and the peel would then undo it.
                bool overCap = members.Any(t =>
                    MouldGeometry.LeanFromVertical(where, nodes[placement.Trees[t].Nodes[Math.Max(placement.Trees[t].HeadMain, 0)]])
                        > MouldGeometry.MaxLeanDegrees + 1.0e-9);
                if (overCap)
                {
                    refused++;
                    continue;
                }
                foreach (int t in members)
                    foot[t] = where;
                merged++;
            }

            // ---- RULE 4, STANDING CLOSE BUT APART. Any two BUILT feet within
            // the feet-close clearance that did NOT become one node, whatever
            // the reason: not adjacent, refused by the mirror, refused by the
            // cap, or two feet of one span that are not its central pair.
            for (int a = 0; a < treeCount; a++)
            {
                for (int b = a + 1; b < treeCount; b++)
                {
                    if (node[a] >= 0 && node[a] == node[b])
                        continue;
                    double gap = Math.Sqrt(MouldGeometry.PlanDistanceSquared(foot[a], foot[b]));
                    if (gap <= 0.25 * Math.Min(spacing[a], spacing[b]))
                        close++;
                }
            }
            return node;
        }
```

`ToleranceOf` returns the tree's own `TauWeld`, which is `placement.Frames[tree.Span].TauWeld` on a span tree and `1e-9 * R` on the ring tree, with `R` the smallest plan distance between two of its own rim notches; `SpansAdjacent` builds the span-by-span adjacency once from the net's edge list and the shared-notch map; `CandidateNotchesOf` returns the notch indices `GroupFoot` took the tree's own foot from; `PlanOf` reads a notch's plan point off the frame; `SharedNotchesOf` returns the net nodes held by two of the component's spans at once; and `MirrorAccepts` implements the mirror-by-group-index rule of the third bullet above, reading `placed` and never `foot`. The node allocation into `levelNodes`, the weld of rule 1 and the recording of `footSpacing` happen in one pass after this and are what fill the returned `node` array.

Add to `Level`:

```csharp
            /// <summary>
            /// Merge candidates refused, by the mirror rule or by the lean
            /// cap. Reported rather than silent: accepting one of a mirrored
            /// pair of merges and not the other is exactly how two matching
            /// columns stop matching.
            /// </summary>
            public int MergeRefused;
            /// <summary>Convergences that fell back to the plan mean.</summary>
            public int ConvergenceFallback;
```

and rewrite `FeetMerged`'s doc comment to say it counts accepted merge GROUPS of both kinds.

- [ ] **Step 4: The second peel pass**

After the merge, run the peel AGAIN over the trees standing on a shared or merged foot. A merged foot is a fresh convergence and it MOVES, so a trunk sitting just inside sixty degrees before the merge can stand past it afterwards; the earlier draft's reasoning for judging the peel once was true of the peel and not of the merge. The second pass cannot cascade, because peeling is one-way, a peeled tree never rejoins a shared foot, and no foot moves on account of a peel; a tree that peels in the second pass takes its partner with it exactly as in the first. Because section 12 also refuses a merge whose converged foot would put a participating trunk over the cap, in practice the second pass finds nothing, and the harness is required to DEMONSTRATE that rather than to assume it.

The MERGE-THEN-PEEL fixture, built so that a trunk stands just inside sixty degrees before a cross-line merge and outside it after, asserts EITHER that the merge is refused and counted in `MergeRefused` OR that the second peel pass catches the trunk, and asserts that a THIRD pass changes nothing.

- [ ] **Step 5: Re-pin the three same-span fixtures**

Spec 17.1 and section 17's THE SAME-SPAN CENTRAL PAIR item:

1. `tests/native_smoke/Program.cs:6860-6895`, the plan-curved bar at Type 0. STAYS GREEN, with the clearance restated from `0.05 * medianPlanEdge` to `0.25 * g`. The gap of 1/9 sits inside 0.25 either way, the merged foot is still chord `(0, 160/81)`, `FeetMerged` is still 1 and the feet still seven. Print both clearances:

```csharp
            const double curvedG = 1.0;   // eight notches from 1/9 to 8/9 on a chord of 9
            Console.WriteLine($"      central-pair clearance 0.25 * g = {0.25 * curvedG:0.###} against 0.05 * median = {0.05 * 4.0:0.###} before; gap {1.0 / 9.0:0.###}.");
```

2. `tests/native_smoke/Program.cs:7115-7153`, the nudged ten-notch arch. STAYS GREEN, the innermost pair merging at x = 4.49 exactly and not at the chord midpoint of 4.5. Its gap is 0.032 against `0.25 * g = 0.25`. `AsymmetricSpans 0` became `UnpairedTrees 0` in Task 7.

3. `tests/native_smoke/Program.cs:7092-7113`, the narrow bay. STAYS GREEN in its MERGE count, because its tree row is ODD and only an EVEN row has a central pair. That is what keeps a centre column and its two leaning neighbours three columns rather than one, and it is the fixture that would flip if the merge were extended to any mirror pair. Its `FeetClose` count RISES on the new feet-close clearance, `0.25 * g = 0.167` against the old `0.033`, and Task 3 already put both numbers in its message.

- [ ] **Step 6: Run the gate green, then commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/ColumnPlacement.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(columns): feet weld, an even row's centre pair merges, and adjacent lines converge to one column"
```

---

### Task 9: The diagnostics and the component surface

Spec section 16. The diagnostics all keep the `columns.` prefix and the source name `Columns`, so `Diagnose` reads them without change, and the block written into `Mould.Columns` keeps its shape.

**Files:**
- Modify: `plugin/native_v02/Components/ColumnsComponent.cs` (the Branching tooltip at 158-164; the Type tooltip at 165-184; the `Message` at 433-438; `Diagnostics` at 492-742)
- Test: `tests/native_smoke/Program.cs`, one new block plus the `PASS` line at 996-1010

**Interfaces:**
- Consumes: every `Placement` and `Level` field added by Tasks 4 to 8.
- Produces: the diagnostic codes Task 10 asserts are present on the emitted Result.

- [ ] **Step 1: Write the diagnostics presence check, red**

A check that runs the component's `Diagnostics` by reflection on a placed net and asserts that every code spec section 16 names is present, that the retired phrase about unmirrored spans is ABSENT, and that `columns.overlap` carries the NEW sentence. `columns.symmetry` rises to `warning` when the residual is above 1e-9.

- [ ] **Step 2: Rewrite the diagnostics**

- `columns.grouping` keeps its code and reports the layout: the trees, the notches held, the STRAYS and where the ladder put them, and the remainder trees smaller than Branching. The phrase about the remainder sitting at the anchors is replaced by the ladder's own words.
- `columns.type` keeps its code and its context keys and reports the Type asked and placed, the GROUPS, the feet built, the CENTRAL COLUMNS and the peels. Where every non-ring tree peeled it still says the columns stand as Type 0. `nothingGathered` stays `Gathered > 0 && Peeled >= Gathered`.
- `columns.symmetry` keeps its code and reports the trees paired, the SELF-PAIRED trees, the UNPAIRED trees, the CLOSED SPANS, the families, the largest angle an aim moved through, and the COMMON MODE RESIDUAL beside it. The phrase about spans placed unmirrored GOES. The entry names the residual as the number that reads zero when the rule worked and says so in as many words, and rises to warning when the residual is above 1e-9.
- `columns.feet` is NEW, at info: the groups, the convergences accepted, the convergences that fell back to the mean, the welds and the distinct feet built.
- `columns.snap` is NEW, at info, and at warning when the worst snap exceeds half its span's own spacing: how far the furthest foot stands from the nearest notch, as a fraction of that span's spacing and as a length.
- `columns.shared_nodes` is NEW, at info: how many notches two principal lines share, that BOTH spans hold them for layout and symmetry, which span owns each head, and that the load at each is counted once and in full.
- `columns.span_degenerate` is NEW, at warning, for the two degenerate spans of section 15.
- `columns.feet_merged` keeps its code and reports BOTH kinds of merge group, naming adjacency by net edge and the clearance in the spans' own terms.
- `columns.feet_close` keeps its code and its warning, on the FEET-CLOSE CLEARANCE, and names whether a merge was refused by the mirror rule or by the lean cap. The entry says that the clearance HAS CHANGED SCALE, so an author comparing a saved definition's warnings before and after this wave is not left guessing.
- `columns.overlap` keeps its code and its warning and gets a NEW SENTENCE: both traces hold the notch, the owner rule decides which builds, and the doubly traced run is deduplicated in the head-pull arithmetic so that its along-bar contribution is not subtracted twice.
- `columns.alignment`, `columns.collision`, `columns.lean`, `columns.load_path`, `columns.branch_off_thrust`, `columns.head_load`, `columns.head_load_total`, `columns.load_split`, `columns.plumb_fallback`, `columns.spans`, `columns.ring_tree`, `columns.bar_shape`, `columns.principal_source`, `columns.no_principal_runs` and `columns.demand_only` are UNCHANGED in code and in content, save that `head_load_total` now reports the full load.

The `Message` becomes:

```csharp
                Message = (type < 0 ? "Auto: " : string.Empty)
                    + $"Type {placement.GroundPlaced}, {Count(built.Feet.Count, "foot", "feet")}"
                    + (built.CentralColumns > 0 ? $", {built.CentralColumns} central" : string.Empty)
                    + (built.Peeled > 0 ? $", {built.Peeled} peeled" : string.Empty)
                    + (placement.UnpairedTrees > 0 ? $", {placement.UnpairedTrees} unpaired" : string.Empty);
```

The Type VALUE LIST ITEMS are UNCHANGED, by spec section 2, so the canvas still reads "2 two feet" on a span that will show three. The TOOLTIP carries the truth and is rewritten to say that Type N gathers each span's trees onto N MIRRORED feet, that a foot stands where its group's own central notches converge, and that a tree standing alone in the middle of an odd row at an even Type keeps its own STRAIGHT column, so the foot count can be one more than the Type or, on a span of fewer trees, fewer. The Branching tooltip is rewritten to the ladder: trees of B neighbouring notches, mirrored about the middle of each span, with ONE stray at the centre, TWO at the ends, and THREE at the ends and the centre.

- [ ] **Step 3: Update the harness `PASS` line**

The long `PASS  ColumnPlacement: ...` sentence at `tests/native_smoke/Program.cs:996-1010` still describes bands and unmirrored spans. Rewrite it to name what is now measured: the ladder's tables at fewest strays, the foot groups, the group foot at its own central notches, the central column standing straight, the shared notch held by both lines with its load counted once and in full, the common mode removed by subtraction, and the merge in the spans' own terms.

- [ ] **Step 4: Run the gate green, then commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/ColumnsComponent.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(columns): the diagnostics say what the ladder, the shared nodes and the residual did"
```

---

### Task 10: The records, and the preservation pins

Spec section 17's tail. Every one of these is a MEASUREMENT in the check's message or a preservation asserted as a FAILURE and not as a comment.

**Files:**
- Test only: `tests/native_smoke/Program.cs`

**Interfaces:**
- Consumes: every field and rule of Tasks 1 to 9.
- Produces: nothing the engine reads.

- [ ] **Step 1: The mirror defect is zero**

On every fixture above, compute the worst mirror defect of the SORTED foot list about the NOTCH ROW'S OWN centre, which on a symmetric row is the chord midpoint and on a lopsided one is not, and assert it is zero to 1e-9 wherever the notch row is symmetric and no worse than the notch row's own defect wherever it is not. The present engine gives 1.0, 2.0, 3.0, 3.0 and 2.0 metres on the crossed span at Types 0 to 4. At Type 0 on a crossed span the bound is the notch row's defect PLUS the contribution of the other bar's pull, which the check COMPUTES rather than assumes.

- [ ] **Step 2: The peel, the merge and the collision counts, as records**

Record, as measured numbers in the check's message and not as claims:

- the PEEL COUNT at each of Types 1 to 4 on the control arch and on the plan-curved bar;
- on the review net, the count of accepted CROSS-LINE MERGES, the count of accepted SAME-SPAN CENTRAL PAIRS, the count of WELDS, and the count of feet standing CLOSE BUT APART. The spec's own expectation is that cross-line merging is rare on a net whose lines meet at a shared node, because the feet coincide there and are WELDED instead, and the point of the record is that the expectation is a measurement rather than an assumption;
- the COLLISION COUNT and Auto's chosen level under the old net-median clearance and under the new span-term one, with the new counts asserted to be the ones the check computes from the span spacings.

- [ ] **Step 3: The preservation pins**

Each asserted as a failure and not as a comment:

- Every member of every fixture leaves LOWER END FIRST.
- Every fork lies on its foot-to-HEAD-MAIN segment to 1e-9, and the LOWERED-FORK case fires on an anchor-end tree at Branching 3 whose outer notch is below the fork height.
- The ring tree's foot is IDENTICAL before and after this wave on the free-rim fixture, it never merges, its rim notches still cut the spans, and its `TAU_weld` and its collision clearance come from its own rim scale R and never from a net median.
- Auto's chosen level equals the level the check RECOMPUTES from `Tried`.
- The Type value list items and values pin UNCHANGED, all six of them, INCLUDING the item text `"2 · two feet"` on a fixture that places three, which is the inaccuracy spec section 2 leaves standing knowingly and section 18.3 puts to Param. The check NAMES it so that nobody later reads the green as agreement:

```csharp
            // The item text is pinned UNCHANGED and it is KNOWINGLY
            // INACCURATE: this fixture places THREE feet under an item that
            // reads "two feet", because an odd tree row at an even Type
            // leaves one column standing alone. The brief preserves the list,
            // the tooltip carries the truth, and the wording that would fix
            // it is "2 two gathered feet". Changing the item text is PARAM'S
            // to authorise, and spec section 18.3 has it open for him. Do not
            // read this green as agreement.
```

- Every `columns.` code spec section 16 names is present on the emitted Result, the retired phrase about unmirrored spans is ABSENT, the `columns.overlap` sentence is the new one, and `Diagnose` renders the set.

- [ ] **Step 4: No NaNs and no escapes**

On every fixture above, assert every foot is FINITE and lies within its span's own plan bounding box grown by ONE NOTCH SPACING plus the merge clearance, so that a foot beyond its own anchors is caught as a failure rather than read off a screenshot.

- [ ] **Step 5: Run the gate green, then commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "tests/native_smoke/Program.cs"
git -C $repo commit -m "test(columns): the peel, merge and collision counts recorded, and every preservation pinned"
```

---

### Task 11: Rebuild, install, hand over

Spec section 20 requires the install as the final step. This task is NOT run by the implementer of Tasks 1 to 10: the controller executes it after the whole-branch review, so the installed `.gha` is the reviewed one.

**Files:** none.

**Interfaces:** none.

- [ ] **Step 1: Check for clashes, then build and install with Rhino CLOSED**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
$clash = Get-ChildItem -Path "$repo\plugin","$repo\tests","$repo\docs" -Recurse -Filter "*Name clash*" -ErrorAction SilentlyContinue
if ($clash) { $clash | ForEach-Object { $_.FullName }; throw "OneDrive clash file in the tree; resolve by CONTENT before installing" }
Get-Process -Name "Rhino" -ErrorAction SilentlyContinue
& "$repo\plugin\native_v02\Build-And-Install.ps1"
```

If `Get-Process` returns a running Rhino, stop and ask Param to close it: the installed `.gha` is locked while Rhino holds it.

- [ ] **Step 2: Hand over**

Tell Param, in plain text with full absolute paths:

- what changed, in one line per task;
- that the plugin is installed at `C:\Users\Param\AppData\Roaming\Grasshopper\Libraries\Ananke_COMPAS\Ananke.COMPAS.gha` and RHINO MUST BE RESTARTED, because an open session keeps the old `.gha` and the old worker;
- that BRANCHING 3 MOVES COLUMNS ON SAVED DEFINITIONS at four free-notch counts, 3, 7, 9 and 13, by his own ruling of 2026-09-01, and that none moves at Branching 1 or 2;
- that the FEET-CLOSE warning has changed scale by a factor of five and will warn more often, and that the COLLISION clearance has changed with it and can move Auto's choice on some nets;
- that on a clean symmetric span not one column moved, and that what changed is that the same numbers now come out on a span with an off-centre crest, a crossing, a free end or a coarse mesh, where the engine handed back a foot set 10 to 30 per cent of the span away from mirrored;
- that TWO items remain open for him in spec section 18.3, the Type value list's item text and the even group's foot standing between two notches rather than on one;
- that the commits are local and NOT pushed.

---

