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
    const document = {
      schema: "bench.mechanism/1",
      lengthUnitToMetres: 1,
      reels: [{ geometry: bodyGeom }, { geometry: bodyGeom }],
      motors: [{ geometry: bodyGeom }],
      anchors: [{ geometry: bodyGeom }],
      tensionTies: [{ geometry: bodyGeom }],
      instances: [
        { side: 0, mechanism: 0,
          placement: { origin: [0,0,0], xAxis: [1,0,0], yAxis: [0,1,0] } },
        { side: 1, mechanism: 0,
          placement: { origin: [5,0,0], xAxis: [1,0,0], yAxis: [0,1,0],
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
      somethingNew: [1, 2, 3],
    };
    const read = readMechanism(document);
    expect(read.ok === true, "the document reads");
    expect(read.parts.length === 5, "two reels, a motor, an anchor and a tie");
    const kinds = read.parts.map((p) => p.kind).join(",");
    expect(kinds === "motor,reel,reel,anchor,tie",
      "kind comes from the PORT, in the table's own order: " + kinds);
    const reel = read.parts.find((p) => p.kind === "reel");
    expect(reel.spins === true, "a reel spins");
    expect(reel.material === "timber/birch-pale-fine", "his ruling: birch reels");
    const anchor = read.parts.find((p) => p.kind === "anchor");
    expect(anchor.permanent === true && anchor.world === true,
      "the anchor is permanent and arrives pre-placed");
    const tie = read.parts.find((p) => p.kind === "tie");
    expect(tie.permanent === true, "so does the tension tie");
    expect(read.parts.find((p) => p.kind === "motor").material
      === "metal/steel-powder-coated-black", "his ruling: black motors");

    expect(read.instances.length === 2, "both instances");
    expect(read.instances[1].mirrored === true,
      "side 1 is a reflection and is reported as one");

    expect(read.wires.length === 1, "the wire reads");
    expect(read.wires[0].netVertex === 0, "explicit net vertex, never inferred");
    expect(read.wires[0].route[1].owner === "reel", "owner survives");
    expect(read.wires[0].route[1].ownerReel === 1, "and which reel");

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
      mechanism: { geometry: bodyGeom } });
    expect(oneBody.parts.length === 1 && oneBody.parts[0].kind === "body",
      "a document with one authored body still reads");

    // A wire with no net vertex is named rather than guessed at.
    const noVertex = readMechanism({ schema: "bench.mechanism/1",
      wires: [{ id: "x", route: [] }] });
    expect(noVertex.wires[0].netVertex === null, "not invented");
    expect(noVertex.notes.some((n) => n.indexOf("net_vertex") !== -1),
      "and said out loud");

    // A renamed port is read AND reported, so a rename is visible rather
    // than silently absorbed.
    const renamed = readMechanism({ schema: "bench.mechanism/1",
      drums: [{ geometry: bodyGeom }] });
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


@needs_node
def test_the_material_table_matches_his_rulings():
    """Param's answers, 2026-09-08: mill steel frames, black motors, birch
    reels, and the two permanent works in one dark anodised family."""

    source = MODULE.read_text(encoding="utf-8")
    for port, material in (
            ("frames1", "metal/steel-mill-grey"),
            ("frames2", "metal/steel-mill-grey"),
            ("motors", "metal/steel-powder-coated-black"),
            ("reels", "timber/birch-pale-fine"),
            ("pulleys", "timber/birch-pale-fine"),
            ("anchors", "metal/aluminium-mill-grey"),
            ("tensionTies", "metal/aluminium-mill-grey")):
        line = [row for row in source.splitlines()
                if 'port: "%s"' % port in row]
        assert line, port
        block = source[source.index('port: "%s"' % port):]
        block = block[:block.index("}")]
        assert material in block, "%s should wear %s" % (port, material)


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


def test_the_machine_comes_back_verbatim(tmp_path, monkeypatch):
    """Unshaped on purpose. The key layout is expected to move again, and
    a server that understood those keys would need a restart every time it
    did -- mid-session, while Param is exporting and looking."""

    client, _ = make_client(tmp_path, monkeypatch)
    import bundle
    document = {
        "schema": "bench.mechanism/1",
        "reels": [{"geometry": {"vertices": [[0, 0, 0]], "faces": []}}],
        "aKeyInventedTomorrow": [1, 2, 3],
    }
    _write(bundle.UPLOAD_DIR, "Tiny-mechanism.json", document)
    body = client.get("/api/studies/Tiny/mechanism").json()
    assert body["reels"] == document["reels"]
    assert body["aKeyInventedTomorrow"] == [1, 2, 3], (
        "a key this reader has never heard of must still reach the client")
    assert body["lengthUnitToMetres"] == 1.0, "the scale is resolved once, here"


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
