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
/// </summary>
internal sealed record SkinNet(
    IReadOnlyList<double[]> Vertices,
    IReadOnlyList<int[]> Faces);

/// <summary>
/// One traced level-curve component: the polyline of edge crossings at
/// Height, OPEN (a strip ending on the surface boundary, the barrel case)
/// or CLOSED (a loop, the dome case), with cumulative arc lengths and,
/// once seams are assigned, the seam every setout coordinate is measured
/// from. Cumulative[i] is the arc length at Points[i] from Points[0]; a
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
/// diagnostics text the component's D output carries, and the count of
/// bands REFUSED because the level curves changed component count across
/// them, which the component turns into a runtime Warning because a hole
/// in the skin has to be said out loud.</summary>
internal sealed record SkinPatternResult(
    IReadOnlyList<SkinCell> Cells,
    int CourseCount,
    string Diagnostics,
    int TransitionBands);

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

    // ---- level-curve tracing and seams (spec section 4) -----------------

    /// <summary>
    /// Trace the net at every height, ascending, NORMALISE every traced
    /// curve's direction, and assign every curve its seam, in one pass:
    /// a direction has to be settled before the seam that is measured
    /// along it, and a closed loop's seam is propagated from the level
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
            // number of times). Pair consecutive crossings; on a saddle
            // face the pairing is the deterministic marching choice.
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
    /// Spec section 4's "matched to the component below it by plan
    /// overlap": the candidate whose plan bounding box overlaps this
    /// curve's with the greatest area. Parallel open strips (the barrel)
    /// have zero-thickness boxes that never overlap, so where nothing
    /// does, the nearest plan centroid stands in. Ties keep the first
    /// candidate, which is deterministic because Trace's component order
    /// is.
    /// </summary>
    private static int MatchBelow(
        SkinLevelCurve curve,
        IReadOnlyList<SkinLevelCurve> candidates)
    {
        if (candidates.Count == 0)
            return -1;
        (double MinX, double MinY, double MaxX, double MaxY) box =
            PlanBox(curve);
        int best = -1;
        double bestArea = 0.0;
        for (int i = 0; i < candidates.Count; i++)
        {
            (double MinX, double MinY, double MaxX, double MaxY) other =
                PlanBox(candidates[i]);
            double overlapX =
                Math.Min(box.MaxX, other.MaxX) -
                Math.Max(box.MinX, other.MinX);
            double overlapY =
                Math.Min(box.MaxY, other.MaxY) -
                Math.Max(box.MinY, other.MinY);
            double area =
                Math.Max(overlapX, 0.0) * Math.Max(overlapY, 0.0);
            if (area > bestArea + 1.0e-12)
            {
                bestArea = area;
                best = i;
            }
        }
        if (best >= 0)
            return best;
        (double X, double Y) centroid = PlanCentroid(curve);
        double bestDistance = double.PositiveInfinity;
        for (int i = 0; i < candidates.Count; i++)
        {
            (double X, double Y) other = PlanCentroid(candidates[i]);
            double dx = centroid.X - other.X;
            double dy = centroid.Y - other.Y;
            double distance = dx * dx + dy * dy;
            if (distance < bestDistance - 1.0e-12)
            {
                bestDistance = distance;
                best = i;
            }
        }
        return best;
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

    // ---- small shared arithmetic ----------------------------------------

    private static (double MinX, double MinY, double MaxX, double MaxY)
        PlanBox(SkinLevelCurve curve)
    {
        double minX = double.PositiveInfinity;
        double minY = double.PositiveInfinity;
        double maxX = double.NegativeInfinity;
        double maxY = double.NegativeInfinity;
        foreach (double[] point in curve.Points)
        {
            minX = Math.Min(minX, point[0]);
            minY = Math.Min(minY, point[1]);
            maxX = Math.Max(maxX, point[0]);
            maxY = Math.Max(maxY, point[1]);
        }
        return (minX, minY, maxX, maxY);
    }

    private static (double X, double Y) PlanCentroid(SkinLevelCurve curve)
    {
        double x = 0.0;
        double y = 0.0;
        foreach (double[] point in curve.Points)
        {
            x += point[0];
            y += point[1];
        }
        return (x / curve.Points.Count, y / curve.Points.Count);
    }

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
        var pieceLengths = new List<double>();
        var transitions = new List<(double Low, double High)>();
        int transitionBands = 0;
        int clipped = 0;
        for (int r = 0; r < bands; r++)
        {
            IReadOnlyList<SkinLevelCurve> mids = traced[2 * r + 1];
            IReadOnlyList<SkinLevelCurve> lowers = traced[2 * r];
            IReadOnlyList<SkinLevelCurve> uppers = traced[2 * r + 2];
            // A TOPOLOGY TRANSITION: the level curve count changed across
            // the three levels this band spans, so the components no
            // longer correspond one for one and MatchBelow would pair
            // curves that are not the same piece of surface, laying
            // overlapping and self-crossing cells. Refuse the band whole
            // (spec is silent on transitions; the ruling is that a stated
            // hole beats a poisoned sidecar, because Bench Studio rejects
            // a whole tessellation for one self-crossing cell). Splitting
            // the band at its transition height is the right long answer
            // and belongs to a later wave.
            if (lowers.Count != mids.Count || mids.Count != uppers.Count)
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
                    if (cell.Clipped)
                        clipped++;
                    pieceLengths.Add(u1 - u0);
                    keyed.Add((r, component, u0, cell));
                }
            }
        }
        List<SkinCell> cells = keyed
            .OrderBy(item => item.Course)
            .ThenBy(item => item.Order)
            .ThenBy(item => item.U0)
            .Select(item => item.Cell)
            .ToList();
        return new SkinPatternResult(
            cells,
            bands,
            PatternDiagnostics(
                "courses", cells.Count, bands, pieceLengths,
                "half a pitch on odd courses", clipped,
                TransitionLine("courses", transitionBands, transitions)),
            transitionBands);
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
        return
            $"Transition bands skipped: {skipped} (level curve splits " +
            $"{where}; {name} cannot bond across it)";
    }

    /// <summary>The D output's text for a native pattern: the pattern
    /// name, cell and course counts, mean/min/max piece length, the
    /// stagger, the count of boundary-clipped cells and, where the level
    /// curves changed component count, the refused transition bands.
    /// The key of every line is capitalised, so the transition line
    /// reads beside the rest rather than under it.</summary>
    private static string PatternDiagnostics(
        string name,
        int cellCount,
        int courseCount,
        IReadOnlyList<double> pieceLengths,
        string stagger,
        int clipped,
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
                0),
            0);

    // ---- pattern 1: hexagonal (spec section 6) --------------------------

    /// <summary>One chart: the traced components at successive heights,
    /// chained bottom-up by plan-overlap matching, so each chain is one
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
    /// extent intersects the chart's interior, so a shell shallower than
    /// CH still grows one clipped course instead of nothing. Each vertex
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
        // of consecutive chart levels whose component count differs is a
        // height a hexagon cannot bond across, because the vertices of
        // one cell would map through curves that are not the same piece
        // of surface. Every lattice row spanning such an interval is
        // refused whole, the same ruling the courses engine follows.
        var transitions = new List<(double Low, double High)>();
        for (int level = 0; level + 1 < heights.Count; level++)
        {
            if (traced[level].Count != traced[level + 1].Count)
            {
                AddTransition(
                    transitions, heights[level], heights[level + 1]);
            }
        }
        var skippedRows = new HashSet<int>();

        var keyed =
            new List<(int Course, int Chart, double U0, SkinCell Cell)>();
        var pieceLengths = new List<double>();
        int clippedCount = 0;

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
                    double widest = 0.0;
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
                        widest = Math.Max(widest, half);
                        if (Math.Abs(z - zRaw) > clipTolerance ||
                            Math.Abs(u - setout[v].U) > clipTolerance)
                        {
                            clipped = true;
                        }
                        mapped[v] = (u, curve);
                    }

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
                    // centred on the column; and the chart's interior is
                    // the open box between chartBottom and chartTop by
                    // the widest half-length of the level curves this
                    // candidate maps through. The clamp above has
                    // already pulled every vertex onto the chart and
                    // Dedupe drops what collapsed, so an intersecting
                    // candidate arrives as its CLIPPED outline, which is
                    // the pattern's standing rule for the rim. A
                    // candidate wholly outside still fails, so the
                    // ruling that off-surface lattice cells are not
                    // cells stands.
                    //
                    // A closed loop's u domain is still cut at the
                    // meridian opposite the seam rather than wrapped, so
                    // the honeycomb never folds into itself and the
                    // disjoint-plan guarantee holds.
                    bool overlaps =
                        zMin + courseHeight * (centreRow + 1)
                            > chartBottom + 1.0e-9 &&
                        zMin + courseHeight * (centreRow - 1)
                            < chartTop - 1.0e-9 &&
                        uc + size / 2.0 > -widest + 1.0e-9 &&
                        uc - size / 2.0 < widest - 1.0e-9;
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
                    if (clipped)
                        clippedCount++;
                    pieceLengths.Add(mapped[2].U - mapped[5].U);
                    keyed.Add((course, chartAt, mapped[5].U, cell));
                }
            }
        }
        List<SkinCell> cells = keyed
            .OrderBy(item => item.Course)
            .ThenBy(item => item.Chart)
            .ThenBy(item => item.U0)
            .Select(item => item.Cell)
            .ToList();
        return new SkinPatternResult(
            cells,
            bands,
            PatternDiagnostics(
                "hexagonal", cells.Count, bands, pieceLengths,
                "0.75 x S per course row", clippedCount,
                TransitionLine(
                    "hexagonal", skippedRows.Count, transitions)),
            skippedRows.Count);
    }
}
