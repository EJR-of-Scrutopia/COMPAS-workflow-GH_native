from __future__ import annotations

import json
import re
import time
from pathlib import Path

import pytest

fastapi = pytest.importorskip("fastapi")
from fastapi.testclient import TestClient  # noqa: E402

from conftest_data import tiny_contract

REPO = Path(__file__).resolve().parents[2]


def make_client(tmp_path, monkeypatch, runner=None):
    import sys

    path = str(REPO / "bench" / "studio")
    if path not in sys.path:
        sys.path.insert(0, path)
    import app as app_module
    import bundle

    upload = tmp_path / "upload"
    studies = tmp_path / "studies"
    upload.mkdir(exist_ok=True)
    studies.mkdir(exist_ok=True)
    (upload / "Tiny-contract.json").write_text(
        json.dumps(tiny_contract()), encoding="utf-8"
    )
    (upload / "Tiny-compas.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(bundle, "UPLOAD_DIR", upload)
    monkeypatch.setattr(bundle, "STUDIES_DIR", studies)
    # HIS FOLDERS ARE OUT OF REACH OF EVERY TEST.
    #
    # deliver_recording copies each stitched take to RECORDINGS_DIR, and
    # RECORDINGS_DIR defaults to his real PhD Animation folder. A stitch
    # test with a faked ffmpeg therefore wrote a three-byte stub there on
    # every run, and 137 of them had accumulated before he found them and
    # asked why his animations folder was full of unplayable videos.
    #
    # SETTINGS_PATH goes with it: deliver_recording reads
    # recordings_folder from the settings file, so patching only the
    # default would still send a take wherever he had last pointed it.
    monkeypatch.setattr(app_module, "RECORDINGS_DIR", tmp_path / "recordings")
    monkeypatch.setattr(app_module, "SETTINGS_PATH", tmp_path / "settings.json")
    app_module.RUNS.clear()
    if runner is None:
        runner = lambda request: {"converged": True, "message": ""}
    return TestClient(app_module.create_app(
        runner=runner,
        cra_runner=lambda request: {
            "stands": True, "status": "optimal", "message": "",
            "blocks": len(request["blocks"]), "interfaces": 1,
            "mu": request["mu"]},
    )), studies


def wait_for(client, run_id, timeout=10.0):
    deadline = time.time() + timeout
    while time.time() < deadline:
        state = client.get("/api/runs/{}".format(run_id)).json()
        if state["state"] in ("done", "failed"):
            return state
        time.sleep(0.05)
    raise AssertionError("run never finished: {}".format(state))


def test_the_prop_layout_is_kept_beside_the_study(tmp_path, monkeypatch):
    """Browser storage holds five megabytes and a 25,375-prop field filled
    it: the write threw, and the throw came out of the undo that was
    taking the field away. The layout is kept beside the study as well,
    where it always fits, and a second device opens with it."""

    client, studies = make_client(tmp_path, monkeypatch)
    # None yet is an ordinary state, not an error in the console.
    assert client.get("/api/studies/Tiny/layout").status_code == 204
    layout = {
        "saved": 1789123456789,
        "layers": [{"id": 1, "name": "Layer 1", "visible": True}],
        "props": {"stride": 9, "types": ["stone_01"],
                  "rows": [0, 1.25, -2.5, 0, 0.7854, 0, 0, 1.1, 1], "extras": {}},
        "scatter": {"species": []},
    }
    assert client.put("/api/studies/Tiny/layout", json=layout).status_code == 200
    assert client.get("/api/studies/Tiny/layout").json() == layout
    assert (studies / "tiny" / "studio" / "layout.json").is_file()
    # Only for a study that exists, and only a layout that is one.
    assert client.put("/api/studies/Nobody/layout", json=layout).status_code == 404
    assert client.get("/api/studies/Nobody/layout").status_code == 404
    assert client.put("/api/studies/Tiny/layout", content=b"not json").status_code == 400
    assert client.put("/api/studies/Tiny/layout", json={"props": 3}).status_code == 400


def test_a_layout_beyond_its_bound_is_refused(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    monkeypatch.setattr(app_module, "MAX_LAYOUT_BYTES", 64)
    big = {"props": {"stride": 9, "types": [], "rows": [0] * 100}}
    assert client.put("/api/studies/Tiny/layout", json=big).status_code == 413


def bay_contract():
    """A 3x3 grid of unit quads with the (2, 1) face removed.

    The bay makes the plan genuinely not star shaped about its own axis --
    the same fixture shape as test_domain.py's grid(3, drop={(2, 1)}), here
    expressed as a full equilibrium/formGraph contract so it can drive the
    real bundle build. generators.generate refuses a plan like this, and
    that refusal has to reach the client as a 400, not a stack trace.
    """
    side, n = 3, 4
    verts = [
        {"x": float(i), "y": float(j), "z": 0.0}
        for j in range(n) for i in range(n)
    ]
    faces = []
    fid = 0
    for j in range(side):
        for i in range(side):
            if (i, j) == (2, 1):
                continue
            faces.append({
                "id": fid,
                "vertices": [
                    j * n + i, j * n + i + 1,
                    (j + 1) * n + i + 1, (j + 1) * n + i,
                ],
            })
            fid += 1
    edges = []
    for face in faces:
        v = face["vertices"]
        for k in range(4):
            edges.append({"u": v[k], "v": v[(k + 1) % 4]})
    return {
        "equilibrium": {
            "vertices": verts, "edges": edges, "loads": [],
            "resolvedSupportNodeIds": [0],
        },
        "formGraph": {"faces": faces},
    }


def authored_tiny_contract():
    """tiny_contract with an authored tessellation embedded in the contract
    itself, so build_bundle routes through tessellation.from_document
    instead of a generated pattern. An authored cut ignores the requested
    size entirely, so its target_size is None (see
    tessellation.build_tessellation).
    """
    contract = tiny_contract()
    contract["tessellation"] = {
        "schema": "bench.tessellation/1",
        "units": "m",
        "domain": "plan",
        "pattern": "authored",
        "cells": [
            {"key": "a", "course": 0,
             "outline": [[0, 0], [2, 0], [2, 2], [0, 2]]},
        ],
    }
    return contract


def test_studies_lists_the_export_and_ffmpeg_flag(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    payload = client.get("/api/studies").json()
    assert [s["export"] for s in payload["studies"]] == ["Tiny"]
    assert isinstance(payload["ffmpeg"], bool)


def test_bundle_endpoint_validates_and_serves(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    ok = client.get("/api/studies/Tiny/bundle", params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    assert ok.status_code == 200
    assert ok.json()["slug"] == "tiny"
    missing = client.get("/api/studies/Nope/bundle", params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    assert missing.status_code == 404
    assert "Tiny" in missing.json()["detail"]
    bad = client.get("/api/studies/Tiny/bundle",
                     params={"material": "adamantium", "pattern": "bonded-courses", "size": 0.9})
    assert bad.status_code == 400
    out_of_range = client.get("/api/studies/Tiny/bundle",
                              params={"material": "concrete", "pattern": "bonded-courses", "size": 9.0})
    assert out_of_range.status_code == 400


def test_a_plan_the_engine_refuses_opens_with_no_cut(tmp_path, monkeypatch):
    """A vault with a bay (re-entrant plan) is not star shaped, and no
    polar pattern can cover it.

    This used to be a 400: the message reached the user, but so did a
    study that would not open at all. That was the wrong failure. The
    voussoirs are only one of the things a study carries -- the net, the
    formwork and the machine are all independent of them -- and Param's
    2 Sided Vault is exactly the case: a barrel form whose plan rim turns
    back on itself, no skin document, and a machine he needs to look at.

    So the cut comes back EMPTY and carries the generator's own message.
    Nothing is invented, no piece is drawn, and the reason is on the
    document where the studio can show it.
    """
    client, _ = make_client(tmp_path, monkeypatch)
    upload = tmp_path / "upload"
    (upload / "Bay-contract.json").write_text(
        json.dumps(bay_contract()), encoding="utf-8"
    )
    (upload / "Bay-compas.json").write_text("{}", encoding="utf-8")
    response = client.get(
        "/api/studies/Bay/bundle",
        params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9},
    )
    assert response.status_code == 200, "the study opens"
    body = response.json()
    assert body["pieces"] == [], "and draws no voussoirs"
    refusal = body["tessellation"]["cut_refusal"]
    assert "not star shaped" in refusal
    assert "Author the tessellation in Grasshopper and import it instead" in refusal
    # The rest of the study is intact, which is the whole point.
    assert body["render_mesh"]["vertices"], "the surface still arrives"
    assert body["tessellation"]["cells"] == 0


def test_an_authored_bundles_size_round_trips_through_the_api(tmp_path, monkeypatch):
    """Task 8 fix round 1, C1: an authored cut ignores the requested size,
    so tess["target_size"] is None. The bundle's top level "size" field
    used to echo tess["target_size"] straight through (0.0 before the
    tessellation.py sentinel fix, None after it), and applyCut copied that
    poisoned value into state.size client side. The very next reload
    (a material switch, a thickness commit, anything that calls loadStudy
    again) sent that value back to this endpoint and got a 400, with no
    way out except dragging the size slider by hand.

    The top level "size" must be the REQUESTED size instead, which this
    endpoint is guaranteed to accept back: that is the round trip this
    test drives for real, through two live requests, not just a range
    check on the first response.
    """
    client, studies = make_client(tmp_path, monkeypatch)
    upload = tmp_path / "upload"
    (upload / "Authored-contract.json").write_text(
        json.dumps(authored_tiny_contract()), encoding="utf-8"
    )
    (upload / "Authored-compas.json").write_text("{}", encoding="utf-8")

    first = client.get(
        "/api/studies/Authored/bundle",
        params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9},
    )
    assert first.status_code == 200, first.json()
    document = first.json()
    assert document["tessellation"]["source"] == "imported"
    # The cut's own honest record: it truly has no target size, not one of
    # zero metres.
    assert document["tessellation"]["target_size"] is None
    round_tripped_size = document["size"]
    assert round_tripped_size == 0.9, (
        "the top level size must be the REQUESTED size, not the cut's own "
        "target_size"
    )

    second = client.get(
        "/api/studies/Authored/bundle",
        params={
            "material": "concrete", "pattern": "bonded-courses",
            "size": round_tripped_size,
        },
    )
    assert second.status_code == 200, (
        "the value the first response reported as the bundle's own size "
        "must be a value this same endpoint accepts back: {}".format(
            second.json() if second.headers.get("content-type", "").startswith(
                "application/json") else second.status_code
        )
    )


def test_run_lifecycle_reaches_done_and_embeds_staging(tmp_path, monkeypatch):
    client, studies = make_client(tmp_path, monkeypatch)
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete",
                                    "pattern": "bonded-courses", "size": 0.9})
    assert started.status_code == 202
    run_id = started.json()["run"]
    state = wait_for(client, run_id)
    assert state["state"] == "done", state["message"]
    assert (
        studies / "tiny" / "studio"
        / "staging-concrete-bonded-courses-s900-t200.json"
    ).is_file()
    document = client.get(
        "/api/studies/Tiny/bundle", params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9}
    ).json()
    assert document["staging"] is not None
    # Tiny (see conftest_data.tiny_contract) is small enough that at this
    # target size the whole plan is one course: see
    # tests/studio/test_staging.py for the pinned contract.
    assert len(document["staging"]["stages"]) == 1
    assert document["staging"]["size"] == 0.9


def test_bundle_url_is_percent_encoded_for_spaced_export_names(tmp_path, monkeypatch):
    """bundle_url must URL-encode the export path segment.

    'Trial 2' is a real export name in this repo; every spaced export must
    not leak a literal space into bundle_url, since that contradicts the
    documented output format ('Trial%202') and breaks naive URL joining on
    the client. This proves the encoding round-trips: the encoded bundle_url
    actually resolves through the same TestClient.
    """
    client, studies = make_client(tmp_path, monkeypatch)
    upload = tmp_path / "upload"
    (upload / "Tiny Two-contract.json").write_text(
        json.dumps(tiny_contract()), encoding="utf-8"
    )
    (upload / "Tiny Two-compas.json").write_text("{}", encoding="utf-8")

    started = client.post(
        "/api/runs", json={"export": "Tiny Two", "material": "concrete",
                            "pattern": "bonded-courses", "size": 0.9}
    )
    assert started.status_code == 202
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "done", state["message"]

    bundle_url = state["bundle_url"]
    assert "Tiny%20Two" in bundle_url
    assert " " not in bundle_url

    round_trip = client.get(bundle_url)
    assert round_trip.status_code == 200


def test_second_run_on_the_same_export_is_409(tmp_path, monkeypatch):
    import threading

    release = threading.Event()

    def slow_runner(request):
        release.wait(timeout=5)
        return {"converged": True, "message": ""}

    client, _ = make_client(tmp_path, monkeypatch, runner=slow_runner)
    first = client.post("/api/runs", json={"export": "Tiny", "material": "concrete",
                                    "pattern": "bonded-courses", "size": 0.9})
    assert first.status_code == 202
    second = client.post("/api/runs", json={"export": "Tiny", "material": "timber",
                                    "pattern": "bonded-courses", "size": 0.9})
    assert second.status_code == 409
    assert second.json()["run"] == first.json()["run"]
    release.set()
    wait_for(client, first.json()["run"])


def test_failed_staging_reports_failed_not_stuck(tmp_path, monkeypatch):
    def broken_runner(request):
        raise RuntimeError("the fea venv is on fire")

    client, _ = make_client(tmp_path, monkeypatch, runner=broken_runner)
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete",
                                    "pattern": "bonded-courses", "size": 0.9})
    state = wait_for(client, started.json()["run"])
    assert state["state"] == "failed"
    assert "on fire" in state["message"]


def test_frames_and_stitch_guardrails(tmp_path, monkeypatch):
    client, studies = make_client(tmp_path, monkeypatch)
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete",
                                    "pattern": "bonded-courses", "size": 0.9})
    run_id = started.json()["run"]
    wait_for(client, run_id)
    posted = client.post(
        "/api/frames/{}?frame=1".format(run_id),
        content=b"\x89PNG fake bytes",
        headers={"content-type": "application/octet-stream"},
    )
    assert posted.status_code == 200
    assert (studies / "tiny" / "studio" / "frames" / "frame-000001.png").is_file()
    assert client.post("/api/frames/nonsense?frame=1", content=b"x").status_code == 404


def test_posting_frame_one_clears_stale_frames_from_a_previous_recording(tmp_path, monkeypatch):
    """A shorter second recording must not inherit the first take's tail.

    frame-%06d.png accumulates in the same directory across recordings; if
    frame 1 does not clear it, a longer first take leaves frame-000047.png
    etc. behind, and ffmpeg silently stitches that stale tail into the new,
    shorter video. Posting frame 1 again is the recording-restart signal.
    """
    client, studies = make_client(tmp_path, monkeypatch)
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete",
                                    "pattern": "bonded-courses", "size": 0.9})
    run_id = started.json()["run"]
    wait_for(client, run_id)
    frames = studies / "tiny" / "studio" / "frames"

    for frame in (1, 2, 3):
        response = client.post(
            "/api/frames/{}?frame={}".format(run_id, frame),
            content="first take frame {}".format(frame).encode("utf-8"),
            headers={"content-type": "application/octet-stream"},
        )
        assert response.status_code == 200
    assert sorted(p.name for p in frames.glob("frame-*.png")) == [
        "frame-000001.png", "frame-000002.png", "frame-000003.png",
    ]

    second_take = client.post(
        "/api/frames/{}?frame=1".format(run_id),
        content=b"second take frame 1",
        headers={"content-type": "application/octet-stream"},
    )
    assert second_take.status_code == 200
    assert sorted(p.name for p in frames.glob("frame-*.png")) == ["frame-000001.png"]
    assert (frames / "frame-000001.png").read_bytes() == b"second take frame 1"

    # Stitch-guard behaviour is unchanged: still 404s with no frames, still
    # refuses when ffmpeg is missing, still stitches when both are present.
    assert client.post("/api/frames/nonsense/stitch").status_code == 404


def _mechanism(spool_radii, instances=0, wires=0, anchors=0, schema=None):
    """A mechanism document with a bank of spools of the given radii."""
    return {
        "schema": schema or "bench.mechanism/1",
        "lengthUnitToMetres": 1,
        "mechanism": {
            "frame1": {"vertices": [[0, 0, 0]], "faces": [[0, 0, 0]]},
            "reels": [{"reel": i, "windingRadius": r}
                      for i, r in enumerate(spool_radii)],
        },
        "instances": [{"side": 0, "mechanism": 0} for _ in range(instances)],
        "wires": [{"id": str(i)} for i in range(wires)],
        "anchors": [{"side": 0} for _ in range(anchors)],
    }


def test_the_mechanism_library_says_what_each_machine_is(tmp_path, monkeypatch):
    """Param: "the mechanism itself wants to become an asset, so add to
    import the mechanism as a drop down selection".

    A dropdown of bare study names says nothing about which machine suits
    which vault, so the listing carries the facts a choice is made on --
    above all the SPOOL count, since one machine pulls one bank.
    """

    import json as _json
    client, _studies = make_client(tmp_path, monkeypatch)
    import sys
    sys.path.insert(0, str(REPO / "bench" / "studio"))
    import bundle

    # Seven spools and three pulleys, exactly the shape of his real file:
    # they all arrive under `reels`, and only the winding radius separates
    # them.
    (bundle.UPLOAD_DIR / "Tiny-mechanism.json").write_text(
        _json.dumps(_mechanism([0.05] * 7 + [0.17, 0.2, 0.3],
                               instances=6, wires=42, anchors=6)),
        encoding="utf-8")
    (bundle.UPLOAD_DIR / "Five-mechanism.json").write_text(
        _json.dumps(_mechanism([0.05] * 5)), encoding="utf-8")
    (bundle.UPLOAD_DIR / "Broken-mechanism.json").write_text(
        "{not json", encoding="utf-8")

    rows = client.get("/api/mechanisms").json()["mechanisms"]
    by_name = {row["export"]: row for row in rows}
    assert sorted(by_name) == ["Broken", "Five", "Tiny"]

    tiny = by_name["Tiny"]
    assert tiny["spools"] == 7, "the pulleys are not part of the bank"
    assert tiny["reels"] == 10, "though they are still reels"
    assert tiny["instances"] == 6 and tiny["wires"] == 42 and tiny["anchors"] == 6
    assert "reels" in tiny["parts"] and "frame1" in tiny["parts"]
    assert tiny["ok"] is True

    assert by_name["Five"]["spools"] == 5

    # A REEL STATING NO WINDING RADIUS MEANS TWO DIFFERENT THINGS.
    #
    # When NO reel states one, the document predates the writer measuring
    # them and every reel is a drum.
    (bundle.UPLOAD_DIR / "Silent-mechanism.json").write_text(
        _json.dumps({
            "schema": "bench.mechanism/1", "lengthUnitToMetres": 1,
            "mechanism": {"reels": [{"reel": 0}, {"reel": 1}, {"reel": 2}]},
        }), encoding="utf-8")
    silent = {row["export"]: row
              for row in client.get("/api/mechanisms").json()["mechanisms"]}["Silent"]
    assert silent["spools"] == 3, "with none stated, every reel is a drum"
    assert silent["unstated"] == 0

    # When SOME state one and one does not, it cannot be placed and is not
    # counted. Measured on his real file: reels 0-6 wind at 0.033, reels 7
    # and 9 at 0.20 and 0.27, and reel 8 states null while sitting on the
    # PULLEYS' own axis. Counting it in gave a bank of eight for a machine
    # with seven spools, which would have chosen the wrong mechanism for
    # every study.
    (bundle.UPLOAD_DIR / "Partial-mechanism.json").write_text(
        _json.dumps({
            "schema": "bench.mechanism/1", "lengthUnitToMetres": 1,
            "mechanism": {"reels": [
                {"reel": 0, "windingRadius": 0.033},
                {"reel": 1, "windingRadius": 0.033},
                {"reel": 2, "windingRadius": 0.20},
                {"reel": 3, "windingRadius": None},
                # JSON true. In Python isinstance(True, int) is True, so
                # without a guard this reads as a radius of 1.0 -- not a
                # spool, and not reported as unplaceable either, which is
                # the worst of both: a reel that silently vanishes from
                # the count with nothing said about it.
                {"reel": 4, "windingRadius": True},
            ]},
        }), encoding="utf-8")
    partial = {row["export"]: row
               for row in client.get("/api/mechanisms").json()["mechanisms"]}["Partial"]
    assert partial["spools"] == 2, "the unstated reel is not counted into the bank"
    assert partial["unstated"] == 2, "and it is reported rather than absorbed"
    assert partial["reels"] == 5

    # A damaged mechanism is LISTED and says why, not skipped: it is his
    # work, and one that silently vanishes from the picker is worse than
    # one that cannot be chosen.
    assert by_name["Broken"]["ok"] is False
    assert by_name["Broken"]["reason"]
    assert by_name["Broken"]["spools"] == 0


def test_the_mechanisms_have_a_library_folder_of_their_own(tmp_path, monkeypatch):
    """Param: "Ok make a directory and export it there, I can then wire in
    other mechanisms there too."

    A mechanism stopped being a property of one vault the moment he wanted
    to choose between them, so it gets a root like the skins and the
    props. BOTH roots are read: a study's own mechanism, exported beside
    it, should not have to be filed anywhere to be usable.
    """

    import json as _json
    import sys
    sys.path.insert(0, str(REPO / "bench" / "studio"))
    import app as app_module
    import bundle

    client, _studies = make_client(tmp_path, monkeypatch)
    library = tmp_path / "machines"
    library.mkdir()
    monkeypatch.setattr(app_module, "MECHANISMS_DIR", library)

    (library / "Seven spool winch-mechanism.json").write_text(
        _json.dumps(_mechanism([0.05] * 7)), encoding="utf-8")
    (bundle.UPLOAD_DIR / "Tiny-mechanism.json").write_text(
        _json.dumps(_mechanism([0.05] * 3)), encoding="utf-8")

    # The folder reports itself the way every other library does.
    row = client.get("/api/mechanisms/folder").json()
    assert row["path"] == str(library)
    assert row["exists"] is True
    assert row["count"] == 1, "one machine filed, whatever sits beside the vaults"

    # And BOTH roots are listed.
    names = [r["export"] for r in client.get("/api/mechanisms").json()["mechanisms"]]
    assert names == ["Seven spool winch", "Tiny"], names


def test_the_folder_route_is_not_read_as_the_name_of_a_machine(tmp_path, monkeypatch):
    """/api/mechanisms/folder and /api/mechanisms/{name} share a prefix,
    and FastAPI matches in declaration order. With the name route first,
    "folder" is a machine nobody has -- a 404 on the control panel that
    looks like a broken folder rather than a routing mistake. The props
    and hdri routes are already arranged around this same trap."""

    client, _studies = make_client(tmp_path, monkeypatch)
    assert client.get("/api/mechanisms/folder").status_code == 200
    assert "path" in client.get("/api/mechanisms/folder").json()


def test_a_machine_is_fetched_by_name_from_either_root(tmp_path, monkeypatch):
    """Keyed by NAME rather than by study, because a machine in the
    library belongs to no study -- which is the whole point of the
    library. The library is read first, so a curated copy wins over one
    that happens to sit beside a vault under the same name."""

    import json as _json
    import sys
    sys.path.insert(0, str(REPO / "bench" / "studio"))
    import app as app_module
    import bundle

    client, _studies = make_client(tmp_path, monkeypatch)
    library = tmp_path / "machines"
    library.mkdir()
    monkeypatch.setattr(app_module, "MECHANISMS_DIR", library)

    (library / "Shared-mechanism.json").write_text(
        _json.dumps(_mechanism([0.05] * 7)), encoding="utf-8")
    (bundle.UPLOAD_DIR / "Shared-mechanism.json").write_text(
        _json.dumps(_mechanism([0.05] * 2)), encoding="utf-8")
    (bundle.UPLOAD_DIR / "Only-beside-a-vault-mechanism.json").write_text(
        _json.dumps(_mechanism([0.05] * 4)), encoding="utf-8")

    got = client.get("/api/mechanisms/Shared")
    assert got.status_code == 200
    assert len(got.json()["mechanism"]["reels"]) == 7, (
        "the library's copy wins over the one beside the vault")
    # A machine that lives only beside a vault is still reachable.
    beside = client.get("/api/mechanisms/Only-beside-a-vault")
    assert beside.status_code == 200
    assert len(beside.json()["mechanism"]["reels"]) == 4
    # And one that is nowhere says so.
    assert client.get("/api/mechanisms/Nothing").status_code == 404

    # A NAME CANNOT CLIMB OUT OF EITHER ROOT. A bare ".." proves nothing:
    # it names a file that is not there, so a 404 arrives with or without
    # a guard. An ENCODED separator is what the guard is actually for --
    # Starlette decodes %2F into the path parameter, so without the check
    # the name reaches the filesystem carrying a directory separator.
    outside = tmp_path / "outside-mechanism.json"
    outside.write_text(_json.dumps(_mechanism([0.05])), encoding="utf-8")
    for attempt in ("..%2Foutside", "..%5Coutside", "..%2F..%2Foutside"):
        got = client.get("/api/mechanisms/" + attempt)
        assert got.status_code in (400, 404), (attempt, got.status_code)
        assert "mechanism" not in got.json(), (
            "a name reached outside its root: " + attempt)


def test_the_mechanism_folder_is_remembered_between_runs(tmp_path, monkeypatch):
    """Every other library root survives a restart, and this one has to as
    well or he re-points it every morning. apply_saved_folders is the one
    that does it, and it is called by serve.py rather than by create_app,
    so it is exercised directly here."""

    import json as _json
    import sys
    sys.path.insert(0, str(REPO / "bench" / "studio"))
    import app as app_module

    library = tmp_path / "machines"
    library.mkdir()
    settings = tmp_path / "settings.json"
    settings.write_text(_json.dumps({"mechanism_folder": str(library)}),
                        encoding="utf-8")
    monkeypatch.setattr(app_module, "SETTINGS_PATH", settings)
    monkeypatch.setattr(app_module, "MECHANISMS_DIR", None)

    applied = app_module.apply_saved_folders()
    assert applied.get("mechanism_folder") == library
    assert app_module.MECHANISMS_DIR == library

    # A folder that has since gone is reported and left alone, not set to
    # a path that is not there.
    monkeypatch.setattr(app_module, "MECHANISMS_DIR", None)
    settings.write_text(_json.dumps({"mechanism_folder": str(tmp_path / "gone")}),
                        encoding="utf-8")
    assert "mechanism_folder" not in app_module.apply_saved_folders()
    assert app_module.MECHANISMS_DIR is None


def test_a_mechanism_summary_is_memoised_but_a_re_export_invalidates_it(
        tmp_path, monkeypatch):
    """His mechanism document is 25 MB, almost all of it vertices. Listing
    would be unusable if every call re-parsed every file, and stale if the
    memo never let go."""

    import json as _json
    client, _studies = make_client(tmp_path, monkeypatch)
    import sys
    sys.path.insert(0, str(REPO / "bench" / "studio"))
    import bundle

    path = bundle.UPLOAD_DIR / "Tiny-mechanism.json"
    path.write_text(_json.dumps(_mechanism([0.05] * 7)), encoding="utf-8")
    assert client.get("/api/mechanisms").json()["mechanisms"][0]["spools"] == 7

    # A re-export moves the mtime and changes the size, so the memo lets
    # go without anyone having to clear it.
    path.write_text(_json.dumps(_mechanism([0.05] * 3, wires=1)), encoding="utf-8")
    row = client.get("/api/mechanisms").json()["mechanisms"][0]
    assert row["spools"] == 3, "a re-export is seen"
    assert row["wires"] == 1


def test_a_mechanism_of_an_unsupported_schema_is_listed_not_hidden(
        tmp_path, monkeypatch):
    import json as _json
    client, _studies = make_client(tmp_path, monkeypatch)
    import sys
    sys.path.insert(0, str(REPO / "bench" / "studio"))
    import bundle

    (bundle.UPLOAD_DIR / "Future-mechanism.json").write_text(
        _json.dumps(_mechanism([0.05], schema="bench.mechanism/9")),
        encoding="utf-8")
    row = client.get("/api/mechanisms").json()["mechanisms"][0]
    assert row["ok"] is False
    assert "bench.mechanism/9" in row["reason"], row["reason"]


JPEG_MAGIC = b"\xff\xd8\xff"


def test_a_frame_is_named_after_its_own_bytes(tmp_path, monkeypatch):
    """Frames are JPEG from 2026-09-09 -- Param's take was running at over
    ten seconds a frame, and PNG's lossless deflate on a gravel ground was
    most of it.

    The extension follows the BYTES rather than the caller's word for
    them, because ffmpeg chooses its decoder from the file name: a JPEG
    written as .png stitches into nothing and says very little about why.
    """

    client, studies = make_client(tmp_path, monkeypatch)
    # The study directory has to exist before frames can land in it.
    client.get("/api/studies/Tiny/bundle", params={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    frames = studies / "tiny" / "studio" / "frames"
    post = lambda n, body: client.post(
        "/api/frames/study-tiny?frame={}".format(n), content=body,
        headers={"content-type": "application/octet-stream"})

    assert post(1, JPEG_MAGIC + b" fake jpeg").status_code == 200
    assert (frames / "frame-000001.jpg").is_file()
    assert not (frames / "frame-000001.png").exists()
    # Anything that is not a JPEG keeps the old name, so an older client
    # against a newer server still records.
    assert post(2, b"\x89PNG fake bytes").status_code == 200
    assert (frames / "frame-000002.png").is_file()


def test_frame_one_clears_the_other_format_too(tmp_path, monkeypatch):
    """A take that changed format must not stitch the previous take's
    frames. Clearing only the matching suffix would leave a full set of
    PNGs beside one JPEG, and the stitch would pick the PNGs -- silently
    producing the OLD video from a recording that appeared to succeed."""

    client, studies = make_client(tmp_path, monkeypatch)
    # The study directory has to exist before frames can land in it.
    client.get("/api/studies/Tiny/bundle", params={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    frames = studies / "tiny" / "studio" / "frames"
    post = lambda n, body: client.post(
        "/api/frames/study-tiny?frame={}".format(n), content=body,
        headers={"content-type": "application/octet-stream"})

    for n in (1, 2, 3):
        assert post(n, b"\x89PNG old take").status_code == 200
    assert len(list(frames.glob("frame-*.png"))) == 3

    assert post(1, JPEG_MAGIC + b" new take").status_code == 200
    assert sorted(p.name for p in frames.glob("frame-*")) == ["frame-000001.jpg"], (
        "the previous take's PNGs go, not just its JPEGs")

    # AND THE OTHER WAY ROUND, which is the direction that actually bites
    # now that JPEG is the default: a long JPEG take followed by a short
    # PNG one would otherwise stitch the old JPEGs, because the stitch
    # prefers .jpg when any are present.
    for n in (2, 3, 4):
        assert post(n, JPEG_MAGIC + b" jpeg take").status_code == 200
    assert len(list(frames.glob("frame-*.jpg"))) == 4
    assert post(1, b"\x89PNG later take").status_code == 200
    assert sorted(p.name for p in frames.glob("frame-*")) == ["frame-000001.png"], (
        "the previous take's JPEGs go too")


def test_the_stitch_reads_whichever_format_the_take_wrote(tmp_path, monkeypatch):
    """ffmpeg is handed a numbered pattern, not a glob, so the suffix has
    to be chosen from what is actually on disk. A folder left by an older
    PNG take is still stitchable rather than reported as empty."""

    import sys
    sys.path.insert(0, str(REPO / "bench" / "studio"))
    import app as app_module

    client, studies = make_client(tmp_path, monkeypatch)
    # The study directory has to exist before frames can land in it.
    client.get("/api/studies/Tiny/bundle", params={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    frames = studies / "tiny" / "studio" / "frames"
    seen = {}

    class Done:
        returncode = 0
        stderr = ""

    def fake_run(args, **kwargs):
        seen["input"] = args[args.index("-i") + 1]
        Path(args[-1]).write_bytes(b"mp4")
        return Done()

    monkeypatch.setattr(app_module, "_ffmpeg_present", lambda: True)
    monkeypatch.setattr(app_module.subprocess, "run", fake_run)

    # Nothing on disk is still a 404, not a stitch of nothing.
    assert client.post("/api/frames/study-tiny/stitch").status_code == 404

    client.post("/api/frames/study-tiny?frame=1", content=JPEG_MAGIC + b" x",
                headers={"content-type": "application/octet-stream"})
    assert client.post("/api/frames/study-tiny/stitch").status_code == 200
    assert seen["input"].endswith("frame-%06d.jpg"), seen["input"]

    # An older take's folder, PNG only.
    for path in frames.glob("frame-*"):
        path.unlink()
    (frames / "frame-000001.png").write_bytes(b"\x89PNG")
    assert client.post("/api/frames/study-tiny/stitch").status_code == 200
    assert seen["input"].endswith("frame-%06d.png"), seen["input"]


def test_no_test_can_reach_his_real_folders(tmp_path, monkeypatch):
    """The guard that should have existed before a faked ffmpeg wrote 137
    three-byte videos into his PhD Animation folder.

    deliver_recording copies each stitched take to RECORDINGS_DIR, whose
    default is that real folder, and reads recordings_folder from the
    settings file besides -- so patching only the default would still send
    a take wherever he had last pointed it."""

    import sys
    sys.path.insert(0, str(REPO / "bench" / "studio"))
    import app as app_module

    client, _studies = make_client(tmp_path, monkeypatch)
    assert tmp_path in Path(app_module.RECORDINGS_DIR).parents, (
        "RECORDINGS_DIR still points outside the test's own folder")
    assert tmp_path in Path(app_module.SETTINGS_PATH).parents, (
        "the settings file a test reads must be the test's own")
    # And the client is alive, so the guard has not broken the fixture.
    assert client.get("/api/studies").status_code == 200


def test_a_stitch_that_writes_no_video_says_so(tmp_path, monkeypatch):
    """His 2-sided-vault take left a recording.mp4 of ZERO BYTES beside
    3,617 frames. An empty file delivered under a stamped name is
    indistinguishable from a take that worked until he tries to play it,
    so a clean exit with no video is now a failure at the moment it
    happens rather than a discovery in a folder later."""

    import sys
    sys.path.insert(0, str(REPO / "bench" / "studio"))
    import app as app_module

    client, studies = make_client(tmp_path, monkeypatch)
    client.get("/api/studies/Tiny/bundle", params={
        "material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    client.post("/api/frames/study-tiny?frame=1", content=JPEG_MAGIC + b" x",
                headers={"content-type": "application/octet-stream"})

    class Done:
        returncode = 0
        stderr = ""

    def wrote_nothing(args, **kwargs):
        Path(args[-1]).write_bytes(b"")        # a clean exit, an empty file
        return Done()

    monkeypatch.setattr(app_module, "_ffmpeg_present", lambda: True)
    monkeypatch.setattr(app_module.subprocess, "run", wrote_nothing)
    failed = client.post("/api/frames/study-tiny/stitch")
    assert failed.status_code == 500
    assert "no video" in failed.json()["detail"]
    assert "frames are still in" in failed.json()["detail"], (
        "and it says where the frames are, so a long take is not lost")
    # Nothing was delivered under a stamped name.
    delivered = Path(app_module.RECORDINGS_DIR)
    assert not delivered.is_dir() or not list(delivered.glob("*.mp4"))


def test_the_recordings_have_an_output_folder(tmp_path, monkeypatch):
    """Param: "we need a recorder output folder button too to select where
    it gets directed." The setting existed and deliver_recording has
    always read it; what was missing was any way to see or change it."""

    import sys
    sys.path.insert(0, str(REPO / "bench" / "studio"))
    import app as app_module

    client, _studies = make_client(tmp_path, monkeypatch)
    where = tmp_path / "animations"
    where.mkdir()
    (where / "an-old-take.mp4").write_bytes(b"0" * 10)

    set_to = client.post("/api/recordings/folder", json={"path": str(where)})
    assert set_to.status_code == 200, set_to.text
    row = client.get("/api/recordings/folder").json()
    assert row["path"] == str(where)
    assert row["exists"] is True
    assert row["count"] == 1, "it counts the takes already there"
    assert Path(app_module.RECORDINGS_DIR) == where
    # And it is remembered, like every other folder.
    import json as _json
    stored = _json.loads(Path(app_module.SETTINGS_PATH).read_text(encoding="utf-8"))
    assert stored["recordings_folder"] == str(where)
    # A path that is not a folder is refused rather than silently kept.
    assert client.post("/api/recordings/folder",
                       json={"path": str(where / "nope")}).status_code == 400

    # AND IT SURVIVES A RESTART. Written is not applied: apply_saved_folders
    # is what points the roots at their remembered paths, and it is called
    # by serve.py rather than by create_app, so nothing else reaches it.
    monkeypatch.setattr(app_module, "RECORDINGS_DIR", tmp_path / "somewhere-else")
    applied = app_module.apply_saved_folders()
    assert applied.get("recordings_folder") == where
    assert Path(app_module.RECORDINGS_DIR) == where


def test_frames_accept_a_study_slug_without_a_run(tmp_path, monkeypatch):
    client, studies = make_client(tmp_path, monkeypatch)
    client.get("/api/studies/Tiny/bundle", params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    posted = client.post(
        "/api/frames/study-tiny?frame=3",
        content=b"png bytes",
        headers={"content-type": "application/octet-stream"},
    )
    assert posted.status_code == 200
    assert (studies / "tiny" / "studio" / "frames" / "frame-000003.png").is_file()
    assert client.post("/api/frames/study-nope?frame=1", content=b"x").status_code == 404
    # Path traversal in the slug must never resolve outside STUDIES_DIR. Either
    # the router rejects the encoded slash before frames_dir ever runs, or
    # frames_dir's own "/", "\\", ".." guard catches it first; both land as
    # 400 or 404, and either is acceptable as long as the guard exists.
    traversal_encoded = client.post("/api/frames/study-..%2F..?frame=1", content=b"x")
    assert traversal_encoded.status_code in (400, 404)
    traversal_plain = client.post("/api/frames/study-..?frame=1", content=b"x")
    assert traversal_plain.status_code in (400, 404)


def test_thickness_is_validated_and_reaches_the_bundle(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    ok = client.get("/api/studies/Tiny/bundle",
                    params={"material": "concrete", "pattern": "bonded-courses",
                            "size": 0.9, "thickness": 0.3})
    assert ok.status_code == 200
    assert ok.json()["provenance"]["thickness"] == 0.3
    bad = client.get("/api/studies/Tiny/bundle",
                     params={"material": "concrete", "pattern": "bonded-courses",
                             "size": 0.9, "thickness": 0.9})
    assert bad.status_code == 400
    run = client.post("/api/runs", json={
        "export": "Tiny", "material": "concrete", "pattern": "bonded-courses",
        "size": 0.9, "thickness": 0.3})
    assert run.status_code == 202
    state = wait_for(client, run.json()["run"])
    assert state["state"] == "done", state["message"]
    assert "thickness=0.3" in state["bundle_url"]


def test_column_files_are_listed_and_path_traversal_is_rejected(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    columns = tmp_path / "columns"
    columns.mkdir()
    (columns / "piers.json").write_text('{"vertices": [], "faces": []}', encoding="utf-8")
    monkeypatch.setattr(app_module, "COLUMNS_DIR", columns)
    assert client.get("/api/studies").json()["columns"] == ["piers.json"]
    assert client.get("/api/columns/piers.json").status_code == 200
    assert client.get("/api/columns/..%2Fsecrets.json").status_code in (400, 404)


def test_export_upload_stores_a_valid_pair_and_lists_it(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    body = json.dumps(tiny_contract()).encode()
    first = client.put("/api/uploads/exports/Fresh/contract", content=body)
    assert first.status_code == 200
    assert first.json()["pair_complete"] is False
    second = client.put("/api/uploads/exports/Fresh/compas",
                        content=b'{"thrustMesh": "{}"}')
    assert second.json()["pair_complete"] is True
    exports = [s["export"] for s in client.get("/api/studies").json()["studies"]]
    assert "Fresh" in exports


def test_export_upload_rejects_garbage_and_traversal(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    assert client.put("/api/uploads/exports/Bad/contract",
                      content=b"not json").status_code == 400
    assert client.put("/api/uploads/exports/Bad/contract",
                      content=b'{"no": "equilibrium"}').status_code == 400
    assert client.put("/api/uploads/exports/../evil/contract",
                      content=b"{}").status_code in (400, 404)
    assert client.put("/api/uploads/exports/Bad/nonsense",
                      content=b"{}").status_code == 400
    listed = [s["export"] for s in client.get("/api/studies").json()["studies"]]
    assert "Bad" not in listed


def test_reupload_with_changed_geometry_invalidates_bundle_and_staging_caches(tmp_path, monkeypatch):
    """C1: re-importing changed geometry under the same name must not keep
    serving the old cached bundle. GET a bundle (which caches it), run a
    staging pass (which caches that too), then re-upload the contract with
    a moved vertex; both caches must be gone, frames/recording must survive,
    and a fresh GET must show the new geometry."""
    client, studies = make_client(tmp_path, monkeypatch)
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete",
                                    "pattern": "bonded-courses", "size": 0.9})
    wait_for(client, started.json()["run"])

    studio_dir = studies / "tiny" / "studio"
    bundle_cache = studio_dir / "bundle-concrete-bonded-courses-s900-t200.json"
    staging_cache = studio_dir / "staging-concrete-bonded-courses-s900-t200.json"
    assert bundle_cache.is_file()
    assert staging_cache.is_file()

    frames_dir = studio_dir / "frames"
    frames_dir.mkdir(parents=True, exist_ok=True)
    (frames_dir / "frame-000001.png").write_bytes(b"kept")
    (studio_dir / "recording.mp4").write_bytes(b"kept")

    contract = tiny_contract()
    contract["equilibrium"]["vertices"][0]["z"] = 9.0
    reupload = client.put(
        "/api/uploads/exports/Tiny/contract", content=json.dumps(contract).encode()
    )
    assert reupload.status_code == 200

    assert not bundle_cache.is_file()
    assert not staging_cache.is_file()
    assert (frames_dir / "frame-000001.png").is_file()
    assert (studio_dir / "recording.mp4").is_file()

    fresh = client.get(
        "/api/studies/Tiny/bundle", params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9}
    )
    assert fresh.status_code == 200
    assert fresh.json()["analysis_mesh"]["vertices"][0][2] == 9.0


def test_upload_during_a_live_run_is_409(tmp_path, monkeypatch):
    """I1: uploading over an export name with a queued or running run must
    409 with the live run's id, mirroring start_run's own liveness check."""
    import threading

    release = threading.Event()

    def slow_runner(request):
        release.wait(timeout=5)
        return {"converged": True, "message": ""}

    client, _ = make_client(tmp_path, monkeypatch, runner=slow_runner)
    started = client.post("/api/runs", json={"export": "Tiny", "material": "concrete",
                                    "pattern": "bonded-courses", "size": 0.9})
    assert started.status_code == 202
    run_id = started.json()["run"]

    upload = client.put(
        "/api/uploads/exports/Tiny/contract", content=json.dumps(tiny_contract()).encode()
    )
    assert upload.status_code == 409
    assert upload.json()["run"] == run_id

    release.set()
    state = wait_for(client, run_id)
    assert state["state"] == "done", state["message"]


def test_export_upload_rejects_member_forces_edge_count_mismatch(tmp_path, monkeypatch):
    """I2: a contract-mode upload with memberForces that do not line up
    one-to-one with edges must be rejected 400, naming the mismatch, instead
    of importing green and 500ing on every subsequent view."""
    client, _ = make_client(tmp_path, monkeypatch)
    contract = tiny_contract()
    assert len(contract["equilibrium"]["edges"]) == 12
    contract["equilibrium"]["memberForces"] = [-2.0] * 5
    response = client.put(
        "/api/uploads/exports/Mismatch/contract", content=json.dumps(contract).encode()
    )
    assert response.status_code == 400
    assert "5" in response.json()["detail"]
    assert not (tmp_path / "upload" / "Mismatch-contract.json").is_file()
    listed = [s["export"] for s in client.get("/api/studies").json()["studies"]]
    assert "Mismatch" not in listed


def test_columns_upload_validates_shape(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    columns = tmp_path / "columns"
    columns.mkdir()
    monkeypatch.setattr(app_module, "COLUMNS_DIR", columns)
    good = client.put("/api/uploads/columns/piers.json",
                      content=b'{"vertices": [[0,0,0]], "faces": [[0,0,0]]}')
    assert good.status_code == 200
    assert (columns / "piers.json").is_file()
    assert client.put("/api/uploads/columns/junk.json",
                      content=b'{"nope": 1}').status_code == 400
    assert client.put("/api/uploads/columns/..%2Fx.json",
                      content=b"{}").status_code in (400, 404)


def test_size_out_of_range_is_rejected_by_name(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    response = client.get(
        "/api/studies/Tiny/bundle",
        params={"material": "concrete", "pattern": "bonded-courses",
                "size": 9.0, "thickness": 0.2},
    )
    assert response.status_code == 400
    # Re-pinned 2026-09-08: the floor dropped to 100 mm on his word ("I
    # would like to make the piece size go down to 100mm target"), so the
    # refusal names 0.1 now. Read from the module rather than typed, so
    # a later move of the floor cannot leave this sentence stale.
    from app import SIZE_MIN
    assert SIZE_MIN == 0.1, "his 100 mm target floor"
    assert str(SIZE_MIN) in response.json()["detail"]
    # The slider must reach as low as the server allows, or the floor
    # exists only in the API and he can never drag down to it.
    html = (Path(__file__).resolve().parents[2] / "bench" / "studio"
            / "static" / "index.html").read_text(encoding="utf-8")
    assert 'id="size-slider" type="range" min="{}"'.format(SIZE_MIN) in html
    # Same rule for thickness, widened on his word ("the thickness of
    # steel or copper on this scale probably can go down to 50mm or
    # less"): a metal shell is sheet, and the slider must reach what the
    # server allows or the floor exists only in the API.
    from app import THICKNESS_MIN, THICKNESS_MAX
    assert THICKNESS_MIN == 0.02 and THICKNESS_MAX == 0.5
    assert 'id="thickness-input" type="range" min="{}" max="{}"'.format(
        THICKNESS_MIN, THICKNESS_MAX) in html


def test_an_unknown_pattern_is_rejected_by_name(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    response = client.get(
        "/api/studies/Tiny/bundle",
        params={"material": "concrete", "pattern": "herringbone",
                "size": 0.9, "thickness": 0.2},
    )
    assert response.status_code == 400
    assert "bonded-courses" in response.json()["detail"]


def test_studies_lists_patterns_and_their_defaults(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    payload = client.get("/api/studies").json()
    assert "bonded-courses" in payload["patterns"]
    assert payload["pattern_defaults"]["concrete-sprayed"] == "monolithic-bands"
    assert "guastavino-herringbone" in payload["patterns_planned"]


def test_a_malformed_authored_tessellation_is_a_400_naming_the_cell(
    tmp_path, monkeypatch
):
    """The 400 contract must hold for a wrong container type too.

    from_document validated values by name but never the shape of the JSON
    it was handed, so a wrong container escaped as a bare AttributeError
    or TypeError. get_bundle catches only ValueError, and rightly so, so
    each of these answered 500 with no detail body: a Grasshopper author
    got neither the cell key nor which file to open, on the one route this
    whole feature is built around. The bad-units case is the control: that
    contract has always been kept.
    """
    client, _ = make_client(tmp_path, monkeypatch)
    upload = tmp_path / "upload"
    (upload / "Bad-compas.json").write_text("{}", encoding="utf-8")
    base = {
        "schema": "bench.tessellation/1", "units": "m", "domain": "plan",
        "pattern": "authored",
    }
    square = [[0, 0], [2, 0], [2, 2], [0, 2]]
    cases = [
        ("bad units, the control",
         dict(base, units="mm", cells=[{"key": "a", "course": 0,
                                        "outline": square}]), "mm"),
        ("a bare string among the cells", dict(base, cells=["oops"]), "cell 0"),
        ("a non-list outline",
         dict(base, cells=[{"key": "a", "course": 0, "outline": 7}]), "a"),
        ("non-list holes",
         dict(base, cells=[{"key": "a", "course": 0, "outline": square,
                            "holes": 5}]), "a"),
        ("a negative course",
         dict(base, cells=[{"key": "sunk", "course": -1,
                            "outline": square}]), "sunk"),
    ]
    for label, tess, expected in cases:
        contract = tiny_contract()
        contract["tessellation"] = tess
        (upload / "Bad-contract.json").write_text(
            json.dumps(contract), encoding="utf-8"
        )
        for stale in (tmp_path / "studies").glob("bad/studio/*.json"):
            stale.unlink()
        response = client.get(
            "/api/studies/Bad/bundle",
            params={"material": "concrete", "pattern": "bonded-courses",
                    "size": 0.9},
        )
        assert response.status_code == 400, "{}: got {} {!r}".format(
            label, response.status_code, response.text[:200])
        assert expected in response.json()["detail"], "{}: {}".format(
            label, response.json()["detail"])


def test_a_non_numeric_size_or_thickness_is_a_400_not_a_500(tmp_path, monkeypatch):
    """POST /api/runs coerced with float() before _validate ever ran.

    A missing size correctly gave 400 (float(0.0) then the range check),
    but a size the client typed as text and a null thickness both raised
    out of the coercion itself and answered 500. The body is a request
    the user can fix, so it is a 400 that says which field.
    """
    client, _ = make_client(tmp_path, monkeypatch)
    for body, expected in (
        ({"export": "Tiny", "material": "concrete",
          "pattern": "bonded-courses", "size": "abc"}, "size"),
        ({"export": "Tiny", "material": "concrete",
          "pattern": "bonded-courses", "size": 0.9, "thickness": None},
         "thickness"),
    ):
        response = client.post("/api/runs", json=body)
        assert response.status_code == 400, "{} gave {} {!r}".format(
            body, response.status_code, response.text[:200])
        assert expected in response.json()["detail"]
    # The range check still owns a number that is merely out of bounds.
    out_of_range = client.post("/api/runs", json={
        "export": "Tiny", "material": "concrete",
        "pattern": "bonded-courses", "size": 99.0})
    assert out_of_range.status_code == 400
    assert "between" in out_of_range.json()["detail"]


def test_a_run_reports_the_stage_count_and_says_what_it_is_doing(
    tmp_path, monkeypatch
):
    """run["of"] is 0 until the cut is known, which is the slow part.

    The count of stages comes from the cut, so it cannot be known when the
    run is created; what the server can do is say which phase it is in
    rather than leaving the reader with a bare "0/0". The run carries a
    phase from the moment it starts, and "of" is filled in the moment the
    first stage begins.
    """
    client, _ = make_client(tmp_path, monkeypatch)
    started = client.post("/api/runs", json={
        "export": "Tiny", "material": "concrete",
        "pattern": "bonded-courses", "size": 0.9})
    run_id = started.json()["run"]
    state = wait_for(client, run_id)
    assert state["state"] == "done", state
    assert state["of"] >= 1, "the stage count must be filled in once known"
    assert state["stage"] == state["of"]
    assert state["phase"] == "done"


def test_a_reupload_reports_the_authored_sidecar_that_will_keep_winning(
    tmp_path, monkeypatch
):
    """A sidecar survives a re-upload and keeps overriding the new cut.

    _invalidate_studio_cache drops bundle-*.json and staging-*.json, so a
    re-upload does force a re-cut, but the re-cut still reads the sidecar
    authored for the PREVIOUS geometry and quietly wins with it. Deleting
    the author's file here would be wrong; going silent about it is what
    was wrong. The route names it.
    """
    client, _ = make_client(tmp_path, monkeypatch)
    import bundle

    plain = client.put(
        "/api/uploads/exports/Tiny/contract",
        content=json.dumps(tiny_contract()).encode(),
    )
    assert plain.status_code == 200
    assert plain.json()["authored_tessellation"] is None

    bundle.tessellation_sidecar("Tiny").write_text(
        json.dumps({"schema": "bench.tessellation/1"}), encoding="utf-8"
    )
    again = client.put(
        "/api/uploads/exports/Tiny/contract",
        content=json.dumps(tiny_contract()).encode(),
    )
    assert again.status_code == 200
    assert again.json()["authored_tessellation"] == "Tiny-tessellation.json"


def test_hdri_list_upload_and_fetch(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    monkeypatch.setattr(app_module, "HDRI_DIR", tmp_path / "hdri")
    assert client.get("/api/hdri").json() == {"files": []}
    body = b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y 1 +X 1\n\x00\x00\x00\x00"
    response = client.put("/api/uploads/hdri/studio.hdr", content=body)
    assert response.status_code == 200
    assert response.json() == {"stored": "studio.hdr"}
    assert client.get("/api/hdri").json() == {"files": ["studio.hdr"]}
    fetched = client.get("/api/hdri/studio.hdr")
    assert fetched.status_code == 200
    assert fetched.content == body


def test_hdri_upload_rejections(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    monkeypatch.setattr(app_module, "HDRI_DIR", tmp_path / "hdri")
    wrong_ext = client.put("/api/uploads/hdri/notes.txt", content=b"#?RADIANCE")
    assert wrong_ext.status_code == 400
    wrong_magic = client.put("/api/uploads/hdri/fake.hdr", content=b"not radiance")
    assert wrong_magic.status_code == 400
    assert client.get("/api/hdri/missing.hdr").status_code == 404
    traversal = client.get("/api/hdri/..%5Capp.py")
    assert traversal.status_code in (400, 404)
    traversal_put = client.put(
        "/api/uploads/hdri/..%5Cevil.hdr", content=b"#?RADIANCE")
    assert traversal_put.status_code in (400, 404)
    assert not (tmp_path / "hdri").exists() or not list((tmp_path / "hdri").glob("*evil*"))
    assert not (tmp_path / "hdri" / "notes.txt").exists()
    assert not (tmp_path / "hdri" / "fake.hdr").exists()


def test_windows_drive_relative_names_cannot_escape(tmp_path, monkeypatch):
    """Task 5, defect table report 6/7 hardening: a Windows drive-relative
    name like 'C:evil.hdr' is not caught by a plain '/'/'\\'/'..' character
    guard, and Path's own join can replace the base directory entirely for
    such names. _contained() closes this on the hdri GET, hdri PUT and
    columns PUT routes."""
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    monkeypatch.setattr(app_module, "HDRI_DIR", tmp_path / "hdri")
    body = b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y 1 +X 1\n\x00\x00\x00\x00"
    assert client.put("/api/uploads/hdri/C:evil.hdr", content=body).status_code == 400
    # _contained() rejects the drive-relative name before any lookup runs,
    # so this is a guard failure every time, not a "maybe it 404s instead"
    # depending on what happens to sit at the resolved path.
    assert client.get("/api/hdri/C:app.py").status_code == 400
    assert not list(tmp_path.rglob("*evil*")), (
        "no file named for the drive-relative payload may exist anywhere "
        "under tmp_path"
    )
    assert client.put(
        "/api/uploads/columns/C:evil.json", content=b"{}").status_code == 400


def test_hdri_same_name_reupload_overwrites(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)
    import app as app_module

    monkeypatch.setattr(app_module, "HDRI_DIR", tmp_path / "hdri")
    head = b"#?RADIANCE\nFORMAT=32-bit_rle_rgbe\n\n-Y 1 +X 1\n"
    assert client.put("/api/uploads/hdri/a.hdr", content=head + b"\x01\x01\x01\x01").status_code == 200
    assert client.put("/api/uploads/hdri/a.hdr", content=head + b"\x02\x02\x02\x02").status_code == 200
    assert (tmp_path / "hdri" / "a.hdr").read_bytes().endswith(b"\x02\x02\x02\x02")


def test_export_reupload_serves_new_geometry(tmp_path, monkeypatch):
    client, _ = make_client(tmp_path, monkeypatch)

    first = client.get(
        "/api/studies/Tiny/bundle",
        params={"material": "concrete", "pattern": "bonded-courses",
                "size": 0.9, "thickness": 0.2},
    )
    assert first.status_code == 200
    tall = tiny_contract()
    # tiny_contract's vertices are a LIST of {"x", "y", "z"} dicts (see
    # conftest_data.tiny_contract), not a mapping keyed by id.
    for vertex in tall["equilibrium"]["vertices"]:
        vertex["z"] = vertex.get("z", 0.0) + 1.2
    put = client.put(
        "/api/uploads/exports/Tiny/contract", content=json.dumps(tall).encode())
    assert put.status_code == 200
    second = client.get(
        "/api/studies/Tiny/bundle",
        params={"material": "concrete", "pattern": "bonded-courses",
                "size": 0.9, "thickness": 0.2},
    )
    assert second.status_code == 200
    assert first.content != second.content, "a re-upload must serve the new geometry"


def _png(width, height, colour=(200, 120, 60, 255)):
    """A real PNG of one colour, because the endpoint checks the magic."""

    import io
    from PIL import Image
    out = io.BytesIO()
    Image.new("RGBA", (width, height), colour).save(out, format="PNG")
    return out.getvalue()


def test_a_still_keeps_its_own_folder_and_never_touches_a_take(tmp_path, monkeypatch):
    """post_frame deletes every frame in a study's frames folder when it
    is handed frame 1, on purpose. A still export that reused it would
    destroy a recording the first tile it sent. So stills live in
    studio/still and clear only their own."""

    client, studies = make_client(tmp_path, monkeypatch)
    client.get("/api/studies/Tiny/bundle", params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    # A take already on disk.
    client.post("/api/frames/study-tiny?frame=1", content=b"png bytes")
    client.post("/api/frames/study-tiny?frame=2", content=b"png bytes")
    frames = studies / "tiny" / "studio" / "frames"
    assert len(list(frames.glob("frame-*"))) == 2

    # A stale still from a previous, bigger plate.
    still = studies / "tiny" / "studio" / "still"
    still.mkdir(parents=True)
    (still / "tile-009-004096-000000.png").write_bytes(_png(4, 4))

    posted = client.post("/api/still/study-tiny?tile=0&x=0&y=0", content=_png(8, 8))
    assert posted.status_code == 200
    assert not (still / "tile-009-004096-000000.png").exists(), (
        "tile 0 clears the previous plate's tiles, or a smaller plate "
        "stitches the old one's right-hand tiles into its margin")
    assert len(list(frames.glob("frame-*"))) == 2, (
        "and the TAKE is untouched: that is the whole reason for a "
        "separate folder")

    # Not a PNG, not a tile.
    jpeg = client.post("/api/still/study-tiny?tile=1&x=8&y=0",
                       content=b"\xff\xd8\xff\xe0 jpeg bytes")
    assert jpeg.status_code == 400
    assert client.post("/api/still/study-nope?tile=0&x=0&y=0",
                       content=_png(8, 8)).status_code == 404


def test_a_stitch_takes_its_size_from_the_tiles_and_refuses_to_be_told_otherwise(tmp_path, monkeypatch):
    """A stitch that trusts the query can be told any size at all. A
    stray request for an 8 by 8 plate was served happily out of four
    2048 tiles, because those tiles genuinely cover an 8 by 8 rectangle,
    and it overwrote a finished 3840 by 2284 plate with a 181 byte
    thumbnail. Coverage was never the right question; agreement is."""

    from PIL import Image

    client, studies = make_client(tmp_path, monkeypatch)
    client.get("/api/studies/Tiny/bundle", params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    # A 24 by 16 plate in four uneven tiles, the way the browser cuts one.
    for index, (x, y, w, h) in enumerate(
            [(0, 0, 16, 12), (16, 0, 8, 12), (0, 12, 16, 4), (16, 12, 8, 4)]):
        r = client.post("/api/still/study-tiny?tile={}&x={}&y={}".format(index, x, y),
                        content=_png(w, h, (index * 60, 80, 90, 255)))
        assert r.status_code == 200

    wrong = client.post("/api/still/study-tiny/stitch?width=8&height=8")
    assert wrong.status_code == 409, wrong.text
    assert "24 by 16" in wrong.json()["detail"]

    right = client.post("/api/still/study-tiny/stitch?width=24&height=16")
    assert right.status_code == 200, right.text
    out = studies / "tiny" / "studio" / "still.png"
    assert out.is_file()
    with Image.open(out) as plate:
        assert plate.size == (24, 16)
        # Each tile's own colour where it was pasted, so the offsets in
        # the filenames were honoured and not merely trusted.
        assert plate.getpixel((0, 0))[0] == 0
        assert plate.getpixel((20, 0))[0] == 60
        assert plate.getpixel((0, 14))[0] == 120
        assert plate.getpixel((20, 14))[0] == 180

    # A missing tile is a hole, and a plate with a hole is refused. (The
    # plate above was whole, so its tiles are already gone; this one is
    # sent again without its third.)
    for index, (x, y, w, h) in enumerate(
            [(0, 0, 16, 12), (16, 0, 8, 12), (0, 12, 16, 4), (16, 12, 8, 4)]):
        if index == 2:
            continue
        client.post("/api/still/study-tiny?tile={}&x={}&y={}".format(index, x, y),
                    content=_png(w, h, (index * 60, 80, 90, 255)))
    holed = client.post("/api/still/study-tiny/stitch?width=24&height=16")
    assert holed.status_code == 500
    assert "never arrived" in holed.json()["detail"]
    assert client.post("/api/still/study-nope/stitch?width=1&height=1").status_code == 404


def test_a_stitch_heals_frames_whose_bytes_disagree_with_their_names(tmp_path, monkeypatch):
    """On 2026-09-09 a server started before the JPEG commit went on
    naming every frame .png while a freshly loaded client sent JPEG
    bytes. ffmpeg picks its decoder from the extension, refused all
    3,617 of them, exited 69 and wrote a zero-byte mp4. Two eleven-minute
    takes were lost that way and the next take's frame 1 deleted their
    frames. The same files renamed .jpg stitch in one pass."""

    client, studies = make_client(tmp_path, monkeypatch)
    client.get("/api/studies/Tiny/bundle", params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    frames = studies / "tiny" / "studio" / "frames"
    frames.mkdir(parents=True)
    # JPEG bytes under PNG names: the 09-09 residue, exactly.
    for n in (1, 2, 3):
        (frames / "frame-{:06d}.png".format(n)).write_bytes(b"\xff\xd8\xff\xe0 jpeg bytes")

    import app as studio_app
    healed = studio_app._heal_frame_names(frames, ".png")
    assert healed == ".jpg"
    assert sorted(p.name for p in frames.iterdir()) == [
        "frame-000001.jpg", "frame-000002.jpg", "frame-000003.jpg"]
    # Idempotent: a folder that is already right is left alone.
    assert studio_app._heal_frame_names(frames, ".jpg") == ".jpg"
    # And bytes it cannot name are left as they are rather than guessed.
    (frames / "frame-000004.jpg").write_bytes(b"who knows")
    assert studio_app._heal_frame_names(frames, ".jpg") == ".jpg"

    # The stitch endpoint calls it before ffmpeg: with ffmpeg absent it
    # must still have renamed, and say so with the 503's own path.
    monkeypatch.setattr(studio_app, "_ffmpeg_present", lambda: False)
    (frames / "frame-000005.png").write_bytes(b"\xff\xd8\xff\xe0 more")
    for stale in frames.glob("frame-*.jpg"):
        stale.unlink()
    r = client.post("/api/frames/study-tiny/stitch?fps=60")
    assert r.status_code == 503
    assert (frames / "frame-000005.jpg").is_file(), (
        "the stitch heals BEFORE it checks for ffmpeg, so the frames are "
        "right for whoever runs it by hand")


# ------------------------------------- the formwork route's graph passengers


def tiny_with_mould():
    """tiny_contract with the blocks the live graphs read: one force
    density per equilibrium edge (twelve) and a mould block of two column
    nodes joined by one member carrying one memberForce."""

    contract = tiny_contract()
    contract["equilibrium"]["forceDensities"] = [-0.5 * i for i in range(12)]
    contract["mould"] = {"columns": {
        "nodes": [{"x": 1.0, "y": 1.0, "z": 0.0}, {"x": 1.0, "y": 1.0, "z": 1.0}],
        "members": [{"u": 0, "v": 1}],
        "memberForce": [7.5],
    }}
    return contract


def tiny_frames(forces=None, column_forces=None, members=((0, 1),)):
    """A bench.frames/1 document that pairs with tiny_contract (its time-100
    frame is the solved net, its column nodes the mould's), with the
    optional series on every frame scaled by the frame's ordinal so each
    served frame can be told from the last. members=None leaves the
    document's columns block out, so the members come from the contract."""

    solved = [[v["x"], v["y"], v["z"]] for v in tiny_contract()["equilibrium"]["vertices"]]
    flat = [[x, y, 0.0] for x, y, _ in solved]
    frames = []
    schedule = ((0.0, "reel", 0.0), (30.0, "raise", 0.3), (60.0, "finish", 0.6),
                (90.0, "hold", 0.9), (100.0, "hold", 1.0))
    for ordinal, (time_, phase, u) in enumerate(schedule, start=1):
        frame = {
            "time": time_, "phase": phase,
            "vertices": solved if u == 1.0 else [
                [a[0], a[1], a[2] + (b[2] - a[2]) * u] for a, b in zip(flat, solved)],
            "columnNodes": [[1.0, 1.0, 0.0], [1.0, 1.0, u]],
        }
        if forces is not None:
            frame["forces"] = [value * ordinal for value in forces]
        if column_forces is not None:
            frame["columnForces"] = [value * ordinal for value in column_forces]
        frames.append(frame)
    document = {
        "schema": "bench.frames/1", "units": "m", "study": "Tiny",
        "vertexCount": len(solved), "columnNodeCount": 2, "frames": frames,
    }
    if members is not None:
        document["columns"] = {"members": [list(pair) for pair in members]}
    return document


def formwork_study(tmp_path, monkeypatch, contract, document):
    client, _ = make_client(tmp_path, monkeypatch)
    upload = tmp_path / "upload"
    (upload / "Tiny-contract.json").write_text(json.dumps(contract), encoding="utf-8")
    (upload / "Tiny-frames.json").write_text(json.dumps(document), encoding="utf-8")
    answer = client.get("/api/studies/Tiny/formwork")
    assert answer.status_code == 200, answer.text
    return answer.json()


def test_the_formwork_route_serves_per_frame_forces_that_fit_the_net(tmp_path, monkeypatch):
    """Spec section 10, the happy path: twelve forces for twelve edges and
    one column force for one member ride through on every frame, the
    contract's force densities come out beside the edges, and the mould's
    memberForce beside the members, all in the served order."""

    served = formwork_study(
        tmp_path, monkeypatch, tiny_with_mould(),
        tiny_frames(forces=[float(i) for i in range(12)], column_forces=[2.5]))
    assert served["notes"] == []
    assert [frame["forces"][11] for frame in served["frames"]] == [
        11.0, 22.0, 33.0, 44.0, 55.0]
    assert [frame["columnForces"] for frame in served["frames"]] == [
        [2.5], [5.0], [7.5], [10.0], [12.5]]
    assert served["forceDensities"] == [-0.5 * i for i in range(12)]
    assert served["columns"] == {
        "members": [[0, 1]], "forces": [7.5], "forceUnit": "kN"}
    assert len(served["edges"]) == 12


def test_forces_of_the_wrong_length_leave_every_frame_with_the_reason_served(
        tmp_path, monkeypatch):
    """Five values for twelve edges cannot be joined to anything: the key
    leaves every frame, the note says the two counts, and the column
    series, which does fit, is untouched. The act itself is unharmed."""

    served = formwork_study(
        tmp_path, monkeypatch, tiny_with_mould(),
        tiny_frames(forces=[1.0] * 5, column_forces=[2.5]))
    assert not any("forces" in frame for frame in served["frames"])
    assert all("columnForces" in frame for frame in served["frames"])
    assert "per-frame forces dropped: 5 values for 12 edges" in served["notes"]
    assert len(served["frames"]) == 5


def test_columns_forces_are_null_when_the_documents_members_are_not_the_contracts(
        tmp_path, monkeypatch):
    """The mould's memberForce is aligned with the CONTRACT's member list.
    A formwork document whose own members are the same legs in another
    order would have each force drawn on the wrong leg, so the forces are
    null and the note says why. A forceDensities list of the wrong length
    is null the same way."""

    contract = tiny_with_mould()
    contract["equilibrium"]["forceDensities"] = [1.0] * 11
    served = formwork_study(
        tmp_path, monkeypatch, contract, tiny_frames(members=((1, 0),)))
    assert served["columns"]["members"] == [[1, 0]]
    assert served["columns"]["forces"] is None
    assert served["forceDensities"] is None
    notes = " ".join(served["notes"])
    assert "not the contract's mould members in the same order" in notes
    assert "forceDensities absent" in notes


def test_every_series_is_filtered_to_the_served_pairs_by_raw_index(
        tmp_path, monkeypatch):
    """The served edges and members skip a pair whose end is out of range,
    so every series keyed on the raw lists (forceDensities, memberForce,
    the per-frame series) must be filtered by the SAME raw indices or the
    client would zip a twelve-long list against thirteen-long values and
    put every force one cable along. The members here come from the
    contract, the older document shape, so its forces are served."""

    contract = tiny_with_mould()
    contract["equilibrium"]["edges"].insert(0, {"u": 0, "v": 50})
    contract["equilibrium"]["forceDensities"] = [-99.0] + [-0.5 * i for i in range(12)]
    contract["mould"]["columns"]["members"] = [{"u": 0, "v": 9}, {"u": 0, "v": 1}]
    contract["mould"]["columns"]["memberForce"] = [99.0, 7.5]
    served = formwork_study(
        tmp_path, monkeypatch, contract,
        tiny_frames(members=None, forces=[99.0] + [float(i) for i in range(12)],
                    column_forces=[99.0, 2.5]))
    assert served["notes"] == []
    assert len(served["edges"]) == 12
    # The bundle's member forces are keyed on the raw list; the client
    # picks them through these, so cable i is the same cable in both.
    assert served["edgeIndices"] == list(range(1, 13))
    assert served["forceDensities"] == [-0.5 * i for i in range(12)]
    assert served["columns"] == {
        "members": [[0, 1]], "forces": [7.5], "forceUnit": "kN"}
    assert served["frames"][0]["forces"] == [float(i) for i in range(12)]
    assert served["frames"][0]["columnForces"] == [2.5]


def test_an_empty_series_and_a_plain_contract_serve_nothing_and_say_nothing(
        tmp_path, monkeypatch):
    """A writer with no column members that always writes the key sends
    columnForces: [] on every frame; served as present it drew a flat card
    of zeros captioned as the machine's own. An empty series is absent,
    silently, and a contract with no mould block at all has no column
    forces to be missing, so nothing is said about them either."""

    served = formwork_study(
        tmp_path, monkeypatch, tiny_contract(),
        tiny_frames(members=None, forces=[], column_forces=[]))
    assert not any("columnForces" in frame for frame in served["frames"])
    assert not any("forces" in frame for frame in served["frames"])
    assert served["notes"] == []
    assert served["columns"]["forces"] is None


def test_the_live_graphs_module_is_remapped_to_its_versioned_address(
        tmp_path, monkeypatch):
    """The import map is how a remote reload gets a fresh copy of each
    module studio.js imports; a module left out of the tuple is served
    from whatever the browser held, which is the stale-panel fault over
    again for the graphs."""

    client, _ = make_client(tmp_path, monkeypatch)
    page = client.get("/").text
    assert re.search(
        r'"/static/live_graphs\.js": "/static/live_graphs\.js\?v=[0-9a-f]{6,}"',
        page), "live_graphs.js must be remapped to its versioned address"


def test_the_atmosphere_module_is_remapped_to_its_versioned_address(
        tmp_path, monkeypatch):
    """The atmosphere's fog chunks live in their own module; a stale copy
    would put an old fog on a new page, so it is versioned like the rest."""

    client, _ = make_client(tmp_path, monkeypatch)
    page = client.get("/").text
    assert re.search(
        r'"/static/atmosphere\.js": "/static/atmosphere\.js\?v=[0-9a-f]{6,}"',
        page), "atmosphere.js must be remapped to its versioned address"


def test_a_still_goes_to_the_output_folder_and_leaves_no_tiles(tmp_path, monkeypatch):
    """Param, 2026-09-13: "the output folder for the image still is not
    taking the output folder we set, its got its own random location? the
    video and the stills should use the same output folder the one we
    select." And of the tiles left behind: "the still gave 2 un stitched
    images? This always must be one image no matter the resolution".

    The stitch was sound -- one 3840 by 1718 plate -- but it was written
    only into the study's studio folder, and its two tiles stayed in a
    folder beside it looking like the output."""

    import sys
    from PIL import Image
    sys.path.insert(0, str(REPO / "bench" / "studio"))
    import app as app_module

    client, studies = make_client(tmp_path, monkeypatch)
    # One stamp for every delivery here, so two plates DO share a second.
    monkeypatch.setattr(app_module.time, "strftime", lambda fmt: "20260913-120000")
    chosen = tmp_path / "captures"
    (tmp_path / "settings.json").write_text(
        json.dumps({"recordings_folder": str(chosen)}), encoding="utf-8")
    client.get("/api/studies/Tiny/bundle", params={"material": "concrete", "pattern": "bonded-courses", "size": 0.9})
    for index, (x, y, w, h) in enumerate([(0, 0, 16, 16), (16, 0, 8, 16)]):
        client.post("/api/still/study-tiny?tile={}&x={}&y={}".format(index, x, y),
                    content=_png(w, h, (index * 90, 80, 90, 255)))

    done = client.post("/api/still/study-tiny/stitch?width=24&height=16")
    assert done.status_code == 200, done.text
    delivered = Path(done.json()["still"])
    assert delivered.parent == chosen, (
        "the still goes where the takes go, and the readout names it there")
    assert delivered.name.startswith("tiny-still-24x16-") and delivered.suffix == ".png"
    with Image.open(delivered) as plate:
        assert plate.size == (24, 16), "ONE image, at the size asked for"
    assert not list((studies / "tiny" / "studio" / "still").glob("tile-*.png")), (
        "no tile outlives a whole plate")
    assert (studies / "tiny" / "studio" / "still.png").is_file(), (
        "the study keeps its own copy, as the takes do")

    # A second plate in the same second does not overwrite the first.
    for index, (x, y, w, h) in enumerate([(0, 0, 16, 16), (16, 0, 8, 16)]):
        client.post("/api/still/study-tiny?tile={}&x={}&y={}".format(index, x, y),
                    content=_png(w, h, (index * 90, 80, 90, 255)))
    again = Path(client.post("/api/still/study-tiny/stitch?width=24&height=16").json()["still"])
    assert again != delivered and delivered.is_file() and again.is_file()

    # And the folder button says it is for both.
    assert app_module.FOLDER_TITLES["recordings_folder"] == (
        "Choose where finished stills and recordings are saved")
