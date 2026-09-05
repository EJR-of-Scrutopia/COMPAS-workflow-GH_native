"""The waker: the one always-on piece of Vaulted's remote door.

A laptop or a phone on the tailnet cannot double-click the desktop
shortcut, so something on this machine has to answer "start the studio"
around the clock. This is that something, and deliberately nothing more:
it listens on loopback only (Tailscale Serve is the front door that
carries it to the tailnet), it takes no input, and the only thing it can
do is run the same launcher the desktop shortcut runs. Stopping came
first -- the page has a Stop server button -- so this closes the loop:
one URL now starts the studio from anywhere.

GET /start (or /) answers one of two ways:
- studio already up: a redirect to /, which on the shared tailnet port
  is the studio's own mount, not this process;
- studio down: the launcher is spawned (windowless, browserless) and a
  small page is returned that polls /api/health and moves to / the
  moment the studio answers. The page does the waiting, so the waker
  never holds a request open.

Runs under pythonw from a logon task. Under pythonw there is NO stderr:
a single print, including the request logging BaseHTTPRequestHandler
does by default, would end the process (the same fault serve.py's
ensure_stdio exists for). So the waker never writes to its streams.
"""

from __future__ import annotations

import json
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent

WAKER_PORT = 8611
STUDIO_PORT = 8600

# A second knock while a launch is already under way must not stack
# launchers. portcheck would keep the pile-up harmless -- each new studio
# takes the port from the last -- but a burst of opens should still be
# one launch, not five restarts in a row.
SPAWN_COOLDOWN = 30.0

START_PAGE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Vaulted is starting</title>
<style>
  body { margin: 0; min-height: 100vh; display: grid; place-items: center;
         background: #16161a; color: #e8e6e1;
         font: 15px/1.5 "Segoe UI", system-ui, sans-serif; }
  .card { text-align: center; }
  .spin { width: 34px; height: 34px; margin: 0 auto 14px;
          border: 3px solid #3a3a42; border-top-color: #e8e6e1;
          border-radius: 50%; animation: turn 0.9s linear infinite; }
  @keyframes turn { to { transform: rotate(360deg); } }
  p { margin: 0; opacity: 0.85; }
</style>
</head>
<body>
<div class="card">
  <div class="spin"></div>
  <p id="say">Starting Vaulted on the desktop...</p>
</div>
<script>
  // The health answer must be the studio's own, not the proxy's: when the
  // studio is down the tailnet proxy still replies, with a 502, so only
  // an ok answer that says "studio" counts as up.
  const deadline = Date.now() + 100000;
  async function knock() {
    try {
      const reply = await fetch("/api/health", { cache: "no-store" });
      if (reply.ok) {
        const health = await reply.json();
        if (health && health.studio) { location.replace("/"); return; }
      }
    } catch (error) { /* not up yet */ }
    if (Date.now() > deadline) {
      document.getElementById("say").textContent =
        "The studio did not come up. Check the desktop.";
      return;
    }
    setTimeout(knock, 700);
  }
  knock();
</script>
</body>
</html>
"""


def studio_is_up(port: int = STUDIO_PORT) -> bool:
    """Whether a Bench Studio, specifically, answers on the port."""

    address = "http://127.0.0.1:{}/api/health".format(port)
    try:
        with urllib.request.urlopen(address, timeout=1.5) as reply:
            return bool(json.load(reply).get("studio"))
    except (OSError, ValueError):
        return False


def plan(path: str, up: bool) -> str:
    """What one request gets, as a word the handler acts on.

    Both "/start" and "/" wake, because Tailscale Serve may hand the
    mounted path over stripped or whole depending on how the mount was
    written, and the waker should not care which.
    """

    route = path.split("?", 1)[0].rstrip("/") or "/"
    if route in ("/", "/start"):
        return "studio" if up else "wake"
    if route == "/waker-health":
        return "health"
    return "missing"


def should_spawn(now: float, last: float,
                 cooldown: float = SPAWN_COOLDOWN) -> bool:
    return (now - last) >= cooldown


_last_spawn = 0.0
_spawn_lock = threading.Lock()


def spawn_studio() -> bool:
    """Run the launcher, at most once per cooldown. True if it ran.

    The same launch.ps1 as the desktop shortcut, so the port takeover,
    the pidfile and the logs all stay in the one place they are already
    understood. -NoBrowser because the device that asked has its own
    browser already open, on this very page.
    """

    global _last_spawn
    with _spawn_lock:
        now = time.monotonic()
        if not should_spawn(now, _last_spawn):
            return False
        _last_spawn = now
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    try:
        subprocess.Popen(
            ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass",
             "-File", str(HERE / "launch.ps1"), "-Quiet", "-NoBrowser"],
            cwd=str(REPO), creationflags=flags, close_fds=True,
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL)
    except OSError:
        # A failed spawn leaves the waker alive to try again next knock.
        return False
    return True


class WakerHandler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 (the stdlib names it)
        what = plan(self.path, studio_is_up())
        if what == "studio":
            self.send_response(302)
            self.send_header("Location", "/")
            self.end_headers()
        elif what == "wake":
            spawn_studio()
            body = START_PAGE.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif what == "health":
            body = json.dumps({"waker": True}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):  # noqa: A002 (stdlib signature)
        """Silence, on purpose: under pythonw a write to stderr is fatal."""


def main() -> int:
    try:
        server = ThreadingHTTPServer(("127.0.0.1", WAKER_PORT), WakerHandler)
    except OSError:
        # The port is taken. If it is taken by another waker -- two logon
        # tasks racing -- that waker is doing the job and this one should
        # go quietly. Anything else on the port is a real fault, but there
        # is nowhere safe to say so from pythonw; exiting nonzero leaves
        # the mark where a scheduled task's history can show it.
        address = "http://127.0.0.1:{}/waker-health".format(WAKER_PORT)
        try:
            with urllib.request.urlopen(address, timeout=1.5) as reply:
                if json.load(reply).get("waker"):
                    return 0
        except (OSError, ValueError):
            pass
        return 1
    server.serve_forever()
    return 0


if __name__ == "__main__":
    sys.exit(main())
