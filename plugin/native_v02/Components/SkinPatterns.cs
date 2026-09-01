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
internal sealed record SkinNet(
    IReadOnlyList<double[]> Vertices,
    IReadOnlyList<int[]> Faces)
{
    /// <summary>The faces, triangulated. An all-triangle face list comes
    /// through untouched, so the invariant is idempotent and a net built
    /// from another net's faces is the same net.</summary>
    public IReadOnlyList<int[]> Faces { get; } =
        SkinPatterns.Triangulate(Vertices, Faces);
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
    public double Height { get; set; }

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
    double U1);

/// <summary>One generated pattern: the cells sorted by course then
/// position (the studio's build sequence), the band count, the readable
/// diagnostics text the component's D output carries, the count of
/// bands REFUSED because the level curves across them do not correspond
/// one for one, and the two counts of cells DROPPED by the plan-validity
/// filter, self-crossing and overlapping. The component turns all three
/// into runtime Warnings, because a hole in the skin has to be said out
/// loud whether a band or a cell made it.</summary>
internal sealed record SkinPatternResult(
    IReadOnlyList<SkinCell> Cells,
    int CourseCount,
    string Diagnostics,
    int TransitionBands,
    int PlanDegenerateDropped,
    int PlanOverlapDropped);

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
        return new SkinNet(vertices, faces);
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

    /// <summary>One step of Triangulate's rule: find the shortest valid
    /// plan diagonal, cut the ring in two along it and recurse. The
    /// comment on Triangulate carries the rule and the tie-break.
    /// </summary>
    private static void SplitPolygon(
        IReadOnlyList<double[]> vertices,
        IReadOnlyList<int> ring,
        List<int[]> into)
    {
        int count = ring.Count;
        if (count < 3)
            return;
        if (count == 3)
        {
            into.Add(new[] { ring[0], ring[1], ring[2] });
            return;
        }
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
                double[] a = vertices[ring[from]];
                double[] b = vertices[ring[to]];
                double dx = a[0] - b[0];
                double dy = a[1] - b[1];
                double length = Math.Sqrt(dx * dx + dy * dy);
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
        if (bestFrom < 0)
        {
            // Degenerate in plan, outside the height-field domain: fan
            // from the first corner so the answer is still deterministic.
            for (int corner = 1; corner + 1 < count; corner++)
            {
                into.Add(new[]
                {
                    ring[0], ring[corner], ring[corner + 1]
                });
            }
            return;
        }
        // The two halves, each still wound the way the face was: the near
        // side runs from the diagonal's first corner to its second, the
        // far side leaves the first corner, jumps the diagonal and comes
        // back round. Both start at the same corner, so a quad split on
        // its 0-2 diagonal reads [0,1,2] and [0,2,3] rather than the
        // same triangles written from somewhere else in their cycle.
        var near = new List<int>();
        for (int at = bestFrom; at <= bestTo; at++)
            near.Add(ring[at]);
        var far = new List<int> { ring[bestFrom] };
        for (int at = bestTo; at != bestFrom; at = (at + 1) % count)
            far.Add(ring[at]);
        SplitPolygon(vertices, near, into);
        SplitPolygon(vertices, far, into);
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
        IReadOnlyList<double> heights)
    {
        var working = new List<List<SkinLevelCurve>>();
        foreach (double height in heights)
            working.Add(Trace(net, height));
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
    private static List<SkinLevelCurve> Trace(SkinNet net, double height)
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
            double za = net.Vertices[key.Item1][2];
            double zb = net.Vertices[key.Item2][2];
            double t = (height - za) / (zb - za);
            crossingByEdge[key] = crossingPoints.Count;
            crossingPoints.Add(
                Lerp(net.Vertices[key.Item1], net.Vertices[key.Item2], t));
            return crossingPoints.Count - 1;
        }

        bool Crosses(int a, int b)
        {
            double za = net.Vertices[a][2];
            double zb = net.Vertices[b][2];
            return (za < height && zb >= height) ||
                   (zb < height && za >= height);
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
                curves.Add(Finish(Walk(index, out bool closed), height, closed));
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
            curves.Add(Finish(Walk(index, out bool closed), height, closed));
        }
        return curves
            .Where(curve => curve.Points.Count >= 2 && curve.Length > 1.0e-12)
            .ToList();
    }

    private static SkinLevelCurve Finish(
        List<double[]> points,
        double height,
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
            Height = height,
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
        SkinLevelCurve rebuilt = Finish(points, curve.Height, curve.Closed);
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
    /// neighbours and not an overlap. The 1e-9 floor on the side values
    /// is what makes "strictly" survive arithmetic on coordinates of the
    /// order of a vault.
    /// </summary>
    private static bool PlanSegmentsCross(
        double[] a,
        double[] b,
        double[] c,
        double[] d)
    {
        double d1 = PlanSide(a, b, c);
        double d2 = PlanSide(a, b, d);
        double d3 = PlanSide(c, d, a);
        double d4 = PlanSide(c, d, b);
        return ((d1 > 1.0e-9 && d2 < -1.0e-9) ||
                (d1 < -1.0e-9 && d2 > 1.0e-9)) &&
               ((d3 > 1.0e-9 && d4 < -1.0e-9) ||
                (d3 < -1.0e-9 && d4 > 1.0e-9));
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
    /// Do two outlines OVERLAP in plan? True when any edge of one
    /// properly crosses any edge of the other, and true when one's own
    /// interior point lies inside the other, which is the containment
    /// case no edge crossing can see. The interior point used is the
    /// outline's plan mean, and it is required to lie inside the
    /// outline itself before it is asked about the other, since a
    /// non-convex outline's mean can fall outside it.
    ///
    /// Touching along a shared joint edge is NOT overlap: two cells of
    /// the same course meet at their joint by construction and the
    /// crossing test is strict.
    ///
    /// PUBLIC for the same reason PlanSelfCrosses is.
    /// </summary>
    public static bool PlansOverlap(
        IReadOnlyList<double[]> first,
        IReadOnlyList<double[]> second)
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
        double x = 0.0;
        double y = 0.0;
        foreach (double[] point in first)
        {
            x += point[0];
            y += point[1];
        }
        x /= first.Count;
        y /= first.Count;
        if (PlanContains(x, y, first) && PlanContains(x, y, second))
            return true;
        x = 0.0;
        y = 0.0;
        foreach (double[] point in second)
        {
            x += point[0];
            y += point[1];
        }
        x /= second.Count;
        y /= second.Count;
        return PlanContains(x, y, second) && PlanContains(x, y, first);
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
                overlaps = PlansOverlap(cell.Outline, kept[at].Outline);
            }
            if (overlaps)
            {
                overlapDropped++;
                continue;
            }
            kept.Add(cell);
            boxes.Add((minX, minY, maxX, maxY));
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
        (double zMin, double zMax) = HeightRange(net);
        if (net.Faces.Count == 0 || !(zMax - zMin > 1.0e-9))
            return Empty("courses");

        int bands = BandCount(zMin, zMax, courseHeight);
        double epsilon = Math.Max((zMax - zMin) * 1.0e-6, 1.0e-9);

        // Heights, ascending: the boundary of band r at index 2r, its
        // mid-height at 2r + 1. The extreme cuts are pulled inside the
        // surface by epsilon so the trace exists at the base and the
        // crown; the top band's mid runs to the true crown height.
        var heights = new List<double>();
        for (int r = 0; r <= bands; r++)
        {
            heights.Add(
                r == 0 ? zMin + epsilon
                : r == bands ? zMax - epsilon
                : zMin + r * courseHeight);
            if (r < bands)
            {
                double bandTop = r == bands - 1
                    ? zMax
                    : zMin + (r + 1) * courseHeight;
                heights.Add((zMin + r * courseHeight + bandTop) / 2.0);
            }
        }
        IReadOnlyList<IReadOnlyList<SkinLevelCurve>> traced =
            TraceAll(net, heights);

        var keyed =
            new List<(int Course, int Order, double U0, SkinCell Cell)>();
        var transitions = new List<(double Low, double High)>();
        int transitionBands = 0;
        for (int r = 0; r < bands; r++)
        {
            IReadOnlyList<SkinLevelCurve> mids = traced[2 * r + 1];
            IReadOnlyList<SkinLevelCurve> lowers = traced[2 * r];
            IReadOnlyList<SkinLevelCurve> uppers = traced[2 * r + 2];
            // A TOPOLOGY TRANSITION: the components of the three levels
            // this band spans do not CORRESPOND one for one, so
            // MatchBelow would pair curves that are not the same piece
            // of surface and the band would be laid with overlapping and
            // self-crossing cells. The mid curve is what every cell of
            // the band is set out on, so the correspondence is tested
            // from the mid DOWN to the lower level and from the mid UP
            // to the upper. Refuse the band whole (spec is silent on
            // transitions; the ruling is that a stated hole beats a
            // poisoned sidecar, because Bench Studio rejects a whole
            // tessellation for one self-crossing cell). Splitting the
            // band at its transition height is the right long answer and
            // belongs to a later wave.
            if (!Corresponds(mids, lowers) || !Corresponds(mids, uppers))
            {
                transitionBands++;
                AddTransition(
                    transitions, heights[2 * r], heights[2 * r + 2]);
                continue;
            }
            for (int component = 0; component < mids.Count; component++)
            {
                SkinLevelCurve mid = mids[component];
                int lowerAt = MatchBelow(mid, lowers);
                int upperAt = MatchBelow(mid, uppers);
                if (lowerAt < 0 || upperAt < 0 || !(mid.Length > 1.0e-9))
                    continue;
                SkinLevelCurve lowerCurve = lowers[lowerAt];
                SkinLevelCurve upperCurve = uppers[upperAt];
                int pieces = Math.Max(
                    1, (int)Math.Round(mid.Length / size));
                double pitch = mid.Length / pieces;
                double phase = r % 2 == 0 ? 0.0 : 0.5 * pitch;
                foreach ((double u0, double u1) in
                         CourseSpans(mid, pieces, pitch, phase))
                {
                    // Only an open strip's end piece is shorter than the
                    // pitch: it absorbed the phase, and it is the
                    // "boundary-clipped" cell of this pattern.
                    bool endPiece = u1 - u0 < pitch - 1.0e-9;
                    SkinCell cell = BandCell(
                        r, lowerCurve, mid, upperCurve, u0, u1, endPiece);
                    if (cell.Outline.Count < 3)
                        continue;
                    keyed.Add((r, component, u0, cell));
                }
            }
        }
        // The plan guarantee is ENFORCED here, on the sorted list, so
        // the cells that leave are the cells that were measured. Every
        // diagnostics number below is then taken off the SURVIVORS, so
        // the text describes what the component actually hands over
        // rather than what it built before the filter looked at it.
        List<SkinCell> cells = KeepValidPlans(
            keyed
                .OrderBy(item => item.Course)
                .ThenBy(item => item.Order)
                .ThenBy(item => item.U0)
                .Select(item => item.Cell)
                .ToList(),
            out int degenerateDropped,
            out int overlapDropped);
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
            degenerateDropped,
            overlapDropped);
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

    private static (double Min, double Max) HeightRange(SkinNet net)
    {
        double min = double.PositiveInfinity;
        double max = double.NegativeInfinity;
        foreach (double[] vertex in net.Vertices)
        {
            min = Math.Min(min, vertex[2]);
            max = Math.Max(max, vertex[2]);
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
    /// True when one of the recorded transition intervals lies WITHIN
    /// the height span [low, high] a candidate cell reaches across, so
    /// the cell would have to bond over a level whose component count
    /// changes. Both ends of a lattice cell's span are themselves traced
    /// heights, so the comparison is exact but for the usual tolerance.
    /// </summary>
    private static bool SpansTransition(
        IReadOnlyList<(double Low, double High)> transitions,
        double low,
        double high)
    {
        foreach ((double at, double to) in transitions)
        {
            if (at >= low - 1.0e-12 && to <= high + 1.0e-12)
                return true;
        }
        return false;
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
        IReadOnlyList<(double Low, double High)> transitions)
    {
        if (skipped == 0 || transitions.Count == 0)
            return null;
        static string F(double value) =>
            value.ToString("F3", CultureInfo.InvariantCulture);
        string where = string.Join(
            " and ",
            transitions.Select(item =>
                $"between z={F(item.Low)} and z={F(item.High)}"));
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
        string? transitions = null)
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
        return string.Join("\n", lines);
    }

    private static SkinPatternResult Empty(string name) =>
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
            0,
            0);

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
                chart.Heights.Add(curve.Height);
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
        (double zMin, double zMax) = HeightRange(net);
        if (net.Faces.Count == 0 || !(zMax - zMin > 1.0e-9))
            return Empty("hexagonal");

        int bands = BandCount(zMin, zMax, courseHeight);
        double epsilon = Math.Max((zMax - zMin) * 1.0e-6, 1.0e-9);
        double zBottom = zMin + epsilon;
        double zTop = zMax - epsilon;
        double clipTolerance = 10.0 * epsilon;

        // Every lattice height is zMin + CH * row for an integer row:
        // the base centre sits at zRef = zMin + CH (so the seam column's
        // bottom row lands its lower edge on the base rim), and both
        // lattice translations move by whole multiples of CH. Rows -1 to
        // topRow + 1 cover every vertex a candidate cell can have; rows
        // beyond the surface clamp to the epsilon-pulled extremes and
        // collapse to shared traces.
        int topRow = (int)Math.Ceiling(
            (zMax - zMin) / courseHeight - 1.0e-9);
        double ClampedRowHeight(int row) =>
            Math.Min(Math.Max(zMin + courseHeight * row, zBottom), zTop);
        List<double> heights = Enumerable
            .Range(-1, topRow + 3)
            .Select(ClampedRowHeight)
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
                    if (transitions.Count > 0 &&
                        SpansTransition(
                            transitions,
                            ClampedRowHeight(centreRow - 1),
                            ClampedRowHeight(centreRow + 1)))
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
                        double zRaw =
                            zMin + courseHeight * setout[v].Row;
                        double z = Math.Min(
                            Math.Max(zRaw, chartBottom), chartTop);
                        SkinLevelCurve curve = CurveAt(chart, z);
                        double half = curve.Length / 2.0;
                        double u = Math.Min(
                            Math.Max(setout[v].U, -half), half);
                        if (Math.Abs(z - zRaw) > clipTolerance ||
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
                                zMin + courseHeight * centreRow,
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
                        zMin + courseHeight * (centreRow + 1)
                            > chartBottom + 1.0e-9 &&
                        zMin + courseHeight * (centreRow - 1)
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

                    double zcClamped = Math.Min(
                        Math.Max(zMin + courseHeight * centreRow, zMin),
                        zMax);
                    int course = Math.Min(
                        bands - 1,
                        Math.Max(0, (int)Math.Floor(
                            (zcClamped - zMin) / courseHeight
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
                    "hexagonal", skippedRows.Count, transitions)),
            skippedRows.Count,
            degenerateDropped,
            overlapDropped);
    }
}
