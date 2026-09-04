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

DEFAULT_PORT = 8600


def chosen_port(argv) -> int:
    """--port, if given. The studio is one window on one machine and does
    not need a settings file for this; it needs the option to exist so the
    restart path can be exercised without stopping the real studio."""

    for index, item in enumerate(argv):
        if item == "--port" and index + 1 < len(argv):
            try:
                return int(argv[index + 1])
            except ValueError:
                break
        if item.startswith("--port="):
            try:
                return int(item.split("=", 1)[1])
            except ValueError:
                break
    return DEFAULT_PORT


def main() -> int:
    import uvicorn

    import portcheck
    from app import apply_saved_folders, create_app

    port = chosen_port(sys.argv[1:])

    # The shortcut opens a window and the window fails to bind, because the
    # last studio is still on the port. uvicorn says so and exits, and the
    # browser goes on talking to the old process: every change since is
    # invisible, and the studio looks broken rather than absent. This has
    # cost three rounds of "nothing has changed on the interface".
    #
    # It is also how the Restart button works: the new process started by
    # the old one comes through here and stops its parent by name.
    if not portcheck.take_the_port(port):
        print("The studio cannot start while that port is in use.")
        return 1

    # The folders the user last chose, applied before the app is built. Here
    # rather than inside create_app, which the tests call with their own
    # temporary folders already monkeypatched into place.
    for key, folder in sorted(apply_saved_folders().items()):
        print("{}: {}".format(key.replace("_", " "), folder))
    print("Bench Studio at http://127.0.0.1:{}".format(port))
    uvicorn.run(create_app(), host="127.0.0.1", port=port, log_level="info")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
