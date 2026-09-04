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

    /// <summary>The AREA-WEIGHTED UNIT NORMAL at every vertex (spec
    /// 2026-09-03, skin-offset-surface, rule 1), ORIENTED so that a
    /// positive Thickness is outward and up whatever the net's winding
    /// (spec 2026-09-04, skin-offset-extrude-slider, rule 4). Computed once
    /// here, beside the Levels field, because it is the same shape of data
    /// and has the same lifetime: one double[3] per vertex, valid for as
    /// long as the net is. Triangulate is called again rather than the
    /// Faces property read, for the reason Levels gives: an instance
    /// property initialiser cannot see `this`, and Triangulate is
    /// idempotent.</summary>
    public IReadOnlyList<double[]> Normals { get; } =
        SkinPatterns.OrientedVertexNormals(
            Vertices,
            SkinPatterns.Triangulate(Vertices, Faces));

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
///
/// SECTIONS is the one thing rule 5.2.3 lofts: the cell's own CROSS
/// SECTIONS, in one direction, never its edges in cyclic order. A courses
/// or force-aligned cell carries two, the lower bed run and the upper bed
/// run, both running the same way (routes (a) and (c)); a six-cornered
/// hexagon three, the bottom run, the two-point section from the left side
/// vertex to the right, and the top run (route (b)); a cap none, and a cell
/// whose corner count its own pattern's route does not fit none either, so
/// the component fans both (routes (d) and (e)).
///
/// CHAINS is a different thing and is read by a different check: the outline
/// broken into its own named edges, in the order the engine laid them round
/// the ring. Only the force-aligned pattern fills it, with four, the lower
/// bed run, the upward streamline segment, the upper bed run REVERSED as the
/// ring walks it, and the downward streamline segment (rule 3.3.6). Check
/// 12.3(b) measures each chain against the family it is meant to lie on,
/// which cannot be done on a single flattened ring. The two fields are held
/// apart because they disagree: the ring's four chains in cyclic order are
/// the cell's four EDGES, and lofting those is the opposite of route (a),
/// which is what happens when one field is asked to be both.
/// </summary>
internal sealed record SkinCell(
    int Course,
    IReadOnlyList<double[]> Outline,
    bool Clipped,
    double U0,
    double U1,
    bool Cap = false,
    int SetoutCorners = 0,
    IReadOnlyList<IReadOnlyList<double[]>>? Sections = null,
    IReadOnlyList<IReadOnlyList<double[]>>? Chains = null);

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
/// FLOWLINES and BEDCURVES are the force-aligned pattern's own ACCEPTED
/// streamlines and its TRACED beds, kept on the record because check 12.3(b)
/// cannot be taken without them: a check that re-derived the streamlines in
/// the harness would be comparing the engine with a second engine. They are
/// empty on the other two patterns and on Empty.
///
/// The three piece lengths are DERIVED from the surviving cells and need no
/// member, excluding Cap cells by rule 2.3.2a. skin.surface_failed is
/// deliberately NOT here: the Brep build happens on the solve thread beside
/// ClosedOutlineCurve and never in this file, which is rule 5.2.4.
///
/// WELDCOLLAPSEDDROPPED is studio request R-006: at cell emission, every
/// outline is welded (consecutive corners, and the closing seam, closer
/// than 1e-6 m are collapsed to one) before it ever reaches KeepValidPlans
/// or a port, matching the third plan-validity habit the other two drop
/// counts already keep. A cell whose outline collapses below three
/// distinct corners after welding cannot be a plan at all and is dropped
/// here, counted, and never silently absorbed the way it was before this
/// task: the studio measured 28 of 1074 exported COURSE cells carrying a
/// consecutive corner pair some 5e-7 m apart, a gap the plugin's own
/// filter never saw because Dedupe's consecutive pass welded only within
/// 1e-9 m, well under the float noise the studio's own import actually
/// rejects; the force-aligned ("armadillo-style") export was already
/// clean, 0 of 1501, because its own outline happens not to accumulate
/// that noise, not because it was ever welded any wider.
///
/// THREESIDEDCELLS is the force-aligned pattern's own closer, rule
/// 3.3.5's three-cornered cell, where a streamline ENDS inside the band
/// and the cell closes against the upper bed's arc. It has its own field
/// because it was reported in SEVENSIDEDCELLS until 2026-09-03, and the
/// component printed that field as "seven-sided" while the engine's own
/// diagnostics string called the same number "three-sided", so the two
/// readings of one pattern disagreed by name. SEVENSIDEDCELLS now means
/// only what it says: the honeycomb's genuine seven-cornered rim cell of
/// rule 4.3. It is appended LAST, after WELDCOLLAPSEDDROPPED and with a
/// default of 0, so every existing construction site keeps its
/// positions.
///
/// BANDESCAPEDREFUSED is the fourth way a cell fails to reach the author,
/// beside the three drops above: the force-aligned pattern REFUSES a cell
/// at emission when one of its head joints stands outside the band's own
/// two beds (plan 2026-09-03 task 2, step 2), because such a cell closes
/// with an implicit chord across whatever lies between. It is a field and
/// not a diagnostics-only counter because the component sizes its drop
/// warning by the fraction of the pattern that did not survive, and a
/// refusal the component cannot read makes that fraction understate the
/// hole: on Param's own crown arch 65 of the 142 cells the pattern
/// proposed are refused here, against 6 dropped by the plan filter, so a
/// component reading only the drops would call a half-empty pattern an 8
/// per cent hole. Appended LAST, after THREESIDEDCELLS and with a default
/// of 0, on the same rule.</summary>
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
    IReadOnlyList<int> ClosedRows,
    int MergedPieces,
    int DegenerateCentroidsSkipped,
    int ExtraLevels,
    int TracePasses,
    int MergedShortKept,
    int MergedStillShort,
    IReadOnlyList<double[][]> FlowLines,
    IReadOnlyList<double[][]> BedCurves,
    int WeldCollapsedDropped = 0,
    int ThreeSidedCells = 0,
    int BandEscapedRefused = 0);

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

    /// <summary>
    /// What FRACTION of the net's own plan area the surviving cells cover,
    /// which is the whole-branch review's finding 12: the honeycomb's
    /// neighbouring rows overlap in plan often enough that the
    /// plan-validity filter removes a third of the candidates on an
    /// ordinary dome, and what it removes is a HOLE in the skin. The
    /// pattern's own doc comment argues for coverage, saying a cell
    /// crossing the boundary is clipped and KEPT because a coverage hole
    /// is worse than an odd-shaped rim piece, while the filter downstream
    /// was taking that coverage away and nothing said so. An author
    /// counting cells cannot see it; a percentage he can.
    ///
    /// The cells are disjoint after KeepValidPlans, so the sum of their
    /// plan areas against the net's own is real uncovered area and not an
    /// estimate. Both are absolute values: a ring's winding is not the
    /// question here.
    /// </summary>
    private static double PlanCoverage(
        SkinNet net,
        IReadOnlyList<SkinCell> cells)
    {
        double whole = 0.0;
        foreach (int[] face in net.Faces)
        {
            double[] a = net.Vertices[face[0]];
            double[] b = net.Vertices[face[1]];
            double[] c = net.Vertices[face[2]];
            whole += Math.Abs(
                ((b[0] - a[0]) * (c[1] - a[1])) -
                ((c[0] - a[0]) * (b[1] - a[1]))) / 2.0;
        }
        if (!(whole > 1.0e-12))
            return double.NaN;
        double covered = 0.0;
        foreach (SkinCell cell in cells)
        {
            IReadOnlyList<double[]> ring = cell.Outline;
            if (ring.Count < 3)
                continue;
            double cx = 0.0;
            double cy = 0.0;
            foreach (double[] corner in ring)
            {
                cx += corner[0];
                cy += corner[1];
            }
            cx /= ring.Count;
            cy /= ring.Count;
            double twice = 0.0;
            for (int at = 0; at < ring.Count; at++)
            {
                double[] one = ring[at];
                double[] next = ring[(at + 1) % ring.Count];
                twice +=
                    ((one[0] - cx) * (next[1] - cy)) -
                    ((next[0] - cx) * (one[1] - cy));
            }
            covered += Math.Abs(twice) / 2.0;
        }
        return covered / whole;
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
    /// the loop below it (the point nearest in plan to the lower seam,
    /// by EXACT projection onto this loop's own segments, rule 4.2.6 and
    /// NearestArcInPlan below); the lowest loop's seam is the trace
    /// vertex on the +X bearing from its plan centroid, deterministic
    /// and stated, and exact already since it is not measured against
    /// anything below it.
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
                    curve.Seam = NearestArcInPlan(curve, lowerSeam);
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
    /// the order the component hands out and the overlap filter reads,
    /// not the studio's own build sequence:
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
        out int overlapDropped,
        out int degenerateCentroidsSkipped)
    {
        degenerateDropped = 0;
        overlapDropped = 0;
        degenerateCentroidsSkipped = 0;
        var kept = new List<SkinCell>(cells.Count);
        var boxes = new List<(double MinX, double MinY,
            double MaxX, double MaxY)>(cells.Count);
        var insides = new List<double[]?>(cells.Count);
        foreach (SkinCell cell in cells)
        {
            if (cell.Outline.Count < 3 ||
                PlanSelfCrosses(cell.Outline) ||
                PlanVertexOnEdge(cell.Outline))
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
            double[]? inside = PlanInteriorPoint(
                cell.Outline, out int skippedHere);
            degenerateCentroidsSkipped += skippedHere;
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

    /// <summary>
    /// Studio request R-006, fixed AT EMISSION: two CONSECUTIVE outline
    /// corners (the ring's own closing seam, last back to first, counted
    /// as consecutive too) closer than 1e-6 m are float noise, not two
    /// distinct corners, and are collapsed to the first of the pair. The
    /// studio measured 28 of 1074 exported COURSE cells carrying exactly
    /// this kind of pair, about 5e-7 m apart, which reads as a
    /// zero-length edge and makes its simplicity check call the cell
    /// self-crossing; the real contrast is Param's own courses export
    /// against his armadillo-style (force-aligned) export, which came
    /// back clean, 0 of 1501, because that pattern's own outline
    /// arithmetic happens not to accumulate noise this coarse, not
    /// because it was ever welded any wider than 1e-9 m either. Both
    /// patterns are welded at the same 1e-6 m here, so neither is a
    /// second, looser rule.
    ///
    /// A three-dimensional distance and ONLY EVER a corner against its
    /// immediate neighbour, which is what distinguishes it from Dedupe's
    /// own further pass below (rule 3.5.4): a genuine float-noise
    /// duplicate is adjacent by construction, the tracer having written
    /// the same point twice, and not two unrelated corners that merely
    /// coincide in plan.
    /// </summary>
    internal static List<double[]> WeldConsecutiveCorners(
        List<double[]> outline)
    {
        var welded = new List<double[]>(outline.Count);
        foreach (double[] point in outline)
        {
            if (welded.Count == 0 ||
                Distance(welded[^1], point) > 1.0e-6)
            {
                welded.Add(point);
            }
        }
        while (welded.Count > 1 &&
               Distance(welded[0], welded[^1]) <= 1.0e-6)
        {
            welded.RemoveAt(welded.Count - 1);
        }
        return welded;
    }

    /// <summary>
    /// Weld consecutive corners (<see cref="WeldConsecutiveCorners"/>),
    /// then drop every duplicate the STUDIO would reject over the WHOLE
    /// ring, so an outline is a clean open ring the component closes
    /// itself.
    ///
    /// Rule 3.5.4. The studio's import rule is stricter than the plugin's
    /// filter and the gap becomes likelier under this wave's patterns. The
    /// raised test is a PLAN test in the STUDIO'S PER-AXIS FORM, not a
    /// three-dimensional distance: raising a three-dimensional test to 1e-6
    /// does NOT close the gap, because two outline points 1e-7 apart in plan
    /// and 1e-3 apart in z pass a three-dimensional 1e-6 test comfortably
    /// and still fail the studio, which is the exact case a cell spanning a
    /// steep band produces. And it runs over the WHOLE RING and not only
    /// over consecutive points, again as the studio's does; the weld above
    /// is what covers consecutive points, in three dimensions, before this
    /// pass ever runs.
    /// </summary>
    private static List<double[]> Dedupe(List<double[]> outline)
    {
        List<double[]> cleaned = WeldConsecutiveCorners(outline);
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
    {
        RequireSizes(size, courseHeight);
        // Rule 6.4's bounds, applied in the engine so the harness can
        // measure them without a canvas. The component clamps and WARNS
        // (rule 9.5); the engine simply takes the clamped value, the same
        // split the CH floor already keeps.
        double clampedMinPiece =
            double.IsFinite(minPiece)
                ? Math.Min(Math.Max(minPiece, 0.0), 0.5)
                : 1.0 / 3.0;
        double minimumPiece = clampedMinPiece * size;
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

        var levelIndex = new Dictionary<double, int>();
        for (int at = 0; at < resolved.Levels.Count; at++)
            levelIndex[resolved.Levels[at]] = at;

        var keyed =
            new List<(int Course, int Order, double U0, SkinCell Cell)>();
        var transitions = new List<(double Low, double High)>();
        int mergedPieces = 0;
        int mergedShortKept = 0;
        int mergedStillShort = 0;
        int weldCollapsed = 0;
        var capGirths = new List<double>();
        var capWedges = new List<int>();
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
            // A band's OWN Low, not merely its Course, decides whether it is
            // the crown band the cap pass planned against: bisection (rule
            // 8.2.3) can split a refused top course into several sub-bands
            // that all share Course = bands - 1, and only the one sub-band
            // whose Low equals the cap pass's own top.Low is the band that
            // pass actually tested. Any other shares nothing but the number.
            bool isCapBand =
                top is not null &&
                Math.Abs(band.Low - top.Low) <= 1.0e-12 &&
                Math.Abs(band.High - top.High) <= 1.0e-12;
            for (int component = 0; component < mids.Count; component++)
            {
                SkinLevelCurve mid = mids[component];
                int lowerAt = MatchBelow(mid, lowers);
                int upperAt = MatchBelow(mid, uppers);
                if (lowerAt < 0 || upperAt < 0 || !(mid.Length > 1.0e-9))
                    continue;
                SkinLevelCurve lowerCurve = lowers[lowerAt];
                SkinLevelCurve upperCurve = uppers[upperAt];

                // THE CAP'S OUTLINE IS THE LEVEL CURVE, whole, from its seam
                // round to its seam (rule 2.3.1), or a ring of wedges about a
                // smaller centre disc where rule 2.6 split it. It carries
                // every trace vertex of the curves it is built from, so it
                // typically has tens of corners, and it follows the surface
                // exactly rather than chording across it, the same property
                // Run gives every other cell edge. It is NOT exempted from
                // KeepValidPlans and must not be: if it ever fails, that is
                // a defect and the filter is where it should show.
                //
                // The qualification test itself already ran, ONCE, in the
                // cap pass above: capPlans carries an entry for every
                // component that pass found qualifying (rule 2.2.1),
                // whether it ended up whole, oversized, or split, and
                // capRefusals already carries the reason for every one that
                // did not. A component with no plan is not a cap at all and
                // falls through to ordinary band tiling below.
                // BY THE INDEX THE PLAN WAS RECORDED AGAINST, which is the
                // whole-branch review's finding 15. The cap pass walks
                // topCurves, which is resolved.Traced at top.Low, the
                // LOWERS list of this band, and records each plan against
                // a position in it. This lookup read `component`, a
                // position in MIDS, while the curve the plan is applied to
                // is lowers[lowerAt]. Three ways of naming a component and
                // two of them assumed to agree. Where a level's components
                // come back in a different order at the mid than at the
                // low, which nothing forbids, a cap takes another cap's
                // wedge count, inner level and ring mid: a dome that
                // needed no split is cut into a rosette at heights
                // borrowed from its neighbour, and one that needed a split
                // is emitted whole and oversized with CapsOversized
                // reading zero.
                SkinCapPlan? plan = isCapBand
                    ? capPlans.FirstOrDefault(
                        item => item.ComponentAt == lowerAt)
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
                        else
                        {
                            // R-006: welded below three distinct corners,
                            // so there is no plan left to keep.
                            weldCollapsed++;
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
                        else
                        {
                            // R-006: welded below three distinct corners.
                            weldCollapsed++;
                        }
                        continue;
                    }
                    // BandCell's u0/u1 are always MID-CURVE arc length, the
                    // same convention ordinary tiling uses, and it is the
                    // ring's own mid curve that is passed as "mid" here: the
                    // wedge boundaries are cut on ringMidCurve, not on the
                    // outer curve's own (generally longer) girth, and
                    // BandCell's internal ratio then carries each boundary
                    // out to outer and in to innerCurve proportionally
                    // (rule 1.8.1). Using plan.Girth (the outer curve's own
                    // length, recorded for the threshold test) here instead
                    // double-applies that ratio and walks the outer curve
                    // past its own seam, so the last wedge overlaps the
                    // first: reproduced on the CH 1.2 hemisphere, W = 4,
                    // dropped as an overlap by the plan-validity filter.
                    double girth = ringMidCurve.Length;
                    for (int w = 0; w < plan.Wedges; w++)
                    {
                        double u0 = -girth / 2.0 + w * girth / plan.Wedges;
                        double u1 = u0 + girth / plan.Wedges;
                        SkinCell wedge = BandCell(
                            band.Course, outer, ringMidCurve, innerCurve,
                            u0, u1, false);
                        if (wedge.Outline.Count < 3)
                        {
                            // R-006: welded below three distinct corners.
                            weldCollapsed++;
                            continue;
                        }
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
                    else
                    {
                        // R-006: welded below three distinct corners.
                        weldCollapsed++;
                    }
                    capGirths.Add(innerCurve.Length);
                    capWedges.Add(plan.Wedges);
                    continue;
                }

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
                    {
                        // R-006: welded below three distinct corners.
                        weldCollapsed++;
                        continue;
                    }
                    keyed.Add((band.Course, component, u0, cell));
                }
            }
        }
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
            out int overlapDropped,
            out int degenerateCentroidsSkipped);
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
                  : string.Empty) +
              (capsOversized > 0
                  ? $"; {capsOversized} emitted WHOLE and OVERSIZED above " +
                    "the maximum piece size, so a smaller CH or a larger " +
                    "Min Piece is wanted"
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
                mergedPieces,
                degenerateDropped, overlapDropped,
                TransitionLine(
                    "courses", transitionBands, transitions,
                    FieldKindOf(net)),
                capLine,
                weldCollapsed,
                PlanCoverage(net, cells)),
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
            capWedges,
            capsOversized,
            0,
            0,
            Array.Empty<int>(),
            Array.Empty<int>(),
            mergedPieces,
            degenerateCentroidsSkipped,
            resolved.ExtraLevels,
            resolved.Passes,
            mergedShortKept,
            mergedStillShort,
            Array.Empty<double[][]>(),
            Array.Empty<double[][]>(),
            weldCollapsed);
    }

    // ---- pattern 2: force aligned (spec section 3) ----------------------

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

        // THE BEDS, ONCE (rule 3.3.1a). A bed is a LIST of traced components
        // and not one curve, and the cell loop below reads bed r as its
        // lower and bed r + 1 as its upper. Resolving every bed here, from
        // the one level expression, is what guarantees a crossing's
        // component index means the same thing in the crossings table, in
        // the insertion walk and in the run that finally uses the curve.
        var bedLevels = new List<double>();
        var bedsAt = new List<IReadOnlyList<SkinLevelCurve>>();
        for (int r = 0; r <= bands; r++)
        {
            double level = r == 0
                ? intervals[0].Low
                : r == bands
                    ? intervals[bands - 1].High
                    : intervals[r].Low;
            bedLevels.Add(level);
            bedsAt.Add(resolved.Traced[levelIndex[level]]);
        }

        // SEEDING, on BED 0 and never on the rim (rule 3.3.1). There is no
        // curve at field value 0 to place a seed on: the tracer's crossing
        // rule is half-open, so at level 0 every rim vertex is at-or-above,
        // no edge crosses anywhere and Trace returns nothing. Seeds go on
        // the traced curve at the epsilon, at uniform pitch
        // P0 = L0 / max(1, round(L0 / (S / 2))), that is at HALF the target
        // piece length, because rule 3.3.4's course takes every OTHER line.
        var lines = new List<(double[][] Points, int Parity)>();
        IReadOnlyList<SkinLevelCurve> bed0 = bedsAt[0];
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

        // CROSSINGS. Each line's crossing with each bed is the candidate
        // head joint of that bed, recorded as a signed arc on the bed's own
        // component (rule 3.3.2). Everything from here is PER TRACED
        // COMPONENT (rule 3.3.1a): a bed is a LIST of components and not one
        // curve, so L_k, P_k, the seam-outward walk, the insertion and
        // termination tests and the parity are all taken per component,
        // each with its own length and its own seam.
        //
        // ONE LIST PER COMPONENT of each bed, not one per bed. An arc is
        // measured from the seam of the component it landed on, and two
        // components of one level have different lengths and different
        // seams, so pooling them lets a sorted walk pair an arc measured on
        // one springing with an arc measured on the other and close a
        // "piece" across the whole vault. Param's own crown arch carries two
        // components on 26 of its 28 beds.
        //
        // A LINE MEETS A BED ONCE PER COMPONENT. A head joint on an arch
        // runs springing to springing over the crown, so it crosses every
        // bed TWICE, once on each side. Recording only the first crossing
        // and stopping put the whole barrel's arcs on whichever component
        // the walk happened to reach first and left the other bare; the
        // pooled list hid it because the two components of a symmetric
        // fixture are congruent and their arcs coincide.
        var crossings = new List<List<List<SkinCrossing>>>();
        for (int r = 0; r <= bands; r++)
        {
            var perComponent = new List<List<SkinCrossing>>();
            for (int c = 0; c < bedsAt[r].Count; c++)
                perComponent.Add(new List<SkinCrossing>());
            crossings.Add(perComponent);
        }
        for (int at = 0; at < lines.Count; at++)
        {
            RecordCrossings(
                net, bedLevels, bedsAt, bands, crossings,
                lines[at].Points, at);
        }

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
        //
        // A LINE RETIRES ABOVE ITS OWN BED AND NOWHERE ELSE (rule 3.3.3,
        // "TERMINATE the later of the two AT BED k", and rule 3.3.5, "no
        // cell elsewhere along the bed changes its side count"). This was
        // a global HashSet until 2026-09-03, and the walk that fills it
        // runs bottom-up while the CELL loop below runs afterwards against
        // the finished set: a line terminated at bed 12 was therefore
        // absent from beds 0 to 11 as well, so it vanished retroactively
        // from every course it had been a head joint on and its two
        // neighbours' spans merged into one long piece. That is where a
        // 7.52 m piece against a Size of 0.5 m came from on Param's own
        // net. The bed index is recorded instead, and a line is excluded
        // only where the bed being read is ABOVE the bed it terminated at.
        // A line terminated while bed r is being walked is still present on
        // bed r itself, which is the behaviour the insertion walk already
        // had within one component and now has across all of them.
        int inserted = 0;
        int terminated = 0;
        var retiredAt = new Dictionary<int, int>();
        bool RetiredBelow(int line, int bed) =>
            retiredAt.TryGetValue(line, out int at) && bed > at;
        for (int r = 0; r <= bands; r++)
        {
            IReadOnlyList<SkinLevelCurve> bed = bedsAt[r];
            // PER COMPONENT (rule 3.3.1a): L_k, P_k and the seam-outward
            // walk all belong to one component, so a springing with three
            // crossings does not have its gaps measured against the other
            // springing's arcs.
            for (int c = 0; c < bed.Count; c++)
            {
                double target = bed[c].Length /
                    Math.Max(1.0, Math.Round(bed[c].Length / (size / 2.0)));
                List<SkinCrossing> here = crossings[r][c]
                    .Where(item => !RetiredBelow(item.Line, r))
                    .OrderBy(item => item.U)
                    .ToList();
                for (int at = 1; at < here.Count; at++)
                {
                    double gap = here[at].U - here[at - 1].U;
                    if (gap < 0.5 * target)
                    {
                        // The FIRST bed a line is terminated at is the bed
                        // it retires above, and the count is of LINES
                        // retired and not of terminations seen: a line
                        // crosses two components of one bed on an arch, so
                        // the same line can meet the half-pitch test twice
                        // at the same bed, and counting both would report
                        // more terminations than there are lines.
                        if (!retiredAt.ContainsKey(here[at].Line))
                        {
                            retiredAt[here[at].Line] = r;
                            terminated++;
                        }
                    }
                    else if (gap > 1.5 * target)
                    {
                        double middle = (here[at].U + here[at - 1].U) / 2.0;
                        double[] from = PointAt(bed[c], middle);
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
                        // An inserted line is a head joint on every bed it
                        // reaches and not only on the one it was inserted
                        // on: a line whose crossings above bed k were never
                        // recorded would stop being a joint the moment it
                        // left bed k, which is the property rule 3.3.4
                        // anchors on the LINE for. Its own bed's crossing is
                        // the exact midpoint, taken from the gap rather than
                        // re-derived, and it belongs to the component the
                        // gap was measured on.
                        RecordCrossings(
                            net, bedLevels, bedsAt, bands,
                            crossings, line, lines.Count - 1, r, c);
                        crossings[r][c].Add(new SkinCrossing(
                            middle, lines.Count - 1, c, 0, from, true));
                        inserted++;
                    }
                }
            }
        }

        var cells = new List<SkinCell>();
        var flowLines = new List<double[][]>();
        var bedCurves = new List<double[][]>();
        int fiveSided = 0;
        // Rule 3.3.5's closer has THREE corners, and this counter is named
        // for what it counts. It was called sevenSided and reported in
        // SevenSidedCells until 2026-09-03, so the component printed
        // "seven-sided" over a number the engine's own diagnostics line
        // called "three-sided". The force-aligned pattern builds no
        // seven-cornered cell at all; that is the honeycomb's rim cell.
        int threeSided = 0;
        int mergedPieces = 0;
        int mergedShortKept = 0;
        int mergedStillShort = 0;
        int weldCollapsed = 0;
        // A cell REFUSED because one of its head joints stood outside the
        // band it belongs to (rule 3.3.5's closer, escaping). Counted and
        // reported rather than emitted for KeepValidPlans to delete: a cell
        // that closes with a chord across a topology change is not a cell
        // the pattern should have proposed, and a drop counted as
        // "self-crossing in plan" tells the author the wrong thing about
        // where it came from.
        int bandEscaped = 0;
        // THE FIELD UNDER EVERY POINT OF EVERY ACCEPTED LINE, taken once
        // and only after the insertion walk has finished adding lines. A
        // chain clipped to its own band needs the level at each polyline
        // point, and LevelAt locates a face in plan, so paying for it
        // inside the cell loop would pay for the same walk again on every
        // band the line crosses.
        var lineLevels = new List<double[]>();
        foreach ((double[][] points, int _) in lines)
        {
            flowLines.Add(points);
            var value = new double[points.Length];
            for (int at = 0; at < points.Length; at++)
                value[at] = LevelAt(net, points[at]);
            lineLevels.Add(value);
        }
        for (int r = 0; r < bands; r++)
        {
            // Bed r is this band's lower and bed r + 1 its upper, by the same
            // level expression the crossings table was built from, so a
            // component index here indexes the same curve it did there.
            IReadOnlyList<SkinLevelCurve> lowerBed = bedsAt[r];
            IReadOnlyList<SkinLevelCurve> upperBed = bedsAt[r + 1];
            if (lowerBed.Count == 0 || upperBed.Count == 0)
                continue;
            foreach (SkinLevelCurve component in lowerBed)
                bedCurves.Add(BedPolyline(component));
            foreach (SkinLevelCurve component in upperBed)
                bedCurves.Add(BedPolyline(component));

            // ONE COURSE PER COMPONENT of the lower bed (rule 3.3.1a). A
            // vault with two springings, an oculus or a ridge carries more
            // than one contour at a level; tiling only the first left the
            // rest of the shell bare, and a span could take one end from an
            // arc measured on one component and the other from an arc
            // measured on another.
            for (int c = 0; c < lowerBed.Count; c++)
            {
                // THE PAIRING IS BY LINE AND NOT BY INDEX (rule 3.3.4). A
                // course takes the crossings of the lines whose parity is r
                // mod 2, and a piece runs between two ADJACENT such
                // crossings, so its two head joints are two whole streamlines
                // and not two positions in a sorted list. Anchoring on the
                // index instead would let a head joint stop running along one
                // streamline between its own two beds, which is the single
                // property check 12.3(b) exists for.
                var onLower = crossings[r][c]
                    .Where(item => lines[item.Line].Parity == (r % 2))
                    .Where(item => !RetiredBelow(item.Line, r))
                    .OrderBy(item => item.U)
                    .ToList();
                if (onLower.Count < 2)
                    continue;
                // Every crossing of the UPPER bed, by line and whatever
                // component it landed on. A joint leaving THIS component of
                // the lower bed meets the upper bed at the crossing NEAREST
                // ALONG ITS OWN POLYLINE, which is the only reading that
                // survives a joint running over the crown and down the far
                // side: the far side's crossings belong to the far side's
                // cells, not to this one.
                var above = new Dictionary<int, List<SkinCrossing>>();
                for (int uc = 0; uc < upperBed.Count; uc++)
                {
                    foreach (SkinCrossing item in crossings[r + 1][uc])
                    {
                        if (!above.TryGetValue(
                                item.Line, out List<SkinCrossing>? found))
                        {
                            found = new List<SkinCrossing>();
                            above[item.Line] = found;
                        }
                        found.Add(item);
                    }
                }
                SkinCrossing? Above(SkinCrossing from)
                {
                    if (!above.TryGetValue(
                            from.Line, out List<SkinCrossing>? found))
                    {
                        return null;
                    }
                    SkinCrossing? best = null;
                    int bestGap = int.MaxValue;
                    foreach (SkinCrossing item in found)
                    {
                        int gap = Math.Abs(item.At - from.At);
                        if (gap < bestGap)
                        {
                            bestGap = gap;
                            best = item;
                        }
                    }
                    return best;
                }

                // The spans, seam outward, then section 6's own merge, which
                // rule 3.3.6 inherits whole rather than reimplementing.
                var spans = new List<(double U0, double U1, bool Clipped)>();
                for (int at = 1; at < onLower.Count; at++)
                    spans.Add((onLower[at - 1].U, onLower[at].U, false));
                List<(double U0, double U1, bool Clipped)> keptSpans =
                    MergeShortPieces(
                        spans, clampedMinPiece * size,
                        ref mergedPieces, ref mergedShortKept,
                        ref mergedStillShort);

                foreach ((double u0, double u1, bool clipped) in keptSpans)
                {
                    // The two head joints this piece actually runs between,
                    // found by their own arc rather than by their place in
                    // the list, so a merged span picks up the outer two lines
                    // and not the two it started with.
                    int leftAt = NearestCrossingLine(onLower, u0);
                    int rightAt = NearestCrossingLine(onLower, u1);
                    if (leftAt < 0 || rightAt < 0)
                        continue;
                    SkinCrossing leftLower = onLower[leftAt];
                    SkinCrossing rightLower = onLower[rightAt];
                    int leftLine = leftLower.Line;
                    int rightLine = rightLower.Line;

                    // FOUR CHAINS, in the order rule 5.2.1 records them: the
                    // lower bed's Run between the two joints, the right-hand
                    // streamline segment upward, the upper bed's Run
                    // reversed, and the left-hand streamline segment
                    // downward. Run takes a SIGNED offset from the seam and
                    // adds the seam itself, and a crossing is recorded
                    // seam-relative already, so the arcs go in as they stand:
                    // adding the seam here would add it twice, which on an
                    // open strip (seam L / 2) clamps both ends of every run
                    // to the far end of the bed.
                    double[][] lowerRun = Run(lowerBed[c], u0, u1).ToArray();
                    SkinCrossing? rightUpper = Above(rightLower);
                    SkinCrossing? leftUpper = Above(leftLower);
                    // Two joints that land on DIFFERENT components of the
                    // upper bed have no run of that bed between them at all
                    // (rule 3.3.1a). The cell closes against the upper bed
                    // the way a cell whose joint simply stopped does, which
                    // is rule 3.3.5's three-cornered closer, rather than
                    // splicing two unrelated arcs into one edge.
                    int upperComponent =
                        rightUpper is not null && leftUpper is not null &&
                        rightUpper.Component == leftUpper.Component
                            ? rightUpper.Component
                            : -1;
                    // The upper run is walked the increasing-u way and
                    // REVERSED, because the ring closes right to left along
                    // the top; Run itself refuses to walk backwards.
                    double[][] upperRun = upperComponent >= 0
                        ? Run(upperBed[upperComponent],
                              Math.Min(leftUpper!.U, rightUpper!.U),
                              Math.Max(leftUpper.U, rightUpper.U))
                            .AsEnumerable().Reverse().ToArray()
                        : Array.Empty<double[]>();
                    // A CHAIN STOPS AT THE BAND IT BELONGS TO. A cell's
                    // two head joints are the stretches of two streamlines
                    // between its own two beds; a chain standing outside
                    // them closes the cell with an implicit chord across
                    // whatever lies between, which on Param's own net is
                    // the merge of the two level-curve strips. The band's
                    // two bed levels go in, the closer's walk stops at the
                    // upper one, and a chain that leaves the band anyway
                    // refuses the cell outright rather than handing the
                    // plan filter a self-crossing or overlapping outline to
                    // delete three stages later under another name.
                    double[][] rightSegment = ChainBetween(
                        lines[rightLine].Points, lineLevels[rightLine],
                        bedLevels[r], bedLevels[r + 1],
                        rightLower, rightUpper, out bool rightEscaped);
                    double[][] leftSegment = ChainBetween(
                        lines[leftLine].Points, lineLevels[leftLine],
                        bedLevels[r], bedLevels[r + 1],
                        leftLower, leftUpper, out bool leftEscaped);
                    if (rightEscaped || leftEscaped)
                    {
                        bandEscaped++;
                        continue;
                    }
                    // The left-hand joint is walked DOWNWARD (rule 3.3.6's
                    // fourth chain), so the ring closes on the lower bed
                    // where it started instead of doubling back up the same
                    // line. Enumerable.Reverse by name: an array binds
                    // MemoryExtensions.Reverse(Span) first, which reverses in
                    // place and returns void.
                    leftSegment = Enumerable.Reverse(leftSegment).ToArray();

                    var outline = new List<double[]>();
                    outline.AddRange(lowerRun);
                    outline.AddRange(rightSegment);
                    outline.AddRange(upperRun);
                    outline.AddRange(leftSegment);
                    List<double[]> ring = Dedupe(outline);
                    if (ring.Count < 3)
                    {
                        // R-006: welded below three distinct corners.
                        weldCollapsed++;
                        continue;
                    }

                    // RULE 3.3.5. A cell gains or loses a side only where a
                    // line BEGINS OR ENDS within its own band: a line that
                    // does not reach the upper bed closes the cell against
                    // the upper bed's own arc and the cell comes back with
                    // three or five setout corners rather than four. They are
                    // the pattern's honest response to a flow that converges,
                    // and refusing them would put a hole where a mason puts a
                    // closer.
                    int setout = 4;
                    if (upperComponent < 0)
                        setout = 3;
                    else if (InsertedWithin(
                                 lines, crossings[r + 1][upperComponent],
                                 crossings[r], leftLine, rightLine))
                    {
                        setout = 5;
                    }
                    if (setout == 5)
                        fiveSided++;
                    else if (setout == 3)
                        threeSided++;

                    // RULE 5.2.3(c). A four-cornered force-aligned cell is a
                    // courses cell by rule 3.2.3 and takes route (a): a loft
                    // of TWO sections, the lower bed run and the upper bed
                    // run, both in the SAME direction. The ring holds the
                    // upper run reversed, because the outline closes right to
                    // left along the top, so the loft pair un-reverses it.
                    // Handing the component the ring's four chains instead
                    // would loft the cell's four EDGES in cyclic order,
                    // bottom to right to top to left, which is the opposite
                    // of what a loft is for; the chains go on their own field
                    // for check 12.3(b) and the two never share one.
                    //
                    // A three- or five-cornered cell (rule 3.3.5) carries no
                    // sections and takes the deterministic fan of route (e):
                    // route (a) is written for a cell with exactly two bed
                    // edges, and a cell that lost or gained a side has an odd
                    // corner with nothing on the opposite run to loft
                    // against.
                    IReadOnlyList<IReadOnlyList<double[]>>? loftSections =
                        setout == 4 && lowerRun.Length >= 2 &&
                        upperRun.Length >= 2
                            ? new IReadOnlyList<double[]>[]
                              {
                                  lowerRun,
                                  Enumerable.Reverse(upperRun).ToArray()
                              }
                            : null;
                    cells.Add(new SkinCell(
                        r, ring, clipped, u0, u1, false, setout, loftSections,
                        new[]
                        {
                            lowerRun, rightSegment, upperRun, leftSegment
                        }));
                }
            }
        }
        // Rule 3.3.6's "sorted by the same rule as section 7": course, then
        // seam outward, then the seam-ward side first on a tie.
        List<SkinCell> valid = KeepValidPlans(
            cells
                .OrderBy(cell => cell.Course)
                .ThenBy(cell => Math.Abs((cell.U0 + cell.U1) / 2.0))
                .ThenBy(cell => (cell.U0 + cell.U1) / 2.0)
                .ToList(),
            out int degenerateDropped, out int overlapDropped,
            out int degenerateCentroidsSkipped);

        var oddLines = new List<string>();
        if (fiveSided + threeSided > 0)
        {
            oddLines.Add(
                $"Odd cells: {fiveSided} five-sided, {threeSided} " +
                $"three-sided ({inserted} lines inserted, {terminated} " +
                "terminated)");
        }
        if (bandEscaped > 0)
        {
            oddLines.Add(
                $"Cells refused for leaving their band: {bandEscaped} (a " +
                "head joint stood outside the band's own two beds, so the " +
                "cell would have closed with a chord across whatever lay " +
                "between; refused at emission rather than emitted for the " +
                "plan filter to delete as self-crossing)");
        }
        string? oddLine = oddLines.Count > 0
            ? string.Join("\n", oddLines)
            : null;
        return new SkinPatternResult(
            valid,
            bands,
            PatternDiagnostics(
                "force aligned", valid.Count, bands,
                valid.Where(cell => !cell.Cap)
                    .Select(cell => cell.U1 - cell.U0).ToList(),
                "alternate streamline parity per course",
                valid.Count(cell => cell.Clipped),
                mergedPieces,
                degenerateDropped, overlapDropped,
                // STEP 3 OF THE 2026-09-03 PLAN, AND A DEPARTURE FROM WHAT
                // THIS LINE USED TO SAY. The courses engine reads
                // resolved.Tileable and tiles only the bands that
                // correspond; this engine's band loop iterates EVERY band
                // and has never read it. So "Transition bands skipped: 1"
                // was FALSE on pattern 2: nothing was skipped, the band was
                // tiled straight across the merge, and the author was sent
                // looking for a hole that the engine had in fact filled
                // with bad cells.
                //
                // The RULING, recorded rather than assumed: the loop is NOT
                // gated here. Gating it alone converts the damage into a
                // visible hole at the crown, and Param's ruling of record
                // is that the merge is to be COVERED by a closer band in
                // the next wave, which makes the gate moot. What is fixed
                // is the report: this pattern says plainly that it does not
                // test correspondence, and it raises no skipped-band count,
                // so the component's warning (which reads TransitionBands)
                // stays silent instead of describing a hole that is not
                // there.
                "Transition bands: not tested (this pattern tiles every " +
                "band and never tests whether the level curves correspond " +
                "across one, so a course that spans a split or a merge is " +
                "tiled straight across it rather than refused; the courses " +
                "pattern is the one that refuses such a band)",
                oddLine,
                weldCollapsed,
                PlanCoverage(net, valid)),
            0,
            Array.Empty<(double Low, double High)>(),
            degenerateDropped,
            overlapDropped,
            FieldKindOf(net),
            net.Rim.Count,
            net.RimDropped,
            net.EdgesDropped,
            UnreachableCount(net),
            valid.Count(cell => cell.Clipped),
            Array.Empty<double>(),
            Array.Empty<int>(),
            0,
            fiveSided,
            // SevenSidedCells is ZERO here and it is not an oversight: this
            // pattern's closer has three corners, and it is counted in
            // ThreeSidedCells below.
            0,
            Array.Empty<int>(),
            Array.Empty<int>(),
            mergedPieces,
            degenerateCentroidsSkipped,
            resolved.ExtraLevels,
            resolved.Passes,
            mergedShortKept,
            mergedStillShort,
            flowLines,
            bedCurves,
            weldCollapsed,
            threeSided,
            // The refusals reach the COMPONENT and not only the diagnostics
            // string. A cell refused here never enters Cells and is not a
            // plan drop, so a component that sizes its hole warning by the
            // drops alone reports a fraction of the truth: on Param's own
            // crown arch that is 6 of 77 against the 71 of 142 the pattern
            // actually failed to deliver.
            bandEscaped);
    }

    /// <summary>The accepted streamlines and the traced beds this pattern
    /// actually used, which is what check 12.3(b) measures every head joint
    /// and every bed edge against. A check that re-derived them in the
    /// harness would be comparing the engine with a second engine.</summary>
    public static double[][][] ForceAlignedLines(SkinPatternResult pattern) =>
        pattern.FlowLines.ToArray();

    public static double[][][] ForceAlignedBeds(SkinPatternResult pattern) =>
        pattern.BedCurves.ToArray();

    /// <summary>A traced bed as a polyline, with a closed loop's own closing
    /// segment present: a cell's bed run may cross the seam, and a distance
    /// measured to an unclosed ring would read the whole chord across that
    /// gap.</summary>
    private static double[][] BedPolyline(SkinLevelCurve curve)
    {
        var points = new List<double[]>(curve.Points);
        if (curve.Closed && points.Count > 1)
            points.Add(points[0]);
        return points.ToArray();
    }

    /// <summary>Rule 3.3.2. One line's crossing with each bed, recorded as a
    /// signed arc on the nearest component of that bed. Written once and
    /// called for a seeded line and for an inserted one alike: an inserted
    /// line that carried a crossing on its own bed and on no bed above it
    /// would stop being a head joint the moment it left the bed it was
    /// inserted on, which is the property rule 3.3.4 anchors on the line
    /// for.</summary>
    private static void RecordCrossings(
        SkinNet net,
        IReadOnlyList<double> bedLevels,
        IReadOnlyList<IReadOnlyList<SkinLevelCurve>> bedsAt,
        int bands,
        List<List<List<SkinCrossing>>> crossings,
        double[][] line,
        int index,
        int skipBed = -1,
        int skipComponent = -1)
    {
        // The field under each polyline point, taken ONCE: LevelAt locates a
        // face in plan and every bed would otherwise pay for the same walk.
        var value = new double[line.Length];
        for (int at = 0; at < line.Length; at++)
            value[at] = LevelAt(net, line[at]);
        for (int r = 0; r <= bands; r++)
        {
            double level = bedLevels[r];
            IReadOnlyList<SkinLevelCurve> bed = bedsAt[r];
            if (bed.Count == 0)
                continue;
            // ONE crossing per COMPONENT of this bed, and the FIRST one the
            // walk meets on each. A head joint on an arch runs springing to
            // springing over the crown, so it meets every bed again coming
            // down the far side, and that second meeting is the far side's
            // head joint rather than a duplicate of this one.
            var taken = new bool[bed.Count];
            for (int point = 0; point + 1 < line.Length; point++)
            {
                // A crossing lands between two polyline points whose
                // interpolated field values straddle the level; the
                // point is taken on the bed itself, by exact plan
                // projection, so a head joint LIES on its bed.
                double[] a = line[point];
                double[] b = line[point + 1];
                double la = value[point];
                double lb = value[point + 1];
                bool up = la < level && lb >= level;
                if (!up && !(lb < level && la >= level))
                    continue;
                double t = (level - la) / (lb - la);
                double[] on = Lerp(a, b, t);
                SkinLevelCurve component = bed[0];
                int componentAt = 0;
                double best = double.PositiveInfinity;
                for (int candidateAt = 0; candidateAt < bed.Count; candidateAt++)
                {
                    SkinLevelCurve candidate = bed[candidateAt];
                    double arc = NearestArcInPlan(candidate, on);
                    double[] near = PointAtArcPublic(candidate, arc);
                    double distance =
                        (near[0] - on[0]) * (near[0] - on[0]) +
                        (near[1] - on[1]) * (near[1] - on[1]);
                    if (distance < best)
                    {
                        best = distance;
                        component = candidate;
                        componentAt = candidateAt;
                    }
                }
                if (taken[componentAt])
                    continue;
                taken[componentAt] = true;
                if (r == skipBed && componentAt == skipComponent)
                    continue;
                // Rule 3.3.1a: the arc goes on the list of the COMPONENT it
                // was measured against, because it is signed from that
                // component's own seam and scaled by that component's own
                // length. The polyline index rides with it, so a cell can
                // follow ONE joint from this bed to the next rather than
                // guessing which of its crossings above is the right one.
                crossings[r][componentAt].Add(new SkinCrossing(
                    NearestArcInPlan(component, on) - component.Seam,
                    index, componentAt, point, on, up));
            }
        }
    }

    /// <summary>Rule 3.3.2's crossing: where one streamline meets one
    /// component of one bed. <c>U</c> is the arc signed from that
    /// component's own seam, <c>At</c> the index of the polyline segment the
    /// crossing lies in and <c>Point</c> the exact point within it, and
    /// <c>Up</c> whether the field was rising along the walk there, which is
    /// what tells a joint coming down the far side of a crown from one
    /// climbing this side.</summary>
    private sealed record SkinCrossing(
        double U, int Line, int Component, int At, double[] Point, bool Up);

    /// <summary>
    /// The stretch of one streamline between its crossing of a band's lower
    /// bed and its crossing of that band's upper bed, taken by POLYLINE
    /// INDEX and not by field value: a joint that runs over the crown
    /// re-enters the band's field range on the far side, and clipping by
    /// value alone would hand this side's chain to a far-side cell.
    ///
    /// Where the joint has NO upper crossing at all (rule 3.3.5's closer)
    /// it is walked to its own END, and the walk now stops at the first
    /// polyline point above the band's UPPER BED LEVEL so that a closer
    /// cannot climb out of its own band.
    ///
    /// THAT CLIP IS A GUARD AND NOT A FIX, and it is said here rather than
    /// left to be found. MEASURED 2026-09-03 across every fixture in the
    /// harness, Param's own crown arch included: it fires ZERO times, and
    /// it cannot fire while RecordCrossings stands as it does. A line that
    /// reaches the upper bed's level MUST cross it, RecordCrossings records
    /// the first crossing on every component of every bed, and Above reads
    /// all of them, so a null upper crossing already means the line stops
    /// inside the band. The clip is kept because that is an invariant of
    /// another function and not of this one.
    ///
    /// WHAT ACTUALLY ESCAPES is the chain standing outside the band's two
    /// beds along the way, and <paramref name="escaped"/> is what catches
    /// it: a closer walked to a line's end that DIPS below its own lower
    /// bed (55 of the 86 escapes on Param's crown arch at S 0.17), and a
    /// two-crossing chain walked between its crossings BY INDEX, which is
    /// deliberate and which lets a streamline that rises, falls and rises
    /// again stand outside the band in between (the other 31). Rule 3.3.5
    /// sanctions a three-sided closer, so a closer that stays inside its
    /// band is still emitted; only the ones that escape are refused.
    /// </summary>
    private static double[][] ChainBetween(
        double[][] line,
        IReadOnlyList<double> levels,
        double bandLow,
        double bandHigh,
        SkinCrossing from,
        SkinCrossing? to,
        out bool escaped)
    {
        // The band's own slack, a thousandth of its height, which is
        // 0.375 mm at the shipped course height of 0.375 m. It is there for
        // the field interpolation's rounding at a polyline point standing
        // on a bed and not to let a chain wander: an escape across a merge
        // is measured in metres, not in microns.
        double slack = Math.Max((bandHigh - bandLow) * 1.0e-3, 1.0e-9);
        var taken = new List<int>();
        if (to is null)
        {
            if (from.Up)
            {
                for (int at = from.At + 1; at < line.Length; at++)
                {
                    if (levels[at] > bandHigh + slack)
                        break;
                    taken.Add(at);
                }
            }
            else
            {
                for (int at = from.At; at >= 0; at--)
                {
                    if (levels[at] > bandHigh + slack)
                        break;
                    taken.Add(at);
                }
            }
        }
        else if (to.At >= from.At)
        {
            for (int at = from.At + 1; at <= to.At; at++)
                taken.Add(at);
        }
        else
        {
            for (int at = from.At; at > to.At; at--)
                taken.Add(at);
        }
        escaped = false;
        var chain = new List<double[]> { from.Point };
        foreach (int at in taken)
        {
            chain.Add(line[at]);
            escaped |= levels[at] > bandHigh + slack ||
                       levels[at] < bandLow - slack;
        }
        if (to is not null)
            chain.Add(to.Point);
        return chain.ToArray();
    }

    /// <summary>The POSITION in the list of the crossing whose arc is
    /// nearest a given arc, within a thousandth of the bed's own pitch, or
    /// -1. A merged span's ends are still two real crossings, so the piece
    /// picks up the OUTER two lines and not the two it started with. The
    /// position and not the line, because the cell needs the crossing's
    /// polyline index as well as which streamline it belongs to.</summary>
    private static int NearestCrossingLine(
        IReadOnlyList<SkinCrossing> crossings,
        double at)
    {
        if (crossings.Count == 0)
            return -1;
        double pitch = crossings.Count > 1
            ? (crossings[^1].U - crossings[0].U) / (crossings.Count - 1)
            : 0.0;
        double tolerance = Math.Max(Math.Abs(pitch) / 1000.0, 1.0e-9);
        int best = -1;
        double bestDistance = double.PositiveInfinity;
        for (int position = 0; position < crossings.Count; position++)
        {
            double distance = Math.Abs(crossings[position].U - at);
            if (distance < bestDistance)
            {
                bestDistance = distance;
                best = position;
            }
        }
        return bestDistance <= tolerance ? best : -1;
    }

    /// <summary>Rule 3.3.5, the five-sided half: did a line BEGIN within
    /// this cell's own span, meaning it carries a crossing on the band's
    /// upper bed strictly between the two named lines' crossings there and
    /// none at all on the band's lower bed? A line that begins nowhere near
    /// the cell changes no side count, which is what anchoring the parity on
    /// the line rather than on an index buys.</summary>
    private static bool InsertedWithin(
        IReadOnlyList<(double[][] Points, int Parity)> lines,
        IReadOnlyList<SkinCrossing> upper,
        IReadOnlyList<List<SkinCrossing>> lowerBed,
        int leftLine,
        int rightLine)
    {
        // The upper list is ONE component's (rule 3.3.1a), because the two
        // arcs bracketing the candidate have to be measured on the curve the
        // candidate's own arc was measured on. The lower is every component
        // of the bed below: a line that crosses that bed ANYWHERE did not
        // begin inside this band, whichever component it crossed on.
        double leftTop = double.NaN;
        double rightTop = double.NaN;
        foreach (SkinCrossing item in upper)
        {
            if (item.Line == leftLine)
                leftTop = item.U;
            if (item.Line == rightLine)
                rightTop = item.U;
        }
        if (double.IsNaN(leftTop) || double.IsNaN(rightTop))
            return false;
        double low = Math.Min(leftTop, rightTop);
        double high = Math.Max(leftTop, rightTop);
        var below = new HashSet<int>();
        foreach (List<SkinCrossing> component in lowerBed)
            foreach (SkinCrossing item in component)
                below.Add(item.Line);
        foreach (SkinCrossing item in upper)
        {
            if (item.Line == leftLine || item.Line == rightLine ||
                item.Line < 0 || item.Line >= lines.Count ||
                below.Contains(item.Line))
            {
                continue;
            }
            if (item.U > low + 1.0e-12 && item.U < high - 1.0e-12)
                return true;
        }
        return false;
    }

    /// <summary>Which net face contains a point in plan, or -1.
    ///
    /// A PLAN BOUNDING-BOX PREFILTER stands in front of the containment
    /// test, because NormalAt made this a hot path: every outline corner of
    /// every cell asks it, and it is a linear scan of the net's faces.
    ///
    /// The prefilter is ANSWER-PRESERVING and not a tolerance, which is why
    /// it may sit in front of a predicate the engine and the harness must
    /// never disagree about. PlanContains is a crossing count with STRICT
    /// comparisons. Above the box in y, or below it, no edge straddles the
    /// point's height and the count is zero. Right of the box in x, the
    /// crossing abscissa of any straddling edge lies between that edge's
    /// own two x, so it is no greater than the box's own maximum and the
    /// strict "x is less than" is false at every edge. Left of the box, a
    /// triangle straddles the point's height on exactly none or two of its
    /// edges (a horizontal edge straddles nothing under a strict test) and
    /// both toggles cancel. Every point the prefilter skips is a point
    /// PlanContains would have answered false for.</summary>
    private static int FaceUnder(SkinNet net, double[] at)
    {
        for (int face = 0; face < net.Faces.Count; face++)
        {
            int[] triangle = net.Faces[face];
            double[] pa = net.Vertices[triangle[0]];
            double[] pb = net.Vertices[triangle[1]];
            double[] pc = net.Vertices[triangle[2]];
            if (at[0] < Math.Min(pa[0], Math.Min(pb[0], pc[0])) ||
                at[0] > Math.Max(pa[0], Math.Max(pb[0], pc[0])) ||
                at[1] < Math.Min(pa[1], Math.Min(pb[1], pc[1])) ||
                at[1] > Math.Max(pa[1], Math.Max(pb[1], pc[1])))
            {
                continue;
            }
            var ring = new[] { pa, pb, pc };
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

    /// <summary>
    /// THE NORMAL FIELD (spec 2026-09-03, skin-offset-surface, rule 1):
    /// area-weighted unit normals, one per vertex, by the arithmetic
    /// bench/studio/blocks.py has carried since the studio's blocks were
    /// written (vertex_normals, lines 25 to 54).
    ///
    /// The area weighting is had FOR FREE by summing UNNORMALISED cross
    /// products, because a raw cross product is twice the triangle's own
    /// area. So a vertex shared by one large face and one small one leans
    /// toward the large one, which is the whole of what "area-weighted"
    /// buys and the reason no area is ever computed here explicitly.
    ///
    /// A face of ANY corner count is fanned from its first corner, because
    /// this engine's nets carry both triangles and quads: the net's own
    /// Faces property triangulates, but VertexNormals is called on raw face
    /// lists by the harness too and a quad-only reading would throw on a
    /// triangle. The fan is the same one blocks.py takes on its quads.
    ///
    /// A degenerate fan, whose crosses cancel or whose face list never
    /// mentions the vertex at all, falls back to (0, 0, 1): an arbitrary
    /// but FINITE direction is the honest answer where the surface has no
    /// normal, and it is what blocks.py answers too.
    /// </summary>
    public static IReadOnlyList<double[]> VertexNormals(
        IReadOnlyList<double[]> vertices, IReadOnlyList<int[]> faces)
    {
        var accumulator = new double[vertices.Count][];
        for (int at = 0; at < vertices.Count; at++)
            accumulator[at] = new double[3];
        foreach (int[] face in faces)
        {
            if (face.Length < 3)
                continue;
            for (int corner = 1; corner + 1 < face.Length; corner++)
            {
                int a = face[0];
                int b = face[corner];
                int c = face[corner + 1];
                if (a < 0 || a >= vertices.Count ||
                    b < 0 || b >= vertices.Count ||
                    c < 0 || c >= vertices.Count)
                {
                    continue;
                }
                double[] pa = vertices[a];
                double[] pb = vertices[b];
                double[] pc = vertices[c];
                double ux = pb[0] - pa[0];
                double uy = pb[1] - pa[1];
                double uz = pb[2] - pa[2];
                double vx = pc[0] - pa[0];
                double vy = pc[1] - pa[1];
                double vz = pc[2] - pa[2];
                double nx = (uy * vz) - (uz * vy);
                double ny = (uz * vx) - (ux * vz);
                double nz = (ux * vy) - (uy * vx);
                foreach (int index in new[] { a, b, c })
                {
                    accumulator[index][0] += nx;
                    accumulator[index][1] += ny;
                    accumulator[index][2] += nz;
                }
            }
        }
        var normals = new double[vertices.Count][];
        for (int at = 0; at < vertices.Count; at++)
        {
            double[] sum = accumulator[at];
            double length = Math.Sqrt(
                (sum[0] * sum[0]) + (sum[1] * sum[1]) + (sum[2] * sum[2]));
            normals[at] = length > 1.0e-12
                ? new[] { sum[0] / length, sum[1] / length, sum[2] / length }
                : new[] { 0.0, 0.0, 1.0 };
        }
        return normals;
    }

    /// <summary>
    /// THE AREA-WEIGHTED SUM OF EVERY RAW FACE CROSS over a net, which is
    /// the quantity spec 2026-09-04 (skin-offset-extrude-slider) rule 4
    /// reads the winding off. A raw cross is TWICE the triangle's area, so
    /// summing the raw crosses weights each face by its own area without
    /// any area being computed, exactly as VertexNormals does per vertex.
    ///
    /// It is the SUM over the whole net and not a vote per face, because a
    /// net whose faces disagree among themselves has no winding to read at
    /// all and the largest surface is the honest tie-break.
    ///
    /// Public so the harness can build a fixture BOTH WAYS ROUND and
    /// measure that the two give one field, which is rule 4's own check.
    /// </summary>
    public static double[] GlobalCrossSum(
        IReadOnlyList<double[]> vertices, IReadOnlyList<int[]> faces)
    {
        double sx = 0.0, sy = 0.0, sz = 0.0;
        foreach (int[] face in faces)
        {
            if (face.Length < 3)
                continue;
            for (int corner = 1; corner + 1 < face.Length; corner++)
            {
                int a = face[0];
                int b = face[corner];
                int c = face[corner + 1];
                if (a < 0 || a >= vertices.Count ||
                    b < 0 || b >= vertices.Count ||
                    c < 0 || c >= vertices.Count)
                {
                    continue;
                }
                double[] pa = vertices[a];
                double[] pb = vertices[b];
                double[] pc = vertices[c];
                double ux = pb[0] - pa[0];
                double uy = pb[1] - pa[1];
                double uz = pb[2] - pa[2];
                double vx = pc[0] - pa[0];
                double vy = pc[1] - pa[1];
                double vz = pc[2] - pa[2];
                sx += (uy * vz) - (uz * vy);
                sy += (uz * vx) - (ux * vz);
                sz += (ux * vy) - (uy * vx);
            }
        }
        return new[] { sx, sy, sz };
    }

    /// <summary>
    /// THE FIELD, ORIENTED (spec 2026-09-04, skin-offset-extrude-slider,
    /// rule 4). <see cref="VertexNormals"/> follows the mesh's own
    /// winding, and a winding is an accident of whoever built the net:
    /// Param's first offset test ran on a net wound the other way and
    /// drove every block through the surface instead of standing it on
    /// the surface.
    ///
    /// THE RULE IS ONE FLIP FOR THE WHOLE NET. Where the area-weighted sum
    /// of the raw face crosses (<see cref="GlobalCrossSum"/>) has NEGATIVE
    /// Z, every vertex normal is negated, once, globally. A positive Th is
    /// then outward and up on every net whatever its winding, and a
    /// negative one inward.
    ///
    /// ONE GLOBAL FLIP PRESERVES THE WELD EXACTLY. Rule 3 of spec
    /// 2026-09-03 rests on the field being a continuous function of the
    /// POINT alone; negating every vertex normal by one constant sign
    /// leaves it continuous and leaves it a function of the point, so two
    /// cells sharing a corner still move it to one place. A per-face or
    /// per-cell correction would not, which is why the rule is written
    /// this way and not as a hemisphere test.
    ///
    /// A ZERO OR POSITIVE Z IS LEFT ALONE, so a net already wound up comes
    /// back BIT-IDENTICAL rather than merely equal: the very list the
    /// unoriented field built, untouched. A flat net whose sum is exactly
    /// zero has no winding to read and is left as it is.
    /// </summary>
    public static IReadOnlyList<double[]> OrientedVertexNormals(
        IReadOnlyList<double[]> vertices, IReadOnlyList<int[]> faces)
    {
        IReadOnlyList<double[]> normals = VertexNormals(vertices, faces);
        if (GlobalCrossSum(vertices, faces)[2] >= 0.0)
            return normals;
        var flipped = new double[normals.Count][];
        for (int at = 0; at < normals.Count; at++)
        {
            double[] normal = normals[at];
            flipped[at] = new[] { -normal[0], -normal[1], -normal[2] };
        }
        return flipped;
    }

    /// <summary>
    /// THE NORMAL AT AN ARBITRARY POINT (spec 2026-09-03,
    /// skin-offset-surface, rule 2). An outline point is almost never a net
    /// vertex: it lies on a traced level curve, which crosses faces. So the
    /// face under the point is found in plan, by the same FaceUnder the
    /// cap's apex already uses, and the answer is the BARYCENTRIC
    /// combination of that face's three vertex normals, renormalised.
    ///
    /// WHY THIS IS ENOUGH FOR THE WELD, which is rule 3 and the whole point
    /// of the change. Interpolated vertex normals are CONTINUOUS ACROSS A
    /// FACE EDGE: along a shared edge both faces interpolate the same two
    /// vertex normals with the same weights, the third weight being zero on
    /// each side. So the answer is a continuous function of the POINT
    /// ALONE, independent of which of the two faces the lookup happened to
    /// pick, and two cells that share a corner move it to the same place
    /// whether or not they agree about its face. No weld pass, no
    /// tolerance, no shared-corner table. Nothing about the calling CELL
    /// may enter this method, or that argument fails and the change is
    /// worthless.
    ///
    /// OFF THE MESH IN PLAN, the answer is the NEAREST face's own, by the
    /// same rule LevelAt already answers an off-mesh point with: the face
    /// whose plan centroid is closest, evaluated at the point. This is not
    /// a nicety. A traced level curve runs along the net's own boundary
    /// edges, and PlanContains claims a boundary point for a face only
    /// about half the time, so 172 of the 8870 cell corners on Param's own
    /// crown arch found no face at all and took a VERTICAL thickness
    /// direction at the steep rim, which is exactly the defect this whole
    /// change removes. Amended 2026-09-04; rule 2's continuity argument is
    /// untouched, because the nearest-face answer is still a function of
    /// the POINT alone and two cells sharing such a corner still get the
    /// same three doubles back.
    ///
    /// A FACE WITH NO PLAN AREA answers the renormalised MEAN of its three
    /// vertex normals (spec 2026-09-04 section 6), which on a vertical face
    /// is a horizontal direction and is the whole point of the ruling.
    ///
    /// (0, 0, 1) survives only where there is no usable face to read at
    /// all: a net with no faces, an interpolated vector shorter than
    /// 1e-12, or a degenerate face whose own three normals cancel.
    /// </summary>
    public static double[] NormalAt(SkinNet net, double[] at)
    {
        if (net.Faces.Count == 0)
            return new[] { 0.0, 0.0, 1.0 };
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
        double twice =
            ((b[0] - a[0]) * (c[1] - a[1])) -
            ((c[0] - a[0]) * (b[1] - a[1]));
        // A PLAN-DEGENERATE FACE ANSWERS WITH THE MEAN OF ITS OWN THREE
        // VERTEX NORMALS (spec 2026-09-04, section 6). The tolerance is the
        // same 1e-15 LevelAt refuses to divide by on the SAME triangle: one
        // tolerance for one geometric fact, and a face of twice-plan-area
        // 1e-16 would otherwise multiply a point's offsets by 1e16 and
        // answer with noise.
        //
        // WHAT CHANGED, AND WHY IT IS A RULING AND NOT A TOLERANCE. Until
        // 2026-09-04 this branch answered (0, 0, 1), a VERTICAL direction
        // on a face standing EXACTLY VERTICAL, which is the one place the
        // offset most needs a horizontal one: the offset there degraded
        // silently to the extrusion it exists to replace. The mean is what
        // LevelAt's own degenerate convention already does with the same
        // triangle (it answers with the mean of its three values), so this
        // is the sibling's rule and not a new one. Param ruled on it after
        // it was parked as paragraph 8 of the 2026-09-03 erratum.
        //
        // (0, 0, 1) survives only for a net with no usable face at all: no
        // faces, or a mean that cancels to nothing.
        if (Math.Abs(twice) <= 1.0e-15)
        {
            double mx = 0.0, my = 0.0, mz = 0.0;
            foreach (int corner in triangle)
            {
                double[] normal = net.Normals[corner];
                mx += normal[0];
                my += normal[1];
                mz += normal[2];
            }
            double mean = Math.Sqrt((mx * mx) + (my * my) + (mz * mz));
            return mean > 1.0e-12
                ? new[] { mx / mean, my / mean, mz / mean }
                : new[] { 0.0, 0.0, 1.0 };
        }
        double wb =
            (((at[0] - a[0]) * (c[1] - a[1])) -
             ((c[0] - a[0]) * (at[1] - a[1]))) / twice;
        double wc =
            (((b[0] - a[0]) * (at[1] - a[1])) -
             ((at[0] - a[0]) * (b[1] - a[1]))) / twice;
        double wa = 1.0 - wb - wc;
        double[] na = net.Normals[triangle[0]];
        double[] nb = net.Normals[triangle[1]];
        double[] nc = net.Normals[triangle[2]];
        double x = (wa * na[0]) + (wb * nb[0]) + (wc * nc[0]);
        double y = (wa * na[1]) + (wb * nb[1]) + (wc * nc[1]);
        double z = (wa * na[2]) + (wb * nb[2]) + (wc * nc[2]);
        double length = Math.Sqrt((x * x) + (y * y) + (z * z));
        return length > 1.0e-12
            ? new[] { x / length, y / length, z / length }
            : new[] { 0.0, 0.0, 1.0 };
    }

    /// <summary>The existing private PointAtArc, reachable from this file's
    /// own crossing walk. A wrapper and not a second implementation, so a
    /// head joint's point and a bed's own point cannot disagree.</summary>
    internal static double[] PointAtArcPublic(SkinLevelCurve curve, double arc) =>
        PointAtArc(curve, arc);

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
            Sections: new[] { (IReadOnlyList<double[]>)lower, upper });
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
    /// WHERE the level curves stopped corresponding, as the one sentence
    /// fragment every reader of a refusal gets. It lives on its own
    /// because the Skin component's own transition WARNING promised the
    /// reader "Diagnostics names the heights" while no component read
    /// Diagnostics at all after the D port went, so the promise was
    /// unkept from the day the port was removed. The component now
    /// appends this same fragment to its warning, and it must be the
    /// SAME arithmetic and the same wording as the diagnostics line, not
    /// a second formatter that can drift.
    ///
    /// Rule 8.2.8: a rim distance is a DISTANCE and is named as one, in
    /// metres; the "z=" wording survives only under the fallback of rule
    /// 1.7.4, where it is still true.
    /// </summary>
    internal static string TransitionWhere(
        IReadOnlyList<(double Low, double High)> transitions,
        string fieldKind)
    {
        static string F(double value) =>
            value.ToString("F3", CultureInfo.InvariantCulture);
        return string.Join(
            " and ",
            transitions.Select(item =>
                fieldKind == "world Z"
                    ? $"between z={F(item.Low)} and z={F(item.High)}"
                    : $"between d={F(item.Low)} m and d={F(item.High)} m"));
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
        string where = TransitionWhere(transitions, fieldKind);
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
    /// stagger, the count of boundary-clipped cells, the THREE
    /// plan-validity drop counts and, where the level curves do not
    /// correspond, the refused transition bands. The key of every line
    /// is capitalised, so the transition line reads beside the rest
    /// rather than under it. The drop lines are worded exactly as the
    /// force-aligned pattern words its own, because they mean the same
    /// thing and an author reading D should not have to notice which
    /// pattern produced it. weldCollapsedDropped is studio request R-006:
    /// an outline welded (rule: consecutive corners within 1e-6 m) below
    /// three distinct corners at emission, before it ever reached the
    /// other two filters.</summary>
    private static string PatternDiagnostics(
        string name,
        int cellCount,
        int courseCount,
        IReadOnlyList<double> pieceLengths,
        string stagger,
        int clipped,
        int mergedPieces,
        int planDegenerateDropped,
        int planOverlapDropped,
        string? transitions = null,
        string? caps = null,
        int weldCollapsedDropped = 0,
        double planCoverage = double.NaN)
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
            $"Merged pieces: {mergedPieces} (spans at or under the minimum " +
            "piece size, merged into the shorter neighbour along the course)");
        lines.Add(
            $"Plan-degenerate cells dropped: {planDegenerateDropped} " +
            "(self-crossing in plan; excluded automatically so the " +
            "sidecar imports)");
        lines.Add(
            $"Plan-overlap cells dropped: {planOverlapDropped} " +
            "(overlapped another surviving cell in plan; excluded " +
            "automatically so the sidecar imports)");
        lines.Add(
            $"Weld-collapsed cells dropped: {weldCollapsedDropped} " +
            "(outline fell below three distinct corners once consecutive " +
            "corners within 1e-6 m were welded at emission; excluded " +
            "automatically so the sidecar imports)");
        if (double.IsFinite(planCoverage))
        {
            // Whole-branch review finding 12. A drop count tells an author
            // how many cells went; it does not tell him how much SHELL
            // went, and on this pattern those are different questions,
            // because a dropped honeycomb candidate leaves a hole where a
            // dropped courses cell rarely does.
            lines.Add(
                "Plan coverage: " +
                F(planCoverage * 100.0) +
                " per cent of the net's own plan area (the surviving " +
                "cells are disjoint in plan, so the remainder is " +
                "uncovered shell and not overlap)");
        }
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
                0, 0, 0, 0),
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
            Array.Empty<int>(),
            0,
            0,
            0,
            1,
            0,
            0,
            Array.Empty<double[][]>(),
            Array.Empty<double[][]>());

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

    /// <summary>Signed arc about the seam from a NORMALISED position on a
    /// row: t in [0, 1) is normalised arc from the seam on a closed row and
    /// from the strip's start on an open one, and an open strip's seam is
    /// its arc-length midpoint at t = 0.5. Where the column set that feeds
    /// this is laid out is <see cref="ColumnAt"/>'s business, not
    /// this method's.</summary>
    private static double ArcOf(SkinLevelCurve curve, double t) =>
        curve.Closed
            ? t * curve.Length
            : t * curve.Length - curve.Length / 2.0;

    /// <summary>
    /// Rule 4.2.4's column position for one row, normalised.
    ///
    /// A CLOSED loop has no ends and its columns run from the seam at
    /// j / m, a set that is its own mirror. An OPEN strip's seam is its
    /// arc-length MIDPOINT, and AssignSeams states the guarantee that
    /// follows in its own words: setout is centre-outward, so
    /// mirror-symmetric geometry gets mirror-symmetric joints by
    /// construction. j / m does not honour it. It anchors the grid on the
    /// strip's LEFT END, so for m = 8 the arcs run -0.5 to +0.375 of L
    /// whose mirror is -0.375 to +0.5, a different set. Measured on
    /// Param's own net, mirror-symmetric in y to 7e-14 m: 26 of the
    /// honeycomb's 501 cells had no mirror partner within 10 mm, against
    /// none at all of the 1032 courses cells. Whole-branch review finding
    /// 13.
    ///
    /// THE CENTRING HAS TO BE DONE ON THE USED SUBSET AND NOT ON m, and
    /// this is where the review's own suggested one-liner, 0.5 + (j -
    /// (m - 1) / 2) / m, goes wrong. Rule 4.2.4 takes only the columns
    /// with j + k EVEN, which is half of them, and centring the whole set
    /// of m leaves that half a QUARTER of a column pitch off centre.
    /// MEASURED: it takes Param's honeycomb from 26 unpartnered cells to
    /// 484 of 495, which is worse than what it was written to fix.
    ///
    /// Nor can the two row families simply both be centred and keep the
    /// bond. A set of n columns at spacing 1 / n has exactly ONE
    /// arrangement symmetric about the seam, so two symmetric rows of
    /// equal count coincide and the half-pitch offset rule 4.2.4 exists
    /// for is lost. The rows have to ALTERNATE between two counts one
    /// apart, which is what a honeycomb strip does at its ends anyway.
    ///
    /// The whole of it is one shift and one extra column:
    ///
    ///     t = (j + 1) / m,  with j running from -1 rather than 0
    ///
    /// An even row takes j = 0, 2, ... m - 2 and gets m / 2 columns from
    /// 1 / m to 1 - 1 / m, inset half a pitch at each end and symmetric
    /// about the seam. An odd row takes j = -1, 1, ... m - 1 and gets
    /// m / 2 + 1 columns from 0 to 1, standing ON both ends and also
    /// symmetric about the seam, one column pitch off the even row's set.
    /// The LONGER row is the one carrying the end columns, which is what
    /// keeps a narrow strip alive: at n = 1 the short row takes one centre
    /// on the seam and the long row two on the ends, where taking the
    /// alternation the other way would have left a row with none at all.
    /// </summary>
    private static double ColumnAt(int j, int columns, bool closed) =>
        closed
            ? (double)j / columns
            : (double)(j + 1) / columns;

    /// <summary>The first column index of a row: 0 on a closed loop, which
    /// has no ends, and -1 on an OPEN strip, where
    /// <see cref="ColumnAt"/> shifts the whole set by one column so that
    /// both row families stand symmetrically about the strip's own
    /// seam.</summary>
    private static int FirstColumn(bool closed) => closed ? 0 : -1;

    /// <summary>
    /// How many of a neighbouring row's columns fall within the cell's own
    /// span (rule 4.2.5's closing paragraph and rule 4.3): one column
    /// within the span is the plain honeycomb; NONE marks a five-sided
    /// cell; TWO a seven-sided one. Split out from vertex-building (below)
    /// so a cell whose count changes on BOTH sides at once can be resolved
    /// before either side commits to an odd shape; see the note on
    /// <see cref="VerticesForWithin"/>.
    /// </summary>
    private static int WithinCount(
        double t,
        int columns,
        bool closed,
        double spanLeft,
        double spanRight)
    {
        int within = 0;
        for (int j = FirstColumn(closed); j < columns; j++)
        {
            double at = ColumnAt(j, columns, closed);
            if (closed)
            {
                double shifted = at - t;
                shifted -= Math.Floor(shifted + 0.5);
                at = t + shifted;
            }
            if (at > spanLeft + 1.0e-12 && at < spanRight - 1.0e-12)
                within++;
        }
        return within;
    }

    /// <summary>
    /// The vertices a neighbouring row contributes for a given WithinCount
    /// (rule 4.2.5's closing paragraph): one column within the span is the
    /// plain honeycomb and gives two vertices at that row's own thirds;
    /// NONE gives one vertex and a five-sided cell; TWO gives three
    /// vertices and a seven-sided one. Where the extra vertex sits is this
    /// engine's own resolution, stated because the spec states the count
    /// and not the position: at the cell's own centre, so the extra corner
    /// lies on the cell's axis and the cell stays symmetric about it.
    ///
    /// DEVIATION (recorded in progress.md): tried literally first with
    /// each side's WithinCount committing independently, which rule 4.3.4
    /// bounds only in MAGNITUDE (adjacent rows differ by at most one
    /// centre) and not in WHICH side of a row it falls on. On a dome,
    /// whose centre count tapers by exactly one every row, an interior
    /// row differs from its row below AND its row above at once, at the
    /// same meridian both transitions share, and the literal rule built
    /// an 8-sided cell there, which check 12.4(d)/(e)'s converse
    /// (rule 4.3, six/five/seven only) then caught. The smallest
    /// correction: at most one side of a cell may be irregular; where
    /// both are, the side closer to the ordinary count of one is treated
    /// as ordinary (a tie keeps the below side irregular), capping every
    /// cell at seven sides as rule 4.3.4 states.
    /// </summary>
    private static List<double> VerticesForWithin(
        double t,
        int columns,
        int within,
        ref int fiveSided,
        ref int sevenSided)
    {
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

        // Rule 4.2.1: rows run 0 to K at k * CH, the two extremes pulled
        // inside the surface by the epsilon of rule 1.5.2, and nothing
        // clamped beyond the surface.
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
        IReadOnlyList<IReadOnlyList<SkinLevelCurve>> traced =
            TraceAll(net, levels);
        List<SkinChart> charts = BuildCharts(traced);

        // The TOPOLOGY TRANSITIONS, found once for the whole net: a pair
        // of consecutive levels whose components do not CORRESPOND one
        // for one is a height a hexagon cannot bond across, because the
        // vertices of one cell would map through curves that are not the
        // same piece of surface. Every lattice row spanning such an
        // interval is refused whole, the same ruling the courses engine
        // follows and the same correspondence test.
        var transitions = new List<(double Low, double High)>();
        for (int level = 0; level + 1 < levels.Count; level++)
        {
            if (!Corresponds(traced[level], traced[level + 1]))
            {
                AddTransition(
                    transitions, levels[level], levels[level + 1]);
            }
        }
        var skippedRows = new HashSet<int>();

        var keyed =
            new List<(int Course, int Chart, double U0, SkinCell Cell)>();
        var closedRows = new HashSet<int>();
        var countChangeRows = new HashSet<int>();
        int fiveSided = 0;
        int sevenSided = 0;
        int weldCollapsed = 0;
        for (int chartAt = 0; chartAt < charts.Count; chartAt++)
        {
            SkinChart chart = charts[chartAt];
            int rows = chart.Curves.Count;
            // DEVIATION (recorded in progress.md): tried the brief's
            // literal "fewer than three curves, skip the whole chart"
            // guard first, kept from when the interior loop needed a
            // below AND an above from OTHER rows. Both ends now
            // self-clamp (above), so a chart of one or two curves still
            // gets a below and an above; skipping it whole instead
            // dropped every course a short-lived chart would have
            // covered. Measured on the two-hump barrel, whose base
            // chart runs only two levels before the topology transition
            // splits it into the two hump charts: courses 0 and 1, which
            // only that chart ever carries, came back with no cells at
            // all. The smallest correction: only a chart with NO curves
            // at all is skipped.
            if (rows < 1)
                continue;

            // COUNTS, stated in CENTRES and not in columns (rule 4.2.2).
            // Row k takes its own centre count n_k = max(1, round(L_k /
            // (1.5 S))) from its own arc length and its column count is
            // m_k = 2 n_k, so the column pitch is L_k / m_k against a
            // target of 0.75 S. The count is taken in centres because
            // rule 4.2.4 puts a centre on every other column, and on a
            // CLOSED row that alternation only closes onto itself when
            // the column count is EVEN: round a column count straight
            // off the length and it is odd about half the time, two
            // hexagons then sit side by side at the meridian and their
            // cells overlap, which is the very defect this section
            // exists to remove arriving by a different road.
            var centres = new int[rows];
            for (int k = 0; k < rows; k++)
            {
                centres[k] = Math.Max(
                    1,
                    (int)Math.Round(chart.Curves[k].Length / (1.5 * size)));
            }
            // Rule 4.3.4: where two adjacent rows would differ by more
            // than one CENTRE the difference is spread over the
            // intervening rows one centre at a time, so no single row
            // carries more than one centre change and no cell has more
            // than seven sides. The adjustment is made in CENTRES and
            // never in columns, because a closed row's column count must
            // stay even and an even count can only change by two.
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

            // DEVIATION (recorded in progress.md): tried the brief's
            // literal interior range, k = 1 to rows - 2, first, which
            // only ever reads a chart's own SECOND curve through its
            // second-to-last as "here": the first and last curves feed a
            // neighbour's below or above but are never a "here"
            // themselves. Read off its own HEIGHT (the course line
            // below), that loses whichever course the chart's own first
            // curve names: measured on the two-peak net, whose one chart
            // spans the whole net, course 0 came back with no cells,
            // because the chart's first curve IS the net's own base.
            // Widening the range to k = 0 to rows - 1 with BOTH ends
            // self-clamping (a chart's own first curve stands in for its
            // own below, its own last for its own above) fixed that
            // fixture but then measured wrong the other way on the next
            // one: a chart's LAST curve is, on every fixture tried, a
            // dTop (or matched-transition) clamp that the surface itself
            // pulls inside its already-covered top band rather than a
            // new one of its own, so self-clamping it as a SECOND "here"
            // built a duplicate top course, measured on the barrel as a
            // row of 28 cells where its four other rows held 14. Rows
            // read off a real, unclamped height never repeat a course
            // this way, because each is a full course height from the
            // last; only a clamped end can coincide with the row before
            // it. The smallest correction: keep the widened range and
            // the self-clamp, which is what let the two-hump barrel's
            // hump chart (born partway up the net, so its own first
            // curve is not the net's base either) reach ITS first
            // course, and skip a "here" whose course repeats the one
            // immediately before it in the same chart, which is what a
            // genuine extra course never does and a redundant clamp
            // always does.
            int lastCourse = -1;
            for (int k = 0; k < rows; k++)
            {
                int columns = 2 * centres[k];
                SkinLevelCurve here = chart.Curves[k];
                SkinLevelCurve below = chart.Curves[Math.Max(0, k - 1)];
                SkinLevelCurve above =
                    chart.Curves[Math.Min(rows - 1, k + 1)];
                if (!ChainCorresponds(here, below) ||
                    !ChainCorresponds(above, here))
                {
                    skippedRows.Add(k);
                    continue;
                }
                int course = Math.Min(
                    bands - 1,
                    Math.Max(0, (int)Math.Floor(
                        (here.Level - dMin) / courseHeight + 1.0e-9)));
                if (course == lastCourse)
                    continue;
                lastCourse = course;
                if (here.Closed)
                    closedRows.Add(course);
                int columnsBelow = 2 * centres[Math.Max(0, k - 1)];
                int columnsAbove = 2 * centres[Math.Min(rows - 1, k + 1)];
                for (int j = FirstColumn(here.Closed); j < columns; j++)
                {
                    // CENTRES (rule 4.2.4): a hexagon has its centre at
                    // (row k, column j) with j + k EVEN, so adjacent
                    // rows' centres are offset by exactly one column
                    // pitch, 1 / m_k in normalised arc, which is half the
                    // in-row centre spacing of 2 / m_k. That is the
                    // honeycomb's own offset and rule 4.2.3 applies it in
                    // this ONE place: there is no phase term in the
                    // column set, because the phase and the parity are
                    // two spellings of one rule.
                    //
                    // An OPEN strip's j starts at -1, so the remainder is
                    // taken the mathematician's way and not the machine's:
                    // C# gives -1 % 2 = -1.
                    if ((((j + k) % 2) + 2) % 2 != 0)
                        continue;
                    double t = ColumnAt(j, columns, here.Closed);

                    // VERTICES (rule 4.2.5), as fractions of each ROW'S
                    // OWN column pitch, EACH EVALUATED ON ITS OWN ROW'S
                    // parameterisation and never on the centre row's. Two
                    // thirds and one third of a column pitch are, at a
                    // pitch of 0.75 S, exactly S / 2 and S / 4, which is
                    // the shipped flat-topped hexagon.
                    double sideLeft = t - 2.0 / (3.0 * columns);
                    double sideRight = t + 2.0 / (3.0 * columns);
                    int belowWithin = WithinCount(
                        t, columnsBelow, here.Closed, sideLeft, sideRight);
                    int aboveWithin = WithinCount(
                        t, columnsAbove, here.Closed, sideLeft, sideRight);
                    // At most ONE side is irregular per cell (rule 4.3.4
                    // caps every cell at seven sides); see the deviation
                    // note on VerticesForWithin.
                    if (belowWithin != 1 && aboveWithin != 1)
                    {
                        if (Math.Abs(belowWithin - 1) <= Math.Abs(aboveWithin - 1))
                            aboveWithin = 1;
                        else
                            belowWithin = 1;
                    }
                    List<double> bottom = VerticesForWithin(
                        t, columnsBelow, belowWithin,
                        ref fiveSided, ref sevenSided);
                    List<double> aboveVerts = VerticesForWithin(
                        t, columnsAbove, aboveWithin,
                        ref fiveSided, ref sevenSided);

                    var outline = new List<double[]>();
                    foreach (double at in bottom)
                        outline.Add(PointAt(below, ArcOf(below, at)));
                    outline.Add(PointAt(here, ArcOf(here, sideRight)));
                    for (int at = aboveVerts.Count - 1; at >= 0; at--)
                        outline.Add(
                            PointAt(above, ArcOf(above, aboveVerts[at])));
                    outline.Add(PointAt(here, ArcOf(here, sideLeft)));
                    List<double[]> cleaned = Dedupe(outline);
                    if (cleaned.Count < 3)
                    {
                        // R-006: welded below three distinct corners.
                        weldCollapsed++;
                        continue;
                    }
                    bool clipped = !here.Closed &&
                        (sideLeft < 0.0 || sideRight > 1.0);
                    int setoutCorners = bottom.Count + aboveVerts.Count + 2;
                    if (setoutCorners != 6)
                        countChangeRows.Add(course);
                    // Rule 5.2.3(b): a REGULAR hexagon (six setout corners)
                    // lofts three sections in outline order, the bottom
                    // run, the two-point section from the left side vertex
                    // to the right, and the top run; a five- or seven-sided
                    // cell carries none and takes the deterministic fan of
                    // route (e), because its odd corner has no matching
                    // section on the opposite run to loft against.
                    IReadOnlyList<IReadOnlyList<double[]>>? sections =
                        setoutCorners == 6
                            ? new IReadOnlyList<double[]>[]
                              {
                                  bottom
                                      .Select(at =>
                                          PointAt(below, ArcOf(below, at)))
                                      .ToList(),
                                  new List<double[]>
                                  {
                                      PointAt(here, ArcOf(here, sideLeft)),
                                      PointAt(here, ArcOf(here, sideRight))
                                  },
                                  aboveVerts
                                      .Select(at =>
                                          PointAt(above, ArcOf(above, at)))
                                      .ToList()
                              }
                            : null;
                    var cell = new SkinCell(
                        course, cleaned, clipped,
                        ArcOf(here, sideLeft), ArcOf(here, sideRight),
                        false, setoutCorners, sections);
                    keyed.Add((course, chartAt, cell.U0, cell));
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
                .ThenBy(item => Math.Abs(
                    (item.Cell.U0 + item.Cell.U1) / 2.0))
                .ThenBy(item => (item.Cell.U0 + item.Cell.U1) / 2.0)
                .Select(item => item.Cell)
                .ToList(),
            out int degenerateDropped,
            out int overlapDropped,
            out int degenerateCentroidsSkipped);
        List<int> countChangeRowsSorted =
            countChangeRows.OrderBy(row => row).ToList();
        string? oddLine = fiveSided + sevenSided > 0
            ? $"Odd cells: {fiveSided} five-sided, {sevenSided} seven-sided " +
              "(row counts change at rows " +
              string.Join(", ", countChangeRowsSorted) + ")"
            : null;
        return new SkinPatternResult(
            cells,
            bands,
            PatternDiagnostics(
                "hexagonal", cells.Count, bands,
                cells.Select(cell => cell.U1 - cell.U0).ToList(),
                "0.75 x S per course row",
                cells.Count(cell => cell.Clipped),
                0,
                degenerateDropped, overlapDropped,
                TransitionLine(
                    "hexagonal", skippedRows.Count, transitions,
                    FieldKindOf(net)),
                oddLine,
                weldCollapsed,
                PlanCoverage(net, cells)),
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
            fiveSided,
            sevenSided,
            countChangeRowsSorted,
            closedRows.OrderBy(row => row).ToList(),
            0,
            degenerateCentroidsSkipped,
            0,
            1,
            0,
            0,
            Array.Empty<double[][]>(),
            Array.Empty<double[][]>(),
            weldCollapsed);
    }
}
