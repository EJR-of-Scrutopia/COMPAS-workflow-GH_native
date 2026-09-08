#nullable enable

using System;
using System.Collections;
using System.Collections.Generic;
using System.Diagnostics.CodeAnalysis;
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
/// NAMED PORTS, not a tree of type-and-part (the input model settled with
/// Param 2026-09-08 night, superseding this file's earlier {type}{part}
/// scheme entire): anchor, tension tie, mechanism, placement, reel, reel
/// axis, routing, plus reel kind. The port a part arrives on IS its
/// semantic kind -- read by the structural array it lands in (anchors,
/// tensionTies, mechanism.body, mechanism.spinners, wires) rather than a
/// redundant tag field, per the studio's own REPLY 4 point 7: permanence
/// and material both derive from the port, "no new field anywhere".
///
/// This is the collector's OWN packaging model: the meshes, axes, frames
/// and rows as Param wires them, validated and reduced to plain data on the
/// solve thread (Rhino access happens in
/// <see cref="MechanismCollectorComponent"/> only). What is NOT here is any
/// PLACEMENT COMPUTATION: he places the mechanisms himself (Placement, one
/// authority), and net-vertex matching needs the solved Result, so both are
/// finished in <see cref="MechanismDocument"/> at Export time.
/// </summary>
internal sealed record MechanismMesh(
    IReadOnlyList<double[]> Vertices,
    IReadOnlyList<int[]> Faces);

/// <summary>One routing (or placement, or reel axis) frame: origin plus X and Y axes, Z derived.</summary>
internal sealed record MechanismFrame(double[] Origin, double[] XAxis, double[] YAxis);

/// <summary>
/// The ONE authored mechanism BODY (his "one continuous body ... always
/// place"). Authored ONCE regardless of how many places it is instanced --
/// never six copies of the mesh, the studio's own 8 GB iPad constraint
/// (C4). His REELS no longer travel here: his ruling of 2026-09-08 night
/// (superseding this record's own earlier shape, which carried them
/// alongside the body) moved them to per-mechanism data -- see <see
/// cref="MechanismReelEntry"/> and its two branch types below -- since he
/// authors their orientation deliberately, either per mechanism or once
/// for the whole asset, never bundled with the body mesh itself.
/// </summary>
internal sealed record MechanismAssetInput(
    MechanismMesh? Body,
    bool BodyFromBrep);

/// <summary>
/// ONE ROTATING REEL: its mesh and its rotation-axis FRAME, unit-local
/// space. His ruling, 2026-09-08 night, verbatim: "the plane, will be xy
/// so rotation will go in that axis from z and i will always provide you
/// the xy orientation so that it rotates in the correct way" -- the
/// plane's Z is the rotation axis, but its X and Y are carried through
/// UNCHANGED into the document rather than reduced to a bare
/// origin-plus-direction, because they are how he encodes which way the
/// reel spins. Never re-derived, never normalised away.
/// </summary>
internal sealed record MechanismReelEntry(
    MechanismMesh Mesh,
    bool FromBrep,
    MechanismFrame Axis);

/// <summary>
/// One authored branch of Reel (RE): its raw tree path (empty, or
/// length one, for the default path GH assigns a bare flat list; length
/// TWO -- {side}{mechanism} -- for a genuine per-mechanism branch) and
/// its meshes in branch order. Kept Rhino- and Grasshopper-free (the path
/// is plain ints) so <see cref="MechanismCollector"/> can tell a flat
/// list from a real tree, and drive that decision by reflection in the
/// harness exactly as it runs live.
/// </summary>
internal sealed record MechanismMeshBranch(
    IReadOnlyList<int> Path,
    IReadOnlyList<MechanismMesh?> Meshes,
    IReadOnlyList<bool> FromBrep);

/// <summary>The same shape as <see cref="MechanismMeshBranch"/>, for Reel Axis (AX).</summary>
internal sealed record MechanismAxisBranch(
    IReadOnlyList<int> Path,
    IReadOnlyList<MechanismFrame?> Axes);

/// <summary>One instance address: side then mechanism, his own tree order ("mechanisms per side, sides").</summary>
internal readonly record struct MechanismInstanceId(int Side, int Mechanism)
{
    public string Label => $"side {Side} mechanism {Mechanism}";
}

/// <summary>
/// One placed instance (PL), his own placement, plus its optional
/// functional label (RK, "edge"/"node") -- informational only, never
/// structural (spec 3a's settled reading: SR/PR no longer travel as
/// authored ports at all, so nothing downstream branches on this word).
/// </summary>
internal sealed record MechanismInstanceInput(
    MechanismInstanceId Id,
    MechanismFrame Placement,
    string? Kind);

/// <summary>
/// One authored wire (RT): the ordered local routing planes in threading
/// order, planes[0] the NET END by his ruling (R2) -- validated after
/// placement in <see cref="MechanismDocument"/>, which is the one place
/// that also owns the Result the net-vertex world position comes from.
/// </summary>
internal sealed record MechanismWireInput(
    MechanismInstanceId Instance,
    int Wire,
    IReadOnlyList<MechanismFrame> Route);

/// <summary>
/// One AN or TT row: the authored mesh, its ORIGINAL position in the port's
/// own list (so a dropped item mid-list never renumbers the rows after
/// it), its world-space centroid (the door-guard's own probe point), and
/// whether it arrived as a Brep and was meshed here.
/// </summary>
internal sealed record MechanismRowPartInput(
    int Index,
    MechanismMesh Mesh,
    double[] Centroid,
    bool FromBrep);

/// <summary>
/// One anchor row's node points, world space, in the walking order
/// <c>MouldGeometry.ConnectedGroups</c> returns -- the same order AN/TT's
/// own row numbering follows (requirements doc section 2).
/// </summary>
internal sealed record MechanismAnchorRow(IReadOnlyList<double[]> NodePoints);

/// <summary>
/// The pure packaging and door-guard logic behind the MECHANISM collector:
/// no Rhino type crosses this boundary, so the harness can drive every rule
/// with arrays it builds itself.
///
/// ONE JOB: turn what was wired into one JSON payload
/// <see cref="MechanismDocument"/> can finish (net-vertex matching,
/// reversed-route naming) and Export can embed, and say by name what could
/// not be trusted rather than silently dropping it or silently accepting
/// it.
/// </summary>
internal static class MechanismCollector
{
    /// <summary>
    /// The permanence field's own name and its two values, said once and
    /// read everywhere a part payload is built (here and in
    /// <see cref="MechanismDocument"/>'s wires). Param's ruling to the
    /// Vaulted studio, 2026-09-08: "the two things that remain when all is
    /// taken away is the tension tie / column slide, and the anchor" --
    /// Anchor (AN) and Tension Tie (TT) are the PERMANENT works; the
    /// mechanism body, its spinners and the wires that reel them are the
    /// TEMPORARY machine that comes away once the vault stands.
    ///
    /// A STRING, not a boolean, following the document's own convention:
    /// <c>"placement"</c> already carries <c>"instance"</c>/<c>"world"</c>
    /// as a declared word rather than a flag the reader has to remember the
    /// sense of.
    /// </summary>
    public const string PermanenceField = "permanence";

    public const string Permanent = "permanent";

    public const string Temporary = "temporary";

    /// <summary>
    /// How far an AN or TT mesh may sit from the nearest node of its own
    /// row before the door-guard names it: a multiple of the row's OWN
    /// characteristic anchor spacing, so the tolerance scales with the
    /// study rather than assuming a unit.
    /// </summary>
    public const double AnchorTieToleranceFactor = 3.0;

    public const double MinimumAnchorTieTolerance = 1.0e-6;

    public const double MinimumSpoolRadius = 1.0e-6;

    /// <summary>
    /// The note said whenever a mesh-or-brep port meshed a Brep itself
    /// rather than being handed an authored mesh: he cannot see the
    /// settings once it is meshed, so the settings are named here (spec's
    /// own validation list, "a brep accepted and meshed says so with the
    /// settings used").
    /// </summary>
    public const string BrepMeshingNote =
        "arrived as a Brep and was meshed here with Rhino's default " +
        "meshing parameters (MeshingParameters.Default), since no mesh " +
        "was authored directly and you cannot see the settings once it " +
        "is meshed.";

    /// <summary>
    /// Build the mechanism payload, or null when nothing was wired at all
    /// (spec section 8 item 6: "the collector with NOTHING wired produces
    /// no mechanism document and no warning noise"). <paramref
    /// name="warnings"/> and <paramref name="notes"/> are appended to,
    /// never cleared, so a caller can pool them across a whole solve's
    /// chin.
    /// </summary>
    public static string? Build(
        MechanismAssetInput asset,
        IReadOnlyList<MechanismMeshBranch> reelMeshes,
        IReadOnlyList<MechanismAxisBranch> reelAxes,
        IReadOnlyList<MechanismInstanceInput> instances,
        IReadOnlyList<MechanismWireInput> wires,
        IReadOnlyList<MechanismRowPartInput> anchors,
        IReadOnlyList<MechanismRowPartInput> tensionTies,
        IReadOnlyList<MechanismAnchorRow>? rows,
        List<string> warnings,
        List<string> notes)
    {
        ArgumentNullException.ThrowIfNull(asset);
        ArgumentNullException.ThrowIfNull(reelMeshes);
        ArgumentNullException.ThrowIfNull(reelAxes);
        ArgumentNullException.ThrowIfNull(instances);
        ArgumentNullException.ThrowIfNull(wires);
        ArgumentNullException.ThrowIfNull(anchors);
        ArgumentNullException.ThrowIfNull(tensionTies);
        ArgumentNullException.ThrowIfNull(warnings);
        ArgumentNullException.ThrowIfNull(notes);

        bool anyReelMeshAuthored = reelMeshes.Any(b => b.Meshes.Count > 0);
        bool nothingWired =
            asset.Body is null && !anyReelMeshAuthored &&
            instances.Count == 0 && wires.Count == 0 &&
            anchors.Count == 0 && tensionTies.Count == 0;
        if (nothingWired)
            return null;

        bool assetOk = asset.Body is not null;
        if (!assetOk && (instances.Count > 0 || wires.Count > 0))
        {
            warnings.Add(
                "Placement (PL) or Routing (RT) was authored, but " +
                "Mechanism (ME) carries no body mesh; nothing is " +
                "instanced without a body.");
        }

        // FOUR REELS PER MECHANISM, EITHER AUTHORING STYLE (his ruling,
        // 2026-09-08 night): a tree keyed {side}{mechanism}, authored per
        // instance, or a flat list of four authored once and replicated
        // across every instance. See ResolveReelAuthoring below for how
        // the two are told apart and what a mismatch refuses.
        Dictionary<MechanismInstanceId, List<MechanismReelEntry>> resolvedReels =
            ResolveReelAuthoring(reelMeshes, reelAxes, instances, warnings, notes);

        Dictionary<string, object?>? mechanismOut = null;
        if (assetOk && asset.Body is not null)
        {
            Dictionary<string, object?> bodyPayload = MeshPayload(asset.Body);
            bodyPayload[PermanenceField] = Temporary;
            if (asset.BodyFromBrep)
                notes.Add($"Mechanism (ME) {BrepMeshingNote}");

            var reelsOut = new List<Dictionary<string, object?>>();
            List<MechanismReelEntry>? boundingGroup = null;
            foreach (KeyValuePair<MechanismInstanceId, List<MechanismReelEntry>> group in
                resolvedReels.OrderBy(kv => kv.Key.Side).ThenBy(kv => kv.Key.Mechanism))
            {
                boundingGroup ??= group.Value;
                for (int i = 0; i < group.Value.Count; i++)
                {
                    MechanismReelEntry entry = group.Value[i];
                    reelsOut.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["side"] = group.Key.Side,
                        ["mechanism"] = group.Key.Mechanism,
                        // reel 0 within its own mechanism is the driven
                        // spool, the one spinner section 5's derived
                        // rotation ever turns (requirements doc section
                        // 1); reels 1..3 are cosmetic wheels, carried but
                        // not rotated.
                        ["reel"] = i,
                        ["mesh"] = MeshPayload(entry.Mesh),
                        ["axis"] = FramePayload(entry.Axis),
                        ["driven"] = i == 0,
                        [PermanenceField] = Temporary,
                    });
                    if (entry.FromBrep)
                    {
                        notes.Add(
                            $"Reel (RE)[{group.Key.Side}][{group.Key.Mechanism}]" +
                            $"[{i}] {BrepMeshingNote}");
                    }
                }
            }

            // SPOOL RADIUS: the driven spool's (reel 0's) own bounding box
            // smallest dimension over 4, read off the first mechanism in
            // document order when reels vary per instance, falling back to
            // the body's own bounding box when the mechanism carries no
            // spinner at all -- said in the chin so the default is never
            // silent.
            MechanismMesh boundingSource =
                boundingGroup is { Count: > 0 } ? boundingGroup[0].Mesh : asset.Body;
            double spoolRadius = Math.Max(
                SmallestBoundingDimension(boundingSource) / 4.0,
                MinimumSpoolRadius);
            notes.Add(
                "mechanism: spoolRadius defaulted to " +
                spoolRadius.ToString("0.####", CultureInfo.InvariantCulture) +
                (boundingGroup is { Count: > 0 }
                    ? " from the driven spool's own bounding box (smallest " +
                      "dimension over 4)."
                    : " from the body's own bounding box (smallest " +
                      "dimension over 4), since this mechanism carries no " +
                      "spinner."));

            // THE REEVE FACTOR IS PROVISIONAL (his ruling, verbatim: "i
            // dont [want] it to be accurate righ tnow"). Fixed at 1.0, no
            // authored port, and said here EVERY time a mechanism is
            // built so an inaccurate spin rate is a stated limitation
            // rather than a mystery -- the spec's "reeve factor, settled
            // 2026-09-08 late" records why 1.0 is very probably wrong on
            // his four-wheel unit and what shape the real fix takes; not
            // built now.
            notes.Add(
                "mechanism: reeveFactor is fixed at 1.0 -- PROVISIONAL, " +
                "not accurate, per his own ruling that accuracy is not " +
                "wanted right now; every reel's spin RATE is likely wrong " +
                "until a real reeve factor is authored.");

            mechanismOut = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["body"] = bodyPayload,
                ["reels"] = reelsOut,
                ["reeveFactor"] = 1.0,
                ["spoolRadius"] = spoolRadius,
            };
        }

        var instancesOut = new List<Dictionary<string, object?>>();
        var instanceIds = new HashSet<(int Side, int Mechanism)>();
        if (mechanismOut is not null)
        {
            foreach (MechanismInstanceInput instance in instances)
            {
                instanceIds.Add((instance.Id.Side, instance.Id.Mechanism));
                instancesOut.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["side"] = instance.Id.Side,
                    ["mechanism"] = instance.Id.Mechanism,
                    ["frame"] = FramePayload(instance.Placement),
                    ["kind"] = instance.Kind ?? "mechanism",
                    // ONE PLACEMENT CONVENTION (studio's C5/A5): every
                    // instance carries a placement frame he authored,
                    // unlike Anchor/Tension Tie's "world" flag below.
                    ["placement"] = "instance",
                });
                if (instance.Kind is null)
                {
                    notes.Add(
                        $"{instance.Id.Label}: no Reel Kind (RK) authored; " +
                        "tagged the generic kind \"mechanism\".");
                }
            }
        }
        else if (instances.Count > 0)
        {
            warnings.Add(
                $"{instances.Count} Placement (PL) instance(s) were " +
                "authored, but the mechanism asset was refused or absent; " +
                "no instances are produced.");
        }

        var wiresOut = new List<Dictionary<string, object?>>();
        foreach (MechanismWireInput wire in wires
            .OrderBy(w => w.Instance.Side)
            .ThenBy(w => w.Instance.Mechanism)
            .ThenBy(w => w.Wire))
        {
            if (!instanceIds.Contains((wire.Instance.Side, wire.Instance.Mechanism)))
            {
                warnings.Add(
                    $"Routing (RT)[{wire.Instance.Side}][{wire.Instance.Mechanism}]" +
                    $"[{wire.Wire}] has no matching Placement (PL) instance; " +
                    "wire dropped.");
                continue;
            }
            wiresOut.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["side"] = wire.Instance.Side,
                ["mechanism"] = wire.Instance.Mechanism,
                ["wire"] = wire.Wire,
                ["route"] = wire.Route.Select(FramePayload).ToList(),
            });
        }

        List<Dictionary<string, object?>> anchorsOut =
            BuildRowParts("Anchor (AN)", anchors, rows, warnings, notes);
        List<Dictionary<string, object?>> tiesOut =
            BuildRowParts("Tension Tie (TT)", tensionTies, rows, warnings, notes);

        var payload = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["mechanism"] = mechanismOut,
            ["instances"] = instancesOut,
            ["wires"] = wiresOut,
            ["anchors"] = anchorsOut,
            ["tensionTies"] = tiesOut,
        };
        return JsonSerializer.Serialize(payload, ContractJson.Options);
    }

    /// <summary>
    /// FOUR REELS PER MECHANISM, EITHER AUTHORING STYLE (his ruling,
    /// 2026-09-08 night): a TREE keyed {side}{mechanism}, matching the
    /// shape his routing frames (RT) already use one level deeper
    /// ({side}{mechanism}{wire}), with four reel entries per branch --
    /// authored per instance, for when a mechanism's reels genuinely
    /// differ (a mirrored side, say). OR a single FLAT list of four,
    /// authored once on the asset and replicated across every declared
    /// instance, for when they do not. Both cost him little and both are
    /// accepted; which one was read is always said in <paramref
    /// name="notes"/> (the chin), never left silent.
    ///
    /// A reel with no matching axis (by position within its own group)
    /// refuses ITS UNIT: in tree style that is the one mechanism whose
    /// branch failed, named and left with no reels while every other
    /// mechanism proceeds; in flat style, since it is one set shared by
    /// every instance, it is the whole reel set. Either way the axis is
    /// authored, never inferred. Neither failure touches the body,
    /// placements or wires -- only reels are ever refused here.
    /// </summary>
    private static Dictionary<MechanismInstanceId, List<MechanismReelEntry>> ResolveReelAuthoring(
        IReadOnlyList<MechanismMeshBranch> meshBranches,
        IReadOnlyList<MechanismAxisBranch> axisBranches,
        IReadOnlyList<MechanismInstanceInput> instances,
        List<string> warnings,
        List<string> notes)
    {
        var resolved = new Dictionary<MechanismInstanceId, List<MechanismReelEntry>>();
        bool anyMeshes = meshBranches.Any(b => b.Meshes.Count > 0);
        if (!anyMeshes)
        {
            if (axisBranches.Any(b => b.Axes.Count > 0))
            {
                warnings.Add(
                    "Reel Axis (AX) was authored but Reel (RE) carries no " +
                    "reel mesh(es); a spinner without a matching mesh " +
                    "refuses its unit, so no reels are produced.");
            }
            return resolved;
        }

        bool meshTree = meshBranches.All(b => b.Path.Count == 2);
        bool axisTree = axisBranches.Count == 0 || axisBranches.All(b => b.Path.Count == 2);
        bool meshFlat = meshBranches.Count == 1 && meshBranches[0].Path.Count <= 1;
        bool axisFlat = axisBranches.Count <= 1 && axisBranches.All(b => b.Path.Count <= 1);

        if (meshTree && axisTree)
        {
            foreach (MechanismMeshBranch branch in meshBranches)
            {
                int side = branch.Path[0];
                int mechanism = branch.Path[1];
                string label = $"[{side}][{mechanism}]";
                MechanismAxisBranch? axisBranch = axisBranches.FirstOrDefault(
                    b => b.Path.Count == 2 && b.Path[0] == side && b.Path[1] == mechanism);
                IReadOnlyList<MechanismFrame?> axes = axisBranch?.Axes ?? Array.Empty<MechanismFrame?>();
                if (!TryZipReels(branch.Meshes, branch.FromBrep, axes, out List<MechanismReelEntry>? zipped, out string? failure))
                {
                    warnings.Add(
                        $"Reel (RE){label}: {failure} a spinner without a " +
                        "matching axis refuses its unit, so mechanism " +
                        $"{label}'s reels are refused: the axis is " +
                        "authored, never inferred.");
                    continue;
                }
                if (zipped.Count != 4)
                {
                    warnings.Add(
                        $"Reel (RE){label} carries {zipped.Count} reel(s); " +
                        "his machine is four reels per mechanism, so this " +
                        "is unusual but used as authored.");
                }
                resolved[new MechanismInstanceId(side, mechanism)] = zipped;
            }
            notes.Add(
                "mechanism: Reel (RE) / Reel Axis (AX) were read as a " +
                "TREE, one branch per mechanism (path {side}{mechanism}); " +
                $"{resolved.Count} of {meshBranches.Count} mechanism(s) " +
                "carry reel data.");
            return resolved;
        }

        if (meshFlat && axisFlat)
        {
            MechanismMeshBranch mb = meshBranches[0];
            IReadOnlyList<MechanismFrame?> axesFlat =
                axisBranches.Count == 1 ? axisBranches[0].Axes : Array.Empty<MechanismFrame?>();
            if (!TryZipReels(mb.Meshes, mb.FromBrep, axesFlat, out List<MechanismReelEntry>? zipped, out string? failure))
            {
                warnings.Add(
                    $"Reel (RE): {failure} a spinner without a matching " +
                    "axis refuses its unit, so the whole reel set is " +
                    "refused: the axis is authored, never inferred.");
                return resolved;
            }
            if (zipped.Count != 4)
            {
                warnings.Add(
                    $"Reel (RE) carries {zipped.Count} reel(s); his " +
                    "machine is four reels per mechanism, so this is " +
                    "unusual but used as authored.");
            }
            foreach (MechanismInstanceInput instance in instances)
                resolved[instance.Id] = zipped;
            notes.Add(
                "mechanism: Reel (RE) / Reel Axis (AX) were read as a " +
                $"FLAT list of {zipped.Count} reel(s), authored once on " +
                $"the asset, and replicated across {instances.Count} " +
                "instance(s).");
            return resolved;
        }

        warnings.Add(
            "Reel (RE) / Reel Axis (AX) paths are neither a clean " +
            "{side}{mechanism} tree (one branch per mechanism) nor a " +
            "single flat list (authored once on the asset); reels " +
            "refused, since the two authoring styles could not be told " +
            "apart.");
        return resolved;
    }

    /// <summary>
    /// Pairs a branch's meshes with its axes by position (reel 0 with
    /// axis 0, and so on): the only place a mesh or axis actually going
    /// missing is named. Returns false, with <paramref name="failure"/>
    /// naming what went wrong, the moment either list runs a different
    /// length or a single position fails to resolve on either side.
    /// </summary>
    private static bool TryZipReels(
        IReadOnlyList<MechanismMesh?> meshes,
        IReadOnlyList<bool> fromBrep,
        IReadOnlyList<MechanismFrame?> axes,
        [NotNullWhen(true)] out List<MechanismReelEntry>? zipped,
        out string? failure)
    {
        zipped = null;
        if (meshes.Count != axes.Count)
        {
            failure = $"carries {meshes.Count} reel mesh(es) but " +
                $"{axes.Count} axis plane(s);";
            return false;
        }
        var list = new List<MechanismReelEntry>(meshes.Count);
        for (int i = 0; i < meshes.Count; i++)
        {
            if (meshes[i] is null)
            {
                failure = $"reel[{i}] did not resolve to a mesh or a " +
                    "closed Brep;";
                return false;
            }
            if (axes[i] is null)
            {
                failure = $"reel[{i}] has no matching Reel Axis (AX) " +
                    "plane;";
                return false;
            }
            list.Add(new MechanismReelEntry(meshes[i]!, fromBrep[i], axes[i]!));
        }
        zipped = list;
        failure = null;
        return true;
    }

    /// <summary>
    /// Anchor (AN) and Tension Tie (TT) share the SAME door-guard
    /// (requirements doc section (b): "reused as-is for BOTH new ports ...
    /// just run twice instead of once"). Both are authored in place in
    /// world coordinates and never placed by this component; both are
    /// permanent, and both are validated against the anchor row's own
    /// nearest node, with a tolerance that scales with the row's own
    /// characteristic anchor spacing.
    /// </summary>
    private static List<Dictionary<string, object?>> BuildRowParts(
        string portLabel,
        IReadOnlyList<MechanismRowPartInput> parts,
        IReadOnlyList<MechanismAnchorRow>? rows,
        List<string> warnings,
        List<string> notes)
    {
        var results = new List<Dictionary<string, object?>>(parts.Count);
        if (parts.Count > 0 && rows is null)
        {
            warnings.Add(
                $"{portLabel} carries {parts.Count} mesh(es) but no Result " +
                "was wired to Mechanism: the door-guard proximity check " +
                $"against the anchor rows could not run, and each " +
                $"{portLabel} row is its own position in {portLabel}, " +
                "unconfirmed.");
        }
        foreach (MechanismRowPartInput part in parts)
        {
            int i = part.Index;
            if (rows is not null)
            {
                if (i >= rows.Count)
                {
                    warnings.Add(
                        $"{portLabel}[{i}] has no matching anchor row " +
                        $"(only {rows.Count} found by the solved net); its " +
                        "row index is unvalidated.");
                }
                else if (rows[i].NodePoints.Count == 0)
                {
                    warnings.Add(
                        $"anchor row {i} carries no anchor nodes; " +
                        $"{portLabel}[{i}] cannot be validated against it.");
                }
                else
                {
                    IReadOnlyList<double[]> nodePoints = rows[i].NodePoints;
                    double nearest = nodePoints
                        .Select(p => Distance(p, part.Centroid))
                        .Min();
                    double tolerance = Math.Max(
                        AnchorTieToleranceFactor * CharacteristicSpacing(nodePoints),
                        MinimumAnchorTieTolerance);
                    if (nearest > tolerance)
                    {
                        warnings.Add(
                            $"{portLabel}[{i}] sits " +
                            nearest.ToString("0.###", CultureInfo.InvariantCulture) +
                            $" from anchor row {i} (nearest anchor node), " +
                            "farther than the door-guard tolerance of " +
                            tolerance.ToString("0.###", CultureInfo.InvariantCulture) +
                            $" ({AnchorTieToleranceFactor.ToString("0.#", CultureInfo.InvariantCulture)}x " +
                            "the row's own anchor spacing): this part may " +
                            "be authored against a different solve.");
                    }
                }
            }
            results.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["row"] = i,
                ["mesh"] = MeshPayload(part.Mesh),
                // ONE PLACEMENT CONVENTION (studio's C5/A5): Anchor and
                // Tension Tie arrive pre-placed in world coordinates,
                // unlike the mechanism's own instances above; the flag
                // says so directly rather than leaving it to be inferred
                // from "this kind carries no frame".
                ["placement"] = "world",
                // THE PERMANENT WORKS (Param's ruling, see PermanenceField
                // above): Anchor and Tension Tie are the two things that
                // remain when the machine comes away.
                [PermanenceField] = Permanent,
            });
            if (part.FromBrep)
                notes.Add($"{portLabel}[{i}] {BrepMeshingNote}");
        }
        return results;
    }

    private static Dictionary<string, object?> MeshPayload(MechanismMesh mesh) =>
        new(StringComparer.Ordinal)
        {
            ["vertices"] = mesh.Vertices,
            ["faces"] = mesh.Faces,
        };

    internal static Dictionary<string, object?> FramePayload(MechanismFrame frame) =>
        new(StringComparer.Ordinal)
        {
            ["origin"] = frame.Origin,
            ["xAxis"] = frame.XAxis,
            ["yAxis"] = frame.YAxis,
        };

    /// <summary>
    /// The smallest of the three world-axis extents of a mesh's own
    /// vertices: the spool-radius default's source. Zero for an empty
    /// mesh, which the caller floors at <see cref="MinimumSpoolRadius"/>
    /// rather than dividing by it.
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

    /// <summary>The bounding-box centre of a mesh's own vertices, plain arithmetic, used as AN/TT's own door-guard probe point.</summary>
    internal static double[] BoundingBoxCenter(MechanismMesh mesh)
    {
        if (mesh.Vertices.Count == 0)
            return new double[] { 0.0, 0.0, 0.0 };
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
        return new[]
        {
            (min[0] + max[0]) / 2.0,
            (min[1] + max[1]) / 2.0,
            (min[2] + max[2]) / 2.0,
        };
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
/// The anchor-row geometry the door-guard (and, from Export, wire-to-anchor
/// matching) both read off a solved Result: the same grouping
/// <c>MouldGeometry.ConnectedGroups</c>/<c>GroupingAdjacency</c> already give
/// Diagnose's own "every anchor is in a strip of its own" check
/// (requirements doc section 2), so an AN/TT row and a wire's matched
/// anchor can never disagree about what a row is.
/// </summary>
internal static class MechanismGeometry
{
    /// <summary>
    /// Every anchor row's NODE INDICES, in <c>ConnectedGroups</c>' own
    /// order. The one place this grouping is computed, so the door-guard's
    /// rows (points only) and Export's own wire-to-anchor matching
    /// (indices) can never disagree about what a row is. Empty when the
    /// Result carries no equilibrium or no anchors.
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
/// Export beside RES and Cells. NAMED PORTS, settled with Param 2026-09-08
/// night: "anchor, tension tie, mechanism, mechanism normal, mechanism
/// reel, reel plane", plus Routing and Reel Kind (this document's own
/// additions, needed to carry what his six words describe but do not name
/// a port for).
///
/// Every port is optional, so an author who wants only a mechanism, only a
/// tension tie, or nothing at all can wire exactly that. Nothing here
/// PLACES anything: he places every instance himself (Placement), and
/// Anchor/Tension Tie travel in world coordinates exactly as authored,
/// validated rather than placed (the door-guard rule). Result (RES) is
/// wired so the door-guard has anchor rows to check Anchor/Tension Tie
/// against, and so Export can later match each wire to a net vertex.
///
/// Nothing wired produces an empty Payload and a quiet chin (spec section 8
/// item 6): Export reads an empty Payload as "no mechanism document for
/// this study" exactly the way it reads no Cells as "no skin document".
/// </summary>
public sealed class MechanismCollectorComponent : NativeComponentBase
{
    public MechanismCollectorComponent()
        : base(
            "Mechanism",
            "ME",
            "Collect the reeling machine's authored parts on their named " +
            "ports -- Anchor, Tension Tie, Mechanism, Placement, Reel, " +
            "Reel Axis, Routing, Reel Kind -- and validate them into one " +
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
            "The solved Result, wired so Anchor (AN) and Tension Tie (TT) " +
            "can be validated against the anchor rows they should sit " +
            "beside, and so Export can match each wire (RT) to a net " +
            "vertex (default: wire order against anchor order along the " +
            "row). Placement is authored, not computed here or by Export.",
            GH_ParamAccess.item);
        parameters[0].Optional = true;

        parameters.AddGenericParameter(
            "Anchor",
            "AN",
            "The foundation anchor: one mesh (or closed Brep, meshed " +
            "here and said so) per anchored row, authored IN PLACE in " +
            "WORLD coordinates. This component computes no placement for " +
            "it; it validates it against the anchor rows (a proximity " +
            "check, named by row when one strays).",
            GH_ParamAccess.list);
        parameters[1].Optional = true;

        parameters.AddGenericParameter(
            "Tension Tie",
            "TT",
            "The sliding ground bar / column tension tie: one mesh (or " +
            "closed Brep, meshed here and said so) per anchored row, " +
            "authored IN PLACE in WORLD coordinates and validated " +
            "against the anchor rows exactly as Anchor (AN) is.",
            GH_ParamAccess.list);
        parameters[2].Optional = true;

        parameters.AddGenericParameter(
            "Mechanism",
            "ME",
            "The ONE authored mechanism body (a mesh, or a closed Brep " +
            "meshed here and said so), in the unit's own local space. " +
            "Instanced at every Placement (PL) frame -- never a copy per " +
            "instance.",
            GH_ParamAccess.item);
        parameters[3].Optional = true;

        parameters.AddPlaneParameter(
            "Placement",
            "PL",
            "One placement frame per instance, tree path " +
            "{side}{mechanism}, world coordinates: where he puts the " +
            "mechanism. Authored by him; this component computes no " +
            "placement.",
            GH_ParamAccess.tree);
        parameters[4].Optional = true;

        parameters.AddGenericParameter(
            "Reel",
            "RE",
            "The spinning parts' meshes (or closed Breps, meshed here " +
            "and said so), unit-local space: FOUR per mechanism (his " +
            "machine, ruling of 2026-09-08 night), reel 0 the driven " +
            "spool and reels 1..3 cosmetic wheels carried but not " +
            "rotated. Tree path {side}{mechanism}, one branch of four " +
            "per mechanism (matching Placement/PL and Routing/RT), OR a " +
            "flat list of four authored once and replicated across " +
            "every instance -- either is accepted, and Status (ST) says " +
            "which was read.",
            GH_ParamAccess.tree);
        parameters[5].Optional = true;

        parameters.AddPlaneParameter(
            "Reel Axis",
            "AX",
            "ONE PLANE PER ROTATING REEL, matching Reel (RE) 1:1 by " +
            "position within its own mechanism, unit-local space: the " +
            "plane's Z is the rotation axis, read from the plane's " +
            "normal. Its X and Y are carried through into the document " +
            "UNCHANGED -- his ruling, 2026-09-08 night -- because he " +
            "authors them deliberately to fix the spin direction; never " +
            "re-derived or normalised away. Same tree-or-flat shape as " +
            "Reel (RE): {side}{mechanism}, or a flat four replicated " +
            "across every instance. A reel with no matching axis here " +
            "refuses its own mechanism's reels: the axis is authored, " +
            "never inferred.",
            GH_ParamAccess.tree);
        parameters[6].Optional = true;

        parameters.AddPlaneParameter(
            "Routing",
            "RT",
            "The wire's routing frames, tree path {side}{mechanism}" +
            "{wire}: an ordered list of planes per wire, unit-local " +
            "space, in threading order, planes[0] the NET END (his " +
            "ruling; validated after placement, a reversed list is " +
            "named).",
            GH_ParamAccess.tree);
        parameters[7].Optional = true;

        parameters.AddTextParameter(
            "Reel Kind",
            "RK",
            "One word per instance, tree path {side}{mechanism} " +
            "matching Placement (PL): \"edge\" or \"node\", naming which " +
            "functional family this instance belongs to. Optional and " +
            "purely informational: an unspecified instance is still " +
            "built, tagged the generic kind \"mechanism\", and a chin " +
            "remark says so.",
            GH_ParamAccess.tree);
        parameters[8].Optional = true;
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
            "What was received (the mechanism body, its reels, how many " +
            "placements and wires, Anchor/Tension Tie rows, whether a " +
            "Result was wired), then any named warning the door-guard or " +
            "the axis check raised, then any note the chin owes about a " +
            "default or a Brep meshed in passing.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        try
        {
            var warnings = new List<string>();
            var notes = new List<string>();

            bool hasResult = TryReadResult(data, out ResultDto? result);
            List<MechanismAnchorRow>? rows =
                hasResult ? MechanismGeometry.AnchorRows(result!) : null;

            List<MechanismRowPartInput> anchors = ReadRowParts(data, 1, "AN", warnings);
            List<MechanismRowPartInput> ties = ReadRowParts(data, 2, "TT", warnings);
            MechanismAssetInput asset = ReadAsset(data, warnings);
            List<MechanismInstanceInput> instances = ReadInstances(data, warnings);
            List<MechanismWireInput> wires = ReadWires(data, warnings);
            (List<MechanismMeshBranch> reelMeshes, List<MechanismAxisBranch> reelAxes) =
                ReadReels(data, warnings);

            string? payload = MechanismCollector.Build(
                asset, reelMeshes, reelAxes, instances, wires, anchors, ties,
                rows, warnings, notes);

            int reelMeshCount = reelMeshes.Sum(b => b.Meshes.Count);
            var status = new List<string>
            {
                payload is null
                    ? "received: nothing wired; no mechanism document."
                    : "received: mechanism body " +
                      (asset.Body is null ? "not authored" : "authored") +
                      $", {reelMeshCount} reel(s), " +
                      $"{instances.Count} placement(s), {wires.Count} " +
                      $"wire(s), {anchors.Count} anchor(s), {ties.Count} " +
                      "tension tie(s), Result " +
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
                : $"{instances.Count} instance(s), {wires.Count} wire(s)";
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

    private List<MechanismRowPartInput> ReadRowParts(
        IGH_DataAccess data, int index, string label, List<string> warnings)
    {
        var items = new List<object>();
        data.GetDataList(index, items);
        var parts = new List<MechanismRowPartInput>(items.Count);
        for (int i = 0; i < items.Count; i++)
        {
            if (!TryMeshOrBrep(items[i], out MechanismMesh? mesh, out bool fromBrep) ||
                mesh is null)
            {
                warnings.Add(
                    $"{label}[{i}] did not resolve to a mesh or a closed " +
                    "Brep; skipped.");
                continue;
            }
            double[] centroid = MechanismCollector.BoundingBoxCenter(mesh);
            parts.Add(new MechanismRowPartInput(i, mesh, centroid, fromBrep));
        }
        return parts;
    }

    private MechanismAssetInput ReadAsset(IGH_DataAccess data, List<string> warnings)
    {
        object? meItem = null;
        data.GetData(3, ref meItem);
        MechanismMesh? body = null;
        bool bodyFromBrep = false;
        if (meItem is not null)
        {
            if (!TryMeshOrBrep(meItem, out body, out bodyFromBrep) || body is null)
            {
                warnings.Add(
                    "Mechanism (ME) did not resolve to a mesh or a closed " +
                    "Brep; the mechanism has no body.");
                body = null;
            }
        }

        return new MechanismAssetInput(body, bodyFromBrep);
    }

    /// <summary>
    /// Reads Reel (RE) and Reel Axis (AX) as TREES, exactly as he
    /// authors them: a genuine {side}{mechanism} branch per mechanism, or
    /// GH's own default single-branch path for a bare flat list. Only the
    /// raw shape is read here; the Rhino- and Grasshopper-free <see
    /// cref="MechanismCollector.ResolveReelAuthoring"/> decides what it
    /// means, so the same decision the harness drives by reflection is
    /// exactly what runs live. The plane's X and Y are carried through
    /// into <see cref="MechanismFrame"/> UNCHANGED (his ruling): only Z
    /// is ever read as the rotation axis, and that reading happens
    /// downstream, never here.
    /// </summary>
    private (List<MechanismMeshBranch> Meshes, List<MechanismAxisBranch> Axes) ReadReels(
        IGH_DataAccess data, List<string> warnings)
    {
        data.GetDataTree(5, out GH_Structure<IGH_Goo> reTree);
        var meshBranches = new List<MechanismMeshBranch>();
        foreach (GH_Path path in reTree.Paths)
        {
            IList branch = reTree.get_Branch(path);
            var meshes = new List<MechanismMesh?>(branch.Count);
            var fromBrep = new List<bool>(branch.Count);
            for (int i = 0; i < branch.Count; i++)
            {
                object? value = (branch[i] as IGH_Goo)?.ScriptVariable();
                if (!TryMeshOrBrep(value, out MechanismMesh? mesh, out bool brep))
                {
                    warnings.Add(
                        $"Reel (RE)[{string.Join("][", path.Indices)}]" +
                        $"[{i}] did not resolve to a mesh or a closed " +
                        "Brep; treated as missing.");
                    meshes.Add(null);
                    fromBrep.Add(false);
                    continue;
                }
                meshes.Add(mesh);
                fromBrep.Add(brep);
            }
            meshBranches.Add(new MechanismMeshBranch(path.Indices, meshes, fromBrep));
        }

        data.GetDataTree(6, out GH_Structure<GH_Plane> axTree);
        var axisBranches = new List<MechanismAxisBranch>();
        foreach (GH_Path path in axTree.Paths)
        {
            var axes = new List<MechanismFrame?>();
            foreach (GH_Plane planeGoo in axTree.get_Branch(path))
            {
                if (planeGoo is null)
                {
                    axes.Add(null);
                    continue;
                }
                Plane plane = planeGoo.Value;
                // HIS RULING, 2026-09-08 night: X and Y survive unchanged
                // -- they carry his intended spin direction -- never
                // reduced to a bare origin+direction.
                axes.Add(new MechanismFrame(
                    new[] { plane.Origin.X, plane.Origin.Y, plane.Origin.Z },
                    new[] { plane.XAxis.X, plane.XAxis.Y, plane.XAxis.Z },
                    new[] { plane.YAxis.X, plane.YAxis.Y, plane.YAxis.Z }));
            }
            axisBranches.Add(new MechanismAxisBranch(path.Indices, axes));
        }

        return (meshBranches, axisBranches);
    }

    private List<MechanismInstanceInput> ReadInstances(IGH_DataAccess data, List<string> warnings)
    {
        data.GetDataTree(4, out GH_Structure<GH_Plane> plTree);
        data.GetDataTree(8, out GH_Structure<GH_String> rkTree);

        var kinds = new Dictionary<(int Side, int Mechanism), string>();
        foreach (GH_Path path in rkTree.Paths)
        {
            if (path.Indices.Length != 2)
            {
                warnings.Add(
                    $"RK path {{{string.Join(",", path.Indices)}}} is not " +
                    "a {side}{mechanism} two-level path; ignored.");
                continue;
            }
            IList branch = rkTree.get_Branch(path);
            if (branch.Count == 0)
                continue;
            GH_String? textGoo = branch[0] as GH_String;
            if (textGoo is null || string.IsNullOrWhiteSpace(textGoo.Value))
                continue;
            kinds[(path.Indices[0], path.Indices[1])] = textGoo.Value;
        }

        var instances = new List<MechanismInstanceInput>();
        foreach (GH_Path path in plTree.Paths)
        {
            if (path.Indices.Length != 2)
            {
                warnings.Add(
                    $"PL path {{{string.Join(",", path.Indices)}}} is not " +
                    "a {side}{mechanism} two-level path; ignored.");
                continue;
            }
            int side = path.Indices[0];
            int mechanism = path.Indices[1];
            IList branch = plTree.get_Branch(path);
            if (branch.Count == 0)
                continue;
            if (branch.Count > 1)
            {
                warnings.Add(
                    $"PL[{side}][{mechanism}] carries {branch.Count} " +
                    "planes; only the first is used (one plane per " +
                    "instance).");
            }
            GH_Plane? planeGoo = branch[0] as GH_Plane;
            if (planeGoo is null)
            {
                warnings.Add($"PL[{side}][{mechanism}] is null; instance skipped.");
                continue;
            }
            Plane plane = planeGoo.Value;
            var frame = new MechanismFrame(
                new[] { plane.Origin.X, plane.Origin.Y, plane.Origin.Z },
                new[] { plane.XAxis.X, plane.XAxis.Y, plane.XAxis.Z },
                new[] { plane.YAxis.X, plane.YAxis.Y, plane.YAxis.Z });
            kinds.TryGetValue((side, mechanism), out string? kind);
            instances.Add(new MechanismInstanceInput(
                new MechanismInstanceId(side, mechanism), frame, kind));
        }
        return instances;
    }

    private List<MechanismWireInput> ReadWires(IGH_DataAccess data, List<string> warnings)
    {
        data.GetDataTree(7, out GH_Structure<GH_Plane> rtTree);
        var wires = new List<MechanismWireInput>();
        foreach (GH_Path path in rtTree.Paths)
        {
            if (path.Indices.Length != 3)
            {
                warnings.Add(
                    $"RT path {{{string.Join(",", path.Indices)}}} is not " +
                    "a {side}{mechanism}{wire} three-level path; ignored.");
                continue;
            }
            int side = path.Indices[0];
            int mechanism = path.Indices[1];
            int wire = path.Indices[2];
            var frames = new List<MechanismFrame>();
            foreach (GH_Plane planeGoo in rtTree.get_Branch(path))
            {
                if (planeGoo is null)
                    continue;
                Plane plane = planeGoo.Value;
                frames.Add(new MechanismFrame(
                    new[] { plane.Origin.X, plane.Origin.Y, plane.Origin.Z },
                    new[] { plane.XAxis.X, plane.XAxis.Y, plane.XAxis.Z },
                    new[] { plane.YAxis.X, plane.YAxis.Y, plane.YAxis.Z }));
            }
            if (frames.Count == 0)
            {
                warnings.Add(
                    $"RT[{side}][{mechanism}][{wire}] carries no routing " +
                    "planes; wire dropped.");
                continue;
            }
            wires.Add(new MechanismWireInput(
                new MechanismInstanceId(side, mechanism), wire, frames));
        }
        return wires;
    }

    /// <summary>
    /// Reads a mesh directly, or a closed Brep meshed here with Rhino's
    /// default meshing parameters (spec's own validation list: "a brep
    /// accepted and meshed says so with the settings used" -- the note
    /// itself is added by <see cref="MechanismCollector"/> from the
    /// <c>fromBrep</c> flag this returns, so the setting stays named in
    /// ONE place).
    /// </summary>
    private static bool TryMeshOrBrep(object? item, out MechanismMesh? mesh, out bool fromBrep)
    {
        fromBrep = false;
        mesh = null;
        switch (item)
        {
            case Mesh m:
                mesh = MeshFromRhino(m);
                return true;
            case Brep b:
                Mesh[] pieces = Mesh.CreateFromBrep(b, MeshingParameters.Default);
                if (pieces is null || pieces.Length == 0)
                    return false;
                var joined = new Mesh();
                foreach (Mesh piece in pieces)
                    joined.Append(piece);
                mesh = MeshFromRhino(joined);
                fromBrep = true;
                return true;
            default:
                return false;
        }
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
