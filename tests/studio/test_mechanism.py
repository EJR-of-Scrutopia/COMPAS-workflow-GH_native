"""The machine document: the server's check and the reader's arithmetic.

The reader (static/mechanism.js) is pure on purpose -- plain data in,
plain data out, no three.js and no DOM -- because the document's key
layout is expected to move again, and the place a moved key lands should
be a tested function rather than a renderer.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench" / "studio"))

import mechanism  # noqa: E402

MODULE = REPO / "bench" / "studio" / "static" / "mechanism.js"

needs_node = pytest.mark.skipif(
    shutil.which("node") is None, reason="node is not on PATH")


def test_the_schema_is_checked_and_named():
    with pytest.raises(ValueError) as raised:
        mechanism.validate_mechanism_document({"schema": "bench.mould/1"})
    assert "bench.mould/1" in str(raised.value)
    assert "bench.mechanism/1" in str(raised.value), (
        "the message names what it wanted, not just what it got")

    with pytest.raises(ValueError) as raised:
        mechanism.validate_mechanism_document([1, 2, 3])
    assert "JSON object" in str(raised.value)


def test_a_future_version_is_refused_rather_than_read():
    """A reader that shrugs at bench.mechanism/2 would draw a machine
    from keys it does not understand, which is worse than drawing none."""

    with pytest.raises(ValueError) as raised:
        mechanism.validate_mechanism_document({"schema": "bench.mechanism/2"})
    assert "does not support" in str(raised.value)


def test_the_scale_resolves_from_either_spelling():
    """Two conventions are in play across the sibling set: the frames
    document says units 'm', and the columns convention this document's
    geometry follows carries lengthUnitToMetres. Both are read, and a
    document that says both must agree with itself."""

    assert mechanism.scale_to_metres({"units": "m"}) == 1.0
    assert mechanism.scale_to_metres({"lengthUnitToMetres": 0.001}) == 0.001
    assert mechanism.scale_to_metres({}) == 1.0, "silence means metres"

    with pytest.raises(ValueError) as raised:
        mechanism.scale_to_metres({"units": "mm"})
    assert "not 'm'" in str(raised.value)

    with pytest.raises(ValueError) as raised:
        mechanism.scale_to_metres({"units": "m", "lengthUnitToMetres": 0.001})
    assert "cannot both be true" in str(raised.value)

    with pytest.raises(ValueError):
        mechanism.scale_to_metres({"lengthUnitToMetres": 0})


def test_the_resolved_scale_rides_on_the_document():
    """So the client never has to work out which spelling was used."""

    out = mechanism.validate_mechanism_document(
        {"schema": "bench.mechanism/1", "lengthUnitToMetres": 0.001,
         "reels": [{"anything": True}]})
    assert out["lengthUnitToMetres"] == 0.001
    assert out["reels"] == [{"anything": True}], "the parts pass through untouched"


def test_the_server_does_not_shape_the_document():
    """The key layout is expected to move again. A server that understood
    those keys would need editing and RESTARTING every time they moved,
    mid-session, while Param is exporting and looking. So the validator
    knows about the schema and the scale and nothing else, and the module
    says so where the next person will read it."""

    source = (REPO / "bench" / "studio" / "mechanism.py").read_text(
        encoding="utf-8")
    for port in ("reels", "motors", "instances", "wires", "anchors"):
        assert '"%s"' % port not in source, (
            "the server must not know the part ports: %s" % port)
    assert "static/mechanism.js" in source, "it points at where shaping lives"


CHECK = textwrap.dedent("""
    import {
      SCHEMA, PART_KINDS, readGeometry, placementMatrix, isReflection,
      turnsFor, readMechanism, checkNetVertices, checkRouteDirection,
      wireCentreline, reelContactRadius, SPOOL_STEPS, PULLEY_STEPS,
      ribChain, chainLength, DEFAULT_CABLE_RADIUS,
      supportRows, outwardFrame, betweenFrames, derivePlacements,
    } from %MODULE%;

    function expect(condition, message) {
      if (!condition) { console.error("FAIL: " + message); process.exit(1); }
    }
    function near(a, b, tol, message) {
      expect(Math.abs(a - b) < (tol || 1e-9),
        message + " (got " + a + ", wanted " + b + ")");
    }

    // ---------- geometry ----------
    // Mixed triangles and quads, the columns convention, and three
    // spellings of a vertex list because the writer has used more than one.
    const nested = readGeometry({
      vertices: [[0, 0, 0], [1, 0, 0], [1, 1, 0], [0, 1, 0]],
      faces: [[0, 1, 2, 3]],
    });
    expect(nested.vertexCount === 4, "four corners");
    expect(nested.triangles.length === 6, "a quad fans into two triangles");
    const flat = readGeometry({ vertices: [0, 0, 0, 1, 0, 0, 1, 1, 0],
      faces: [[0, 1, 2]] });
    expect(flat.vertexCount === 3, "a flat vertex list reads too");
    const objects = readGeometry({
      vertices: [{ x: 0, y: 0, z: 0 }, { x: 2, y: 0, z: 0 }, { x: 0, y: 2, z: 0 }],
      faces: [{ vertices: [0, 1, 2] }] });
    expect(objects.triangles.length === 3, "faces as objects read too");

    // The scale is applied to positions.
    const mm = readGeometry({ vertices: [[1000, 0, 0]], faces: [] }, 0.001);
    near(mm.vertices[0], 1, 1e-9, "a millimetre document lands in metres");

    // A face naming a vertex that does not exist is DROPPED, not drawn:
    // an out-of-range index in a renderer is a crash or a spike to the
    // origin, and neither is a machine.
    const bad = readGeometry({ vertices: [[0,0,0],[1,0,0],[1,1,0]],
      faces: [[0, 1, 9]] });
    expect(bad.triangles.length === 0, "a face out of range is dropped");

    // ---------- placement ----------
    const identity = placementMatrix({ origin: [1, 2, 3],
      xAxis: [1, 0, 0], yAxis: [0, 1, 0] });
    near(identity[12], 1, 1e-9, "origin x");
    near(identity[14], 3, 1e-9, "origin z");
    expect(isReflection(identity) === false, "a plain frame is not mirrored");

    // THE REFLECTION. The writer reports side 1 as determinant -1, and a
    // DERIVED z cannot express that: z = x cross y is right-handed by
    // construction, always. So a derived z silently turns a mirrored
    // instance into a rotation, and the mirrored half comes back turned
    // the wrong way rather than mirrored.
    const derivedOnly = placementMatrix({ origin: [0, 0, 0],
      xAxis: [-1, 0, 0], yAxis: [0, 1, 0] });
    expect(isReflection(derivedOnly) === false,
      "with z derived, no frame can ever be a reflection -- which is "
      + "exactly why an explicit z has to be honoured");

    // An explicit z is used VERBATIM, reflection and all.
    const mirrored = placementMatrix({ origin: [0, 0, 0],
      xAxis: [1, 0, 0], yAxis: [0, 1, 0], zAxis: [0, 0, -1] });
    expect(isReflection(mirrored) === true,
      "an explicit z opposing x cross y is a reflection and stays one");
    near(mirrored[10], -1, 1e-9, "and z points the way the document said");

    // Derived when the document sends none, so the older shape still works.
    const built = placementMatrix({ origin: [0, 0, 0],
      xAxis: [1, 0, 0], yAxis: [0, 1, 0] });
    near(built[8], 0, 1e-9, "z x");
    near(built[10], 1, 1e-9, "z z");

    // Axes that are parallel describe no frame at all, and saying so
    // beats returning a matrix that collapses the part to a plane.
    expect(placementMatrix({ origin: [0,0,0], xAxis: [1,0,0], yAxis: [2,0,0] })
      === null, "parallel axes are refused");
    expect(placementMatrix({ origin: [0,0,0], xAxis: [0,0,0], yAxis: [0,1,0] })
      === null, "a zero axis is refused");

    // ---------- the spin ----------
    // turns = (free at frame 0 - free now) * reeve / (2 pi r).
    // POSITIVE TURNS TAKE UP WIRE: reeling in shortens the free span, so
    // a shorter span now than at frame 0 must come out positive. The
    // formula briefly read the other way round and said the opposite of
    // its own sign sentence.
    const takeUp = turnsFor(3.0, 2.0, 1, 0.05);
    expect(takeUp > 0, "a shortening span takes up wire, so turns positive");
    near(takeUp, 1 / (2 * Math.PI * 0.05), 1e-9, "one metre at 50 mm radius");
    expect(turnsFor(2.0, 3.0, 1, 0.05) < 0, "a lengthening span pays out");
    near(turnsFor(3.0, 2.0, 4, 0.05), 4 * takeUp, 1e-9,
      "reeve 4 turns four times as far");
    // A radius of zero is a document fault, not a divide by zero.
    expect(turnsFor(3.0, 2.0, 1, 0) === 0, "no radius, no spin, no NaN");

    // ---------- reading a document ----------
    const bodyGeom = { vertices: [[0,0,0],[1,0,0],[1,1,0]], faces: [[0,1,2]] };
    // The real document's shape, measured from Param's own 2 Sided Vault
    // export: the parts live INSIDE the authored body under named keys,
    // each key holding one part or a list, each declaring its own
    // permanence; instances carry `frame` (a frame) and `placement` (a
    // LABEL); reels carry `mesh`, their own `reel` number and an axis.
    const document = {
      schema: "bench.mechanism/1",
      lengthUnitToMetres: 1,
      mechanism: {
        frame1: { vertices: bodyGeom.vertices, faces: bodyGeom.faces,
          permanence: "temporary" },
        reels: [
          { reel: 0, mesh: bodyGeom, permanence: "temporary", driven: true,
            axis: { origin: [0,0,0], xAxis: [1,0,0], yAxis: [0,1,0],
              zAxis: [0,0,1] } },
          { reel: 1, mesh: bodyGeom, permanence: "temporary", driven: true,
            windingRadius: 0.17 },
        ],
        motors: { vertices: bodyGeom.vertices, faces: bodyGeom.faces,
          permanence: "temporary" },
        tensionTie: { vertices: bodyGeom.vertices, faces: bodyGeom.faces,
          permanence: "permanent" },
        reeveFactor: 1,
        spoolRadius: 0.05,
      },
      instances: [
        { side: 0, mechanism: 0, placement: "authored", wireIds: ["0-0-0"],
          frame: { origin: [0,0,0], xAxis: [1,0,0], yAxis: [0,1,0],
            zAxis: [0,0,1] } },
        { side: 1, mechanism: 0, placement: "authored", wireIds: ["1-0-0"],
          frame: { origin: [5,0,0], xAxis: [1,0,0], yAxis: [0,1,0],
            zAxis: [0,0,-1] } },
      ],
      wires: [
        { id: "0-0-0", net_vertex: 0, reeveFactor: 1, spoolRadius: 0.05,
          route: [
            { origin: [0.1, 0, 0], xAxis: [1,0,0], yAxis: [0,1,0], owner: "body" },
            { origin: [0.9, 0, 0], xAxis: [1,0,0], yAxis: [0,1,0],
              owner: "reel", ownerReel: 1 },
          ] },
      ],
      // The anchor stamps, as the writer emits them from plugin 95a31af:
      // the body once under mechanism.anchor, a frame per machine here.
      // `placement` is the LABEL "instance", not a frame, which is the
      // trap the instances reader already fell into once.
      anchors: [
        { side: 0, mechanism: 0, placement: "instance", ref: "mechanism.anchor",
          permanence: "permanent", net_vertices: [0, 1, 2],
          frame: { origin: [1, 2, 3], xAxis: [1,0,0], yAxis: [0,1,0],
            zAxis: [0,0,1] } },
        { side: 1, mechanism: 0, placement: "instance", ref: null,
          permanence: "permanent", net_vertices: [3, 4],
          frame: { origin: [4, 5, 6], xAxis: [1,0,0], yAxis: [0,1,0],
            zAxis: [0,0,1] } },
        { side: 1, mechanism: 1, placement: "instance", ref: null,
          permanence: "permanent", net_vertices: "not a list" },
      ],
      somethingNew: [1, 2, 3],
    };
    const read = readMechanism(document);
    expect(read.ok === true, "the document reads");
    expect(read.parts.length === 5, "a frame, two reels, a motor and a tie");
    const kinds = read.parts.map((p) => p.kind).join(",");
    expect(kinds === "frame1,motor,reel,reel,tie",
      "kind comes from the KEY, in the table's own order: " + kinds);
    expect(read.parts.find((p) => p.kind === "reel").index === 0
      && read.parts.filter((p) => p.kind === "reel")[1].index === 1,
      "a reel states its own number, which is what ownerReel points at");
    const reel = read.parts.find((p) => p.kind === "reel");
    expect(reel.spins === true, "a reel spins");
    expect(reel.material === "timber/birch-pale-fine", "his ruling: birch reels");
    // THE WINDING RADIUS PER REEL. The writer measures each reel's own
    // (median perpendicular distance of the routing frames it owns from
    // its own axis) rather than sharing one bounding-box figure across
    // four -- the old global 0.030 matched nothing in the real file. A
    // reel that does not state one says so with null, so the studio can
    // fall back to measuring rather than inherit a neighbour's number.
    const reels = read.parts.filter((p) => p.kind === "reel");
    near(reels[1].windingRadius, 0.17, 1e-12, "the reel's stated winding radius");
    expect(reels[0].windingRadius === null,
      "a reel that states none says null, not a borrowed figure");

    // HIS TWO DECLARED FACTS, and their defaults. This document carries
    // neither key, as every file exported before 2026-09-09 does, so it
    // must read as his settled ruling: HE offsets the routing planes, so
    // what arrives is the centreline and the reader adds nothing. The
    // cable is 10 mm thick, read as a diameter.
    expect(read.routingFrameMeaning === "centreline",
      "a silent document means centreline, his ruling: " + read.routingFrameMeaning);
    // The LITERAL, not the constant: comparing the reader's output with
    // DEFAULT_CABLE_RADIUS moves both sides together and pins nothing,
    // which is how a mutation of the constant survived this line once.
    near(read.cableRadius, 0.02, 1e-12,
      "a file stating neither figure gets his settled 0.02 radius, not "
      + "the 0.01 he has since corrected");
    near(DEFAULT_CABLE_RADIUS, 0.02, 1e-12, "and that is what the constant says");
    const declared = readMechanism(Object.assign({}, document, {
      routingFrameMeaning: "Contact", cableThickness: 0.02 }));
    expect(declared.routingFrameMeaning === "contact",
      "a declaration is read, and case does not matter");
    near(declared.cableRadius, 0.01, 1e-12,
      "a file carrying only a thickness has it halved");
    // THE EXPLICIT RADIUS WINS over the thickness beside it. Both are
    // emitted from 2026-09-09, thickness exactly twice radius, because
    // this number was halved or doubled three times in a day and a lone
    // figure does not say which convention it follows. A reader that
    // halved the thickness regardless would draw at half size the moment
    // the two ever disagreed.
    const both = readMechanism(Object.assign({}, document, {
      cableRadius: 0.02, cableThickness: 0.04 }));
    near(both.cableRadius, 0.02, 1e-12, "the stated radius, not the halved thickness");
    const disagreeing = readMechanism(Object.assign({}, document, {
      cableRadius: 0.02, cableThickness: 0.5 }));
    near(disagreeing.cableRadius, 0.02, 1e-12,
      "and it still wins when the two disagree");
    // Both scale with the document's units like every other length.
    const inMillimetres = readMechanism(Object.assign({}, document, {
      lengthUnitToMetres: 0.001, cableRadius: 20 }));
    near(inMillimetres.cableRadius, 0.02, 1e-12, "a radius is a length");
    expect(!both.notes.some((n) => n.indexOf("cableRadius") >= 0
      || n.indexOf("cableThickness") >= 0
      || n.indexOf("routingFrameMeaning") >= 0),
      "no declared key is reported as one the reader does not use");
    const tie = read.parts.find((p) => p.kind === "tie");
    expect(tie.permanent === true,
      "the tie DECLARES its permanence and it is read, not inferred");
    expect(read.parts.find((p) => p.kind === "frame1").permanent === false,
      "and a temporary part declares that too");
    // Everything is in the body's LOCAL space, tie included, so every
    // part is stamped with each instance's placement: permanent means
    // "survives the strike", not "arrives pre-placed".
    expect(read.parts.every((p) => p.world === false),
      "no part arrives pre-placed in this shape");
    expect(read.parts.find((p) => p.kind === "motor").material
      === "metal/steel-powder-coated-black", "his ruling: black motors");

    expect(read.instances.length === 2, "both instances");
    expect(read.instances[1].mirrored === true,
      "side 1 is a reflection and is reported as one");

    expect(read.wires.length === 1, "the wire reads");
    expect(read.wires[0].netVertex === 0, "explicit net vertex, never inferred");
    expect(read.wires[0].route[1].owner === "reel", "owner survives");
    expect(read.wires[0].route[1].ownerReel === 1, "and which reel");
    // reeveFactor and spoolRadius ride on the BODY in this writer, not on
    // each wire, so the body's values stand in rather than the reader
    // inheriting a rule it has to know about.
    expect(read.wires[0].reeveFactor === 1, "reeve falls back to the body's");
    expect(Math.abs(read.wires[0].spoolRadius - 0.05) < 1e-9,
      "so does the spool radius");
    // The instance names the wires it carries, which is exact.
    expect(read.instances[0].wireIds.join() === "0-0-0",
      "an instance names its own wires");

    // An unknown key is REPORTED, because it is the earliest signal that
    // the layout moved -- which the contract says to expect.
    expect(read.notes.some((n) => n.indexOf("somethingNew") !== -1),
      "an unread key is named: " + JSON.stringify(read.notes));

    // A document it cannot read never throws: the studio must not go
    // blank because an exporter changed its mind.
    expect(readMechanism(null).ok === false, "null is refused politely");
    expect(readMechanism({ schema: "bench.mechanism/9" }).ok === false,
      "a future schema is refused politely");
    expect(readMechanism({ schema: "bench.mechanism/9" }).reason.length > 10,
      "and says why");

    // The older one-body shape still opens.
    const oneBody = readMechanism({ schema: "bench.mechanism/1",
      mechanism: { vertices: bodyGeom.vertices, faces: bodyGeom.faces } });
    expect(oneBody.parts.length === 1 && oneBody.parts[0].kind === "body",
      "a document with one authored body still reads");

    // A wire with no net vertex is named rather than guessed at.
    const noVertex = readMechanism({ schema: "bench.mechanism/1",
      wires: [{ id: "x", route: [] }] });
    expect(noVertex.wires[0].netVertex === null, "not invented");
    expect(noVertex.notes.some((n) => n.indexOf("net_vertex") !== -1),
      "and said out loud");

    // A renamed key is read AND reported, so a rename is visible rather
    // than silently absorbed.
    const renamed = readMechanism({ schema: "bench.mechanism/1",
      mechanism: { drums: [{ mesh: bodyGeom }] } });
    expect(renamed.parts.length === 1 && renamed.parts[0].kind === "reel",
      "drums are reels");
    expect(renamed.notes.some((n) => n.indexOf("drums") !== -1),
      "and the rename is named");

    // ---------- the checks the contract asks for ----------
    // The writer DERIVES net_vertex by matching wire order to anchor
    // order. A bad match lands the wire on a real vertex that is simply
    // the wrong one, with nothing on screen to show it, so the reader
    // re-checks and reports.
    const vertices = [0, 0, 0,  10, 0, 0];
    const wires = [{ id: "w", netVertex: 0, route: [
      { matrix: placementMatrix({ origin: [9.9, 0, 0], xAxis: [1,0,0],
        yAxis: [0,1,0] }) }] }];
    const complaints = checkNetVertices(wires, vertices, null);
    expect(complaints.length === 1, "the wrong vertex is caught");
    expect(complaints[0].nearest === 1, "and the right one named");

    // Merely closer is not enough: a wire leaves from a point near
    // several vertices and a small difference proves nothing.
    const tight = [0, 0, 0,  0.2, 0, 0];
    const near_ = [{ id: "w", netVertex: 0, route: [
      { matrix: placementMatrix({ origin: [0.11, 0, 0], xAxis: [1,0,0],
        yAxis: [0,1,0] }) }] }];
    expect(checkNetVertices(near_, tight, null).length === 0,
      "a marginal difference is not a complaint");

    // planes[0] is the net end by contract. Checked, not trusted.
    const backwards = [{ id: "b", netVertex: 0, route: [
      { matrix: placementMatrix({ origin: [9, 0, 0], xAxis: [1,0,0], yAxis: [0,1,0] }) },
      { matrix: placementMatrix({ origin: [1, 0, 0], xAxis: [1,0,0], yAxis: [0,1,0] }) },
    ] }];
    expect(checkRouteDirection(backwards, vertices).length === 1,
      "a reversed route is caught");
    const forwards = [{ id: "f", netVertex: 0, route: [
      { matrix: placementMatrix({ origin: [1, 0, 0], xAxis: [1,0,0], yAxis: [0,1,0] }) },
      { matrix: placementMatrix({ origin: [9, 0, 0], xAxis: [1,0,0], yAxis: [0,1,0] }) },
    ] }];
    expect(checkRouteDirection(forwards, vertices).length === 0,
      "a correct route is not");

    // ---------- the wire centreline ----------
    // Measured on the real file: a routing frame's origin sits ON the
    // drum surface, so the centreline is one wire radius further out,
    // radially from the drum axis; and a spool is sampled at five frames
    // a turn, so the arc between two frames is walked in steps rather
    // than cut by a chord.
    const drum = { origin: [0, 0, 0], direction: [0, 0, 1] };
    const at = (x, y, z, owner, reel) => ({
      matrix: placementMatrix({ origin: [x, y, z], xAxis: [1,0,0], yAxis: [0,1,0] }),
      owner, ownerReel: reel === undefined ? -1 : reel });
    const Rc = 0.05, deg = Math.PI / 180;
    const route = [
      at(-3, 0, 0, "body"),                     // the net end, straight run
      at(-1.5, 0, 0, "body"),
      at(Rc, 0, 0, "reel", 0),                  // on the drum at 0 degrees
      at(Rc * Math.cos(73.6 * deg), Rc * Math.sin(73.6 * deg), 0.005, "reel", 0),
      at(Rc * Math.cos(147.2 * deg), Rc * Math.sin(147.2 * deg), 0.010, "reel", 0),
    ];
    const wires_ = [{ route }];
    near(reelContactRadius(wires_, 0, drum), Rc, 1e-9,
      "the contact radius is what the frames say, not spoolRadius");
    expect(reelContactRadius(wires_, 5, drum) === null,
      "a reel no wire names has no contact radius");

    // The step counts are MEASURED floors, not free parameters: eight on a
    // spool brings the chord sag under 0.16 mm at R 0.05 and 73.6 degrees
    // a frame; the pulleys are sampled three to six times finer, so they
    // need fewer. A test that read these back from the constants adjusted
    // itself when they changed, which is not a test.
    expect(SPOOL_STEPS >= 8, "a spool span is walked in at least eight steps");
    expect(PULLEY_STEPS >= 4 && PULLEY_STEPS < SPOOL_STEPS,
      "a pulley span takes fewer steps than a spool's, and at least four");
    const line = wireCentreline(route, { 0: drum }, 0.02);
    // 5 frames plus (SPOOL_STEPS - 1) walked points on each of the two
    // spool spans.
    expect(line.length === 5 + 2 * (SPOOL_STEPS - 1),
      "spool spans are subdivided: got " + line.length);
    expect(line.every((p) => p.every(Number.isFinite)), "no NaN in the line");
    // Every point on the drum stands at Rc + wire radius from the axis.
    for (let i = 2; i < line.length; i++) {
      near(Math.hypot(line[i][0], line[i][1]), Rc + 0.02, 1e-9,
        "drum point " + i + " is one wire radius off the surface");
    }
    // The net end leaves the anchor untouched and the straight run ramps
    // toward the drum's offset.
    near(Math.hypot(line[0][0] + 3, line[0][1], line[0][2]), 0, 1e-12,
      "the first point is the frame origin itself");
    near(line[1][0], -1.5 + 0.01, 1e-9,
      "halfway along the run the offset is half the wire radius");
    // The walk follows the SIGNED angle, so it goes the short way round.
    const a0 = Math.atan2(line[2][1], line[2][0]);
    const a1 = Math.atan2(line[3][1], line[3][0]);
    near((a1 - a0) / deg, 73.6 / SPOOL_STEPS, 1e-6,
      "each step turns one eighth of the frame-to-frame angle");
    // The axial coordinate is walked too, so a helix stays a helix.
    near(line[2 + SPOOL_STEPS][2], 0.005, 1e-9, "axial position reaches the next frame");

    // A pulley (radius above the spool limit) takes fewer steps.
    const Rp = 0.2;
    const pulley = [
      at(Rp, 0, 0, "reel", 1),
      at(Rp * Math.cos(20 * deg), Rp * Math.sin(20 * deg), 0, "reel", 1),
    ];
    const pl = wireCentreline(pulley, { 1: drum }, 0.02);
    expect(pl.length === 2 + (PULLEY_STEPS - 1), "pulley spans take PULLEY_STEPS");

    // No axis for a reel: nothing invented, the frame is used as sent.
    const blind = wireCentreline(route, {}, 0.02);
    expect(blind.length === 5, "without axes there is nothing to subdivide");
    near(blind[2][0], Rc, 1e-12, "and nothing is offset");

    // ---------- the take-up, along the rib ----------
    // A little net: anchor 0 on the ground, a rim neighbour 5 also on the
    // ground, and a rib 0-1-2-3-4 rising over a crown to the far anchor 4.
    // The rib is what the reel shortens; the rim is not.
    const pose = [
      [0, 0, 0],      // 0 anchor
      [1, 0, 1],      // 1
      [2, 0, 1.6],    // 2 crown
      [3, 0, 1],      // 3
      [4, 0, 0],      // 4 far anchor
      [0, 1, 0],      // 5 rim neighbour of the anchor, level
      [4, 1, 0],      // 6 rim neighbour of the far anchor
    ];
    const net = [[0, 1], [1, 2], [2, 3], [3, 4], [0, 5], [4, 6]];
    const chain = ribChain(net, pose, 0);
    expect(chain.join() === "0,1,2,3,4",
      "the rib climbs from the anchor over the crown to the far anchor, "
      + "not along the rim: " + chain.join());
    const slack = chainLength(pose, chain);
    near(slack, 2 * Math.hypot(1, 1) + 2 * Math.hypot(1, 0.6), 1e-9, "its length");
    // Reeled in: the same chain measured on a tauter pose is shorter, and
    // the take-up formula turns positive on the difference.
    const taut = pose.map((v, i) => (i === 2 ? [2, 0, 1.2] : v));
    const shorter = chainLength(taut, chain);
    expect(shorter < slack, "a tauter rib is a shorter rib");
    expect(turnsFor(slack / 2, shorter / 2, 1, 0.05) > 0,
      "and the reel takes up wire for it");
    // An anchor with no edges is a chain of itself, not a crash.
    expect(ribChain([], pose, 0).join() === "0", "no edges, no rib");
    expect(chainLength(pose, [0]) === 0, "and no length");

    // ---------- the anchor stamps ----------
    // One body, many stamps: a hundred anchors cost one mesh. Until
    // 2026-09-09 the anchor was fused into the tension tie and travelled
    // as one permanent part drawn once, untransformed.
    expect(read.anchors.length === 2,
      "an anchor with no readable frame is refused, not placed at the "
      + "origin: " + read.anchors.length);
    expect(read.notes.some((n) => n.indexOf("anchor carried no readable") >= 0),
      "and it is reported rather than dropped in silence");
    near(read.anchors[0].matrix[12], 1, 1e-12, "the frame's own origin x");
    near(read.anchors[0].matrix[14], 3, 1e-12, "and its z");
    expect(read.anchors[0].ref === "mechanism.anchor", "the body it stamps");
    expect(read.anchors[1].ref === null,
      "and null when he has authored no body, which still leaves the "
      + "frames standing as a rail");
    expect(read.anchors[0].netVertices.join() === "0,1,2",
      "the net vertices its bank holds");
    expect(read.anchors[1].side === 1 && read.anchors[1].mechanism === 0,
      "side and mechanism pair with the instances");
    // The label must never be read as a frame.
    expect(!read.anchors.some((a) => a.matrix === null), "no null matrices survive");
    // A document with no anchors at all reads as none, not as a crash.
    const bare = readMechanism({ schema: "bench.mechanism/1",
      mechanism: { frame1: { vertices: bodyGeom.vertices, faces: bodyGeom.faces } } });
    expect(bare.ok === true && bare.anchors.length === 0,
      "a document carrying no anchors reads as none");

    // ---------- deriving where the machines stand ----------
    // Two springings of three, 16 m apart, the shape of his own study in
    // miniature. NOT grouped by edges: on his form document zero of 800
    // edges join two supports, so an edge walk returns 42 rows of one.
    const twoRows = [
      [-8, -0.15, 0], [-8, 0, 0], [-8, 0.15, 0],
      [8, -0.15, 0], [8, 0, 0], [8, 0.15, 0],
    ];
    const grouped = supportRows(twoRows);
    expect(grouped.length === 2, "two springings, not six: " + grouped.length);
    expect(grouped.every((r) => r.length === 3), "three supports each");
    expect(supportRows([[0, 0, 0]]).length === 1, "one support is one row");
    expect(supportRows([]).length === 0, "and none is none, not a crash");

    // The frame: Y away from the net, Z up, X their cross. Built by the
    // same rule for the authored machine and every derived one, so the
    // transform between them is a TURN and never a reflection -- which
    // is what stops the far side lighting from the inside.
    const f = outwardFrame([1, 2, 3], [-1, 0, 0]);
    near(f[12], 1, 1e-12, "the frame's origin");
    near(f[4], -1, 1e-12, "Y is outward");
    near(f[10], 1, 1e-12, "Z is up");
    near(f[0], 0, 1e-12, "X is Y cross Z");
    near(f[1], 1, 1e-12, "which points along the row");
    const det = (m4) => m4[0] * (m4[5] * m4[10] - m4[6] * m4[9])
      - m4[4] * (m4[1] * m4[10] - m4[2] * m4[9])
      + m4[8] * (m4[1] * m4[6] - m4[2] * m4[5]);
    near(det(f), 1, 1e-12, "a frame with no reflection in it");
    // OUTWARD IS A PLAN DIRECTION. A springing that climbs, or a net
    // centroid well above the ground -- his is at z 3.030 -- gives an
    // outward with a large z in it, and following that would stand the
    // machine on its nose while still looking like a valid frame.
    const leaning = outwardFrame([0, 0, 0], [-3, 0, 9]);
    near(leaning[6], 0, 1e-12, "Y stays in the ground plane");
    near(leaning[4], -1, 1e-12, "keeping only its plan direction");
    near(leaning[10], 1, 1e-12, "and Z is still the world's own up");
    near(det(outwardFrame([0, 0, 0], [1, 0, 0])), 1, 1e-12,
      "and the same on the opposite side");

    // betweenFrames carries source onto target exactly.
    const src = outwardFrame([1, 2, 3], [-1, 0, 0]);
    const dst = outwardFrame([-4, 5, 6], [0, 1, 0]);
    const between = betweenFrames(src, dst);
    near(det(between), 1, 1e-12, "a rigid turn, no reflection and no scale");
    const put = (m4, p) => [
      m4[0] * p[0] + m4[4] * p[1] + m4[8] * p[2] + m4[12],
      m4[1] * p[0] + m4[5] * p[1] + m4[9] * p[2] + m4[13],
      m4[2] * p[0] + m4[6] * p[1] + m4[10] * p[2] + m4[14],
    ];
    const moved = put(between, [1, 2, 3]);
    near(moved[0], -4, 1e-9, "the source origin lands on the target's");
    near(moved[1], 5, 1e-9, "y");
    near(moved[2], 6, 1e-9, "z");
    // A POINT OFF THE ORIGIN, which is what actually pins the rotation.
    // The translation is solved FROM the rotation, so mapping the origin
    // alone is satisfied by any rotation at all -- including a
    // transposed one, which is orthonormal and unit-determinant and
    // therefore passes every other check here.
    const along2 = (frame, k) => [frame[0] * k, frame[1] * k, frame[2] * k];
    const from = along2(src, 2);
    const to = along2(dst, 2);
    const off = put(between, [1 + from[0], 2 + from[1], 3 + from[2]]);
    near(off[0], -4 + to[0], 1e-9, "two metres along the source X ...");
    near(off[1], 5 + to[1], 1e-9, "... lands two along the target X");
    near(off[2], 6 + to[2], 1e-9, "z");

    // The whole derivation on the miniature: two rows of three, a bank
    // of three spools, so one machine a side.
    const spools = [[-9, -0.15, 1], [-9, 0, 1], [-9, 0.15, 1]];
    const placed = derivePlacements(twoRows, spools, [0, 0, 0]);
    expect(placed.instances.length === 2,
      "one machine a side: " + placed.instances.length);
    expect(placed.wires.length === 6, "one cable per support");
    expect(placed.instances.every((i) => i.mirrored === false),
      "neither side is a reflection");
    // The authored machine lands back on its own spools: the setback is
    // READ from where its body already stands against its own row, so
    // the side it was authored on is reproduced rather than moved.
    const home = placed.instances.find((i) => i.side === 0);
    const back = spools.map((s) => put(home.matrix, s));
    near(back[1][0], -9, 1e-9, "the authored machine is put back where it was");
    near(back[1][1], 0, 1e-9, "along the row too");
    // ORDERED ALONG THE ROW, so spool k pulls support k and no two
    // cables in a bank cross. Checked on a row that does NOT divide
    // evenly: reverse an even row and you get the same machines in the
    // other order, so it proves nothing.
    const four = [
      [-8, 0, 0], [-8, 0.15, 0], [-8, 0.3, 0], [-8, 0.45, 0],
      [8, 0, 0], [8, 0.15, 0],
    ];
    const run = derivePlacements(four, [[-9, 0, 1], [-9, 0.15, 1], [-9, 0.3, 1]],
      [0, 0, 0]);
    const first = run.instances.filter((i) => i.side === 0)
      .sort((a, b) => a.mechanism - b.mechanism);
    expect(first.length === 2, "four supports, a bank of three: two machines");
    expect(first[0].netVertices.join() === "0,1,2",
      "the first machine takes the first three ALONG the row: "
      + first[0].netVertices.join());
    expect(first[1].netVertices.join() === "3",
      "and the leftover is the last one, not the first: "
      + first[1].netVertices.join());

    // ONE ANCHOR PER SIDE. Param's correction on seeing the first
    // version: "It's one anchor per side, and the tension tie is fixed
    // to the anchor ... The anchor itself is just the shape of the skin
    // edge on the first row." So it is one welded body a springing, not
    // a pad in front of each machine, and what is derived is only where
    // it stands and which way it faces -- a rail for the body he
    // intends to author.
    expect(placed.anchors.length === placed.rows.length,
      "one anchor a SIDE, not one a machine: " + placed.anchors.length);
    const anchor = placed.anchors.find((a) => a.side === 0);
    expect(anchor.netVertices.length === 3,
      "and it holds the whole row, not one machine's bank: "
      + anchor.netVertices.length);
    const held = anchor.netVertices.map((i) => twoRows[i]);
    const heldCentre = held.reduce((a, q) => [a[0] + q[0] / held.length,
      a[1] + q[1] / held.length, a[2] + q[2] / held.length], [0, 0, 0]);
    near(anchor.matrix[12], heldCentre[0], 1e-9,
      "the anchor stands on the centre of the cables it holds");
    near(anchor.matrix[13], heldCentre[1], 1e-9, "along the row too");
    near(det(anchor.matrix), 1, 1e-12, "and with no reflection in it");
    // In FRONT of its machine: the machine stands back from the same
    // line, so the anchor is nearer the net by exactly the setback.
    const mine = placed.instances.find((i) => i.side === 0);
    const machineSpools = spools.map((s) => put(mine.matrix, s));
    const mc = machineSpools.reduce((a, q) => [a[0] + q[0] / machineSpools.length,
      a[1] + q[1] / machineSpools.length, 0], [0, 0, 0]);
    expect(Math.hypot(anchor.matrix[12], anchor.matrix[13])
      < Math.hypot(mc[0], mc[1]),
      "the anchor is nearer the net than the machines behind it");
    expect(anchor.ref === null,
      "a derived anchor names no body of its own");
    expect(placed.notes.some((n) => n.indexOf(" anchors") >= 0),
      "and the summary counts them beside the machines and the cables");

    // A bank bigger than the row still serves it, short-handed and said.
    const short = derivePlacements(twoRows, [[-9, 0, 1], [-9, 0.15, 1],
      [-9, 0.3, 1], [-9, 0.45, 1]], [0, 0, 0]);
    expect(short.instances.length === 2, "still one machine a side");
    expect(short.instances[0].short === true, "and it knows it is short-handed");
    expect(short.notes.some((n) => n.indexOf("does not divide evenly") >= 0),
      "and says so rather than dropping the leftover supports");
    expect(short.wires.length === 6, "no support goes unserved");
    expect(short.anchors.length === 2,
      "still one anchor a side however the row divides: " + short.anchors.length);
    // Nothing to work from is said, never guessed.
    expect(derivePlacements([[0, 0, 0]], spools, [0, 0, 0]).instances.length === 0,
      "one support is no springing");
    // Not an array at all: a study with no form document reaches here as
    // null, and the guard is the difference between a note and a throw
    // out of the build.
    for (const nothing of [null, undefined, "supports"]) {
      const bare = derivePlacements(nothing, spools, [0, 0, 0]);
      expect(bare && bare.instances.length === 0,
        "no supports means no machines, not a crash");
      expect(bare.notes.some((n) => n.indexOf("fewer than two supports") >= 0),
        "and it says which of the two inputs was missing");
    }
    expect(derivePlacements(twoRows, [], [0, 0, 0]).notes.some(
      (n) => n.indexOf("no reel axes") >= 0),
      "a mechanism with no spool line says so");

    console.log("ok");
""")


@needs_node
def test_the_reader_reads(tmp_path):
    script = tmp_path / "check.mjs"
    script.write_text(
        CHECK.replace("%MODULE%", json.dumps(MODULE.as_uri())),
        encoding="utf-8")
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ok" in result.stdout


def _part_block(source, port):
    """The one table entry for a port, as text."""
    assert 'key: "%s"' % port in source, port
    block = source[source.index('key: "%s"' % port):]
    return block[:block.index("}")]


@needs_node
def test_the_material_table_matches_his_rulings():
    """Param, 2026-09-09, on seeing every part in one flat grey: the
    anchor and tie in the principal bars' shiny dark metal, the frames in
    anodised aluminium (frame 2 lighter than frame 1 but darker than the
    grey he was looking at), NEMA-black motors, fine-grain timber ONLY on
    the reels, and metal everywhere else -- which moves the pulleys off
    the birch they had been sharing with the reels."""

    source = MODULE.read_text(encoding="utf-8")
    for port, material in (
            ("frame1", "metal/aluminium-mill-grey"),
            ("frame2", "metal/aluminium-mill-grey"),
            ("motors", "metal/steel-powder-coated-black"),
            ("reels", "timber/birch-pale-fine"),
            # "the others are metal": a sheave is not a timber part.
            ("pulleys", "metal/steel-brushed"),
            # "Shiny ish metalic, like we used for the principle line
            # bars, dark. This is for the anchor / tie."
            ("anchor", "metal/steel-polished-dark"),
            ("tensionTie", "metal/steel-polished-dark")):
        block = _part_block(source, port)
        assert material in block, "%s should wear %s" % (port, material)
    assert "timber/" not in _part_block(source, "pulleys"), (
        "the pulleys are metal now, not the reels' birch")


# His metal/aluminium-mill-grey, measured from the library's own
# colour.jpg: mean sRGB (156, 160, 165), 0.3511 linear luminance.
ALUMINIUM_ALBEDO = 0.3511

# The flat fallback grey he was looking at when he said "not as light as
# it is now", and again when he said the parts were all one colour.
FALLBACK_GREY = 0x8d9298


def _to_linear(byte):
    c = byte / 255.0
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _to_srgb_byte(linear):
    if linear <= 0.0031308:
        return round(255 * 12.92 * linear)
    return round(255 * (1.055 * linear ** (1 / 2.4) - 0.055))


def _rendered(tint, albedo=ALUMINIUM_ALBEDO):
    """What a tint actually LANDS at, as an sRGB byte: three.js multiplies
    the tint into the albedo map in linear space, so the rendered grey is
    the product of the two and never the tint on its own."""
    grey = ((tint >> 16) & 255) * 0.2126 + ((tint >> 8) & 255) * 0.7152 \
        + (tint & 255) * 0.0722
    return _to_srgb_byte(albedo * _to_linear(grey))


@needs_node
def test_the_two_frames_are_one_aluminium_under_two_depths_of_coat():
    """"the aluminium frames are a anodised aluminium coated, a dark grey
    if we can, make the frame 2 a lighter grey but not as light as it is
    now." Anodising is a coat over the same mill aluminium, so the two
    frames share a set and differ only by tint.

    The tint MULTIPLIES the albedo, and the first pass at these numbers
    picked them as though they were the finished colours. Against a 0.3511
    albedo that rendered frame 1 at about sRGB 46 -- near black, on a part
    he had asked to be dark GREY -- and he came back with "the color
    scheme changed again, needs fixing". So this checks where the tints
    LAND, which is the thing he can see, rather than what they are."""

    source = MODULE.read_text(encoding="utf-8")
    one = _part_block(source, "frame1")
    two = _part_block(source, "frame2")
    assert "metal/aluminium-mill-grey" in one and "metal/aluminium-mill-grey" in two, (
        "one aluminium under both, so the grain agrees across the frames")
    tint = lambda block: int(
        block.split("tint: 0x")[1].split(",")[0].split("\n")[0].strip(), 16)
    dark, light = _rendered(tint(one)), _rendered(tint(two))
    assert dark < light, (
        "frame 2 must READ lighter than frame 1: %d vs %d" % (light, dark))
    assert light < _rendered(FALLBACK_GREY, 1.0), (
        "and still darker than the flat grey he called too light: "
        "%d against %d" % (light, _rendered(FALLBACK_GREY, 1.0)))
    # Dark GREY, not black. This is the assertion the first pass failed.
    assert dark > 70, (
        "frame 1 renders at sRGB %d, which is a black frame, not the dark "
        "anodised grey he asked for" % dark)


@needs_node
def test_the_motors_are_black_but_not_a_hole_in_the_render():
    """"the motors are a deep black like a nema motor". A NEMA case is
    cast and powder coated: near-black, with enough left to catch an edge.
    Its library set is already dark (0.0270 linear), so the tint has very
    little room and is checked against that set rather than the
    aluminium's."""

    source = MODULE.read_text(encoding="utf-8")
    block = _part_block(source, "motors")
    assert "metal/steel-powder-coated-black" in block
    tint = int(block.split("tint: 0x")[1].split(",")[0].split("\n")[0].strip(), 16)
    landed = _rendered(tint, 0.0270)
    assert landed < 40, "a NEMA case is near-black: sRGB %d" % landed


def test_every_material_the_table_names_exists_in_his_library():
    """The fault that produced the flat-grey machine was a LOAD failure,
    not a naming one -- but a name with no folder behind it fails exactly
    the same way and looks identical on screen. His library is the
    authority, so the table is checked against it when it is reachable.

    Skipped rather than failed when the folder is not mounted: this pins
    the table against the real library on his machine without making the
    suite depend on a OneDrive path everywhere else."""

    import re
    settings = REPO / "bench" / "studio" / "settings.json"
    if not settings.exists():
        pytest.skip("no studio settings to name the library folder")
    folder = json.loads(settings.read_text(encoding="utf-8")).get("material_folder")
    if not folder or not Path(folder).is_dir():
        pytest.skip("his material library folder is not mounted here")
    root = Path(folder)
    source = MODULE.read_text(encoding="utf-8")
    named = set(re.findall(r'material: "([^"]+)"', source))
    assert named, "the table names materials"
    for key in sorted(named):
        family, _, name = key.partition("/")
        assert (root / family / name).is_dir(), (
            "%s is named in PART_KINDS but is not in %s" % (key, folder))


REAL_STUDY = r"""
import { readFileSync } from "node:fs";
import {
  supportRows, derivePlacements,
} from %MODULE%;

const fail = (m) => { console.log("FAIL: " + m); process.exit(1); };
const near = (a, b, tol, what) => {
  if (!(Math.abs(a - b) <= tol)) fail(what + ": " + a + " vs " + b);
};

const form = JSON.parse(readFileSync(%FORM%, "utf-8"));
const mech = JSON.parse(readFileSync(%MECH%, "utf-8"));
const eq = form.equilibrium;
const ids = eq.resolvedSupportNodeIds;
const supports = ids.map((i) => {
  const v = eq.vertices[i];
  return [v.x, v.y, v.z];
});
const n = eq.vertices.length;
const centre = eq.vertices.reduce(
  (a, v) => [a[0] + v.x / n, a[1] + v.y / n, a[2] + v.z / n], [0, 0, 0]);

// A spool, not a pulley. His reels arrive under one key.
const reels = mech.mechanism.reels || [];
const stated = reels.map((r) => r.windingRadius)
  .filter((v) => typeof v === "number");
const spools = reels.filter((r) => {
  const v = r.windingRadius;
  return typeof v === "number" ? v < 0.1 : stated.length === 0;
}).map((r) => r.axis.origin);

// ZERO of his 800 edges join two supports, which is why the rows cannot
// be walked and must be grouped by their own spacing.
const support = new Set(ids);
const joined = eq.edges.filter((e) => support.has(e.u) && support.has(e.v)).length;
if (joined !== 0) fail("edges joining two supports: " + joined);

const rows = supportRows(supports);
if (rows.length !== 2) fail("springings: " + rows.length);
if (!rows.every((r) => r.length === supports.length / 2)) {
  fail("row sizes: " + rows.map((r) => r.length).join(","));
}

const out = derivePlacements(supports, spools, centre);
const perMachine = spools.length;
const want = Math.ceil(supports.length / 2 / perMachine) * 2;
if (out.instances.length !== want) {
  fail("machines: " + out.instances.length + " wanted " + want);
}
if (out.wires.length !== supports.length) {
  fail("cables: " + out.wires.length + " wanted " + supports.length);
}
if (out.instances.some((i) => i.mirrored)) fail("a side came out mirrored");

const put = (m4, p) => [
  m4[0] * p[0] + m4[4] * p[1] + m4[8] * p[2] + m4[12],
  m4[1] * p[0] + m4[5] * p[1] + m4[9] * p[2] + m4[13],
  m4[2] * p[0] + m4[6] * p[1] + m4[10] * p[2] + m4[14],
];
const det = (m4) => m4[0] * (m4[5] * m4[10] - m4[6] * m4[9])
  - m4[4] * (m4[1] * m4[10] - m4[2] * m4[9])
  + m4[8] * (m4[1] * m4[6] - m4[2] * m4[5]);

// THE MACHINE HE AUTHORED MUST LAND BACK ON ITSELF. The setback is read
// from where that body already stands against its own springing, so the
// side it was authored on is reproduced rather than moved, and the rest
// are derived from it.
const home = spools.reduce((a, q) => [a[0] + q[0] / spools.length,
  a[1] + q[1] / spools.length, a[2] + q[2] / spools.length], [0, 0, 0]);
let best = Infinity;
for (const inst of out.instances) {
  near(det(inst.matrix), 1, 1e-9, "a placement with a reflection in it");
  const moved = spools.map((s) => put(inst.matrix, s));
  const c = moved.reduce((a, q) => [a[0] + q[0] / moved.length,
    a[1] + q[1] / moved.length, a[2] + q[2] / moved.length], [0, 0, 0]);
  best = Math.min(best, Math.hypot(c[0] - home[0], c[1] - home[1], c[2] - home[2]));
}
near(best, 0, 1e-6, "the authored machine is not put back where he authored it");
console.log("ok " + out.instances.length + " machines, "
  + out.wires.length + " cables, " + rows.length + " springings");
"""


@needs_node
def test_the_derivation_reproduces_his_own_placement(tmp_path):
    """The whole derivation, against his real study rather than a fixture.

    His authored export carried six machines of seven cables. This asks
    the derivation for the same answer from the same study's supports,
    and for the machine HE authored to land back on its own spool centre
    -- which it must, because the setback is read from where that body
    already stands against its own springing.

    Skipped when the export is not mounted, the shape the material
    library test already uses: it pins the derivation against the real
    thing on his machine without making the suite depend on a path that
    exists nowhere else.
    """

    settings = REPO / "bench" / "studio" / "settings.json"
    if not settings.exists():
        pytest.skip("no studio settings to name the export folder")
    folder = json.loads(settings.read_text(encoding="utf-8")).get("upload_folder")
    if not folder or not Path(folder).is_dir():
        pytest.skip("his export folder is not mounted here")
    root = Path(folder)
    pairs = [(p, root / p.name.replace("-mechanism.json", "-form.json"))
             for p in sorted(root.glob("*-mechanism.json"))]
    pairs = [(mech, form) for mech, form in pairs if form.is_file()]
    if not pairs:
        pytest.skip("no study in the folder carries both a form and a mechanism")
    mech, form = pairs[0]
    script = tmp_path / "real.mjs"
    script.write_text(
        REAL_STUDY.replace("%MODULE%", json.dumps(MODULE.as_uri()))
        .replace("%FORM%", json.dumps(str(form)))
        .replace("%MECH%", json.dumps(str(mech))),
        encoding="utf-8")
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=300)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ok " in result.stdout, result.stdout


# ---------- the route ----------
# Reuses test_app's own client so the mechanism route is exercised through
# the real application, with the real folder scan, rather than by calling
# the function.

fastapi = pytest.importorskip("fastapi")

from test_app import make_client  # noqa: E402


def _write(upload_dir, name, payload):
    (upload_dir / name).write_text(json.dumps(payload), encoding="utf-8")


def test_a_study_without_a_machine_says_so_rather_than_failing(tmp_path, monkeypatch):
    """A 404 here is an ordinary state of the world: most studies carry no
    machine, and the client reads any non-200 as "no machine" and loads
    the study exactly as before."""

    client, _ = make_client(tmp_path, monkeypatch)
    response = client.get("/api/studies/Tiny/mechanism")
    assert response.status_code == 404
    assert "carries no mechanism document" in response.json()["detail"]

    missing = client.get("/api/studies/Nothing/mechanism")
    assert missing.status_code == 404
    assert "no export named" in missing.json()["detail"]


def _citing_study(extra=None):
    document = {
        "schema": "bench.mechanism/1",
        "machine": {"schema": "bench.machine/1", "id": "winch 7"},
        "mechanism": {"tensionTie": {"vertices": [[0, 0, 0]], "faces": []}},
    }
    document.update(extra or {})
    return document


def _machine_file(ident="winch 7"):
    return {"schema": "bench.machine/1", "id": ident,
            "machine": {"frame1": {"vertices": [[0, 0, 0]], "faces": []}}}


def test_the_machine_comes_back_verbatim(tmp_path, monkeypatch):
    """Unshaped on purpose. The key layout is expected to move again, and
    a server that understood those keys would need a restart every time it
    did -- mid-session, while Param is exporting and looking. The cited
    machine is folded in, and nothing else is touched."""

    client, _ = make_client(tmp_path, monkeypatch)
    import bundle
    _write(bundle.UPLOAD_DIR, "Tiny-mechanism.json",
           _citing_study({"aKeyInventedTomorrow": [1, 2, 3]}))
    _write(bundle.UPLOAD_DIR, "winch 7-machine.json", _machine_file())
    body = client.get("/api/studies/Tiny/mechanism").json()
    assert "frame1" in body["mechanism"] and "tensionTie" in body["mechanism"]
    assert body["aKeyInventedTomorrow"] == [1, 2, 3], (
        "a key this reader has never heard of must still reach the client")
    assert body["lengthUnitToMetres"] == 1.0, "the scale is resolved once, here"


def test_a_mechanism_from_before_the_machine_split_is_not_read(tmp_path, monkeypatch):
    """ONE FORMAT (Param, 2026-09-15): "we will use this export as one whole
    format now". A mechanism that cites no machine is the old combined shape,
    and it is refused by name so the vault loads bare and says to re-export,
    rather than wearing a machine from before the split."""

    client, _ = make_client(tmp_path, monkeypatch)
    import bundle
    _write(bundle.UPLOAD_DIR, "Tiny-mechanism.json",
           {"schema": "bench.mechanism/1",
            "mechanism": {"frame1": {"vertices": [[0, 0, 0]], "faces": []}}})
    response = client.get("/api/studies/Tiny/mechanism")
    assert response.status_code == 404
    assert "re-export" in response.json()["detail"]


def test_the_machine_is_read_only_from_beside_the_vault(tmp_path, monkeypatch):
    """"I want it to take the mechanism i provide it when giving the form in
    and thats what it should use." The cited machine is read from beside the
    vault's own mechanism document and from nowhere else; a machine of that
    id anywhere else does not stand in, and a missing one is named."""

    client, _ = make_client(tmp_path, monkeypatch)
    import bundle
    _write(bundle.UPLOAD_DIR, "Tiny-mechanism.json", _citing_study())
    elsewhere = tmp_path / "somewhere else"
    elsewhere.mkdir()
    _write(elsewhere, "winch 7-machine.json", _machine_file())
    missing = client.get("/api/studies/Tiny/mechanism")
    assert missing.status_code == 404
    assert "winch 7-machine.json" in missing.json()["detail"]
    _write(bundle.UPLOAD_DIR, "winch 7-machine.json", _machine_file("winch 8"))
    wrong = client.get("/api/studies/Tiny/mechanism")
    assert wrong.status_code == 404 and "winch 8" in wrong.json()["detail"]


def test_an_unusable_machine_document_names_its_own_fault(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    import bundle
    _write(bundle.UPLOAD_DIR, "Tiny-mechanism.json",
           {"schema": "bench.mechanism/7"})
    response = client.get("/api/studies/Tiny/mechanism")
    assert response.status_code == 404
    detail = response.json()["detail"]
    assert "unusable" in detail and "bench.mechanism/7" in detail


def test_the_machine_file_is_not_mistaken_for_a_study(tmp_path, monkeypatch):
    """It sits beside form, skin and formwork in the same folder the study
    list scans. Before it joined the known suffixes it fell through to the
    loose scan, which READS every unrecognised JSON to decide whether it
    is a contract -- a real cost at seven routing wires of 200 frames."""

    client, _ = make_client(tmp_path, monkeypatch)
    import bundle
    _write(bundle.UPLOAD_DIR, "Tiny-mechanism.json",
           {"schema": "bench.mechanism/1"})
    studies = client.get("/api/studies").json()["studies"]
    names = [row["export"] for row in studies]
    assert names == ["Tiny"], "the machine file is not a study of its own"

    import geometry
    assert "-mechanism.json" in geometry.KIND_SUFFIXES, (
        "so the loose scan skips it without reading it")
    assert "-machine.json" in geometry.KIND_SUFFIXES, (
        "and a machine filed beside the vaults is skipped the same way")


# ---------- the machine a study cites (plugin, 2026-09-15) ----------
# Since the machine split, a study's mechanism document carries no machine
# bodies: it cites a bench.machine/1 document by id, and Export files that
# machine as <id>-machine.json beside the study's own mechanism file. The
# server folds the machine's parts back in, so the reader sees a whole
# mechanism exactly as it always has.

_TRIANGLE = {"vertices": [[0, 0, 0], [1, 0, 0], [0, 1, 0]], "faces": [[0, 1, 2]]}


def _study_citing(ident="winch-7"):
    return {
        "schema": "bench.mechanism/1",
        "lengthUnitToMetres": 1,
        "machine": {"schema": "bench.machine/1", "id": ident, "name": ident,
                    "wireCount": 7},
        "mechanism": {"tensionTie": dict(_TRIANGLE, permanence="permanent")},
        "instances": [],
        "wires": [],
    }


def _machine_document(ident="winch-7"):
    return {
        "schema": "bench.machine/1",
        "id": ident,
        "lengthUnitToMetres": 1,
        "machine": {
            "frame1": _TRIANGLE,
            "reels": [{"reel": 0, "mesh": _TRIANGLE, "windingRadius": 0.05,
                       "bodies": []}],
            # A key the study owns as well: the study's own must win.
            "tensionTie": {"vertices": [[9, 9, 9]], "faces": []},
        },
    }


def test_a_study_takes_its_parts_from_the_machine_it_cites():
    merged = mechanism.merge_cited_machine(_study_citing(), _machine_document())
    body = merged["mechanism"]
    assert "frame1" in body and "reels" in body, "the machine's parts are folded in"
    assert body["tensionTie"]["vertices"][0] == [0, 0, 0], (
        "the study's own tie wins over anything the machine carries under that key")
    assert merged["machineResolution"] == {"id": "winch-7", "found": True}
    assert mechanism.cited_machine_id(_machine_document()) is None, (
        "a machine document cites nothing")


def test_a_machine_of_another_id_or_schema_is_refused():
    with pytest.raises(ValueError, match="winch-8"):
        mechanism.merge_cited_machine(_study_citing(), _machine_document("winch-8"))
    wrong = _machine_document()
    wrong["schema"] = "bench.mechanism/1"
    with pytest.raises(ValueError, match="bench.machine/1"):
        mechanism.merge_cited_machine(_study_citing(), wrong)
    scaled = _machine_document()
    scaled["lengthUnitToMetres"] = 0.001
    with pytest.raises(ValueError, match="scale"):
        mechanism.merge_cited_machine(_study_citing(), scaled)


READ_BODIES = textwrap.dedent("""
    import { readMechanism } from %MODULE%;
    const tri = { vertices: [[0,0,0],[1,0,0],[0,1,0]], faces: [[0,1,2]] };
    const plane = (x) => ({ origin: [x,0,0], xAxis: [1,0,0], yAxis: [0,1,0], zAxis: [0,0,1] });
    const identity = [1,0,0, 0,1,0, 0,0,1];
    const doc = {
      schema: "bench.mechanism/1", lengthUnitToMetres: 1,
      machine: { schema: "bench.machine/1", id: "winch-7" },
      machineResolution: { id: "winch-7", found: true },
      mechanism: { reels: [
        { reel: 0, mesh: tri, windingRadius: 0.05, bodies: [
          { axis: plane(0), linear: identity, translation: [0,0,0], determinant: 1 },
          { axis: plane(2), linear: identity, translation: [2,0,0], determinant: 1 } ] },
        { reel: 1, mesh: tri, windingRadius: 0.2, bodies: [
          { axis: plane(5), linear: [0,-1,0, 1,0,0, 0,0,1], translation: [5,0,0], determinant: 1 } ] } ] },
      instances: [], wires: [] };
    const fail = (message) => { console.log("FAIL " + message); process.exit(1); };
    const model = readMechanism(doc);
    const reels = model.parts.filter((part) => part.kind === "reel");
    if (reels.length !== 3) fail("three bodies are three reels, got " + reels.length);
    if (reels.map((r) => r.index).join() !== "0,1,2")
      fail("a reel's index is its BODY number, entry then body: " + reels.map((r) => r.index).join());
    if (Math.abs(reels[1].geometry.vertices[3] - 3) > 1e-12)
      fail("body 1 sits where its translation puts it: vertex 1 x is " + reels[1].geometry.vertices[3]);
    if (Math.abs(reels[2].geometry.vertices[3] - 5) > 1e-12 || Math.abs(reels[2].geometry.vertices[4] - 1) > 1e-12)
      fail("body 2 is turned by its linear part, row by row: vertex 1 is "
        + reels[2].geometry.vertices.slice(3, 6).join());
    if (Math.abs(reels[2].windingRadius - 0.2) > 1e-12) fail("a body winds at its entry's radius");
    if (!reels.every((r) => r.axis)) fail("every body carries its own axis");
    if (model.notes.some((note) => note.includes("does not use the key")))
      fail("the citation keys are read, not reported as unread: " + model.notes.join(" | "));
    const cabled = readMechanism({ ...doc, mechanism: { ...doc.mechanism,
      cables: { vertices: [[0,0,0],[1,0,0],[0,1,0]], faces: [[0,1,2]], permanence: "temporary" } } });
    const cables = cabled.parts.filter((part) => part.kind === "cable");
    if (cables.length !== 1 || cables[0].permanent)
      fail("his Cables (CB) mesh is one temporary cable part: " + JSON.stringify(cables.map((c) => c.permanent)));
    const missing = readMechanism({ ...doc, mechanism: {},
      machineResolution: { id: "winch-7", found: false, reason: "no winch-7-machine.json" } });
    if (!missing.notes.some((note) => note.includes("winch-7") && note.includes("not found")))
      fail("a machine that could not be found is said: " + missing.notes.join(" | "));
    console.log("ok");
""")


@needs_node
def test_reel_bodies_are_reels_numbered_the_way_wire_frames_name_them(tmp_path):
    script = tmp_path / "bodies.mjs"
    script.write_text(
        READ_BODIES.replace("%MODULE%", json.dumps(MODULE.as_uri())),
        encoding="utf-8")
    result = subprocess.run(
        ["node", str(script)], capture_output=True, text=True, timeout=60)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "ok" in result.stdout
