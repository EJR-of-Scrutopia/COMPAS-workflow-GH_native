#nullable enable

using System;
using System.Collections;
using System.Collections.Generic;
using System.Globalization;
using System.IO;
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

/// <summary>
/// THE ONE AUTHORED MECHANISM, his five parts (plus the reels' own axes,
/// which travel with them): Frame 1, one joined mesh; Frame 2, a SECOND
/// frame part in a different material, several objects, joined only as far
/// as he can join them; the Motors, one joined mesh; the Tension Tie, ONE
/// FUSED mesh (his settled ruling: the foundation anchor and the tension
/// tie are now one object, so this single part carries both, permanence
/// "permanent"); and the Reels, kept OUT of Frame 1 (his own words: "its
/// not all combined as one mesh in the frame") because a reel spins and a
/// frame does not.
///
/// THE REELS ARRIVE ALREADY RESOLVED, as ENTRIES (spec 4.1, his ruling 1.5
/// of 2026-09-09): one authored mesh at N bodies, not N meshes zipped to N
/// planes. His ten physical reels are FOUR entries, and that is the whole
/// point -- the drum mesh is serialised once per entry rather than once per
/// reel. The pairing of meshes to axes now happens in the READER, where the
/// Grasshopper tree that expresses the grouping still exists
/// (<see cref="MechanismReels.Resolve"/>); by the time an asset is built
/// the grouping is settled and nothing downstream re-derives it.
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
    IReadOnlyList<MechanismReelGroup> Reels,

    // THE ONE TYPICAL ANCHOR, authored once and stamped at every anchor the
    // net has (2026-09-09, his ask: "I can do tension tie, but the anchors
    // dont play fair in my script with many chnaging forms").
    //
    // ONE PER SIDE (his corrected model, 2026-09-09): the anchor is one
    // continuous mass under the whole springing, the shape of the skin edge
    // on the first row, so the machines sit cleanly on it. It is not one per
    // machine and it is not one per cable.
    //
    // ITS DECLARED CONVENTION, so nothing downstream infers it from a mesh:
    // authored in its own local space, +Z is UP, X runs ALONG THE ROW, and
    // THE LOCAL ORIGIN IS THE CENTRE OF THE ROW it spans. Model its bearing
    // face on the z=0 plane and it sits on the ground wherever the net meets
    // it.
    MechanismMesh? Anchor,
    bool AnchorFromBrep);

/// <summary>
/// ONE OF THE SEVEN WIRES the one authored mechanism routes, indexed by
/// wire number (0..6) rather than by instance -- routing is authored ONCE,
/// for the mechanism, never per placement. An ordered list of local routing
/// planes in threading order, <c>Route[0]</c> the NET END by his ruling
/// (R2), and also -- new here -- the FIRST CORRESPONDENCE every placement
/// branch derives its instance transform from when <c>Wire == 0</c>.
/// </summary>
internal sealed record MechanismRoutingWire(int Wire, IReadOnlyList<MechanismFrame> Route);

/// <summary>
/// THE MACHINE A STUDY CITES (ruling 1.2: "a study cites exactly ONE
/// machine, by id, and the export writes N placements of it"), read off the
/// <c>bench.machine/1</c> document wired to the Mechanism component's own
/// Machine (MA) port by
/// <see cref="MechanismCollector.ReadMachineCitation"/>.
///
/// FOUR FACTS AND NO BODIES, which is the whole point of the split: the
/// study points at the machine and carries none of it. The bodies, the reel
/// entries and the unit-local routing stay in the machine document, which
/// uploads once (ruling 1.7: it stays about 36 MiB while the study falls to
/// a few hundred KB).
///
/// WHY <c>WireCount</c> TRAVELS: it is the machine's own declared count of
/// routed wires, and the study cross-checks the wires it actually places
/// against it BY EQUALITY (spec 5.5).
/// <see cref="MechanismCollector.PlacementGroupSize"/> is a compile-time
/// seven, so without that check a study citing a twelve-wire machine writes
/// twelve in its citation and exactly seven wires: the document validates,
/// seven cables animate and five are simply absent.
///
/// WHY <c>ReeveDefault</c> TRAVELS: it is the SECOND SOURCE of every wire's
/// resolved reeve factor (spec 6.1 to 6.3). The per-wire override wins over
/// it, and NOTHING comes after it -- a study with no machine to take a
/// default from is refused by name rather than given a number nobody
/// authored.
///
/// WHY <c>CableSpan</c> TRAVELS (spec 7.4, Task 7): it is the machine's own
/// <c>footprint.cableSpan</c>, the distance between its first and its last
/// routed wire's own <c>route[0]</c>, MEASURED IN THE MACHINE'S OWN DOCUMENT.
/// That makes it the one fact about the layout that the study's own placement
/// derivation did not produce. Every other number the study document could
/// check a placement with is fed from the anchor rows the placement was
/// derived FROM, so on the default path it agrees with itself by
/// construction; this one is sourced elsewhere and can therefore disagree.
///
/// IT IS OPTIONAL, unlike the four above, and its absence refuses nothing: a
/// machine routing fewer than two wires has no cable line and writes no
/// <c>footprint</c> at all, so the witness that reads it simply does not run.
///
/// NOT PROVED BY ANYTHING THAT BUILDS ONE, and said rather than left to be
/// found: that the machine document this was read from is the same document
/// the studio will later resolve the id against. Nothing in this repo has an
/// upload route (spec 11.1), the machine arrives through the library folder,
/// and a file whose contents have moved on since the study was exported
/// cannot be seen from here.
/// </summary>
internal sealed record MechanismMachineCitation(
    string Id,
    string Name,
    int WireCount,
    double ReeveDefault,
    double? CableSpan = null);

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
    /// THE CABLE'S OWN RADIUS, his ruling 2026-09-09: 0.02 m, settled as a
    /// RADIUS rather than a diameter, so the cable is 40 mm across.
    ///
    /// IT IS THE SAME CABLE THE NET IS PULLED BY, which is the fact that
    /// actually governs and the one he has stated twice ("the wires are the
    /// same as the cabes"). The machine's wire and the vault's cable meet at
    /// a net vertex and must arrive there as one continuous cable, so
    /// anything drawn from this number has to agree with whatever the net's
    /// own cables are drawn at.
    ///
    /// CARRIED IN THE DOCUMENT BECAUSE A GUESS CANNOT KNOW IT IS WRONG. It
    /// went round twice already: the studio first drew this wire at a 0.02 m
    /// radius while the document said nothing, then at 0.005 m when the
    /// document briefly said 0.01 m thick, and at that size his 0.0267 m
    /// helix pitch read as adjacent turns overlapping by 12 mm -- a
    /// modelling fault that never existed. Both the radius and the diameter
    /// are emitted, the same fact stated twice, so no reader can halve or
    /// double it by accident.
    ///
    /// A DEFAULT, not authored per study: there is no port for it yet, and
    /// the chin says so every time rather than letting it pass as measured.
    /// </summary>
    public const double DefaultCableRadiusMetres = 0.02;

    /// <summary>
    /// What a routing plane's origin marks on the cable, when he does not
    /// say. CENTRELINE, because that is the reading that composes safely
    /// with him offsetting the planes himself: an offset he has already
    /// applied must not be applied again by a reader.
    /// </summary>
    public const string DefaultRoutingFrameMeaning = "centreline";

    /// <summary>
    /// How far apart two anchors may sit, as a multiple of the anchor set's
    /// own median nearest-neighbour distance, and still belong to the same
    /// row. Generous enough to survive an uneven springing, far short of
    /// the gap between one springing and another.
    /// </summary>
    public const double AnchorRowReachFactor = 3.0;

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
    /// HOW CLOSE A ROUTING FRAME MUST SIT TO THE RADIUS ITS OWN REEL
    /// PUBLISHES, as a fraction of that radius, to count as AGREEING with
    /// it.
    ///
    /// The fraction is stated in the units the number is used in. A
    /// windingRadius drives exactly one thing, and the document says so
    /// itself: turns = take-up * reeveFactor / (2 * pi * windingRadius). A
    /// radius wrong by a fraction f spins that drum wrong by the same
    /// fraction f, so fifteen per cent here reads "within fifteen per cent
    /// of the spin rate this number implies".
    ///
    /// MEASURED RATHER THAN PICKED (2026-09-09, on his exported
    /// 2 Sided Vault machine). The one drum in that file that demonstrably
    /// IS a barrel, pulley 7, holds all 219 of its authored frames inside
    /// 2 per cent of a single radius. This band is seven and a half times
    /// that, so no wrap of that quality can be called disagreeing by it.
    /// </summary>
    public const double WindingRadiusAgreementFraction = 0.15;

    /// <summary>
    /// HOW MANY ROUTING FRAMES NEAR A REEL MAY DISAGREE WITH THE RADIUS IT
    /// PUBLISHES, per frame that agrees, before that radius is NAMED and
    /// marked unfit to animate.
    ///
    /// BOTH ENDS OF THIS NUMBER WERE MEASURED on his 2 Sided Vault machine
    /// (2026-09-09), with the agreement band above:
    ///   pulley 7, a real wrap on a real barrel, reads 0.041;
    ///   his seven spools, whose owned frames sweep 0.0200 m to 0.0600 m
    ///   about drums that publish 0.0330 m, read 4.00 to 4.24.
    /// The gap is a hundredfold, and 0.40 is its geometric centre: the
    /// exact centre of 0.041 and 4.00 is 0.4035, taken down to the nearer
    /// hundredth so that of two defensible values the gate is the more
    /// sensitive. The real wrap then sits a factor of ten below the limit
    /// and the real defect a factor of ten above it, so neither is near
    /// enough to the line for a differently proportioned machine to cross
    /// it by accident.
    /// </summary>
    public const double WindingRadiusScatterLimit = 0.40;

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
    /// THE MACHINE COMPONENT'S OWN REEVE DEFAULT, his unit's value (spec
    /// 6.1). The mechanical advantage of one wire's reeving through its
    /// block: a wheel that MOVES WITH THE LOAD gives advantage, one that
    /// merely guides gives none, and no amount of geometry can tell them
    /// apart, so it is authored rather than measured.
    /// </summary>
    public const double DefaultReeveFactor = 4.0;

    // THE STUDY SIDE'S PROVISIONAL REEVE DEFAULT IS GONE (Task 6). It was
    // 1.0, stated by the collector for itself while the Machine (MA) port
    // was registered and unread, and it is not replaced by a constant: a
    // study takes the default from the machine it CITES, and a study that
    // cites none is refused by name rather than given a number nobody
    // authored. Leaving a fallback here would put every export back to
    // applying 1.0 where he authored 4.0, with the geometry, the wire
    // paths and the timing all still correct so that nothing looks broken.

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
        BuildWithResult(
            asset, routing, placements, warnings, notes, null,
            DefaultRoutingFrameMeaning);

    /// <summary>
    /// The same build, with the solved Result available so that placement
    /// can be DERIVED from the net's own anchor rows when none is authored
    /// (his ruling, 2026-09-09: "the placement point will be figured out as
    /// part of the export"). A five-argument call is the same thing with
    /// nothing to derive from, kept so every existing caller stands.
    ///
    /// <paramref name="reevePerWire"/> is the collector's own Reeve Per
    /// Wire (RW) tree, resolved to a wire-indexed dictionary (spec 6.1),
    /// carried straight through to the payload's own reeve.perWire (below)
    /// and never inspected here: the RESOLUTION against a machine default
    /// happens once, downstream, in <c>MechanismDocument.Json</c>, which
    /// is the one place a Result -- and so a net vertex to match each wire
    /// against -- is available at all. Null or empty means no overrides
    /// were authored, which is the ordinary case and not itself a fault.
    ///
    /// <paramref name="machine"/> is the MACHINE THIS STUDY CITES (spec 5.1,
    /// ruling 1.2), read off the Machine (MA) port by
    /// <see cref="ReadMachineCitation"/>. It reaches the payload as the
    /// citation block a study document is built on, and its own authored
    /// reeve default is the SECOND SOURCE of every wire's resolved factor.
    ///
    /// NULL IS NOT NAMED HERE, and that is deliberate. This build is
    /// SHARED: <see cref="BuildMachine"/> drives it with no citation by
    /// design, a machine citing nothing being the whole point of a machine,
    /// and pools these same warnings into the Machine component's own chin.
    /// A message here would paint a CORRECT machine build orange over a
    /// port that component does not have. What null does instead is
    /// structural and cannot be missed downstream: no machine block and no
    /// reeve default are written, so <c>MechanismDocument.Json</c> refuses
    /// the document by name. The message for an uncited STUDY is raised
    /// where the port exists, in
    /// <c>MechanismCollectorComponent.SolveInstance</c>.
    /// </summary>
    public static string? BuildWithResult(
        MechanismAssetInput asset,
        IReadOnlyList<MechanismRoutingWire> routing,
        IReadOnlyList<MechanismPlacementBranch> placements,
        List<string> warnings,
        List<string> notes,
        ResultDto? result,
        string? routingFrameMeaning,
        IReadOnlyDictionary<int, double>? reevePerWire = null,
        MechanismMachineCitation? machine = null)
    {
        ArgumentNullException.ThrowIfNull(asset);
        string meaning = (routingFrameMeaning ?? string.Empty).Trim().ToLowerInvariant();
        if (meaning.Length == 0)
        {
            meaning = DefaultRoutingFrameMeaning;
        }
        else if (meaning != "centreline" && meaning != "top" && meaning != "contact")
        {
            warnings.Add(
                $"Frame Meaning (FM) \"{routingFrameMeaning}\" is not one " +
                "of centreline, top or contact; read as " +
                $"\"{DefaultRoutingFrameMeaning}\".");
            meaning = DefaultRoutingFrameMeaning;
        }
        ArgumentNullException.ThrowIfNull(routing);
        ArgumentNullException.ThrowIfNull(placements);
        ArgumentNullException.ThrowIfNull(warnings);
        ArgumentNullException.ThrowIfNull(notes);

        bool anyAssetPart =
            asset.Frame1 is not null || asset.Frame2.Count > 0 || asset.Motors is not null ||
            asset.TensionTie is not null || asset.Reels.Count > 0;
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

        // REEL ENTRIES AND BODIES (spec 4.1, his ruling 1.5 of 2026-09-09:
        // "a reel ENTRY is one mesh at N axes, not N meshes"). The pairing
        // of meshes to axes is settled by the READER, where the tree that
        // expresses the grouping still exists; here they arrive resolved
        // and are used as authored.
        //
        // THIS REVERSES THE NOTE THAT STOOD HERE (spec 4.5). It recorded
        // his ten-reel statement as "a fact about the machine, not a
        // grouping to build: every reel here is driven by its own axis".
        // Ruling 1.5 reverses exactly that, so the note goes rather than
        // sits contradicting the build.
        IReadOnlyList<MechanismReelGroup> reels = asset.Reels;

        // THE PHYSICAL REELS, FLATTENED, AND THE ORDER IS PART OF THE
        // CONTRACT: entry 0's bodies in order, then entry 1's, and so on --
        // the order a reader gets by walking the document's own "reels"
        // array and flattening each entry's "bodies". Every ownerReel index
        // stamped on a routing frame counts PHYSICAL reels in this order,
        // not entries, because a wire rides one drum and not one kind.
        var reelBodies = new List<MechanismReelBody>();
        var reelBodyEntry = new List<int>();
        for (int e = 0; e < reels.Count; e++)
        {
            foreach (MechanismReelBody body in reels[e].Bodies)
            {
                reelBodies.Add(body);
                reelBodyEntry.Add(e);
            }
        }
        if (reelBodies.Count > 0 && reelBodies.Count != ExpectedReelCount)
        {
            notes.Add(
                $"mechanism: Reel (RE) carries {reelBodies.Count} " +
                "physical reel(s); his machine is ten, so this is unusual " +
                "but used as authored.");
        }
        if (reels.Count > 0)
        {
            notes.Add(
                $"mechanism: {reels.Count} reel ENTRY(ies) carrying " +
                $"{reelBodies.Count} BODY(ies). An entry is ONE authored " +
                "mesh at as many axes as it has bodies, so a drum that " +
                "appears seven times is serialised ONCE and carried to its " +
                "other six places by a transform. His own machine is four " +
                "entries at ten bodies: the spool entry with seven, and " +
                "three pulleys with one each.");
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

            // NO TIE MEANS NO KEY, not a key carrying null (spec 3.3, and
            // Task 1's mid-task finding). Dictionary<string, object?>
            // writes the key whatever the value, so an unwired tie used to
            // put an explicit "tensionTie": null into EVERY document this
            // build makes, the machine document included -- and the machine
            // document's whole negative invariant is that it carries no
            // permanent study work at all. A key standing for "there is no
            // such part" says nothing a reader cannot see from its absence,
            // and it forced the harness's own leak check to tolerate nulls
            // by name, which is a tolerance one careless write turns into a
            // hole. The same now goes for the anchor below.

            if (asset.Anchor is not null)
            {
                Dictionary<string, object?> anchorBody = MeshPayload(asset.Anchor);
                anchorBody[PermanenceField] = Permanent;
                mechanismOut["anchor"] = anchorBody;
                notes.Add(
                    "mechanism: an Anchor (AN) body was authored and is " +
                    "stamped at EVERY anchor the net has, once each, from " +
                    "one mesh. Its declared convention: +Z is up and its " +
                    "own ORIGIN is where the cable attaches, so that origin " +
                    "lands on the net vertex it holds. Model its bearing " +
                    "face on the z=0 plane and it sits on the ground too.");
                if (asset.AnchorFromBrep)
                    notes.Add($"Anchor (AN) {BrepMeshingNote}");
            }

            // NO ANCHOR MEANS NO KEY, for the reason given at the tie above.

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
                //
                // THE MESH IS WRITTEN ONCE PER ENTRY and the BODIES carry
                // it (spec 4.1 to 4.3). Each body states its own axis
                // plane, the transform that takes the entry's mesh frame
                // onto that axis (nine row-major numbers and three), and
                // that transform's DETERMINANT -- carried rather than left
                // for each reader to recompute, because it is the one
                // number that separates a rotation from a reflection.
                //
                // "axis" STAYS ON THE ENTRY, and it is BODY 0's: the entry
                // is authored at body 0, so its own frame is that body's
                // (spec 4.2). It is kept because everything that reads this
                // document today reads it, and it is the honest answer for
                // a single-body entry, which is every entry any fixture or
                // any machine of his has yet carried. A reader wanting the
                // OTHER bodies' axes must read "bodies", and the bank
                // cross-check is re-derived for entries in its own task
                // (spec 4.6).
                var bodiesOut = new List<Dictionary<string, object?>>(reels[i].Bodies.Count);
                foreach (MechanismReelBody body in reels[i].Bodies)
                {
                    bodiesOut.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                    {
                        ["axis"] = FramePayload(body.Axis),
                        ["linear"] = body.Linear,
                        ["translation"] = body.Translation,
                        ["determinant"] = body.Determinant,
                    });
                }
                reelsOut.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["reel"] = i,
                    ["mesh"] = MeshPayload(reels[i].Mesh),
                    ["axis"] = FramePayload(reels[i].Bodies[0].Axis),
                    ["bodies"] = bodiesOut,
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
                ? reels[0].Mesh   // the ENTRY's own mesh, authored at its body 0
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

            // THE REEVE DEFAULT IS STATED ONCE, AND NEVER INSIDE THIS
            // MECHANISM BLOCK (spec 6.3). The machine document lifts THIS
            // BLOCK whole into its own "machine" key, so a scalar written
            // here would travel into a machine document that already states
            // its own authored default in its header: one document, two
            // keys, two plausible numbers and neither null, which is how a
            // reader applies 1.0 where he authored 4.0 and every reel spins
            // four times too slowly.
            //
            // THE ONE STATEMENT IS NOW THE CITED MACHINE'S OWN (Task 6, and
            // the provisional 1.0 this collector used to state for itself
            // is retired with it): a study takes its default from the
            // machine it cites, and a study citing none writes no default
            // at all rather than a number nobody authored. The citation
            // itself is said once, at the payload's own assembly below,
            // because a study with routing and no parts at all still cites
            // a machine and this block does not run for one.

            // THE ROUTING FRAMES ARE THE CABLE'S CENTRELINE, his ruling,
            // said in the document so no consumer has to infer it from
            // where the frames happen to sit against a drum mesh.
            notes.Add(
                "mechanism: the routing frames are the cable's CENTRELINE " +
                "(his ruling), so draw the wire on them as they are and do " +
                "NOT offset them by a wire radius. cableRadius is his " +
                "stated default " +
                DefaultCableRadiusMetres.ToString("0.####", CultureInfo.InvariantCulture) +
                " m, settled as a RADIUS, and it is THE SAME CABLE THE NET " +
                "IS PULLED BY -- the machine's wire and the vault's cable " +
                "meet at a net vertex and must arrive there the same size. " +
                "cableThickness carries the diameter, the same fact stated " +
                "twice so nobody halves or doubles it. A default, not " +
                "authored per study and not measured from anything." +
                Environment.NewLine +
                $"Frame Meaning (FM) is \"{meaning}\": " +
                (meaning == "centreline"
                    ? "a plane's origin is where the cable's CENTRE runs, " +
                      "so a reader draws on the planes as they arrive and " +
                      "adds nothing. This is the reading to keep if YOU " +
                      "have offset the planes to clear the machine, since " +
                      "your offset has already put them where the centre " +
                      "goes and a second offset would double it."
                    : meaning == "top"
                        ? "the cable hangs one radius INWARD of each plane. " +
                          "Check that against your drums: routing planes " +
                          "sitting ON a barrel read this way put the whole " +
                          "cable INSIDE it."
                        : "the cable sits one radius OUTWARD of each plane, " +
                          "so a plane is where it touches the drum. Do NOT " +
                          "combine this with offsetting the planes " +
                          "yourself, or the cable stands off by two radii."));

            mechanismOut["cableRadius"] = DefaultCableRadiusMetres;
            mechanismOut["cableThickness"] = DefaultCableRadiusMetres * 2.0;
            mechanismOut["cableMatchesNetCable"] = true;
            mechanismOut["routingFrameMeaning"] = meaning;
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
        for (int r = 0; r < reelBodies.Count; r++)
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

        // THE FRAMES A REEL'S OWNERSHIP REFUSED, kept per reel and by
        // distance rather than merely counted (Task 8, spec 8.4). These are
        // the frames that came to a drum and were turned away: just outside
        // its own radius, or inside that radius but past its end faces.
        // They are what the winding radius scatter is a ratio OF, and they
        // have to be gathered here because this is the only pass that
        // classifies. A frame another reel OWNS is never counted against
        // this one: two drums on a common shaft each sit in the other's
        // radial shadow, and counting a neighbour's honest wrap as this
        // drum's refusal would paint a correct machine orange.
        var refusedRadii = new Dictionary<int, List<double>>();
        void Refuse(int reel, double distance)
        {
            if (!refusedRadii.TryGetValue(reel, out List<double>? refused))
            {
                refused = new List<double>();
                refusedRadii[reel] = refused;
            }
            refused.Add(distance);
        }

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

                if (verdict.AxiallyExcludedReel >= 0)
                    beyondTheFacesCount++;

                if (!ownedByReel &&
                    verdict.NearestReel >= 0 &&
                    verdict.NearestRatio <= 1.0 + RouteOwnerAmbiguityMargin)
                {
                    justOutsideCount++;
                    Refuse(verdict.NearestReel, verdict.NearestDistance);
                    if (verdict.NearestRatio < closestJustOutsideRatio)
                    {
                        closestJustOutsideRatio = verdict.NearestRatio;
                        closestJustOutsideReel = verdict.NearestReel;
                        closestJustOutsideWire = w;
                        closestJustOutsideFrame = frameIndex;
                    }
                }
                else if (!ownedByReel && verdict.AxiallyExcludedReel >= 0)
                {
                    // INSIDE THE DRUM'S RADIUS, PAST ITS FACES: refused by
                    // the axial half of ownership, and counted against the
                    // drum that refused it. An offset that rotates with the
                    // helix throws frames off the ends as well as off the
                    // surface, so leaving this half out would measure only
                    // half the defect.
                    Refuse(verdict.AxiallyExcludedReel, verdict.AxiallyExcludedDistance);
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
        //
        // WHAT THE SCATTER GATE BELOW IS NOT PROVED ON, said here rather
        // than left to be found (Task 8):
        //
        //   IT IS LIVE ONLY ON THE MACHINE BUILD PATH. A study build has no
        //   reels at all since Task 3 moved them off that component and its
        //   Reel (RE) and Reel Axis (AX) ports became refusing stubs, so
        //   BuildReelNeighbourhoods returns nothing there and every frame
        //   classifies as "body" before any geometry is read. The gate is
        //   built and proved through BuildMachine, where reels exist. That
        //   gap is the plan's own running DEFER and is not this code's to
        //   close.
        //
        //   IT SEES A SWEEP ON A FLANGED DRUM, which is the shape his seven
        //   spools have and the shape the defect was found on: the flange
        //   holds the wandering frames inside the ownership window, where
        //   their disagreement with the published radius is countable. A
        //   drum whose mesh stops AT the wire -- a grooved sheave with no
        //   cheek -- hides the same defect, because frames that leave that
        //   barrel by more than the ambiguity margin leave the tally
        //   altogether rather than entering the numerator. Nothing here
        //   claims to measure that case.
        var measuredRadii = new List<double>();
        if (mechanismOut is not null &&
            mechanismOut.TryGetValue("reels", out object? reelsObject) &&
            reelsObject is List<Dictionary<string, object?>> reelsPayload)
        {
            // EVERY REEL STATES A RADIUS, NEVER NULL (2026-09-09, and the
            // studio session had to write a rule around the null before I
            // fixed it -- counting an unstated radius as a drum gave it a
            // bank of eight for a machine with seven spools, which would
            // have chosen the wrong mechanism for every study).
            //
            // A reel that owns no routing frame has nothing to MEASURE, but
            // it still has a size: the furthest its own mesh reaches from
            // its own axis. That is a weaker number than a measurement and
            // is labelled as such rather than passed off as one, because a
            // reader that cannot tell them apart will trust the wrong one.
            // THE RADIUS BELONGS TO THE ENTRY, NOT TO ONE BODY, so an
            // entry's own frames are gathered from EVERY body of it before
            // the median is taken. That is not a convenience: an entry is
            // one drum authored once, its bodies are rigid images of it,
            // and they therefore share a radius exactly. Seven spools
            // carrying seven wires now measure one radius off up to seven
            // times the samples rather than one seventh of them each.
            var fellBack = new List<int>();
            var unfit = new List<(int Reel, double Scatter, int Agreeing, int Disagreeing)>();
            for (int r = 0; r < reelsPayload.Count; r++)
            {
                var entryRadii = new List<double>();
                var entryRefused = new List<double>();
                for (int b = 0; b < reelBodies.Count; b++)
                {
                    if (reelBodyEntry[b] != r)
                        continue;
                    if (ownedRadii.TryGetValue(b, out List<double>? bodyRadii))
                        entryRadii.AddRange(bodyRadii);
                    if (refusedRadii.TryGetValue(b, out List<double>? bodyRefused))
                        entryRefused.AddRange(bodyRefused);
                }

                // A MEASURED RADIUS OF ABOUT NOTHING IS NOT A RADIUS. A
                // frame lying on a reel's own axis measures zero, and a
                // drum whose wire runs at no radius turns infinitely fast
                // for any take-up at all. Where the measurement is
                // degenerate the mesh wins, exactly as it does when there
                // is nothing to measure. Found by the machine document's
                // own check on its first run.
                bool haveFrames =
                    entryRadii.Count > 0 && MedianOf(entryRadii) > MinimumSpoolRadius;
                if (haveFrames)
                {
                    double measured = MedianOf(entryRadii);
                    reelsPayload[r]["windingRadius"] = measured;
                    reelsPayload[r]["windingRadiusSource"] = "frames";
                    reelsPayload[r]["windingRadiusSamples"] = entryRadii.Count;
                    measuredRadii.Add(measured);

                    // WHAT THE DOCUMENT MUST ADMIT (spec 8.3 to 8.5). The
                    // median above is a number whatever the frames beneath
                    // it look like: a wire wound on a barrel and a wire
                    // sweeping across one both produce a median, and the
                    // document has so far published the two identically.
                    //
                    // THE FIGURE IS REJECTED-AGAINST-AGREEING, NOT THE
                    // SPREAD OF WHAT SURVIVED (spec 8.4). Ownership is
                    // radial AND axial, so the frames furthest off the
                    // barrel are thrown out BEFORE any statistic is taken of
                    // the rest, and a spread read off the survivors is
                    // therefore weakest exactly where the defect is worst:
                    // the harder the truncation, the tighter the remainder
                    // looks. That is the fault this figure exists to avoid,
                    // and the harness proves it on a drum whose survivors
                    // have no spread at all.
                    //
                    // ONE BAND, APPLIED TO EVERY FRAME NEAR THE DRUM,
                    // whichever side of the ownership window it fell: does
                    // this frame sit at the radius this reel PUBLISHES, to
                    // within WindingRadiusAgreementFraction of it? The
                    // frames that do are what the number can honestly claim
                    // to rest on; the frames that do not are what it cannot.
                    //
                    // WHAT THIS FIGURE DOES NOT DO, STATED EXACTLY, BECAUSE
                    // AN EARLIER DRAFT OF THIS COMMENT CLAIMED THE OPPOSITE
                    // (fix round 1, measured rather than argued). It is NOT
                    // true that every frame the ownership window rejects
                    // lands in the numerator, and it is NOT true that the
                    // figure rises as truncation gets harsher. Two things
                    // bound it. A refused frame that still sits within the
                    // band is counted as AGREEING, since the question asked
                    // is whether it sits at the published radius and not
                    // which side of a mesh boundary it fell; and the
                    // population reaches only to RouteOwnerAmbiguityMargin
                    // past the mesh radius, so frames beyond that are
                    // outside the figure altogether. Measured on a uniform
                    // sweep from 0.020 m to 0.060 m on one drum, varying
                    // only that drum's own flange:
                    //     flange 0.0600 -> 2.33   (named)
                    //     flange 0.0300 -> 0.93   (named)
                    //     flange 0.0205 -> 0.09   (SILENT)
                    // The figure FALLS as the mesh closes on the wire. A
                    // drum whose mesh stops at the inner end of its own
                    // sweep therefore passes while publishing a radius
                    // wrong by a factor of two for spin rate: that is not a
                    // blind spot off to one side, it is the direction this
                    // measure weakens in, and it is the direction to check
                    // by hand on any machine whose drums are modelled
                    // without cheeks. The narrow reading of 8.4 -- refusals
                    // counted against owned, with no band -- does rise on
                    // those same three drums (0, 0.45, 6.02) and is what a
                    // future round would reach for if that shape ever
                    // appears; it cannot be used here, because on his own
                    // machine it reads 0.16 to 0.28 on the seven swept
                    // spools and 0.40 on the one honest pulley, which is
                    // backwards.
                    double low = measured * (1.0 - WindingRadiusAgreementFraction);
                    double high = measured * (1.0 + WindingRadiusAgreementFraction);
                    int agreeing = 0;
                    int disagreeing = 0;
                    foreach (double radius in entryRadii)
                    {
                        if (radius >= low && radius <= high)
                            agreeing++;
                        else
                            disagreeing++;
                    }
                    foreach (double radius in entryRefused)
                    {
                        if (radius >= low && radius <= high)
                            agreeing++;
                        else
                            disagreeing++;
                    }

                    // The floor of one in the denominator is arithmetic
                    // hygiene and nothing else: a reel not one of whose
                    // nearby frames agrees with its own published radius
                    // reads its whole neighbourhood as the numerator and
                    // fails this gate by a wide margin, which is the
                    // answer that case deserves.
                    double scatter = disagreeing / (double)Math.Max(agreeing, 1);
                    reelsPayload[r]["windingRadiusScatter"] = scatter;

                    // TWO POPULATIONS, AND THE ROW SAYS WHICH IS WHICH (fix
                    // round 1). windingRadiusSamples counts the frames the
                    // MEDIAN rests on, which is the frames this reel owns.
                    // windingRadiusNearby counts the frames the SCATTER
                    // rests on, which is those plus the ones ownership
                    // refused within reach of this drum. They differ by
                    // construction and a reader who assumes agreeing plus
                    // disagreeing equals samples gets a different number
                    // with nothing to say so, which in a task about the
                    // document admitting what it measured is the exact
                    // fault being fixed.
                    reelsPayload[r]["windingRadiusNearby"] = agreeing + disagreeing;
                    reelsPayload[r]["windingRadiusAgreeing"] = agreeing;
                    reelsPayload[r]["windingRadiusDisagreeing"] = disagreeing;
                    if (scatter > WindingRadiusScatterLimit)
                    {
                        // NAMED AND MARKED, NEVER REPLACED AND NEVER
                        // BLESSED (spec 8.5). The number stays exactly as
                        // measured: substituting a fallback here would put
                        // an invented radius in a document that reads as a
                        // measurement, and no reader could tell. There is
                        // deliberately no matching "fit" or "confidence"
                        // key on the reels that pass, either -- a wrong
                        // number carrying a certificate of correctness is
                        // trusted where a bare wrong number is questioned,
                        // so what the passing reels get is silence.
                        reelsPayload[r]["windingRadiusUnfitToAnimate"] = true;
                        unfit.Add((r, scatter, agreeing, disagreeing));
                    }
                }
                else
                {
                    reelsPayload[r]["windingRadius"] = r < reels.Count
                        ? ReelRadialExtent(reels[r].Mesh, reels[r].Bodies[0].Axis)
                        : MinimumSpoolRadius;
                    reelsPayload[r]["windingRadiusSource"] = "mesh";
                    reelsPayload[r]["windingRadiusSamples"] = 0;

                    // A REEL WITH NOTHING TO MEASURE HAS NOTHING TO ADMIT.
                    // Its radius came off its own mesh, which
                    // windingRadiusSource already says, and a scatter of
                    // zero here would read as "measured, and every frame
                    // agreed" -- the strongest claim in the document, made
                    // by the weakest number in it. Null is the honest
                    // answer and it is stated rather than left out, so a
                    // reader walking the key finds it on every reel. The two
                    // counts are zero for the same reason: they count frames
                    // FOR AND AGAINST a measured radius, and there is no
                    // measured radius here to be for or against. Filling
                    // them with the frames that merely came near would give
                    // one key two meanings depending on another key's value,
                    // which is how a reader gets it wrong.
                    reelsPayload[r]["windingRadiusScatter"] = null;
                    reelsPayload[r]["windingRadiusNearby"] = 0;
                    reelsPayload[r]["windingRadiusAgreeing"] = 0;
                    reelsPayload[r]["windingRadiusDisagreeing"] = 0;
                    fellBack.Add(r);
                }
            }
            if (unfit.Count > 0)
            {
                warnings.Add(
                    "mechanism: reel entry(ies) " +
                    string.Join(
                        ", ",
                        unfit.Select(u =>
                            $"{u.Reel} (scatter " +
                            u.Scatter.ToString("0.00", CultureInfo.InvariantCulture) +
                            $": {u.Disagreeing} frame(s) near it disagree with " +
                            $"the radius it publishes, {u.Agreeing} agree)")) +
                    " -- their windingRadius is UNFIT TO ANIMATE. It is the " +
                    "median of frames that are not on one cylinder, which is " +
                    "a number rather than a radius, and the studio spins a " +
                    "drum at a rate computed from it: a wrong radius is a " +
                    "wrong spin rate on geometry that still looks right. " +
                    "The value is left exactly as measured and marked " +
                    "windingRadiusUnfitToAnimate rather than replaced by a " +
                    "guess, and mechanism.spoolRadius still counts it, so " +
                    "read that one with the same suspicion. A frame agrees " +
                    "when it sits within " +
                    (WindingRadiusAgreementFraction * 100.0).ToString("0.#", CultureInfo.InvariantCulture) +
                    " per cent of the published radius, which is the same " +
                    "per cent as the error it would put in that drum's spin " +
                    "rate. LIKELY CAUSE, to confirm on your own canvas: an " +
                    "offset applied along a direction that ROTATES WITH THE " +
                    "HELIX rather than radially, which moves the wire inward " +
                    "on one side of every turn and outward on the other. " +
                    "That is a fix in the offset step, not here.");
            }
            if (fellBack.Count > 0)
            {
                notes.Add(
                    "mechanism: reel entry(ies) " + string.Join(", ", fellBack) +
                    " own no routing frame on any body, so their " +
                    "windingRadius is the " +
                    "furthest their OWN MESH reaches from their own axis " +
                    "rather than a measurement of where the wire runs. " +
                    "windingRadiusSource says which every reel got, " +
                    "\"frames\" or \"mesh\", and windingRadiusSamples how " +
                    "many frames the measured ones rest on. A reel owning " +
                    "no frame is worth a look: either no wire passes it, or " +
                    "its neighbours are close enough to have claimed the " +
                    "frames that are really its own.");
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
                $"{measuredRadii.Count} reel entry(ies) that carry wire, " +
                "not guessed from a bounding box; each entry also carries " +
                "its own windingRadius, which is the one to prefer per reel " +
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

            // A TALLY OF "body N" AND NOTHING ELSE IS NOT A MEASUREMENT,
            // AND MUST NOT READ LIKE ONE. With no reel wired to this build
            // there is no neighbourhood to classify against, so
            // ClassifyRouteFrameOwner returns the body for every frame
            // before it looks at any geometry: the answer is universal by
            // construction, and a note tallying it says "measured" where
            // nothing was measured.
            //
            // THIS IS NOW THE ORDINARY SHAPE OF EVERY STUDY BUILD, and that
            // is the point of naming it. The reels moved to the Machine
            // component in Task 3, so the collector's own Reel (RE) and
            // Reel Axis (AX) are refusing stubs and a study build cannot
            // classify ownership at all any more. The studio therefore
            // holds every wire fixed and no wrap spins on any drum. It is
            // named as a WARNING because the consequence is a wrong
            // animation with correct geometry, which is this strand's own
            // named failure class, and it goes when ownership is taken from
            // the cited machine instead (its own round, not this one's).
            if (reelBodies.Count == 0)
            {
                warnings.Add(
                    "mechanism: NO REEL was wired to this build, so all " +
                    $"{ownerCounts.GetValueOrDefault(RouteOwnerBody)} " +
                    "routing frame(s) are held by the BODY by construction " +
                    "rather than by measurement: nothing here rides a drum, " +
                    "so nothing spins the wire in the animation while the " +
                    "geometry, the wire paths and the timing all stay " +
                    "correct. A STUDY build cannot classify ownership at " +
                    "all since the reels moved to the Machine component; " +
                    "the studio must take a wire's drum from the machine " +
                    "this study cites.");
            }
            else
            {
                notes.Add($"mechanism: routing frame ownership, the ONE authored mechanism -- {tally}.");
            }
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

        var anchorsOut = new List<Dictionary<string, object?>>();
        if (result is not null)
        {
            foreach ((int side, IReadOnlyList<int> netVertices, MechanismFrame frame) in
                DeriveAnchorFrames(result, notes))
            {
                anchorsOut.Add(new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    // ONE PER SIDE, so it pairs with every instance carrying
                    // this side rather than with one of them.
                    ["side"] = side,
                    ["net_vertices"] = netVertices,
                    ["frame"] = FramePayload(frame),
                    ["placement"] = "instance",
                    ["ref"] = asset.Anchor is not null ? "mechanism.anchor" : null,
                    [PermanenceField] = Permanent,
                });
            }
        }

        // THE CITATION, SAID ONCE IN THE CHIN (ruling 1.2), WHEN THERE IS
        // ONE.
        //
        // AND NOTHING AT ALL IS SAID WHEN THERE IS NOT, because this build
        // is SHARED: BuildMachine drives it with no citation BY DESIGN, a
        // machine citing nothing being the whole point of a machine, and it
        // pools its warnings into the Machine component's own chin. A
        // message here about wiring Machine (MA) would therefore paint that
        // component orange on every CORRECT machine build, telling him to
        // wire a port it does not have, about a study he is not building --
        // a warning firing on correct input, which this project holds
        // exactly as serious as one that misses a fault. The message about
        // an uncited STUDY belongs where the port exists, in
        // MechanismCollectorComponent.SolveInstance, and it is raised there
        // instead. The payload's own shape carries the fact regardless (no
        // machine key, no reeve default), so MechanismDocument.Json still
        // refuses by name whatever this build says or does not say.
        if (machine is not null)
        {
            notes.Add(
                $"mechanism: this study cites machine \"{machine.Name}\" " +
                $"(id {machine.Id}), which routes {machine.WireCount} " +
                "wire(s) and states a reeve default of " +
                machine.ReeveDefault.ToString("0.####", CultureInfo.InvariantCulture) +
                ". The machine's own bodies stay in its own document and " +
                "none of them travels here; every wire's resolved factor " +
                "comes from that default unless Reeve Per Wire (RW) " +
                "overrides that wire.");
        }

        var payload = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["mechanism"] = mechanismOut,
            // THE CITED MACHINE, AND THE ONE STATEMENT OF ITS REEVE DEFAULT
            // IN THIS PAYLOAD (spec 5.3, 6.3). The key is ABSENT, not null,
            // when nothing is cited: a key standing for "there is no such
            // thing" says nothing its absence does not, and it forces every
            // reader downstream to tolerate a null by name, which is a
            // tolerance one careless write turns into a hole. The same
            // reasoning already governs an unwired tie and anchor above.
            //
            // reeveDefault LIVES HERE AND NOWHERE ELSE, and in particular
            // NOT beside reeve.perWire below. It is the MACHINE's number,
            // not the study's, and two keys carrying it would be two
            // plausible numbers with neither null -- the exact shape that
            // has a reader apply 1.0 where he authored 4.0 while the
            // geometry, the wire paths and the timing all stay correct.
            //
            // The key is REMOVED rather than left null just below, since a
            // C# collection initialiser cannot omit one.
            ["machine"] = MachineCitationPayload(machine),
            ["reeve"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["how"] = "THE DEFAULT IS THE CITED MACHINE'S OWN and is " +
                    "stated once, at machine.reeveDefault; this block " +
                    "carries only what the STUDY authors over it. A study " +
                    "that cites no machine states no default at all and is " +
                    "refused when the document is written, rather than " +
                    "given a number nobody authored.",
                // THE PER-WIRE OVERRIDE (spec 6.1-6.2, Task 5): Reeve Per
                // Wire (RW)'s own tree, resolved to {wire: value} and
                // carried through UNRESOLVED -- MechanismDocument.Json is
                // where each wire's final reeveFactor and reeveFactorSource
                // are decided, since that is the one place a wire's own id
                // exists to say which "wire" this key means. Always
                // present, an empty object when nothing was authored,
                // rather than an absent key a reader has to branch on.
                ["perWire"] = ReevePerWirePayload(reevePerWire),
            },
            ["instances"] = instancesOut,
            ["wires"] = wiresOut,
            // THE ANCHORS, STAMPED (2026-09-09). This array was empty by
            // design while the anchor arrived fused into the Tension Tie
            // and there was no separate port. There is one now, because his
            // own script cannot keep anchors right across changing forms,
            // and the net already knows exactly where every one of them
            // goes. Each entry carries the net vertex it holds and a frame
            // built by the same rule the machines are placed by; the body
            // itself lives ONCE under mechanism.anchor and is referenced,
            // never copied per anchor.
            ["anchors"] = anchorsOut,
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
        // NO CITATION MEANS NO KEY, not a key carrying null: the reader
        // refuses either shape alike, but a key standing for "this study
        // cites nothing" would have to be tolerated by name everywhere it
        // is walked, and that tolerance is what one careless write turns
        // into a hole (Task 1's own finding, on the unwired tie).
        if (machine is null)
            payload.Remove("machine");
        return JsonSerializer.Serialize(payload, ContractJson.Options);
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
    /// THE CITED MACHINE, AS THE PAYLOAD CARRIES IT: the four facts a study
    /// cannot render without, and the cable span when the machine states
    /// one. Null for a study citing nothing at all, which the caller then
    /// REMOVES rather than writing as a null key.
    ///
    /// cableSpan IS OMITTED, NOT WRITTEN NULL, when the machine states
    /// none, for the same reason the whole block is: a key standing for
    /// "there is no such thing" says nothing its absence does not, and it
    /// forces every reader downstream to tolerate a null by name. It sits
    /// LAST so the four facts that were here before keep their written
    /// order, which the change-key requirement depends on.
    /// </summary>
    private static Dictionary<string, object?>? MachineCitationPayload(
        MechanismMachineCitation? machine)
    {
        if (machine is null)
            return null;
        var block = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["schema"] = MachineSchema,
            ["id"] = machine.Id,
            ["name"] = machine.Name,
            ["wireCount"] = machine.WireCount,
            ["reeveDefault"] = machine.ReeveDefault,
        };
        if (machine.CableSpan is double cableSpan)
            block["cableSpan"] = cableSpan;
        return block;
    }

    /// <summary>
    /// Reeve Per Wire (RW), keyed by wire index as JSON demands (object
    /// keys are strings; a wire number is not one), and always present as
    /// an object -- empty when nothing was authored, never an absent key a
    /// reader has to branch on separately from "authored but empty".
    /// </summary>
    private static Dictionary<string, object?> ReevePerWirePayload(
        IReadOnlyDictionary<int, double>? reevePerWire)
    {
        var payload = new Dictionary<string, object?>(StringComparer.Ordinal);
        if (reevePerWire is null)
            return payload;
        foreach (KeyValuePair<int, double> entry in reevePerWire)
            payload[entry.Key.ToString(CultureInfo.InvariantCulture)] = entry.Value;
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
    ///
    /// THE AXIAL REFUSAL NAMES ITS REEL, not merely that one happened
    /// (Task 8). A frame inside a drum's radius but past its end faces is
    /// a frame that drum's barrel cannot have carried, and the winding
    /// radius scatter counts it against that drum. A bare flag says a
    /// refusal occurred somewhere and cannot be counted anywhere:
    /// <c>AxiallyExcludedReel &gt;= 0</c> is exactly the old flag, so
    /// nothing that read it lost anything.
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
        int AxiallyExcludedReel,
        double AxiallyExcludedDistance);

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

    /// <summary>
    /// Every PHYSICAL reel's own neighbourhood, in body order: entry 0's
    /// bodies in order, then entry 1's, which is the order every
    /// <c>ownerReel</c> index counts in.
    ///
    /// THE SIZE IS MEASURED ONCE PER ENTRY, NOT ONCE PER BODY, and that is
    /// exact rather than a saving. An entry's mesh is authored at its body 0
    /// and every other body's transform is a RIGID map carrying that body 0
    /// frame onto its own axis, so the mesh's furthest reach from the axis
    /// and its two end faces along the axis are the same numbers for every
    /// body of the entry. Measuring the untransformed mesh against a LATER
    /// body's axis would be the bug here: for a seven-body spool entry that
    /// reads one drum's vertices against another drum's axis, half a machine
    /// away, and inflates the ownership window until it swallows its
    /// neighbours' routing frames.
    /// </summary>
    internal static ReelNeighbourhood[] BuildReelNeighbourhoods(
        IReadOnlyList<MechanismReelGroup> reels)
    {
        var built = new List<ReelNeighbourhood>();
        foreach (MechanismReelGroup entry in reels)
        {
            if (entry.Bodies.Count == 0)
                continue;
            MechanismFrame authored = entry.Bodies[0].Axis;
            double radius = ReelRadialExtent(entry.Mesh, authored);
            (double axialMin, double axialMax) = ReelAxialExtent(entry.Mesh, authored);
            foreach (MechanismReelBody body in entry.Bodies)
            {
                built.Add(new ReelNeighbourhood(
                    body.Axis.Origin,
                    NormalizeOrZ(CrossProduct(body.Axis.XAxis, body.Axis.YAxis)),
                    radius,
                    axialMin,
                    axialMax));
            }
        }
        return built.ToArray();
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
                NoOwnerReel, double.PositiveInfinity, NoOwnerReel, 0.0);
        }

        double bestRatio = double.PositiveInfinity;
        int bestIndex = NoOwnerReel;
        double bestDistance = 0.0;
        double bestRadius = 0.0;
        double secondRatio = double.PositiveInfinity;
        int secondIndex = NoOwnerReel;
        int axiallyExcludedIndex = NoOwnerReel;
        double axiallyExcludedRatio = double.PositiveInfinity;
        double axiallyExcludedDistance = 0.0;

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
                // THE NEAREST OF THE REELS THAT REFUSED IT AXIALLY, kept by
                // name and by distance so a caller can count the refusal
                // against the drum that made it. Nearest in the same
                // relative terms ownership uses, so a small drum and a
                // large one are compared on their own sizes.
                if (ratio <= 1.0 && ratio < axiallyExcludedRatio)
                {
                    axiallyExcludedRatio = ratio;
                    axiallyExcludedIndex = i;
                    axiallyExcludedDistance = distance;
                }
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
            axiallyExcludedIndex,
            axiallyExcludedDistance);
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

    /// <summary>
    /// ONE ANCHOR PER SIDE, spanning the whole springing. His corrected
    /// model, 2026-09-09 morning, verbatim: "It's one anchor per side, and
    /// the tension tie is fixed to the anchor but it's based off the
    /// perimeter lines and rides under the columns as a rectangular mass.
    /// The anchor itself is just the shape of the skin edge on the first
    /// row, so they sit cleanly on it. Then it becomes a box."
    ///
    /// THIS REPLACES ONE PER MACHINE, which is what he ruled the night
    /// before and what was built then. A side's anchor is one continuous
    /// mass under the whole row rather than three separate blocks in front
    /// of three machines, so its origin is the ROW's own centre and it
    /// names every anchor on that row.
    ///
    /// The frame is the same rule everything else here uses: X along the
    /// row, Z the world's own up taken across X, Y = Z cross X with X's
    /// sign settled so Y points AWAY from the net. So the anchor, the
    /// machines standing on it and the tie welded into it cannot disagree
    /// about which way is out.
    ///
    /// STILL OPEN, and deliberately not built until he authors it: he
    /// intends the tension tie WELDED INTO this body ("I can provide always
    /// 1 anchor shape, the full tension tie in welded to the anchor"). When
    /// that arrives, mechanism.tensionTie must stop being emitted
    /// separately or a reader draws the tie twice, once inside the anchor
    /// and once on its own. He has not authored it yet and said the two
    /// hours are hours he does not have, so the port keeps its own life
    /// until then.
    /// </summary>
    internal static List<(int Side, IReadOnlyList<int> NetVertices, MechanismFrame Frame)>
        DeriveAnchorFrames(ResultDto result, List<string> notes)
    {
        var placed = new List<(int, IReadOnlyList<int>, MechanismFrame)>();
        EquilibriumResultDto? eq = result.Equilibrium;
        if (eq is null || eq.Vertices.Count == 0)
            return placed;

        var netPoints = new List<double[]>(eq.Vertices.Count);
        foreach (Point3Dto v in eq.Vertices)
            netPoints.Add(new[] { v.X, v.Y, v.Z });
        double[] netCentre = CentroidOf(netPoints);

        List<List<int>> rows = MechanismGeometry.AnchorRowIndices(result);
        if (!rows.Any(row => row.Count >= PlacementGroupSize))
        {
            var anchorIds = new List<int>();
            foreach (int id in eq.ResolvedSupportNodeIds)
            {
                if (id >= 0 && id < netPoints.Count)
                    anchorIds.Add(id);
            }
            rows = ClusterAnchorsBySpacing(anchorIds, netPoints);
        }

        for (int side = 0; side < rows.Count; side++)
        {
            List<int> row = rows[side];
            if (row.Count < PlacementGroupSize)
                continue;
            var rowPoints = row.Select(id => netPoints[id]).ToList();

            double[] rowX = WidestPairDirection(rowPoints);

            double[] rowZ = AcrossAxis(WorldUp, rowX);
            double[] rowY = CrossProduct(rowZ, rowX);
            double[] rowCentre = CentroidOf(rowPoints);
            if (Dot3(rowY, Difference3(netCentre, rowCentre)) > 0.0)
            {
                rowX = Negate3(rowX);
                rowY = CrossProduct(rowZ, rowX);
            }

            var ordered = OrderAlongAxis(rowPoints, rowX)
                .Select(i => row[i])
                .ToList();
            placed.Add((side, ordered, new MechanismFrame(rowCentre, rowX, rowY, rowZ)));
        }

        if (placed.Count > 0)
        {
            notes.Add(
                $"anchors: {placed.Count} anchor(s) derived, ONE PER SIDE " +
                "and not one per machine (his corrected model: the anchor " +
                "is one continuous mass under the whole springing, the " +
                "shape of the skin edge on the first row, with the tension " +
                "tie riding under the columns and welded into it). Each " +
                "sits at the CENTRE of its own row, names every anchor on " +
                "that row in order along it, and carries the same frame the " +
                "machines standing on it are placed by -- X along the row, " +
                "Z the world's up across it, Y away from the net.");
        }
        return placed;
    }

    /// <summary>
    /// ANCHOR ROWS FOUND BY SPACING, for a net whose springings are not
    /// meshed along themselves and so give the edge walk nothing to follow.
    ///
    /// Each anchor is joined to every other anchor within a multiple of the
    /// set's own MEDIAN NEAREST-NEIGHBOUR distance, and the connected
    /// groups of that are the rows. Using the set's own spacing rather than
    /// any fixed distance is what lets it work at any scale: on his study
    /// the anchors sit 0.15 m apart along a springing while the two
    /// springings stand 16 m apart, so the rows separate by a factor of a
    /// hundred.
    /// </summary>
    internal static List<List<int>> ClusterAnchorsBySpacing(
        IReadOnlyList<int> anchors, IReadOnlyList<double[]> points)
    {
        var rows = new List<List<int>>();
        if (anchors.Count == 0)
            return rows;
        if (anchors.Count == 1)
        {
            rows.Add(new List<int> { anchors[0] });
            return rows;
        }

        var nearest = new List<double>(anchors.Count);
        for (int i = 0; i < anchors.Count; i++)
        {
            double best = double.PositiveInfinity;
            for (int j = 0; j < anchors.Count; j++)
            {
                if (i == j)
                    continue;
                double gap = Distance(points[anchors[i]], points[anchors[j]]);
                if (gap < best)
                    best = gap;
            }
            if (!double.IsPositiveInfinity(best))
                nearest.Add(best);
        }
        if (nearest.Count == 0)
            return rows;
        double reach = MedianOf(nearest) * AnchorRowReachFactor;

        var unvisited = new HashSet<int>(Enumerable.Range(0, anchors.Count));
        while (unvisited.Count > 0)
        {
            int seed = unvisited.First();
            unvisited.Remove(seed);
            var queue = new Queue<int>();
            queue.Enqueue(seed);
            var row = new List<int>();
            while (queue.Count > 0)
            {
                int at = queue.Dequeue();
                row.Add(anchors[at]);
                var reached = unvisited
                    .Where(other => Distance(points[anchors[at]], points[anchors[other]]) <= reach)
                    .ToList();
                foreach (int other in reached)
                {
                    unvisited.Remove(other);
                    queue.Enqueue(other);
                }
            }
            rows.Add(row);
        }
        return rows;
    }

    /// <summary>The world's own up, the one direction a machine standing on a foundation does not have to be told.</summary>
    internal static readonly double[] WorldUp = { 0.0, 0.0, 1.0 };

    /// <summary>
    /// SEVERAL PARTS AS ONE MESH: vertices concatenated, face indices
    /// shifted by the running vertex count. No welding and no repair -- the
    /// parts keep every vertex and face they arrived with, and only their
    /// numbering changes.
    ///
    /// WHY THIS EXISTS (2026-09-09, and it cost him a night): Frame 1 was an
    /// ITEM port meaning "one joined mesh", and he wired SEVENTEEN meshes to
    /// it. Grasshopper's answer to a list on an item port is to solve the
    /// whole component once per item, so the mechanism was built seventeen
    /// times and the last build won -- a 55 mm bracket in place of his
    /// frame, exported without one word of complaint, and seventeen payloads
    /// out of ME which then made Export iterate and warn about its Result.
    /// A port that silently produces a plausible wrong answer is worse than
    /// one that refuses, so these ports take a list and join it.
    /// </summary>
    internal static MechanismMesh JoinMeshes(IReadOnlyList<MechanismMesh> parts)
    {
        var vertices = new List<double[]>();
        var faces = new List<int[]>();
        foreach (MechanismMesh part in parts)
        {
            int offset = vertices.Count;
            vertices.AddRange(part.Vertices);
            foreach (int[] face in part.Faces)
            {
                var shifted = new int[face.Length];
                for (int i = 0; i < face.Length; i++)
                    shifted[i] = face[i] + offset;
                faces.Add(shifted);
            }
        }
        return new MechanismMesh(vertices, faces);
    }

    /// <summary>The machine document's own schema, the fifth kind and the first that is NOT a study.</summary>
    public const string MachineSchema = "bench.machine/1";

    /// <summary>
    /// THE CITATION, READ OFF THE MACHINE DOCUMENT wired to the Mechanism
    /// component's own Machine (MA) port (spec 5.1, ruling 1.2). Returns
    /// the four facts a study needs from the machine it cites, or NULL when
    /// there is no machine to cite.
    ///
    /// NOTHING WIRED IS NOT A FAULT HERE and draws no warning of its own:
    /// the ONE message about an uncited study belongs to the build that
    /// noticed (<see cref="BuildWithResult"/>), so that a study exported
    /// without a machine is named once and not twice. Everything else -- a
    /// document that will not parse, one of another schema, one with no id,
    /// no wireCount or no usable reeve default -- is REFUSED BY NAME here
    /// and returns null, because a citation is all or nothing: the id
    /// without the reeve default would give a study that renders the right
    /// machine at the wrong spin rate, and the reeve default without the id
    /// a study that renders nothing at all.
    ///
    /// THE SCHEMA IS CHECKED, and this is not ceremony. Spec 10.3 records a
    /// 36 MiB <c>bench.mechanism/1</c> STUDY document sitting in the machine
    /// library folder where the studio scans for machines; wiring that file
    /// here would otherwise read "id" off a document that has none and cite
    /// a machine that does not exist.
    ///
    /// WHAT IT CANNOT SEE: whether the id it read names a machine the studio
    /// can actually resolve. There is no upload route in this repo (spec
    /// 11.1) and no library index to look the id up in, so a citation is
    /// proved well formed here and never proved resolvable.
    /// </summary>
    public static MechanismMachineCitation? ReadMachineCitation(
        string? machineDocumentJson, List<string> warnings)
    {
        ArgumentNullException.ThrowIfNull(warnings);
        string text = (machineDocumentJson ?? string.Empty).Trim();
        if (text.Length == 0)
            return null;

        JsonElement root;
        JsonDocument parsed;
        try
        {
            parsed = JsonDocument.Parse(text);
        }
        catch (JsonException parseError)
        {
            warnings.Add(
                "Machine (MA) did not parse as a machine document (" +
                parseError.Message + "), so this study cites no machine. " +
                "Wire it from the Machine component's own Machine (MC) " +
                "output, which writes the " + MachineSchema + " document " +
                "a study cites.");
            return null;
        }

        using (parsed)
        {
            root = parsed.RootElement;
            if (root.ValueKind != JsonValueKind.Object)
            {
                warnings.Add(
                    "Machine (MA) is JSON but not a machine document (its " +
                    $"root is {root.ValueKind}, not an object), so this " +
                    "study cites no machine.");
                return null;
            }

            string schema =
                root.TryGetProperty("schema", out JsonElement schemaElement) &&
                schemaElement.ValueKind == JsonValueKind.String
                    ? schemaElement.GetString() ?? string.Empty
                    : string.Empty;
            if (!string.Equals(schema, MachineSchema, StringComparison.Ordinal))
            {
                warnings.Add(
                    "Machine (MA) carries a \"" +
                    (schema.Length == 0 ? "<no schema>" : schema) +
                    $"\" document, not a {MachineSchema}, so this study " +
                    "cites no machine." +
                    (string.Equals(schema, MechanismDocument.Schema, StringComparison.Ordinal)
                        ? " That is a STUDY document, and there is one of " +
                          "those sitting in the machine library folder " +
                          "already (Seven spool winch-mechanism.json, 36 " +
                          "MiB, whose own study field reads \"2 Sided " +
                          "Vault\"): it is not a machine and citing it " +
                          "would name a machine that does not exist."
                        : string.Empty));
                return null;
            }

            string id =
                root.TryGetProperty("id", out JsonElement idElement) &&
                idElement.ValueKind == JsonValueKind.String
                    ? (idElement.GetString() ?? string.Empty).Trim()
                    : string.Empty;
            if (id.Length == 0)
            {
                warnings.Add(
                    $"Machine (MA) is a {MachineSchema} document that " +
                    "states no id, so this study cites no machine. The id " +
                    "is the MINTED CODE a study cites and the one thing " +
                    "about a machine that never changes; a study citing " +
                    "nothing renders nothing, silently.");
                return null;
            }

            string label =
                root.TryGetProperty("name", out JsonElement nameElement) &&
                nameElement.ValueKind == JsonValueKind.String
                    ? (nameElement.GetString() ?? string.Empty).Trim()
                    : string.Empty;
            if (label.Length == 0)
                label = id;

            if (!root.TryGetProperty("wireCount", out JsonElement wireCountElement) ||
                wireCountElement.ValueKind != JsonValueKind.Number ||
                !wireCountElement.TryGetInt32(out int wireCount) ||
                wireCount < 0)
            {
                warnings.Add(
                    $"Machine \"{id}\": its document states no usable " +
                    "wireCount, so this study cites no machine. The count " +
                    "is what the study's own placed wires are checked " +
                    "against, one for one; without it a study placing " +
                    "seven wires against a twelve-wire machine animates " +
                    "seven cables, leaves five absent, and says nothing.");
                return null;
            }

            if (!root.TryGetProperty("reeve", out JsonElement reeveElement) ||
                reeveElement.ValueKind != JsonValueKind.Object ||
                !reeveElement.TryGetProperty("default", out JsonElement reeveDefaultElement) ||
                reeveDefaultElement.ValueKind != JsonValueKind.Number ||
                !double.IsFinite(reeveDefaultElement.GetDouble()) ||
                reeveDefaultElement.GetDouble() <= 0.0)
            {
                warnings.Add(
                    $"Machine \"{id}\": its document states no reeve " +
                    "default that could be a mechanical advantage, so this " +
                    "study cites no machine. It is the advantage of one " +
                    "wire's reeving through its block, so it is finite and " +
                    "greater than zero, and it is REFUSED rather than " +
                    "replaced by a plausible number: a wrong factor makes " +
                    "every reel spin at the wrong RATE while the geometry, " +
                    "the wire paths and the timing all stay correct, so " +
                    "nothing looks broken.");
                return null;
            }

            // THE CABLE SPAN, READ WHERE IT IS FOUND AND NEVER DEMANDED
            // (spec 7.4). It is the witness the study document checks its
            // anchor rows against, and it is the only number in this
            // citation that the study's own placement derivation cannot
            // also have produced. A machine routing fewer than two wires
            // writes no footprint at all, and one whose span reads zero,
            // negative or not finite describes no cable line, so both are
            // read as "no witness" rather than refused: the citation's four
            // required facts are what a study cannot render without, and a
            // machine that cannot be layout-checked still animates
            // correctly.
            double? cableSpan = null;
            if (root.TryGetProperty("footprint", out JsonElement footprintElement) &&
                footprintElement.ValueKind == JsonValueKind.Object &&
                footprintElement.TryGetProperty("cableSpan", out JsonElement spanElement) &&
                spanElement.ValueKind == JsonValueKind.Number &&
                double.IsFinite(spanElement.GetDouble()) &&
                spanElement.GetDouble() > 0.0)
            {
                cableSpan = spanElement.GetDouble();
            }

            return new MechanismMachineCitation(
                id, label, wireCount, reeveDefaultElement.GetDouble(), cableSpan);
        }
    }


    /// <summary>
    /// THE MACHINE ALONE, with no study anywhere in it (his ruling,
    /// 2026-09-09: "one component purely deals with the mechanism and its
    /// own export write, so it doesnt collide with anything").
    ///
    /// A machine is not a property of a vault. It is a thing he owns, that
    /// outlives any study, and that he may have several of at different
    /// sizes. The mechanism document confused the two: bodies and routing
    /// beside net vertices and world placements, ten megabytes of it,
    /// rewritten whole on every solve of every study.
    ///
    /// WHAT MAKES IT SELF-DESCRIBING, so a five-wire machine and a
    /// twelve-wire machine both lay out with no code change anywhere:
    ///
    ///   id          the MINTED CODE a study cites, authored on the Machine
    ///               Id (ID) port and NEVER derived from the name.
    ///   name        the human label, renameable without orphaning a study.
    ///   wireCount   cables one machine takes. Every layout decision turns
    ///               on this one number.
    ///   reeve       the machine's default reeve factor, stated ONCE in the
    ///               whole document (spec 6.3).
    ///   indexing    which index space each "reel" number counts in, since
    ///               an entry index and a body index both read as a reel.
    ///   bank        which reel ENTRIES are driven and which are idlers,
    ///               derived from the bodies that TERMINATE wire routes
    ///               (spec 4.6), and cross-checked against wireCount.
    ///   footprint   its span along the cable line and how far it reaches
    ///               BEHIND that line, so a layout can tell whether a
    ///               bigger machine still fits a row and space several
    ///               without collision.
    ///   datum       the wire first-frames. The machine's real datum, and
    ///               NOT the body origin, which means nothing.
    ///
    /// THE FOOTPRINT IS THE MACHINE'S OWN, AND ITS PUBLISHED NUMBERS MOVED
    /// (spec 3.4). It used to sweep the tension tie's and the anchor's
    /// vertices as well, so footprint.min, footprint.max, footprint.setback
    /// and footprint.cableSpan are MEASURABLY DIFFERENT numbers for any
    /// machine that had either wired: the tie is a foundation body reaching
    /// well behind and below the machine, and it inflated exactly the
    /// numbers a layout spaces units by. The change is correct, since a
    /// footprint describes the machine and the tie and the anchor are the
    /// works that REMAIN when the machine is taken away, and the harness
    /// pins the new values outright rather than inheriting the old ones.
    ///
    /// WHAT IS NOT PROVED HERE, said rather than left to be found: no
    /// fixture and no machine of his has yet authored a multi-body entry
    /// AND wired a tie to this build at once, so the interaction of the two
    /// is right by inspection. What the harness does prove is that the same
    /// machine built with and without a tie and an anchor gives the
    /// IDENTICAL footprint, which is the property the removal exists for.
    /// </summary>
    public static string BuildMachine(
        MechanismAssetInput asset,
        IReadOnlyList<MechanismRoutingWire> routing,
        string machineId,
        string name,
        double reeveDefault,
        string? routingFrameMeaning,
        List<string> warnings,
        List<string> notes)
    {
        ArgumentNullException.ThrowIfNull(asset);
        ArgumentNullException.ThrowIfNull(routing);

        // THE ID IS THE IDENTITY AND IT IS REFUSED BY NAME WHEN EMPTY. A
        // study cites a machine by this code and nothing else; a study
        // citing a machine that is not there renders NOTHING, silently, so
        // a machine with no id is worse than no machine at all. It is not
        // derived from the name and it is not sanitised into one: the old
        // id path rewrote any name that was not a single path segment to
        // "machine", so two differently named machines minted the same
        // identity and the second silently became the first.
        string id = (machineId ?? string.Empty).Trim();
        if (id.Length == 0)
        {
            warnings.Add(
                "Machine Id (ID) is empty, so no machine document was " +
                "built. The id is the MINTED CODE a study cites, and it is " +
                "the one thing about this machine that must never change: " +
                "the Name is a label you may rename freely, and deriving " +
                "an id from it would let a rename orphan every study that " +
                "cites this machine. Author an id such as MCH-0007.");
            return string.Empty;
        }

        // THE LABEL. Empty is said rather than left blank in a chooser, and
        // the id stands in for it, because a machine that lists as nothing
        // is one he cannot pick out of a library.
        string label = (name ?? string.Empty).Trim();
        if (label.Length == 0)
        {
            label = id;
            warnings.Add(
                $"Machine \"{id}\": Name (N) is empty, so the id stands in " +
                "as this machine's label. The two are separate on purpose: " +
                "the id is cited and never changes, the name is what you " +
                "read in a list, so give it one you will recognise.");
        }

        // THE REEVE DEFAULT IS AUTHORED AND IS REFUSED WHEN IT CANNOT BE
        // ONE (spec 6.6). A wrong factor makes every reel spin at the wrong
        // RATE while the geometry, the wire paths and the timing all stay
        // correct, so nothing looks broken; a zero or a negative one is not
        // a wrong number but an impossible one, and it is refused rather
        // than quietly replaced by a plausible number he did not author.
        if (!double.IsFinite(reeveDefault) || reeveDefault <= 0.0)
        {
            warnings.Add(
                $"Machine \"{id}\": Reeve (RV) is {reeveDefault.ToString(CultureInfo.InvariantCulture)}, " +
                "which is not a mechanical advantage; no machine document " +
                "was built. It is the advantage of one wire's reeving " +
                "through its block, so it is finite and greater than zero " +
                $"({DefaultReeveFactor.ToString("0.####", CultureInfo.InvariantCulture)} " +
                "is this unit's own value).");
            return string.Empty;
        }

        // THE TIE AND THE ANCHOR NEVER REACH A MACHINE DOCUMENT (spec 3.3),
        // and they are refused BY NAME here rather than only at the Machine
        // component's own withdrawn ports, so that a future caller reaching
        // this build directly cannot put a permanent study work inside a
        // machine. They are dropped from the asset before anything is
        // built, which is what keeps them out of the document AND out of
        // the footprint at once.
        MechanismAssetInput machineOnly = asset;
        if (asset.TensionTie is not null || asset.Anchor is not null)
        {
            warnings.Add(
                $"Machine \"{id}\": a " +
                (asset.TensionTie is not null && asset.Anchor is not null
                    ? "Tension Tie and an Anchor were"
                    : asset.TensionTie is not null
                        ? "Tension Tie was"
                        : "Anchor was") +
                " handed to the machine build and left out of it, body and " +
                "footprint both. They are the PERMANENT WORKS of a study, " +
                "the things that remain when the machine is taken away, and " +
                "they belong to the Mechanism component's own Tension Tie " +
                "(TT) and Anchor (AN) inputs. Two authoring points for one " +
                "body would give two copies that drift the first time one " +
                "is edited.");
            machineOnly = asset with
            {
                TensionTie = null,
                TensionTieFromBrep = false,
                Anchor = null,
                AnchorFromBrep = false,
            };
        }

        // The bodies, the reels, the cable and the measured radii all come
        // from the SAME build the study document uses, so the two can never
        // disagree about the machine. It is handed no Result and no
        // placement, so it produces no instances and no wires.
        string? shape = BuildWithResult(
            machineOnly,
            routing,
            Array.Empty<MechanismPlacementBranch>(),
            warnings,
            notes,
            null,
            routingFrameMeaning);
        if (shape is null)
            return string.Empty;

        using JsonDocument built = JsonDocument.Parse(shape);
        JsonElement machineBlock = built.RootElement.GetProperty("mechanism");

        var wires = routing
            .Where(w => w.Route.Count > 0)
            .OrderBy(w => w.Wire)
            .ToList();

        // THE BANK IS RE-DERIVED FOR ENTRIES (spec 4.6): the bank is the
        // entry (or entries) whose BODIES TERMINATE WIRE ROUTES. A wire
        // ends on the drum that pays it out, so the drums a machine's own
        // routes end on ARE the driven ones, measured rather than inferred.
        //
        // WHAT THIS REPLACES, AND WHY IT HAD TO GO. The old rule was "the
        // largest group of reels sharing one axis direction AND one winding
        // radius", which identifies seven driven spools only while seven
        // separate spool MESHES are authored. Since reels became entries,
        // his own machine is FOUR entries and ten bodies, and that rule
        // reads one or two driven spools against seven wires and fires its
        // own count-disagreement warning on a CORRECTLY authored machine.
        // A warning that fires on correct input is a defect, exactly as
        // serious as one that misses a fault: it teaches him to ignore the
        // line that will one day be real.
        //
        // TWO INDEX SPACES, AND THE DOCUMENT SAYS WHICH IS WHICH. "spools"
        // and "idlers" are ENTRY indices, matching reels[].reel; while
        // "drivenBodies" counts PHYSICAL BODIES in the flattened order
        // routing frames' own ownerReel counts in. The header's "indexing"
        // block states that difference rather than leaving two numbers that
        // both read as a reel.
        var entryRadii = new List<double>();
        int entryCount = 0;
        if (machineBlock.TryGetProperty("reels", out JsonElement reelsBlock) &&
            reelsBlock.ValueKind == JsonValueKind.Array)
        {
            foreach (JsonElement reel in reelsBlock.EnumerateArray())
            {
                entryCount++;
                entryRadii.Add(
                    reel.TryGetProperty("windingRadius", out JsonElement r) &&
                    r.ValueKind == JsonValueKind.Number
                        ? r.GetDouble()
                        : 0.0);
            }
        }

        // BODY ORDER, MIRRORING BuildReelNeighbourhoods EXACTLY, including
        // its skip of a bodyless entry: an ownerReel index counts the
        // neighbourhoods it built, so a body-to-entry map that counted
        // differently would name the wrong entry as driven.
        var bodyEntry = new List<int>();
        var bodyAxis = new List<MechanismFrame>();
        for (int e = 0; e < machineOnly.Reels.Count; e++)
        {
            if (machineOnly.Reels[e].Bodies.Count == 0)
                continue;
            foreach (MechanismReelBody body in machineOnly.Reels[e].Bodies)
            {
                bodyEntry.Add(e);
                bodyAxis.Add(body.Axis);
            }
        }

        ReelNeighbourhood[] bankNeighbourhoods = BuildReelNeighbourhoods(machineOnly.Reels);
        var drivenBodies = new SortedSet<int>();
        var drivenEntries = new SortedSet<int>();
        foreach (MechanismRoutingWire wire in wires)
        {
            MechanismFrame last = wire.Route[wire.Route.Count - 1];
            RouteOwnerVerdict verdict = ClassifyRouteFrameOwner(last, bankNeighbourhoods);
            if (verdict.Owner != RouteOwnerReel ||
                verdict.OwnerReel < 0 ||
                verdict.OwnerReel >= bodyEntry.Count)
            {
                continue;
            }
            drivenBodies.Add(verdict.OwnerReel);
            drivenEntries.Add(bodyEntry[verdict.OwnerReel]);
        }

        var spools = drivenEntries.ToList();
        var idlers = Enumerable.Range(0, entryCount)
            .Where(i => !drivenEntries.Contains(i))
            .ToList();
        double bankRadius = spools.Count > 0
            ? MedianOf(spools
                .Where(i => i < entryRadii.Count)
                .Select(i => entryRadii[i])
                .ToList())
            : 0.0;
        double[] bankAxis = drivenBodies.Count > 0
            ? NormalizeOrZ(CrossProduct(
                bodyAxis[drivenBodies.Min].XAxis,
                bodyAxis[drivenBodies.Min].YAxis))
            : new[] { 0.0, 0.0, 1.0 };

        // THE COUNT CROSS-CHECK, NOW BODIES AGAINST WIRES. One spool drives
        // one cable, so the driven BODIES and the wires are the two numbers
        // that must agree; entries never were, and comparing entries is
        // what made this warning fire on his own four-entry machine.
        if (drivenBodies.Count > 0 && wires.Count > 0 && drivenBodies.Count != wires.Count)
        {
            warnings.Add(
                $"Machine \"{id}\": its bank reads {drivenBodies.Count} driven " +
                $"reel bod(y/ies) but it routes {wires.Count} wire(s). One " +
                "spool drives one cable, so a machine whose two counts " +
                "disagree will lay out on a row by one number and be built " +
                "to the other. Check which reels the wires actually END on: " +
                "a route stopping short of its drum, or two routes ending " +
                "on the same one, reads this way.");
        }
        else if (drivenBodies.Count == 0 && wires.Count > 0 && bankNeighbourhoods.Length > 0)
        {
            // SAID, NOT WARNED. He offsets his routing planes clear of the
            // drums so the drawn cable stops cutting them (which is what
            // Wire Start (WS) exists for), and an offset route legitimately
            // ends just OUTSIDE every reel. Warning here would fire on a
            // correctly authored machine; the note names the consequence
            // instead, which is that the bank is empty and a layout has
            // nothing to read.
            notes.Add(
                $"machine \"{id}\": no wire route ENDS on a reel, so the " +
                "bank names no driven reel at all. Every reel here is an " +
                "idler by that reading. If you have offset your routing " +
                "planes clear of the drums, that is why, and the bank is " +
                "the one number a layout cannot then take from this " +
                "machine.");
        }

        // THE FOOTPRINT, in the machine's OWN canonical frame: X along the
        // cable line, Z the world's up across it, Y toward the body. Only
        // then does "how far it reaches behind the cables" mean anything.
        var first = wires.Select(w => w.Route[0].Origin).ToList();
        var far = wires.Select(w => w.Route[w.Route.Count - 1].Origin).ToList();
        Dictionary<string, object?>? footprint = null;
        double[]? datumSpan = null;
        if (first.Count >= 2)
        {
            double[] machineX = NormalizeOrZ(Difference3(first[first.Count - 1], first[0]));
            double[] machineZ = AcrossAxis(WorldUp, machineX);
            double[] machineY = CrossProduct(machineZ, machineX);
            if (Dot3(machineY, Difference3(CentroidOf(far), CentroidOf(first))) < 0.0)
            {
                machineX = Negate3(machineX);
                machineY = CrossProduct(machineZ, machineX);
            }
            double[] origin = CentroidOf(first);

            var everyVertex = new List<double[]>();
            void Take(MechanismMesh? mesh)
            {
                if (mesh is not null)
                    everyVertex.AddRange(mesh.Vertices);
            }
            // THE MACHINE'S OWN PARTS, AND NOTHING A STUDY OWNS (spec 3.4).
            // The tension tie and the anchor used to be swept here too, and
            // their vertices moved footprint.min, footprint.max,
            // footprint.setback and footprint.cableSpan -- the very numbers
            // a layout spaces machines by. A tie is a foundation body that
            // reaches behind and below the machine, so the setback it
            // produced described the works, not the winch, and a row spaced
            // by it stood further apart than it needed to. The numbers
            // MOVED, deliberately, and the harness pins the new ones.
            Take(machineOnly.Frame1);
            foreach (MechanismMesh part in machineOnly.Frame2)
                Take(part);
            Take(machineOnly.Motors);

            // EVERY BODY, NOT EVERY ENTRY. A reel entry stores its mesh
            // ONCE, at body 0, so sweeping the entries alone would measure
            // his seven-spool bank as though it were one spool and hand
            // back a machine that reads narrower than it is. Each body's
            // own transform puts that mesh where that body stands, which
            // for body 0 hands the vertex straight back.
            foreach (MechanismReelGroup entry in machineOnly.Reels)
            {
                foreach (MechanismReelBody body in entry.Bodies)
                {
                    foreach (double[] vertex in entry.Mesh.Vertices)
                        everyVertex.Add(MechanismReels.Place(body, vertex));
                }
            }

            if (everyVertex.Count > 0)
            {
                double[] low = { double.MaxValue, double.MaxValue, double.MaxValue };
                double[] high = { double.MinValue, double.MinValue, double.MinValue };
                foreach (double[] v in everyVertex)
                {
                    double[] local =
                    {
                        Dot3(Difference3(v, origin), machineX),
                        Dot3(Difference3(v, origin), machineY),
                        Dot3(Difference3(v, origin), machineZ),
                    };
                    for (int i = 0; i < 3; i++)
                    {
                        if (local[i] < low[i])
                            low[i] = local[i];
                        if (local[i] > high[i])
                            high[i] = local[i];
                    }
                }
                footprint = new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["frame"] = "the machine's own: X along the cable line, " +
                        "Y toward the body, Z up. Its origin is the centre " +
                        "of the wire first-frames.",
                    ["min"] = low,
                    ["max"] = high,
                    ["cableSpan"] = Distance(first[0], first[first.Count - 1]),
                    ["setback"] = high[1],
                };
            }
            datumSpan = machineX;
        }

        var document = new Dictionary<string, object?>(StringComparer.Ordinal)
        {
            ["schema"] = MachineSchema,
            // THE ID IS MINTED AND THE NAME IS A LABEL, and they are two
            // keys because they answer two questions: which machine is
            // this, and what do I call it. A study cites the id, so a
            // rename must not be able to orphan one.
            ["id"] = id,
            ["name"] = label,
            ["units"] = "m",
            ["lengthUnitToMetres"] = 1.0,
            ["wireCount"] = wires.Count,
            // THE ONE STATEMENT OF THE REEVE DEFAULT IN THIS DOCUMENT (spec
            // 6.3). Nothing under "machine" states it and nothing else
            // does: two keys carrying two plausible numbers, neither null,
            // is how a reader applies 1.0 where he authored 4.0 and every
            // reel spins four times too slowly, with the geometry, the wire
            // paths and the timing all still correct so nothing looks
            // broken.
            ["reeve"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["default"] = reeveDefault,
                ["how"] = "AUTHORED on the Machine component's Reeve (RV) " +
                    "input, per mechanism, and stated once in this whole " +
                    "document. It is the mechanical advantage of one wire's " +
                    "reeving through its block: a wheel that MOVES WITH " +
                    "THE LOAD gives advantage, one that merely guides gives " +
                    "none, and no geometry can tell the two apart. A study " +
                    "may override it per wire; where it does not, this is " +
                    "the value every wire resolves to.",
            },
            // WHICH INDEX SPACE A "reel" NUMBER COUNTS IN, stated because
            // two different numbers in this document both read as a reel
            // and nothing else distinguishes them. Neither key is renamed:
            // both names are already read by the studio, and this codebase
            // has paid for a silent rename once (bench.frames/1 to
            // bench.formwork/1 broke the reader and cost days), so the
            // document explains itself instead.
            ["indexing"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["entries"] = "machine.reels[].reel, bank.spools and " +
                    "bank.idlers are ENTRY indices: an entry is one reel " +
                    "KIND, one authored mesh carried to as many places as " +
                    "it has bodies.",
                ["bodies"] = "bank.drivenBodies, and a routing frame's own " +
                    "ownerReel, are PHYSICAL BODY indices: entry 0's " +
                    "bodies in order, then entry 1's, and so on. A wire " +
                    "rides one drum, not one kind, so the frames count " +
                    "bodies.",
            },
            ["bank"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["spools"] = spools,
                ["idlers"] = idlers,
                ["drivenBodies"] = drivenBodies.ToList(),
                ["radius"] = bankRadius,
                ["axis"] = bankAxis,
                ["how"] = "the entry(ies) whose BODIES terminate wire " +
                    "routes: a wire ends on the drum that pays it out, so " +
                    "the drums the routes end on are the driven ones, " +
                    "measured rather than inferred from size or from a " +
                    "shared radius. Cross-checked against wireCount by " +
                    "BODY, since one spool drives one cable. radius is the " +
                    "median winding radius of the driven entries and axis " +
                    "is the first driven body's own axis direction.",
            },
            ["footprint"] = footprint,
            ["datum"] = new Dictionary<string, object?>(StringComparer.Ordinal)
            {
                ["what"] = "the wire first-frames, in order of wire. THE " +
                    "machine's datum: placement pins to these, never to a " +
                    "body origin, which means nothing.",
                ["direction"] = datumSpan,
                ["frames"] = wires.Select(w => FramePayload(w.Route[0])).ToList(),
            },
            ["machine"] = ToPlainObject(machineBlock),
            ["routing"] = wires
                .Select(w => new Dictionary<string, object?>(StringComparer.Ordinal)
                {
                    ["wire"] = w.Wire,
                    ["route"] = w.Route.Select(FramePayload).ToList(),
                })
                .ToList(),
        };

        notes.Add(
            $"machine \"{label}\" (id {id}): {wires.Count} wire(s), reeve " +
            "default " +
            reeveDefault.ToString("0.####", CultureInfo.InvariantCulture) +
            $", {spools.Count} driven entry(ies) carrying " +
            $"{drivenBodies.Count} driven bod(y/ies), {idlers.Count} " +
            "idler entry(ies), " +
            (footprint is not null
                ? "cable span " +
                  ((double)footprint["cableSpan"]!).ToString("0.###", CultureInfo.InvariantCulture) +
                  " m, reaching " +
                  ((double)footprint["setback"]!).ToString("0.###", CultureInfo.InvariantCulture) +
                  " m behind the cable line"
                : "no footprint, since fewer than two wires carry frames") +
            ". This document carries NO STUDY: no net vertices, no world " +
            "placement, nothing that belongs to one vault. It is the " +
            "machine, and a study says which machine it was laid out for.");
        return JsonSerializer.Serialize(document, ContractJson.Options);
    }

    /// <summary>
    /// REFUSE WRITING ONE MACHINE OVER ANOTHER ONE'S FILE. Returns null
    /// when the write may go ahead, and the refusal message when it may
    /// not; it never writes and never deletes anything itself.
    ///
    /// WHY THIS EXISTS, AND WHAT IT IS NOT. The machine file is still named
    /// from the NAME, not from the minted id: two machines with different
    /// ids and the same name land on one path, and a name that is not one
    /// path segment collapses to "machine-machine.json", which is the very
    /// collapse the minted id was introduced to stop, relocated to disk.
    /// The cost is not a lost file. It is that a study citing id A can then
    /// open a file holding id B and render THE WRONG MACHINE with no
    /// complaint at all: the document is well formed, the schema is right,
    /// the geometry draws, and only the id inside it says it is somebody
    /// else's.
    ///
    /// THE REAL FIX is to name the file from the id, which needs a
    /// path-segment rule for ids and re-keys a library that already has
    /// files in it. That is Param's ruling to make, not this task's. This
    /// is the interim guard: an existing file whose own id DIFFERS is
    /// refused by name, saying which id is on disk and which was about to
    /// be written, and nothing is written. A matching id overwrites exactly
    /// as before, because rewriting your own machine is the ordinary case.
    ///
    /// A FILE THAT CANNOT BE READ OR PARSED IS REFUSED TOO, rather than
    /// assumed to be a spare copy of this machine. The whole point of the
    /// guard is that overwriting is irreversible, so the one thing it must
    /// never do is guess in the direction of writing.
    ///
    /// NOT PROVED, and said rather than left to be found: this cannot see a
    /// COLLISION THAT HAS NOT HAPPENED YET. Two machines sharing a name
    /// are refused on the second one's first write, so the guard names the
    /// clash at the moment it would occur and never before.
    /// </summary>
    public static string? RefuseOverwritingAnotherMachine(string targetPath, string machineId)
    {
        ArgumentNullException.ThrowIfNull(targetPath);
        string want = (machineId ?? string.Empty).Trim();
        if (!File.Exists(targetPath))
            return null;

        string onDisk;
        try
        {
            using FileStream stream = File.OpenRead(targetPath);
            using JsonDocument existing = JsonDocument.Parse(stream);
            if (existing.RootElement.ValueKind != JsonValueKind.Object ||
                !existing.RootElement.TryGetProperty("id", out JsonElement idOnDisk) ||
                idOnDisk.ValueKind != JsonValueKind.String)
            {
                return
                    $"\"{targetPath}\" already exists and states no id of " +
                    "its own, so it cannot be shown to be this machine's " +
                    $"file; nothing was written. The id about to be written " +
                    $"is \"{want}\". The file is named from the machine's " +
                    "NAME, not its minted id, so a file with another " +
                    "machine's contents can legitimately sit on this path, " +
                    "and a study citing one id that opened a file holding " +
                    "another would render the WRONG MACHINE without one " +
                    "word of complaint. Rename this machine, or move the " +
                    "existing file out of the library yourself.";
            }
            onDisk = idOnDisk.GetString() ?? string.Empty;
        }
        catch (Exception readError)
        {
            return
                $"\"{targetPath}\" already exists but could not be read as " +
                "a machine document (" + readError.Message + "), so its id " +
                "is unknown and nothing was written. The id about to be " +
                $"written is \"{want}\". Overwriting cannot be undone, so a " +
                "file this cannot identify is left alone rather than " +
                "assumed to be a spare copy of this machine.";
        }

        if (string.Equals(onDisk.Trim(), want, StringComparison.Ordinal))
            return null;

        return
            $"\"{targetPath}\" already holds the machine \"{onDisk}\", and " +
            $"the machine about to be written is \"{want}\"; nothing was " +
            "written. The file is named from the machine's NAME and not " +
            "from its minted id, so two machines you have named alike land " +
            "on one path. Overwriting would leave every study citing " +
            $"\"{onDisk}\" opening a document that says \"{want}\", which " +
            "renders the WRONG MACHINE with no complaint: the schema is " +
            "right, the geometry draws, and only the id inside says it is " +
            "somebody else's. Give one of the two a different Name.";
    }

    private static double[] ReadVector(JsonElement frame, string key) =>
        frame.TryGetProperty(key, out JsonElement v) && v.ValueKind == JsonValueKind.Array
            ? v.EnumerateArray().Select(e => e.GetDouble()).ToArray()
            : new[] { 0.0, 0.0, 0.0 };

    /// <summary>A parsed JSON element back to plain objects, so it can be re-serialised inside another document.</summary>
    private static object? ToPlainObject(JsonElement element)
    {
        switch (element.ValueKind)
        {
            case JsonValueKind.Object:
                var map = new Dictionary<string, object?>(StringComparer.Ordinal);
                foreach (JsonProperty property in element.EnumerateObject())
                    map[property.Name] = ToPlainObject(property.Value);
                return map;
            case JsonValueKind.Array:
                var items = new List<object?>();
                foreach (JsonElement item in element.EnumerateArray())
                    items.Add(ToPlainObject(item));
                return items;
            case JsonValueKind.String:
                return element.GetString();
            case JsonValueKind.Number:
                return element.GetDouble();
            case JsonValueKind.True:
                return true;
            case JsonValueKind.False:
                return false;
            default:
                return null;
        }
    }

    /// <summary>
    /// GROUP ROUTING BRANCHES BY WIRE, at whatever depth the tree has: the
    /// wire is the LAST index of each path and anything above it is
    /// grouping, read through.
    ///
    /// Pure on purpose. This logic used to live inside the component, where
    /// it needed an IGH_DataAccess and a Grasshopper tree and so could not
    /// be tested at all -- and it was WRONG for a year of canvases: it
    /// demanded a single-level path and silently ignored every branch that
    /// was not one. On 2026-09-09 his routing came out two levels deep,
    /// every branch was thrown away, and the whole document went out with
    /// no wires and no machines in it. The component now does the reading
    /// and this does the deciding, so the deciding has a test.
    ///
    /// Branches landing on the same wire are joined IN THE ORDER GIVEN,
    /// rather than one silently winning, and wires come back in wire order
    /// whatever order the paths arrived in.
    /// </summary>
    public static List<MechanismRoutingWire> GroupRouteBranchesByWire(
        IReadOnlyList<(IReadOnlyList<int> Path, IReadOnlyList<MechanismFrame> Frames)> branches)
    {
        var byWire = new SortedDictionary<int, List<MechanismFrame>>();
        foreach ((IReadOnlyList<int> path, IReadOnlyList<MechanismFrame> frames) in branches)
        {
            if (path.Count == 0)
                continue;
            int wire = path[path.Count - 1];
            if (!byWire.TryGetValue(wire, out List<MechanismFrame>? gathered))
            {
                gathered = new List<MechanismFrame>();
                byWire[wire] = gathered;
            }
            gathered.AddRange(frames);
        }
        var wires = new List<MechanismRoutingWire>(byWire.Count);
        foreach (KeyValuePair<int, List<MechanismFrame>> entry in byWire)
            wires.Add(new MechanismRoutingWire(entry.Key, entry.Value));
        return wires;
    }

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
    /// THE DIRECTION OF A LINE OF POINTS, taken between its two
    /// FURTHEST-APART members, so the order along it can never depend on
    /// how the set happened to be walked or discovered. A set of fewer than
    /// two points, or one whose members all coincide, has no direction at
    /// all and gets <see cref="NormalizeOrZ"/>'s own world-Z fallback,
    /// which keeps a degenerate row ordering rather than dividing by zero.
    ///
    /// ONE COPY, THREE CALLERS (2026-09-10). The same nested loop stood
    /// written out twice already, in <see cref="DerivePlacements"/> and in
    /// <see cref="DeriveAnchorFrames"/>; the study document's own
    /// wire-to-anchor matching is the third, and is the reason it is now a
    /// method. Two orderings that MUST agree are not written twice.
    /// </summary>
    internal static double[] WidestPairDirection(IReadOnlyList<double[]> points)
    {
        if (points.Count < 2)
            return NormalizeOrZ(new[] { 0.0, 0.0, 0.0 });
        double[] direction = NormalizeOrZ(Difference3(points[1], points[0]));
        double widest = 0.0;
        for (int a = 0; a < points.Count; a++)
        {
            for (int b = a + 1; b < points.Count; b++)
            {
                double span = Distance(points[a], points[b]);
                if (span > widest)
                {
                    widest = span;
                    direction = NormalizeOrZ(Difference3(points[b], points[a]));
                }
            }
        }
        return direction;
    }

    /// <summary>
    /// THE ORDER OF A SET OF POINTS ALONG ONE AXIS, as indices into the
    /// set: the single ordering rule every anchor row, every machine and
    /// every document matching in this file runs on.
    ///
    /// STABLE BY CONSTRUCTION: LINQ's OrderBy is a stable sort, so points
    /// sharing a position along the axis keep the order they were handed in
    /// rather than swapping on a floating-point tie.
    /// </summary>
    internal static int[] OrderAlongAxis(IReadOnlyList<double[]> points, double[] axis) =>
        Enumerable.Range(0, points.Count)
            .OrderBy(i => Dot3(points[i], axis))
            .ToArray();

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
        int[] alongMachine = OrderAlongAxis(first, machineX);
        double[][] machineBasisTransposed =
            Transpose3(BasisFromColumns(machineX, machineY, machineZ));

        var netPoints = new List<double[]>(eq.Vertices.Count);
        foreach (Point3Dto v in eq.Vertices)
            netPoints.Add(new[] { v.X, v.Y, v.Z });
        double[] netCentre = CentroidOf(netPoints);

        // THE ROWS, FOUND BY GEOMETRY WHEN TOPOLOGY CANNOT FIND THEM
        // (2026-09-09, measured on his own 2 Sided Vault and the reason his
        // first derived export placed NOTHING). AnchorRowIndices walks the
        // net's own edges, and on his study ZERO edges join two supports:
        // every anchor is connected only to interior vertices, never to its
        // neighbour along the springing. So it returns 42 groups of one,
        // every one shorter than the seven a machine needs.
        //
        // Nothing had depended on that before. The document's own wire
        // matching FLATTENS every row and pairs by order, so fragmentation
        // cost it nothing and stayed invisible. This is the first code to
        // need a row to actually be a row.
        //
        // Topology is still asked first, since where it does answer it
        // answers with the net's own structure. Where it cannot, the
        // anchors are clustered by their own spacing instead, which needs
        // no edges at all.
        List<List<int>> rows = MechanismGeometry.AnchorRowIndices(result);
        int topologicalRowCount = rows.Count;
        bool rowsFromTopology = rows.Any(row => row.Count >= PlacementGroupSize);
        if (!rowsFromTopology)
        {
            var anchorIds = new List<int>();
            foreach (int id in eq.ResolvedSupportNodeIds)
            {
                if (id >= 0 && id < netPoints.Count)
                    anchorIds.Add(id);
            }
            rows = ClusterAnchorsBySpacing(anchorIds, netPoints);
            notes.Add(
                "Placement (PL): the net's own edges join no two anchors on " +
                $"this study, so its {topologicalRowCount} topological " +
                "anchor group(s) are all too small to place a machine on. " +
                $"The {anchorIds.Count} anchors were grouped by their own " +
                $"spacing instead, giving {rows.Count} row(s) of " +
                string.Join(", ", rows.Select(r => r.Count)) +
                ". This needs no edges between anchors and is the reading " +
                "to expect on any net whose springing is not meshed along " +
                "itself.");
        }
        if (rows.Count == 0)
        {
            warnings.Add(
                "Placement (PL) is not authored and none could be derived: " +
                "the solved Result carries no anchors to read rows from.");
            return derived;
        }

        int placedTotal = 0;
        var shortRows = new List<int>();
        for (int side = 0; side < rows.Count; side++)
        {
            List<int> row = rows[side];
            var rowPoints = row.Select(id => netPoints[id]).ToList();
            if (row.Count < PlacementGroupSize)
            {
                shortRows.Add(row.Count);
                continue;
            }

            // THE ROW'S OWN DIRECTION, from its two furthest-apart anchors,
            // so the order along it can never depend on how the row was
            // walked.
            double[] rowDirection = WidestPairDirection(rowPoints);
            int[] sorted = OrderAlongAxis(rowPoints, rowDirection);

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
                int[] alongRow = OrderAlongAxis(anchors, worldX);

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

        if (shortRows.Count > 0)
        {
            string shortLine =
                $"{shortRows.Count} anchor row(s) hold fewer than the " +
                $"{PlacementGroupSize} anchors one machine needs (" +
                string.Join(", ", shortRows) + ") and carry no mechanism.";
            if (placedTotal == 0)
                warnings.Add(shortLine);
            else
                notes.Add(shortLine);
        }

        // AN EXPORTER THAT WRITES A WELL-FORMED DOCUMENT WITH NO MACHINES
        // IN IT IS THE WORST SHAPE THIS CAN FAIL IN: every schema check
        // passes and the absence only shows three steps downstream, as a
        // missing machine in the studio. So it is said here, in as many
        // words, as a warning.
        if (placedTotal == 0)
        {
            warnings.Add(
                "Placement (PL) is not authored and NO MECHANISM WAS " +
                "DERIVED, so this document carries no instances and no " +
                "wires at all: the machine's bodies travel but nothing is " +
                "placed, nothing is wired to the net, and no reel can " +
                "turn. Wire Placement (PL) directly, or see the row report " +
                "above for why the net's anchors could not be read as rows.");
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
            "rail, ONE piece in the mechanism's own local space (his " +
            "settled ruling that they arrive fused). Wire several objects " +
            "and they are JOINED into that one piece rather than solving " +
            "the component once per object. Instanced exactly like Frame " +
            "1, Frame 2, the Motors and the reels; permanence " +
            "\"permanent\".",
            GH_ParamAccess.list);
        parameters[1].Optional = true;

        parameters.AddGenericParameter(
            "Frame 1",
            "F1",
            "REFUSING STUB (spec 5.1): Frame 1 MOVED to the Machine " +
            "component's own Frame 1 (F1) input. This slot is held rather " +
            "than removed, since Grasshopper archives a wire by index and " +
            "removing a port silently re-points every wire after it, " +
            "landing a mesh on Wire Start, Placement, Routing, Frame " +
            "Meaning or Anchor instead; anything still wired here is " +
            "refused by name rather than read.",
            GH_ParamAccess.list);
        parameters[2].Optional = true;

        parameters.AddGenericParameter(
            "Frame 2",
            "F2",
            "REFUSING STUB (spec 5.1): Frame 2 MOVED to the Machine " +
            "component's own Frame 2 (F2) input. Held, not removed, for " +
            "the same reason as Frame 1 (F1); anything still wired here " +
            "is refused by name rather than read.",
            GH_ParamAccess.list);
        parameters[3].Optional = true;

        parameters.AddGenericParameter(
            "Motors",
            "MO",
            "REFUSING STUB (spec 5.1): the motors MOVED to the Machine " +
            "component's own Motors (MO) input. Held, not removed, for " +
            "the same reason as Frame 1 (F1); anything still wired here " +
            "is refused by name rather than read.",
            GH_ParamAccess.list);
        parameters[4].Optional = true;

        // RE AND AX ARE TREES HERE TOO, though nothing is read from them
        // (spec 4.1): a stub exists so an archived wire still lands
        // somewhere it can be refused by name, and a wire he moves to the
        // Machine component's own RE/AX carries a BRANCHED tree now. A stub
        // registered list would flatten that tree on the way in and count
        // ten objects where he authored four branches, which is a wrong
        // number in a message about a port he is being told not to use.
        parameters.AddGenericParameter(
            "Reel",
            "RE",
            "REFUSING STUB (spec 5.1): the reels MOVED to the Machine " +
            "component's own Reel (RE) input, which now reads a TREE, one " +
            "branch per reel KIND. Held, not removed, for the same reason " +
            "as Frame 1 (F1); anything still wired here is refused by name " +
            "rather than read.",
            GH_ParamAccess.tree);
        parameters[5].Optional = true;

        parameters.AddPlaneParameter(
            "Reel Axis",
            "AX",
            "REFUSING STUB (spec 5.1): the reel axes MOVED to the " +
            "Machine component's own Reel Axis (AX) input, which now reads " +
            "a TREE, one branch per reel KIND and one plane per BODY. " +
            "Held, not removed, for the same reason as Frame 1 (F1); " +
            "anything still wired here is refused by name rather than read.",
            GH_ParamAccess.tree);
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

        parameters.AddPlaneParameter(
            "Wire Start",
            "WS",
            "OPTIONAL, tree path {wire}: ONE plane per wire, the wire's " +
            "true start at its net anchor, BEFORE any offset. Wire it when " +
            "you have pushed the routing planes off the machine's own " +
            "surfaces so the drawn cable stops cutting through the drums " +
            "and the frame -- that offset moves the first plane too, and " +
            "the first plane is the anchor every correspondence in this " +
            "document is built on. The plane wired here is PREPENDED to " +
            "that wire's route, so the cable is drawn from its real anchor " +
            "out onto the offset path, and the placement, the net-vertex " +
            "matching and the residual all keep reading a route whose " +
            "planes[0] is genuinely the net end. Only the first plane of " +
            "each branch is read.",
            GH_ParamAccess.tree);
        parameters[9].Optional = true;

        parameters.AddTextParameter(
            "Frame Meaning",
            "FM",
            "What a routing plane's ORIGIN marks on the cable: " +
            "\"centreline\" (default), \"top\" (the cable hangs one " +
            "radius INWARD of the plane) or \"contact\" (the cable sits " +
            "one radius OUTWARD, so the plane is where it touches the " +
            "drum). It is written into the document and the studio obeys " +
            "it, so this is the one place the question is answered. " +
            "IF YOU OFFSET THE PLANES YOURSELF to stop the cable cutting " +
            "through the machine, leave this at \"centreline\": your " +
            "offset has already put them where the cable's centre goes, " +
            "and any further offset here would double it.",
            GH_ParamAccess.item,
            MechanismCollector.DefaultRoutingFrameMeaning);
        parameters[10].Optional = true;

        parameters.AddGenericParameter(
            "Anchor",
            "AN",
            "OPTIONAL: ONE typical foundation anchor, stamped ONCE PER " +
            "SIDE -- one continuous mass under the whole springing, the " +
            "shape of the skin edge on the first row, so the machines sit " +
            "cleanly on it. Authored in its own local space with +Z UP, X " +
            "ALONG THE ROW, and its OWN ORIGIN AT THE CENTRE of the row it " +
            "spans; model its bearing face on the z=0 plane and it sits on " +
            "the ground too. " +
            "Wire several objects and they are joined into one piece. The " +
            "body travels ONCE in the document and every anchor references " +
            "it, so a hundred anchors cost one mesh. Permanence " +
            "\"permanent\": it is works that remain, not machine that " +
            "comes away.",
            GH_ParamAccess.list);
        parameters[11].Optional = true;

        // TWO NEW PORTS, APPENDED (spec 3.0, 5.1): nothing above this line
        // moves or is renumbered, so an archived wire keeps the slot it
        // left. Appending them here means their index never moves under
        // whichever task resolves what they mean.
        parameters.AddTextParameter(
            "Machine", "MA",
            "THE MACHINE THIS STUDY CITES: the bench.machine/1 document " +
            "wired from the Machine component's own Machine (MC) output. " +
            "A study cites exactly ONE machine, by id, and this is that " +
            "citation. Since the split, the study document carries NO " +
            "MACHINE BODIES at all -- no frame, no motors, no reels -- so " +
            "without this the study has no machine to draw and no reeve " +
            "default to resolve its wires against, and no mechanism " +
            "document is written. The wires this study places are also " +
            "cross-checked against the cited machine's own declared wire " +
            "count, one for one.",
            GH_ParamAccess.item, string.Empty);
        parameters[12].Optional = true;

        parameters.AddNumberParameter(
            "Reeve Per Wire", "RW",
            "OPTIONAL, tree {wire}: a per-wire override of the machine's " +
            "own reeve default. Wire it only for the wire(s) whose " +
            "mechanical advantage genuinely differs from the machine's " +
            "stated default; every other wire keeps that default. " +
            "RESOLVED PER WIRE (spec 6.1-6.2): an override authored here " +
            "beats the machine default outright, and the resolved value " +
            "-- never the override or the default alone -- is what is " +
            "written onto that wire in the document, alongside which " +
            "source won (\"wire\" or \"machine\"), the same shape " +
            "net_vertex already uses so the studio never inherits or " +
            "infers one. A declared override that is not a finite, " +
            "positive number is refused BY NAME and that one wire falls " +
            "back to the machine default; it does not cost any other " +
            "wire or the document as a whole.",
            GH_ParamAccess.tree);
        parameters[13].Optional = true;
    }

    private static readonly ComponentValueListSpec[] MeaningValueLists =
    {
        new(
            10,
            "Frame Meaning",
            new (string Label, string Value)[]
            {
                ("Centreline", "centreline"),
                ("Top of the cable", "top"),
                ("Contact with the drum", "contact"),
            },
            MechanismCollector.DefaultRoutingFrameMeaning),
    };

    private protected override IReadOnlyList<ComponentValueListSpec>
        SuggestedValueLists => MeaningValueLists;

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

            MechanismAssetInput asset = ReadAsset(data, warnings, notes);
            List<MechanismRoutingWire> routing = ReadRouting(data, warnings, notes);

            // THE WIRE'S TRUE START GOES BACK ON THE FRONT of its route, so
            // an offset path still begins at the anchor everything else in
            // this document is pinned to.
            Dictionary<int, MechanismFrame> wireStarts = ReadWireStarts(data, warnings);
            if (wireStarts.Count > 0)
            {
                var rejoined = new List<MechanismRoutingWire>(routing.Count);
                int prepended = 0;
                double worstJump = 0.0;
                foreach (MechanismRoutingWire wire in routing)
                {
                    if (!wireStarts.TryGetValue(wire.Wire, out MechanismFrame? start) ||
                        wire.Route.Count == 0)
                    {
                        rejoined.Add(wire);
                        continue;
                    }
                    var route = new List<MechanismFrame>(wire.Route.Count + 1) { start };
                    route.AddRange(wire.Route);
                    rejoined.Add(new MechanismRoutingWire(wire.Wire, route));
                    prepended++;
                    double jump = MechanismCollector.Distance(
                        start.Origin, wire.Route[0].Origin);
                    if (jump > worstJump)
                        worstJump = jump;
                }
                routing = rejoined;
                var missing = routing
                    .Where(w => w.Route.Count > 0 && !wireStarts.ContainsKey(w.Wire))
                    .Select(w => w.Wire)
                    .ToList();
                notes.Add(
                    $"Wire Start (WS): {prepended} wire(s) had their true " +
                    "start prepended, so an offset routing path still " +
                    "begins at the anchor the placement and the net-vertex " +
                    "match are read from. The furthest a start sits from " +
                    "the first offset plane is " +
                    worstJump.ToString("0.####", CultureInfo.InvariantCulture) +
                    " m, which is the step the drawn cable takes leaving " +
                    "its anchor and should be about the offset you applied." +
                    (missing.Count > 0
                        ? " Wire(s) " + string.Join(", ", missing) +
                          " carry routing but NO start, so their route " +
                          "still begins at the offset plane and their " +
                          "anchor will read as moved."
                        : string.Empty));
            }
            List<MechanismPlacementBranch> placements = ReadPlacements(data, warnings);

            string meaning = string.Empty;
            data.GetData(10, ref meaning);

            // REEVE PER WIRE (RW, spec 6.1): read here and carried through
            // to the payload's own reeve.perWire UNRESOLVED -- the
            // resolution against a machine default happens downstream, in
            // MechanismDocument.Json, the one place a Result is available
            // to match wires against net vertices at all.
            Dictionary<int, double> reevePerWire = ReadReevePerWire(data, warnings, notes);

            // MACHINE (MA, spec 5.1): the bench.machine/1 document this
            // study cites, read as TEXT off an item port and parsed by the
            // pure reader so that every refusal is one this harness can
            // drive. Nothing wired is null and is named by the build
            // itself, once; a document that cannot be used is named here,
            // by the reader, and is also null.
            string machineDocument = string.Empty;
            data.GetData(12, ref machineDocument);
            MechanismMachineCitation? citation =
                MechanismCollector.ReadMachineCitation(machineDocument, warnings);

            // AN UNCITED STUDY IS NAMED HERE, AT THE PORT, AND NOWHERE
            // ELSE. It cannot be named inside the shared build: that same
            // build makes MACHINE documents, which cite nothing by design
            // and pool their warnings into the Machine component's chin,
            // so a message there would paint a correct machine build
            // orange over a port that component does not have. The
            // consequence is stated in full because it costs him the whole
            // document: since the split the study carries no machine
            // bodies at all, it points at a machine by id, and it takes
            // that machine's own authored reeve default.
            if (citation is null)
            {
                warnings.Add(
                    (machineDocument.Trim().Length == 0
                        ? "Machine (MA) is not wired, so this study CITES " +
                          "NO MACHINE"
                        : "Machine (MA) could not be read as a machine " +
                          "document (the reason is named above), so this " +
                          "study CITES NO MACHINE") +
                    " and no mechanism document can be written from it. " +
                    "Since the split, the study document carries no " +
                    "machine bodies at all: it points at a " +
                    MechanismCollector.MachineSchema + " document by id, " +
                    "and it takes that machine's own authored reeve " +
                    "default. Wire the Machine component's own Machine " +
                    "(MC) output here. Nothing is defaulted in its place, " +
                    "because a wrong reeve factor makes every reel spin at " +
                    "the wrong RATE while the geometry, the wire paths and " +
                    "the timing all stay correct, so nothing looks broken.");
            }

            string? payload = MechanismCollector.BuildWithResult(
                asset, routing, placements, warnings, notes, solved, meaning,
                reevePerWire, citation);

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
                      $", {asset.Reels.Count} reel entry(ies) offered, " +
                      $"{routedWireCount} of {MechanismCollector.PlacementGroupSize} " +
                      $"routing wire(s) authored, {placements.Count} " +
                      "placement branch(es), machine " +
                      (citation is null
                          ? "NOT CITED"
                          : $"\"{citation.Id}\" cited ({citation.WireCount} wire(s))") +
                      ", Result " +
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

    /// <summary>
    /// ONE PIECE OF THE MACHINE, however many objects he wired to say it.
    /// The port takes a LIST and joins it, so a frame modelled in seventeen
    /// parts arrives whole instead of Grasshopper solving the component
    /// seventeen times and keeping the last part. A single wired object is
    /// a list of one and behaves exactly as it always did.
    /// </summary>
    private MechanismMesh? ReadOnePiece(
        IGH_DataAccess data,
        int port,
        string label,
        List<string> warnings,
        List<string> notes,
        out bool fromBrep)
    {
        fromBrep = false;
        var items = new List<object>();
        data.GetDataList(port, items);
        var parts = new List<MechanismMesh>(items.Count);
        for (int i = 0; i < items.Count; i++)
        {
            if (!TryMeshOrBrep(items[i], out MechanismMesh? part, out bool partFromBrep) ||
                part is null)
            {
                warnings.Add(
                    $"{label}" + (items.Count > 1 ? $"[{i}]" : string.Empty) +
                    " did not resolve to a mesh or a closed Brep; " +
                    (items.Count > 1 ? "skipped." : "refused."));
                continue;
            }
            parts.Add(part);
            fromBrep |= partFromBrep;
        }
        if (parts.Count == 0)
            return null;
        if (parts.Count == 1)
            return parts[0];
        int vertexCount = parts.Sum(part => part.Vertices.Count);
        // A NOTE, NOT A WARNING: joining is what this port is FOR now, and
        // his machine authors its frame in seventeen parts and its motors
        // in seven. Work that came out right must not paint the component
        // orange -- his ruling, and the second time it has had to be made.
        notes.Add(
            $"{label} arrived as {parts.Count} separate objects and was " +
            $"joined here into one piece ({vertexCount} vertices), which is " +
            "what this port is for. The join keeps every vertex and face " +
            "as authored and welds nothing; it only renumbers them.");
        return MechanismCollector.JoinMeshes(parts);
    }

    /// <summary>
    /// A port that has MOVED to the other component (spec 3.0). Its slot
    /// is held rather than removed, because Grasshopper archives a wire by
    /// INDEX and removing a port silently re-points every wire after it
    /// onto whichever port now sits in that slot -- and the ports it
    /// re-points onto are the permissive ones, a text port casting from
    /// almost anything, a list landing on an item port and making the
    /// whole component solve once per item and keep the last. Anything
    /// wired here is refused BY NAME: an archived definition gets a
    /// sentence telling him where the port went, instead of a document
    /// that quietly carries the wrong thing, or silence with no
    /// explanation at all.
    ///
    /// READS WITH THE ACCESS THE PORT WAS REGISTERED WITH, passed in
    /// rather than assumed. GetDataList against an item- or tree-access
    /// parameter throws, or silently reads nothing, which would let a
    /// wired stub through with no warning; a port whose original access
    /// was item would need GetData, and one whose access was tree would
    /// need GetDataTree, counted across every branch, neither of which
    /// this helper implements yet because neither is needed yet: every
    /// stub this task creates -- TT and AN on the Machine component, and
    /// F1, F2, MO, RE and AX here on the Mechanism component -- was
    /// registered GH_ParamAccess.list, so GetDataList is correct for all
    /// seven. The access is asserted rather than silently assumed, so a
    /// future withdrawn port registered item or tree fails loudly here at
    /// the call site instead of quietly reading nothing and letting a
    /// wired-but-unread port through with no message.
    /// </summary>
    private static bool RefuseMovedPort(
        IGH_DataAccess data, int at, GH_ParamAccess access, string label,
        string wentWhere, List<string> warnings)
    {
        if (access != GH_ParamAccess.list)
        {
            throw new InvalidOperationException(
                $"{label} is registered {access}, not list. " +
                "RefuseMovedPort reads with GetDataList, which throws or " +
                "silently reads nothing against an item or tree " +
                "parameter; read it with GetData or GetDataTree instead " +
                "and count what arrived by hand.");
        }
        var junk = new List<IGH_Goo>();
        if (!data.GetDataList(at, junk) || junk.Count == 0)
            return false;
        warnings.Add(
            $"{label} has MOVED to the {wentWhere}, and {junk.Count} " +
            "object(s) are still wired to it here. Nothing wired to this " +
            "port is read. Move the wire and the message goes.");
        return true;
    }

    /// <summary>The Machine component's own withdrawn ports (TT, AN) share this reader; see <see cref="RefuseMovedPort"/>.</summary>
    internal static bool RefuseMovedPortPublic(
        IGH_DataAccess data, int at, GH_ParamAccess access, string label,
        string wentWhere, List<string> warnings) =>
        RefuseMovedPort(data, at, access, label, wentWhere, warnings);

    /// <summary>
    /// THE SAME REFUSAL FOR A WITHDRAWN TREE PORT (RE and AX, spec 4.1 and
    /// 5.1). A separate reader rather than a flag inside
    /// <see cref="RefuseMovedPort"/> because the two read by different
    /// calls: <c>GetDataList</c> against a tree parameter reads nothing at
    /// all, so a stub that kept the list reader would go SILENT the moment
    /// its port became a tree, and a silent refusal is worse than none --
    /// he would move nothing and be told nothing.
    ///
    /// It says how many BRANCHES as well as how many objects, because a
    /// branched reel tree is what he is being asked to move and the branch
    /// count is the thing that tells him this is the new-shaped wiring.
    /// </summary>
    private static bool RefuseMovedTreePort(
        IGH_DataAccess data, int at, GH_ParamAccess access, string label,
        string wentWhere, List<string> warnings)
    {
        if (access != GH_ParamAccess.tree)
        {
            throw new InvalidOperationException(
                $"{label} is registered {access}, not tree. " +
                "RefuseMovedTreePort reads with GetDataTree, which does not " +
                "match an item or list parameter; read it with GetData or " +
                "GetDataList instead and count what arrived by hand.");
        }
        if (!data.GetDataTree(at, out GH_Structure<IGH_Goo> tree) || tree is null)
            return false;
        int objects = 0;
        int branches = 0;
        foreach (GH_Path path in tree.Paths)
        {
            int inBranch = 0;
            foreach (IGH_Goo item in tree.get_Branch(path))
            {
                if (item is not null)
                    inBranch++;
            }
            if (inBranch == 0)
                continue;
            branches++;
            objects += inBranch;
        }
        if (objects == 0)
            return false;
        warnings.Add(
            $"{label} has MOVED to the {wentWhere}, and {objects} " +
            $"object(s) in {branches} branch(es) are still wired to it " +
            "here. Nothing wired to this port is read. Move the wire and " +
            "the message goes.");
        return true;
    }

    private MechanismAssetInput ReadAsset(IGH_DataAccess data, List<string> warnings, List<string> notes)
    {
        MechanismMesh? tt = ReadOnePiece(data, 1, "Tension Tie (TT)", warnings, notes, out bool ttBrep);

        // F1, F2, MO, RE and AX MOVED to the Machine component (spec 5.1):
        // the slots stay, each read by the access it is registered with --
        // list for F1, F2 and MO, TREE for RE and AX since Task 3 -- so an
        // archived wire still connects and can be refused by name rather
        // than left dangling with no explanation.
        _ = RefuseMovedPort(
            data, 2, GH_ParamAccess.list, "Frame 1 (F1)",
            "the Machine component's own Frame 1 (F1) input", warnings);
        _ = RefuseMovedPort(
            data, 3, GH_ParamAccess.list, "Frame 2 (F2)",
            "the Machine component's own Frame 2 (F2) input", warnings);
        _ = RefuseMovedPort(
            data, 4, GH_ParamAccess.list, "Motors (MO)",
            "the Machine component's own Motors (MO) input", warnings);

        MechanismMesh? an = ReadOnePiece(data, 11, "Anchor (AN)", warnings, notes, out bool anBrep);

        _ = RefuseMovedTreePort(
            data, 5, GH_ParamAccess.tree, "Reel (RE)",
            "the Machine component's own Reel (RE) input", warnings);
        _ = RefuseMovedTreePort(
            data, 6, GH_ParamAccess.tree, "Reel Axis (AX)",
            "the Machine component's own Reel Axis (AX) input", warnings);

        // Frame1, Frame2, Motors and the reels are always null/empty here
        // now, whatever used to be wired to the five stubs above: their
        // function moved to the Machine component, and a later task reads
        // them back in through the new Machine (MA) citation port instead
        // of local wires.
        return new MechanismAssetInput(
            null, false,
            Array.Empty<MechanismMesh>(), Array.Empty<bool>(),
            null, false,
            tt, ttBrep,
            Array.Empty<MechanismReelGroup>(),
            an, anBrep);
    }

    /// <summary>
    /// Reads Routing (RT) as a tree, path {wire}: the ONE authored
    /// mechanism's own routing, never per instance now.
    /// </summary>
    /// <summary>
    /// THE WIRE'S TRUE START, one plane per wire, read off the tree the same
    /// way Routing is (path {wire}, first plane of the branch).
    ///
    /// WHY IT EXISTS (2026-09-09, his own words): "the cables keep cutting
    /// through the geometry on the web app. so i need to offset the wires by
    /// 0.02. but this means the starting frame isnt right." Offsetting the
    /// routing planes off the drums is the right fix for a cable drawn at a
    /// real radius, but it moves the FIRST plane too -- and that plane is
    /// the anchor this whole document is pinned to: the placement
    /// correspondence, the net-vertex match and the residual all read it.
    /// Prepending the un-offset plane gives the drawn cable its real start
    /// and leaves every one of those readings exactly as it was.
    /// </summary>
    private Dictionary<int, MechanismFrame> ReadWireStarts(
        IGH_DataAccess data, List<string> warnings)
    {
        var starts = new Dictionary<int, MechanismFrame>();
        data.GetDataTree(9, out GH_Structure<GH_Plane> wsTree);
        foreach (GH_Path path in wsTree.Paths)
        {
            if (path.Indices.Length == 0)
                continue;
            foreach (GH_Plane planeGoo in wsTree.get_Branch(path))
            {
                if (planeGoo is null)
                    continue;
                Plane plane = planeGoo.Value;
                starts[path.Indices[path.Indices.Length - 1]] = new MechanismFrame(
                    new[] { plane.Origin.X, plane.Origin.Y, plane.Origin.Z },
                    new[] { plane.XAxis.X, plane.XAxis.Y, plane.XAxis.Z },
                    new[] { plane.YAxis.X, plane.YAxis.Y, plane.YAxis.Z },
                    new[] { plane.ZAxis.X, plane.ZAxis.Y, plane.ZAxis.Z });
                break;
            }
        }
        return starts;
    }

    /// <summary>
    /// Reeve Per Wire (RW), path {wire} exactly as Wire Start (WS) above:
    /// the LAST index of the path is the wire it overrides. Carried
    /// through UNRESOLVED against any machine default -- this method only
    /// reads what was authored, never what it means against 1.0 or 4.0 or
    /// anything else, because the resolution (<see
    /// cref="MechanismReeve.Resolve"/>) happens downstream in
    /// MechanismDocument.Json, the one place a wire's own id exists to
    /// name which override this is.
    ///
    /// A DECLARED OVERRIDE THAT IS NOT A MECHANICAL ADVANTAGE (not finite,
    /// or not greater than zero) is refused BY NAME and DROPPED, not
    /// carried through as a wrong number: that one wire then resolves
    /// against the machine default instead, exactly as if nothing had
    /// been wired for it, and every other wire and the document as a
    /// whole are unaffected. This mirrors the cited machine's own default
    /// refusal in spirit but not in force -- a bad override costs one
    /// wire, never the whole document, because it is optional by nature
    /// where a citation is not.
    /// </summary>
    private Dictionary<int, double> ReadReevePerWire(
        IGH_DataAccess data, List<string> warnings, List<string> notes)
    {
        var perWire = new Dictionary<int, double>();
        data.GetDataTree(13, out GH_Structure<GH_Number> rwTree);
        foreach (GH_Path path in rwTree.Paths)
        {
            if (path.Indices.Length == 0)
                continue;
            int wire = path.Indices[path.Indices.Length - 1];
            foreach (GH_Number numberGoo in rwTree.get_Branch(path))
            {
                if (numberGoo is null)
                    continue;
                double value = numberGoo.Value;
                if (!double.IsFinite(value) || value <= 0.0)
                {
                    warnings.Add(
                        $"Reeve Per Wire (RW)[{wire}] is " +
                        value.ToString(CultureInfo.InvariantCulture) +
                        ", which is not a mechanical advantage; ignored, " +
                        "so wire " + wire + " keeps the machine's own " +
                        "default instead.");
                }
                else
                {
                    perWire[wire] = value;
                }
                break;
            }
        }
        if (perWire.Count > 0)
        {
            notes.Add(
                $"Reeve Per Wire (RW): {perWire.Count} wire(s) carry an " +
                "override of the machine's own reeve default -- wire(s) " +
                string.Join(", ", perWire.Keys.OrderBy(w => w)) +
                "; every other wire takes the machine's default instead.");
        }
        return perWire;
    }

    /// <summary>
    /// THE WIRE IS THE LAST INDEX OF THE PATH, whatever depth the tree has.
    ///
    /// This used to demand a single-level {wire} path and IGNORE every
    /// branch that was not one. On 2026-09-09 he rebuilt his routing for the
    /// offset and the higher frame resolution, it came out two levels deep
    /// as {0;wire}, and the reader silently threw away all of it -- so there
    /// were no wire first-frames, so no correspondence, so NOTHING was
    /// placed, with PL wired or not. The chin filled with one warning per
    /// branch saying the path was the wrong shape, which is true and useless:
    /// a tree with a grouping level above the wire is an ordinary thing for
    /// an author to build, and refusing it costs the whole document.
    ///
    /// Routing belongs to the ONE authored mechanism and is indexed by wire,
    /// so any levels ABOVE the wire are grouping and are read through. Two
    /// branches that land on the same wire are joined in path order rather
    /// than one silently winning. What was found is REPORTED, once, with the
    /// shape it had.
    /// </summary>
    private List<MechanismRoutingWire> ReadRouting(
        IGH_DataAccess data, List<string> warnings, List<string> notes)
    {
        data.GetDataTree(7, out GH_Structure<GH_Plane> rtTree);
        var branches = new List<(IReadOnlyList<int>, IReadOnlyList<MechanismFrame>)>();
        int deepest = 0;
        int emptyPaths = 0;
        foreach (GH_Path path in rtTree.Paths)
        {
            if (path.Indices.Length == 0)
            {
                emptyPaths++;
                continue;
            }
            deepest = Math.Max(deepest, path.Indices.Length);
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
            branches.Add((path.Indices, frames));
        }
        if (emptyPaths > 0)
            warnings.Add($"Routing (RT): {emptyPaths} branch(es) carry no path indices; ignored.");

        List<MechanismRoutingWire> wires =
            MechanismCollector.GroupRouteBranchesByWire(branches);

        if (wires.Count > 0)
        {
            notes.Add(
                $"Routing (RT): {rtTree.Paths.Count} branch(es) " +
                (deepest > 1
                    ? $"{deepest} level(s) deep, read as {{...;wire}} -- the " +
                      "LAST index of each path is the wire and anything " +
                      "above it is grouping"
                    : "one level deep, read as {wire}") +
                $", giving {wires.Count} wire(s) numbered " +
                string.Join(", ", wires.Select(w => w.Wire)) +
                ", carrying " +
                string.Join(", ", wires.Select(w => w.Route.Count)) +
                " frame(s) each.");
            if (wires.Count != MechanismCollector.PlacementGroupSize)
            {
                warnings.Add(
                    $"Routing (RT) resolved {wires.Count} wire(s), not the " +
                    $"{MechanismCollector.PlacementGroupSize} a mechanism instance needs. " +
                    "Placement pairs one wire with one anchor, so a count " +
                    "that is not seven cannot be placed. The wire numbers " +
                    "found were " + string.Join(", ", wires.Select(w => w.Wire)) +
                    "; if your tree groups the wires under something else, " +
                    "it is the LAST path index that must be the wire.");
            }
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

    internal static bool TryMeshOrBrepPublic(object? item, out MechanismMesh? mesh, out bool fromBrep) =>
        TryMeshOrBrep(item, out mesh, out fromBrep);

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

/// <summary>
/// MACHINE ("MC"): the machine ALONE, written to its own file, with no
/// study anywhere near it.
///
/// His ruling, 2026-09-09: "one component purely deals with the mechanism
/// and its own export write, so it doesnt collide with anything ... i might
/// make several different ones that might deal with different amounts of
/// wires each, smaller, larger etc."
///
/// So this writes bench.machine/1 and nothing else. It takes no Result, it
/// derives no placement, it names no net vertex. What it produces is the
/// thing he owns and may own several of, and a study says which machine it
/// was laid out for rather than carrying a copy of one.
///
/// It writes its OWN file rather than travelling through Export, which is
/// what stops it colliding: a machine changes when he changes the machine,
/// not when a vault re-solves, and a ten megabyte document has no business
/// being rewritten by every study.
/// </summary>
public sealed class MachineComponent : NativeComponentBase
{
    public MachineComponent()
        : base(
            "Machine",
            "MC",
            "The machine alone -- bodies, reels and axes, routing, the " +
            "anchor and tie -- written to its own bench.machine/1 file. " +
            "No Result, no placement, no study: this is the thing you own " +
            "and may own several of, at different wire counts, and a study " +
            "says which one it was laid out for.",
            ComponentCategories.Deliver,
            "machine")
    {
    }

    public override Guid ComponentGuid =>
        new("7c4f1a28-5d63-4e90-8b17-2af6c05d9e33");

    protected override void RegisterInputParams(GH_InputParamManager parameters)
    {
        parameters.AddTextParameter(
            "Name",
            "N",
            "The machine's own name, which becomes its id and its file " +
            "name: <Name>-machine.json. Name it for what it IS -- the " +
            "seven-wire bank, the twelve -- since this is what a study " +
            "will cite and what a chooser will list.",
            GH_ParamAccess.item,
            "machine");

        parameters.AddTextParameter(
            "Folder",
            "F",
            "Where to write it. Keep every machine in ONE folder: that " +
            "folder is the library, and the studio scans it to offer them.",
            GH_ParamAccess.item,
            string.Empty);
        parameters[1].Optional = true;

        parameters.AddBooleanParameter(
            "Write",
            "W",
            "True writes the file. A machine changes when you change the " +
            "machine, not when a vault re-solves, so this is deliberate " +
            "rather than automatic.",
            GH_ParamAccess.item,
            false);
        parameters[2].Optional = true;

        parameters.AddGenericParameter(
            "Tension Tie",
            "TT",
            "REFUSING STUB (spec 3.3): the tension tie MOVED to the " +
            "Mechanism component's own Tension Tie (TT) input, because it " +
            "is study-side permanent work, not machine. This slot is held " +
            "rather than removed, since Grasshopper archives a wire by " +
            "index and removing a port silently re-points every wire " +
            "after it; anything still wired here is refused by name " +
            "rather than read.",
            GH_ParamAccess.list);
        parameters[3].Optional = true;

        parameters.AddGenericParameter(
            "Anchor",
            "AN",
            "REFUSING STUB (spec 3.3): the anchor MOVED to the Mechanism " +
            "component's own Anchor (AN) input, because it is study-side " +
            "permanent work, not machine. This slot is held rather than " +
            "removed, since Grasshopper archives a wire by index and " +
            "removing a port silently re-points every wire after it; " +
            "anything still wired here is refused by name rather than " +
            "read.",
            GH_ParamAccess.list);
        parameters[4].Optional = true;

        parameters.AddGenericParameter(
            "Frame 1", "F1", "The machine frame, one piece; several objects are joined.",
            GH_ParamAccess.list);
        parameters[5].Optional = true;

        parameters.AddGenericParameter(
            "Frame 2", "F2", "A second frame part in a different material, a list.",
            GH_ParamAccess.list);
        parameters[6].Optional = true;

        parameters.AddGenericParameter(
            "Motors", "MO", "The motors, one piece; several objects are joined.",
            GH_ParamAccess.list);
        parameters[7].Optional = true;

        // RE AND AX ARE TREES (spec 4.1, his ruling 1.5): ONE BRANCH PER
        // REEL KIND, not one item per reel. Ten physical reels are four
        // branches, and the mesh is serialised once per branch rather than
        // once per reel. The old flat wiring lands entirely in branch {0}
        // and is REFUSED by name rather than read as one drum repeated at
        // ten axes (spec 4.7).
        parameters.AddGenericParameter(
            "Reel", "RE",
            "The reels, ONE BRANCH PER REEL KIND: the seven spools that " +
            "move alike are ONE branch holding ONE authored mesh, and each " +
            "pulley is its own branch. Several meshes in a branch are " +
            "joined into that kind's one body mesh. A flat list of every " +
            "reel is the OLD shape and is refused, not guessed at.",
            GH_ParamAccess.tree);
        parameters[8].Optional = true;

        parameters.AddPlaneParameter(
            "Reel Axis",
            "AX",
            "One branch per reel kind, matching Reel BY BRANCH POSITION, " +
            "and within a branch ONE PLANE PER PHYSICAL REEL: seven planes " +
            "in the spool branch draw that one drum at seven places. The " +
            "FIRST plane of a branch is the frame its mesh is authored at.",
            GH_ParamAccess.tree);
        parameters[9].Optional = true;

        parameters.AddPlaneParameter(
            "Routing",
            "RT",
            "The wire frames, tree path {wire} or grouped above it: the " +
            "wire is the LAST index. planes[0] is the NET END. HOW MANY " +
            "WIRES YOU GIVE IS THE MACHINE'S wireCount, and every layout " +
            "decision downstream turns on it, so a five-wire machine and a " +
            "twelve-wire one need no change anywhere else.",
            GH_ParamAccess.tree);
        parameters[10].Optional = true;

        parameters.AddTextParameter(
            "Frame Meaning",
            "FM",
            "What a routing plane's origin marks on the cable: " +
            "\"centreline\" (default), \"top\" or \"contact\".",
            GH_ParamAccess.item,
            MechanismCollector.DefaultRoutingFrameMeaning);
        parameters[11].Optional = true;

        // THREE NEW PORTS, APPENDED (spec 3.0, 3.1): nothing above this
        // line moves or is renumbered, so an archived wire keeps the slot
        // it left.
        parameters.AddPlaneParameter(
            "Wire Start", "WS",
            "OPTIONAL, tree {wire}: ONE plane per wire, the wire's true " +
            "start BEFORE any offset. Wire it when you have pushed the " +
            "routing planes off the machine's own surfaces so the drawn " +
            "cable stops cutting the drums. That offset moves planes[0], " +
            "and planes[0] is this machine's DATUM, so without this the " +
            "offset moves every study placed against it.",
            GH_ParamAccess.tree);
        parameters[12].Optional = true;

        parameters.AddTextParameter(
            "Machine Id", "ID",
            "The MINTED CODE a study cites, and the one thing about this " +
            "machine that must never change. Name is the label and may be " +
            "renamed freely; the id is the identity. They are separate " +
            "because a study citing a missing machine renders nothing at " +
            "all, silently, so renaming must not be able to orphan one.",
            GH_ParamAccess.item, string.Empty);
        parameters[13].Optional = false;

        parameters.AddNumberParameter(
            "Reeve", "RV",
            "The mechanical advantage of one wire's reeving through its " +
            "block, this machine's DEFAULT. A wheel that MOVES WITH THE " +
            "LOAD gives advantage; one that merely guides gives none, and " +
            "no amount of geometry can tell them apart, so this is " +
            "authored. Param's unit is 4.0. A wrong value makes every reel " +
            "spin at the wrong RATE while geometry, wire paths and timing " +
            "all stay correct, so nothing looks broken.",
            GH_ParamAccess.item, MechanismCollector.DefaultReeveFactor);
        parameters[14].Optional = true;
    }

    protected override void RegisterOutputParams(GH_OutputParamManager parameters)
    {
        parameters.AddTextParameter(
            "Machine",
            "MC",
            "The bench.machine/1 document, whether or not it was written. " +
            "Wire it straight into a study's exporter to lay this machine " +
            "out on that vault without going near a file.",
            GH_ParamAccess.item);
        parameters.AddTextParameter(
            "Status",
            "ST",
            "What it read, what it measured and where it wrote, then every " +
            "warning and note in full.",
            GH_ParamAccess.item);
    }

    protected override void SolveInstance(IGH_DataAccess data)
    {
        try
        {
            var warnings = new List<string>();
            var notes = new List<string>();

            string name = "machine";
            string folder = string.Empty;
            bool write = false;
            string meaning = string.Empty;
            string machineId = string.Empty;
            double reeve = MechanismCollector.DefaultReeveFactor;
            data.GetData(0, ref name);
            data.GetData(1, ref folder);
            data.GetData(2, ref write);
            data.GetData(11, ref meaning);
            data.GetData(13, ref machineId);
            data.GetData(14, ref reeve);

            MechanismAssetInput asset = ReadAsset(data, warnings, notes);
            List<MechanismRoutingWire> routing = ReadRouting(data, warnings, notes);

            // THE NAME REACHES THE DOCUMENT AS AUTHORED, and the id comes
            // from its own port (spec 3.6). StudyName still sanitises the
            // FILE name, which is what it was written for, but it no longer
            // touches the identity: it rewrites any name that is not one
            // path segment to "machine", so two machines named "winch, 4 m"
            // and "winch (spare)" both minted the id "machine" and the
            // second silently became the first.
            string document = MechanismCollector.BuildMachine(
                asset, routing, machineId, name, reeve, meaning, warnings, notes);

            var status = new List<string>
            {
                document.Length == 0
                    ? "received: no machine document; the warning(s) below " +
                      "say why (nothing wired, no Machine Id, or a Reeve " +
                      "that is not a mechanical advantage)."
                    : $"received: machine \"{name.Trim()}\", id " +
                      $"\"{machineId.Trim()}\", " +
                      $"{routing.Count(w => w.Route.Count > 0)} wire(s) " +
                      "routed, reeve default " +
                      reeve.ToString("0.####", CultureInfo.InvariantCulture) + ".",
            };

            if (write && document.Length > 0)
            {
                if (string.IsNullOrWhiteSpace(folder))
                {
                    warnings.Add(
                        "Write is True but Folder is empty, so there is " +
                        "nowhere to write the machine; nothing was written.");
                }
                else
                {
                    try
                    {
                        Directory.CreateDirectory(folder);
                        string target = Path.Combine(
                            folder, $"{StudyName(name)}-machine.json");

                        // NEVER WRITE ONE MACHINE OVER ANOTHER ONE'S FILE.
                        // The path is built from the NAME, so two machines
                        // named alike share it; a study citing one id that
                        // opened the other's document would render the
                        // WRONG MACHINE with nothing to see. Refused by
                        // name, with both ids in the message.
                        string? refusal =
                            MechanismCollector.RefuseOverwritingAnotherMachine(
                                target, machineId);
                        if (refusal is not null)
                        {
                            warnings.Add(refusal);
                        }
                        else
                        {
                            AtomicFile.Write(target, document);
                            status.Add($"written: {target}");
                        }
                    }
                    catch (Exception writeError)
                    {
                        warnings.Add(
                            "The machine could not be written: " + writeError.Message);
                    }
                }
            }
            else
            {
                status.Add("written: nothing.");
            }

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

            data.SetData(0, document);
            data.SetData(1, string.Join(Environment.NewLine, status));
            Message = document.Length == 0
                ? "no document"
                : $"{routing.Count(w => w.Route.Count > 0)} wire(s)";
        }
        catch (Exception error)
        {
            Message = "Failed";
            ReportException("Machine failed", error);
        }
    }

    /// <summary>
    /// A name that is ONE path segment, since it becomes a FILE name. The
    /// same rule Export's own Name follows, for the same reason.
    ///
    /// IT NO LONGER TOUCHES THE MACHINE'S IDENTITY (spec 3.6). The id used
    /// to be this sanitised name, so a name that was not one path segment
    /// became the literal id "machine", and two such machines minted one
    /// identity. The id is authored on its own port now, and this is left
    /// where it belongs: on the file the library holds.
    ///
    /// NOT CHANGED HERE, and said rather than left to be found: the written
    /// file is still named from the NAME, not the id, so two machines with
    /// different ids and the same name still write to one file. Naming the
    /// file by the id would be the better rule and is a deliberate change
    /// to his library's own layout, not a side effect of this one.
    /// </summary>
    private static string StudyName(string name)
    {
        string trimmed = (name ?? string.Empty).Trim();
        return ExportPlan.NameIsOneSegment(trimmed) ? trimmed : "machine";
    }

    private MechanismAssetInput ReadAsset(
        IGH_DataAccess data, List<string> warnings, List<string> notes)
    {
        // TT and AN MOVED to the Mechanism component (spec 3.3): the slots
        // stay, GH_ParamAccess.list exactly as they were registered, so an
        // archived wire still connects and can be refused by name rather
        // than left dangling with no explanation.
        _ = MechanismCollectorComponent.RefuseMovedPortPublic(
            data, 3, GH_ParamAccess.list, "Tension Tie (TT)",
            "the Mechanism component's own Tension Tie (TT) input",
            warnings);
        _ = MechanismCollectorComponent.RefuseMovedPortPublic(
            data, 4, GH_ParamAccess.list, "Anchor (AN)",
            "the Mechanism component's own Anchor (AN) input",
            warnings);
        MechanismMesh? f1 = ReadOnePiece(data, 5, "Frame 1 (F1)", warnings, notes, out bool f1Brep);

        var f2Items = new List<object>();
        data.GetDataList(6, f2Items);
        var f2 = new List<MechanismMesh>(f2Items.Count);
        var f2Brep = new List<bool>(f2Items.Count);
        for (int i = 0; i < f2Items.Count; i++)
        {
            if (!MechanismCollectorComponent.TryMeshOrBrepPublic(f2Items[i], out MechanismMesh? m, out bool b) ||
                m is null)
            {
                warnings.Add($"Frame 2 (F2)[{i}] did not resolve to a mesh or a closed Brep; skipped.");
                continue;
            }
            f2.Add(m);
            f2Brep.Add(b);
        }

        MechanismMesh? mo = ReadOnePiece(data, 7, "Motors (MO)", warnings, notes, out bool moBrep);

        // THE REELS, READ AS TREES AND PAIRED BY BRANCH POSITION (spec
        // 4.1): Reel (RE) branch i against Reel Axis (AX) branch i, in the
        // order Grasshopper itself lists the paths. Position, never path
        // NAME: he groups his reels under whatever path his own definition
        // happens to produce, the two ports are branched by the same
        // upstream tree, and demanding the two path strings match would
        // refuse a machine that is wired correctly. What that costs is
        // named in the chin below rather than left to be discovered.
        List<List<MechanismMesh?>> reelBranches = ReadMeshTree(
            data, 8, "Reel (RE)", warnings, out List<bool> reelBranchFromBrep,
            out int reelPaths);
        List<List<MechanismFrame?>> axisBranches = ReadPlaneTree(data, 9, out int axisPaths);

        if (reelPaths > 0 && axisPaths > 0 && reelPaths != axisPaths)
        {
            warnings.Add(
                $"Reel (RE) holds {reelPaths} branch(es) and Reel Axis " +
                $"(AX) holds {axisPaths}. They are paired by BRANCH " +
                "POSITION, one branch per reel KIND, so a count that " +
                "disagrees leaves entries with a mesh and no axis, or an " +
                "axis and no mesh; each is refused by name below. Branch " +
                "the two ports off the same tree and the counts agree by " +
                "construction.");
        }

        IReadOnlyList<MechanismReelGroup> reels = MechanismReels.Resolve(
            reelBranches, axisBranches, warnings, reelBranchFromBrep);
        if (reels.Count > 0)
        {
            notes.Add(
                $"Reel (RE): {reelPaths} branch(es) against {axisPaths} " +
                $"axis branch(es), read as {reels.Count} reel ENTRY(ies) " +
                $"carrying {reels.Sum(g => g.Bodies.Count)} physical " +
                "reel(s). Branches are paired by POSITION in Grasshopper's " +
                "own path order, not by path name.");
        }

        // TensionTie and Anchor are always null here now: TT and AN are
        // refusing stubs above, never read, so this component can no
        // longer hand BuildMachine a non-null tie or anchor no matter what
        // is wired to the deprecated ports (spec 3.3). That closes the gap
        // ValidateMachineDocument's own doc comment names: its fixture
        // already builds MechanismAssetInput with a null tie and anchor
        // (calling BuildMachine directly, beneath this component), so the
        // footprint literals it pins were never inflated by them and stay
        // unchanged; what changes is that THIS reader can no longer be the
        // one that inflates them (spec 3.4).
        return new MechanismAssetInput(
            f1, f1Brep, f2, f2Brep, mo, moBrep, null, false,
            reels, null, false);
    }

    /// <summary>
    /// A TREE OF MESHES, BRANCH BY BRANCH, in Grasshopper's own path order:
    /// one list per branch, an object that is neither mesh nor closed Brep
    /// refused BY BRANCH AND POSITION rather than dropped, and one
    /// from-Brep flag per BRANCH, OR-ed across it, since a reel entry
    /// carries one mesh and therefore one answer to "was this meshed here".
    ///
    /// A null hole in a branch is kept as a null, so the position of every
    /// object after it in that branch is the position the author sees.
    /// </summary>
    private static List<List<MechanismMesh?>> ReadMeshTree(
        IGH_DataAccess data, int at, string label, List<string> warnings,
        out List<bool> fromBrepByBranch, out int paths)
    {
        var branches = new List<List<MechanismMesh?>>();
        fromBrepByBranch = new List<bool>();
        paths = 0;
        if (!data.GetDataTree(at, out GH_Structure<IGH_Goo> tree) || tree is null)
            return branches;
        foreach (GH_Path path in tree.Paths)
        {
            paths++;
            var branch = new List<MechanismMesh?>();
            bool anyFromBrep = false;
            int at_ = 0;
            foreach (IGH_Goo item in tree.get_Branch(path))
            {
                int here = at_++;
                if (item is null)
                {
                    branch.Add(null);
                    continue;
                }
                if (!MechanismCollectorComponent.TryMeshOrBrepPublic(
                        item, out MechanismMesh? mesh, out bool fromBrep) ||
                    mesh is null)
                {
                    warnings.Add(
                        $"{label} branch {{{string.Join(";", path.Indices)}}} " +
                        $"item [{here}] did not resolve to a mesh or a " +
                        "closed Brep; refused.");
                    branch.Add(null);
                    continue;
                }
                branch.Add(mesh);
                anyFromBrep |= fromBrep;
            }
            branches.Add(branch);
            fromBrepByBranch.Add(anyFromBrep);
        }
        return branches;
    }

    /// <summary>
    /// A TREE OF PLANES, BRANCH BY BRANCH, in Grasshopper's own path order.
    /// A null plane is carried through as a null so that
    /// <see cref="MechanismReels.Resolve"/> can name the BODY it costs;
    /// dropping it here would silently renumber the bodies after it and
    /// every message about them would then be one out.
    /// </summary>
    private static List<List<MechanismFrame?>> ReadPlaneTree(
        IGH_DataAccess data, int at, out int paths)
    {
        var branches = new List<List<MechanismFrame?>>();
        paths = 0;
        if (!data.GetDataTree(at, out GH_Structure<GH_Plane> tree) || tree is null)
            return branches;
        foreach (GH_Path path in tree.Paths)
        {
            paths++;
            var branch = new List<MechanismFrame?>();
            foreach (GH_Plane planeGoo in tree.get_Branch(path))
            {
                if (planeGoo is null)
                {
                    branch.Add(null);
                    continue;
                }
                Plane plane = planeGoo.Value;
                branch.Add(new MechanismFrame(
                    new[] { plane.Origin.X, plane.Origin.Y, plane.Origin.Z },
                    new[] { plane.XAxis.X, plane.XAxis.Y, plane.XAxis.Z },
                    new[] { plane.YAxis.X, plane.YAxis.Y, plane.YAxis.Z },
                    new[] { plane.ZAxis.X, plane.ZAxis.Y, plane.ZAxis.Z }));
            }
            branches.Add(branch);
        }
        return branches;
    }

    private MechanismMesh? ReadOnePiece(
        IGH_DataAccess data, int port, string label,
        List<string> warnings, List<string> notes, out bool fromBrep)
    {
        fromBrep = false;
        var items = new List<object>();
        data.GetDataList(port, items);
        var parts = new List<MechanismMesh>(items.Count);
        for (int i = 0; i < items.Count; i++)
        {
            if (!MechanismCollectorComponent.TryMeshOrBrepPublic(items[i], out MechanismMesh? part, out bool b) ||
                part is null)
            {
                warnings.Add(
                    $"{label}" + (items.Count > 1 ? $"[{i}]" : string.Empty) +
                    " did not resolve to a mesh or a closed Brep; " +
                    (items.Count > 1 ? "skipped." : "refused."));
                continue;
            }
            parts.Add(part);
            fromBrep |= b;
        }
        if (parts.Count == 0)
            return null;
        if (parts.Count == 1)
            return parts[0];
        notes.Add(
            $"{label} arrived as {parts.Count} separate objects and was " +
            $"joined here into one piece ({parts.Sum(x => x.Vertices.Count)} " +
            "vertices), which is what this port is for.");
        return MechanismCollector.JoinMeshes(parts);
    }

    private List<MechanismRoutingWire> ReadRouting(
        IGH_DataAccess data, List<string> warnings, List<string> notes)
    {
        data.GetDataTree(10, out GH_Structure<GH_Plane> rtTree);
        var branches = new List<(IReadOnlyList<int>, IReadOnlyList<MechanismFrame>)>();
        int deepest = 0;
        foreach (GH_Path path in rtTree.Paths)
        {
            if (path.Indices.Length == 0)
                continue;
            deepest = Math.Max(deepest, path.Indices.Length);
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
            branches.Add((path.Indices, frames));
        }
        List<MechanismRoutingWire> wires =
            MechanismCollector.GroupRouteBranchesByWire(branches);
        if (wires.Count > 0)
        {
            notes.Add(
                $"Routing (RT): {rtTree.Paths.Count} branch(es) " +
                (deepest > 1 ? $"{deepest} level(s) deep" : "one level deep") +
                $", giving {wires.Count} wire(s) carrying " +
                string.Join(", ", wires.Select(w => w.Route.Count)) +
                " frame(s) each. THIS COUNT IS THE MACHINE'S wireCount.");
        }
        return wires;
    }
}
