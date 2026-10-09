"""Run the formwork engine on the real 5 sided form export through the
studio's own routes, in process; print what it found and draw it (spec
2026-10-09 section 7). The images show the net at the end of the raise and
under the last course, coloured by tension and by how far it strays from the
designed form, and the worst figures capture by capture.

Usage, from the repo root under the solver interpreter:

    .venv/Scripts/python.exe bench/scripts/formwork_real.py
        [--study "5 sided form"] [--material tile] [--pattern bonded-courses]
        [--size 1.0] [--thickness 0.02] [--prestress 300] [--wires-per-motor 1]
        [--wall 3.2] [--images docs/superpowers/findings-images/2026-10-09-formwork]

The export folder is the one the studio remembers in bench/studio/settings.json.
The script reads it and writes only under bench/studies/ and the images folder.

Exits 2 when the export is not on this machine, 1 when the run fails.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "bench" / "studio"))
sys.path.insert(0, str(REPO / "src"))

IMAGES = REPO / "docs" / "superpowers" / "findings-images" / "2026-10-09-formwork"


def _where(capture):
    if capture["phase"] == "tiling":
        return "{} q{}".format(capture["row"], capture["quarter"])
    return "t {:g}".format(capture["time"])


def summary_lines(document):
    """What the run found, as lines to print: the headline figures, then one
    line a capture."""

    import numpy as np
    from solve_formwork import unpack

    summary = document["summary"]
    thinnest = document["trees"]["thinnest_wall"]
    lines = [
        "{} captures in {} s; the thinnest standard wall that holds every capture: {}".format(
            summary["captures"], document["seconds"],
            "none of them" if thinnest is None else "{:g} mm".format(thinnest)),
        "worst deviation from the designed form: {:.0f} mm at the end of the raise, {} under "
        "the last course".format(summary["raise_deviation_max_mm"],
                                  "no course" if summary["tiling_deviation_max_mm"] is None
                                  else "{:.0f} mm".format(summary["tiling_deviation_max_mm"])),
        "worst wire tension {:.0f} N; most a rim node is let out {:.2f} mm; worst tree "
        "utilisation {:.2f}; {} captures needed relaxation".format(
            summary["wire_tension_max_n"], summary["let_out_max_mm"],
            summary["tree_utilisation_max"], summary["relaxation_captures"]),
        "{:8} {:9} {:>9} {:>9} {:>9} {:>10} {:>6}  {}".format(
            "phase", "where", "dev mm", "wire N", "out mm", "head N", "tree", "solver"),
    ]
    for capture in document["captures"]:
        push = unpack(capture["head_push"])
        lines.append("{:8} {:9} {:9.0f} {:9.0f} {:9.2f} {:10.0f} {:6.2f}  {} {}".format(
            capture["phase"], _where(capture), float(unpack(capture["deviation"]).max()),
            float(unpack(capture["wire_tension"]).max(initial=0.0)),
            float(unpack(capture["let_out"]).max(initial=0.0)),
            float(np.linalg.norm(push, axis=1).max(initial=0.0)),
            float(unpack(capture["tree_utilisation"]).max(initial=0.0)),
            capture["solver"], capture["iterations"]))
    return lines


def render(document, folder):
    """The net at the end of the raise and under the last course, by tension and
    by deviation, over the designed form in grey, and the worst figures capture
    by capture. Returns the files written."""

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import numpy as np
    from mpl_toolkits.mplot3d.art3d import Line3DCollection
    from solve_formwork import unpack

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    edges = np.asarray(document["net"]["edges"], dtype=int)
    design = unpack(document["net"]["design"])
    captures = document["captures"]
    raised = [c for c in captures if c["phase"] != "tiling"]
    tiled = [c for c in captures if c["phase"] == "tiling"]
    chosen = [("end-of-raise", raised[-1])] + ([("last-course", tiled[-1])] if tiled else [])
    written = []
    for name, capture in chosen:
        x = unpack(capture["x"])
        deviation = unpack(capture["deviation"])
        for lens, values, label in (
                ("tension", unpack(capture["tension"]), "rope tension, N"),
                ("deviation", 0.5 * (deviation[edges[:, 0]] + deviation[edges[:, 1]]),
                 "distance from the designed form, mm")):
            figure = plt.figure(figsize=(10, 8))
            axes = figure.add_subplot(projection="3d")
            axes.add_collection3d(Line3DCollection(design[edges], colors="0.85", linewidths=0.4))
            lines = Line3DCollection(x[edges], cmap="viridis", linewidths=0.9)
            lines.set_array(values)
            axes.add_collection3d(lines)
            low, high = np.minimum(x.min(axis=0), design.min(axis=0)), np.maximum(
                x.max(axis=0), design.max(axis=0))
            axes.set_xlim(low[0], high[0])
            axes.set_ylim(low[1], high[1])
            axes.set_zlim(low[2], high[2])
            axes.set_box_aspect(high - low)
            axes.set_title("{}: {} ({}), the designed form in grey".format(
                document.get("study"), name.replace("-", " "), _where(capture)))
            figure.colorbar(lines, ax=axes, shrink=0.6, label=label)
            path = folder / "{}-{}.png".format(name, lens)
            figure.savefig(path, dpi=150)
            plt.close(figure)
            written.append(path)
    figure, panels = plt.subplots(3, 1, figsize=(11, 9), sharex=True)
    steps = list(range(len(captures)))
    for panel, field, label in ((panels[0], "deviation", "worst deviation, mm"),
                                (panels[1], "wire_tension", "worst wire tension, N"),
                                (panels[2], "tree_utilisation", "worst tree utilisation")):
        panel.plot(steps, [float(unpack(c[field]).max(initial=0.0)) for c in captures])
        panel.axvline(len(raised) - 0.5, color="0.6", linestyle="--")
        panel.set_ylabel(label)
    panels[2].axhline(1.0, color="tab:red", linewidth=0.8)
    panels[2].set_xlabel("capture: the raise frame by frame, then the tiling a quarter at a time")
    path = folder / "sequence.png"
    figure.savefig(path, dpi=150)
    plt.close(figure)
    written.append(path)
    return written


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--study", default="5 sided form")
    parser.add_argument("--material", default="tile")
    parser.add_argument("--pattern", default="bonded-courses")
    parser.add_argument("--size", type=float, default=1.0)
    parser.add_argument("--thickness", type=float, default=0.02)
    parser.add_argument("--prestress", type=float, default=300.0)
    parser.add_argument("--wires-per-motor", type=int, default=1)
    parser.add_argument("--wall", type=float, default=3.2)
    parser.add_argument("--images", default=str(IMAGES))
    args = parser.parse_args()
    # redirected to a file, a block-buffered run shows nothing until it ends
    sys.stdout.reconfigure(line_buffering=True)

    import json

    import geometry
    import bundle
    from fastapi.testclient import TestClient
    import app as studio_app

    # create_app does not read settings.json, serve.py does, before it builds
    # the app: without this the export is looked for in the repo's demo folder
    studio_app.apply_saved_folder()
    pairs = geometry.available_exports(bundle.UPLOAD_DIR)
    if args.study not in pairs:
        print("the export {!r} is not in {}".format(args.study, bundle.UPLOAD_DIR))
        return 2
    print("export folder:", bundle.UPLOAD_DIR)
    client = TestClient(studio_app.create_app())
    options = {"material": args.material, "pattern": args.pattern, "size": args.size,
               "thickness": args.thickness}
    started = client.post("/api/studies/{}/formwork/run".format(args.study), json={
        **options, "prestress": args.prestress, "wires_per_motor": args.wires_per_motor,
        "wall": args.wall})
    print("run:", started.status_code, started.json())
    if started.status_code not in (202, 409):
        return 1
    run_id = started.json()["run"]
    began = time.time()
    while True:
        state = client.get("/api/runs/{}".format(run_id)).json()
        if state["state"] in ("done", "failed"):
            break
        print("  {:5.0f} s  {} {}/{}  {}".format(time.time() - began, state["phase"],
                                               state["stage"], state["of"], state["message"]))
        time.sleep(10)
    print("run {} after {:.0f} s {}".format(state["state"], time.time() - began, state["message"]))
    if state["state"] != "done":
        return 1
    response = client.get("/api/studies/{}/formwork/sim".format(args.study), params=options)
    if response.status_code != 200:
        print("the captures could not be read:", response.status_code, response.text[:500])
        return 1
    document = json.loads(response.content)
    for line in summary_lines(document):
        print(line)
    for path in render(document, args.images):
        print("drawn:", path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
