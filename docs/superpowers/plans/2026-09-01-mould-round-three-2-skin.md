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

## Phase two: skin, Tasks 12 to 32

Spec, and the authority for every task below:
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\docs\superpowers\specs\2026-09-01-skin-buildability-design.md

Position in the build: SECOND. These tasks touch
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Components\SkinPatterns.cs,
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Components\SkinComponents.cs,
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Components\DeliveryComponents.cs
and
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\tests\native_smoke\Program.cs.
They depend on nothing in the columns work and must not be interleaved with it.

### The standing commands

Every task's build step is this, run from the repository root. The output goes to scratch and never to
the repository's own bin, which OneDrive syncs.

```powershell
dotnet build "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Ananke.COMPAS.Native.csproj" -c Release -o "C:\Users\Param\AppData\Local\Temp\ananke-skin-build" --nologo
```

Every task's test step is this.

```powershell
dotnet run --project "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\tests\native_smoke" -- "C:\Users\Param\AppData\Local\Temp\ananke-skin-build\Ananke.COMPAS.gha"
```

Every task's clash scan is this, from the repository root, before the build and again before the commit.

```bash
find . -name "*Name clash*" -not -path "./.git/*"
```

Installing to Grasshopper is not part of Tasks 12 to 31. It happens ONCE in this phase, in TASK 32'S
OWN STEP 6, through
C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Build-And-Install.ps1
with Rhino closed, and Param is then told to restart Rhino, because the walk list Task 32 writes is a
walk he takes in Rhino. It is the second of the four installs named in the install policy at the head
of this plan.

The items this phase's spec leaves open are gathered at the end of this plan, under "What the three specs leave open for Param".

---

### Task 12: the net carries a rim, force edges and a rim-distance field

**Files:**
- Modify: plugin/native_v02/Components/SkinPatterns.cs:31-40 (the SkinNet record) and after
  SkinPatterns.cs:285 (the new field methods)
- Test: tests/native_smoke/Program.cs, new `ValidateSkinField` plus its entry in `Run` after the
  `ValidateSkinNet` block at Program.cs:616-630

**Interfaces:**
- Consumes: `SkinPatterns.Triangulate(IReadOnlyList<double[]>, IReadOnlyList<int[]>)` and
  `SkinPatterns.Distance(double[], double[])`, both already in the file.
- Produces: `internal sealed record SkinNetEdge(int A, int B, double Force)`;
  `SkinNet(IReadOnlyList<double[]> Vertices, IReadOnlyList<int[]> Faces, IReadOnlyList<int> Rim,
  IReadOnlyList<SkinNetEdge> Edges)` with a two-argument convenience constructor and a computed
  `IReadOnlyList<double> Levels { get; }`;
  `public static IReadOnlyList<double> SkinPatterns.RimDistanceField(IReadOnlyList<double[]> vertices,
  IReadOnlyList<int[]> faces, IReadOnlyList<int> rim)`.

Rule 1.2.2 asks for the three new members "each declared with a default so that every existing
two-argument construction in the harness goes on compiling". A C# optional parameter does not carry
that promise through the harness, because the harness constructs the net with
`Activator.CreateInstance(netType, new object[] { vertices, faces })` (Program.cs:9796-9797 and
:9384-9386) and the default binder does not fill optional parameters. An explicit two-argument
constructor does carry it, in source and through reflection alike, so that is what is written.

1. [ ] Add the harness fixture and check. In tests/native_smoke/Program.cs, beside the other Skin
   fixtures (after `SkinBarrelScrambledNet` at Program.cs:8480), add:

```csharp
    /// <summary>
    /// A flat rectangular plate, x 0 to 10 and y 0 to 4 at a 0.25 m pitch,
    /// z = 0 throughout, with the y = 0 long edge as its rim. Check 12.1(b)
    /// measures the field on it against the perpendicular distance, which
    /// pins the triangle update rather than the edge fallback; check 12.1(a)
    /// reads the rim's own zeros off it, and rule 1.5.4 reads its Z range,
    /// which is nothing at all.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces, int[] Rim) SkinPlateNet()
    {
        var vertices = new List<double[]>();
        for (int j = 0; j <= 16; j++)
        {
            for (int i = 0; i <= 40; i++)
                vertices.Add(new double[] { 0.25 * i, 0.25 * j, 0.0 });
        }
        var faces = new List<int[]>();
        for (int j = 0; j < 16; j++)
        {
            for (int i = 0; i < 40; i++)
            {
                int a = j * 41 + i;
                faces.Add(new[] { a, a + 1, a + 42, a + 41 });
            }
        }
        var rim = new List<int>();
        for (int i = 0; i <= 40; i++)
            rim.Add(i);
        return (vertices.ToArray(), faces.ToArray(), rim.ToArray());
    }

    /// <summary>
    /// A square-plan plate, 8 by 8 at 1 m, carried on FOUR PAIRWISE
    /// NON-ADJACENT support vertices: its own corners. It is the fixture
    /// rule 1.4.1(b) exists for. No triangle anywhere has two frozen corners
    /// at the first pop, so an update rule written only as the two-frozen
    /// triangle case never relaxes anything and leaves every non-rim vertex
    /// at positive infinity.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces, int[] Rim)
        SkinFourSupportNet()
    {
        var vertices = new List<double[]>();
        for (int j = 0; j <= 8; j++)
        {
            for (int i = 0; i <= 8; i++)
                vertices.Add(new double[] { i, j, 0.0 });
        }
        var faces = new List<int[]>();
        for (int j = 0; j < 8; j++)
        {
            for (int i = 0; i < 8; i++)
            {
                int a = j * 9 + i;
                faces.Add(new[] { a, a + 1, a + 10, a + 9 });
            }
        }
        return (
            vertices.ToArray(),
            faces.ToArray(),
            new[] { 0, 8, 72, 80 });
    }

    /// <summary>The Levels array off a constructed net.</summary>
    private static double[] SkinLevels(object net) =>
        ((IEnumerable)net.GetType().GetProperty("Levels")!.GetValue(net)!)
            .Cast<double>()
            .ToArray();

    /// <summary>A rim-bearing, force-bearing net through the four-argument
    /// constructor.</summary>
    private static object SkinNetWith(
        Type netType,
        Type edgeType,
        double[][] vertices,
        int[][] faces,
        int[] rim,
        (int A, int B, double Force)[] forces)
    {
        Array edges = Array.CreateInstance(edgeType, forces.Length);
        for (int at = 0; at < forces.Length; at++)
        {
            edges.SetValue(
                Activator.CreateInstance(
                    edgeType,
                    new object[]
                    {
                        forces[at].A, forces[at].B, forces[at].Force
                    }),
                at);
        }
        return Activator.CreateInstance(
            netType,
            new object[] { vertices, faces, rim, edges })!;
    }
```

2. [ ] Add the check itself, beside `ValidateSkinNet` in tests/native_smoke/Program.cs:

```csharp
    /// <summary>
    /// The rim-distance field (spec 2026-09-01 section 1), checks 12.1(a),
    /// (b), (e) and (i). The field is the scalar the tracer will cut, so it
    /// is measured on the net itself, before anything downstream reads it.
    /// </summary>
    private static void ValidateSkinField(Assembly plugin)
    {
        Type netType = RequireComponentType(plugin, "SkinNet");
        Type edgeType = RequireComponentType(plugin, "SkinNetEdge");
        var noForces = Array.Empty<(int, int, double)>();

        // 12.1(a) and 12.1(b): the plate.
        (double[][] plateVertices, int[][] plateFaces, int[] plateRim) =
            SkinPlateNet();
        object plate = SkinNetWith(
            netType, edgeType, plateVertices, plateFaces, plateRim, noForces);
        double[] plateLevels = SkinLevels(plate);
        foreach (int seed in plateRim)
        {
            if (plateLevels[seed] != 0.0)
            {
                throw new InvalidOperationException(
                    "Every rim vertex is seeded at 0 (rule 1.4.1); vertex " +
                    $"{seed} reads {plateLevels[seed]}.");
            }
        }
        for (int at = 0; at < plateLevels.Length; at++)
        {
            double expected = plateVertices[at][1];
            if (plateLevels[at] < 0.0 ||
                Math.Abs(plateLevels[at] - expected) > 0.02 * expected + 1.0e-9)
            {
                throw new InvalidOperationException(
                    "On a flat plate rimmed along y = 0 the field is the " +
                    "PERPENDICULAR distance from that edge to within 2 per " +
                    $"cent (check 12.1(b)); vertex {at} at y = {expected} " +
                    $"reads {plateLevels[at]}.");
            }
        }

        // 12.1(i): a rim of pairwise non-adjacent vertices.
        (double[][] cornerVertices, int[][] cornerFaces, int[] cornerRim) =
            SkinFourSupportNet();
        object corners = SkinNetWith(
            netType, edgeType, cornerVertices, cornerFaces, cornerRim,
            noForces);
        double[] cornerLevels = SkinLevels(corners);
        for (int at = 0; at < cornerLevels.Length; at++)
        {
            if (!double.IsFinite(cornerLevels[at]))
            {
                throw new InvalidOperationException(
                    "A rim of FOUR pairwise non-adjacent supports must give " +
                    "a finite field at every vertex (check 12.1(i)): the " +
                    "one-frozen edge relaxation of rule 1.4.1(b) is what " +
                    "STARTS the front, and without it nothing is ever " +
                    $"relaxed. Vertex {at} reads {cornerLevels[at]}.");
            }
        }

        // 12.1(e): an EMPTY rim keeps the field identical, byte for byte.
        (double[][] barrelVertices, int[][] barrelFaces) = SkinBarrelNet();
        (double[][] domeVertices, int[][] domeFaces) = SkinDomeNet();
        foreach ((double[][] vertices, int[][] faces, string label) fixture in
                 new[]
                 {
                     (barrelVertices, barrelFaces, "barrel"),
                     (domeVertices, domeFaces, "dome")
                 })
        {
            object bare = Activator.CreateInstance(
                netType,
                new object[] { fixture.vertices, fixture.faces })!;
            double[] levels = SkinLevels(bare);
            for (int at = 0; at < levels.Length; at++)
            {
                if (levels[at] != fixture.vertices[at][2])
                {
                    throw new InvalidOperationException(
                        "With an EMPTY rim the field IS the vertices' own Z " +
                        "(rule 1.2.3), byte for byte, which is what keeps " +
                        "six adversarial rounds of pins alive; on the " +
                        $"{fixture.label} vertex {at} reads {levels[at]} " +
                        $"against z {fixture.vertices[at][2]}.");
                }
            }
        }
    }
```

3. [ ] Wire it into `Run`, immediately after the `ValidateSkinNet` block at Program.cs:616-630:

```csharp
        try
        {
            ValidateSkinField(plugin);
            Console.WriteLine(
                "PASS  Skin rim-distance field: a rimmed flat plate reads " +
                "its own perpendicular distance to within 2 per cent and " +
                "its rim reads zero; a plate carried on four pairwise " +
                "non-adjacent supports is FINITE at every vertex, which is " +
                "the one-frozen edge relaxation doing the starting; and a " +
                "net built through the two-argument constructor has an " +
                "EMPTY rim, so its field is the vertices' own Z byte for " +
                "byte and every shipped pin still measures what it did.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Skin rim-distance field: {DescribeException(exception)}");
        }
```

4. [ ] Build and run the harness. It must fail with
   `Type 'Ananke.COMPAS.Native.Components.SkinNetEdge' was not found.`

5. [ ] Replace the SkinNet record at SkinPatterns.cs:31-40 with:

```csharp
/// <summary>One force edge of the net: two NET vertex indices, A less than
/// B, and the member force in kN (spec 2026-09-01 rule 1.2.2(b)). The
/// indices are NET indices and not equilibrium ones; ReadNet maps them, and
/// rule 1.3.5 says what goes wrong silently when it does not.</summary>
internal sealed record SkinNetEdge(int A, int B, double Force);

internal sealed record SkinNet(
    IReadOnlyList<double[]> Vertices,
    IReadOnlyList<int[]> Faces,
    IReadOnlyList<int> Rim,
    IReadOnlyList<SkinNetEdge> Edges)
{
    /// <summary>The bare net: no rim, no forces. Rule 1.2.2 asks for
    /// defaults so that every existing two-argument construction goes on
    /// compiling AND goes on measuring what it measures today. An optional
    /// parameter would only honour the first half: the smoke harness builds
    /// its nets through Activator.CreateInstance, whose default binder does
    /// not fill optional parameters, so a two-argument construction there
    /// would stop finding a constructor at all. This one is found by both.
    /// </summary>
    public SkinNet(
        IReadOnlyList<double[]> vertices,
        IReadOnlyList<int[]> faces)
        : this(
            vertices,
            faces,
            Array.Empty<int>(),
            Array.Empty<SkinNetEdge>())
    {
    }

    /// <summary>The faces, triangulated. An all-triangle face list comes
    /// through untouched, so the invariant is idempotent and a net built
    /// from another net's faces is the same net.</summary>
    public IReadOnlyList<int[]> Faces { get; } =
        SkinPatterns.Triangulate(Vertices, Faces);

    /// <summary>The scalar the tracer cuts: geodesic distance from the rim
    /// in metres, or the vertices' own Z where the rim is empty (rules 1.2.1
    /// to 1.2.3). Computed once here, for the same reason the triangulation
    /// is: the harness builds its nets straight through this constructor, so
    /// a field that lived in ReadNet alone would be a field no fixture could
    /// measure. Triangulate is called a second time rather than the Faces
    /// property being read, because an instance property initialiser cannot
    /// see `this`; it is idempotent and returns the same list unchanged when
    /// every face is already a triangle.</summary>
    public IReadOnlyList<double> Levels { get; } =
        SkinPatterns.RimDistanceField(
            Vertices,
            SkinPatterns.Triangulate(Vertices, Faces),
            Rim);
}
```

6. [ ] Add the field itself to SkinPatterns, after `SplitPolygon` ends at SkinPatterns.cs:298:

```csharp
    // ---- the rim-distance field (spec 2026-09-01 section 1) -------------

    /// <summary>
    /// GEODESIC DISTANCE FROM THE RIM, one value per vertex, in metres
    /// (rule 1.2.1), by FAST MARCHING on the triangulated net: Dijkstra's
    /// structure with the edge relaxation replaced by the Kimmel and
    /// Sethian triangle update (rule 1.4.1).
    ///
    /// An EMPTY rim gives the vertices' own Z, which is rule 1.2.3 and the
    /// honest fallback of rule 1.7.4. A vertex unreachable from the rim
    /// across the triangulation keeps positive infinity, which rule 1.7.3
    /// excludes from the field range and counts.
    ///
    /// The field the engine DEFINES is the piecewise-linear interpolant of
    /// these vertex values over the triangles (rule 1.4.4). The chord the
    /// tracer draws between two edge crossings is the exact level set of
    /// that interpolant on a planar triangle, for the same reason it was
    /// the exact level set of Z: a function affine on a plane has straight
    /// level sets. What is approximate is the relation between the
    /// interpolant and the true geodesic distance, and that approximation
    /// is the field's own definition rather than an error downstream of it.
    ///
    /// Cost is O(V log V) with a small constant, run once per net. It must
    /// NOT be cached across solves (rule 1.4.5): a Result whose vertices
    /// moved is a different field.
    /// </summary>
    public static IReadOnlyList<double> RimDistanceField(
        IReadOnlyList<double[]> vertices,
        IReadOnlyList<int[]> faces,
        IReadOnlyList<int> rim)
    {
        int count = vertices.Count;
        var levels = new double[count];
        if (rim.Count == 0)
        {
            for (int at = 0; at < count; at++)
                levels[at] = vertices[at][2];
            return levels;
        }
        for (int at = 0; at < count; at++)
            levels[at] = double.PositiveInfinity;

        var facesAt = new List<int>?[count];
        for (int face = 0; face < faces.Count; face++)
        {
            foreach (int corner in faces[face])
            {
                if (corner < 0 || corner >= count)
                    continue;
                (facesAt[corner] ??= new List<int>()).Add(face);
            }
        }

        var frozen = new bool[count];
        // A SortedSet of (value, vertex) IS the min-heap with rule 1.4.3's
        // tie-break built in: the tuple comparer falls through to the vertex
        // index when two tentative values are equal, so the field is a
        // property of the mesh's own numbering rather than of any traversal.
        // A vertex whose value improves is added again; the stale entry is
        // skipped when it pops, because the vertex is frozen by then.
        var heap = new SortedSet<(double Value, int Vertex)>();
        foreach (int seed in rim)
        {
            if (seed < 0 || seed >= count || levels[seed] == 0.0)
                continue;
            levels[seed] = 0.0;
            heap.Add((0.0, seed));
        }
        while (heap.Count > 0)
        {
            (double Value, int Vertex) top = heap.Min;
            heap.Remove(top);
            if (frozen[top.Vertex])
                continue;
            frozen[top.Vertex] = true;
            List<int>? incident = facesAt[top.Vertex];
            if (incident is null)
                continue;
            foreach (int face in incident)
            {
                int[] triangle = faces[face];
                if (triangle.Length != 3)
                    continue;
                for (int corner = 0; corner < 3; corner++)
                {
                    int c = triangle[corner];
                    if (frozen[c])
                        continue;
                    int a = triangle[(corner + 1) % 3];
                    int b = triangle[(corner + 2) % 3];
                    double offer;
                    if (frozen[a] && frozen[b])
                    {
                        offer = TriangleUpdate(
                            vertices[c], vertices[a], vertices[b],
                            levels[a], levels[b]);
                    }
                    else if (frozen[a])
                    {
                        offer = levels[a] +
                            Distance(vertices[a], vertices[c]);
                    }
                    else if (frozen[b])
                    {
                        offer = levels[b] +
                            Distance(vertices[b], vertices[c]);
                    }
                    else
                    {
                        // Neither end frozen: this triangle offers nothing
                        // on this pop (rule 1.4.1(c)).
                        continue;
                    }
                    if (offer < levels[c] - 1.0e-12)
                    {
                        levels[c] = offer;
                        heap.Add((offer, c));
                    }
                }
            }
        }
        return levels;
    }

    /// <summary>
    /// Rule 1.4.2: the planar wavefront solved on the triangle itself, which
    /// is planar by the net's own invariant. Where the characteristic
    /// direction falls outside the triangle, which an obtuse angle at the
    /// updated corner gives, the update falls back to the plain edge
    /// relaxation min(dA + |CA|, dB + |CB|). No unfolding across neighbours:
    /// the fallback is bounded, stated and cheap, and the cost of getting it
    /// slightly wrong is a course boundary a few millimetres off on a badly
    /// shaped triangle, against a CH of order 0.35 m on mesh edges of order
    /// 0.2 m.
    /// </summary>
    private static double TriangleUpdate(
        double[] c,
        double[] pa,
        double[] pb,
        double da,
        double db)
    {
        // A carries the SMALLER of the two known values; u is the difference.
        if (db < da)
        {
            (pa, pb) = (pb, pa);
            (da, db) = (db, da);
        }
        double b = Distance(c, pa);
        double a = Distance(c, pb);
        double fallback = Math.Min(da + b, db + a);
        if (!(a > 1.0e-12) || !(b > 1.0e-12))
            return fallback;
        double cos =
            ((pa[0] - c[0]) * (pb[0] - c[0]) +
             (pa[1] - c[1]) * (pb[1] - c[1]) +
             (pa[2] - c[2]) * (pb[2] - c[2])) / (a * b);
        cos = Math.Min(Math.Max(cos, -1.0), 1.0);
        double u = db - da;
        double quadA = a * a + b * b - 2.0 * a * b * cos;
        if (!(quadA > 1.0e-18))
            return fallback;
        double quadB = 2.0 * b * u * (a * cos - b);
        double quadC = b * b * (u * u - a * a * (1.0 - cos * cos));
        double discriminant = quadB * quadB - 4.0 * quadA * quadC;
        if (discriminant < 0.0)
            return fallback;
        double t = (-quadB + Math.Sqrt(discriminant)) / (2.0 * quadA);
        if (!(t > u) || !(t > 0.0))
            return fallback;
        double lower = a * cos;
        double upper = Math.Abs(cos) > 1.0e-12
            ? a / cos
            : double.PositiveInfinity;
        double middle = b * (t - u) / t;
        if (!(middle > lower) || !(middle < upper))
            return fallback;
        return Math.Min(fallback, da + t);
    }
```

7. [ ] Build and run the harness. The new PASS line must appear and every existing Skin PASS line must
   still appear: rule 1.2.3's Z fallback is what keeps them.

8. [ ] Scan for clash files and commit.

```powershell
git add "plugin/native_v02/Components/SkinPatterns.cs" "tests/native_smoke/Program.cs"
git commit -m "feat(skin): the net carries a rim, force edges and a rim-distance field"
```

---

### Task 13: the fixtures rule 12.0 asks for first

**Files:**
- Modify: tests/native_smoke/Program.cs, beside the existing Skin fixtures (SkinBarrelNet at
  Program.cs:8404, SkinDomeNet at :8490), and `ValidateSkinField` from Task 12
- Test: tests/native_smoke/Program.cs, `ValidateSkinField` gains checks 12.1(c) and 12.1(g); new
  `ValidateSkinFixtures` plus its entry in `Run`

**Interfaces:**
- Consumes: `SkinNetWith(Type, Type, double[][], int[][], int[], (int, int, double)[])`,
  `SkinLevels(object)` from Task 12; `SkinPatterns.Hexagonal(SkinNet, double, double)` as shipped.
- Produces: `SkinHemisphereNet()`, `SkinTwoOculusNet()`, `SkinSerpentineNet()`,
  `SkinEllipticalDomeNet()`, `SkinDisconnectedNet()`, `SkinBarrelRim()`, `SkinBarrelForces()`,
  `SkinDomeRim()`, each returning plain arrays; and the SHIPPED honeycomb's withheld counts on the
  two-oculus and serpentine fixtures, recorded as the BEFORE of check 12.4(g).

Rule 12.0 is explicit that the fixtures come first and that the honeycomb's 26 to 49 and 38 to 62 per
cent were quoted against prose reconstructions nothing in this repository can rebuild. This task
builds the fixtures and takes the before-measurement while the honeycomb is still the shipped one.
Task 23 re-measures against it.

FIRST, ONE HOUSEKEEPING MOVE THIS TASK AND EVERY SKIN TASK AFTER IT DEPENDS ON. `Reading<T>(object,
string)` is used forty-two times by the new check methods of Tasks 13 to 32, but today it is not a
class-scope helper at all: it is a LOCAL function declared three separate times, inside three
unrelated methods, at tests/native_smoke/Program.cs:10074, :10678 and :10974. A new
`private static void ValidateSkinFixtures(Assembly)` cannot see any of them, and neither can any of
the other new methods, so Task 13 is the first task that would fail to compile and every later skin
task carries the same error. `SkinCells`, `RequireComponentType`, `RequireContractType`,
`CreateInstance`, `SetContractProperty`, `CreateResultDto` and `DescribeException` are genuinely
class-scope already and need nothing.

0. [ ] Promote `Reading<T>` to class scope. Add it beside `SkinCells` at tests/native_smoke/Program.cs:9622:

```csharp
    /// <summary>Read a property off a reflected object. Class-scope, because
    /// every Skin check method reads the pattern record this way; three
    /// identical local copies used to live inside three unrelated methods
    /// and no new method could see any of them.</summary>
    private static T Reading<T>(object owner, string name) =>
        (T)owner.GetType().GetProperty(name)!.GetValue(owner)!;
```

   then DELETE the three local declarations at :10074, :10678 and :10974. The call sites in those
   three methods bind to the class-scope one unchanged, so nothing else in the file moves. Build and
   run the harness once before going on: it must be green, with no new PASS line, which is what
   proves the move changed nothing.

1. [ ] Add the fixtures to tests/native_smoke/Program.cs, after `SkinPlateNet` from Task 12:

```csharp
    /// <summary>
    /// A HEMISPHERE of radius 3: 24 rings by 48 around, ring i at polar
    /// parameter phi = (pi / 2) (i / 24) from the base, the vertex at
    /// (R cos phi cos theta, R cos phi sin theta, R sin phi), quads between
    /// adjacent rings and triangles to the apex (0, 0, R). Ring 0 is the
    /// rim. Check 12.1(c) reads the apex against pi R / 2, which is the one
    /// closed form for a geodesic distance this repository can assert
    /// against.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces, int[] Rim)
        SkinHemisphereNet()
    {
        const int Rings = 24;
        const int Around = 48;
        const double Radius = 3.0;
        var vertices = new List<double[]>();
        for (int ring = 0; ring < Rings; ring++)
        {
            double phi = Math.PI / 2.0 * ring / Rings;
            for (int k = 0; k < Around; k++)
            {
                double theta = Math.PI * 2.0 * k / Around;
                vertices.Add(new[]
                {
                    Radius * Math.Cos(phi) * Math.Cos(theta),
                    Radius * Math.Cos(phi) * Math.Sin(theta),
                    Radius * Math.Sin(phi)
                });
            }
        }
        int apex = vertices.Count;
        vertices.Add(new[] { 0.0, 0.0, Radius });
        var faces = new List<int[]>();
        for (int ring = 0; ring + 1 < Rings; ring++)
        {
            for (int k = 0; k < Around; k++)
            {
                int next = (k + 1) % Around;
                faces.Add(new[]
                {
                    ring * Around + k,
                    ring * Around + next,
                    (ring + 1) * Around + next,
                    (ring + 1) * Around + k
                });
            }
        }
        for (int k = 0; k < Around; k++)
        {
            int next = (k + 1) % Around;
            faces.Add(new[]
            {
                (Rings - 1) * Around + k,
                (Rings - 1) * Around + next,
                apex
            });
        }
        var rim = new List<int>();
        for (int k = 0; k < Around; k++)
            rim.Add(k);
        return (vertices.ToArray(), faces.ToArray(), rim.ToArray());
    }

    /// <summary>
    /// Rule 12.0's `SkinTwoOculusNet`, in its own words. A plan grid over
    /// x in [0, 10] and y in [0, 6] at a 0.25 m pitch, so i runs 0 to 40 and
    /// j runs 0 to 24, vertices at (0.25 i, 0.25 j, z) with
    /// z = 2 sin(pi x / 10) sin(pi y / 6), which is zero on all four edges
    /// and 2 m at the centre. Quad faces between adjacent grid vertices,
    /// EXCEPT that a face is omitted where its plan centre lies within 1.0 m
    /// of (3, 3) or within 1.0 m of (7, 3), which cuts two oculi with
    /// stepped free edges. The rim is every boundary vertex of the
    /// rectangle, i = 0, i = 40, j = 0 or j = 24, and NOT the oculus edges,
    /// which is what makes this the fixture that measures rule 1.3.3 and
    /// rule 2.2.1(b) at once.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces, int[] Rim)
        SkinTwoOculusNet()
    {
        var vertices = new List<double[]>();
        for (int j = 0; j <= 24; j++)
        {
            for (int i = 0; i <= 40; i++)
            {
                double x = 0.25 * i;
                double y = 0.25 * j;
                vertices.Add(new[]
                {
                    x,
                    y,
                    2.0 * Math.Sin(Math.PI * x / 10.0) *
                        Math.Sin(Math.PI * y / 6.0)
                });
            }
        }
        var faces = new List<int[]>();
        for (int j = 0; j < 24; j++)
        {
            for (int i = 0; i < 40; i++)
            {
                double cx = 0.25 * i + 0.125;
                double cy = 0.25 * j + 0.125;
                bool inOculus =
                    Math.Sqrt((cx - 3.0) * (cx - 3.0) +
                              (cy - 3.0) * (cy - 3.0)) < 1.0 ||
                    Math.Sqrt((cx - 7.0) * (cx - 7.0) +
                              (cy - 3.0) * (cy - 3.0)) < 1.0;
                if (inOculus)
                    continue;
                int a = j * 41 + i;
                faces.Add(new[] { a, a + 1, a + 42, a + 41 });
            }
        }
        var rim = new List<int>();
        for (int j = 0; j <= 24; j++)
        {
            for (int i = 0; i <= 40; i++)
            {
                if (i == 0 || i == 40 || j == 0 || j == 24)
                    rim.Add(j * 41 + i);
            }
        }
        return (vertices.ToArray(), faces.ToArray(), rim.ToArray());
    }

    /// <summary>
    /// Rule 12.0's `SkinSerpentineNet`: a sheared strip vault, plan-injective
    /// by construction. For i = 0 to 60 and j = 0 to 12, with x = 0.25 i and
    /// t = (j - 6) / 6, the vertex is
    /// (x, 0.6 sin(2 pi x / 10) + 1.5 t, (1.4 + 0.6 sin(2 pi x / 7.5))
    /// cos(pi t / 2)). Quad faces between adjacent (i, j). Both long edges,
    /// j = 0 and j = 12, sit at z 0 and are the rim. The crest meanders
    /// between 0.8 m and 2.0 m along the strip, so a constant-Z level curve
    /// above 0.8 m breaks into SEVERAL components of differing length.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces, int[] Rim)
        SkinSerpentineNet()
    {
        var vertices = new List<double[]>();
        for (int j = 0; j <= 12; j++)
        {
            double t = (j - 6.0) / 6.0;
            for (int i = 0; i <= 60; i++)
            {
                double x = 0.25 * i;
                vertices.Add(new[]
                {
                    x,
                    0.6 * Math.Sin(2.0 * Math.PI * x / 10.0) + 1.5 * t,
                    (1.4 + 0.6 * Math.Sin(2.0 * Math.PI * x / 7.5)) *
                        Math.Cos(Math.PI * t / 2.0)
                });
            }
        }
        var faces = new List<int[]>();
        for (int j = 0; j < 12; j++)
        {
            for (int i = 0; i < 60; i++)
            {
                int a = j * 61 + i;
                faces.Add(new[] { a, a + 1, a + 62, a + 61 });
            }
        }
        var rim = new List<int>();
        for (int i = 0; i <= 60; i++)
        {
            rim.Add(i);
            rim.Add(12 * 61 + i);
        }
        return (vertices.ToArray(), faces.ToArray(), rim.ToArray());
    }

    /// <summary>
    /// Rule 12.0's `SkinEllipticalDomeNet`, which exists for rule 2.6.6's
    /// base case and for nothing else. SkinDomeNet's own construction with
    /// the plan circle replaced by an ellipse: rings at parameter h from 0
    /// to 1 in 24 steps and 96 vertices a ring, the vertex at ring h and
    /// angle theta sitting at (3 (1 - h) cos theta, 1.5 (1 - h) sin theta,
    /// 2 h), quads between adjacent rings and the last ring collapsed to the
    /// apex (0, 0, 2). The base ring at h = 0 is the rim. Because the plan is
    /// not a circle the cut locus inside the crown is a SEGMENT along the
    /// major axis rather than a point, so the girth at the top cut stays of
    /// the order of twice the segment's length however fine CH is made.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces, int[] Rim)
        SkinEllipticalDomeNet()
    {
        const int Rings = 24;
        const int Around = 96;
        var vertices = new List<double[]>();
        for (int ring = 0; ring < Rings; ring++)
        {
            double h = (double)ring / Rings;
            for (int k = 0; k < Around; k++)
            {
                double theta = Math.PI * 2.0 * k / Around;
                vertices.Add(new[]
                {
                    3.0 * (1.0 - h) * Math.Cos(theta),
                    1.5 * (1.0 - h) * Math.Sin(theta),
                    2.0 * h
                });
            }
        }
        int apex = vertices.Count;
        vertices.Add(new[] { 0.0, 0.0, 2.0 });
        var faces = new List<int[]>();
        for (int ring = 0; ring + 1 < Rings; ring++)
        {
            for (int k = 0; k < Around; k++)
            {
                int next = (k + 1) % Around;
                faces.Add(new[]
                {
                    ring * Around + k,
                    ring * Around + next,
                    (ring + 1) * Around + next,
                    (ring + 1) * Around + k
                });
            }
        }
        for (int k = 0; k < Around; k++)
        {
            int next = (k + 1) % Around;
            faces.Add(new[]
            {
                (Rings - 1) * Around + k,
                (Rings - 1) * Around + next,
                apex
            });
        }
        var rim = new List<int>();
        for (int k = 0; k < Around; k++)
            rim.Add(k);
        return (vertices.ToArray(), faces.ToArray(), rim.ToArray());
    }

    /// <summary>
    /// Two disjoint plates, the second translated 100 m in x so nothing is
    /// shared, with a rim on the FIRST only. Check 12.1(g): the second
    /// piece's vertices are unreachable from the rim across the
    /// triangulation and keep positive infinity.
    /// </summary>
    private static (double[][] Vertices, int[][] Faces, int[] Rim)
        SkinDisconnectedNet()
    {
        (double[][] one, int[][] oneFaces, int[] rim) = SkinPlateNet();
        var vertices = new List<double[]>(one);
        var faces = new List<int[]>(oneFaces);
        int offset = one.Length;
        foreach (double[] vertex in one)
            vertices.Add(new[] { vertex[0] + 100.0, vertex[1], vertex[2] });
        foreach (int[] face in oneFaces)
            faces.Add(face.Select(corner => corner + offset).ToArray());
        return (vertices.ToArray(), faces.ToArray(), rim);
    }

    /// <summary>The barrel's rim: both eaves, j = 0 and j = 4, which is the
    /// ordinary two-springing case of rule 1.7.2 and the ridge of rule
    /// 2.5.</summary>
    private static int[] SkinBarrelRim()
    {
        var rim = new List<int>();
        for (int i = 0; i <= 6; i++)
        {
            rim.Add(i);
            rim.Add(4 * 7 + i);
        }
        return rim.ToArray();
    }

    /// <summary>
    /// Check 12.3(a)'s one-way thrust, stated as DATA rather than assumed:
    /// every edge running ALONG the barrel, between (i, j) and (i + 1, j),
    /// carries a compression of 1 kN, and every edge ACROSS it, between
    /// (i, j) and (i, j + 1), carries 0.1 kN.
    /// </summary>
    private static (int A, int B, double Force)[] SkinBarrelForces()
    {
        var forces = new List<(int, int, double)>();
        for (int j = 0; j <= 4; j++)
        {
            for (int i = 0; i < 6; i++)
                forces.Add((j * 7 + i, j * 7 + i + 1, 1.0));
        }
        for (int j = 0; j < 4; j++)
        {
            for (int i = 0; i <= 6; i++)
                forces.Add((j * 7 + i, (j + 1) * 7 + i, 0.1));
        }
        return forces.ToArray();
    }

    /// <summary>The dome's rim: ring 0, the eight base vertices.</summary>
    private static int[] SkinDomeRim() =>
        new[] { 0, 1, 2, 3, 4, 5, 6, 7 };
```

2. [ ] Add checks 12.1(c) and 12.1(g) to `ValidateSkinField`, at its end:

```csharp
        // 12.1(c): the hemisphere's apex.
        (double[][] domeSphereVertices, int[][] domeSphereFaces,
            int[] domeSphereRim) = SkinHemisphereNet();
        object hemisphere = SkinNetWith(
            netType, edgeType, domeSphereVertices, domeSphereFaces,
            domeSphereRim, noForces);
        double[] hemisphereLevels = SkinLevels(hemisphere);
        double apexLevel = hemisphereLevels[^1];
        double quarterCircle = Math.PI * 3.0 / 2.0;
        if (Math.Abs(apexLevel - quarterCircle) > 0.02 * quarterCircle)
        {
            throw new InvalidOperationException(
                "On a hemisphere of R = 3 rimmed at its base ring the field " +
                $"at the apex is pi R / 2 = {quarterCircle} to within 2 per " +
                $"cent (check 12.1(c)); got {apexLevel}.");
        }

        // 12.1(g): a net in two pieces, rimmed on one.
        (double[][] splitVertices, int[][] splitFaces, int[] splitRim) =
            SkinDisconnectedNet();
        object split = SkinNetWith(
            netType, edgeType, splitVertices, splitFaces, splitRim, noForces);
        double[] splitLevels = SkinLevels(split);
        int half = splitLevels.Length / 2;
        for (int at = 0; at < half; at++)
        {
            if (!double.IsFinite(splitLevels[at]))
            {
                throw new InvalidOperationException(
                    "The RIMMED piece of a two-piece net is reachable " +
                    $"throughout; vertex {at} reads {splitLevels[at]}.");
            }
        }
        for (int at = half; at < splitLevels.Length; at++)
        {
            if (!double.IsPositiveInfinity(splitLevels[at]))
            {
                throw new InvalidOperationException(
                    "A vertex UNREACHABLE from the rim across the " +
                    "triangulation takes positive infinity (rule 1.7.3), " +
                    "so it can be excluded from the field range and " +
                    $"counted; vertex {at} reads {splitLevels[at]}.");
            }
        }
```

3. [ ] Add `ValidateSkinFixtures`, which asserts what each new fixture claims and takes the shipped
   honeycomb's BEFORE:

```csharp
    /// <summary>
    /// Rule 12.0's fixtures, asserted against the properties the rules read
    /// off them, and check 12.4(g)'s BEFORE. The honeycomb's quoted 26 to 49
    /// and 38 to 62 per cent were taken against prose reconstructions
    /// nothing here can rebuild, so there is no honest before until these
    /// fixtures exist. These numbers are the before. Task 23 re-measures
    /// them against the reworked lattice and states the improvement between
    /// the two.
    /// </summary>
    private static void ValidateSkinFixtures(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        MethodInfo hexagonal = RequirePublicStatic(patterns, "Hexagonal");

        // The serpentine is PLAN-INJECTIVE by construction, and the whole
        // engine requires it: plan x strictly increasing in i, plan y
        // strictly increasing in j at every i.
        (double[][] serpentine, int[][] _, int[] serpentineRim) =
            SkinSerpentineNet();
        for (int j = 0; j <= 12; j++)
        {
            for (int i = 0; i < 60; i++)
            {
                if (!(serpentine[j * 61 + i + 1][0] >
                      serpentine[j * 61 + i][0]))
                {
                    throw new InvalidOperationException(
                        "The serpentine's plan x must increase strictly in " +
                        $"i; it does not at i {i}, j {j}.");
                }
            }
        }
        for (int i = 0; i <= 60; i++)
        {
            for (int j = 0; j < 12; j++)
            {
                if (!(serpentine[(j + 1) * 61 + i][1] >
                      serpentine[j * 61 + i][1]))
                {
                    throw new InvalidOperationException(
                        "The serpentine's plan y must increase strictly in " +
                        $"j; it does not at i {i}, j {j}.");
                }
            }
        }
        if (serpentineRim.Length != 122)
        {
            throw new InvalidOperationException(
                "The serpentine's rim is both long edges, 61 vertices each; " +
                $"got {serpentineRim.Length}.");
        }

        // The two oculi are really cut: a full grid would carry 960 quads.
        (double[][] oculusVertices, int[][] oculusFaces, int[] oculusRim) =
            SkinTwoOculusNet();
        if (oculusFaces.Length >= 960 || oculusRim.Length != 128)
        {
            throw new InvalidOperationException(
                "The two-oculus fixture omits the faces inside two 1.0 m " +
                "plan discs, so it holds fewer than the full grid's 960 " +
                "quads, and its rim is the RECTANGLE'S 128 boundary " +
                "vertices and not the oculus edges (rule 1.3.3); got " +
                $"{oculusFaces.Length} faces and {oculusRim.Length} rim " +
                "vertices.");
        }

        // Check 12.4(g)'s BEFORE, on the SHIPPED honeycomb.
        object oculusNet = Activator.CreateInstance(
            netType, new object[] { oculusVertices, oculusFaces })!;
        object oculusBuilt = hexagonal.Invoke(
            null, new object[] { oculusNet, 0.6, 0.35 })!;
        (double[][] serpentineVertices, int[][] serpentineFaces, int[] _) =
            SkinSerpentineNet();
        object serpentineNet = Activator.CreateInstance(
            netType,
            new object[] { serpentineVertices, serpentineFaces })!;
        object serpentineBuilt = hexagonal.Invoke(
            null, new object[] { serpentineNet, 0.6, 0.35 })!;
        int Withheld(object built) =>
            Reading<int>(built, "PlanDegenerateDropped") +
            Reading<int>(built, "PlanOverlapDropped");
        int Built(object built) =>
            Withheld(built) + SkinCells(built).Length;
        Console.WriteLine(
            "      Skin honeycomb BEFORE (check 12.4(g), shipped lattice, " +
            $"S 0.6 CH 0.35): two-oculus {Withheld(oculusBuilt)} withheld " +
            $"of {Built(oculusBuilt)} built; serpentine " +
            $"{Withheld(serpentineBuilt)} withheld of " +
            $"{Built(serpentineBuilt)} built.");
        if (Built(oculusBuilt) == 0 || Built(serpentineBuilt) == 0)
        {
            throw new InvalidOperationException(
                "Both fixtures must give the shipped honeycomb something " +
                "to build, or there is no before to measure an after " +
                "against.");
        }
    }
```

4. [ ] Wire `ValidateSkinFixtures` into `Run`, immediately after the `ValidateSkinField` block added
   in Task 12:

```csharp
        try
        {
            ValidateSkinFixtures(plugin);
            Console.WriteLine(
                "PASS  Skin fixtures: the serpentine is plan-injective in " +
                "both directions by construction, the two-oculus fixture " +
                "really omits its two oculi and rims the RECTANGLE rather " +
                "than the free edges, and the shipped honeycomb's withheld " +
                "counts on both are printed as check 12.4(g)'s BEFORE, " +
                "which is the first honest one this repository has had.");
        }
        catch (Exception exception)
        {
            failures.Add($"Skin fixtures: {DescribeException(exception)}");
        }
```

5. [ ] Build and run the harness. Read the two printed BEFORE lines and write both numbers into the
   comment above `ValidateSkinFixtures`, in this form, so Task 23 has them without re-running the
   shipped engine: `// BEFORE, measured 2026-09-01: two-oculus N of M, serpentine N of M.`

6. [ ] Build and run the harness again. Every PASS line, old and new, must appear.

7. [ ] Scan for clash files and commit.

```powershell
git add "tests/native_smoke/Program.cs"
git commit -m "test(skin): the two-oculus, serpentine, elliptical dome and hemisphere fixtures"
```

---

### Task 14: ReadNet builds the rim and the force edges in NET index space

**Files:**
- Modify: plugin/native_v02/Components/SkinPatterns.cs:131-195 (`ReadNet`) and the SkinNet record from
  Task 12 (two new init properties)
- Test: tests/native_smoke/Program.cs, new `ValidateSkinRimIndexSpace` plus its entry in `Run`

**Interfaces:**
- Consumes: `TnaMappingsDto.Supports` of `TnaSupportMappingDto(int FormVertexId, int
  EquilibriumVertexId, ...)` (TnaContracts.cs:226-236, the collection at TnaContracts.cs:272-273);
  `EquilibriumResultDto.Edges` of `EdgeDto(int U, int V)` and `EquilibriumResultDto.MemberForces`
  (ContractDtos.cs:670-674).
- Produces: `SkinNet.Rim` populated from the anchor set, `SkinNet.Edges` populated in net index space,
  and two new init properties on SkinNet, `public int RimDropped { get; init; }` and
  `public int EdgesDropped { get; init; }`, which Task 15 reads onto the result record.

1. [ ] Add the check to tests/native_smoke/Program.cs, beside `ValidateSkinNet`:

```csharp
    /// <summary>
    /// Check 12.1(h). A Result whose FORM and EQUILIBRIUM vertex counts are
    /// EQUAL but whose orderings differ must still seed the right vertices.
    /// This is the trap at VisualiseComponents.cs:196-206 against
    /// SkinPatterns.cs:164-178, and it fails SILENTLY if got wrong: the rim
    /// would be a set of real vertices, just the wrong ones. The same
    /// Result asserts it of the FORCE EDGES of rule 1.3.5, which fails in
    /// exactly the same way and poisons the whole of section 3 rather than
    /// the rim alone.
    ///
    /// The fixture: four form vertices 10, 11, 12, 13 mapped to equilibrium
    /// vertices 3, 2, 1, 0, so the two index spaces are the same SIZE and
    /// the exact REVERSE of one another. Net order is form order, so net 0
    /// is form 10 is equilibrium 3.
    /// </summary>
    private static void ValidateSkinRimIndexSpace(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        MethodInfo readNet = RequirePublicStatic(patterns, "ReadNet");
        Type resultType = RequireContractType(plugin, "ResultDto");
        Type equilibriumType =
            RequireContractType(plugin, "EquilibriumResultDto");
        Type point = RequireContractType(plugin, "Point3Dto");
        Type edgeDtoType = RequireContractType(plugin, "EdgeDto");
        Type graphType = RequireContractType(plugin, "TnaDiagramGraphDto");
        Type graphVertexType =
            RequireContractType(plugin, "TnaGraphVertexDto");
        Type graphFaceType = RequireContractType(plugin, "TnaGraphFaceDto");
        Type mappingsType = RequireContractType(plugin, "TnaMappingsDto");
        Type vertexMappingType =
            RequireContractType(plugin, "TnaSourceVertexMappingDto");
        Type supportMappingType =
            RequireContractType(plugin, "TnaSupportMappingDto");

        object P(double x, double y, double z) =>
            Activator.CreateInstance(point, x, y, z)!;
        Array Of(Type type, params object[] items)
        {
            Array array = Array.CreateInstance(type, items.Length);
            for (int i = 0; i < items.Length; i++)
                array.SetValue(items[i], i);
            return array;
        }

        // Equilibrium order 0, 1, 2, 3 carries positions the reverse of the
        // form's, so a rim read in the wrong space lands on the wrong
        // corners of the square.
        object equilibrium = CreateInstance(equilibriumType);
        SetContractProperty(equilibrium, equilibriumType, "Vertices",
            Of(point, P(0, 1, 1), P(1, 1, 1), P(1, 0, 0), P(0, 0, 0)));
        SetContractProperty(equilibrium, equilibriumType, "Edges",
            Of(edgeDtoType,
                Activator.CreateInstance(edgeDtoType, 3, 2)!,
                Activator.CreateInstance(edgeDtoType, 2, 1)!));
        SetContractProperty(equilibrium, equilibriumType, "MemberForces",
            new[] { 7.0, -3.0 });

        object GraphVertex(int id)
        {
            object vertex = CreateInstance(graphVertexType);
            SetContractProperty(vertex, graphVertexType, "Id", id);
            return vertex;
        }
        object face = CreateInstance(graphFaceType);
        SetContractProperty(face, graphFaceType, "Id", 0);
        SetContractProperty(
            face, graphFaceType, "Vertices", new[] { 10, 11, 12, 13 });
        object formGraph = CreateInstance(graphType);
        SetContractProperty(formGraph, graphType, "Vertices",
            Of(graphVertexType,
                GraphVertex(10), GraphVertex(11),
                GraphVertex(12), GraphVertex(13)));
        SetContractProperty(formGraph, graphType, "Faces",
            Of(graphFaceType, face));

        object Mapping(int formId, int equilibriumId)
        {
            object item = CreateInstance(vertexMappingType);
            SetContractProperty(
                item, vertexMappingType, "FormVertexId", formId);
            SetContractProperty(
                item, vertexMappingType, "EquilibriumVertexId",
                equilibriumId);
            return item;
        }
        object Support(int formId, int equilibriumId)
        {
            object item = CreateInstance(supportMappingType);
            SetContractProperty(
                item, supportMappingType, "FormVertexId", formId);
            SetContractProperty(
                item, supportMappingType, "EquilibriumVertexId",
                equilibriumId);
            return item;
        }
        object mappings = CreateInstance(mappingsType);
        SetContractProperty(mappings, mappingsType,
            "SourceVertexToFormVertex",
            Of(vertexMappingType,
                Mapping(10, 3), Mapping(11, 2),
                Mapping(12, 1), Mapping(13, 0)));
        // Form 10 and form 13 are the supports, so the rim is net 0 and
        // net 3. One further support names a form vertex that does not
        // exist, which rule 1.3.4 drops and counts.
        SetContractProperty(mappings, mappingsType, "Supports",
            Of(supportMappingType,
                Support(10, 3), Support(13, 0), Support(99, 0)));

        object result = CreateResultDto(
            resultType, "tna", equilibrium,
            CreateInstance(graphType), CreateInstance(graphType));
        SetContractProperty(result, resultType, "FormGraph", formGraph);
        SetContractProperty(result, resultType, "Mappings", mappings);

        object net = readNet.Invoke(null, new[] { result })
            ?? throw new InvalidOperationException(
                "A TNA Result with faces must give a net.");
        int[] rim = ((IEnumerable)net.GetType()
                .GetProperty("Rim")!.GetValue(net)!)
            .Cast<int>()
            .OrderBy(index => index)
            .ToArray();
        if (!rim.SequenceEqual(new[] { 0, 3 }))
        {
            throw new InvalidOperationException(
                "The rim is the ANCHOR SET mapped through ReadNet's own " +
                "formToNet (rule 1.3.1), so form 10 and form 13 are NET 0 " +
                "and NET 3. Reading Mappings.Supports' EquilibriumVertexId " +
                "into a net lookup instead would give 3 and 0 here by " +
                "accident and the wrong vertices on any other ordering; " +
                $"got [{string.Join(",", rim)}].");
        }
        if (Reading<int>(net, "RimDropped") != 1)
        {
            throw new InvalidOperationException(
                "A form vertex named as a support but absent from " +
                "formToNet is DROPPED and COUNTED (rule 1.3.4); the " +
                "fixture names one and the count must be 1, got " +
                $"{Reading<int>(net, "RimDropped")}.");
        }

        IList edges = (IList)net.GetType()
            .GetProperty("Edges")!.GetValue(net)!;
        var read = new List<(int A, int B, double Force)>();
        foreach (object? item in edges)
        {
            object edge = item!;
            read.Add((
                Reading<int>(edge, "A"),
                Reading<int>(edge, "B"),
                Reading<double>(edge, "Force")));
        }
        // Equilibrium edge (3, 2) is net (0, 1) and carries 7 kN; edge
        // (2, 1) is net (1, 2) and carries -3 kN. Stored raw, they would be
        // (2, 3) and (1, 2), which is a different pair of net vertices on a
        // net whose two index spaces happen to have the same count.
        if (read.Count != 2 ||
            read[0] != (0, 1, 7.0) ||
            read[1] != (1, 2, -3.0))
        {
            throw new InvalidOperationException(
                "Force edges arrive in EQUILIBRIUM index space and must be " +
                "mapped into NET space, both ends, A below B (rule 1.3.5): " +
                "(3,2) at 7 kN is net (0,1) and (2,1) at -3 kN is net " +
                "(1,2); got [" +
                string.Join(
                    ", ",
                    read.Select(e => $"({e.A},{e.B},{e.Force})")) + "].");
        }
    }
```

2. [ ] Wire it into `Run`, after the `ValidateSkinFixtures` block:

```csharp
        try
        {
            ValidateSkinRimIndexSpace(plugin);
            Console.WriteLine(
                "PASS  Skin rim and force index space: on a Result whose " +
                "form and equilibrium vertex counts are EQUAL and whose " +
                "orderings are the exact reverse, the rim is the anchor " +
                "set mapped through formToNet and the force edges are " +
                "mapped through the inverse of formToEquilibrium composed " +
                "with it, both ends, A below B; an unmappable support and " +
                "an unmappable edge are dropped and counted.");
        }
        catch (Exception exception)
        {
            failures.Add(
                "Skin rim and force index space: " +
                $"{DescribeException(exception)}");
        }
```

3. [ ] Build and run the harness. It must fail on `RimDropped` or on the empty rim.

4. [ ] Add the two counts to the SkinNet record, immediately after the `Levels` property:

```csharp
    /// <summary>How many named supports rule 1.3.4 dropped as unmappable,
    /// and how many force edges rule 1.3.6 dropped. Init properties and not
    /// constructor parameters, so that neither the two-argument nor the
    /// four-argument construction moves and every fixture in the harness
    /// goes on binding.</summary>
    public int RimDropped { get; init; }

    public int EdgesDropped { get; init; }
```

5. [ ] Replace the tail of `ReadNet`, from the face loop at SkinPatterns.cs:180 to the return at
   SkinPatterns.cs:194, with:

```csharp
        var faces = new List<int[]>();
        foreach (TnaGraphFaceDto face in
                 formGraph.Faces.OrderBy(item => item.Id))
        {
            int[] corners = face.Vertices
                .Select(id => formToNet.TryGetValue(id, out int netId)
                    ? netId
                    : throw new InvalidOperationException(
                        $"Form face {face.Id} references unknown " +
                        $"vertex {id}."))
                .ToArray();
            if (corners.Length >= 3)
                faces.Add(corners);
        }

        // THE RIM IS THE ANCHOR SET (rule 1.3.1), mapped through this
        // method's own formToNet. It is NOT ResultTables.SupportNodes
        // (VisualiseComponents.cs:196-206), which returns EQUILIBRIUM
        // vertex ids: on a net whose two index spaces happen to have the
        // same count, feeding those into a net lookup indexes the wrong
        // vertices silently. And it is NOT the mesh boundary (rule 1.3.3),
        // which includes an oculus, a free edge and every hole, none of
        // which is a support and none of which a course should be measured
        // from.
        var rim = new List<int>();
        var seen = new HashSet<int>();
        int rimDropped = 0;
        foreach (TnaSupportMappingDto support in mappings.Supports)
        {
            if (formToNet.TryGetValue(
                    support.FormVertexId, out int netIndex) &&
                netIndex >= 0 &&
                netIndex < vertices.Count)
            {
                if (seen.Add(netIndex))
                    rim.Add(netIndex);
            }
            else
            {
                rimDropped++;
            }
        }

        // THE FORCE EDGES ARRIVE IN EQUILIBRIUM INDEX SPACE (rule 1.3.5).
        // The composition equilibrium index -> form id -> net index is the
        // inverse of formToEquilibrium composed with formToNet, and both
        // ends of every edge go through it. Stored raw, the weights land on
        // the wrong net vertices silently and every direction section 3
        // computes is noise wearing the right units.
        var equilibriumToNet = new Dictionary<int, int>();
        foreach (KeyValuePair<int, int> pair in formToEquilibrium)
        {
            if (formToNet.TryGetValue(pair.Key, out int netIndex))
                equilibriumToNet[pair.Value] = netIndex;
        }
        var edges = new List<SkinNetEdge>();
        int edgesDropped = 0;
        for (int at = 0; at < equilibrium.Edges.Count; at++)
        {
            EdgeDto edge = equilibrium.Edges[at];
            if (at >= equilibrium.MemberForces.Count ||
                !equilibriumToNet.TryGetValue(edge.U, out int a) ||
                !equilibriumToNet.TryGetValue(edge.V, out int b) ||
                a == b)
            {
                edgesDropped++;
                continue;
            }
            edges.Add(new SkinNetEdge(
                Math.Min(a, b),
                Math.Max(a, b),
                equilibrium.MemberForces[at]));
        }

        return new SkinNet(vertices, faces, rim, edges)
        {
            RimDropped = rimDropped,
            EdgesDropped = edgesDropped
        };
```

6. [ ] Build and run the harness. The new PASS line must appear and every existing one must remain.

7. [ ] Scan for clash files and commit.

```powershell
git add "plugin/native_v02/Components/SkinPatterns.cs" "tests/native_smoke/Program.cs"
git commit -m "feat(skin): ReadNet reads the anchor rim and the force edges into net index space"
```

### Task 15: the engine's return record restated in full

**Files:**
- Modify: plugin/native_v02/Components/SkinPatterns.cs:94-108 (the `SkinPatternResult` record),
  SkinPatterns.cs:2096-2108 (`Empty`), SkinPatterns.cs:1834-1846 (the `Courses` return) and
  SkinPatterns.cs:2432-2445 (the `Hexagonal` return)
- Test: tests/native_smoke/Program.cs, new `ValidateSkinResultRecord` plus its entry in `Run`

**Interfaces:**
- Consumes: `SkinNet.Rim`, `SkinNet.Levels`, `SkinNet.RimDropped`, `SkinNet.EdgesDropped` from Tasks
  12 and 14.
- Produces: the twenty-one-member `SkinPatternResult` of rule 9.3.6, which every later task in this
  part reads and fills. Nothing outside SkinPatterns.cs and the harness constructs it.

Rule 9.3.6 restates the record in full because rule 9.3.3 asks for twelve diagnostic entries carrying
real Values and section 12 measures all of them ON THE ENGINE, through reflection without a canvas.
The members this task cannot yet fill are filled by the task that produces them, named here so the
implementer knows which zero is temporary and which is real: `CapGirths`, `CapWedgeCounts` and
`CapsOversized` by Tasks 18 and 22; `FiveSidedCells`, `SevenSidedCells` and `CountChangeRows` by
Tasks 23 and 26; `MergedPieces` by Task 20; `DegenerateCentroidsSkipped` by Task 21.

1. [ ] Add the check to tests/native_smoke/Program.cs, beside `ValidateSkinCourses`:

```csharp
    /// <summary>
    /// Rule 9.3.6's record, member for member. Section 12 measures every
    /// number in this wave off this record and never off a component, so a
    /// member quietly dropped or renamed would take a check with it.
    /// </summary>
    private static void ValidateSkinResultRecord(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        Type edgeType = RequireComponentType(plugin, "SkinNetEdge");
        MethodInfo courses = RequirePublicStatic(patterns, "Courses");
        (double[][] vertices, int[][] faces) = SkinDomeNet();
        object net = SkinNetWith(
            netType, edgeType, vertices, faces, SkinDomeRim(),
            Array.Empty<(int, int, double)>());
        object generated = courses.Invoke(
            null, new object[] { net, 0.6, 0.5 })!;
        string[] required =
        {
            "Cells", "CourseCount", "Diagnostics", "TransitionBands",
            "TransitionIntervals", "PlanDegenerateDropped",
            "PlanOverlapDropped", "FieldKind", "RimVerticesUsed",
            "RimVerticesDropped", "ForceEdgesDropped", "UnreachableVertices",
            "ClippedCells", "CapGirths", "CapWedgeCounts", "CapsOversized",
            "FiveSidedCells", "SevenSidedCells", "CountChangeRows",
            "MergedPieces", "DegenerateCentroidsSkipped"
        };
        foreach (string member in required)
        {
            if (generated.GetType().GetProperty(member) is null)
            {
                throw new InvalidOperationException(
                    "SkinPatternResult carries rule 9.3.6's twenty-one " +
                    $"members; '{member}' is missing, and section 12 " +
                    "measures every number off this record rather than off " +
                    "a component.");
            }
        }
        if (Reading<string>(generated, "FieldKind") != "rim distance")
        {
            throw new InvalidOperationException(
                "A net whose Result named supports cuts a RIM DISTANCE " +
                "field, and the engine says which field it cut; got " +
                $"'{Reading<string>(generated, "FieldKind")}'.");
        }
        if (Reading<int>(generated, "RimVerticesUsed") != 8)
        {
            throw new InvalidOperationException(
                "The dome's rim is its eight base vertices; got " +
                $"{Reading<int>(generated, "RimVerticesUsed")}.");
        }
        object bare = Activator.CreateInstance(
            netType, new object[] { vertices, faces })!;
        object fallback = courses.Invoke(
            null, new object[] { bare, 0.6, 0.5 })!;
        if (Reading<string>(fallback, "FieldKind") != "world Z")
        {
            throw new InvalidOperationException(
                "With no rim the field falls back to world Z (rule 1.7.4) " +
                "and the engine names the fallback, because a silent " +
                "change of what CH means is worse than an empty output; " +
                $"got '{Reading<string>(fallback, "FieldKind")}'.");
        }
    }
```

2. [ ] Wire it into `Run`, after the `ValidateSkinRimIndexSpace` block:

```csharp
        try
        {
            ValidateSkinResultRecord(plugin);
            Console.WriteLine(
                "PASS  Skin result record: rule 9.3.6's twenty-one members " +
                "are all present, the engine names which field it cut, and " +
                "the rim it used is counted, so section 12 can measure " +
                "every number of this wave off the engine without a canvas.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Skin result record: {DescribeException(exception)}");
        }
```

3. [ ] Build and run the harness. It must fail naming `TransitionIntervals`.

4. [ ] Replace the record at SkinPatterns.cs:94-108 with rule 9.3.6's, verbatim:

```csharp
/// <summary>One generated pattern. The cells sorted by course then by
/// rule 7.1's seam-outward order, the band count, the readable diagnostics
/// text (kept on the RECORD and on no port, rule 9.3.6), the refused
/// transition bands and their intervals, the two plan-validity drop counts,
/// and every number rule 9.3.3 names, so that section 12 measures the
/// ENGINE through reflection without a canvas rather than measuring a
/// component's formatted string.
///
/// The three cap members are read together and each is per CAP, not per
/// cell: CapGirths carries the girth of each emitted cap, meaning the
/// CENTRE DISC's girth where rule 2.6 split it and the whole cap's girth
/// where it did not; CapWedgeCounts carries that cap's W, zero where it was
/// not split; and CapsOversized counts the caps rule 2.6.6 emitted whole
/// above the maximum.
///
/// The three piece lengths are DERIVED from the surviving cells and need no
/// member, excluding Cap cells by rule 2.3.2a. skin.surface_failed is
/// deliberately NOT here: the Brep build happens on the solve thread beside
/// ClosedOutlineCurve and never in this file, which is rule 5.2.4.</summary>
internal sealed record SkinPatternResult(
    IReadOnlyList<SkinCell> Cells,
    int CourseCount,
    string Diagnostics,
    int TransitionBands,
    IReadOnlyList<(double Low, double High)> TransitionIntervals,
    int PlanDegenerateDropped,
    int PlanOverlapDropped,
    string FieldKind,
    int RimVerticesUsed,
    int RimVerticesDropped,
    int ForceEdgesDropped,
    int UnreachableVertices,
    int ClippedCells,
    IReadOnlyList<double> CapGirths,
    IReadOnlyList<int> CapWedgeCounts,
    int CapsOversized,
    int FiveSidedCells,
    int SevenSidedCells,
    IReadOnlyList<int> CountChangeRows,
    int MergedPieces,
    int DegenerateCentroidsSkipped);
```

5. [ ] Add the two shared readers to SkinPatterns, immediately above `Empty` at SkinPatterns.cs:2096:

```csharp
    /// <summary>Which field the tracer cut, in the words rule 1.7.4 and the
    /// skin.field diagnostic use.</summary>
    private static string FieldKindOf(SkinNet net) =>
        net.Rim.Count > 0 ? "rim distance" : "world Z";

    /// <summary>How many vertices are unreachable from the rim across the
    /// triangulation (rule 1.7.3). They are excluded from the field range
    /// and their faces produce no cells, so the count is a hole and reaches
    /// a Warning.</summary>
    private static int UnreachableCount(SkinNet net)
    {
        int count = 0;
        foreach (double level in net.Levels)
        {
            if (!double.IsFinite(level))
                count++;
        }
        return count;
    }
```

6. [ ] Replace `Empty` at SkinPatterns.cs:2096-2108 with:

```csharp
    private static SkinPatternResult Empty(string name, SkinNet? net = null) =>
        new(
            Array.Empty<SkinCell>(),
            0,
            PatternDiagnostics(
                name, 0, 0, Array.Empty<double>(),
                name == "courses"
                    ? "half a pitch on odd courses"
                    : "0.75 x S per course row",
                0, 0, 0),
            0,
            Array.Empty<(double, double)>(),
            0,
            0,
            net is null ? "world Z" : FieldKindOf(net),
            net?.Rim.Count ?? 0,
            net?.RimDropped ?? 0,
            net?.EdgesDropped ?? 0,
            net is null ? 0 : UnreachableCount(net),
            0,
            Array.Empty<double>(),
            Array.Empty<int>(),
            0,
            0,
            0,
            Array.Empty<int>(),
            0,
            0);
```

7. [ ] Replace the `Courses` return at SkinPatterns.cs:1834-1846 with:

```csharp
        return new SkinPatternResult(
            cells,
            bands,
            PatternDiagnostics(
                "courses", cells.Count, bands,
                cells.Select(cell => cell.U1 - cell.U0).ToList(),
                "half a pitch on odd courses",
                cells.Count(cell => cell.Clipped),
                degenerateDropped, overlapDropped,
                TransitionLine("courses", transitionBands, transitions)),
            transitionBands,
            transitions,
            degenerateDropped,
            overlapDropped,
            FieldKindOf(net),
            net.Rim.Count,
            net.RimDropped,
            net.EdgesDropped,
            UnreachableCount(net),
            cells.Count(cell => cell.Clipped),
            Array.Empty<double>(),
            Array.Empty<int>(),
            0,
            0,
            0,
            Array.Empty<int>(),
            0,
            0);
```

8. [ ] Replace the `Hexagonal` return at SkinPatterns.cs:2432-2445 with the same shape, its own three
   leading members kept:

```csharp
        return new SkinPatternResult(
            cells,
            bands,
            PatternDiagnostics(
                "hexagonal", cells.Count, bands,
                cells.Select(cell => cell.U1 - cell.U0).ToList(),
                "0.75 x S per course row",
                cells.Count(cell => cell.Clipped),
                degenerateDropped, overlapDropped,
                TransitionLine(
                    "hexagonal", skippedRows.Count, transitions)),
            skippedRows.Count,
            transitions,
            degenerateDropped,
            overlapDropped,
            FieldKindOf(net),
            net.Rim.Count,
            net.RimDropped,
            net.EdgesDropped,
            UnreachableCount(net),
            cells.Count(cell => cell.Clipped),
            Array.Empty<double>(),
            Array.Empty<int>(),
            0,
            0,
            0,
            Array.Empty<int>(),
            0,
            0);
```

9. [ ] Replace the two `return Empty("courses");` and `return Empty("hexagonal");` calls at
   SkinPatterns.cs:1736 and :2209 with `return Empty("courses", net);` and
   `return Empty("hexagonal", net);` so an empty answer still names its field.

10. [ ] Build and run the harness. The new PASS line must appear; nothing else moves, because no
    number this task adds is read by any existing check.

11. [ ] Scan for clash files and commit.

```powershell
git add "plugin/native_v02/Components/SkinPatterns.cs" "tests/native_smoke/Program.cs"
git commit -m "feat(skin): the engine's return record carries every number section 12 measures"
```

---

### Task 16: the tracer cuts the field, and Height becomes Level

**Files:**
- Modify: plugin/native_v02/Components/SkinPatterns.cs:52-77 (`SkinLevelCurve.Height`),
  :484-541 (`Trace`'s two Z reads), :605-634 (`Finish`), :863 (`ReverseCurve`),
  :1734-1759 (the courses ladder), :1894-1904 (`HeightRange`), :2023-2043 (`TransitionLine`),
  :2148 and :2158-2170 (`BuildCharts` and `CurveAt`), :2207-2232 (the honeycomb's ladder)
- Test: tests/native_smoke/Program.cs, new `ValidateSkinBedSpacing` plus its entry in `Run`

**Interfaces:**
- Consumes: `SkinNet.Levels` from Task 12, `FieldKindOf` and `UnreachableCount` from Task 15.
- Produces: `SkinLevelCurve.Level` in place of `Height`;
  `private static (double Min, double Max) LevelRange(SkinNet net)`;
  `TransitionLine(string name, int skipped, IReadOnlyList<(double Low, double High)> transitions,
  string fieldKind)`.

Rule 1.2.5 is the reason the rename is in this task and not deferred: without it the author is shown a
rim distance labelled as a height and warned about a "height" that is not one, which is a worse defect
than the one being fixed.

1. [ ] Add the check to tests/native_smoke/Program.cs:

```csharp
    /// <summary>
    /// Check 12.1(d), the whole point of section 1. On a hemisphere of
    /// R = 3 rimmed at its base ring, at S 0.6 and CH 0.35, the along-surface
    /// distance between consecutive course boundaries is CH to within 5 per
    /// cent at every joint of every INTERIOR course, and the same net with
    /// an EMPTY rim, which is the shipped Z field, is measured beside it.
    ///
    /// Two scopes, and each is stated because they differ. The rim field's
    /// bar is taken over courses 0 to CourseCount - 2: the TOP band is
    /// whatever the field range leaves after the sliver merge, which rule
    /// 2.4.2 bounds at 1.25 CH rather than fixing at CH, so a bar on it
    /// would be measuring the merge and not the field. The shipped ratio is
    /// taken over ALL cells, because that is the number the author sees.
    /// The spec quotes a shipped ratio above 5; that figure was taken on a
    /// shallower shell than this one, and the discipline of check 12.4(g)
    /// applies, so what is pinned here is the ratio this repository can
    /// rebuild, with a floor of 2.5 well under it.
    ///
    /// The measurement itself is the CHORD from a cell's first outline
    /// point, its low-U corner on the lower bed, to its last, the same
    /// corner on the upper bed. On concentric similar circles the
    /// proportional mapping of rule 1.8.1 is exact, so the two points lie on
    /// one meridian, and the chord is under the along-surface distance only
    /// by the sagitta, which at 0.35 m over R = 3 is under a per cent.
    /// </summary>
    private static void ValidateSkinBedSpacing(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        Type edgeType = RequireComponentType(plugin, "SkinNetEdge");
        MethodInfo courses = RequirePublicStatic(patterns, "Courses");
        (double[][] vertices, int[][] faces, int[] rim) = SkinHemisphereNet();

        object rimmed = SkinNetWith(
            netType, edgeType, vertices, faces, rim,
            Array.Empty<(int, int, double)>());
        object built = courses.Invoke(
            null, new object[] { rimmed, 0.6, 0.35 })!;
        var cells = SkinCells(built);
        int courseCount = Reading<int>(built, "CourseCount");
        double Chord((int Course, double[][] Outline, bool Clipped,
            double U0, double U1) cell)
        {
            double[] first = cell.Outline[0];
            double[] last = cell.Outline[^1];
            return Math.Sqrt(
                (first[0] - last[0]) * (first[0] - last[0]) +
                (first[1] - last[1]) * (first[1] - last[1]) +
                (first[2] - last[2]) * (first[2] - last[2]));
        }
        foreach (var cell in cells)
        {
            if (cell.Course >= courseCount - 1)
                continue;
            double chord = Chord(cell);
            if (Math.Abs(chord - 0.35) > 0.05 * 0.35)
            {
                throw new InvalidOperationException(
                    "Under a rim-distance field CH is the true BED-TO-BED " +
                    "spacing measured along the surface, to within 5 per " +
                    "cent (check 12.1(d)); a cell of course " +
                    $"{cell.Course} spans {chord} m against CH 0.35.");
            }
        }

        object bare = Activator.CreateInstance(
            netType, new object[] { vertices, faces })!;
        object shipped = courses.Invoke(
            null, new object[] { bare, 0.6, 0.35 })!;
        var shippedCells = SkinCells(shipped);
        double widest = shippedCells.Max(Chord);
        double narrowest = shippedCells.Min(Chord);
        Console.WriteLine(
            "      Skin bed spacing (check 12.1(d)): world Z on the same " +
            $"hemisphere spans {narrowest:F3} m to {widest:F3} m, a ratio " +
            $"of {widest / narrowest:F2}; the rim field holds every " +
            "interior course to 0.35 m within 5 per cent.");
        if (!(widest / narrowest > 2.5))
        {
            throw new InvalidOperationException(
                "The shipped Z field stretches the beds towards the crown " +
                "by construction, since a rise of CH is a distance along " +
                "the surface of CH / sin(theta); the measured ratio must " +
                $"stay above 2.5 on this fixture, got {widest / narrowest}.");
        }
    }
```

2. [ ] Wire it into `Run`, after the `ValidateSkinResultRecord` block:

```csharp
        try
        {
            ValidateSkinBedSpacing(plugin);
            Console.WriteLine(
                "PASS  Skin bed spacing: on a rimmed hemisphere every " +
                "interior course is CH apart along the SURFACE to within " +
                "5 per cent, against the same net under world Z, whose " +
                "courses stretch towards the crown in the measured ratio " +
                "printed beside this line.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Skin bed spacing: {DescribeException(exception)}");
        }
```

3. [ ] Build and run the harness. It must fail: under the shipped tracer the rimmed net cuts Z, so
   the two measurements are identical and the interior courses are not 0.35 m apart.

4. [ ] Rename the property at SkinPatterns.cs:54, with its comment, and rename its four consumers.
   In SkinPatterns.cs:52-77 replace `public double Height { get; set; }` with:

```csharp
    /// <summary>The FIELD value this curve is the level set of: a rim
    /// distance in metres where the net carries a rim, and the world Z it
    /// used to be where it does not (rules 1.2.1 and 1.2.5). Renamed from
    /// Height with the field, because an author shown a rim distance
    /// labelled as a height has been given a worse defect than the one this
    /// wave fixes.</summary>
    public double Level { get; set; }
```

   Then: SkinPatterns.cs:628 `Height = height,` becomes `Level = level,`; `Finish`'s parameter at
   :612-615 is renamed from `double height` to `double level`; SkinPatterns.cs:863 becomes
   `SkinLevelCurve rebuilt = Finish(points, curve.Level, curve.Closed);`; SkinPatterns.cs:2148 becomes
   `chart.Heights.Add(curve.Level);`.

5. [ ] Make `Trace` cut the field. In SkinPatterns.cs:484-541, replace the two readers and add the
   reachability guard:

```csharp
        int CrossingOf(int a, int b)
        {
            (int, int) key = EdgeKey(a, b);
            if (crossingByEdge.TryGetValue(key, out int index))
                return index;
            double da = net.Levels[key.Item1];
            double db = net.Levels[key.Item2];
            double t = (level - da) / (db - da);
            crossingByEdge[key] = crossingPoints.Count;
            // The crossing POSITION stays a three-dimensional Lerp between
            // the two vertices (rule 1.2.4); only the parameter t changes
            // source.
            crossingPoints.Add(
                Lerp(net.Vertices[key.Item1], net.Vertices[key.Item2], t));
            return crossingPoints.Count - 1;
        }

        bool Crosses(int a, int b)
        {
            double da = net.Levels[a];
            double db = net.Levels[b];
            return (da < level && db >= level) ||
                   (db < level && da >= level);
        }
```

   and, inside `foreach (int[] face in net.Faces)`, before the corner walk:

```csharp
            // A face touching an UNREACHABLE vertex produces no cells (rule
            // 1.7.3). Its level is positive infinity, so every edge to it
            // would read as a crossing and the trace would draw a curve
            // along the edge of a region the field never reached.
            bool reachable = true;
            foreach (int corner in face)
            {
                if (!double.IsFinite(net.Levels[corner]))
                {
                    reachable = false;
                    break;
                }
            }
            if (!reachable)
                continue;
```

   `Trace`'s own parameter is renamed from `double height` to `double level` throughout the method,
   and `TraceAll`'s from `IReadOnlyList<double> heights` to `IReadOnlyList<double> levels`.

6. [ ] Replace `HeightRange` at SkinPatterns.cs:1894-1904 with:

```csharp
    /// <summary>The FIELD's range over the net, unreachable vertices
    /// excluded (rules 1.2.4 and 1.7.3). Both ends are in metres whether the
    /// field is a rim distance or the Z fallback, so no tolerance
    /// anywhere moves with the change.</summary>
    private static (double Min, double Max) LevelRange(SkinNet net)
    {
        double min = double.PositiveInfinity;
        double max = double.NegativeInfinity;
        foreach (double level in net.Levels)
        {
            if (!double.IsFinite(level))
                continue;
            min = Math.Min(min, level);
            max = Math.Max(max, level);
        }
        return (min, max);
    }
```

7. [ ] Point both engines at it. At SkinPatterns.cs:1734 and :2207 replace
   `(double zMin, double zMax) = HeightRange(net);` with
   `(double dMin, double dMax) = LevelRange(net);` and rename every `zMin` and `zMax` in the two
   method bodies to `dMin` and `dMax`, including the guards at :1735 and :2208, which then read
   `if (net.Faces.Count == 0 || !(dMax - dMin > 1.0e-9))`. Rule 1.5.4: a surface flat in Z now has
   courses, because it has a rim distance, and a surface with no rim and no Z range still has none.
   In the honeycomb also rename `zBottom`, `zTop`, `zRaw`, `zcClamped` and `ClampedRowHeight` to
   `dBottom`, `dTop`, `dRaw`, `dcClamped` and `ClampedRowLevel`, which is a mechanical rename of names
   only.

8. [ ] Make the diagnostics say which field. Replace `TransitionLine` at SkinPatterns.cs:2023-2043
   with:

```csharp
    private static string? TransitionLine(
        string name,
        int skipped,
        IReadOnlyList<(double Low, double High)> transitions,
        string fieldKind)
    {
        if (skipped == 0 || transitions.Count == 0)
            return null;
        static string F(double value) =>
            value.ToString("F3", CultureInfo.InvariantCulture);
        // Rule 8.2.8: a rim distance is a DISTANCE and is named as one, in
        // metres; the "z=" wording survives only under the fallback of rule
        // 1.7.4, where it is still true.
        string where = string.Join(
            " and ",
            transitions.Select(item =>
                fieldKind == "world Z"
                    ? $"between z={F(item.Low)} and z={F(item.High)}"
                    : $"between d={F(item.Low)} m and d={F(item.High)} m"));
        return
            $"Transition bands skipped: {skipped} (level curves do not " +
            $"correspond {where}; {name} cannot bond across it)";
    }
```

   and pass `FieldKindOf(net)` at both call sites, in the `Courses` and `Hexagonal` returns Task 15
   rewrote.

9. [ ] Build and run the harness. The new PASS line must appear. The two shipped string pins at
   Program.cs:10136-10145 and :10345-10349 stay green as they are: both fixtures are built through the
   two-argument constructor, so their field is world Z and their wording is unchanged. Rule 9.3.6 says
   why they survive at all, and Task 30 moves them off the component's D output onto the engine's own
   record.

10. [ ] Scan for clash files and commit.

```powershell
git add "plugin/native_v02/Components/SkinPatterns.cs" "tests/native_smoke/Program.cs"
git commit -m "feat(skin): the tracer cuts the rim-distance field and Height becomes Level"
```

---

### Task 17: band splitting at topology transitions

**Files:**
- Modify: plugin/native_v02/Components/SkinPatterns.cs:1728-1846 (the whole of `Courses`) and
  :2279-2287 (the honeycomb's global transition refusal)
- Test: tests/native_smoke/Program.cs, `ValidateSkinTransitions` at Program.cs:10064 gains checks
  12.8(a) to 12.8(e); new `ValidateSkinBandSplitCost` for check 12.9(c)

**Interfaces:**
- Consumes: `TraceAll(SkinNet, IReadOnlyList<double>)`, `Corresponds`, `MatchBelow`, `BandCell`,
  `CourseSpans`, `AddTransition`, all already in the file.
- Produces: `private sealed record SkinBandInterval(int Course, double Low, double Mid, double High,
  int Depth)`; `private static SkinBandResolution ResolveBands(SkinNet net, List<double> levels,
  IReadOnlyList<SkinBandInterval> bands)`; `private static double AddLevel(List<double> levels, double
  level)`; `private static bool ChainCorresponds(SkinLevelCurve upper, SkinLevelCurve lower)`.

Section 8 is a PRECONDITION for section 1 and not an improvement beside it (rule 1.5.5 and 8.1): level
sets of a rim distance MEET at a cut locus, and refusing a whole band there would put a hole of one
full course wherever the fronts meet, which on an ordinary barrel is the whole ridge.

1. [ ] Add checks 12.8(a) to 12.8(d) to `ValidateSkinTransitions`, at the end of the method:

```csharp
        // Check 12.8(a) and 12.8(c): the two nets a count test cannot see.
        // Today each refuses exactly one band WHOLE. After splitting, each
        // emits cells at every course including the one previously refused,
        // TransitionBands counts only the RESIDUAL, and the refused
        // interval named in the diagnostics is at most CH / 64 wide.
        foreach ((double[][] vertices, int[][] faces, string label) fixture in
                 new[]
                 {
                     (SkinTwoHumpBarrelNet().Vertices,
                      SkinTwoHumpBarrelNet().Faces, "two-hump barrel"),
                     (SkinSplitAndDeathNet().Vertices,
                      SkinSplitAndDeathNet().Faces, "split-and-death")
                 })
        {
            object net = Activator.CreateInstance(
                netType,
                new object[] { fixture.vertices, fixture.faces })!;
            object built = courses.Invoke(
                null, new object[] { net, 0.6, 0.5 })!;
            var cells = SkinCells(built);
            int courseCount = Reading<int>(built, "CourseCount");
            for (int course = 0; course < courseCount; course++)
            {
                if (!cells.Any(cell => cell.Course == course))
                {
                    throw new InvalidOperationException(
                        $"After splitting, the {fixture.label} emits cells " +
                        $"at EVERY course; course {course} is empty, which " +
                        "is the whole-band refusal section 8 replaces.");
                }
            }
            IList intervals = (IList)built.GetType()
                .GetProperty("TransitionIntervals")!.GetValue(built)!;
            foreach (object? item in intervals)
            {
                (double Low, double High) span =
                    ((double, double))item!;
                if (span.High - span.Low > 0.5 / 64.0 + 1.0e-9)
                {
                    throw new InvalidOperationException(
                        "A residual interval still failing at depth six is " +
                        "refused and named, and it is at most CH / 64 " +
                        $"wide, which at CH 0.5 is 7.8 mm; the " +
                        $"{fixture.label} names one {span.High - span.Low} " +
                        "m wide.");
                }
            }
            RequireDisjointSimplePlans(
                cells.Select(cell => cell.Outline).ToList(),
                $"{fixture.label} after splitting");
        }

        // Check 12.8(d): a BARREL under the rim field, whose ridge is a cut
        // locus. The shipped rule would leave one course's worth of hole
        // along the whole ridge, so both are measured.
        (double[][] barrelVertices, int[][] barrelFaces) = SkinBarrelNet();
        object ridgeNet = SkinNetWith(
            netType,
            RequireComponentType(plugin, "SkinNetEdge"),
            barrelVertices,
            barrelFaces,
            SkinBarrelRim(),
            Array.Empty<(int, int, double)>());
        object ridge = courses.Invoke(
            null, new object[] { ridgeNet, 0.6, 0.5 })!;
        var ridgeCells = SkinCells(ridge);
        int ridgeCourses = Reading<int>(ridge, "CourseCount");
        for (int course = 0; course < ridgeCourses; course++)
        {
            if (!ridgeCells.Any(cell => cell.Course == course))
            {
                throw new InvalidOperationException(
                    "A barrel seeded from BOTH springings meets at a cut " +
                    "locus along its ridge, which is a topology event at " +
                    "every point of it; section 8 splits the band there " +
                    $"rather than refusing it, and course {course} must " +
                    "carry cells.");
            }
        }
```

2. [ ] Add check 12.8(e), the honeycomb's LOCAL refusal, to the same method:

```csharp
        // Check 12.8(e). The two-hump barrel carries its transition on one
        // side at a time; with the refusal restricted to the candidate's own
        // CHART, the other side's cells are unaffected. Under the shipped
        // global SpansTransition every row spanning the interval was refused
        // anywhere on the net, so a transition on one side holed the other.
        object humpNet = Activator.CreateInstance(
            netType,
            new object[]
            {
                SkinTwoHumpBarrelNet().Vertices,
                SkinTwoHumpBarrelNet().Faces
            })!;
        object hump = hexagonal.Invoke(
            null, new object[] { humpNet, 0.6, 0.5 })!;
        var humpCells = SkinCells(hump);
        int refusedRows = Reading<int>(hump, "TransitionBands");
        Console.WriteLine(
            "      Skin honeycomb transition (check 12.8(e)): " +
            $"{refusedRows} candidate rows refused on their own chart, " +
            $"{humpCells.Length} cells kept.");
        if (humpCells.Length == 0)
        {
            throw new InvalidOperationException(
                "Restricting the refusal to the cell's own chart makes the " +
                "hole LOCAL (rule 8.2.7); the honeycomb must still cover " +
                "the sides that carry no transition.");
        }
```

3. [ ] Build and run the harness. It must fail on the two-hump barrel's empty course.

4. [ ] Add the splitting machinery to SkinPatterns, immediately above `Courses` at
   SkinPatterns.cs:1715:

```csharp
    /// <summary>One band of a pattern: the course it belongs to, the three
    /// field values it is built on, and how many times it has been bisected
    /// (rule 8.2.2). Its MID is what every cell of it is set out on, so a
    /// sub-band needs its OWN mid at a quarter point and one level of
    /// bisection costs TWO new mid traces, not one.</summary>
    private sealed record SkinBandInterval(
        int Course,
        double Low,
        double Mid,
        double High,
        int Depth);

    /// <summary>What ResolveBands returns: the ascending level list it
    /// finished with, that list traced, the bands that correspond and may be
    /// tiled, the residual intervals refused at depth six or at the cap, how
    /// many extra levels the splitting introduced, how many TraceAll passes
    /// it cost, and whether the cap of rule 8.2.3b was reached.</summary>
    private sealed record SkinBandResolution(
        IReadOnlyList<double> Levels,
        IReadOnlyList<IReadOnlyList<SkinLevelCurve>> Traced,
        IReadOnlyList<SkinBandInterval> Tileable,
        IReadOnlyList<(double Low, double High)> Refused,
        int ExtraLevels,
        int Passes,
        bool CapReached);

    /// <summary>Add a level to the ascending list, or return the existing
    /// one it coincides with, so the list never carries the same level
    /// twice and a sub-band's mid always names a level that was actually
    /// traced.</summary>
    private static double AddLevel(List<double> levels, double level)
    {
        foreach (double at in levels)
        {
            if (Math.Abs(at - level) <= 1.0e-12)
                return at;
        }
        levels.Add(level);
        return level;
    }

    /// <summary>
    /// Rules 8.2.1 to 8.2.9. A band whose three levels do not CORRESPOND one
    /// for one is BISECTED rather than refused whole: the lower sub-band is
    /// [a, m] with its own mid (a + m) / 2, the upper is [m, b] with its own
    /// mid (m + b) / 2, each is tested by the same correspondence test, each
    /// half that passes is tiled and each half that fails recurses.
    ///
    /// EVERY LEVEL THIS WAVE INTRODUCES ENTERS ONE ASCENDING LIST AND
    /// TraceAll RUNS ONCE OVER THE WHOLE LIST (rule 8.2.9). Its contract is
    /// that levels arrive ASCENDING, because nesting depth, direction
    /// normalisation and seam assignment are one bottom-up pass and a closed
    /// loop's seam is propagated from the loop below it. A sub-band mid
    /// traced on its own would have no level beneath it, its seam would fall
    /// to the +X rule instead of the propagated one, and its cells' u origin
    /// would not agree with the rest of its own course. So splitting is a
    /// STAGED solve: trace, test, insert the new mids of every failing band,
    /// trace the whole list again, and so on.
    ///
    /// DEPTH SIX (rule 8.2.3), so the residual interval is CH / 64, about
    /// 5.5 mm at the shipped CH of 0.35 m, which is below the coarsest
    /// tolerance anything downstream uses and well above the 1e-9 arithmetic
    /// floor. A full recursion to depth six costs up to 63 new mid traces on
    /// ONE band, so no solve may introduce more than 128 extra levels across
    /// all bands together (rule 8.2.3b): a pathological net must not be able
    /// to lock Grasshopper's canvas thread.
    /// </summary>
    private static SkinBandResolution ResolveBands(
        SkinNet net,
        List<double> levels,
        IReadOnlyList<SkinBandInterval> bands)
    {
        const int MaxDepth = 6;
        const int MaxExtraLevels = 128;
        var pending = new List<SkinBandInterval>(bands);
        var tileable = new List<SkinBandInterval>();
        var refused = new List<(double Low, double High)>();
        IReadOnlyList<IReadOnlyList<SkinLevelCurve>> traced =
            Array.Empty<IReadOnlyList<SkinLevelCurve>>();
        int extra = 0;
        int passes = 0;
        bool capReached = false;
        while (true)
        {
            levels.Sort();
            traced = TraceAll(net, levels);
            passes++;
            var index = new Dictionary<double, int>();
            for (int at = 0; at < levels.Count; at++)
                index[levels[at]] = at;
            var next = new List<SkinBandInterval>();
            foreach (SkinBandInterval band in pending)
            {
                IReadOnlyList<SkinLevelCurve> mids = traced[index[band.Mid]];
                IReadOnlyList<SkinLevelCurve> lowers =
                    traced[index[band.Low]];
                IReadOnlyList<SkinLevelCurve> uppers =
                    traced[index[band.High]];
                if (Corresponds(mids, lowers) && Corresponds(mids, uppers))
                {
                    tileable.Add(band);
                    continue;
                }
                if (band.Depth >= MaxDepth || extra + 2 > MaxExtraLevels)
                {
                    capReached |= extra + 2 > MaxExtraLevels;
                    refused.Add((band.Low, band.High));
                    continue;
                }
                int before = levels.Count;
                double lowerMid = AddLevel(
                    levels, (band.Low + band.Mid) / 2.0);
                double upperMid = AddLevel(
                    levels, (band.Mid + band.High) / 2.0);
                extra += levels.Count - before;
                next.Add(new SkinBandInterval(
                    band.Course, band.Low, lowerMid, band.Mid,
                    band.Depth + 1));
                next.Add(new SkinBandInterval(
                    band.Course, band.Mid, upperMid, band.High,
                    band.Depth + 1));
            }
            if (next.Count == 0)
                break;
            pending = next;
        }
        return new SkinBandResolution(
            levels, traced, tileable, refused, extra, passes, capReached);
    }
```

5. [ ] Replace the body of `Courses`, SkinPatterns.cs:1733-1833, from `RequireSizes(size,
   courseHeight);` down to the closing brace of the `KeepValidPlans` call, with:

```csharp
        RequireSizes(size, courseHeight);
        (double dMin, double dMax) = LevelRange(net);
        if (net.Faces.Count == 0 || !(dMax - dMin > 1.0e-9))
            return Empty("courses", net);

        int bands = BandCount(dMin, dMax, courseHeight);
        double epsilon = Math.Max((dMax - dMin) * 1.0e-6, 1.0e-9);

        // The band ladder, in FIELD values. Under a rim field dMin is 0 and
        // this is rule 1.5.3's BandCount(0, dMax, CH) over a geodesic extent
        // rather than a vertical one; under the Z fallback it is the ladder
        // that shipped. The extreme cuts are pulled inside the surface by
        // the epsilon of rule 1.5.2, which is a fraction of the FIELD range
        // and in metres either way, so no tolerance moves with the change.
        var levels = new List<double>();
        var intervals = new List<SkinBandInterval>();
        for (int r = 0; r < bands; r++)
        {
            double low = AddLevel(
                levels,
                r == 0 ? dMin + epsilon : dMin + r * courseHeight);
            double bandTop = r == bands - 1
                ? dMax
                : dMin + (r + 1) * courseHeight;
            double high = AddLevel(
                levels,
                r == bands - 1 ? dMax - epsilon : bandTop);
            double mid = AddLevel(
                levels, (dMin + r * courseHeight + bandTop) / 2.0);
            intervals.Add(new SkinBandInterval(r, low, mid, high, 0));
        }
        SkinBandResolution resolved = ResolveBands(net, levels, intervals);
        var levelIndex = new Dictionary<double, int>();
        for (int at = 0; at < resolved.Levels.Count; at++)
            levelIndex[resolved.Levels[at]] = at;

        var keyed =
            new List<(int Course, int Order, double U0, SkinCell Cell)>();
        var transitions = new List<(double Low, double High)>();
        foreach ((double low, double high) in resolved.Refused)
            AddTransition(transitions, low, high);
        int transitionBands = resolved.Refused.Count;
        foreach (SkinBandInterval band in resolved.Tileable)
        {
            IReadOnlyList<SkinLevelCurve> mids =
                resolved.Traced[levelIndex[band.Mid]];
            IReadOnlyList<SkinLevelCurve> lowers =
                resolved.Traced[levelIndex[band.Low]];
            IReadOnlyList<SkinLevelCurve> uppers =
                resolved.Traced[levelIndex[band.High]];
            for (int component = 0; component < mids.Count; component++)
            {
                SkinLevelCurve mid = mids[component];
                int lowerAt = MatchBelow(mid, lowers);
                int upperAt = MatchBelow(mid, uppers);
                if (lowerAt < 0 || upperAt < 0 || !(mid.Length > 1.0e-9))
                    continue;
                SkinLevelCurve lowerCurve = lowers[lowerAt];
                SkinLevelCurve upperCurve = uppers[upperAt];
                // A sub-band takes its OWN mid curve and its own pitch (rule
                // 8.2.5), so a thin sub-band beside a cut locus gives short
                // pieces, which section 6 then merges: a course that runs
                // into a ridge closes with a short stone. Its COURSE is the
                // band it came from and never a new one (rule 8.2.4),
                // because the studio builds one stage per distinct course.
                int pieces = Math.Max(
                    1, (int)Math.Round(mid.Length / size));
                double pitch = mid.Length / pieces;
                double phase = band.Course % 2 == 0 ? 0.0 : 0.5 * pitch;
                foreach ((double u0, double u1) in
                         CourseSpans(mid, pieces, pitch, phase))
                {
                    bool endPiece = u1 - u0 < pitch - 1.0e-9;
                    SkinCell cell = BandCell(
                        band.Course, lowerCurve, mid, upperCurve,
                        u0, u1, endPiece);
                    if (cell.Outline.Count < 3)
                        continue;
                    keyed.Add((band.Course, component, u0, cell));
                }
            }
        }
        List<SkinCell> cells = KeepValidPlans(
            keyed
                .OrderBy(item => item.Course)
                .ThenBy(item => item.Order)
                .ThenBy(item => item.U0)
                .Select(item => item.Cell)
                .ToList(),
            out int degenerateDropped,
            out int overlapDropped);
```

6. [ ] Make the honeycomb's refusal local. Add beside `Corresponds`:

```csharp
    /// <summary>Rule 8.2.7's chain test, taken WITHIN ONE CHART. A candidate
    /// hexagon is refused when the three rows it maps through do not
    /// correspond as a chain within its own chart, which is a question about
    /// the two curves it actually bonds across and not about the whole net.
    /// The shipped test was global (SpansTransition against every recorded
    /// interval), so a transition on one side of a two-sided vault holed the
    /// other side too.</summary>
    private static bool ChainCorresponds(
        SkinLevelCurve upper,
        SkinLevelCurve lower) =>
        Corresponds(new[] { upper }, new[] { lower });
```

   and replace SkinPatterns.cs:2279-2287, the `SpansTransition` branch, with:

```csharp
                    SkinLevelCurve rowBelow =
                        CurveAt(chart, ClampedRowLevel(centreRow - 1));
                    SkinLevelCurve rowHere =
                        CurveAt(chart, ClampedRowLevel(centreRow));
                    SkinLevelCurve rowAbove =
                        CurveAt(chart, ClampedRowLevel(centreRow + 1));
                    if (!ChainCorresponds(rowHere, rowBelow) ||
                        !ChainCorresponds(rowAbove, rowHere))
                    {
                        skippedRows.Add(centreRow);
                        continue;
                    }
```

   `SpansTransition` at SkinPatterns.cs:2004-2015 then has no caller and is deleted with its comment.
   The global scan that fills `transitions` at :2244-2252 STAYS: it is what the diagnostics name the
   intervals from.

7. [ ] Add the cost check for 12.9(c):

```csharp
    /// <summary>
    /// Check 12.9(c). Rule 8.2.3a states the cost as up to 2^depth - 1 new
    /// levels per refused band, delivered in at most depth + 1 passes of
    /// TraceAll over the whole ascending list, and rule 8.2.3b caps the
    /// total at 128 extra levels for the whole solve. In practice a band's
    /// failure is local and one half passes at each level, so the ordinary
    /// cost is of order twelve traces; the bound is what must be budgeted,
    /// and what is under test here is that the engine RETURNS with its
    /// diagnostics rather than how long it takes.
    /// </summary>
    private static void ValidateSkinBandSplitCost(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        MethodInfo courses = RequirePublicStatic(patterns, "Courses");
        foreach ((double[][] vertices, int[][] faces, string label) fixture in
                 new[]
                 {
                     (SkinTwoHumpBarrelNet().Vertices,
                      SkinTwoHumpBarrelNet().Faces, "two-hump barrel"),
                     (SkinSplitAndDeathNet().Vertices,
                      SkinSplitAndDeathNet().Faces, "split-and-death")
                 })
        {
            object net = Activator.CreateInstance(
                netType,
                new object[] { fixture.vertices, fixture.faces })!;
            var clock = System.Diagnostics.Stopwatch.StartNew();
            object built = courses.Invoke(
                null, new object[] { net, 0.6, 0.5 })!;
            clock.Stop();
            int extra = Reading<int>(built, "ExtraLevels");
            int passes = Reading<int>(built, "TracePasses");
            Console.WriteLine(
                $"      Skin band splitting on the {fixture.label}: " +
                $"{extra} extra levels in {passes} TraceAll passes, " +
                $"{clock.ElapsedMilliseconds} ms.");
            if (extra > 128 || passes > 8)
            {
                throw new InvalidOperationException(
                    "No solve may introduce more than 128 extra levels " +
                    "across all bands (rule 8.2.3b), delivered in at most " +
                    "depth + 1 = 7 passes of TraceAll plus the first; the " +
                    $"{fixture.label} took {extra} levels in {passes} " +
                    "passes.");
            }
        }
    }
```

   This check reads two members the record does not yet carry, so add them to `SkinPatternResult`
   after `DegenerateCentroidsSkipped`, `int ExtraLevels` and `int TracePasses`. Rule 9.3.6 does not
   name them because it names what the DIAGNOSTICS carry; these two are the cost check's own, and
   check 12.9(c) cannot be taken without them.

   `SkinPatternResult` is a POSITIONAL record, so widening it means editing EVERY construction site
   in the same commit or the plugin will not compile. There are THREE and all three are named here,
   because Task 15 step 6 wrote `Empty` with exactly twenty-one positional arguments and an earlier
   draft of this step named only two of the three:

   - `Empty` at SkinPatterns.cs:2096, as Task 15 step 6 rewrote it: append `0, 1` at the end. Zero
     extra levels and ONE pass is what an empty answer took, and it is the same pair `Hexagonal`
     passes for the same reason.
   - the `Courses` return, as Task 15 step 7 rewrote it: append `resolved.ExtraLevels,
     resolved.Passes`.
   - the `Hexagonal` return, as Task 15 step 8 rewrote it: append `0, 1`. The honeycomb does not
     split, so it inserts no level and traces once.

8. [ ] Wire `ValidateSkinBandSplitCost` into `Run`, after the `ValidateSkinPlanFilterCost` block at
   Program.cs:824-842:

```csharp
        try
        {
            ValidateSkinBandSplitCost(plugin);
            Console.WriteLine(
                "PASS  Skin band splitting cost: the two nets a count test " +
                "cannot see split inside rule 8.2.3b's cap of 128 extra " +
                "levels and inside depth six's own pass count, and the " +
                "measured levels and passes are printed beside this line.");
        }
        catch (Exception exception)
        {
            failures.Add(
                "Skin band splitting cost: " +
                $"{DescribeException(exception)}");
        }
```

9. [ ] Build and run the harness. `ValidateSkinTransitions` will now fail on its own shipped pins,
   which is expected and is what rule 8.2.9 warns of: the refused counts move because splitting
   replaces the whole-band refusal, and inserting a level re-propagates the seams above it. Re-measure
   each moved number, re-pin it, and write the new number into the check's own message with the
   reason, which is the discipline check 12.4(g) states. The one pin that must NOT move is
   `RequireDisjointSimplePlans`: check 12.8(b) is the whole reason the refusal existed.

10. [ ] Build and run the harness again. Everything green.

11. [ ] Scan for clash files and commit.

```powershell
git add "plugin/native_v02/Components/SkinPatterns.cs" "tests/native_smoke/Program.cs"
git commit -m "feat(skin): bands split at topology transitions instead of being refused whole"
```

### Task 18: the crown cap, whole

**Files:**
- Modify: plugin/native_v02/Components/SkinPatterns.cs:87-92 (`SkinCell` gains `Cap`), the band tiling
  loop in `Courses` that Task 17 rewrote, and `PatternDiagnostics` at :2055-2094
- Test: tests/native_smoke/Program.cs, new `ValidateSkinCrownCap` plus its entry in `Run`; and
  `ValidateSkinBedSpacing` from Task 16 gains a `cell.Cap` skip

**Interfaces:**
- Consumes: `SkinLevelCurve`, `Dedupe`, `PlanContains`, `SkinBandResolution` from Task 17.
- Produces: `SkinCell(int Course, IReadOnlyList<double[]> Outline, bool Clipped, double U0, double U1,
  bool Cap = false)`; `private static bool CapQualifies(SkinNet net, double level, int componentAt,
  IReadOnlyList<SkinLevelCurve> level Components, bool[] faceHasBoundaryEdge, out string refusedBy)`;
  the record's `CapGirths` filled.

The cap is emitted by the BAND construction, which the courses engine owns and which the
force-aligned pattern inherits whole by rule 3.3.6. It is NOT added to the honeycomb, and the reason
is a reading rather than a quotation: every rule in section 2 is stated in the band ladder's own
terms, L_top = (n - 1) CH, band n - 1, and `BandCount`'s sliver merge, and the honeycomb has no such
ladder. What closes the honeycomb's crown instead is rule 4.2.1, which stops its rows at the surface,
and check 12.4(c), which pins the crown lollipop out of existence. Rule 4.4's standing rule, that a
cell crossing the crown is CLIPPED and KEPT, covers what is left.

FIRST, THE HARNESS READER HAS TO CARRY THE FLAG, or nothing below compiles. `SkinCells` at
tests/native_smoke/Program.cs:9625 returns
`(int Course, double[][] Outline, bool Clipped, double U0, double U1)[]`, which has no `Cap` member,
and `cell.Cap` is read TWENTY times across Tasks 18, 19, 20, 22, 23 and 26. That is a compile error
and not a runtime failure, and Task 19 makes it plain by writing the tuple type out longhand and then
reading `cell.Cap` off it.

0. [ ] Widen `SkinCells`. Replace its return type and its `read` list with the six-member tuple, and
   read the new property beside the others:

```csharp
    private static (int Course, double[][] Outline, bool Clipped,
        double U0, double U1, bool Cap)[] SkinCells(object generated)
    {
        IList cells = (IList)generated.GetType()
            .GetProperty("Cells")!.GetValue(generated)!;
        var read = new List<(int, double[][], bool, double, double, bool)>();
        foreach (object? item in cells)
        {
            object cell = item!;
            Type type = cell.GetType();
            IList outline =
                (IList)type.GetProperty("Outline")!.GetValue(cell)!;
            read.Add((
                (int)type.GetProperty("Course")!.GetValue(cell)!,
                outline.Cast<double[]>().ToArray(),
                (bool)type.GetProperty("Clipped")!.GetValue(cell)!,
                (double)type.GetProperty("U0")!.GetValue(cell)!,
                (double)type.GetProperty("U1")!.GetValue(cell)!,
                (bool)type.GetProperty("Cap")!.GetValue(cell)!));
        }
        return read.ToArray();
    }
```

   Every place that writes the tuple type out longhand rather than using `var` moves with it, and
   there are two: the `IGrouping<int, (...)>` in Task 19's build-order check and the one in Task 23's
   scar check. Both gain `, bool Cap` as their sixth member. Step 4 below adds the property that this
   reader is looking for, so between step 0 and step 4 the harness does not build; that is the same
   red the rest of this task is written against, and step 3 says so.

   `SkinCell` gains two further members later, `SetoutCorners` in Task 23 for check 12.4(d) and
   `Sections` in Task 26 for check 12.3(b), and NEITHER widens `SkinCells` again: `SetoutCorners` is
   read by its own class-scope reader, `SkinSetoutCorners`, and the sections are a list of lists that
   no check measures through this reader at all, since Task 26 and Task 29 both read them off the
   reflected cell directly, which is what Task 29's own `SectionCount` local already does.

1. [ ] Add the check to tests/native_smoke/Program.cs:

```csharp
    /// <summary>
    /// The crown cap (spec section 2), checks 12.2(a) to 12.2(e). There is
    /// no cap today: the top course closes on the level curve at the crown
    /// minus epsilon, which on a dome is a micron-scale loop around the
    /// apex, and the surface above it is covered by nothing.
    /// </summary>
    private static void ValidateSkinCrownCap(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        Type edgeType = RequireComponentType(plugin, "SkinNetEdge");
        MethodInfo courses = RequirePublicStatic(patterns, "Courses");
        var noForces = Array.Empty<(int, int, double)>();

        static double PlanArea(double[][] ring)
        {
            // The harness's own shoelace, and NOT a second copy of a
            // guarantee: rule 11.5 requires the plan-VALIDITY predicates to
            // be the engine's, because the filter and the check must not be
            // able to disagree about what a bad cell is. An area is a
            // measurement, and this one is centred for the same reason rule
            // 11.2 centres the engine's.
            double cx = ring.Average(point => point[0]);
            double cy = ring.Average(point => point[1]);
            double twice = 0.0;
            for (int at = 0; at < ring.Length; at++)
            {
                double[] a = ring[at];
                double[] b = ring[(at + 1) % ring.Length];
                twice += (a[0] - cx) * (b[1] - cy) -
                         (b[0] - cx) * (a[1] - cy);
            }
            return Math.Abs(twice) / 2.0;
        }

        // 12.2(a) and 12.2(b): the hemisphere, rimmed at its base ring.
        (double[][] vertices, int[][] faces, int[] rim) = SkinHemisphereNet();
        object net = SkinNetWith(
            netType, edgeType, vertices, faces, rim, noForces);
        object built = courses.Invoke(null, new object[] { net, 0.6, 0.35 })!;
        var cells = SkinCells(built);
        int courseCount = Reading<int>(built, "CourseCount");
        var caps = cells.Where(cell => cell.Cap).ToArray();
        if (caps.Length != 1)
        {
            throw new InvalidOperationException(
                "A dome with ONE springing rim gets exactly one cap, " +
                "because a keystone is one stone (rule 2.2.3); got " +
                $"{caps.Length}.");
        }
        if (caps[0].Course != courseCount - 1)
        {
            throw new InvalidOperationException(
                "The cap replaces the TILING of band n - 1 and its course " +
                $"is CourseCount - 1 = {courseCount - 1} (rule 2.4.1); got " +
                $"{caps[0].Course}.");
        }
        if (Math.Abs(caps[0].U0 + caps[0].U1) > 1.0e-9 ||
            !(caps[0].U1 - caps[0].U0 > 0.0))
        {
            throw new InvalidOperationException(
                "A cap's span is its whole girth, U0 and U1 being " +
                "-L / 2 and +L / 2 (rule 2.3.2); got " +
                $"[{caps[0].U0}, {caps[0].U1}].");
        }
        foreach (var cell in cells)
        {
            if (cell.Course > caps[0].Course && cell.Outline.Length < 4)
            {
                throw new InvalidOperationException(
                    "Nothing above the cap's course has fewer than four " +
                    "corners, which is the epsilon loop out of existence " +
                    "(check 12.2(b)).");
            }
        }
        double covered = cells.Sum(cell => PlanArea(cell.Outline));
        double netArea = 0.0;
        IList netFaces = (IList)net.GetType()
            .GetProperty("Faces")!.GetValue(net)!;
        foreach (object? item in netFaces)
        {
            int[] triangle = (int[])item!;
            netArea += PlanArea(new[]
            {
                vertices[triangle[0]],
                vertices[triangle[1]],
                vertices[triangle[2]]
            });
        }
        if (Math.Abs(covered - netArea) > 0.01 * netArea)
        {
            throw new InvalidOperationException(
                "The cells cover the surface: the summed plan area differs " +
                "from the net's own by under one per cent (check 12.2(b)), " +
                $"which the epsilon loop fails today; got {covered} against " +
                $"{netArea}.");
        }

        // 12.2(c): a BARREL with two springing rims gets a RIDGE and no cap.
        (double[][] barrelVertices, int[][] barrelFaces) = SkinBarrelNet();
        object barrel = SkinNetWith(
            netType, edgeType, barrelVertices, barrelFaces, SkinBarrelRim(),
            noForces);
        object barrelBuilt = courses.Invoke(
            null, new object[] { barrel, 0.6, 0.5 })!;
        if (SkinCells(barrelBuilt).Any(cell => cell.Cap))
        {
            throw new InvalidOperationException(
                "A barrel's crown is a RIDGE LINE and not a point, and its " +
                "two sides are separate traced components matched to one " +
                "another by nothing; no cap is emitted there (rule 2.5.2) " +
                "and each side gets an ordinary top band, which is what a " +
                "barrel is actually built as.");
        }
        if (!Reading<string>(barrelBuilt, "Diagnostics").Contains(
                "ridge", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "Say the ridge in the diagnostics in those words rather " +
                "than reporting a missing cap as a failure (rule 2.5.2).");
        }

        // 12.2(d): the TWO-OCULUS fixture, where a free edge is in the crown.
        (double[][] oculusVertices, int[][] oculusFaces, int[] oculusRim) =
            SkinTwoOculusNet();
        object oculus = SkinNetWith(
            netType, edgeType, oculusVertices, oculusFaces, oculusRim,
            noForces);
        object oculusBuilt = courses.Invoke(
            null, new object[] { oculus, 0.6, 0.35 })!;
        if (SkinCells(oculusBuilt).Any(cell => cell.Cap))
        {
            throw new InvalidOperationException(
                "Rule 2.2.1(b) refuses a crown region carrying a MESH " +
                "BOUNDARY EDGE, and both the region and the straddling " +
                "band are tested, so an oculus small enough to lie wholly " +
                "within the straddling band cannot pass; the two-oculus " +
                "fixture gets no cap.");
        }
        Console.WriteLine(
            "      Skin crown cap (check 12.2(d)): two-oculus refusal " +
            "reported as '" +
            Reading<string>(oculusBuilt, "Diagnostics")
                .Split('\n')
                .FirstOrDefault(line => line.StartsWith(
                    "Crown caps", StringComparison.Ordinal)) + "'.");

        // 12.2(e): the SLIVER, which pins rule 2.4.2 against the "cap one
        // band low" failure. CH is chosen from the net's own field extent so
        // the top band is exactly a twentieth of CH before the merge.
        double extent = SkinLevels(net).Where(double.IsFinite).Max();
        double sliverHeight = extent / 13.05;
        object sliver = courses.Invoke(
            null, new object[] { net, 0.6, sliverHeight })!;
        var sliverCells = SkinCells(sliver);
        int sliverCourses = Reading<int>(sliver, "CourseCount");
        var sliverCaps = sliverCells.Where(cell => cell.Cap).ToArray();
        if (sliverCourses != 13 ||
            sliverCaps.Length != 1 ||
            sliverCaps[0].Course != 12)
        {
            throw new InvalidOperationException(
                "BandCount's sliver merge runs BEFORE the cap decision " +
                "(rule 2.4.2): an extent of 13.05 CH is 14 bands whose top " +
                "is CH / 20, under CH / 4, so it merges to 13 and the cap " +
                $"sits at course 12. Got {sliverCourses} courses and " +
                $"{sliverCaps.Length} caps at course " +
                $"{(sliverCaps.Length > 0 ? sliverCaps[0].Course : -1)}.");
        }
    }
```

2. [ ] Wire it into `Run`, after the `ValidateSkinBedSpacing` block, and add `if (cell.Cap) continue;`
   to the loop in `ValidateSkinBedSpacing`, beside its existing top-course skip, because a cap's
   outline is one loop and carries no bed-to-bed chord at all:

```csharp
        try
        {
            ValidateSkinCrownCap(plugin);
            Console.WriteLine(
                "PASS  Skin crown cap: a rimmed hemisphere gets exactly ONE " +
                "cap, at course CourseCount - 1, spanning its whole girth, " +
                "and the cells then cover the net's plan area to within " +
                "one per cent, which the shipped epsilon loop fails; a " +
                "barrel with two springings gets a RIDGE and says so; the " +
                "two-oculus fixture is refused for its free edge; and an " +
                "extent of 13.05 CH still puts the cap on the top course, " +
                "which pins the sliver merge running first.");
        }
        catch (Exception exception)
        {
            failures.Add($"Skin crown cap: {DescribeException(exception)}");
        }
```

3. [ ] Build the harness. It must fail TO COMPILE, in `SkinCells` as step 0 rewrote it, because
   `SkinCell` carries no `Cap` property for `GetProperty("Cap")` to be given a non-null result from,
   and then at runtime with a null reference there. This is a compile-and-run failure rather than a
   failed assertion, and it is what step 4 answers.

4. [ ] Add the flag to `SkinCell` at SkinPatterns.cs:87-92:

```csharp
internal sealed record SkinCell(
    int Course,
    IReadOnlyList<double[]> Outline,
    bool Clipped,
    double U0,
    double U1,
    bool Cap = false);
```

5. [ ] Add the crown tests to SkinPatterns, above `Courses`:

```csharp
    /// <summary>One flag per face: does this face carry a MESH BOUNDARY
    /// EDGE, an edge belonging to exactly one triangle? Computed once per
    /// net, because rule 2.2.1(b) asks it of two whole face sets.</summary>
    private static bool[] FacesOnBoundary(SkinNet net)
    {
        var owners = new Dictionary<(int, int), int>();
        foreach (int[] face in net.Faces)
        {
            for (int corner = 0; corner < face.Length; corner++)
            {
                int a = face[corner];
                int b = face[(corner + 1) % face.Length];
                (int, int) key = a < b ? (a, b) : (b, a);
                owners[key] = owners.TryGetValue(key, out int seen)
                    ? seen + 1
                    : 1;
            }
        }
        var flagged = new bool[net.Faces.Count];
        for (int at = 0; at < net.Faces.Count; at++)
        {
            int[] face = net.Faces[at];
            for (int corner = 0; corner < face.Length; corner++)
            {
                int a = face[corner];
                int b = face[(corner + 1) % face.Length];
                (int, int) key = a < b ? (a, b) : (b, a);
                if (owners[key] == 1)
                {
                    flagged[at] = true;
                    break;
                }
            }
        }
        return flagged;
    }

    /// <summary>
    /// Rule 2.2.1's three tests, and the CROWN REGION they are asked of,
    /// defined tightly because three separate tests turn on it and a loose
    /// definition gives each of them a different answer.
    ///
    /// R is the connected set of net faces ALL THREE of whose vertices carry
    /// a Levels value strictly greater than the level, seeded from every
    /// such face that shares a vertex with a face the component crosses, and
    /// walked from face to face across a shared edge only where BOTH ends of
    /// that edge exceed the level. The STRADDLING BAND is the faces the
    /// component actually crosses. It is NOT in R: it is the band the cap's
    /// own outline runs through and it belongs to the cap rather than to the
    /// region the tests interrogate. Saying which of the two holds a face is
    /// what decides whether a dome gets a keystone and a barrel does not.
    ///
    /// A straddling face is assigned to a component by its own CROSSING
    /// POINTS, which ARE that component's points: Trace computes them with
    /// this same arithmetic and stores them, so the equality is exact but
    /// for a nanometre.
    /// </summary>
    private static bool CapQualifies(
        SkinNet net,
        double level,
        int componentAt,
        IReadOnlyList<SkinLevelCurve> components,
        bool[] faceOnBoundary,
        out string refusedBy)
    {
        SkinLevelCurve component = components[componentAt];
        if (!component.Closed)
        {
            refusedBy =
                "the top course is an OPEN strip, so its crown is a RIDGE " +
                "and not a disc, and both sides get an ordinary top band";
            return false;
        }

        // Every component's straddling faces, by crossing point.
        var straddling = new List<int>[components.Count];
        for (int at = 0; at < components.Count; at++)
            straddling[at] = new List<int>();
        for (int face = 0; face < net.Faces.Count; face++)
        {
            int[] triangle = net.Faces[face];
            bool below = false;
            bool above = false;
            bool finite = true;
            foreach (int corner in triangle)
            {
                double at = net.Levels[corner];
                if (!double.IsFinite(at))
                    finite = false;
                else if (at < level)
                    below = true;
                else
                    above = true;
            }
            if (!finite || !below || !above)
                continue;
            for (int corner = 0; corner < 3; corner++)
            {
                int a = triangle[corner];
                int b = triangle[(corner + 1) % 3];
                double da = net.Levels[a];
                double db = net.Levels[b];
                if (!((da < level && db >= level) ||
                      (db < level && da >= level)))
                {
                    continue;
                }
                double t = (level - da) / (db - da);
                double[] crossing = Lerp(net.Vertices[a], net.Vertices[b], t);
                for (int which = 0; which < components.Count; which++)
                {
                    foreach (double[] point in components[which].Points)
                    {
                        if (Math.Abs(point[0] - crossing[0]) <= 1.0e-9 &&
                            Math.Abs(point[1] - crossing[1]) <= 1.0e-9 &&
                            Math.Abs(point[2] - crossing[2]) <= 1.0e-9)
                        {
                            if (!straddling[which].Contains(face))
                                straddling[which].Add(face);
                            break;
                        }
                    }
                }
            }
        }

        // R, seeded from the straddling band and walked only across edges
        // both of whose ends exceed the level.
        bool AboveFace(int[] triangle)
        {
            foreach (int corner in triangle)
            {
                if (!(net.Levels[corner] > level))
                    return false;
            }
            return true;
        }
        var facesAt = new List<int>?[net.Vertices.Count];
        for (int face = 0; face < net.Faces.Count; face++)
        {
            foreach (int corner in net.Faces[face])
                (facesAt[corner] ??= new List<int>()).Add(face);
        }
        var region = new HashSet<int>();
        var queue = new Queue<int>();
        foreach (int seedFace in straddling[componentAt])
        {
            foreach (int corner in net.Faces[seedFace])
            {
                foreach (int candidate in facesAt[corner] ?? new List<int>())
                {
                    if (AboveFace(net.Faces[candidate]) &&
                        region.Add(candidate))
                    {
                        queue.Enqueue(candidate);
                    }
                }
            }
        }
        while (queue.Count > 0)
        {
            int[] triangle = net.Faces[queue.Dequeue()];
            for (int corner = 0; corner < 3; corner++)
            {
                int a = triangle[corner];
                int b = triangle[(corner + 1) % 3];
                if (!(net.Levels[a] > level) || !(net.Levels[b] > level))
                    continue;
                foreach (int candidate in facesAt[a] ?? new List<int>())
                {
                    if (!net.Faces[candidate].Contains(b))
                        continue;
                    if (AboveFace(net.Faces[candidate]) &&
                        region.Add(candidate))
                    {
                        queue.Enqueue(candidate);
                    }
                }
            }
        }

        foreach (int face in region.Concat(straddling[componentAt]))
        {
            if (faceOnBoundary[face])
            {
                refusedBy =
                    "a FREE EDGE or an oculus lies in the crown above this " +
                    "course, so the region is not a disc";
                return false;
            }
        }
        for (int other = 0; other < components.Count; other++)
        {
            if (other == componentAt)
                continue;
            foreach (int face in straddling[other])
            {
                foreach (int corner in net.Faces[face])
                {
                    foreach (int candidate in
                             facesAt[corner] ?? new List<int>())
                    {
                        if (region.Contains(candidate))
                        {
                            refusedBy =
                                "another component of the same course seeds " +
                                "this crown region, so it is the SADDLE " +
                                "joining two crowns and not a keystone";
                            return false;
                        }
                    }
                }
            }
        }
        refusedBy = string.Empty;
        return true;
    }
```

6. [ ] Emit the cap in `Courses`. Inside the `foreach (SkinBandInterval band in resolved.Tileable)`
   loop Task 17 wrote, before the component loop, add:

```csharp
            bool topBand = band.Course == bands - 1;
            bool[]? onBoundary = topBand ? FacesOnBoundary(net) : null;
```

   and inside the component loop, AFTER `int lowerAt = MatchBelow(mid, lowers);` and its upper twin
   are computed and validated, not at the top of the loop. The cap's outline is the curve at the
   band's LOW level, which is `lowers[lowerAt]`, so the block cannot run before `lowerAt` exists:

```csharp
                // Declared BEFORE the test, not in it. C# assigns an out
                // parameter only when the call is made, and `topBand &&` will
                // short-circuit on every band but the last, so a refusedBy
                // declared inside the condition is an unassigned local at the
                // line below and the file does not compile.
                string refusedBy = string.Empty;
                if (topBand &&
                    CapQualifies(
                        net, band.Low, component, mids, onBoundary!,
                        out refusedBy))
                {
                    // THE CAP'S OUTLINE IS THE LEVEL CURVE, whole, from its
                    // seam round to its seam (rule 2.3.1). It carries every
                    // trace vertex of that curve, so it typically has tens
                    // of corners, and it follows the surface exactly rather
                    // than chording across it, the same property Run gives
                    // every other cell edge. It is NOT exempted from
                    // KeepValidPlans and must not be: if it ever fails,
                    // that is a defect and the filter is where it should
                    // show.
                    var loop = new List<double[]>();
                    for (int at = 0; at < mid.Points.Count; at++)
                        loop.Add(mid.Points[at]);
                    List<double[]> capOutline = Dedupe(loop);
                    if (capOutline.Count >= 3)
                    {
                        capGirths.Add(mid.Length);
                        keyed.Add((
                            band.Course,
                            component,
                            -mid.Length / 2.0,
                            new SkinCell(
                                band.Course, capOutline, false,
                                -mid.Length / 2.0, mid.Length / 2.0,
                                true)));
                        continue;
                    }
                }
                if (topBand && refusedBy.Length > 0)
                    capRefusals.Add(refusedBy);
```

   The cap's outline is the curve at the band's LOW level, which is L_top, while `mid` above is the
   band's mid curve; replace `mid` with `lowers[lowerAt]` in the three places inside that block, the
   two outline reads and the girth, which is why the block is placed after `lowerAt` is computed and
   not at the top of the loop. Declare `var capGirths = new List<double>();` and
   `var capRefusals = new List<string>();` beside `transitions`, and pass `capGirths` and a cap line
   into the return. Where a cap is emitted, band n - 1 is NOT otherwise tiled for that component,
   which is what the `continue` does; where it is refused, the band is tiled as an ordinary band with
   the level curve at dMax minus epsilon as its upper boundary, which is today's behaviour kept
   deliberately as the fallback (rule 2.2.2).

7. [ ] Give the diagnostics the cap line. Add a `string? caps = null` parameter to
   `PatternDiagnostics` after `transitions`, appended as its own line when not null, and build it in
   `Courses` as:

```csharp
        string? capLine = capGirths.Count > 0 || capRefusals.Count > 0
            ? $"Crown caps: {capGirths.Count}" +
              (capGirths.Count > 0
                  ? " (girth " + string.Join(
                      ", ",
                      capGirths.Select(girth =>
                          girth.ToString(
                              "F3", CultureInfo.InvariantCulture) + " m")) +
                    ")"
                  : string.Empty) +
              (capRefusals.Count > 0
                  ? "; no cap where " +
                    string.Join("; ", capRefusals.Distinct())
                  : string.Empty)
            : null;
```

   A barrel's refusal then carries the word "ridge" from `CapQualifies`' own first message, which is
   what check 12.2(c) reads.

8. [ ] Exclude caps from the piece-length statistics, which is rule 2.3.2a and matters more than it
   sounds: on a dome the cap's girth is metres against ordinary pieces of order S, so a cap left in the
   list dominates the maximum and the max-over-min ratio single-handedly, and the one number this round
   exists to restore stops measuring the thing it was restored for. In the `Courses` return, replace
   `cells.Select(cell => cell.U1 - cell.U0).ToList()` with
   `cells.Where(cell => !cell.Cap).Select(cell => cell.U1 - cell.U0).ToList()`, and pass
   `capGirths` for `CapGirths`.

9. [ ] Build and run the harness. The new PASS line must appear. The shipped courses pins move where a
   fixture now carries a cap: re-measure and re-pin each with the reason written into the check's own
   message.

10. [ ] Scan for clash files and commit.

```powershell
git add "plugin/native_v02/Components/SkinPatterns.cs" "tests/native_smoke/Program.cs"
git commit -m "feat(skin): the crown gets a keystone instead of an epsilon loop"
```

---

### Task 19: signed spans and the seam-outward build order

**Files:**
- Modify: plugin/native_v02/Components/SkinPatterns.cs:1913-1944 (`CourseSpans`) and the two sort keys,
  in `Courses` as Task 17 rewrote it and at :2423-2431 in `Hexagonal`
- Test: tests/native_smoke/Program.cs, new `ValidateSkinBuildOrder` plus its entry in `Run`

**Interfaces:**
- Consumes: `CourseSpans(SkinLevelCurve mid, int pieces, double pitch, double phase)`.
- Produces: spans in the signed range (-L / 2, +L / 2] on a closed course, and cells emitted seam
  outward within every branch, which Task 20's merge and rule 7.3's filter both read.

Rule 7.3 is the consequence that must not be discovered late: `KeepValidPlans` runs in EMISSION ORDER,
and which of an overlapping pair survives is decided by that order. The filter runs in the NEW order,
because "the first cell wins" must mean "the first cell the author is handed", and seam-outward then
biases survival towards the cells nearest the seam, which are the setout cells and the right ones to
keep. Every pinned drop count in the harness must be re-measured against the new order, and a moved
number is not by itself a regression.

1. [ ] Add the check:

```csharp
    /// <summary>
    /// Build order (spec section 7), checks 12.7(a) and 12.7(b). Within
    /// every branch the absolute seam-relative mid-span is non-decreasing
    /// and the first two cells lie on OPPOSITE SIDES of the seam. That
    /// second bar is only reachable because of rule 7.1.1: on a closed
    /// course CourseSpans emits every span non-negative, so without the
    /// re-centring no cell ever has a negative mid and the bar fails on
    /// every dome fixture. Taken on a closed course and on an open strip,
    /// since the two reach it by different routes, and in ARRIVAL order,
    /// never re-sorted.
    /// </summary>
    private static void ValidateSkinBuildOrder(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        MethodInfo courses = RequirePublicStatic(patterns, "Courses");
        foreach ((double[][] vertices, int[][] faces, string label,
                  bool closed) fixture in new[]
                 {
                     (SkinDomeNet().Vertices, SkinDomeNet().Faces,
                      "dome", true),
                     (SkinBarrelNet().Vertices, SkinBarrelNet().Faces,
                      "barrel", false)
                 })
        {
            object net = Activator.CreateInstance(
                netType,
                new object[] { fixture.vertices, fixture.faces })!;
            object built = courses.Invoke(
                null, new object[] { net, 0.6, 0.5 })!;
            var cells = SkinCells(built);
            foreach (IGrouping<int, (int Course, double[][] Outline,
                         bool Clipped, double U0, double U1, bool Cap)> branch in
                     cells.GroupBy(cell => cell.Course))
            {
                var inBranch = branch.ToArray();
                double previous = -1.0;
                foreach (var cell in inBranch)
                {
                    if (cell.Cap)
                        continue;
                    double mid = Math.Abs((cell.U0 + cell.U1) / 2.0);
                    if (mid < previous - 1.0e-9)
                    {
                        throw new InvalidOperationException(
                            $"On the {fixture.label}, cells within a branch " +
                            "run FROM THE SEAM OUTWARD, so the absolute " +
                            "mid-span is non-decreasing (rule 7.1); course " +
                            $"{cell.Course} goes {previous} then {mid}.");
                    }
                    previous = mid;
                }
                var ordinary = inBranch.Where(cell => !cell.Cap).ToArray();
                if (ordinary.Length >= 2)
                {
                    double first = (ordinary[0].U0 + ordinary[0].U1) / 2.0;
                    double second = (ordinary[1].U0 + ordinary[1].U1) / 2.0;
                    if (!(first < 0.0 && second > 0.0) &&
                        !(first > 0.0 && second < 0.0))
                    {
                        throw new InvalidOperationException(
                            $"On the {fixture.label}, the order alternates " +
                            "either side of the seam and a tie goes to the " +
                            "NEGATIVE side first (rule 7.1); course " +
                            $"{ordinary[0].Course} opens with mids {first} " +
                            $"and {second}.");
                    }
                }
                if (fixture.closed)
                {
                    foreach (var cell in inBranch)
                    {
                        if (cell.Cap)
                            continue;
                        if (cell.U0 > cell.U1)
                        {
                            throw new InvalidOperationException(
                                "A re-centred span keeps U0 below U1 even " +
                                "where it STRADDLES the seam (rule 7.1.2); " +
                                $"got [{cell.U0}, {cell.U1}].");
                        }
                    }
                }
            }
        }
    }
```

2. [ ] Wire it into `Run` after the `ValidateSkinCrownCap` block:

```csharp
        try
        {
            ValidateSkinBuildOrder(plugin);
            Console.WriteLine(
                "PASS  Skin build order: within every branch the cells run " +
                "from the seam outward, alternating either side of it with " +
                "the negative side first, on a closed dome course and on " +
                "an open barrel strip alike, the closed course's spans " +
                "having been re-centred into (-L/2, +L/2] at source so U " +
                "means signed arc about the seam everywhere in the engine.");
        }
        catch (Exception exception)
        {
            failures.Add(
                $"Skin build order: {DescribeException(exception)}");
        }
```

3. [ ] Build and run the harness. It must fail on the dome, where every mid is non-negative today.

4. [ ] Re-centre the closed branch of `CourseSpans` at SkinPatterns.cs:1919-1927:

```csharp
        if (mid.Closed)
        {
            double length = mid.Length;
            for (int k = 0; k < pieces; k++)
            {
                double u0 = phase + k * pitch;
                double u1 = u0 + pitch;
                // RE-CENTRED AT SOURCE into the signed range
                // (-L / 2, +L / 2] (rule 7.1.1), on the SPANS and not
                // merely on the sort key. Re-centring the spans gives U one
                // meaning across the whole engine, closed and open alike,
                // namely signed arc about the seam; wrapping only the sort
                // key would leave two meanings in one engine and would make
                // rule 6.2's "a tie goes to the neighbour with the lower
                // U0, which is the seam-ward one" false on every dome. The
                // cost is stated rather than discovered: every pinned U0
                // and U1 on a closed fixture moves, and the sidecar's
                // recorded spans move with them.
                if ((u0 + u1) / 2.0 > length / 2.0)
                {
                    u0 -= length;
                    u1 -= length;
                }
                spans.Add((u0, u1));
            }
            return spans;
        }
```

5. [ ] Order the emission seam outward. In `Courses`, replace the `OrderBy` chain with:

```csharp
        List<SkinCell> cells = KeepValidPlans(
            keyed
                .OrderBy(item => item.Course)
                .ThenBy(item => item.Order)
                .ThenBy(item => Math.Abs(
                    (item.Cell.U0 + item.Cell.U1) / 2.0))
                .ThenBy(item => (item.Cell.U0 + item.Cell.U1) / 2.0)
                .Select(item => item.Cell)
                .ToList(),
            out int degenerateDropped,
            out int overlapDropped);
```

   and the same chain in `Hexagonal` at SkinPatterns.cs:2423-2431, keeping its `ThenBy(item =>
   item.Chart)` where the courses engine has `Order`. Where a course holds several traced components,
   components are ordered as they are today, by their index, before this rule applies within each
   (rule 7.1).

6. [ ] Build and run the harness. Every pinned U0, U1, joint set and drop count on a CLOSED fixture
   has moved. Re-measure each, re-pin it as a new measurement, and write the reason into the check's
   own message: rule 7.1.2 for the moved spans, rule 7.3 for any moved drop count. The mirror-symmetry
   and pitch pins on the OPEN barrel do not move, because the open branch of `CourseSpans` was already
   signed about the seam.

7. [ ] Scan for clash files and commit.

```powershell
git add "plugin/native_v02/Components/SkinPatterns.cs" "tests/native_smoke/Program.cs"
git commit -m "feat(skin): spans are signed about the seam and cells are emitted seam outward"
```

---

### Task 20: Min Piece, one threshold read at both ends, and the merge

**Files:**
- Modify: plugin/native_v02/Components/SkinPatterns.cs, `Courses`' signature and its tiling loop
- Test: tests/native_smoke/Program.cs, new `ValidateSkinPieceSize` plus its entry in `Run`

**Interfaces:**
- Consumes: `CourseSpans` as Task 19 left it, `BandCell`.
- Produces: `public static SkinPatternResult Courses(SkinNet net, double size, double courseHeight,
  double minPiece)` with a three-argument overload defaulting to 1.0 / 3.0;
  `private static List<(double U0, double U1, bool Clipped)> MergeShortPieces(List<(double U0, double
  U1, bool Clipped)> spans, double minimum, ref int merged, ref int keptShort, ref int stillShort)`;
  the record's `MergedPieces`, `MergedShortKept` and `MergedStillShort`.

Rule 6.0 names the threshold ONCE and uses it twice. `MP` is a pure fraction of Size, default 1/3,
floored at 0 and capped at 0.5. The MINIMUM PIECE SIZE is `MP * S`, which this task merges anything at
or under; the MAXIMUM is `Mx = S / MP`, which is 3 S at the default and 2 S at the cap, and which Task
22 splits a crown cap strictly above. Reciprocal, and not a second port: a second number would let an
author set a minimum above his own maximum. At MP = 0 the minimum is 0 and Mx is unbounded, so both
ends go off together.

The three-argument overload is explicit and not an optional parameter, for the reason Task 12 gives:
`MethodInfo.Invoke` does not fill optional parameters either, so every existing three-argument call in
the harness would stop binding.

1. [ ] Add the check:

```csharp
    /// <summary>
    /// Piece size at both ends (spec section 6), checks 12.6(a) to 12.6(e).
    /// The barrel's open strips have end pieces of exactly half a pitch on
    /// odd courses, 0.3 m at S 0.6 and CH 0.5, which the harness already
    /// pins in those words; MP at 0.5 merges those end pieces and MP at 0.3
    /// does not. The values are 0.5 and 0.3 and NOT 0.6, for two reasons
    /// that both hold at once: rule 6.4 caps MP at 0.5 and clamps anything
    /// above it, so 0.6 never reaches the engine; and at MP 0.5 the
    /// threshold is exactly 0.3, which a strict "under" would leave
    /// undecided on the one fixture this check names, so rule 6.1's
    /// comparison is "at or under" within 1e-9.
    /// </summary>
    private static void ValidateSkinPieceSize(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        MethodInfo courses = RequirePublicStatic(patterns, "Courses");
        (double[][] vertices, int[][] faces) = SkinBarrelNet();
        object net = Activator.CreateInstance(
            netType, new object[] { vertices, faces })!;
        object At(double minPiece) => courses.Invoke(
            null, new object[] { net, 0.6, 0.5, minPiece })!;

        // 12.6(a): the two bars separate at 0.5 and at 0.3.
        var merged = SkinCells(At(0.5));
        var unmerged = SkinCells(At(0.3));
        if (merged.Any(cell =>
                cell.U1 - cell.U0 <= 0.3 + 1.0e-9 && !cell.Cap))
        {
            throw new InvalidOperationException(
                "At MP 0.5 the minimum piece is 0.3 m and the barrel's odd " +
                "courses' 0.3 m end pieces are AT the threshold, so they " +
                "merge (rule 6.1's comparison is at-or-under within 1e-9).");
        }
        if (!unmerged.Any(cell =>
                Math.Abs(cell.U1 - cell.U0 - 0.3) < 1.0e-9))
        {
            throw new InvalidOperationException(
                "At MP 0.3 the minimum piece is 0.18 m and the 0.3 m end " +
                "pieces are plainly above it, so they stand.");
        }

        // 12.6(b): after merging, no span is under MP * S anywhere, except
        // a course's only piece and a merged pair whose union is still
        // under, both of which are counted. Stated without the exceptions
        // this check is false against two rules written on purpose.
        object built = At(1.0 / 3.0);
        int keptShort = Reading<int>(built, "MergedShortKept");
        int stillShort = Reading<int>(built, "MergedStillShort");
        int shortCells = SkinCells(built).Count(cell =>
            !cell.Cap && cell.U1 - cell.U0 <= 0.2 + 1.0e-9);
        if (shortCells > keptShort + stillShort)
        {
            throw new InvalidOperationException(
                $"{shortCells} cells are at or under MP * S = 0.2 m, but " +
                $"only {keptShort} courses kept their only piece and " +
                $"{stillShort} merged pairs are still under the threshold " +
                "(rules 6.5 and 6.3); the rest are a defect.");
        }

        // 12.6(c): the merge TERMINATES. The MERGE PASS ITSELF is run twice,
        // the second time over its own output, and the answer does not move.
        // Calling Courses twice would compare a pure function with itself and
        // could never fail, whatever the engine did; this drives the static
        // that rule 6.3 is about.
        MethodInfo mergeShort = patterns.GetMethod(
            "MergeShortPieces",
            BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "MergeShortPieces must be reachable for check 12.6(c) to " +
                "measure a second pass rather than a second call.");
        Type spanType = typeof(ValueTuple<double, double, bool>);
        Type spanList = typeof(List<>).MakeGenericType(spanType);
        object SpansOf(params (double U0, double U1, bool Clipped)[] spans)
        {
            object list = Activator.CreateInstance(spanList)!;
            MethodInfo add = spanList.GetMethod("Add")!;
            foreach ((double u0, double u1, bool clipped) in spans)
            {
                add.Invoke(list, new[]
                {
                    Activator.CreateInstance(spanType, u0, u1, clipped)
                });
            }
            return list;
        }
        (double U0, double U1)[] ReadSpans(object list) =>
            ((IEnumerable)list).Cast<object>()
                .Select(item => (
                    (double)item.GetType().GetField("Item1")!.GetValue(item)!,
                    (double)item.GetType().GetField("Item2")!.GetValue(item)!))
                .ToArray();
        object RunMerge(object spans)
        {
            object?[] arguments =
            {
                spans, 0.2, 0, 0, 0
            };
            object answer = mergeShort.Invoke(null, arguments)!;
            return answer;
        }
        // One course's spans, seam outward, with two short pieces at one end
        // and long ones elsewhere: the shape rule 6.3 is written against.
        object first = RunMerge(SpansOf(
            (-1.5, -0.9, false), (-0.9, -0.3, false), (-0.3, 0.0, true),
            (0.0, 0.6, false), (0.6, 1.2, false), (1.2, 1.35, true)));
        object second = RunMerge(first);
        if (!ReadSpans(first).SequenceEqual(ReadSpans(second)))
        {
            throw new InvalidOperationException(
                "Merging runs in ONE pass over a course's spans, seam " +
                "outward, and a span that has already absorbed a merge is " +
                "not itself tested again, so the pass terminates in a " +
                "single sweep and a SECOND pass over its own output changes " +
                "nothing (rule 6.3). The first pass gave " +
                $"[{string.Join(" ", ReadSpans(first).Select(s => $"{s.U0:F3}..{s.U1:F3}"))}] " +
                "and the second moved it.");
        }

        // 12.6(e), first half: MP at 0 changes nothing at either end. The
        // baseline is the engine's own PRE-MERGE span set, read off the
        // three-argument overload with the merge suppressed by the same zero,
        // and not a second identical call to At(0.0), which would compare a
        // pure function with itself.
        var off = SkinCells(At(0.0))
            .Select(cell => (cell.Course, cell.U0, cell.U1))
            .ToArray();
        object premerged = RunMerge(SpansOf(
            (-1.5, -0.9, false), (-0.9, -0.3, false), (-0.3, 0.0, true),
            (0.0, 0.6, false), (0.6, 1.2, false), (1.2, 1.35, true)));
        object untouched = mergeShort.Invoke(
            null,
            new object?[]
            {
                SpansOf(
                    (-1.5, -0.9, false), (-0.9, -0.3, false), (-0.3, 0.0, true),
                    (0.0, 0.6, false), (0.6, 1.2, false), (1.2, 1.35, true)),
                0.0, 0, 0, 0
            })!;
        if (ReadSpans(untouched).Length != 6)
        {
            throw new InvalidOperationException(
                "At a minimum of 0 the merge returns its input untouched, " +
                "six spans in and six out; it returned " +
                $"{ReadSpans(untouched).Length}.");
        }
        if (ReadSpans(premerged).Length == 6)
        {
            throw new InvalidOperationException(
                "This check only measures anything while the SAME spans DO " +
                "merge at a live minimum; at 0.2 they did not, so the " +
                "zero case is being compared against nothing.");
        }
        if (Reading<int>(At(0.0), "MergedPieces") != 0)
        {
            throw new InvalidOperationException(
                "MP at 0 is a legal value and not an error: the minimum is " +
                "0 and Mx is unbounded, so no piece is merged and no crown " +
                "cap is split (rule 6.0). It is the value an author uses " +
                "to see the engine's raw output; MergedPieces read " +
                $"{Reading<int>(At(0.0), "MergedPieces")} and the cells were " +
                $"{off.Length}.");
        }

        // 12.6(d): A COURSE HOLDING EXACTLY ONE PIECE IN TOTAL KEEPS IT
        // HOWEVER SHORT. Rule 6.5 in rule 6.5's own words, and NOT "a course
        // with exactly one short piece", which would wrongly protect a single
        // short piece sitting among many long ones and is the opposite of
        // what the rule says. Driven on the static, because no fixture in
        // this file gives a course exactly one piece and inventing one would
        // measure the fixture rather than the rule.
        object lonely = mergeShort.Invoke(
            null,
            new object?[] { SpansOf((-0.05, 0.05, true)), 0.2, 0, 0, 0 })!;
        (double U0, double U1)[] kept = ReadSpans(lonely);
        if (kept.Length != 1 ||
            Math.Abs(kept[0].U1 - kept[0].U0 - 0.1) > 1.0e-12)
        {
            throw new InvalidOperationException(
                "A course whose ONLY piece is under the minimum keeps that " +
                "piece as it is (rule 6.5): a tenth of a metre against a " +
                "minimum of 0.2 survives, because there is nothing to merge " +
                "it into and a dropped course is a hole. It came back as " +
                $"{kept.Length} spans.");
        }
        object lonelyAtHalf = mergeShort.Invoke(
            null,
            new object?[] { SpansOf((-0.05, 0.05, true)), 0.3, 0, 0, 0 })!;
        if (ReadSpans(lonelyAtHalf).Length != 1)
        {
            throw new InvalidOperationException(
                "The same course keeps its only piece at MP 0.5 too; the " +
                "rule is about the piece being ALONE and not about how far " +
                "under the threshold it is.");
        }
        // And the negative case, which is what stops the weaker reading:
        // ONE short piece among many long ones is NOT protected.
        object crowded = mergeShort.Invoke(
            null,
            new object?[]
            {
                SpansOf(
                    (-1.2, -0.6, false), (-0.6, 0.0, false),
                    (0.0, 0.1, true), (0.1, 0.7, false), (0.7, 1.3, false)),
                0.2, 0, 0, 0
            })!;
        if (ReadSpans(crowded).Length != 4)
        {
            throw new InvalidOperationException(
                "A single SHORT piece among many long ones is not what rule " +
                "6.5 protects: it merges, and five spans come back as four. " +
                $"Got {ReadSpans(crowded).Length}. Reading 6.5 as \"a course " +
                "with exactly one short piece\" is the opposite of what it " +
                "says.");
        }
    }
```

`MergeShortPieces` takes three `ref int` counters, so the reflection call above passes an `object?[]` and reads the updated counts back out of it where a check wants them; `RunMerge` returns the list and discards the counts, which is all checks 12.6(c) and 12.6(d) need.

2. [ ] Wire it into `Run` after the `ValidateSkinBuildOrder` block, with a PASS line naming the two
   bars, the two counted exceptions, the single pass and MP at zero.

3. [ ] Build and run the harness. It must fail: `Courses` takes three arguments.

4. [ ] Give `Courses` the fourth argument and the overload:

```csharp
    /// <summary>The engine's own default for Min Piece, which is rule 9.5's
    /// port default: a third of Size, giving a minimum piece of S / 3 and a
    /// maximum of 3 S. An explicit overload and not an optional parameter,
    /// so that every reflection call binds.</summary>
    public static SkinPatternResult Courses(
        SkinNet net,
        double size,
        double courseHeight) =>
        Courses(net, size, courseHeight, 1.0 / 3.0);

    public static SkinPatternResult Courses(
        SkinNet net,
        double size,
        double courseHeight,
        double minPiece)
```

   and, at the top of the four-argument body, after `RequireSizes`:

```csharp
        // Rule 6.4's bounds, applied in the engine so the harness can
        // measure them without a canvas. The component clamps and WARNS
        // (rule 9.5); the engine simply takes the clamped value, the same
        // split the CH floor already keeps.
        double clampedMinPiece =
            double.IsFinite(minPiece)
                ? Math.Min(Math.Max(minPiece, 0.0), 0.5)
                : 1.0 / 3.0;
        double minimumPiece = clampedMinPiece * size;
```

5. [ ] Add the merge, above `BandCell`:

```csharp
    /// <summary>
    /// Rules 6.1 to 6.7. A cell whose along-course span is AT OR UNDER the
    /// minimum piece size is MERGED into a neighbour, and the merged cell is
    /// REBUILT and not glued: this runs on the SPANS, before any outline
    /// exists, so the BandCell construction is simply run again over the
    /// union span. Gluing two outlines would leave the absorbed joint's two
    /// points in the ring as a pair of collinear corners, which is exactly
    /// the degeneracy rule 6.8 exists to guard PlanInteriorPoint against.
    ///
    /// WHICH NEIGHBOUR WINS: the neighbour ALONG THE COURSE with the SHORTER
    /// span, so merging keeps the maximum piece length down rather than
    /// growing one long piece. A tie goes to the neighbour with the lower
    /// U0, which is deterministic and is the seam-ward one. A piece with
    /// only one neighbour, which a strip end has, merges into that one.
    ///
    /// WHAT STOPS A CASCADE: ONE pass, seam outward, and a span that has
    /// already absorbed a merge is not itself tested again. Each span can
    /// therefore grow at most once per side and the pass terminates in a
    /// single sweep. There is no iteration to convergence and no recursion.
    ///
    /// The neighbour walk is LINEAR and never wraps, even on a closed
    /// course, and the reason is worth stating: within a closed course every
    /// piece is exactly the pitch by construction, so the rule does not bite
    /// there at all, and a span merged across the meridian opposite the seam
    /// would not be one arc in signed U anyway. It is mostly a rim rule.
    /// </summary>
    private static List<(double U0, double U1, bool Clipped)>
        MergeShortPieces(
            List<(double U0, double U1, bool Clipped)> spans,
            double minimum,
            ref int merged,
            ref int keptShort,
            ref int stillShort)
    {
        if (!(minimum > 0.0) || spans.Count == 0)
            return spans;
        var working = spans
            .OrderBy(span => span.U0)
            .ToList();
        if (working.Count == 1)
        {
            // A course whose ONLY piece is under the threshold keeps that
            // piece as it is (rule 6.5), and the fact is counted.
            if (working[0].U1 - working[0].U0 <= minimum + 1.0e-9)
                keptShort++;
            return working;
        }
        var absorbed = new bool[working.Count];
        var grown = new bool[working.Count];
        int[] order = Enumerable
            .Range(0, working.Count)
            .OrderBy(at => Math.Abs(
                (working[at].U0 + working[at].U1) / 2.0))
            .ThenBy(at => (working[at].U0 + working[at].U1) / 2.0)
            .ToArray();
        foreach (int at in order)
        {
            if (absorbed[at] || grown[at])
                continue;
            if (working[at].U1 - working[at].U0 > minimum + 1.0e-9)
                continue;
            int left = at - 1;
            while (left >= 0 && absorbed[left])
                left--;
            int right = at + 1;
            while (right < working.Count && absorbed[right])
                right++;
            bool hasLeft = left >= 0;
            bool hasRight = right < working.Count;
            if (!hasLeft && !hasRight)
                continue;
            int into;
            if (!hasLeft)
            {
                into = right;
            }
            else if (!hasRight)
            {
                into = left;
            }
            else
            {
                double leftSpan = working[left].U1 - working[left].U0;
                double rightSpan = working[right].U1 - working[right].U0;
                into = rightSpan < leftSpan - 1.0e-12 ? right : left;
            }
            double u0 = Math.Min(working[into].U0, working[at].U0);
            double u1 = Math.Max(working[into].U1, working[at].U1);
            working[into] = (
                u0, u1, working[into].Clipped || working[at].Clipped);
            absorbed[at] = true;
            grown[into] = true;
            merged++;
            if (u1 - u0 <= minimum + 1.0e-9)
                stillShort++;
        }
        var kept = new List<(double U0, double U1, bool Clipped)>();
        for (int at = 0; at < working.Count; at++)
        {
            if (!absorbed[at])
                kept.Add(working[at]);
        }
        return kept;
    }
```

6. [ ] Call it in `Courses`' tiling loop, replacing the `foreach ((double u0, double u1) in
   CourseSpans(...))` loop with:

```csharp
                var spans = new List<(double U0, double U1, bool Clipped)>();
                foreach ((double u0, double u1) in
                         CourseSpans(mid, pieces, pitch, phase))
                {
                    // Only an open strip's end piece is shorter than the
                    // pitch: it absorbed the phase, and it is the
                    // "boundary-clipped" cell of this pattern.
                    spans.Add((u0, u1, u1 - u0 < pitch - 1.0e-9));
                }
                // The merge runs BEFORE KeepValidPlans (rule 6.6), so the
                // filter sees and judges the cells the author is actually
                // handed.
                spans = MergeShortPieces(
                    spans, minimumPiece,
                    ref mergedPieces, ref mergedShortKept,
                    ref mergedStillShort);
                foreach ((double u0, double u1, bool clipped) in spans)
                {
                    SkinCell cell = BandCell(
                        band.Course, lowerCurve, mid, upperCurve,
                        u0, u1, clipped);
                    if (cell.Outline.Count < 3)
                        continue;
                    keyed.Add((band.Course, component, u0, cell));
                }
```

   with `int mergedPieces = 0; int mergedShortKept = 0; int mergedStillShort = 0;` declared beside
   `transitions`, and the two exception counts added to the record as `int MergedShortKept` and
   `int MergedStillShort` after `TracePasses`, which check 12.6(b) is the reason for.

   The record is POSITIONAL, so all THREE construction sites gain the two arguments in this same
   commit, exactly as Task 17 step 7 did for `ExtraLevels` and `TracePasses`. An earlier draft named
   only the `Courses` return and the plugin would not have compiled:

   - `Empty` at SkinPatterns.cs:2096: append `0, 0`. Nothing was merged and nothing was kept short,
     because nothing was built.
   - the `Courses` return: append `mergedShortKept, mergedStillShort`, with `mergedPieces` already
     passed for `MergedPieces`.
   - the `Hexagonal` return: append `0, 0`, for the reason rule 6.7(b) gives below, which is that
     section 6 does not reach the lattice at all.

7. [ ] Add the merged count to the diagnostics text, in `PatternDiagnostics`, after the clipped line:

```csharp
        lines.Add(
            $"Merged pieces: {mergedPieces} (spans at or under the minimum " +
            "piece size, merged into the shorter neighbour along the course)");
```

   with `int mergedPieces` added as a parameter after `clipped`, and `0` passed from `Hexagonal`,
   which rule 6.7(b) excludes from section 6 outright: "the neighbour ALONG THE COURSE" has no
   referent in a lattice, two hexagons of one row meet at a single side vertex rather than along an
   edge, and merging two cells that touch at a point is not a merge but a bow tie.

8. [ ] Build and run the harness. The barrel's odd-course end pieces now merge at the default MP of
   1/3, whose minimum is 0.2 m, and 0.3 m is above it, so the shipped joint pins at
   Program.cs:9762-9771 do NOT move; if any pin does move, re-measure and re-pin it with the reason.

9. [ ] Scan for clash files and commit.

```powershell
git add "plugin/native_v02/Components/SkinPatterns.cs" "tests/native_smoke/Program.cs"
git commit -m "feat(skin): Min Piece names one threshold and the short pieces merge"
```

---

### Task 21: the zero-area centroid guard and the studio's own two tests

**Files:**
- Modify: plugin/native_v02/Components/SkinPatterns.cs:1445-1479 (`PlanInteriorPoint`),
  :1694-1711 (`Dedupe`), :1618-1673 (`KeepValidPlans`'s degenerate branch)
- Test: tests/native_smoke/Program.cs, new `ValidateSkinDegeneracyGuards` plus its entry in `Run`

**Interfaces:**
- Consumes: `SplitPolygonInOrder`, `PlanContains`, `PlanSide`, all already in the file.
- Produces: `public static double[]? PlanInteriorPoint(IReadOnlyList<double[]> outline, out int
  degenerateSkipped)` with the shipped one-argument form kept as an overload; the record's
  `DegenerateCentroidsSkipped`.

Rule 11.11 permits exactly two exceptions to section 11, and this task is both of them. The safety
argument differs between the halves and must be stated for each. Adding the vertex-on-edge test makes
`KeepValidPlans` drop MORE cells and never fewer, so it cannot hide a defect, and every fixture
asserting zero drops must still assert zero after it. Raising the duplicate test does NOT have that
property: it removes POINTS from outlines rather than dropping cells, and removing a point can turn a
self-crossing plan ring into a clean one, so it can make the filter drop FEWER. What it guarantees
instead is the thing it exists for, that no surviving outline holds two points the studio would
reject, and check 12.6(g) asserts exactly that rather than assuming it.

1. [ ] Add the check:

```csharp
    /// <summary>
    /// Checks 12.6(f) and 12.6(g). The zero-area candidate centroid is
    /// Param's own carried ruling in his own words: "a candidate interior
    /// point can be the centroid of three collinear trace corners lying
    /// exactly ON the joint, where the containment test is a coin flip.
    /// Named fix: refuse a candidate centroid whose triangle has no area."
    ///
    /// The BARREL is the fixture, and not by luck: every level cut there is
    /// a straight strip, so every cell's lower run is a chain of collinear
    /// trace corners and the candidate triangles taken off it have no area
    /// at all. Check 12.6(f) asks for the same fixture measured with the
    /// guard removed; a build without the guard is not something this
    /// harness can produce, so what is measured instead is that the guard
    /// FIRES (the skipped count is above zero) while nothing is dropped,
    /// which is the same claim in one build rather than two.
    /// </summary>
    private static void ValidateSkinDegeneracyGuards(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        MethodInfo courses = RequirePublicStatic(patterns, "Courses");
        MethodInfo hexagonal = RequirePublicStatic(patterns, "Hexagonal");
        (double[][] vertices, int[][] faces) = SkinBarrelNet();
        object net = Activator.CreateInstance(
            netType, new object[] { vertices, faces })!;
        object built = courses.Invoke(
            null, new object[] { net, 0.6, 0.5 })!;
        if (Reading<int>(built, "DegenerateCentroidsSkipped") <= 0)
        {
            throw new InvalidOperationException(
                "The barrel's level cuts are straight strips, so its cells " +
                "carry collinear trace corners and the zero-area guard MUST " +
                "fire; a count of zero means the check is measuring the " +
                "fixture's luck and not the guard (rule 6.8).");
        }
        if (Reading<int>(built, "PlanDegenerateDropped") != 0)
        {
            throw new InvalidOperationException(
                "The guard turns an ARBITRARY containment answer into a " +
                "defined one and can only stop a cell being dropped for a " +
                "reason that was never real; no cell is dropped as " +
                "degenerate on the barrel.");
        }

        // 12.6(g): THE STUDIO'S OWN TEST, per axis in plan, over the whole
        // ring, on every fixture. A three-dimensional distance check here
        // would pass while the studio rejected the file, which is the gap
        // rule 3.5.4 was written to close.
        foreach ((double[][] v, int[][] f, string label) fixture in new[]
                 {
                     (SkinBarrelNet().Vertices, SkinBarrelNet().Faces,
                      "barrel"),
                     (SkinDomeNet().Vertices, SkinDomeNet().Faces, "dome"),
                     (SkinTwoOculusNet().Vertices,
                      SkinTwoOculusNet().Faces, "two-oculus"),
                     (SkinSerpentineNet().Vertices,
                      SkinSerpentineNet().Faces, "serpentine")
                 })
        {
            object fixtureNet = Activator.CreateInstance(
                netType, new object[] { fixture.v, fixture.f })!;
            foreach (MethodInfo engine in new[] { courses, hexagonal })
            {
                object pattern = engine.Invoke(
                    null, new object[] { fixtureNet, 0.6, 0.35 })!;
                foreach (var cell in SkinCells(pattern))
                {
                    double[][] ring = cell.Outline;
                    for (int i = 0; i < ring.Length; i++)
                    {
                        for (int j = i + 1; j < ring.Length; j++)
                        {
                            if (Math.Abs(ring[i][0] - ring[j][0]) <= 1.0e-6 &&
                                Math.Abs(ring[i][1] - ring[j][1]) <= 1.0e-6)
                            {
                                throw new InvalidOperationException(
                                    "The studio rejects any ring with two " +
                                    "points within 1e-6 of each other IN " +
                                    "PLAN, compared per axis over the " +
                                    "whole ring, and it rejects the WHOLE " +
                                    "sidecar on the first offender " +
                                    $"(check 12.6(g)); the {fixture.label} " +
                                    $"has one at course {cell.Course}.");
                            }
                        }
                    }
                }
            }
        }
    }
```

2. [ ] Wire it into `Run` after the `ValidateSkinPieceSize` block, with a PASS line naming the guard
   firing on the barrel, nothing dropped, and no surviving outline anywhere holding two points the
   studio would reject.

3. [ ] Build and run the harness. It must fail: the record's `DegenerateCentroidsSkipped` is still 0.

4. [ ] Add the guard to `PlanInteriorPoint`, replacing SkinPatterns.cs:1445-1479:

```csharp
    public static double[]? PlanInteriorPoint(
        IReadOnlyList<double[]> outline) =>
        PlanInteriorPoint(outline, out int _);

    /// <summary>
    /// ... (the shipped comment stands, and this is added to it.)
    ///
    /// RULE 6.8. Before PlanContains is called on a candidate centroid, the
    /// candidate triangle's PLAN AREA is computed by the centred signed
    /// shoelace of rule 11.2 and the triangle is SKIPPED where the absolute
    /// area is at or below 1e-12 square metres. Skipping a triangle is free,
    /// because SplitPolygonInOrder yields them one at a time and the method
    /// already walks on to the next one; what is not free is accepting a
    /// point whose containment answer is arbitrary, because
    /// PlansOverlapWithInteriors then decides an overlap on it and a good
    /// cell is dropped where two courses touch. The guard goes INSIDE this
    /// one call and not beside it (rule 11.7): it is a constant-time test
    /// per candidate triangle, taken before the containment walk it would
    /// otherwise pay for, so it makes the method cheaper on a degenerate
    /// outline and unchanged on every other.
    /// </summary>
    public static double[]? PlanInteriorPoint(
        IReadOnlyList<double[]> outline,
        out int degenerateSkipped)
    {
        degenerateSkipped = 0;
        int count = outline.Count;
        if (count < 3)
            return null;
        double x = 0.0;
        double y = 0.0;
        foreach (double[] point in outline)
        {
            x += point[0];
            y += point[1];
        }
        x /= count;
        y /= count;
        if (PlanContains(x, y, outline))
            return new[] { x, y };
        var ring = new int[count];
        for (int at = 0; at < count; at++)
            ring[at] = at;
        foreach (int[] triangle in SplitPolygonInOrder(outline, ring))
        {
            double[] a = outline[triangle[0]];
            double[] b = outline[triangle[1]];
            double[] c = outline[triangle[2]];
            double mx = (a[0] + b[0] + c[0]) / 3.0;
            double my = (a[1] + b[1] + c[1]) / 3.0;
            double twice =
                (a[0] - mx) * (b[1] - my) - (b[0] - mx) * (a[1] - my) +
                (b[0] - mx) * (c[1] - my) - (c[0] - mx) * (b[1] - my) +
                (c[0] - mx) * (a[1] - my) - (a[0] - mx) * (c[1] - my);
            if (Math.Abs(twice / 2.0) <= 1.0e-12)
            {
                degenerateSkipped++;
                continue;
            }
            if (PlanContains(mx, my, outline))
                return new[] { mx, my };
        }
        return null;
    }
```

5. [ ] Count the skips through the filter. In `KeepValidPlans`, add
   `out int degenerateCentroidsSkipped` as a third out parameter, initialise it to 0, replace
   `double[]? inside = PlanInteriorPoint(cell.Outline);` with

```csharp
            double[]? inside = PlanInteriorPoint(
                cell.Outline, out int skippedHere);
            degenerateCentroidsSkipped += skippedHere;
```

   and pass the count through both engines into `DegenerateCentroidsSkipped`.

6. [ ] Raise `Dedupe` to the studio's own test, replacing SkinPatterns.cs:1692-1711:

```csharp
    /// <summary>
    /// Drop a closing repeat and every duplicate the STUDIO would reject, so
    /// an outline is a clean open ring the component closes itself.
    ///
    /// Rule 3.5.4. The studio's import rule is stricter than the plugin's
    /// filter and the gap becomes likelier under this wave's patterns. The
    /// raised test is a PLAN test in the STUDIO'S PER-AXIS FORM, not a
    /// three-dimensional distance: raising a three-dimensional test to 1e-6
    /// does NOT close the gap, because two outline points 1e-7 apart in plan
    /// and 1e-3 apart in z pass a three-dimensional 1e-6 test comfortably
    /// and still fail the studio, which is the exact case a cell spanning a
    /// steep band produces. And it runs over the WHOLE RING and not only
    /// over consecutive points, again as the studio's does.
    /// </summary>
    private static List<double[]> Dedupe(List<double[]> outline)
    {
        var cleaned = new List<double[]>();
        foreach (double[] point in outline)
        {
            if (cleaned.Count == 0 ||
                Distance(cleaned[^1], point) > 1.0e-9)
            {
                cleaned.Add(point);
            }
        }
        while (cleaned.Count > 1 &&
               Distance(cleaned[0], cleaned[^1]) <= 1.0e-9)
        {
            cleaned.RemoveAt(cleaned.Count - 1);
        }
        for (int i = 0; i < cleaned.Count; i++)
        {
            for (int j = cleaned.Count - 1; j > i; j--)
            {
                if (Math.Abs(cleaned[i][0] - cleaned[j][0]) <= 1.0e-6 &&
                    Math.Abs(cleaned[i][1] - cleaned[j][1]) <= 1.0e-6)
                {
                    cleaned.RemoveAt(j);
                }
            }
        }
        return cleaned;
    }
```

7. [ ] Add the studio's vertex-on-edge test to the degenerate branch of `KeepValidPlans` at
   SkinPatterns.cs:1631:

```csharp
            if (cell.Outline.Count < 3 ||
                PlanSelfCrosses(cell.Outline) ||
                PlanVertexOnEdge(cell.Outline))
```

   with, beside `PlanSelfCrosses`:

```csharp
    /// <summary>The studio's second ring test (rule 3.5.4(d)): does a vertex
    /// lie STRICTLY on a non-adjacent edge of its own ring? Adding it makes
    /// the filter drop MORE cells and never fewer, so it cannot hide a
    /// defect, and every fixture asserting zero drops must still assert zero
    /// after it (rule 11.11(a)).</summary>
    public static bool PlanVertexOnEdge(IReadOnlyList<double[]> outline)
    {
        int count = outline.Count;
        for (int at = 0; at < count; at++)
        {
            double[] point = outline[at];
            for (int edge = 0; edge < count; edge++)
            {
                int next = (edge + 1) % count;
                if (at == edge || at == next)
                    continue;
                double[] from = outline[edge];
                double[] to = outline[next];
                if (Math.Abs(PlanSide(from, to, point)) > 1.0e-12)
                    continue;
                double dx = to[0] - from[0];
                double dy = to[1] - from[1];
                double lengthSquared = dx * dx + dy * dy;
                if (!(lengthSquared > 1.0e-18))
                    continue;
                double t =
                    ((point[0] - from[0]) * dx +
                     (point[1] - from[1]) * dy) / lengthSquared;
                if (t > 1.0e-9 && t < 1.0 - 1.0e-9)
                    return true;
            }
        }
        return false;
    }
```

8. [ ] Build and run the harness. Every fixture that asserted zero drops must still assert zero. If
   one does not, that is a genuine finding and not a pin to move: the vertex-on-edge test only drops
   more, so a new drop is a cell the studio would have rejected.

9. [ ] Scan for clash files and commit.

```powershell
git add "plugin/native_v02/Components/SkinPatterns.cs" "tests/native_smoke/Program.cs"
git commit -m "feat(skin): the zero-area centroid guard and the studio's own ring tests"
```

### Task 22: the cap that is too big becomes a rosette

**Files:**
- Modify: plugin/native_v02/Components/SkinPatterns.cs, `Courses` (a cap-planning pass before the
  tiling loop) and the cap emission Task 18 added
- Test: tests/native_smoke/Program.cs, new `ValidateSkinCapSplit` plus its entry in `Run`

**Interfaces:**
- Consumes: `CapQualifies` and `FacesOnBoundary` from Task 18, `ResolveBands` and `AddLevel` from Task
  17, `MergeShortPieces`' threshold arithmetic from Task 20, `Trace` and `TraceAll`.
- Produces: `private sealed record SkinCapPlan(int ComponentAt, double Girth, int Wedges, double
  InnerLevel, double RingMid, bool Oversized)`; the record's `CapWedgeCounts` and `CapsOversized`.

Param ruled on 2026-09-01: above the maximum piece size the cap becomes a ring of wedge pieces around
a smaller centre disc, the wedge count chosen so each wedge falls under the maximum, and ONE threshold
governs both ends of the size question. So the maximum is not a new number and gets no port of its
own: it is the Min Piece port read from the other end, `Mx = S / MP`, which is 3 S at the default MP
of 1/3 and 2 S at the cap of rule 6.4.

1. [ ] Add the check:

```csharp
    /// <summary>
    /// The split cap (section 2.6), checks 12.2(f), 12.2(g) and 12.6(h).
    /// </summary>
    private static void ValidateSkinCapSplit(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        Type edgeType = RequireComponentType(plugin, "SkinNetEdge");
        MethodInfo courses = RequirePublicStatic(patterns, "Courses");
        var noForces = Array.Empty<(int, int, double)>();
        (double[][] vertices, int[][] faces, int[] rim) = SkinHemisphereNet();
        object net = SkinNetWith(
            netType, edgeType, vertices, faces, rim, noForces);

        // 12.2(f). At CH 1.2 the topmost boundary sits low enough on the
        // hemisphere that the cap's girth G exceeds Mx = S / MP = 1.8 m at
        // S 0.6 and MP 1/3.
        object split = courses.Invoke(
            null, new object[] { net, 0.6, 1.2, 1.0 / 3.0 })!;
        var cells = SkinCells(split);
        int courseCount = Reading<int>(split, "CourseCount");
        var capCells = cells.Where(cell => cell.Cap).ToArray();
        IList wedgeCounts = (IList)split.GetType()
            .GetProperty("CapWedgeCounts")!.GetValue(split)!;
        IList girths = (IList)split.GetType()
            .GetProperty("CapGirths")!.GetValue(split)!;
        int wedges = (int)wedgeCounts[0]!;
        double maximum = 0.6 / (1.0 / 3.0);
        if (wedges < 2)
        {
            throw new InvalidOperationException(
                "A cap whose girth exceeds Mx = S / MP is SPLIT into " +
                "W = max(2, ceil(G / Mx)) wedges about a smaller centre " +
                $"disc (rules 2.6.1 and 2.6.2); got {wedges} wedges.");
        }
        if (capCells.Length != wedges + 1)
        {
            throw new InvalidOperationException(
                "A split cap is W + 1 cells, the ring's wedges and the " +
                $"centre disc, all carrying the Cap flag; got " +
                $"{capCells.Length} against {wedges + 1}.");
        }
        foreach (var cell in capCells)
        {
            if (cell.Course != courseCount - 1)
            {
                throw new InvalidOperationException(
                    "All W + 1 pieces sit in branch n - 1, the course the " +
                    "cap already had (rule 2.6.5): a rosette is laid in " +
                    "ONE stage, and a split that invented a course would " +
                    "silently multiply his analysis stages.");
            }
            double span = cell.U1 - cell.U0;
            if (span > maximum + 1.0e-9)
            {
                throw new InvalidOperationException(
                    $"Every piece of a split cap is at or under Mx = " +
                    $"{maximum} m; one spans {span} m.");
            }
        }
        double disc = (double)girths[0]!;
        if (disc > maximum + 1.0e-9)
        {
            throw new InvalidOperationException(
                "The centre disc's girth is at or under Mx, which is what " +
                "rule 2.6.3's bracket invariant guarantees rather than the " +
                $"shape of the surface; got {disc}.");
        }
        var inBranch = cells
            .Where(cell => cell.Course == courseCount - 1)
            .ToArray();
        if (!inBranch[0].Cap || Math.Abs(
                (inBranch[0].U0 + inBranch[0].U1) / 2.0) > 1.0e-9)
        {
            throw new InvalidOperationException(
                "The disc's mid-span is 0, so it is emitted FIRST and " +
                "WINS any overlap against its own wedges under the " +
                "first-emitted-wins filter (rule 2.6.5); where W is odd the " +
                "middle wedge's mid-span is 0 as well and the tie is broken " +
                "in the disc's favour, since the keystone is the piece " +
                "least worth dropping.");
        }
        // The piece-length statistics contain NONE of the W + 1 spans, which
        // pins the amended rule 2.3.2a: a ring of wedges left in the list
        // would carry check 12.3(d)'s ratio past its bar on any dome by
        // itself.
        string diagnostics = Reading<string>(split, "Diagnostics");
        double longest = cells
            .Where(cell => !cell.Cap)
            .Max(cell => cell.U1 - cell.U0);
        if (!diagnostics.Contains(
                $"max {longest.ToString("F3", System.Globalization.CultureInfo.InvariantCulture)} m",
                StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "The piece-length statistics exclude every Cap cell, the " +
                "wedges of a split cap included (rule 2.3.2a); the " +
                $"diagnostics report a maximum other than {longest}.");
        }

        // 12.6(h): ONE PORT, BOTH ENDS. A smaller MP gives a LARGER maximum
        // and FEWER wedges, and MP at the cap of 0.5 gives the most. That is
        // the direct measurement that the maximum is the same number read
        // from the other end and not a second constant hidden in the cap
        // code.
        int WedgesAt(double minPiece)
        {
            object built = courses.Invoke(
                null, new object[] { net, 0.6, 1.2, minPiece })!;
            IList counts = (IList)built.GetType()
                .GetProperty("CapWedgeCounts")!.GetValue(built)!;
            return counts.Count == 0 ? 0 : (int)counts[0]!;
        }
        if (!(WedgesAt(0.5) >= WedgesAt(1.0 / 3.0)) ||
            !(WedgesAt(1.0 / 3.0) >= WedgesAt(0.2)))
        {
            throw new InvalidOperationException(
                "The wedge count moves as ceil(G / (S / MP)) does: a " +
                "smaller MP gives a larger maximum and fewer wedges, and " +
                "MP at the cap of 0.5 gives the most (check 12.6(h)); got " +
                $"{WedgesAt(0.5)}, {WedgesAt(1.0 / 3.0)}, {WedgesAt(0.2)}.");
        }
        if (WedgesAt(0.0) != 0)
        {
            throw new InvalidOperationException(
                "At MP = 0 the minimum is 0 and Mx is unbounded, so " +
                "merging and splitting go off TOGETHER, which is the only " +
                "coherent reading of a single threshold turned off " +
                "(rule 2.6.1).");
        }

        // 12.2(g): THE BASE CASE, on the elliptical dome and at the default
        // MP. A dome whose plan is not a circle has a cut locus that is a
        // SEGMENT rather than a point, so the girth at the top cut is
        // bounded below by roughly twice the segment's length however fine
        // CH is made, and rule 2.6.3 finds no qualifying inner level.
        (double[][] ellipseVertices, int[][] ellipseFaces, int[] ellipseRim) =
            SkinEllipticalDomeNet();
        object ellipse = SkinNetWith(
            netType, edgeType, ellipseVertices, ellipseFaces, ellipseRim,
            noForces);
        object ellipseBuilt = courses.Invoke(
            null, new object[] { ellipse, 0.6, 0.35, 1.0 / 3.0 })!;
        var ellipseCells = SkinCells(ellipseBuilt);
        if (Reading<int>(ellipseBuilt, "CapsOversized") != 1 ||
            ellipseCells.Count(cell => cell.Cap) != 1)
        {
            throw new InvalidOperationException(
                "Where no qualifying inner level exists the cap is emitted " +
                "WHOLE and OVERSIZED and not refused, because a refusal at " +
                "the crown is a hole at the crown (rule 2.6.6); got " +
                $"{Reading<int>(ellipseBuilt, "CapsOversized")} oversized " +
                $"and {ellipseCells.Count(cell => cell.Cap)} caps.");
        }
        Console.WriteLine(
            "      Skin oversized cap (check 12.2(g)): elliptical dome " +
            $"girth {((IList)ellipseBuilt.GetType().GetProperty("CapGirths")!.GetValue(ellipseBuilt)!)[0]} m " +
            $"against a maximum of {maximum} m.");
    }
```

2. [ ] Wire it into `Run` after the `ValidateSkinDegeneracyGuards` block, with a PASS line naming the
   rosette, the branch count that does not move, the disc first in its branch, the wedge count moving
   with MP alone, and the elliptical dome's oversized cap emitted whole with its girth printed.

3. [ ] Build and run the harness. It must fail: `CapWedgeCounts` is empty.

4. [ ] Add the cap plan and its bisection to SkinPatterns, beside `CapQualifies`:

```csharp
    /// <summary>What a qualifying cap becomes: whole, or a ring of W wedges
    /// about a centre disc whose inner boundary is the traced level curve at
    /// InnerLevel and whose ring's own mid is RingMid, or whole and
    /// OVERSIZED where rule 2.6.6's base case fires.</summary>
    private sealed record SkinCapPlan(
        int ComponentAt,
        double Girth,
        int Wedges,
        double InnerLevel,
        double RingMid,
        bool Oversized);

    /// <summary>
    /// Rule 2.6.3. The inner boundary is a TRACED LEVEL CURVE, like every
    /// other boundary in this engine, found by BISECTION on [level, top]
    /// keeping a bracket whose UPPER end always satisfies the test.
    ///
    /// hi starts at the top cut. Where the curve inside c at the top cut has
    /// girth ABOVE Mx, no level qualifies at all and the base case fires
    /// immediately. Otherwise lo starts at the cap's own level and each step
    /// traces the midpoint: hi becomes m where the component of level m
    /// lying inside c has girth at or under Mx, and lo becomes m where it
    /// does not. Where MORE THAN ONE component of level m lies inside c the
    /// crown holds two summits above m and the base case fires. SIX steps,
    /// the depth of rule 8.2.3 and for the same reason.
    ///
    /// The bracket invariant and not the shape of the surface is what
    /// guarantees the disc is under the maximum. Girth need NOT fall
    /// monotonically as the level rises, because a wiggly curve inside a
    /// smooth one can be longer than it, so this is a search for a large
    /// ALLOWED disc and not for a crossing, and taking hi at the end is
    /// correct whatever the girth does in between.
    /// </summary>
    private static double InnerCapLevel(
        SkinNet net,
        SkinLevelCurve outer,
        double level,
        double top,
        double maximum)
    {
        double? GirthInside(double at)
        {
            List<SkinLevelCurve> curves = Trace(net, at);
            double? only = null;
            foreach (SkinLevelCurve curve in curves)
            {
                if (curve.Points.Count == 0)
                    continue;
                if (!PlanContains(
                        curve.Points[0][0], curve.Points[0][1],
                        outer.Points))
                {
                    continue;
                }
                if (only is not null)
                    return null;
                only = curve.Length;
            }
            return only;
        }
        double? atTop = GirthInside(top);
        if (atTop is null || atTop > maximum + 1.0e-9)
            return double.NaN;
        double lo = level;
        double hi = top;
        for (int step = 0; step < 6; step++)
        {
            double middle = (lo + hi) / 2.0;
            double? girth = GirthInside(middle);
            if (girth is null)
                return double.NaN;
            if (girth <= maximum + 1.0e-9)
                hi = middle;
            else
                lo = middle;
        }
        return hi;
    }
```

5. [ ] Plan the caps before the tiling loop. In `Courses`, after `ResolveBands` and before the level
   index is built, add:

```csharp
        // THE CAP PASS. Both new levels enter the ONE ascending list and the
        // whole list is traced again (rule 2.6.4(c)): the ring needs its own
        // MID at (L_top + Li) / 2 as well as Li itself, so a split cap costs
        // two levels beyond the ones its bisection has already spent, and
        // inserting them re-propagates the seams above them exactly as rule
        // 8.2.9 says a band split does.
        var capPlans = new List<SkinCapPlan>();
        var capRefusals = new List<string>();
        int capsOversized = 0;
        double maximumPiece = clampedMinPiece > 0.0
            ? size / clampedMinPiece
            : double.PositiveInfinity;
        SkinBandInterval? top = resolved.Tileable
            .FirstOrDefault(band => band.Course == bands - 1);
        if (top is not null)
        {
            var workingLevels = new List<double>(resolved.Levels);
            IReadOnlyList<SkinLevelCurve> topCurves =
                resolved.Traced[workingLevels.IndexOf(top.Low)];
            bool[] onBoundary = FacesOnBoundary(net);
            bool inserted = false;
            for (int at = 0; at < topCurves.Count; at++)
            {
                if (!CapQualifies(
                        net, top.Low, at, topCurves, onBoundary,
                        out string refusedBy))
                {
                    if (refusedBy.Length > 0)
                        capRefusals.Add(refusedBy);
                    continue;
                }
                double girth = topCurves[at].Length;
                if (!(girth > maximumPiece + 1.0e-9))
                {
                    capPlans.Add(new SkinCapPlan(
                        at, girth, 0, double.NaN, double.NaN, false));
                    continue;
                }
                double inner = InnerCapLevel(
                    net, topCurves[at], top.Low, top.High, maximumPiece);
                if (double.IsNaN(inner))
                {
                    capsOversized++;
                    capPlans.Add(new SkinCapPlan(
                        at, girth, 0, double.NaN, double.NaN, true));
                    continue;
                }
                // W is the FEWEST wedges that put every one of them under
                // the maximum, and not the pattern's own pitch: a keystone
                // region is one stone where it can be one and as few stones
                // as it can be where it cannot.
                int wedges = Math.Max(
                    2, (int)Math.Ceiling(girth / maximumPiece - 1.0e-9));
                double ringMid = AddLevel(
                    workingLevels, (top.Low + inner) / 2.0);
                inner = AddLevel(workingLevels, inner);
                inserted = true;
                capPlans.Add(new SkinCapPlan(
                    at, girth, wedges, inner, ringMid, false));
            }
            if (inserted)
            {
                workingLevels.Sort();
                resolved = resolved with
                {
                    Levels = workingLevels,
                    Traced = TraceAll(net, workingLevels)
                };
            }
        }
```

   `SkinBandResolution` must be a record with settable-by-`with` members, which it is.

6. [ ] Emit the ring and the disc. In the cap block Task 18 added, replace the whole-cap emission with
   a branch on the plan:

```csharp
                SkinCapPlan? plan = topBand
                    ? capPlans.FirstOrDefault(
                        item => item.ComponentAt == component)
                    : null;
                if (plan is not null)
                {
                    SkinLevelCurve outer = lowers[lowerAt];
                    if (plan.Wedges == 0)
                    {
                        // Whole, and oversized where rule 2.6.6 fired.
                        var loop = Dedupe(new List<double[]>(outer.Points));
                        if (loop.Count >= 3)
                        {
                            capGirths.Add(outer.Length);
                            capWedges.Add(0);
                            keyed.Add((
                                band.Course, component, 0.0,
                                new SkinCell(
                                    band.Course, loop, false,
                                    -outer.Length / 2.0,
                                    outer.Length / 2.0, true)));
                        }
                        continue;
                    }
                    // THE RING is the band [L_top, Li] tiled by the band
                    // construction with the piece count FORCED to W and the
                    // spans equal, taken about the outer curve's own seam so
                    // that rule 7.1's seam-outward order applies to them
                    // with no special case. A wedge is an ordinary BandCell
                    // and inherits every guarantee and every defect that
                    // construction carries, the proportional arc mapping of
                    // rule 1.8.1 included, which rule 1.8.4 defers out of
                    // this round.
                    SkinLevelCurve ringMidCurve =
                        resolved.Traced[levelIndex[plan.RingMid]]
                            [MatchBelowIndex(outer, plan.RingMid, resolved,
                                levelIndex)];
                    SkinLevelCurve innerCurve =
                        resolved.Traced[levelIndex[plan.InnerLevel]]
                            [MatchBelowIndex(outer, plan.InnerLevel, resolved,
                                levelIndex)];
                    double girth = plan.Girth;
                    for (int w = 0; w < plan.Wedges; w++)
                    {
                        double u0 = -girth / 2.0 + w * girth / plan.Wedges;
                        double u1 = u0 + girth / plan.Wedges;
                        SkinCell wedge = BandCell(
                            band.Course, outer, ringMidCurve, innerCurve,
                            u0, u1, false);
                        if (wedge.Outline.Count < 3)
                            continue;
                        keyed.Add((
                            band.Course, component, u0,
                            wedge with { Cap = true }));
                    }
                    var disc = Dedupe(
                        new List<double[]>(innerCurve.Points));
                    if (disc.Count >= 3)
                    {
                        keyed.Add((
                            band.Course, component, 0.0,
                            new SkinCell(
                                band.Course, disc, false,
                                -innerCurve.Length / 2.0,
                                innerCurve.Length / 2.0, true)));
                    }
                    capGirths.Add(innerCurve.Length);
                    capWedges.Add(plan.Wedges);
                    continue;
                }
```

   with `var capWedges = new List<int>();` beside `capGirths`, both passed to the return as
   `CapGirths` and `CapWedgeCounts`, `capsOversized` passed as `CapsOversized`, and a small helper
   beside `MatchBelow`:

```csharp
    /// <summary>Which component of a traced level is the one lying under a
    /// given curve, by the engine's own MatchBelow, so a cap's ring and disc
    /// are taken from the same piece of surface the cap sits on.</summary>
    private static int MatchBelowIndex(
        SkinLevelCurve curve,
        double level,
        SkinBandResolution resolved,
        IReadOnlyDictionary<double, int> levelIndex)
    {
        IReadOnlyList<SkinLevelCurve> candidates =
            resolved.Traced[levelIndex[level]];
        int matched = MatchBelow(curve, candidates);
        return matched < 0 ? 0 : matched;
    }
```

7. [ ] Test the ring like a band, which is rule 2.6.4(d). Immediately before emitting the wedges, add:

```csharp
                    if (!Corresponds(
                            new[] { ringMidCurve }, new[] { outer }) ||
                        !Corresponds(
                            new[] { ringMidCurve }, new[] { innerCurve }))
                    {
                        // The ring is a BAND and is tested like one. Where
                        // it FAILS the split is abandoned and rule 2.6.6's
                        // base case fires. The ring is NOT bisected
                        // further: section 8's bisection exists to find a
                        // level at which the topology is simple, and here
                        // the level is already being chosen, by rule 2.6.3.
                        capsOversized++;
                        var whole = Dedupe(new List<double[]>(outer.Points));
                        if (whole.Count >= 3)
                        {
                            capGirths.Add(outer.Length);
                            capWedges.Add(0);
                            keyed.Add((
                                band.Course, component, 0.0,
                                new SkinCell(
                                    band.Course, whole, false,
                                    -outer.Length / 2.0,
                                    outer.Length / 2.0, true)));
                        }
                        continue;
                    }
```

8. [ ] Raise the Warning's own number. Add the oversized count to the cap diagnostics line built in
   Task 18:

```csharp
              (capsOversized > 0
                  ? $"; {capsOversized} emitted WHOLE and OVERSIZED above " +
                    "the maximum piece size, so a smaller CH or a larger " +
                    "Min Piece is wanted"
                  : string.Empty)
```

9. [ ] Build and run the harness. Check 12.9(c)'s cost check now counts the cap's own levels in the
   same total, which rule 2.6.4(c) requires and check 12.2(h) states: up to six from the bisection
   plus the ring's mid and its inner curve.

10. [ ] Scan for clash files and commit.

```powershell
git add "plugin/native_v02/Components/SkinPatterns.cs" "tests/native_smoke/Program.cs"
git commit -m "feat(skin): an oversized keystone becomes a rosette of wedges about a disc"
```

---

### Task 23: the honeycomb laid in each row's own normalised arc

**Files:**
- Modify: plugin/native_v02/Components/SkinPatterns.cs:2201-2446 (the whole of `Hexagonal`)
- Test: tests/native_smoke/Program.cs, `ValidateSkinHexagonal` at Program.cs:11527 is rewritten to
  checks 12.4(a) to 12.4(g)

**Interfaces:**
- Consumes: `BuildCharts`, `CurveAt`, `ChainCorresponds` from Task 17, `PointAt`, `Run`, `Dedupe`.
- Produces: the record's `FiveSidedCells`, `SevenSidedCells` and `CountChangeRows`.

The whole of section 4.2 is one move: the lattice stops being laid in ABSOLUTE arc length and is laid
in each row's OWN NORMALISED arc length, with each row taking its own count from its own length. That
removes defects 1, 3 and 4 together. Two things this task does NOT claim. It does not fix the
arc-length RATIO mapping, which is his first cause: that belongs to pattern 0's `BandCell` and rule
1.8.4 defers it. And it does not reduce to the shipped lattice on the barrel: every level cut there is
a straight strip of length 6 and the check runs at S 0.6, so n = round(6.0 / 0.9) = 7, m = 14 and the
pitch is 6 / 14 = 0.4286 m against the shipped absolute 0.45 m. Every column, every vertex and every
outline moves, on the one fixture an earlier draft named as unchanged.

1. [ ] Rewrite `ValidateSkinHexagonal`'s assertions to what rule 4.2 actually claims, keeping the
   method's name and its `Run` entry:

```csharp
        // 12.4(a): the BARREL, whose rows are all one length. The bar is NOT
        // byte identity and cannot be. What is asserted is what the rule
        // claims: every row takes the SAME centre count and the SAME pitch;
        // the pitch is within one rounding step of 0.75 S; adjacent rows'
        // centres are offset by exactly half the in-row centre spacing; the
        // interior cell's six corners sit at its own row's 2 / (3 m) and
        // 1 / (3 m); and the plan filter drops ZERO cells.
        // The pitch is MEASURED OFF THE BUILT RECORD and not computed from
        // three literals. An earlier draft wrote `double pitch = 6.0 / 14.0`
        // and compared it against `0.75 * 0.6` with a bound of
        // `0.75 * 0.6 / 14.0`: all three are constants, `generated` was never
        // read, and the check passed whatever the engine's lattice did. A
        // fixture that would pass whether or not the rule held is not a
        // fixture.
        var barrelCells = SkinCells(generated);
        var byRow = barrelCells
            .GroupBy(cell => cell.Course)
            .OrderBy(row => row.Key)
            .ToArray();
        if (byRow.Length < 2)
        {
            throw new InvalidOperationException(
                "The barrel builds several honeycomb rows, or 12.4(a) has " +
                $"nothing to compare between rows; it built {byRow.Length}.");
        }
        int[] perRow = byRow.Select(row => row.Count()).ToArray();
        if (perRow.Distinct().Count() != 1)
        {
            throw new InvalidOperationException(
                "The barrel's rows are ALL ONE LENGTH, so every row takes " +
                "the SAME centre count and the same column count (rule " +
                $"4.2.2); the rows hold [{string.Join(",", perRow)}].");
        }
        double[] rowPitches = byRow
            .Select(row =>
            {
                double[] mids = row
                    .Select(cell => (cell.U0 + cell.U1) / 2.0)
                    .OrderBy(value => value)
                    .ToArray();
                return (mids[^1] - mids[0]) / Math.Max(mids.Length - 1, 1);
            })
            .ToArray();
        if (rowPitches.Max() - rowPitches.Min() > 1.0e-9)
        {
            throw new InvalidOperationException(
                "Every row takes the SAME pitch on a strip whose rows are " +
                $"all one length; they read {rowPitches.Min():F6} to " +
                $"{rowPitches.Max():F6}.");
        }
        double pitch = rowPitches[0];
        // Within ONE ROUNDING STEP of 0.75 S, which is the claim rule 4.2.2
        // makes: the count is rounded, so the pitch cannot be exact, and the
        // step is the pitch's own share of one column.
        if (Math.Abs(pitch - (0.75 * 0.6)) > pitch + 1.0e-9)
        {
            throw new InvalidOperationException(
                "Row k takes its own CENTRE count n = max(1, round(L / " +
                "(1.5 S))) from its own arc length and its COLUMN count is " +
                "m = 2 n, so the barrel's 6.0 m strip at S 0.6 gives n = 7, " +
                "m = 14 and a pitch within one rounding step of a target of " +
                $"0.75 S = 0.45 m; the engine laid it at {pitch:F6} m.");
        }
        RequireNothingDropped(generated, "barrel honeycomb");

        // 12.4(a) again: THE 76 CELLS AND 36 CLIPPED ARE RE-MEASURED AND
        // RE-PINNED AS NEW NUMBERS, with the new numbers written into the
        // check's own message beside the shipped ones. That is the discipline
        // 12.4(g) asks for elsewhere and it is what replaces the two pins at
        // Program.cs:11548-11554 that this rework invalidates: rule 4.2.2
        // moves every column and rule 4.2.5 removes the vertex clamp the 36
        // was measuring, so leaving them out would retire two measurements
        // and put nothing in the record.
        //
        // MEASURE FIRST, THEN WRITE THE TWO NUMBERS IN HERE. Until they are
        // measured these two constants are the shipped ones and the check is
        // red on purpose.
        const int barrelCellsPinned = 76;      // re-measure and replace
        const int barrelClippedPinned = 36;    // re-measure and replace
        int barrelClipped = barrelCells.Count(cell => cell.Clipped);
        Console.WriteLine(
            "      Skin honeycomb barrel (check 12.4(a), S 0.6 CH 0.35): " +
            $"{barrelCells.Length} cells and {barrelClipped} clipped, " +
            "against the shipped 76 and 36. Rule 4.2.2 laid the lattice in " +
            "each row's own normalised arc so every column moved, and rule " +
            "4.2.5 removed the vertex clamp the 36 was measuring.");
        if (barrelCells.Length != barrelCellsPinned ||
            barrelClipped != barrelClippedPinned)
        {
            throw new InvalidOperationException(
                $"The barrel honeycomb builds {barrelCellsPinned} cells of " +
                $"which {barrelClippedPinned} are clipped; it built " +
                $"{barrelCells.Length} and {barrelClipped}. These are " +
                "RE-MEASURED numbers replacing the shipped 76 and 36, and a " +
                "later change to either must re-measure and say why in this " +
                "message rather than relax the pin.");
        }

        // 12.4(f): THE SCAR IS GONE. On a CLOSED row the arc gap between the
        // last column and the first, measured round the wrap, equals every
        // other column gap to within 1e-9. That is the direct measurement of
        // defect 3, the u domain cut at plus and minus half rather than
        // wrapped, whose leftover differed row by row.
        (double[][] domeVertices, int[][] domeFaces) = SkinDomeNet();
        object domeNet = Activator.CreateInstance(
            netType, new object[] { domeVertices, domeFaces })!;
        object domeBuilt = hexagonal.Invoke(
            null, new object[] { domeNet, 0.6, 0.35 })!;
        var domeCells = SkinCells(domeBuilt);
        foreach (IGrouping<int, (int Course, double[][] Outline,
                     bool Clipped, double U0, double U1, bool Cap)> course in
                 domeCells.GroupBy(cell => cell.Course))
        {
            double[] mids = course
                .Select(cell => (cell.U0 + cell.U1) / 2.0)
                .OrderBy(value => value)
                .ToArray();
            if (mids.Length < 3)
                continue;
            var gaps = new List<double>();
            for (int at = 1; at < mids.Length; at++)
                gaps.Add(mids[at] - mids[at - 1]);
            if (gaps.Max() - gaps.Min() > 1.0e-6)
            {
                throw new InvalidOperationException(
                    "A closed row's columns sit at normalised arc j / m " +
                    "for j = 0 to m - 1, so the last column closes onto the " +
                    "first EXACTLY and there is no ragged leftover at the " +
                    "meridian opposite the seam (rule 4.2.3); course " +
                    $"{course.Key} has gaps from {gaps.Min()} to " +
                    $"{gaps.Max()}.");
            }
        }

        // 12.4(b): no cell has a collapsed edge, meaning no two outline
        // points within 1e-6 of each other IN PLAN after Dedupe, per axis in
        // the studio's own form, against the 26-of-161 port measurement of
        // section 4.1 defect 2. Taken by ValidateSkinDegeneracyGuards over
        // every fixture, so it is not repeated here.

        // 12.4(c): no cell contains a whole row, which pins the crown
        // lollipop out of existence.
        foreach (var cell in domeCells)
        {
            if (cell.Outline.Length > 12 + 2 * 8)
            {
                throw new InvalidOperationException(
                    "At the crown the shipped top row's whole curve was " +
                    "shorter than the span a hexagon asked for, so Run's " +
                    "closed branch collected every trace vertex of the ring " +
                    "and the cell came back as a short lower arc plus the " +
                    "ENTIRE crown circle, 104 corners and self-crossing in " +
                    "plan. Rule 4.2.1 stops the rows at the surface; got a " +
                    $"cell of {cell.Outline.Length} corners.");
            }
        }

        // 12.4(d) and 12.4(e): the odd cells exist, sit ONLY where the
        // CENTRE count changes, and are placed at the meridian opposite the
        // seam on a closed row or at the ends on an open strip. BOTH
        // DIRECTIONS of rule 4.3.1 are asserted, and 4.3.2 is asserted at
        // all: a block that only asked "some odd cells and some change rows
        // exist" would go green against an engine that scattered pentagons
        // anywhere it liked, which is the one failure this pair exists for.
        //
        // CORNERS HERE MEANS SETOUT CORNERS and not the trace vertices the
        // two horizontal edges carry, so the count is taken off the record's
        // own FiveSidedCells and SevenSidedCells and, per cell, off the
        // engine's own setout-corner list rather than off Outline.Length,
        // which counts the mesh.
        int five = Reading<int>(domeBuilt, "FiveSidedCells");
        int seven = Reading<int>(domeBuilt, "SevenSidedCells");
        IList changeRows = (IList)domeBuilt.GetType()
            .GetProperty("CountChangeRows")!.GetValue(domeBuilt)!;
        var change = changeRows.Cast<int>().ToHashSet();
        if (five + seven == 0 || change.Count == 0)
        {
            throw new InvalidOperationException(
                "A surface with Gaussian curvature cannot be tiled by " +
                "hexagons alone: positive curvature requires pentagons and " +
                "negative curvature heptagons, which is why a sphere needs " +
                "exactly twelve pentagons. On a dome the row counts change " +
                "and the odd cells follow, and they are NOT a defect and " +
                "must not be filtered (rule 4.3).");
        }
        // The dome and the two-oculus fixture, both, as 12.4(d) names them.
        (double[][] oculusForOdd, int[][] oculusFacesForOdd, int[] _unusedRim) =
            SkinTwoOculusNet();
        object oculusForOddNet = Activator.CreateInstance(
            netType, new object[] { oculusForOdd, oculusFacesForOdd })!;
        object oculusOddBuilt = hexagonal.Invoke(
            null, new object[] { oculusForOddNet, 0.6, 0.35 })!;
        foreach ((object built, string label) fixture in new[]
                 {
                     (domeBuilt, "dome"),
                     (oculusOddBuilt, "two-oculus")
                 })
        {
            var here = SkinCells(fixture.built);
            var rows = ((IList)fixture.built.GetType()
                .GetProperty("CountChangeRows")!.GetValue(fixture.built)!)
                .Cast<int>().ToHashSet();
            int[] setout = SkinSetoutCorners(fixture.built);
            var odd = Enumerable.Range(0, here.Length)
                .Where(at => setout[at] == 5 || setout[at] == 7)
                .ToArray();
            if (odd.Length == 0)
            {
                throw new InvalidOperationException(
                    $"On the {fixture.label} the count of five- plus " +
                    "seven-cornered cells is NON-ZERO (rule 4.3.1); it is " +
                    "zero, so either the row counts never change or the odd " +
                    "cells are being filtered.");
            }
            // FORWARD: every odd cell sits at a row where the centre count
            // changes.
            foreach (int at in odd)
            {
                if (!rows.Contains(here[at].Course))
                {
                    throw new InvalidOperationException(
                        $"On the {fixture.label} an odd cell of " +
                        $"{setout[at]} setout corners sits at course " +
                        $"{here[at].Course}, which is NOT a row where the " +
                        "centre count changes. An odd cell away from a count " +
                        "change is a defect and not curvature (rule 4.3.1).");
                }
            }
            // CONVERSE: nowhere else. Stated as its own loop, because an
            // engine that scattered pentagons on every row would satisfy
            // neither and an engine that put none anywhere would satisfy the
            // forward direction vacuously.
            foreach (int at in Enumerable.Range(0, here.Length))
            {
                if (setout[at] != 6 && setout[at] != 5 && setout[at] != 7 &&
                    !here[at].Cap && !here[at].Clipped)
                {
                    throw new InvalidOperationException(
                        $"On the {fixture.label} an unclipped interior cell " +
                        $"has {setout[at]} setout corners; rule 4.3 allows " +
                        "six, and five or seven only at a count change.");
                }
            }
            foreach (int course in here.Select(cell => cell.Course).Distinct())
            {
                bool oddHere = odd.Any(at => here[at].Course == course);
                if (oddHere != rows.Contains(course))
                {
                    throw new InvalidOperationException(
                        $"On the {fixture.label} course {course} " +
                        (oddHere ? "carries an odd cell but is not a count-change row"
                                 : "is a count-change row but carries no odd cell") +
                        ". Rule 4.3.1 holds in BOTH directions, and this is " +
                        "the direction an engine that scattered pentagons " +
                        "would fail.");
                }
            }
            // 12.4(e), PLACEMENT: every odd cell's normalised position is
            // within ONE COLUMN of t = 0.5 on a closed row, which is the
            // meridian opposite the seam, or at an END on an open strip.
            // That pins rule 4.3.2.
            foreach (int at in odd)
            {
                var row = here.Where(cell => cell.Course == here[at].Course)
                    .OrderBy(cell => (cell.U0 + cell.U1) / 2.0)
                    .ToArray();
                double low = row.Min(cell => cell.U0);
                double high = row.Max(cell => cell.U1);
                double column = (high - low) / Math.Max(row.Length, 1);
                double t = ((here[at].U0 + here[at].U1) / 2.0 - low) /
                    Math.Max(high - low, 1.0e-12);
                bool closed = SkinRowIsClosed(fixture.built, here[at].Course);
                if (closed)
                {
                    double slack = column / Math.Max(high - low, 1.0e-12);
                    if (Math.Abs(t - 0.5) > slack + 1.0e-9)
                    {
                        throw new InvalidOperationException(
                            $"On the {fixture.label} a closed row's odd cell " +
                            $"sits at normalised {t:F4}, further than one " +
                            "column from the meridian opposite the seam at " +
                            "0.5 (rule 4.3.2). Putting it anywhere else " +
                            "walks the defect round the dome.");
                    }
                }
                else if (t > column / Math.Max(high - low, 1.0e-12) + 1.0e-9 &&
                         t < 1.0 - (column / Math.Max(high - low, 1.0e-12)) - 1.0e-9)
                {
                    throw new InvalidOperationException(
                        $"On the {fixture.label} an OPEN strip's odd cell " +
                        $"sits at normalised {t:F4}, which is neither end " +
                        "(rule 4.3.2). An open strip has no meridian " +
                        "opposite a seam, so the closer goes at an end.");
                }
            }
        }

        // 12.4(g): the AFTER, against the before Task 13 recorded.
        (double[][] oculusVertices, int[][] oculusFaces, int[] _) =
            SkinTwoOculusNet();
        object oculusNet = Activator.CreateInstance(
            netType, new object[] { oculusVertices, oculusFaces })!;
        object oculusBuilt = hexagonal.Invoke(
            null, new object[] { oculusNet, 0.6, 0.35 })!;
        Console.WriteLine(
            "      Skin honeycomb AFTER (check 12.4(g), S 0.6 CH 0.35): " +
            "two-oculus " +
            $"{Reading<int>(oculusBuilt, "PlanDegenerateDropped") + Reading<int>(oculusBuilt, "PlanOverlapDropped")} " +
            $"withheld of {SkinCells(oculusBuilt).Length + Reading<int>(oculusBuilt, "PlanDegenerateDropped") + Reading<int>(oculusBuilt, "PlanOverlapDropped")} " +
            "built, against the before recorded in ValidateSkinFixtures.");
```

   `SkinSetoutCorners` and `SkinRowIsClosed` are two small class-scope readers beside `SkinCells`, and
   they exist because 12.4(d) is explicit that corners means SETOUT corners and not the trace vertices
   the two horizontal edges carry: counting `Outline.Length` would count the mesh and the check would
   measure the tessellation of the net rather than the tessellation of the skin. `SkinCell` therefore
   gains `int SetoutCorners` beside `Cap`, filled by the lattice as it builds each cell, and
   `SkinPatternResult` gains `IReadOnlyList<int> ClosedRows` beside `CountChangeRows`, filled with the
   courses whose traced component closes. Both are widenings of a POSITIONAL record, so every
   construction site named in Task 17 step 7 and Task 20 step 6 gains its argument here too: `Empty`
   takes `Array.Empty<int>()`, `Courses` takes `Array.Empty<int>()` because a course pattern's rows are
   not a lattice's rows, and `Hexagonal` takes the list it built.

2. [ ] Build and run the harness. It must fail: the shipped lattice's pitch is the absolute 0.45 m and
   nothing reports `FiveSidedCells`.

3. [ ] Replace the lattice generation in `Hexagonal`, from the chart loop at SkinPatterns.cs:2258 to
   the end of the candidate loop at :2417, with the per-row construction:

```csharp
        var countChangeRows = new HashSet<int>();
        int fiveSided = 0;
        int sevenSided = 0;
        for (int chartAt = 0; chartAt < charts.Count; chartAt++)
        {
            SkinChart chart = charts[chartAt];
            int rows = chart.Curves.Count;
            if (rows < 3)
                continue;

            // COUNTS, stated in CENTRES and not in columns (rule 4.2.2). Row
            // k takes its own centre count n_k = max(1, round(L_k / (1.5 S)))
            // from its own arc length and its column count is m_k = 2 n_k,
            // so the column pitch is L_k / m_k against a target of 0.75 S.
            // The count is taken in centres because rule 4.2.4 puts a centre
            // on every other column, and on a CLOSED row that alternation
            // only closes onto itself when the column count is EVEN: round a
            // column count straight off the length and it is odd about half
            // the time, two hexagons then sit side by side at the meridian
            // and their cells overlap, which is the very defect this section
            // exists to remove arriving by a different road.
            var centres = new int[rows];
            for (int k = 0; k < rows; k++)
            {
                centres[k] = Math.Max(
                    1,
                    (int)Math.Round(chart.Curves[k].Length / (1.5 * size)));
            }
            // Rule 4.3.4: where two adjacent rows would differ by more than
            // one CENTRE the difference is spread over the intervening rows
            // one centre at a time, so no single row carries more than one
            // centre change and no cell has more than seven sides. The
            // adjustment is made in CENTRES and never in columns, because a
            // closed row's column count must stay even and an even count can
            // only change by two.
            for (int pass = 0; pass < rows; pass++)
            {
                bool moved = false;
                for (int k = 1; k < rows; k++)
                {
                    if (centres[k] > centres[k - 1] + 1)
                    {
                        centres[k] = centres[k - 1] + 1;
                        moved = true;
                    }
                    else if (centres[k] < centres[k - 1] - 1)
                    {
                        centres[k] = centres[k - 1] - 1;
                        moved = true;
                    }
                }
                if (!moved)
                    break;
            }
            for (int k = 1; k < rows; k++)
            {
                if (centres[k] != centres[k - 1])
                    countChangeRows.Add(k);
            }

            for (int k = 1; k + 1 < rows; k++)
            {
                int columns = 2 * centres[k];
                SkinLevelCurve here = chart.Curves[k];
                SkinLevelCurve below = chart.Curves[k - 1];
                SkinLevelCurve above = chart.Curves[k + 1];
                if (!ChainCorresponds(here, below) ||
                    !ChainCorresponds(above, here))
                {
                    skippedRows.Add(k);
                    continue;
                }
                int columnsBelow = 2 * centres[k - 1];
                int columnsAbove = 2 * centres[k + 1];
                for (int j = 0; j < columns; j++)
                {
                    // CENTRES (rule 4.2.4): a hexagon has its centre at
                    // (row k, column j) with j + k EVEN, so adjacent rows'
                    // centres are offset by exactly one column pitch,
                    // 1 / m_k in normalised arc, which is half the in-row
                    // centre spacing of 2 / m_k. That is the honeycomb's own
                    // offset and rule 4.2.3 applies it in this ONE place:
                    // there is no phase term in the column set, because the
                    // phase and the parity are two spellings of one rule.
                    if ((j + k) % 2 != 0)
                        continue;
                    double t = (double)j / columns;

                    // VERTICES (rule 4.2.5), as fractions of each ROW'S OWN
                    // column pitch, EACH EVALUATED ON ITS OWN ROW'S
                    // parameterisation and never on the centre row's. Two
                    // thirds and one third of a column pitch are, at a pitch
                    // of 0.75 S, exactly S / 2 and S / 4, which is the
                    // shipped flat-topped hexagon.
                    double sideLeft = t - 2.0 / (3.0 * columns);
                    double sideRight = t + 2.0 / (3.0 * columns);
                    List<double> bottom = LatticeVertices(
                        t, columnsBelow, here.Closed,
                        sideLeft, sideRight, ref fiveSided, ref sevenSided);
                    List<double> topRow = LatticeVertices(
                        t, columnsAbove, here.Closed,
                        sideLeft, sideRight, ref fiveSided, ref sevenSided);

                    var outline = new List<double[]>();
                    foreach (double at in bottom)
                        outline.Add(PointAt(below, ArcOf(below, at)));
                    outline.Add(PointAt(here, ArcOf(here, sideRight)));
                    for (int at = topRow.Count - 1; at >= 0; at--)
                        outline.Add(PointAt(above, ArcOf(above, topRow[at])));
                    outline.Add(PointAt(here, ArcOf(here, sideLeft)));
                    List<double[]> cleaned = Dedupe(outline);
                    if (cleaned.Count < 3)
                        continue;
                    bool clipped = !here.Closed &&
                        (sideLeft < 0.0 || sideRight > 1.0);
                    int course = Math.Min(
                        bands - 1, Math.Max(0, k - 1));
                    var cell = new SkinCell(
                        course, cleaned, clipped,
                        ArcOf(here, sideLeft), ArcOf(here, sideRight));
                    keyed.Add((course, chartAt, cell.U0, cell));
                }
            }
        }
```

   with the two small helpers beside `CurveAt`:

```csharp
    /// <summary>Signed arc about the seam from a NORMALISED position on a
    /// row: t in [0, 1) is normalised arc from the seam on a closed row and
    /// from the strip's start on an open one, and an open strip's seam is
    /// its arc-length midpoint, which is what makes the column set j / m
    /// symmetric about t = 0.5 and keeps the strip mirror-symmetric.</summary>
    private static double ArcOf(SkinLevelCurve curve, double t) =>
        curve.Closed
            ? t * curve.Length
            : t * curve.Length - curve.Length / 2.0;

    /// <summary>
    /// How many of a neighbouring row's columns fall within the cell's own
    /// span decides how many vertices that row contributes, and the thirds
    /// decide where they sit (rule 4.2.5's closing paragraph and rule 4.3).
    /// One column within the span is the plain honeycomb and gives two
    /// vertices at that row's own thirds; NONE gives one vertex and a
    /// five-sided cell; TWO gives three vertices and a seven-sided one.
    /// Where the extra vertex sits is this engine's own resolution, stated
    /// because the spec states the count and not the position: at the cell's
    /// own centre, so the extra corner lies on the cell's axis and the cell
    /// stays symmetric about it.
    /// </summary>
    private static List<double> LatticeVertices(
        double t,
        int columns,
        bool closed,
        double spanLeft,
        double spanRight,
        ref int fiveSided,
        ref int sevenSided)
    {
        int within = 0;
        for (int j = 0; j < columns; j++)
        {
            double at = (double)j / columns;
            if (closed)
            {
                double shifted = at - t;
                shifted -= Math.Floor(shifted + 0.5);
                at = t + shifted;
            }
            if (at > spanLeft + 1.0e-12 && at < spanRight - 1.0e-12)
                within++;
        }
        double third = 1.0 / (3.0 * columns);
        if (within <= 0)
        {
            fiveSided++;
            return new List<double> { t };
        }
        if (within >= 2)
        {
            sevenSided++;
            return new List<double> { t - third, t, t + third };
        }
        return new List<double> { t - third, t + third };
    }
```

4. [ ] Replace the row ladder at SkinPatterns.cs:2217-2232 so rows run 0 to K at k * CH with the two
   extremes pulled inside by the epsilon of rule 1.5.2, and nothing is clamped beyond the surface
   (rule 4.2.1):

```csharp
        int topRow = (int)Math.Ceiling(
            (dMax - dMin) / courseHeight - 1.0e-9);
        double RowLevel(int row) =>
            row <= 0 ? dBottom
            : row >= topRow ? dTop
            : dMin + courseHeight * row;
        List<double> levels = Enumerable
            .Range(0, topRow + 1)
            .Select(RowLevel)
            .Distinct()
            .ToList();
```

5. [ ] Pass the three new counts into the `Hexagonal` return: `fiveSided` as `FiveSidedCells`,
   `sevenSided` as `SevenSidedCells`, and `countChangeRows.OrderBy(row => row).ToList()` as
   `CountChangeRows`; and add the odd-cell line to the diagnostics, worded as rule 4.3.3 gives it:

```csharp
        string? oddLine = fiveSided + sevenSided > 0
            ? $"Odd cells: {fiveSided} five-sided, {sevenSided} seven-sided " +
              "(row counts change at rows " +
              string.Join(
                  ", ", countChangeRows.OrderBy(row => row)) + ")"
            : null;
```

6. [ ] Build and run the harness. Every honeycomb pin has moved, which rule 12.4(a) states in advance:
   re-measure the cell and clipped counts, re-pin them as new numbers, and write the new numbers into
   the check's own message. `RequireNothingDropped` must still pass on the barrel: the whole point of
   the per-row lattice is that the columns no longer shear until the cells overlap.

7. [ ] Scan for clash files and commit.

```powershell
git add "plugin/native_v02/Components/SkinPatterns.cs" "tests/native_smoke/Program.cs"
git commit -m "feat(skin): the honeycomb is laid in each row's own normalised arc"
```

### Task 24: the seam becomes exact

**Files:**
- Modify: plugin/native_v02/Components/SkinPatterns.cs:878-906 (`AssignSeams`) and a new
  `NearestArcInPlan` beside `NearestInPlan` at :1126-1142
- Test: tests/native_smoke/Program.cs, new `SkinFineDomeNet` fixture and `ValidateSkinSeamDrift` plus
  its entry in `Run`

**Interfaces:**
- Consumes: `SkinLevelCurve.Cumulative`, `PointAt`, `MatchBelow`.
- Produces: `private static double NearestArcInPlan(SkinLevelCurve curve, double[] target)`.

Defect 5 of section 4.1: the seam every u is measured from is QUANTISED to a trace vertex, both when
it is propagated from the loop below and when it is taken on the +X bearing, so it jumps from row to
row by up to half the mesh's own vertex spacing, which on a 96-a-ring dome is up to 0.098 m against a
hexagon half-width of 0.15 m. That is the SECOND of the two causes Param names as the setout
distortion, and it is the one this round answers. His FIRST cause, the arc-length ratio mapping, is
rule 1.8.1's and rule 1.8.4 defers it; Task 32 measures the residual.

Rule 4.2.6 and rule 5.4.3 need the same fix, which is why they are one job.

1. [ ] Add the fixture and the check to tests/native_smoke/Program.cs:

```csharp
    /// <summary>A circular dome at 96 a ring: 24 rings, the vertex at ring h
    /// and angle theta at (3 (1 - h) cos theta, 3 (1 - h) sin theta, 2 h),
    /// the last ring collapsed to the apex. Check 12.5(f) needs a fine
    /// closed-row fixture, and the coarse octagonal dome cannot show a drift
    /// of half a vertex spacing because half its vertex spacing is most of a
    /// hexagon.</summary>
    private static (double[][] Vertices, int[][] Faces, int[] Rim)
        SkinFineDomeNet()
    {
        const int Rings = 24;
        const int Around = 96;
        var vertices = new List<double[]>();
        for (int ring = 0; ring < Rings; ring++)
        {
            double h = (double)ring / Rings;
            for (int k = 0; k < Around; k++)
            {
                double theta = Math.PI * 2.0 * k / Around;
                vertices.Add(new[]
                {
                    3.0 * (1.0 - h) * Math.Cos(theta),
                    3.0 * (1.0 - h) * Math.Sin(theta),
                    2.0 * h
                });
            }
        }
        int apex = vertices.Count;
        vertices.Add(new[] { 0.0, 0.0, 2.0 });
        var faces = new List<int[]>();
        for (int ring = 0; ring + 1 < Rings; ring++)
        {
            for (int k = 0; k < Around; k++)
            {
                int next = (k + 1) % Around;
                faces.Add(new[]
                {
                    ring * Around + k,
                    ring * Around + next,
                    (ring + 1) * Around + next,
                    (ring + 1) * Around + k
                });
            }
        }
        for (int k = 0; k < Around; k++)
        {
            int next = (k + 1) % Around;
            faces.Add(new[]
            {
                (Rings - 1) * Around + k,
                (Rings - 1) * Around + next,
                apex
            });
        }
        var rim = new List<int>();
        for (int k = 0; k < Around; k++)
            rim.Add(k);
        return (vertices.ToArray(), faces.ToArray(), rim.ToArray());
    }

    /// <summary>
    /// Check 12.5(f). On a circular dome at 96 a ring every course's seam
    /// sits on the +X bearing, because the lowest loop's seam is taken there
    /// and every loop above propagates from the one below. Under the shipped
    /// rule the propagated seam is QUANTISED to the nearest trace vertex, so
    /// it wanders by up to half a vertex spacing, which is 0.098 m at this
    /// ring count. Measured as the seam's plan BEARING, because on a dome
    /// the rings shrink and consecutive seams differ radially by
    /// construction: the drift the defect describes is angular.
    /// </summary>
    private static void ValidateSkinSeamDrift(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        MethodInfo traceAll = RequirePublicStatic(patterns, "TraceAll");
        (double[][] vertices, int[][] faces, int[] _) = SkinFineDomeNet();
        object net = Activator.CreateInstance(
            netType, new object[] { vertices, faces })!;
        var levels = new List<double>();
        for (int k = 1; k <= 18; k++)
            levels.Add(0.1 * k);
        object traced = traceAll.Invoke(
            null, new object[] { net, levels })!;
        double worst = 0.0;
        foreach (object? level in (IList)traced)
        {
            foreach (object? item in (IList)level!)
            {
                object curve = item!;
                if (!Reading<bool>(curve, "Closed"))
                    continue;
                MethodInfo pointAt = RequirePublicStatic(patterns, "PointAt");
                double[] seam = (double[])pointAt.Invoke(
                    null, new object[] { curve, 0.0 })!;
                double angle = Math.Atan2(seam[1], seam[0]);
                worst = Math.Max(worst, Math.Abs(angle));
            }
        }
        if (worst > 1.0e-6)
        {
            throw new InvalidOperationException(
                "A closed row's seam is the point on that row NEAREST IN " +
                "PLAN to the row below's seam, found by exact projection " +
                "onto the row's segments and stored as a continuous arc " +
                "length, not by choosing the nearest sample vertex " +
                "(rule 4.2.6); on a circular dome every seam then sits on " +
                $"the +X bearing, and the worst bearing here is {worst} rad " +
                "against a vertex spacing of 2 pi / 96 = 0.065 rad.");
        }
    }
```

2. [ ] Wire it into `Run` after the honeycomb block, with a PASS line naming the exact projection and
   the bearing it holds.

3. [ ] Build and run the harness. It must fail with a bearing of order 0.03 rad, which is half the
   96-a-ring vertex spacing.

4. [ ] Add the exact projection beside `NearestInPlan`:

```csharp
    /// <summary>
    /// The ARC LENGTH at the point of this curve nearest IN PLAN to a
    /// target, by exact projection onto the curve's own segments (rule
    /// 4.2.6). NearestInPlan returns a sample INDEX and quantises the answer
    /// to the mesh; this returns a continuous arc length. A straight segment
    /// projects to a straight plan segment and the parameter along it is
    /// affine in both, so interpolating the cumulative arc by the plan
    /// parameter is exact rather than approximate.
    /// </summary>
    private static double NearestArcInPlan(
        SkinLevelCurve curve,
        double[] target)
    {
        double bestArc = 0.0;
        double bestDistance = double.PositiveInfinity;
        int segments = curve.Closed
            ? curve.Points.Count
            : curve.Points.Count - 1;
        for (int i = 0; i < segments; i++)
        {
            double[] a = curve.Points[i];
            double[] b = curve.Points[(i + 1) % curve.Points.Count];
            double dx = b[0] - a[0];
            double dy = b[1] - a[1];
            double lengthSquared = dx * dx + dy * dy;
            double t = lengthSquared > 1.0e-18
                ? ((target[0] - a[0]) * dx +
                   (target[1] - a[1]) * dy) / lengthSquared
                : 0.0;
            t = Math.Min(Math.Max(t, 0.0), 1.0);
            double px = a[0] + dx * t;
            double py = a[1] + dy * t;
            double distance =
                (px - target[0]) * (px - target[0]) +
                (py - target[1]) * (py - target[1]);
            if (distance < bestDistance)
            {
                bestDistance = distance;
                double start = curve.Cumulative[i];
                double end = i + 1 < curve.Points.Count
                    ? curve.Cumulative[i + 1]
                    : curve.Length;
                bestArc = start + (end - start) * t;
            }
        }
        return bestArc;
    }
```

5. [ ] Use it in `AssignSeams` at SkinPatterns.cs:894-896:

```csharp
                    double[] lowerSeam = PointAt(below[matched], 0.0);
                    curve.Seam = NearestArcInPlan(curve, lowerSeam);
```

   The lowest loop's seam stays the trace vertex on the +X bearing (SkinPatterns.cs:900) and an open
   strip's seam stays its arc-length midpoint (SkinPatterns.cs:888), which is exact already.

6. [ ] Build and run the harness. Seam-dependent pins on closed fixtures move by up to half a vertex
   spacing: re-measure and re-pin each, with the reason written into the check's own message.

7. [ ] Scan for clash files and commit.

```powershell
git add "plugin/native_v02/Components/SkinPatterns.cs" "tests/native_smoke/Program.cs"
git commit -m "feat(skin): a propagated seam is an exact projection and not a trace vertex"
```

---

### Task 25: the native line field

**Files:**
- Create: plugin/native_v02/Components/SkinFlowField.cs
- Test: tests/native_smoke/Program.cs, new `ValidateSkinLineField` plus its entry in `Run`

**Interfaces:**
- Consumes: `SkinNet.Vertices`, `SkinNet.Faces`, `SkinNet.Edges` from Tasks 12 and 14.
- Produces: `internal static class SkinFlowField` with
  `public static IReadOnlyList<double[]> Directions(SkinNet net)`, one unit three-dimensional vector
  per face lying in that face's plane, and
  `public static IReadOnlyList<double> Coherences(SkinNet net)`.

Rule 3.5.1 is why this task has its own bars rather than a comparison: a C# port of the line field
will NOT reproduce today's flow lines and cannot be validated against them. The Python side
fan-triangulates every polygon from its first vertex; the C# tracer splits on the shortest valid plan
diagonal, and its own comment records the measured reason a fan is unacceptable for level-curve work.
Different triangles give different face bases, a different edge set, a different smoothed field and
different streamlines. Taking the FORMULAE from the Python is a different thing from validating OUTPUT
against it: the formulae are copied and cited, the outputs are not comparable.

1. [ ] Add the check:

```csharp
    /// <summary>
    /// Check 12.3(a). The native line field on a BARREL, where the thrust
    /// runs one way everywhere, gives directions that agree with the
    /// barrel's own generators to within 5 degrees at every face. THE
    /// FIXTURE MUST CARRY FORCES: every edge running along the barrel
    /// carries a compression of 1 kN and every edge across it 0.1 kN, which
    /// is a one-way thrust stated as data rather than assumed. On the SAME
    /// barrel with its force list removed the field falls to the (1, 0)
    /// default of rule 3.2.8 on every face and the component does not throw.
    /// The author must be able to tell a straight flow line from a defaulted
    /// one, and running the fixture both ways is what makes that
    /// distinction exist.
    /// </summary>
    private static void ValidateSkinLineField(Assembly plugin)
    {
        Type field = RequireComponentType(plugin, "SkinFlowField");
        Type netType = RequireComponentType(plugin, "SkinNet");
        Type edgeType = RequireComponentType(plugin, "SkinNetEdge");
        MethodInfo directions = RequirePublicStatic(field, "Directions");
        (double[][] vertices, int[][] faces) = SkinBarrelNet();
        object forced = SkinNetWith(
            netType, edgeType, vertices, faces, SkinBarrelRim(),
            SkinBarrelForces());
        var withForce = ((IEnumerable)directions.Invoke(
                null, new[] { forced })!)
            .Cast<double[]>()
            .ToArray();
        foreach (double[] direction in withForce)
        {
            // The barrel runs along x, so the generator is (1, 0, 0) and a
            // LINE field has no sign: the angle is taken to the nearer end.
            double along = Math.Abs(direction[0]);
            double angle = Math.Acos(Math.Min(1.0, along)) * 180.0 / Math.PI;
            if (angle > 5.0)
            {
                throw new InvalidOperationException(
                    "Under rule 3.2.7 a barrel carrying 1 kN along and " +
                    "0.1 kN across lies along its own generators " +
                    $"everywhere, to within 5 degrees; got {angle} degrees. " +
                    "If it does not, the arithmetic of rules 3.2.5 to 3.2.9 " +
                    "was built wrong.");
            }
        }
        object bare = Activator.CreateInstance(
            netType, new object[] { vertices, faces })!;
        var defaulted = ((IEnumerable)directions.Invoke(null, new[] { bare })!)
            .Cast<double[]>()
            .ToArray();
        if (defaulted.Length != withForce.Length)
        {
            throw new InvalidOperationException(
                "A net carrying NO force edges at all is not an error: " +
                "every face takes the (1, 0) default of rule 3.2.8, which " +
                "is its own e1, and the diagnostics say so rather than " +
                "leaving the author to wonder why his flow lines came out " +
                "straight (rule 1.3.6).");
        }
    }
```

2. [ ] Wire it into `Run` after the seam-drift block, with a PASS line naming both runs.

3. [ ] Build and run the harness. It must fail: there is no `SkinFlowField`.

4. [ ] Create plugin/native_v02/Components/SkinFlowField.cs:

```csharp
#nullable enable

using System;
using System.Collections.Generic;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// The line field the force-aligned pattern's head joints follow (spec
/// 2026-09-01 section 3.2a), computed natively. The arithmetic is taken from
/// the shipped Python worker and cited rule by rule; the OUTPUT is not
/// comparable with it and must not be validated against it, because the two
/// sides triangulate differently (rule 3.5.1).
///
/// Nothing here may reference RhinoCommon, the rule the harness's whole
/// ability to measure the engine rests on.
/// </summary>
internal static class SkinFlowField
{
    /// <summary>Rule 3.2.5. Each triangle carries its own orthonormal plane
    /// basis: e1 is the first edge normalised, the normal is the normalised
    /// cross product of the first two edges falling back to (0, 0, 1) where
    /// it degenerates, and e2 is the cross product of normal and e1. Every
    /// direction lives in its own face's (e1, e2) and never in a shared
    /// world frame.</summary>
    private static (double[] E1, double[] E2, double[] Normal) Basis(
        SkinNet net,
        int[] face)
    {
        double[] a = net.Vertices[face[0]];
        double[] b = net.Vertices[face[1]];
        double[] c = net.Vertices[face[2]];
        double[] first = { b[0] - a[0], b[1] - a[1], b[2] - a[2] };
        double[] second = { c[0] - a[0], c[1] - a[1], c[2] - a[2] };
        double[] normal =
        {
            first[1] * second[2] - first[2] * second[1],
            first[2] * second[0] - first[0] * second[2],
            first[0] * second[1] - first[1] * second[0]
        };
        double normalLength = Length(normal);
        normal = normalLength > 1.0e-12
            ? Scale(normal, 1.0 / normalLength)
            : new[] { 0.0, 0.0, 1.0 };
        double firstLength = Length(first);
        double[] e1 = firstLength > 1.0e-12
            ? Scale(first, 1.0 / firstLength)
            : new[] { 1.0, 0.0, 0.0 };
        double[] e2 =
        {
            normal[1] * e1[2] - normal[2] * e1[1],
            normal[2] * e1[0] - normal[0] * e1[2],
            normal[0] * e1[1] - normal[1] * e1[0]
        };
        return (e1, e2, normal);
    }

    private static double Length(double[] vector) =>
        Math.Sqrt(
            vector[0] * vector[0] +
            vector[1] * vector[1] +
            vector[2] * vector[2]);

    private static double[] Scale(double[] vector, double by) =>
        new[] { vector[0] * by, vector[1] * by, vector[2] * by };

    /// <summary>Rule 3.2.6. A unit plane direction is carried as
    /// (dx dx - dy dy, 2 dx dy), which is (cos 2 theta, sin 2 theta): a line
    /// and its negation are the same line, and doubling is what makes an
    /// average of lines mean anything at all.</summary>
    private static (double X, double Y) Double(double dx, double dy) =>
        (dx * dx - dy * dy, 2.0 * dx * dy);

    /// <summary>Rule 3.2.6's inverse, returning (1, 0) where the magnitude
    /// is at or below 1e-12.</summary>
    private static (double X, double Y) Undouble(double x, double y)
    {
        if (Math.Sqrt(x * x + y * y) <= 1.0e-12)
            return (1.0, 0.0);
        double half = Math.Atan2(y, x) / 2.0;
        return (Math.Cos(half), Math.Sin(half));
    }

    /// <summary>
    /// Rules 3.2.7 to 3.2.9: the raw per-face direction weighted by member
    /// force, its coherence, the (1, 0) fallback, and EXACTLY THREE
    /// neighbour-averaging passes, which is a constant and not an input.
    /// </summary>
    public static IReadOnlyList<double[]> Directions(SkinNet net)
    {
        (double[] Plane, double Coherence)[] state = Raw(net);
        var bases = new (double[] E1, double[] E2, double[] Normal)[
            net.Faces.Count];
        for (int face = 0; face < net.Faces.Count; face++)
            bases[face] = Basis(net, net.Faces[face]);
        var neighbours = Neighbours(net);
        // The coherence used in the weight is the RAW coherence, fixed from
        // the unsmoothed field and never recomputed between passes.
        // Weighting every neighbour by its raw coherence instead, without
        // the clamp, was tried and measured: it discounts the ninety-two per
        // cent of ordinary faces along with the eight per cent meant,
        // changes every face's final direction and regresses the vault's own
        // bars. Do not.
        double[] coherence = new double[net.Faces.Count];
        var current = new double[net.Faces.Count][];
        for (int face = 0; face < net.Faces.Count; face++)
        {
            coherence[face] = state[face].Coherence;
            current[face] = state[face].Plane;
        }
        for (int pass = 0; pass < 3; pass++)
        {
            var next = new double[net.Faces.Count][];
            for (int face = 0; face < net.Faces.Count; face++)
            {
                (double[] e1, double[] e2, double[] normal) = bases[face];
                double x = 0.0;
                double y = 0.0;
                (double px, double py) = Project(current[face], e1, e2);
                (double dx, double dy) = Double(px, py);
                x += dx;
                y += dy;
                foreach (int other in neighbours[face])
                {
                    double[] world = current[other];
                    double dot =
                        world[0] * normal[0] +
                        world[1] * normal[1] +
                        world[2] * normal[2];
                    double[] flattened =
                    {
                        world[0] - normal[0] * dot,
                        world[1] - normal[1] * dot,
                        world[2] - normal[2] * dot
                    };
                    double flatLength = Length(flattened);
                    if (flatLength <= 1.0e-12)
                        continue;
                    (double ox, double oy) = Project(
                        Scale(flattened, 1.0 / flatLength), e1, e2);
                    double planeLength = Math.Sqrt(ox * ox + oy * oy);
                    if (planeLength <= 1.0e-12)
                        continue;
                    ox /= planeLength;
                    oy /= planeLength;
                    double weight = Math.Min(1.0, coherence[other] / 0.2);
                    (double ddx, double ddy) = Double(ox, oy);
                    x += weight * ddx;
                    y += weight * ddy;
                }
                (double ux, double uy) = Undouble(x, y);
                next[face] = new[]
                {
                    e1[0] * ux + e2[0] * uy,
                    e1[1] * ux + e2[1] * uy,
                    e1[2] * ux + e2[2] * uy
                };
            }
            current = next;
        }
        return current;
    }

    public static IReadOnlyList<double> Coherences(SkinNet net)
    {
        (double[] Plane, double Coherence)[] state = Raw(net);
        var read = new double[state.Length];
        for (int face = 0; face < state.Length; face++)
            read[face] = state[face].Coherence;
        return read;
    }

    private static (double X, double Y) Project(
        double[] world,
        double[] e1,
        double[] e2) =>
        (world[0] * e1[0] + world[1] * e1[1] + world[2] * e1[2],
         world[0] * e2[0] + world[1] * e2[1] + world[2] * e2[2]);

    /// <summary>Rule 3.2.7's raw per-face direction and its coherence, and
    /// rule 3.2.8's fallback: a face NONE of whose edges carries a weight
    /// takes the direction (1, 0), which is its own e1, and reports
    /// coherence 1.0, so that a fixed default is never discounted as though
    /// it were a contested vote.</summary>
    private static (double[] Plane, double Coherence)[] Raw(SkinNet net)
    {
        var forceOf = new Dictionary<(int, int), double>();
        foreach (SkinNetEdge edge in net.Edges)
            forceOf[(edge.A, edge.B)] = edge.Force;
        var read = new (double[], double)[net.Faces.Count];
        for (int face = 0; face < net.Faces.Count; face++)
        {
            int[] triangle = net.Faces[face];
            (double[] e1, double[] e2, double[] _) = Basis(net, triangle);
            double x = 0.0;
            double y = 0.0;
            double weight = 0.0;
            for (int corner = 0; corner < triangle.Length; corner++)
            {
                int a = triangle[corner];
                int b = triangle[(corner + 1) % triangle.Length];
                (int, int) key = a < b ? (a, b) : (b, a);
                if (!forceOf.TryGetValue(key, out double force) ||
                    Math.Abs(force) <= 1.0e-12)
                {
                    continue;
                }
                double[] from = net.Vertices[key.Item1];
                double[] to = net.Vertices[key.Item2];
                double[] along =
                    { to[0] - from[0], to[1] - from[1], to[2] - from[2] };
                double alongLength = Length(along);
                if (alongLength <= 1.0e-12)
                    continue;
                (double px, double py) = Project(
                    Scale(along, 1.0 / alongLength), e1, e2);
                double planeLength = Math.Sqrt(px * px + py * py);
                if (planeLength <= 1.0e-12)
                    continue;
                (double dx, double dy) = Double(
                    px / planeLength, py / planeLength);
                x += Math.Abs(force) * dx;
                y += Math.Abs(force) * dy;
                weight += Math.Abs(force);
            }
            if (!(weight > 0.0))
            {
                read[face] = (e1, 1.0);
                continue;
            }
            (double ux, double uy) = Undouble(x, y);
            read[face] = (
                new[]
                {
                    e1[0] * ux + e2[0] * uy,
                    e1[1] * ux + e2[1] * uy,
                    e1[2] * ux + e2[2] * uy
                },
                Math.Sqrt(x * x + y * y) / weight);
        }
        return read;
    }

    /// <summary>Every face's neighbours across a shared triangle edge.
    /// Public to the file because the advection walk of rule 3.2.10 needs
    /// the same adjacency.</summary>
    internal static IReadOnlyList<int>[] Neighbours(SkinNet net)
    {
        var byEdge = new Dictionary<(int, int), List<int>>();
        for (int face = 0; face < net.Faces.Count; face++)
        {
            int[] triangle = net.Faces[face];
            for (int corner = 0; corner < triangle.Length; corner++)
            {
                int a = triangle[corner];
                int b = triangle[(corner + 1) % triangle.Length];
                (int, int) key = a < b ? (a, b) : (b, a);
                if (!byEdge.TryGetValue(key, out List<int>? owners))
                    byEdge[key] = owners = new List<int>();
                owners.Add(face);
            }
        }
        var read = new IReadOnlyList<int>[net.Faces.Count];
        for (int face = 0; face < net.Faces.Count; face++)
        {
            var found = new List<int>();
            int[] triangle = net.Faces[face];
            for (int corner = 0; corner < triangle.Length; corner++)
            {
                int a = triangle[corner];
                int b = triangle[(corner + 1) % triangle.Length];
                (int, int) key = a < b ? (a, b) : (b, a);
                foreach (int owner in byEdge[key])
                {
                    if (owner != face)
                        found.Add(owner);
                }
            }
            read[face] = found;
        }
        return read;
    }
}
```

5. [ ] Build and run the harness. The new PASS line must appear.

6. [ ] Scan for clash files and commit.

```powershell
git add "plugin/native_v02/Components/SkinFlowField.cs" "tests/native_smoke/Program.cs"
git commit -m "feat(skin): the line field is computed natively from the net's own force edges"
```

---

### Task 26: native streamlines and the force-aligned pattern

**Files:**
- Modify: plugin/native_v02/Components/SkinFlowField.cs (the advection walk) and
  plugin/native_v02/Components/SkinPatterns.cs (a new `ForceAligned` engine)
- Test: tests/native_smoke/Program.cs, new `ValidateSkinForceAligned` plus its entry in `Run`

**Interfaces:**
- Consumes: `SkinFlowField.Directions`, `SkinFlowField.Neighbours`, `ResolveBands`, `Run`, `PointAt`,
  `NearestArcInPlan`, `MergeShortPieces`, `KeepValidPlans`.
- Produces:
  - ```csharp
    public static double[][] SkinFlowField.Streamline(
        SkinNet net,
        IReadOnlyList<double[]> directions,
        IReadOnlyList<int>[] neighbours,
        double[] from,
        int face,
        double[] hint,
        double clearance,
        IReadOnlyList<double[][]> accepted)
    ```
    ONE polyline, not a list of them, and it takes the neighbour lists it walks over rather than
    rebuilding them per seed, which on a fine dome is the difference between a seed and a solve. An
    earlier draft of this line declared a different return type and one fewer parameter than the
    body in Step 4, which is the kind of disagreement Task 32's `MarchToLevel` then inherits.
  - `public static SkinPatternResult SkinPatterns.ForceAligned(SkinNet net, double size,
    double courseHeight, double minPiece)` with a three-argument overload defaulting to 1.0 / 3.0.
  - `public static double SkinPatterns.LevelAt(SkinNet net, double[] at)`, the piecewise-linear
    interpolant of rule 1.4.4 evaluated at a point.
  - `internal static double[] SkinPatterns.PointAtArcPublic(SkinLevelCurve curve, double arc)`, a
    thin wrapper on the existing private `PointAtArc`.
  - `public static double[][][] SkinPatterns.ForceAlignedLines(SkinPatternResult)` and
    `ForceAlignedBeds(SkinPatternResult)`, which check 12.3(b) measures the pattern's central
    property against.

The masonry reading stands and it is what this task builds: the BEDS are the continuous family and
they are the section 1 level curves, running across the thrust so the thrust closes them; the HEAD
joints are the native streamlines, generated at S / 2 by rule 3.3.1 with alternate parity per course
by rule 3.3.4. The rejected reading, pieces sitting between adjacent flow lines in strips running rim
to crown, is recorded in rule 3.3.4a with its reason: a joint continuous from rim to crown is a crack
line up the form, nothing crosses it, so nothing closes it.

1. [ ] Add the check:

```csharp
    /// <summary>
    /// The force-aligned pattern (spec section 3), checks 12.3(b) to
    /// 12.3(e).
    /// </summary>
    private static void ValidateSkinForceAligned(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        Type edgeType = RequireComponentType(plugin, "SkinNetEdge");
        MethodInfo forceAligned = RequirePublicStatic(
            patterns, "ForceAligned");
        (double[][] vertices, int[][] faces) = SkinBarrelNet();
        object net = SkinNetWith(
            netType, edgeType, vertices, faces, SkinBarrelRim(),
            SkinBarrelForces());
        object built = forceAligned.Invoke(
            null, new object[] { net, 0.6, 0.5, 1.0 / 3.0 })!;
        var cells = SkinCells(built);
        if (cells.Length == 0)
        {
            throw new InvalidOperationException(
                "The force-aligned pattern is NATIVE and synchronous like " +
                "the other two (rule 3.2.4); it must build cells on a " +
                "force-bearing barrel.");
        }

        // 12.3(b): EVERY HEAD JOINT OF EVERY CELL LIES ON A STREAMLINE, and
        // every bed edge lies on a level curve. This is the property the
        // pattern exists for and the one that would silently not hold: the
        // ratio, the bond and the odd cells can all be right on a pattern
        // whose joints have quietly drifted off the flow. The tolerance is
        // stated and it is ONE HUNDREDTH OF A PIECE, S / 100 = 6 mm at the
        // sizes this check runs at, which is far under the setout accuracy
        // any of this is built to and far over the tracer's own rounding.
        const double onStreamline = 0.6 / 100.0;
        MethodInfo acceptedLines = RequirePublicStatic(
            patterns, "ForceAlignedLines");
        MethodInfo acceptedBeds = RequirePublicStatic(
            patterns, "ForceAlignedBeds");
        void RequireJointsOnFlow(object generated, string label)
        {
            double[][][] flow = (double[][][])acceptedLines.Invoke(
                null, new[] { generated })!;
            double[][][] beds = (double[][][])acceptedBeds.Invoke(
                null, new[] { generated })!;
            foreach (object cell in (IList)generated.GetType()
                         .GetProperty("Cells")!.GetValue(generated)!)
            {
                if (Reading<bool>(cell, "Cap"))
                    continue;
                IList sections = (IList)cell.GetType()
                    .GetProperty("Sections")!.GetValue(cell)!;
                // A force-aligned cell carries four chains: the lower bed
                // run, the upper streamline segment, the upper bed run and
                // the lower streamline segment, in that order (rule 3.3.6).
                double[][] lowerBed = ((IList)sections[0]!).Cast<double[]>().ToArray();
                double[][] upFlow = ((IList)sections[1]!).Cast<double[]>().ToArray();
                double[][] upperBed = ((IList)sections[2]!).Cast<double[]>().ToArray();
                double[][] downFlow = ((IList)sections[3]!).Cast<double[]>().ToArray();
                foreach ((double[][] chain, double[][][] family, string what) in
                         new[]
                         {
                             (upFlow, flow, "head joint"),
                             (downFlow, flow, "head joint"),
                             (lowerBed, beds, "bed edge"),
                             (upperBed, beds, "bed edge")
                         })
                {
                    foreach (double[] sample in chain)
                    {
                        double nearest = family.Min(
                            line => PolylineDistance(sample, line));
                        if (nearest > onStreamline)
                        {
                            throw new InvalidOperationException(
                                $"On the {label} a {what} sample stands " +
                                $"{nearest:F5} m from the nearest accepted " +
                                (what == "head joint" ? "STREAMLINE" : "LEVEL CURVE") +
                                $", against a stated tolerance of {onStreamline:F5} m " +
                                "(check 12.3(b)). Every head joint of every " +
                                "cell lies on a streamline and every bed " +
                                "edge lies on a level curve; that is the " +
                                "property the pattern exists for and the one " +
                                "that would silently not hold.");
                        }
                    }
                }
            }
        }
        RequireJointsOnFlow(built, "force-bearing barrel");

        // 12.3(d): UNIFORMITY. Max piece length over min is at or under 2.5,
        // measured over the non-Cap cells by rule 2.3.2a, against the 0.377
        // to 3.889 ratio of over 10 his screenshot recorded. The bar is 2.5
        // and not 3 because the construction's own bound IS 3 and a check
        // set at its own bound cannot fail meaningfully: rules 3.3.3 and
        // 3.3.4 hold a gap between 0.5 P_k and 1.5 P_k and a piece is two
        // gaps, so a piece lies between P_k and 3 P_k.
        double[] spans = cells
            .Where(cell => !cell.Cap)
            .Select(cell => cell.U1 - cell.U0)
            .ToArray();
        double ratio = spans.Max() / spans.Min();
        Console.WriteLine(
            "      Skin force-aligned uniformity (check 12.3(d)): piece " +
            $"{spans.Min():F3} m to {spans.Max():F3} m, ratio " +
            $"{ratio:F2}.");
        if (ratio > 2.5)
        {
            throw new InvalidOperationException(
                "A pattern whose min and max piece lengths read 0.377 m " +
                "against 3.889 m fails the fourth property of section 3.4 " +
                "and must be visible as failing it; the ratio is " +
                $"{ratio}. Where a fixture measures between 2.5 and 3, " +
                "re-pin the bar as a measurement with the reason written " +
                "beside it rather than bending the engine to reach it.");
        }

        // 12.3(c): BOND. For every pair of vertically adjacent cells the
        // head joints of the upper do not coincide with those of the lower,
        // to within a tenth of a piece. That pins rule 3.3.4's parity, which
        // is anchored on the STREAMLINE and never on a bed's crossing index.
        foreach (var lower in cells.Where(cell => !cell.Cap))
        {
            foreach (var upper in cells.Where(cell =>
                         cell.Course == lower.Course + 1 && !cell.Cap))
            {
                double tolerance = (lower.U1 - lower.U0) / 10.0;
                if (Math.Abs(upper.U0 - lower.U0) < tolerance &&
                    Math.Abs(upper.U1 - lower.U1) < tolerance)
                {
                    throw new InvalidOperationException(
                        "Course r takes as its head joints the crossings of " +
                        "the lines whose parity is r mod 2, so no head " +
                        "joint runs through two consecutive courses and no " +
                        "joint becomes a crack line up the form (rule " +
                        $"3.3.4); courses {lower.Course} and " +
                        $"{upper.Course} share a joint pair.");
                }
            }
        }

        // 12.3(e): INSERTION AND TERMINATION. A fanning fixture whose rows
        // lengthen produces at least one insertion and a converging one at
        // least one termination, each producing exactly one odd-sided cell,
        // each counted in skin.odd_cells.
        (double[][] domeVertices, int[][] domeFaces, int[] domeRim) =
            SkinFineDomeNet();
        object dome = SkinNetWith(
            netType, edgeType, domeVertices, domeFaces, domeRim,
            Array.Empty<(int, int, double)>());
        object domeBuilt = forceAligned.Invoke(
            null, new object[] { dome, 0.6, 0.35, 1.0 / 3.0 })!;
        if (Reading<int>(domeBuilt, "FiveSidedCells") +
            Reading<int>(domeBuilt, "SevenSidedCells") == 0)
        {
            throw new InvalidOperationException(
                "A converging dome must TERMINATE lines, and a cell gains " +
                "or loses a side only where a line begins or ends within " +
                "its own band (rule 3.3.5). Those cells are the pattern's " +
                "honest response to a flow that converges, and refusing " +
                "them would put a hole where a mason puts a closer.");
        }
        RequireJointsOnFlow(domeBuilt, "fine dome");
    }
```

   Three things this check needs that the engine does not carry yet, and each is small. `ForceAligned`
   keeps its ACCEPTED streamlines and its TRACED BEDS and exposes them as
   `public static double[][][] SkinPatterns.ForceAlignedLines(SkinPatternResult)` and
   `ForceAlignedBeds(SkinPatternResult)`, reading two new members on the record,
   `IReadOnlyList<double[][]> FlowLines` and `IReadOnlyList<double[][]> BedCurves`, empty on the other
   two patterns and on `Empty`; check 12.3(b) cannot be taken without them, because a check that
   re-derived the streamlines in the harness would be comparing the engine with a second engine.
   `PolylineDistance` is an ordinary point-to-polyline helper beside `SkinCells`: the smallest
   point-to-segment distance over the polyline's segments, in three dimensions, since a bed and a
   streamline both lie on the surface. And the doc comment on `ValidateSkinForceAligned` says it
   covers "checks 12.3(b) to 12.3(e)", which is now true; an earlier draft made that claim while
   implementing only (c), (d) and (e), and 12.3(b) appeared nowhere but in a comment inside the
   engine.

2. [ ] Wire it into `Run` after the line-field block, with a PASS line naming the four bars.

3. [ ] Build and run the harness. It must fail: there is no `ForceAligned`.

4. [ ] Add the advection walk to SkinFlowField.cs:

```csharp
    /// <summary>
    /// Rule 3.2.10. ADVECTION IS A FACE-EXIT WALK AND NOT A FIXED STEP, so
    /// there is no step length to choose and none is specified. From a point
    /// inside a face, take that face's own field direction, project it into
    /// the face's plane, normalise, cast the ray from the point along it,
    /// and find where it EXITS the triangle. That exit point is the next
    /// polyline point and the face across the exited edge is the next face.
    /// A streamline therefore carries exactly one point per face crossed,
    /// which is the same discipline Run keeps for a level curve.
    ///
    /// The sign ambiguity a line field carries is resolved by CONTINUATION:
    /// the next face's direction is negated where its dot product with the
    /// direction just used is negative, and the very first face takes an
    /// orientation hint.
    ///
    /// TERMINATION (rule 3.2.11): a mesh boundary edge, a field that
    /// projects to nothing, 20000 steps, or coming within the termination
    /// radius of an already-accepted line, measured point to SEGMENT against
    /// the accepted lines resampled at the same radius.
    /// </summary>
    public static double[][] Streamline(
        SkinNet net,
        IReadOnlyList<double[]> directions,
        IReadOnlyList<int>[] neighbours,
        double[] from,
        int face,
        double[] hint,
        double clearance,
        IReadOnlyList<double[][]> accepted)
    {
        var line = new List<double[]> { from };
        double[] previous = hint;
        double[] at = from;
        int current = face;
        for (int step = 0; step < 20000; step++)
        {
            double[] direction = directions[current];
            double dot =
                direction[0] * previous[0] +
                direction[1] * previous[1] +
                direction[2] * previous[2];
            if (dot < 0.0)
                direction = new[]
                    { -direction[0], -direction[1], -direction[2] };
            if (Length(direction) <= 1.0e-12)
                break;
            (double[]? exit, int through) = ExitOf(net, current, at, direction);
            if (exit is null)
                break;
            line.Add(exit);
            if (TooClose(exit, accepted, clearance))
                break;
            int next = -1;
            foreach (int candidate in neighbours[current])
            {
                if (candidate != current && SharesEdge(
                        net, candidate, net.Faces[current], through))
                {
                    next = candidate;
                    break;
                }
            }
            if (next < 0)
                break;
            previous = direction;
            at = exit;
            current = next;
        }
        return line.ToArray();
    }

    /// <summary>Where a ray from a point inside a triangle, along a
    /// direction lying in its plane, leaves it: the exit point and the index
    /// of the exited edge within the face.</summary>
    private static (double[]? Exit, int Edge) ExitOf(
        SkinNet net,
        int face,
        double[] from,
        double[] direction)
    {
        int[] triangle = net.Faces[face];
        (double[] e1, double[] e2, double[] _) = Basis(net, triangle);
        (double px, double py) = Project(
            new[]
            {
                from[0] - net.Vertices[triangle[0]][0],
                from[1] - net.Vertices[triangle[0]][1],
                from[2] - net.Vertices[triangle[0]][2]
            },
            e1, e2);
        (double dx, double dy) = Project(direction, e1, e2);
        double best = double.PositiveInfinity;
        int bestEdge = -1;
        for (int corner = 0; corner < 3; corner++)
        {
            double[] a = net.Vertices[triangle[corner]];
            double[] b = net.Vertices[triangle[(corner + 1) % 3]];
            (double ax, double ay) = Project(
                new[]
                {
                    a[0] - net.Vertices[triangle[0]][0],
                    a[1] - net.Vertices[triangle[0]][1],
                    a[2] - net.Vertices[triangle[0]][2]
                },
                e1, e2);
            (double bx, double by) = Project(
                new[]
                {
                    b[0] - net.Vertices[triangle[0]][0],
                    b[1] - net.Vertices[triangle[0]][1],
                    b[2] - net.Vertices[triangle[0]][2]
                },
                e1, e2);
            double ex = bx - ax;
            double ey = by - ay;
            double denominator = dx * ey - dy * ex;
            if (Math.Abs(denominator) <= 1.0e-15)
                continue;
            double t = ((ax - px) * ey - (ay - py) * ex) / denominator;
            double s = ((ax - px) * dy - (ay - py) * dx) / denominator;
            if (t <= 1.0e-12 || s < -1.0e-9 || s > 1.0 + 1.0e-9)
                continue;
            if (t < best)
            {
                best = t;
                bestEdge = corner;
            }
        }
        if (bestEdge < 0)
            return (null, -1);
        return (
            new[]
            {
                from[0] + direction[0] * best,
                from[1] + direction[1] * best,
                from[2] + direction[2] * best
            },
            bestEdge);
    }

    private static bool SharesEdge(
        SkinNet net,
        int candidate,
        int[] face,
        int edge)
    {
        int a = face[edge];
        int b = face[(edge + 1) % 3];
        int[] other = net.Faces[candidate];
        bool hasA = false;
        bool hasB = false;
        foreach (int corner in other)
        {
            if (corner == a)
                hasA = true;
            if (corner == b)
                hasB = true;
        }
        return hasA && hasB;
    }

    private static bool TooClose(
        double[] point,
        IReadOnlyList<double[][]> accepted,
        double clearance)
    {
        foreach (double[][] line in accepted)
        {
            for (int at = 0; at + 1 < line.Length; at++)
            {
                double[] a = line[at];
                double[] b = line[at + 1];
                double dx = b[0] - a[0];
                double dy = b[1] - a[1];
                double dz = b[2] - a[2];
                double lengthSquared = dx * dx + dy * dy + dz * dz;
                double t = lengthSquared > 1.0e-18
                    ? ((point[0] - a[0]) * dx +
                       (point[1] - a[1]) * dy +
                       (point[2] - a[2]) * dz) / lengthSquared
                    : 0.0;
                t = Math.Min(Math.Max(t, 0.0), 1.0);
                double qx = a[0] + dx * t - point[0];
                double qy = a[1] + dy * t - point[1];
                double qz = a[2] + dz * t - point[2];
                if (Math.Sqrt(qx * qx + qy * qy + qz * qz) < clearance)
                    return true;
            }
        }
        return false;
    }
```

5. [ ] Add the engine to SkinPatterns.cs, after `Courses`:

```csharp
    public static SkinPatternResult ForceAligned(
        SkinNet net,
        double size,
        double courseHeight) =>
        ForceAligned(net, size, courseHeight, 1.0 / 3.0);

    /// <summary>
    /// Pattern 2, native (spec section 3). Its BED joints are the SAME
    /// curves pattern 0 uses, level sets of the rim-distance field at
    /// spacing CH: they are continuous, they run across the thrust, and the
    /// thrust closes them rather than sliding along them. Its HEAD joints
    /// are STREAMLINES of the line field, and every head joint of every cell
    /// lies on one, which is what makes the pattern force-aligned in the
    /// sense he can see: the sinusoidal curves running up his form become
    /// the joints instead of being ignored by them.
    ///
    /// Everything downstream is pattern 0's (rule 3.3.6): the same
    /// KeepValidPlans, the same section 6 merge, the same section 7 order.
    /// It therefore INHERITS the proportional arc mapping of rule 1.8.1
    /// along with the rest, which is his first cause of the setout
    /// distortion and is deferred by rule 1.8.4. Said here rather than left
    /// to be found: pattern 2 does not escape a defect merely by being new.
    ///
    /// A cell's course is its BED index (rule 3.6.1), the rim-distance band
    /// it sits in, and never its seed's along-flow band: the Python's
    /// docstring records 7 of 39 streamlines rising then falling by more
    /// than 0.5 m, and Bench Studio runs a formwork weight and an FEA solve
    /// per stage, so this is a structural choice and not a labelling one.
    /// </summary>
    public static SkinPatternResult ForceAligned(
        SkinNet net,
        double size,
        double courseHeight,
        double minPiece)
    {
        RequireSizes(size, courseHeight);
        double clampedMinPiece =
            double.IsFinite(minPiece)
                ? Math.Min(Math.Max(minPiece, 0.0), 0.5)
                : 1.0 / 3.0;
        (double dMin, double dMax) = LevelRange(net);
        if (net.Faces.Count == 0 || !(dMax - dMin > 1.0e-9))
            return Empty("force aligned", net);

        int bands = BandCount(dMin, dMax, courseHeight);
        double epsilon = Math.Max((dMax - dMin) * 1.0e-6, 1.0e-9);
        var levels = new List<double>();
        var intervals = new List<SkinBandInterval>();
        for (int r = 0; r < bands; r++)
        {
            double low = AddLevel(
                levels, r == 0 ? dMin + epsilon : dMin + r * courseHeight);
            double bandTop = r == bands - 1
                ? dMax
                : dMin + (r + 1) * courseHeight;
            double high = AddLevel(
                levels, r == bands - 1 ? dMax - epsilon : bandTop);
            double mid = AddLevel(
                levels, (dMin + r * courseHeight + bandTop) / 2.0);
            intervals.Add(new SkinBandInterval(r, low, mid, high, 0));
        }
        SkinBandResolution resolved = ResolveBands(net, levels, intervals);
        var levelIndex = new Dictionary<double, int>();
        for (int at = 0; at < resolved.Levels.Count; at++)
            levelIndex[resolved.Levels[at]] = at;

        IReadOnlyList<double[]> directions = SkinFlowField.Directions(net);
        IReadOnlyList<int>[] neighbours = SkinFlowField.Neighbours(net);

        // SEEDING, on BED 0 and never on the rim (rule 3.3.1). There is no
        // curve at field value 0 to place a seed on: the tracer's crossing
        // rule is half-open, so at level 0 every rim vertex is at-or-above,
        // no edge crosses anywhere and Trace returns nothing. Seeds go on
        // the traced curve at the epsilon, at uniform pitch
        // P0 = L0 / max(1, round(L0 / (S / 2))), that is at HALF the target
        // piece length, because rule 3.3.4's course takes every OTHER line.
        var lines = new List<(double[][] Points, int Parity)>();
        IReadOnlyList<SkinLevelCurve> bed0 =
            resolved.Traced[levelIndex[intervals[0].Low]];
        double clearance = 0.5 * (size / 2.0);
        var accepted = new List<double[][]>();
        foreach (SkinLevelCurve component in bed0)
        {
            int seeds = Math.Max(
                1, (int)Math.Round(component.Length / (size / 2.0)));
            double pitch = component.Length / seeds;
            for (int at = 0; at < seeds; at++)
            {
                double u = component.Closed
                    ? at * pitch
                    : at * pitch - component.Length / 2.0;
                double[] from = PointAt(component, u);
                int face = FaceUnder(net, from);
                if (face < 0)
                    continue;
                double[] hint = AscentHint(net, face);
                double[][] line = SkinFlowField.Streamline(
                    net, directions, neighbours, from, face, hint,
                    clearance, accepted);
                if (line.Length < 2)
                    continue;
                accepted.Add(line);
                lines.Add((line, at % 2));
            }
        }
        // The crossings, the insertion and termination pass and the cell
        // build follow, in steps 6 and 7 below. They are the second HALF of
        // this engine and every assertion in step 1, the piece-length ratio,
        // the bond, the odd cells and check 12.3(b) itself, measures exactly
        // that half, so it is written out there rather than left as prose.
    }
```

   with the helpers beside it:

```csharp
    /// <summary>Which net face contains a point in plan, or -1.</summary>
    private static int FaceUnder(SkinNet net, double[] at)
    {
        for (int face = 0; face < net.Faces.Count; face++)
        {
            int[] triangle = net.Faces[face];
            var ring = new[]
            {
                net.Vertices[triangle[0]],
                net.Vertices[triangle[1]],
                net.Vertices[triangle[2]]
            };
            if (PlanContains(at[0], at[1], ring))
                return face;
        }
        return -1;
    }

    /// <summary>The ASCENDING direction of the Levels field on a face, which
    /// is the orientation hint rule 3.2.10 asks for, since rule 3.3.2
    /// advects upward. Constant on each triangle, because the field is the
    /// piecewise-linear interpolant of rule 1.4.4.</summary>
    private static double[] AscentHint(SkinNet net, int face)
    {
        int[] triangle = net.Faces[face];
        int low = triangle[0];
        int high = triangle[0];
        foreach (int corner in triangle)
        {
            if (net.Levels[corner] < net.Levels[low])
                low = corner;
            if (net.Levels[corner] > net.Levels[high])
                high = corner;
        }
        double[] from = net.Vertices[low];
        double[] to = net.Vertices[high];
        return new[] { to[0] - from[0], to[1] - from[1], to[2] - from[2] };
    }

    /// <summary>
    /// The field of rule 1.4.4 evaluated at a point: the piecewise-linear
    /// interpolant of the vertex Levels over the triangles. The point's face
    /// is found in plan and the value is the barycentric combination of that
    /// face's three vertex levels. Off the mesh in plan it returns the value
    /// at the nearest face's own centroid, which is the honest answer for a
    /// point the field is not defined at and never happens on a streamline,
    /// since every streamline point is an exit point on an edge.
    /// </summary>
    public static double LevelAt(SkinNet net, double[] at)
    {
        int face = FaceUnder(net, at);
        if (face < 0)
        {
            int nearest = 0;
            double best = double.PositiveInfinity;
            for (int candidate = 0; candidate < net.Faces.Count; candidate++)
            {
                int[] corners = net.Faces[candidate];
                double cx = corners.Average(c => net.Vertices[c][0]);
                double cy = corners.Average(c => net.Vertices[c][1]);
                double distance =
                    ((cx - at[0]) * (cx - at[0])) + ((cy - at[1]) * (cy - at[1]));
                if (distance < best)
                {
                    best = distance;
                    nearest = candidate;
                }
            }
            face = nearest;
        }
        int[] triangle = net.Faces[face];
        double[] a = net.Vertices[triangle[0]];
        double[] b = net.Vertices[triangle[1]];
        double[] c = net.Vertices[triangle[2]];
        double area =
            ((b[0] - a[0]) * (c[1] - a[1])) - ((c[0] - a[0]) * (b[1] - a[1]));
        if (Math.Abs(area) <= 1.0e-15)
        {
            // A triangle with no plan area: its three levels average, which
            // is what a vertical face gives and is finite.
            return triangle.Average(corner => net.Levels[corner]);
        }
        double wb =
            (((at[0] - a[0]) * (c[1] - a[1])) - ((c[0] - a[0]) * (at[1] - a[1]))) / area;
        double wc =
            (((b[0] - a[0]) * (at[1] - a[1])) - ((at[0] - a[0]) * (b[1] - a[1]))) / area;
        double wa = 1.0 - wb - wc;
        return (wa * net.Levels[triangle[0]]) +
               (wb * net.Levels[triangle[1]]) +
               (wc * net.Levels[triangle[2]]);
    }

    /// <summary>The existing private PointAtArc, reachable from this file's
    /// own crossing walk. A wrapper and not a second implementation, so a
    /// head joint's point and a bed's own point cannot disagree.</summary>
    internal static double[] PointAtArcPublic(SkinLevelCurve curve, double arc) =>
        PointAtArc(curve, arc);
```

6. [ ] Finish the engine's second half, replacing the `...` above: record each line's crossing with
   each bed, apply rule 3.3.3's insertion and termination, and build the cells.

```csharp
        // CROSSINGS. Each line's crossing with each bed is the candidate
        // head joint of that bed, recorded as a signed arc on the bed's own
        // component (rule 3.3.2). Everything from here is PER TRACED
        // COMPONENT (rule 3.3.1a): a bed is a LIST of components and not one
        // curve, so L_k, P_k, the seam-outward walk, the insertion and
        // termination tests and the parity are all taken per component,
        // each with its own length and its own seam.
        var crossings = new List<List<(double U, int Line)>>();
        for (int r = 0; r <= bands; r++)
            crossings.Add(new List<(double, int)>());
        for (int at = 0; at < lines.Count; at++)
        {
            double[][] line = lines[at].Points;
            for (int r = 0; r <= bands; r++)
            {
                double level = r == 0
                    ? intervals[0].Low
                    : r == bands
                        ? intervals[bands - 1].High
                        : intervals[r].Low;
                IReadOnlyList<SkinLevelCurve> bed =
                    resolved.Traced[levelIndex[level]];
                if (bed.Count == 0)
                    continue;
                for (int point = 0; point + 1 < line.Length; point++)
                {
                    // A crossing lands between two polyline points whose
                    // interpolated field values straddle the level; the
                    // point is taken on the bed itself, by exact plan
                    // projection, so a head joint LIES on its bed.
                    double[] a = line[point];
                    double[] b = line[point + 1];
                    double la = LevelAt(net, a);
                    double lb = LevelAt(net, b);
                    if (!((la < level && lb >= level) ||
                          (lb < level && la >= level)))
                    {
                        continue;
                    }
                    double t = (level - la) / (lb - la);
                    double[] on = Lerp(a, b, t);
                    SkinLevelCurve component = bed[0];
                    double best = double.PositiveInfinity;
                    foreach (SkinLevelCurve candidate in bed)
                    {
                        double arc = NearestArcInPlan(candidate, on);
                        double[] near = PointAtArcPublic(candidate, arc);
                        double distance =
                            (near[0] - on[0]) * (near[0] - on[0]) +
                            (near[1] - on[1]) * (near[1] - on[1]);
                        if (distance < best)
                        {
                            best = distance;
                            component = candidate;
                        }
                    }
                    crossings[r].Add((
                        NearestArcInPlan(component, on) - component.Seam,
                        at));
                    break;
                }
            }
        }
```

   with `LevelAt(SkinNet, double[])`, the piecewise-linear interpolant of rule 1.4.4 evaluated at a
   point by locating its face in plan and taking the barycentric combination of the face's three
   Levels, and `PointAtArcPublic` as a thin internal wrapper on the existing private `PointAtArc`.

7. [ ] Apply rule 3.3.3 and rule 3.3.4, then build the cells:

```csharp
        // INSERTION AND TERMINATION (rule 3.3.3), which is the difference
        // between a force-aligned pattern and a mess. On bed k let
        // Pk = Lk / max(1, round(Lk / (S / 2))) be that bed's own target
        // half-pitch. Walk the bed's crossings seam-outward. Where two
        // consecutive crossings are more than 1.5 Pk apart, INSERT a new
        // streamline at the midpoint of that gap and advect it upward from
        // there; where two are less than 0.5 Pk apart, TERMINATE the later
        // of the two at bed k. Both events are counted and both are what a
        // mason does when he adds or drops a course.
        //
        // PARITY IS ANCHORED ON THE STREAMLINE AND NEVER ON A BED'S
        // CROSSING INDEX (rule 3.3.4). A line inserted takes the parity
        // opposite to both of its neighbours, which is always well defined
        // because the two crossings bracketing a gap of more than 1.5 P_k
        // carry opposite parities; a line terminated retires its parity with
        // it. Anchoring on the index instead would make a head joint stop
        // running along one streamline between its own two beds, which is
        // the single property rule 3.2.2 and check 12.3(b) exist for.
        int inserted = 0;
        int terminated = 0;
        var retired = new HashSet<int>();
        for (int r = 0; r <= bands; r++)
        {
            IReadOnlyList<SkinLevelCurve> bed =
                resolved.Traced[levelIndex[
                    r == 0 ? intervals[0].Low
                    : r == bands ? intervals[bands - 1].High
                    : intervals[r].Low]];
            if (bed.Count == 0)
                continue;
            double target = bed[0].Length /
                Math.Max(1.0, Math.Round(bed[0].Length / (size / 2.0)));
            List<(double U, int Line)> here = crossings[r]
                .Where(item => !retired.Contains(item.Line))
                .OrderBy(item => item.U)
                .ToList();
            for (int at = 1; at < here.Count; at++)
            {
                double gap = here[at].U - here[at - 1].U;
                if (gap < 0.5 * target)
                {
                    retired.Add(here[at].Line);
                    terminated++;
                }
                else if (gap > 1.5 * target)
                {
                    double middle = (here[at].U + here[at - 1].U) / 2.0;
                    double[] from = PointAt(bed[0], middle);
                    int face = FaceUnder(net, from);
                    if (face < 0)
                        continue;
                    double[][] line = SkinFlowField.Streamline(
                        net, directions, neighbours, from, face,
                        AscentHint(net, face), clearance, accepted);
                    if (line.Length < 2)
                        continue;
                    accepted.Add(line);
                    int parity = 1 - lines[here[at].Line].Parity;
                    lines.Add((line, parity));
                    crossings[r].Add((middle, lines.Count - 1));
                    inserted++;
                }
            }
        }
```

   Then the cell build. Every assertion in step 1 measures this loop, so it is written out rather
   than described: the piece-length ratio is its spans, the bond is its parity, the odd cells are its
   three- and five-sided answers, and check 12.3(b) is its two `Run` chains and its two streamline
   segments.

```csharp
        var cells = new List<SkinCell>();
        var flowLines = new List<double[][]>();
        var bedCurves = new List<double[][]>();
        int fiveSided = 0;
        int sevenSided = 0;
        int mergedPieces = 0;
        int mergedShortKept = 0;
        int mergedStillShort = 0;
        foreach ((double[][] points, int _) in lines)
            flowLines.Add(points);
        for (int r = 0; r < bands; r++)
        {
            IReadOnlyList<SkinLevelCurve> lowerBed =
                resolved.Traced[levelIndex[intervals[r].Low]];
            IReadOnlyList<SkinLevelCurve> upperBed = resolved.Traced[levelIndex[
                r == bands - 1 ? intervals[r].High : intervals[r + 1].Low]];
            if (lowerBed.Count == 0 || upperBed.Count == 0)
                continue;
            foreach (SkinLevelCurve component in lowerBed)
                bedCurves.Add(component.Points.ToArray());

            // THE PAIRING IS BY LINE AND NOT BY INDEX (rule 3.3.4). A course
            // takes the crossings of the lines whose parity is r mod 2, and a
            // piece runs between two ADJACENT such crossings, so its two head
            // joints are two whole streamlines and not two positions in a
            // sorted list. Anchoring on the index instead would let a head
            // joint stop running along one streamline between its own two
            // beds, which is the single property check 12.3(b) exists for.
            var onLower = crossings[r]
                .Where(item => lines[item.Line].Parity == (r % 2))
                .Where(item => !retired.Contains(item.Line))
                .OrderBy(item => item.U)
                .ToList();
            var onUpper = crossings[r + 1]
                .Where(item => lines[item.Line].Parity == (r % 2))
                .ToDictionary(item => item.Line, item => item.U);
            if (onLower.Count < 2)
                continue;

            // The spans, seam outward, then section 6's own merge, which
            // rule 3.3.6 inherits whole rather than reimplementing.
            var spans = new List<(double U0, double U1, bool Clipped)>();
            var spanLines = new List<(int Left, int Right)>();
            for (int at = 1; at < onLower.Count; at++)
            {
                spans.Add((onLower[at - 1].U, onLower[at].U, false));
                spanLines.Add((onLower[at - 1].Line, onLower[at].Line));
            }
            List<(double U0, double U1, bool Clipped)> keptSpans =
                MergeShortPieces(
                    spans, clampedMinPiece * size,
                    ref mergedPieces, ref mergedShortKept, ref mergedStillShort);

            foreach ((double u0, double u1, bool clipped) in keptSpans)
            {
                // The two head joints this piece actually runs between, found
                // by their own arc rather than by their place in the list, so
                // a merged span picks up the outer two lines and not the two
                // it started with.
                int leftLine = NearestCrossingLine(onLower, u0);
                int rightLine = NearestCrossingLine(onLower, u1);
                if (leftLine < 0 || rightLine < 0)
                    continue;

                // FOUR CHAINS, in the order rule 5.2.1 records them: the
                // lower bed's Run between the two joints, the right-hand
                // streamline segment upward, the upper bed's Run reversed,
                // and the left-hand streamline segment downward.
                double[][] lowerRun = Run(
                    lowerBed[0], u0 + lowerBed[0].Seam, u1 + lowerBed[0].Seam);
                bool rightReaches = onUpper.TryGetValue(rightLine, out double rightTop);
                bool leftReaches = onUpper.TryGetValue(leftLine, out double leftTop);
                double[][] upperRun = rightReaches && leftReaches
                    ? Run(upperBed[0], rightTop + upperBed[0].Seam, leftTop + upperBed[0].Seam)
                    : Array.Empty<double[]>();
                double[][] rightSegment = SegmentBetween(
                    lines[rightLine].Points, LevelAt(net, PointAt(lowerBed[0], u0)), intervals, r, net);
                double[][] leftSegment = SegmentBetween(
                    lines[leftLine].Points, LevelAt(net, PointAt(lowerBed[0], u1)), intervals, r, net);

                var outline = new List<double[]>();
                outline.AddRange(lowerRun);
                outline.AddRange(rightSegment);
                outline.AddRange(upperRun);
                outline.AddRange(leftSegment);
                List<double[]> ring = Dedupe(outline);
                if (ring.Count < 3)
                    continue;

                // RULE 3.3.5. A cell gains or loses a side only where a line
                // BEGINS OR ENDS within its own band: a line that does not
                // reach the upper bed closes the cell against the upper bed's
                // own arc and the cell comes back with three or five setout
                // corners rather than four. They are the pattern's honest
                // response to a flow that converges, and refusing them would
                // put a hole where a mason puts a closer.
                int setout = 4;
                if (!rightReaches || !leftReaches)
                    setout = 3;
                else if (InsertedWithin(lines, crossings, r, leftLine, rightLine))
                    setout = 5;
                if (setout == 5)
                    fiveSided++;
                else if (setout == 3)
                    sevenSided++;

                cells.Add(new SkinCell(
                    r, ring, clipped, u0, u1, false, setout,
                    new[] { lowerRun, rightSegment, upperRun, leftSegment }));
            }
        }
        List<SkinCell> valid = KeepValidPlans(
            cells, out int degenerateDropped, out int overlapDropped,
            out int degenerateCentroidsSkipped);
```

   `NearestCrossingLine` returns the line whose crossing arc is nearest a given arc, within a
   thousandth of the bed's own pitch, or -1; `SegmentBetween` clips a streamline polyline to the two
   field values bounding band r, using `LevelAt` on its own points and interpolating the two ends
   exactly, so the segment starts and finishes ON the two beds; and `InsertedWithin` reports whether a
   line was inserted or terminated between the two named lines within this band, which is what turns
   a four-cornered cell into a five-cornered one. The `sevenSided` counter takes the three-cornered
   terminations for now, and the name is the record's rather than the geometry's; rule 4.3's five and
   seven belong to the honeycomb and section 3's own odd cells are three and five, which check
   12.3(e) states in those words.

   `SkinCell` already carries `int SetoutCorners`, which TASK 23 added for check 12.4(d) and which
   this engine fills with 3, 4 or 5; and it gains `IReadOnlyList<IReadOnlyList<double[]>>? Sections`
   HERE, which check 12.3(b) reads immediately above and which TASK 29 then reads for the Brep route.
   Task 29's Interfaces line naming that member is the same member and not a second one; when Task 29
   is reached it fills it for `Courses` and `Hexagonal` too, a courses cell passing its two runs and a
   hexagon its three, and a cap passing null so the component fans it.

8. [ ] Build and run the harness. Every bar of `ValidateSkinForceAligned` must pass, and the ratio
   printed beside it is the number check 12.3(d) exists for.

9. [ ] Scan for clash files and commit.

```powershell
git add "plugin/native_v02/Components/SkinFlowField.cs" "plugin/native_v02/Components/SkinPatterns.cs" "tests/native_smoke/Program.cs"
git commit -m "feat(skin): the force-aligned pattern is native, with streamlined head joints"
```

---

### Task 27: the worker round trip goes

**Files:**
- Modify: plugin/native_v02/Components/SkinComponents.cs:183-236 (`SolveInstance`'s dispatch),
  :397-507 (`SolveForceAligned`), :643-943 (`ComputeAsync`, `RequestPatternAsync`, `DecodeResponse`,
  `FormatDiagnostics` and their helpers)
- Test: tests/native_smoke/Program.cs, new `ValidateSkinNoWorkerDispatch` plus its entry in `Run`

**Interfaces:**
- Consumes: `SkinPatterns.ForceAligned` from Task 26.
- Produces: a Skin component with no worker dispatch at all.

Rule 3.2.4: pattern 2 becomes native and synchronous like the other two, so the dispatch and the
decode are deleted. `pattern.armadillo_dual` stays in the Python package for the acceptance tests and
stops being reachable from the canvas.

1. [ ] Add the check:

```csharp
    /// <summary>
    /// Check 12.3(f). The pattern computes SYNCHRONOUSLY: no worker command
    /// named pattern.armadillo_dual is reachable from the component. Read
    /// off the compiled assembly's own string constants, the
    /// ValidateExportDefaultTessellation convention of reading rather than
    /// running.
    /// </summary>
    private static void ValidateSkinNoWorkerDispatch(Assembly plugin)
    {
        Type skin = RequireComponentType(plugin, "SkinComponent");
        foreach (MethodInfo method in skin.GetMethods(
                     BindingFlags.Public | BindingFlags.NonPublic |
                     BindingFlags.Instance | BindingFlags.Static))
        {
            if (method.Name.Contains(
                    "ArmadilloDual", StringComparison.Ordinal) ||
                method.Name.Contains(
                    "RequestPattern", StringComparison.Ordinal) ||
                method.Name.Contains(
                    "DecodeResponse", StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    "Pattern 2 is NATIVE and synchronous like the other two " +
                    "(rule 3.2.4), so the worker dispatch and the decode " +
                    $"are deleted; '{method.Name}' is still here.");
            }
        }
        if (skin.GetInterface("IGH_TaskCapableComponent") is not null ||
            skin.BaseType?.Name.Contains(
                "TaskCapable", StringComparison.Ordinal) == true)
        {
            throw new InvalidOperationException(
                "With no pattern dispatching a worker, Skin is not a " +
                "task-capable component at all, and the NoTask placeholder " +
                "that kept TaskList's iteration indices lined up has " +
                "nothing left to keep.");
        }
    }
```

2. [ ] Wire it into `Run` after the force-aligned block, with a PASS line saying the round trip is
   gone and the pattern computes on the solve thread.

3. [ ] Build and run the harness. It must fail naming `RequestPatternAsync`.

4. [ ] Delete the dispatch. In SkinComponents.cs, remove the whole `InPreSolve` branch of
   `SolveInstance` (SkinComponents.cs:185-214), `NoTask` (:238-253), `SolveForceAligned` (:397-507),
   `ComputeAsync` (:643-677), `RequestPatternAsync` (:679-731), `DecodeResponse` (:733-782),
   `FormatDiagnostics` (:784-838) and the JSON helpers `PointList`, `RequiredArray`, `RequiredObject`,
   `RequiredInt`, `FiniteDouble`, `OptionalString`, `OptionalInt` and `ArrayLength` (:840-943), which
   have no other caller in this file. Change the class declaration to the plain native base, drop the
   `ArmadilloDualTaskResult` and `ArmadilloDualCellData` usings and types where they are Skin's alone,
   and reduce `SolveInstance` to:

```csharp
    protected override void SolveInstance(IGH_DataAccess data)
    {
        if (!TryReadInputs(
                data,
                out ResultDto? result,
                out int pattern,
                out double size,
                out double courseHeight,
                out double minPiece))
        {
            return;
        }
        SolveNative(
            data, result!, pattern, size, courseHeight, minPiece);
    }
```

   `TryReadInputs`' extra `minPiece` out parameter is Task 30's; until then, call the four-parameter
   form and pass `1.0 / 3.0`.

5. [ ] Point `SolveNative` at the third engine, replacing SkinComponents.cs:287-289:

```csharp
            SkinPatternResult generated = pattern switch
            {
                0 => SkinPatterns.Courses(
                    net, size, courseHeight, minPiece),
                1 => SkinPatterns.Hexagonal(net, size, courseHeight),
                _ => SkinPatterns.ForceAligned(
                    net, size, courseHeight, minPiece)
            };
```

6. [ ] Build and run the harness. The GUID pin, the dead Armadillo Dual GUID, the Pattern value list,
   the component count and the icon map all stay as they are (check 12.10(c)), so nothing there moves.

7. [ ] Scan for clash files and commit.

```powershell
git add "plugin/native_v02/Components/SkinComponents.cs" "tests/native_smoke/Program.cs"
git commit -m "feat(skin): pattern 2 computes on the solve thread and the worker round trip goes"
```

### Task 28: the Brep route, proved before it is built on

**Files:**
- Create: scripts/rhino_skin_surface.py
- Modify: tests/native_smoke/Program.cs, new `ValidateSkinBrepApi` plus its entry in `Run`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: the proof, and a build-time guarantee that the two RhinoCommon members Task 29 calls
  exist with the signatures it calls them by.

Check 12.5(a) asks for the Brep route to be proved FIRST, before anything else in section 5 is built,
because every rule in 5.2 depends on RhinoCommon behaviour this repository has never exercised: there
is no `Brep`, `NurbsSurface`, `CreateEdgeSurface`, `CreatePatch` or `CreatePlanarBreps` anywhere in
it, and a Surface output would be the plugin's first Brep.

The check cannot run in native_smoke, and the honest reason is the harness's own: it loads
RhinoCommon's managed assembly but has no native core, which is why
`ValidateExportDefaultTessellation` reads the default tessellation rather than running it. A Brep
built without that core is not a Brep. So the proof is split. The API SHAPE is asserted here, by
reflection, so a wrong signature fails the gate at once; the BEHAVIOUR is proved once inside Rhino, by
the script this task writes, and rule 5.2's own sentence stands until it is: every statement in
section 5.2 is an assertion about the API and must be adjusted if the script says otherwise.

1. [ ] Add the API-shape check:

```csharp
    /// <summary>
    /// Check 12.5(a), the half this process can take. Brep.CreateFromLoft's
    /// signature is asserted by reflection against the loaded RhinoCommon,
    /// so a wrong argument list fails here rather than at the first solve in
    /// Rhino. The behaviour is proved by scripts/rhino_skin_surface.py,
    /// which runs inside Rhino, because a Brep needs the native core this
    /// harness deliberately does not launch.
    /// </summary>
    private static void ValidateSkinBrepApi(Assembly plugin)
    {
        Assembly rhinoCommon = AppDomain.CurrentDomain
            .GetAssemblies()
            .FirstOrDefault(item =>
                item.GetName().Name == "RhinoCommon")
            ?? throw new InvalidOperationException(
                "RhinoCommon is not loaded, so the Brep route cannot be " +
                "checked at all.");
        Type brep = rhinoCommon.GetType("Rhino.Geometry.Brep", true)!;
        MethodInfo? loft = brep.GetMethod(
            "CreateFromLoft",
            BindingFlags.Public | BindingFlags.Static);
        if (loft is null || loft.ReturnType != brep.MakeArrayType())
        {
            throw new InvalidOperationException(
                "Rule 5.2.3 lofts the cell's own RUNS, so " +
                "Brep.CreateFromLoft must exist and return a Brep array; " +
                "if it does not, section 5.2 is wrong about the API and " +
                "the rules there are adjusted before anything is built on " +
                "them.");
        }
        Type? loftType = rhinoCommon.GetType("Rhino.Geometry.LoftType", true);
        if (loftType is null ||
            !Enum.GetNames(loftType).Contains("Straight"))
        {
            throw new InvalidOperationException(
                "Routes (a) and (b) loft with LoftType.Straight and no " +
                "closing; the enum member must exist.");
        }
        if (brep.GetMethod(
                "CreateFromCornerPoints",
                BindingFlags.Public | BindingFlags.Static) is null)
        {
            // Not used, and its absence is not a failure; named here only
            // so that a reader of rule 5.2.2 can see the refusal was a
            // choice and not an omission.
        }
    }
```

2. [ ] Wire it into `Run` before every other Surface check, with a PASS line saying the API shape is
   right and the behaviour is proved by the Rhino-side script.

3. [ ] Write scripts/rhino_skin_surface.py, to be run once inside Rhino from the Python editor:

```python
"""Prove the Brep route section 5 is built on (check 12.5(a)).

Run inside Rhino 8. It builds one loft from two known polylines and reports
whether a valid single-face Brep comes back, then repeats the deterministic
fan of rule 5.2.3(d) for a cap-shaped loop. Nothing here touches the plugin:
it proves the API, which is the only part of section 5 this repository has
never exercised.
"""

import Rhino
import Rhino.Geometry as rg


def polyline(points):
    return rg.PolylineCurve([rg.Point3d(*point) for point in points])


def loft_two_runs():
    lower = polyline([(0, 0, 0), (1, 0, 0.1), (2, 0, 0.15)])
    upper = polyline([(0, 1, 0.4), (1, 1, 0.5), (2, 1, 0.55)])
    breps = rg.Brep.CreateFromLoft(
        [lower, upper],
        rg.Point3d.Unset,
        rg.Point3d.Unset,
        rg.LoftType.Straight,
        False,
    )
    if not breps or len(breps) != 1:
        return "FAIL: CreateFromLoft returned %r" % (breps,)
    brep = breps[0]
    if not brep.IsValid:
        return "FAIL: the loft came back invalid"
    if brep.Faces.Count != 1:
        return "FAIL: %d faces, and rule 5.2.3(a) promises one" % (
            brep.Faces.Count,
        )
    return "PASS: a two-section loft is one valid single-face Brep"


def fan_a_cap():
    loop = [
        (0.5, 0.0, 1.0), (0.35, 0.35, 1.0), (0.0, 0.5, 1.0),
        (-0.35, 0.35, 1.0), (-0.5, 0.0, 1.0), (-0.35, -0.35, 1.0),
        (0.0, -0.5, 1.0), (0.35, -0.35, 1.0),
    ]
    apex = rg.Point3d(0.0, 0.0, 1.2)
    faces = []
    for at in range(len(loop)):
        a = rg.Point3d(*loop[at])
        b = rg.Point3d(*loop[(at + 1) % len(loop)])
        faces.append(rg.Brep.CreateFromCornerPoints(a, b, apex, 1e-9))
    joined = rg.Brep.JoinBreps(faces, 1e-9)
    if not joined or len(joined) != 1:
        return "FAIL: the fan did not join into one Brep"
    return "PASS: a cap fans into one joined Brep of %d faces" % (
        joined[0].Faces.Count,
    )


print(loft_two_runs())
print(fan_a_cap())
```

4. [ ] Build and run the harness. The API PASS line must appear.

5. [ ] Ask Param to run scripts/rhino_skin_surface.py once in Rhino and report the two lines. Until he
   does, Task 29 is written to rule 5.2 as it stands; if either line fails, rule 5.2's own sentence
   applies and the route is adjusted before Task 29 is built.

6. [ ] Scan for clash files and commit.

```powershell
git add "scripts/rhino_skin_surface.py" "tests/native_smoke/Program.cs"
git commit -m "test(skin): prove the Brep route before section 5 is built on it"
```

---

### Task 29: the Surface output

**Files:**
- Modify: plugin/native_v02/Components/SkinPatterns.cs (`SkinCell` gains `Sections`, and the three
  engines fill it), plugin/native_v02/Components/SkinComponents.cs (the Brep build and the second
  output tree)
- Test: tests/native_smoke/Program.cs, new `ValidateSkinSurfaceSections` plus its entry in `Run`

**Interfaces:**
- Consumes: `BandCell`, the honeycomb's outline builder, the cap emission from Tasks 18 and 22.
- Produces: `SkinComponent.CellSurface(SkinCell cell)` returning `Brep?`; the component's
  `surfaceFailed` count; and `Sections` FILLED on the courses and honeycomb cells. The member itself,
  `SkinCell(..., bool Cap = false, int SetoutCorners = 6, IReadOnlyList<IReadOnlyList<double[]>>?
  Sections = null)`, already exists by this point: Task 23 added `SetoutCorners` for check 12.4(d)
  and Task 26 added `Sections` because check 12.3(b) measures the force-aligned cell's own four
  chains through it. This task fills it for the other two patterns and does not add it a second time.
  `SkinCells` is NOT widened again either: no check measures the sections through it, and this
  method's own `SectionCount` local reads them off the reflected cell directly.

Rule 5.2.1: the surface is derived from the two RUNS the cell was built from, never re-derived from
the finished closed polyline. Both runs still exist separately inside `BandCell` before they are
concatenated, and a ruled surface between them is the cell's own surface; recovering four chains from
the concatenated ring afterwards means re-detecting the joint corners, which `Dedupe` has already made
ambiguous. So the engine RECORDS the sections and the component lofts them.

The split follows rule 5.2.4: construction happens on the SOLVE thread and only there, beside
`ClosedOutlineCurve`. Nothing in SkinPatterns.cs may reference RhinoCommon; that is the rule the
harness's whole ability to measure the engine rests on. This task therefore measures the SECTIONS in
native_smoke and leaves the Brep build to the Rhino-side script of Task 28, extended here.

1. [ ] Add the sections check:

```csharp
    /// <summary>
    /// The engine half of section 5. Every cell carries the sections its own
    /// route lofts: a COURSES or FORCE-ALIGNED cell two, the lower run and
    /// the upper run, both in the same direction (route 5.2.3(a) and (c)); a
    /// HEXAGON three, the bottom run, the two-point section from the left
    /// side vertex to the right, and the top run (route (b)); a CAP none, so
    /// the component fans it (route (d)); and any other corner count none,
    /// so the component fans that too (route (e)). Route (e) is not optional
    /// tidying: rule 3.3.5 requires three- and five-sided force-aligned
    /// cells and rule 4.3 requires five- and seven-sided honeycomb cells,
    /// and without it check 12.4(d) and check 12.5(b) could not both pass.
    /// </summary>
    private static void ValidateSkinSurfaceSections(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        Type edgeType = RequireComponentType(plugin, "SkinNetEdge");
        MethodInfo courses = RequirePublicStatic(patterns, "Courses");
        MethodInfo hexagonal = RequirePublicStatic(patterns, "Hexagonal");
        (double[][] vertices, int[][] faces, int[] rim) = SkinHemisphereNet();
        object net = SkinNetWith(
            netType, edgeType, vertices, faces, rim,
            Array.Empty<(int, int, double)>());

        static int SectionCount(object cell)
        {
            object? sections = cell.GetType()
                .GetProperty("Sections")!.GetValue(cell);
            return sections is null ? 0 : ((IList)sections).Count;
        }
        object built = courses.Invoke(
            null, new object[] { net, 0.6, 0.35, 1.0 / 3.0 })!;
        IList cells = (IList)built.GetType()
            .GetProperty("Cells")!.GetValue(built)!;
        foreach (object? item in cells)
        {
            object cell = item!;
            bool cap = Reading<bool>(cell, "Cap");
            int sections = SectionCount(cell);
            if (cap && sections != 0)
            {
                throw new InvalidOperationException(
                    "A CAP is the one cell that cannot be a single face: it " +
                    "is emitted as a Brep of triangular faces fanned from " +
                    "the net vertex of greatest field value inside its loop " +
                    "to each segment of the loop, joined (route 5.2.3(d)), " +
                    "so it carries no loft sections. A WEDGE of a split cap " +
                    "is NOT a cap for this purpose: by rule 2.6.4(a) it is " +
                    "an ordinary band cell and takes route (a).");
            }
            if (!cap && sections != 2)
            {
                throw new InvalidOperationException(
                    "A courses cell is a loft of TWO sections, the lower " +
                    $"run and the upper run (route 5.2.3(a)); got {sections}.");
            }
        }
        object honeycomb = hexagonal.Invoke(
            null, new object[] { net, 0.6, 0.35 })!;
        foreach (object? item in (IList)honeycomb.GetType()
                     .GetProperty("Cells")!.GetValue(honeycomb)!)
        {
            object cell = item!;
            int corners = ((IList)cell.GetType()
                .GetProperty("Outline")!.GetValue(cell)!).Count;
            int sections = SectionCount(cell);
            if (sections != 0 && sections != 3)
            {
                throw new InvalidOperationException(
                    "A hexagon is a loft of THREE sections (route " +
                    $"5.2.3(b)); a cell of {corners} corners carries " +
                    $"{sections}, and a cell whose corner count its own " +
                    "route does not fit carries NONE and takes the " +
                    "deterministic fan of route (e).");
            }
        }
    }
```

2. [ ] Wire it into `Run` after the Brep API block, with a PASS line naming the four routes.

3. [ ] Build and run the harness. It must fail: `SkinCell` has no `Sections`.

4. [ ] Add the member and fill it. `SkinCell` becomes:

```csharp
internal sealed record SkinCell(
    int Course,
    IReadOnlyList<double[]> Outline,
    bool Clipped,
    double U0,
    double U1,
    bool Cap = false,
    IReadOnlyList<IReadOnlyList<double[]>>? Sections = null);
```

   `BandCell`'s return becomes:

```csharp
        List<double[]> lower = Run(
            lowerCurve, u0 * lowerRatio, u1 * lowerRatio);
        List<double[]> upper = Run(
            upperCurve, u0 * upperRatio, u1 * upperRatio);
        var outline = new List<double[]>(lower);
        List<double[]> back = new List<double[]>(upper);
        back.Reverse();
        outline.AddRange(back);
        // The surface is derived from the two RUNS the cell was built from
        // and never re-derived from the finished closed polyline (rule
        // 5.2.1): recovering four chains from the concatenated ring
        // afterwards means re-detecting the joint corners, which Dedupe has
        // already made ambiguous.
        return new SkinCell(
            course, Dedupe(outline), clipped, u0, u1, false,
            new[] { (IReadOnlyList<double[]>)lower, upper });
```

   and the honeycomb's cell gains its three sections, the bottom run, the two-point section from the
   left side vertex to the right, and the top run, in the same order the outline is built from, but
   ONLY where the cell has exactly six corners of setout; a five- or seven-sided cell passes `null`
   and takes route (e).

5. [ ] Build the Breps in SkinComponents.cs, beside `ClosedOutlineCurve`:

```csharp
    /// <summary>
    /// One cell's surface (spec section 5). On the SOLVE thread and only
    /// here, the split the component already keeps: nothing in
    /// SkinPatterns.cs may reference RhinoCommon.
    ///
    /// A cell carrying two sections is a straight, unclosed loft of them,
    /// which is route 5.2.3(a) and (c); three sections is route (b); no
    /// sections is the deterministic fan of routes (d) and (e), from the
    /// cell's own interior point lifted onto the surface, to each segment of
    /// the outline, joined. Brep.CreatePatch is NOT used: it is a fitting
    /// solver, its output is not the surface the cell describes, and a
    /// deterministic fan is worth more here than a smooth guess.
    /// </summary>
    private static Brep? CellSurface(SkinCell cell, SkinNet net)
    {
        if (cell.Sections is not null && cell.Sections.Count >= 2)
        {
            var sections = new List<Curve>(cell.Sections.Count);
            foreach (IReadOnlyList<double[]> section in cell.Sections)
            {
                if (section.Count < 2)
                    return null;
                sections.Add(OpenOutlineCurve(section));
            }
            Brep[] lofted = Brep.CreateFromLoft(
                sections,
                Point3d.Unset,
                Point3d.Unset,
                LoftType.Straight,
                false);
            return lofted is { Length: 1 } && lofted[0].IsValid
                ? lofted[0]
                : null;
        }
        double[]? inside = SkinPatterns.PlanInteriorPoint(cell.Outline);
        if (inside is null)
            return null;
        double[]? apex = SkinPatterns.LiftPlanPoint(net, inside[0], inside[1]);
        if (apex is null)
            return null;
        var pieces = new List<Brep>(cell.Outline.Count);
        for (int at = 0; at < cell.Outline.Count; at++)
        {
            double[] a = cell.Outline[at];
            double[] b = cell.Outline[(at + 1) % cell.Outline.Count];
            Brep? piece = Brep.CreateFromCornerPoints(
                new Point3d(a[0], a[1], a[2]),
                new Point3d(b[0], b[1], b[2]),
                new Point3d(apex[0], apex[1], apex[2]),
                1.0e-9);
            if (piece is null)
                return null;
            pieces.Add(piece);
        }
        Brep[] joined = Brep.JoinBreps(pieces, 1.0e-9);
        return joined is { Length: 1 } && joined[0].IsValid
            ? joined[0]
            : null;
    }
```

   with, in SkinPatterns.cs, the lift the fan needs:

```csharp
    /// <summary>A plan point lifted onto the surface: the net face
    /// containing it in plan, evaluated at that point on the face's own
    /// plane. Null where no face contains it.</summary>
    public static double[]? LiftPlanPoint(SkinNet net, double x, double y)
    {
        foreach (int[] triangle in net.Faces)
        {
            double[] a = net.Vertices[triangle[0]];
            double[] b = net.Vertices[triangle[1]];
            double[] c = net.Vertices[triangle[2]];
            if (!PlanContains(x, y, new[] { a, b, c }))
                continue;
            double twice =
                (b[0] - a[0]) * (c[1] - a[1]) -
                (c[0] - a[0]) * (b[1] - a[1]);
            if (Math.Abs(twice) <= 1.0e-18)
                continue;
            double alpha =
                ((b[0] - x) * (c[1] - y) - (c[0] - x) * (b[1] - y)) / twice;
            double beta =
                ((c[0] - x) * (a[1] - y) - (a[0] - x) * (c[1] - y)) / twice;
            double gamma = 1.0 - alpha - beta;
            return new[]
            {
                x,
                y,
                alpha * a[2] + beta * b[2] + gamma * c[2]
            };
        }
        return null;
    }
```

6. [ ] Emit the second tree in `SolveNative`, beside the Cells tree, aligned BRANCH FOR BRANCH and
   ITEM FOR ITEM, with a NULL where a cell will not close into a Brep. The item is never dropped:
   dropping it would silently misalign every downstream index against the Cells tree, which is the one
   promise this output exists to keep. An empty course survives as an EMPTY BRANCH in both trees,
   because `OutputTree` creates every path before filling it and the component pre-creates one branch
   per course:

```csharp
            var surfaceBranches = new List<List<Brep?>>();
            for (int course = 0; course < generated.CourseCount; course++)
                surfaceBranches.Add(new List<Brep?>());
            int surfaceFailed = 0;
            int firstFailedCourse = -1;
            foreach (SkinCell cell in generated.Cells)
            {
                int course = Math.Min(
                    Math.Max(cell.Course, 0),
                    Math.Max(generated.CourseCount - 1, 0));
                cellBranches[course].Add(ClosedOutlineCurve(cell.Outline));
                Brep? surface = CellSurface(cell, net);
                surfaceBranches[course].Add(surface);
                if (surface is null)
                {
                    surfaceFailed++;
                    if (firstFailedCourse < 0)
                        firstFailedCourse = course;
                }
            }
            if (surfaceFailed > 0)
            {
                // A failure is a defect in this engine, not a fact about the
                // geometry, so it is counted, reported and raised.
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    $"{surfaceFailed} cell" +
                    (surfaceFailed == 1 ? "" : "s") +
                    " would not close into a surface, the first at course " +
                    $"{firstFailedCourse}; those slots carry a NULL so the " +
                    "Surface tree stays aligned with Cells item for item.");
            }
```

7. [ ] Extend scripts/rhino_skin_surface.py with the four behavioural checks the harness cannot take,
   12.5(b) to 12.5(e): every cell yields a Brep on every fixture; each Brep's area is within 2 per
   cent of its cell's plan area divided by the cosine of the cell's mean surface slope; the branch
   count, branch paths and per-branch item counts are identical between Cells and Surface, including
   on a fixture with an empty course and on the split-cap fixture, whose top branch holds W + 1 items
   in both trees, each wedge coming back as a single-face Brep and only the centre disc as a
   multi-face fan; and an injected degenerate cell produces a NULL in the Surface slot rather than a
   missing item.

8. [ ] Build and run the harness. The sections PASS line must appear, and every other line must stand.

9. [ ] Scan for clash files and commit.

```powershell
git add "plugin/native_v02/Components/SkinPatterns.cs" "plugin/native_v02/Components/SkinComponents.cs" "scripts/rhino_skin_surface.py" "tests/native_smoke/Program.cs"
git commit -m "feat(skin): every cell carries its own surface, aligned item for item with Cells"
```

---

### Task 30: Skin's ports after the wave

**Files:**
- Modify: plugin/native_v02/Components/SkinComponents.cs:98-181 (both registrations), :183-395
  (`SolveNative`'s outputs, chin, Remark), :554-629 (`TryReadInputs`)
- Test: tests/native_smoke/Program.cs:100-102 (the port pin) and new `ValidateSkinPortText`

**Interfaces:**
- Consumes: `SkinPatternResult` in full, `CellSurface` from Task 29.
- Produces: Skin's final surface: inputs {Result, Pattern, Size, Course Height, Min Piece}, outputs
  {Cells, Surface}.

THE OUTPUT LIST IS WRITTEN TO THE SPEC'S STATED DEFAULT, which is TWO outputs. Rule 9.4.1 marks the
RES output as the controller's ruling and not Param's, his own sentence asked for a removal only, and
rule 9.1's second branch is "literally what his own sentence asked for". Section 13.2 item 1 is what
would change it: if he takes the RES output, this task additionally builds it with Skin's own
`CloneResult`, which reattaches RawWire after the deep clone (rule 9.4.3), writes rule 9.3.3's twelve
entries into it with `ResultDiagnostics.Replace(result, "Skin", entries)`, puts it at output index 0,
and check 12.10(a)'s output half becomes {Result, Cells, Surface}.

1. [ ] Update the port pin at Program.cs:100-102 and add the port-text check:

```csharp
                ["Ananke.COMPAS.Native.Components.SkinComponent"] = (
                    new[]
                    {
                        "Result", "Pattern", "Size", "Course Height",
                        "Min Piece"
                    },
                    new[] { "Cells", "Surface" }),
```

```csharp
    /// <summary>
    /// Check 12.7(c), which is the operative half of Param's ruling of
    /// 2026-09-01 and therefore a check and not a nicety. He made the
    /// seam-outward ruling believing it fed the studio's build sequence; he
    /// was shown that tessellation.py:473 re-sorts every tessellation by
    /// course and by each cell's angle on import, so the order never reaches
    /// the studio, and that it does still decide which cell survives an
    /// overlap. He kept the order on that basis. What does not survive is
    /// the sentence on the port claiming the order is the studio's build
    /// sequence.
    /// </summary>
    private static void ValidateSkinPortText(Assembly plugin)
    {
        Type skinType = RequireComponentType(plugin, "SkinComponent");
        object skin = Activator.CreateInstance(skinType)!;
        object parameters = skinType.GetProperty("Params")!.GetValue(skin)!;
        IList outputs = (IList)parameters.GetType()
            .GetProperty("Output")!.GetValue(parameters)!;
        string CellsText()
        {
            object port = outputs[0]!;
            return (string)port.GetType()
                .GetProperty("Description")!.GetValue(port)!;
        }
        string text = CellsText();
        if (text.Contains(
                "the studio's build sequence within a run",
                StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "The false clause is GONE: the studio re-sorts every " +
                "tessellation on import, so the order in the file is " +
                "discarded the moment it is read (rule 7.5).");
        }
        if (!text.Contains("re-sorts", StringComparison.Ordinal) ||
            !text.Contains("running bond", StringComparison.Ordinal))
        {
            throw new InvalidOperationException(
                "The replacement carries its two load-bearing clauses, the " +
                "one saying the studio re-sorts on import and the one " +
                "saying the courses are a RUNNING BOND so item k of one " +
                "branch is not above item k of the next; a text that " +
                "dropped either would leave the author with a different " +
                "false belief in place of the old one.");
        }
    }
```

2. [ ] Wire `ValidateSkinPortText` into `Run` and build. It must fail on the false clause.

3. [ ] Register the fifth input, at slot 4, exactly as rule 9.5 states it: a `Param_Number`,
   `GH_ParamAccess.item`, optional, default 1/3, no unit of its own:

```csharp
        parameters.AddNumberParameter(
            "Min Piece",
            "MP",
            "The smallest piece worth laying, as a FRACTION of Size and not " +
                "a length of its own: 1/3 by default, so the minimum piece " +
                "is S / 3 and the maximum is S / MP = 3 S. A cell whose " +
                "along-course span is at or under the minimum is merged " +
                "into the shorter neighbour along its course, and a crown " +
                "cap above the maximum becomes a ring of wedges about a " +
                "smaller centre disc. Zero turns BOTH ends off, which is " +
                "the value for seeing the engine's raw output; a negative " +
                "clamps to zero and anything above 0.5 clamps to 0.5, each " +
                "with a warning naming the clamped value.",
            GH_ParamAccess.item,
            1.0 / 3.0);
        parameters[4].Optional = true;
```

4. [ ] Replace the output registration with the two ports, the Cells description being rule 7.5's
   replacement text exactly:

```csharp
        parameters.AddCurveParameter(
            "Cells",
            "C",
            "One closed polyline per cell, on the thrust surface, as a " +
                "TREE branched by COURSE (path = course, 0 up from the " +
                "bottom), which is now the ONLY carrier of the course: " +
                "Export reads the branch path. Within a branch cells run " +
                "FROM THE SEAM OUTWARD, alternating either side of it. " +
                "That order is for sequencing work on this canvas, and for " +
                "one thing more: where two cells overlap in plan the FIRST " +
                "one emitted is the one kept, so the cells nearest the " +
                "seam survive and the losses fall out at the edges of the " +
                "course. It is NOT the studio's build sequence. The studio " +
                "re-sorts every tessellation by course and then by each " +
                "cell's angle about the cut's own centre and reassigns its " +
                "own index, so the order in the file is discarded on " +
                "import. Courses are a RUNNING BOND, so cell 0 of one " +
                "course does not sit above cell 0 of the course below it " +
                "and the two courses may not even hold the same number of " +
                "cells; do not map item k of one branch against item k of " +
                "the next. Wire into Export's Cells. Do NOT graft, flatten " +
                "or regraft the wire: the branch path is the course, and a " +
                "flatten sends every cell to course 0 and every build " +
                "stage with it.",
            GH_ParamAccess.tree);
        parameters.AddBrepParameter(
            "Surface",
            "SRF",
            "One surface per cell, aligned with Cells BRANCH FOR BRANCH and " +
                "ITEM FOR ITEM: item k of branch r IS the surface of cell k " +
                "of course r. Skin's cells are non-planar many-sided rings, " +
                "and turning one of those into a face by hand is the " +
                "awkward job this output exists to spare. A cell that will " +
                "not close leaves a NULL in its slot rather than being " +
                "dropped, so the alignment holds. A crown cap comes back as " +
                "a Brep of MANY triangular faces rather than one, and so " +
                "does any cell whose corner count its pattern's own route " +
                "does not fit. Courses are a running bond, so item k of one " +
                "branch is NOT the surface sitting above item k of the " +
                "branch below; find the piece above a given piece " +
                "geometrically, by overlapping signed arc, and not by index.",
            GH_ParamAccess.tree);
```

4a. [ ] Rewrite the PATTERN input's description to carry rule 3.5.2. The rule ends "Say so on the
   port", and no other task in this plan touches that port's text: step 4 above rewrites Cells for
   rule 7.5 and step 3 writes Min Piece, and rule 3.5.2 would otherwise appear nowhere in the plan at
   all. What it asks for is three clauses, and each of them is a promise the force-aligned pattern
   would otherwise be read as making and does not keep:

```csharp
        parameters.AddIntegerParameter(
            "Pattern",
            "P",
            "Which tessellation to lay: 0 courses, 1 honeycomb, 2 " +
                "force-aligned. The force-aligned pattern's flow lines are " +
                "the MESH'S OWN EDGE DIRECTIONS weighted by member force and " +
                "averaged in doubled-angle space. They are NOT principal " +
                "stress directions, and the pattern does not claim to be " +
                "one. Because the directions are read off the form " +
                "diagram's own layout, a REMESH OF THE FORM DIAGRAM MOVES " +
                "THE JOINTS even where the surface and the forces are " +
                "unchanged. And where a face's edges carry no force at all " +
                "the direction is a DEFAULT rather than a measurement: the " +
                "face takes its own first basis vector, so the joints there " +
                "are arbitrary and not wrong. Wire a Result that carries " +
                "member forces, or pattern 2 defaults everywhere and says so " +
                "in its own diagnostics.",
            GH_ParamAccess.item,
            0);
```

   And extend `ValidateSkinPortText` to assert the three clauses are present, the same way it asserts
   "re-sorts" and "running bond" on Cells, so that a later edit cannot quietly drop one:

```csharp
        IList inputs = (IList)parameters.GetType()
            .GetProperty("Input")!.GetValue(parameters)!;
        object patternPort = inputs[1]!;
        string patternText = (string)patternPort.GetType()
            .GetProperty("Description")!.GetValue(patternPort)!;
        foreach (string clause in new[]
                 {
                     "edge directions", "principal stress", "remesh",
                     "default"
                 })
        {
            if (!patternText.Contains(
                    clause, StringComparison.OrdinalIgnoreCase))
            {
                throw new InvalidOperationException(
                    "Rule 3.5.2 ends \"Say so on the port\", and the three " +
                    "clauses it names are load-bearing: the lines are the " +
                    "mesh's own EDGE DIRECTIONS weighted by member force and " +
                    "not principal stress directions; a REMESH of the form " +
                    "diagram moves the joints; and where a face's edges " +
                    "carry no force the direction is a DEFAULT rather than a " +
                    "measurement. Any promise that the pattern follows the " +
                    "forces inherits all three, and the text has dropped " +
                    $"'{clause}'.");
            }
        }
```

   `Flowlines` (rule 9.2.1), `Diagnostics` (rule 9.2.2) and `Courses` (rule 9.2.3) are deleted. Nothing
   in the plugin reads Flowlines or Diagnostics as DATA, but the port NAMES are read twice over, by
   the ports-moved load warning at NativeComponentBase.cs:571-600 and by the harness's pin at
   Program.cs:100-102, so every saved definition raises the warning on open and the pin moves in this
   same commit.

5. [ ] Write the message chin, the Remark and the warnings. In `SolveNative`, replace the chin at
   SkinComponents.cs:385-388 with rule 9.3.1's:

```csharp
            double[] spans = generated.Cells
                .Where(cell => !cell.Cap)
                .Select(cell => cell.U1 - cell.U0)
                .ToArray();
            Message =
                $"{generated.Cells.Count} cells · " +
                $"{generated.CourseCount} courses · " +
                PatternName(pattern) +
                (spans.Length > 0
                    ? $" · piece {spans.Min():F2} to {spans.Max():F2} m"
                    : string.Empty);
```

   Min and max piece length are on the FACE of the component because they are what showed him the
   force-aligned pattern was not uniform, 0.377 m against 3.889 m, and losing them would remove the
   measurement this round exists to restore.

   Then add rule 9.3.5's single Remark, which his own sentence requires: the residual D content that
   is not a hole and does not fit the chin reaches him nowhere at all unless it is stated here.

```csharp
            var residual = new List<string>
            {
                $"Field: {generated.FieldKind} ({generated.RimVerticesUsed} " +
                $"rim vertices, {generated.RimVerticesDropped} named " +
                $"supports and {generated.ForceEdgesDropped} force edges " +
                "dropped as unmappable)",
                $"Mean piece length: {(spans.Length > 0 ? spans.Average() : 0.0):F3} m",
                $"Boundary-clipped cells: {generated.ClippedCells}",
                $"Crown caps: {generated.CapGirths.Count}" +
                (generated.CapGirths.Count > 0
                    ? " (girth " + string.Join(
                        ", ",
                        generated.CapGirths.Select(
                            girth => $"{girth:F3} m")) + "; wedges " +
                      string.Join(", ", generated.CapWedgeCounts) + ")"
                    : string.Empty),
                $"Odd cells: {generated.FiveSidedCells} five-sided, " +
                $"{generated.SevenSidedCells} seven-sided" +
                (generated.CountChangeRows.Count > 0
                    ? " (row counts change at rows " +
                      string.Join(", ", generated.CountChangeRows) + ")"
                    : string.Empty),
                $"Merged pieces: {generated.MergedPieces}"
            };
            AddRuntimeMessage(
                GH_RuntimeMessageLevel.Remark,
                string.Join("; ", residual));
```

   And add the three new Warnings rule 9.3.2 asks for beside the two the component already raises: the
   field fallback of rule 1.7.4, in those words; the unreachable-vertex Warning of rule 1.7.3; and the
   oversized-cap Warning of rule 2.6.6, naming the cap's girth against the maximum.

```csharp
            if (generated.FieldKind == "world Z" && net.Rim.Count == 0)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    "world Z: this Result names no supports, so courses " +
                    "are cut horizontally. Course Height is then a RISE " +
                    "and not a bed-to-bed spacing along the surface, so " +
                    "the courses stretch wherever the surface flattens.");
            }
            if (generated.UnreachableVertices > 0)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    $"{generated.UnreachableVertices} vertices are " +
                    "UNREACHABLE from the rim across the triangulation, so " +
                    "no cells are laid there and the skin has a hole over " +
                    "that region.");
            }
            if (generated.CapsOversized > 0)
            {
                AddRuntimeMessage(
                    GH_RuntimeMessageLevel.Warning,
                    $"{generated.CapsOversized} crown cap" +
                    (generated.CapsOversized == 1 ? " is" : "s are") +
                    " above the maximum piece size and could not be split " +
                    "into a ring of wedges, so " +
                    (generated.CapsOversized == 1 ? "it is" : "they are") +
                    " emitted WHOLE: a stone you can see and measure beats " +
                    "a hole you cannot fill. A smaller Course Height, or a " +
                    "larger Min Piece for bigger stones, is the remedy.");
            }
```

6. [ ] Read the fifth input in `TryReadInputs`, clamping by rule 6.4 with a Warning naming the clamped
   value, the discipline the CH floor already keeps. The clamp itself is extracted as an INTERNAL
   STATIC rather than written inline, for the reason Task 35 gives about the empty-branch guard: this
   harness never calls `SolveInstance`, so a rule buried inside `TryReadInputs` is a rule no fixture
   can drive, and check 12.6(e)'s second half asks for exactly that measurement:

```csharp
    /// <summary>
    /// Rule 6.4's bounds, as a static so the harness can drive them without a
    /// canvas. Anything above 0.5 clamps to 0.5, anything below 0 clamps to
    /// 0, and a value that is not finite falls back to the port default. The
    /// message is returned rather than raised, so the one arithmetic serves
    /// both the component's Warning and check 12.6(e).
    /// </summary>
    internal static double ClampMinPiece(
        double asked, out bool clamped, out string warning)
    {
        double answer =
            !double.IsFinite(asked)
                ? 1.0 / 3.0
                : Math.Min(Math.Max(asked, 0.0), 0.5);
        clamped = !double.IsFinite(asked) || asked < 0.0 || asked > 0.5;
        warning = clamped
            ? "Min Piece is a fraction of Size between 0 and 0.5; using " +
              answer.ToString("F3", CultureInfo.InvariantCulture) +
              ". Zero turns both the merge and the crown-cap split off " +
              "together, which is the only coherent reading of a single " +
              "threshold turned off."
            : string.Empty;
        return answer;
    }
```

```csharp
        data.GetData(4, ref minPieceInput);
        minPieceInput = ClampMinPiece(
            minPieceInput, out bool minPieceClamped, out string minPieceWarning);
        if (minPieceClamped && report)
            AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, minPieceWarning);
```

   A negative therefore means "off" rather than meaning a failed solve, because refusing the whole
   output over a number he can see and fix on the canvas would cost him more than the mistake did.

6a. [ ] Add check 12.6(e)'s SECOND HALF, which no fixture in Task 20 could take because the clamp
   lives on the component. Extend `ValidateSkinPortText`, or add it beside as
   `ValidateSkinMinPieceClamp`:

```csharp
        // Check 12.6(e), second half. MP at 0.9 clamps to 0.5 with a Warning,
        // and MP at -1 clamps to 0 with a Warning and behaves exactly as MP
        // at 0, which is rule 9.5's answer for a negative value. Driven on
        // the static, because this harness never calls SolveInstance and a
        // clamp written inline in TryReadInputs is a clamp nothing measures.
        MethodInfo clamp = skinType.GetMethod(
            "ClampMinPiece",
            BindingFlags.NonPublic | BindingFlags.Static)
            ?? throw new InvalidOperationException(
                "Rule 6.4's clamp is an internal static so that check " +
                "12.6(e) can drive it; it is not one.");
        double Clamped(double asked, out bool flagged, out string message)
        {
            object?[] arguments = { asked, false, string.Empty };
            double answer = (double)clamp.Invoke(null, arguments)!;
            flagged = (bool)arguments[1]!;
            message = (string)arguments[2]!;
            return answer;
        }
        foreach ((double asked, double wanted) in
                 new[] { (0.9, 0.5), (-1.0, 0.0) })
        {
            double got = Clamped(asked, out bool flagged, out string message);
            if (Math.Abs(got - wanted) > 1.0e-12)
            {
                throw new InvalidOperationException(
                    $"Min Piece {asked} clamps to {wanted} (rule 6.4); it " +
                    $"clamped to {got}.");
            }
            if (!flagged)
            {
                throw new InvalidOperationException(
                    $"A clamped Min Piece raises a WARNING; {asked} was " +
                    "clamped in silence, and an author cannot see a number " +
                    "the component quietly changed.");
            }
            if (!message.Contains(
                    wanted.ToString("F3", CultureInfo.InvariantCulture),
                    StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    "The Warning NAMES the clamped value, so the author " +
                    $"reads what the component is actually using; it said " +
                    $"'{message}'.");
            }
        }
        // And -1 behaves exactly as 0: the same value, so the same pattern.
        if (Math.Abs(Clamped(-1.0, out _, out _) - Clamped(0.0, out _, out _)) > 1.0e-12)
        {
            throw new InvalidOperationException(
                "MP at -1 clamps to 0 and behaves EXACTLY as MP at 0; a " +
                "negative means \"off\" and not a failed solve.");
        }
```

7. [ ] Move the two string pins off the component. The harness's transition-wording assertions at
   Program.cs:10136-10145 and :10345-10349 already read the ENGINE's `Diagnostics` property rather
   than a port, which is where they should have been; confirm both still read the record, since rule
   9.2.2 removes the D PORT and not the text.

8. [ ] Add check 12.10(d)'s declines half:

```csharp
        // Rule 9.4.4. He declined the RES output, so the numbers live on
        // the chin of rule 9.3.1 and in the Remark of rule 9.3.5, and
        // section 12 measures every one of them off the engine record. If he
        // takes it, this check becomes its other half: a ResultParam at
        // index 0 whose Result carries at least one diagnostic sourced
        // "Skin". One of the two is written, never both.
        foreach (object? port in outputs)
        {
            if (port!.GetType().Name.Contains(
                    "ResultParam", StringComparison.Ordinal))
            {
                throw new InvalidOperationException(
                    "Skin registers NO ResultParam output: his own sentence " +
                    "asked for a removal only, and section 13.2 item 1 is " +
                    "still open.");
            }
        }
```

9. [ ] Build and run the harness. Every port pin and text check must pass.

10. [ ] Scan for clash files and commit.

```powershell
git add "plugin/native_v02/Components/SkinComponents.cs" "tests/native_smoke/Program.cs"
git commit -m "feat(skin): five inputs, two outputs, and the port text says what the order serves"
```

---

### Task 31: Export's input reorder and the branch-read Cells

**Files:**
- Modify: plugin/native_v02/Components/DeliveryComponents.cs:219-323 (`RegisterInputParams`),
  :755-790 (`TryReadInputs`' reads)
- Test: tests/native_smoke/Program.cs, the FlattenedInputs map at Program.cs:34-35 and new
  `ValidateExportBranchCourses`

**Interfaces:**
- Consumes: Skin's Cells tree from Task 30.
- Produces: Export's inputs in the order {Result, Cells, Courses, Column Radius, Name, Path, Studio,
  Live, Write}.

Param's sentence gives: Result, Cells, Courses if it survives, Radius, Name, Studio URL, Live, Write.
He OMITTED PATH. The ruling is the controller's and stays marked as his until Param says otherwise:
Path sits IMMEDIATELY AFTER Name, because the name and the folder together decide the file and neither
means anything without the other, and because putting it there leaves every port he DID name in
exactly the relative order he named it in.

The consequence must be stated rather than discovered on the next file open. `SideMoved` fires on a
different NAME at any index, not only on a changed count, so every saved definition will reattach its
wires BY POSITION onto different ports, raise the ports-moved Warning, and have Live HELD until it is
toggled off and on again. Every existing definition needs its Export wires checked once after this
wave.

1. [ ] Add the check:

```csharp
    /// <summary>
    /// Check 12.10(b) and 12.10(e). Export's inputs are reordered and its
    /// Cells port becomes a TREE whose branch path is the course, which
    /// reproduces exactly what Courses supplies today for Skin-sourced
    /// cells, since Skin already branches Cells by course. Courses SURVIVES
    /// on Export for the one case branch-path derivation cannot serve: an
    /// author wiring a FLAT list of hand-authored cells with an explicit
    /// per-item course list.
    /// </summary>
    private static void ValidateExportBranchCourses(Assembly plugin)
    {
        Type exportType = RequireComponentType(plugin, "ExportComponent");
        object export = Activator.CreateInstance(exportType)!;
        object parameters = exportType.GetProperty("Params")!.GetValue(export)!;
        IList inputs = (IList)parameters.GetType()
            .GetProperty("Input")!.GetValue(parameters)!;
        string[] expected =
        {
            "Result", "Cells", "Courses", "Column Radius", "Name", "Path",
            "Studio", "Live", "Write"
        };
        for (int at = 0; at < expected.Length; at++)
        {
            object port = inputs[at]!;
            string name = (string)port.GetType()
                .GetProperty("Name")!.GetValue(port)!;
            if (name != expected[at])
            {
                throw new InvalidOperationException(
                    "Export's inputs are {Result, Cells, Courses, Column " +
                    "Radius, Name, Path, Studio, Live, Write}, Path " +
                    "immediately AFTER Name by the ruling of section 10.1; " +
                    $"slot {at} is '{name}' and should be " +
                    $"'{expected[at]}'.");
            }
        }
        object cellsPort = inputs[1]!;
        object mapping = cellsPort.GetType()
            .GetProperty("DataMapping")!.GetValue(cellsPort)!;
        if (mapping.ToString() == "Flatten")
        {
            throw new InvalidOperationException(
                "Export's Cells port drops its Flatten and becomes a TREE " +
                "read with GetDataTree (rule 10.2.1): each branch's path " +
                "index is the course of every cell in that branch. A " +
                "Flatten there sends every cell to course 0, which is ONE " +
                "studio stage instead of many.");
        }
        object coursesPort = inputs[2]!;
        object coursesMapping = coursesPort.GetType()
            .GetProperty("DataMapping")!.GetValue(coursesPort)!;
        if (coursesMapping.ToString() != "Flatten")
        {
            throw new InvalidOperationException(
                "Export's Courses port KEEPS its Flatten and its list " +
                "access (rule 10.2.2): it exists for the one case " +
                "branch-path derivation cannot serve, and removing it " +
                "would forbid that case outright.");
        }
    }
```

2. [ ] Update the FlattenedInputs map at Program.cs:34-35, which pins which ports flatten, from
   `new[] { 4, 5 }` to `new[] { 2 }`: Cells is no longer flattened and Courses has moved to slot 2.

3. [ ] Wire the check into `Run` and build. It must fail on slot 1.

4. [ ] Reorder `RegisterInputParams` in DeliveryComponents.cs:219-323 to the nine ports in the order
   above, keeping every description as it stands except Cells', which gains rule 10.2.4's hazard:

```csharp
            "One closed planar outline per cutting cell (a brick), " +
            "authored against the solved form the Result still carries. " +
            "Wire Skin's Cells (C) straight in as a TREE: each branch's " +
            "path index is the course of every cell in that branch, which " +
            "is what the studio stages the build animation by. Any " +
            "Flatten, graft or regraft between Skin and here DESTROYS the " +
            "courses, and a Flatten specifically sends every cell to " +
            "course 0, which is one studio stage instead of many. " +
            "Projected to plan (z dropped) into the sidecar's outline " +
            "points; non-polyline curves are approximated at a 5 mm chord. " +
            "Wiring them is what adds the tessellation kind to the export."
```

5. [ ] Read Cells as a tree and derive the course from the branch path, and refuse the conflict rather
   than resolving it:

```csharp
        data.GetData(0, ref resultGoo);
        data.GetDataTree(1, out GH_Structure<GH_Curve> cellTree);
        data.GetDataList(2, courseInput);
        data.GetData(3, ref radiusInput);
        data.GetData(4, ref nameInput);
        data.GetData(5, ref pathInput);
        data.GetData(6, ref studioInput);
        data.GetData(7, ref liveInput);
        data.GetData(8, ref writeInput);

        var cellInput = new List<Curve>();
        var derivedCourses = new List<int>();
        foreach (GH_Path path in cellTree.Paths)
        {
            int course = path.Indices.Length > 0
                ? path.Indices[^1]
                : 0;
            foreach (GH_Curve? item in cellTree.get_Branch(path))
            {
                if (item?.Value is null)
                    continue;
                cellInput.Add(item.Value);
                derivedCourses.Add(course);
            }
        }
        // The two are mutually exclusive and the conflict is REFUSED, not
        // resolved: guessing which the author meant is how a study silently
        // loses its stages (rule 10.2.3).
        if (cellTree.Paths.Count > 1 && courseInput.Count > 0)
        {
            errors.Add(
                "Cells arrived as more than one branch AND Courses is not " +
                "empty. The branch path IS the course when a tree is " +
                "wired, so wire one or the other: Skin's Cells straight " +
                "in, or a FLAT list of cells with your own Courses list.");
        }
        else if (cellTree.Paths.Count > 1)
        {
            courseInput.Clear();
            courseInput.AddRange(derivedCourses);
        }
```

   When Cells arrives as ONE branch, Courses supplies the course as it does today; when Cells arrives
   as one branch and Courses is empty, every cell is course 0, which is what one branch means. The
   negative-course refusal stays exactly as it is and now applies to derived courses too: a branch
   path cannot be negative, so it becomes unreachable from a Skin wire and stays reachable from a
   hand-wired Courses list, which is where it was earned.

6. [ ] Build and run the harness, then add check 12.10(e)'s three cases to
   `ValidateExportBranchCourses` by driving the derivation directly: a tree of three branches with two
   cells each gives courses 0, 0, 1, 1, 2, 2; a flat list with a Courses list gives that list; both
   together give the Error and no file.

7. [ ] Scan for clash files and commit.

```powershell
git add "plugin/native_v02/Components/DeliveryComponents.cs" "tests/native_smoke/Program.cs"
git commit -m "feat(export): the inputs are reordered and Cells carries its course in the branch path"
```

---

### Task 32: cost, the deferred cause measured, and the wave closed

**Files:**
- Modify: tests/native_smoke/Program.cs:826-841 (the plan-filter cost bound), new
  `ValidateSkinFieldCost` and `ValidateSkinDeferredCause`
- Create: docs/superpowers/notes/2026-09-01-skin-wave-walk.md

**Interfaces:**
- Consumes: everything above.
- Produces: the wave's measured residuals and the walk list Param reads before he opens Rhino.

1. [ ] Re-measure the plan filter's cost bound at Program.cs:826-841 rather than relaxing it. Rule
   3.5.3 makes cells carry more corners and the filter is quadratic in the cell count and expensive
   per cell, so it gets dearer exactly as the pattern improves. Run the annular vault at 96 a ring,
   read the new time, and re-pin it with the measured number written into the check's own message.

2. [ ] Add check 12.9(b), the field's own cost, so nobody mistakes the field for the expensive part:

```csharp
    /// <summary>
    /// Check 12.9(b). The field computation is measured separately and
    /// asserted under a TENTH of the plan filter's time on the same net. It
    /// is O(V log V) with a small constant, run once per solve, against a
    /// filter already measured at seconds on the canvas thread.
    /// </summary>
    private static void ValidateSkinFieldCost(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type netType = RequireComponentType(plugin, "SkinNet");
        Type edgeType = RequireComponentType(plugin, "SkinNetEdge");
        MethodInfo courses = RequirePublicStatic(patterns, "Courses");
        (double[][] vertices, int[][] faces, int[] rim) = SkinFineDomeNet();
        var fieldClock = System.Diagnostics.Stopwatch.StartNew();
        object net = SkinNetWith(
            netType, edgeType, vertices, faces, rim,
            Array.Empty<(int, int, double)>());
        fieldClock.Stop();
        var patternClock = System.Diagnostics.Stopwatch.StartNew();
        courses.Invoke(null, new object[] { net, 0.6, 0.35, 1.0 / 3.0 });
        patternClock.Stop();
        Console.WriteLine(
            "      Skin field cost (check 12.9(b)): the field took " +
            $"{fieldClock.ElapsedMilliseconds} ms and the pattern " +
            $"{patternClock.ElapsedMilliseconds} ms on a 96-a-ring dome.");
        if (fieldClock.ElapsedMilliseconds >
            Math.Max(1L, patternClock.ElapsedMilliseconds / 10))
        {
            throw new InvalidOperationException(
                "The field is not the expensive part of this component and " +
                "must not become it: it is asserted under a tenth of the " +
                $"pattern's own time; got {fieldClock.ElapsedMilliseconds} " +
                $"ms against {patternClock.ElapsedMilliseconds} ms.");
        }
    }
```

3. [ ] Add check 12.1(j), which measures the deferral of rule 1.8.4 rather than leaving it unknown.
   For every joint on every fixture, compute the plan distance between the proportional image of rule
   1.8.1 and the gradient-marched image of rule 1.8.3, and pin the maximum per fixture as a
   MEASUREMENT. It is the size of his cause 1 on real geometry and it is what tells him whether the
   deferral is cheap. Taking the measurement needs no engine change, because the march is computed in
   the harness and never in the pattern:

```csharp
    /// <summary>
    /// Check 12.1(j). Rule 1.8.1's proportional mapping lands a joint at
    /// signed arc u on the mid curve at u (L_boundary / L_mid) on each
    /// boundary curve. It is exact where the three curves are similar about
    /// a common centre and wrong everywhere else, because it assumes a
    /// boundary curve differs from the mid only by a scale factor. Rule
    /// 1.8.3's principled replacement marches from the joint along the
    /// GRADIENT of Levels until the boundary curve is met. Rule 1.8.4 defers
    /// the replacement out of this round and this check measures what the
    /// deferral costs.
    /// </summary>
    private static void ValidateSkinDeferredCause(Assembly plugin)
    {
        Type patterns = RequireComponentType(plugin, "SkinPatterns");
        Type flow = RequireComponentType(plugin, "SkinFlowField");
        Type netType = RequireComponentType(plugin, "SkinNet");
        Type edgeType = RequireComponentType(plugin, "SkinNetEdge");
        MethodInfo traceAll = RequirePublicStatic(patterns, "TraceAll");
        MethodInfo pointAt = RequirePublicStatic(patterns, "PointAt");
        MethodInfo streamline = RequirePublicStatic(flow, "Streamline");
        MethodInfo neighbours = flow.GetMethod(
            "Neighbours",
            BindingFlags.NonPublic | BindingFlags.Static |
            BindingFlags.Public)!;
        foreach ((double[][] v, int[][] f, int[] rim, string label) fixture in
                 new[]
                 {
                     (SkinFineDomeNet().Vertices, SkinFineDomeNet().Faces,
                      SkinFineDomeNet().Rim, "fine dome"),
                     (SkinSerpentineNet().Vertices,
                      SkinSerpentineNet().Faces,
                      SkinSerpentineNet().Rim, "serpentine")
                 })
        {
            object net = SkinNetWith(
                netType, edgeType, fixture.v, fixture.f, fixture.rim,
                Array.Empty<(int, int, double)>());
            double[] levels = SkinLevels(net);
            double extent = levels.Where(double.IsFinite).Max();
            var cuts = new List<double> { 0.35, 0.525, 0.70 };
            if (extent < 0.75)
                continue;
            object traced = traceAll.Invoke(
                null, new object[] { net, cuts })!;
            IList byLevel = (IList)traced;
            IList mids = (IList)byLevel[1]!;
            IList lowers = (IList)byLevel[0]!;
            if (mids.Count == 0 || lowers.Count == 0)
                continue;
            object mid = mids[0]!;
            object lower = lowers[0]!;
            double midLength = Reading<double>(mid, "Length");
            double lowerLength = Reading<double>(lower, "Length");
            double worst = 0.0;
            for (int at = 0; at < 24; at++)
            {
                double u = -midLength / 2.0 + midLength * at / 24.0;
                double[] proportional = (double[])pointAt.Invoke(
                    null, new object[]
                    {
                        lower, u * (lowerLength / midLength)
                    })!;
                double[] from = (double[])pointAt.Invoke(
                    null, new object[] { mid, u })!;
                // The march is the same face-exit walk section 3 uses, on a
                // different vector: the DESCENT of the level field.
                double[] marched = MarchToLevel(
                    net, flow, streamline, neighbours, from, 0.35);
                worst = Math.Max(
                    worst,
                    Math.Sqrt(
                        (marched[0] - proportional[0]) *
                        (marched[0] - proportional[0]) +
                        (marched[1] - proportional[1]) *
                        (marched[1] - proportional[1])));
            }
            Console.WriteLine(
                "      Skin deferred cause (check 12.1(j)): on the " +
                $"{fixture.label} the proportional image and the " +
                $"gradient-marched image differ by up to {worst:F4} m in " +
                "plan. That is the size of cause 1 on this geometry, and " +
                "rule 1.8.4 defers it.");
        }
    }
```

   `MarchToLevel` is written out here rather than described, because the whole measurement the check
   exists to print depends on it and a walk given in one sentence is a walk an implementer invents:

```csharp
    /// <summary>
    /// Rule 1.8.3's gradient march, in the harness and never in the pattern.
    /// It reuses section 3's own face-exit walk on a different vector: the
    /// DESCENT of the Levels field, one direction per face, constant on each
    /// triangle because the field is the piecewise-linear interpolant of rule
    /// 1.4.4. The walk is stopped at the first point whose field value has
    /// crossed the wanted level, and that crossing is interpolated between
    /// the two polyline points that straddle it, so the answer lies ON the
    /// level rather than just past it.
    /// </summary>
    private static double[] MarchToLevel(
        object net,
        Type flow,
        MethodInfo streamline,
        MethodInfo neighbours,
        double[] from,
        double level)
    {
        Type patterns = flow.Assembly.GetType(
            "Ananke.COMPAS.Native.Components.SkinPatterns")!;
        MethodInfo levelAt = RequirePublicStatic(patterns, "LevelAt");
        double Level(double[] at) =>
            (double)levelAt.Invoke(null, new object[] { net, at })!;

        // One DESCENT direction per face: the in-plane vector from the face's
        // highest-field corner to its lowest, which is the steepest descent
        // of an affine function on a triangle.
        IList faces = (IList)net.GetType().GetProperty("Faces")!.GetValue(net)!;
        IList vertices = (IList)net.GetType().GetProperty("Vertices")!.GetValue(net)!;
        double[] levels = SkinLevels(net);
        var directions = new List<double[]>();
        foreach (object? item in faces)
        {
            int[] triangle = (int[])item!;
            int high = triangle[0];
            int low = triangle[0];
            foreach (int corner in triangle)
            {
                if (levels[corner] > levels[high])
                    high = corner;
                if (levels[corner] < levels[low])
                    low = corner;
            }
            double[] a = (double[])vertices[high]!;
            double[] b = (double[])vertices[low]!;
            directions.Add(new[] { b[0] - a[0], b[1] - a[1], b[2] - a[2] });
        }

        MethodInfo faceUnder = patterns.GetMethod(
            "FaceUnder",
            BindingFlags.NonPublic | BindingFlags.Static)!;
        int face = (int)faceUnder.Invoke(null, new object[] { net, from })!;
        if (face < 0)
            return from;
        object neighbourLists = neighbours.Invoke(null, new object[] { net })!;
        double[][] line = (double[][])streamline.Invoke(
            null,
            new object?[]
            {
                net, directions, neighbourLists, from, face,
                directions[face], 0.0, Array.Empty<double[][]>()
            })!;
        for (int at = 0; at + 1 < line.Length; at++)
        {
            double here = Level(line[at]);
            double next = Level(line[at + 1]);
            if (!((here > level && next <= level) || (next > level && here <= level)))
                continue;
            double t = (level - here) / (next - here);
            return new[]
            {
                line[at][0] + ((line[at + 1][0] - line[at][0]) * t),
                line[at][1] + ((line[at + 1][1] - line[at][1]) * t),
                line[at][2] + ((line[at + 1][2] - line[at][2]) * t)
            };
        }
        // The march ran off the mesh before reaching the level, which on
        // these two fixtures means the joint sits below the cut already. The
        // last point is the honest answer and the printed difference is then
        // a lower bound, which the message says.
        return line.Length > 0 ? line[^1] : from;
    }
```

   The `clearance` of 0 and the empty accepted list are deliberate: a march is a measurement of ONE
   line's path and must not be stopped by proximity to another. `SkinFlowField.Streamline` is called
   with the eight arguments Task 26's Interfaces block now states, the neighbour lists included.

4. [ ] Wire both checks into `Run` and build. Everything must be green, and the two measured lines
   must print.

5. [ ] Write the walk list to
   C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\docs\superpowers\notes\2026-09-01-skin-wave-walk.md,
   in plain British prose, numbered, carrying: the four open items of section 13.2 with what each would
   change; the measured numbers this wave printed, the honeycomb before and after, the bed-spacing
   ratio, the uniformity ratio, the band-splitting cost, the deferred cause and the oversized cap's
   girth; the fact that every saved definition needs its Skin and Export wires checked once, because
   both components' ports moved and Export's Live is HELD until it is toggled off and on again; and
   the one instruction that Rhino must be restarted after the install, since an open session keeps the
   old .gha and its worker.

6. [ ] Build the plugin and install it with Rhino CLOSED, then tell Param to restart Rhino:

```powershell
Get-Process -Name Rhino -ErrorAction SilentlyContinue
& "C:\Users\Param\OneDrive - Ananke-eidos\Documents\Ananke Eidos Studio\VS code\COMPAS Workflow\plugin\native_v02\Build-And-Install.ps1"
```

7. [ ] Scan for clash files and commit.

```powershell
git add "tests/native_smoke/Program.cs" "docs/superpowers/notes/2026-09-01-skin-wave-walk.md"
git commit -m "test(skin): the wave's costs and its deferred cause are measured, not asserted"
```

---

