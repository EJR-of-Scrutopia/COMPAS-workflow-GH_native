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
/// HIS MODEL, settled 2026-09-08, verbatim: "take one mechanism, there is 3
/// per side at the moment linked via 7 wires each. I will [give] the
/// component everything for one component like this. Reel 1-10, reel 1-10
/// with axis, mechanism frame 1, mechanism frame 2, motors, tension tie,
/// wire routing frames, placement planes (this will be for all wires, set
/// into 7 and into side, so that you will know 7 anchors = 1 mechanism, and
/// its already branched that way, then which side they are)". THIS
/// SUPERSEDES THE {type}{part} PORT SCHEME (and the 2026-09-08-night NAMED
/// PORTS scheme built on top of it) ENTIRE.
///
/// ONE MECHANISM IS AUTHORED, ONCE, in its own local space -- reels, reel
/// axes, both frame parts, the motors, the fused tension tie and the seven
/// wires' routing frames -- and INSTANCED at every placement branch,
/// exactly the studio's 8 GB iPad constraint already demanded of the
/// single-body scheme this replaces. Every part he authors lives in that
/// SAME local space, and the ONE derived instance transform (below) is
/// applied to all of them, unchanged and identically: relative arrangement
/// -- a reel's exact seat against its own frame -- is preserved by
/// construction, never independently placed or inferred.
/// </summary>
internal sealed record MechanismMesh(
    IReadOnlyList<double[]> Vertices,
    IReadOnlyList<int[]> Faces);

/// <summary>
/// One routing (or reel axis) frame: origin and all THREE axes, Z CARRIED
/// rather than derived.
///
/// Z WAS ONCE DERIVED AS X CROSS Y AND THAT WAS A BUG, found by this
/// component's own rebuild and fixed here. The authored mechanism itself is
/// never mirrored, so a derived Z was sound where the frame was WRITTEN; but
/// an INSTANCE frame is the derived placement transform, and Param's far side
/// is a REFLECTION, whose basis is left-handed. There X cross Y points
/// OPPOSITE the true Z, so any local point with an out-of-plane component
/// landed on the wrong side of the frame. Carrying the real Z removes the
/// question entirely rather than making every reader remember the handedness.
/// </summary>
internal sealed record MechanismFrame(
    double[] Origin,
    double[] XAxis,
    double[] YAxis,
    double[] ZAxis);

/// <summary>
/// A placement TARGET plane (Placement/PL), his own authored frame in world
/// space: origin plus X, Y AND Z, all three read TRUE off the Rhino plane,
/// Z NEVER re-derived as X cross Y. This is the one place handedness must
/// survive intact -- when he mirrors a plane for the far side, Rhino's own
/// Transform leaves its stored ZAxis genuinely LEFT-HANDED (ZAxis no longer
/// equal to XAxis cross YAxis), and that is exactly the signal the
/// placement maths below reads to build a reflection rather than a
/// rotation. Deriving Z here, the way <see cref="MechanismFrame"/> does,
/// would silently throw that signal away and turn every mirrored instance
/// into an upside-down one instead of a flipped one.
/// </summary>
internal sealed record MechanismPlacementPlane(
    double[] Origin, double[] XAxis, double[] YAxis, double[] ZAxis);

/// <summary>ONE ROTATING REEL: its mesh and its rotation-axis frame, unit-local space, one of ten.</summary>
internal sealed record MechanismReelEntry(
    MechanismMesh Mesh,
    bool FromBrep,
    MechanismFrame Axis);

/// <summary>
/// THE ONE AUTHORED MECHANISM, his five parts (plus the reels' own axes,
/// which travel with them): Frame 1, one joined mesh; Frame 2, a SECOND
/// frame part in a different material, several objects, joined only as far
/// as he can join them; the Motors, one joined mesh; the Tension Tie, ONE
/// FUSED mesh (his settled ruling: the foundation anchor and the tension
/// tie are now one object, so this single part carries both, permanence
/// "permanent"); and the Reels, ten meshes each with its own authored axis
/// plane, kept as SEPARATE meshes (his own words: "its not all combined as
/// one mesh in the frame") rather than joined into Frame 1, because a reel
/// spins and a frame does not.
/// </summary>
internal sealed record MechanismAssetInput(
    MechanismMesh? Frame1,
    bool Frame1FromBrep,
    IReadOnlyList<MechanismMesh> Frame2,
    IReadOnlyList<bool> Frame2FromBrep,
    MechanismMesh? Motors,
    bool MotorsFromBrep,
    MechanismMesh? TensionTie,
    bool TensionTieFromBrep,
    IReadOnlyList<MechanismMesh?> ReelMeshes,
    IReadOnlyList<bool> ReelFromBrep,
    IReadOnlyList<MechanismFrame?> ReelAxes);

/// <summary>
/// ONE OF THE SEVEN WIRES the one authored mechanism routes, indexed by
/// wire number (0..6) rather than by instance -- routing is authored ONCE,
/// for the mechanism, never per placement. An ordered list of local routing
/// planes in threading order, <c>Route[0]</c> the NET END by his ruling
/// (R2), and also -- new here -- the FIRST CORRESPONDENCE every placement
/// branch derives its instance transform from when <c>Wire == 0</c>.
/// </summary>
internal sealed record MechanismRoutingWire(int Wire, IReadOnlyList<MechanismFrame> Route);

/// <summary>One instance address: side then group of seven, his own tree order ("mechanisms per side, sides").</summary>
internal readonly record struct MechanismInstanceId(int Side, int Group)
{
    public string Label => $"side {Side} group {Group}";
}

/// <summary>
/// ONE PLACEMENT BRANCH ({side}{group}): the seven world-space target
/// planes his placement authors for one mechanism instance's seven wires,
/// <c>Planes[i]</c> corresponding to Routing wire <c>i</c>. His own words:
/// "placement planes, this will be for all wires, set into 7 and into
/// side, so that you will know 7 anchors = 1 mechanism, and its already
/// branched that way, then which side they are".
/// </summary>
internal sealed record MechanismPlacementBranch(
    MechanismInstanceId Id, IReadOnlyList<MechanismPlacementPlane> Planes);

/// <summary>
/// The pure packaging and placement-derivation logic behind the MECHANISM
/// collector: no Rhino type crosses this boundary, so the harness can drive
/// every rule with arrays it builds itself.
///
/// ONE JOB: turn what was wired into one JSON payload Export can embed, and
/// say by name what could not be trusted rather than silently dropping it
/// or silently accepting it.
/// </summary>
internal static class MechanismCollector
{
    /// <summary>
    /// The permanence field's own name and its two values, said once and
    /// read everywhere a part payload is built. Param's ruling: "the two
    /// things that remain when all is taken away is the tension tie /
    /// column slide, and the anchor" -- now ONE fused part -- are the
    /// PERMANENT works; Frame 1, Frame 2, the Motors, the reels and the
    /// wires that reel them are the TEMPORARY machine that comes away once
    /// the vault stands.
    /// </summary>
    public const string PermanenceField = "permanence";

    public const string Permanent = "permanent";

    public const string Temporary = "temporary";

    /// <summary>
    /// STILL READ BY EXPORT'S OWN SEAM (<c>MechanismDocument.Json</c> in
    /// ExportPayloads.cs, untouched by this rebuild): the wire-to-net-vertex
    /// match-distance door-guard tolerance, a multiple of the matched row's
    /// own characteristic anchor spacing. Kept here, by name, even though
    /// this file's own AN/TT door-guard that ORIGINALLY used it is gone now
    /// the tie arrives fused and unplaced by this collector.
    /// </summary>
    public const double AnchorTieToleranceFactor = 3.0;

    public const double MinimumAnchorTieTolerance = 1.0e-6;

    public const double MinimumSpoolRadius = 1.0e-6;

    /// <summary>
    /// ROUTING FRAME OWNERSHIP, his ruling confirmed 2026-09-08: "it is
    /// option 2. i have modelled the wire to wrap around the drums." A
    /// routing frame that sits on a rotating reel is no longer fixed
    /// hardware -- treating it as fixed while the reel spins reads as the
    /// wire slipping under a still drum, backwards from the reeling he
    /// built. UNCHANGED by this rebuild (7c8db59); only its callers'
    /// per-instance bookkeeping simplified to a single authored mechanism.
    /// </summary>
    public const string RouteOwnerField = "owner";

    public const string RouteOwnerReelField = "ownerReel";

    public const string RouteOwnerBody = "body";

    public const string RouteOwnerReel = "reel";

    /// <summary>
    /// No reel owns this frame: the sentinel <c>ownerReel</c> carries when
    /// <c>owner</c> is <see cref="RouteOwnerBody"/>, the same "no index"
    /// convention a tree with no notch already uses elsewhere in this
    /// plugin (ColumnPlacement's own <c>footIndex[t] == -1</c>).
    /// </summary>
    public const int NoOwnerReel = -1;

    public const double MinimumReelExtentRadius = 1.0e-6;

    /// <summary>
    /// How close a frame's own distance-to-axis, relative to that reel's
    /// own radius, may sit to the 1.0 ownership boundary -- or how close a
    /// SECOND reel's own ratio may also sit at or under it -- before the
    /// classification is NAMED rather than trusted silently.
    /// </summary>
    public const double RouteOwnerAmbiguityMargin = 0.15;

    /// <summary>His machine: seven wires, seven placement planes, per mechanism instance.</summary>
    public const int PlacementGroupSize = 7;

    /// <summary>His machine, nominal: ten reels per mechanism. Used only for the "unusual but used as authored" note, never enforced.</summary>
    public const int ExpectedReelCount = 10;

    /// <summary>
    /// The placement door-guard's own tolerance: how far, in metres, the
    /// derived transform may disagree with the six OTHER placement planes
    /// before it is named. Small and deliberate -- this is the redundancy
    /// that makes a bad placement plane show as a number, never a silently
    /// skewed machine.
    /// </summary>
    public const double MaxResidualWarnMetres = 0.001;

    /// <summary>How close a 3x3 basis's own determinant may sit to zero before it is refused as singular (coincident or collinear axes).</summary>
    public const double SingularBasisDeterminantEpsilon = 1.0e-9;

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
        IReadOnlyList<MechanismRoutingWire> routing,
        IReadOnlyList<MechanismPlacementBranch> placements,
        List<string> warnings,
        List<string> notes)
    {
        ArgumentNullException.ThrowIfNull(asset);
        ArgumentNullException.ThrowIfNull(routing);
        ArgumentNullException.ThrowIfNull(placements);
        ArgumentNullException.ThrowIfNull(warnings);
        ArgumentNullException.ThrowIfNull(notes);

        bool anyAssetPart =
            asset.Frame1 is not null || asset.Frame2.Count > 0 || asset.Motors is not null ||
            asset.TensionTie is not null || asset.ReelMeshes.Count > 0 || asset.ReelAxes.Count > 0;
        bool anyRouting = routing.Any(w => w.Route.Count > 0);
        bool nothingWired = !anyAssetPart && !anyRouting && placements.Count == 0;
        if (nothingWired)
            return null;

        if (!anyAssetPart && (placements.Count > 0 || anyRouting))
        {
            warnings.Add(
                "Placement (PL) or Routing (RT) was authored, but no " +
                "mechanism part (Frame 1, Frame 2, Motors, Tension Tie or " +
                "Reel) was; nothing is instanced without a mechanism to " +
                "instance.");
        }

        // TEN REELS, EACH SEPARATE, EACH ITS OWN AXIS (his ruling,
        // 2026-09-08: "as long as the reel is place correctly in the
        // mechanism, its not all combined as one mesh in the frame ...
        // you will need to know where its placed in relation to the rest
        // of the frames"). Zipped by POSITION, never re-grouped: a reel
        // without a matching axis (or an axis without a matching reel)
        // refuses ONLY that reel, by name -- the axis is authored, never
        // inferred.
        List<MechanismReelEntry> reels =
            ResolveReelsFlat(asset.ReelMeshes, asset.ReelFromBrep, asset.ReelAxes, warnings);
        if (asset.ReelMeshes.Count > 0 && asset.ReelMeshes.Count != ExpectedReelCount)
        {
            notes.Add(
                $"mechanism: Reel (RE) carries {asset.ReelMeshes.Count} " +
                "reel(s); his machine is ten, so this is unusual but used " +
                "as authored.");
        }
        if (reels.Count > 0)
        {
            // BUILD THE INDEPENDENT CASE (his second open point, settled):
            // he said seven of the ten move identically, but authors all
            // ten with their own axis, so every reel here spins about ITS
            // OWN authored axis rather than being collapsed into a shared
            // group of four.
            notes.Add(
                $"mechanism: {reels.Count} reel(s) resolved, each spinning " +
                "INDEPENDENTLY about its own authored axis -- his ruling " +
                "that seven of the ten move identically in practice is " +
                "read as a fact about the machine, not a grouping to " +
                "build: every reel here is driven by its own axis.");
        }

        Dictionary<string, object?>? mechanismOut = null;
        if (anyAssetPart)
        {
            mechanismOut = new Dictionary<string, object?>(StringComparer.Ordinal);

            if (asset.Frame1 is not null)
            {
                Dictionary<string, object?> f1 = MeshPayload(asset.Frame1);
                f1[PermanenceField] = Temporary;
                mechanismOut["frame1"] = f1;
                if (asset.Frame1FromBrep)
                    notes.Add($"Frame 1 (F1) {BrepMeshingNote}");
            }
            else
            {
                mechanismOut["frame1"] = null;
            }

            var f2Out = new List<Dictionary<string, object?>>(asset.Frame2.Count);
            for (int i = 0; i < asset.Frame2.Count; i++)
            {
                Dictionary<string, object?> f2 = MeshPayload(asset.Frame2[i]);
                f2[PermanenceField] = Temporary;
                f2Out.Add(f2);
                if (i < asset.Frame2FromBrep.Count && asset.Frame2FromBrep[i])
                    notes.Add($"Frame 2 (F2)[{i}] {BrepMeshingNote}");
            }
            mechanismOut["frame2"] = f2Out;

            if (asset.Motors is not null)
            {
                Dictionary<string, object?> mo = MeshPayload(asset.Motors);
                mo[PermanenceField] = Temporary;
                mechanismOut["motors"] = mo;
                if (asset.MotorsFromBrep)
                    notes.Add($"Motors (MO) {BrepMeshingNote}");
            }
            else
            {
                mechanismOut["motors"] = null;
            }

            if (asset.TensionTie is not null)
            {
                Dictionary<string, object?> tt = MeshPayload(asset.TensionTie);
                tt[PermanenceField] = Permanent;
                mechanismOut["tensionTie"] = tt;
                // OPEN POINT (1), SETTLED: "the anchor and tension tie and
                // now one" -- the reading is on the record, every time,
                // rather than assumed silently.
                notes.Add(
                    "mechanism: Tension Tie (TT) arrived as ONE FUSED " +
                    "object (the foundation anchor and the tension tie " +
                    "together), his settled ruling; tagged permanence " +
                    "\"permanent\".");
                if (asset.TensionTieFromBrep)
                    notes.Add($"Tension Tie (TT) {BrepMeshingNote}");
            }
            else
            {
                mechanismOut["tensionTie"] = null;
            }

            var reelsOut = new List<Dictionary<string, object?>>(reels.Count);
            for (int i = 0; i < reels.Count; i++)
            {
                // THE REEL AXIS PLANE STAYS LOCAL, X AND Y RAW (never
                // re-derived): it lives in the SAME local space as Frame 1,
                // Frame 2, the Motors and the Tension Tie, and is carried
                // by the SAME derived instance transform they are (see the
                // placement loop below). Because a rotation axis is a
                // PSEUDOVECTOR, carrying its authored X and Y through that
                // transform (rather than only its origin or only a bare
                // direction) is what gives the correct rotation SENSE on a
                // mirrored instance: Z' = X' cross Y' flips sign under a
                // reflection exactly the way a mirror flips the sense a
                // spinning wheel is seen to turn. Transforming only a
                // direction vector would lose that sign and leave a
                // mirrored machine whose reels turn the wrong way -- wrong
                // for the whole animation, invisible in a still frame.
                reelsOut.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["reel"] = i,
                    ["mesh"] = MeshPayload(reels[i].Mesh),
                    ["axis"] = FramePayload(reels[i].Axis),
                    ["driven"] = true,
                    [PermanenceField] = Temporary,
                });
                if (reels[i].FromBrep)
                    notes.Add($"Reel (RE)[{i}] {BrepMeshingNote}");
            }
            mechanismOut["reels"] = reelsOut;

            // SPOOL RADIUS: reel[0]'s own bounding box smallest dimension
            // over 4, falling back down the rest of the mechanism's parts
            // when no reel resolved, said in the chin so the default is
            // never silent.
            MechanismMesh? spoolSource = reels.Count > 0
                ? reels[0].Mesh
                : asset.Frame1 ?? asset.Motors ?? asset.TensionTie ??
                  (asset.Frame2.Count > 0 ? asset.Frame2[0] : null);
            double spoolRadius = spoolSource is not null
                ? Math.Max(SmallestBoundingDimension(spoolSource) / 4.0, MinimumSpoolRadius)
                : MinimumSpoolRadius;
            notes.Add(
                "mechanism: spoolRadius defaulted to " +
                spoolRadius.ToString("0.####", CultureInfo.InvariantCulture) +
                (reels.Count > 0
                    ? " from reel[0]'s own bounding box (smallest " +
                      "dimension over 4)."
                    : spoolSource is not null
                        ? " from the frame/motors/tie's own bounding box " +
                          "(smallest dimension over 4), since no reel " +
                          "resolved."
                        : " from the floor value, since no geometry was " +
                          "wired to derive it from."));

            // THE REEVE FACTOR IS PROVISIONAL (his ruling, verbatim: "i
            // dont [want] it to be accurate righ tnow"). Fixed at 1.0, no
            // authored port, said here every time a mechanism is built.
            notes.Add(
                "mechanism: reeveFactor is fixed at 1.0 -- PROVISIONAL, " +
                "not accurate, per his own ruling that accuracy is not " +
                "wanted right now; every reel's spin RATE is likely wrong " +
                "until a real reeve factor is authored.");

            mechanismOut["reeveFactor"] = 1.0;
            mechanismOut["spoolRadius"] = spoolRadius;
        }

        // ROUTING: the ONE authored mechanism's wire frames, indexed
        // 0..6 -- authored ONCE, never per instance. A wire whose list is
        // empty carries no first frame, named by index; wire 0 is the
        // FIRST CORRESPONDENCE every placement derives from, so its
        // absence is fatal to every instance, not just its own wire.
        var routingByIndex = new Dictionary<int, MechanismRoutingWire>();
        foreach (MechanismRoutingWire wire in routing)
        {
            if (routingByIndex.ContainsKey(wire.Wire))
                warnings.Add($"Routing (RT)[{wire.Wire}] appears more than once; the later branch wins.");
            routingByIndex[wire.Wire] = wire;
        }
        for (int w = 0; w < PlacementGroupSize; w++)
        {
            if (!routingByIndex.TryGetValue(w, out MechanismRoutingWire? wire) || wire.Route.Count == 0)
            {
                warnings.Add(
                    $"Routing (RT)[{w}] carries no routing planes; it has " +
                    $"no first frame, so wire {w} is dropped from every " +
                    "instance" +
                    (w == 0
                        ? " AND NO MECHANISM INSTANCE CAN BE PLACED, since " +
                          "wire 0's first frame is the correspondence every " +
                          "placement derives its transform from."
                        : "."));
            }
        }

        // ROUTING FRAME OWNERSHIP (7c8db59, unchanged): classified ONCE
        // against the mechanism's own reels, since both are authored once
        // now -- never per instance.
        var ownerCounts = new Dictionary<string, int>(StringComparer.Ordinal) { [RouteOwnerBody] = 0 };
        for (int r = 0; r < reels.Count; r++)
            ownerCounts[$"reel {r}"] = 0;
        var classifiedRoutes = new Dictionary<int, List<(MechanismFrame Frame, string Owner, int OwnerReel)>>();
        for (int w = 0; w < PlacementGroupSize; w++)
        {
            if (!routingByIndex.TryGetValue(w, out MechanismRoutingWire? wire) || wire.Route.Count == 0)
                continue;
            var classified = new List<(MechanismFrame, string, int)>(wire.Route.Count);
            for (int frameIndex = 0; frameIndex < wire.Route.Count; frameIndex++)
            {
                MechanismFrame frame = wire.Route[frameIndex];
                (string owner, int ownerReel, string? ambiguity) = ClassifyRouteFrameOwner(frame, reels);
                string countKey = owner == RouteOwnerReel ? $"reel {ownerReel}" : RouteOwnerBody;
                ownerCounts[countKey] = ownerCounts.GetValueOrDefault(countKey) + 1;
                if (ambiguity is not null)
                {
                    warnings.Add(
                        $"Routing (RT)[{w}] frame [{frameIndex}]: ownership " +
                        $"is AMBIGUOUS ({ambiguity}); assigned " +
                        (owner == RouteOwnerReel ? $"reel {ownerReel}" : "the body") +
                        " as the nearest, never picked silently -- look at it.");
                }
                classified.Add((frame, owner, ownerReel));
            }
            classifiedRoutes[w] = classified;
        }
        if (classifiedRoutes.Count > 0)
        {
            string tally = string.Join(
                ", ",
                ownerCounts.OrderBy(p => p.Key, StringComparer.Ordinal)
                    .Select(p => $"{p.Key} {p.Value}"));
            notes.Add($"mechanism: routing frame ownership, the ONE authored mechanism -- {tally}.");
        }

        // PLACEMENT: one instance transform per branch, derived from the
        // FIRST CORRESPONDENCE (wire 0's first routing frame S_0 against
        // the branch's own plane 0, T_0), then validated against the other
        // six. See the class doc and MechanismPlacementPlane for why T's Z
        // is read true rather than derived: that is what lets a mirrored
        // branch yield a genuine reflection here.
        var instancesOut = new List<Dictionary<string, object?>>();
        var wiresOut = new List<Dictionary<string, object?>>();

        bool haveS0 = routingByIndex.TryGetValue(0, out MechanismRoutingWire? wire0) && wire0.Route.Count > 0;
        double[][]? mSInverse = null;
        if (haveS0)
        {
            MechanismFrame s0 = wire0!.Route[0];
            double[] zS = CrossProduct(s0.XAxis, s0.YAxis);
            double[][] mS = BasisFromColumns(s0.XAxis, s0.YAxis, zS);
            mSInverse = Invert3(mS);
            if (mSInverse is null)
            {
                warnings.Add(
                    "Routing (RT)[0]'s own first frame has coincident or " +
                    "collinear X/Y axes (the basis is singular); no " +
                    "mechanism instance can be placed from it.");
            }
        }

        if (mSInverse is not null)
        {
            MechanismFrame s0 = wire0!.Route[0];
            foreach (MechanismPlacementBranch branch in placements
                .OrderBy(b => b.Id.Side).ThenBy(b => b.Id.Group))
            {
                string label = branch.Id.Label;
                if (branch.Planes.Count != PlacementGroupSize)
                {
                    warnings.Add(
                        $"Placement (PL) {label}: carries " +
                        $"{branch.Planes.Count} plane(s), not the seven a " +
                        "mechanism instance needs (one per wire); instance refused.");
                    continue;
                }

                MechanismPlacementPlane t0 = branch.Planes[0];
                double[][] mT = BasisFromColumns(t0.XAxis, t0.YAxis, t0.ZAxis);
                double detT = Determinant3(mT);
                if (Math.Abs(detT) < SingularBasisDeterminantEpsilon)
                {
                    warnings.Add(
                        $"Placement (PL) {label}: its own first plane has " +
                        "coincident or collinear axes (the basis is " +
                        "singular); instance refused.");
                    continue;
                }

                // L = M_T * inverse(M_S), applied whole -- never forced to
                // a rotation, so a left-handed T0 yields a reflection.
                double[][] linear = Multiply3(mT, mSInverse);
                double[] linearOs = MultiplyVector3(linear, s0.Origin);
                double[] translation =
                {
                    t0.Origin[0] - linearOs[0],
                    t0.Origin[1] - linearOs[1],
                    t0.Origin[2] - linearOs[2],
                };
                double det = Determinant3(linear);
                bool reflected = det < 0.0;
                if (reflected)
                {
                    notes.Add(
                        $"Placement (PL) {label}: derived transform is A " +
                        "REFLECTION (determinant " +
                        det.ToString("0.###", CultureInfo.InvariantCulture) +
                        "); expected for a mirrored side, not an error.");
                }

                // VALIDATE WITH THE OTHER SIX: the redundancy that makes a
                // bad placement plane show as a number, never a silently
                // skewed machine. Reported ALWAYS, whichever way it comes out.
                double maxResidual = 0.0;
                int validated = 0;
                for (int i = 1; i < PlacementGroupSize; i++)
                {
                    if (!routingByIndex.TryGetValue(i, out MechanismRoutingWire? wireI) ||
                        wireI.Route.Count == 0)
                    {
                        continue;
                    }
                    double[] predicted = MultiplyVector3(linear, wireI.Route[0].Origin);
                    predicted[0] += translation[0];
                    predicted[1] += translation[1];
                    predicted[2] += translation[2];
                    double residual = Distance(predicted, branch.Planes[i].Origin);
                    if (residual > maxResidual)
                        maxResidual = residual;
                    validated++;
                }
                if (validated == 0)
                {
                    notes.Add(
                        $"Placement (PL) {label}: residual check could not " +
                        "run -- only Routing (RT)[0] carries frames, " +
                        "nothing else to validate the placement against.");
                }
                else
                {
                    notes.Add(
                        $"Placement (PL) {label}: max residual " +
                        maxResidual.ToString("0.######", CultureInfo.InvariantCulture) +
                        $" m across {validated} of 6 other wire(s).");
                    if (maxResidual > MaxResidualWarnMetres)
                    {
                        warnings.Add(
                            $"Placement (PL) {label}: max residual " +
                            maxResidual.ToString("0.######", CultureInfo.InvariantCulture) +
                            $" m exceeds the {MaxResidualWarnMetres} m " +
                            "door-guard -- this placement plane set may " +
                            "not be well-founded.");
                    }
                }

                instancesOut.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["side"] = branch.Id.Side,
                    ["mechanism"] = branch.Id.Group,
                    // THE FRAME FIELD, KEPT FOR EXPORT'S OWN UNCHANGED SEAM
                    // (MechanismDocument.Json/TransformLocal): origin plus
                    // the derived transform's own X and Y columns. A
                    // reflected instance's X/Y are still exactly right;
                    // ONLY a routing frame's own LOCAL Z-component would be
                    // mis-signed by that seam's own X-cross-Y derivation,
                    // a known, out-of-scope limit of a two-axis frame
                    // representation, not fixed by this rebuild.
                    ["frame"] = FramePayload(new MechanismFrame(
                        translation,
                        Column3(linear, 0),
                        Column3(linear, 1),
                        Column3(linear, 2))),
                    ["kind"] = "mechanism",
                    ["placement"] = "instance",
                    // THE FULL DERIVED TRANSFORM, informational: every row
                    // of L, so a future reader is never limited to the
                    // two-axis frame above.
                    ["linear"] = new[] { linear[0], linear[1], linear[2] },
                    ["reflected"] = reflected,
                    ["residualM"] = validated > 0 ? (object)maxResidual : null,
                });

                for (int w = 0; w < PlacementGroupSize; w++)
                {
                    if (!classifiedRoutes.TryGetValue(w, out List<(MechanismFrame Frame, string Owner, int OwnerReel)>? route))
                        continue;
                    wiresOut.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["side"] = branch.Id.Side,
                        ["mechanism"] = branch.Id.Group,
                        ["wire"] = w,
                        ["route"] = route
                            .Select(r => RouteFramePayload(r.Frame, r.Owner, r.OwnerReel))
                            .ToList(),
                    });
                }
            }
        }
        else if (placements.Count > 0)
        {
            warnings.Add(
                $"{placements.Count} Placement (PL) branch(es) were " +
                "authored, but no mechanism instance could be derived " +
                "(see the routing warning above); nothing is instanced.");
        }

        var payload = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["mechanism"] = mechanismOut,
            ["instances"] = instancesOut,
            ["wires"] = wiresOut,
            // ANCHOR ARRIVES FUSED INTO TENSION TIE NOW (open point 1,
            // settled): no separate port, so this array stays empty; kept,
            // never removed, since Export's own seam reads it.
            ["anchors"] = new List<object>(),
            // A LIGHTWEIGHT REFERENCE, not a second copy of the mesh: the
            // fused tie's own vertices live ONCE, under mechanism.tensionTie,
            // instanced exactly like Frame 1/2, the Motors and the reels;
            // this top-level array exists only so the permanence view keeps
            // a place to find the tie's tag without knowing to look inside
            // "mechanism".
            ["tensionTies"] = asset.TensionTie is not null
                ? new List<Dictionary<string, object?>>
                  {
                      new(StringComparer.Ordinal)
                      {
                          ["ref"] = "mechanism.tensionTie",
                          [PermanenceField] = Permanent,
                      },
                  }
                : new List<Dictionary<string, object?>>(),
        };
        return JsonSerializer.Serialize(payload, ContractJson.Options);
    }

    /// <summary>
    /// TEN REELS, ZIPPED BY POSITION: pairs Reel (RE)[i] with Reel Axis
    /// (AX)[i]; a mesh with no matching axis, or an axis with no matching
    /// mesh, refuses ONLY that index, by name -- the axis is authored,
    /// never inferred, and a mismatch elsewhere never costs a reel that
    /// resolved cleanly.
    /// </summary>
    private static List<MechanismReelEntry> ResolveReelsFlat(
        IReadOnlyList<MechanismMesh?> meshes,
        IReadOnlyList<bool> fromBrep,
        IReadOnlyList<MechanismFrame?> axes,
        List<string> warnings)
    {
        int count = Math.Max(meshes.Count, axes.Count);
        var reels = new List<MechanismReelEntry>(count);
        for (int i = 0; i < count; i++)
        {
            MechanismMesh? mesh = i < meshes.Count ? meshes[i] : null;
            MechanismFrame? axis = i < axes.Count ? axes[i] : null;
            if (mesh is null && axis is null)
                continue;
            if (mesh is null || axis is null)
            {
                warnings.Add(
                    mesh is null
                        ? $"Reel Axis (AX)[{i}] was authored but Reel " +
                          $"(RE)[{i}] carries no matching reel mesh; the " +
                          "axis is authored, never inferred, so reel " +
                          $"{i} is refused."
                        : $"Reel (RE)[{i}] was authored but Reel Axis " +
                          $"(AX)[{i}] carries no matching axis plane; the " +
                          "axis is authored, never inferred, so reel " +
                          $"{i} is refused.");
                continue;
            }
            reels.Add(new MechanismReelEntry(mesh, i < fromBrep.Count && fromBrep[i], axis));
        }
        return reels;
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
            ["zAxis"] = frame.ZAxis,
        };

    /// <summary>
    /// A routing frame with its OWNER stamped alongside -- the static
    /// body, or the reel it rides. Built on <see cref="FramePayload"/>, so
    /// the frame's own origin and axes are byte-identical to a plain
    /// routing/axis frame; <see cref="RouteOwnerField"/> and
    /// <see cref="RouteOwnerReelField"/> are the only addition.
    /// </summary>
    internal static Dictionary<string, object?> RouteFramePayload(
        MechanismFrame frame, string owner, int ownerReel)
    {
        Dictionary<string, object?> payload = FramePayload(frame);
        payload[RouteOwnerField] = owner;
        payload[RouteOwnerReelField] = ownerReel;
        return payload;
    }

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

    internal static double Distance(double[] a, double[] b)
    {
        double dx = a[0] - b[0];
        double dy = a[1] - b[1];
        double dz = a[2] - b[2];
        return Math.Sqrt((dx * dx) + (dy * dy) + (dz * dz));
    }

    /// <summary>
    /// The perpendicular distance from a point to a line given as an
    /// origin plus a UNIT direction: plain arithmetic, Rhino-free, the
    /// same reasoning as <c>MechanismDocument.TransformLocal</c>'s own
    /// hand-rolled cross product -- RhinoCommon's native convenience
    /// members throw outside Rhino.
    /// </summary>
    internal static double PerpendicularDistanceToLine(
        double[] point, double[] lineOrigin, double[] lineDirectionUnit)
    {
        double[] toPoint =
        {
            point[0] - lineOrigin[0],
            point[1] - lineOrigin[1],
            point[2] - lineOrigin[2],
        };
        double along =
            (toPoint[0] * lineDirectionUnit[0]) +
            (toPoint[1] * lineDirectionUnit[1]) +
            (toPoint[2] * lineDirectionUnit[2]);
        double[] perpendicular =
        {
            toPoint[0] - (along * lineDirectionUnit[0]),
            toPoint[1] - (along * lineDirectionUnit[1]),
            toPoint[2] - (along * lineDirectionUnit[2]),
        };
        return Math.Sqrt(
            (perpendicular[0] * perpendicular[0]) +
            (perpendicular[1] * perpendicular[1]) +
            (perpendicular[2] * perpendicular[2]));
    }

    internal static double[] CrossProduct(double[] a, double[] b) => new[]
    {
        (a[1] * b[2]) - (a[2] * b[1]),
        (a[2] * b[0]) - (a[0] * b[2]),
        (a[0] * b[1]) - (a[1] * b[0]),
    };

    /// <summary>
    /// A unit vector, or world Z as a degenerate-axis guard (an authored
    /// plane whose X and Y happen to be parallel), so a broken axis frame
    /// still classifies rather than divides by zero.
    /// </summary>
    internal static double[] NormalizeOrZ(double[] v)
    {
        double length = Math.Sqrt((v[0] * v[0]) + (v[1] * v[1]) + (v[2] * v[2]));
        return length < 1.0e-12
            ? new double[] { 0.0, 0.0, 1.0 }
            : new[] { v[0] / length, v[1] / length, v[2] / length };
    }

    /// <summary>
    /// A REEL'S OWN RADIAL NEIGHBOURHOOD: the furthest any of its OWN mesh
    /// vertices sits from its OWN axis line, measured perpendicular to
    /// that axis. Floored, like spoolRadius, so an empty or degenerate
    /// mesh cannot divide a ratio by zero.
    /// </summary>
    internal static double ReelRadialExtent(MechanismMesh mesh, MechanismFrame axis)
    {
        double[] axisDirection = NormalizeOrZ(CrossProduct(axis.XAxis, axis.YAxis));
        double maxRadius = 0.0;
        foreach (double[] vertex in mesh.Vertices)
        {
            double radius = PerpendicularDistanceToLine(vertex, axis.Origin, axisDirection);
            if (radius > maxRadius)
                maxRadius = radius;
        }
        return Math.Max(maxRadius, MinimumReelExtentRadius);
    }

    /// <summary>
    /// THE OWNERSHIP RULE (7c8db59, unchanged): a routing frame belongs to
    /// the reel whose own radial neighbourhood it sits nearest, relative to
    /// that reel's own size. WARNS, NEVER GUESSES SILENTLY, on a frame
    /// close to the 1.0 boundary or near two reels at once.
    /// </summary>
    internal static (string Owner, int OwnerReel, string? Ambiguity) ClassifyRouteFrameOwner(
        MechanismFrame frame, IReadOnlyList<MechanismReelEntry> reels)
    {
        if (reels.Count == 0)
            return (RouteOwnerBody, NoOwnerReel, null);

        double bestRatio = double.PositiveInfinity;
        int bestIndex = -1;
        double bestDistance = 0.0;
        double bestRadius = 0.0;
        double secondRatio = double.PositiveInfinity;
        int secondIndex = -1;
        double secondDistance = 0.0;
        double secondRadius = 0.0;

        for (int i = 0; i < reels.Count; i++)
        {
            double[] axisDirection = NormalizeOrZ(
                CrossProduct(reels[i].Axis.XAxis, reels[i].Axis.YAxis));
            double distance = PerpendicularDistanceToLine(
                frame.Origin, reels[i].Axis.Origin, axisDirection);
            double radius = ReelRadialExtent(reels[i].Mesh, reels[i].Axis);
            double ratio = distance / radius;
            if (ratio < bestRatio)
            {
                secondRatio = bestRatio;
                secondIndex = bestIndex;
                secondDistance = bestDistance;
                secondRadius = bestRadius;
                bestRatio = ratio;
                bestIndex = i;
                bestDistance = distance;
                bestRadius = radius;
            }
            else if (ratio < secondRatio)
            {
                secondRatio = ratio;
                secondIndex = i;
                secondDistance = distance;
                secondRadius = radius;
            }
        }

        bool ownedByReel = bestRatio <= 1.0;
        string owner = ownedByReel ? RouteOwnerReel : RouteOwnerBody;
        int ownerReel = ownedByReel ? bestIndex : NoOwnerReel;

        bool nearBoundary = Math.Abs(bestRatio - 1.0) <= RouteOwnerAmbiguityMargin;
        bool nearTwoReels = secondIndex >= 0 && secondRatio <= 1.0 + RouteOwnerAmbiguityMargin;
        string? ambiguity = null;
        if (nearBoundary || nearTwoReels)
        {
            var pieces = new List<string>();
            if (nearBoundary)
            {
                pieces.Add(
                    $"reel {bestIndex} at distance " +
                    bestDistance.ToString("0.####", CultureInfo.InvariantCulture) +
                    " against its own radius " +
                    bestRadius.ToString("0.####", CultureInfo.InvariantCulture) +
                    " (ratio " + bestRatio.ToString("0.###", CultureInfo.InvariantCulture) +
                    ", within " + RouteOwnerAmbiguityMargin.ToString("0.##", CultureInfo.InvariantCulture) +
                    " of the 1.0 boundary)");
            }
            if (nearTwoReels)
            {
                pieces.Add(
                    $"also within reach of reel {secondIndex} at distance " +
                    secondDistance.ToString("0.####", CultureInfo.InvariantCulture) +
                    " against its own radius " +
                    secondRadius.ToString("0.####", CultureInfo.InvariantCulture) +
                    " (ratio " + secondRatio.ToString("0.###", CultureInfo.InvariantCulture) + ")");
            }
            ambiguity = string.Join("; ", pieces);
        }
        return (owner, ownerReel, ambiguity);
    }

    /// <summary>
    /// STILL READ BY EXPORT'S OWN SEAM (MechanismDocument.Json): the row's
    /// own typical anchor-to-anchor gap. Zero for a row of one (or none),
    /// which the caller floors rather than lets zero the whole tolerance.
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

    /// <summary>
    /// THE PLACEMENT MATHS: a 3x3 matrix with X, Y, Z as its COLUMNS,
    /// <c>m[row][col]</c>, so <see cref="MultiplyVector3"/> is a plain
    /// matrix-vector product. Used for both the authored mechanism's own
    /// wire-0 frame (Z derived, X cross Y -- routing frames are never
    /// mirrored, always right-handed) and a placement target plane (Z read
    /// TRUE off the plane, never re-derived, since a mirrored placement
    /// plane is genuinely LEFT-HANDED and that is exactly the signal a
    /// reflection must be built from).
    /// </summary>
    internal static double[][] BasisFromColumns(double[] x, double[] y, double[] z) => new[]
    {
        new[] { x[0], y[0], z[0] },
        new[] { x[1], y[1], z[1] },
        new[] { x[2], y[2], z[2] },
    };

    internal static double Determinant3(double[][] m) =>
        (m[0][0] * ((m[1][1] * m[2][2]) - (m[1][2] * m[2][1]))) -
        (m[0][1] * ((m[1][0] * m[2][2]) - (m[1][2] * m[2][0]))) +
        (m[0][2] * ((m[1][0] * m[2][1]) - (m[1][1] * m[2][0])));

    /// <summary>The inverse of a 3x3 matrix, or null when its determinant sits too close to zero to trust (a singular basis: coincident or collinear axes).</summary>
    internal static double[][]? Invert3(double[][] m)
    {
        double det = Determinant3(m);
        if (Math.Abs(det) < SingularBasisDeterminantEpsilon)
            return null;
        double inv = 1.0 / det;
        return new[]
        {
            new[]
            {
                ((m[1][1] * m[2][2]) - (m[1][2] * m[2][1])) * inv,
                ((m[0][2] * m[2][1]) - (m[0][1] * m[2][2])) * inv,
                ((m[0][1] * m[1][2]) - (m[0][2] * m[1][1])) * inv,
            },
            new[]
            {
                ((m[1][2] * m[2][0]) - (m[1][0] * m[2][2])) * inv,
                ((m[0][0] * m[2][2]) - (m[0][2] * m[2][0])) * inv,
                ((m[0][2] * m[1][0]) - (m[0][0] * m[1][2])) * inv,
            },
            new[]
            {
                ((m[1][0] * m[2][1]) - (m[1][1] * m[2][0])) * inv,
                ((m[0][1] * m[2][0]) - (m[0][0] * m[2][1])) * inv,
                ((m[0][0] * m[1][1]) - (m[0][1] * m[1][0])) * inv,
            },
        };
    }

    internal static double[][] Multiply3(double[][] a, double[][] b)
    {
        var result = new double[3][];
        for (int r = 0; r < 3; r++)
        {
            result[r] = new double[3];
            for (int c = 0; c < 3; c++)
            {
                double sum = 0.0;
                for (int k = 0; k < 3; k++)
                    sum += a[r][k] * b[k][c];
                result[r][c] = sum;
            }
        }
        return result;
    }

    internal static double[] MultiplyVector3(double[][] m, double[] v) => new[]
    {
        (m[0][0] * v[0]) + (m[0][1] * v[1]) + (m[0][2] * v[2]),
        (m[1][0] * v[0]) + (m[1][1] * v[1]) + (m[1][2] * v[2]),
        (m[2][0] * v[0]) + (m[2][1] * v[1]) + (m[2][2] * v[2]),
    };

    internal static double[] Column3(double[][] m, int col) => new[] { m[0][col], m[1][col], m[2][col] };
}

/// <summary>
/// The anchor-row geometry Export's own seam still reads off a solved
/// Result (MechanismDocument.Json's own <c>AnchorRowIndices</c> call, for
/// wire-to-net-vertex matching): the same grouping
/// <c>MouldGeometry.ConnectedGroups</c>/<c>GroupingAdjacency</c> already give
/// Diagnose's own "every anchor is in a strip of its own" check.
/// UNCHANGED by this rebuild; this collector no longer calls it itself
/// (there is no AN/TT door-guard left to run against it), but Export's seam
/// still does.
/// </summary>
internal static class MechanismGeometry
{
    /// <summary>
    /// Every anchor row's NODE INDICES, in <c>ConnectedGroups</c>' own
    /// order. Empty when the Result carries no equilibrium or no anchors.
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
}

/// <summary>
/// MECHANISM ("ME"): the collector for the fourth sibling document, feeding
/// Export beside RES and Cells. HIS MODEL, settled 2026-09-08, verbatim:
/// "take one mechanism, there is 3 per side at the moment linked via 7
/// wires each. I will [give] the component everything for one component
/// like this. Reel 1-10, reel 1-10 with axis, mechanism frame 1, mechanism
/// frame 2, motors, tension tie, wire routing frames, placement planes
/// (this will be for all wires, set into 7 and into side, so that you will
/// know 7 anchors = 1 mechanism, and its already branched that way, then
/// which side they are) ... we are using the first wire frame to dictate
/// how the mechanism attaches to the 7 placement planes."
///
/// ONE MECHANISM IS AUTHORED, ONCE (Frame 1, Frame 2, the Motors, the
/// fused Tension Tie, the ten Reels each with its own axis, and the seven
/// Routing wires), and PLACED at every branch of Placement -- one instance
/// per {side}{group} of seven planes, its transform DERIVED from the
/// mechanism's own Routing wire 0 against that branch's own first plane,
/// then validated against the other six (Placement's own maths, settled,
/// not redesigned here).
///
/// Every port is optional, so an author who wants only a mechanism, only a
/// tension tie, or nothing at all can wire exactly that. Nothing wired
/// produces an empty Payload and a quiet chin (spec section 8 item 6):
/// Export reads an empty Payload as "no mechanism document for this study"
/// exactly the way it reads no Cells as "no skin document".
/// </summary>
public sealed class MechanismCollectorComponent : NativeComponentBase
{
    public MechanismCollectorComponent()
        : base(
            "Mechanism",
            "ME",
            "Collect the ONE authored mechanism's parts -- Tension Tie, " +
            "Frame 1, Frame 2, Motors, Reel, Reel Axis, Routing -- and " +
            "place it at every Placement branch, deriving each instance's " +
            "transform from Routing wire 0 against that branch's own " +
            "first plane and validating it against the other six. " +
            "Nothing wired produces nothing: this is the fourth sibling " +
            "document, and it is optional per study.",
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
            "The solved Result. Kept for forward compatibility with his " +
            "existing wiring; the Anchor/Tension Tie door-guard that once " +
            "read it is gone now the tie arrives fused and travels with " +
            "the mechanism's own placement rather than being separately " +
            "authored in world space.",
            GH_ParamAccess.item);
        parameters[0].Optional = true;

        parameters.AddGenericParameter(
            "Tension Tie",
            "TT",
            "The foundation anchor and the tension tie / column slider " +
            "rail, arrived as ONE FUSED mesh (his settled ruling), in the " +
            "mechanism's own local space. Instanced exactly like Frame 1, " +
            "Frame 2, the Motors and the reels; permanence \"permanent\".",
            GH_ParamAccess.item);
        parameters[1].Optional = true;

        parameters.AddGenericParameter(
            "Frame 1",
            "F1",
            "The mechanism frame, one joined mesh, unit-local space.",
            GH_ParamAccess.item);
        parameters[2].Optional = true;

        parameters.AddGenericParameter(
            "Frame 2",
            "F2",
            "A second frame part in a DIFFERENT MATERIAL, unit-local " +
            "space, joined as far as he can join it -- so a list, not " +
            "necessarily one mesh.",
            GH_ParamAccess.list);
        parameters[3].Optional = true;

        parameters.AddGenericParameter(
            "Motors",
            "MO",
            "The motors, one joined mesh, unit-local space.",
            GH_ParamAccess.item);
        parameters[4].Optional = true;

        parameters.AddGenericParameter(
            "Reel",
            "RE",
            "The ten reels, SEPARATE meshes (never joined into Frame 1, " +
            "since a reel spins and a frame does not), unit-local space, " +
            "one list, position i pairs with Reel Axis (AX)[i].",
            GH_ParamAccess.list);
        parameters[5].Optional = true;

        parameters.AddPlaneParameter(
            "Reel Axis",
            "AX",
            "One plane per reel, matching Reel (RE) 1:1 by POSITION, " +
            "unit-local space: the plane's Z is the rotation axis. Its X " +
            "and Y are carried through into the document UNCHANGED -- " +
            "his ruling -- because he authors them deliberately to fix " +
            "the spin direction; never re-derived or normalised away. A " +
            "reel with no matching axis here refuses ONLY that reel: the " +
            "axis is authored, never inferred.",
            GH_ParamAccess.list);
        parameters[6].Optional = true;

        parameters.AddPlaneParameter(
            "Routing",
            "RT",
            "The ONE authored mechanism's wire frames, tree path " +
            "{wire}: an ordered list of planes per wire (seven wires), " +
            "unit-local space, in threading order, planes[0] the NET " +
            "END. Wire 0's first frame is also the FIRST CORRESPONDENCE " +
            "every Placement branch derives its instance transform from.",
            GH_ParamAccess.tree);
        parameters[7].Optional = true;

        parameters.AddPlaneParameter(
            "Placement",
            "PL",
            "Planes for ALL wires, world space, tree path {side}{group}: " +
            "seven planes per branch, one mechanism instance per branch, " +
            "plane i the world target for Routing wire i. The instance " +
            "transform is DERIVED from plane 0 against Routing wire 0's " +
            "own first frame and validated against the other six -- he " +
            "no longer authors a placement frame directly.",
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
            "What was received, then any named warning the door-guards " +
            "raised (a bad branch count, a singular basis, an over-" +
            "tolerance residual, a reel with no axis), then every " +
            "instance's own derived-transform report (its max residual " +
            "against the other six wires, and whether it came out a " +
            "reflection), then any note the chin owes about a default or " +
            "a Brep meshed in passing.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        try
        {
            var warnings = new List<string>();
            var notes = new List<string>();

            bool hasResult = TryReadResult(data, out _);

            MechanismAssetInput asset = ReadAsset(data, warnings);
            List<MechanismRoutingWire> routing = ReadRouting(data, warnings);
            List<MechanismPlacementBranch> placements = ReadPlacements(data, warnings);

            string? payload = MechanismCollector.Build(asset, routing, placements, warnings, notes);

            int routedWireCount = routing.Count(w => w.Route.Count > 0);
            var status = new List<string>
            {
                payload is null
                    ? "received: nothing wired; no mechanism document."
                    : "received: frame1 " +
                      (asset.Frame1 is null ? "not authored" : "authored") +
                      $", frame2 {asset.Frame2.Count} part(s), motors " +
                      (asset.Motors is null ? "not authored" : "authored") +
                      ", tension tie " +
                      (asset.TensionTie is null ? "not authored" : "authored (fused anchor+tie)") +
                      $", {asset.ReelMeshes.Count} reel(s) offered, " +
                      $"{routedWireCount} of {MechanismCollector.PlacementGroupSize} " +
                      $"routing wire(s) authored, {placements.Count} " +
                      "placement branch(es), Result " +
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
                : $"{placements.Count} placement branch(es), {routedWireCount} routed wire(s)";
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

    private MechanismAssetInput ReadAsset(IGH_DataAccess data, List<string> warnings)
    {
        object? ttItem = null;
        data.GetData(1, ref ttItem);
        MechanismMesh? tt = null;
        bool ttBrep = false;
        if (ttItem is not null)
        {
            if (!TryMeshOrBrep(ttItem, out tt, out ttBrep) || tt is null)
            {
                warnings.Add("Tension Tie (TT) did not resolve to a mesh or a closed Brep; refused.");
                tt = null;
            }
        }

        object? f1Item = null;
        data.GetData(2, ref f1Item);
        MechanismMesh? f1 = null;
        bool f1Brep = false;
        if (f1Item is not null)
        {
            if (!TryMeshOrBrep(f1Item, out f1, out f1Brep) || f1 is null)
            {
                warnings.Add("Frame 1 (F1) did not resolve to a mesh or a closed Brep; refused.");
                f1 = null;
            }
        }

        var f2Items = new List<object>();
        data.GetDataList(3, f2Items);
        var f2 = new List<MechanismMesh>(f2Items.Count);
        var f2Brep = new List<bool>(f2Items.Count);
        for (int i = 0; i < f2Items.Count; i++)
        {
            if (!TryMeshOrBrep(f2Items[i], out MechanismMesh? m, out bool b) || m is null)
            {
                warnings.Add($"Frame 2 (F2)[{i}] did not resolve to a mesh or a closed Brep; skipped.");
                continue;
            }
            f2.Add(m);
            f2Brep.Add(b);
        }

        object? moItem = null;
        data.GetData(4, ref moItem);
        MechanismMesh? mo = null;
        bool moBrep = false;
        if (moItem is not null)
        {
            if (!TryMeshOrBrep(moItem, out mo, out moBrep) || mo is null)
            {
                warnings.Add("Motors (MO) did not resolve to a mesh or a closed Brep; refused.");
                mo = null;
            }
        }

        var reItems = new List<object>();
        data.GetDataList(5, reItems);
        var reMeshes = new List<MechanismMesh?>(reItems.Count);
        var reBrep = new List<bool>(reItems.Count);
        for (int i = 0; i < reItems.Count; i++)
        {
            if (!TryMeshOrBrep(reItems[i], out MechanismMesh? m, out bool b))
            {
                warnings.Add($"Reel (RE)[{i}] did not resolve to a mesh or a closed Brep; treated as missing.");
                reMeshes.Add(null);
                reBrep.Add(false);
                continue;
            }
            reMeshes.Add(m);
            reBrep.Add(b);
        }

        var axItems = new List<Plane>();
        data.GetDataList(6, axItems);
        var axes = new List<MechanismFrame?>(axItems.Count);
        foreach (Plane plane in axItems)
        {
            axes.Add(new MechanismFrame(
                new[] { plane.Origin.X, plane.Origin.Y, plane.Origin.Z },
                new[] { plane.XAxis.X, plane.XAxis.Y, plane.XAxis.Z },
                new[] { plane.YAxis.X, plane.YAxis.Y, plane.YAxis.Z },
                new[] { plane.ZAxis.X, plane.ZAxis.Y, plane.ZAxis.Z }));
        }

        return new MechanismAssetInput(
            f1, f1Brep, f2, f2Brep, mo, moBrep, tt, ttBrep, reMeshes, reBrep, axes);
    }

    /// <summary>
    /// Reads Routing (RT) as a tree, path {wire}: the ONE authored
    /// mechanism's own routing, never per instance now.
    /// </summary>
    private List<MechanismRoutingWire> ReadRouting(IGH_DataAccess data, List<string> warnings)
    {
        data.GetDataTree(7, out GH_Structure<GH_Plane> rtTree);
        var wires = new List<MechanismRoutingWire>();
        foreach (GH_Path path in rtTree.Paths)
        {
            if (path.Indices.Length != 1)
            {
                warnings.Add(
                    $"RT path {{{string.Join(",", path.Indices)}}} is not " +
                    "a {wire} single-level path (Routing now belongs to " +
                    "the ONE authored mechanism, indexed by wire alone); ignored.");
                continue;
            }
            int wire = path.Indices[0];
            var frames = new List<MechanismFrame>();
            foreach (GH_Plane planeGoo in rtTree.get_Branch(path))
            {
                if (planeGoo is null)
                    continue;
                Plane plane = planeGoo.Value;
                frames.Add(new MechanismFrame(
                    new[] { plane.Origin.X, plane.Origin.Y, plane.Origin.Z },
                    new[] { plane.XAxis.X, plane.XAxis.Y, plane.XAxis.Z },
                    new[] { plane.YAxis.X, plane.YAxis.Y, plane.YAxis.Z },
                    new[] { plane.ZAxis.X, plane.ZAxis.Y, plane.ZAxis.Z }));
            }
            wires.Add(new MechanismRoutingWire(wire, frames));
        }
        return wires;
    }

    /// <summary>
    /// Reads Placement (PL) as a tree, path {side}{group}: the world
    /// TARGET planes the placement maths derives every instance transform
    /// from. Z is read TRUE off the Rhino plane, never re-derived --
    /// see <see cref="MechanismPlacementPlane"/> for why.
    /// </summary>
    private List<MechanismPlacementBranch> ReadPlacements(IGH_DataAccess data, List<string> warnings)
    {
        data.GetDataTree(8, out GH_Structure<GH_Plane> plTree);
        var branches = new List<MechanismPlacementBranch>();
        foreach (GH_Path path in plTree.Paths)
        {
            if (path.Indices.Length != 2)
            {
                warnings.Add(
                    $"PL path {{{string.Join(",", path.Indices)}}} is not " +
                    "a {side}{group} two-level path; ignored.");
                continue;
            }
            int side = path.Indices[0];
            int group = path.Indices[1];
            var planes = new List<MechanismPlacementPlane>();
            IList branch = plTree.get_Branch(path);
            for (int i = 0; i < branch.Count; i++)
            {
                GH_Plane? planeGoo = branch[i] as GH_Plane;
                if (planeGoo is null)
                {
                    warnings.Add($"PL[{side}][{group}][{i}] is null; dropped from its branch.");
                    continue;
                }
                Plane plane = planeGoo.Value;
                planes.Add(new MechanismPlacementPlane(
                    new[] { plane.Origin.X, plane.Origin.Y, plane.Origin.Z },
                    new[] { plane.XAxis.X, plane.XAxis.Y, plane.XAxis.Z },
                    new[] { plane.YAxis.X, plane.YAxis.Y, plane.YAxis.Z },
                    new[] { plane.ZAxis.X, plane.ZAxis.Y, plane.ZAxis.Z }));
            }
            branches.Add(new MechanismPlacementBranch(new MechanismInstanceId(side, group), planes));
        }
        return branches;
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
