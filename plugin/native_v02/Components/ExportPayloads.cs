#nullable enable

using System;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
using System.Linq;
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

    /// <summary>
    /// The fourth sibling: heavy but rare, re-sent only when its own change
    /// key moves, exactly like the other three (mechanism spec section 1).
    /// </summary>
    public const string MechanismKind = "mechanism";

    public static string[] Kinds(bool hasCells, bool hasColumns, bool hasMechanism)
    {
        var kinds = new List<string> { FormKind };
        if (hasCells)
            kinds.Add(SkinKind);
        if (hasColumns)
            kinds.Add(FormworkKind);
        if (hasMechanism)
            kinds.Add(MechanismKind);
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
        return JsonFromContract(ContractJson.Serialize(result), study, thrustMesh);
    }

    /// <summary>
    /// The same document from a contract already serialised, which is how a
    /// build that ends up wanting a thrust mesh pays for the contract's own
    /// bytes ONCE: the cheap document is written first so its key can be
    /// asked about, and the answered one is spliced from the same string
    /// rather than from a second serialisation of the same Result.
    /// </summary>
    public static string JsonFromContract(
        string contract,
        string study,
        string? thrustMesh)
    {
        ArgumentNullException.ThrowIfNull(contract);
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
                ? AbsentMesh
                : PresentMesh);
    }

    /// <summary>The two endings <see cref="KeyMaterial"/> can produce.</summary>
    public const string AbsentMesh = "null}";

    public const string PresentMesh = "\"present\"}";

    /// <summary>
    /// The CONTRACT half of one key material, which is what decides whether
    /// a form document has anything new in it, and the presence half beside
    /// it, which is what decides whether a build that could not reach the
    /// worker is still owed a retry (rule 3.3). They are read apart because
    /// the two answer different questions: the contract half decides whether
    /// to SEND, and it must not move when only a uuid did; the presence half
    /// decides whether to BUILD a mesh at all, and a document already sent
    /// with one is never rebuilt for its sake.
    /// </summary>
    public static string ContractHalf(string keyMaterial)
    {
        if (keyMaterial is null)
            return string.Empty;
        int at = keyMaterial.LastIndexOf(
            ThrustMeshMember, StringComparison.Ordinal);
        return at < 0 ? keyMaterial : keyMaterial[..at];
    }

    public static bool CarriesMesh(string keyMaterial) =>
        keyMaterial is not null &&
        keyMaterial.EndsWith(
            ThrustMeshMember + PresentMesh, StringComparison.Ordinal);
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
            // THE BLOCK'S NODES ARE {"x","y","z"} OBJECTS, not triples,
            // because that is the shape their reader has already shipped
            // against. bench/studio/frames.py pairing_error does
            // `target = reference.get(axis) if isinstance(reference,
            // Mapping) else None` over exactly this list (their commit
            // cafecc9, announced in R-012(c)); handed an [x, y, z] list it
            // reads no numeric x, returns "column node 0 in the formwork
            // document's own columns block has no numeric x", and the
            // formwork act 404s on EVERY export. The contract's own
            // mould.columns.nodes are Point3Dto objects and this block is
            // the same bookkeeping moved, so the same encoding is also the
            // consistent one. The FRAMES keep their triples: their reader
            // validates columnNodes as triples and pairs the two lists
            // across the encodings.
            ["nodes"] = NodeObjects(nodes),
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
    /// The machine's nodes in the encoding the studio's pairing check
    /// reads: one <c>{"x":.., "y":.., "z":..}</c> object per node, the same
    /// shape the contract's <c>mould.columns.nodes</c> carries, in the same
    /// order the members index.
    /// </summary>
    internal static IReadOnlyList<Dictionary<string, object?>> NodeObjects(
        IReadOnlyList<Point3d> nodes)
    {
        var written = new List<Dictionary<string, object?>>(nodes.Count);
        foreach (Point3d node in nodes)
        {
            written.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["x"] = node.X,
                ["y"] = node.Y,
                ["z"] = node.Z,
            });
        }
        return written;
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

/// <summary>
/// MECHANISM, <c>&lt;study&gt;-mechanism.json</c>, schema
/// <c>bench.mechanism/1</c>: the fourth sibling document (mechanism spec
/// section 1), built from TWO halves that never disagree about a row
/// because they share one call (<see cref="MechanismGeometry"/>):
///
/// the SHAPE half is the MECHANISM collector's own payload, and it is NOT
/// passed through verbatim: it is filtered to the six keys
/// <see cref="StudyMechanismKeys"/> names (tensionTie, anchor, cableRadius,
/// cableThickness, cableMatchesNetCable, routingFrameMeaning), which is the
/// whole point of the machine split. Everything else the collector's block
/// can carry -- frame1, frame2, motors, reels and spoolRadius -- belongs to
/// the machine document and is dropped here rather than copied into every
/// study. The PLACEMENT half is computed here, against the Result Export
/// already owns, exactly the way the formwork document's frames are built
/// here and not by Columns or Animate.
///
/// THE OLD SENTENCE SAID THE OPPOSITE, and is recorded because it is the
/// seventh piece of stale text this rework has had to correct: it listed
/// "bodies, spinners, axes, sockets, reeve factor, spool radius, anchor tie
/// meshes" as passed through verbatim, and every one of those either left
/// for the machine document or never existed under that name.
///
/// Caught on its own by the caller, the way formwork is: a Result the
/// mechanism payload's shape does not fit (a node reel with no columns,
/// say) costs this document and nothing else.
/// </summary>
internal static class MechanismDocument
{
    /// <summary>
    /// THE STUDY DOCUMENT'S OWN SCHEMA NAME, AND IT DOES NOT CHANGE (spec
    /// 5.6). Since Task 6 this document is no longer mostly a mechanism --
    /// it carries a citation, the placements, the permanent works and the
    /// wires, and not one machine body -- and a name describing that would
    /// be a better name. It stays <c>bench.mechanism/1</c> anyway. The
    /// precedent is close and recent and expensive: renaming
    /// <c>bench.frames/1</c> to <c>bench.formwork/1</c> broke the studio's
    /// reader SILENTLY, and cost days. The change is in the contents, and
    /// the studio is told about it through the channel note (spec 10.2)
    /// rather than by a reader that stops finding the file.
    /// </summary>
    public const string Schema = "bench.mechanism/1";

    /// <summary>
    /// EXACTLY WHAT A STUDY DOCUMENT'S <c>mechanism</c> BLOCK MAY CARRY
    /// (spec 2.2): the two permanent works that travel with every study
    /// (ruling 1.1), and the facts about the cable itself that a reader
    /// needs to draw the wires. Everything else in the collector's own
    /// block -- frame1, frame2, motors, reels, spoolRadius -- belongs to
    /// the machine and stays in the machine document.
    ///
    /// THE ORDER IS THE WRITTEN ORDER, so the document is byte-identical
    /// for the same payload, which the change-key requirement depends on.
    /// </summary>
    private static readonly string[] StudyMechanismKeys =
    {
        "tensionTie",
        "anchor",
        "cableRadius",
        "cableThickness",
        "cableMatchesNetCable",
        "routingFrameMeaning",
    };

    /// <summary>
    /// Finish the collector's raw payload into the fourth sibling document:
    /// match each authored wire (Routing/RT) to a net vertex, validate the
    /// match (R2's reversed-list check) and pass the rest through.
    /// This is the ONE place the Result is available, so it is also the
    /// one place net-vertex matching can happen (the collector itself is
    /// Result-free except for the door-guard). <paramref name="warnings"/>
    /// and <paramref name="notes"/> are appended to, matching
    /// <see cref="MechanismCollector.Build"/>'s own convention, so a caller
    /// can pool them across a whole solve's chin.
    ///
    /// SINCE TASK 6 IT IS ALSO THE GATE THE MACHINE DOES NOT PASS. The
    /// study document cites its machine by id and carries no machine body
    /// at all (spec 2.2), so this writer:
    ///
    /// 1. REFUSES A PAYLOAD THAT CITES NO MACHINE, by name. There is no
    ///    fallback default anywhere in the chain any more.
    /// 2. Takes the MACHINE DEFAULT for every wire's reeve resolution from
    ///    the CITED MACHINE (spec 6.1 to 6.3).
    /// 3. Writes the <c>mechanism</c> block from an ALLOWLIST
    ///    (<see cref="StudyMechanismKeys"/>), so a machine body reaching
    ///    this writer in a payload is dropped rather than carried.
    /// 4. Names every wire's machine wire by the AUTHORED wire number
    ///    (spec 5.4), never by a position in the machine's own routing.
    /// 5. Cross-checks the wires each instance places against the cited
    ///    machine's declared count BY EQUALITY (spec 5.5).
    /// 6. Since Task 7, checks each matched ANCHOR ROW's own characteristic
    ///    spacing against that machine's own <c>footprint.cableSpan</c>
    ///    (spec 7.4). It is the only check here whose two numbers come from
    ///    two documents, and therefore the only one that can fail on a
    ///    DERIVED placement.
    ///
    /// A DERIVED RESIDUAL PROVES NOTHING, AND SAYING SO IS PART OF THIS
    /// TASK (spec 7.5). Placement is derived from the solved net's own
    /// anchor rows by default and has been since 2026-09-09; a derived
    /// transform is therefore FITTED TO the anchors the wires are then
    /// matched against, so <c>instances[].residualM</c> reads 0.000000 m on
    /// every correct instance and on a routing tree authored backwards
    /// alike. It is a measure of the derivation's own fit and it cannot
    /// report a fault in what was fitted. The MATCH DISTANCE below is the
    /// number that can, because it is taken between the placed route and a
    /// net vertex this document chose by its own separate rule -- but only
    /// on an AUTHORED placement, and the guard block itself carries the
    /// measurement of what it does and does not separate on the derived
    /// one.
    ///
    /// NOT PROVED HERE, and it cannot be from inside this process: that the
    /// machine document the id names still holds the machine this study was
    /// laid out against. There is no upload route and no library index in
    /// this repo (spec 11.1); the id is written faithfully and resolving it
    /// is the studio's own step. Item 6 above is the nearest thing to a
    /// check on it that exists: a cited machine whose cable line does not
    /// fit the row it is placed on is named, though one that fits and is
    /// still the wrong machine is not.
    /// </summary>
    public static string Json(
        ResultDto result,
        string study,
        double unitFactor,
        string mechanismPayloadJson,
        List<string> warnings,
        List<string> notes)
    {
        ArgumentNullException.ThrowIfNull(result);
        ArgumentNullException.ThrowIfNull(mechanismPayloadJson);
        ArgumentNullException.ThrowIfNull(warnings);
        ArgumentNullException.ThrowIfNull(notes);
        if (!double.IsFinite(unitFactor) || unitFactor <= 0.0)
        {
            throw new ArgumentOutOfRangeException(
                nameof(unitFactor),
                unitFactor,
                "The length unit factor is how many metres one document " +
                "unit is, so it is finite and positive.");
        }

        using JsonDocument parsed = JsonDocument.Parse(mechanismPayloadJson);
        JsonElement root = parsed.RootElement;
        JsonElement mechanismIn = root.TryGetProperty("mechanism", out JsonElement me) ? me : default;
        JsonElement instancesIn = root.TryGetProperty("instances", out JsonElement inst) ? inst : default;
        JsonElement wiresIn = root.TryGetProperty("wires", out JsonElement wi) ? wi : default;
        JsonElement anchorsIn = root.TryGetProperty("anchors", out JsonElement an) ? an : default;
        JsonElement tiesIn = root.TryGetProperty("tensionTies", out JsonElement tt) ? tt : default;

        EquilibriumResultDto? eq = result.Equilibrium;
        int vertexCount = eq?.Vertices.Count ?? 0;
        int columnNodeCount = result.Mould?.Columns?.Nodes.Count ?? 0;

        var wireEntries = new List<(int Side, int Mechanism, int Wire,
            List<(MechanismFrame Frame, string Owner, int OwnerReel)> Route)>();
        if (wiresIn.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement w in wiresIn.EnumerateArray())
            {
                int side = w.GetProperty("side").GetInt32();
                int mechanism = w.GetProperty("mechanism").GetInt32();
                int wireIndex = w.GetProperty("wire").GetInt32();
                var route = new List<(MechanismFrame Frame, string Owner, int OwnerReel)>();
                foreach (JsonElement p in w.GetProperty("route").EnumerateArray())
                {
                    // OWNERSHIP CARRIED THROUGH, NEVER RECOMPUTED: the
                    // collector is the one place holding the reel
                    // geometry this classification needs (his
                    // wrapped-wire ruling, 2026-09-08), so this document
                    // only reads what it already decided. A missing field
                    // (an older payload, or a fixture with no reels
                    // wired) falls back to the body, the same default
                    // the classification itself returns when no reel
                    // claims a frame.
                    string owner =
                        p.TryGetProperty(MechanismCollector.RouteOwnerField, out JsonElement ownerEl) &&
                        ownerEl.ValueKind == JsonValueKind.String
                            ? ownerEl.GetString() ?? MechanismCollector.RouteOwnerBody
                            : MechanismCollector.RouteOwnerBody;
                    int ownerReel =
                        p.TryGetProperty(MechanismCollector.RouteOwnerReelField, out JsonElement reelEl) &&
                        reelEl.ValueKind == JsonValueKind.Number
                            ? reelEl.GetInt32()
                            : MechanismCollector.NoOwnerReel;
                    route.Add((ReadFrame(p), owner, ownerReel));
                }
                wireEntries.Add((side, mechanism, wireIndex, route));
            }
        }
        // HIS OWN TREE ORDER: "frames, wires per mechanism, mechanisms per
        // side, sides" -- side ascending, then mechanism, then wire.
        wireEntries.Sort((a, b) =>
        {
            int bySide = a.Side.CompareTo(b.Side);
            if (bySide != 0)
                return bySide;
            int byMechanism = a.Mechanism.CompareTo(b.Mechanism);
            return byMechanism != 0 ? byMechanism : a.Wire.CompareTo(b.Wire);
        });

        var instanceFrames = new Dictionary<(int Side, int Mechanism), MechanismFrame>();
        var instanceWireIds = new Dictionary<(int Side, int Mechanism), List<string>>();
        var instancesOut = new List<Dictionary<string, object?>>();
        if (instancesIn.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement instanceIn in instancesIn.EnumerateArray())
            {
                int side = instanceIn.GetProperty("side").GetInt32();
                int mechanism = instanceIn.GetProperty("mechanism").GetInt32();
                MechanismFrame frame = ReadFrame(instanceIn.GetProperty("frame"));
                instanceFrames[(side, mechanism)] = frame;
                var wireIds = new List<string>();
                instanceWireIds[(side, mechanism)] = wireIds;
                instancesOut.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["side"] = side,
                    ["mechanism"] = mechanism,
                    ["frame"] = MechanismCollector.FramePayload(frame),
                    ["kind"] = instanceIn.TryGetProperty("kind", out JsonElement k)
                        ? k.GetString()
                        : null,
                    // ONE PLACEMENT CONVENTION (studio's C5/A5): every
                    // instance carries a placement frame he authored,
                    // unlike Anchor/Tension Tie's "world" flag below.
                    ["placement"] = "instance",
                    ["wireIds"] = wireIds,
                });
            }
        }

        // NET VERTEX MATCHING. WHICH ANCHORS an instance draws from is
        // settled here, row by row: the rows are paired to sides by
        // proximity (below) and flattened, and each instance takes its own
        // run of that flat list in his tree order (side, mechanism, wire).
        // WHICH OF THOSE ANCHORS EACH WIRE GETS is settled further down, by
        // where the wire was actually PLACED and not by its position in the
        // tree (Task 7a). R1's non-negotiable survives both: every wire
        // gets its OWN explicit net_vertex written into the document, never
        // left to be inferred from tree position downstream.
        //
        // WHICH ROW IS WHICH SIDE'S is decided by PHYSICAL PROXIMITY (audit
        // finding 3), never by row-discovery order:
        // MouldGeometry.ConnectedGroups' own order is "the order of their
        // lowest node index... arbitrary but STABLE", an artefact of how
        // the net happened to get numbered, with zero relationship to his
        // own authored `side` field. Each row is paired to whichever
        // side's own instances sit nearest it in world space. Falls back to
        // document order when the row count and the authored side count
        // disagree, which this pairing cannot resolve unambiguously -- the
        // same behaviour this file always had.
        List<List<int>> rows = MechanismGeometry.AnchorRowIndices(result);
        List<List<int>> orderedRows = rows;
        List<int> sideOrder = instanceFrames.Keys
            .Select(k => k.Side)
            .Distinct()
            .OrderBy(s => s)
            .ToList();
        if (eq is not null && rows.Count > 0 && rows.Count == sideOrder.Count)
        {
            List<double[]> rowCentres = rows
                .Select(row => Centroid(row.Select(id =>
                {
                    Point3Dto p = eq.Vertices[id];
                    return new[] { p.X, p.Y, p.Z };
                }).ToList()))
                .ToList();
            var unassigned = Enumerable.Range(0, rows.Count).ToList();
            var assignment = new int[sideOrder.Count];
            for (int s = 0; s < sideOrder.Count; s++)
            {
                double[] sideCentre = Centroid(instanceFrames
                    .Where(kv => kv.Key.Side == sideOrder[s])
                    .Select(kv => kv.Value.Origin)
                    .ToList());
                int nearest = unassigned
                    .OrderBy(r => MechanismCollector.Distance(rowCentres[r], sideCentre))
                    .First();
                assignment[s] = nearest;
                unassigned.Remove(nearest);
            }
            orderedRows = assignment.Select(r => rows[r]).ToList();
            bool swapped = false;
            for (int i = 0; i < assignment.Length; i++)
                swapped |= assignment[i] != i;
            if (swapped)
            {
                notes.Add(
                    "mechanism: anchor rows were paired to sides by " +
                    "physical proximity to each side's own placed " +
                    "instances, not by the net's own numbering, and the " +
                    "two disagreed for this study: document-order " +
                    "pairing would have matched every wire against the " +
                    "wrong side's anchors.");
            }
        }
        var anchorFlat = new List<int>();
        foreach (List<int> row in orderedRows)
            anchorFlat.AddRange(row);

        // A PER-ROW TOLERANCE for the match-distance check below (finding
        // 3's second half): the door-guard's own pattern
        // (MechanismCollector.BuildRowParts), a multiple of the row's own
        // characteristic anchor spacing, so a wire's printed distance is
        // backed by a check rather than left for him to eyeball on a
        // vault where a full side swap can print a distance the same
        // order as a correctly matched wire's own free span.
        //
        // THE SAME SPACING IS ALSO THE INDEPENDENT WITNESS'S OWN END of the
        // comparison below (spec 7.4), so the row each matched vertex
        // belongs to is remembered here as well as its spacing: the witness
        // is stated ONCE PER ROW, not once per wire and not once per
        // instance, because a row is the thing whose spacing it reads and
        // six instances on two rows would otherwise print the identical
        // line six times over.
        var vertexRowSpacing = new Dictionary<int, double>();
        var vertexRowIndex = new Dictionary<int, int>();
        var rowSpacing = new Dictionary<int, double>();
        if (eq is not null)
        {
            for (int r = 0; r < orderedRows.Count; r++)
            {
                List<int> row = orderedRows[r];
                IReadOnlyList<double[]> points = row.Select(id =>
                {
                    Point3Dto p = eq.Vertices[id];
                    return new[] { p.X, p.Y, p.Z };
                }).ToList();
                double spacing = MechanismCollector.CharacteristicSpacing(points);
                rowSpacing[r] = spacing;
                foreach (int id in row)
                {
                    vertexRowSpacing[id] = spacing;
                    vertexRowIndex[id] = r;
                }
            }
        }

        // WHICH ANCHOR IN THE INSTANCE'S OWN RUN EACH WIRE IS BOUND TO,
        // DECIDED BY WHERE THE WIRE WAS PLACED (Task 7a, 2026-09-10).
        //
        // THIS CHANGES THE ARTEFACT ON EVERY TWO-SIDED VAULT, which is his
        // default workflow, and it is said here as loudly as in the commit
        // that made it: a wire's net_vertex is the anchor THE STUDIO DRAWS
        // ITS CABLE TO, so a study exported before this and a study
        // exported after it bind the turned side's seven cables to
        // different anchors. The new binding is the one the machine was
        // actually placed against; the old one was the row's own discovery
        // order, and on a turned instance the two ran end for end.
        //
        // WHAT WAS WRONG. MechanismCollector.DerivePlacements pairs wire to
        // anchor SPATIALLY -- its alongMachine order against its alongRow
        // order -- and settles each row's sense by which side of the row
        // the net stands on, so the far side's machine is turned round to
        // face away from its own springing. That is the whole content of
        // "one machine, built once, turned round". This document paired
        // wire ORDER against the row's DISCOVERY order, which
        // MouldGeometry.ConnectedGroups documents as "arbitrary but
        // stable". The two agree on an untouched instance and run end for
        // end on a turned one: measured on a seven-wire, two-row fixture,
        // the turned side's wires were bound 0.9, 0.6, 0.3, 0, 0.3, 0.6 and
        // 0.9 m from where they had been placed, and a CORRECT study drew
        // FOUR match-distance warnings for it.
        //
        // THE RULE NOW, AND WHY IT IS THE SAME RULE AND NOT A SECOND COPY
        // OF IT. Both ends are ordered along ONE axis, the row's own
        // direction (MechanismCollector.WidestPairDirection, the method
        // DerivePlacements itself orders anchor rows by), using
        // MechanismCollector.OrderAlongAxis, the method it orders both
        // alongMachine and alongRow by. The k-th wire along that axis takes
        // the k-th anchor along it.
        //
        // That reproduces the derivation EXACTLY, and the algebra is worth
        // stating because it is why one axis suffices where the derivation
        // needs two. A placed wire end is R*first + t, and the derivation's
        // own worldX is R*machineX, so ordering placed wire ends along
        // worldX is ordering first along machineX to within a constant --
        // alongMachine, recovered in world space. Ordering the anchors
        // along the same axis is alongRow. And pairing k-th to k-th is
        // INVARIANT UNDER FLIPPING THAT AXIS, since flipping reverses both
        // lists, so the sign conventions that make DerivePlacements' two
        // frames comparable drop out here entirely and cannot be got wrong
        // a second time.
        //
        // IT ALSO WORKS ON AN AUTHORED PLACEMENT, where there is no
        // derivation to agree with: the wire is bound to the anchor it was
        // laid out against, which is what the match-distance guard below
        // has always been measuring.
        //
        // WHAT IS NOT PROVED, AND IS DELIBERATELY LEFT ALONE. An instance
        // whose run of anchors is SHORT (fewer anchors left than it has
        // wires) keeps the old flat pairing and the old drop rule: a
        // spatial pairing over an incomplete pair of sets would silently
        // change WHICH wire is dropped, and a dropped wire is named by id
        // in a warning he reads. So is an instance with a single wire (no
        // order to fix), one carrying no placement frame, and one whose
        // wires carry no route to place. And the axis is the ANCHORS' own:
        // a machine authored with its wire ends running across the row
        // rather than along it projects them all onto nearly one point, and
        // this pairing is then no better than the tree order it replaced.
        // None of those shapes appear in a study this plugin writes.
        var matchedVertices = new int[wireEntries.Count];
        for (int i = 0; i < wireEntries.Count; i++)
            matchedVertices[i] = i < anchorFlat.Count ? anchorFlat[i] : -1;
        for (int blockStart = 0; blockStart < wireEntries.Count;)
        {
            int blockSide = wireEntries[blockStart].Side;
            int blockMechanism = wireEntries[blockStart].Mechanism;
            int blockEnd = blockStart;
            while (blockEnd < wireEntries.Count &&
                   wireEntries[blockEnd].Side == blockSide &&
                   wireEntries[blockEnd].Mechanism == blockMechanism)
            {
                blockEnd++;
            }

            int blockCount = blockEnd - blockStart;
            if (eq is null ||
                blockCount < 2 ||
                blockEnd > anchorFlat.Count ||
                !instanceFrames.TryGetValue(
                    (blockSide, blockMechanism), out MechanismFrame? blockFrame) ||
                blockFrame is null)
            {
                blockStart = blockEnd;
                continue;
            }

            var blockAnchorIds = new List<int>(blockCount);
            var blockAnchorPoints = new List<double[]>(blockCount);
            var blockWirePoints = new List<double[]>(blockCount);
            bool blockReadable = true;
            for (int k = 0; k < blockCount; k++)
            {
                int anchorId = anchorFlat[blockStart + k];
                if (anchorId < 0 ||
                    anchorId >= eq.Vertices.Count ||
                    wireEntries[blockStart + k].Route.Count == 0)
                {
                    blockReadable = false;
                    break;
                }
                blockAnchorIds.Add(anchorId);
                Point3Dto anchorPoint = eq.Vertices[anchorId];
                blockAnchorPoints.Add(new[] { anchorPoint.X, anchorPoint.Y, anchorPoint.Z });
                blockWirePoints.Add(TransformLocal(
                    wireEntries[blockStart + k].Route[0].Frame.Origin, blockFrame));
            }
            if (!blockReadable)
            {
                blockStart = blockEnd;
                continue;
            }

            double[] rowAxis = MechanismCollector.WidestPairDirection(blockAnchorPoints);
            int[] anchorsAlongRow = MechanismCollector.OrderAlongAxis(blockAnchorPoints, rowAxis);
            int[] wiresAlongRow = MechanismCollector.OrderAlongAxis(blockWirePoints, rowAxis);
            for (int k = 0; k < blockCount; k++)
                matchedVertices[blockStart + wiresAlongRow[k]] = blockAnchorIds[anchorsAlongRow[k]];

            blockStart = blockEnd;
        }

        // THE REEVE FACTOR'S OWN SHAPE (spec section 6, parallel to
        // net_vertex): the document carries the RESOLVED value on every
        // wire, alongside WHICH SOURCE won it, so the studio never
        // inherits or infers one.
        //
        // THE CITED MACHINE, AND THE MACHINE DEFAULT WITH IT (spec 5.3, 6.3;
        // Task 6). A study cites exactly ONE machine, by id (ruling 1.2),
        // and since the split it carries none of that machine's bodies: the
        // citation is the only thing tying this document to the winch it
        // draws. It is REFUSED BY NAME when absent.
        //
        // WHAT THIS REPLACED, AND WHY. Task 4 read the default from the
        // payload's own reeve.default, which the collector stated for
        // ITSELF as a provisional 1.0 while the Machine (MA) port was
        // registered and unread. That was a deliberate placeholder and it
        // is gone: the middle source of every wire's resolved factor is now
        // the CITED MACHINE's own authored default, and there is no third
        // source at all. A fallback here -- to 1.0, to 4.0, to anything --
        // would have every export silently applying a number nobody
        // authored, with the geometry, the wire paths and the timing all
        // still correct so that nothing looks broken. Export writes what it
        // is handed (spec 1.3); where it is handed no machine it writes
        // NOTHING and says so, which costs the mechanism document and
        // nothing else.
        //
        // THE REFUSAL NAMES THE PORT, not the key, because the port is
        // where he can act: a payload with no machine block is a Mechanism
        // component with nothing wired to Machine (MA).
        if (!root.TryGetProperty("machine", out JsonElement citedMachine) ||
            citedMachine.ValueKind != JsonValueKind.Object ||
            !citedMachine.TryGetProperty("id", out JsonElement citedId) ||
            citedId.ValueKind != JsonValueKind.String ||
            string.IsNullOrWhiteSpace(citedId.GetString()))
        {
            throw new InvalidOperationException(
                "this study cites no machine, so no mechanism document was " +
                "written. Wire the Machine component's own Machine (MC) " +
                "output to the Mechanism component's Machine (MA) input. " +
                "Since the machine left the study, the study document " +
                "carries no machine bodies at all and names its machine by " +
                "id instead, and it takes that machine's own authored " +
                "reeve default: a document with neither would draw nothing " +
                "and spin nothing.");
        }
        string machineId = citedId.GetString()!.Trim();
        string machineName =
            citedMachine.TryGetProperty("name", out JsonElement citedName) &&
            citedName.ValueKind == JsonValueKind.String &&
            !string.IsNullOrWhiteSpace(citedName.GetString())
                ? citedName.GetString()!.Trim()
                : machineId;
        if (!citedMachine.TryGetProperty("wireCount", out JsonElement citedWireCount) ||
            citedWireCount.ValueKind != JsonValueKind.Number ||
            !citedWireCount.TryGetInt32(out int machineWireCount) ||
            machineWireCount < 0)
        {
            throw new InvalidOperationException(
                $"the cited machine \"{machineId}\" declares no usable " +
                "wireCount, so no mechanism document was written. The " +
                "wires this study places are checked against that count " +
                "ONE FOR ONE, and without it a study placing seven wires " +
                "against a twelve-wire machine animates seven cables, " +
                "leaves five absent, and says nothing at all.");
        }

        // THIS reeveFactor VARIABLE IS machineDefault FOR EVERY CALL TO
        // MechanismReeve.Resolve BELOW, and it is the CITED MACHINE's own
        // authored number. It is validated here as well as where the
        // citation was read, because this reader re-validates any payload
        // handed to it and is not entitled to assume this collector wrote
        // it (the same reasoning that put the guard on reeve.perWire).
        if (!citedMachine.TryGetProperty("reeveDefault", out JsonElement citedReeve) ||
            citedReeve.ValueKind != JsonValueKind.Number ||
            !double.IsFinite(citedReeve.GetDouble()) ||
            citedReeve.GetDouble() <= 0.0)
        {
            throw new InvalidOperationException(
                $"the cited machine \"{machineId}\" " +
                (citedReeve.ValueKind == JsonValueKind.Number
                    ? "states a reeve default of " +
                      citedReeve.GetDouble().ToString(CultureInfo.InvariantCulture) +
                      ", which is not a mechanical advantage"
                    : "states no reeve default at all") +
                ", so no mechanism document was written. It is the " +
                "advantage of one wire's reeving through its block, so it " +
                "is finite and greater than zero, and it is refused here " +
                "rather than replaced by a plausible number: a wrong " +
                "factor makes every reel spin at the wrong RATE while the " +
                "geometry, the wire paths and the timing all stay correct, " +
                "so nothing looks broken.");
        }
        double reeveFactor = citedReeve.GetDouble();

        // THE CITED MACHINE'S OWN CABLE SPAN (spec 7.4), the independent
        // witness's machine end. READ, NOT DEMANDED: a machine routing
        // fewer than two wires has no cable line and writes no footprint at
        // all, and a payload this collector did not write may carry
        // anything, so an absent, non-numeric, non-finite or non-positive
        // span means "this study cannot be layout-checked" rather than "no
        // document". Refusing here would cost him the whole export over a
        // number that changes nothing the studio draws or spins.
        double? machineCableSpan = null;
        if (citedMachine.TryGetProperty("cableSpan", out JsonElement citedSpan) &&
            citedSpan.ValueKind == JsonValueKind.Number &&
            double.IsFinite(citedSpan.GetDouble()) &&
            citedSpan.GetDouble() > 0.0)
        {
            machineCableSpan = citedSpan.GetDouble();
        }

        JsonElement reeveBlock = root.TryGetProperty("reeve", out JsonElement reeveIn)
            ? reeveIn
            : default;

        // THE PER-WIRE OVERRIDES (RW, spec 6.1), read off reeve.perWire --
        // an object keyed by wire index as a JSON string, since a wire
        // number is not a valid object key. ABSENT, NOT AN OBJECT, OR AN
        // ENTRY THAT IS NOT ITSELF A NUMBER is read as "no override for
        // that wire" rather than refused: reeve.perWire is optional by
        // nature (RW is an OPTIONAL port), unlike the citation above, which
        // a study cannot do without, and a key that never parses as a wire
        // index can never wrongly override one. The whole reeve block may
        // be absent for the same reason, which is why its own kind is
        // tested before it is read into.
        //
        // AN ENTRY THAT IS A NUMBER BUT NOT A MECHANICAL ADVANTAGE IS
        // REFUSED, THE WHOLE DOCUMENT, BY NAME -- the same guard the cited
        // machine's own default gets above, in the same words and the same
        // shape (fix round 1, finding 1). This reader re-validates every
        // number it is handed precisely because the collector is not the
        // only possible author of a payload; the override is exactly the
        // same kind of number and deserves exactly the same guard. Before
        // this, a payload carrying reeve.perWire.3 = -2 (or 0, or NaN)
        // resolved wire 3's reeveFactor to -2, sourced "wire", on every
        // instance of that wire, with no refusal and no warning -- the
        // sanity check is ONE-SIDED (spec 6.4) and never fires on a small
        // or negative number. The collector's own ReadReevePerWire already
        // drops a bad override by name at the point it is authored; this is
        // the same check at the point it is READ, which is the one that
        // matters for a payload this collector did not write.
        var reevePerWire = new Dictionary<int, double>();
        if (reeveBlock.ValueKind == JsonValueKind.Object &&
            reeveBlock.TryGetProperty("perWire", out JsonElement perWireBlock) &&
            perWireBlock.ValueKind == JsonValueKind.Object)
        {
            foreach (JsonProperty entry in perWireBlock.EnumerateObject())
            {
                if (entry.Value.ValueKind != JsonValueKind.Number ||
                    !int.TryParse(
                        entry.Name, NumberStyles.Integer, CultureInfo.InvariantCulture,
                        out int wireIndex))
                {
                    continue;
                }
                double overrideValue = entry.Value.GetDouble();
                if (!double.IsFinite(overrideValue) || overrideValue <= 0.0)
                {
                    throw new InvalidOperationException(
                        $"the payload's reeve.perWire[{wireIndex}] is " +
                        overrideValue.ToString(CultureInfo.InvariantCulture) +
                        ", which is not a mechanical advantage, so no " +
                        "mechanism document was written. It is the " +
                        "advantage of one wire's reeving through its " +
                        "block, so it is finite and greater than zero.");
                }
                reevePerWire[wireIndex] = overrideValue;
            }
        }

        // RESOLVED ONCE PER WIRE INDEX, NOT ONCE PER (side, mechanism,
        // wire) INSTANCE: routing is authored ONCE per mechanism and the
        // SAME local route is written for every placement branch (see
        // MechanismCollector.BuildWithResult's own wiresOut loop), so wire
        // 3's own resolution, its wrap-reversal count and its sanity
        // verdict are IDENTICAL on every instance that carries a wire 3.
        // Computing this once per wire index rather than once per instance
        // is the same reasoning that turned forty-two per-wire match lines
        // into one headline above (2026-09-08, his ruling on the balloon):
        // a six-instance machine would otherwise print the identical
        // sanity warning six times over for the one wire that earns it.
        var resolvedReeve = new Dictionary<int, (double Value, string Source)>();

        (double Value, string Source) ResolveWireReeve(
            int wireIndex, IReadOnlyList<MechanismFrame> route)
        {
            if (resolvedReeve.TryGetValue(wireIndex, out (double Value, string Source) cached))
                return cached;

            (double value, string source) =
                MechanismReeve.Resolve(reeveFactor, reevePerWire, wireIndex);
            resolvedReeve[wireIndex] = (value, source);

            // THE SANITY CHECK (spec 6.4): compares the resolved factor
            // against the band its own wrap reversals imply, and WARNS BY
            // NAME ONLY WHEN WILDLY OUTSIDE IT. It REFUSES NOTHING: a
            // wheel that merely GUIDES the wire gives no advantage at all
            // while one that MOVES WITH THE LOAD does, and geometry cannot
            // tell the two apart, so a check that refused would be
            // refusing a machine it cannot actually assess. See
            // MechanismReeve.SanityCeiling for the band itself and why it
            // has no floor.
            int reversals = MechanismReeve.WrapReversals(route);
            double ceiling = MechanismReeve.SanityCeiling(reversals);
            if (value > ceiling)
            {
                warnings.Add(
                    $"wire {wireIndex}: reeveFactor " +
                    value.ToString("0.####", CultureInfo.InvariantCulture) +
                    $" (source \"{source}\") is wildly above what this " +
                    $"wire's own route can plausibly support -- " +
                    $"{reversals} wrap reversal(s) imply a ceiling of " +
                    "about " +
                    ceiling.ToString("0.####", CultureInfo.InvariantCulture) +
                    ". This warns rather than refuses, since a wheel that " +
                    "only GUIDES the wire gives no advantage at all while " +
                    "one that MOVES WITH THE LOAD does, and geometry " +
                    "cannot tell the two apart; check the declared factor " +
                    "against the machine's own reeving before trusting " +
                    "this wire's spin rate.");
            }
            return (value, source);
        }

        // TOP-LEVEL WIRES (studio's C7/A7): "ids on instances say an
        // instance participates but not what the wire IS". Every wire this
        // document declares is finished ONCE here and instances above
        // carry only the id, never a second copy of what it names.
        var wiresOut = new List<Dictionary<string, object?>>();

        // EVERY MATCH IS STILL PRINTED WITH ITS DISTANCE, but as the tail
        // of ONE chin line rather than as forty-two of them (2026-09-08,
        // his ruling on the balloon: "make the bubble message only the fix
        // and make that small. the ST can have more detail"). Six instances
        // of seven wires is forty-two routine confirmations, and a balloon
        // that shows fifteen lines and then gives up buries the one line
        // that is not routine. The headline carries the count and the worst
        // case; the per-wire distances follow it and reach Status intact.
        var matchLines = new List<string>();
        double worstMatchDistance = -1.0;
        string worstMatchId = string.Empty;
        int worstMatchVertex = -1;

        // WHICH ANCHOR ROWS THIS DOCUMENT ACTUALLY LANDED WIRES ON, so the
        // independent witness below runs on the rows in use and says
        // nothing about a row no machine stands on. Ordered, so the
        // document and its chin are the same for the same payload.
        var rowsMatched = new SortedSet<int>();

        for (int i = 0; i < wireEntries.Count; i++)
        {
            (int side, int mechanism, int wireIndex,
                List<(MechanismFrame Frame, string Owner, int OwnerReel)> route) = wireEntries[i];
            if (i >= anchorFlat.Count)
            {
                warnings.Add(
                    $"wire (side {side}, mechanism {mechanism}, wire " +
                    $"{wireIndex}): no anchor node left to match against " +
                    $"({anchorFlat.Count} anchor node(s) found for " +
                    $"{wireEntries.Count} wire(s) authored, and each " +
                    "instance takes its own run of the anchors its row " +
                    "holds); dropped.");
                continue;
            }
            int netVertex = matchedVertices[i];
            AssertInRange(netVertex, vertexCount, "wires[].net_vertex");
            string id = $"{side}-{mechanism}-{wireIndex}";

            // R2, VALIDATED AFTER PLACEMENT (his ruling: planes[0] is the
            // net end; the door-guard pattern, not trust): transform the
            // route's own first and last local points through the
            // instance's placement and compare their distance to the
            // matched net vertex's world position. Also the "PRINTS ITS
            // DISTANCES" requirement: every match is named, not only a
            // wrong one, so a wire on the wrong anchor is visible rather
            // than merely possible.
            //
            // THESE THREE GUARDS RUN ON BOTH PLACEMENT PATHS, THE DERIVED
            // AND THE AUTHORED ALIKE (spec 7.2), and the test that follows
            // them through the document writer drives BOTH. The only thing
            // they ask for is an instance frame, and every instance carries
            // one whether Placement (PL) authored it or
            // MechanismCollector.DerivePlacements built it from the net's
            // own anchor rows. There is no override-only branch here to
            // move them out of, and no path they are skipped on.
            //
            // WHAT A DERIVED PLACEMENT'S OWN RESIDUAL PROVES, WHICH IS
            // NOTHING (spec 7.3, 7.5, and the reason this comment is here
            // rather than only in the spec). Since placement became DERIVED
            // by default, the transform is fitted to the very anchors these
            // wires are then matched against, so residualM reads 0.000000
            // on every correct instance AND on a routing tree authored
            // backwards: it measures the derivation's own fit and can never
            // report a fault in what was fitted. The match distance below
            // is a different number, taken between the placed route and the
            // net vertex the document itself chose, so it CAN differ from
            // its right value -- and it does, on an authored placement laid
            // out against the wrong anchors.
            //
            // WHAT THE MATCH DISTANCE DOES NOT PROVE, SAID HERE RATHER THAN
            // LEFT TO BE FOUND. On the DERIVED path it cannot separate a
            // backwards routing tree from a correct one, and since Task 7a
            // it cannot in the plainest possible way: this document now
            // binds each wire to the anchor the derivation PLACED it on
            // (the block above), so on a derived placement the distance
            // below reads zero on every instance, turned or not, correct or
            // backwards. It is the derivation's own fit measured a second
            // time, exactly as residualM is.
            //
            // WHAT IT DID READ BEFORE THAT, AND WHY IT MEANT NOTHING
            // EITHER: the two pairings disagreed on a turned instance, so a
            // seven-wire fixture on two rows printed 0.9, 0.6, 0.3, 0, 0.3,
            // 0.6, 0.9 m on its turned side whether the routing tree was
            // authored correctly or reversed, and drew four warnings on
            // CORRECT input. Those numbers measured the disagreement
            // between two rules, never the machine.
            //
            // THAT IS WHY THE WITNESS BELOW IS SOURCED FROM THE MACHINE'S
            // OWN DOCUMENT and not from anything on this path. The distance
            // still earns its keep on an AUTHORED placement, where the
            // anchors are his and the layout is his and the two can
            // genuinely disagree.
            if (eq is not null &&
                route.Count > 0 &&
                instanceFrames.TryGetValue(
                    (side, mechanism), out MechanismFrame? instanceFrame) &&
                instanceFrame is not null)
            {
                if (vertexRowIndex.TryGetValue(netVertex, out int matchedRow))
                    rowsMatched.Add(matchedRow);
                Point3Dto netPoint = eq.Vertices[netVertex];
                double[] netWorld = { netPoint.X, netPoint.Y, netPoint.Z };
                double[] firstWorld = TransformLocal(route[0].Frame.Origin, instanceFrame);
                double distFirst = MechanismCollector.Distance(firstWorld, netWorld);
                matchLines.Add(
                    $"wire {id}: matched net_vertex {netVertex}, first " +
                    "routing plane " +
                    distFirst.ToString("0.###", CultureInfo.InvariantCulture) +
                    " m from it.");
                if (distFirst > worstMatchDistance)
                {
                    worstMatchDistance = distFirst;
                    worstMatchId = id;
                    worstMatchVertex = netVertex;
                }

                // THE MATCH-DISTANCE CHECK, PROMOTED (finding 3's second
                // half): the note above is unconditional, "prints its
                // distances" whatever the answer; this is the door-guard
                // itself, a Warning the moment that distance exceeds a
                // tolerance built the same way AN/TT's own is -- a
                // multiple of the MATCHED row's own characteristic anchor
                // spacing -- so a wire latched to the wrong anchor is
                // named, not merely printed for him to notice by eye.
                double tolerance = Math.Max(
                    MechanismCollector.AnchorTieToleranceFactor *
                        vertexRowSpacing.GetValueOrDefault(netVertex, 0.0),
                    MechanismCollector.MinimumAnchorTieTolerance);
                if (distFirst > tolerance)
                {
                    warnings.Add(
                        $"wire {id}: matched net_vertex {netVertex} but " +
                        "sits " +
                        distFirst.ToString("0.###", CultureInfo.InvariantCulture) +
                        " m from it, farther than the door-guard " +
                        "tolerance of " +
                        tolerance.ToString("0.###", CultureInfo.InvariantCulture) +
                        " m (" +
                        MechanismCollector.AnchorTieToleranceFactor.ToString(
                            "0.#", CultureInfo.InvariantCulture) +
                        "x the matched row's own anchor spacing): this " +
                        "wire may be latched to the wrong anchor, or " +
                        "authored against a different solve.");
                }
                if (route.Count > 1)
                {
                    double[] lastWorld = TransformLocal(route[^1].Frame.Origin, instanceFrame);
                    double distLast = MechanismCollector.Distance(lastWorld, netWorld);
                    if (distLast < distFirst)
                    {
                        warnings.Add(
                            $"wire {id}: routing list appears REVERSED " +
                            "(last routing plane " +
                            distLast.ToString("0.###", CultureInfo.InvariantCulture) +
                            $" m from net_vertex {netVertex}, nearer than " +
                            "the first at " +
                            distFirst.ToString("0.###", CultureInfo.InvariantCulture) +
                            $" m); RT[{side}][{mechanism}][{wireIndex}]'s " +
                            "planes[0] should be authored at the net end, " +
                            "his ruling.");
                    }
                }
            }

            if (instanceWireIds.TryGetValue((side, mechanism), out List<string>? wireIds))
                wireIds.Add(id);

            (double resolvedReeveValue, string resolvedReeveSource) =
                ResolveWireReeve(wireIndex, route.Select(r => r.Frame).ToList());

            wiresOut.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["id"] = id,
                ["net_vertex"] = netVertex,
                // WHICH OF THE CITED MACHINE'S WIRES THIS IS, BY THE
                // AUTHORED WIRE NUMBER AND NEVER BY A POSITION (spec 5.4).
                // The machine document's own routing array is built from
                // routing.Where(Route.Count > 0).OrderBy(Wire), so it is
                // FILTERED AND COMPACTED: a machine authored with one
                // wire's frames missing shifts every entry after it, and a
                // study laid out on those offsets lands all seven cables on
                // real drums in a self-consistent arrangement, every one of
                // them wrong and nothing in the document to say so. A
                // reader MATCHES this against machine.routing[].wire; it
                // must never index with it. R1's whole point, applied to
                // the wire as it already is to the net vertex: the identity
                // travels, never the position.
                ["machine_wire"] = wireIndex,
                // THE RESOLVED VALUE, PER WIRE, NEVER INHERITED (finding 5,
                // spec 6.2): the same principle already applied to
                // net_vertex. A per-wire override (RW) beats the machine
                // default outright (spec 6.1); reeveFactorSource says
                // which one won ("wire" or "machine") so the studio, and
                // Param reading the document, never has to guess.
                ["reeveFactor"] = resolvedReeveValue,
                ["reeveFactorSource"] = resolvedReeveSource,
                // THE ORDERED PATH (A7): every wire this document derives
                // visits exactly one instance, so the list is length one
                // today; declared as a list rather than a single reference
                // so a future wire threaded through more than one unit
                // costs no reshape.
                ["path"] = new List<Dictionary<string, object?>>
                {
                    new(StringComparer.Ordinal) { ["side"] = side, ["mechanism"] = mechanism },
                },
                // THE ROUTE ITSELF (his construction, "create a circle on
                // each frame and loft"): the ordered local routing planes,
                // carried through unchanged so the studio builds the
                // identical tube this component's own Rhino preview would.
                // THE ROUTE ITSELF, WITH ITS OWNER (his wrapped-wire
                // ruling, 2026-09-08): carried straight through from the
                // collector's own classification, never recomputed here,
                // so the studio knows which frames to hold fixed in the
                // instance and which to rotate with a spinner.
                ["route"] = route
                    .Select(r => MechanismCollector.RouteFramePayload(r.Frame, r.Owner, r.OwnerReel))
                    .ToList(),
                // A wire is the machine reeling, not the works that remain
                // (Param's ruling; the field and its two values are
                // declared once, on MechanismCollector, and read here
                // unchanged).
                [MechanismCollector.PermanenceField] = MechanismCollector.Temporary,
            });
        }

        if (matchLines.Count > 0)
        {
            notes.Add(
                $"{matchLines.Count} wire(s) matched their net vertices; " +
                "worst first-plane distance " +
                worstMatchDistance.ToString("0.###", CultureInfo.InvariantCulture) +
                $" m (wire {worstMatchId} to net_vertex {worstMatchVertex}). " +
                "Every one is listed below, in Status." +
                Environment.NewLine +
                string.Join(Environment.NewLine, matchLines));
        }

        // THE INDEPENDENT WITNESS (spec 7.4): the anchor row's own
        // characteristic spacing against the cited machine's own
        // footprint.cableSpan.
        //
        // WHY THIS PAIR AND NO OTHER. Everything else the study document
        // could check a placement with is fed from the anchor rows the
        // placement was DERIVED FROM -- the residual, the instance frame,
        // the net vertex, the match distance -- so on the default path each
        // agrees with itself by construction and measures the derivation's
        // own fit rather than the layout. These two numbers have two
        // sources that never meet: the SPACING is the solved net's, read
        // off this Result's own anchor row, and the SPAN is the MACHINE's,
        // measured in the bench.machine/1 document by the Machine component
        // and carried here through the citation. They must agree for the
        // layout to make sense, and when they do not, one of them is about
        // a different machine or a different net.
        //
        // WHAT IT CATCHES that nothing else on the derived path can:
        //   1. A STALE OR WRONG CITED MACHINE. The id is written faithfully
        //      and never proved resolvable (there is no library index in
        //      this repo, spec 11.1), so a study laid out against one
        //      machine and citing another has, until now, produced a
        //      document in which every number agrees with every other.
        //   2. A ROUTING TREE AUTHORED BACKWARDS, where planes[0] is the
        //      drum end rather than the net end (R2). The machine's
        //      cableSpan is then the span of its DRUM BANK, and a bank that
        //      is not laid out at the springing's own pitch reads wrong
        //      here while the residual still reads 0.000000 m.
        //
        // IT HAS A CEILING AND NO FLOOR, deliberately, and the reason is
        // the same shape as MechanismReeve.SanityCeiling's. cableSpan is
        // measured between the machine's FIRST and LAST ROUTED WIRE by
        // number, not between the two furthest apart: a machine whose wires
        // are not numbered along its own cable line therefore reads SHORT,
        // legitimately, and a floor would warn on it. Nothing correct can
        // read LONG, because every one of those wire ends is meant to sit
        // on an anchor of this row and no two anchors of the row are
        // further apart than the row itself. A warning that fires on
        // correct input is a defect equal in seriousness to one that misses
        // a fault, so the half that cannot be told apart from correct
        // authoring is not checked at all.
        //
        // WHAT IT DOES NOT PROVE, said rather than left to be found: a
        // backwards routing tree whose drum bank happens to stand at the
        // springing's own pitch passes it, because then the two ends of
        // every wire are congruent point sets and NO measurement in this
        // document can tell one from the other. It also says nothing about
        // a machine that is merely in the wrong place along a row whose
        // spacing it does match.
        //
        // IT WARNS AND REFUSES NOTHING. Both numbers are honest
        // measurements of real geometry, and the study still animates: the
        // cables are drawn on the routes and anchors this document carries
        // whatever the machine document says. Refusing would cost him the
        // export over a disagreement he may be able to explain.
        if (machineCableSpan is double cableSpan && rowsMatched.Count > 0)
        {
            foreach (int row in rowsMatched)
            {
                double spacing = rowSpacing.GetValueOrDefault(row, 0.0);
                if (spacing <= 0.0 || machineWireCount < 2)
                    continue;
                double expected = spacing * (machineWireCount - 1);
                double tolerance = Math.Max(
                    MechanismCollector.AnchorTieToleranceFactor * spacing,
                    MechanismCollector.MinimumAnchorTieTolerance);
                if (cableSpan <= expected + tolerance)
                    continue;
                warnings.Add(
                    $"anchor row {row}: the cited machine \"{machineId}\" " +
                    "spans " +
                    cableSpan.ToString("0.###", CultureInfo.InvariantCulture) +
                    " m between its first and last cable, but this row's " +
                    "own anchors sit " +
                    spacing.ToString("0.###", CultureInfo.InvariantCulture) +
                    " m apart, so " + machineWireCount + " of them reach " +
                    "only " +
                    expected.ToString("0.###", CultureInfo.InvariantCulture) +
                    " m. THIS IS THE ONE CHECK ON A DERIVED PLACEMENT THAT " +
                    "IS NOT FED BY THE PLACEMENT: the spacing is the " +
                    "solved net's and the span is the machine document's, " +
                    "so a residual of 0.000000 m says nothing about it. " +
                    "Either the machine cited is not the machine this " +
                    "study was laid out against, or Routing (RT) is " +
                    "authored the other way round and planes[0] is the " +
                    "DRUM end rather than the net end (his ruling: " +
                    "planes[0] is the net end), which puts the drum bank's " +
                    "own span here in place of the cable line's.");
            }
        }

        // THE WIRE COUNT CROSS-CHECK, AND IT IS AN EQUALITY (spec 5.5).
        //
        // WHY A RANGE WOULD AGREE WITH THE CODE BY COINCIDENCE:
        // MechanismCollector.PlacementGroupSize is a compile-time SEVEN and
        // it drives the derivation loop, the placement override's own
        // plane-count refusal and the study's wire emit loop alike. Ruling
        // 1.2 lets him author a machine with any number of wires, so a
        // study citing a TWELVE-wire machine writes twelve in its citation
        // and exactly seven wires -- and "every wire lies in
        // [0, wireCount)" passes, since 0 to 6 all lie inside 0 to 11. The
        // document validates, seven cables animate, five are simply absent
        // and nothing says so. Counted PER INSTANCE, because that is the
        // unit a machine is placed as: one instance is one machine, and one
        // machine's wires are the count it declares.
        //
        // IT WARNS RATHER THAN REFUSING, deliberately. Both numbers reach
        // the document -- the citation's wireCount, and the wires
        // themselves -- so the mismatch is visible in the artefact as well
        // as in the chin, and refusing would leave a study whose machine
        // has more wires than this collector can place with no export at
        // all rather than an export he can see is short. That is a ruling
        // to revisit the day PlacementGroupSize stops being a constant.
        foreach (KeyValuePair<(int Side, int Mechanism), List<string>> instance in
            instanceWireIds.OrderBy(p => p.Key.Side).ThenBy(p => p.Key.Mechanism))
        {
            if (instance.Value.Count == machineWireCount)
                continue;
            warnings.Add(
                $"instance (side {instance.Key.Side}, mechanism " +
                $"{instance.Key.Mechanism}) places {instance.Value.Count} " +
                $"wire(s), but the cited machine \"{machineId}\" declares a " +
                $"wireCount of {machineWireCount}. One wire is one cable on " +
                "one drum, so the two numbers must be EQUAL: where this " +
                "instance places fewer, the missing cables are simply " +
                "absent from the animation and nothing else in the document " +
                "says so, and where it places more, wires are being drawn " +
                "that the machine has no drum for. Check that every wire " +
                "the machine routes is authored in Routing (RT) here, and " +
                "that the net has an anchor for each of them.");
        }

        // DECLARE THE PRINCIPAL ROWS (studio's C6/A6): the ordered net
        // vertices of each principal run, so their side can drop its own
        // clustering/nearest-vertex derivation and treat this as the
        // authority (their derivation stays their fallback for a study with
        // no mechanism document). Emitted whenever the net solved at all;
        // empty when there is nothing to walk, never omitted.
        List<List<int>> principalRuns = eq is null
            ? new List<List<int>>()
            : MouldGeometry.PrincipalRuns(eq, vertexCount);
        var principalRowsOut = new List<IReadOnlyList<int>>(principalRuns.Count);
        foreach (List<int> run in principalRuns)
            principalRowsOut.Add(run);

        // THE STUDY DOCUMENT CARRIES NO MACHINE BODIES AT ALL (spec 2.2),
        // and this is the line the whole rework exists for. What survives
        // into it is an ALLOWLIST, not a list of things to drop: the two
        // permanent works the study's own ports carry (ruling 1.1), and the
        // facts about the CABLE that a reader needs to draw the wires this
        // document does carry. Frame 1, Frame 2, the Motors, the reels and
        // the spool radius are the machine's, they live in the
        // bench.machine/1 document the citation names, and a study that
        // restated any of them would be restating a fact that can go stale
        // the moment the machine is re-authored.
        //
        // AN ALLOWLIST RATHER THAN A DENYLIST because the leak this guards
        // against is not only the five keys named above. A payload reaching
        // here was not necessarily written by this collector, and a
        // denylist admits every key nobody has thought of yet -- which for
        // a body is tens of megabytes travelling in silence.
        //
        // spoolRadius IS DROPPED RATHER THAN CARRIED, and that is a real
        // change for a reader. On the study side it would now be derived
        // from the tension tie's own bounding box, since no reel reaches
        // this build any more: a plausible number, measured from the wrong
        // object. The radii are the machine's, per reel entry, in the
        // machine document (its own windingRadius, and the median
        // spoolRadius beside it), and the rotation block below says so.
        object? mechanismOut = null;
        if (mechanismIn.ValueKind == JsonValueKind.Object)
        {
            var studyMechanism = new Dictionary<string, object?>(StringComparer.Ordinal);
            foreach (string key in StudyMechanismKeys)
            {
                if (mechanismIn.TryGetProperty(key, out JsonElement kept) &&
                    kept.ValueKind != JsonValueKind.Null)
                {
                    studyMechanism[key] = kept;
                }
            }
            mechanismOut = studyMechanism;
        }

        var anchorsOut = new List<JsonElement>();
        if (anchorsIn.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement anchor in anchorsIn.EnumerateArray())
                anchorsOut.Add(anchor);
        }
        var tensionTiesOut = new List<JsonElement>();
        if (tiesIn.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement tie in tiesIn.EnumerateArray())
                tensionTiesOut.Add(tie);
        }

        var payload = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["schema"] = Schema,
            ["study"] = study,
            ["units"] = "m",
            ["lengthUnitToMetres"] = unitFactor,
            ["vertexCount"] = vertexCount,
            ["columnNodeCount"] = columnNodeCount,
            // THE CITATION (ruling 1.2, spec 5.3): this study's ONE
            // machine, by the minted id, and the machine's own schema
            // beside it so a reader knows what kind of document to go and
            // fetch. This is the whole of the machine that reaches a study
            // now: no frame, no motors, no reels, no radii.
            //
            // wireCount IS A COPY, taken at export time, and it is here
            // because it is the number every wire in this document is
            // checked against, one for one. If the machine is re-authored
            // with a different number of wires afterwards, this study still
            // says what it was laid out against, which is the honest answer
            // and the one that makes the disagreement findable.
            //
            // THE REEVE DEFAULT IS NOT COPIED HERE. Every wire below
            // carries its own RESOLVED factor and the source that won it,
            // so a reader needs nothing else; restating the machine's
            // default beside them would be a second number that can go
            // stale against the first while both stay plausible.
            ["machine"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["schema"] = MechanismCollector.MachineSchema,
                ["id"] = machineId,
                ["name"] = machineName,
                ["wireCount"] = machineWireCount,
                ["how"] = "THIS STUDY CITES ONE MACHINE AND CARRIES NONE " +
                    "OF IT. Resolve the id against the " +
                    MechanismCollector.MachineSchema + " document of the " +
                    "same id: the frames, the motors, the reel entries, " +
                    "their bodies and their winding radii are all there, " +
                    "and none of them is here. MATCH A WIRE TO A MACHINE " +
                    "WIRE BY wires[].machine_wire AGAINST THAT DOCUMENT'S " +
                    "routing[].wire, NEVER by position: its routing array " +
                    "carries only the wires that were routed, in wire " +
                    "order, so a machine authored with one wire's frames " +
                    "missing shifts every entry after it and an offset " +
                    "would land every cable on a real drum in a " +
                    "self-consistent arrangement, every one of them wrong. " +
                    "AND COMPARE wireCount WITH THE WIRES THIS DOCUMENT " +
                    "CARRIES, per instance: they are written to be EQUAL, " +
                    "and where they are not, the cables this document is " +
                    "short of are simply absent from the animation, with " +
                    "nothing else in it to say so.",
            },
            // THE SHARED-NUMBERING GUARANTEE, DECLARED (studio's C2/A2):
            // measured true on two real exports, and now written into the
            // schema as a promise rather than left as a coincidence a
            // reader discovers by measuring a third one.
            // THE column_node CLAIM WAS STRUCK (audit finding 2's own sub-
            // issue): no object this writer ever emits carries a key named
            // column_node -- it was leftover language from the earlier
            // P-004 wire shape, which did not survive the INPUT MODEL's
            // collapse to one generic wire shape. A promise this document
            // does not keep is worse than no promise at all; the reader's
            // own invariant 3, which still quotes it back, needs its own
            // re-diff against this document on the studio side.
            ["numbering"] = "net_vertex indices are the same numbering as " +
                "the form document's equilibrium.vertices and the " +
                "formwork document's frames[].vertices for this study, by " +
                "construction, in every frame including frame 0 (numbering, " +
                "not position: only the LAST frame's positions equal the " +
                "form document's equilibrium).",
            // THE ROTATION DECLARATION (studio's C3/A3): the spin the
            // driven spinner turns, stated as unit, sign and reference
            // rather than left for the reader to guess from a bare
            // formula. The studio derives the angle; nothing here is
            // per-frame.
            ["rotation"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["unit"] = "turns",
                ["reference"] = "frame0",
                ["sign"] = "positive turns take up wire: the spool winds " +
                    "in and the wire's routed length shortens. Negative " +
                    "pays out.",
                ["formula"] = "turns = (length_at(frame0) - length_at(t)) " +
                    "* reeveFactor / (2 * pi * windingRadius), where " +
                    "length_at(t) is the run of NET CABLE the wire pulls " +
                    "at frame t -- the rib leaving its anchor and climbing " +
                    "the vault -- halved between the two machines that " +
                    "pull it. THE RADIUS COMES FROM THE CITED MACHINE'S " +
                    "OWN DOCUMENT (see the machine block above), not from " +
                    "this one, which carries no reels at all since the " +
                    "machine left the study. WHICH reel a given wire rides " +
                    "is NOT PUBLISHED ANYWHERE TODAY, and this document " +
                    "will not pretend it is: the machine document's own " +
                    "routing frames carry no owner and no ownerReel, and " +
                    "this document's frames carry ownerReel -1 with owner " +
                    "\"body\" on every frame, because the reels left the " +
                    "study when the machine split out of it. Binding a " +
                    "wire to its drum is an OPEN ITEM on the plugin side, " +
                    "registered as a running deferral in its own test " +
                    "harness. Until it is closed, use the cited machine's " +
                    "bank: bank.radius is the median winding radius across " +
                    "the entries whose bodies terminate wire routes, which " +
                    "is the spools and not the pulleys, so it is the right " +
                    "median for a take-up rate even though it is one " +
                    "number for every wire. A pulley and a spool do not " +
                    "share a radius, so do NOT fall back to the machine's " +
                    "own spoolRadius, which is medianed over a wider " +
                    "population. THE SUBTRACTION IS frame0 MINUS " +
                    "t, not the other way about, so that taking up reads " +
                    "POSITIVE and agrees with the sign sentence: reeling " +
                    "in SHORTENS what is pulled, so frame0 minus t grows. " +
                    "The delta is always measured from frame 0, never the " +
                    "previous frame, so the result is a pure function of t " +
                    "and safe to scrub or play out of order. THIS " +
                    "DEFINITION REPLACES 'the free span from the net " +
                    "vertex to the first routing frame', which is ZERO at " +
                    "every frame on every study: route[0] IS the anchor, " +
                    "and an anchor is a fixed support, so that reading can " +
                    "only ever return about nothing.",
                ["wrapIsAuthored"] = true,
                ["wrapNote"] = "THE WIRE'S WRAP IS ALREADY IN THE FRAMES " +
                    "(his ruling, 2026-09-09, verbatim: \"the frames i " +
                    "give you already spool for you. I dont wish for you " +
                    "to spool any more or less, just assume with rotation " +
                    "that the spooling happens\"). The routing planes " +
                    "carry the wire as it is wound, so a reader draws them " +
                    "as they arrive and NEVER synthesises further turns, " +
                    "unwinds the authored ones, or pays wire on or off as " +
                    "the rotation changes. The turns above are what the " +
                    "DRUM does; they are not a driver of the wire's own " +
                    "geometry, which is authored and final.",
            },
            ["principalRows"] = principalRowsOut,
            ["mechanism"] = mechanismOut,
            ["instances"] = instancesOut,
            ["anchors"] = anchorsOut,
            ["tensionTies"] = tensionTiesOut,
            ["wires"] = wiresOut,
        };
        return JsonSerializer.Serialize(payload, ContractJson.Options);
    }

    private static void AssertInRange(int value, int count, string label)
    {
        if (value < 0 || value >= count)
        {
            throw new InvalidOperationException(
                $"{label} = {value} is out of range for a net/column set " +
                $"of {count}; a mechanism document is not written from a " +
                "wire mapping that cannot be resolved.");
        }
    }

    /// <summary>
    /// A frame from the collector's payload. Z is READ where the payload
    /// carries it, which every payload this plugin writes now does, and
    /// falls back to X cross Y where it does not. The fallback is right for
    /// every right-handed frame and is the only sane reading available for a
    /// payload written before Z travelled; a REFLECTED frame always carries
    /// its own Z, so the fallback can never silently mirror anything.
    /// </summary>
    private static MechanismFrame ReadFrame(JsonElement element)
    {
        double[] origin = ReadTripleRaw(element.GetProperty("origin"));
        double[] xAxis = ReadTripleRaw(element.GetProperty("xAxis"));
        double[] yAxis = ReadTripleRaw(element.GetProperty("yAxis"));
        double[] zAxis = element.TryGetProperty("zAxis", out JsonElement z)
            ? ReadTripleRaw(z)
            : Cross(xAxis, yAxis);
        return new MechanismFrame(origin, xAxis, yAxis, zAxis);
    }

    /// <summary>
    /// The plain arithmetic mean of a set of world points: the row-to-side
    /// pairing's own probe point (finding 3), for both an anchor row's
    /// nodes and a side's own placed instances. The origin for an empty
    /// set, which the caller never actually hands it (both call sites
    /// guard the shapes that would).
    /// </summary>
    private static double[] Centroid(IReadOnlyList<double[]> points)
    {
        if (points.Count == 0)
            return new double[] { 0.0, 0.0, 0.0 };
        double x = 0.0, y = 0.0, z = 0.0;
        foreach (double[] p in points)
        {
            x += p[0];
            y += p[1];
            z += p[2];
        }
        return new[] { x / points.Count, y / points.Count, z / points.Count };
    }

    private static double[] ReadTripleRaw(JsonElement array) =>
        array.EnumerateArray().Select(e => e.GetDouble()).ToArray();

    /// <summary>
    /// A LOCAL POINT, TRANSFORMED THROUGH AN AUTHORED PLACEMENT FRAME:
    /// origin plus x*xAxis plus y*yAxis plus z*zAxis, zAxis derived by hand
    /// (xAxis cross yAxis) rather than through
    /// <c>Vector3d.CrossProduct</c>/<c>Plane</c>: measured (this harness's
    /// own MechanismDocument check), RhinoCommon's native convenience
    /// members throw <c>DllNotFoundException</c> outside Rhino, which is
    /// exactly why <see cref="ColumnsMesh"/>'s own <c>Cross</c> helper
    /// already reimplements the cross product rather than calling it --
    /// the precedent this follows. Plain <c>double[]</c> throughout, since
    /// placement is now authored, not computed, and none of this needs a
    /// Rhino type at all.
    /// </summary>
    private static double[] TransformLocal(double[] localPoint, MechanismFrame frame)
    {
        // Z IS CARRIED, NEVER DERIVED. X cross Y is the true Z only for a
        // RIGHT-handed frame; an instance frame on Param's mirrored side is a
        // REFLECTION, where X cross Y points the opposite way, and a local
        // point with an out-of-plane component would land on the wrong side.
        double[] z = frame.ZAxis;
        double x = localPoint[0];
        double y = localPoint[1];
        double zc = localPoint[2];
        return new[]
        {
            frame.Origin[0] + (x * frame.XAxis[0]) + (y * frame.YAxis[0]) + (zc * z[0]),
            frame.Origin[1] + (x * frame.XAxis[1]) + (y * frame.YAxis[1]) + (zc * z[1]),
            frame.Origin[2] + (x * frame.XAxis[2]) + (y * frame.YAxis[2]) + (zc * z[2]),
        };
    }

    private static double[] Cross(double[] a, double[] b) => new[]
    {
        (a[1] * b[2]) - (a[2] * b[1]),
        (a[2] * b[0]) - (a[0] * b[2]),
        (a[0] * b[1]) - (a[1] * b[0]),
    };
}
