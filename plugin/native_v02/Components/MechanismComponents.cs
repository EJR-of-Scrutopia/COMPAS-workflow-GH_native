#nullable enable

using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;
using System.Text.Json;
using Ananke.COMPAS.Native.Contracts;
using Grasshopper.Kernel;
using Grasshopper.Kernel.Data;
using Grasshopper.Kernel.Types;
using Rhino.Geometry;

namespace Ananke.COMPAS.Native.Components;

/// <summary>
/// The fourth sibling document's SHAPE, plain and Rhino-free so the harness
/// can drive every rule below with arrays it builds itself, exactly the way
/// <see cref="TessellationCell"/> keeps Export's own cells Rhino-free.
///
/// This is the collector's OWN packaging model: the meshes, axes, sockets and
/// declared facts as Param wires them, validated and reduced to plain data on
/// the solve thread (Rhino access happens in
/// <see cref="MechanismCollectorComponent"/> only). What is NOT here is any
/// placement: the spec's section 4 has the plugin compute instances from the
/// Result it already owns, and that Result belongs to Export, not to this
/// collector, so placement is built in <see cref="MechanismDocument"/>
/// alongside the formwork document it already sits beside.
/// </summary>
internal sealed record MechanismMesh(
    IReadOnlyList<double[]> Vertices,
    IReadOnlyList<int[]> Faces);

/// <summary>One spinner's rotation axis, unit-local: a point on it and its direction.</summary>
internal sealed record MechanismAxis(double[] Origin, double[] Direction);

/// <summary>One routing (or placement) frame, unit-local unless stated otherwise.</summary>
internal sealed record MechanismFrame(double[] Origin, double[] XAxis, double[] YAxis);

/// <summary>
/// One spinner as PU/AX hand it in: a mesh and, when AX carried a matching
/// plane, its axis. A null <see cref="Axis"/> is what makes the door-guard
/// refuse this spinner's whole unit (spec 3a: "a spinner mesh in PU with no
/// matching plane in AX is refused").
/// </summary>
internal sealed record MechanismSpinnerInput(
    MechanismMesh Mesh,
    MechanismAxis? Axis,
    string MaterialTag);

/// <summary>
/// One pulley type's whole contribution (PU's {type} branch plus AX/PS/PR/SR
/// at that same type), before validation.
/// </summary>
internal sealed record MechanismUnitInput(
    int Type,
    MechanismMesh? Body,
    string BodyMaterialTag,
    IReadOnlyList<MechanismSpinnerInput> Spinners,
    IReadOnlyList<MechanismFrame> Sockets,
    double? ReeveFactor,
    double? SpoolRadius);

/// <summary>One AT row: the authored tie mesh, its world-space centroid, and its tag.</summary>
internal sealed record MechanismAnchorTieInput(
    MechanismMesh Mesh,
    double[] Centroid,
    string MaterialTag);

/// <summary>
/// One anchor row's node points, world space, in the walking order
/// <c>MouldGeometry.ConnectedGroups</c> returns -- the same order AT's own
/// row numbering follows (requirements doc section 2).
/// </summary>
internal sealed record MechanismAnchorRow(IReadOnlyList<double[]> NodePoints);

/// <summary>
/// The pure packaging and door-guard logic behind the MECHANISM collector:
/// no Rhino type crosses this boundary, so the harness can drive every rule
/// with arrays it builds itself.
///
/// ONE JOB: turn what was wired into one JSON payload Export can embed, and
/// say by name what could not be trusted rather than silently dropping it or
/// silently accepting it. Placement (the plugin's other half, spec section 4)
/// is not this class's concern; it is built by <see cref="MechanismDocument"/>
/// from the Result Export already owns.
/// </summary>
internal static class MechanismCollector
{
    public const string EdgeTypeName = "edge";
    public const string NodeTypeName = "node";

    /// <summary>
    /// How far an anchor tie may sit from the nearest node of its own row
    /// before the door-guard names it: a multiple of the row's OWN
    /// characteristic anchor spacing, so the tolerance scales with the study
    /// rather than assuming a unit. No numeric ruling from Param exists yet
    /// for this figure; three times the row's own spacing is generous enough
    /// that an authored-in-place tie never trips it by construction, while a
    /// tie left over from a different solve, whose anchors sit rows apart,
    /// still does.
    /// </summary>
    public const double AnchorTieToleranceFactor = 3.0;

    public const double MinimumAnchorTieTolerance = 1.0e-6;

    public const double MinimumSpoolRadius = 1.0e-6;

    /// <summary>
    /// Build the mechanism payload, or null when nothing was wired at all
    /// (spec section 8 item 6: "the collector with NOTHING wired produces no
    /// mechanism document and no warning noise"). <paramref name="warnings"/>
    /// and <paramref name="notes"/> are appended to, never cleared, so a
    /// caller can pool them across a whole solve's chin.
    /// </summary>
    public static string? Build(
        IReadOnlyList<MechanismUnitInput> units,
        IReadOnlyList<MechanismAnchorTieInput> ties,
        IReadOnlyList<MechanismAnchorRow>? rows,
        List<string> warnings,
        List<string> notes)
    {
        ArgumentNullException.ThrowIfNull(units);
        ArgumentNullException.ThrowIfNull(ties);
        ArgumentNullException.ThrowIfNull(warnings);
        ArgumentNullException.ThrowIfNull(notes);

        if (units.Count == 0 && ties.Count == 0)
            return null;

        var unitPayloads = new Dictionary<string, object?>(StringComparer.Ordinal);
        foreach (MechanismUnitInput unit in units)
        {
            string typeName = TypeName(unit.Type);
            if (typeName.Length == 0)
            {
                warnings.Add(
                    $"PU branch {{{unit.Type}}} is neither 0 (edge reel) nor " +
                    "1 (node reel); ignored.");
                continue;
            }
            if (unit.Body is null)
            {
                warnings.Add(
                    $"{typeName}: PU carries no part 0 (the static body); " +
                    "a mechanism with no body is not a mechanism, so this " +
                    "unit is dropped.");
                continue;
            }
            MechanismMesh body = unit.Body;

            var spinnerPayloads = new List<Dictionary<string, object?>>(unit.Spinners.Count);
            bool refused = false;
            for (int i = 0; i < unit.Spinners.Count; i++)
            {
                MechanismSpinnerInput spinner = unit.Spinners[i];
                if (spinner.Axis is null)
                {
                    warnings.Add(
                        $"{typeName} spinner {i + 1}: PU carries a mesh but " +
                        "AX carries no matching axis; the axis is authored, " +
                        "never inferred (spec 3a), so this unit is refused.");
                    refused = true;
                    continue;
                }
                spinnerPayloads.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["mesh"] = MeshPayload(spinner.Mesh, null),
                    ["axis"] = new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["origin"] = spinner.Axis.Origin,
                        ["direction"] = spinner.Axis.Direction,
                    },
                    ["materialTag"] = spinner.MaterialTag,
                    // spinners[0] (PU's part 1) is the driven spool, the one
                    // spinner section 5's derived rotation ever turns
                    // (requirements doc section 1); anything after it is a
                    // cosmetic wheel, carried but not rotated.
                    ["driven"] = i == 0,
                });
            }
            if (refused)
                continue;

            double reeveFactor = unit.ReeveFactor ?? 1.0;
            double spoolRadius;
            if (unit.SpoolRadius is double declared)
            {
                spoolRadius = declared;
            }
            else
            {
                MechanismMesh boundingSource =
                    unit.Spinners.Count > 0 ? unit.Spinners[0].Mesh : body;
                spoolRadius = Math.Max(
                    SmallestBoundingDimension(boundingSource) / 4.0,
                    MinimumSpoolRadius);
                notes.Add(
                    $"{typeName}: SR defaulted to " +
                    spoolRadius.ToString("0.####", CultureInfo.InvariantCulture) +
                    (unit.Spinners.Count > 0
                        ? " from the spool's own bounding box (smallest " +
                          "dimension over 4)."
                        : " from the body's own bounding box (smallest " +
                          "dimension over 4), since this unit carries no " +
                          "spinner."));
            }

            unitPayloads[typeName] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["body"] = MeshPayload(body, unit.BodyMaterialTag),
                ["spinners"] = spinnerPayloads,
                ["sockets"] = unit.Sockets.Select(FramePayload).ToList(),
                ["reeveFactor"] = reeveFactor,
                ["spoolRadius"] = spoolRadius,
            };
        }

        var tiePayloads = new List<Dictionary<string, object?>>(ties.Count);
        if (ties.Count > 0 && rows is null)
        {
            warnings.Add(
                $"AT carries {ties.Count} anchor tie mesh(es) but no Result " +
                "was wired to Mechanism: the door-guard proximity check " +
                "against the anchor rows could not run, and each tie's row " +
                "is its own position in AT, unconfirmed.");
        }
        for (int i = 0; i < ties.Count; i++)
        {
            MechanismAnchorTieInput tie = ties[i];
            if (rows is not null)
            {
                if (i >= rows.Count)
                {
                    warnings.Add(
                        $"AT[{i}] has no matching anchor row (only " +
                        $"{rows.Count} found by the solved net); its row " +
                        "index is unvalidated.");
                }
                else if (rows[i].NodePoints.Count == 0)
                {
                    warnings.Add(
                        $"anchor row {i} carries no anchor nodes; AT[{i}] " +
                        "cannot be validated against it.");
                }
                else
                {
                    IReadOnlyList<double[]> nodePoints = rows[i].NodePoints;
                    double nearest = nodePoints
                        .Select(p => Distance(p, tie.Centroid))
                        .Min();
                    double tolerance = Math.Max(
                        AnchorTieToleranceFactor * CharacteristicSpacing(nodePoints),
                        MinimumAnchorTieTolerance);
                    if (nearest > tolerance)
                    {
                        warnings.Add(
                            $"AT[{i}] sits " +
                            nearest.ToString("0.###", CultureInfo.InvariantCulture) +
                            $" from anchor row {i} (nearest anchor node), " +
                            "farther than the door-guard tolerance of " +
                            tolerance.ToString("0.###", CultureInfo.InvariantCulture) +
                            $" ({AnchorTieToleranceFactor.ToString("0.#", CultureInfo.InvariantCulture)}x " +
                            "the row's own anchor spacing): this tension " +
                            "tie may be authored against a different solve.");
                    }
                }
            }
            tiePayloads.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["row"] = i,
                ["mesh"] = MeshPayload(tie.Mesh, null),
                ["materialTag"] = tie.MaterialTag,
                // ONE PLACEMENT CONVENTION (studio's C5/A5): the fused tie
                // and rail is authored in place and exported in world
                // coordinates already, unlike the reels which are type plus
                // instance placement. Rather than let the reader infer that
                // from "this kind has no frame", the flag says so directly:
                // the studio trusts this word, not the kind, per their ask.
                ["placement"] = "world",
            });
        }

        var payload = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["unitTypes"] = unitPayloads,
            ["anchorTies"] = tiePayloads,
        };
        return JsonSerializer.Serialize(payload, ContractJson.Options);
    }

    public static string TypeName(int type) => type switch
    {
        0 => EdgeTypeName,
        1 => NodeTypeName,
        _ => string.Empty,
    };

    private static Dictionary<string, object?> MeshPayload(
        MechanismMesh mesh, string? materialTag)
    {
        var payload = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["vertices"] = mesh.Vertices,
            ["faces"] = mesh.Faces,
        };
        if (materialTag is not null)
            payload["materialTag"] = materialTag;
        return payload;
    }

    private static Dictionary<string, object?> FramePayload(MechanismFrame frame) =>
        new(StringComparer.Ordinal)
        {
            ["origin"] = frame.Origin,
            ["xAxis"] = frame.XAxis,
            ["yAxis"] = frame.YAxis,
        };

    /// <summary>
    /// The smallest of the three world-axis extents of a mesh's own
    /// vertices: SR's declared default source (settled section 3a: "the
    /// {part} 1 spinner's (the spool's) bounding box smallest dimension over
    /// 4"). Zero for an empty mesh, which the caller floors at
    /// <see cref="MinimumSpoolRadius"/> rather than dividing by it.
    /// </summary>
    internal static double SmallestBoundingDimension(MechanismMesh mesh)
    {
        if (mesh.Vertices.Count == 0)
            return 0.0;
        double[] min = { double.MaxValue, double.MaxValue, double.MaxValue };
        double[] max = { double.MinValue, double.MinValue, double.MinValue };
        foreach (double[] v in mesh.Vertices)
        {
            for (int axis = 0; axis < 3; axis++)
            {
                if (v[axis] < min[axis])
                    min[axis] = v[axis];
                if (v[axis] > max[axis])
                    max[axis] = v[axis];
            }
        }
        return Math.Min(max[0] - min[0], Math.Min(max[1] - min[1], max[2] - min[2]));
    }

    internal static double Distance(double[] a, double[] b)
    {
        double dx = a[0] - b[0];
        double dy = a[1] - b[1];
        double dz = a[2] - b[2];
        return Math.Sqrt((dx * dx) + (dy * dy) + (dz * dz));
    }

    /// <summary>
    /// The row's own typical anchor-to-anchor gap: the mean of its
    /// consecutive point distances, in walking order. Zero for a row of one
    /// (or none), which the caller floors rather than lets zero the whole
    /// tolerance.
    /// </summary>
    internal static double CharacteristicSpacing(IReadOnlyList<double[]> points)
    {
        if (points.Count < 2)
            return 0.0;
        double total = 0.0;
        for (int i = 0; i + 1 < points.Count; i++)
            total += Distance(points[i], points[i + 1]);
        return total / (points.Count - 1);
    }
}

/// <summary>
/// The anchor-row geometry the door-guard (and, from Export, the edge-reel
/// placement) both read off a solved Result: the same grouping
/// <c>MouldGeometry.ConnectedGroups</c>/<c>GroupingAdjacency</c> already give
/// Diagnose's own "every anchor is in a strip of its own" check
/// (requirements doc section 2), so an edge-reel row and an anchor-tie row
/// can never disagree about what a row is.
/// </summary>
internal static class MechanismGeometry
{
    /// <summary>
    /// Every anchor row's NODE INDICES, in <c>ConnectedGroups</c>' own
    /// order. The one place this grouping is computed, so the door-guard's
    /// rows (points only) and Export's placement/wires (indices) can never
    /// disagree about what a row is. Empty when the Result carries no
    /// equilibrium or no anchors.
    /// </summary>
    public static List<List<int>> AnchorRowIndices(ResultDto result)
    {
        ArgumentNullException.ThrowIfNull(result);
        EquilibriumResultDto? eq = result.Equilibrium;
        if (eq is null || eq.Vertices.Count == 0)
            return new List<List<int>>();
        int n = eq.Vertices.Count;
        (int, int)[] edges = MouldGeometry.ValidEdges(eq, n, out _);
        List<int>[] grouping = MouldGeometry.GroupingAdjacency(result, edges, n);
        var anchors = new List<int>();
        foreach (int id in eq.ResolvedSupportNodeIds)
        {
            if (id >= 0 && id < n)
                anchors.Add(id);
        }
        return MouldGeometry.ConnectedGroups(anchors, grouping);
    }

    /// <summary>
    /// Every anchor row, in the same order, as world-space points: the
    /// door-guard's own read of <see cref="AnchorRowIndices"/>.
    /// </summary>
    public static List<MechanismAnchorRow> AnchorRows(ResultDto result)
    {
        EquilibriumResultDto? eq = result.Equilibrium;
        List<List<int>> groups = AnchorRowIndices(result);
        var rows = new List<MechanismAnchorRow>(groups.Count);
        foreach (List<int> group in groups)
        {
            var points = new List<double[]>(group.Count);
            foreach (int id in group)
            {
                Point3Dto p = eq!.Vertices[id];
                points.Add(new[] { p.X, p.Y, p.Z });
            }
            rows.Add(new MechanismAnchorRow(points));
        }
        return rows;
    }
}

/// <summary>
/// MECHANISM ("ME"): the collector for the fourth sibling document, feeding
/// Export beside RES and Cells exactly as the spec's section 3 describes.
///
/// Every port is optional and every one is a tree except AT and RES, so an
/// author who wants only a pulley unit, only a tension tie, or nothing at
/// all can wire exactly that. Nothing here places anything: PU/AX/PS/PR/SR
/// travel unit-local and AT travels in world coordinates exactly as
/// authored, validated rather than placed (the door-guard rule). Result
/// (RES) is wired ONLY so that door-guard has anchor rows to check AT
/// against; placement itself is Export's job, against the Result it already
/// owns.
///
/// Nothing wired produces an empty Payload and a quiet chin (spec section 8
/// item 6): Export reads an empty Payload as "no mechanism document for this
/// study" exactly the way it reads no Cells as "no skin document".
/// </summary>
public sealed class MechanismCollectorComponent : NativeComponentBase
{
    public MechanismCollectorComponent()
        : base(
            "Mechanism",
            "ME",
            "Collect the reeling machine's authored parts -- the pulley " +
            "units and their spinners with their own rotation axes, the " +
            "wire routing, the reeve factor and spool radius, and the " +
            "anchor tie authored in place -- and validate them into one " +
            "payload for Export's mechanism document. Nothing wired " +
            "produces nothing: this is the fourth sibling document, and " +
            "it is optional per study.",
            ComponentCategories.Deliver,
            "mechanism")
    {
    }

    public override Guid ComponentGuid =>
        new("6b2e9f14-8a3d-4c7e-9f21-5d0a7c3e9b41");

    protected override void RegisterInputParams(GH_InputParamManager parameters)
    {
        parameters.AddParameter(
            new ResultParam(),
            "Result",
            "RES",
            "The solved Result, wired ONLY so the anchor tie (AT) can be " +
            "validated against the anchor rows it should sit beside. " +
            "Placement is not computed here (Export owns that); AT wired " +
            "with no Result here is accepted but its proximity check is " +
            "skipped and said so.",
            GH_ParamAccess.item);
        parameters[0].Optional = true;
        parameters.AddMeshParameter(
            "Pulley Units",
            "PU",
            "One mesh per part, as a tree path {type}{part}: type 0 is " +
            "the edge reel (anchor-line unit), type 1 the node reel " +
            "(principal-node unit); within a type, part 0 is ALWAYS the " +
            "static body and part 1..N are the spinners in order. A type " +
            "with only part 0 is a legal fully-static unit. A missing " +
            "type means the machine has no reels of that kind.",
            GH_ParamAccess.tree);
        parameters[1].Optional = true;
        parameters.AddPlaneParameter(
            "Spinner Axes",
            "AX",
            "One rotation-axis plane per spinner, matching Pulley Units' " +
            "{type}{part} path for part >= 1 only: plane origin is a " +
            "point on the axis, plane Z is the axis direction, both in " +
            "the unit's own local space. A spinner mesh with no matching " +
            "axis here is refused: the axis is authored, never inferred.",
            GH_ParamAccess.tree);
        parameters[2].Optional = true;
        parameters.AddPlaneParameter(
            "Sockets",
            "PS",
            "The wire's routing frames through one unit type, in WIRE " +
            "ORDER, unit-local space: one branch per {type} (matching " +
            "Pulley Units' outer index only, not part), items in the " +
            "order the wire passes them. A type with no branch here " +
            "routes with no via points.",
            GH_ParamAccess.tree);
        parameters[3].Optional = true;
        parameters.AddNumberParameter(
            "Reeve Factor",
            "PR",
            "Rope crossing the spool per unit of net-side length change, " +
            "one number per {type}; default 1.0 when a type's branch is " +
            "absent or empty.",
            GH_ParamAccess.tree);
        parameters[4].Optional = true;
        parameters.AddNumberParameter(
            "Spool Radius",
            "SR",
            "One number per {type}; when absent, defaulted from the " +
            "part 1 spinner's own bounding box (smallest dimension over " +
            "4), or the body's when the type carries no spinner, and " +
            "said in the chin so the default is never silent.",
            GH_ParamAccess.tree);
        parameters[5].Optional = true;
        parameters.AddMeshParameter(
            "Anchor Ties",
            "AT",
            "The sliding ground bar, anchor clamps and column tension " +
            "tie as ONE authored mesh per anchor row, in the same row " +
            "order the solved net's anchor grouping gives (item 0 is " +
            "row 0). Authored IN PLACE and exported in WORLD " +
            "coordinates: this component computes no placement for it, " +
            "it validates it against the anchor rows (a proximity check, " +
            "named by index when a tie strays).",
            GH_ParamAccess.list);
        parameters[6].Optional = true;
        parameters.AddTextParameter(
            "Materials",
            "MT",
            "Tags per part, matched by position: Pulley Units' own " +
            "{type}{part} paths for body/spinner tags, plus {2}{row} for " +
            "each Anchor Tie row. A missing tag falls back to the " +
            "part's own name (for example 'edge body', 'node spinner1', " +
            "'anchor tie 0').",
            GH_ParamAccess.tree);
        parameters[7].Optional = true;
    }

    protected override void RegisterOutputParams(GH_OutputParamManager parameters)
    {
        parameters.AddTextParameter(
            "Payload",
            "ME",
            "One JSON payload of everything wired, validated, ready for " +
            "Export's Mechanism input -- or blank when nothing was " +
            "wired, which is what tells Export this study has no " +
            "mechanism document.",
            GH_ParamAccess.item);
        parameters.AddTextParameter(
            "Status",
            "ST",
            "What was received (unit types, spinners, anchor ties, " +
            "sockets, whether a Result was wired), then any named " +
            "warning the door-guard raised, then any default the chin " +
            "owes an author who left SR blank.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        try
        {
            var shapeWarnings = new List<string>();
            var units = ReadUnits(data, shapeWarnings);
            var ties = ReadAnchorTies(data, shapeWarnings);
            bool hasResult = TryReadResult(data, out ResultDto? result);
            List<MechanismAnchorRow>? rows =
                hasResult ? MechanismGeometry.AnchorRows(result!) : null;

            var warnings = new List<string>(shapeWarnings);
            var notes = new List<string>();
            string? payload = MechanismCollector.Build(
                units, ties, rows, warnings, notes);

            var status = new List<string>
            {
                units.Count == 0 && ties.Count == 0
                    ? "received: nothing wired; no mechanism document."
                    : $"received: {units.Count} pulley unit type(s), " +
                      $"{ties.Count} anchor tie(s), Result " +
                      (hasResult ? "wired." : "not wired."),
            };
            foreach (string warning in warnings)
            {
                status.Add(warning);
                AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, warning);
            }
            foreach (string note in notes)
            {
                status.Add(note);
                AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, note);
            }

            data.SetData(0, payload ?? string.Empty);
            data.SetData(1, string.Join(Environment.NewLine, status));
            Message = payload is null
                ? "nothing wired"
                : $"{units.Count} unit type(s), {ties.Count} tie(s)";
        }
        catch (Exception error)
        {
            Message = "Failed";
            ReportException("Mechanism failed", error);
        }
    }

    private bool TryReadResult(IGH_DataAccess data, out ResultDto? result)
    {
        ResultGoo? goo = null;
        result = null;
        if (!data.GetData(0, ref goo) || goo?.Value is not ResultDto value)
            return false;
        result = value;
        return true;
    }

    private List<MechanismUnitInput> ReadUnits(
        IGH_DataAccess data, List<string> warnings)
    {
        data.GetDataTree(1, out GH_Structure<GH_Mesh> puTree);
        data.GetDataTree(2, out GH_Structure<GH_Plane> axTree);
        data.GetDataTree(3, out GH_Structure<GH_Plane> psTree);
        data.GetDataTree(4, out GH_Structure<GH_Number> prTree);
        data.GetDataTree(5, out GH_Structure<GH_Number> srTree);
        data.GetDataTree(7, out GH_Structure<GH_String> mtTree);

        // {type}{part} -> mesh, from PU's own two-level paths.
        var bodies = new Dictionary<int, MechanismMesh>();
        var spinnersByType = new Dictionary<int, SortedDictionary<int, MechanismMesh>>();
        foreach (GH_Path path in puTree.Paths)
        {
            if (path.Indices.Length != 2)
            {
                warnings.Add(
                    $"PU path {{{string.Join(",", path.Indices)}}} is not a " +
                    "{type}{part} two-level path; ignored.");
                continue;
            }
            int type = path.Indices[0];
            int part = path.Indices[1];
            IList branch = puTree.get_Branch(path);
            if (branch.Count == 0)
                continue;
            GH_Mesh? meshGoo = branch[0] as GH_Mesh;
            if (meshGoo?.Value is null)
            {
                warnings.Add($"PU[{type}][{part}] is null; skipped.");
                continue;
            }
            MechanismMesh mesh = MeshFromRhino(meshGoo.Value);
            if (part == 0)
            {
                bodies[type] = mesh;
            }
            else
            {
                if (!spinnersByType.TryGetValue(type, out var spinners))
                {
                    spinners = new SortedDictionary<int, MechanismMesh>();
                    spinnersByType[type] = spinners;
                }
                spinners[part] = mesh;
            }
        }

        var axes = new Dictionary<(int Type, int Part), MechanismAxis>();
        foreach (GH_Path path in axTree.Paths)
        {
            if (path.Indices.Length != 2)
            {
                warnings.Add(
                    $"AX path {{{string.Join(",", path.Indices)}}} is not a " +
                    "{type}{part} two-level path; ignored.");
                continue;
            }
            int type = path.Indices[0];
            int part = path.Indices[1];
            IList branch = axTree.get_Branch(path);
            if (branch.Count == 0)
                continue;
            GH_Plane? planeGoo = branch[0] as GH_Plane;
            if (planeGoo is null)
                continue;
            Plane plane = planeGoo.Value;
            axes[(type, part)] = new MechanismAxis(
                new[] { plane.Origin.X, plane.Origin.Y, plane.Origin.Z },
                new[] { plane.Normal.X, plane.Normal.Y, plane.Normal.Z });
        }

        var sockets = new Dictionary<int, List<MechanismFrame>>();
        foreach (GH_Path path in psTree.Paths)
        {
            if (path.Indices.Length != 1)
            {
                warnings.Add(
                    $"PS path {{{string.Join(",", path.Indices)}}} is not a " +
                    "single {type} path; ignored.");
                continue;
            }
            int type = path.Indices[0];
            var frames = new List<MechanismFrame>();
            foreach (GH_Plane planeGoo in psTree.get_Branch(path))
            {
                if (planeGoo is null)
                    continue;
                Plane plane = planeGoo.Value;
                frames.Add(new MechanismFrame(
                    new[] { plane.Origin.X, plane.Origin.Y, plane.Origin.Z },
                    new[] { plane.XAxis.X, plane.XAxis.Y, plane.XAxis.Z },
                    new[] { plane.YAxis.X, plane.YAxis.Y, plane.YAxis.Z }));
            }
            sockets[type] = frames;
        }

        var reeve = ReadOneNumberPerType(prTree, "PR", warnings);
        var spool = ReadOneNumberPerType(srTree, "SR", warnings);

        var tags = new Dictionary<(int Type, int Part), string>();
        foreach (GH_Path path in mtTree.Paths)
        {
            if (path.Indices.Length != 2)
                continue;
            IList branch = mtTree.get_Branch(path);
            if (branch.Count == 0)
                continue;
            GH_String? textGoo = branch[0] as GH_String;
            if (textGoo is null || string.IsNullOrWhiteSpace(textGoo.Value))
                continue;
            tags[(path.Indices[0], path.Indices[1])] = textGoo.Value;
        }

        var types = new SortedSet<int>(bodies.Keys);
        foreach (int type in spinnersByType.Keys)
            types.Add(type);

        var units = new List<MechanismUnitInput>(types.Count);
        foreach (int type in types)
        {
            bodies.TryGetValue(type, out MechanismMesh? body);
            var spinnerInputs = new List<MechanismSpinnerInput>();
            if (spinnersByType.TryGetValue(type, out var spinnerMeshes))
            {
                foreach ((int part, MechanismMesh mesh) in spinnerMeshes)
                {
                    axes.TryGetValue((type, part), out MechanismAxis? axis);
                    string tag = tags.TryGetValue((type, part), out string? explicitTag)
                        ? explicitTag
                        : $"{MechanismCollector.TypeName(type)} spinner{part}";
                    spinnerInputs.Add(new MechanismSpinnerInput(mesh, axis, tag));
                }
            }
            sockets.TryGetValue(type, out List<MechanismFrame>? typeSockets);
            reeve.TryGetValue(type, out double? typeReeve);
            spool.TryGetValue(type, out double? typeSpool);
            string bodyTag = tags.TryGetValue((type, 0), out string? explicitBodyTag)
                ? explicitBodyTag
                : $"{MechanismCollector.TypeName(type)} body";
            units.Add(new MechanismUnitInput(
                type,
                body,
                bodyTag,
                spinnerInputs,
                (IReadOnlyList<MechanismFrame>?)typeSockets ?? Array.Empty<MechanismFrame>(),
                typeReeve,
                typeSpool));
        }
        return units;
    }

    private static Dictionary<int, double?> ReadOneNumberPerType(
        GH_Structure<GH_Number> tree, string portName, List<string> warnings)
    {
        var byType = new Dictionary<int, double?>();
        foreach (GH_Path path in tree.Paths)
        {
            if (path.Indices.Length != 1)
            {
                warnings.Add(
                    $"{portName} path {{{string.Join(",", path.Indices)}}} " +
                    "is not a single {type} path; ignored.");
                continue;
            }
            int type = path.Indices[0];
            IList branch = tree.get_Branch(path);
            if (branch.Count == 0)
                continue;
            if (branch.Count > 1)
            {
                warnings.Add(
                    $"{portName}[{type}] carries {branch.Count} values; " +
                    "only the first is used.");
            }
            GH_Number? numberGoo = branch[0] as GH_Number;
            if (numberGoo is null)
                continue;
            byType[type] = numberGoo.Value;
        }
        return byType;
    }

    private List<MechanismAnchorTieInput> ReadAnchorTies(
        IGH_DataAccess data, List<string> warnings)
    {
        data.GetDataTree(6, out GH_Structure<GH_Mesh> atTree);
        data.GetDataTree(7, out GH_Structure<GH_String> mtTree);

        var atTags = new Dictionary<int, string>();
        foreach (GH_Path path in mtTree.Paths)
        {
            if (path.Indices.Length != 2 || path.Indices[0] != 2)
                continue;
            IList branch = mtTree.get_Branch(path);
            if (branch.Count == 0)
                continue;
            GH_String? textGoo = branch[0] as GH_String;
            if (textGoo is null || string.IsNullOrWhiteSpace(textGoo.Value))
                continue;
            atTags[path.Indices[1]] = textGoo.Value;
        }

        var ties = new List<MechanismAnchorTieInput>(atTree.DataCount);
        int index = 0;
        foreach (GH_Path path in atTree.Paths)
        {
            foreach (GH_Mesh? meshGoo in atTree.get_Branch(path))
            {
                if (meshGoo?.Value is null)
                {
                    warnings.Add($"AT[{index}] is null; skipped.");
                    index++;
                    continue;
                }
                Mesh mesh = meshGoo.Value;
                BoundingBox box = mesh.GetBoundingBox(true);
                Point3d centre = box.Center;
                string tag = atTags.TryGetValue(index, out string? explicitTag)
                    ? explicitTag
                    : $"anchor tie {index}";
                ties.Add(new MechanismAnchorTieInput(
                    MeshFromRhino(mesh),
                    new[] { centre.X, centre.Y, centre.Z },
                    tag));
                index++;
            }
        }
        return ties;
    }

    private static MechanismMesh MeshFromRhino(Mesh mesh)
    {
        var vertices = new List<double[]>(mesh.Vertices.Count);
        for (int i = 0; i < mesh.Vertices.Count; i++)
        {
            Point3f p = mesh.Vertices[i];
            vertices.Add(new double[] { p.X, p.Y, p.Z });
        }
        var faces = new List<int[]>(mesh.Faces.Count);
        foreach (MeshFace face in mesh.Faces)
        {
            faces.Add(face.IsTriangle
                ? new[] { face.A, face.B, face.C }
                : new[] { face.A, face.B, face.C, face.D });
        }
        return new MechanismMesh(vertices, faces);
    }
}
