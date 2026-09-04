"""Take the port back from the studio that is already on it.

The symptom this exists for, in the owner's words: "i open the shortcut and
it reopens a window but i get the same display?" The shortcut works. What
happens is that the old server never stopped, so the new one cannot bind:

    ERROR: [Errno 10048] error while attempting to bind on address
    ('127.0.0.1', 8600): only one usage of each socket address is normally
    permitted

uvicorn prints that, exits, and the window closes or sits there; the browser
goes on talking to the process from an hour ago. Every change since is
invisible, and the studio looks broken rather than absent. This has cost
three rounds of "nothing has changed on the interface".

So the launcher takes the port. Carefully, and only from itself: the process
holding it is asked whether it is a Bench Studio before anything is done to
it, and if it is not, the launcher says what is there and refuses. Killing
whatever happens to own a port is how a tool eats somebody's database.

Standard library only, like the rest of this package.
"""

from __future__ import annotations

import json
import os
import re
import signal
import subprocess
import sys
import urllib.error
import urllib.request
from typing import List, Optional

# netstat prints a line per connection; only a LISTENING socket owns the
# port, and only the local address matters. The last column is the pid.
LISTENING = re.compile(
    r"^\s*TCP\s+\S+:(\d+)\s+\S+\s+LISTENING\s+(\d+)\s*$", re.MULTILINE)


def pids_listening(port: int, netstat_output: str) -> List[int]:
    """Every process id listening on this port, from netstat's own output.

    Parsed rather than shelled out to line by line so it can be tested
    against real captured output without opening a socket.
    """

    found = []
    for match in LISTENING.finditer(netstat_output):
        if int(match.group(1)) == port:
            pid = int(match.group(2))
            if pid and pid not in found:
                found.append(pid)
    return found


def _netstat() -> str:
    try:
        finished = subprocess.run(["netstat", "-ano", "-p", "TCP"],
                                  capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return ""
    return finished.stdout or ""


def _ask(port: int, path: str, timeout: float) -> Optional[dict]:
    try:
        with urllib.request.urlopen(
                "http://127.0.0.1:{}{}".format(port, path),
                timeout=timeout) as response:
            body = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return None
    return body if isinstance(body, dict) else None


def who_is_there(port: int, timeout: float = 2.0) -> Optional[dict]:
    """Ask whatever is on the port whether it is a Bench Studio.

    Two questions, because the server that most needs displacing is the one
    too old to answer the first. /api/health was added in the same change as
    this module, so a studio started before it answers 404 and identifies
    itself as nothing at all -- and the launcher would then politely refuse
    to touch the very process it exists to replace. Measured on a live pair:
    the old one on 8600 gave 404, the new one on 8601 gave its build.

    /api/studies is the second question. It has been in this studio since
    long before any of this and returns an object with a "studies" key.
    Nothing else on a developer's machine answers that on localhost, and it
    is the only way a version check can reach a version that predates it.

    Anything that answers neither -- a different application, a stale
    socket, a firewall -- is None, and None is never stopped. That is the
    whole safety of this module.
    """

    modern = _ask(port, "/api/health", timeout)
    if modern and modern.get("studio"):
        return modern

    older = _ask(port, "/api/studies", timeout)
    if older is not None and "studies" in older:
        return {"studio": True, "build": "older than this launcher"}
    return None


def stop(pid: int) -> bool:
    """End one process. Windows has no SIGTERM worth the name, so taskkill."""

    if os.name == "nt":
        try:
            finished = subprocess.run(
                ["taskkill", "/PID", str(pid), "/F"],
                capture_output=True, text=True, timeout=20)
            return finished.returncode == 0
        except (OSError, subprocess.SubprocessError):
            return False
    try:
        os.kill(pid, signal.SIGTERM)
        return True
    except OSError:
        return False


def take_the_port(port: int, say=print) -> bool:
    """Make the port free, if what is on it is one of ours.

    Returns True when the port is free to bind afterwards. Says what it did
    either way, because a launcher that silently kills things is worse than
    one that silently fails.
    """

    holders = pids_listening(port, _netstat())
    if not holders:
        return True

    previous = who_is_there(port)
    if previous is None:
        say("Port {} is held by process {} and it is not a Bench Studio, so "
            "it has been left alone. Close it, or start the studio on "
            "another port.".format(port, ", ".join(str(p) for p in holders)))
        return False

    for pid in holders:
        # Never the process asking the question. It cannot be, since it has
        # not bound anything yet, but a launcher that can kill itself is one
        # restart away from being unable to start.
        if pid == os.getpid():
            continue
        if stop(pid):
            say("Stopped the studio that was already on port {} (build {}, "
                "process {}).".format(port, previous.get("build", "unknown"), pid))
        else:
            say("Could not stop process {} on port {}. Close it by hand and "
                "try again.".format(pid, port))
            return False

    # The socket takes a moment to come back after the process goes.
    for _ in range(40):
        if not pids_listening(port, _netstat()):
            return True
        _sleep(0.1)
    say("Port {} is still held after stopping its process.".format(port))
    return False


def _sleep(seconds: float) -> None:
    import time

    time.sleep(seconds)


if __name__ == "__main__":
    wanted = int(sys.argv[1]) if len(sys.argv) > 1 else 8600
    raise SystemExit(0 if take_the_port(wanted) else 1)
