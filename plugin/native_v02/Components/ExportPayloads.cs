#nullable enable

using System;
using System.Collections.Generic;
using System.IO;
using System.Text;
using System.Text.Json;
using Ananke.COMPAS.Native.Contracts;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// What a Result can be exported as. THREE documents, not five kinds
/// (design of 2026-09-04 section 1, Param's ruling settled twice over).
///
/// FORM is every Result: the portable contract exactly as it is written
/// today, plus the study name and the thrust mesh the studio's FEA reads.
/// SKIN joins it when somebody wired cutting cells, and FORMWORK when the
/// Result's Mould block carries columns; formwork is self-contained, the
/// machine and its motion in one document.
///
/// Export writes what the Result can be rather than asking which one.
/// </summary>
internal static class ExportPlan
{
    /// <summary>The three kind suffixes, named once and read everywhere.</summary>
    public const string FormKind = "form";

    public const string SkinKind = "skin";

    public const string FormworkKind = "formwork";

    public static string[] Kinds(bool hasCells, bool hasColumns)
    {
        var kinds = new List<string> { FormKind };
        if (hasCells)
            kinds.Add(SkinKind);
        if (hasColumns)
            kinds.Add(FormworkKind);
        return kinds.ToArray();
    }

    // Refused on top of the invalid file name characters the platform
    // knows about, so the rule reads the same on any of them: these three
    // are what turn a name into a path or a second route segment.
    private static readonly char[] SeparatorCharacters = { '/', '\\', ':' };

    /// <summary>
    /// Whether a study name is ONE segment, which is what both
    /// destinations need it to be. The files are
    /// <c>&lt;Name&gt;-&lt;kind&gt;.json</c> inside the folder the author
    /// chose, so a name carrying a separator or a <c>..</c> writes the set
    /// somewhere else entirely, quietly and successfully; the studio's
    /// route takes the name as one path segment too. Blank is refused
    /// here, and the caller has already turned a blank Name into the
    /// default before asking.
    ///
    /// DOT-DOT IS REFUSED WHEREVER IT STANDS, not only when it is the whole
    /// name (design of 2026-09-04 section 4 item 1). The studio's deployed
    /// boundary already refuses "a..b" with a live 400, demonstrated on the
    /// channel on 2026-09-03, so a name this side accepted was a set the
    /// far side would not take; and a path segment carrying a dot-dot is
    /// the shape every traversal defence is written against, whether or not
    /// this particular platform would resolve it.
    /// </summary>
    public static bool NameIsOneSegment(string name)
    {
        if (name is null)
            return false;
        string trimmed = name.Trim();
        if (trimmed.Length == 0)
            return false;
        if (trimmed == ".")
            return false;
        if (trimmed.Contains("..", StringComparison.Ordinal))
            return false;
        if (trimmed.IndexOfAny(SeparatorCharacters) >= 0)
            return false;
        return trimmed.IndexOfAny(Path.GetInvalidFileNameChars()) < 0;
    }
}

/// <summary>
/// The columns as a mesh the studio renders today: one closed prism per
/// member, six side quads and two triangle-fanned caps, at the radius
/// asked. Pure arithmetic: the harness builds it without Rhino.
///
/// This no longer writes a document of its own. The prisms are the drawn
/// half of the formwork document's columns block (design of 2026-09-04
/// section 1), and the members, the nodes and the tree bookkeeping travel
/// beside them there, so the studio can draw its own tubes at the declared
/// radius from lines and indices rather than from a baked mesh.
/// </summary>
internal static class ColumnsMesh
{
    /// <summary>
    /// A prism needs three sides to be a solid and a radius that is not
    /// zero to have a surface, so both are floored here. The floor is the
    /// last line of defence: Export refuses a non-positive Column Radius
    /// and says so long before this.
    /// </summary>
    public const int MinimumSides = 3;

    public const double MinimumRadius = 1.0e-9;

    /// <summary>
    /// A member this short has no direction to build a prism about. It is
    /// skipped in BOTH lists, the prisms and the members, so a consumer
    /// pairing the nth of one with the nth of the other never finds them
    /// out of step.
    /// </summary>
    public const double MinimumLength = 1.0e-9;

    public static bool IsTooShort(Point3d from, Point3d to) =>
        (to - from).Length <= MinimumLength;

    public static (double[][] Vertices, int[][] Faces) Build(
        IReadOnlyList<(Point3d From, Point3d To, double Force)> members,
        double radius,
        int sides = 6)
    {
        sides = Math.Max(sides, MinimumSides);
        radius = Math.Max(radius, MinimumRadius);
        var vertices = new List<double[]>();
        var faces = new List<int[]>();
        foreach ((Point3d from, Point3d to, double _) in members)
        {
            if (IsTooShort(from, to))
                continue;
            Vector3d axis = to - from;
            double length = axis.Length;
            axis = axis / length;
            Vector3d helper = Math.Abs(axis.Z) < 0.9 ? Vector3d.ZAxis : Vector3d.XAxis;
            Vector3d u = Cross(axis, helper);
            u = u / u.Length;
            Vector3d v = Cross(axis, u);
            int baseIndex = vertices.Count;
            for (int end = 0; end < 2; end++)
            {
                Point3d centre = end == 0 ? from : to;
                for (int s = 0; s < sides; s++)
                {
                    double a = 2.0 * Math.PI * s / sides;
                    Point3d p = centre + (u * (radius * Math.Cos(a))) + (v * (radius * Math.Sin(a)));
                    vertices.Add(new[] { p.X, p.Y, p.Z });
                }
            }
            for (int s = 0; s < sides; s++)
            {
                int n = (s + 1) % sides;
                faces.Add(new[] { baseIndex + s, baseIndex + n, baseIndex + sides + n, baseIndex + sides + s });
            }
            for (int s = 1; s + 1 < sides; s++)
            {
                faces.Add(new[] { baseIndex, baseIndex + s + 1, baseIndex + s });
                faces.Add(new[] { baseIndex + sides, baseIndex + sides + s, baseIndex + sides + s + 1 });
            }
        }
        return (vertices.ToArray(), faces.ToArray());
    }

    /// <summary>
    /// Which of the members handed in actually got a prism, in prism order.
    ///
    /// A member too short to have a direction is skipped by
    /// <see cref="Build"/>, so the nth prism is NOT in general the nth
    /// member. The formwork document's members list is the Mould block's
    /// own, unrenumbered, because its trees index into it by position and
    /// renumbering there would silently rewrite the branch structure. This
    /// is therefore how the two stay paired: the nth prism belongs to the
    /// member this names. Built off the same <see cref="IsTooShort"/>
    /// predicate <see cref="Build"/> uses, so the two cannot drift.
    /// </summary>
    public static int[] Drawn(
        IReadOnlyList<(Point3d From, Point3d To, double Force)> members)
    {
        var drawn = new List<int>(members.Count);
        for (int i = 0; i < members.Count; i++)
        {
            if (!IsTooShort(members[i].From, members[i].To))
                drawn.Add(i);
        }
        return drawn.ToArray();
    }

    private static Vector3d Cross(Vector3d a, Vector3d b) => new(
        (a.Y * b.Z) - (a.Z * b.Y),
        (a.Z * b.X) - (a.X * b.Z),
        (a.X * b.Y) - (a.Y * b.X));
}

/// <summary>
/// The formwork build as a sequence of frames: the "frames" array of the
/// <c>bench.formwork/1</c> document, which is the thing the studio replays.
///
/// It no longer writes a document of its own. The frames and the machine
/// that makes them are one document now (design of 2026-09-04 section 1),
/// so this builds the array and <see cref="FormworkDocument"/> puts the
/// envelope round it; what used to be the sidecar's own head keys,
/// vertexCount and columnNodeCount, are the document's head keys, which is
/// where the studio's validator reads them before any frame.
///
/// The writer INVENTS NO MOTION. It calls <see cref="MouldAnimation.Prepare"/>
/// once and <see cref="MouldAnimation.At"/> at every sample, which are the two
/// calls Animate makes on every slider tick, so a frame in the file is the
/// frame Grasshopper draws at that time rather than a second account of it.
///
/// Three properties the studio's reader enforces at read time, and which are
/// therefore load-bearing here rather than decoration:
///
///   <c>frames[k].vertices[i]</c> is <c>equilibrium.vertices[i]</c>'s node, in
///   that order, in every frame. There is no separate id list; the index IS
///   the join key to the rest of the study.
///
///   The time-100 frame equals the contract's own equilibrium vertices. At
///   Time 100 the sag and the lift are both exactly one, so every blend
///   collapses back onto the solved geometry; the reader checks that equality
///   to 1e-9 and treats a failure as a set mixed from two solves.
///
///   <c>columnNodes</c> is the mould columns block's OWN node list, not indices
///   into the net, and its count and order are constant across frames, so the
///   members of the static columns block index into it frame by frame.
/// </summary>
internal static class MouldFrames
{
    /// <summary>
    /// One Result's whole sweep, and the two counts that describe it, ready
    /// for the formwork document's envelope. The last frame's own vertices
    /// and column nodes come back beside the array because they are what
    /// the two pairing invariants are checked against, and reading them
    /// back out of the serialised dictionaries would be reading the answer
    /// off the page rather than off the engine.
    /// </summary>
    public sealed record Sequence(
        IReadOnlyList<Dictionary<string, object?>> Frames,
        int VertexCount,
        int ColumnNodeCount,
        IReadOnlyList<Point3d> FinalVertices,
        IReadOnlyList<Point3d> FinalColumnNodes);

    /// <summary>Time units between samples across the 0 to 100 timeline.</summary>
    public const double Step = 2.0;

    /// <summary>
    /// The phase boundaries, which are always sampled exactly. At the step
    /// above the base sweep already lands on every one of them; they are
    /// inserted anyway so that a future step cannot quietly drop the frames
    /// the reader validates for. Nothing at <see cref="Step"/> can tell
    /// whether the insertion happens, which is why
    /// <see cref="Times(double)"/> exists and is driven at a step that
    /// misses them.
    /// </summary>
    public static readonly double[] Boundaries = { 0.0, 30.0, 60.0, 90.0, 100.0 };

    /// <summary>
    /// Two samples closer than this are the same instant. Only ever reached by
    /// a boundary that the base sweep already produced.
    /// </summary>
    private const double SameTime = 1.0e-9;

    /// <summary>
    /// The sampled times the file is written at: the base sweep at
    /// <see cref="Step"/>, the boundaries, sorted and with duplicates
    /// removed, so the array is strictly ascending. The reader is told
    /// never to assume the count or the step, but it does require 0, 30,
    /// 60, 90 and 100 to be present.
    /// </summary>
    public static double[] Times() => Times(Step);

    /// <summary>
    /// The same sweep at an ARBITRARY step, which is the only way the
    /// boundary insertion can be seen at all.
    ///
    /// At <see cref="Step"/> the base sweep already lands on every
    /// boundary, so the insertion below adds nothing and the deduplication
    /// removes exactly what it added: measured 2026-09-03, deleting 60.0
    /// from <see cref="Boundaries"/> leaves the whole harness green. The
    /// safety net was unreachable, not sound. It is reachable here: a step
    /// that MISSES a boundary, 7 for instance, must still produce that
    /// boundary, and the boundary it does land on, 0, must appear once and
    /// not twice.
    ///
    /// A step at or below zero would never terminate, so it is refused
    /// rather than hung.
    /// </summary>
    public static double[] Times(double step)
    {
        if (!(step > 0.0))
        {
            throw new ArgumentOutOfRangeException(
                nameof(step),
                step,
                "The frame step is a positive number of time units.");
        }
        var times = new List<double>();
        for (int k = 0; ; k++)
        {
            double t = k * step;
            if (t > 100.0 + SameTime)
                break;
            times.Add(Math.Min(t, 100.0));
        }
        times.AddRange(Boundaries);
        times.Sort();
        var kept = new List<double>(times.Count);
        foreach (double t in times)
        {
            if (kept.Count > 0 && t - kept[kept.Count - 1] <= SameTime)
                continue;
            kept.Add(t);
        }
        return kept.ToArray();
    }

    /// <summary>
    /// The whole sequence for one Result, at Animate's own default Pre-Sag.
    /// Export has no Pre-Sag port of its own and the file has to be
    /// deterministic for a given Result, so the sweep is written at the value
    /// an author sees when they drop an Animate on the canvas and touch only
    /// the Time slider.
    ///
    /// THE COORDINATES ARE THE CONTRACT'S OWN, unscaled, which is the
    /// whole-branch review's finding 16 and survives the move into the
    /// formwork document unchanged. SpineComponents builds a Result's
    /// pattern vertices straight from the Rhino geometry with no scaling
    /// anywhere, so a Result's coordinates are in whatever unit the
    /// document was in when it was solved; the factor is DECLARED by the
    /// document round this array and never applied here. Converting would
    /// break the reader's own integrity check, that the time-100 frame
    /// EQUALS the contract's equilibrium vertices: converting one side of
    /// an equality and not the other is not a fix.
    /// </summary>
    public static Sequence Build(ResultDto result)
    {
        ArgumentNullException.ThrowIfNull(result);
        MouldAnimation.Setup setup = MouldAnimation.Prepare(result);
        double[] times = Times();
        var frames = new List<Dictionary<string, object?>>(times.Length);
        var nodeCounts = new List<int>(times.Length);
        Point3d[] finalVertices = Array.Empty<Point3d>();
        Point3d[] finalNodes = Array.Empty<Point3d>();
        foreach (double time in times)
        {
            MouldAnimation.Frame frame = MouldAnimation.At(
                setup, time, MouldAnimation.DefaultPreSagPercent);
            Point3d[] nodes = frame.ColumnNodes ?? Array.Empty<Point3d>();
            nodeCounts.Add(nodes.Length);
            finalVertices = frame.Vertices;
            finalNodes = nodes;
            frames.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["time"] = frame.Time,
                ["phase"] = frame.Phase,
                ["vertices"] = Triples(frame.Vertices),
                ["columnNodes"] = Triples(nodes),
            });
        }
        // columnNodeCount is a property of the SET, which is what the
        // reader is told: the count and the order of the column nodes are
        // constant across frames, and the static columns block indexes
        // into them frame by frame. It is taken ONCE, from the first
        // frame, with the invariant asserted here beside the declaration
        // rather than assumed.
        //
        // CORRECTION, whole-branch review finding 8. An earlier version of
        // this comment presented reading frame 0 rather than the last
        // frame as a behavioural FIX. It is not one, and cannot be: the
        // loop below throws before the payload is built on any set whose
        // frames disagree, so on every input that reaches the declaration
        // the first and the last frame carry the same count by
        // construction, and reading either gives the same file. Measured:
        // putting the read back on the last frame leaves the whole suite
        // green, and inverting the guard below to fire on AGREEMENT
        // produces its message immediately on the real contract, which
        // shows the message path is wired and the shipped predicate's true
        // branch is simply never taken by any fixture. What the pair
        // actually buys is that the two readings are provably equal
        // instead of accidentally so. The INVARIANT is the fix; the choice
        // of frame is its corollary.
        int columnNodeCount = nodeCounts.Count == 0 ? 0 : nodeCounts[0];
        for (int k = 1; k < nodeCounts.Count; k++)
        {
            if (nodeCounts[k] != columnNodeCount)
            {
                throw new InvalidOperationException(
                    "The column-node count is constant across the frames of " +
                    $"one set, and the reader depends on it: frame {k} at " +
                    $"time {times[k]} carries {nodeCounts[k]} nodes against " +
                    $"the {columnNodeCount} of frame 0. No sidecar is " +
                    "written from frames that disagree.");
            }
        }
        return new Sequence(
            frames, setup.Count, columnNodeCount, finalVertices, finalNodes);
    }

    internal static double[][] Triples(IReadOnlyList<Point3d> points)
    {
        var triples = new double[points.Count][];
        for (int i = 0; i < points.Count; i++)
            triples[i] = new[] { points[i].X, points[i].Y, points[i].Z };
        return triples;
    }
}

/// <summary>
/// FORM, <c>&lt;study&gt;-form.json</c>: the portable contract EXACTLY as
/// <c>ContractJson.Serialize</c> writes it today, mould block included, with
/// two keys added round it (design of 2026-09-04 section 1).
///
/// "study" leads, because the studio keys Live's follow-the-push on a field
/// we stamp rather than on a file name it parses (their R-010(h)(3), their
/// R-012(i)). "thrustMesh" trails, and carries the same COMPAS json string
/// the compas document carried at its own "thrustMesh" key: it is the one
/// thing their FEA reads, their measurement, and it lands at
/// <c>form["thrustMesh"]</c> exactly as the REPLY to R-010(d) promised.
///
/// THE CONTRACT'S OWN BYTES ARE NOT REWRITTEN. They are spliced in whole,
/// between the leading key and the trailing one, rather than round-tripped
/// through a JsonNode: every number's raw text, every escape and every key
/// order in the middle of this document is therefore the contract's, byte
/// for byte, and a reader that strips the two added keys is holding what
/// <c>ContractJson.Serialize</c> wrote. That is checkable, and it is
/// checked.
/// </summary>
internal static class FormDocument
{
    /// <summary>
    /// The trailing member, as the exact bytes it is written and found by.
    ///
    /// It CANNOT occur anywhere else in the document. The thrust mesh
    /// travels as a JSON string, so every quote inside it is escaped as
    /// <c>\"</c> and the unescaped <c>,"</c> that opens this sequence
    /// cannot appear within it; and it is written last, so nothing of the
    /// contract's follows it.
    /// </summary>
    public const string ThrustMeshMember = ",\"thrustMesh\":";

    public static string Json(ResultDto result, string study, string? thrustMesh)
    {
        ArgumentNullException.ThrowIfNull(result);
        string contract = ContractJson.Serialize(result);
        // The contract's own body, between its braces. Serialize always
        // writes an object, and the empty one is handled rather than
        // trusted not to happen: an object with no keys would otherwise
        // leave a comma with nothing after it.
        string body = contract.Length >= 2
            ? contract[1..^1]
            : string.Empty;
        var builder = new StringBuilder(contract.Length + 64);
        builder.Append("{\"study\":");
        builder.Append(JsonSerializer.Serialize(study, ContractJson.Options));
        if (body.Length > 0)
            builder.Append(',').Append(body);
        builder.Append(ThrustMeshMember);
        builder.Append(thrustMesh is null
            ? "null"
            : JsonSerializer.Serialize(thrustMesh, ContractJson.Options));
        builder.Append('}');
        return builder.ToString();
    }

    /// <summary>
    /// The form document with its thrust mesh reduced to a PRESENCE TOKEN,
    /// which is what a change key reads.
    ///
    /// The mesh's BYTES are left out. It is the worker's
    /// <c>compas.data.json_dumps</c> of freshly built objects, and
    /// json_dumps stamps a fresh uuid4 into every serialisation
    /// (compas/data/data.py), so two solves of an unchanged Result produce
    /// two different strings. A key that read those bytes could never
    /// repeat: every outcome expires the component, the re-solve would
    /// enqueue a set that looked new, and the sending would go round for as
    /// long as Live was left on. That is the standing SetKey lesson,
    /// inherited from the compas kind this document absorbed, and the
    /// contract half IS read, so a changed Result still keys differently.
    ///
    /// The mesh's PRESENCE is counted, and that half is not cosmetic. A
    /// worker that will not start writes <c>"thrustMesh": null</c>, and the
    /// same Result recovered on the next build writes the real string. If
    /// the member were deleted outright the two would key IDENTICALLY, the
    /// uploader would report "unchanged since: ..." and the recovered set
    /// would never be sent: the studio would keep a form document with no
    /// thrust mesh, and no staged analysis, until the Result itself changed
    /// or Live was toggled off and on, with nothing on the canvas saying so.
    /// That was the compas kind's rule too, whose bytes were skipped while
    /// its presence counted, and it moved here with the string.
    /// </summary>
    public static string KeyMaterial(string json)
    {
        if (json is null)
            return string.Empty;
        int at = json.LastIndexOf(ThrustMeshMember, StringComparison.Ordinal);
        if (at < 0)
            return json;
        ReadOnlySpan<char> value = json.AsSpan(at + ThrustMeshMember.Length);
        return json[..at]
            + ThrustMeshMember
            + (value.StartsWith("null".AsSpan(), StringComparison.Ordinal)
                ? "null}"
                : "\"present\"}");
    }
}

/// <summary>
/// FORMWORK, <c>&lt;study&gt;-formwork.json</c>, schema
/// <c>bench.formwork/1</c>: the machine and its motion in ONE
/// self-contained document (design of 2026-09-04 section 1; the studio's
/// R-011(e) asked for it and the REPLY's point 2 settled it).
///
/// Self-contained means the studio never has to hold two of our files at
/// once to validate this one. The study name, the unit declaration, the
/// force unit and the radius are its own; the columns block is its own,
/// nodes and members and the tree bookkeeping together; vertexCount and
/// columnNodeCount are at DOCUMENT level, because their validator reads
/// them before it reads a frame; and the frames array is beneath them.
///
/// THE TWO PAIRING INVARIANTS ARE TRUE BY CONSTRUCTION HERE, and asserted
/// rather than assumed (their R-011(f), agreed in the REPLY):
///
///   The time-100 columnNodes equal this document's OWN columns block. They
///   are not merely compared: the block's nodes ARE the time-100 frame's
///   column nodes, and the drawn prisms are built from those, so the still
///   machine and the last instant of the moving one cannot disagree. Point
///   frames.pairing_error at the columns block in this document, which is
///   what their R-012(c) has already done.
///
///   The time-100 vertices equal the form document's equilibrium vertices
///   to 1e-9. At Time 100 the sag and the lift are both exactly one, so
///   every blend collapses back onto the solved geometry; the equality is
///   checked here against the contract the form document is written from,
///   and a set that fails it is not written at all.
/// </summary>
internal static class FormworkDocument
{
    public const string Schema = "bench.formwork/1";

    /// <summary>
    /// The columns block's own schema, kept inside the block. The studio
    /// reads a bench.columns/1 shape there and has since before this
    /// document existed; the envelope keys that used to sit beside it
    /// (units, lengthUnitToMetres, forceUnit, radius) are the document's
    /// now, said once for the whole machine rather than twice.
    /// </summary>
    public const string ColumnsSchema = "bench.columns/1";

    /// <summary>
    /// How far the time-100 frame may stand from the solved geometry before
    /// the set is refused. The studio's own reader checks the same equality
    /// at the same tolerance and treats a failure as a set mixed from two
    /// solves; refusing it here means such a set never reaches them.
    /// </summary>
    public const double PairingTolerance = 1.0e-9;

    public static string Json(
        ResultDto result,
        string study,
        double unitFactor,
        double radius,
        string forceUnit)
    {
        ArgumentNullException.ThrowIfNull(result);
        if (!double.IsFinite(unitFactor) || unitFactor <= 0.0)
        {
            throw new ArgumentOutOfRangeException(
                nameof(unitFactor),
                unitFactor,
                "The length unit factor is how many metres one document " +
                "unit is, so it is finite and positive.");
        }
        MouldColumnsDto block = result.Mould?.Columns
            ?? throw new InvalidOperationException(
                "A formwork document is the columns and their motion, and " +
                "this Result carries no columns block.");

        MouldFrames.Sequence sweep = MouldFrames.Build(result);

        // THE COLUMNS BLOCK'S NODES ARE THE TIME-100 FRAME'S. That is what
        // makes the first pairing invariant true by construction rather
        // than by luck: the machine at rest is the last instant of the
        // machine moving, in the same encoding, so the studio's comparison
        // is over identical numbers. The count still has to line up with
        // the block the members index into, and where it does not there is
        // nothing coherent to write.
        IReadOnlyList<Point3d> nodes = sweep.FinalColumnNodes;
        if (nodes.Count != block.Nodes.Count)
        {
            throw new InvalidOperationException(
                "The animation's column nodes and the Mould block's own " +
                $"disagree in count, {nodes.Count} against " +
                $"{block.Nodes.Count}, so the members could not index the " +
                "nodes they are written beside. No formwork document is " +
                "written from a machine that does not match its motion.");
        }

        // THE SECOND PAIRING INVARIANT, checked against the contract the
        // form document is written from rather than against a copy of it.
        IReadOnlyList<Point3Dto> solved =
            result.Equilibrium?.Vertices ?? Array.Empty<Point3Dto>();
        IReadOnlyList<Point3d> settled = sweep.FinalVertices;
        if (settled.Count != solved.Count)
        {
            throw new InvalidOperationException(
                "The time-100 frame carries one point per net vertex, and " +
                $"this one carries {settled.Count} against the " +
                $"{solved.Count} of the form document's equilibrium.");
        }
        for (int i = 0; i < solved.Count; i++)
        {
            if (Math.Abs(settled[i].X - solved[i].X) <= PairingTolerance &&
                Math.Abs(settled[i].Y - solved[i].Y) <= PairingTolerance &&
                Math.Abs(settled[i].Z - solved[i].Z) <= PairingTolerance)
            {
                continue;
            }
            throw new InvalidOperationException(
                "The time-100 frame must EQUAL the form document's " +
                $"equilibrium vertices to {PairingTolerance}, which is how " +
                "the studio tells one solve's animation from another's: " +
                $"vertex {i} settles at ({settled[i].X}, {settled[i].Y}, " +
                $"{settled[i].Z}) against ({solved[i].X}, {solved[i].Y}, " +
                $"{solved[i].Z}).");
        }

        // Clamped ONCE, and the clamped value is both what the prisms are
        // built at and what the document declares: a radius floored inside
        // Build alone put a prism at one size on the page and another size
        // in the "radius" key beside it.
        radius = Math.Max(radius, ColumnsMesh.MinimumRadius);
        IReadOnlyList<(Point3d From, Point3d To, double Force)> drawnMembers =
            MemberEnds(block, nodes);
        (double[][] vertices, int[][] faces) =
            ColumnsMesh.Build(drawnMembers, radius);

        // The members are the block's OWN, in the block's own order and
        // none of them renumbered, because trees[] indexes into them by
        // position and renumbering there would silently rewrite the branch
        // structure. A member too short to have a direction still draws no
        // prism, so "drawnMembers" names which member each prism belongs to
        // and the two lists cannot fall out of step.
        var memberPayloads =
            new List<Dictionary<string, object?>>(block.Members.Count);
        foreach (EdgeDto member in block.Members)
        {
            memberPayloads.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["u"] = member.U,
                ["v"] = member.V,
            });
        }

        var columns = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["schema"] = ColumnsSchema,
            ["nodes"] = MouldFrames.Triples(nodes),
            ["members"] = memberPayloads,
            ["memberForce"] = block.MemberForce,
            ["trees"] = block.Trees,
            ["heads"] = block.Heads,
            ["forks"] = block.Forks,
            ["feet"] = block.Feet,
            ["headNode"] = block.HeadNode,
            ["vertices"] = vertices,
            ["faces"] = faces,
            ["drawnMembers"] = ColumnsMesh.Drawn(drawnMembers),
        };

        var payload = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["schema"] = Schema,
            ["study"] = study,
            // The unit the coordinates are IN, and how many metres one of
            // them is. The coordinates are the contract's own, unscaled,
            // which is what makes the time-100 equality checkable at all,
            // so the factor is the studio's only way to know whether it is
            // reading metres or millimetres.
            ["units"] = "m",
            ["lengthUnitToMetres"] = unitFactor,
            ["forceUnit"] = forceUnit,
            // KEPT, on the studio's own ask (their R-010(h)): they draw the
            // animated column members as tubes at exactly this radius, so
            // the machine's columns and the exported solids are one
            // drawing rather than two.
            ["radius"] = radius,
            ["vertexCount"] = sweep.VertexCount,
            ["columnNodeCount"] = sweep.ColumnNodeCount,
            ["columns"] = columns,
            ["frames"] = sweep.Frames,
        };
        return JsonSerializer.Serialize(payload, ContractJson.Options);
    }

    /// <summary>
    /// Each member as the two node points it spans and the force on it,
    /// which is the only shape <see cref="ColumnsMesh"/> reads. The points
    /// come from the node list this document carries, so the prisms stand
    /// where the document says the nodes are.
    /// </summary>
    private static IReadOnlyList<(Point3d From, Point3d To, double Force)>
        MemberEnds(MouldColumnsDto block, IReadOnlyList<Point3d> nodes)
    {
        var members =
            new List<(Point3d From, Point3d To, double Force)>(
                block.Members.Count);
        for (int i = 0; i < block.Members.Count; i++)
        {
            EdgeDto member = block.Members[i];
            members.Add((
                nodes[member.U],
                nodes[member.V],
                i < block.MemberForce.Count ? block.MemberForce[i] : 0.0));
        }
        return members;
    }
}
