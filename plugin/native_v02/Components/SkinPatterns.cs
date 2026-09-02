#nullable enable

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using Ananke.COMPAS.Native.Contracts;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// The thrust surface as plain arrays: one vertex is a double[3] in metres,
/// one face an int[] of vertex indices in winding order. Read off a Result
/// by the same form-graph-to-equilibrium walk DeconstructComponent's
/// ThrustMesh makes, without the Mesh, so the smoke harness can hand one in
/// and measure everything downstream of it.
///
/// FACES ARE TRIANGLES, always, whoever built the net. The faces handed to
/// the constructor are triangulated once, here, at READ TIME, by
/// SkinPatterns.Triangulate, whose comment carries the rule and the reason.
/// The short of it: a face whose corners are not coplanar does not define a
/// surface at all until something says how to fill it, and the level set of
/// a filled quad is a curve rather than the chord the tracer draws, so a
/// quad mesh gives the tracer APPROXIMATE level curves, and two
/// approximations of one level set can interleave in plan where the exact
/// curves cannot. Making it the net's own invariant rather than ReadNet's
/// is deliberate: the smoke harness builds its nets straight through this
/// constructor, so a rule that lived in ReadNet alone would be a rule no
/// fixture could measure.
/// </summary>
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

    /// <summary>How many named supports rule 1.3.4 dropped as unmappable,
    /// and how many force edges rule 1.3.6 dropped. Init properties and not
    /// constructor parameters, so that neither the two-argument nor the
    /// four-argument construction moves and every fixture in the harness
    /// goes on binding.</summary>
    public int RimDropped { get; init; }

    public int EdgesDropped { get; init; }
}

/// <summary>
/// One traced level-curve component: the polyline of edge crossings at
/// Height, OPEN (a strip ending on the surface boundary, the barrel case)
/// or CLOSED (a loop, the dome case), with cumulative arc lengths, the
/// nesting depth the correspondence classifies on and, once seams are
/// assigned, the seam every setout coordinate is measured from.
/// Cumulative[i] is the arc length at Points[i] from Points[0]; a
/// closed curve's Length additionally carries the closing segment back to
/// Points[0], which Points does NOT repeat.
/// </summary>
internal sealed class SkinLevelCurve
{
    /// <summary>The FIELD value this curve is the level set of: a rim
    /// distance in metres where the net carries a rim, and the world Z it
    /// used to be where it does not (rules 1.2.1 and 1.2.5). Renamed from
    /// Height with the field, because an author shown a rim distance
    /// labelled as a height has been given a worse defect than the one this
    /// wave fixes.</summary>
    public double Level { get; set; }

    public List<double[]> Points { get; set; } = new();

    public bool Closed { get; set; }

    public double[] Cumulative { get; set; } = Array.Empty<double>();

    public double Length { get; set; }

    public double Seam { get; set; }

    /// <summary>
    /// The NESTING DEPTH of this component within its OWN level: how
    /// many other closed components at the same height contain it in
    /// plan. An outer rim loop is 0, the oculus loop inside it is 1, a
    /// loop inside that 2; an OPEN strip is 0 by the rule, since a
    /// curve with two ends encloses nothing. Assigned by
    /// AssignNestingDepths, whose comment carries the rule and the
    /// argument for it, and read by MatchBelow, which will not match
    /// across two depths.
    /// </summary>
    public int Depth { get; set; }
}

/// <summary>
/// One generated cell: the outline points in order (NOT closed by
/// repeating the first point; the component appends the closing repeat
/// when it builds the PolylineCurve, the ClosedOutlineCurve convention),
/// the course band, whether the boundary clipped it, and the setout span
/// [U0, U1] along the course direction, seam-relative, which is what the
/// harness measures the pitch, the phase and the stagger on.
/// </summary>
internal sealed record SkinCell(
    int Course,
    IReadOnlyList<double[]> Outline,
    bool Clipped,
    double U0,
    double U1,
    bool Cap = false);

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
    int DegenerateCentroidsSkipped,
    int ExtraLevels,
    int TracePasses);

/// <summary>
/// The native skin patterns (spec 2026-08-31 sections 4 to 6): the setout
/// map shared by both, the running-bond courses engine and the stretched
/// honeycomb. Pure C# on the net's vertex and face arrays; nothing in
/// this file may reference RhinoCommon, so the harness measures every
/// step without launching Rhino. PolylineCurves exist only at the
/// component's output boundary, the FrameGeometry Read/Build split.
/// </summary>
internal static class SkinPatterns
{
    // ---- the net --------------------------------------------------------

    /// <summary>
    /// The Result's own vertex and face arrays: form-graph faces mapped
    /// through Mappings.SourceVertexToFormVertex onto the equilibrium
    /// vertex positions, ordered by form vertex id, exactly the walk
    /// DeconstructComponent.ThrustMesh makes. Null for a Result that is
    /// not a full TNA Result (an FD Result carries no faces), so the
    /// component can say WHY there are no cells rather than showing an
    /// empty tree with no explanation.
    /// </summary>
    public static SkinNet? ReadNet(ResultDto result)
    {
        if (!ResultTables.IsTna(result))
            return null;
        EquilibriumResultDto equilibrium = result.Equilibrium!;
        TnaDiagramGraphDto formGraph = result.FormGraph!;
        TnaMappingsDto mappings = result.Mappings!;

        Dictionary<int, int> formToEquilibrium = mappings
            .SourceVertexToFormVertex
            .Where(item =>
                item.FormVertexId.HasValue &&
                item.EquilibriumVertexId.HasValue)
            .GroupBy(item => item.FormVertexId!.Value)
            .ToDictionary(
                group => group.Key,
                group =>
                {
                    int[] ids = group
                        .Select(item => item.EquilibriumVertexId!.Value)
                        .Distinct()
                        .ToArray();
                    if (ids.Length != 1)
                    {
                        throw new InvalidOperationException(
                            $"Form vertex {group.Key} maps to multiple " +
                            "equilibrium vertices.");
                    }
                    return ids[0];
                });

        var vertices = new List<double[]>();
        var formToNet = new Dictionary<int, int>();
        foreach (TnaGraphVertexDto vertex in
                 formGraph.Vertices.OrderBy(item => item.Id))
        {
            if (!formToEquilibrium.TryGetValue(
                    vertex.Id, out int equilibriumId) ||
                equilibriumId < 0 ||
                equilibriumId >= equilibrium.Vertices.Count)
            {
                throw new InvalidOperationException(
                    $"Form vertex {vertex.Id} has no equilibrium vertex.");
            }
            Point3Dto at = equilibrium.Vertices[equilibriumId];
            formToNet[vertex.Id] = vertices.Count;
            vertices.Add(new[] { at.X, at.Y, at.Z });
        }

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
    }

    /// <summary>
    /// Every face as TRIANGLES, so that every face the tracer ever sees is
    /// PLANAR and every level curve it draws is the EXACT level set of the
    /// surface rather than an approximation of one.
    ///
    /// WHY IT EXISTS. Trace cuts a face by joining the two crossings on its
    /// boundary with a straight CHORD. On a triangle that chord IS the
    /// level set, because three points define a plane and height restricted
    /// to a plane is affine. On a quad whose four corners are NOT coplanar
    /// it is not: such a quad does not define a surface at all until
    /// something says how to fill it, and every filling has a level set that
    /// bends. The chord is therefore an approximation, and two
    /// approximations of ONE level set can interleave in plan where the
    /// exact curves cannot.
    ///
    /// That impossibility is the point. On a plan-injective surface (a
    /// height field, which spec section 4's whole guarantee rests on) two
    /// components of one level set cannot cross in plan: a crossing point
    /// would lie on both, so they would be one component. Nesting is
    /// therefore well defined, the depth rule AssignNestingDepths states is
    /// sound rather than sampling-dependent, and the correspondence and the
    /// plan guarantee are strengthened with it. With quads none of that
    /// holds, because the curves being classified are not the level set.
    ///
    /// REPRODUCED against the build before this change on an annular vault
    /// meshed as a SPIRAL: thirteen rings of twelve on the profile
    /// z = 2 (1 - ((r - 2.5) / 1.5)^2), ring j turned by j full angular
    /// steps, which moves NO vertex (a full step maps a ring onto itself)
    /// and leaves the mesh a certified height field. The courses engine went
    /// from the unturned control's 52 cells to ZERO with a band refused at
    /// CH 1.9, from 205 to 75 at CH 0.5 and from 310 to 103 at CH 0.35, and
    /// the diagnostics reported a transition on a shell that has none.
    /// Measured at the top cut, z = 1.999998: all 24 quads the trace
    /// crosses are non-planar, by up to 4.038e-2 m; the chord misses the
    /// exact level set by up to 2.562e-5 m; and the two loops are only
    /// 1.559e-5 m apart in radius there. The approximation is LARGER than
    /// the separation, so the two traced polygons interleave, neither
    /// contains the other, both are classified depth 0, and the bijection
    /// fails. Triangulating the same net returns depths 0 and 1, no
    /// crossing, and the control's own 52, 205 and 310.
    ///
    /// THE RULE, stated because it must not depend on the order the faces
    /// arrive in. A triangle passes through untouched. A polygon is split
    /// on its SHORTEST valid PLAN DIAGONAL, and the two halves are split
    /// again by the same rule until only triangles are left. A diagonal is
    /// valid when it crosses no edge of the polygon properly and its
    /// midpoint lies inside the polygon in plan, which is what keeps the
    /// triangles inside the face and their union equal to it; a non-convex
    /// quad has exactly one such diagonal and the shorter of the two is not
    /// always it, so validity is tested before length and not after. Ties
    /// in length go to the pair with the lower vertex index (the lower of
    /// the two indices first, then the higher), which is a property of the
    /// mesh's own numbering rather than of any traversal, so a concentric
    /// quad whose two diagonals are exactly equal splits the same way
    /// whichever corner its winding starts from. A polygon with no valid
    /// diagonal at all is degenerate in plan, outside the height-field
    /// domain, and is fanned from its first corner so the answer stays
    /// deterministic.
    ///
    /// The triangulation is IDEMPOTENT and an all-triangle list is returned
    /// unchanged, so a net built from another net's faces is the same net.
    /// </summary>
    public static IReadOnlyList<int[]> Triangulate(
        IReadOnlyList<double[]> vertices,
        IReadOnlyList<int[]> faces)
    {
        bool anyPolygon = false;
        foreach (int[] face in faces)
        {
            if (face.Length > 3)
            {
                anyPolygon = true;
                break;
            }
        }
        if (!anyPolygon)
            return faces;
        var triangles = new List<int[]>(faces.Count * 2);
        foreach (int[] face in faces)
        {
            if (face.Length <= 3)
            {
                triangles.Add(face);
                continue;
            }
            SplitPolygon(vertices, face, triangles);
        }
        return triangles;
    }

    /// <summary>Triangulate's rule applied to one ring, written into a
    /// list. The comment on Triangulate carries the rule and the
    /// tie-break; the splitting itself, and the order, are
    /// SplitPolygonInOrder's.</summary>
    private static void SplitPolygon(
        IReadOnlyList<double[]> vertices,
        IReadOnlyList<int> ring,
        List<int[]> into)
    {
        foreach (int[] triangle in SplitPolygonInOrder(vertices, ring))
            into.Add(triangle);
    }

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

    /// <summary>
    /// One step of Triangulate's rule, and then the next: find the
    /// shortest valid plan diagonal, cut the ring in two along it and go
    /// on with the halves, giving up each triangle as it is found.
    ///
    /// The order is the order the recursion had, the NEAR half before the
    /// far half all the way down, which is what makes this the same
    /// triangulation written the same way round rather than a second
    /// arithmetic. The halves waiting their turn sit on a stack, and
    /// pushing the far half before the near one is what puts the near one
    /// next.
    ///
    /// It gives them up ONE AT A TIME because PlanInteriorPoint wants the
    /// FIRST triangle whose centroid is inside and almost never the rest,
    /// and the rest is where the time goes: the diagonal search tests
    /// about half of n squared candidates against the ring's own edges at
    /// every level, and a split takes a level, so triangulating the whole
    /// of a 192-corner outline to read one centroid off the front of it
    /// cost 2.3 SECONDS. Triangulate itself wants every triangle and
    /// takes them all.
    /// </summary>
    private static IEnumerable<int[]> SplitPolygonInOrder(
        IReadOnlyList<double[]> vertices,
        IReadOnlyList<int> ring)
    {
        var waiting = new Stack<IReadOnlyList<int>>();
        waiting.Push(ring);
        while (waiting.Count > 0)
        {
            IReadOnlyList<int> current = waiting.Pop();
            int count = current.Count;
            if (count < 3)
                continue;
            if (count == 3)
            {
                yield return new[] { current[0], current[1], current[2] };
                continue;
            }
            (int From, int To) cut = ShortestPlanDiagonal(vertices, current);
            if (cut.From < 0)
            {
                // Degenerate in plan, outside the height-field domain: fan
                // from the first corner so the answer is still deterministic.
                for (int corner = 1; corner + 1 < count; corner++)
                {
                    yield return new[]
                    {
                        current[0], current[corner], current[corner + 1]
                    };
                }
                continue;
            }
            // The two halves, each still wound the way the face was: the
            // near side runs from the diagonal's first corner to its
            // second, the far side leaves the first corner, jumps the
            // diagonal and comes back round. Both start at the same
            // corner, so a quad split on its 0-2 diagonal reads [0,1,2]
            // and [0,2,3] rather than the same triangles written from
            // somewhere else in their cycle.
            var near = new List<int>();
            for (int at = cut.From; at <= cut.To; at++)
                near.Add(current[at]);
            var far = new List<int> { current[cut.From] };
            for (int at = cut.To; at != cut.From; at = (at + 1) % count)
                far.Add(current[at]);
            waiting.Push(far);
            waiting.Push(near);
        }
    }

    /// <summary>The ring's SHORTEST VALID plan diagonal, as two positions
    /// within the ring, or (-1, -1) where the ring has none. Validity is
    /// tested before length and the tie in length goes to the mesh's own
    /// numbering: the comment on Triangulate carries both rules and the
    /// reason for each.</summary>
    private static (int From, int To) ShortestPlanDiagonal(
        IReadOnlyList<double[]> vertices,
        IReadOnlyList<int> ring)
    {
        int count = ring.Count;
        int bestFrom = -1;
        int bestTo = -1;
        double bestLength = double.PositiveInfinity;
        (int Low, int High) bestPair = (int.MaxValue, int.MaxValue);
        for (int from = 0; from < count; from++)
        {
            for (int to = from + 2; to < count; to++)
            {
                if (from == 0 && to == count - 1)
                    continue;
                if (!IsPlanDiagonal(vertices, ring, from, to))
                    continue;
                double length = PlanDistance(
                    vertices[ring[from]], vertices[ring[to]]);
                (int Low, int High) pair =
                    ring[from] < ring[to]
                        ? (ring[from], ring[to])
                        : (ring[to], ring[from]);
                bool better = length < bestLength - 1.0e-12 ||
                    (length <= bestLength + 1.0e-12 &&
                     (pair.Low < bestPair.Low ||
                      (pair.Low == bestPair.Low &&
                       pair.High < bestPair.High)));
                if (!better)
                    continue;
                bestLength = Math.Min(bestLength, length);
                bestPair = pair;
                bestFrom = from;
                bestTo = to;
            }
        }
        return (bestFrom, bestTo);
    }

    /// <summary>Is the segment between two non-adjacent corners a DIAGONAL
    /// of the ring in plan: crossing no edge properly, and with its
    /// midpoint inside? The midpoint test is what refuses the outside
    /// diagonal of a non-convex quad, which the shorter-of-the-two rule
    /// alone would sometimes choose.</summary>
    private static bool IsPlanDiagonal(
        IReadOnlyList<double[]> vertices,
        IReadOnlyList<int> ring,
        int from,
        int to)
    {
        int count = ring.Count;
        double[] a = vertices[ring[from]];
        double[] b = vertices[ring[to]];
        for (int edge = 0; edge < count; edge++)
        {
            int next = (edge + 1) % count;
            if (edge == from || edge == to || next == from || next == to)
                continue;
            if (PlanSegmentsCross(
                    a, b, vertices[ring[edge]], vertices[ring[next]]))
            {
                return false;
            }
        }
        var outline = new double[count][];
        for (int corner = 0; corner < count; corner++)
            outline[corner] = vertices[ring[corner]];
        return PlanContains(
            (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0, outline);
    }

    // ---- level-curve tracing and seams (spec section 4) -----------------

    /// <summary>
    /// Trace the net at every height, ascending, CLASSIFY every traced
    /// component by its nesting depth, NORMALISE every traced curve's
    /// direction, and assign every curve its seam, in one pass. The
    /// order is forced: depth is what MatchBelow classifies on, and
    /// both the direction rule and the seam rule call MatchBelow; a
    /// direction has to be settled before the seam that is measured
    /// along it; and a closed loop's seam is propagated from the level
    /// below it, so the propagation only means something bottom-up. The
    /// heights MUST arrive ascending; both engines build them that way.
    /// </summary>
    public static IReadOnlyList<IReadOnlyList<SkinLevelCurve>> TraceAll(
        SkinNet net,
        IReadOnlyList<double> levels)
    {
        var working = new List<List<SkinLevelCurve>>();
        foreach (double level in levels)
            working.Add(Trace(net, level));
        AssignNestingDepths(working);
        NormaliseDirections(working);
        AssignSeams(working);
        return working;
    }

    /// <summary>
    /// Cut the net at one height and stitch the crossings into polyline
    /// components. An edge CROSSES when one end is strictly below the cut
    /// and the other at or above it (the half-open rule: a vertex lying
    /// exactly on the cut belongs to the upper side and is counted once,
    /// so a cut through a vertex row is deterministic). Each face
    /// contributes segments between consecutive crossings around its
    /// boundary; a crossing on an edge two faces share joins their
    /// segments, and a chain that ends at a crossing only one face
    /// touched is OPEN. Crossing indices are assigned in face-walk order,
    /// so the component order is deterministic.
    /// </summary>
    private static List<SkinLevelCurve> Trace(SkinNet net, double level)
    {
        var crossingByEdge = new Dictionary<(int, int), int>();
        var crossingPoints = new List<double[]>();

        (int, int) EdgeKey(int a, int b) =>
            a < b ? (a, b) : (b, a);

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

        var linksByCrossing = new Dictionary<int, List<int>>();
        void Link(int from, int to)
        {
            if (!linksByCrossing.TryGetValue(from, out List<int>? list))
                linksByCrossing[from] = list = new List<int>();
            list.Add(to);
        }
        foreach (int[] face in net.Faces)
        {
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

            var hits = new List<int>();
            for (int corner = 0; corner < face.Length; corner++)
            {
                int a = face[corner];
                int b = face[(corner + 1) % face.Length];
                if (Crosses(a, b))
                    hits.Add(CrossingOf(a, b));
            }
            // The crossing count around a closed face boundary is even
            // (the below/at-or-above classification changes state an even
            // number of times), and on a TRIANGLE, which is all a net now
            // holds, it is 0 or 2, so the pairing is forced and the saddle
            // ambiguity a quad used to leave is gone with the quad.
            for (int pair = 0; pair + 1 < hits.Count; pair += 2)
            {
                Link(hits[pair], hits[pair + 1]);
                Link(hits[pair + 1], hits[pair]);
            }
        }

        var visited = new HashSet<int>();
        var curves = new List<SkinLevelCurve>();

        List<double[]> Walk(int start, out bool closed)
        {
            var chain = new List<double[]>();
            closed = false;
            int previous = -1;
            int current = start;
            while (true)
            {
                visited.Add(current);
                chain.Add(crossingPoints[current]);
                int next = -1;
                if (linksByCrossing.TryGetValue(
                        current, out List<int>? links))
                {
                    foreach (int link in links)
                    {
                        if (link != previous)
                        {
                            next = link;
                            break;
                        }
                    }
                }
                if (next < 0)
                    return chain;
                if (next == start)
                {
                    closed = true;
                    return chain;
                }
                previous = current;
                current = next;
            }
        }

        // Open chains first, from their degree-one ends, so a chain is
        // walked end to end; whatever remains connected is a loop.
        for (int index = 0; index < crossingPoints.Count; index++)
        {
            if (visited.Contains(index))
                continue;
            int degree = linksByCrossing.TryGetValue(
                index, out List<int>? links)
                ? links.Count
                : 0;
            if (degree == 1)
                curves.Add(Finish(Walk(index, out bool closed), level, closed));
        }
        for (int index = 0; index < crossingPoints.Count; index++)
        {
            if (visited.Contains(index))
                continue;
            if (!linksByCrossing.ContainsKey(index))
            {
                // An isolated crossing paired with nothing: a degenerate
                // touch, not a curve.
                visited.Add(index);
                continue;
            }
            curves.Add(Finish(Walk(index, out bool closed), level, closed));
        }
        return curves
            .Where(curve => curve.Points.Count >= 2 && curve.Length > 1.0e-12)
            .ToList();
    }

    private static SkinLevelCurve Finish(
        List<double[]> points,
        double level,
        bool closed)
    {
        var cumulative = new double[points.Count];
        double length = 0.0;
        for (int i = 1; i < points.Count; i++)
        {
            length += Distance(points[i - 1], points[i]);
            cumulative[i] = length;
        }
        if (closed && points.Count > 2)
            length += Distance(points[^1], points[0]);
        return new SkinLevelCurve
        {
            Level = level,
            Points = points,
            Closed = closed,
            Cumulative = cumulative,
            Length = length
        };
    }

    /// <summary>
    /// Classify every traced component by its NESTING DEPTH within its
    /// own level, before anything measures a distance.
    ///
    /// THE RULE. The depth of a CLOSED component is the number of other
    /// closed components at the same height that contain it in plan: an
    /// outer rim loop is 0, the oculus loop inside it is 1, a loop
    /// inside that 2. An OPEN strip is 0, because a curve with two ends
    /// encloses nothing and is not asked to.
    ///
    /// WHY IT EXISTS. The ruling before this one took the world axes
    /// out of the correspondence and left the SAMPLING in.
    /// MeanNearestPlanDistance measures each sample point of one curve
    /// to the nearest SAMPLE POINT of the other, so its score carries an
    /// error of roughly half the other curve's sample spacing, and where
    /// two components genuinely lie close together in plan that error,
    /// and with it the MESH, decides which curve corresponds to which.
    /// Reproduced against the built plugin on the annular ring vault by
    /// turning its ridge ring ALONE about world Z, which moves no level
    /// set, no component and no topology: at 0 and at 0.05 degrees, CH
    /// 1.9 gave 52 courses cells and refused nothing; at 0.1 degrees,
    /// 4.4 mm on a 2.5 m circle, it gave ZERO cells and reported a
    /// transition where the two loops correspond perfectly, outer to
    /// outer and inner to inner. The same loss followed from
    /// TRIANGULATING the mesh (312 cells to 260 at the shipped default
    /// CH 0.35, 208 to 156 at CH 0.5) and from giving the rings UNEQUAL
    /// densities, neither of which changes any level set.
    ///
    /// A finer distance does not answer it and must not be reached for.
    /// At a ridge the outer and the inner loop genuinely COINCIDE in
    /// plan, three millionths of a metre apart on this fixture, and no
    /// distance whatever can separate two curves lying on top of one
    /// another. Only a classification can.
    ///
    /// WHY DEPTH IS THE RIGHT CLASSIFICATION. It is topological, so it
    /// is invariant under exactly the changes that must not move the
    /// answer. A rotation about world Z turns both loops together and
    /// leaves which contains which untouched; a translation likewise; a
    /// remeshing moves each loop's sample points ALONG the same curve
    /// and cannot move one loop through another. So on a ring vault the
    /// outer crown loop is depth 0 and the inner is depth 1 at every
    /// angle and every mesh density, however close the two lie, and
    /// MatchBelow decides the correspondence before it measures
    /// anything.
    ///
    /// THE CONTAINMENT TEST is the engine's own PlanContains, the
    /// even-odd ray cast the plan filter already uses, taken as a VOTE
    /// over the inner curve's sample points: contained when more than
    /// half of them lie inside. Two components of ONE level cannot
    /// properly cross, so in exact arithmetic a single point would
    /// settle it; the vote is what makes the shared-vertex cases
    /// harmless, a cut through a vertex row leaving two components
    /// touching at a point neither strictly inside nor strictly outside.
    /// It is the same strictness the crossing predicate keeps, where a
    /// zero side value is not a crossing.
    /// </summary>
    private static void AssignNestingDepths(
        IReadOnlyList<List<SkinLevelCurve>> byHeight)
    {
        foreach (List<SkinLevelCurve> level in byHeight)
        {
            for (int inner = 0; inner < level.Count; inner++)
            {
                int depth = 0;
                if (level[inner].Closed)
                {
                    for (int outer = 0; outer < level.Count; outer++)
                    {
                        if (outer == inner || !level[outer].Closed)
                            continue;
                        if (PlanEncloses(level[outer], level[inner]))
                            depth++;
                    }
                }
                level[inner].Depth = depth;
            }
        }
    }

    /// <summary>Does the outer curve's plan projection CONTAIN the inner
    /// one's? The vote described in AssignNestingDepths: more than half
    /// of the inner curve's sample points inside the outer curve, by the
    /// engine's own PlanContains.</summary>
    private static bool PlanEncloses(
        SkinLevelCurve outer,
        SkinLevelCurve inner)
    {
        int inside = 0;
        foreach (double[] point in inner.Points)
        {
            if (PlanContains(point[0], point[1], outer.Points))
                inside++;
        }
        return 2 * inside > inner.Points.Count;
    }

    /// <summary>
    /// Normalise every traced curve's DIRECTION, before any seam is
    /// assigned against it.
    ///
    /// Trace fixes a direction from FACE-ARRAY ORDER alone: a closed loop
    /// follows whichever neighbour happened to be linked first, an open
    /// strip starts at the lowest-index degree-one crossing. Nothing in
    /// the net's geometry says which that is, so the same surface handed
    /// in with its faces in a different order can trace west to east at
    /// one height and east to west at the next. Every consumer assumes
    /// the matched curves of a band run the SAME way (BandCell maps one
    /// joint onto the band's lower and upper curves; Hexagonal maps one
    /// hexagon's vertices through three row curves), so a disagreement
    /// turns every cell of that band into a bow tie in plan and breaks
    /// the height-field guarantee spec section 4 argues from.
    ///
    /// The two rules, stated, because an arbitrary rule that is written
    /// down is what makes the direction a property of the GEOMETRY
    /// rather than of the face array:
    ///
    /// CLOSED: a loop runs COUNTER-CLOCKWISE in plan. It is reversed
    /// when its signed plan area (the shoelace sum over the plan
    /// projection, closing edge included) is negative.
    ///
    /// OPEN: a strip runs the same way as the strip matched below it in
    /// the same chart, matched by MatchBelow, the same matching every
    /// other consumer uses. Compare the chord from the strip's first
    /// point to its last, in plan, against the matched strip's chord: a
    /// negative dot product means the two disagree, so reverse. The
    /// LOWEST strip of a chart has nothing below it (the bottom level,
    /// or a strip whose match below is a closed loop rather than a
    /// strip) and takes a stated GLOBAL rule instead: its chord must
    /// bear a non-negative X component, and where that X is zero (a
    /// strip running due north) a non-negative Y component. A chord of
    /// zero length, which only a degenerate strip has, is left alone.
    ///
    /// Levels are walked bottom-up and reversed IN PLACE, so a strip is
    /// always compared against an already-normalised strip below it.
    /// </summary>
    private static void NormaliseDirections(
        IReadOnlyList<List<SkinLevelCurve>> byHeight)
    {
        IReadOnlyList<SkinLevelCurve> below = Array.Empty<SkinLevelCurve>();
        foreach (List<SkinLevelCurve> level in byHeight)
        {
            foreach (SkinLevelCurve curve in level)
            {
                if (curve.Closed)
                {
                    if (SignedPlanArea(curve) < 0.0)
                        Reverse(curve);
                    continue;
                }
                (double X, double Y) chord = PlanChord(curve);
                int matched = MatchBelow(curve, below);
                if (matched >= 0 && !below[matched].Closed)
                {
                    (double X, double Y) under = PlanChord(below[matched]);
                    if (chord.X * under.X + chord.Y * under.Y < 0.0)
                        Reverse(curve);
                    continue;
                }
                if (chord.X < -1.0e-12 ||
                    (Math.Abs(chord.X) <= 1.0e-12 && chord.Y < -1.0e-12))
                {
                    Reverse(curve);
                }
            }
            if (level.Count > 0)
                below = level;
        }
    }

    /// <summary>
    /// Twice the shoelace sum, halved: the signed area of the curve's
    /// PLAN projection, positive counter-clockwise and negative
    /// clockwise. The closing edge back to the first point is included,
    /// which is the same edge a closed curve's Length carries.
    ///
    /// The sum is taken on coordinates measured FROM THE POINTS' PLAN
    /// MEAN, the same centroid-relative form PlusXVertex uses, and a
    /// model sited away from the world origin is why. The raw shoelace
    /// sums terms of order d squared for a model d metres out while the
    /// answer it is asked for is the loop's own area, so the
    /// cancellation error grows with the square of the distance and a
    /// small loop far from the origin loses its SIGN. Measured on the
    /// dome fixture translated 1000 m in plan: the crown loop's
    /// centred area is -1.131e-11 m2 while the raw sum returns exactly
    /// 0.0, which reads as "not negative", leaves the crown loop
    /// running clockwise against every loop below it, and turns the top
    /// band's cells into bow ties in plan. Sited models are the ordinary
    /// case in a studio, not an exotic one: an OS-gridded site is
    /// hundreds of kilometres out. At the origin the centred and raw
    /// sums agree to 1e-16, so no existing pin moves.
    /// </summary>
    private static double SignedPlanArea(SkinLevelCurve curve)
    {
        double cx = curve.Points.Average(point => point[0]);
        double cy = curve.Points.Average(point => point[1]);
        double twice = 0.0;
        int count = curve.Points.Count;
        for (int i = 0; i < count; i++)
        {
            double[] a = curve.Points[i];
            double[] b = curve.Points[(i + 1) % count];
            twice +=
                (a[0] - cx) * (b[1] - cy) -
                (b[0] - cx) * (a[1] - cy);
        }
        return twice / 2.0;
    }

    /// <summary>The chord from an open strip's first point to its last,
    /// in plan: the direction the strip runs, reduced to one vector.
    /// </summary>
    private static (double X, double Y) PlanChord(SkinLevelCurve curve) =>
        (curve.Points[^1][0] - curve.Points[0][0],
         curve.Points[^1][1] - curve.Points[0][1]);

    /// <summary>
    /// Reverse a curve IN PLACE, rebuilding Points, Cumulative and
    /// Length together through the same Finish the trace uses, so the
    /// three can never disagree. The edge set is unchanged, so the
    /// length is unchanged too; only the direction and the arc-length
    /// origin move. Seams are assigned AFTER this pass, so there is no
    /// seam to carry over.
    /// </summary>
    private static void Reverse(SkinLevelCurve curve)
    {
        var points = new List<double[]>(curve.Points);
        points.Reverse();
        SkinLevelCurve rebuilt = Finish(points, curve.Level, curve.Closed);
        curve.Points = rebuilt.Points;
        curve.Cumulative = rebuilt.Cumulative;
        curve.Length = rebuilt.Length;
    }

    /// <summary>
    /// Every level curve needs a u origin (spec section 4). An open
    /// strip's seam is its arc-length MIDPOINT, so setout is
    /// centre-outward and mirror-symmetric geometry gets mirror-symmetric
    /// joints by construction. A closed loop's seam is propagated from
    /// the loop below it (the trace vertex nearest in plan to the lower
    /// seam); the lowest loop's seam is the trace vertex on the +X
    /// bearing from its plan centroid, deterministic and stated.
    /// </summary>
    private static void AssignSeams(
        IReadOnlyList<List<SkinLevelCurve>> byHeight)
    {
        IReadOnlyList<SkinLevelCurve> below = Array.Empty<SkinLevelCurve>();
        foreach (List<SkinLevelCurve> level in byHeight)
        {
            foreach (SkinLevelCurve curve in level)
            {
                if (!curve.Closed)
                {
                    curve.Seam = curve.Length / 2.0;
                    continue;
                }
                int matched = MatchBelow(curve, below);
                if (matched >= 0 && below[matched].Closed)
                {
                    double[] lowerSeam = PointAt(below[matched], 0.0);
                    curve.Seam =
                        curve.Cumulative[NearestInPlan(curve, lowerSeam)];
                }
                else
                {
                    curve.Seam = curve.Cumulative[PlusXVertex(curve)];
                }
            }
            if (level.Count > 0)
                below = level;
        }
    }

    /// <summary>
    /// Spec section 4's "matched to the component below it", in TWO
    /// stages: CLASSIFY, then measure.
    ///
    /// 0. KIND. An OPEN strip may only be matched to an open strip and a
    /// CLOSED loop only to a closed loop. A strip has two ends on the
    /// surface boundary and a loop has none, so the two are never the
    /// same piece of surface, and a band bonded from one to the other is
    /// the bow tie ruling B2 was written against: on the two-hump
    /// barrel the mid level at z 0.75 cuts into the front and back
    /// STRIPS and the upper level at z 1.00 into the two hump LOOPS, and
    /// a band built across that change lays every cell of it over its
    /// neighbour. Kind is topological, like depth, and it is the same
    /// invariant two of this method's callers were already testing by
    /// hand after the fact (NormaliseDirections would not take a
    /// direction from a loop, AssignSeams would not propagate a seam
    /// from a strip); putting it in the classification is what makes it
    /// hold for the correspondence too. Nothing else could: at a
    /// transition of this shape both levels hold two components, both of
    /// nesting depth 0, and a distance can only say which is nearer, so
    /// the refusal rested on a near-tie between a full-length strip and
    /// two half-length loops. That tie broke the right way while the
    /// mesh was quads and the wrong way once the tracer began drawing
    /// EXACT level curves with twice as many points, which is how it was
    /// found.
    ///
    /// 1. NESTING DEPTH. A component may only be matched to a candidate
    /// of EQUAL depth, the depth AssignNestingDepths assigned from
    /// containment within each component's own level. That comment
    /// carries the rule, the reproduction and the invariance argument;
    /// the short of it is that a distance, however fine, cannot separate
    /// two loops that coincide in plan at a ridge, and depth can,
    /// because containment survives rotation, translation and
    /// remeshing. Where no candidate shares this curve's depth there is
    /// NO match, and -1 comes back: every caller already reads -1 as no
    /// answer, and in Corresponds a depth class of a different size on
    /// the two levels is a genuine correspondence failure and refuses
    /// the band exactly as an unmatched curve does.
    ///
    /// 2. DISTANCE WITHIN THE CLASS. Among the candidates of equal
    /// depth, the one whose plan projection lies CLOSEST to this
    /// curve's.
    ///
    /// The measure is a DISTANCE, and it is a distance because a
    /// distance is the thing a rotation cannot change. The rule this
    /// replaces scored candidates by the overlap AREA of axis-aligned
    /// plan bounding boxes, and an axis-aligned box is a property of
    /// the WORLD AXES rather than of the surface. Turning a model about
    /// world Z moves no z, no face and no traced component, so it
    /// cannot change which curves correspond, and yet it changed the
    /// answer. Measured against the build before this change, the
    /// two-hump barrel swept 0 to 180 degrees in 5 degree steps had its
    /// transition band refused at EXACTLY five angles, 0, 45, 90, 135
    /// and 180. At the other thirty-two the band was built and the
    /// courses engine emitted 84 cells with 12 to 14 self-crossing and
    /// 152 to 214 overlapping pairs in plan; at 37 degrees, 13 and 183.
    /// The mechanism: a long thin strip lying at an angle has an
    /// axis-aligned box inflated by roughly its own length times the
    /// sine of that angle, which manufactures an overlap where the
    /// strips themselves are nowhere near one another, and with it a
    /// false bijection. The same blind spot refused an ordinary annular
    /// shell (an oculus dome, whose every cut is two NESTED loops)
    /// WHOLE at every course height, because the outer loop's box
    /// CONTAINS the inner loop's and a bounding-box area cannot express
    /// nesting. An arbitrarily oriented model and an oculus dome are
    /// both ordinary studio cases.
    ///
    /// The score, symmetrised so it does not depend on which curve is
    /// read first: the mean over this curve's sample points of the plan
    /// distance to the nearest sample point of the candidate, plus the
    /// same mean taken the other way round, halved. The trace's own
    /// points are the sampling, which is why no new sampling rule is
    /// needed. Distances are invariant under rotation and translation,
    /// so the answer is a property of the geometry rather than of the
    /// model's alignment or its siting.
    ///
    /// The nearest-centroid fallback went with the boxes. It existed
    /// only because parallel open strips (the barrel) have
    /// zero-thickness boxes that overlap in nothing, so the area rule
    /// had no answer at all there; a distance always has one, and a
    /// better one than the centroid's, which cannot tell two curves
    /// sharing a centroid apart. Ties keep the first candidate, which
    /// is deterministic because Trace's component order is.
    ///
    /// Spec section 4 words this rule as "by plan overlap". The words
    /// are the spec's, the defect is the words' own, and the ruling
    /// this comment records replaces them with proximity.
    /// </summary>
    private static int MatchBelow(
        SkinLevelCurve curve,
        IReadOnlyList<SkinLevelCurve> candidates)
    {
        if (candidates.Count == 0)
            return -1;
        int best = -1;
        double bestScore = double.PositiveInfinity;
        for (int i = 0; i < candidates.Count; i++)
        {
            // Stage one: a candidate of another KIND, or of another
            // nesting depth, is not a candidate at all, whatever the
            // distance says.
            if (candidates[i].Closed != curve.Closed)
                continue;
            if (candidates[i].Depth != curve.Depth)
                continue;
            double score = PlanProximity(curve, candidates[i]);
            if (score < bestScore - 1.0e-12)
            {
                bestScore = score;
                best = i;
            }
        }
        return best;
    }

    /// <summary>
    /// How close two curves lie to one another in PLAN: the mean
    /// nearest-point distance taken from the first to the second, plus
    /// the same from the second to the first, halved. Zero for two
    /// curves whose sample points coincide, and it grows with
    /// separation. Symmetric by construction, because a correspondence
    /// that depended on reading order would not be a correspondence.
    ///
    /// PLAN only. The two curves being compared are at different
    /// heights by construction, so a three-dimensional distance would
    /// score every pair by the course height they are apart rather than
    /// by where in plan they sit, which is the thing being asked.
    /// </summary>
    private static double PlanProximity(
        SkinLevelCurve first,
        SkinLevelCurve second) =>
        (MeanNearestPlanDistance(first, second) +
         MeanNearestPlanDistance(second, first)) / 2.0;

    /// <summary>The mean, over one curve's sample points, of the plan
    /// distance from that point to the nearest sample point of the
    /// other curve.</summary>
    private static double MeanNearestPlanDistance(
        SkinLevelCurve from,
        SkinLevelCurve to)
    {
        double total = 0.0;
        foreach (double[] point in from.Points)
        {
            double nearest = double.PositiveInfinity;
            foreach (double[] other in to.Points)
            {
                double dx = point[0] - other[0];
                double dy = point[1] - other[1];
                double squared = dx * dx + dy * dy;
                if (squared < nearest)
                    nearest = squared;
            }
            total += Math.Sqrt(nearest);
        }
        return total / from.Points.Count;
    }

    /// <summary>
    /// Do two levels' components CORRESPOND, one for one? This is the
    /// test a band is refused on, and it is a test of the MATCHING, not
    /// of the count.
    ///
    /// Counting was the first answer and it is too weak: two ordinary
    /// surfaces keep the count and change the components. A two-hump
    /// barrel whose ridge dips between the humps cuts into the front and
    /// back STRIPS at 0.75 and into the two hump LOOPS at 1.00, two
    /// components at both heights and not the same two. A net where one
    /// island splits in the same band as another island dies reads two
    /// at every height while nothing above corresponds to anything
    /// below. Both were reproduced against the built plugin: the count
    /// test refused nothing, the bands were built, and the cells came
    /// back self-crossing and overlapping in plan (the two-hump barrel
    /// at S 0.6, CH 0.5: courses 70 cells with 10 self-crossing and 166
    /// overlapping pairs, the honeycomb 72 with 8 and 85).
    ///
    /// The rule: build the correspondence with MatchBelow in BOTH
    /// directions and require a mutual bijection. No curve on either
    /// level may be claimed by two, none may be left unclaimed, and the
    /// two maps must be inverses of each other. One test catches split,
    /// death, swap and simultaneous split-and-death, because all four
    /// break the same thing: on the two-hump barrel both mid strips
    /// claim the same upper loop, and on the split-and-death net both
    /// mid loops claim the same lower one.
    ///
    /// Two levels with no curves at all correspond trivially: there is
    /// nothing to bond and no cell will be built either way, so refusing
    /// would report a hole where there is no surface.
    /// </summary>
    private static bool Corresponds(
        IReadOnlyList<SkinLevelCurve> from,
        IReadOnlyList<SkinLevelCurve> to)
    {
        if (from.Count != to.Count)
            return false;
        if (from.Count == 0)
            return true;
        var forward = new int[from.Count];
        var claimed = new bool[to.Count];
        for (int i = 0; i < from.Count; i++)
        {
            int match = MatchBelow(from[i], to);
            if (match < 0 || claimed[match])
                return false;
            claimed[match] = true;
            forward[i] = match;
        }
        var back = new bool[from.Count];
        for (int j = 0; j < to.Count; j++)
        {
            int match = MatchBelow(to[j], from);
            if (match < 0 || back[match] || forward[match] != j)
                return false;
            back[match] = true;
        }
        return true;
    }

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

    private static int NearestInPlan(SkinLevelCurve curve, double[] target)
    {
        int best = 0;
        double bestDistance = double.PositiveInfinity;
        for (int i = 0; i < curve.Points.Count; i++)
        {
            double dx = curve.Points[i][0] - target[0];
            double dy = curve.Points[i][1] - target[1];
            double distance = dx * dx + dy * dy;
            if (distance < bestDistance)
            {
                bestDistance = distance;
                best = i;
            }
        }
        return best;
    }

    /// <summary>The trace vertex on the +X bearing from the loop's plan
    /// centroid: the vertex whose unit plan offset from the centroid has
    /// the greatest X component. First index wins a tie.</summary>
    private static int PlusXVertex(SkinLevelCurve curve)
    {
        double cx = curve.Points.Average(point => point[0]);
        double cy = curve.Points.Average(point => point[1]);
        int best = 0;
        double bestScore = double.NegativeInfinity;
        for (int i = 0; i < curve.Points.Count; i++)
        {
            double dx = curve.Points[i][0] - cx;
            double dy = curve.Points[i][1] - cy;
            double reach = Math.Sqrt(dx * dx + dy * dy);
            double score = reach > 1.0e-12
                ? dx / reach
                : double.NegativeInfinity;
            if (score > bestScore + 1.0e-12)
            {
                bestScore = score;
                best = i;
            }
        }
        return best;
    }

    // ---- the (u, z) map -------------------------------------------------

    /// <summary>
    /// The setout map's point at signed arc length u from the curve's
    /// seam: (u, z) evaluated on the level curve that IS height z. An
    /// open strip clamps (u beyond an end is the end); a closed loop
    /// wraps.
    /// </summary>
    public static double[] PointAt(SkinLevelCurve curve, double u) =>
        PointAtArc(curve, curve.Seam + u);

    private static double[] PointAtArc(SkinLevelCurve curve, double s)
    {
        double length = curve.Length;
        if (curve.Closed)
        {
            s %= length;
            if (s < 0.0)
                s += length;
        }
        else
        {
            s = Math.Min(Math.Max(s, 0.0), length);
        }
        int segments = curve.Closed
            ? curve.Points.Count
            : curve.Points.Count - 1;
        for (int i = 0; i < segments; i++)
        {
            double start = curve.Cumulative[i];
            double end = i + 1 < curve.Points.Count
                ? curve.Cumulative[i + 1]
                : length;
            if (s <= end + 1.0e-12 || i == segments - 1)
            {
                double[] a = curve.Points[i];
                double[] b = curve.Points[(i + 1) % curve.Points.Count];
                double span = end - start;
                double t = span > 1.0e-15 ? (s - start) / span : 0.0;
                return Lerp(a, b, Math.Min(Math.Max(t, 0.0), 1.0));
            }
        }
        return curve.Points[^1];
    }

    /// <summary>
    /// The sampled run from signed offset uStart to uEnd (uStart less
    /// than or equal to uEnd) along a level curve: both endpoints plus
    /// every trace vertex strictly between them, so a cell edge FOLLOWS
    /// the surface instead of chording across it. On a closed loop the
    /// run goes the increasing-u way round.
    /// </summary>
    public static List<double[]> Run(
        SkinLevelCurve curve,
        double uStart,
        double uEnd)
    {
        var run = new List<double[]> { PointAt(curve, uStart) };
        double length = curve.Length;
        if (!curve.Closed)
        {
            double sStart =
                Math.Min(Math.Max(curve.Seam + uStart, 0.0), length);
            double sEnd =
                Math.Min(Math.Max(curve.Seam + uEnd, 0.0), length);
            for (int i = 0; i < curve.Points.Count; i++)
            {
                double at = curve.Cumulative[i];
                if (at > sStart + 1.0e-9 && at < sEnd - 1.0e-9)
                    run.Add(curve.Points[i]);
            }
        }
        else
        {
            double span = uEnd - uStart;
            double sStart = curve.Seam + uStart;
            var interior = new List<(double Forward, double[] Point)>();
            for (int i = 0; i < curve.Points.Count; i++)
            {
                double forward =
                    ((curve.Cumulative[i] - sStart) % length + length)
                    % length;
                if (forward > 1.0e-9 && forward < span - 1.0e-9)
                    interior.Add((forward, curve.Points[i]));
            }
            interior.Sort(
                (left, right) => left.Forward.CompareTo(right.Forward));
            foreach ((double _, double[] point) in interior)
                run.Add(point);
        }
        run.Add(PointAt(curve, uEnd));
        return run;
    }

    // ---- the plan guarantee, enforced (spec section 4) ------------------

    /// <summary>
    /// Which side of the directed line from-to the point at lies on:
    /// positive left, negative right, zero on the line. Plan only.
    /// </summary>
    private static double PlanSide(double[] from, double[] to, double[] at) =>
        (to[0] - from[0]) * (at[1] - from[1]) -
        (to[1] - from[1]) * (at[0] - from[0]);

    /// <summary>
    /// Do two plan segments cross PROPERLY: does each strictly separate
    /// the other's ends? Touching at an endpoint and lying collinear are
    /// both excluded, because two cells sharing a joint edge are bonded
    /// neighbours and not an overlap.
    ///
    /// "Strictly" is a DISTANCE, and the tolerance is PlanFoldTolerance,
    /// one nanometre of perpendicular separation. The side values come
    /// back from PlanSide as cross products, which are AREAS: twice the
    /// triangle's area, or equivalently the segment's own length times
    /// the perpendicular distance from the point to its line. Comparing
    /// a raw cross product against a fixed floor therefore compares a
    /// distance times a length, so the effective tolerance moves with
    /// the segment: at a floor of 1e-9 it was about 1e-11 m on a 100 m
    /// edge and about 0.65 mm on the 1.5 micron edges of a crown epsilon
    /// loop, which is a millimetre of tolerance inside a cell a micron
    /// across. Measured against an arithmetic that divides through, the
    /// two answers disagreed 72 times in 422 configurations, every one
    /// on the honeycomb and every one at the crown, the deepest fold
    /// missed being 7.586e-6 m. Dividing each side value by its own
    /// segment's length makes the comparison a perpendicular distance in
    /// metres, the same tolerance everywhere on the model.
    /// </summary>
    private static bool PlanSegmentsCross(
        double[] a,
        double[] b,
        double[] c,
        double[] d)
    {
        double first = PlanDistance(a, b);
        double second = PlanDistance(c, d);
        // A segment of no length in plan separates nothing: both its side
        // values are zero however the arithmetic is written, and the
        // division would be meaningless. The floor is a picometre, below
        // which the direction of the segment is itself noise.
        if (first < 1.0e-12 || second < 1.0e-12)
            return false;
        double d1 = PlanSide(a, b, c) / first;
        double d2 = PlanSide(a, b, d) / first;
        double d3 = PlanSide(c, d, a) / second;
        double d4 = PlanSide(c, d, b) / second;
        return ((d1 > PlanFoldTolerance && d2 < -PlanFoldTolerance) ||
                (d1 < -PlanFoldTolerance && d2 > PlanFoldTolerance)) &&
               ((d3 > PlanFoldTolerance && d4 < -PlanFoldTolerance) ||
                (d3 < -PlanFoldTolerance && d4 > PlanFoldTolerance));
    }

    /// <summary>
    /// How deep a fold has to be before it is a fold: ONE NANOMETRE of
    /// perpendicular separation in plan.
    ///
    /// It is a physical statement and it wants a physical justification
    /// at both ends. Below it: a vault sited on an OS grid carries
    /// coordinates of order 1e5 m, and a double holds those to about
    /// 1e5 x 2^-52 = 2e-11 m, so a nanometre is above the arithmetic's
    /// own noise even at the worst siting this engine expects and two
    /// orders above it at the 100 m of an ordinary model. Above it:
    /// nothing anyone builds is a nanometre. A cell whose plan
    /// projection doubles back by less than that is a cell whose edges
    /// touch, and two cells that come within a nanometre of one another
    /// are two cells that meet at their joint, which is what a bonded
    /// course is made of. So the predicate refuses to call either a
    /// crossing, and says why in a unit an author could measure.
    /// </summary>
    private const double PlanFoldTolerance = 1.0e-9;

    /// <summary>The distance between two points in PLAN, which is what
    /// turns a cross product into a perpendicular distance.</summary>
    private static double PlanDistance(double[] a, double[] b)
    {
        double dx = a[0] - b[0];
        double dy = a[1] - b[1];
        return Math.Sqrt(dx * dx + dy * dy);
    }

    /// <summary>The even-odd ray cast: is the plan point (x, y) inside
    /// the outline's plan projection?</summary>
    private static bool PlanContains(
        double x,
        double y,
        IReadOnlyList<double[]> outline)
    {
        bool inside = false;
        for (int i = 0, j = outline.Count - 1; i < outline.Count; j = i++)
        {
            if ((outline[i][1] > y) != (outline[j][1] > y) &&
                x < (outline[j][0] - outline[i][0]) *
                    (y - outline[i][1]) /
                    (outline[j][1] - outline[i][1]) + outline[i][0])
            {
                inside = !inside;
            }
        }
        return inside;
    }

    /// <summary>
    /// Does an outline's PLAN projection cross ITSELF? True when two
    /// edges that do not share a vertex cross properly. The outline is
    /// an open ring, so edge i runs from point i to point i + 1 modulo
    /// the count and the closing edge is edge count - 1; edges i and
    /// i + 1 are adjacent, and so are edge 0 and the closing edge.
    ///
    /// PUBLIC because the smoke harness calls this exact method rather
    /// than keeping arithmetic of its own. The engine and the harness
    /// must not be able to disagree about what a bad cell is: a filter
    /// that dropped what the harness would have accepted, or kept what
    /// it would have refused, would be worse than no filter at all.
    /// </summary>
    public static bool PlanSelfCrosses(IReadOnlyList<double[]> outline)
    {
        int count = outline.Count;
        for (int i = 0; i < count; i++)
        {
            for (int j = i + 1; j < count; j++)
            {
                if (j == i + 1 || (i == 0 && j == count - 1))
                    continue;
                if (PlanSegmentsCross(
                        outline[i], outline[(i + 1) % count],
                        outline[j], outline[(j + 1) % count]))
                {
                    return true;
                }
            }
        }
        return false;
    }

    /// <summary>
    /// A point that is certainly INSIDE an outline in plan, as {x, y};
    /// null when the outline has no interior to find one in.
    ///
    /// PUBLIC, and meant to be computed ONCE PER OUTLINE by whatever
    /// walks the pairs, which then hands it to
    /// PlansOverlapWithInteriors. The point does not depend on the other
    /// outline, so a pair walk that asks for it again in every pair pays
    /// O(k squared) times for O(k) answers, and this is not a cheap
    /// answer to buy.
    ///
    /// Two rules, tried in order, each candidate confirmed by the same
    /// PlanContains that every other part of the filter judges
    /// insideness with, so what counts as inside is ONE rule whichever
    /// branch found the point:
    ///
    /// 1. The plan MEAN, because on a convex cell it is inside and costs
    ///    four arithmetic operations a corner. Nearly every cell of a
    ///    pattern is convex enough for it.
    /// 2. Where the mean falls outside, which a sufficiently non-convex
    ///    outline's does (a C shape's mean sits in its notch), the
    ///    outline is TRIANGULATED by the same rule the net triangulates
    ///    its faces and the CENTROID of a triangle is taken instead: a
    ///    triangle of a valid triangulation lies inside the polygon, and
    ///    its centroid lies in that triangle's own interior. The
    ///    triangles are tried in SplitPolygon's own order and the first
    ///    centroid PlanContains accepts wins, which steps over any
    ///    triangle a degenerate corner made flat.
    ///
    /// The triangles come from SplitPolygonInOrder, which produces them
    /// ONE AT A TIME in exactly the order SplitPolygon writes them, so
    /// the point is the point the whole triangulation would have given
    /// and the outline is only split as far as the first accepted
    /// centroid. That is nearly always the first triangle, and building
    /// the rest of the triangulation to reach it was most of the cost of
    /// this method: measured on one PlansOverlap call against a square
    /// host, a 192-corner outline took 2.3 SECONDS to triangulate whole.
    ///
    /// Null, and no point, only for an outline of fewer than three
    /// corners or one so degenerate that no triangle of it has an
    /// interior at all.
    /// </summary>
    public static double[]? PlanInteriorPoint(
        IReadOnlyList<double[]> outline)
    {
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
            double cx =
                (outline[triangle[0]][0] +
                 outline[triangle[1]][0] +
                 outline[triangle[2]][0]) / 3.0;
            double cy =
                (outline[triangle[0]][1] +
                 outline[triangle[1]][1] +
                 outline[triangle[2]][1]) / 3.0;
            if (PlanContains(cx, cy, outline))
                return new[] { cx, cy };
        }
        return null;
    }

    /// <summary>
    /// Do two outlines OVERLAP in plan? True when any edge of one
    /// properly crosses any edge of the other, and true when one's own
    /// interior point lies inside the other, which is the containment
    /// case no edge crossing can see.
    ///
    /// The interior point is PlanInteriorPoint's, and the reason it is
    /// not simply the plan mean is a stated blind spot this closes. The
    /// mean of a sufficiently non-convex outline falls OUTSIDE it (a C
    /// shape's mean sits in the notch), and the rule before this one
    /// tested the mean for interiority and, finding it outside, SKIPPED
    /// the containment test rather than looking harder. So a
    /// sufficiently non-convex cell lying wholly inside another passed
    /// as no overlap, with no edge crossing anywhere to catch it. It was
    /// never observed in 422 measured configurations, which is what
    /// makes it worth closing now: a latent hole in the plan guarantee
    /// is a hole that will be found by a surface nobody has drawn yet,
    /// and the guarantee is the reason the native patterns exist.
    ///
    /// Touching along a shared joint edge is NOT overlap: two cells of
    /// the same course meet at their joint by construction and the
    /// crossing test is strict.
    ///
    /// PUBLIC for the same reason PlanSelfCrosses is. This is the
    /// CONVENIENCE form, which finds both interior points itself; a
    /// caller walking pairs should find each outline's point once and
    /// call PlansOverlapWithInteriors instead.
    /// </summary>
    public static bool PlansOverlap(
        IReadOnlyList<double[]> first,
        IReadOnlyList<double[]> second) =>
        PlansOverlapWithInteriors(
            first,
            PlanInteriorPoint(first),
            second,
            PlanInteriorPoint(second));

    /// <summary>
    /// PlansOverlap with each outline's interior point ALREADY FOUND, as
    /// PlanInteriorPoint returns it, or null where that outline has no
    /// interior. The answer is PlansOverlap's exactly; what changes is
    /// who pays for the points.
    ///
    /// This exists because an interior point is a property of ONE
    /// outline and finding it is not free, while the pair walk that
    /// needs it is quadratic. Finding it inside the pair test therefore
    /// bought O(k) answers O(k squared) times, and on an outline whose
    /// mean falls outside itself the cost of one answer runs to
    /// milliseconds and beyond: measured on a square host, one pair test
    /// on a 128-corner outline took 0.4 seconds and on a 192-corner
    /// outline 2.3, against 0.05 milliseconds when the mean served. An
    /// annular vault at a Size of 3 m has exactly that kind of cell, so
    /// the courses engine on a 96-a-ring mesh took over three minutes on
    /// the canvas thread, at every nudge of the slider. The interior
    /// points are now found once each, where the outlines are walked,
    /// and handed in here.
    ///
    /// The points are TRUSTED. Nothing is recomputed and nothing is
    /// checked: PlanInteriorPoint has already tested its answer with the
    /// same PlanContains this test judges containment with, and a second
    /// test here would be the very cost this signature exists to avoid.
    /// </summary>
    public static bool PlansOverlapWithInteriors(
        IReadOnlyList<double[]> first,
        double[]? firstInside,
        IReadOnlyList<double[]> second,
        double[]? secondInside)
    {
        for (int i = 0; i < first.Count; i++)
        {
            for (int j = 0; j < second.Count; j++)
            {
                if (PlanSegmentsCross(
                        first[i], first[(i + 1) % first.Count],
                        second[j], second[(j + 1) % second.Count]))
                {
                    return true;
                }
            }
        }
        if (firstInside is not null &&
            PlanContains(firstInside[0], firstInside[1], second))
        {
            return true;
        }
        return secondInside is not null &&
               PlanContains(secondInside[0], secondInside[1], first);
    }

    /// <summary>
    /// The plan guarantee ENFORCED rather than argued.
    ///
    /// Spec section 4 claims cells from the native patterns cannot
    /// self-cross or overlap in plan, and that claim was carried by an
    /// argument about the height-field setout. Three successive
    /// adversarial rounds each found a surface where the argument
    /// fails: a transition on a rotated model, a non-convex re-entrant
    /// plan (an L-shaped shell gives one self-crossing courses cell at
    /// CH 0.5 and is clean at six other course heights), and the
    /// honeycomb over closed level curves whose length changes quickly.
    /// ONE bad cell makes Bench Studio reject the entire tessellation,
    /// so an argued guarantee is worth nothing at the sidecar.
    ///
    /// The rule, run in EMISSION ORDER over the sorted cells, which is
    /// the order the component hands out and the studio builds in:
    /// drop a cell whose plan projection self-crosses, then drop a cell
    /// whose plan projection overlaps a cell that has ALREADY SURVIVED.
    /// Each kind is counted, both counts reach the diagnostics as their
    /// own lines, and the component raises a runtime Warning when
    /// either is non-zero, so a dropped cell is never silent.
    ///
    /// This is exactly what the force-aligned worker already does (its
    /// diagnostics carry plan_degenerate_dropped and
    /// plan_overlap_dropped), so the native patterns are being brought
    /// up to the standard the third pattern already meets rather than
    /// given a new indulgence. The filter is a guarantee and NOT a
    /// licence to stop caring: every clean fixture in the smoke harness
    /// asserts that both counts are ZERO, so a regression that starts
    /// dropping cells fails the gate loudly instead of quietly shipping
    /// a smaller pattern.
    ///
    /// The plan bounding boxes are a pure speed-up over the pair walk
    /// and change no answer: two outlines whose plan boxes are disjoint
    /// can neither cross nor contain one another.
    ///
    /// The INTERIOR POINTS are the other speed-up, and change no answer
    /// either. Each outline's point is found ONCE, here, where the
    /// outlines are walked anyway, and handed to every pair test that
    /// outline takes part in. Found inside the pair test instead, as it
    /// was, an outline's point was recomputed for every cell it was
    /// measured against, and on a cell whose plan mean falls outside
    /// itself, which is what an annular vault gives at a large Size,
    /// finding it costs milliseconds: the courses engine spent nine
    /// seconds on a 13 by 48 annular vault at Size 3 and over three
    /// minutes at 96 a ring, on Grasshopper's canvas thread, for every
    /// nudge of the slider.
    /// </summary>
    private static List<SkinCell> KeepValidPlans(
        IReadOnlyList<SkinCell> cells,
        out int degenerateDropped,
        out int overlapDropped)
    {
        degenerateDropped = 0;
        overlapDropped = 0;
        var kept = new List<SkinCell>(cells.Count);
        var boxes = new List<(double MinX, double MinY,
            double MaxX, double MaxY)>(cells.Count);
        var insides = new List<double[]?>(cells.Count);
        foreach (SkinCell cell in cells)
        {
            if (cell.Outline.Count < 3 || PlanSelfCrosses(cell.Outline))
            {
                degenerateDropped++;
                continue;
            }
            double minX = double.PositiveInfinity;
            double minY = double.PositiveInfinity;
            double maxX = double.NegativeInfinity;
            double maxY = double.NegativeInfinity;
            foreach (double[] point in cell.Outline)
            {
                minX = Math.Min(minX, point[0]);
                minY = Math.Min(minY, point[1]);
                maxX = Math.Max(maxX, point[0]);
                maxY = Math.Max(maxY, point[1]);
            }
            double[]? inside = PlanInteriorPoint(cell.Outline);
            bool overlaps = false;
            for (int at = 0; at < kept.Count && !overlaps; at++)
            {
                (double MinX, double MinY, double MaxX, double MaxY) box =
                    boxes[at];
                if (box.MinX > maxX + 1.0e-9 ||
                    box.MaxX < minX - 1.0e-9 ||
                    box.MinY > maxY + 1.0e-9 ||
                    box.MaxY < minY - 1.0e-9)
                {
                    continue;
                }
                overlaps = PlansOverlapWithInteriors(
                    cell.Outline, inside, kept[at].Outline, insides[at]);
            }
            if (overlaps)
            {
                overlapDropped++;
                continue;
            }
            kept.Add(cell);
            boxes.Add((minX, minY, maxX, maxY));
            insides.Add(inside);
        }
        return kept;
    }

    // ---- small shared arithmetic ----------------------------------------

    private static double Distance(double[] a, double[] b)
    {
        double dx = a[0] - b[0];
        double dy = a[1] - b[1];
        double dz = a[2] - b[2];
        return Math.Sqrt(dx * dx + dy * dy + dz * dz);
    }

    private static double[] Lerp(double[] a, double[] b, double t) => new[]
    {
        a[0] + (b[0] - a[0]) * t,
        a[1] + (b[1] - a[1]) * t,
        a[2] + (b[2] - a[2]) * t
    };

    /// <summary>Drop consecutive duplicates and a closing repeat, so an
    /// outline is a clean open ring the component closes itself.</summary>
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
        return cleaned;
    }

    // ---- pattern 0: courses (spec section 5) ----------------------------

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
                "the top course is an OPEN strip, so its crown is a ridge " +
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
        // both of whose ends exceed the level. A vertex EXACTLY AT the
        // level counts as exceeding it here (>=, not >), matching the
        // half-open rule Trace's own Crosses uses (SkinPatterns.cs:839-845):
        // a vertex on the cut belongs to the upper side. Without that a
        // mesh ring landing exactly on level (an exact tie, not a
        // near-miss) breaks the walk one ring short of where the true
        // surface plainly continues, turning one connected saddle into two
        // false keystones either side of the tie.
        bool AboveFace(int[] triangle)
        {
            foreach (int corner in triangle)
            {
                if (!(net.Levels[corner] >= level))
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
                if (!(net.Levels[a] >= level) || !(net.Levels[b] >= level))
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
                        // R alone is not enough: a RING or GROIN ridge is a
                        // discrete row of vertices with nothing strictly
                        // above it on either side (rule 2.5.3), so R is
                        // EMPTY for both components even though they meet
                        // AT the ridge. The other component's straddling
                        // band reaching a face of my OWN straddling band is
                        // the same saddle, seen with no interior faces to
                        // walk through: the region above one side is
                        // reachable from the other's own boundary (rule
                        // 2.5.2), not only from an interior R.
                        if (region.Contains(candidate) ||
                            straddling[componentAt].Contains(candidate))
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

    /// <summary>
    /// Running-bond quads, the Bench Studio bonded-courses algorithm
    /// restated on the thrust surface. Bands of Course Height from the
    /// base; on each band's MID-height level curve the pitch is
    /// P = L / max(1, round(L / S)), uniform within the course; a CLOSED
    /// loop is n equal pieces rotated half a pitch on odd courses; an
    /// OPEN strip's joints lie on a grid of pitch P anchored at the seam
    /// with the course's phase, truncated at the ends, so interior pieces
    /// are exactly P, only the two end pieces absorb the phase, every
    /// course is individually symmetric about the seam and adjacent
    /// courses carry the half-piece stagger. Cells map to the band
    /// boundary curves by normalised arc length from the matching seams.
    /// </summary>
    public static SkinPatternResult Courses(
        SkinNet net,
        double size,
        double courseHeight)
    {
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
        var capGirths = new List<double>();
        var capRefusals = new List<string>();
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
            bool topBand = band.Course == bands - 1;
            bool[]? onBoundary = topBand ? FacesOnBoundary(net) : null;
            for (int component = 0; component < mids.Count; component++)
            {
                SkinLevelCurve mid = mids[component];
                int lowerAt = MatchBelow(mid, lowers);
                int upperAt = MatchBelow(mid, uppers);
                if (lowerAt < 0 || upperAt < 0 || !(mid.Length > 1.0e-9))
                    continue;
                SkinLevelCurve lowerCurve = lowers[lowerAt];
                SkinLevelCurve upperCurve = uppers[upperAt];

                // Declared BEFORE the test, not in it. C# assigns an out
                // parameter only when the call is made, and `topBand &&`
                // will short-circuit on every band but the last, so a
                // refusedBy declared inside the condition is an unassigned
                // local at the line below and the file does not compile.
                string refusedBy = string.Empty;
                if (topBand &&
                    CapQualifies(
                        net, band.Low, lowerAt, lowers, onBoundary!,
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
                    for (int at = 0; at < lowerCurve.Points.Count; at++)
                        loop.Add(lowerCurve.Points[at]);
                    List<double[]> capOutline = Dedupe(loop);
                    if (capOutline.Count >= 3)
                    {
                        capGirths.Add(lowerCurve.Length);
                        keyed.Add((
                            band.Course,
                            component,
                            -lowerCurve.Length / 2.0,
                            new SkinCell(
                                band.Course, capOutline, false,
                                -lowerCurve.Length / 2.0,
                                lowerCurve.Length / 2.0,
                                true)));
                        continue;
                    }
                }
                if (topBand && refusedBy.Length > 0)
                    capRefusals.Add(refusedBy);

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
        // Rule 2.3.2a: a cap's girth is metres against ordinary pieces of
        // order S, so a cap left in the piece-length statistics dominates
        // the maximum and the max-over-min ratio single-handedly.
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
        return new SkinPatternResult(
            cells,
            bands,
            PatternDiagnostics(
                "courses", cells.Count, bands,
                cells.Where(cell => !cell.Cap)
                    .Select(cell => cell.U1 - cell.U0).ToList(),
                "half a pitch on odd courses",
                cells.Count(cell => cell.Clipped),
                degenerateDropped, overlapDropped,
                TransitionLine(
                    "courses", transitionBands, transitions,
                    FieldKindOf(net)),
                capLine),
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
            capGirths,
            Array.Empty<int>(),
            0,
            0,
            0,
            Array.Empty<int>(),
            0,
            0,
            resolved.ExtraLevels,
            resolved.Passes);
    }

    /// <summary>
    /// Spec section 5's banding: course r spans
    /// [zMin + r CH, zMin + (r + 1) CH); the top band runs to the crown,
    /// and a top band whose rise is under a quarter of CH merges into the
    /// band below rather than shipping a sliver course.
    /// </summary>
    public static int BandCount(
        double zMin,
        double zMax,
        double courseHeight)
    {
        double rise = zMax - zMin;
        int bands = Math.Max(
            1, (int)Math.Ceiling(rise / courseHeight - 1.0e-9));
        if (bands > 1 &&
            rise - (bands - 1) * courseHeight < courseHeight / 4.0)
        {
            bands -= 1;
        }
        return bands;
    }

    /// <summary>
    /// The 1 mm floors, negated comparisons so NaN is caught: NaN fails
    /// every comparison, so a guard written "value <= floor" would let
    /// NaN sail past. The component floors CH with a warning before
    /// calling; the engine refuses outright so the harness can measure
    /// the floor without a canvas.
    /// </summary>
    private static void RequireSizes(double size, double courseHeight)
    {
        if (!(size > 0.001))
        {
            throw new ArgumentException(
                "S must be greater than 1 mm (0.001 m); received " +
                $"{size}.");
        }
        if (!(courseHeight > 0.001))
        {
            throw new ArgumentException(
                "Course Height must be greater than 1 mm (0.001 m); " +
                $"received {courseHeight}.");
        }
    }

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

    /// <summary>
    /// The joint grid on one mid-height level curve, as spans. CLOSED:
    /// n equal pieces from the seam, the whole division rotated by the
    /// phase. OPEN: grid joints at phase + k P strictly inside
    /// (-L/2, L/2) plus the two strip ends, so interior pieces are
    /// exactly P and the end pieces absorb the phase.
    /// </summary>
    private static List<(double U0, double U1)> CourseSpans(
        SkinLevelCurve mid,
        int pieces,
        double pitch,
        double phase)
    {
        var spans = new List<(double, double)>();
        if (mid.Closed)
        {
            for (int k = 0; k < pieces; k++)
            {
                spans.Add(
                    (phase + k * pitch, phase + (k + 1) * pitch));
            }
            return spans;
        }
        double half = mid.Length / 2.0;
        var joints = new List<double> { -half };
        int first = (int)Math.Ceiling((-half - phase) / pitch - 1.0e-9);
        for (int k = first; ; k++)
        {
            double joint = phase + k * pitch;
            if (joint >= half - 1.0e-9)
                break;
            if (joint > -half + 1.0e-9)
                joints.Add(joint);
        }
        joints.Add(half);
        for (int j = 0; j + 1 < joints.Count; j++)
            spans.Add((joints[j], joints[j + 1]));
        return spans;
    }

    /// <summary>
    /// Spec section 5's cell: the lower boundary curve's sampled run
    /// between the two joints, the straight joint edge up, the upper
    /// curve's run back, and the implicit closing edge down. A joint at
    /// signed arc u on the mid curve lands at u (L_boundary / L_mid) on
    /// each boundary curve, normalised arc length from the matching
    /// seams.
    /// </summary>
    private static SkinCell BandCell(
        int course,
        SkinLevelCurve lowerCurve,
        SkinLevelCurve mid,
        SkinLevelCurve upperCurve,
        double u0,
        double u1,
        bool clipped)
    {
        double lowerRatio = lowerCurve.Length / mid.Length;
        double upperRatio = upperCurve.Length / mid.Length;
        var outline = new List<double[]>();
        outline.AddRange(
            Run(lowerCurve, u0 * lowerRatio, u1 * lowerRatio));
        List<double[]> back =
            Run(upperCurve, u0 * upperRatio, u1 * upperRatio);
        back.Reverse();
        outline.AddRange(back);
        return new SkinCell(course, Dedupe(outline), clipped, u0, u1);
    }

    /// <summary>
    /// Record one transition height interval, keeping the list free of
    /// duplicates: the honeycomb finds the same interval again for every
    /// lattice row that spans it, and the diagnostics line names each
    /// interval once.
    /// </summary>
    private static void AddTransition(
        List<(double Low, double High)> transitions,
        double low,
        double high)
    {
        foreach ((double at, double to) in transitions)
        {
            if (Math.Abs(at - low) <= 1.0e-12 &&
                Math.Abs(to - high) <= 1.0e-12)
            {
                return;
            }
        }
        transitions.Add((low, high));
    }

    /// <summary>
    /// The diagnostics line for refused transition bands, or null when
    /// there are none. It names how many bands were skipped and the
    /// heights each transition sits between, because the author needs to
    /// know WHERE the skin has a hole, not merely that it has one.
    /// </summary>
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
        // "do not correspond" rather than "splits": the refusal is decided
        // on the matching, so it fires for a curve that splits, one that
        // dies, and two that swap places at an unchanged count, and the
        // author is told which heights rather than which of the three.
        return
            $"Transition bands skipped: {skipped} (level curves do not " +
            $"correspond {where}; {name} cannot bond across it)";
    }

    /// <summary>The D output's text for a native pattern: the pattern
    /// name, cell and course counts, mean/min/max piece length, the
    /// stagger, the count of boundary-clipped cells, the two
    /// plan-validity drop counts and, where the level curves do not
    /// correspond, the refused transition bands. The key of every line
    /// is capitalised, so the transition line reads beside the rest
    /// rather than under it. The two drop lines are worded exactly as
    /// the force-aligned pattern words its own, because they mean the
    /// same thing and an author reading D should not have to notice
    /// which pattern produced it.</summary>
    private static string PatternDiagnostics(
        string name,
        int cellCount,
        int courseCount,
        IReadOnlyList<double> pieceLengths,
        string stagger,
        int clipped,
        int planDegenerateDropped,
        int planOverlapDropped,
        string? transitions = null,
        string? caps = null)
    {
        static string F(double value) =>
            value.ToString("F3", CultureInfo.InvariantCulture);
        var lines = new List<string>
        {
            $"Pattern: {name}",
            $"Cells: {cellCount}",
            $"Courses: {courseCount}"
        };
        if (pieceLengths.Count > 0)
        {
            lines.Add(
                $"Piece length: mean {F(pieceLengths.Average())} m, " +
                $"min {F(pieceLengths.Min())} m, " +
                $"max {F(pieceLengths.Max())} m");
        }
        lines.Add($"Stagger: {stagger}");
        lines.Add($"Boundary-clipped cells: {clipped}");
        lines.Add(
            $"Plan-degenerate cells dropped: {planDegenerateDropped} " +
            "(self-crossing in plan; excluded automatically so the " +
            "sidecar imports)");
        lines.Add(
            $"Plan-overlap cells dropped: {planOverlapDropped} " +
            "(overlapped another surviving cell in plan; excluded " +
            "automatically so the sidecar imports)");
        if (transitions is not null)
            lines.Add(transitions);
        if (caps is not null)
            lines.Add(caps);
        return string.Join("\n", lines);
    }

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
            0,
            0,
            1);

    // ---- pattern 1: hexagonal (spec section 6) --------------------------

    /// <summary>One chart: the traced components at successive heights,
    /// chained bottom-up by plan-proximity matching, so each chain is one
    /// side of the surface set out independently (spec section 4).</summary>
    private sealed class SkinChart
    {
        public List<double> Heights { get; } = new();

        public List<SkinLevelCurve> Curves { get; } = new();
    }

    private static List<SkinChart> BuildCharts(
        IReadOnlyList<IReadOnlyList<SkinLevelCurve>> traced)
    {
        var charts = new List<SkinChart>();
        IReadOnlyList<SkinLevelCurve> below = Array.Empty<SkinLevelCurve>();
        var chartOf = new Dictionary<SkinLevelCurve, SkinChart>();
        foreach (IReadOnlyList<SkinLevelCurve> level in traced)
        {
            foreach (SkinLevelCurve curve in level)
            {
                int matched = MatchBelow(curve, below);
                // A chart takes a successor only while the matched curve
                // is still its top: the second component matched to one
                // curve (a split) starts a chart of its own.
                SkinChart? chart =
                    matched >= 0 &&
                    chartOf.TryGetValue(
                        below[matched], out SkinChart? found) &&
                    found.Curves[^1] == below[matched]
                        ? found
                        : null;
                if (chart is null)
                {
                    chart = new SkinChart();
                    charts.Add(chart);
                }
                chart.Heights.Add(curve.Level);
                chart.Curves.Add(curve);
                chartOf[curve] = chart;
            }
            if (level.Count > 0)
                below = level;
        }
        return charts;
    }

    private static SkinLevelCurve CurveAt(SkinChart chart, double height)
    {
        for (int i = 0; i < chart.Heights.Count; i++)
        {
            if (Math.Abs(chart.Heights[i] - height) <= 1.0e-9)
                return chart.Curves[i];
        }
        // The chart does not reach this height: its nearest end stands in
        // (the vertex is being clamped to the chart anyway).
        return height < chart.Heights[0]
            ? chart.Curves[0]
            : chart.Curves[^1];
    }

    /// <summary>
    /// A stretched honeycomb in the setout plane, width S and height
    /// 2 CH, so the bond reads at the same course rhythm as pattern 0.
    /// The flat-topped hexagon centred at (uc, zc) has vertices, in
    /// order: (uc - S/4, zc - CH), (uc + S/4, zc - CH), (uc + S/2, zc),
    /// (uc + S/4, zc + CH), (uc - S/4, zc + CH), (uc - S/2, zc). The
    /// lattice is generated by the translations (0.75 S, CH) and
    /// (0, 2 CH), which tiles the plane with these cells exactly;
    /// centres are laid out from the seam outward, so the crown column
    /// sits on the seam. A candidate is a cell when its raw (u, z)
    /// extent intersects the chart's interior, measured in z against the
    /// chart's own extremes and in u against the half-length of the
    /// level curve at the candidate's CENTRE row: a shell shallower than
    /// CH still grows one clipped course instead of nothing, and a
    /// candidate lying wholly beyond the curve it sits on is still not a
    /// cell. Each vertex
    /// maps through the setout map at its own height; a cell crossing
    /// the surface boundary or the crown is
    /// CLIPPED to it and KEPT (a coverage hole is worse than an
    /// odd-shaped rim piece); the two horizontal edges follow their
    /// level curves, the rest are straight chords; the course index is
    /// the band holding the cell's clamped lattice CENTRE height. That
    /// is the spec's "centroid height" resolved as the centre, a
    /// deliberate substitution recorded in the plan's Task 3 note: a
    /// symmetric hexagon's centroid IS its centre, so the two rules
    /// agree on every unclipped cell, and the centre stays
    /// deterministic on clipped cells where a clipped outline's
    /// centroid would drift with the clip.
    /// </summary>
    public static SkinPatternResult Hexagonal(
        SkinNet net,
        double size,
        double courseHeight)
    {
        RequireSizes(size, courseHeight);
        (double dMin, double dMax) = LevelRange(net);
        if (net.Faces.Count == 0 || !(dMax - dMin > 1.0e-9))
            return Empty("hexagonal", net);

        int bands = BandCount(dMin, dMax, courseHeight);
        double epsilon = Math.Max((dMax - dMin) * 1.0e-6, 1.0e-9);
        double dBottom = dMin + epsilon;
        double dTop = dMax - epsilon;
        double clipTolerance = 10.0 * epsilon;

        // Every lattice height is dMin + CH * row for an integer row:
        // the base centre sits at zRef = dMin + CH (so the seam column's
        // bottom row lands its lower edge on the base rim), and both
        // lattice translations move by whole multiples of CH. Rows -1 to
        // topRow + 1 cover every vertex a candidate cell can have; rows
        // beyond the surface clamp to the epsilon-pulled extremes and
        // collapse to shared traces.
        int topRow = (int)Math.Ceiling(
            (dMax - dMin) / courseHeight - 1.0e-9);
        double ClampedRowLevel(int row) =>
            Math.Min(Math.Max(dMin + courseHeight * row, dBottom), dTop);
        List<double> heights = Enumerable
            .Range(-1, topRow + 3)
            .Select(ClampedRowLevel)
            .Distinct()
            .ToList();
        IReadOnlyList<IReadOnlyList<SkinLevelCurve>> traced =
            TraceAll(net, heights);
        List<SkinChart> charts = BuildCharts(traced);

        // The TOPOLOGY TRANSITIONS, found once for the whole net: a pair
        // of consecutive levels whose components do not CORRESPOND one
        // for one is a height a hexagon cannot bond across, because the
        // vertices of one cell would map through curves that are not the
        // same piece of surface. Every lattice row spanning such an
        // interval is refused whole, the same ruling the courses engine
        // follows and the same correspondence test.
        var transitions = new List<(double Low, double High)>();
        for (int level = 0; level + 1 < heights.Count; level++)
        {
            if (!Corresponds(traced[level], traced[level + 1]))
            {
                AddTransition(
                    transitions, heights[level], heights[level + 1]);
            }
        }
        var skippedRows = new HashSet<int>();

        var keyed =
            new List<(int Course, int Chart, double U0, SkinCell Cell)>();

        for (int chartAt = 0; chartAt < charts.Count; chartAt++)
        {
            SkinChart chart = charts[chartAt];
            double chartBottom = chart.Heights[0];
            double chartTop = chart.Heights[^1];
            double uMax =
                chart.Curves.Max(curve => curve.Length) / 2.0;
            int iMax = (int)Math.Ceiling(
                (uMax + size / 2.0) / (0.75 * size));
            for (int i = -iMax; i <= iMax; i++)
            {
                double uc = 0.75 * size * i;
                for (int j = (int)Math.Floor((-2.0 - i) / 2.0);
                     ;
                     j++)
                {
                    int centreRow = 1 + i + 2 * j;
                    if (centreRow > topRow + 1)
                        break;
                    if (centreRow < -1)
                        continue;
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

                    // The six setout vertices: (u offset, row offset).
                    (double U, int Row)[] setout =
                    {
                        (uc - size / 4.0, centreRow - 1),
                        (uc + size / 4.0, centreRow - 1),
                        (uc + size / 2.0, centreRow),
                        (uc + size / 4.0, centreRow + 1),
                        (uc - size / 4.0, centreRow + 1),
                        (uc - size / 2.0, centreRow)
                    };
                    bool clipped = false;
                    var mapped =
                        new (double U, SkinLevelCurve Curve)[6];
                    for (int v = 0; v < 6; v++)
                    {
                        double dRaw =
                            dMin + courseHeight * setout[v].Row;
                        double z = Math.Min(
                            Math.Max(dRaw, chartBottom), chartTop);
                        SkinLevelCurve curve = CurveAt(chart, z);
                        double half = curve.Length / 2.0;
                        double u = Math.Min(
                            Math.Max(setout[v].U, -half), half);
                        if (Math.Abs(z - dRaw) > clipTolerance ||
                            Math.Abs(u - setout[v].U) > clipTolerance)
                        {
                            clipped = true;
                        }
                        mapped[v] = (u, curve);
                    }

                    // The candidate's OWN level curve is the one at its
                    // CENTRE row, clamped onto the chart the same way its
                    // vertices are, and that curve's half-length is what
                    // the u half of the membership test is measured
                    // against.
                    double halfAtCentre = CurveAt(
                        chart,
                        Math.Min(
                            Math.Max(
                                dMin + courseHeight * centreRow,
                                chartBottom),
                            chartTop))
                        .Length / 2.0;

                    // MEMBERSHIP by INTERVAL OVERLAP, not by vertex.
                    // Asking whether any of the six mapped vertices lies
                    // strictly inside the chart is a proxy, and it fails
                    // on a shallow shell: when CH reaches the surface's
                    // rise, which the shipped 0.35 default does on any
                    // shell rising less than that, every lattice row
                    // lands at or beyond the chart's z extremes, no
                    // vertex is ever strictly inside, and the honeycomb
                    // comes back EMPTY while the courses engine on the
                    // same shell happily builds a band.
                    //
                    // The rule instead: a candidate is a cell when its
                    // raw (u, z) extent INTERSECTS the chart's interior.
                    // Its z extent is the two lattice rows the hexagon
                    // reaches, CH either side of the centre; its u
                    // extent is the flat-topped hexagon's own width, S,
                    // centred on the column; the z half is measured
                    // against chartBottom and chartTop; and the u half
                    // is measured against the half-length of the curve
                    // at the candidate's OWN CENTRE ROW.
                    //
                    // The centre row, and never the widest of the rows
                    // the candidate maps through, because the widest is
                    // where the second defect lived. On a barrel every
                    // level curve is the same length and the two agree,
                    // but on any shell whose curves shorten with height
                    // the widest comes from the row BELOW and admits
                    // candidates lying wholly beyond the curve the cell
                    // actually sits on. Those then clamp their vertices
                    // onto the short curve's ends together and the cells
                    // land on top of one another. Measured over a
                    // 210-configuration sweep of seven nets, three
                    // sizes and five course heights: the widest rule
                    // leaves 3716 overlapping pairs in plan and the
                    // centre-row rule 2358, on nets with closed level
                    // curves almost without exception.
                    //
                    // The clamp above has already pulled every vertex
                    // onto the chart and Dedupe drops what collapsed, so
                    // an intersecting candidate arrives as its CLIPPED
                    // outline, which is the pattern's standing rule for
                    // the rim. A candidate wholly outside its own curve
                    // fails, so the ruling that off-surface lattice
                    // cells are not cells stands.
                    //
                    // A closed loop's u domain is still cut at the
                    // meridian opposite the seam rather than wrapped, so
                    // the honeycomb never folds into itself.
                    bool overlaps =
                        dMin + courseHeight * (centreRow + 1)
                            > chartBottom + 1.0e-9 &&
                        dMin + courseHeight * (centreRow - 1)
                            < chartTop - 1.0e-9 &&
                        uc + size / 2.0 > -halfAtCentre + 1.0e-9 &&
                        uc - size / 2.0 < halfAtCentre - 1.0e-9;
                    if (!overlaps)
                        continue;

                    var outline = new List<double[]>();
                    outline.AddRange(Run(
                        mapped[0].Curve, mapped[0].U, mapped[1].U));
                    outline.Add(PointAt(mapped[2].Curve, mapped[2].U));
                    List<double[]> top = Run(
                        mapped[4].Curve, mapped[4].U, mapped[3].U);
                    top.Reverse();
                    outline.AddRange(top);
                    outline.Add(PointAt(mapped[5].Curve, mapped[5].U));
                    List<double[]> cleaned = Dedupe(outline);
                    if (cleaned.Count < 3)
                        continue;

                    double dcClamped = Math.Min(
                        Math.Max(dMin + courseHeight * centreRow, dMin),
                        dMax);
                    int course = Math.Min(
                        bands - 1,
                        Math.Max(0, (int)Math.Floor(
                            (dcClamped - dMin) / courseHeight
                            + 1.0e-9)));
                    var cell = new SkinCell(
                        course, cleaned, clipped,
                        mapped[5].U, mapped[2].U);
                    keyed.Add((course, chartAt, mapped[5].U, cell));
                }
            }
        }
        // The plan guarantee, enforced on the sorted list exactly as the
        // courses engine enforces it, and every diagnostics number below
        // taken off the survivors.
        List<SkinCell> cells = KeepValidPlans(
            keyed
                .OrderBy(item => item.Course)
                .ThenBy(item => item.Chart)
                .ThenBy(item => item.U0)
                .Select(item => item.Cell)
                .ToList(),
            out int degenerateDropped,
            out int overlapDropped);
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
                    "hexagonal", skippedRows.Count, transitions,
                    FieldKindOf(net))),
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
            0,
            0,
            1);
    }
}
