"""No JS runtime in CI, so pin what Python can see: files exist, the
importmap wires the vendored three, the page and app agree on element ids,
and the vendor files are the pinned build."""

from __future__ import annotations

import re
from pathlib import Path

STATIC = Path(__file__).resolve().parents[2] / "bench" / "studio" / "static"


def test_vendor_files_are_present_and_pinned():
    core = STATIC / "vendor" / "three.core.js"
    module = STATIC / "vendor" / "three.module.js"
    assert core.is_file() and core.stat().st_size > 100_000
    assert module.is_file()
    assert "185" in module.read_text(encoding="utf-8")[:20_000] or "185" in core.read_text(encoding="utf-8")[:20_000]
    assert (STATIC / "vendor" / "addons" / "controls" / "OrbitControls.js").is_file()
    assert (STATIC / "vendor" / "addons" / "environments" / "RoomEnvironment.js").is_file()


def test_index_wires_the_importmap_and_scripts():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    assert '"three"' in html and "vendor/three.module.js" in html
    assert "three/addons/" in html
    assert "studio.js" in html and "studio.css" in html


def test_no_external_urls_in_the_page_or_scripts():
    for name in ("index.html", "studio.js", "studio.css"):
        text = (STATIC / name).read_text(encoding="utf-8")
        assert not re.search(r"https?://", text), (
            "{} references the network; the studio must work offline".format(name)
        )


def test_binning_js_avoids_the_known_parity_traps():
    js = (STATIC / "binning.js").read_text(encoding="utf-8")
    assert "Math.round" not in js, "use floor(x + 0.5); Math.round differs from Python round at .5"
    assert "halfUp" in js
    assert "theta < 0" in js, "JS % keeps sign; the fold to [0, 2pi) must be explicit"
    assert "WEDGES_AT_RIM = 12" in js


def test_pbr_helpers_and_column_loader_exist():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for name in ("noiseTexture", "grainTexture", "columnGeometryFrom", "loadColumns"):
        assert name in js, "studio.js lost {}".format(name)
    assert "MeshPhysicalMaterial" in js
    assert "ACESFilmicToneMapping" in js


def test_the_timeline_is_a_pure_function_of_time():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "applyTimeline" in js and "timelineDuration" in js
    start = js.index("function applyTimeline")
    end = js.index("\n}", start)
    body = js[start:end]
    for clock in ("performance.now", "Date.now", "requestAnimationFrame"):
        assert clock not in body, (
            "applyTimeline reads {}; it must be pure in t or recording "
            "will not be deterministic".format(clock)
        )


def test_the_layer_registry_has_the_agreed_names():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    for name in ("stress", "deflection", "loads", "reactions", "overlays", "pulse", "wires"):
        assert '"{}"'.format(name) in js
    assert "layerAvailability" in js
    assert "no staging" in js or "staged run" in js, "disabled layers must say why"


def test_record_mode_is_frame_indexed_not_clock_driven():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert "recordAnimation" in js
    assert "frameIndex / fps" in js, "frames must come from applyTimeline(frame/fps)"
    assert "study-" in js
    assert "state.recording" in js


def test_thickness_control_is_wired_and_honest():
    html = (STATIC / "index.html").read_text(encoding="utf-8")
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    assert 'id="thickness-input"' in html and 'id="thickness-value"' in html
    assert "state.thickness" in js
    assert "thickness=" in js, "loadStudy must send the thickness parameter"
    assert "verified run used" in js, "the HUD must flag a thickness mismatch"
