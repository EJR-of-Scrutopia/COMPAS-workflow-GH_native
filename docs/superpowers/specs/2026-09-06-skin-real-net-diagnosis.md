# Real-net skin diagnosis

Build measured: commit a09b7f9 (the exact build Param is running and photographing), from the
scratch archive at
C:/Users/Param/AppData/Local/Temp/claude/c--Users-Param-OneDrive---Ananke-eidos-Documents-Ananke-Eidos-Studio-VS-code-Random-comfyui/0df46ca4-9f90-4938-93e9-c6b9ac56b1c1/scratchpad/real-a09b7f9

Data measured: the eight studies exported minutes before this task started, at
C:/Users/Param/OneDrive - Ananke-eidos/Documents/Kinetic AI/PHD robotics/COMPAS Exports

Harness built for this task (new files, nothing in the plugin touched):
C:/Users/Param/AppData/Local/Temp/claude/c--Users-Param-OneDrive---Ananke-eidos-Documents-Ananke-Eidos-Studio-VS-code-Random-comfyui/0df46ca4-9f90-4938-93e9-c6b9ac56b1c1/scratchpad/real-a09b7f9/tests/net_diagnosis/
(NetLoader.cs, ReflectionUtil.cs, Program.cs, Ananke.COMPAS.NetDiagnosis.csproj)

Raw measured output (every field this report draws on, per study, per pattern):
C:/Users/Param/AppData/Local/Temp/claude/c--Users-Param-OneDrive---Ananke-eidos-Documents-Ananke-Eidos-Studio-VS-code-Random-comfyui/0df46ca4-9f90-4938-93e9-c6b9ac56b1c1/scratchpad/real-net-diagnosis.raw.json

Settings used, taken from Param's own canvas screenshot: Pattern 0 (courses), Size 0.5 m, Course
Height 0.5 m, Min Piece 0.20, Gaps 0.95. Pattern 1 (hexagonal, value list entry "1 · hexagonal" on
SkinComponent) was additionally run on the three Hex-named studies. Thickness was not legible on
the screenshot; Th/Gaps only affect the thickened Brep, which needs Rhino's native core and cannot
be built in this harness regardless (established already in the codebase's own comments, not a gap
this task introduces) — see section 3.6.


## 1. The loader

### 1.1 What it is and why it is a direct mapping, not a rebuild

`plugin/native_v02/Components/ExportPayloads.cs`'s `FormDocument.JsonFromContract` writes a
`<study>-form.json` as exactly `{"study": "...", <ContractJson.Serialize(ResultDto) body, spliced
in whole>, "thrustMesh": ...}`. The middle is the plugin's own `ResultDto` contract, byte for byte.
So the form document already carries a live `ResultDto`, and reading it is simply the inverse of
that one splice: drop `"study"` and `"thrustMesh"`, hand the remainder to
`ContractJson.Deserialize<ResultDto>`, then to `SkinPatterns.ReadNet` — the exact same call
`SkinComponent.SolveNative` makes on a live Result via `SkinSolveCache.NetFor`. No synthetic
geometry is built anywhere in this path.

Every plugin type is resolved by reflection against the built `.gha`, never by a compile-time
reference to the plugin project. `SkinNet`, `SkinPatterns` and `ContractJson` are all `internal`;
reflection reaches a type's public members regardless of the type's own accessibility (.NET does
not gate `MemberInfo.Invoke` on declaring-type visibility, only on sandbox trust level, and a
desktop console process has none of the old partial-trust restrictions). This is the same
convention `tests/native_smoke/Program.cs` already established for its own
`SkinPlanSelfCrosses`/`SkinPlansOverlap` lookups (that file's lines 464-471) — this loader is not a
new pattern, it is that one applied one level deeper.

The one real trap: `ContractJson.Options` sets `UnmappedMemberHandling = JsonUnmappedMemberHandling
.Disallow` (Contracts/ContractCore.cs). Deserialising the raw form-document file straight into
`ResultDto` throws, because neither `"study"` nor `"thrustMesh"` is a `ResultDto` member. The
loader's entire job is stripping those two keys first.

### 1.2 The code (ready to lift into tests/native_smoke)

`NetLoader.cs`, verbatim from the scratch build:

```csharp
#nullable enable

using System;
using System.IO;
using System.Linq;
using System.Reflection;
using System.Text;
using System.Text.Json;

namespace Ananke.COMPAS.NetDiagnosis;

internal static class NetLoader
{
    /// <summary>
    /// The form document's embedded contract, as the exact JSON text
    /// ContractJson.Serialize(ResultDto) produced, recovered by dropping the
    /// two keys FormDocument.JsonFromContract adds around it ("study" leads,
    /// "thrustMesh" trails). A JsonDocument walk rather than the writer's own
    /// byte-offset trick: a READER parsing a file it did not just write
    /// should not assume the same byte positions, only that the two keys
    /// exist and every other key is the contract's own.
    /// </summary>
    public static string ExtractResultContractJson(string formJsonPath)
    {
        byte[] raw = File.ReadAllBytes(formJsonPath);
        using JsonDocument document = JsonDocument.Parse(raw);
        if (document.RootElement.ValueKind != JsonValueKind.Object)
        {
            throw new InvalidDataException(
                $"{formJsonPath}: root is not a JSON object, so this is " +
                "not a form document FormDocument.JsonFromContract wrote.");
        }
        using var buffer = new MemoryStream();
        using (var writer = new Utf8JsonWriter(buffer))
        {
            writer.WriteStartObject();
            int kept = 0;
            foreach (JsonProperty property in document.RootElement.EnumerateObject())
            {
                if (property.NameEquals("study") ||
                    property.NameEquals("thrustMesh"))
                {
                    continue;
                }
                property.WriteTo(writer);
                kept++;
            }
            writer.WriteEndObject();
            if (kept == 0)
            {
                throw new InvalidDataException(
                    $"{formJsonPath}: nothing left once 'study' and " +
                    "'thrustMesh' are dropped -- this is not a form " +
                    "document, or the two added keys have changed name.");
            }
        }
        return Encoding.UTF8.GetString(buffer.ToArray());
    }

    /// <summary>The Result, exactly as the plugin's own ResultDto would
    /// carry it after a live solve.</summary>
    public static object LoadResultDto(Assembly plugin, string formJsonPath)
    {
        Type contractJsonType = RequireType(plugin, "Contracts.ContractJson");
        Type resultDtoType = RequireType(plugin, "Contracts.ResultDto");
        MethodInfo openDeserialize = contractJsonType
            .GetMethods(BindingFlags.Public | BindingFlags.Static)
            .Single(method =>
                method.Name == "Deserialize" && method.IsGenericMethodDefinition);
        MethodInfo deserialize = openDeserialize.MakeGenericMethod(resultDtoType);
        string contractJson = ExtractResultContractJson(formJsonPath);
        try
        {
            return deserialize.Invoke(null, new object?[] { contractJson })
                ?? throw new InvalidOperationException(
                    $"{formJsonPath}: Deserialize<ResultDto> returned null.");
        }
        catch (TargetInvocationException wrapped) when (wrapped.InnerException is not null)
        {
            throw wrapped.InnerException;
        }
    }

    /// <summary>The SkinNet the engine itself would build from this Result:
    /// SkinPatterns.ReadNet(ResultDto), by reflection. Null exactly where
    /// ReadNet itself returns null (an FD Result) -- not a loader failure.
    /// </summary>
    public static object? LoadNet(Assembly plugin, object resultDto)
    {
        Type skinPatternsType = RequireType(plugin, "Components.SkinPatterns");
        MethodInfo readNet =
            skinPatternsType.GetMethod("ReadNet", BindingFlags.Public | BindingFlags.Static)
            ?? throw new MissingMethodException(
                "Ananke.COMPAS.Native.Components.SkinPatterns.ReadNet(ResultDto) not found.");
        try
        {
            return readNet.Invoke(null, new[] { resultDto });
        }
        catch (TargetInvocationException wrapped) when (wrapped.InnerException is not null)
        {
            throw wrapped.InnerException;
        }
    }

    public static (object Result, object? Net) Load(Assembly plugin, string formJsonPath)
    {
        object result = LoadResultDto(plugin, formJsonPath);
        object? net = LoadNet(plugin, result);
        return (result, net);
    }

    public static Type RequireType(Assembly plugin, string suffix)
    {
        string fullName = $"Ananke.COMPAS.Native.{suffix}";
        return plugin.GetType(fullName, throwOnError: true)
            ?? throw new InvalidOperationException($"Type '{fullName}' missing.");
    }
}
```

`ReflectionUtil.cs` carries the generic accessors this and the diagnosis driver both need
(`Get`/`GetInt`/`GetDouble`/`GetBool`/`GetString`/`GetList`/`GetIntList`/`GetDoubleList`/
`GetStringList`/`GetTuple`/`GetTupleList`/`RequireStatic`/`Invoke`) — full text at
tests/net_diagnosis/ReflectionUtil.cs in the scratch build; omitted here for length, but every
method is under ten lines and none of it is specific to skin diagnosis. It is what makes reading an
internal record's fields off a dynamically loaded assembly bearable.

**One live trap this task hit and is recording so it is not repaid**: `MethodInfo.Invoke(object?,
object?[])` is not itself a `params` method, but a caller's own `params object?[] args` wrapper is.
Passing a single reference-type-array-typed local (e.g. `double[][] outline`) as the sole trailing
argument to such a wrapper is array-covariant with `object?[]` (`double[]` is a reference type), so
the compiler hands the array straight through as the whole params array — unpacking every corner as
a separate argument — instead of wrapping it as one argument. That produced
`TargetParameterCountException` the first time this ran (`PlanInteriorPoint(outline)` against a
1-parameter method receiving 13 arguments). The fix is an explicit `(object)` cast at the call site
whenever the sole argument's static type is itself an array. Two call sites in `Program.cs` needed
it; the fix is in place and commented at both.

### 1.3 Verification: loader counts against the JSON's own numbers

All eight studies loaded cleanly, first attempt of the corrected build. Every count the loader
produced from `SkinNet` matched the ground truth read **independently**, straight off the raw JSON
via a second, un-related parse path (not the loader's own extraction), for every study:

| Study | Vertices (form/net) | Faces raw / triangulated | Edges (equilib./net) | Supports (mappings/rim) | Seed groups | Match |
|---|---:|---:|---:|---:|---:|:---:|
| 2 sided vault | 441 / 441 | 400 / 800 | 800 / 800 | 42 / 42 | 2 | yes |
| 2 sided vault Hex | 661 / 661 | 600 / 1200 | 1200 / 1200 | 63 / 63 | 3 | yes |
| 3 sided vault | 661 / 661 | 600 / 1200 | 1200 / 1200 | 63 / 63 | 3 | yes |
| 3 sided vault Hex | 661 / 661 | 600 / 1200 | 1200 / 1200 | 63 / 63 | 3 | yes |
| 4 sided vault | 881 / 881 | 800 / 1600 | 1600 / 1600 | 84 / 84 | 4 | yes |
| 4 sided vault Hex | 881 / 881 | 800 / 1600 | 1600 / 1600 | 84 / 84 | 4 | yes |
| 5 sided vault | 1101 / 1101 | 1000 / 2000 | 2000 / 2000 | 105 / 105 | 5 | yes |
| 6 sided vault | 1321 / 1321 | 1200 / 2400 | 2400 / 2400 | 126 / 126 | 6 | yes |

`RimDropped` and `EdgesDropped` were 0 on every study: nothing was silently discarded mapping form
ids to net indices. The face count doubles exactly on triangulation because every face on every one
of his nets is a quad (2 triangles each), consistent with `SkinPatterns.Triangulate`'s documented
behaviour.

The "Seed groups" column (`SkinNet.SeedGroups`, distinct values excluding -1) is a genuinely useful
by-product: it equals the vault's own side count on every study (2-sided has 2 disconnected support
groups, 6-sided has 6). This matters directly for section 3 — the seam/closer machinery is gated on
having 2 or more seed groups, and every one of his nets clears that gate structurally, by a wide
margin.


## 2. Per-study measurement table

Ground truth for this table is the pattern actually **confirmed** to match his exported
`-skin.json` sidecar byte-for-count (section 4). For the three Hex studies that is Pattern 1
(hexagonal); for the other five it is Pattern 0 (courses), which is also the only pattern those
five ever ran under his settings.

| Study (matching pattern) | Cells | Courses | Cap: shape | Cap oversized | Uncovered residue | Duplicate/overlap witnesses | Band refused → closed | Sliver stones under floor |
|---|---:|---:|---|:---:|---|---:|---|---:|
| 2 sided vault (courses) | 215 | 19 | ONE polygon, **4 corners** (a diamond) | **yes**, girth 2.85 m > 2.50 m ceiling | none reported | 0 | 1 seam → 16 stones | 0 |
| 2 sided vault Hex (hexagonal) | 226 | 17 | none (honeycomb has no cap; rim is 74 seven-sided cells) | n/a | none reported | **127/353 = 36%** dropped as overlap | 0 (closer never runs for this pattern) | 0 |
| 3 sided vault (courses) | 461 | 19 | ONE polygon, 6 corners | yes, girth 4.97 m | **0.3316 m² at the closer band itself**, course 14, field 7.0-7.5 m, plan centre (0,0) | 0 | 1 seam → 42 stones (yet 0.33 m² still open) | 0 |
| 3 sided vault Hex (hexagonal) | 226 | 17 | none | n/a | none reported | **127/353 = 36%** dropped | 0 | 0 |
| 4 sided vault (courses) | 752 | 20 | ONE polygon, 4 corners | no | none reported | 4/756 = 0.5% dropped | 1 seam → 76 stones | **3, worst = 0.000 m (a genuinely zero-width piece)** |
| 4 sided vault Hex (hexagonal) | 381 | 18 | none | n/a | none reported | **252/633 = 40%** dropped | 0 | **25/381 = 6.6%, worst = 0.029 m (against a 0.10 m floor)** |
| 5 sided vault (courses) | 831 | 20 | ONE polygon, 5 corners | no | none reported | 8/839 = 1% dropped | 1 seam → 80 stones | 0 |
| 6 sided vault (courses) | 908 | 20 | ONE polygon, 12 corners | no | none reported | 8/916 = 1% dropped | 1 seam → 84 stones | 0 |

Interior-sampling deviation (max, non-cap cells, corner-average height vs the net's own lifted
height at the cell's plan interior point — a pure-arrays proxy for how far a cell's flat top face
departs from the true surface): worst was 0.097 m on 2 sided vault (four symmetric cells at course
18, the course directly below the diamond cap), against 0.008-0.037 m typical elsewhere. That
0.097 m sits at exactly the course that carries the oversized diamond cap, on the study that
matches Param's own "lens void with a diamond inside" description — the geometry most stretched by
that cap is the geometry showing the worst flat-face departure, which is the numeric shape of the
same defect rather than a coincidence.

Every warning line quoted in this table is the **actual text** `SkinComponent.SolveNative` would
put on the canvas, reproduced by calling its own internal static line-builder methods
(`LostCellsWarningLine`, `UncoveredRegionsWarningLine`, `TransitionSeamLine`, `OddCellsLine`) by
reflection against the counts measured above, not paraphrased.


## 3. Fix-by-fix verdict: does it reach his geometry?

Research pass located each fix's exact gate in the source (file:line citations below); this
harness then instrumented the gate directly against his eight nets. Combined verdicts follow.

### 3.1 Uniform course heights — ALIVE, firing correctly

`BandCount` (SkinPatterns.cs ~6866-6880) folds a would-be final course under a quarter of Course
Height into the course below rather than shipping it as its own sliver row. Measured directly: the
net's own field range (`LevelRange`, on the blended net at his Course Height) gives a naive
`ceil(rise / 0.5)` course count; compared against the engine's actual `CourseCount`:

| Study | Naive course count | Actual CourseCount | Absorption fired? |
|---|---:|---:|:---:|
| 2 sided vault | 20 | 19 | yes |
| 2/3 sided vault Hex, 3 sided vault | 20 | 19 | yes (all three share this mesh) |
| 4 / 5 / 6 sided vault | 20 | 20 | not needed |

The fix reaches his geometry and does the documented thing on 4 of 8 studies; the other 4 simply
had no sliver row to absorb. No defect here.

### 3.2 Ridge plateau coverage — reaches geometry rarely, and does not resolve what it finds

`BandUncoveredArea` + `SliverFloor` + `FormatUncoveredRegion` feed `UncoveredRegions`
(SkinPatterns.cs 633-654, field at 652). Its ridge-crest branch is gated tightly: `isCapBand &&
band.Depth==0 && uppers.Count==2 && both open && seams.Count>0`, and only reports when the residual
area exceeds `SliverFloor`. Measured: it fired on exactly one canvas-matching study (3 sided vault),
naming a 0.3316 m² hole. It did **not** fire on 2 sided vault, the study whose oversized diamond cap
matches Param's "lens void" description most directly — by design (section 3.4), that shape class
is outside this detector's remit. And where it did fire, the hole it names is still open: the
closer band it is describing had already reported "1 seam CLOSED with 42 stones" in the same solve.
A detector that correctly measures a hole and a closer that reports "CLOSED" over the same patch of
surface is exactly the kind of contradiction that erodes trust in these fixes; both readings come
from the same `SkinPatternResult`, so this is not a measurement artefact on this harness's side.

### 3.3 Crest starve — gate not directly instrumented this pass; circumstantial evidence it is too narrow

FIX 3 ("ridge-crest closer starve", SkinPatterns.cs 4820-4875) is gated by `seamRescue`: it only
engages when the slab's other guide family has degenerated to near-nothing (`Sum(Length) < size`).
This harness did not instrument that boolean directly (a follow-up item, section 5). But the
residual 0.3316 m² hole measured on 3 sided vault sits at the closer band the rescue exists to
protect, and the rescue did not prevent it. That is consistent with a rescue gated on total
degeneracy failing to catch a partial shortfall — the more common real-world case — but this is
inference from a downstream symptom, not a direct reading of `seamRescue`'s own return value, and it
should be read as circumstantial pending that direct instrumentation. Separately: rule 2.6.3's
"crown disc" bisection is confirmed **dead code** by the codebase's own comment (SkinComponents.cs
1138-1151, "the whole-branch review found this engine never built that apex") — `CellSurface` uses
the `PlanInteriorPoint`/`LiftPlanPoint` fan apex unconditionally instead. Nothing in this run
depends on the crown disc, so its deadness is confirmed but moot.

### 3.4 Cap crescents (G3, "the lens void with a diamond inside") — never reported, whatever the underlying build does

`CapPolygonOutline` (SkinComponents.cs 3977-4122) handles concave dips unconditionally and clears a
convex "crescent" only when a span has no concave overlap and the lens area exceeds the sliver
floor. `UncoveredRegions`' own doc comment states plainly that it does **not** audit this class
(line 643). Measured consequence: 2 sided vault ships a real, oversized (girth 2.85 m against a
2.50 m ceiling), 4-cornered — literally diamond-shaped — crown cap, at the worst interior-sampling
deviation of any cell on any study (0.097 m), and the **only** warning it produces is the generic
"1 crown cap above the maximum piece size" line. Nothing names the shape, the void, or the
deviation. This is the fix Param is most directly complaining about, and the diagnostic surface
gives him nothing beyond "your cap is big" to go on. Verdict: whatever `CapPolygonOutline`'s own
crescent-clearing logic does internally, **no counter or warning in the shipped diagnostics
reaches the author for this defect class at all.**

### 3.5 Four-corner merge holes — general safety net measured dead on at least one real net

`CloseFreeEdgeWedge` (`guides.Count == 4` gate, SkinPatterns.cs 7552-7583) was not directly
triggered on any of the eight studies (no four-guide wedge situation arose). The broader
`MergeShortPieces` safety net (SkinPatterns.cs 7007-7084, fires on any span `<= minimumPiece` with a
neighbour) reported **zero merges on all eight studies** (`MergedPieces`, `MergedShortKept`,
`MergedStillShort` all 0 everywhere). On 4 sided vault, the same solve that reports zero merges also
ships 3 cells under the 0.10 m sliver floor, the worst a literal **0.000 m span** — a genuinely
degenerate, zero-width stone, present in the exact 752-cell output that matches his exported
sidecar exactly. `CloserUndersized` (the dedicated undersized-closer-stone counter) is also 0 for
this study, so these are not closer stones falling through a different net; they are ordinary
courses-engine cells that the merge pass should have caught and did not. Verdict: **the merge
safety net is dead on this real geometry** — it is not merely failing to reach an edge case, it
failed to reach a zero-width degenerate cell sitting in his actual shipped output.

### 3.6 Walls-first thickening — the one guard this harness CAN run measures clean; the rest is unreachable here

`ThickenCellSurface` needs RhinoCommon's native core and cannot run in this harness (confirmed:
`Brep.CreateFromCornerPoints` throws `DllNotFoundException` outside Rhino, per the codebase's own
prior measurement, SkinComponents.cs). But `CellOffsetImpossible`/`EdgeOffsetImpossible`
(SkinComponents.cs 1548-1619) are pure `double[]`/`Math.*` — no RhinoCommon type appears in either
body — and this harness confirmed they run headless. Sampled at three representative shell
thicknesses (0.02, 0.05, 0.10 m) against every non-cap cell on every one of the eight studies: **0
cells reported impossible at any thickness, on any study.** Verdict: the concave-curvature fold
this guard exists to catch is not present on any of his real geometry at plausible thicknesses. If
he is still seeing wall/join failures on canvas, this specific guard is not the explanation; the
cause is either an ordinary Brep-join tolerance failure (only reachable by
`scripts/rhino_skin_surface.py` running inside Rhino, per the codebase's own stated limitation) or
something in the Gaps mechanism this harness cannot exercise without a live native core. This is a
genuine "cannot measure further from here" rather than a "dead" finding, and should not be
conflated with one.

### 3.7 Seam closer stones — ALIVE and firing on every courses-pattern study; architecturally absent from the hexagonal pattern

`CloserBand` engaged and closed the one refused band on all five canvas-matching courses-pattern
studies (16, 42, 76, 80, 84 stones respectively — never zero). This is the most robustly "alive" of
the seven fixes measured here. But it is wired, by explicit, documented deferral (SkinPatterns.cs,
"rule 2.1's own deferral"), to the courses engine alone: `ClosedSeams` and `CloserCells` were **0 on
every one of the three hexagonal runs**, confirmed both by the code (deferral is stated, not
inferred) and by direct measurement. Combined with 3.2's finding that even a successful closer can
leave a real hole behind, and with the honeycomb's own 36-40% overlap-drop rate (3.8 below) having
no closer to call on at all, this deferral is a real, structural gap for the pattern Param describes
as his "really troublesome" one.

### 3.8 The honeycomb pattern's own defect, measured directly (not one of the seven named fixes, but the loudest number in this dataset)

On all three Hex studies, the hexagonal pattern proposed roughly twice as many cells as it kept,
dropping the rest as "overlapping a cell already kept": 127 of 353 (36%) on both 2 and 3 sided
vault Hex, 252 of 633 (40%) on 4 sided vault Hex. `SevenSidedCells` (the honeycomb's own documented
rim-cell class, rule 4.3) accounts for 74, 74 and 208 of the kept cells respectively — a large
fraction of the pattern's surviving stones are these rim cells rather than ordinary hexagons. 4
sided vault Hex additionally ships 25 of 381 cells (6.6%) under the 0.10 m sliver floor, the
smallest at 0.029 m, roughly a third of the floor. None of this is caught by the seam-closer
machinery (structurally absent here, 3.7) or by `UncoveredRegions` (reported empty on all three).


## 4. Sidecar comparison: is the harness's reproduction faithful?

Compared cell-by-cell count and per-course tally between what this harness computed and what the
plugin itself wrote to `<study>-skin.json` on Param's own machine:

| Study | Pattern that matches | Cells (harness / sidecar) | Per-course tally matches |
|---|---|---:|:---:|
| 2 sided vault | courses | 215 / 215 | yes, all 19 courses |
| 3 sided vault | courses | 461 / 461 | yes, all 19 courses |
| 4 sided vault | courses | 752 / 752 | yes, all 20 courses |
| 5 sided vault | courses | 831 / 831 | yes, all 20 courses |
| 6 sided vault | courses | 908 / 908 | yes, all 20 courses |
| 2 sided vault Hex | hexagonal | 226 / 226 | yes, all 17 courses |
| 3 sided vault Hex | hexagonal | 226 / 226 | yes, all 17 courses |
| 4 sided vault Hex | hexagonal | 381 / 381 | yes, all 18 courses |

Every one of the eight studies matches exactly, **once the correct pattern is compared against**.
Reported loudly rather than papered over, per this task's own instruction: the courses pattern does
**not** match any of the three Hex sidecars (461 cells against a 226-cell sidecar for both 2 and
3 sided vault Hex; 752 cells against a 381-cell sidecar for 4 sided vault Hex) — this is not a
harness defect, it is proof that Param's canvas was set to Pattern 1 (hexagonal) when he exported
those three sidecars, not Pattern 0. Both numbers are reported in the raw JSON for every study so
this conclusion is checkable rather than asserted. Where the pattern is matched correctly, the
reproduction is exact to the cell and to the course, on nets from 215 to 908 cells: the harness's
geometry pipeline (ReadNet, Blended, Courses/Hexagonal) is faithful to what the plugin itself
produced.


## 5. Prioritised list of what must change, each grounded in a measured number

1. **The honeycomb pattern's overlap-drop rate (36-40% of every proposal, all three Hex studies)**
   is the single largest, most confidently measured defect in this dataset, and it matches Param's
   own description of the hex skin as "really troublesome". No rescue mechanism currently reaches
   it: the seam closer is architecturally wired to the courses engine only (3.7), and
   `UncoveredRegions` reports nothing on any of the three (it audits slab/ridge residues, not
   overlap drops). This is the first thing to fix.

2. **A literal zero-width cell ships in the 4 sided vault courses output** (min piece span
   0.000 m, in the exact 752-cell set that matches his exported sidecar), while
   `MergeShortPieces` reports zero merges anywhere across all eight studies. The general merge
   safety net needs its gate re-examined against real, non-synthetic spans: something is preventing
   it from ever firing on this geometry, not merely from firing enough.

3. **The crown-cap defect Param is photographing has no dedicated diagnostic at all.** 2 sided
   vault's crown cap is a real, oversized, 4-cornered (diamond) polygon, sitting at the worst
   interior-sampling deviation measured on any cell in this dataset (0.097 m), and the only warning
   it produces is a generic oversized-cap line. `UncoveredRegions` explicitly excludes this shape
   class by design. Before claiming a fix for "cap crescents" again, it needs its own named
   counter, not a shared one that already means something else.

4. **A closer band can report "CLOSED" while a real, separately-measured hole remains at the same
   location** (3 sided vault: 1 seam closed with 42 stones, and a 0.3316 m² hole at that same band,
   course, and plan centre). This contradiction between two readings of one `SkinPatternResult` is
   exactly the kind of thing that would make a screenshot look unchanged between rounds even when
   code has moved: the "closed" claim and the uncovered-area claim need to agree, or the "closed"
   wording needs to soften to "partially closed" until they do.

5. **`seamRescue`'s own gate (crest starve, FIX 3) needs direct instrumentation**, not just
   inference from a downstream symptom. This pass measured the residual hole but not the boolean
   that was supposed to prevent it; a follow-up run should log `slabOtherFamily.Sum(Length)` against
   `size` for every band on every study to confirm whether the gate is simply never met on real
   nets (a partial-degeneracy case, not a total one) or whether it is met and the rescue itself is
   insufficient.

6. **Walls-first thickening's array-math guard (`CellOffsetImpossible`) measured completely clean**
   (0 impossible cells, 0.02-0.10 m, all eight studies): if wall/join defects are still visible on
   canvas, look inside Rhino at the actual Brep join (`ThickenFailureLine`'s own failure counters,
   or `scripts/rhino_skin_surface.py`), not at this guard. Confirmed unreachable from a headless
   harness, not confirmed dead.

7. **Uniform course heights (BandCount's absorption) and the seam-closer's basic engagement
   (3.1, 3.7) are both measured alive and doing what they claim** on every study where their
   precondition is met. These are not where the remaining defects live; re-testing them is not a
   priority.
