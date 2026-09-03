"""Play-button launcher for the studio, in the main venv.

Same bootstrap discipline as the demos: hand this file to .venv's
interpreter if the picker chose something else, then serve on localhost.
"""

from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[0] / "demo"))
sys.path.insert(0, str(HERE))

from _bootstrap import ensure_venv  # noqa: E402

ensure_venv(__file__)


def main() -> int:
    import uvicorn

    from app import apply_saved_folder, create_app

    # The folder the user last chose, applied before the app is built. Here
    # rather than inside create_app, which the tests call with their own
    # temporary folder already monkeypatched into place.
    chosen = apply_saved_folder()
    if chosen is not None:
        print("Reading vaults from {}".format(chosen))
    print("Bench Studio at http://127.0.0.1:8600")
    uvicorn.run(create_app(), host="127.0.0.1", port=8600, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
