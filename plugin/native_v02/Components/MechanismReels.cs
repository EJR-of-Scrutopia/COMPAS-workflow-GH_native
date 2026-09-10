#nullable enable

using System;
using System.Collections.Generic;
using System.Globalization;
using System.Linq;

namespace Ananke.COMPAS.Native.Components;

/// <summary>ONE PHYSICAL REEL: its own axis, and the transform that carries
/// the entry's mesh onto it. Determinant is CARRIED rather than recomputed
/// by every reader, because it is the one number that separates a rotation
/// from a reflection and a reflection is invisible in a still frame.
///
/// <c>Linear</c> is NINE numbers, ROW-MAJOR, flat. The maths in
/// <see cref="MechanismCollector"/> works in jagged <c>double[][]</c>, and
/// the conversion happens in exactly one named place,
/// <see cref="MechanismReels.LinearFromBasis"/>, rather than inline at each
/// call: flat is what goes into the JSON document, jagged is what the
/// matrix helpers take, and a codebase that converts between them in five
/// places is a codebase that will one day transpose one of them.</summary>
internal sealed record MechanismReelBody(
    MechanismFrame Axis,
    double[] Linear,        // row-major 3x3
    double[] Translation,
    double Determinant);

/// <summary>ONE REEL KIND: one authored mesh, and every body that moves
/// alike. His ten reels are FOUR of these, seven bodies plus three singles,
/// which is what makes the mesh travel once instead of ten times.
///
/// <c>Bodies</c> is NEVER EMPTY as <see cref="MechanismReels.Resolve"/>
/// builds it: an entry whose every body was refused is dropped whole and
/// named, so a reader may take <c>Bodies[0]</c> -- the frame the mesh is
/// authored at -- without asking first.</summary>
internal sealed record MechanismReelGroup(
    MechanismMesh Mesh,
    bool FromBrep,
    IReadOnlyList<MechanismReelBody> Bodies);

/// <summary>
/// REELS AS ENTRIES AND BODIES (spec 4.1 to 4.7, his ruling 1.5 of
/// 2026-09-09: "a reel ENTRY is one mesh at N axes, not N meshes. Grouping
/// only earns its keep if the mesh travels once").
///
/// WHAT AN ENTRY IS: one authored mesh and N BODIES. A BODY is one physical
/// reel -- one axis plane, one place, one spin. His machine is FOUR entries
/// and TEN bodies: the spool entry with seven bodies, and three pulley
/// entries with one each. Before this, the same drum mesh was serialised
/// seven times.
///
/// THE ORDER BODIES COME BACK IN IS PART OF THE CONTRACT, because the
/// routing-frame ownership tally and every route frame's own
/// <c>ownerReel</c> index count PHYSICAL REELS: entry 0's bodies in order,
/// then entry 1's, and so on -- exactly the order a reader gets by walking
/// the document's own <c>reels</c> array and flattening each entry's
/// <c>bodies</c>. For a machine of single-body entries (every fixture in
/// this repo, and every machine he has authored to date) that index is
/// identical to the old flat reel index, which is why nothing downstream
/// had to move.
/// </summary>
internal static class MechanismReels
{
    /// <summary>A body transform whose determinant is AT OR BELOW this is
    /// refused. Not a tolerance on zero: a proper rotation has determinant
    /// exactly +1 and a reflection exactly -1, so anything negative is
    /// unambiguous. The comparison is INCLUSIVE so that a degenerate basis
    /// (coincident or collinear plane axes, determinant 0) is refused
    /// alongside the reflections rather than read as a body whose drum is
    /// flattened onto a plane. No Rhino plane can arrive degenerate, so
    /// that half of the gate guards a caller rather than an author.</summary>
    public const double MinimumBodyDeterminant = 0.0;

    /// <summary>
    /// Turn N branches of meshes and N branches of axis planes into reel
    /// ENTRIES, each one mesh at as many bodies as it has axes.
    ///
    /// BRANCHES ARE PAIRED BY POSITION, entry i of Reel (RE) against entry i
    /// of Reel Axis (AX), which is the same convention the two ports have
    /// always had; this method never sees a Grasshopper path, so there is no
    /// second reading available to drift into. A branch with no matching
    /// branch refuses ONLY that entry, by name -- the axis is authored,
    /// never inferred.
    ///
    /// WHAT IS NOT PROVED HERE, said plainly rather than left to be
    /// discovered.
    ///
    /// ONE: nothing in this method checks that the bodies of one entry
    /// really are the same drum. He could author a spool and a pulley in one
    /// branch and get one mesh drawn at both axes, and the transform would
    /// be a clean rotation with determinant +1. Geometry cannot tell a
    /// deliberate grouping from a mistaken one, so the grouping is his
    /// statement and this method carries it rather than second-guessing it.
    ///
    /// TWO: the legacy-shape refusal below is an EQUALITY between the ITEM
    /// count and the plane count, so a single branch holding a genuinely
    /// different number of objects from its planes -- ten objects against
    /// nine planes -- falls through it and is read as one entry. The
    /// equality is deliberate: the looser reading, any single branch holding
    /// more than one mesh, would refuse a genuine single-kind entry authored
    /// as several disjoint objects, and a warning that fires on correct
    /// input is a defect. It counts ITEMS rather than meshes that resolved,
    /// so a null or an unmeshable object among his ten cannot shrink the
    /// count past the test; a bare null arrives with no warning of its own,
    /// so counting resolved meshes would have made that fall-through silent
    /// as well as wrong.
    ///
    /// THREE: that the bodies of an entry are rigid images of one another.
    /// The transform is built from the authored planes as given, so
    /// non-unit or non-orthogonal plane axes would scale or shear the drum
    /// rather than turn it. Rhino planes are orthonormal by construction and
    /// neither component's reader can make one that is not, so this is a
    /// statement about callers, not about authors; the determinant gate
    /// catches the degenerate and reflected cases, not a scaled one.
    /// </summary>
    /// <param name="fromBrepByBranch">Whether entry i's own meshes were
    /// meshed from a Brep here rather than authored as meshes, one flag per
    /// MESH branch, already OR-ed across the branch by the reader that knows.
    /// Optional because the pure maths does not care and every harness
    /// fixture builds meshes directly; the components pass it so the chin
    /// can still say which parts were meshed in passing.</param>
    public static List<MechanismReelGroup> Resolve(
        IReadOnlyList<IReadOnlyList<MechanismMesh?>> branches,
        IReadOnlyList<IReadOnlyList<MechanismFrame?>> axisBranches,
        List<string> warnings,
        IReadOnlyList<bool>? fromBrepByBranch = null)
    {
        ArgumentNullException.ThrowIfNull(branches);
        ArgumentNullException.ThrowIfNull(axisBranches);
        ArgumentNullException.ThrowIfNull(warnings);

        // THE ONE ARCHIVED SHAPE WHOSE MEANING CHANGES. Today RE and AX are
        // two flat lists zipped one to one: ten meshes, ten planes, ten
        // reels. Under the tree reading that same wiring lands entirely in
        // branch {0}, which is ONE entry whose mesh is all ten reels JOINED,
        // repeated at ten axes: a complete, plausible, catastrophically
        // wrong machine, produced by every definition he has saved, on first
        // open. Refuse it. Do NOT guess which reading he meant.
        //
        // WHY THIS CANNOT FIRE ON A CORRECTLY BRANCHED MACHINE: his own is
        // four branches, and any machine of more than one reel KIND fails
        // the first clause outright. A machine of exactly ONE kind reaches
        // the rest, and is refused only where its branch holds exactly as
        // many ITEMS as it has axes -- which is the flat zip byte for byte.
        // One kind authored as ONE mesh at N axes, the shape this whole
        // section exists to accept, has one item against N planes and
        // passes untouched.
        //
        // THE COUNT IS OF ITEMS, NOT OF MESHES THAT RESOLVED, and that is
        // the guard rather than a detail of it. Both readers keep a hole in
        // place as a null (MechanismComponents.cs, ReadMeshTree and
        // ReadPlaneTree), so a branch of ten objects is ten items whether
        // or not every one of them became a mesh. Counting only the ones
        // that did would let a SINGLE null among his archived ten drop the
        // count to nine, fall through this test, and be read as one entry
        // of every drum joined together repeated at ten axes -- the exact
        // misreading this section exists to prevent, and a bare null is not
        // even warned about on the way in, so that fall-through would be
        // silent as well as wrong.
        if (branches.Count == 1 && axisBranches.Count == 1 &&
            axisBranches[0].Count > 1 &&
            branches[0].Count == axisBranches[0].Count)
        {
            warnings.Add(
                $"Reel (RE) and Reel Axis (AX) both hold ONE branch of " +
                $"{axisBranches[0].Count} objects. That is the OLD flat " +
                "reading, where reel i paired with axis i. They are now " +
                "read as ENTRIES: one branch per reel KIND, its meshes " +
                "joined into one body mesh, and one plane per BODY. Read " +
                "the old way round this would build a single reel whose " +
                "mesh is every drum joined together, repeated at every " +
                "axis. Branch the reels by kind and the message goes.");
            return new List<MechanismReelGroup>();
        }

        var groups = new List<MechanismReelGroup>();
        int entries = Math.Max(branches.Count, axisBranches.Count);
        for (int e = 0; e < entries; e++)
        {
            IReadOnlyList<MechanismMesh?> meshBranch =
                e < branches.Count ? branches[e] : Array.Empty<MechanismMesh?>();
            IReadOnlyList<MechanismFrame?> axisBranch =
                e < axisBranches.Count ? axisBranches[e] : Array.Empty<MechanismFrame?>();

            var meshes = new List<MechanismMesh>(meshBranch.Count);
            foreach (MechanismMesh? mesh in meshBranch)
            {
                if (mesh is not null)
                    meshes.Add(mesh);
            }

            // A NULL AXIS COSTS ITS OWN BODY, named, and shifts the bodies
            // after it down one. Named rather than dropped silently, because
            // the body indices in every other message here are positions in
            // this list and a silent hole would make them lie.
            var axes = new List<MechanismFrame>(axisBranch.Count);
            for (int a = 0; a < axisBranch.Count; a++)
            {
                if (axisBranch[a] is null)
                {
                    warnings.Add(
                        $"Reel Axis (AX) entry [{e}] plane [{a}] is null, so " +
                        "that BODY has no axis to spin about and is refused; " +
                        "the axis is authored, never inferred. The bodies " +
                        "after it move down one place." +
                        (a == 0
                            ? " It was the FIRST plane, which is the frame " +
                              "this entry's mesh is authored at, so the next " +
                              "sound plane becomes body 0 and every other " +
                              "body is measured from THAT one instead."
                            : string.Empty));
                    continue;
                }
                axes.Add(axisBranch[a]!);
            }

            if (meshes.Count == 0 && axes.Count == 0)
                continue;
            if (meshes.Count == 0)
            {
                warnings.Add(
                    $"Reel Axis (AX) entry [{e}] carries " +
                    $"{axes.Count} plane(s) but Reel (RE) has no matching " +
                    "reel mesh branch; the axis is authored, never inferred, " +
                    $"so reel entry {e} is refused.");
                continue;
            }
            if (axes.Count == 0)
            {
                warnings.Add(
                    $"Reel (RE) entry [{e}] carries {meshes.Count} mesh(es) " +
                    "but Reel Axis (AX) has no matching axis plane; the axis " +
                    "is authored, never inferred, so reel entry " +
                    $"{e} is refused.");
                continue;
            }

            MechanismMesh entryMesh = meshes.Count == 1
                ? meshes[0]
                : MechanismCollector.JoinMeshes(meshes);

            // THE ENTRY'S MESH IS AUTHORED AT BODY 0 (spec 4.2), so body 0's
            // own axis plane is the SOURCE frame every other body is
            // measured from.
            MechanismFrame source = axes[0];
            double[][] sourceBasis = MechanismCollector.BasisFromColumns(
                source.XAxis, source.YAxis, source.ZAxis);
            double[][]? sourceInverse = MechanismCollector.Invert3(sourceBasis);
            if (sourceInverse is null)
            {
                warnings.Add(
                    $"Reel (RE) entry [{e}]'s own FIRST axis plane has " +
                    "coincident or collinear axes (the basis is singular), " +
                    "and that plane is the frame this entry's mesh is " +
                    "authored at, so no body transform can be built from it " +
                    $"at all; reel entry {e} is refused whole.");
                continue;
            }

            var bodies = new List<MechanismReelBody>(axes.Count);
            for (int b = 0; b < axes.Count; b++)
            {
                MechanismFrame axis = axes[b];
                double[][] bodyBasis = MechanismCollector.BasisFromColumns(
                    axis.XAxis, axis.YAxis, axis.ZAxis);
                // THE PLANE'S OWN HANDEDNESS, read from the CARRIED Z.
                // MechanismFrame keeps a true Z rather than deriving it as X
                // cross Y precisely so that a mirrored authored plane still
                // says so here; re-deriving it would make every plane
                // right-handed by construction and this test unable to fail.
                double planeDeterminant = MechanismCollector.Determinant3(bodyBasis);

                double[] linear;
                double[] translation;
                double determinant;
                if (b == 0)
                {
                    // BODY 0'S TRANSFORM IS DECLARED, NOT COMPUTED. It is
                    // the identity because the mesh IS authored there, not
                    // because a matrix product came out that way: computing
                    // M0 * inverse(M0) for a general authored basis lands on
                    // 0.9999999999999998 and leaves a reader wondering
                    // whether the drum came back very slightly scaled.
                    linear = new[] { 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0 };
                    translation = new[] { 0.0, 0.0, 0.0 };
                    determinant = 1.0;
                }
                else
                {
                    double[][] basis = MechanismCollector.Multiply3(bodyBasis, sourceInverse);
                    double[] carried = MechanismCollector.MultiplyVector3(basis, source.Origin);
                    linear = LinearFromBasis(basis);
                    translation = new[]
                    {
                        axis.Origin[0] - carried[0],
                        axis.Origin[1] - carried[1],
                        axis.Origin[2] - carried[2],
                    };
                    determinant = MechanismCollector.Determinant3(basis);
                }

                // A REFLECTION IS REFUSED, AND THE SAME SIGN MEANS THE
                // OPPOSITE THING ONE SCREEN AWAY. In the PLACEMENT maths
                // (MechanismComponents.cs, the instance loop) a negative
                // determinant is read as a genuine MIRROR and kept: his far
                // side really is a reflected copy of the near side, he
                // authors it by mirroring a plane, and Rhino leaves that
                // plane's stored Z genuinely left-handed as the signal. A
                // whole machine reflected is still the machine.
                //
                // A REEL BODY is the opposite case. The body is one drum,
                // rotationally symmetric about its own axis, so reflecting
                // it about a plane through that axis produces a body that is
                // PIXEL-IDENTICAL in every still frame and turns the
                // OPPOSITE WAY for the same take-up. There is no still
                // picture in which the fault is visible and no residual it
                // disturbs: the obvious test, that the transform reproduces
                // the body's own axis to 1e-12, is satisfied EXACTLY by the
                // reflection. The determinant is the only witness, so it is
                // the guard.
                //
                // BOTH numbers are gated by the same constant. The
                // transform's own determinant catches a body mirrored
                // relative to its entry; the plane's catches an entry whose
                // FIRST plane is itself mirrored, where the transform is the
                // declared identity and would report +1 for a left-handed
                // frame.
                if (determinant <= MinimumBodyDeterminant ||
                    planeDeterminant <= MinimumBodyDeterminant)
                {
                    warnings.Add(
                        $"Reel (RE) entry [{e}] body {b} is a reflection " +
                        "or a degenerate plane, not a rotation (transform " +
                        "determinant " +
                        determinant.ToString("0.###", CultureInfo.InvariantCulture) +
                        ", its own authored axis plane's determinant " +
                        planeDeterminant.ToString("0.###", CultureInfo.InvariantCulture) +
                        "). A mirrored PLACEMENT plane is expected here and " +
                        "is built as a reflection, because his far side " +
                        "genuinely is a mirrored copy of the machine; a " +
                        "mirrored REEL BODY is not, because a drum is " +
                        "rotationally symmetric about its own axis, so a " +
                        "reflected one looks identical in every still frame " +
                        "and turns the OPPOSITE way for the same take-up. " +
                        $"Body {b} is refused. Un-mirror that axis plane and " +
                        "the message goes.");
                    continue;
                }

                bodies.Add(new MechanismReelBody(axis, linear, translation, determinant));
            }

            if (bodies.Count == 0)
            {
                warnings.Add(
                    $"Reel (RE) entry [{e}] has no sound body left, so the " +
                    "entry itself is dropped: an entry with no body is a " +
                    "reel that exists nowhere, and leaving it in the " +
                    "document would hand the bank a reel to classify and a " +
                    "mesh with no place to stand.");
                continue;
            }

            bool fromBrep =
                fromBrepByBranch is not null &&
                e < fromBrepByBranch.Count &&
                fromBrepByBranch[e];
            groups.Add(new MechanismReelGroup(entryMesh, fromBrep, bodies));
        }

        return groups;
    }

    /// <summary>
    /// THE ONE PLACE JAGGED BECOMES FLAT: a 3x3 basis as
    /// <c>m[row][col]</c>, the shape every matrix helper in
    /// <see cref="MechanismCollector"/> takes and returns, written out as
    /// nine numbers ROW-MAJOR, the shape <see cref="MechanismReelBody"/>
    /// carries and the document publishes. Named and shared rather than
    /// repeated inline, because the two shapes differ only by a transpose
    /// and a transpose is invisible until the machine animates.
    /// </summary>
    internal static double[] LinearFromBasis(double[][] basis) => new[]
    {
        basis[0][0], basis[0][1], basis[0][2],
        basis[1][0], basis[1][1], basis[1][2],
        basis[2][0], basis[2][1], basis[2][2],
    };

    /// <summary>
    /// ONE POINT OF THE ENTRY'S OWN MESH, CARRIED ONTO ONE BODY: the same
    /// row-major nine and the same three that the document publishes,
    /// applied here rather than left for every reader to re-derive. Body 0
    /// hands the point straight back, since its transform is the identity.
    ///
    /// It exists because the entry's mesh is stored ONCE, at body 0, and
    /// anything measured over the whole machine -- the footprint is the
    /// live case -- must still see every body's geometry rather than one
    /// drum standing in for seven.
    /// </summary>
    internal static double[] Place(MechanismReelBody body, double[] point) => new[]
    {
        (body.Linear[0] * point[0]) + (body.Linear[1] * point[1]) +
            (body.Linear[2] * point[2]) + body.Translation[0],
        (body.Linear[3] * point[0]) + (body.Linear[4] * point[1]) +
            (body.Linear[5] * point[2]) + body.Translation[1],
        (body.Linear[6] * point[0]) + (body.Linear[7] * point[1]) +
            (body.Linear[8] * point[2]) + body.Translation[2],
    };
}
