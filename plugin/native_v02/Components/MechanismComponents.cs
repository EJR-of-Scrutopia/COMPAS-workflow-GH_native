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
    /// THE CABLE'S OWN THICKNESS, his ruling 2026-09-09, verbatim: "the
    /// routing for the spool via framing is its center line. the defualt
    /// cable thickness is 0.01".
    ///
    /// Read as a DIAMETER, so the drawn wire's radius is half of it. It is
    /// carried in the document because a consumer that has to guess will
    /// guess wrongly and cannot know it has: the studio drew this wire at a
    /// 0.02 m RADIUS, four times over, and the drum's own 0.0267 m helix
    /// pitch then read as adjacent turns overlapping by 12 mm -- a modelling
    /// fault that did not exist. At 0.01 m thick the same pitch clears
    /// comfortably.
    ///
    /// A DEFAULT, not authored per study: there is no port for it yet, and
    /// the chin says so every time rather than letting it pass as measured.
    /// </summary>
    public const double DefaultCableThicknessMetres = 0.01;

    /// <summary>
    /// How close a frame's own distance-to-axis, relative to that reel's
    /// own radius, may sit to the 1.0 ownership boundary -- or how close a
    /// SECOND reel's own ratio may also sit at or under it -- before the
    /// classification is NAMED rather than trusted silently.
    /// </summary>
    public const double RouteOwnerAmbiguityMargin = 0.15;

    /// <summary>
    /// How far past a reel's OWN END FACES, as a fraction of that reel's
    /// own radius, a routing frame may still sit and be counted as riding
    /// on it. A wire leaving a drum crosses the end face within about a
    /// wire's thickness, so this is deliberately small.
    ///
    /// WHY AN AXIAL TEST EXISTS AT ALL (2026-09-08, found on his own ten-reel
    /// mechanism): the radial test measures distance to an INFINITE axis
    /// line. Without a bound along that line, a reel claims every frame
    /// within its radius however far past its own faces the frame sits --
    /// so a wire running parallel to a drum, a metre away along the axis,
    /// read as riding on it and would have been spun by it in the studio's
    /// animation. A reel owns only what lies between its own faces.
    /// </summary>
    public const double RouteOwnerAxialMarginFraction = 0.25;

    /// <summary>
    /// How far, in metres, two seven-point sets' own matching edge lengths
    /// may disagree before they are called DIFFERENT SHAPES rather than the
    /// same shape differently placed. Shared with
    /// <see cref="MaxResidualWarnMetres"/>'s own scale on purpose: a set
    /// congruent to within the placement guard is congruent for placement.
    /// </summary>
    public const double ShapeCongruenceToleranceMetres = MaxResidualWarnMetres;

    /// <summary>
    /// The smallest off-axis reach, as a fraction of a point set's own
    /// spread, that still founds a third basis direction. Below it the
    /// seven origins are effectively collinear and no orientation can be
    /// fitted from them at all.
    /// </summary>
    public const double CollinearFitFraction = 1.0e-3;

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
        List<string> notes) =>
        BuildWithResult(asset, routing, placements, warnings, notes, null);

    /// <summary>
    /// The same build, with the solved Result available so that placement
    /// can be DERIVED from the net's own anchor rows when none is authored
    /// (his ruling, 2026-09-09: "the placement point will be figured out as
    /// part of the export"). A five-argument call is the same thing with
    /// nothing to derive from, kept so every existing caller stands.
    /// </summary>
    public static string? BuildWithResult(
        MechanismAssetInput asset,
        IReadOnlyList<MechanismRoutingWire> routing,
        IReadOnlyList<MechanismPlacementBranch> placements,
        List<string> warnings,
        List<string> notes,
        ResultDto? result)
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

        string? spoolRadiusFallbackNote = null;
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
            // HELD, NOT SAID YET: the routing frames below can MEASURE a
            // real winding radius, and a measurement supersedes this guess
            // rather than arguing with it in the chin.
            spoolRadiusFallbackNote =
                "mechanism: spoolRadius defaulted to " +
                spoolRadius.ToString("0.####", CultureInfo.InvariantCulture) +
                (reels.Count > 0
                    ? " from reel[0]'s own bounding box (smallest " +
                      "dimension over 4), since no routing frame rides a " +
                      "reel to measure a real winding radius from."
                    : spoolSource is not null
                        ? " from the frame/motors/tie's own bounding box " +
                          "(smallest dimension over 4), since no reel " +
                          "resolved."
                        : " from the floor value, since no geometry was " +
                          "wired to derive it from.");

            // THE REEVE FACTOR IS PROVISIONAL (his ruling, verbatim: "i
            // dont [want] it to be accurate righ tnow"). Fixed at 1.0, no
            // authored port, said here every time a mechanism is built.
            notes.Add(
                "mechanism: reeveFactor is fixed at 1.0 -- PROVISIONAL, " +
                "not accurate, per his own ruling that accuracy is not " +
                "wanted right now; every reel's spin RATE is likely wrong " +
                "until a real reeve factor is authored.");

            // THE ROUTING FRAMES ARE THE CABLE'S CENTRELINE, his ruling,
            // said in the document so no consumer has to infer it from
            // where the frames happen to sit against a drum mesh.
            notes.Add(
                "mechanism: the routing frames are the cable's CENTRELINE " +
                "(his ruling), and cableThickness is his stated default " +
                DefaultCableThicknessMetres.ToString("0.####", CultureInfo.InvariantCulture) +
                " m read as a DIAMETER -- a default, not authored per " +
                "study, and not measured from anything. Draw the wire on " +
                "the frames as they are: do NOT offset them by a wire " +
                "radius.");

            mechanismOut["cableThickness"] = DefaultCableThicknessMetres;
            mechanismOut["routingFrameMeaning"] = "centreline";
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

        // PLACEMENT, DERIVED FROM THE NET when he authored none. His own
        // words, 2026-09-09: the planes "just flip randomly, and its so
        // hard to create rules so they each follow them". Nothing that is
        // authored can be stopped from flipping; a rule derived from the
        // solved net has nothing to flip.
        if (placements.Count == 0 && result is not null)
        {
            placements = DerivePlacements(result, routingByIndex, warnings, notes);
        }

        // ROUTING FRAME OWNERSHIP (7c8db59, unchanged): classified ONCE
        // against the mechanism's own reels, since both are authored once
        // now -- never per instance.
        var ownerCounts = new Dictionary<string, int>(StringComparer.Ordinal) { [RouteOwnerBody] = 0 };
        for (int r = 0; r < reels.Count; r++)
            ownerCounts[$"reel {r}"] = 0;
        ReelNeighbourhood[] neighbourhoods = BuildReelNeighbourhoods(reels);
        var classifiedRoutes = new Dictionary<int, List<(MechanismFrame Frame, string Owner, int OwnerReel)>>();

        // THE BORDERLINE CASES ARE GATHERED ACROSS EVERY WIRE AND SAID ONCE
        // (2026-09-08, second pass on his real machine).
        //
        // A wire WRAPPED on a drum sits at that drum's own surface on every
        // frame of the wrap, and the radius it is measured against is the
        // mesh's own outermost extent -- the flanges -- so a CORRECT wrap
        // lands a little inside 1.0 on every frame and the tangent frames
        // where it lifts off land a little outside. Both are the normal
        // shape of wrapped wire, not a fault, and both fire on every wire
        // over every drum: his second solve produced twenty-eight such
        // lines and pushed the PLACEMENT report -- the only part of this
        // chin he can act on -- past Grasshopper's own "further remarks not
        // shown" cut.
        //
        // A frame just outside is left with the BODY deliberately, not
        // merely by the arithmetic: the point where a wire leaves a drum
        // stands still in space however fast that drum turns, so holding it
        // is what the machine actually does. What survives as a WARNING is
        // only the case where the answer is genuinely undecided and would
        // move different geometry: two reels reaching the same frame.
        var contested = new Dictionary<(int First, int Second), (int Count, int Wire, int Frame, double FirstRatio, double SecondRatio)>();
        var ownedRadii = new Dictionary<int, List<double>>();
        int rideCount = 0;
        int justOutsideCount = 0;
        int beyondTheFacesCount = 0;
        double closestJustOutsideRatio = double.PositiveInfinity;
        int closestJustOutsideReel = NoOwnerReel;
        int closestJustOutsideWire = -1;
        int closestJustOutsideFrame = -1;
        for (int w = 0; w < PlacementGroupSize; w++)
        {
            if (!routingByIndex.TryGetValue(w, out MechanismRoutingWire? wire) || wire.Route.Count == 0)
                continue;
            var classified = new List<(MechanismFrame, string, int)>(wire.Route.Count);

            for (int frameIndex = 0; frameIndex < wire.Route.Count; frameIndex++)
            {
                MechanismFrame frame = wire.Route[frameIndex];
                RouteOwnerVerdict verdict = ClassifyRouteFrameOwner(frame, neighbourhoods);
                bool ownedByReel = verdict.Owner == RouteOwnerReel;
                string countKey = ownedByReel ? $"reel {verdict.OwnerReel}" : RouteOwnerBody;
                ownerCounts[countKey] = ownerCounts.GetValueOrDefault(countKey) + 1;

                if (verdict.AxiallyExcluded)
                    beyondTheFacesCount++;

                if (!ownedByReel &&
                    verdict.NearestReel >= 0 &&
                    verdict.NearestRatio <= 1.0 + RouteOwnerAmbiguityMargin)
                {
                    justOutsideCount++;
                    if (verdict.NearestRatio < closestJustOutsideRatio)
                    {
                        closestJustOutsideRatio = verdict.NearestRatio;
                        closestJustOutsideReel = verdict.NearestReel;
                        closestJustOutsideWire = w;
                        closestJustOutsideFrame = frameIndex;
                    }
                }

                if (ownedByReel &&
                    verdict.SecondReel >= 0 &&
                    verdict.SecondRatio <= 1.0 + RouteOwnerAmbiguityMargin)
                {
                    (int First, int Second) key = (verdict.OwnerReel, verdict.SecondReel);
                    (int count, int atWire, int atFrame, double firstRatio, double secondRatio) =
                        contested.GetValueOrDefault(key, (0, w, frameIndex, 0.0, double.PositiveInfinity));
                    contested[key] = verdict.SecondRatio < secondRatio
                        ? (count + 1, w, frameIndex, verdict.NearestRatio, verdict.SecondRatio)
                        : (count + 1, atWire, atFrame, firstRatio, secondRatio);
                }

                if (ownedByReel && verdict.NearestRatio >= 1.0 - RouteOwnerAmbiguityMargin)
                    rideCount++;

                // THE WINDING RADIUS, MEASURED. Every frame a reel owns
                // sits at the radius the wire actually runs at on that
                // reel, so the reel's own frames say what a bounding box
                // can only guess at.
                if (ownedByReel)
                {
                    if (!ownedRadii.TryGetValue(verdict.OwnerReel, out List<double>? radii))
                    {
                        radii = new List<double>();
                        ownedRadii[verdict.OwnerReel] = radii;
                    }
                    radii.Add(verdict.NearestDistance);
                }

                classified.Add((frame, verdict.Owner, verdict.OwnerReel));
            }
            classifiedRoutes[w] = classified;
        }

        foreach (KeyValuePair<(int First, int Second), (int Count, int Wire, int Frame, double FirstRatio, double SecondRatio)> entry
            in contested.OrderBy(p => p.Key.First).ThenBy(p => p.Key.Second))
        {
            warnings.Add(
                $"mechanism: {entry.Value.Count} routing frame(s) sit within " +
                $"reach of BOTH reel {entry.Key.First} and reel " +
                $"{entry.Key.Second} -- ownership AMBIGUOUS, closest at " +
                $"Routing (RT)[{entry.Value.Wire}] frame [{entry.Value.Frame}] " +
                $"(reel {entry.Key.First} ratio " +
                entry.Value.FirstRatio.ToString("0.###", CultureInfo.InvariantCulture) +
                $", reel {entry.Key.Second} ratio " +
                entry.Value.SecondRatio.ToString("0.###", CultureInfo.InvariantCulture) +
                $"); assigned reel {entry.Key.First} as the nearer, never " +
                "picked silently.");
        }

        // EACH REEL'S OWN WINDING RADIUS, and the mechanism's own spool
        // radius with it (2026-09-09, measured on his real file by the
        // studio session and true: the defaulted 0.03 matched nothing in
        // the document -- his spool barrels read 0.05 and his pulleys
        // 0.17, 0.20 and 0.30, so a bounding box over four was a guess
        // that happened to be wrong). A reel's own routing frames sit at
        // the radius the wire actually runs at on it, so they are the
        // measurement, and the guess is only kept where there is nothing
        // to measure.
        var measuredRadii = new List<double>();
        if (mechanismOut is not null &&
            mechanismOut.TryGetValue("reels", out object? reelsObject) &&
            reelsObject is List<Dictionary<string, object?>> reelsPayload)
        {
            for (int r = 0; r < reelsPayload.Count; r++)
            {
                double? measured =
                    ownedRadii.TryGetValue(r, out List<double>? radii) && radii.Count > 0
                        ? MedianOf(radii)
                        : null;
                reelsPayload[r]["windingRadius"] = measured;
                if (measured is not null)
                    measuredRadii.Add(measured.Value);
            }
        }
        if (measuredRadii.Count > 0 && mechanismOut is not null)
        {
            double measuredSpool = MedianOf(measuredRadii);
            mechanismOut["spoolRadius"] = measuredSpool;
            notes.Add(
                "mechanism: spoolRadius MEASURED at " +
                measuredSpool.ToString("0.####", CultureInfo.InvariantCulture) +
                $" m from the routing frames themselves, across " +
                $"{measuredRadii.Count} reel(s) that carry wire, not " +
                "guessed from a bounding box; each reel also carries its " +
                "own windingRadius, which is the one to prefer per reel " +
                "since a pulley and a spool do not share a radius.");
        }
        else if (spoolRadiusFallbackNote is not null)
        {
            notes.Add(spoolRadiusFallbackNote);
        }

        if (classifiedRoutes.Count > 0)
        {
            var borderline = new List<string>();
            if (rideCount > 0)
            {
                borderline.Add(
                    $"{rideCount} ride the reel that owns them, within " +
                    RouteOwnerAmbiguityMargin.ToString("0.##", CultureInfo.InvariantCulture) +
                    " of its own outer radius (expected of a wire wrapped on " +
                    "a drum, whose wrap sits at that drum's own surface by " +
                    "construction)");
            }
            if (justOutsideCount > 0)
            {
                borderline.Add(
                    $"{justOutsideCount} sit JUST outside a reel and are held " +
                    "by the body, which is what a wire's lift-off point does " +
                    "in life (it stands still however fast the drum turns), " +
                    $"closest reel {closestJustOutsideReel} at ratio " +
                    closestJustOutsideRatio.ToString("0.###", CultureInfo.InvariantCulture) +
                    $", Routing (RT)[{closestJustOutsideWire}] frame " +
                    $"[{closestJustOutsideFrame}]");
            }
            if (beyondTheFacesCount > 0)
            {
                borderline.Add(
                    $"{beyondTheFacesCount} sat inside a reel's own radius but " +
                    "BEYOND its own end faces, so the body keeps them (a reel " +
                    "owns only what lies between its own faces)");
            }
            if (borderline.Count > 0)
            {
                notes.Add(
                    "mechanism: the borderline routing frames, every wire " +
                    "together -- " + string.Join("; ", borderline) + ".");
            }

            string tally = string.Join(
                ", ",
                ownerCounts.OrderBy(p => p.Key, StringComparer.Ordinal)
                    .Select(p => $"{p.Key} {p.Value}"));
            notes.Add($"mechanism: routing frame ownership, the ONE authored mechanism -- {tally}.");
        }

        // WHERE THE PLACEMENT REPORT STARTS. Everything it adds is moved to
        // the FRONT of the chin below: Grasshopper's own balloon shows
        // fifteen lines and then "further remarks not shown", and the
        // placement report is the only part of this chin that can be acted
        // on -- it must never be the part that falls off the bottom.
        int notesBeforePlacement = notes.Count;
        int warningsBeforePlacement = warnings.Count;

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

            // THE SEVEN AUTHORED CORRESPONDENCES, BOTH ENDS OF EACH WIRE.
            // Route[0] is the NET END by his own ruling (R2), so the first
            // frames are the set a placement branch's own planes should
            // match; the last frames are carried only so that a route
            // threaded the other way round can be RECOGNISED and named
            // rather than left looking like broken geometry.
            var sourceFirstOrigins = new List<double[]?>(PlacementGroupSize);
            var sourceLastOrigins = new List<double[]?>(PlacementGroupSize);

            // Their AXES travel with them, for the one degree of freedom
            // collinear anchors cannot supply (see
            // FitTransformAboutAnchorLine): the spin about the anchor line.
            var sourceFirstAxes = new List<double[][]?>(PlacementGroupSize);
            for (int i = 0; i < PlacementGroupSize; i++)
            {
                bool present =
                    routingByIndex.TryGetValue(i, out MechanismRoutingWire? wireI) &&
                    wireI.Route.Count > 0;
                sourceFirstOrigins.Add(present ? wireI!.Route[0].Origin : null);
                sourceLastOrigins.Add(present ? wireI!.Route[wireI.Route.Count - 1].Origin : null);
                sourceFirstAxes.Add(present
                    ? new[] { wireI!.Route[0].XAxis, wireI.Route[0].YAxis }
                    : null);
            }

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
                // The reflection is NAMED once the transform is settled, not
                // here: a placement that falls back to the origin fit below
                // can legitimately change handedness, and a note written
                // before that would be stale.
                double det = Determinant3(linear);
                bool reflected = det < 0.0;

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
                // ONE LINE PER BRANCH, AND ITS FIRST LINE IS THE WHOLE
                // MESSAGE (2026-09-08, his own words on seeing this chin:
                // "if it worked why is it orange ... make the bubble
                // message only the fix and make that small. the ST can
                // have more detail"). A chin line may carry further lines
                // after the first; the component shows only the FIRST in
                // Grasshopper's balloon and puts all of them in Status. So
                // a placement that worked reads as one short line, the
                // reasoning stays one port away, and a refit that SUCCEEDED
                // is a remark rather than a warning -- work that came out
                // right must not paint the component orange.
                string Metres(double value) =>
                    value.ToString("0.######", CultureInfo.InvariantCulture);
                string headline;
                string? detail = null;
                bool placementFailed = false;

                if (validated == 0)
                {
                    headline =
                        $"Placement (PL) {label}: placed; residual not " +
                        "checked, only Routing (RT)[0] carries frames.";
                }
                else if (maxResidual <= MaxResidualWarnMetres)
                {
                    headline =
                        $"Placement (PL) {label}: placed, residual " +
                        Metres(maxResidual) +
                        $" m across {validated} of 6 other wire(s).";
                }
                else
                {
                    // WHY THE SETS DISAGREE, NOT JUST THAT THEY DO.
                    // A residual alone cannot tell a wrongly oriented
                    // placement from a wrongly ordered one or from planes
                    // authored against different features: all three read
                    // as "about a metre out". Edge lengths can, because
                    // they survive any placement -- matched pairwise they
                    // separate orientation from the rest, and sorted they
                    // separate a reordering from a genuine shape
                    // difference.
                    var targetOrigins = new List<double[]?>(PlacementGroupSize);
                    var targetAxes = new List<double[][]?>(PlacementGroupSize);
                    foreach (MechanismPlacementPlane plane in branch.Planes)
                    {
                        targetOrigins.Add(plane.Origin);
                        targetAxes.Add(new[] { plane.XAxis, plane.YAxis });
                    }

                    double ordered = OrderedShapeMismatch(sourceFirstOrigins, targetOrigins);
                    double unordered = UnorderedShapeMismatch(sourceFirstOrigins, targetOrigins);
                    double orderedFromLast = OrderedShapeMismatch(sourceLastOrigins, targetOrigins);
                    double authoredResidual = maxResidual;

                    if (ordered <= ShapeCongruenceToleranceMetres)
                    {
                        (double[][] Linear, double[] Translation, double Residual)? fitted =
                            FitTransformFromOrigins(sourceFirstOrigins, targetOrigins);

                        // COLLINEAR ANCHORS ARE NOT A DEAD END, they are
                        // two thirds of an answer: the line is exact and
                        // only the spin about it wants another source.
                        (double[][] Linear, double[] Translation, double Residual, double AxisDisagreementDegrees)? alongLine =
                            fitted is null
                                ? FitTransformAboutAnchorLine(
                                    sourceFirstOrigins, targetOrigins, sourceFirstAxes, targetAxes)
                                : null;

                        if (fitted is not null && fitted.Value.Residual < authoredResidual)
                        {
                            linear = fitted.Value.Linear;
                            translation = fitted.Value.Translation;
                            maxResidual = fitted.Value.Residual;
                            det = Determinant3(linear);
                            reflected = det < 0.0;
                            headline =
                                $"Placement (PL) {label}: placed from all " +
                                "seven anchors, residual " +
                                Metres(maxResidual) + " m (was " +
                                Metres(authoredResidual) + " m).";
                            detail =
                                "The seven wire first-frames and the seven " +
                                "placement planes ARE THE SAME SHAPE (worst " +
                                "edge disagreement " + Metres(ordered) + " m), " +
                                "so nothing is mis-ordered or mis-picked and " +
                                "the whole residual was ORIENTATION: " +
                                "placement plane [0]'s own X/Y do not " +
                                "correspond to Routing (RT)[0] frame [0]'s " +
                                "own X/Y, and the settled maths derive the " +
                                "instance from that one pair alone. THE " +
                                "TRANSFORM WAS REFITTED from all seven " +
                                "origins instead, so the instance is placed " +
                                "by the refit, not by plane [0]'s axes.";
                        }
                        else if (alongLine is not null && alongLine.Value.Residual < authoredResidual)
                        {
                            linear = alongLine.Value.Linear;
                            translation = alongLine.Value.Translation;
                            maxResidual = alongLine.Value.Residual;
                            det = Determinant3(linear);
                            reflected = det < 0.0;
                            string degrees = alongLine.Value.AxisDisagreementDegrees
                                .ToString("0.##", CultureInfo.InvariantCulture);
                            headline =
                                $"Placement (PL) {label}: placed from all " +
                                "seven anchors, residual " +
                                Metres(maxResidual) + " m (was " +
                                Metres(authoredResidual) + " m); anchors in a " +
                                "line, so the roll about it comes from the " +
                                $"authored axes and those are {degrees} " +
                                "degrees out.";
                            detail =
                                "The seven wire first-frames and the seven " +
                                "placement planes ARE THE SAME SHAPE (worst " +
                                "edge disagreement " + Metres(ordered) + " m), " +
                                "and the seven anchors sit IN A LINE. A line " +
                                "pins which way it points but not the SPIN " +
                                "about it, so the job splits. THE TRANSFORM " +
                                "WAS REFITTED: the origins carry the line, so " +
                                "every anchor now lands on its own plane, and " +
                                "the spin about that line is taken from ALL " +
                                "SEVEN planes' own axes against all seven " +
                                "routing frames' own axes rather than from " +
                                "plane [0] alone. After the best spin those " +
                                $"axes still disagree by {degrees} degrees on " +
                                "average. Near zero means the spin is as well " +
                                "founded as the rest. A large figure means " +
                                "your plane axes do not agree with your " +
                                "routing frames, so the mechanism may be " +
                                "ROLLED about the anchor line even though " +
                                "every anchor is exactly placed -- the " +
                                "placement is right and the machine may be " +
                                "turned on its side. Give your placement " +
                                "planes the same X/Y convention as your " +
                                "routing frames to settle that last degree " +
                                "of freedom.";
                        }
                        else
                        {
                            placementFailed = true;
                            headline =
                                $"Placement (PL) {label}: NOT placed well -- " +
                                "residual " + Metres(authoredResidual) +
                                " m, orientation alone, and no better fit is " +
                                "possible from these origins. See ST.";
                            detail =
                                "The seven wire first-frames and the seven " +
                                "placement planes are the same shape (worst " +
                                "edge disagreement " + Metres(ordered) + " m), " +
                                "so the residual is orientation alone -- but " +
                                "no better transform could be fitted from the " +
                                "origins at all (fewer than two wires carry " +
                                "frames, or every anchor sits on the same " +
                                "point). Plane [0]'s own axes still place this " +
                                "instance; give plane [0] the same X/Y as " +
                                "Routing (RT)[0] frame [0].";
                        }
                    }
                    else if (unordered <= ShapeCongruenceToleranceMetres)
                    {
                        placementFailed = true;
                        headline =
                            $"Placement (PL) {label}: your placement planes " +
                            "and your routing wires are in DIFFERENT ORDERS; " +
                            "residual " + Metres(authoredResidual) +
                            " m. Reorder one to match the other. See ST.";
                        detail =
                            "The seven placement planes carry THE SAME EDGE " +
                            "LENGTHS as the seven wire first-frames (worst " +
                            "disagreement " + Metres(unordered) + " m) but NOT " +
                            "PAIRED THE SAME WAY (worst matched-pair " +
                            "disagreement " + Metres(ordered) + " m). " +
                            "Placement plane [i] must correspond to Routing " +
                            "(RT)[i]. Nothing is refitted here, because a fit " +
                            "onto the wrong pairing would place a plausible, " +
                            "wrong machine.";
                    }
                    else if (orderedFromLast <= ShapeCongruenceToleranceMetres)
                    {
                        placementFailed = true;
                        headline =
                            $"Placement (PL) {label}: your routing lists are " +
                            "threaded THE OTHER WAY ROUND; residual " +
                            Metres(authoredResidual) +
                            " m. Reverse them. See ST.";
                        detail =
                            "The placement planes match each wire's LAST " +
                            "routing frame, not its first (worst edge " +
                            "disagreement " + Metres(orderedFromLast) +
                            " m against " + Metres(ordered) + " m for the " +
                            "first frames). Route[0] is the NET END by your " +
                            "own ruling, so reverse the routing lists. " +
                            "Nothing is refitted here.";
                    }
                    else
                    {
                        placementFailed = true;
                        headline =
                            $"Placement (PL) {label}: your placement planes " +
                            "and your wire ends are DIFFERENT GEOMETRY; " +
                            "residual " + Metres(authoredResidual) +
                            " m. See ST.";
                        detail =
                            "The two seven-point sets are NOT THE SAME SHAPE " +
                            "by any pairing (worst matched-pair disagreement " +
                            Metres(ordered) + " m, worst sorted-edge " +
                            "disagreement " + Metres(unordered) + " m, and " +
                            Metres(orderedFromLast) + " m against the wires' " +
                            "last frames). They are authored against " +
                            "different features, or on a different mechanism " +
                            "than the one wired here. No transform can " +
                            "satisfy all seven; this placement is not " +
                            "well-founded.";
                    }
                }

                if (reflected)
                {
                    headline += " Mirrored side (reflection, determinant " +
                        det.ToString("0.###", CultureInfo.InvariantCulture) +
                        "), expected, not an error.";
                }

                string placementLine = detail is null
                    ? headline
                    : headline + Environment.NewLine + detail;
                if (placementFailed)
                    warnings.Add(placementLine);
                else
                    notes.Add(placementLine);

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

        MoveTailToFront(notes, notesBeforePlacement);
        MoveTailToFront(warnings, warningsBeforePlacement);

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
    /// A REEL'S OWN NEIGHBOURHOOD, MEASURED ONCE: its axis direction, the
    /// furthest any of its OWN mesh vertices sits from its OWN axis line
    /// (the radius), and how far those vertices reach ALONG that line from
    /// the axis frame's own origin (the two end faces).
    ///
    /// Measured once per reel rather than once per reel PER FRAME, which is
    /// what the first cut did: his own mechanism walks 1,400 routing frames
    /// against ten reels, so re-walking every reel mesh inside that loop
    /// cost several thousand mesh traversals for an answer that never
    /// changes.
    /// </summary>
    internal readonly record struct ReelNeighbourhood(
        double[] AxisOrigin, double[] AxisDirection, double Radius, double AxialMin, double AxialMax);

    /// <summary>
    /// One routing frame's ownership, decided: who owns it, who was nearest
    /// whether they own it or not, and the runners-up the caller needs to
    /// report an ambiguity honestly without re-deriving any of it.
    /// </summary>
    internal readonly record struct RouteOwnerVerdict(
        string Owner,
        int OwnerReel,
        int NearestReel,
        double NearestRatio,
        double NearestDistance,
        double NearestRadius,
        int SecondReel,
        double SecondRatio,
        bool AxiallyExcluded);

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
    /// A REEL'S OWN END FACES: how far its OWN mesh vertices reach along
    /// its OWN axis, signed from the axis frame's own origin. An empty mesh
    /// collapses to a point at that origin, which the ownership rule then
    /// treats as a reel with no length -- it owns nothing, which is the
    /// honest answer for a reel with no geometry.
    /// </summary>
    internal static (double Min, double Max) ReelAxialExtent(MechanismMesh mesh, MechanismFrame axis)
    {
        double[] direction = NormalizeOrZ(CrossProduct(axis.XAxis, axis.YAxis));
        double min = double.PositiveInfinity;
        double max = double.NegativeInfinity;
        foreach (double[] vertex in mesh.Vertices)
        {
            double along = AlongAxis(vertex, axis.Origin, direction);
            if (along < min)
                min = along;
            if (along > max)
                max = along;
        }
        return double.IsPositiveInfinity(min) ? (0.0, 0.0) : (min, max);
    }

    /// <summary>Where a point sits along a line, signed, given a UNIT direction.</summary>
    internal static double AlongAxis(double[] point, double[] lineOrigin, double[] lineDirectionUnit) =>
        ((point[0] - lineOrigin[0]) * lineDirectionUnit[0]) +
        ((point[1] - lineOrigin[1]) * lineDirectionUnit[1]) +
        ((point[2] - lineOrigin[2]) * lineDirectionUnit[2]);

    /// <summary>Every reel's own neighbourhood, measured once, in reel order.</summary>
    internal static ReelNeighbourhood[] BuildReelNeighbourhoods(IReadOnlyList<MechanismReelEntry> reels)
    {
        var built = new ReelNeighbourhood[reels.Count];
        for (int i = 0; i < reels.Count; i++)
        {
            double[] direction = NormalizeOrZ(
                CrossProduct(reels[i].Axis.XAxis, reels[i].Axis.YAxis));
            (double axialMin, double axialMax) = ReelAxialExtent(reels[i].Mesh, reels[i].Axis);
            built[i] = new ReelNeighbourhood(
                reels[i].Axis.Origin,
                direction,
                ReelRadialExtent(reels[i].Mesh, reels[i].Axis),
                axialMin,
                axialMax);
        }
        return built;
    }

    /// <summary>
    /// THE OWNERSHIP RULE: a routing frame belongs to the reel whose own
    /// neighbourhood it sits nearest, relative to that reel's own size --
    /// inside its radius AND between its own end faces, since the radial
    /// test alone measures an infinite line (see
    /// <see cref="RouteOwnerAxialMarginFraction"/>). Decides only; the
    /// caller does the reporting, so that a wire wrapped on a drum -- which
    /// sits at that drum's own boundary by construction, on every one of
    /// its frames -- is tallied once rather than warned about a hundred
    /// times over.
    /// </summary>
    internal static RouteOwnerVerdict ClassifyRouteFrameOwner(
        MechanismFrame frame, IReadOnlyList<ReelNeighbourhood> reels)
    {
        if (reels.Count == 0)
        {
            return new RouteOwnerVerdict(
                RouteOwnerBody, NoOwnerReel, NoOwnerReel,
                double.PositiveInfinity, 0.0, 0.0,
                NoOwnerReel, double.PositiveInfinity, false);
        }

        double bestRatio = double.PositiveInfinity;
        int bestIndex = NoOwnerReel;
        double bestDistance = 0.0;
        double bestRadius = 0.0;
        double secondRatio = double.PositiveInfinity;
        int secondIndex = NoOwnerReel;
        bool axiallyExcluded = false;

        for (int i = 0; i < reels.Count; i++)
        {
            ReelNeighbourhood reel = reels[i];
            double distance = PerpendicularDistanceToLine(
                frame.Origin, reel.AxisOrigin, reel.AxisDirection);
            double ratio = distance / reel.Radius;

            // BETWEEN ITS OWN FACES, or it is not on this reel at all.
            double along = AlongAxis(frame.Origin, reel.AxisOrigin, reel.AxisDirection);
            double axialMargin = RouteOwnerAxialMarginFraction * reel.Radius;
            if (along < reel.AxialMin - axialMargin || along > reel.AxialMax + axialMargin)
            {
                if (ratio <= 1.0)
                    axiallyExcluded = true;
                continue;
            }

            if (ratio < bestRatio)
            {
                secondRatio = bestRatio;
                secondIndex = bestIndex;
                bestRatio = ratio;
                bestIndex = i;
                bestDistance = distance;
                bestRadius = reel.Radius;
            }
            else if (ratio < secondRatio)
            {
                secondRatio = ratio;
                secondIndex = i;
            }
        }

        bool ownedByReel = bestIndex >= 0 && bestRatio <= 1.0;
        return new RouteOwnerVerdict(
            ownedByReel ? RouteOwnerReel : RouteOwnerBody,
            ownedByReel ? bestIndex : NoOwnerReel,
            bestIndex,
            bestRatio,
            bestDistance,
            bestRadius,
            secondIndex,
            secondRatio,
            axiallyExcluded);
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

    /// <summary>A rotation of <paramref name="angle"/> radians about a UNIT axis, Rodrigues, with X/Y/Z as its COLUMNS.</summary>
    internal static double[][] RotationAboutAxis(double[] axisUnit, double angle)
    {
        double c = Math.Cos(angle);
        double s = Math.Sin(angle);
        double t = 1.0 - c;
        double x = axisUnit[0];
        double y = axisUnit[1];
        double z = axisUnit[2];
        return new[]
        {
            new[] { (t * x * x) + c, (t * x * y) - (s * z), (t * x * z) + (s * y) },
            new[] { (t * x * y) + (s * z), (t * y * y) + c, (t * y * z) - (s * x) },
            new[] { (t * x * z) - (s * y), (t * y * z) + (s * x), (t * z * z) + c },
        };
    }

    /// <summary>Any unit vector perpendicular to a UNIT vector, chosen off its own smallest component so the cross product never degenerates.</summary>
    internal static double[] AnyPerpendicular(double[] unit)
    {
        double[] candidate = Math.Abs(unit[0]) <= Math.Abs(unit[1]) && Math.Abs(unit[0]) <= Math.Abs(unit[2])
            ? new[] { 1.0, 0.0, 0.0 }
            : Math.Abs(unit[1]) <= Math.Abs(unit[2])
                ? new[] { 0.0, 1.0, 0.0 }
                : new[] { 0.0, 0.0, 1.0 };
        return NormalizeOrZ(CrossProduct(unit, candidate));
    }

    /// <summary>The SHORTEST rotation carrying one unit vector onto another; the identity when they already agree, and a half turn about any perpendicular when they oppose.</summary>
    internal static double[][] MinimalRotation(double[] from, double[] to)
    {
        double[] cross = CrossProduct(from, to);
        double sine = Math.Sqrt((cross[0] * cross[0]) + (cross[1] * cross[1]) + (cross[2] * cross[2]));
        double cosine = (from[0] * to[0]) + (from[1] * to[1]) + (from[2] * to[2]);
        if (sine < 1.0e-12)
        {
            return cosine > 0.0
                ? BasisFromColumns(new[] { 1.0, 0.0, 0.0 }, new[] { 0.0, 1.0, 0.0 }, new[] { 0.0, 0.0, 1.0 })
                : RotationAboutAxis(AnyPerpendicular(from), Math.PI);
        }
        return RotationAboutAxis(
            new[] { cross[0] / sine, cross[1] / sine, cross[2] / sine },
            Math.Atan2(sine, cosine));
    }

    /// <summary>
    /// THE PLACEMENT FIT WHEN THE ANCHORS SIT IN A LINE (2026-09-08, third
    /// pass, and what his own machine turns out to need: his seven anchors
    /// per mechanism are collinear to within a thousandth of their own
    /// spread).
    ///
    /// Seven points on a line pin only TWO of the three rotational degrees
    /// of freedom. They fix which way the line points; they say nothing
    /// about the spin ABOUT that line, so a fit that demands all three from
    /// the origins refuses and throws away the two it could have had. Note
    /// what collinearity also means: a wrong spin about the anchor line
    /// moves those anchors not at all, so a large residual on collinear
    /// anchors is never a roll error -- it is the LINE ITSELF pointed
    /// wrongly, which the origins can fix exactly.
    ///
    /// So the job splits. The origins carry the line, exactly: every anchor
    /// lands on its own plane's origin, residual to zero. The remaining
    /// spin is taken from the AUTHORED AXES of all seven planes against all
    /// seven routing frames, by a closed-form circular least squares, not
    /// from plane [0] alone. Both handednesses are tried, because collinear
    /// origins cannot tell a mirrored side from a turned one either; the
    /// axes decide that too.
    ///
    /// The returned AxisDisagreementDegrees is how far the authored axes
    /// still disagree after the best spin, and it is the honest measure of
    /// how much to trust the one degree of freedom the origins could not
    /// supply. The caller says it out loud.
    /// </summary>
    internal static (double[][] Linear, double[] Translation, double Residual, double AxisDisagreementDegrees)? FitTransformAboutAnchorLine(
        IReadOnlyList<double[]?> source,
        IReadOnlyList<double[]?> target,
        IReadOnlyList<double[][]?> sourceAxes,
        IReadOnlyList<double[][]?> targetAxes)
    {
        var shared = new List<int>();
        int count = Math.Min(source.Count, target.Count);
        for (int i = 0; i < count; i++)
        {
            if (source[i] is not null && target[i] is not null)
                shared.Add(i);
        }
        if (shared.Count < 2)
            return null;

        int baseIndex = shared[0];
        double[] sourceBase = source[baseIndex]!;
        double[] targetBase = target[baseIndex]!;

        int farIndex = -1;
        double spread = 0.0;
        foreach (int i in shared)
        {
            double length = Distance(source[i]!, sourceBase);
            if (length > spread)
            {
                spread = length;
                farIndex = i;
            }
        }
        if (farIndex < 0 || spread <= 0.0)
            return null;

        double[] sourceLine = NormalizeOrZ(new[]
        {
            source[farIndex]![0] - sourceBase[0],
            source[farIndex]![1] - sourceBase[1],
            source[farIndex]![2] - sourceBase[2],
        });
        double[] targetLine = NormalizeOrZ(new[]
        {
            target[farIndex]![0] - targetBase[0],
            target[farIndex]![1] - targetBase[1],
            target[farIndex]![2] - targetBase[2],
        });

        // The spin is measured in a frame across the target line, right
        // handed with it, so the closed form below reads as an ordinary
        // rotation by theta in that plane.
        double[] across1 = AnyPerpendicular(targetLine);
        double[] across2 = CrossProduct(targetLine, across1);

        (double[][] Linear, double[] Translation, double Residual, double AxisDisagreementDegrees)? best = null;
        foreach (bool mirrored in new[] { false, true })
        {
            double[][] aligned = MinimalRotation(sourceLine, targetLine);
            if (mirrored)
            {
                // A reflection through a plane CONTAINING the source line,
                // so the line still lands on the target line and only the
                // handedness changes. Which perpendicular it is chosen
                // across does not matter: the spin below absorbs it.
                double[] normal = AnyPerpendicular(sourceLine);
                double[][] reflection =
                {
                    new[] { 1.0 - (2.0 * normal[0] * normal[0]), -2.0 * normal[0] * normal[1], -2.0 * normal[0] * normal[2] },
                    new[] { -2.0 * normal[1] * normal[0], 1.0 - (2.0 * normal[1] * normal[1]), -2.0 * normal[1] * normal[2] },
                    new[] { -2.0 * normal[2] * normal[0], -2.0 * normal[2] * normal[1], 1.0 - (2.0 * normal[2] * normal[2]) },
                };
                aligned = Multiply3(aligned, reflection);
            }

            double sumSin = 0.0;
            double sumCos = 0.0;
            foreach (int i in shared)
            {
                double[][]? fromAxes = i < sourceAxes.Count ? sourceAxes[i] : null;
                double[][]? toAxes = i < targetAxes.Count ? targetAxes[i] : null;
                if (fromAxes is null || toAxes is null)
                    continue;
                for (int a = 0; a < fromAxes.Length && a < toAxes.Length; a++)
                {
                    double[] turned = MultiplyVector3(aligned, fromAxes[a]);
                    double p = Dot3(turned, across1);
                    double q = Dot3(turned, across2);
                    double r = Dot3(toAxes[a], across1);
                    double s = Dot3(toAxes[a], across2);
                    sumCos += (p * r) + (q * s);
                    sumSin += (p * s) - (q * r);
                }
            }

            double spin = Math.Abs(sumSin) < 1.0e-12 && Math.Abs(sumCos) < 1.0e-12
                ? 0.0
                : Math.Atan2(sumSin, sumCos);
            double[][] linear = Multiply3(RotationAboutAxis(targetLine, spin), aligned);
            double[] mapped = MultiplyVector3(linear, sourceBase);
            double[] translation =
            {
                targetBase[0] - mapped[0],
                targetBase[1] - mapped[1],
                targetBase[2] - mapped[2],
            };

            double residual = 0.0;
            foreach (int i in shared)
            {
                double[] predicted = MultiplyVector3(linear, source[i]!);
                predicted[0] += translation[0];
                predicted[1] += translation[1];
                predicted[2] += translation[2];
                double gap = Distance(predicted, target[i]!);
                if (gap > residual)
                    residual = gap;
            }

            double totalAngle = 0.0;
            int angleCount = 0;
            foreach (int i in shared)
            {
                double[][]? fromAxes = i < sourceAxes.Count ? sourceAxes[i] : null;
                double[][]? toAxes = i < targetAxes.Count ? targetAxes[i] : null;
                if (fromAxes is null || toAxes is null)
                    continue;
                for (int a = 0; a < fromAxes.Length && a < toAxes.Length; a++)
                {
                    double alignment = Dot3(MultiplyVector3(linear, fromAxes[a]), toAxes[a]);
                    totalAngle += Math.Acos(Math.Clamp(alignment, -1.0, 1.0));
                    angleCount++;
                }
            }
            double disagreement = angleCount > 0
                ? totalAngle / angleCount * (180.0 / Math.PI)
                : double.NaN;

            bool better = best is null ||
                residual < best.Value.Residual - 1.0e-12 ||
                (Math.Abs(residual - best.Value.Residual) <= 1.0e-12 &&
                 !double.IsNaN(disagreement) &&
                 (double.IsNaN(best.Value.AxisDisagreementDegrees) ||
                  disagreement < best.Value.AxisDisagreementDegrees));
            if (better)
                best = (linear, translation, residual, disagreement);
        }
        return best;
    }

    internal static double Dot3(double[] a, double[] b) =>
        (a[0] * b[0]) + (a[1] * b[1]) + (a[2] * b[2]);

    /// <summary>The world's own up, the one direction a machine standing on a foundation does not have to be told.</summary>
    internal static readonly double[] WorldUp = { 0.0, 0.0, 1.0 };

    /// <summary>
    /// The MEDIAN of a set of values, which is what a winding radius wants
    /// rather than a mean: a wire's frames are nearly all at the drum's own
    /// radius and a handful sit on the run in and out, and a median ignores
    /// those where a mean would be dragged by them.
    /// </summary>
    internal static double MedianOf(IReadOnlyList<double> values)
    {
        var sorted = values.OrderBy(v => v).ToList();
        int middle = sorted.Count / 2;
        return sorted.Count % 2 == 1
            ? sorted[middle]
            : (sorted[middle - 1] + sorted[middle]) / 2.0;
    }

    /// <summary>The mean of a set of points; the origin for an empty set.</summary>
    internal static double[] CentroidOf(IReadOnlyList<double[]> points)
    {
        if (points.Count == 0)
            return new[] { 0.0, 0.0, 0.0 };
        var sum = new double[3];
        foreach (double[] p in points)
        {
            sum[0] += p[0];
            sum[1] += p[1];
            sum[2] += p[2];
        }
        return new[] { sum[0] / points.Count, sum[1] / points.Count, sum[2] / points.Count };
    }

    /// <summary>
    /// The component of a vector ACROSS a unit axis, normalised: the axis's
    /// own contribution removed. Falls back to any perpendicular when the
    /// vector is parallel to the axis and so has no across-component at all.
    /// </summary>
    internal static double[] AcrossAxis(double[] v, double[] axisUnit)
    {
        double along = Dot3(v, axisUnit);
        double[] across =
        {
            v[0] - (along * axisUnit[0]),
            v[1] - (along * axisUnit[1]),
            v[2] - (along * axisUnit[2]),
        };
        double length = Math.Sqrt(Dot3(across, across));
        return length < 1.0e-9 ? AnyPerpendicular(axisUnit) : new[]
        {
            across[0] / length, across[1] / length, across[2] / length,
        };
    }

    private static double[] Negate3(double[] v) => new[] { -v[0], -v[1], -v[2] };

    private static double[] Difference3(double[] a, double[] b) =>
        new[] { a[0] - b[0], a[1] - b[1], a[2] - b[2] };

    /// <summary>
    /// PLACEMENT DERIVED FROM THE NET'S OWN ANCHOR ROWS, so that nothing is
    /// authored and therefore nothing can flip (his ruling, 2026-09-09).
    ///
    /// THE RULE, and its whole content is that BOTH SIDES OF THE
    /// CORRESPONDENCE ARE BUILT THE SAME WAY:
    ///
    ///   X   along the line of anchors
    ///   Z   the world's own up, taken across X
    ///   Y   Z cross X
    ///
    /// and X's sign settled by which side of that line the MACHINE sits on:
    /// in the machine's own space, Y must point from its wire ends toward
    /// its body; in the world, Y must point away from the net. Those are the
    /// same physical statement, which is what makes the two frames
    /// comparable. An earlier attempt used "toward the net's centre" in the
    /// world against "toward the wire's net end" in the machine, and those
    /// are NOT the same direction -- caught by prototyping the rule against
    /// his own exported study before any of this was written, where it put
    /// every anchor 0.97 of a unit out.
    ///
    /// Every placement it derives is a PROPER ROTATION (his ruling: one
    /// machine, built once, turned round, never a mirror-image second
    /// product), and it reproduces his hand-authored side 0 exactly.
    ///
    /// The seven planes it synthesises per group carry the derived
    /// orientation applied to each wire's OWN first-frame axes, so the
    /// settled one-correspondence maths downstream recovers exactly this
    /// transform with a zero residual, and every door-guard, diagnosis and
    /// document downstream runs unchanged against derived planes and
    /// authored ones alike.
    /// </summary>
    internal static List<MechanismPlacementBranch> DerivePlacements(
        ResultDto result,
        IReadOnlyDictionary<int, MechanismRoutingWire> routingByIndex,
        List<string> warnings,
        List<string> notes)
    {
        var derived = new List<MechanismPlacementBranch>();
        EquilibriumResultDto? eq = result.Equilibrium;
        if (eq is null || eq.Vertices.Count == 0)
        {
            warnings.Add(
                "Placement (PL) is not authored and none could be derived: " +
                "the wired Result carries no solved net to read anchor rows " +
                "from. Wire a solved Result, or author Placement planes.");
            return derived;
        }

        // THE MACHINE'S OWN END OF THE CORRESPONDENCE. Every wire must carry
        // frames: a derived placement pairs each wire with an anchor, and a
        // wire with no first frame has nothing to pair.
        var first = new double[PlacementGroupSize][];
        var xAxis = new double[PlacementGroupSize][];
        var yAxis = new double[PlacementGroupSize][];
        var last = new List<double[]>(PlacementGroupSize);
        for (int i = 0; i < PlacementGroupSize; i++)
        {
            if (!routingByIndex.TryGetValue(i, out MechanismRoutingWire? wire) ||
                wire.Route.Count == 0)
            {
                warnings.Add(
                    $"Placement (PL) is not authored and none could be derived: " +
                    $"Routing (RT)[{i}] carries no frames, and a derived " +
                    "placement pairs every one of the seven wires with an " +
                    "anchor of its own.");
                return derived;
            }
            first[i] = wire.Route[0].Origin;
            xAxis[i] = wire.Route[0].XAxis;
            yAxis[i] = wire.Route[0].YAxis;
            last.Add(wire.Route[wire.Route.Count - 1].Origin);
        }

        double[] machineX = NormalizeOrZ(Difference3(first[PlacementGroupSize - 1], first[0]));
        double[] machineZ = AcrossAxis(WorldUp, machineX);
        double[] machineY = CrossProduct(machineZ, machineX);
        double[] wireEndCentre = CentroidOf(first);
        double[] bodyCentre = CentroidOf(last);
        if (Dot3(machineY, Difference3(bodyCentre, wireEndCentre)) < 0.0)
        {
            machineX = Negate3(machineX);
            machineY = CrossProduct(machineZ, machineX);
        }
        int[] alongMachine = Enumerable.Range(0, PlacementGroupSize)
            .OrderBy(i => Dot3(first[i], machineX))
            .ToArray();
        double[][] machineBasisTransposed =
            Transpose3(BasisFromColumns(machineX, machineY, machineZ));

        var netPoints = new List<double[]>(eq.Vertices.Count);
        foreach (Point3Dto v in eq.Vertices)
            netPoints.Add(new[] { v.X, v.Y, v.Z });
        double[] netCentre = CentroidOf(netPoints);

        List<List<int>> rows = MechanismGeometry.AnchorRowIndices(result);
        if (rows.Count == 0)
        {
            warnings.Add(
                "Placement (PL) is not authored and none could be derived: " +
                "the solved Result carries no anchor rows.");
            return derived;
        }

        int placedTotal = 0;
        for (int side = 0; side < rows.Count; side++)
        {
            List<int> row = rows[side];
            var rowPoints = row.Select(id => netPoints[id]).ToList();
            if (row.Count < PlacementGroupSize)
            {
                warnings.Add(
                    $"Anchor row {side} holds {row.Count} anchor(s), fewer " +
                    $"than the {PlacementGroupSize} one machine needs; no " +
                    "mechanism is placed on it.");
                continue;
            }

            // THE ROW'S OWN DIRECTION, from its two furthest-apart anchors,
            // so the order along it can never depend on how the row was
            // walked.
            double[] rowDirection = NormalizeOrZ(Difference3(rowPoints[1], rowPoints[0]));
            double widest = 0.0;
            for (int a = 0; a < rowPoints.Count; a++)
            {
                for (int b = a + 1; b < rowPoints.Count; b++)
                {
                    double span = Distance(rowPoints[a], rowPoints[b]);
                    if (span > widest)
                    {
                        widest = span;
                        rowDirection = NormalizeOrZ(Difference3(rowPoints[b], rowPoints[a]));
                    }
                }
            }
            List<int> sorted = Enumerable.Range(0, row.Count)
                .OrderBy(i => Dot3(rowPoints[i], rowDirection))
                .ToList();

            int groups = row.Count / PlacementGroupSize;
            int leftover = row.Count % PlacementGroupSize;
            for (int g = 0; g < groups; g++)
            {
                var anchors = new double[PlacementGroupSize][];
                for (int k = 0; k < PlacementGroupSize; k++)
                    anchors[k] = rowPoints[sorted[(g * PlacementGroupSize) + k]];

                double[] worldX = NormalizeOrZ(
                    Difference3(anchors[PlacementGroupSize - 1], anchors[0]));
                double[] worldZ = AcrossAxis(WorldUp, worldX);
                double[] worldY = CrossProduct(worldZ, worldX);
                double[] groupCentre = CentroidOf(anchors);
                if (Dot3(worldY, Difference3(netCentre, groupCentre)) > 0.0)
                {
                    worldX = Negate3(worldX);
                    worldY = CrossProduct(worldZ, worldX);
                }
                int[] alongRow = Enumerable.Range(0, PlacementGroupSize)
                    .OrderBy(k => Dot3(anchors[k], worldX))
                    .ToArray();

                double[][] rotation = Multiply3(
                    BasisFromColumns(worldX, worldY, worldZ), machineBasisTransposed);

                var planes = new MechanismPlacementPlane[PlacementGroupSize];
                for (int k = 0; k < PlacementGroupSize; k++)
                {
                    int wire = alongMachine[k];
                    planes[wire] = new MechanismPlacementPlane(
                        anchors[alongRow[k]],
                        MultiplyVector3(rotation, xAxis[wire]),
                        MultiplyVector3(rotation, yAxis[wire]),
                        MultiplyVector3(rotation, CrossProduct(xAxis[wire], yAxis[wire])));
                }
                derived.Add(new MechanismPlacementBranch(
                    new MechanismInstanceId(side, g), planes));
                placedTotal++;
            }

            if (leftover > 0)
            {
                warnings.Add(
                    $"Anchor row {side}: {leftover} anchor(s) are left over " +
                    $"after {groups} machine(s) of {PlacementGroupSize} wires " +
                    "and carry no mechanism. A machine is never stretched or " +
                    "half-filled to use them up; add or remove anchors if you " +
                    "want the row filled exactly.");
            }
        }

        if (placedTotal > 0)
        {
            notes.Add(
                $"Placement (PL) was not authored, so {placedTotal} " +
                $"mechanism(s) were DERIVED from the net's own anchor rows " +
                $"({rows.Count} row(s)), every one a rotation and none a " +
                "mirror." + Environment.NewLine +
                "The rule builds both ends of the correspondence the same " +
                "way: X along the line of anchors, Z the world's own up " +
                "taken across X, Y = Z cross X, with X's sign settled by " +
                "which side of that line the machine sits on -- toward its " +
                "own body in its own space, away from the net in the world. " +
                "Nothing here is authored, so nothing here can flip. The " +
                "seven planes each machine gets carry that orientation " +
                "applied to each wire's own first-frame axes, so every " +
                "door-guard below runs against them exactly as it would " +
                "against planes you drew.");
        }
        return derived;
    }

    /// <summary>
    /// Move everything added from <paramref name="from"/> onwards to the
    /// FRONT of the list, keeping its own order. Grasshopper's balloon shows
    /// fifteen lines and then "further remarks not shown", so a chin whose
    /// actionable half is written last loses exactly the half that matters.
    /// </summary>
    internal static void MoveTailToFront(List<string> lines, int from)
    {
        if (from <= 0 || from >= lines.Count)
            return;
        List<string> tail = lines.GetRange(from, lines.Count - from);
        lines.RemoveRange(from, lines.Count - from);
        lines.InsertRange(0, tail);
    }

    internal static double[][] Transpose3(double[][] m) => new[]
    {
        new[] { m[0][0], m[1][0], m[2][0] },
        new[] { m[0][1], m[1][1], m[2][1] },
        new[] { m[0][2], m[1][2], m[2][2] },
    };

    /// <summary>
    /// HOW FAR TWO POINT SETS ARE FROM BEING THE SAME SHAPE, pair by
    /// matching pair: the worst disagreement between the distance from
    /// a[i] to a[j] and the distance from b[i] to b[j], over every pair
    /// BOTH sets carry. Placement-free by construction -- edge lengths do
    /// not care where or how a set is placed, or whether it is mirrored --
    /// so this separates "the same seven points, wrongly oriented" from
    /// "not the same seven points at all", which a residual alone cannot.
    /// </summary>
    internal static double OrderedShapeMismatch(
        IReadOnlyList<double[]?> a, IReadOnlyList<double[]?> b)
    {
        double worst = 0.0;
        int count = Math.Min(a.Count, b.Count);
        for (int i = 0; i < count; i++)
        {
            if (a[i] is null || b[i] is null)
                continue;
            for (int j = i + 1; j < count; j++)
            {
                if (a[j] is null || b[j] is null)
                    continue;
                double gap = Math.Abs(Distance(a[i]!, a[j]!) - Distance(b[i]!, b[j]!));
                if (gap > worst)
                    worst = gap;
            }
        }
        return worst;
    }

    /// <summary>
    /// The same measure with the PAIRING THROWN AWAY: both sets' own edge
    /// lengths sorted, then compared in order. Small here while
    /// <see cref="OrderedShapeMismatch"/> is large means the two sets are
    /// the same shape carrying the same edges -- just not matched up the
    /// same way, which is what a wrongly ordered branch looks like.
    /// </summary>
    internal static double UnorderedShapeMismatch(
        IReadOnlyList<double[]?> a, IReadOnlyList<double[]?> b)
    {
        var left = new List<double>();
        var right = new List<double>();
        int count = Math.Min(a.Count, b.Count);
        for (int i = 0; i < count; i++)
        {
            if (a[i] is null || b[i] is null)
                continue;
            for (int j = i + 1; j < count; j++)
            {
                if (a[j] is null || b[j] is null)
                    continue;
                left.Add(Distance(a[i]!, a[j]!));
                right.Add(Distance(b[i]!, b[j]!));
            }
        }
        if (left.Count == 0)
            return double.PositiveInfinity;
        left.Sort();
        right.Sort();
        double worst = 0.0;
        for (int k = 0; k < left.Count; k++)
        {
            double gap = Math.Abs(left[k] - right[k]);
            if (gap > worst)
                worst = gap;
        }
        return worst;
    }

    /// <summary>
    /// An orthonormal basis founded on THREE POINTS: X along the first
    /// offset, Y the second offset's own component across it, Z their cross
    /// product. Null when the three are coincident or collinear, which
    /// founds no basis at all.
    /// </summary>
    internal static double[][]? OrthonormalBasisFromPoints(
        double[] origin, double[] alongX, double[] inPlane)
    {
        double[] u =
        {
            alongX[0] - origin[0], alongX[1] - origin[1], alongX[2] - origin[2],
        };
        double lengthU = Math.Sqrt((u[0] * u[0]) + (u[1] * u[1]) + (u[2] * u[2]));
        if (lengthU < 1.0e-12)
            return null;
        double[] e1 = { u[0] / lengthU, u[1] / lengthU, u[2] / lengthU };

        double[] v =
        {
            inPlane[0] - origin[0], inPlane[1] - origin[1], inPlane[2] - origin[2],
        };
        double along = (v[0] * e1[0]) + (v[1] * e1[1]) + (v[2] * e1[2]);
        double[] w =
        {
            v[0] - (along * e1[0]), v[1] - (along * e1[1]), v[2] - (along * e1[2]),
        };
        double lengthW = Math.Sqrt((w[0] * w[0]) + (w[1] * w[1]) + (w[2] * w[2]));
        if (lengthW < 1.0e-12)
            return null;
        double[] e2 = { w[0] / lengthW, w[1] / lengthW, w[2] / lengthW };
        return BasisFromColumns(e1, e2, CrossProduct(e1, e2));
    }

    /// <summary>
    /// THE FALLBACK PLACEMENT FIT, founded on the seven ORIGINS rather than
    /// on one authored plane's own axes.
    ///
    /// WHY IT EXISTS (2026-09-08, his own machine): the settled maths derive
    /// the whole instance transform from ONE correspondence -- Routing
    /// (RT)[0]'s own first frame against placement plane [0] -- so the
    /// instance inherits that one plane's own X and Y. A routing frame's own
    /// X and Y spin freely about the wire's tangent (a perp-frame on a curve
    /// picks them arbitrarily), and an anchor plane's own axes are whatever
    /// they were authored as. There is no reason for the two to agree, and
    /// when they do not, every one of the other six wires lands rotated
    /// about plane [0] -- which on his machine read as 1.36 m of residual
    /// while all seven origins sat exactly where they belong.
    ///
    /// The seven origins carry that orientation redundantly and without
    /// convention, so they can found it instead. Both handednesses are
    /// tried and the better kept, which means a genuinely mirrored side
    /// still yields a genuine reflection -- derived from where its own
    /// anchors sit rather than from a hand-authored left-handed plane.
    ///
    /// Returns null when fewer than three correspondences exist or when the
    /// points are effectively collinear, since neither founds an
    /// orientation. The caller keeps the authored-axis transform then.
    /// </summary>
    internal static (double[][] Linear, double[] Translation, double Residual)? FitTransformFromOrigins(
        IReadOnlyList<double[]?> source, IReadOnlyList<double[]?> target)
    {
        var shared = new List<int>();
        int count = Math.Min(source.Count, target.Count);
        for (int i = 0; i < count; i++)
        {
            if (source[i] is not null && target[i] is not null)
                shared.Add(i);
        }
        if (shared.Count < 3)
            return null;

        int baseIndex = shared[0];
        double[] sourceBase = source[baseIndex]!;
        double[] targetBase = target[baseIndex]!;

        // The furthest correspondence founds the first direction.
        int firstIndex = -1;
        double spread = 0.0;
        foreach (int i in shared)
        {
            if (i == baseIndex)
                continue;
            double length = Distance(source[i]!, sourceBase);
            if (length > spread)
            {
                spread = length;
                firstIndex = i;
            }
        }
        if (firstIndex < 0 || spread <= 0.0)
            return null;

        // The most OFF-axis correspondence founds the second, so the basis
        // is as well conditioned as the seven points allow.
        int secondIndex = -1;
        double bestReach = 0.0;
        double[] axis = NormalizeOrZ(new[]
        {
            source[firstIndex]![0] - sourceBase[0],
            source[firstIndex]![1] - sourceBase[1],
            source[firstIndex]![2] - sourceBase[2],
        });
        foreach (int i in shared)
        {
            if (i == baseIndex || i == firstIndex)
                continue;
            double reach = PerpendicularDistanceToLine(source[i]!, sourceBase, axis);
            if (reach > bestReach)
            {
                bestReach = reach;
                secondIndex = i;
            }
        }
        if (secondIndex < 0 || bestReach < CollinearFitFraction * spread)
            return null;

        double[][]? sourceBasis = OrthonormalBasisFromPoints(
            sourceBase, source[firstIndex]!, source[secondIndex]!);
        double[][]? targetBasis = OrthonormalBasisFromPoints(
            targetBase, target[firstIndex]!, target[secondIndex]!);
        if (sourceBasis is null || targetBasis is null)
            return null;

        double[][] sourceBasisTransposed = Transpose3(sourceBasis);
        double[] f1 = Column3(targetBasis, 0);
        double[] f2 = Column3(targetBasis, 1);
        double[] f3 = Column3(targetBasis, 2);

        (double[][] Linear, double[] Translation, double Residual)? best = null;
        foreach (double handedness in new[] { 1.0, -1.0 })
        {
            double[][] handed = BasisFromColumns(
                f1, f2, new[] { handedness * f3[0], handedness * f3[1], handedness * f3[2] });
            double[][] linear = Multiply3(handed, sourceBasisTransposed);
            double[] mapped = MultiplyVector3(linear, sourceBase);
            double[] translation =
            {
                targetBase[0] - mapped[0],
                targetBase[1] - mapped[1],
                targetBase[2] - mapped[2],
            };
            double residual = 0.0;
            foreach (int i in shared)
            {
                double[] predicted = MultiplyVector3(linear, source[i]!);
                predicted[0] += translation[0];
                predicted[1] += translation[1];
                predicted[2] += translation[2];
                double gap = Distance(predicted, target[i]!);
                if (gap > residual)
                    residual = gap;
            }
            if (best is null || residual < best.Value.Residual)
                best = (linear, translation, residual);
        }
        return best;
    }
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
            "OPTIONAL. Leave it EMPTY and the placement is derived from " +
            "the solved net's own anchor rows instead: X along the line of " +
            "anchors, Z the world's own up across it, Y completing them, " +
            "and the machine turned to face away from the net. Nothing is " +
            "authored that way, so nothing can flip when the form changes, " +
            "and every instance is a rotation of one machine rather than a " +
            "mirror-image second one. Wire it and you override that: seven " +
            "planes per branch, tree path {side}{group}, plane i the world " +
            "target for Routing wire i, the transform taken from plane 0 " +
            "against Routing wire 0's own first frame and validated " +
            "against the other six.",
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

            // THE RESULT IS READ, NOT DISCARDED, now that a placement can be
            // DERIVED from the net's own anchor rows when none is authored
            // (his ruling, 2026-09-09).
            bool hasResult = TryReadResult(data, out ResultDto? solved);

            MechanismAssetInput asset = ReadAsset(data, warnings);
            List<MechanismRoutingWire> routing = ReadRouting(data, warnings);
            List<MechanismPlacementBranch> placements = ReadPlacements(data, warnings);

            string? payload = MechanismCollector.BuildWithResult(
                asset, routing, placements, warnings, notes, solved);

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
            // THE BALLOON GETS THE HEADLINE, STATUS GETS ALL OF IT.
            foreach (string warning in warnings)
            {
                status.Add(warning);
                AddRuntimeMessage(GH_RuntimeMessageLevel.Warning, Headline(warning));
            }
            foreach (string note in notes)
            {
                status.Add(note);
                AddRuntimeMessage(GH_RuntimeMessageLevel.Remark, Headline(note));
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
    /// <summary>
    /// A wired mesh, however Grasshopper chose to hand it over.
    ///
    /// THE BUG THIS FIXES, found by Param's first real wiring: reading an
    /// input as <c>object</c> gives back the GOO WRAPPER (GH_Mesh, GH_Brep,
    /// GH_ObjectWrapper), never the bare <see cref="Mesh"/>, so a switch on
    /// the geometry types alone matched NOTHING and every part he wired was
    /// refused as "not a mesh" while being a perfectly good mesh. Unwrap
    /// first, through the goo's own cast so a Brep-shaped goo converts the
    /// way Grasshopper itself would, and only then look at the geometry.
    /// </summary>
    private static object? UnwrapGeometry(object? item)
    {
        if (item is IGH_Goo goo)
        {
            if (goo.CastTo(out Mesh castMesh) && castMesh is not null)
                return castMesh;
            if (goo.CastTo(out Brep castBrep) && castBrep is not null)
                return castBrep;
            if (goo is GH_ObjectWrapper wrapper)
                return wrapper.Value;
        }
        return item;
    }

    private static bool TryMeshOrBrep(object? item, out MechanismMesh? mesh, out bool fromBrep)
    {
        fromBrep = false;
        mesh = null;
        item = UnwrapGeometry(item);
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
