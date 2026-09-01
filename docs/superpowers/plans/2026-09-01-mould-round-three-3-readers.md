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

## Phase three: the readers merge, Tasks 33 to 47

**Spec (binding):** `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\docs\superpowers\specs\2026-09-01-readers-merge-design.md`

**Goal:** Frame and Deconstruct become ONE fifteen-port reader called Deconstruct, on a new GUID, with the four restated-identifier ports gone, Support Points absorbed into Anchor Nodes, Reaction Vectors rebranched onto the anchor strips and the stray reaction reported rather than dropped, Anchor Lines reduced to one line per strip; Diagnose's Result input becomes optional so an unwired Diagnose reads the whole document; and Import Pieces' and Export's diagnostics text becomes runtime messages.

**Position in the build:** this part runs LAST of the three in this wave. It changes port names and counts on components the columns and skin parts feed, and `ParameterIdentity.Mismatch` compares archived port names as well as counts, so landing it earlier would make every intermediate build warn on saved definitions for reasons about to change again.

**Architecture:** the merged reader keeps the class name `DeconstructComponent` in `VisualiseComponents.cs` (rule 1.4A pins it, because the harness reflects on that string in three places) and `FrameComponents.cs` is deleted outright. Its solve is partitioned into two internal statics with separate catches, `FrameHalf` over `FrameGeometry.Build` and `StaticsHalf` over `ResultTables`, so a Result one half refuses still hands back the other half's ports. Three further internal statics carry what the spec asks the harness to measure: `ReactionBranches` (rebranching plus stray detection) and `SeedDivergence` (the two support lists compared as sets). `FrameGeometry`'s `Net` and `Set` records gain the anchor strips' node index lists, which is what makes the rebranching possible at all. Diagnose gains a document scan built on three pure statics, `IsOurs`, `Digest` and `Scan`, plus a `SolutionEnd` subscription with a content latch.

**Tech Stack:** C# 12 on .NET 8 (`net8.0-windows`), Grasshopper/RhinoCommon 8, the Rhino-free reflection smoke harness in `tests\native_smoke\Program.cs`, and the standard-library-only icon generator in `plugin\icons`.

Further constraints this part carries:

- Repo root: `C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow`. The plugin is `plugin\native_v02`; the harness is `tests\native_smoke\Program.cs`.
- This part runs on the branch the columns and skin parts already cut. If it is executed on its own, cut a branch from `main` first and never push it.
- Files are UTF-8 WITHOUT BOM. Any file created or wholesale-rewritten is BOM-checked before its gate.
- RES stays input 0 on every reader. Readers' geometry outputs start HIDDEN, set by the constructor loop over `Params.Output`.
- The load-protection warning compares archived port NAMES as well as counts (`ParameterIdentity.Mismatch`, `NativeComponentBase.cs:321-407`). Every port reshape here updates its harness pins (`VisualiseContracts`, `SpineComponentContracts`, `NativeIconEntries`, the component count) in the SAME task as the reshape.
- Two GUIDs are retired and NEVER reused: Deconstruct's `68d0b4f2-9a3e-4c17-85d6-f2b8a0c4e961` and Frame's `5d8e2f61-7a4c-4b93-a0e6-c3f19b7d2a58`. The merged reader takes a NEW GUID, written once, in Task 38.
- `ResultTables`, `MouldGeometry`, `MonitorMath` and `plugin\native_v02\Contracts\` are not edited by this part.
- The spec's own warning at rule 10.1: there is a OneDrive edit-conflict artefact in the harness release folder, `tests\native_smoke\bin\Release\net8.0-windows\Ananke.COMPAS.NativeSmoke (# Edit conflict 2026-08-31 5sa2jeC #).dll`. Delete it before trusting any harness run. Task 33 step 1 does this.
- Two things are REFUSED rather than deferred (spec section 11): a sixteenth Result-passthrough port on the merged reader, put to Param and declined; and retiring Backend Health's Report. Neither is a gap for an implementer to close.

### The shared gate

Every "run the gate" step means exactly this, from PowerShell, from any directory:

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
$clash = Get-ChildItem -Path "$repo\plugin","$repo\tests","$repo\docs" -Recurse -Filter "*Name clash*" | Where-Object { $_.FullName -notmatch '\\obj\\' }
if ($clash) { $clash | ForEach-Object { $_.FullName }; throw "OneDrive clash file in the tree; resolve by CONTENT before building" }
dotnet build "$repo\plugin\native_v02\Ananke.COMPAS.Native.csproj" -c Release -v quiet --nologo
dotnet run --project "$repo\tests\native_smoke\Ananke.COMPAS.NativeSmoke.csproj" -c Release -- "$repo\plugin\native_v02\bin\Release\net8.0-windows\Ananke.COMPAS.gha"
```

A passing gate prints `0 warnings` from the build, `Components discovered: 21` (20 from Task 38 on), `Parameters discovered: 12`, a `PASS` line for every check with no `FAIL`, and ends `Native component smoke test passed; Rhino was not launched.` at exit code 0.

Icon-touching tasks additionally run:

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
python "$repo\plugin\icons\generate_icons.py" --check
```

which must end `Validated ... icon files; every one matches a fresh render of the map entry that owns it, byte for byte. ...`.

The BOM check, for any file created or wholesale-rewritten, run from the repo root:

```powershell
python -c "import sys; bad=[p for p in sys.argv[1:] if open(p,'rb').read(3)==b'\xef\xbb\xbf']; print('\n'.join(bad)); sys.exit(1 if bad else 0)" <paths>
```

Commit messages follow the repo's `type(scope): sentence` style with no attribution lines.

### What this part deliberately does not do

Out of scope, from spec section 11, and named so that nothing here is mistaken for an oversight: descending into clusters (question 12B(b)); harvesting the diagnostics inside a Result during a document scan (question 12B(c)); giving Export a Result output of its own (question 12B(d)); renaming Export's Status port (question 12B(e)); re-seeding Supports from `ResolvedSupportNodeIds`, or re-seeding the merged reader from `Mappings.Supports`, so the two agree by construction rather than by warning; changing Load Points and Load Vectors from lists to trees; adding a pure-truncation branch to the load warning; Skin's Diagnostics port and Skin's harness pin at `Program.cs:100-102`, which the skin part of this wave owns; Export's INPUT pin at `Program.cs:183-189`, which the skin part reorders; and any change to what a measure computes.

TWO THINGS ARE REFUSED RATHER THAN DEFERRED. A sixteenth port on the merged reader carrying the Result through with diagnostics appended was PUT TO PARAM AND DECLINED; it is not waiting for a quiet round to pick it up, and Task 39's check is what holds that. Retiring Backend Health's Report was proposed and REFUSED by the controller; nothing about that component changes here, not its registration, not its content, not its harness entries.

THE PRICE OF THE LEAF, said out loud so nobody rediscovers it later as a defect and quietly adds a port to fix it: a stray reaction is reported on the canvas and NOWHERE ELSE. It is not written into the Result, so it is not in what Export writes, so the studio receives a study carrying no record that a reaction was reported at a node on no anchor strip. An author can export a vault whose supports do not account for one of its reactions and nothing downstream of the canvas will say so. Param has seen that and taken it.

The items this phase's spec leaves open are gathered at the end of this plan, under "What the three specs leave open for Param".

---

### Task 33: No two ports of one component share a nickname

Spec rule 10.3(a). This lands FIRST, before the merge, because it is the check that would have caught Frame's Mesh `M` against Deconstruct's Member Lines `M`, and it is worth having in place before the merge that would produce the collision. Verified against the shipped plugin on 2026-09-01: no component has a duplicate nickname on either side today, so the check is green the moment it is written.

**Files:**
- Modify: `tests/native_smoke/Program.cs` (a new `ValidateUniqueNickNames` beside `ValidateSpineComponentContract` at :1865, and one call added in the per-component loop at :445-446)
- Test: `ValidateUniqueNickNames`, run inside the discovery loop over every one of the twenty-one components

**Interfaces:**
- Consumes: nothing from earlier tasks. It reads `Params.Input` and `Params.Output` off a live component instance, exactly as `ValidateVisualiseContract` does at `Program.cs:1829-1845`.
- Produces: nothing later tasks call. Task 38 relies on it being in force: the merged reader's Mesh `M` and Member Lines `ML` are what it protects.

- [ ] **Step 1: Delete the stale harness binary and prove the gate is green**

The spec's rule 10.1 warns that a green run over this artefact proves less than it looks.

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
Remove-Item -Force "$repo\tests\native_smoke\bin\Release\net8.0-windows\Ananke.COMPAS.NativeSmoke (# Edit conflict 2026-08-31 5sa2jeC #).dll" -ErrorAction SilentlyContinue
Get-ChildItem -Path "$repo\tests\native_smoke\bin" -Recurse -Filter "*Edit conflict*" | ForEach-Object { $_.FullName }
```

The second command must print nothing. Then run the gate. It must be green before anything is changed.

- [ ] **Step 2: Write the check and watch it run green**

Add this method to `tests/native_smoke/Program.cs` immediately after `ValidateSpineComponentContract` ends (after line 1947 area, before the next member):

```csharp
    /// <summary>
    /// No two of a component's OUTPUTS share a nickname, and no two of its
    /// INPUTS do.
    ///
    /// Grasshopper does not refuse the collision. It registers both ports,
    /// draws two of them carrying one label, and says nothing at all, so
    /// the only place it surfaces is on the canvas in front of an author
    /// who has no way of telling which port he is wiring. This runs over
    /// EVERY component rather than the one being reshaped, because the
    /// collision is made by merging two port lists that were each fine on
    /// their own, and the next merge will be somebody else's.
    /// </summary>
    private static void ValidateUniqueNickNames(
        object instance,
        Type componentType)
    {
        object parameters = componentType
            .GetProperty("Params")
            ?.GetValue(instance)
            ?? throw new InvalidOperationException(
                $"Could not inspect {componentType.Name} parameters.");

        void Side(string sideName)
        {
            IList side = parameters
                .GetType()
                .GetProperty(sideName)
                ?.GetValue(parameters) as IList
                ?? throw new InvalidOperationException(
                    $"Could not inspect {componentType.Name} {sideName}.");
            var seen = new Dictionary<string, int>(StringComparer.Ordinal);
            for (int index = 0; index < side.Count; index++)
            {
                object port = side[index]!;
                string nick =
                    port.GetType().GetProperty("NickName")?.GetValue(port)
                        as string
                    ?? string.Empty;
                if (seen.TryGetValue(nick, out int first))
                {
                    throw new InvalidOperationException(
                        $"{componentType.Name} {sideName.ToLowerInvariant()}s "
                        + $"{first} and {index} both carry the nickname "
                        + $"'{nick}'. Grasshopper allows it and draws two "
                        + "ports with one label, so nothing but this check "
                        + "says so.");
                }
                seen[nick] = index;
            }
        }

        Side("Input");
        Side("Output");
    }
```

Add the call in the per-component loop, after the `ValidateSpineComponentContract` line at `Program.cs:446`, so the block reads:

```csharp
                ValidateVisualiseContract(instance, componentType);
                ValidateSpineComponentContract(instance, componentType);
                ValidateUniqueNickNames(instance, componentType);
                ValidateIcon(instance, componentType);
```

- [ ] **Step 3: Prove it fails on a real collision**

Temporarily change `plugin/native_v02/Components/FrameComponents.cs:161` from `"AL"` to `"M"`, run the gate, and confirm it fails with `FrameComponent outputs 0 and 9 both carry the nickname 'M'`. Then restore `"AL"` and run the gate again to see it green. Do not commit the temporary change.

- [ ] **Step 4: Run the gate**

Green, `Components discovered: 21`, no `FAIL`.

- [ ] **Step 5: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "tests/native_smoke/Program.cs"
git -C $repo commit -m "test(native_smoke): no two ports of one component share a nickname"
```

---

### Task 34: The anchor strips carry their node indices

Spec rule 3.8, and the measured half of rule 10.3(c). `FrameGeometry.Set` holds `AnchorGroups` as `List<List<Point3d>>`, positions only, with no node ids (`MouldComponents.cs:2435`). Rebranching Reaction Vectors onto those strips needs the ids, so they are added to `Net` and carried onto `Set` beside `AnchorGroups`. The spec calls this a required change whichever seed list wins.

**Files:**
- Modify: `plugin/native_v02/Components/MouldComponents.cs:2411-2421` (the `Net` record), `:2430-2441` (the `Set` record), `:2595-2609` (Read's return), `:2660-2671` (Build's return)
- Modify: `tests/native_smoke/Program.cs` (a new `ValidateFrameAnchorStrips` plus its try/catch PASS block beside the `ValidateFrameGeometry` block at :1202-1219)
- Test: `ValidateFrameAnchorStrips`

**Interfaces:**
- Consumes: `FrameGeometry.Read(ResultDto result, Mesh? mesh, int[] meshToNode)` returning `FrameGeometry.Net`, unchanged in signature.
- Produces:
  - `FrameGeometry.Net.AnchorNodeIds`, type `List<List<int>>`, positional member 4, immediately after `AnchorGroups`.
  - `FrameGeometry.Set.AnchorNodeIds`, type `List<List<int>>`, positional member 5, immediately after `AnchorGroups`.
  - Task 35 inserts `AnchorCloses` and `AnchorLines` after these. Task 38's `SolveInstance` reads `set.AnchorNodeIds` and hands it to `StaticsHalf`.

- [ ] **Step 1: Write the check first, and watch it fail**

Add to `tests/native_smoke/Program.cs`, immediately before `ValidateFrameAnchorLines` at :5109:

```csharp
    /// <summary>
    /// <c>FrameGeometry.Net.AnchorNodeIds</c>: the anchor strips as NODE
    /// INDEX lists beside the same strips as points.
    ///
    /// Rebranching Reaction Vectors onto the anchor strips is an INDEX
    /// question, and <c>AnchorGroups</c> carries positions only. Matching a
    /// reaction back to its strip by coordinate would turn an exact answer
    /// into a tolerance, which is the whole reason the ids are carried.
    ///
    /// The fixture is the three-by-three unit grid <c>ValidateFrameGeometry</c>
    /// uses, twelve edges, no faces and no pattern topology, anchored at
    /// nodes 0, 1, 2 and 8. Nodes 0, 1 and 2 are the bottom row and are
    /// joined by two edges, so they are ONE strip; node 8 is joined to
    /// neither, so it is a strip of its own. That gives the two properties
    /// worth pinning: a multi-node strip comes back walked END TO END, and a
    /// strip of ONE keeps its own branch rather than being merged away.
    /// </summary>
    private static void ValidateFrameAnchorStrips(Assembly plugin)
    {
        Type geometry = RequireComponentType(plugin, "FrameGeometry");
        MethodInfo read = RequirePublicStatic(geometry, "Read");
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edge = RequireContractType(plugin, "EdgeDto");

        object P(double x, double y, double z) =>
            Activator.CreateInstance(point, x, y, z)!;
        Array Points(IEnumerable<object> items)
        {
            object[] all = items.ToArray();
            Array array = Array.CreateInstance(point, all.Length);
            for (int i = 0; i < all.Length; i++)
                array.SetValue(all[i], i);
            return array;
        }
        var pairs = new List<(int U, int V)>();
        for (int row = 0; row < 3; row++)
        {
            for (int column = 0; column < 2; column++)
                pairs.Add(((row * 3) + column, (row * 3) + column + 1));
        }
        for (int column = 0; column < 3; column++)
        {
            for (int row = 0; row < 2; row++)
                pairs.Add(((row * 3) + column, ((row + 1) * 3) + column));
        }
        Array edges = Array.CreateInstance(edge, pairs.Count);
        for (int i = 0; i < pairs.Count; i++)
            edges.SetValue(Activator.CreateInstance(edge, pairs[i].U, pairs[i].V), i);

        object Read(int[] anchors)
        {
            object eq = CreateInstance(equilibriumType);
            SetContractProperty(eq, equilibriumType, "Vertices", Points(
                Enumerable.Range(0, 9).Select(i => P(i % 3, i / 3, 0.0))));
            SetContractProperty(eq, equilibriumType, "Edges", edges);
            SetContractProperty(
                eq, equilibriumType, "ResolvedSupportNodeIds", anchors);
            object result = CreateResultDto(resultType, "fd", eq, null, null);
            return read.Invoke(null, new object?[] { result, null, Array.Empty<int>() })
                ?? throw new InvalidOperationException(
                    "FrameGeometry.Read returned null.");
        }
        T Member<T>(object owner, string name) =>
            (T)(owner.GetType().GetProperty(name)
                ?? throw new InvalidOperationException(
                    $"FrameGeometry.Net has no {name}."))
                .GetValue(owner)!;

        object net = Read(new[] { 0, 1, 2, 8 });
        IList groups = Member<IList>(net, "AnchorGroups");
        IList ids = Member<IList>(net, "AnchorNodeIds");
        if (groups.Count != 2 || ids.Count != 2)
        {
            throw new InvalidOperationException(
                "Nodes 0, 1 and 2 are joined and node 8 is joined to neither, "
                + "so the anchors are TWO strips; got "
                + $"{groups.Count} point branches and {ids.Count} id branches.");
        }
        int[][] walked = ids
            .Cast<IEnumerable>()
            .Select(branch => branch.Cast<int>().ToArray())
            .ToArray();
        if (!walked[0].SequenceEqual(new[] { 0, 1, 2 }) ||
            !walked[1].SequenceEqual(new[] { 8 }))
        {
            throw new InvalidOperationException(
                "The strips come back walked END TO END and in order of their "
                + "lowest node, so the ids are [0,1,2] then [8]; got ["
                + string.Join(",", walked[0]) + "] then ["
                + string.Join(",", walked[1]) + "].");
        }
        Array positions = Member<Array>(net, "Positions");
        Type point3d = positions.GetType().GetElementType()!;
        double Axis(object value, string axis) =>
            (double)point3d.GetProperty(axis)!.GetValue(value)!;
        for (int branch = 0; branch < 2; branch++)
        {
            object[] strip = ((IList)groups[branch]!).Cast<object>().ToArray();
            if (strip.Length != walked[branch].Length)
            {
                throw new InvalidOperationException(
                    $"Branch {branch} carries {strip.Length} points against "
                    + $"{walked[branch].Length} ids; the two must pair item "
                    + "for item or the rebranching has nothing to trust.");
            }
            for (int item = 0; item < strip.Length; item++)
            {
                object at = positions.GetValue(walked[branch][item])!;
                if (Math.Abs(Axis(strip[item], "X") - Axis(at, "X")) > 1.0e-9 ||
                    Math.Abs(Axis(strip[item], "Y") - Axis(at, "Y")) > 1.0e-9)
                {
                    throw new InvalidOperationException(
                        $"Branch {branch} item {item} is the point of node "
                        + $"{walked[branch][item]}, read off the same "
                        + "Positions array, or the ids name a different "
                        + "support from the one the points draw.");
                }
            }
        }
    }
```

Register it beside the existing `ValidateFrameGeometry` block. Insert this immediately after the `ValidateFrameGeometry` try/catch that ends at `Program.cs:1219`:

```csharp
        try
        {
            ValidateFrameAnchorStrips(plugin);
            Console.WriteLine(
                "PASS  FrameGeometry anchor strips: the strips come back as "
                + "NODE INDEX lists beside the same strips as points, walked "
                + "end to end, a strip of one keeping its own branch, and the "
                + "two pairing item for item, which is what lets Reaction "
                + "Vectors be rebranched onto them by index rather than by "
                + "coordinate.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"FrameGeometry anchor strips: {DescribeException(exception)}");
        }
```

Run the gate. It must fail with `FrameGeometry.Net has no AnchorNodeIds`.

- [ ] **Step 2: Add the member to Net**

Replace `plugin/native_v02/Components/MouldComponents.cs:2411-2421` with:

```csharp
        public sealed record Net(
            Point3d[] Positions,
            List<List<Line>> Cables,
            List<List<Point3d>> PrincipalNodes,
            List<List<Point3d>> AnchorGroups,
            List<List<int>> AnchorNodeIds,
            List<List<Point3d>> PerimeterLoops,
            bool[] PerimeterCloses,
            bool PerimeterEstimated,
            int PerimeterCount,
            List<List<Line>> ColumnBranches,
            string Phase);
```

and extend the record's own doc comment above it, at `:2407-2410`, so it reads:

```csharp
        /// <summary>
        /// The frame in managed types: everything that can be worked out
        /// without a Rhino to call.
        ///
        /// <c>AnchorNodeIds</c> is the same strips as <c>AnchorGroups</c>,
        /// item for item, as NODE INDICES rather than positions. Which
        /// support a reaction belongs to is an index question, and the
        /// points cannot answer it: matching a reaction back to a strip by
        /// coordinate would turn an exact answer into a tolerance one.
        /// </summary>
```

- [ ] **Step 3: Add the member to Set and fill both**

Replace `MouldComponents.cs:2430-2441`, the `Set` record, with:

```csharp
        public sealed record Set(
            Mesh? Mesh,
            List<List<Line>> Cables,
            List<List<Curve>> PrincipalLines,
            List<List<Point3d>> PrincipalNodes,
            List<List<Point3d>> AnchorGroups,
            List<List<int>> AnchorNodeIds,
            List<List<Point3d>> PerimeterNodes,
            List<List<Curve>> PerimeterLines,
            bool PerimeterEstimated,
            int PerimeterCount,
            List<List<Line>> ColumnBranches,
            string Phase);
```

In `Read`, replace the return at `:2595-2609` with:

```csharp
            return new Net(
                positions,
                cables,
                principalNodes,
                anchorStrips
                    .Select(strip => strip.Select(i => positions[i]).ToList())
                    .ToList(),
                anchorStrips,
                perimeterLoops
                    .Select(loop => loop.Select(i => positions[i]).ToList())
                    .ToList(),
                closes,
                perimeterEstimated,
                perimeterIds.Length,
                columnBranches,
                phase);
```

In `Build`, replace the return at `:2660-2671` with:

```csharp
            return new Set(
                framed,
                net.Cables,
                principalLines,
                net.PrincipalNodes,
                net.AnchorGroups,
                net.AnchorNodeIds,
                net.PerimeterLoops,
                perimeterLines,
                net.PerimeterEstimated,
                net.PerimeterCount,
                net.ColumnBranches,
                net.Phase);
```

- [ ] **Step 4: Run the gate and see the new check pass**

Green, and the new PASS line present. `MouldAnimateComponent` at `MouldComponents.cs:560` and `FrameComponent` at `FrameComponents.cs:192` both construct `Set` only through `Build`, so neither needs an edit.

- [ ] **Step 5: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/MouldComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(frame): the anchor strips carry their node indices"
```

---

### Task 35: Anchor Lines becomes one line per strip

Spec section 5. Param is seeing "20 items and 2 trees" and wants "just be 2 lines" (design input :63-65). What is settled either way: ONE line per strip, running the length of it; two strips give two items, not twenty.

**BUILD THE POLYLINE OF RULE 5.2(b).** That is an instruction and not a condition. The spec's own body is written for the polyline, it is the spec's own recommendation, and sections 5.4 to 5.6 and 10.2(f) set it out; so the steps below build it and an engineer working through this plan in sequence, in a fresh session, runs them without waiting on anybody.

Question 12B(a) remains OPEN and is recorded as a FOLLOW-UP rather than as a gate, because an unanswered question that stops the whole of phase three is worse for Param than a default he can overturn later at a known cost. If he takes the CHORD of rule 5.2(a) instead, the cost is written out and it is small: Step 4A replaces Steps 2, 3 and 5, Step 4B replaces Step 6, one slot of the registration in Task 38 changes `AddCurveParameter` back to `AddLineParameter` with its own description, and nothing else in this plan moves. Both alternatives are written out in full below, so taking the other one later is an edit and not a redesign.

**Files:**
- Modify: `plugin/native_v02/Components/MouldComponents.cs` (the `Net` record, `Read`'s close computation and return, the `Set` record, `Build`'s branch build and return, and the deletion of `FrameGeometry.AnchorLines` at :2674-2695)
- Modify: `plugin/native_v02/Components/FrameComponents.cs:159-169` (the port registration) and `:202-203` (the emit)
- Modify: `tests/native_smoke/Program.cs:5109-5177` (`ValidateFrameAnchorLines` rewritten) and its PASS text at :1342-1354
- Test: `ValidateFrameAnchorLines`

**Interfaces:**
- Consumes: `FrameGeometry.Net.AnchorNodeIds` and `FrameGeometry.Set.AnchorNodeIds` from Task 34; `MouldGeometry.GroupingAdjacency(ResultDto, (int,int)[], int)` returning `List<int>[]`, already used at `MouldComponents.cs:2573-2574`.
- Produces:
  - `FrameGeometry.Net.AnchorCloses`, type `bool[]`, positional member 5, immediately after `AnchorNodeIds`.
  - `FrameGeometry.Set.AnchorLines`, type `List<List<Curve>>`, and `FrameGeometry.Set.AnchorCloses`, type `bool[]`, positional members 6 and 7.
  - `FrameGeometry.AnchorLines(List<List<Point3d>>)` is DELETED. Task 38 emits `set.AnchorLines` through `OutputTree.Curves`.

- [ ] **Step 1: Rewrite the check first, and watch it fail**

Replace the whole of `ValidateFrameAnchorLines` at `tests/native_smoke/Program.cs:5109-5177` with:

```csharp
    /// <summary>
    /// Anchor Lines under spec section 5: ONE line per strip, running the
    /// length of it, so two strips give two items rather than twenty.
    ///
    /// MEASURED HERE, driven off <c>FrameGeometry.Read</c>, which is
    /// Rhino-free by design: the strips' branch count, and the
    /// <c>AnchorCloses</c> flag of rule 5.4(a), true on a ring fixture and
    /// false on an open strip. A vault anchored right around its springing
    /// gives exactly such a ring, and the earlier rule that assumed an
    /// anchor strip is never a loop would have handed back a polyline one
    /// segment short of closing with nothing said.
    ///
    /// NOT MEASURED, and stated rather than papered over: the Polyline
    /// construction and the empty-branch guard live in
    /// <c>FrameGeometry.Build</c> and need the native core, exactly as
    /// Perimeter Lines' conversion does today, so "one branch holding one
    /// polyline of three points" cannot be asserted from this harness. If
    /// that guard is ever to be measured, the guard ITSELF is extracted as
    /// an internal static over the strips and that static is what this
    /// drives.
    ///
    /// The fixtures are the three-by-three unit grid. Anchoring 0, 1, 2 and
    /// 8 gives one open strip of three and one of one, neither closing.
    /// Anchoring the whole boundary ring, 0, 1, 2, 3, 5, 6, 7 and 8, gives
    /// ONE strip whose last walked node is adjacent to its first in the
    /// grouping graph, which is what <c>AnchorCloses</c> is asking.
    /// </summary>
    private static void ValidateFrameAnchorLines(Assembly plugin)
    {
        Type geometry = RequireComponentType(plugin, "FrameGeometry");
        MethodInfo read = RequirePublicStatic(geometry, "Read");
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edge = RequireContractType(plugin, "EdgeDto");

        object P(double x, double y, double z) =>
            Activator.CreateInstance(point, x, y, z)!;
        Array Points(IEnumerable<object> items)
        {
            object[] all = items.ToArray();
            Array array = Array.CreateInstance(point, all.Length);
            for (int i = 0; i < all.Length; i++)
                array.SetValue(all[i], i);
            return array;
        }
        var pairs = new List<(int U, int V)>();
        for (int row = 0; row < 3; row++)
        {
            for (int column = 0; column < 2; column++)
                pairs.Add(((row * 3) + column, (row * 3) + column + 1));
        }
        for (int column = 0; column < 3; column++)
        {
            for (int row = 0; row < 2; row++)
                pairs.Add(((row * 3) + column, ((row + 1) * 3) + column));
        }
        Array edges = Array.CreateInstance(edge, pairs.Count);
        for (int i = 0; i < pairs.Count; i++)
            edges.SetValue(Activator.CreateInstance(edge, pairs[i].U, pairs[i].V), i);

        object Read(int[] anchors)
        {
            object eq = CreateInstance(equilibriumType);
            SetContractProperty(eq, equilibriumType, "Vertices", Points(
                Enumerable.Range(0, 9).Select(i => P(i % 3, i / 3, 0.0))));
            SetContractProperty(eq, equilibriumType, "Edges", edges);
            SetContractProperty(
                eq, equilibriumType, "ResolvedSupportNodeIds", anchors);
            object result = CreateResultDto(resultType, "fd", eq, null, null);
            return read.Invoke(null, new object?[] { result, null, Array.Empty<int>() })
                ?? throw new InvalidOperationException(
                    "FrameGeometry.Read returned null.");
        }
        T Member<T>(object owner, string name) =>
            (T)(owner.GetType().GetProperty(name)
                ?? throw new InvalidOperationException(
                    $"FrameGeometry.Net has no {name}."))
                .GetValue(owner)!;

        object open = Read(new[] { 0, 1, 2, 8 });
        bool[] openCloses = Member<bool[]>(open, "AnchorCloses");
        IList openGroups = Member<IList>(open, "AnchorGroups");
        if (openCloses.Length != openGroups.Count)
        {
            throw new InvalidOperationException(
                "There is one AnchorCloses flag per strip, or the flag and "
                + $"the strip it belongs to fall out of step; got "
                + $"{openCloses.Length} flags for {openGroups.Count} strips.");
        }
        if (openCloses.Any(one => one))
        {
            throw new InvalidOperationException(
                "A strip of three in a row does not close, and neither does a "
                + "strip of one: the last node walked is not adjacent to the "
                + "first in the grouping graph, and a closing segment drawn "
                + "there would be a chord across the net rather than a member "
                + "of it.");
        }

        object ring = Read(new[] { 0, 1, 2, 3, 5, 6, 7, 8 });
        bool[] ringCloses = Member<bool[]>(ring, "AnchorCloses");
        IList ringIds = Member<IList>(ring, "AnchorNodeIds");
        if (ringIds.Count != 1 || ringCloses.Length != 1 || !ringCloses[0])
        {
            throw new InvalidOperationException(
                "The eight boundary nodes of the grid form ONE anchor strip "
                + "that comes back round to where it started, so it is one "
                + "branch and it CLOSES; got " + ringIds.Count + " strips and "
                + "closes [" + string.Join(",", ringCloses) + "]. A vault "
                + "anchored right around its springing is this case, and a "
                + "polyline one segment short of closing would be drawn there "
                + "with nothing said.");
        }
        int[] walk = ((IEnumerable)ringIds[0]!).Cast<int>().ToArray();
        if (walk.Length != 8)
        {
            throw new InvalidOperationException(
                "Every anchored node stays in its strip: eight went in and "
                + $"{walk.Length} came back.");
        }

        // Rule 10.3(c) lists FOUR things as measured off Read, and the flag
        // count and the AnchorCloses flag are only two of them. The other two
        // are asserted here, because an earlier draft named all four and
        // built two, and the two it left out are the two an implementer would
        // otherwise assume.

        // THE BRANCH COUNT EQUALS ANCHOR NODES' BRANCH COUNT, asserted
        // directly and not inferred from the flag count. AnchorGroups carries
        // the points and AnchorNodeIds the ids, and the port emits one branch
        // per strip from the first while Anchor Nodes emits one from the
        // second, so a reader that dropped a strip from one and not the other
        // would put a line on the wrong branch with nothing said.
        IList openIds = Member<IList>(open, "AnchorNodeIds");
        if (openGroups.Count != openIds.Count)
        {
            throw new InvalidOperationException(
                "There is ONE anchor strip branch per strip in both lists: "
                + $"AnchorGroups holds {openGroups.Count} and AnchorNodeIds "
                + $"holds {openIds.Count}. Anchor Lines is branched exactly "
                + "as Anchor Nodes, so the two counts are the same count.");
        }

        // A STRIP OF ONE NODE AND A STRIP OF NONE EACH KEEP THEIR BRANCH.
        // The open fixture happens to contain a strip of one, node 8, and an
        // earlier draft asserted nothing about it at all. The strip of NONE
        // is produced deliberately, by naming an anchor the net has no vertex
        // for: it is the empty branch rule 5.4's guard exists for, and a
        // reader that silently dropped it would shift every branch after it.
        int[][] openWalks = openIds.Cast<object>()
            .Select(strip => ((IEnumerable)strip).Cast<int>().ToArray())
            .ToArray();
        if (!openWalks.Any(strip => strip.Length == 1 && strip[0] == 8))
        {
            throw new InvalidOperationException(
                "Anchoring 0, 1, 2 and 8 gives one strip of three and one "
                + "strip of ONE, and the strip of one KEEPS ITS BRANCH: it is "
                + "a support the author placed and it gets a line of its own "
                + "however short. The strips came back as "
                + $"[{string.Join(" | ", openWalks.Select(s => string.Join(",", s)))}].");
        }
        object orphan = Read(new[] { 0, 1, 2, 8, 9 });
        IList orphanIds = Member<IList>(orphan, "AnchorNodeIds");
        IList orphanGroups = Member<IList>(orphan, "AnchorGroups");
        if (orphanIds.Count != openIds.Count + 1 ||
            orphanGroups.Count != orphanIds.Count)
        {
            throw new InvalidOperationException(
                "An anchor the net has no vertex for is a strip of NO nodes, "
                + "and it KEEPS ITS BRANCH in both lists so that every strip "
                + "after it stays on its own branch; the two lists came back "
                + $"as {orphanGroups.Count} and {orphanIds.Count} against the "
                + $"{openIds.Count + 1} expected.");
        }

        // EACH STRIP'S NODE ORDER IS END TO END, which here means that
        // consecutive ids in the walk are ADJACENT in the grouping graph. A
        // strip whose ids came back in ascending order rather than in walked
        // order would pass every count above and draw a polyline that zigzags
        // across the springing.
        var adjacency = new Dictionary<int, HashSet<int>>();
        foreach ((int u, int v) in pairs)
        {
            (adjacency.TryGetValue(u, out HashSet<int>? atU)
                ? atU
                : adjacency[u] = new HashSet<int>()).Add(v);
            (adjacency.TryGetValue(v, out HashSet<int>? atV)
                ? atV
                : adjacency[v] = new HashSet<int>()).Add(u);
        }
        foreach (int[] strip in openWalks.Concat(new[] { walk }))
        {
            for (int at = 1; at < strip.Length; at++)
            {
                if (!adjacency.TryGetValue(strip[at - 1], out HashSet<int>? near) ||
                    !near.Contains(strip[at]))
                {
                    throw new InvalidOperationException(
                        "A strip's nodes come back in WALKED order, end to "
                        + "end, so consecutive ids are adjacent in the "
                        + $"grouping graph; {strip[at - 1]} and {strip[at]} "
                        + "are not, and a polyline through them would jump "
                        + "across the net rather than run along the "
                        + "springing.");
                }
            }
        }
        // And the ring closes onto its own start, which is the same rule at
        // the wrap and is what AnchorCloses is claiming.
        if (!adjacency[walk[^1]].Contains(walk[0]))
        {
            throw new InvalidOperationException(
                "AnchorCloses is true only where the LAST node walked is "
                + "adjacent to the FIRST in the grouping graph; here it is "
                + "not, so the flag is claiming a closing segment that would "
                + "be a chord across the net.");
        }
    }
```

Replace the PASS text at `Program.cs:1343-1348` with:

```csharp
            Console.WriteLine(
                "PASS  Anchor Lines: one flag per strip, an open run of three "
                + "and a strip of one both reported as not closing, and the "
                + "boundary ring reported as ONE strip that closes, so a vault "
                + "anchored right around its springing is not drawn one "
                + "segment short.");
```

and the failure label at `:1352-1353` with:

```csharp
            failures.Add(
                $"Anchor Lines: {DescribeException(exception)}");
```

Run the gate. It must fail with `FrameGeometry.Net has no AnchorCloses`.

- [ ] **Step 2: Compute the flag in Read**

Add `bool[] AnchorCloses,` to the `Net` record immediately after `List<List<int>> AnchorNodeIds,`, so it reads:

```csharp
        public sealed record Net(
            Point3d[] Positions,
            List<List<Line>> Cables,
            List<List<Point3d>> PrincipalNodes,
            List<List<Point3d>> AnchorGroups,
            List<List<int>> AnchorNodeIds,
            bool[] AnchorCloses,
            List<List<Point3d>> PerimeterLoops,
            bool[] PerimeterCloses,
            bool PerimeterEstimated,
            int PerimeterCount,
            List<List<Line>> ColumnBranches,
            string Phase);
```

In `Read`, immediately after the perimeter `closes` loop that ends at `MouldComponents.cs:2593`, add:

```csharp
            // CLOSED ONLY WHEN IT CLOSES, on the same test the perimeter
            // uses, less the estimated term: the anchors are NAMED by the
            // Result and are never a heuristic, where a boundary sometimes
            // is. A vault anchored right around its springing gives a strip
            // with no end at all, which ConnectedGroups walks from its
            // lowest node and brings back round, so the closing segment is a
            // real member of the grouping graph and has to be drawn.
            var anchorCloses = new bool[anchorStrips.Count];
            for (int strip = 0; strip < anchorStrips.Count; strip++)
            {
                List<int> walk = anchorStrips[strip];
                anchorCloses[strip] =
                    walk.Count >= 3 &&
                    grouping[walk[walk.Count - 1]].Contains(walk[0]);
            }
```

and add `anchorCloses,` to the return, immediately after `anchorStrips,`.

- [ ] **Step 3: Build the polyline branch and carry it on Set**

Add two members to the `Set` record, after `List<List<int>> AnchorNodeIds,`:

```csharp
            List<List<Curve>> AnchorLines,
            bool[] AnchorCloses,
```

In `Build`, immediately after the `perimeterLines` loop that ends at `MouldComponents.cs:2658`, add:

```csharp
            // ONE curve per strip, through every node of it. Built here
            // beside Perimeter Lines and not in a helper, because
            // Polyline.ToNurbsCurve needs the native core. Two differences
            // from the perimeter shape: there is no estimated flag, the
            // anchors being named by the Result rather than guessed at, and
            // the closing point follows AnchorCloses exactly as the
            // perimeter's follows PerimeterCloses. An empty branch is kept
            // where the polyline will not build, so branch {i} of Anchor
            // Lines stays branch {i} of Anchor Nodes.
            var anchorLines = new List<List<Curve>>();
            for (int strip = 0; strip < net.AnchorGroups.Count; strip++)
            {
                var branch = new List<Curve>();
                List<Point3d> walk = net.AnchorGroups[strip];
                if (walk.Count >= 2)
                {
                    var points = new List<Point3d>(walk);
                    if (net.AnchorCloses[strip])
                        points.Add(points[0]);
                    var polyline = new Polyline(points);
                    if (polyline.IsValid && polyline.Count > 1)
                        branch.Add(polyline.ToNurbsCurve());
                }
                anchorLines.Add(branch);
            }
```

and in `Build`'s return, after `net.AnchorNodeIds,`, add:

```csharp
                anchorLines,
                net.AnchorCloses,
```

Then DELETE the standalone helper `FrameGeometry.AnchorLines` and its doc comment, `MouldComponents.cs:2674-2695` in full. It has exactly one caller in the plugin, and Step 5 rewrites it.

- [ ] **Step 4: Retype and rewrite the port**

Replace `plugin/native_v02/Components/FrameComponents.cs:156-169`, the appended-comment and the registration together, with:

```csharp
            parameters.AddCurveParameter(
                "Anchor Lines",
                "AL",
                "The anchor strips joined up: ONE curve per strip, a "
                    + "polyline through every node of it, as a TREE branched "
                    + "EXACTLY as Anchor Nodes, one branch per CONNECTED "
                    + "STRIP, closed where the strip comes back round to its "
                    + "own first node and open where it does not. A strip of "
                    + "a single node, or none, keeps an EMPTY branch, which "
                    + "is what keeps branch {i} here branch {i} there. AT "
                    + "THIS FRAME: on a Result from Animate these are drawn "
                    + "through the anchors where the frame has them, not "
                    + "where the solved vault has them, and the two agree "
                    + "only at rest and at finish. The solved positions are "
                    + "on the Result's own vertex list.",
                GH_ParamAccess.tree);
```

and replace the emit at `FrameComponents.cs:202-203` with:

```csharp
                data.SetDataTree(9, OutputTree.Curves(set.AnchorLines));
```

- [ ] **Step 5: Run the gate**

Green. The new check passes, the build has no warnings, and `ValidateFrameGeometry` is untouched by the change.

- [ ] **Step 4A: THE CHORD ALTERNATIVE, only if Param answers 12B(a) with rule 5.2(a)**

If he takes the Line he literally asked for, do this INSTEAD of Steps 2, 3 and 4. `AnchorCloses` is not needed, the `Net` and `Set` records keep the shape Task 34 left them in, `Build` gains nothing, and the Rhino-free helper stays where it is with a two-line change to its body. Replace the body of `FrameGeometry.AnchorLines` at `MouldComponents.cs:2683-2695` with:

```csharp
        public static List<List<Line>> AnchorLines(
            List<List<Point3d>> groups)
        {
            var lines = new List<List<Line>>();
            foreach (List<Point3d> strip in groups)
            {
                var branch = new List<Line>();
                if (strip.Count >= 2)
                    branch.Add(new Line(strip[0], strip[strip.Count - 1]));
                lines.Add(branch);
            }
            return lines;
        }
```

and rewrite its doc comment at `:2674-2682` to:

```csharp
        /// <summary>
        /// The anchor strips joined up: ONE Line per strip, running from its
        /// FIRST node to its LAST, so two strips give two lines rather than
        /// twenty. A strip of a single node, or none, keeps an EMPTY branch,
        /// which is what keeps the branch counts aligned with AnchorGroups.
        /// Rule 5.7 is what makes the chord a real chord: ConnectedGroups
        /// walks an open strip from one of its ends, so first and last are
        /// the two ends of the run and not a random pair. Pure over the
        /// groups, so it follows the frame positions exactly as AnchorGroups
        /// does and the harness can drive it without a Rhino: Line is a
        /// managed struct.
        /// </summary>
```

`FrameComponents.cs:159-169` keeps `AddLineParameter` and only its description changes, to the same text as Step 4 with "ONE curve per strip, a polyline through every node of it" replaced by "ONE straight line per strip, from its first node to its last" and the closed/open clause dropped. `FrameComponents.cs:202-203` keeps `OutputTree.Lines(FrameGeometry.AnchorLines(set.AnchorGroups))`.

- [ ] **Step 4B: THE CHORD'S CHECK, only under 5.2(a)**

Do this INSTEAD of Step 1's rewrite. `ValidateFrameAnchorLines` at `Program.cs:5109-5177` keeps its reflection over the helper and only its expected counts change. Replace the three assertions at `:5148-5176` with:

```csharp
        if (branches.Length != 3)
        {
            throw new InvalidOperationException(
                "Three strips give three branches, empties kept, so AL and AN "
                + $"stay branch for branch; got {branches.Length}.");
        }
        if (branches[0].Length != 1 || branches[1].Length != 0 ||
            branches[2].Length != 0)
        {
            throw new InvalidOperationException(
                "A strip of any length is ONE chord and a strip of one, or "
                + "none, is an EMPTY branch; got lengths "
                + $"{branches[0].Length}, {branches[1].Length}, "
                + $"{branches[2].Length}.");
        }
        double At(object line, string end, string axis)
        {
            object point = line.GetType().GetProperty(end)!.GetValue(line)!;
            return (double)point.GetType().GetProperty(axis)!.GetValue(point)!;
        }
        if (Math.Abs(At(branches[0][0], "From", "X")) > 1.0e-9 ||
            Math.Abs(At(branches[0][0], "To", "X") - 1.0) > 1.0e-9 ||
            Math.Abs(At(branches[0][0], "To", "Y") - 1.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "The chord runs the strip's FIRST node to its LAST: (0,0,0) "
                + "to (1,1,0), not node to node along it.");
        }
```

and change the doc comment's first sentence at `:5110-5114` to "a strip of three nodes gives ONE line from its first node to its last; a single-node strip keeps an EMPTY branch; and the branch count equals the strips'." Under the chord, rule 10.3(c)'s unmeasurable half never opens, because nothing moves into `Build`.

- [ ] **Step 6: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/MouldComponents.cs" "plugin/native_v02/Components/FrameComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(frame): Anchor Lines is one line per strip"
```

---

### Task 36: Reaction Vectors rebranched onto the anchor strips, and the stray reaction reported

Spec rules 3.5, 4.3 and 4.5, measured by rules 10.3(d) and 10.3(e). The branching lives inline inside `DeconstructComponent.SolveInstance` at `VisualiseComponents.cs:617-664` today, and the harness never calls `SolveInstance` on anything (`Program.cs:12741-12748`), so inline is unmeasurable. This task hoists it into an internal static beside `ColumnTrees` and `ForceLines`, which the harness already drives by reflection at `Program.cs:2897` and `:3147`, and adds the stray detection to the same static so both halves of rule 4.3 can be asserted without a document.

The static is written here and CALLED in Task 38. The shipped ten-port Deconstruct is not rewired in this task: its Reaction Points port still exists until the merge, and rule 4.3's "no extra branch" cannot be true while a port whose whole purpose is to carry that branch is registered.

**Files:**
- Modify: `plugin/native_v02/Components/VisualiseComponents.cs` (a new internal static after `ColumnTrees`, which ends at :858)
- Modify: `tests/native_smoke/Program.cs` (a new `ValidateDeconstructReactionBranches` plus its PASS block beside the `ValidateDeconstructColumnTrees` block at :1088-1099)
- Test: `ValidateDeconstructReactionBranches`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `internal static (List<List<Vector3d>> Branches, List<int> Strays) DeconstructComponent.ReactionBranches(List<List<int>> strips, (int Node, Vector3d Vector)[] reactions)`. Task 38's `StaticsHalf` calls it with `set.AnchorNodeIds` and `ResultTables.Reactions(result)` filtered to range.

- [ ] **Step 1: Write the check first, and watch it fail**

Add to `tests/native_smoke/Program.cs`, immediately after `ValidateDeconstructColumnTrees` ends at :2947:

```csharp
    /// <summary>
    /// <c>DeconstructComponent.ReactionBranches</c>: the reactions laid out
    /// ON the anchor strips, and the reactions that sit on no strip at all.
    ///
    /// Three properties, and the third is the one the whole of spec section
    /// 4 turns on. First, branch for branch and item for item against the
    /// strips, so strip {i} item [k] is the same support in Anchor Nodes and
    /// here. Second, a support carrying NO reaction holds its slot as a ZERO
    /// VECTOR rather than dropping out, which is the property that makes the
    /// first one true. Third, a reaction at a node on no strip produces NO
    /// extra branch and IS returned in the stray list: a check that measured
    /// only the branch count would pass on the silent deletion this rule
    /// exists to stop, and the shipped code's own comment says why losing it
    /// silently would be worse than an extra branch nobody expected.
    ///
    /// The Warning SolveInstance builds from the stray list is READ rather
    /// than run, which is this harness's own convention for component wiring
    /// (see the note beside ValidateExportCoursesValidation): it never calls
    /// SolveInstance on anything.
    /// </summary>
    private static void ValidateDeconstructReactionBranches(Assembly plugin)
    {
        Type deconstruct = RequireComponentType(plugin, "DeconstructComponent");
        MethodInfo branches = RequireStatic(deconstruct, "ReactionBranches");
        Type stripsType = branches.GetParameters()[0].ParameterType;
        Type stripType = stripsType.GetGenericArguments()[0];
        Type reactionArray = branches.GetParameters()[1].ParameterType;
        Type reactionType = reactionArray.GetElementType()!;
        Type vector3d = reactionType.GetGenericArguments()[1];

        object Strips(params int[][] made)
        {
            object all = Activator.CreateInstance(stripsType)!;
            MethodInfo addStrip = stripsType.GetMethod("Add")!;
            MethodInfo addId = stripType.GetMethod("Add")!;
            foreach (int[] one in made)
            {
                object strip = Activator.CreateInstance(stripType)!;
                foreach (int id in one)
                    addId.Invoke(strip, new object[] { id });
                addStrip.Invoke(all, new[] { strip });
            }
            return all;
        }
        object Reactions(params (int Node, double Z)[] made)
        {
            Array array = Array.CreateInstance(reactionType, made.Length);
            for (int i = 0; i < made.Length; i++)
            {
                object vector = Activator.CreateInstance(
                    vector3d, 0.0, 0.0, made[i].Z)!;
                array.SetValue(
                    Activator.CreateInstance(
                        reactionType, made[i].Node, vector),
                    i);
            }
            return array;
        }
        (int[][] Counts, int[] Strays, double[][] Z) Ask(
            object strips, object reactions)
        {
            object answer = branches.Invoke(null, new[] { strips, reactions })!;
            Type tuple = answer.GetType();
            object[][] made = ((IEnumerable)tuple.GetField("Item1")!
                    .GetValue(answer)!)
                .Cast<IEnumerable>()
                .Select(branch => branch.Cast<object>().ToArray())
                .ToArray();
            int[] strays = ((IEnumerable)tuple.GetField("Item2")!
                    .GetValue(answer)!)
                .Cast<int>()
                .ToArray();
            return (
                made.Select(branch => branch.Select(_ => 0).ToArray()).ToArray(),
                strays,
                made
                    .Select(branch => branch
                        .Select(item => (double)vector3d
                            .GetProperty("Z")!.GetValue(item)!)
                        .ToArray())
                    .ToArray());
        }

        // Every support carries a reaction.
        var full = Ask(
            Strips(new[] { 0, 1, 2 }, new[] { 8 }),
            Reactions((0, 1.0), (1, 2.0), (2, 3.0), (8, 4.0)));
        if (full.Counts.Length != 2 ||
            full.Counts[0].Length != 3 || full.Counts[1].Length != 1)
        {
            throw new InvalidOperationException(
                "Two strips of three and one give two branches of three and "
                + "one, so Reaction Vectors reads against Anchor Nodes branch "
                + "for branch; got "
                + string.Join("/", full.Counts.Select(b => b.Length)) + ".");
        }
        if (full.Strays.Length != 0)
        {
            throw new InvalidOperationException(
                "Every reaction here sits on a strip, so nothing is stray; got "
                + $"[{string.Join(",", full.Strays)}].");
        }

        // A support carrying none holds its slot as a ZERO.
        var gap = Ask(
            Strips(new[] { 0, 1, 2 }, new[] { 8 }),
            Reactions((0, 1.0), (2, 3.0), (8, 4.0)));
        if (gap.Counts[0].Length != 3 || gap.Counts[1].Length != 1)
        {
            throw new InvalidOperationException(
                "A support carrying no reaction keeps its SLOT: three in the "
                + "first branch whatever the reactions table says; got "
                + string.Join("/", gap.Counts.Select(b => b.Length)) + ".");
        }
        if (Math.Abs(gap.Z[0][1]) > 1.0e-12)
        {
            throw new InvalidOperationException(
                "Node 1 carries no reaction, so its slot is the ZERO VECTOR "
                + $"rather than the next support's reading; got {gap.Z[0][1]}. "
                + "Dropping it is what made the old flat list unreadable "
                + "against the supports.");
        }

        // A reaction on no strip: no extra branch, and it is REPORTED.
        var stray = Ask(
            Strips(new[] { 0, 1, 2 }, new[] { 8 }),
            Reactions((0, 1.0), (5, 9.0)));
        if (stray.Counts.Length != 2)
        {
            throw new InvalidOperationException(
                "A stray reaction gets NO branch of its own: two strips still "
                + $"give two branches; got {stray.Counts.Length}. The extra "
                + "branch had nowhere to go once Reaction Points went and "
                + "Reaction Vectors was rebranched onto the anchor strips.");
        }
        if (!stray.Strays.SequenceEqual(new[] { 5 }))
        {
            throw new InvalidOperationException(
                "The stray is RETURNED so the component can raise a Warning "
                + "naming the node it sits on; expected [5], got ["
                + string.Join(",", stray.Strays) + "]. Deleting it quietly is "
                + "exactly the failure the original comment was written "
                + "against.");
        }
    }
```

Register it after the `ValidateDeconstructColumnTrees` try/catch that ends at `Program.cs:1099`:

```csharp
        try
        {
            ValidateDeconstructReactionBranches(plugin);
            Console.WriteLine(
                "PASS  Deconstruct reaction branches: the reactions come back "
                + "branch for branch and item for item against the anchor "
                + "strips, a support carrying none holding its slot as a zero "
                + "vector, and a reaction at a node on no strip producing NO "
                + "extra branch while being returned as a stray for the "
                + "Warning to name.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Deconstruct reaction branches: {DescribeException(exception)}");
        }
```

Run the gate. It must fail with `DeconstructComponent.ReactionBranches was not found.`

- [ ] **Step 2: Write the static**

Add to `plugin/native_v02/Components/VisualiseComponents.cs` immediately after `ColumnTrees` ends at :858:

```csharp
        /// <summary>
        /// The reactions laid out ON THE ANCHOR STRIPS, and the reactions
        /// that sit on no strip at all.
        ///
        /// Branched AND ordered exactly as Anchor Nodes, item for item, so
        /// strip {i} item [k] is the same support in both. That alignment
        /// costs something and it is worth stating: a support carrying no
        /// reaction is a ZERO VECTOR holding its own slot rather than being
        /// dropped. Dropping it is what made the old flat list unreadable
        /// against the supports, because nothing said which support a given
        /// reaction belonged to short of matching coordinates by eye.
        ///
        /// A reaction at a node that is on no strip should not exist. If one
        /// does it gets NO branch of its own, because with Reaction Points
        /// gone and Reaction Vectors rebranched onto the anchor strips there
        /// is nowhere for an extra branch to go; it is returned instead, so
        /// the component can raise a Warning naming how many strays there
        /// are and which nodes they sit on. Losing it silently would be
        /// worse than an extra branch nobody expected, which is what the
        /// branch was there to prevent, and the Warning is what replaces it.
        ///
        /// A static rather than a block inside SolveInstance, because the
        /// smoke harness never calls SolveInstance on anything and a rule
        /// that cannot be driven is a rule nothing measures.
        /// </summary>
        internal static (List<List<Vector3d>> Branches, List<int> Strays)
            ReactionBranches(
                List<List<int>> strips,
                (int Node, Vector3d Vector)[] reactions)
        {
            var reactionAt = new Dictionary<int, Vector3d>();
            foreach ((int node, Vector3d vector) in reactions)
                reactionAt[node] = vector;

            var branches = new List<List<Vector3d>>();
            foreach (List<int> strip in strips)
            {
                var vectors = new List<Vector3d>();
                foreach (int id in strip)
                {
                    vectors.Add(
                        reactionAt.TryGetValue(id, out Vector3d found)
                            ? found
                            : Vector3d.Zero);
                }
                branches.Add(vectors);
            }

            var onAStrip = new HashSet<int>(strips.SelectMany(strip => strip));
            var strays = new List<int>();
            foreach ((int node, Vector3d _) in reactions)
            {
                if (!onAStrip.Contains(node))
                    strays.Add(node);
            }
            return (branches, strays);
        }
```

- [ ] **Step 3: Run the gate**

Green, with the new PASS line. The shipped `SolveInstance` is untouched, so nothing on the canvas changes yet.

- [ ] **Step 4: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/VisualiseComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(deconstruct): reaction branches and the stray reaction as a driveable static"
```

---

### Task 37: The two support lists compared as sets

Spec rules 3.6 and 3.7, measured by rule 10.3(f). The merged reader keeps `FrameGeometry`'s seed, `equilibrium.ResolvedSupportNodeIds` (`MouldComponents.cs:2526-2528`), while SUPPORTS builds its anchor strips from `ResultTables.SupportNodes`, which is `Mappings.Supports` for TNA (`SupportsReaderComponent.cs:278-282`). For a TNA Result built by the shipped codec the two hold the same set, because `ResolvedSupportNodeIds` is derived from `Mappings.Supports` at `TnaWorkerResultCodec.cs:161-165`. Nothing in the contract enforces that for a Result deserialised from JSON: `ResultDto.Validate` cross-checks the two only when `solver == "fd"` (`ContractDtos.cs:830-865`, the explicit cross-check at :850-864). So where they diverge, Supports' trees stop pairing with the merged reader's, and this warning is what announces it.

Supports is NOT re-seeded in this round, by the spec's own narrow ruling.

**Files:**
- Modify: `plugin/native_v02/Components/VisualiseComponents.cs` (a new internal static after `ReactionBranches` from Task 36)
- Modify: `tests/native_smoke/Program.cs` (a new `ValidateDeconstructSeedDivergence` plus its PASS block after Task 36's block)
- Test: `ValidateDeconstructSeedDivergence`

**Interfaces:**
- Consumes: `ResultTables.SupportNodes(ResultDto)` returning `int[]`, unchanged at `VisualiseComponents.cs:196-206`.
- Produces: `internal static string? DeconstructComponent.SeedDivergence(int[] tableSupports, int[] resolvedSupports)`, returning null when the two agree as sets. Task 38's `SolveInstance` raises what it returns and does nothing else with it.

- [ ] **Step 1: Write the check first, and watch it fail**

Add to `tests/native_smoke/Program.cs` immediately after `ValidateDeconstructReactionBranches`:

```csharp
    /// <summary>
    /// <c>DeconstructComponent.SeedDivergence</c>: the two support lists
    /// this plugin has in play, compared as SETS.
    ///
    /// The merged reader's anchors come off equilibrium's
    /// ResolvedSupportNodeIds, because that is what FrameGeometry.Read seeds
    /// from and Animate's viewport draws from the same call. SUPPORTS builds
    /// its anchor strips off ResultTables.SupportNodes, which for TNA is
    /// Mappings.Supports. The shipped codec derives one from the other, so
    /// they agree on every Result this plugin makes; nothing in the contract
    /// enforces it for a Result deserialised from JSON, and where they
    /// diverge two trees an author reads against each other stop pairing
    /// branch for branch with nothing said. This is what says it.
    ///
    /// The fixture is the TNA Result ValidateResultTablesOrder already
    /// builds: three vertices, supports naming 0, 7 and 2, with 7 not a
    /// vertex of this net and dropped by the table. Against a resolved list
    /// of 0, 1 and 2 the two disagree by node 1 alone, which is the case
    /// worth naming: no exception, no dropped port, just two trees that no
    /// longer line up.
    /// </summary>
    private static void ValidateDeconstructSeedDivergence(Assembly plugin)
    {
        Type deconstruct = RequireComponentType(plugin, "DeconstructComponent");
        MethodInfo divergence = RequireStatic(deconstruct, "SeedDivergence");
        Type tables = RequireComponentType(plugin, "ResultTables");
        MethodInfo supportNodes = RequirePublicStatic(tables, "SupportNodes");
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType = RequireContractType(plugin, "EquilibriumResultDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edgeType = RequireContractType(plugin, "EdgeDto");
        Type graphType = RequireContractType(plugin, "TnaDiagramGraphDto");
        Type mappingsType = RequireContractType(plugin, "TnaMappingsDto");
        Type supportType = RequireContractType(plugin, "TnaSupportMappingDto");

        object P(double x, double y, double z) =>
            Activator.CreateInstance(point, x, y, z)!;
        Array Of(Type type, params object[] items)
        {
            Array array = Array.CreateInstance(type, items.Length);
            for (int i = 0; i < items.Length; i++)
                array.SetValue(items[i], i);
            return array;
        }
        object At(int vertex)
        {
            object item = CreateInstance(supportType);
            SetContractProperty(item, supportType, "EquilibriumVertexId", vertex);
            SetContractProperty(item, supportType, "Reaction", P(0, 0, 0));
            return item;
        }

        object equilibrium = CreateInstance(equilibriumType);
        SetContractProperty(equilibrium, equilibriumType, "Vertices",
            Of(point, P(0, 0, 0), P(1, 0, 0), P(2, 0, 0)));
        SetContractProperty(equilibrium, equilibriumType, "Edges",
            Of(edgeType,
                Activator.CreateInstance(edgeType, 0, 1)!,
                Activator.CreateInstance(edgeType, 1, 2)!));
        SetContractProperty(
            equilibrium, equilibriumType, "ResolvedSupportNodeIds",
            new[] { 0, 1, 2 });
        object mappings = CreateInstance(mappingsType);
        SetContractProperty(mappings, mappingsType, "Supports",
            Of(supportType, At(0), At(7), At(2)));
        object tna = CreateResultDto(
            resultType,
            "tna",
            equilibrium,
            CreateInstance(graphType),
            CreateInstance(graphType));
        SetContractProperty(tna, resultType, "Mappings", mappings);

        int[] table = ((IEnumerable)supportNodes.Invoke(null, new[] { tna })!)
            .Cast<int>()
            .ToArray();
        if (!table.SequenceEqual(new[] { 0, 2 }))
        {
            throw new InvalidOperationException(
                "The fixture's mappings name 0, 7 and 2 and the table drops "
                + "the vertex this net does not have, so the two lists are "
                + $"[0,2] against [0,1,2]; got [{string.Join(",", table)}].");
        }

        object? said = divergence.Invoke(
            null, new object?[] { table, new[] { 0, 1, 2 } });
        if (said is not string text)
        {
            throw new InvalidOperationException(
                "Two support lists that disagree must produce a warning "
                + "string; got null, which is what the AGREEING case says.");
        }
        if (!text.Contains("2", StringComparison.Ordinal) ||
            !text.Contains("3", StringComparison.Ordinal) ||
            !text.Contains("1", StringComparison.Ordinal) ||
            !text.Contains("Supports", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "The warning names the count on EACH side, the node ids in "
                + "the difference, and SUPPORTS as the component whose trees "
                + "stop pairing, because an author reading two misaligned "
                + $"trees needs to know which pair went wrong; got '{text}'.");
        }

        object? agreed = divergence.Invoke(
            null, new object?[] { new[] { 0, 2 }, new[] { 2, 0 } });
        if (agreed is not null)
        {
            throw new InvalidOperationException(
                "The comparison is by SET, not by order: [0,2] and [2,0] are "
                + $"the same supports and must say nothing; got '{agreed}'.");
        }
    }
```

Register it after Task 36's PASS block:

```csharp
        try
        {
            ValidateDeconstructSeedDivergence(plugin);
            Console.WriteLine(
                "PASS  Deconstruct seed divergence: two support lists that "
                + "disagree produce a warning naming both counts, the node "
                + "ids in the difference and Supports as the component whose "
                + "trees stop pairing; two that agree as SETS, whatever their "
                + "order, produce nothing.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Deconstruct seed divergence: {DescribeException(exception)}");
        }
```

Run the gate. It must fail with `DeconstructComponent.SeedDivergence was not found.`

- [ ] **Step 2: Write the static**

Add to `plugin/native_v02/Components/VisualiseComponents.cs` immediately after `ReactionBranches`:

```csharp
        /// <summary>
        /// The two support lists in play, compared as SETS: null when they
        /// agree, and the sentence to raise as a Warning when they do not.
        ///
        /// This component's anchors come off equilibrium's
        /// ResolvedSupportNodeIds, because FrameGeometry.Read seeds from
        /// that and Animate's viewport draws from the same call, so changing
        /// the seed would change the drawing of the machine as a side effect
        /// of a reader merge. SUPPORTS seeds from ResultTables.SupportNodes,
        /// which for TNA is Mappings.Supports. The shipped codec derives one
        /// from the other, so they agree on every Result this plugin makes;
        /// a Result deserialised straight from JSON carries no such promise,
        /// and where they diverge Supports' Anchor Along, Anchor Across and
        /// Tip Reaction trees stop pairing branch for branch with Anchor
        /// Nodes here. Both lists are computed in the same solve anyway, so
        /// this costs one set comparison and turns a hope into a mechanism.
        ///
        /// A static rather than a block inside SolveInstance for the reason
        /// ReactionBranches is one: a Warning raised inside SolveInstance is
        /// unreachable from a harness that never calls it.
        /// </summary>
        internal static string? SeedDivergence(
            int[] tableSupports,
            int[] resolvedSupports)
        {
            var table = new HashSet<int>(tableSupports);
            var resolved = new HashSet<int>(resolvedSupports);
            if (table.SetEquals(resolved))
                return null;

            int[] onlyTable = table.Except(resolved).OrderBy(id => id).ToArray();
            int[] onlyResolved = resolved.Except(table).OrderBy(id => id).ToArray();
            var difference = new List<string>();
            if (onlyTable.Length > 0)
            {
                difference.Add(
                    "named by the support mappings but not resolved: " +
                    string.Join(", ", onlyTable));
            }
            if (onlyResolved.Length > 0)
            {
                difference.Add(
                    "resolved but not named by the support mappings: " +
                    string.Join(", ", onlyResolved));
            }
            return
                "This Result's two support lists disagree: " +
                $"{table.Count} named by the mappings against " +
                $"{resolved.Count} resolved (" +
                string.Join("; ", difference) +
                "). Anchor Nodes and Reaction Vectors here are built on the " +
                "RESOLVED list, and SUPPORTS builds its anchor strips on the " +
                "mappings, so Supports' Anchor Along, Anchor Across and Tip " +
                "Reaction trees no longer pair branch for branch with Anchor " +
                "Nodes.";
        }
```

- [ ] **Step 3: Run the gate**

Green, with the new PASS line.

- [ ] **Step 4: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/VisualiseComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(deconstruct): compare the two support seed lists as sets"
```

---

### Task 38: Deconstruct and Frame become one reader

Spec sections 1, 2, 3 and rules 10.2(a) to 10.2(g). This is the atomic edit of the round: the component count, the icon map, both contract tables and both classes have to move together or the harness is red between them. Param ruled on 2026-09-01 that the merged reader is called DECONSTRUCT and carries FIFTEEN ports with no Result passing through it.

The arithmetic, which is the evidence for fifteen: ten registered on Deconstruct at `VisualiseComponents.cs:343-427` and ten on Frame at `FrameComponents.cs:76-169`, less Member IDs (`:363`), Node IDs (`:369`), Reaction Points (`:396`) and Phase (`FrameComponents.cs:148`) gives sixteen, and deduping Anchor Nodes against Support Points gives fifteen. NINE come from Frame and six from the old Deconstruct, so the surviving name describes the smaller half; he was shown the split and chose the name anyway.

**Files:**
- Modify: `plugin/native_v02/Components/VisualiseComponents.cs:281-680` (the class comment, constructor, GUID, both registrations and `SolveInstance` rewritten; `ThrustMesh`, `ThrustLine`, `ColumnTrees`, `FormLine`, `ForceLines`, `ForceLine`, `MemberLines`, `Point`, `Vector`, `ReactionBranches` and `SeedDivergence` all stay)
- Delete: `plugin/native_v02/Components/FrameComponents.cs` (the file holds `FrameComponent` and nothing else; the csproj has no explicit Compile items, only an `EmbeddedResource` glob at :37-40, so deleting the file is the whole of it)
- Modify: `plugin/native_v02/Components/SupportsReaderComponent.cs:15-21`, `:45`, `:113` (three sentences naming Deconstruct's Reaction Points and Frame's Columns)
- Modify: `plugin/native_v02/Components/FitComponent.cs:121` and `plugin/native_v02/Components/ForcesComponent.cs:198` (two disclaimers against a port that will not exist)
- Modify: `plugin/icons/icon-map.json` (the `frame` entry at :199-204 deleted, 21 entries become 20)
- Delete: `plugin/icons/frame.png`
- Modify: `tests/native_smoke/Program.cs:76-94` (VisualiseContracts Deconstruct entry), `:141-143` (the Supports comment), `:158-177` (the Frame entry, deleted), `:264-273` (SpineComponentContracts Frame entry, rekeyed), `:312` (the NativeIconEntries Frame row, deleted), `:503-514` (the count pin)
- Test: the rewritten `VisualiseContracts` and `SpineComponentContracts` pins, `ValidateIconMap`, the count pin

**Interfaces:**
- Consumes: `FrameGeometry.Build(ResultDto)` returning `FrameGeometry.Set` with `AnchorNodeIds` (Task 34) and `AnchorLines` (Task 35); `DeconstructComponent.ReactionBranches` (Task 36); `DeconstructComponent.SeedDivergence` (Task 37); `ResultTables.Members/SupportNodes/Reactions/IsTna`; `MouldGeometry.PrincipalRuns/MemberRunIndex`; `OutputTree.Lines/Curves/Points/Vectors`; `ComponentCategories.Read` = "04 Read"; `NativeComponentBase.ReportException(string, Exception)`.
- Produces:
  - `public sealed class DeconstructComponent : NativeComponentBase`, Name "Deconstruct", NickName "DE", tab "04 Read", icon key `result_breakdown`, badge `DE`, GUID `7b1c94a5-6e83-4f21-9d5a-2c8b0e6f3a74`.
  - `internal sealed record DeconstructComponent.Statics(List<List<Line>> MemberLines, List<List<Line>> FormLines, List<List<Line>> ForceLines, List<Point3d> LoadPoints, List<Vector3d> LoadVectors, List<List<Vector3d>> ReactionBranches, List<int> Strays, int MemberCount)`
  - `internal static (FrameGeometry.Set? Set, string? Error) DeconstructComponent.FrameHalf(ResultDto result)`
  - `internal static (Statics? Answer, string? Error) DeconstructComponent.StaticsHalf(ResultDto result, List<List<int>> anchorStrips)`
  - Task 39 drives both halves by reflection and asserts the leaf property. Task 47 records both retired GUIDs. `FrameComponent` no longer exists.

**THE GUID.** The merged reader takes `7b1c94a5-6e83-4f21-9d5a-2c8b0e6f3a74`, written once, here. Deconstruct's `68d0b4f2-9a3e-4c17-85d6-f2b8a0c4e961` and Frame's `5d8e2f61-7a4c-4b93-a0e6-c3f19b7d2a58` are retired and never reused. Reusing either buys nothing: Grasshopper reattaches an archived wire to the live port at the same INDEX, so old slot 0 (Member Lines, a Line tree) would land on new slot 0 (Mesh, a Mesh item), and Frame would orphan anyway because only one GUID can be reused.

**A NOTE ON RULE 1.7'S TWO EXAMPLE CHINS.** Rule 1.6A states the rule as "the chin carries the surviving half's reading with the failure named after it" and then illustrates it with `"TNA · 412 members · raise (statics failed)"` and `"TNA · raise (frame failed)"`. The member count is the STATICS half's reading and the phase word is the FRAME half's, so the two illustrations are transposed against the rule sentence they illustrate. Step 4 follows the RULE SENTENCE: a failed statics half leaves the phase, a failed frame half leaves the member count. Both example strings are quoted here so a reviewer can see what was chosen, and the transposition is the spec owner's to confirm.

- [ ] **Step 1: Rewrite the harness pins first, and watch them fail**

Replace `tests/native_smoke/Program.cs:76-94`, the Deconstruct entry, with:

```csharp
                ["Ananke.COMPAS.Native.Components.DeconstructComponent"] = (
                    new[] { "Result" },
                    new[]
                    {
                        // FIFTEEN outputs since Frame and Deconstruct merged:
                        // nine from Frame, slots 0 to 8, and six from the old
                        // Deconstruct below them. Member IDs, Node IDs,
                        // Reaction Points and Phase were retired; Support
                        // Points was absorbed into Anchor Nodes; Anchor Lines
                        // moved up beside the nodes it is drawn through.
                        // Every slot here is an index a downstream branch is
                        // read by, and the name-comparing load warning is
                        // what tells a reopened definition.
                        "Mesh",
                        "Cables",
                        "Principal Lines",
                        "Principal Nodes",
                        "Anchor Nodes",
                        "Anchor Lines",
                        "Perimeter Nodes",
                        "Perimeter Lines",
                        "Columns",
                        "Member Lines",
                        "Form Lines",
                        "Force Lines",
                        "Load Points",
                        "Load Vectors",
                        "Reaction Vectors"
                    }),
```

Replace the Supports comment at `:141-143` with:

```csharp
                // Supports owns the ground half: anchors by strip, columns
                // by tree, aligned with Deconstruct's Anchor Nodes and
                // Deconstruct's Columns, which are now one component.
```

Delete `:158-177` in full, the `// Frame READS one.` comment and the `FrameComponent` entry, leaving the Export entry that follows.

Replace `:264-273`, the SpineComponentContracts Frame entry and its comment, with:

```csharp
                // Deconstruct is pinned nickname by nickname because it is
                // the one component whose whole job is the ORDER of its
                // ports: fifteen trees read by index downstream. Note what
                // changed beyond the additions: PH went with Phase, AL moved
                // up to index 5 beside the nodes it is drawn through, and M
                // now means Mesh alone, Member Lines having become ML so the
                // two do not collide.
                ["Ananke.COMPAS.Native.Components.DeconstructComponent"] = (
                    "Deconstruct",
                    "DE",
                    "04 Read",
                    new[] { "RES" },
                    new[]
                    {
                        "M", "C", "PL", "PN", "AN", "AL", "PRN", "PRL", "CO",
                        "ML", "FL", "FCL", "LP", "LV", "RV"
                    }),
```

Delete the `NativeIconEntries` Frame row at `:312`.

Replace the count pin at `:503-514` with:

```csharp
        if (componentTypes.Length != 20)
        {
            // Spec 6 pins three counts and only two were enforced. A
            // component quietly dropped from the assembly, by a failed
            // registration or a merge, would have left the whole suite green
            // with nineteen components' worth of contract untested. 20 is
            // the readers merge: Frame and Deconstruct became ONE reader in
            // 04 Read, fifteen ports over one Result.
            failures.Add(
                $"Expected 20 concrete public components, found " +
                $"{componentTypes.Length}.");
        }
```

If the columns or the skin part of this wave has moved this number since the spec was written, the edit is that number MINUS ONE rather than 21 minus one; the spec names the count as a dependency shared with those rounds rather than asserting it as final. Both sibling specs list the component count among the things they leave alone, checked 2026-09-01.

Run the gate. It must fail with `Expected 20 concrete public components, found 21` and a Deconstruct output-name mismatch.

- [ ] **Step 2: Rewrite the class comment, constructor, GUID and input**

Replace `plugin/native_v02/Components/VisualiseComponents.cs:281-338`, from the `/// <summary>` above `DeconstructComponent` through the end of `RegisterInputParams`, with:

```csharp
    /// <summary>
    /// Deconstruct: one solved Result taken apart into everything it holds.
    ///
    /// One component replaces two. It takes one Result and hands back
    /// fifteen geometry outputs; it configures nothing, targets nothing and
    /// has no second input, which is the property that made the two
    /// candidates for merging in the first place.
    ///
    /// It reads the unified <see cref="ResultDto"/> in TWO HALVES, under
    /// separate catches, because they fail independently in practice. The
    /// FRAME half is <see cref="FrameGeometry.Build"/>, the same call
    /// Animate's viewport draws from, so what is drawn and what is emitted
    /// cannot drift; it throws on a Result carrying no equilibrium or no
    /// vertices. The STATICS half is <see cref="ResultTables"/>; it throws
    /// on a Result whose edge-state ids and member rows disagree. An author
    /// whose TNA mappings are malformed still gets the mesh, the cables and
    /// the columns, and the mirror case still gets the statics streams.
    ///
    /// Slots 0 to 8 follow the FRAME. Slots 9 to 14 are read at the SOLVED
    /// vertices and do not, because there is no frame-time force answer to
    /// draw them at: a member force computed for the finished vault drawn on
    /// the line the half-reeled frame stands at would be a number attached
    /// to geometry it was not solved on. Each of the six says so in its own
    /// description, because it is not obvious from the port list.
    ///
    /// It is a LEAF. It hands back no Result, so nothing wires downstream of
    /// it, and everything it has to say beyond geometry is said on the
    /// canvas as a runtime message: the stray reaction of
    /// <see cref="ReactionBranches"/> and the seed divergence of
    /// <see cref="SeedDivergence"/> are read either off its own balloon or
    /// out of Diagnose's document scan. A sixteenth port carrying the Result
    /// through with diagnostics appended was put to Param on 2026-09-01 and
    /// declined.
    ///
    /// Its member, support and reaction order comes from
    /// <see cref="ResultTables"/>, which is the same table Forces reads, so
    /// Forces' number trees line up with these geometry trees branch for
    /// branch and item for item without either component matching
    /// coordinates.
    /// </summary>
    public sealed class DeconstructComponent : NativeComponentBase
    {
        public DeconstructComponent()
            : base(
                "Deconstruct",
                "DE",
                "Take one solved FD or TNA Result apart: the formwork " +
                "surface and its cables, the notched bars, the anchors and " +
                "the boundary, the columns, and the statics streams. On a " +
                "Result from Animate the FRAME GEOMETRY, Mesh down to " +
                "Columns, is read at that frame; the STATICS STREAMS below " +
                "it, Member Lines down to Reaction Vectors, are read at the " +
                "solved shape, because there is no frame-time force answer " +
                "to draw them at. A Result from a solver or from Columns is " +
                "read at the solved shape throughout. Forces, Fit and " +
                "Supports carry the numbers and Skin the cells. " +
                "Reciprocal-only streams (Form Lines, Force Lines) come out " +
                "empty for FD. This reader is a LEAF: it hands back no " +
                "Result, so nothing wires downstream of it.",
                ComponentCategories.Read,
                "result_breakdown")
        {
            // Deconstruct is a data boundary, not a renderer: Display owns
            // the viewport and Animate owns the drawing of the machine.
            // Grasshopper's default red preview on these geometry outputs is
            // what clashed with Display's element colours and doubled
            // Animate's shaded preview, so previews start hidden; each
            // output can still be re-enabled from its own context menu.
            foreach (IGH_Param output in Params.Output)
            {
                if (output is IGH_PreviewObject preview)
                    preview.Hidden = true;
            }
        }

        public override Guid ComponentGuid =>
            new("7b1c94a5-6e83-4f21-9d5a-2c8b0e6f3a74");

        protected override void RegisterInputParams(
            GH_InputParamManager parameters)
        {
            parameters.AddParameter(
                new ResultParam(),
                "Result",
                "RES",
                "A solved Result. With a Mould frame on it, from Animate, " +
                "the frame geometry comes back at that frame; without one it " +
                "comes back at the solved shape. The statics streams are " +
                "read at the solved shape either way.",
                GH_ParamAccess.item);
        }
```

- [ ] **Step 3: Write the fifteen registrations**

Replace the whole of `RegisterOutputParams`, `VisualiseComponents.cs:340-427`, with:

```csharp
        protected override void RegisterOutputParams(
            GH_OutputParamManager parameters)
        {
            parameters.AddMeshParameter(
                "Mesh",
                "M",
                "The formwork surface at this frame, rebuilt from the " +
                "Result's own faces. Empty for an FD result, which carries " +
                "no faces to rebuild from.",
                GH_ParamAccess.item);
            parameters.AddLineParameter(
                "Cables",
                "C",
                "Every net member at this frame, infill and bar alike, as a " +
                "TREE: one branch per principal line carrying that bar's " +
                "own members in order along it, and a LAST branch holding " +
                "the infill, everything not on a bar. Branch {i} is bar " +
                "{i}, the same bar as branch {i} of Principal Lines and " +
                "Principal Nodes. This is the net AT THIS FRAME, in the " +
                "Result's own edge order with degenerate and out-of-range " +
                "members dropped. It is NOT item-aligned with Member Lines, " +
                "which is the solved net in the member-table's order; pair " +
                "with Principal Lines and Principal Nodes, not with the " +
                "statics streams.",
                GH_ParamAccess.tree);
            parameters.AddCurveParameter(
                "Principal Lines",
                "PL",
                "The notched bars at this frame, bending as they rise, as a " +
                "TREE with one branch per bar. One curve per branch.",
                GH_ParamAccess.tree);
            parameters.AddPointParameter(
                "Principal Nodes",
                "PN",
                "Every notch: one crossing cable, and a pair of stepper " +
                "motors pulling it, one each side. A TREE with one branch " +
                "per bar, the notches IN ORDER ALONG THAT BAR, so branch " +
                "{i} runs the length of Principal Lines branch {i}. A node " +
                "where two bars cross appears in both branches, because it " +
                "is a notch on both.",
                GH_ParamAccess.tree);
            parameters.AddPointParameter(
                "Anchor Nodes",
                "AN",
                "The Result's supports: the side anchors that stay on the " +
                "ground and take the perimeter cables' prestress. A TREE " +
                "with one branch per CONNECTED STRIP, walked end to end, so " +
                "opposite sides of the vault come back as separate branches " +
                "instead of one merged list. AT THIS FRAME: on a Result " +
                "from Animate these are the anchors where the frame has " +
                "them, not where the solved vault has them, and the two " +
                "agree only at rest and at finish. The solved positions are " +
                "on the Result's own vertex list.",
                GH_ParamAccess.tree);
            parameters.AddCurveParameter(
                "Anchor Lines",
                "AL",
                "The anchor strips joined up: ONE curve per strip, a " +
                "polyline through every node of it, as a TREE branched " +
                "EXACTLY as Anchor Nodes, one branch per CONNECTED STRIP, " +
                "closed where the strip comes back round to its own first " +
                "node and open where it does not. A strip of a single node, " +
                "or none, keeps an EMPTY branch, which is what keeps branch " +
                "{i} here branch {i} there. AT THIS FRAME: on a Result from " +
                "Animate these are drawn through the anchors where the " +
                "frame has them, not where the solved vault has them, and " +
                "the two agree only at rest and at finish. The solved " +
                "positions are on the Result's own vertex list.",
                GH_ParamAccess.tree);
            parameters.AddPointParameter(
                "Perimeter Nodes",
                "PRN",
                "Nodes on the naked boundary of the net, as a TREE with one " +
                "branch per boundary LOOP, walked round. A net with a hole " +
                "in it has a branch for the outside and one for the hole.",
                GH_ParamAccess.tree);
            parameters.AddCurveParameter(
                "Perimeter Lines",
                "PRL",
                "The boundary of the net at this frame as polylines, a TREE " +
                "with one branch per boundary group, the same group as " +
                "branch {i} of Perimeter Nodes: closed when the group is a " +
                "loop, open when it is a strip. Empty, with " +
                "animate.perimeter_estimated on the Result to say why, when " +
                "the boundary could only be estimated from node degree.",
                GH_ParamAccess.tree);
            parameters.AddLineParameter(
                "Columns",
                "CO",
                "The columns at this frame: every tree on its built foot, " +
                "as a TREE with one branch per COLUMN TREE, that is per " +
                "foot, each branch holding that tree's trunk and arms " +
                "together. A member whose ends have met at this frame is " +
                "not drawn, so a branch can come back short. Empty unless " +
                "the Result carries columns from Columns upstream.",
                GH_ParamAccess.tree);
            parameters.AddLineParameter(
                "Member Lines",
                "ML",
                "Resolved spatial member axes, as a TREE: one branch per " +
                "principal line holding that bar's own members, and a LAST " +
                "branch holding the infill, everything not on a bar. Form " +
                "Lines and Force Lines are branched and ordered " +
                "identically, and so are FORCES' number trees for the same " +
                "Result, so the alignment holds branch to branch and item " +
                "to item across both components. A bar with no members of " +
                "its own keeps an empty branch, so branch {i} is always bar " +
                "{i}. Cables, above, is a different reading of the same " +
                "net: the frame's edge order rather than this table's. " +
                "Branch {i} is bar {i} in both, but item [k] within a " +
                "branch is not the same member. AT THE SOLVED STATE: this " +
                "is read at the Result's solved vertices even on a Result " +
                "from Animate, because it is the statics of the finished " +
                "vault. The frame's own geometry is Mesh through Columns, " +
                "above.",
                GH_ParamAccess.tree);
            parameters.AddLineParameter(
                "Form Lines",
                "FL",
                "Planar form-diagram edges, branched and ordered exactly as " +
                "Member Lines. Empty for FD. AT THE SOLVED STATE: this is " +
                "read at the Result's solved vertices even on a Result from " +
                "Animate, because it is the statics of the finished vault. " +
                "The frame's own geometry is Mesh through Columns, above.",
                GH_ParamAccess.tree);
            parameters.AddLineParameter(
                "Force Lines",
                "FCL",
                "The reciprocal FORCE diagram's edges, branched and ordered " +
                "exactly as Member Lines and Form Lines, so branch {i} item " +
                "[k] is the same member in all three. This is the force " +
                "polygon at its OWN coordinates: Display lays a copy of it " +
                "out beside the model to draw, and this hands back the " +
                "diagram itself. Empty for FD, which has no reciprocal " +
                "diagram. AT THE SOLVED STATE: this is read at the Result's " +
                "solved vertices even on a Result from Animate, because it " +
                "is the statics of the finished vault. The frame's own " +
                "geometry is Mesh through Columns, above.",
                GH_ParamAccess.tree);
            parameters.AddPointParameter(
                "Load Points",
                "LP",
                "Points carrying applied loads. TNA: non-zero only; FD: " +
                "unfiltered. A flat LIST rather than a tree, as it has " +
                "always been. AT THE SOLVED STATE: this is read at the " +
                "Result's solved vertices even on a Result from Animate, " +
                "because it is the statics of the finished vault. The " +
                "frame's own geometry is Mesh through Columns, above.",
                GH_ParamAccess.list);
            parameters.AddVectorParameter(
                "Load Vectors",
                "LV",
                "Applied load vectors aligned with Load Points. TNA: " +
                "non-zero only; FD: unfiltered. A flat LIST rather than a " +
                "tree, as it has always been. AT THE SOLVED STATE: this is " +
                "read at the Result's solved vertices even on a Result from " +
                "Animate, because it is the statics of the finished vault. " +
                "The frame's own geometry is Mesh through Columns, above.",
                GH_ParamAccess.list);
            parameters.AddVectorParameter(
                "Reaction Vectors",
                "RV",
                "Support reactions, branched and ordered EXACTLY as Anchor " +
                "Nodes: one branch per connected anchor strip, item for " +
                "item, so strip {i} item [k] is the same support in both. A " +
                "support carrying no reaction holds its slot as a ZERO " +
                "rather than dropping out, which is what keeps that " +
                "correspondence true. Sum one branch to get what a single " +
                "side of the vault puts into the ground. A reaction " +
                "reported at a node that is on no anchor strip gets no " +
                "branch here and is named in a Warning instead. AT THE " +
                "SOLVED STATE: this is read at the Result's solved vertices " +
                "even on a Result from Animate, because it is the statics " +
                "of the finished vault. The frame's own geometry is Mesh " +
                "through Columns, above.",
                GH_ParamAccess.tree);
        }
```

If Param answered question 12B(a) with the CHORD of rule 5.2(a), slot 5 is `parameters.AddLineParameter` instead of `AddCurveParameter` and its description reads "ONE straight line per strip, from its first node to its last" in place of "ONE curve per strip, a polyline through every node of it", with the closed/open clause dropped. Nothing else in this registration changes.

Load Points and Load Vectors STAY lists. Changing an access mode changes what a downstream component receives, and the spec records that as a loose end rather than fixing it here.

- [ ] **Step 4: Write the two halves and the new SolveInstance**

Replace `SolveInstance`, `VisualiseComponents.cs:429-680`, with the following. Everything inside `StaticsHalf` is carried from the old body verbatim except that Member IDs, Node IDs, Support Points and the reaction POINTS have gone with their ports, and the reaction branching is now the static of Task 36.

```csharp
        /// <summary>
        /// What the statics half hands back: the six streams below Columns,
        /// plus the stray node ids the Warning names and the member count
        /// the chin reads.
        /// </summary>
        internal sealed record Statics(
            List<List<Line>> MemberLines,
            List<List<Line>> FormLines,
            List<List<Line>> ForceLines,
            List<Point3d> LoadPoints,
            List<Vector3d> LoadVectors,
            List<List<Vector3d>> ReactionBranches,
            List<int> Strays,
            int MemberCount);

        /// <summary>
        /// The frame half, under its OWN catch. FrameGeometry.Read throws on
        /// a Result carrying no equilibrium or no vertices, and a Result
        /// whose TNA mappings are malformed in a way only the statics half
        /// minds must still hand back the mesh, the cables and the columns.
        /// </summary>
        internal static (FrameGeometry.Set? Set, string? Error) FrameHalf(
            ResultDto result)
        {
            try
            {
                return (FrameGeometry.Build(result), null);
            }
            catch (Exception error)
            {
                return (null, error.GetBaseException().Message);
            }
        }

        /// <summary>
        /// The statics half, under its own catch, read at the SOLVED
        /// vertices. It takes the anchor strips as node index lists rather
        /// than deriving its own, so Reaction Vectors is branched on exactly
        /// the strips Anchor Nodes draws. Where the frame half failed there
        /// are no strips, so Reaction Vectors comes back empty and every
        /// reaction is reported as a stray; the other five streams stand,
        /// which is what rule 1.6A asks of the mirror case.
        /// </summary>
        internal static (Statics? Answer, string? Error) StaticsHalf(
            ResultDto result,
            List<List<int>> anchorStrips)
        {
            try
            {
                EquilibriumResultDto equilibrium = result.Equilibrium!;
                bool isTna = ResultTables.IsTna(result);

                // The one ordering every reader of this Result shares.
                // Forces builds its numbers from these same rows, which is
                // what makes its trees align with the geometry trees here
                // without either component matching coordinates.
                ResultTables.MemberRow[] members = ResultTables.Members(result);
                // The two ends of each member as NODE INDICES, which is what
                // says whether a member lies along a principal line. The
                // lines themselves cannot answer that: a point is not an
                // index, and matching by coordinate would make an exact
                // question into a tolerance one.
                (int U, int V)[] memberEnds = members
                    .Select(row => (row.U, row.V))
                    .ToArray();
                // A ResultDto deserialised straight from JSON can name a
                // node this net does not have, and result.Validate() would
                // not stop it, so a reaction whose node is out of range is
                // dropped here rather than indexing off the end of the
                // vertex list.
                (int Node, Vector3d Vector)[] reactions =
                    ResultTables.Reactions(result)
                        .Where(item =>
                            item.Node >= 0 &&
                            item.Node < equilibrium.Vertices.Count)
                        .ToArray();

                Line[] memberLines;
                Line[] formLines;
                (Point3d Point, Vector3d Vector)[] loads;

                if (isTna)
                {
                    // Both line arrays are driven by the TABLE's rows, not
                    // by a second sort of the edge states. Two sorts that
                    // agree today are still two places to disagree
                    // tomorrow, and the point of the table is that there is
                    // one order.
                    var stateById = new Dictionary<int, TnaEdgeStateDto>();
                    foreach (TnaEdgeStateDto state in result.EdgeStates)
                        stateById[state.Id] = state;
                    IReadOnlyDictionary<int, TnaGraphEdgeDto> formEdges =
                        result.FormGraph!.Edges.ToDictionary(edge => edge.Id);
                    IReadOnlyDictionary<int, Point3Dto> formPoints =
                        result.FormGraph!.Vertices.ToDictionary(
                            vertex => vertex.Id,
                            vertex => vertex.Point);

                    memberLines = members
                        .Select(row => ThrustLine(
                            equilibrium, row.EquilibriumEdgeId))
                        .ToArray();
                    formLines = members
                        .Select(row => FormLine(
                            stateById[row.Id], formEdges, formPoints))
                        .ToArray();

                    loads = result.Mappings!.Loads
                        .Select(item => (
                            Point(equilibrium.Vertices[item.EquilibriumVertexId]),
                            Vector(item.Vector)))
                        .Where(item => item.Item2.SquareLength > 1.0e-24)
                        .ToArray();
                }
                else
                {
                    memberLines = MemberLines(equilibrium);
                    formLines = Array.Empty<Line>();

                    loads = equilibrium.Loads
                        .Select(item => (Point(item.Point), Vector(item.Vector)))
                        .ToArray();
                }

                // The force diagram, on the SAME rows as the form diagram
                // above, read from the Result rather than from the locals of
                // the branch above so the rule is one method the harness can
                // drive on its own.
                Line[] forceLines = ForceLines(result, members);

                // The principal lines this Result carries, resolved upstream
                // by Pattern from the curves drawn into it, travelling in
                // the contract, so this reads the same bars Animate and
                // Columns do rather than deriving its own.
                List<List<int>> bars = MouldGeometry.PrincipalRuns(
                    equilibrium, equilibrium.Vertices.Count);
                int[] memberBar = MouldGeometry.MemberRunIndex(
                    memberEnds, bars);

                // One branch per bar, then infill LAST. Every
                // member-aligned stream is sliced by the same index array,
                // so the index-to-index alignment holds branch to branch as
                // well.
                List<List<T>> ByBar<T>(IReadOnlyList<T> values)
                {
                    var branches = new List<List<T>>();
                    for (int b = 0; b <= bars.Count; b++)
                        branches.Add(new List<T>());
                    for (int i = 0; i < values.Count; i++)
                    {
                        int bar = i < memberBar.Length ? memberBar[i] : -1;
                        branches[bar >= 0 ? bar : bars.Count].Add(values[i]);
                    }
                    return branches;
                }

                (List<List<Vector3d>> branches, List<int> strays) =
                    ReactionBranches(anchorStrips, reactions);

                return (
                    new Statics(
                        ByBar(memberLines),
                        ByBar(formLines),
                        ByBar(forceLines),
                        loads.Select(item => item.Point).ToList(),
                        loads.Select(item => item.Vector).ToList(),
                        branches,
                        strays,
                        members.Length),
                    null);
            }
            catch (Exception error)
            {
                return (null, error.GetBaseException().Message);
            }
        }

        protected override void SolveInstance(IGH_DataAccess data)
        {
            ResultGoo? goo = null;
            if (!data.GetData(0, ref goo) ||
                goo?.Value is not ResultDto result)
            {
                // Said in the chin as well as by the empty ports: without
                // this the component sits under the previous solve's reading
                // over ports that now carry nothing.
                Message = "No Result";
                return;
            }

            // ONCE, before either half. A Result that fails the contract is
            // not a Result either half should be reading, so its failure is
            // the single Error that empties everything.
            IReadOnlyList<string> errors = result.Validate();
            if (errors.Count > 0)
            {
                Message = "Invalid";
                ReportException(
                    "Deconstruct failed",
                    new InvalidOperationException(string.Join(" ", errors)));
                return;
            }

            (FrameGeometry.Set? set, string? frameError) = FrameHalf(result);
            List<List<int>> strips =
                set?.AnchorNodeIds ?? new List<List<int>>();
            (Statics? statics, string? staticsError) =
                StaticsHalf(result, strips);

            if (set is not null)
            {
                data.SetData(0, set.Mesh);
                data.SetDataTree(1, OutputTree.Lines(set.Cables));
                data.SetDataTree(2, OutputTree.Curves(set.PrincipalLines));
                data.SetDataTree(3, OutputTree.Points(set.PrincipalNodes));
                data.SetDataTree(4, OutputTree.Points(set.AnchorGroups));
                data.SetDataTree(5, OutputTree.Curves(set.AnchorLines));
                data.SetDataTree(6, OutputTree.Points(set.PerimeterNodes));
                data.SetDataTree(7, OutputTree.Curves(set.PerimeterLines));
                data.SetDataTree(8, OutputTree.Lines(set.ColumnBranches));
            }
            if (statics is not null)
            {
                data.SetDataTree(9, OutputTree.Lines(statics.MemberLines));
                data.SetDataTree(10, OutputTree.Lines(statics.FormLines));
                data.SetDataTree(11, OutputTree.Lines(statics.ForceLines));
                data.SetDataList(12, statics.LoadPoints);
                data.SetDataList(13, statics.LoadVectors);
                data.SetDataTree(
                    14, OutputTree.Vectors(statics.ReactionBranches));

                if (statics.Strays.Count > 0)
                {
                    AddRuntimeMessage(
                        GH_RuntimeMessageLevel.Warning,
                        $"{statics.Strays.Count} reaction(s) are reported at " +
                        "nodes that are on no anchor strip, so they are on " +
                        "no branch of Reaction Vectors: node(s) " +
                        string.Join(", ", statics.Strays) + ". This Result's " +
                        "supports do not account for one of its reactions.");
                }
            }

            if (frameError is not null)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Error,
                    "Deconstruct's FRAME half failed, so Mesh through " +
                    $"Columns are empty: {frameError}");
            }
            if (staticsError is not null)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Error,
                    "Deconstruct's STATICS half failed, so Member Lines " +
                    $"through Reaction Vectors are empty: {staticsError}");
            }

            // The two support lists this plugin has in play, compared on
            // every solve. Both are computed here anyway, so this costs one
            // set comparison and is what turns rule 3.6's second reason into
            // a mechanism rather than a hope.
            EquilibriumResultDto contract = result.Equilibrium!;
            string? divergence = SeedDivergence(
                ResultTables.SupportNodes(result),
                contract.ResolvedSupportNodeIds
                    .Where(id => id >= 0 && id < contract.Vertices.Count)
                    .Distinct()
                    .ToArray());
            if (divergence is not null)
                AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, divergence);

            // Solver, member count, phase. The member count is the statics
            // half's reading and the phase word the frame half's, so a half
            // that failed takes its own clause out and is named after what
            // is left. A Result carrying no frame reports "final", which is
            // FrameGeometry.FinalPhase, so the phase clause is always there
            // while the frame half stands.
            var clauses = new List<string> { result.Solver.ToUpperInvariant() };
            if (statics is not null)
                clauses.Add($"{statics.MemberCount} members");
            if (set is not null)
                clauses.Add(set.Phase);
            string chin = string.Join(" · ", clauses);
            Message =
                set is null && statics is null ? "Invalid"
                : set is null ? chin + " (frame failed)"
                : statics is null ? chin + " (statics failed)"
                : chin;
        }
```

Keep everything from `ThrustMesh` at `:682` to the end of the class unchanged. `ThrustMesh` is called by Export at `DeliveryComponents.cs:1041`; `ColumnTrees` and `ForceLines` are driven by `ValidateDeconstructColumnTrees` at `Program.cs:2897` and `ValidateDeconstructForceLines` at `:3147`, and rule 10.2(g) makes carrying them under their present names a requirement rather than a courtesy.

- [ ] **Step 5: Delete Frame and its icon**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
Remove-Item -Force "$repo\plugin\native_v02\Components\FrameComponents.cs"
Remove-Item -Force "$repo\plugin\icons\frame.png"
```

Then delete the `frame` entry from `plugin/icons/icon-map.json`, lines 199 to 204 today, which read:

```json
    {
      "key": "frame",
      "label": "FR",
      "category": "04 Read",
      "filename": "frame.png"
    },
```

keeping the array valid JSON. `native_components` goes from 21 entries to 20, and the harness enforces one entry per component at `Program.cs:13940-13966`. The `result_breakdown` entry at `:163-168` already reads label `DE` in category `04 Read` and needs no edit at all, which is the cheapest consequence of the name ruling.

- [ ] **Step 6: Repoint the five sentences elsewhere in the plugin**

All five must be corrected in this commit or they become false the day this ships. Because the merged component is still called Deconstruct, three of them keep the word and only the PORT name inside them changes.

`SupportsReaderComponent.cs:15-16`, in the class comment, replace "Every anchor output is branched by support strip exactly as Deconstruct's Reaction Points" with "Every anchor output is branched by support strip exactly as Deconstruct's Anchor Nodes".

`SupportsReaderComponent.cs:17-18`, in the same comment, replace "and every column output by column tree exactly as Frame's Columns" with "and every column output by column tree exactly as Deconstruct's Columns".

`SupportsReaderComponent.cs:45`, in the component description, replace "Anchor trees align with Deconstruct's Reaction Points and column trees with Frame's Columns." with "Anchor trees align with Deconstruct's Anchor Nodes and column trees with Deconstruct's Columns."

`SupportsReaderComponent.cs:113`, in the Anchor Along port text, replace "As a TREE branched EXACTLY as DECONSTRUCT's Reaction Points:" with "As a TREE branched EXACTLY as DECONSTRUCT's Anchor Nodes:".

`FitComponent.cs:121`, the Deviation description, replace "which is the one order here with NO partner tree: DECONSTRUCT's Node IDs are per support strip and its points are branched the same way, so nothing on that side is item-for-item with this." with "which is the one order here with NO partner tree: nothing on Deconstruct's side is item-for-item with this."

`ForcesComponent.cs:198`, the Residuals description, replace "Like Fit's Deviation this has NO partner tree: DECONSTRUCT's Node IDs are per support strip, so read this against the Result's own vertex list." with "Like Fit's Deviation this has NO partner tree: read this against the Result's own vertex list."

The two disclaimers come out whole rather than being repointed, because the port they disclaim against no longer exists. Loads' own Node IDs INPUT at `SpineComponents.cs:626` and `:634` is a different port on a different component and is untouched.

- [ ] **Step 7: Run the gate and the icon check**

Both. Expect `Components discovered: 20`, `Parameters discovered: 12`, every check PASS, `0 warnings`, and the icon check ending `Validated 20 icon files; ...`. If Task 33's nickname check fails on Mesh `M` against Member Lines `M`, slot 9's nickname was left as `M`: it is `ML`, which reads better beside FL and FCL and leaves M meaning a mesh, the convention across the whole Grasshopper ecosystem.

- [ ] **Step 8: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/VisualiseComponents.cs" "plugin/native_v02/Components/FrameComponents.cs" "plugin/native_v02/Components/SupportsReaderComponent.cs" "plugin/native_v02/Components/FitComponent.cs" "plugin/native_v02/Components/ForcesComponent.cs" "plugin/icons/icon-map.json" "plugin/icons/frame.png" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(readers): Deconstruct and Frame become one fifteen-port reader"
```

`git add` on a deleted path stages the deletion, so both `FrameComponents.cs` and `frame.png` are named explicitly rather than swept up by a directory add.

---

### Task 39: The leaf, the partitioned halves, and the harness prose the merge falsified

Spec rules 10.3(b), 10.3(m), 10.2(h) and 10.2(i). The contract pins of Task 38 already assert fifteen names and fifteen nicknames in order. What they do not assert is the LEAF property, and Param declined the sixteenth port deliberately: a later hand adding a Result passthrough back would look like a small kindness to whoever wanted to wire something downstream, and this is the assertion that makes it a decision rather than an edit.

**Files:**
- Modify: `tests/native_smoke/Program.cs` (two new checks with their PASS blocks, the Mismatch PASS message at :1379-1399, the ResultTables PASS message at :1360-1370, the stray sentence at :5439-5441, and the Deconstruct-slim fixture comment at :5617-5624)
- Test: `ValidateDeconstructLeaf`, `ValidateDeconstructHalves`

**Interfaces:**
- Consumes: `DeconstructComponent.FrameHalf` and `DeconstructComponent.StaticsHalf` from Task 38, both internal statics; `RequireStatic(Type, string)` at `Program.cs:7954`.
- Produces: nothing later tasks call.

- [ ] **Step 1: Write the leaf check first, and watch it fail**

Add to `tests/native_smoke/Program.cs` immediately after `ValidateDeconstructSeedDivergence` from Task 37:

```csharp
    /// <summary>
    /// The merged reader is a LEAF, and its port count is fifteen.
    ///
    /// The contract tables already pin the fifteen names and the fifteen
    /// nicknames in order. This asserts the two things they cannot: that
    /// there are exactly fifteen outputs and that NONE of them is a
    /// ResultParam. Param was offered a sixteenth port at output 0 carrying
    /// the Result through with diagnostics appended, which would have let
    /// the stray reaction and the retired diagnostics travel down a wire
    /// into Export and on to the studio, and he declined it on 2026-09-01.
    /// Adding one back would read as a small kindness to whoever wanted to
    /// wire something downstream; this is what makes it a decision rather
    /// than an edit.
    /// </summary>
    private static void ValidateDeconstructLeaf(Assembly plugin)
    {
        Type deconstruct = RequireComponentType(plugin, "DeconstructComponent");
        Type resultParam = RequireContractType(plugin, "ResultParam");
        object instance = CreateInstance(deconstruct);
        try
        {
            object parameters = deconstruct
                .GetProperty("Params")
                ?.GetValue(instance)
                ?? throw new InvalidOperationException(
                    "Could not inspect Deconstruct's parameters.");
            IList inputs = (IList)parameters.GetType()
                .GetProperty("Input")!.GetValue(parameters)!;
            IList outputs = (IList)parameters.GetType()
                .GetProperty("Output")!.GetValue(parameters)!;

            if (inputs.Count != 1 || !resultParam.IsInstanceOfType(inputs[0]))
            {
                throw new InvalidOperationException(
                    "Deconstruct takes ONE input and it is the Result, at "
                    + $"index 0; got {inputs.Count} inputs whose first is "
                    + $"{inputs[0]?.GetType().Name ?? "null"}.");
            }
            if (outputs.Count != 15)
            {
                throw new InvalidOperationException(
                    "The merged reader carries FIFTEEN outputs: nine from "
                    + "Frame and six from the old Deconstruct, less Member "
                    + "IDs, Node IDs, Reaction Points and Phase, with Support "
                    + $"Points absorbed into Anchor Nodes. Got {outputs.Count}.");
            }
            for (int index = 0; index < outputs.Count; index++)
            {
                if (resultParam.IsInstanceOfType(outputs[index]))
                {
                    throw new InvalidOperationException(
                        $"Output {index} is a ResultParam. The merged reader "
                        + "is a LEAF: it hands back no Result, so nothing "
                        + "wires downstream of it. The sixteenth port was put "
                        + "to Param on 2026-09-01 and he declined it, and "
                        + "everything this component has to say beyond "
                        + "geometry is said as a runtime message instead.");
                }
            }
        }
        finally
        {
            if (instance is IDisposable disposable)
                disposable.Dispose();
        }
    }
```

Register it after Task 37's PASS block:

```csharp
        try
        {
            ValidateDeconstructLeaf(plugin);
            Console.WriteLine(
                "PASS  Deconstruct is a leaf: one Result input at index 0, "
                + "exactly fifteen outputs, and not one of them a "
                + "ResultParam, so the sixteenth port Param declined cannot "
                + "come back as a quiet kindness to a downstream wire.");
        }
        catch (Exception exception)
        {
            failures.Add($"Deconstruct is a leaf: {DescribeException(exception)}");
        }
```

Run the gate. It passes if Task 38 was written correctly, and it is worth running before Step 2 to see it green on its own.

- [ ] **Step 2: Write the partitioning check**

Add immediately after `ValidateDeconstructLeaf`:

```csharp
    /// <summary>
    /// The two halves are separate methods with separate catches.
    ///
    /// Merged naively the two components' single try/catch each would have
    /// become one catch over both, and the halves fail independently in
    /// practice: the statics path indexes the edge-state dictionary with no
    /// guard, which throws on a Result whose state ids and member rows
    /// disagree, and FrameGeometry.Read throws on a Result carrying no
    /// equilibrium or no vertices. An author whose TNA mappings are
    /// malformed gets the mesh, the cables and the columns today, and would
    /// have got fifteen empty ports.
    ///
    /// A bare ResultDto with no equilibrium is a Result BOTH halves refuse,
    /// and it is the one fixture this harness can drive: FrameGeometry.Build
    /// reaches ThrustMeshFromResult, which returns null the moment it sees a
    /// null equilibrium and so never constructs a Mesh, and Read then throws
    /// before any Rhino call. Which half's Error reaches the balloon, and
    /// what the chin then reads, needs a document and is a manual check.
    /// </summary>
    private static void ValidateDeconstructHalves(Assembly plugin)
    {
        Type deconstruct = RequireComponentType(plugin, "DeconstructComponent");
        MethodInfo frameHalf = RequireStatic(deconstruct, "FrameHalf");
        MethodInfo staticsHalf = RequireStatic(deconstruct, "StaticsHalf");
        if (frameHalf == staticsHalf)
        {
            throw new InvalidOperationException(
                "The frame half and the statics half are DISTINCT statics, "
                + "or there is one catch over both and a Result one half "
                + "refuses empties all fifteen ports.");
        }

        Type resultType = RequireContractType(plugin, "ResultDto");
        object bare = CreateResultDto(resultType, "fd", null!, null, null);

        object framed = frameHalf.Invoke(null, new[] { bare })!;
        Type frameTuple = framed.GetType();
        if (frameTuple.GetField("Item1")!.GetValue(framed) is not null)
        {
            throw new InvalidOperationException(
                "A Result with no equilibrium has no frame to read, so the "
                + "frame half hands back nothing.");
        }
        if (frameTuple.GetField("Item2")!.GetValue(framed) is not string frameError ||
            frameError.Length == 0)
        {
            throw new InvalidOperationException(
                "The frame half RETURNS its failure rather than throwing, "
                + "and the reason is what the component's Error names; got "
                + "no message.");
        }

        Type stripsType = staticsHalf.GetParameters()[1].ParameterType;
        object noStrips = Activator.CreateInstance(stripsType)!;
        object statics = staticsHalf.Invoke(null, new[] { bare, noStrips })!;
        Type staticsTuple = statics.GetType();
        if (staticsTuple.GetField("Item1")!.GetValue(statics) is not null)
        {
            throw new InvalidOperationException(
                "A Result with no equilibrium has no statics to read, so the "
                + "statics half hands back nothing.");
        }
        if (staticsTuple.GetField("Item2")!.GetValue(statics) is not string staticsError ||
            staticsError.Length == 0)
        {
            throw new InvalidOperationException(
                "The statics half RETURNS its failure rather than throwing, "
                + "and the reason is what the component's Error names; got "
                + "no message.");
        }
    }
```

Register it after the leaf block:

```csharp
        try
        {
            ValidateDeconstructHalves(plugin);
            Console.WriteLine(
                "PASS  Deconstruct's two halves: the frame half and the "
                + "statics half are distinct statics with separate catches, "
                + "and each returns its own empty answer and its own reason "
                + "rather than throwing, so a Result one half refuses does "
                + "not empty the other half's ports.");
        }
        catch (Exception exception)
        {
            failures.Add($"Deconstruct's two halves: {DescribeException(exception)}");
        }
```

Run the gate and see both new checks pass.

- [ ] **Step 3: Correct the harness prose the merge falsified**

Three sentences in the harness are now false and none of them is asserted by anything, so nothing fails until a later reader trusts them.

In the `ParameterIdentity.Mismatch` PASS message at `Program.cs:1392-1396`, replace:

```csharp
                + "Deconstruct's slim lists 'Thrust Mesh', 'Columns', "
                + "'Heads' and 'Feet' as removed, in archived order, and "
                + "still closes check-every-wire; Frame's pure append names "
                + "'Anchor Lines' and closes with existing wires keeping "
                + "their ports instead. "
```

with:

```csharp
                + "the 2026-08-31 Deconstruct slim, whose fixture is kept "
                + "for the SHAPE of a count change rather than for a "
                + "component that still has it, lists 'Thrust Mesh', "
                + "'Columns', 'Heads' and 'Feet' as removed, in archived "
                + "order, and still closes check-every-wire; the pure-append "
                + "fixture beside it names 'Anchor Lines' and closes with "
                + "existing wires keeping their ports instead. Both name "
                + "surfaces the readers merge has since replaced: there is "
                + "no Frame in the plugin now, and the Deconstruct that "
                + "exists carries fifteen different ports. "
```

Add to the Deconstruct-slim fixture comment at `Program.cs:5617-5624`, after its last sentence:

```csharp
        // HISTORY, kept deliberately. The readers MERGE of 2026-09-01
        // replaced this surface again: Deconstruct now carries fifteen
        // ports and Frame is gone. The fixture is hand-built name arrays
        // rather than live components, so it still measures what it was
        // written to measure, which is the SHAPE of the warning a count
        // change produces, and it is not repointed at the current ports.
```

In the `ResultTables` stray sentence at `Program.cs:5439-5441`, replace:

```csharp
                "A zero reaction is not a reaction: two went in and only the "
                + $"non-zero one comes back; got {tnaReactions.Length}. Keeping the "
                + "zero would give Deconstruct and Supports different stray branches.");
```

with:

```csharp
                "A zero reaction is not a reaction: two went in and only the "
                + $"non-zero one comes back; got {tnaReactions.Length}. Keeping the "
                + "zero would make a support that carries nothing look like a "
                + "reaction, and Deconstruct would raise a stray Warning "
                + "naming a node that is not stray at all.");
```

The merged reader has no stray BRANCH to differ in any more; the check itself still holds, because a zero reaction that became a stray would now raise a Warning about a node on a perfectly ordinary support. The `ResultTables` order PASS message at `:1360-1370` names Deconstruct and the name survives, so it needs no edit.

- [ ] **Step 4: Run the gate**

Green, with two new PASS lines.

- [ ] **Step 5: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "tests/native_smoke/Program.cs"
git -C $repo commit -m "test(native_smoke): the merged reader is a leaf and its halves fail apart"
```

---

### Task 40: Diagnose's Result input becomes optional

Spec rules 6.1, 6.2 and 9.5, measured by rule 10.3(g). One port, two behaviours. Wired it reports that chain alone, which is what it does today; unwired it will scan the whole document, which Tasks 41 to 43 build. This task lands the registration change and its assertion on their own, because making input 0 optional changes no name, no count and no order, so `ParameterIdentity.Mismatch` says nothing and a saved definition with a Result wired into Diagnose keeps working identically.

**Files:**
- Modify: `plugin/native_v02/Components/DiagnoseComponents.cs:44-53` (one line added after the `AddParameter` call)
- Modify: `tests/native_smoke/Program.cs` (a new `ValidateDiagnoseOptionalResult` with its PASS block)
- Test: `ValidateDiagnoseOptionalResult`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `DiagnoseComponent`'s input 0 with `Optional = true`. Tasks 42 and 43 rely on `SolveInstance` being reached with nothing wired, which this is what allows.

- [ ] **Step 1: Write the check first, and watch it fail**

Add to `tests/native_smoke/Program.cs` after `ValidateDeconstructHalves`:

```csharp
    /// <summary>
    /// Diagnose's Result input is OPTIONAL.
    ///
    /// One assertion, and it is what stops a later edit quietly making it
    /// required again: a required input that is unwired never reaches
    /// SolveInstance at all, so the document scan would simply never run and
    /// nothing would say why. Diagnose is pinned nowhere else in this
    /// harness, appearing only in NativeIconEntries and in
    /// ValidateDiagnoseRules' type lookup, so it has no port contract to
    /// fall back on.
    /// </summary>
    private static void ValidateDiagnoseOptionalResult(Assembly plugin)
    {
        Type diagnose = RequireComponentType(plugin, "DiagnoseComponent");
        object instance = CreateInstance(diagnose);
        try
        {
            object parameters = diagnose
                .GetProperty("Params")
                ?.GetValue(instance)
                ?? throw new InvalidOperationException(
                    "Could not inspect Diagnose's parameters.");
            IList inputs = (IList)parameters.GetType()
                .GetProperty("Input")!.GetValue(parameters)!;
            if (inputs.Count != 1)
            {
                throw new InvalidOperationException(
                    $"Diagnose takes ONE input; got {inputs.Count}.");
            }
            object port = inputs[0]!;
            if (port.GetType().GetProperty("Optional")?.GetValue(port) is not true)
            {
                throw new InvalidOperationException(
                    "Diagnose's Result input is OPTIONAL: unwired it scans "
                    + "the whole document and reports every Ananke "
                    + "component's complaints, wired it reports that chain "
                    + "alone. A required input that is unwired never reaches "
                    + "SolveInstance, so the scan would never run.");
            }
            string nick =
                port.GetType().GetProperty("NickName")?.GetValue(port) as string
                ?? string.Empty;
            if (!string.Equals(nick, "RES", StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    "RES stays at input 0 and keeps its nickname, so making "
                    + $"it optional moves no wire; got '{nick}'.");
            }
        }
        finally
        {
            if (instance is IDisposable disposable)
                disposable.Dispose();
        }
    }
```

Register it after Task 39's halves block:

```csharp
        try
        {
            ValidateDiagnoseOptionalResult(plugin);
            Console.WriteLine(
                "PASS  Diagnose's Result input is optional and still RES at "
                + "index 0, so an unwired Diagnose reaches SolveInstance and "
                + "scans the document while a saved definition with a Result "
                + "wired into it keeps working identically.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Diagnose's optional Result: {DescribeException(exception)}");
        }
```

Run the gate. It must fail with `Diagnose's Result input is OPTIONAL: ...`.

- [ ] **Step 2: Make it optional**

In `plugin/native_v02/Components/DiagnoseComponents.cs`, after the `AddParameter` call that ends at `:52`, add:

```csharp
            // OPTIONAL, which is the whole of the registration change: one
            // port, two behaviours. Unwired this scans the document; wired
            // it reports that chain alone. The same idiom Export uses on its
            // own optional inputs. Nothing else about the registration
            // moves, so a saved definition with a Result wired in keeps
            // working and the load warning has nothing to compare.
            parameters[0].Optional = true;
```

The six outputs at `:57-78` keep their names, nicknames, types and order.

- [ ] **Step 3: Run the gate**

Green, with the new PASS line.

- [ ] **Step 4: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/DiagnoseComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(diagnose): the Result input becomes optional"
```

---

### Task 41: Telling our components from foreign ones, and the digest that stops the loop

Spec rules 6.5, 6.7 and 7.3(c), measured by rules 10.3(h) and 10.3(i). Both are pure statics with no document behind them, so both land before the scan that uses them.

**The obvious membership test is wrong and must not be used.** `obj is NativeComponentBase` catches only thirteen of the twenty components: the eight task-capable ones derive from `NativeTaskComponentBase<TResult>`, which derives from `GH_TaskCapableComponent<TResult>` and NOT from `NativeComponentBase` (`NativeComponentBase.cs:539` against `:696-697`). The eight are Export (`DeliveryComponents.cs:81`), Backend Health (`FormFindingComponents.cs:17-18`), Import Pieces (`PiecesComponents.cs:84-85`), Skin (`SkinComponents.cs:45-46`) and the four solvers (`SolverComponents.cs:32, :536, :1033`). Export and Import Pieces are the two components Param named by name, so the wrong test would miss precisely the ones the ruling was about. Category is also rejected: `ComponentCategories.Category` is the string "Ananke COMPAS" (`NativeComponentBase.cs:31`) and a string any plugin could register is weaker than an assembly reference.

**Files:**
- Modify: `plugin/native_v02/Components/DiagnoseComponents.cs` (three internal statics and one record struct, added after `Render` ends at :259)
- Modify: `tests/native_smoke/Program.cs` (two new checks with their PASS blocks)
- Test: `ValidateDiagnoseMembership`, `ValidateDiagnoseDigest`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `internal readonly record struct DiagnoseComponent.Entry(Guid Instance, string Name, string Nick, IReadOnlyList<string> Remarks, IReadOnlyList<string> Warnings, IReadOnlyList<string> Errors, string Chin)`
  - `internal static bool DiagnoseComponent.IsOurs(IGH_DocumentObject item)`
  - `internal static List<Entry> DiagnoseComponent.InOrder(IEnumerable<Entry> entries)`
  - `internal static string DiagnoseComponent.Digest(IEnumerable<Entry> entries)`
  - Task 42 calls `IsOurs` and `InOrder`; Task 43 calls `Digest`.

- [ ] **Step 1: Write both checks first, and watch them fail**

Add to `tests/native_smoke/Program.cs` after `ValidateDiagnoseOptionalResult`:

```csharp
    /// <summary>
    /// <c>DiagnoseComponent.IsOurs</c>: the membership predicate the
    /// document scan reads every object through.
    ///
    /// The test is ASSEMBLY IDENTITY, and the obvious alternative is wrong.
    /// `obj is NativeComponentBase` catches only thirteen of the twenty:
    /// the eight task-capable components derive from
    /// NativeTaskComponentBase, which derives from GH_TaskCapableComponent
    /// and not from NativeComponentBase, and Export and Import Pieces are
    /// two of the eight. Those are the components Param named by name when
    /// he asked for a scan of every component of our plugin, so the wrong
    /// test would have missed exactly what the ruling was about. This drives
    /// EVERY concrete component the harness discovered, so the count cannot
    /// drift out from under it, and one foreign Grasshopper type as the
    /// negative case.
    /// </summary>
    private static void ValidateDiagnoseMembership(
        Assembly plugin,
        Type[] componentTypes)
    {
        Type diagnose = RequireComponentType(plugin, "DiagnoseComponent");
        MethodInfo isOurs = RequireStatic(diagnose, "IsOurs");
        Type documentObject = isOurs.GetParameters()[0].ParameterType;

        foreach (Type componentType in componentTypes)
        {
            object instance = CreateInstance(componentType);
            try
            {
                if (isOurs.Invoke(null, new[] { instance }) is not true)
                {
                    throw new InvalidOperationException(
                        $"{componentType.Name} is one of ours and the "
                        + "predicate must say so. A test on "
                        + "NativeComponentBase alone fails here for every "
                        + "task-capable component, Export and Import Pieces "
                        + "among them.");
                }
            }
            finally
            {
                if (instance is IDisposable disposable)
                    disposable.Dispose();
            }
        }

        Type foreignType = documentObject.Assembly.GetType(
            "Grasshopper.Kernel.Parameters.Param_Integer", throwOnError: true)!;
        object foreign = CreateInstance(foreignType);
        try
        {
            if (isOurs.Invoke(null, new[] { foreign }) is not false)
            {
                throw new InvalidOperationException(
                    "Grasshopper's own Param_Integer is not one of ours, and "
                    + "a scan that claimed it would report every slider and "
                    + "panel on the canvas as an Ananke component.");
            }
        }
        finally
        {
            if (foreign is IDisposable disposable)
                disposable.Dispose();
        }
    }

    /// <summary>
    /// <c>DiagnoseComponent.Digest</c> and <c>InOrder</c>: the content latch
    /// that stops the document from never resting, and the one ordering that
    /// serves both it and the report's branch order.
    ///
    /// If the SolutionEnd handler scheduled unconditionally, the scheduled
    /// solution would end, raise SolutionEnd, schedule another, and the
    /// document would never rest. The latch is on the CONTENT: the handler
    /// schedules only when the digest differs from the digest last EMITTED.
    /// So three properties. Identical input gives an identical digest, or
    /// the latch never catches and the document spins. One changed message
    /// gives a different one, or the latch catches for ever and the report
    /// freezes on its first answer. And reordering the input list changes
    /// nothing, because document.Objects is in no order this component
    /// controls and a digest that moved with it would spin on a canvas
    /// nobody had touched.
    ///
    /// The ordering is measured here too, once for both its uses: the same
    /// InstanceGuid-ascending sort serves the digest and the report's branch
    /// order, so inserting a component must not move the ones around it.
    /// </summary>
    private static void ValidateDiagnoseDigest(Assembly plugin)
    {
        Type diagnose = RequireComponentType(plugin, "DiagnoseComponent");
        MethodInfo digest = RequireStatic(diagnose, "Digest");
        MethodInfo inOrder = RequireStatic(diagnose, "InOrder");
        Type entryType = plugin.GetType(
            "Ananke.COMPAS.Native.Components.DiagnoseComponent+Entry",
            throwOnError: true)!;
        Type entryList = typeof(List<>).MakeGenericType(entryType);
        MethodInfo addEntry = entryList.GetMethod("Add")!;

        object Entry(string guid, string nick, string message, string chin) =>
            Activator.CreateInstance(
                entryType,
                new Guid(guid),
                nick + " component",
                nick,
                new List<string>(),
                new List<string> { message },
                new List<string>(),
                chin)!;
        object List(params object[] entries)
        {
            object made = Activator.CreateInstance(entryList)!;
            foreach (object entry in entries)
                addEntry.Invoke(made, new[] { entry });
            return made;
        }
        string Ask(object entries) =>
            (string)digest.Invoke(null, new[] { entries })!;
        string[] Order(object entries) =>
            ((IEnumerable)inOrder.Invoke(null, new[] { entries })!)
                .Cast<object>()
                .Select(entry => (string)entryType
                    .GetProperty("Nick")!.GetValue(entry)!)
                .ToArray();

        const string A = "11111111-1111-1111-1111-111111111111";
        const string B = "22222222-2222-2222-2222-222222222222";
        const string C = "33333333-3333-3333-3333-333333333333";

        object first = List(
            Entry(A, "AA", "one", "chin one"),
            Entry(B, "BB", "two", "chin two"));
        object same = List(
            Entry(A, "AA", "one", "chin one"),
            Entry(B, "BB", "two", "chin two"));
        if (!string.Equals(Ask(first), Ask(same), StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "The same scan twice gives the SAME digest, or the latch "
                + "never catches and the document schedules a solution for "
                + "ever.");
        }

        object changed = List(
            Entry(A, "AA", "one", "chin one"),
            Entry(B, "BB", "two, differently", "chin two"));
        if (string.Equals(Ask(first), Ask(changed), StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "One changed message gives a DIFFERENT digest, or the latch "
                + "catches for ever and the report freezes on its first "
                + "answer.");
        }

        object shuffled = List(
            Entry(B, "BB", "two", "chin two"),
            Entry(A, "AA", "one", "chin one"));
        if (!string.Equals(Ask(first), Ask(shuffled), StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "Reordering the input changes NOTHING: document.Objects is "
                + "in no order this component controls, and a digest that "
                + "moved with it would schedule a solution on a canvas "
                + "nobody had touched.");
        }

        if (!Order(shuffled).SequenceEqual(new[] { "AA", "BB" }))
        {
            throw new InvalidOperationException(
                "The ordering is by InstanceGuid ascending whatever order "
                + "the scan met them in; got ["
                + string.Join(",", Order(shuffled)) + "].");
        }
        object inserted = List(
            Entry(C, "CC", "three", "chin three"),
            Entry(A, "AA", "one", "chin one"),
            Entry(B, "BB", "two", "chin two"));
        if (!Order(inserted).SequenceEqual(new[] { "AA", "BB", "CC" }))
        {
            throw new InvalidOperationException(
                "Inserting a component does not move the ones around it, or "
                + "every branch of the report shifts when an author drops a "
                + "component on the canvas; got ["
                + string.Join(",", Order(inserted)) + "].");
        }
    }
```

Register both after Task 40's block. `ValidateDiagnoseMembership` needs the discovered types, which are in scope where the other checks are registered:

```csharp
        try
        {
            ValidateDiagnoseMembership(plugin, componentTypes);
            Console.WriteLine(
                "PASS  Diagnose membership: every one of our concrete "
                + "components passes the assembly-identity predicate, the "
                + "eight task-capable ones included, and a foreign "
                + "Grasshopper parameter fails it, so the scan reads our "
                + "components and not the canvas.");
        }
        catch (Exception exception)
        {
            failures.Add($"Diagnose membership: {DescribeException(exception)}");
        }

        try
        {
            ValidateDiagnoseDigest(plugin);
            Console.WriteLine(
                "PASS  Diagnose digest: the same scan twice gives the same "
                + "digest, one changed message a different one, and "
                + "reordering the input none at all; the ordering is by "
                + "InstanceGuid ascending and inserting a component does not "
                + "move the ones around it.");
        }
        catch (Exception exception)
        {
            failures.Add($"Diagnose digest: {DescribeException(exception)}");
        }
```

Run the gate. It must fail with `DiagnoseComponent.IsOurs was not found.`

- [ ] **Step 2: Write the three statics and the record**

Add to `plugin/native_v02/Components/DiagnoseComponents.cs`, immediately after `Render` ends at `:259`:

```csharp
        /// <summary>
        /// One scanned component: who it is, and everything it has to say.
        ///
        /// Name and NickName come off IGH_InstanceDescription, which every
        /// document object implements, and InstanceGuid off
        /// IGH_DocumentObject. The nickname alone cannot tell two instances
        /// apart, because every instance of one component type ships the
        /// same nickname from its base constructor, so the guid is carried
        /// for the heading rule as well as for the digest.
        /// </summary>
        internal readonly record struct Entry(
            Guid Instance,
            string Name,
            string Nick,
            IReadOnlyList<string> Remarks,
            IReadOnlyList<string> Warnings,
            IReadOnlyList<string> Errors,
            string Chin);

        /// <summary>
        /// Whether one document object is OURS.
        ///
        /// ASSEMBLY IDENTITY. It is exact, costs one reference comparison,
        /// and needs no Grasshopper lookup. The obvious test is wrong and
        /// must not be used: `item is NativeComponentBase` catches only
        /// thirteen of the twenty, because the eight task-capable components
        /// derive from NativeTaskComponentBase, which derives from
        /// GH_TaskCapableComponent and not from NativeComponentBase, and
        /// Export and Import Pieces are two of the eight. Category is also
        /// rejected: "Ananke COMPAS" is a string any plugin could register,
        /// and a string is weaker than an assembly reference.
        /// </summary>
        internal static bool IsOurs(IGH_DocumentObject item) =>
            item.GetType().Assembly == typeof(DiagnoseComponent).Assembly;

        /// <summary>
        /// The one ordering, serving both the digest and the report's branch
        /// order. By InstanceGuid ascending: arbitrary but STABLE, which is
        /// the property that matters, because document.Objects is in no
        /// order this component controls and a report whose branches moved
        /// with it would be unreadable against itself from one solve to the
        /// next.
        /// </summary>
        internal static List<Entry> InOrder(IEnumerable<Entry> entries) =>
            entries.OrderBy(entry => entry.Instance).ToList();

        /// <summary>
        /// The content digest the SolutionEnd handler latches on.
        ///
        /// If the handler scheduled unconditionally the scheduled solution
        /// would end, raise SolutionEnd, schedule another, and the document
        /// would never rest. The latch is on the CONTENT and not on a flag
        /// or a timer: the handler schedules only when this differs from the
        /// digest last EMITTED. Ordinal, over each component's InstanceGuid,
        /// its three message lists in the order Remark, Warning, Error, and
        /// its chin, with the components in InOrder. Name and NickName are
        /// deliberately not in it: an author renaming an instance changes
        /// what the report reads but not what any component has to SAY, and
        /// a rename is a document change Grasshopper expires the canvas for
        /// anyway.
        /// </summary>
        internal static string Digest(IEnumerable<Entry> entries)
        {
            var text = new StringBuilder();
            foreach (Entry entry in InOrder(entries))
            {
                text.Append(entry.Instance.ToString("N")).Append('\u001f');
                foreach (string line in entry.Remarks)
                    text.Append(line).Append('\u001e');
                text.Append('\u001f');
                foreach (string line in entry.Warnings)
                    text.Append(line).Append('\u001e');
                text.Append('\u001f');
                foreach (string line in entry.Errors)
                    text.Append(line).Append('\u001e');
                text.Append('\u001f').Append(entry.Chin).Append('\u001d');
            }
            return text.ToString();
        }
```

`DiagnoseComponents.cs` already carries `using System;`, `using System.Collections.Generic;`, `using System.Linq;`, `using System.Text;` and `using Grasshopper.Kernel;`, so no using directive is added.

- [ ] **Step 3: Run the gate**

Green, with two new PASS lines. If `ValidateDiagnoseMembership` fails on a component, the predicate is testing something other than assembly identity.

- [ ] **Step 4: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/DiagnoseComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(diagnose): membership by assembly identity and a content digest"
```

---

### Task 42: Document mode

Spec rules 6.3, 6.4, 6.6, 6.8 and 7.4. Unwired, Diagnose scans the whole document and reports every Ananke component's complaints, in the same six ports, filled differently.

Three exact facts the API forces, each read from `C:\Program Files\Rhino 8\Plug-ins\Grasshopper\Grasshopper.xml`. Runtime messages are PER OBJECT, through `IGH_ActiveObject.RuntimeMessages(GH_RuntimeMessageLevel level)` at `:8917-8923`, and `GH_Document` offers no per-object message enumeration at all. There is no all-levels overload: the method takes ONE level and `GH_RuntimeMessageLevel` has exactly four members, Blank, Remark, Warning and Error (`:8814, :8819, :8824, :8829`), so a full scan is THREE calls per object; Blank is the "nothing recorded" state, not a list, and is not called. The chin line is `GH_Component.Message` (`:13352`), so reading it needs a cast to `GH_Component` rather than to `IGH_ActiveObject`.

Remark MUST be read. The plugin deliberately places content there: Display raises "FD result: no reciprocal diagram." and "Metric H unavailable for FD result; used F magnitude." as Remarks at `VisualiseComponents.cs:1285-1297`. Task 44's Rhino check confirms that a scan can retrieve them before Tasks 45 and 46 send anything else to that level.

**Files:**
- Modify: `plugin/native_v02/Components/DiagnoseComponents.cs` (a `Scan`, a `DocumentEntries` and a `RenderDocument` static after `Digest`; `SolveInstance` branched; the component description rewritten)
- Test: the build, plus the manual checks Task 43 carries. The scan itself needs a document and is not reachable from this harness, which is why Task 41 measured everything about it that a static can hold.

**Interfaces:**
- Consumes: `DiagnoseComponent.Entry`, `IsOurs` and `InOrder` from Task 41; `Collect`, `Group` and `Render` unchanged at `:107-259`.
- Produces:
  - `internal static List<Entry> DiagnoseComponent.Scan(GH_Document document, IGH_DocumentObject self)`
  - `internal static List<(Entry Owner, List<(string Code, string Severity, string Message)> Lines)> DiagnoseComponent.DocumentEntries(IEnumerable<Entry> entries)`
  - `internal static string DiagnoseComponent.RenderDocument(IReadOnlyList<Entry> scanned, IReadOnlyList<(Entry Owner, List<(string Code, string Severity, string Message)> Lines)> made)`
  - `private bool _documentMode` on the component, set where rule 6.3 decides the mode. Task 43's handler reads that field and must not run a second test of its own.

- [ ] **Step 1: Write the scan and the render**

Add to `plugin/native_v02/Components/DiagnoseComponents.cs` immediately after `Digest`:

```csharp
        /// <summary>
        /// Every one of OUR components on the document, and everything each
        /// has to say: its three message lists and its chin.
        ///
        /// document.Objects is documented as a list of all normal, TOP-LEVEL
        /// objects, so a component inside a cluster is not read. Descending
        /// would mean calling GH_Cluster.Document(String password), and what
        /// that should do with a cluster that has a password is a question
        /// nobody has answered, so the exclusion is deliberate and the
        /// component's own description says so.
        ///
        /// The scanning instance skips ITSELF. It must not report its own
        /// chin or its own messages, which would otherwise change on every
        /// scan and keep the document scheduling for ever.
        /// </summary>
        internal static List<Entry> Scan(
            GH_Document document,
            IGH_DocumentObject self)
        {
            var entries = new List<Entry>();
            foreach (IGH_DocumentObject item in document.Objects)
            {
                if (ReferenceEquals(item, self) || !IsOurs(item))
                    continue;

                // THREE calls per object, because there is no all-levels
                // overload: the method takes one level and the enum has four
                // members, of which Blank is the nothing-recorded state
                // rather than a list.
                var remarks = new List<string>();
                var warnings = new List<string>();
                var errors = new List<string>();
                if (item is IGH_ActiveObject active)
                {
                    remarks.AddRange(
                        active.RuntimeMessages(GH_RuntimeMessageLevel.Remark));
                    warnings.AddRange(
                        active.RuntimeMessages(GH_RuntimeMessageLevel.Warning));
                    errors.AddRange(
                        active.RuntimeMessages(GH_RuntimeMessageLevel.Error));
                }
                // The chin is GH_Component.Message, so it needs the
                // component cast rather than the active-object one.
                string chin = item is GH_Component component
                    ? component.Message ?? string.Empty
                    : string.Empty;

                entries.Add(new Entry(
                    item.InstanceGuid,
                    item.Name ?? string.Empty,
                    item.NickName ?? string.Empty,
                    remarks,
                    warnings,
                    errors,
                    chin));
            }
            return entries;
        }

        /// <summary>
        /// The scan turned into the report's rows: one row per message and
        /// one for the chin, in the error, warning, info order the existing
        /// Rank gives, with a component that has nothing to say dropped.
        ///
        /// Runtime messages carry no code, so one is synthesised. This keeps
        /// the Code port's documented promise that a code is namespaced by
        /// its source in spirit, and says plainly that the entry came from
        /// the balloon rather than from a Result. Remark maps to "info" and
        /// so does the chin, because Diagnose's own vocabulary is ok, info,
        /// warning, error and has no "remark".
        /// </summary>
        internal static List<(Entry Owner,
            List<(string Code, string Severity, string Message)> Lines)>
            DocumentEntries(IEnumerable<Entry> entries)
        {
            var made = new List<(Entry,
                List<(string, string, string)>)>();
            foreach (Entry entry in InOrder(entries))
            {
                var lines = new List<(string, string, string)>();
                foreach (string message in entry.Errors)
                    lines.Add(("runtime.error", "error", message));
                foreach (string message in entry.Warnings)
                    lines.Add(("runtime.warning", "warning", message));
                foreach (string message in entry.Remarks)
                    lines.Add(("runtime.remark", "info", message));
                if (!string.IsNullOrWhiteSpace(entry.Chin))
                    lines.Add(("runtime.chin", "info", entry.Chin));
                if (lines.Count > 0)
                    made.Add((entry, lines));
            }
            return made;
        }

        /// <summary>
        /// The Text port in document mode: one block per component that has
        /// something to say, then a closing line naming how many of ours
        /// were found and how many had nothing to say.
        ///
        /// The heading carries the first eight characters of the
        /// InstanceGuid where the nickname is NOT unique on the canvas. Two
        /// of the same component must be distinguishable in what the author
        /// reads, and the nickname alone cannot do it: every instance of one
        /// component type ships the same nickname from its base constructor,
        /// so two Deconstructs give two blocks both reading "DE".
        ///
        /// There is no "solver report:" block and no "not yet run on this
        /// Result:" block here. Both read a Result and there is none.
        /// </summary>
        internal static string RenderDocument(
            IReadOnlyList<Entry> scanned,
            IReadOnlyList<(Entry Owner,
                List<(string Code, string Severity, string Message)> Lines)> made)
        {
            if (scanned.Count == 0)
            {
                return
                    "No Ananke component is on this canvas, so there is "
                    + "nothing to read. Wire a Result in to read one chain "
                    + "instead.";
            }

            var repeated = new HashSet<string>(
                scanned
                    .GroupBy(entry => entry.Nick, StringComparer.Ordinal)
                    .Where(group => group.Count() > 1)
                    .Select(group => group.Key),
                StringComparer.Ordinal);

            var text = new StringBuilder();
            foreach ((Entry owner, var lines) in made)
            {
                string heading = repeated.Contains(owner.Nick)
                    ? $"{owner.Nick} ({owner.Name}) " +
                      owner.Instance.ToString("N").Substring(0, 8)
                    : $"{owner.Nick} ({owner.Name})";
                text.AppendLine(heading + ":");
                foreach ((string _, string severity, string message) in lines)
                {
                    if (string.Equals(severity, "info", StringComparison.Ordinal) &&
                        ReferenceEquals(message, owner.Chin))
                    {
                        text.Append("  chin: ").AppendLine(message);
                        continue;
                    }
                    text.Append("  [").Append(severity).Append("] ")
                        .AppendLine(message);
                }
                text.AppendLine();
            }

            int quiet = scanned.Count - made.Count;
            text.AppendLine(
                $"{scanned.Count} Ananke component(s) on this canvas, "
                + $"{quiet} with nothing to say. Components inside a cluster "
                + "are not read.");
            return text.ToString().TrimEnd();
        }
```

The chin line is told apart by reference equality against `owner.Chin`, which is the same string instance `DocumentEntries` put in the row, so a Remark whose text happens to equal the chin is still printed as a Remark.

- [ ] **Step 2: Branch SolveInstance**

Replace `DiagnoseComponents.cs:81-99`, the whole of `SolveInstance`, with:

```csharp
        // WHICH MODE THE LAST SOLVE RAN IN, recorded on the component where
        // rule 6.3 decides it. The SolutionEnd handler reads THIS rather
        // than running a second test of its own: a Result wire that is
        // present but carries nothing, because the upstream solver errored
        // or is disabled, puts the component in document mode, and a handler
        // testing SourceCount would refuse to expire it. The scan would then
        // be computed once and frozen for the rest of the session.
        private bool _documentMode;

        protected override void SolveInstance(IGH_DataAccess data)
        {
            ResultGoo? goo = null;
            if (data.GetData(0, ref goo) && goo?.Value is ResultDto result)
            {
                _documentMode = false;
                SolveChain(data, result);
                return;
            }

            _documentMode = true;
            SolveDocument(data);
        }

        /// <summary>
        /// Chain mode, unchanged: one Result, read exactly.
        /// </summary>
        private void SolveChain(IGH_DataAccess data, ResultDto result)
        {
            List<DiagnosticDto> all = Collect(result);

            IReadOnlyList<(string Source, List<DiagnosticDto> Entries)> groups = Group(all);
            data.SetData(0, Render(result, all));
            data.SetDataTree(1, OutputTree.Strings(groups.Select(g => g.Entries.Select(_ => g.Source))));
            data.SetDataTree(2, OutputTree.Strings(groups.Select(g => g.Entries.Select(e => e.Code))));
            data.SetDataTree(3, OutputTree.Strings(groups.Select(g => g.Entries.Select(e => e.Severity))));
            data.SetDataTree(4, OutputTree.Strings(groups.Select(g => g.Entries.Select(e => e.Message))));
            data.SetDataTree(5, OutputTree.Numbers(groups.Select(g => g.Entries.Select(e => e.Value ?? double.NaN))));
            Message = all.Any(e => e.Severity == "error") ? "errors"
                : all.Any(e => e.Severity == "warning") ? $"{all.Count(e => e.Severity == "warning")} warnings"
                : "clean";
        }

        /// <summary>
        /// Document mode: the same six ports, filled from the canvas.
        ///
        /// Value is NaN throughout, because runtime messages carry no
        /// number and the port already documents NaN as the placeholder that
        /// keeps the tree aligned with Message.
        /// </summary>
        private void SolveDocument(IGH_DataAccess data)
        {
            GH_Document? document = OnPingDocument();
            if (document is null)
            {
                Message = "no document";
                return;
            }

            List<Entry> scanned = Scan(document, this);
            var made = DocumentEntries(scanned);

            data.SetData(0, RenderDocument(scanned, made));
            data.SetDataTree(1, OutputTree.Strings(
                made.Select(one => one.Lines.Select(_ => one.Owner.Nick))));
            data.SetDataTree(2, OutputTree.Strings(
                made.Select(one => one.Lines.Select(line => line.Code))));
            data.SetDataTree(3, OutputTree.Strings(
                made.Select(one => one.Lines.Select(line => line.Severity))));
            data.SetDataTree(4, OutputTree.Strings(
                made.Select(one => one.Lines.Select(line => line.Message))));
            data.SetDataTree(5, OutputTree.Numbers(
                made.Select(one => one.Lines.Select(_ => double.NaN))));

            // The same chin rule as chain mode, computed over the scan.
            int warnings = made
                .SelectMany(one => one.Lines)
                .Count(line => string.Equals(
                    line.Severity, "warning", StringComparison.Ordinal));
            bool errors = made
                .SelectMany(one => one.Lines)
                .Any(line => string.Equals(
                    line.Severity, "error", StringComparison.Ordinal));
            Message = errors ? "errors"
                : warnings > 0 ? $"{warnings} warnings"
                : "clean";

            _emitted = Digest(scanned);
        }
```

`_emitted` is declared by Task 43. Until then this line does not compile, so add it as a field beside `_documentMode` in this task and let Task 43 use it:

```csharp
        // The digest of what was last EMITTED, not of what was last
        // computed. The SolutionEnd handler compares against this, so a
        // scheduled solve that produced the same report stops the chain
        // rather than starting another.
        private string _emitted = string.Empty;
```

- [ ] **Step 3: Rewrite the component description**

Replace the description string at `DiagnoseComponents.cs:32-35` with:

```csharp
                "Read every diagnostic the chain wrote into a Result and say "
                    + "in plain English what is wrong and which lever to "
                    + "pull. Wire a Result in and this reports that chain "
                    + "alone. Leave it UNWIRED and it reads the whole "
                    + "document instead, every Ananke component's warnings, "
                    + "errors, remarks and chin, and settles one solve "
                    + "behind: what you see is the state at the end of the "
                    + "previous solution. Wire a Result in when you want a "
                    + "guaranteed reading of one chain. Components inside a "
                    + "cluster are not read, and the diagnostics carried "
                    + "INSIDE a Result are read only in chain mode.",
```

Rule 6.9 is what the last clause states: document mode does not read the diagnostics carried inside a Result. They are reachable through each scanned component's output parameters' volatile data, and the rule chooses not to read them, for three reasons: a scan reads volatile data left by the PREVIOUS solution, so the entries would be one solution old; a wired Diagnose already reads them exactly; and the same Result travels down several wires, so a document-wide harvest would report one study's entries many times over unless it deduped by identity. That choice is question 12B(c) and is the spec's rather than Param's. If he wants the harvest, `DocumentEntries` gains a seventh source of rows and the staleness has to be said on the face of the report.

- [ ] **Step 4: Run the gate**

Green. Nothing in this task is reachable from the harness, which is why Task 41 measured every static behind it; the manual confirmation is Task 43's.

- [ ] **Step 5: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/DiagnoseComponents.cs"
git -C $repo commit -m "feat(diagnose): an unwired Diagnose reads the whole document"
```

---

### Task 43: The solution-order trap

Spec section 7. This is the part most likely to be got wrong, and the problem is not "one solve behind". Grasshopper solves only EXPIRED objects, so a component with no wired input is never expired by upstream data and holds its FIRST answer for the rest of the session. The plugin already ships proof that this is real rather than theoretical: Backend Health registers no inputs at all (`FormFindingComponents.cs:33-36`) and carries no expiry mechanism of any kind.

The remedy is TWO-PART. Something must EXPIRE Diagnose when the document changes, AND the re-solve must be SCHEDULED rather than forced. Either half alone fails: expiry without scheduling recomputes inside a running solution, and scheduling without expiry schedules a solution in which Diagnose is not expired and therefore does not run.

Four exact values the spec fixes and this task must carry:

- The event is `GH_Document.SolutionEnd`, "raised whenever a new solution request has been handled. Even if the document is locked" (`Grasshopper.xml:25171`). It is the one event that fires after every solve, which is exactly when the messages Diagnose reads have just been rewritten. `ObjectsAdded` (`:24479`) and `ObjectsDeleted` (`:24486`) are not sufficient on their own: a component's messages change without any object being added or removed.
- The pairing is `document.ScheduleSolution(5, _ => ExpireSolution(false))`, from a callback OUTSIDE `SolveInstance`, with a null-document guard first. This is the plugin's existing precedent at `DeliveryComponents.cs:209-217`. `ExpireSolution(true)` recomputes on the spot and is the classic loop.
- The delay is 5, NEVER 0. A delay of 0ms is documented as running the next solution RECURSIVELY within the current one, with an explicit stack-space warning (`Grasshopper.xml:25320-25327`, repeated on both overloads).
- The cap is THREE consecutive scheduled re-solves. A foreign component whose messages genuinely change on every solve would make the digest differ for ever, and the latch alone would schedule for ever.

Diagnose expires ITSELF ONLY, never the document and never a scanned object. Expiring a component CLEARS its runtime messages before `SolveInstance` runs, which the base class records at `NativeComponentBase.cs:631-637` and again at `:790-808`; if Diagnose expired the document it would wipe the very messages it went back to read.

**Files:**
- Modify: `plugin/native_v02/Components/DiagnoseComponents.cs` (the fields, `AddedToDocument`, `RemovedFromDocument`, the handler, a `FirstChanged` static, and `SolveDocument` recording the emitted scan)
- Modify: `tests/native_smoke/Program.cs` (`FirstChanged` folded into the existing `ValidateDiagnoseDigest` from Task 41)
- Test: `ValidateDiagnoseDigest` extended; the settling behaviour itself is a MANUAL check in Rhino, recorded as such by rule 10.3(j)

**Interfaces:**
- Consumes: `Digest`, `Scan`, `InOrder` and `Entry` from Tasks 41 and 42; `_documentMode` and `_emitted` from Task 42; `NativeComponentBase.AddedToDocument(GH_Document)` at `:651`.
- Produces: `internal static string? DiagnoseComponent.FirstChanged(IReadOnlyList<Entry> before, IReadOnlyList<Entry> after)`, returning the nickname of the first component whose own reading changed, or null when nothing did.

- [ ] **Step 1: Extend the digest check first, and watch it fail**

Add to the end of `ValidateDiagnoseDigest` in `tests/native_smoke/Program.cs`, written in Task 41, before its closing brace:

```csharp
        MethodInfo firstChanged = RequireStatic(diagnose, "FirstChanged");
        string? Changed(object before, object after) =>
            (string?)firstChanged.Invoke(null, new[] { before, after });

        if (Changed(first, changed) is not "BB")
        {
            throw new InvalidOperationException(
                "When the document will not settle, Diagnose names the "
                + "component whose entry changed, or the Remark says only "
                + "that something is oscillating and leaves the author "
                + $"hunting for it; got '{Changed(first, changed)}'.");
        }
        if (Changed(first, same) is not null)
        {
            throw new InvalidOperationException(
                "Two identical scans have no changed component to name.");
        }
        if (Changed(first, inserted) is not "CC")
        {
            throw new InvalidOperationException(
                "A component that appears where there was none is a change, "
                + "and it is the one to name; got "
                + $"'{Changed(first, inserted)}'.");
        }
```

Extend the PASS text for that check, appending to its last clause:

```csharp
                + " FirstChanged names the component whose reading moved, "
                + "and says nothing when none did.");
```

Run the gate. It must fail with `DiagnoseComponent.FirstChanged was not found.`

- [ ] **Step 2: Write FirstChanged**

Add to `plugin/native_v02/Components/DiagnoseComponents.cs` immediately after `Digest`:

```csharp
        /// <summary>
        /// The nickname of the first component whose own reading changed
        /// between two scans, or null when none did.
        ///
        /// A document that will not settle is a document where something
        /// else is oscillating, and Diagnose should say WHICH rather than
        /// spin. Compared in InOrder so the answer does not depend on the
        /// order document.Objects happened to hand the two scans back.
        /// </summary>
        internal static string? FirstChanged(
            IReadOnlyList<Entry> before,
            IReadOnlyList<Entry> after)
        {
            var was = new Dictionary<Guid, string>();
            foreach (Entry entry in before)
                was[entry.Instance] = Digest(new[] { entry });
            foreach (Entry entry in InOrder(after))
            {
                string now = Digest(new[] { entry });
                if (!was.TryGetValue(entry.Instance, out string? then) ||
                    !string.Equals(then, now, StringComparison.Ordinal))
                {
                    return entry.Nick;
                }
            }
            return null;
        }
```

- [ ] **Step 3: Subscribe, latch and cap**

Add the remaining fields beside `_documentMode` and `_emitted` in `DiagnoseComponents.cs`:

```csharp
        // The scan as it was last EMITTED, kept so the unsettled Remark can
        // name the component whose entry moved rather than saying only that
        // something did.
        private List<Entry> _emittedScan = new();

        // Consecutive scheduled re-solves without the digest settling. Reset
        // whenever the digest matches.
        private int _unsettled;

        // The document this instance is subscribed to. Held rather than
        // re-read, so RemovedFromDocument detaches from the same object
        // AddedToDocument attached to.
        private GH_Document? _watched;
```

Add the two overrides after `ComponentGuid` at `:41-42`:

```csharp
        /// <summary>
        /// Something must EXPIRE this component when the document changes,
        /// or it holds its first answer for the rest of the session:
        /// Grasshopper solves only EXPIRED objects, and an unwired component
        /// is never expired by upstream data. SolutionEnd is the one event
        /// that fires after every solve, which is exactly when the messages
        /// this reads have just been rewritten.
        /// </summary>
        public override void AddedToDocument(GH_Document document)
        {
            base.AddedToDocument(document);
            if (_watched is not null)
                _watched.SolutionEnd -= OnSolutionEnd;
            _watched = document;
            document.SolutionEnd += OnSolutionEnd;
        }

        /// <summary>
        /// A component deleted from the canvas must leave no handler
        /// running, and must not schedule a solution for a document it is no
        /// longer on.
        /// </summary>
        public override void RemovedFromDocument(GH_Document document)
        {
            if (_watched is not null)
            {
                _watched.SolutionEnd -= OnSolutionEnd;
                _watched = null;
            }
            base.RemovedFromDocument(document);
        }

        /// <summary>
        /// The anti-loop condition, which is where components like this
        /// fail. Scheduling unconditionally means the scheduled solution
        /// ends, raises SolutionEnd, schedules another, and the document
        /// never rests. THE LATCH IS ON THE CONTENT: schedule only when the
        /// scan's digest differs from the digest last EMITTED.
        ///
        /// SCHEDULE, NEVER RECOMPUTE. ExpireSolution(true) recomputes on the
        /// spot and is the classic loop; scheduling asks the document for
        /// the re-solve on its own terms, and a component with no document
        /// does nothing at all. The delay is 5 and never 0: a delay of 0ms
        /// runs the next solution RECURSIVELY inside the current one, with
        /// an explicit stack-space warning in Grasshopper's own
        /// documentation.
        ///
        /// EXPIRE ITSELF ONLY. Expiring a component clears its runtime
        /// messages before SolveInstance runs, so expiring the document
        /// would wipe the very messages this went back to read.
        ///
        /// The mode test is the FIELD the last solve recorded, not
        /// SourceCount. A Result wire that is present but carries nothing,
        /// because the upstream solver errored or is disabled, puts
        /// SolveInstance in document mode; a handler testing SourceCount
        /// would refuse to expire, and the scan would be computed once and
        /// frozen for the rest of the session, which is the very failure
        /// this exists against.
        /// </summary>
        private void OnSolutionEnd(object sender, GH_SolutionEventArgs e)
        {
            if (!_documentMode)
                return;
            GH_Document? document = OnPingDocument();
            if (document is null)
                return;

            List<Entry> scanned = Scan(document, this);
            if (string.Equals(Digest(scanned), _emitted, StringComparison.Ordinal))
            {
                _unsettled = 0;
                return;
            }
            if (_unsettled >= 3)
            {
                string? changed = FirstChanged(_emittedScan, scanned);
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Remark,
                    "This document did not settle after three re-solves, so "
                    + "Diagnose has stopped asking for another. Something on "
                    + "the canvas changes what it says on every solve"
                    + (changed is null
                        ? "."
                        : $", and the first to do so is {changed}.")
                    + " What you see below is one solve old.");
                return;
            }
            _unsettled++;
            document.ScheduleSolution(5, _ => ExpireSolution(false));
        }
```

`SolveDocument`, from Task 42, records what it emitted; replace its last line with:

```csharp
            _emitted = Digest(scanned);
            _emittedScan = scanned;
            _unsettled = 0;
```

If the compiler refuses the `+=` on `SolutionEnd`, the delegate `GH_Document.SolutionEndEventHandler` takes a different parameter list from `(object, GH_SolutionEventArgs)` and the error names what it wants; match `OnSolutionEnd`'s signature to it and change nothing else. The type is present in `Grasshopper.dll`, confirmed 2026-09-01.

- [ ] **Step 4: Run the gate**

Green, with the extended digest PASS line.

- [ ] **Step 5: The manual check in Rhino**

Rule 10.3(j): the settling behaviour cannot be measured without Grasshopper. Close Rhino, install the built plugin, reopen Rhino, and confirm all of the following on a canvas.

1. Place Diagnose UNWIRED on a canvas holding a failing chain. The report appears.
2. The document SETTLES WITHIN TWO SOLVES: solve one produces the answer, solve two confirms the digest is unchanged and schedules nothing. Anything that settles in three or more, or does not settle, is a defect in the digest and not a tuning problem.
3. Rhino's CPU does not sit busy afterwards.
4. Delete a component and confirm the report updates on the next solve.
5. THE BROKEN-UPSTREAM CASE: wire a Result in, then disable the upstream solver so the wire carries nothing, and confirm the report still updates rather than freezing on its first answer. This is the case a SourceCount test would have got wrong.
6. Beside these, since the harness measures the statics behind them rather than the raising of them: the divergence Warning of rule 3.7 and the stray Warning of rule 4.3 are seen on the merged reader's balloon, and rule 1.6A's partitioning is seen by feeding a Result one half refuses and reading which half's ports came back and what the chin says.

Record the outcome in the commit message. If step 2 settles in three or more, do not tune the delay: the digest is carrying something that changes on every solve, and the component to look at is the one `FirstChanged` names in the Remark.

- [ ] **Step 6: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/DiagnoseComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(diagnose): expire on SolutionEnd, latch on content, cap at three"
```

---

### Task 44: The Remark prerequisite, checked in Rhino

Spec rules 6.6(f) and 10.3(k). THIS IS A PREREQUISITE RATHER THAN A VERIFICATION: it is run BEFORE Tasks 45 and 46 are built, and the controller's ruling makes that ordering binding rather than advisory.

**MANUAL, LIKE TASK 28 STEP 5, AND WITH A STATED DEFAULT.** Steps 1 and 2 need Param at a keyboard with Rhino open, so an unattended run cannot take them. AN UNATTENDED RUN TAKES THE FALLBACK OF STEP 4: every line named there goes to WARNING level, Tasks 45 and 46 are built to Warning, and step 3 records in the spec that the check was not taken and that the fallback was assumed. That is the safe direction, because a Warning is certainly retrievable by the document scan while a Remark is the thing in question; what it costs is named in step 4 and is a yellow balloon on a successful import and a successful push. If the check is later taken and Remarks do come back, moving those lines from Warning to Remark is a one-line change per line in Tasks 45 and 46 and nothing else moves.

The shipped documentation for `AddRuntimeMessage` says "Valid message type flags are Warning and Error" and "Only Warnings and Errors are recorded" (`Grasshopper.xml:8909-8915` for the interface, `:9021-9028` for `GH_ActiveObject`). The plugin nevertheless adds Remarks (`VisualiseComponents.cs:1287-1296`) and its comment assumes an author sees them. The documentation and the shipped code disagree, and nothing in either settles which is right, so this cannot be resolved by reading.

**Files:**
- Modify: `docs/superpowers/specs/2026-09-01-readers-merge-design.md` (rule 10.3(k) records the answer; everything in section 8 that a later round reads depends on which way it went)
- Test: a manual check in Rhino, with Diagnose's own document scan as the instrument

**Interfaces:**
- Consumes: Diagnose's document mode from Tasks 42 and 43; Display's two shipped Remarks at `VisualiseComponents.cs:1285-1297`.
- Produces: the answer, recorded in the spec. Tasks 45 and 46 read it to decide whether their retired content is raised at Remark level or at Warning level.

- [ ] **Step 1: Build and install with Rhino closed**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
Get-Process -Name "Rhino" -ErrorAction SilentlyContinue
```

That must print nothing before installing. Then build and install the plugin as the repo's install step does, and reopen Rhino afterwards.

- [ ] **Step 2: Run the check**

On a canvas, place Display and feed it an FD Result. Display raises "FD result: no reciprocal diagram." as a Remark at `VisualiseComponents.cs:1285-1297`, under a comment explaining that these are Display's own readings which no other component can say. Place Diagnose UNWIRED beside it.

Confirm that Diagnose's Text output carries that sentence as an `[info]` line under Display's block, which is the same question as: does `RuntimeMessages(GH_RuntimeMessageLevel.Remark)` return what `AddRuntimeMessage(Remark, ...)` placed there?

- [ ] **Step 3: Record the answer in the spec**

Edit rule 10.3(k) in `docs/superpowers/specs/2026-09-01-readers-merge-design.md` to state the answer and the date it was taken, in plain prose, in the file's own voice. The spec asks for this explicitly, because everything in section 8 that a later round reads depends on which way it went.

- [ ] **Step 4: If it comes back empty, take the fallback**

Rule 6.6(c) fails, and the fallback is already written out line by line so taking it is mechanical rather than a redesign. Every line named below goes to WARNING level instead of Remark, and nothing else in Tasks 45 and 46 changes. The lines are exactly these and there are no others:

1. IMPORT PIECES' nine roll-up lines: schema, units, piece count, courses, thickness, the degenerate_dropped keys, the metres factor, whether base_mesh was present, the branch-path note.
2. EXPORT'S live lines, one per kind (`DeliveryComponents.cs:627-632`).

Import Pieces' per-piece failure Warnings and Export's existing Warnings are already Warnings and do not move.

WHAT THE FALLBACK COSTS, named now rather than discovered on the canvas: a successful import and a successful push each turn their component's balloon yellow, and Diagnose's chin, which counts warnings, reads "<n> warnings" on a document where nothing is wrong.

TWO THINGS THE FALLBACK DOES NOT COVER. Display's own two Remarks are not retired content, so they stay Remarks and the document scan stops seeing them; that is a loss this round did not create and does not repair, and whether to promote them too is question 12B(f), contingent on this check. Do not put that question to Param unless the check comes back empty. And rule 7.3(h)'s Remark, which Diagnose adds to ITSELF when the document will not settle, is for the balloon rather than for the scan, which skips its own instance, so it is unaffected either way.

- [ ] **Step 5: Commit the recorded answer**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "docs/superpowers/specs/2026-09-01-readers-merge-design.md"
git -C $repo commit -m "docs(readers): record whether a document scan retrieves Remarks"
```

---

### Task 45: Import Pieces' Diagnostics port retires to runtime messages

Spec rules 8.2(a), 8.4, 8.5 and 10.2(j), measured by the first half of rule 10.3(l). A component should raise its problems where the author already looks rather than hand back a text output that must be wired to a panel to be read. Import Pieces' Diagnostics is the ONE port this round deletes.

Param's ruling settles the form: the retired content becomes RUNTIME MESSAGES ONLY. The second half of the original ruling, "runtime messages and diagnostics entries", is not possible for this component and he has confirmed that reading: a diagnostics entry in this plugin lives inside a `ResultDto` (`ResultDiagnostics.cs:10-18`), Import Pieces' only input is a Path (`PiecesComponents.cs:105-114`), and there is no Result anywhere in its chain to write into even in principle.

ONE MESSAGE PER FACT, NOT ONE PER PORT, because Diagnose's document scan emits one tree item per message, so a single Remark holding a nine-line block and nine Remarks look completely different on the canvas.

**Files:**
- Modify: `plugin/native_v02/Components/PiecesComponents.cs:147-164` (the Diagnostics registration deleted and the Base Mesh description repointed), `:555-562` (the emit), `:641-687` (`BuildDiagnostics` reshaped into a line list)
- Modify: `tests/native_smoke/Program.cs:274-282` (the Import Pieces output nicknames), plus a new `ValidateImportPiecesMessages` with its PASS block
- Test: `ValidateImportPiecesMessages`

**Interfaces:**
- Consumes: nothing from earlier tasks. The answer recorded by Task 44 decides the level.
- Produces: `internal static List<string> ImportPiecesComponent.DiagnosticLines(PiecesDocument document, double unitFactor, bool baseMeshPresent, Mesh? baseMesh)`, the nine roll-up lines as separate strings. `BuildDiagnostics` and the `failedKeys` parameter go with the port.

- [ ] **Step 1: Rewrite the pin and write the check first, and watch both fail**

Replace `tests/native_smoke/Program.cs:274-282`, the Import Pieces entry, with:

```csharp
                ["Ananke.COMPAS.Native.Components.ImportPiecesComponent"] = (
                    "Import Pieces",
                    "Pieces",
                    "05 Deliver",
                    new[] { "P" },
                    // Addendum, 2026-08-20: the flat Courses (C) output is
                    // removed; M/K/S are trees branched by course, B is
                    // the new base-mesh item. 2026-09-01: Diagnostics (D)
                    // is removed too. It was the LAST output, slot 4 of 5,
                    // so removing it is a pure truncation and no surviving
                    // port changes index; its content is raised as runtime
                    // messages, one per fact, and read off Diagnose's
                    // document scan.
                    new[] { "M", "K", "S", "B" })
```

Add the check after `ValidateDiagnoseDigest`:

```csharp
    /// <summary>
    /// Import Pieces' retired Diagnostics content still EXISTS, as runtime
    /// messages, one per fact.
    ///
    /// Without this, "it moves to the balloon" is a plan rather than a fact.
    /// The nine roll-up lines are asserted as SEPARATE strings rather than
    /// as one block, because Diagnose's document scan emits one tree item
    /// per message: a single message holding nine lines and nine messages
    /// look completely different on the canvas, and the choice must not be
    /// left open.
    ///
    /// The per-piece failure Warning is not measured here. It is raised from
    /// BuildOutputs against a live IGH_DataAccess, and this harness never
    /// calls SolveInstance on anything.
    /// </summary>
    private static void ValidateImportPiecesMessages(Assembly plugin)
    {
        Type pieces = RequireComponentType(plugin, "ImportPiecesComponent");
        MethodInfo lines = RequireStatic(pieces, "DiagnosticLines");
        Type documentType = lines.GetParameters()[0].ParameterType;

        // PiecesDocument is a POSITIONAL record with eight required
        // constructor parameters and no parameterless one
        // (PiecesComponents.cs:50-58), so it is built through its real
        // constructor. CreateInstance is a bare Activator.CreateInstance(type)
        // and would throw MissingMethodException here; and property sets
        // would leave Pieces and DegenerateDropped NULL, which DiagnosticLines
        // dereferences for its piece count and its dropped-keys line.
        Type pieceRecord = RequireComponentType(plugin, "PieceRecord");
        object document = Activator.CreateInstance(
            documentType,
            new object?[]
            {
                "bench.pieces/1",                                   // Schema
                "m",                                                // Units
                4,                                                  // Courses
                0,                                                  // PieceCount
                0.06,                                               // Thickness
                Array.CreateInstance(typeof(string), 0),            // DegenerateDropped
                Array.CreateInstance(pieceRecord, 0),               // Pieces
                null                                                // BaseMesh
            })!;
                null, new object?[] { document, 1000.0, false, null })!)
            .Cast<string>()
            .ToArray();
        if (made.Length != 9)
        {
            throw new InvalidOperationException(
                "NINE roll-up lines, one per fact: schema, units, piece "
                + "count, courses, thickness, the degenerate_dropped keys, "
                + "the metres factor, whether base_mesh was present, and the "
                + $"branch-path note. Got {made.Length}.");
        }
        if (made.Any(string.IsNullOrWhiteSpace))
        {
            throw new InvalidOperationException(
                "Every line carries a fact; an empty one is a message an "
                + "author reads as a blank in Diagnose's report.");
        }
        foreach (string wanted in new[]
                 {
                     "bench.pieces/1", "units", "pieces", "courses",
                     "thickness", "degenerate_dropped", "unit factor",
                     "base_mesh", "branch path"
                 })
        {
            if (!made.Any(line => line.Contains(
                    wanted, StringComparison.OrdinalIgnoreCase)))
            {
                throw new InvalidOperationException(
                    $"The roll-up still names '{wanted}'; the port went, the "
                    + "content did not.");
            }
        }
    }
```

Register it:

```csharp
        try
        {
            ValidateImportPiecesMessages(plugin);
            Console.WriteLine(
                "PASS  Import Pieces messages: the nine roll-up lines the "
                + "retired Diagnostics port carried still exist, as nine "
                + "SEPARATE strings rather than one block, so Diagnose's "
                + "document scan reports them as nine entries.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Import Pieces messages: {DescribeException(exception)}");
        }
```

Run the gate. It must fail on the output nickname pin and on `ImportPiecesComponent.DiagnosticLines was not found.`

- [ ] **Step 2: Turn the block into lines**

Replace `BuildDiagnostics` at `plugin/native_v02/Components/PiecesComponents.cs:641-687` with:

```csharp
    /// <summary>
    /// The roll-up, as NINE separate lines rather than one block.
    ///
    /// The Diagnostics output that carried this went on 2026-09-01: a
    /// component should raise its problems where the author already looks
    /// rather than hand back a text output that has to be wired to a panel
    /// to be read. One message per FACT, because Diagnose's document scan
    /// emits one tree item per message and a single message holding nine
    /// lines reads as one entry on the canvas.
    ///
    /// The per-piece failure line is not here: it is a real fault rather
    /// than a reading, and it is raised as a WARNING by the caller.
    /// </summary>
    internal static List<string> DiagnosticLines(
        PiecesDocument document,
        double unitFactor,
        bool baseMeshPresent,
        Mesh? baseMesh)
    {
        return new List<string>
        {
            $"schema: {document.Schema}",
            $"units: {document.Units}",
            $"pieces: {document.Pieces.Count}",
            $"courses: {document.Courses}",
            "thickness: " +
                document.Thickness.ToString("0.####", CultureInfo.InvariantCulture) +
                " m",
            document.DegenerateDropped.Count > 0
                ? "degenerate_dropped: " +
                  string.Join(", ", document.DegenerateDropped)
                : "degenerate_dropped: none",
            "unit factor applied (m -> doc units): " +
                unitFactor.ToString(
                    "0.################",
                    CultureInfo.InvariantCulture),
            !baseMeshPresent
                ? "base_mesh: absent (this export predates the " +
                  "base_mesh addendum; B is null)"
                : baseMesh is not null
                    ? "base_mesh: present; B carries it"
                    : "base_mesh: present but failed to build a valid " +
                      "mesh; B is null",
            // Addendum, 2026-08-20: Meshes/Keys/Supports are trees; the
            // branch path IS the course (0-up from the rim), replacing
            // the removed flat Courses (C) output.
            "Meshes/Keys/Supports are trees: branch path = course; " +
                "branches need not be contiguous and are never " +
                "pre-created for a course with no pieces."
        };
    }
```

The list is ordered so that the base_mesh line precedes the branch-path note, which is the order the check reads them in; the port's own text listed them the other way round and nothing depended on it.

- [ ] **Step 3: Delete the port and raise the messages**

Delete the Diagnostics registration at `PiecesComponents.cs:155-164` in full. In the Base Mesh description at `:147-154`, replace "(an export written before the addendum stays loadable; see Diagnostics)." with "(an export written before the addendum stays loadable; the component says so in its own messages, which Diagnose reads)."

Replace the emit block at `:555-572` with:

```csharp
        data.SetDataTree(0, meshTree);
        data.SetDataTree(1, keyTree);
        data.SetDataTree(2, supportTree);
        data.SetData(3, baseMesh);

        // The roll-up goes to the BALLOON, one message per fact, where
        // Diagnose's document scan reads it. A Remark cannot be wired, which
        // is the whole objection to sending anything there, and it is
        // answered here by the reading not being data: nothing downstream
        // ever consumed this text.
        foreach (string line in DiagnosticLines(
                     document, unitFactor, baseMeshPresent, baseMesh))
        {
            AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, line);
        }

        if (failedKeys.Count > 0)
        {
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Warning,
                $"Import Pieces: {failedKeys.Count} piece(s) failed to " +
                $"build ({string.Join(", ", failedKeys)}); Meshes carries " +
                "a null placeholder at each, in its own course branch, " +
                "so Keys/Supports stay aligned within that branch.");
        }
```

The per-piece failure stays a WARNING and is unchanged. If Task 44's check came back empty, `GH_RuntimeMessageLevel.Remark` above becomes `GH_RuntimeMessageLevel.Warning` and nothing else in this task changes.

Update the `BuildOutputs` doc comment at `:479-487` so its last clause reads "plus the optional Base Mesh item; the roll-up goes to the balloon as one message per fact."

- [ ] **Step 4: Run the gate**

Green. `ParameterIdentity.Mismatch` reports a count change on a saved definition, naming the removed port and closing "wires may now sit on the wrong port". That close is harsher than the truth here, because Diagnostics was the LAST output and nothing above it moved, but the pure-append branch only softens the message for ADDITIONS. A pure-truncation branch would be the honest counterpart and is recorded by the spec as an optional improvement, not required by this round.

- [ ] **Step 5: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/PiecesComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(import-pieces): the Diagnostics port retires to runtime messages"
```

---

### Task 46: Export's Status narrows to the written paths

Spec rules 8.2(b), 8.5, 8.6(b) and 8.6(c), measured by both halves of rule 10.3(l). The port is NARROWED, not removed, and that is the controller's ruling rather than Param's: the written-file paths stay wireable data. An author needs the path of the file he has just written AS DATA, to open it, to copy it, to feed a File Path or a downstream write, and a message cannot be wired into anything. They are also not a diagnostic: they are the product of the run.

EXPORT'S STATUS CARRIES THREE THINGS, NOT TWO, and each now goes its own way. Its WARNING BLOCK is already a verbatim copy of the runtime messages, by design (`DeliveryComponents.cs:633-637`, under the comment at `:611-616` "the warnings are repeated here because a bubble is not a value and the chin holds one line"), so it is DELETED as a pure duplicate. Its WRITTEN PATHS are KEPT on the port. Its LIVE LINES, one per kind at `:627-632`, are not duplicated anywhere: only the FIRST reaches the chin, through `FirstLine(uploaded)` at `:641-643`, and a live outcome becomes a Warning only when it both failed AND reached Done (`:594-600`), so a two-kind push whose second kind fails while the first succeeds would lose the second outcome entirely. That is why they move to messages rather than being deleted with the warning block.

Export's harness pin at `Program.cs:183-189` is NOT touched by this round: its outputs are pinned as `{ "JSON", "Status" }` and both ports stay registered under those names. The skin part of this wave reorders Export's INPUTS in that same entry, so this round writing nothing there removes an ordering hazard between the two rather than merely managing it.

**Files:**
- Modify: `plugin/native_v02/Components/DeliveryComponents.cs:343-353` (the Status description), `:611-640` (the status list and the live lines)
- Modify: `tests/native_smoke/Program.cs` (a new `ValidateExportStatusNarrowed` with its PASS block)
- Test: `ValidateExportStatusNarrowed`

**Interfaces:**
- Consumes: nothing from earlier tasks. The answer recorded by Task 44 decides the level.
- Produces: `internal static List<string> ExportComponent.WrittenLines(IReadOnlyList<string>? written)` and `internal static List<string> ExportComponent.LiveLines(string uploaded)`, the two halves separated so the check can assert that one is data and the other is a message.

- [ ] **Step 1: Write the check first, and watch it fail**

Add to `tests/native_smoke/Program.cs` after `ValidateImportPiecesMessages`:

```csharp
    /// <summary>
    /// Export's Status after the narrowing: TWO assertions, not one.
    ///
    /// FIRST, the per-kind live lines still exist, one per kind, as separate
    /// strings for the balloon. They are the half with no duplicate
    /// anywhere: only the FIRST reaches the chin, and a live outcome becomes
    /// a Warning only when it both failed and reached Done, so a two-kind
    /// push whose second kind fails while the first succeeds would lose the
    /// second outcome entirely if they were simply deleted with the warning
    /// block.
    ///
    /// SECOND, the written paths are still EMITTED AS DATA on the Status
    /// port and are NOT duplicated as messages. That is the whole content of
    /// the ruling that kept the port: an author needs the path of what was
    /// just written as data, to open it, to copy it or to feed a File Path,
    /// and a message cannot be wired into anything. Putting them on the
    /// balloon as well would be the same fact in two places, which is the
    /// habit this round is retiring.
    /// </summary>
    private static void ValidateExportStatusNarrowed(Assembly plugin)
    {
        Type export = RequireComponentType(plugin, "ExportComponent");
        MethodInfo writtenLines = RequireStatic(export, "WrittenLines");
        MethodInfo liveLines = RequireStatic(export, "LiveLines");

        string[] Ask(MethodInfo method, object? argument) =>
            ((IEnumerable)method.Invoke(null, new[] { argument })!)
                .Cast<string>()
                .ToArray();

        string[] live = Ask(liveLines, "stored\nrefused: no studio");
        if (live.Length != 2 ||
            !live[0].Contains("stored", StringComparison.Ordinal) ||
            !live[1].Contains("refused", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "One line per KIND, each its own string: a two-kind push "
                + "whose second kind fails while the first succeeds must "
                + "report both, and only the first ever reaches the chin. "
                + $"Got [{string.Join(" | ", live)}].");
        }
        if (live.Any(line => line.Contains(
                "written:", StringComparison.Ordinal)))
        {
            throw new InvalidOperationException(
                "The written paths are DATA on the Status port and are not "
                + "duplicated as messages; the same fact in two places is "
                + "the habit this round is retiring.");
        }

        string[] nothing = Ask(writtenLines, null);
        if (nothing.Length != 1 ||
            !nothing[0].Contains("nothing", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "A solve that has written nothing says so on the port, "
                + "rather than emitting an empty text a panel shows as a "
                + $"blank; got [{string.Join(" | ", nothing)}].");
        }

        string[] paths = Ask(
            writtenLines,
            new List<string> { @"C:\studies\a-contract.json", @"C:\studies\a-compas.json" });
        if (paths.Length != 2 ||
            !paths.All(line => line.StartsWith(
                "written: ", StringComparison.Ordinal)) ||
            !paths[0].EndsWith("a-contract.json", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "Every written file is named on the port, one line each, so "
                + "a one-shot Button write stays readable after the button "
                + $"releases; got [{string.Join(" | ", paths)}].");
        }
    }
```

Register it:

```csharp
        try
        {
            ValidateExportStatusNarrowed(plugin);
            Console.WriteLine(
                "PASS  Export's narrowed Status: the per-kind live lines "
                + "exist one per kind for the balloon, the written paths are "
                + "still emitted as DATA on the port and are not duplicated "
                + "as messages, and a solve that wrote nothing says so.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Export's narrowed Status: {DescribeException(exception)}");
        }
```

Run the gate. It must fail with `ExportComponent.WrittenLines was not found.`

- [ ] **Step 2: Split the two halves out**

Add to `plugin/native_v02/Components/DeliveryComponents.cs`, immediately after the `Display` helper that ends at `:665`:

```csharp
    /// <summary>
    /// The written-file paths, one line each, for the Status PORT.
    ///
    /// These stay wireable DATA and do not go to the balloon. An author
    /// needs the path of the file he has just written as data, to open it,
    /// to copy it, to feed a File Path or a downstream write, and a message
    /// cannot be wired into anything. They are also not a diagnostic: they
    /// are the product of the run. The list is the SESSION's latest rather
    /// than this solve's, so a one-shot Button write stays visible after the
    /// button releases.
    /// </summary>
    internal static List<string> WrittenLines(IReadOnlyList<string>? written)
    {
        if (written is null || written.Count == 0)
            return new List<string> { "written: nothing" };
        var lines = new List<string>(written.Count);
        foreach (string path in written)
            lines.Add("written: " + path);
        return lines;
    }

    /// <summary>
    /// The live outcome, one line per KIND, for the BALLOON.
    ///
    /// These are the half with no duplicate anywhere. Only the first reaches
    /// the chin, through FirstLine, and a live outcome becomes a Warning
    /// only when it both failed AND reached Done, so a two-kind push whose
    /// second kind fails while the first succeeds would lose the second
    /// outcome entirely if these were simply deleted with the warning block.
    /// One message per fact, because Diagnose's document scan emits one tree
    /// item per message.
    /// </summary>
    internal static List<string> LiveLines(string uploaded)
    {
        var lines = new List<string>();
        foreach (string line in uploaded
            .Replace("\r\n", "\n", StringComparison.Ordinal)
            .Split('\n'))
        {
            lines.Add("live: " + line);
        }
        return lines;
    }
```

- [ ] **Step 3: Narrow the emit**

Replace `DeliveryComponents.cs:611-640`, from the `// What this solve did, in lines.` comment through the `data.SetData(1, ...)` call, with:

```csharp
            // The Status port now carries the WRITTEN PATHS and nothing
            // else. The live lines moved to the balloon, one message per
            // kind, where Diagnose's document scan reads them; the warning
            // block that used to be repeated here went outright, because it
            // was a verbatim copy of the runtime messages by design and the
            // same fact in two places is the habit this round is retiring.
            // The written list is the session's latest rather than this
            // solve's, so a one-shot Button write stays visible after the
            // button releases.
            foreach (string line in LiveLines(uploaded))
                AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, line);

            data.SetDataList(0, payloads);
            data.SetData(
                1,
                string.Join(Environment.NewLine, WrittenLines(_lastWritten)));
```

If Task 44's check came back empty, `GH_RuntimeMessageLevel.Remark` above becomes `GH_RuntimeMessageLevel.Warning` and nothing else changes. Export's existing Warnings, including the live failure Warning at `:594-600`, are already Warnings and do not move.

- [ ] **Step 4: Rewrite the port description**

Replace the Status description at `DeliveryComponents.cs:344-353` with:

```csharp
        parameters.AddTextParameter(
            "Status",
            "ST",
            "The files this component has written, one per line: written: " +
            "<path> per file of the most recent write, or written: nothing. " +
            "The list is the SESSION's latest rather than this solve's, so a " +
            "one-shot Button write stays readable after the button " +
            "releases. Nothing else is here any more: the per-kind live " +
            "outcome and the warnings this solve raised are runtime messages " +
            "on the component itself, read off its own balloon or out of " +
            "DIAGNOSE with nothing wired into it.",
            GH_ParamAccess.item);
```

The port keeps its slot, its type, its name and its nickname, which is what makes the migration silent: no index moves, the harness pin stands unedited, and `ParameterIdentity.Mismatch` has nothing to report. A saved definition with Status wired to a panel keeps working; the panel simply shows the written paths and no longer shows the warning block or the live lines. Renaming it to something truer, "Written" or "Files", is question 12B(e) and would cost a removed-and-added pair in the load warning plus the harness pin edit this round otherwise avoids. Do not take it here.

- [ ] **Step 5: Run the gate**

Green, with the new PASS line and the Export pin at `Program.cs:183-189` untouched.

- [ ] **Step 6: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "plugin/native_v02/Components/DeliveryComponents.cs" "tests/native_smoke/Program.cs"
git -C $repo commit -m "feat(export): Status carries the written paths and nothing else"
```

---

### Task 47: The record of what moved

Spec rules 1.4 and 9.1. The GUID retirements need recording, and one sentence of this migration has no machinery behind it at all: after this round there is no component called Frame in the palette, while there IS one called Deconstruct which is not the one a saved file remembers and does not hold the ports it held. An author opening such a file meets TWO orphans, one whose name has vanished from the plugin and one whose name is now taken by a component of a different shape.

`ParameterIdentity.Mismatch` cannot help him. It compares an ARCHIVED port list against a REGISTERED one (`NativeComponentBase.cs:321-407`), and an orphan has no registration to compare against because the class no longer exists. So the author gets Grasshopper's missing-component placeholder and nothing from us. That is the honest reading, it is worse for him than a warning would be, and it is accepted because reusing a GUID is worse still: fifteen wires would be silently relanded by index behind one sentence. The sentence has to be carried in words instead, which is what this task writes.

**Files:**
- Modify: `docs/removed-guids.md` (a new section, the repo's register for retired GUIDs and the file that already carries the "saved definitions lose those components on open" sentence)
- Modify: `docs/component-taxonomy.md` (the Deconstruct row at :57 rewritten, the Frame row at :58 deleted, the component list at :125 and the reserved-families sentence at :164, plus the Supports row at :61 and the Animate row at :53 where they name Frame or Deconstruct's Reaction Points)
- Test: no harness check; the harness does not read either document. The gate is run to prove nothing else moved.

**Interfaces:**
- Consumes: the merged reader's name, nickname, GUID and fifteen ports from Task 38; the retired GUIDs named there.
- Produces: nothing later tasks call. This is the last task of this part.

- [ ] **Step 1: Record the two retired GUIDs**

Append to `docs/removed-guids.md`:

```markdown
Deleted 2026-09-01 in the readers merge: Frame and Deconstruct became ONE
fifteen-port reader, on a new GUID, so both of the old components are
retired and neither GUID is reused. Wires cannot be redistributed
mechanically across a shape this different: Grasshopper reattaches an
archived wire to the live port at the same INDEX, and old slot 0 was
Member Lines where new slot 0 is a Mesh.

| Component | GUID |
| --- | --- |
| Frame | 5d8e2f61-7a4c-4b93-a0e6-c3f19b7d2a58 |
| Deconstruct (ten-port) | 68d0b4f2-9a3e-4c17-85d6-f2b8a0c4e961 |

A saved definition holding either meets Grasshopper's own missing-component
placeholder, with its wires still attached to it, and nothing from the
plugin: the load-time warning compares an archived port list against a
registered one, and an orphan has no registration to compare against. The
harder half is Frame. There is now no component of that name in the palette
at all, while there IS one called Deconstruct which is not the one the file
remembers and does not hold the ports it held. Nothing in the plugin can
tell an author that Frame's nine outputs are now slots 0 to 8 of
Deconstruct, so it is written here: delete both placeholders, place one
Deconstruct, and rewire. The order of its fifteen outputs is Mesh, Cables,
Principal Lines, Principal Nodes, Anchor Nodes, Anchor Lines, Perimeter
Nodes, Perimeter Lines, Columns, Member Lines, Form Lines, Force Lines,
Load Points, Load Vectors, Reaction Vectors. Member IDs, Node IDs, Reaction
Points and Phase are gone: the tree structure already carries what the
first two restated, Reaction Points held the same points as Support Points
by construction, and the phase word is on the component's chin. Support
Points is now Anchor Nodes.
```

- [ ] **Step 2: Rewrite the taxonomy's two reader rows**

In `docs/component-taxonomy.md`, replace the Deconstruct row at line 57 with a row whose ports column reads:

```
Result `RES` | Mesh `M`, Cables `C`, Principal Lines `PL`, Principal Nodes `PN`, Anchor Nodes `AN`, Anchor Lines `AL`, Perimeter Nodes `PRN`, Perimeter Lines `PRL`, Columns `CO`, Member Lines `ML`, Form Lines `FL`, Force Lines `FCL`, Load Points `LP`, Load Vectors `LV`, Reaction Vectors `RV`
```

and whose description says, in the file's own voice and in plain prose: that Frame and Deconstruct merged on 2026-09-01 into one reader on a new GUID; that slots 0 to 8 are the frame geometry and follow the animation frame while slots 9 to 14 are the statics of the solved state and do not; that Cables and Member Lines are two readings of the same net and are not item-aligned; that Anchor Lines is one line per strip branched exactly as Anchor Nodes; that Reaction Vectors is branched onto the anchor strips with a zero holding the slot of a support that carries none, and a reaction on no strip raising a Warning rather than taking a branch; that the two halves fail apart; and that it is a LEAF, emitting no Result, so everything beyond geometry is a runtime message.

Delete the Frame row at line 58 entirely.

In the Animate row at line 53, replace "wire it to **Frame** for the geometry at that frame" with "wire it to **Deconstruct** for the geometry at that frame".

In the Columns row at line 54, replace "**Frame** hands the geometry back as trees" with "**Deconstruct** hands the geometry back as trees".

In the Supports row at line 61, replace "branched exactly as **Deconstruct**'s Reaction Points" with "branched exactly as **Deconstruct**'s Anchor Nodes" and "branched exactly as **Frame**'s Columns" with "branched exactly as **Deconstruct**'s Columns".

In the panel list at line 125, remove `Frame` from the `04 Read` row, and in the sentence at line 164 remove `Frame` from the list of reserved families it names. Any count of components in the document moves from twenty-one to twenty.

- [ ] **Step 3: Check for clash files and run the gate**

Both documents are large and sync through OneDrive, so run the clash scan before committing and resolve anything found by CONTENT rather than by which side carries the clash name. Run the gate to prove nothing in the plugin or the harness moved.

- [ ] **Step 4: Commit**

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
git -C $repo add "docs/removed-guids.md" "docs/component-taxonomy.md"
git -C $repo commit -m "docs(readers): record the merged reader and the two retired GUIDs"
```

- [ ] **Step 5: The final install and hand-over**

This is the fourth and last install named in the install policy at the head of this plan, and it is the one that matters to Param: the `.gha` it puts in place is the only one carrying the merged reader, the two retired GUIDs and the fifteen ports. Without it the branch's final build never reaches him, and Task 44's mid-phase install leaves a plugin on his machine that is three tasks out of date.

```powershell
$repo = "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow"
$clash = Get-ChildItem -Path "$repo\plugin","$repo\tests","$repo\docs" -Recurse -Filter "*Name clash*" -ErrorAction SilentlyContinue
if ($clash) { $clash | ForEach-Object { $_.FullName }; throw "OneDrive clash file in the tree; resolve by CONTENT before installing" }
Get-Process -Name "Rhino" -ErrorAction SilentlyContinue
& "$repo\plugin\native_v02\Build-And-Install.ps1"
```

If `Get-Process` returns a running Rhino, stop and ask Param to close it; the installed `.gha` is locked while Rhino holds it. Then tell him, in plain text with full absolute paths:

- that the plugin is installed at `C:\Users\Param\AppData\Roaming\Grasshopper\Libraries\Ananke_COMPAS\Ananke.COMPAS.gha` and RHINO MUST BE RESTARTED, because an open session keeps the old `.gha` and the old worker;
- that Frame and Deconstruct are now ONE reader on a NEW GUID, so a saved definition holding either meets Grasshopper's missing-component placeholder and nothing from the plugin, and that the remedy is written out in `docs/removed-guids.md`: delete both placeholders, place one Deconstruct, and rewire;
- that Skin and Export both moved ports in phase two, so every saved definition needs those two wires checked once, and that Export's Live is HELD until it is toggled off and on again;
- that the columns work moves columns at Branching 3 on four free-notch counts, by his own ruling, and changes the feet-close and collision clearances;
- which of the open questions at the end of this plan are still open, 12B(a) among them;
- that the commits are local and NOT pushed.

---

