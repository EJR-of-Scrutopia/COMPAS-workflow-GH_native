"""Snap a .thumb.png beside every prop model, once, on the desktop.

The prop drawer used to render every tile from the model's own geometry,
which meant owning every model before the drawer could open -- the eager
241 MB boot that an iPad tab cannot survive. The tiles draw these files
instead now, and a model is only loaded when something places it. Run
this against a RUNNING studio (the desktop, where memory is plentiful)
after adding or re-ingesting props; a prop with no snapshot still works,
it just pays a live geometry load for its preview.

    python tools/props/snap_thumbs.py [--force]

Writes <file>.glb.thumb.png beside each GLB in bench/studio/props-hd.
The files are derived and gitignored, like the GLBs they portray.
"""

from __future__ import annotations

import base64
import json
import sys
import urllib.request
from pathlib import Path

from cdp import Browser

REPO = Path(__file__).resolve().parents[2]
PROPS = REPO / "bench" / "studio" / "props-hd"
STUDIO = "http://127.0.0.1:8600/"

SNAP = """(async () => {
  const entry = %s;
  const template = await window.__studio.ensurePropTemplate(entry.key);
  if (!template) return null;
  const canvasEl = document.createElement("canvas");
  canvasEl.width = 256;
  canvasEl.height = 256;
  window.__studio.renderObjectPreview(template, canvasEl);
  return canvasEl.toDataURL("image/png");
})()"""


def main() -> int:
    force = "--force" in sys.argv[1:]
    with urllib.request.urlopen(STUDIO + "api/props", timeout=10) as reply:
        entries = json.load(reply).get("props", [])
    if not entries:
        print("the studio lists no props; is it running with the library?")
        return 1
    wanted = [entry for entry in entries
              if force or not (PROPS / (entry["file"] + ".thumb.png")).is_file()]
    print("{} props, {} need a snapshot".format(len(entries), len(wanted)))
    if not wanted:
        return 0
    with Browser(STUDIO, wait=25) as page:
        page.ws.sock.settimeout(600)
        done = 0
        for entry in wanted:
            data = page.eval(SNAP % json.dumps(
                {"key": entry["key"], "file": entry["file"]}))
            if not data or not data.startswith("data:image/png;base64,"):
                print("  no snapshot for {}".format(entry["key"]))
                continue
            path = PROPS / (entry["file"] + ".thumb.png")
            path.write_bytes(base64.b64decode(
                data.split(",", 1)[1].encode("ascii")))
            done += 1
            if done % 10 == 0:
                print("  {} / {}".format(done, len(wanted)))
    print("wrote {} snapshots into {}".format(done, PROPS))
    return 0 if done == len(wanted) else 1


if __name__ == "__main__":
    sys.exit(main())
