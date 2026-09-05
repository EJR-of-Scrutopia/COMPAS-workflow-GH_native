"""Recording behaves like pressing Play, and the take lands where the
animations live.

Param: "the record didnt do the motion or the rotation of camera as we see
when we play the animation." Diagnosed to the frame: recordAnimation drove
the timeline but never armed what startPlaying arms -- the timeline show
mode (without which applyShowMode erases every computed frame back to the
finished vault and hides the formwork act outright) and the orbit base
(without which applyTimeline leaves the camera still). A recording made
AFTER pressing Play looked fine, which is why the fault read as moody.

And: "as part of the animation the formwork when it grows and then becomes
its final form, can we have that part not rotate, only rotate after that."
The orbit clock is clamped to start when the opening act ends, in BOTH
writers of the angle, or a capture taken mid-take jumps the camera.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STUDIO = REPO / "bench" / "studio"
STATIC = STUDIO / "static"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import app as studio_app  # noqa: E402


def _record_body() -> str:
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    start = js.index("async function recordAnimation")
    return js[start:js.index('document.getElementById("record-button")', start)]


def test_recording_arms_what_play_arms():
    body = _record_body()
    assert 'state.showMode = "timeline"' in body, (
        "without the timeline show mode, applyShowMode rewrites every "
        "recorded frame back to the finished vault"
    )
    assert "captureOrbitBase(0)" in body, (
        "without an orbit base, applyTimeline never moves the camera"
    )
    # And the viewer's own mode comes back afterwards.
    assert "state.showMode = wasShowMode" in body


def test_the_orbit_waits_out_the_opening_act():
    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    apply_body = js[js.index("function applyTimeline"):]
    apply_body = apply_body[:apply_body.index("\n}")]
    clamp = "Math.max(0, t - openingSeconds())"
    assert clamp in apply_body, (
        "the growth into the final form keeps a still camera; the turn "
        "starts when build time begins"
    )
    capture_body = js[js.index("function captureOrbitBase"):]
    capture_body = capture_body[:capture_body.index("\n}")]
    assert "Math.max(0, reference - openingSeconds())" in capture_body, (
        "both writers of the angle must clamp the same clock, or a "
        "mid-take capture jumps the camera by the opening act's length"
    )


def test_a_finished_take_lands_in_the_animation_folder(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    target = tmp_path / "delivered"
    settings.write_text(
        '{"recordings_folder": "%s"}' % str(target).replace("\\", "\\\\"),
        encoding="utf-8")
    monkeypatch.setattr(studio_app, "SETTINGS_PATH", settings)
    video = tmp_path / "recording.mp4"
    video.write_bytes(b"not really a video")

    delivered = studio_app.deliver_recording("study-trial-2", video)

    assert delivered.parent == target
    assert delivered.name.startswith("trial-2-")
    assert delivered.suffix == ".mp4"
    assert delivered.read_bytes() == b"not really a video"
    assert video.exists(), "the repo copy stays as the fallback"


def test_an_unreachable_folder_does_not_lose_the_take(tmp_path, monkeypatch):
    settings = tmp_path / "settings.json"
    blocker = tmp_path / "a-file-not-a-folder"
    blocker.write_text("occupied", encoding="utf-8")
    impossible = blocker / "inside-a-file"
    settings.write_text(
        '{"recordings_folder": "%s"}' % str(impossible).replace("\\", "\\\\"),
        encoding="utf-8")
    monkeypatch.setattr(studio_app, "SETTINGS_PATH", settings)
    video = tmp_path / "recording.mp4"
    video.write_bytes(b"still here")

    delivered = studio_app.deliver_recording("study-trial-2", video)

    assert delivered == video, (
        "a failed delivery reports the copy that exists, not a path that "
        "was never written"
    )
