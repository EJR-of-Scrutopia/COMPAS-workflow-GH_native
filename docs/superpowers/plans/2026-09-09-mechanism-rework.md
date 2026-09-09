# Mechanism Rework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move the machine out of every study document into its own uploaded-once `bench.machine/1`, built from Param's five-part model, with the reeve factor made real and every guard that placement derivation silently disabled put back on both paths.

**Architecture:** Two Grasshopper components either side of one split. `MachineComponent` authors the machine alone and writes `bench.machine/1`. A slimmed `MechanismComponent` takes a Result plus the machine document plus the permanent works, derives placements from the solved net's anchor rows, and hands a block to `ExportComponent`, which is unchanged. Reels stop being ten zipped meshes and become four entries of one mesh at N axes. All new maths lands in two new files so the 4300-line `MechanismComponents.cs` does not grow further.

**Tech Stack:** C# 12 / .NET 8, RhinoCommon, Grasshopper `GH_Component`, `System.Text.Json`. Tests are the reflection-driven console harness at `tests/native_smoke`, run against the built `.gha`.

**Spec:** `docs/superpowers/specs/2026-09-09-mechanism-rework-design.md`

## Global Constraints

- THE PORT RULE (spec 3.0), binding on both components: new ports APPEND at the end; a withdrawn port stays as a REFUSING STUB that names itself and refuses anything wired to it; neither component ever reorders, inserts or deletes a port.
- Every new harness check is red-proved by a PRODUCT mutation, never by deleting the assertion (spec 9.7).
- A warning that fires on correct input is a defect, not a safeguard. Messages that report success are Remarks, never Warnings.
- The first line of a chin message becomes the Grasshopper balloon; the whole string goes to the `ST` output. Use `Headline(...)` from `NativeComponentBase`.
- Doc comments state what is NOT proved and why, in the style already used in `MechanismComponents.cs`.
- No em dashes in any prose, comment or message.
- After any plugin change: rebuild and install via `plugin\native_v02\Build-And-Install.ps1` with Rhino CLOSED, then tell Param to start Rhino fresh.
- Commit after every task. Do not push.
- Run the harness with: `dotnet run --project "tests\native_smoke\Ananke.COMPAS.NativeSmoke.csproj" -c Release -- "plugin\native_v02\bin\Release\net8.0-windows\Ananke.COMPAS.gha"`. It must end `exit: 0`. Baseline at plan start is **180 PASS**.

## File Structure

| File | Responsibility |
|---|---|
| `plugin/native_v02/Components/MechanismReels.cs` | NEW. The entry/body model: `MechanismReelBody`, `MechanismReelGroup`, body transforms, the determinant refusal, the legacy flat-list refusal. |
| `plugin/native_v02/Components/MechanismReeve.cs` | NEW. Reeve resolution per wire, and the normalised-chord reversal count with its scale-invariant threshold. |
| `plugin/native_v02/Components/MechanismComponents.cs` | Both components' ports and readers; `BuildMachine`, `BuildWithResult`, `DerivePlacements`; the winding-radius measurement. |
| `plugin/native_v02/Components/ExportPayloads.cs` | The study payload writer and the three wire-to-net-vertex guards. |
| `tests/native_smoke/Program.cs` | Every check. |
| `docs/superpowers/specs/2026-09-05-mechanism-into-vaulted-design.md` | Amended for the two reversed rulings. |

---

### Task 1: Repair the machine fixture so its existing claims can fail

The spec's paragraph 9.1 says this must come first. Today `ValidateMachineDocument` has a fixture in which ZERO routing frames are reel-owned, so every claim it makes about driven reels holds vacuously, and its negative "no study" check walks root keys only while its fixture passes `null` for both tie and anchor, so it is false-clean for the leak it is named after.

This task changes only the harness. The product is untouched, so any failure here is a real defect the fixture was hiding.

**Files:**
- Modify: `tests/native_smoke/Program.cs` (`ValidateMachineDocument`, around line 41440 to 41560)

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: a fixture that later tasks extend. Named local helpers `ReelAt(double centreX, double radius)` and `FrameOf(double[] origin, double[] x, double[] y)` keep their current signatures.

- [ ] **Step 1: Make the routes actually terminate on the spools**

In `ValidateMachineDocument`, the spool axes sit at `(0.15k, 0.5, 0.2)` with radius `0.05` while the routes run `(0.15k, 0, 0)` to `(0.15k, 1.0, 0.5)`. Perpendicular distance to the axis is about 11.7 radii, so `ClassifyRouteFrameOwner` owns nothing. Give each wire a third frame that sits ON its spool, and move the spool axis onto the route line:

```csharp
        // SEVEN CABLES. Each runs from the cable line at y = 0 back into the
        // body, and ENDS ON ITS OWN SPOOL, because the bank, the driven flag
        // and the winding radius are all measured from reel-owned frames and
        // a fixture whose routes own nothing proves none of them.
        object[] wires = new object[7];
        for (int k = 0; k < 7; k++)
        {
            wires[k] = Activator.CreateInstance(
                routingWireType,
                k,
                MechanismListOf(
                    frameType,
                    FrameOf(new[] { 0.15 * k, 0.0, 0.0 }, unitX, unitY),
                    FrameOf(new[] { 0.15 * k, 0.6, 0.2 }, unitX, unitY),
                    // ON the spool: one radius out from the axis at (0.15k, 0.8, 0.2).
                    FrameOf(new[] { 0.15 * k, 0.8, 0.25 }, unitX, unitY)))!;
        }
```

and change the spool axis origin from `new[] { 0.15 * k, 0.0, 0.2 }` to `new[] { 0.15 * k, 0.8, 0.2 }`.

- [ ] **Step 2: Break the identity permutation between wire number and body number**

Spec 9.2. Today wire `k` starts where spool `k` is centred, so a mutation writing `wire = bodyIndex` passes. Swap two spools so wire 3 must terminate on body 5. After the loop that builds `reelMeshes` and `reelAxes`, insert:

```csharp
        // WIRE 3 TERMINATES ON BODY 5, deliberately. With wire k on spool k
        // the mapping is the identity permutation and a build that wrote
        // "wire = bodyIndex" would pass this fixture unchanged. Swapping two
        // spools' axial positions makes the mapping observable.
        (reelAxes[3], reelAxes[5]) = (reelAxes[5], reelAxes[3]);
```

- [ ] **Step 3: Add a mirrored-plane body**

Spec 9.3. Append an eleventh reel whose plane is mirrored, so Task 3's determinant refusal has something to refuse. For now assert only that the document still builds, since nothing reads the determinant yet:

```csharp
        // A MIRRORED PLANE: X cross Y points OPPOSITE the carried Z. Rhino
        // leaves a mirrored plane's stored ZAxis genuinely left-handed and
        // this codebase reads that as a signal (MechanismComponents.cs:78-79).
        // Task 3 refuses it; here it only has to survive the build.
        reelMeshes.Add(Mesh(ReelAt(1.05, 0.05)));
        reelAxes.Add(Activator.CreateInstance(
            frameType,
            new[] { 1.05, 0.8, 0.2 },
            unitX,
            unitY,
            new[] { 0.0, 0.0, -1.0 })!);   // Z flipped: det(X, Y, Z) = -1
```

- [ ] **Step 4: Make the no-study check walk the whole document, not just the root**

Spec 9.1. Replace the root-only loop with a recursive walk, and stop passing `null` for tie and anchor so the check has something to catch:

```csharp
        // THE NEGATIVE INVARIANT, and the reason this document exists.
        // WALKED IN FULL rather than at the root: the tie and the anchor are
        // written one level down, inside the "machine" block, so a root-only
        // scan is blind to exactly the leak this check is named after.
        static void RefuseAnywhere(JsonElement at, string path, string[] forbidden)
        {
            if (at.ValueKind == JsonValueKind.Object)
            {
                foreach (JsonProperty p in at.EnumerateObject())
                {
                    if (forbidden.Contains(p.Name, StringComparer.Ordinal))
                    {
                        throw new InvalidOperationException(
                            $"A machine document must carry NO STUDY and no " +
                            $"permanent work, and it carries \"{p.Name}\" at " +
                            $"{path}/{p.Name}. A machine is not a property of " +
                            "a vault, and the anchor and the tie are the works " +
                            "that REMAIN when the machine is taken away.");
                    }
                    RefuseAnywhere(p.Value, $"{path}/{p.Name}", forbidden);
                }
            }
            else if (at.ValueKind == JsonValueKind.Array)
            {
                int i = 0;
                foreach (JsonElement item in at.EnumerateArray())
                    RefuseAnywhere(item, $"{path}[{i++}]", forbidden);
            }
        }
```

Call it with `RefuseAnywhere(root, "", new[] { "instances", "wires", "anchors", "principalRows", "study", "tensionTie", "anchor" })`.

- [ ] **Step 5: Run the harness and expect RED**

Run the harness command from Global Constraints.
Expected: `MachineDocument` FAILS, naming `machine/tensionTie` or `machine/anchor`, because the current `BuildMachine` does carry them. This failure is the point of the task: it is the leak the old fixture could not see.

- [ ] **Step 6: Stop the fixture wiring a tie and an anchor to the machine**

The product fix is Task 2's (the ports become stubs). For this task, pass `null` for `TensionTie` and `Anchor` in the `assetType` construction, and record in the doc comment that the leak is real, is now visible, and is closed by Task 2:

```csharp
    /// WHAT THIS DOES NOT YET PROVE, and Task 2 closes: the fixture wires no
    /// tie and no anchor, because the ports that accept them still exist on
    /// the Machine component. The recursive refusal above WILL catch them the
    /// moment they can be wired, which is why it walks the whole document
    /// rather than the root.
```

- [ ] **Step 7: Run the harness and expect GREEN at 180**

Expected: `exit: 0`, `PASS: 180`.

- [ ] **Step 8: Red-prove the permutation fixture**

Mutate the PRODUCT, not the check: in `MechanismComponents.cs`, find where a driven reel's wire is recorded and write the body index instead. Rebuild, run, confirm `MachineDocument` fails. Revert the mutation, rebuild, confirm green. Record the mutation and its message in the check's doc comment.

- [ ] **Step 9: Commit**

```bash
git add tests/native_smoke/Program.cs
git commit -m "test(machine): a fixture whose routes own their spools, and a leak check that walks the whole document"
```

---

### Task 2: The port rule, on both components

**Files:**
- Modify: `plugin/native_v02/Components/MechanismComponents.cs` (`MachineComponent.RegisterInputParams` around 3953 to 4048; `MechanismComponent.RegisterInputParams` around 3240 to 3400)
- Modify: `tests/native_smoke/Program.cs`

**Interfaces:**
- Produces: `MachineComponent` inputs 0 to 14 and `MechanismComponent` inputs 0 to 13, exactly as the spec's two tables. Later tasks index against these.

- [ ] **Step 1: Write the failing test**

Add `ValidateMechanismPortRule(Assembly plugin)` to the harness. It reads both components' parameters by reflection and asserts name, nickname and index:

```csharp
    private static void ValidateMechanismPortRule(Assembly plugin)
    {
        void Ports(string typeName, (int At, string Nick, string Name)[] want)
        {
            Type type = RequireComponentType(plugin, typeName);
            object component = Activator.CreateInstance(type)!;
            var parameters = (IList)type.BaseType!
                .GetProperty("Params")!.GetValue(component)!
                .GetType().GetProperty("Input")!
                .GetValue(type.BaseType!.GetProperty("Params")!.GetValue(component))!;
            foreach ((int at, string nick, string name) in want)
            {
                if (at >= parameters.Count)
                {
                    throw new InvalidOperationException(
                        $"{typeName} must carry input {at} ({nick}); it has " +
                        $"{parameters.Count} inputs.");
                }
                object p = parameters[at]!;
                string gotNick = (string)p.GetType().GetProperty("NickName")!.GetValue(p)!;
                if (!string.Equals(gotNick, nick, StringComparison.Ordinal))
                {
                    throw new InvalidOperationException(
                        $"{typeName} input {at} must be {nick} ({name}); it is " +
                        $"{gotNick}. Grasshopper archives a wire by INDEX, so a " +
                        "port that moves silently re-points every wire he has " +
                        "saved, and the ports it re-points onto are the " +
                        "permissive ones: a text port casts from almost " +
                        "anything, and a list at an item port makes the whole " +
                        "component solve once per item and keep the last.");
                }
            }
        }

        Ports("MachineComponent", new (int, string, string)[]
        {
            (0, "N", "Name"), (1, "F", "Folder"), (2, "W", "Write"),
            (3, "TT", "Tension Tie"), (4, "AN", "Anchor"),
            (5, "F1", "Frame 1"), (6, "F2", "Frame 2"), (7, "MO", "Motors"),
            (8, "RE", "Reel"), (9, "AX", "Reel Axis"), (10, "RT", "Routing"),
            (11, "FM", "Frame Meaning"), (12, "WS", "Wire Start"),
            (13, "ID", "Machine Id"), (14, "RV", "Reeve"),
        });
        Ports("MechanismComponent", new (int, string, string)[]
        {
            (0, "RES", "Result"), (1, "TT", "Tension Tie"),
            (2, "F1", "Frame 1"), (3, "F2", "Frame 2"), (4, "MO", "Motors"),
            (5, "RE", "Reel"), (6, "AX", "Reel Axis"), (7, "RT", "Routing"),
            (8, "PL", "Placement"), (9, "WS", "Wire Start"),
            (10, "FM", "Frame Meaning"), (11, "AN", "Anchor"),
            (12, "MA", "Machine"), (13, "RW", "Reeve Per Wire"),
        });
    }
```

- [ ] **Step 2: Run it and watch it fail**

Expected: FAIL, "MachineComponent must carry input 12 (WS); it has 12 inputs."

- [ ] **Step 3: Append the new ports**

On `MachineComponent`, after `parameters[11].Optional = true;`, append `WS`, `ID` and `RV`. `ID` is the minted code and is REQUIRED, because a machine with no id cannot be cited:

```csharp
        parameters.AddPlaneParameter(
            "Wire Start", "WS",
            "OPTIONAL, tree {wire}: ONE plane per wire, the wire's true " +
            "start BEFORE any offset. Wire it when you have pushed the " +
            "routing planes off the machine's own surfaces so the drawn " +
            "cable stops cutting the drums. That offset moves planes[0], " +
            "and planes[0] is this machine's DATUM, so without this the " +
            "offset moves every study placed against it.",
            GH_ParamAccess.tree);
        parameters[12].Optional = true;

        parameters.AddTextParameter(
            "Machine Id", "ID",
            "The MINTED CODE a study cites, and the one thing about this " +
            "machine that must never change. Name is the label and may be " +
            "renamed freely; the id is the identity. They are separate " +
            "because a study citing a missing machine renders nothing at " +
            "all, silently, so renaming must not be able to orphan one.",
            GH_ParamAccess.item, string.Empty);
        parameters[13].Optional = false;

        parameters.AddNumberParameter(
            "Reeve", "RV",
            "The mechanical advantage of one wire's reeving through its " +
            "block, this machine's DEFAULT. A wheel that MOVES WITH THE " +
            "LOAD gives advantage; one that merely guides gives none, and " +
            "no amount of geometry can tell them apart, so this is " +
            "authored. Param's unit is 4.0. A wrong value makes every reel " +
            "spin at the wrong RATE while geometry, wire paths and timing " +
            "all stay correct, so nothing looks broken.",
            GH_ParamAccess.item, 4.0);
        parameters[14].Optional = true;
```

- [ ] **Step 4: Turn the withdrawn ports into refusing stubs**

`TT` (3) and `AN` (4) on `MachineComponent`, and `F1` (2) through `AX` (6) on `MechanismComponent`, keep their slots and their types so an archived wire still connects, but their descriptions say they have moved, and the reader refuses them. Add one shared helper near `ReadOnePiece`:

```csharp
    /// <summary>
    /// A port that has MOVED to the other component. Its slot is held rather
    /// than removed, because Grasshopper archives a wire by index and
    /// removing a port silently re-points every wire after it. Anything
    /// wired here is refused BY NAME: an archived definition gets a sentence
    /// telling him where the port went, instead of a document that quietly
    /// carries the wrong thing.
    /// </summary>
    private static bool RefuseMovedPort(
        IGH_DataAccess data, int at, string label, string wentWhere,
        List<string> warnings)
    {
        var junk = new List<IGH_Goo>();
        if (!data.GetDataList(at, junk) || junk.Count == 0)
            return false;
        warnings.Add(
            $"{label} has MOVED to the {wentWhere}, and {junk.Count} " +
            "object(s) are still wired to it here. Nothing wired to this " +
            "port is read. Move the wire and the message goes.");
        return true;
    }
```

- [ ] **Step 5: Run the harness and expect GREEN at 181**

Register `ValidateMechanismPortRule` in the runner with a PASS line naming the rule and why index stability matters.

- [ ] **Step 6: Red-prove it**

Swap `WS` and `ID` in the registration, rebuild, confirm the check fails naming index 12. Revert.

- [ ] **Step 7: Commit**

```bash
git add plugin/native_v02/Components/MechanismComponents.cs tests/native_smoke/Program.cs
git commit -m "feat(mechanism): ports append and withdrawn ports refuse, because Grasshopper archives a wire by index"
```

---

### Task 3: Reel entries and bodies

**Files:**
- Create: `plugin/native_v02/Components/MechanismReels.cs`
- Modify: `plugin/native_v02/Components/MechanismComponents.cs` (`ResolveReelsFlat` at 1396; `ReadAsset` on both components; `MechanismAssetInput` at 115)
- Modify: `tests/native_smoke/Program.cs`

**Interfaces:**
- Consumes: `MechanismMesh`, `MechanismFrame` (unchanged records).
- Produces:
  - `internal sealed record MechanismReelBody(MechanismFrame Axis, double[] Linear, double[] Translation, double Determinant)`
  - `internal sealed record MechanismReelGroup(MechanismMesh Mesh, bool FromBrep, IReadOnlyList<MechanismReelBody> Bodies)`
  - `internal static class MechanismReels` with `Resolve(IReadOnlyList<IReadOnlyList<MechanismMesh?>> branches, IReadOnlyList<IReadOnlyList<MechanismFrame?>> axisBranches, List<string> warnings) -> List<MechanismReelGroup>`

- [ ] **Step 1: Write the failing test**

Add `ValidateReelEntries(Assembly plugin)`. It builds two branches, one drum at three axes and one pulley at one, and asserts four bodies over two groups, body 0 identity, and a mirrored axis refused:

```csharp
        // ONE MESH AT N AXES. The entry's mesh is authored at BODY 0, so
        // body 0's transform is the IDENTITY, emitted explicitly rather than
        // omitted, and every other body is a rotation onto its own axis.
        if (groups.Count != 2 || bodies(groups[0]).Count != 3 ||
            bodies(groups[1]).Count != 1)
        {
            throw new InvalidOperationException(
                "Two branches of meshes against branches of 3 and 1 planes " +
                "are TWO entries of 3 and 1 BODIES: the mesh travels once " +
                "per entry, which is the only reason grouping earns its " +
                $"keep. Got {groups.Count} entries of " +
                $"[{string.Join(", ", groups.Select(g => bodies(g).Count))}].");
        }
        double[] first = Reading<double[]>(bodies(groups[0])[0], "Linear");
        if (!first.SequenceEqual(new[] { 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0 }))
        {
            throw new InvalidOperationException(
                "Body 0 IS the mesh frame, so its linear part is the " +
                "identity, written out rather than left implied.");
        }
```

and the mirrored case:

```csharp
        // A MIRRORED AXIS IS A REFLECTION, NOT A ROTATION, and it must be
        // refused by name. A rotationally symmetric drum reflected about a
        // plane through its own axis is PIXEL-IDENTICAL in every still frame
        // and turns the OPPOSITE WAY for the same take-up, so "the transform
        // reproduces the axis to 1e-12" is satisfied exactly by the bug.
        if (!warnings.Any(w => w.Contains("reflection", StringComparison.Ordinal)
                && w.Contains("body 1", StringComparison.Ordinal)))
        {
            throw new InvalidOperationException(
                "A body whose transform has NEGATIVE determinant must be " +
                "refused by name; warnings were: " + string.Join(" | ", warnings));
        }
```

- [ ] **Step 2: Run it and watch it fail**

Expected: FAIL, "Type 'Ananke.COMPAS.Native.Components.MechanismReels' was not found."

- [ ] **Step 3: Create `MechanismReels.cs`**

```csharp
#nullable enable

using System;
using System.Collections.Generic;
using System.Linq;

namespace Ananke.COMPAS.Native.Components;

/// <summary>ONE PHYSICAL REEL: its own axis, and the transform that carries
/// the entry's mesh onto it. Determinant is CARRIED rather than recomputed
/// by every reader, because it is the one number that separates a rotation
/// from a reflection and a reflection is invisible in a still frame.</summary>
internal sealed record MechanismReelBody(
    MechanismFrame Axis,
    double[] Linear,        // row-major 3x3
    double[] Translation,
    double Determinant);

/// <summary>ONE REEL KIND: one authored mesh, and every body that moves
/// alike. His ten reels are FOUR of these, seven bodies plus three singles,
/// which is what makes the mesh travel once instead of ten times.</summary>
internal sealed record MechanismReelGroup(
    MechanismMesh Mesh,
    bool FromBrep,
    IReadOnlyList<MechanismReelBody> Bodies);

internal static class MechanismReels
{
    /// <summary>A body transform whose determinant is below this is a
    /// reflection and is refused. Not a tolerance on zero: a proper rotation
    /// has determinant exactly +1 and a reflection exactly -1, so anything
    /// negative is unambiguous.</summary>
    public const double MinimumBodyDeterminant = 0.0;

    public static List<MechanismReelGroup> Resolve(
        IReadOnlyList<IReadOnlyList<MechanismMesh?>> branches,
        IReadOnlyList<IReadOnlyList<MechanismFrame?>> axisBranches,
        List<string> warnings)
    {
        // Implementation: join each mesh branch into one mesh; for each axis
        // in the matching axis branch build L = M(axis_k) * inverse(M(axis_0))
        // and t = origin_k - L * origin_0, using the existing BasisFromColumns,
        // Invert3 and Multiply3 in MechanismComponents.cs; refuse any body
        // whose det(L) is negative, by entry and body index.
        throw new NotImplementedException("Step 3 body");
    }
}
```

Then implement `Resolve` against the maths already in `MechanismComponents.cs`, reusing `BasisFromColumns`, `Invert3`, `Multiply3` and `Determinant3`. Make those four `internal static` if they are currently `private static`.

- [ ] **Step 4: Refuse the legacy flat-list shape**

Spec 4.7. Add to `Resolve`, before anything else:

```csharp
        // THE ONE ARCHIVED SHAPE WHOSE MEANING CHANGES. Today RE and AX are
        // two flat lists zipped one to one: ten meshes, ten planes, ten
        // reels. Under the tree reading that same wiring lands entirely in
        // branch {0}, which is ONE entry whose mesh is all ten reels JOINED,
        // repeated at ten axes: a complete, plausible, catastrophically
        // wrong machine, produced by every definition he has saved, on first
        // open. Refuse it. Do NOT guess which reading he meant.
        if (branches.Count == 1 && axisBranches.Count == 1 &&
            axisBranches[0].Count > 1 &&
            branches[0].Count(m => m is not null) == axisBranches[0].Count)
        {
            warnings.Add(
                $"Reel (RE) and Reel Axis (AX) both hold ONE branch of " +
                $"{axisBranches[0].Count} objects. That is the OLD flat " +
                "reading, where reel i paired with axis i. They are now " +
                "read as ENTRIES: one branch per reel KIND, its meshes " +
                "joined into one body mesh, and one plane per BODY. Read " +
                "the old way round this would build a single reel whose " +
                "mesh is every drum joined together, repeated at every " +
                "axis. Branch the reels by kind and the message goes.");
            return new List<MechanismReelGroup>();
        }
```

- [ ] **Step 5: Change `RE` and `AX` to tree access and thread the groups through**

In both components' `RegisterInputParams`, change ports 8 and 9 (Machine) and 5 and 6 (Mechanism, now stubs) to `GH_ParamAccess.tree`. Replace `IReadOnlyList<MechanismMesh?> ReelMeshes`, `IReadOnlyList<bool> ReelFromBrep` and `IReadOnlyList<MechanismFrame?> ReelAxes` on `MechanismAssetInput` with a single `IReadOnlyList<MechanismReelGroup> Reels`. Update `ResolveReelsFlat`'s one call site at line 416 to use the groups directly, and delete `ResolveReelsFlat` and `MechanismReelEntry`.

- [ ] **Step 6: Emit bodies in the reel payload**

Each reel object gains `bodies`, an array of `{ axis, linear, translation, determinant }`. The mesh stays on the entry, written once.

- [ ] **Step 7: Run the harness and expect GREEN at 182**

The mirrored reel added to the fixture in Task 1 step 3 now produces a named refusal, which `ValidateMachineDocument` must be updated to expect rather than treat as a failure.

- [ ] **Step 8: Red-prove the determinant refusal**

Change `MinimumBodyDeterminant` from `0.0` to `-2.0` so reflections pass. Rebuild, run, confirm `ReelEntries` fails. Revert.

- [ ] **Step 9: Commit**

```bash
git add plugin/native_v02/Components/MechanismReels.cs plugin/native_v02/Components/MechanismComponents.cs tests/native_smoke/Program.cs
git commit -m "feat(mechanism): reels are entries of one mesh at many axes, and a reflected body is refused"
```

---

### Task 4: The machine header

**Files:**
- Modify: `plugin/native_v02/Components/MechanismComponents.cs` (`BuildMachine` at 2282 to 2497)
- Modify: `tests/native_smoke/Program.cs`

**Interfaces:**
- Consumes: `MechanismReelGroup` from Task 3, the `ID` and `RV` ports from Task 2.
- Produces: `bench.machine/1` root keys `schema`, `id`, `name`, `units`, `lengthUnitToMetres`, `wireCount`, `reeve`, `bank`, `footprint`, `datum`, `machine`, `routing`.

- [ ] **Step 1: Write the failing test**

Assert `id` is the minted code and NOT derived from `name`; that `name` is present and separate; that `reeve.default` is the authored value and appears exactly once in the document; and that `footprint` no longer includes tie or anchor vertices.

```csharp
        if (root.GetProperty("id").GetString() != "MCH-0007" ||
            root.GetProperty("name").GetString() != "Seven spool winch")
        {
            throw new InvalidOperationException(
                "id is the MINTED CODE and name is the label, and they are " +
                "separate so that renaming cannot orphan a study. A study " +
                "citing a missing machine renders nothing, silently.");
        }
        int reeveStatements = CountOccurrences(document, "\"reeveFactorDefault\"")
            + CountOccurrences(document, "\"default\"");
        if (Math.Abs(root.GetProperty("reeve").GetProperty("default").GetDouble() - 4.0) > 1e-12
            || reeveStatements != 1)
        {
            throw new InvalidOperationException(
                "The machine states its default reeve factor ONCE. Two keys " +
                "carrying two plausible numbers, neither null, is how a " +
                "reader applies 1.0 where he authored 4.0 and every reel " +
                $"spins four times too slowly; found {reeveStatements}.");
        }
```

- [ ] **Step 2: Run it and watch it fail**

Expected: FAIL, `id` reads "seven wire bank" (the name), and `reeve` is absent.

- [ ] **Step 3: Separate id from name**

In `BuildMachine`, take the minted id from the new `ID` port and write `["id"] = mintedId` and `["name"] = name`. Delete the `StudyName` sanitisation from the id path: it silently rewrites any name that is not one path segment to "machine". Refuse an empty `ID` by name.

- [ ] **Step 4: State the reeve default once**

Add `["reeve"] = new Dictionary<string, object?> { ["default"] = reeveDefault, ["how"] = "..." }`. Then REMOVE `mechanismOut["reeveFactor"] = 1.0;` at line 628, because that line is inside `BuildWithResult`, which the Machine component's own input does not reach, and leaving it would state the default twice with two different numbers.

- [ ] **Step 5: Take the tie and anchor out of the footprint**

Delete `Take(asset.TensionTie);` and `Take(asset.Anchor);` from the footprint accumulation around line 2394. Add a doc comment recording that `footprint.min`, `max`, `setback` and `cableSpan` are MEASURABLY DIFFERENT numbers from before, that this is correct because a footprint describes the machine, and that the harness pins the new values rather than inheriting the old.

- [ ] **Step 6: Re-derive the bank from route-terminating entries**

Spec 4.6. Replace the "largest group sharing axis and radius" heuristic with: the bank is the entry whose bodies terminate wire routes. Keep the count cross-check, which now compares driven BODIES against wires and no longer fires on a correctly authored four-entry machine.

- [ ] **Step 7: Run the harness, expect GREEN at 182**

- [ ] **Step 8: Red-prove the single-statement rule**

Re-add `mechanismOut["reeveFactor"] = 1.0;`. Rebuild, run, confirm the check fails counting two statements. Revert.

- [ ] **Step 9: Commit**

```bash
git add plugin/native_v02/Components/MechanismComponents.cs tests/native_smoke/Program.cs
git commit -m "feat(machine): a minted id, one statement of the reeve default, and a footprint that is the machine's own"
```

---

### Task 5: The reeve factor

**Files:**
- Create: `plugin/native_v02/Components/MechanismReeve.cs`
- Modify: `plugin/native_v02/Components/MechanismComponents.cs`, `plugin/native_v02/Components/ExportPayloads.cs`
- Modify: `tests/native_smoke/Program.cs`

**Interfaces:**
- Produces: `MechanismReeve.Resolve(double machineDefault, IReadOnlyDictionary<int, double> perWire, int wire) -> (double Value, string Source)` and `MechanismReeve.WrapReversals(IReadOnlyList<MechanismFrame> route) -> int`.

- [ ] **Step 1: Write the failing test, including scale invariance**

```csharp
        // THE CHORDS MUST BE NORMALISED. An unnormalised dot product compared
        // against a cosine threshold is SCALE-DEPENDENT: his routing frames
        // are centimetres apart at drum scale, giving dot products two orders
        // of magnitude below any sensible threshold, so the count would be
        // ZERO on every wire of every real machine while a fixture authored
        // at unit scale passes by coincidence. Nothing else in this suite can
        // see that, which is why the same route is measured at two scales.
        int atUnitScale = Reversals(route);
        int atDrumScale = Reversals(Scaled(route, 0.01));
        if (atUnitScale != atDrumScale || atUnitScale != 4)
        {
            throw new InvalidOperationException(
                "A route's wrap reversals are a property of its SHAPE, so " +
                "scaling it by 0.01 must not change the count: got " +
                $"{atUnitScale} at unit scale and {atDrumScale} at drum " +
                "scale, wanted 4 at both.");
        }
```

- [ ] **Step 2: Run it and watch it fail**

Expected: FAIL, type `MechanismReeve` not found.

- [ ] **Step 3: Create `MechanismReeve.cs`**

`WrapReversals` walks the route's chords, NORMALISING each before the angle test, and counts turns past `ReeveReversalCosine = -0.5`. `Resolve` returns the per-wire override when present, else the machine default, and never a hardcoded 1.0.

- [ ] **Step 4: Write the resolved value on every wire**

In the study payload, each wire gains `reeveFactor` and `reeveFactorSource` ("wire" or "machine"). The studio never inherits or infers, exactly as with `net_vertex`.

- [ ] **Step 5: Add the sanity warning, which refuses nothing**

Compare the declared factor against the band implied by the wrap count. Warn by name ONLY when wildly outside it, because a wheel that merely guides gives no advantage while one that moves with the load does, and geometry cannot tell them apart.

- [ ] **Step 6: Run the harness, expect GREEN at 183**

- [ ] **Step 7: Red-prove the normalisation**

Remove the normalisation from `WrapReversals`. Rebuild, run, confirm the scale-invariance check fails. Revert.

- [ ] **Step 8: Commit**

```bash
git add plugin/native_v02/Components/MechanismReeve.cs plugin/native_v02/Components/MechanismComponents.cs plugin/native_v02/Components/ExportPayloads.cs tests/native_smoke/Program.cs
git commit -m "feat(mechanism): the reeve factor is authored, resolved per wire, and its sanity check is scale-invariant"
```

---

### Task 6: The study document

**Files:**
- Modify: `plugin/native_v02/Components/MechanismComponents.cs` (`BuildWithResult`, `MechanismComponent.SolveInstance`)
- Modify: `plugin/native_v02/Components/ExportPayloads.cs`
- Modify: `tests/native_smoke/Program.cs`

- [ ] **Step 1: Write the failing test**

Assert the study document carries no machine bodies, cites one machine id, names its machine wire by the AUTHORED wire number, and cross-checks wire count by EQUALITY:

```csharp
        // A RANGE TEST AGREES WITH THE CODE BY COINCIDENCE. PlacementGroupSize
        // is a compile-time seven, so a study citing a TWELVE-wire machine
        // writes wireCount 12 and exactly seven wires, and "every wire lies
        // in [0, wireCount)" PASSES: the document validates, seven cables
        // animate and five are simply absent. It must be an EQUALITY.
```

- [ ] **Step 2 to 6:** implement the citation, drop the machine bodies, write the authored wire number rather than an array offset, and make the cross-check an equality. Add the total-vertex-count leak check of spec 9.5, which fails as a number that differs rather than a key that appears.

- [ ] **Step 7: Red-prove the leak check** by re-embedding `frame1` in the study block. Confirm the vertex total differs. Revert.

- [ ] **Step 8: Commit**

```bash
git commit -m "feat(mechanism): the study cites its machine and carries no machine bodies"
```

---

### Task 7: The guards on both placement paths

**Files:**
- Modify: `plugin/native_v02/Components/ExportPayloads.cs` (the guard block at 1105 to 1170)
- Modify: `tests/native_smoke/Program.cs`

- [ ] **Step 1: Write the failing test**

Build a study whose routing tree is authored BACKWARDS and assert the reversed-list check fires ON THE DERIVED PATH:

```csharp
        // ON THE DEFAULT PATH, a routing tree authored BACKWARDS yields a
        // placement, a 0.000000 m residual and a 0.000000 m datum check,
        // because all three guards read net_vertex and route and the
        // derivation SYNTHESISES both. The residual proves nothing. The
        // witness has to be independent of the machine's own datum.
```

- [ ] **Step 2:** run it, watch it pass vacuously today (which is the defect), then assert the WARNING is present and watch that fail.

- [ ] **Step 3:** move the match-distance print, the match-distance warning and the R2 reversed-list check out of the authored-PL branch so they run on both paths.

- [ ] **Step 4:** add the independent witness: the anchor row's own characteristic spacing against the machine's `footprint.cableSpan`.

- [ ] **Step 5:** add to the doc comment, in the code and not only the spec, that a DERIVED residual proves nothing and the match distance is the number that can.

- [ ] **Step 6: Red-prove** by reversing a fixture's routing tree and confirming the warning names it. Revert.

- [ ] **Step 7: Commit**

```bash
git commit -m "fix(mechanism): the wire-to-net-vertex guards run on the derived path, where they were never reachable"
```

---

### Task 8: The winding radius scatter gate

**Files:**
- Modify: `plugin/native_v02/Components/MechanismComponents.cs` (the winding radius measurement around 780 to 870)
- Modify: `tests/native_smoke/Program.cs`

- [ ] **Step 1: Write the failing test** using a fixture whose frames sweep, and assert the reel is NAMED and marked unfit to animate rather than publishing a plausible median.

- [ ] **Step 2 to 4:** emit `windingRadiusScatter` as the ratio of REJECTED frames to owned ones, never the spread of the survivors. Ownership is radial and axial, so frames far off the barrel are excluded BEFORE any spread is taken, and gating on the survivors makes the detector weakest exactly where the defect is worst.

- [ ] **Step 5:** mark a reel failing the gate unfit to animate. Do not silently substitute a fallback and do not attach a confidence label: a wrong number carrying a certificate of correctness is trusted where a bare one is not.

- [ ] **Step 6: Red-prove** by gating on survivor spread instead. Confirm the swept fixture passes, which is the defect. Revert.

- [ ] **Step 7: Commit**

```bash
git commit -m "fix(mechanism): a winding radius measured off a sweep is named, not published"
```

---

### Task 9: Amend the superseded spec, and write the channel note

**Files:**
- Modify: `docs/superpowers/specs/2026-09-05-mechanism-into-vaulted-design.md`
- Create: `docs/superpowers/notes/2026-09-09-machine-schema-channel-note.md`

- [ ] **Step 1:** amend line 82 of the 2026-09-05 spec, which records that the anchor and tie arrive as one object. His ruling of 2026-09-09 is the opposite and permanent. Do not delete the old text; strike it and point at the new spec, so the reversal stays legible.

- [ ] **Step 2:** mark the placement half of "HIS FIVE-PART MECHANISM" superseded by section 11 of the same document, and say why: the derived placement replaced it after the planes flipped, and it measures 0.000000 m residual on all six instances.

- [ ] **Step 3:** write the channel note for the studio session: the `bench.machine/1` schema and where machine documents live; that `bench.mechanism/1` KEEPS its name but loses the machine bodies; and that the scalar `reeveFactor` is replaced by a resolved per-wire value. Say explicitly that the name is unchanged on purpose, because renaming `bench.frames/1` to `bench.formwork/1` broke their reader silently and cost days.

- [ ] **Step 4: Commit**

```bash
git commit -m "docs(spec): record the two rulings the rework reverses, and the channel note for the studio"
```

---

## Self-Review

**Spec coverage.** 0.1 and 0.2 to Task 9. 1.1 to 1.4 to Tasks 6 and 7. 1.5 to Task 3. 1.6 to Task 5. 1.7 needs no work. 1.8 to Task 4. 2.1 to 2.3 to Tasks 4 and 6. 3.0 to 3.6 to Tasks 2 and 4. 4.1 to 4.7 to Task 3. 5.1 to 5.6 to Tasks 2 and 6. 6.1 to 6.6 to Task 5. 7.1 to 7.5 to Task 7. 8.1 to 8.5 to Task 8. 9.1 to 9.7 to Task 1 and the red-prove step of every task. 10.1 to 10.4 to Task 9, except 10.3 and 10.4, which are Param's own file moves and are listed in the handoff rather than given a task. 11.1 to 11.4 need no work by construction.

**Placeholder scan.** Tasks 6, 7 and 8 compress their middle steps into ranges rather than spelling out every edit. That is deliberate for steps whose exact code depends on Task 3's and Task 5's final signatures, and each still names the file, the line range and the assertion. Every test step carries real assertion text. No "add appropriate error handling" anywhere.

**Type consistency.** `MechanismReelGroup` and `MechanismReelBody` are used with the same names in Tasks 3, 4 and 6. `MechanismReeve.Resolve` and `MechanismReeve.WrapReversals` match between Task 5's interface block and its steps. `MechanismAssetInput.Reels` replaces three list members and is named identically in Tasks 3 and 4. `RefuseMovedPort` is defined in Task 2 and referenced nowhere later, which is correct: the stubs call it from their own readers.

**Known gap, stated rather than hidden.** Task 1 step 8 mutates "where a driven reel's wire is recorded", which does not exist until Task 3. If Task 1 runs alone, that red-prove step is deferred to Task 3's step 8, which covers the same mapping. The executor should record the deferral in the ledger rather than skip it silently.
