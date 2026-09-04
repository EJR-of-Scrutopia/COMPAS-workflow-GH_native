"""Restarting the studio without a terminal, and taking the port back.

Param, three rounds into a panel that would not change: "how do i close a
server and reopen a new one? i open the shortcut and it reopens a window but
i get the same display?"

The shortcut was never the problem. The old server had not stopped, so
uvicorn could not bind, printed [Errno 10048] and exited, and the browser
went on talking to a process from an hour ago. Two answers here: a launcher
that takes the port back from a studio that identifies itself as one, and a
button that replaces the running process and reloads the page on the new
build.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[2]
STUDIO = REPO / "bench" / "studio"
STATIC = STUDIO / "static"
if str(STUDIO) not in sys.path:
    sys.path.insert(0, str(STUDIO))

import app as studio_app  # noqa: E402
import portcheck  # noqa: E402

# Real netstat output, trimmed. The shape matters more than the numbers:
# only LISTENING rows own a port, and the last column is the process.
NETSTAT = """
Active Connections

  Proto  Local Address          Foreign Address        State           PID
  TCP    0.0.0.0:135            0.0.0.0:0              LISTENING       1284
  TCP    127.0.0.1:8600         0.0.0.0:0              LISTENING       41916
  TCP    127.0.0.1:8600         127.0.0.1:52104        ESTABLISHED     41916
  TCP    127.0.0.1:52104        127.0.0.1:8600         ESTABLISHED     9032
  TCP    127.0.0.1:8601         0.0.0.0:0              LISTENING       8508
  TCP    [::]:445               [::]:0                 LISTENING       4
"""


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(studio_app, "SETTINGS_PATH", tmp_path / "settings.json")
    return TestClient(studio_app.create_app())


def test_only_a_listening_socket_owns_a_port():
    """An established connection to 8600 is a CLIENT of it. Counting those
    as owners would have the launcher stop the browser."""

    assert portcheck.pids_listening(8600, NETSTAT) == [41916]
    assert portcheck.pids_listening(8601, NETSTAT) == [8508]
    assert portcheck.pids_listening(9999, NETSTAT) == []
    # The client end of the established pair is never returned.
    assert 9032 not in portcheck.pids_listening(8600, NETSTAT)


def test_nothing_is_stopped_that_has_not_said_what_it_is(monkeypatch):
    """The safety of the whole module. Killing whatever happens to own a
    port is how a tool eats somebody's database."""

    said = []
    stopped = []
    monkeypatch.setattr(portcheck, "_netstat", lambda: NETSTAT)
    monkeypatch.setattr(portcheck, "who_is_there", lambda port, timeout=2.0: None)
    monkeypatch.setattr(portcheck, "stop", lambda pid: stopped.append(pid) or True)

    assert portcheck.take_the_port(8600, say=said.append) is False
    assert stopped == [], "a stranger on the port must be left alone"
    assert "not a Bench Studio" in " ".join(said)


def test_a_studio_on_the_port_is_stopped_and_named(monkeypatch):
    said = []
    stopped = []
    states = [NETSTAT, ""]
    monkeypatch.setattr(portcheck, "_netstat", lambda: states.pop(0) if states else "")
    monkeypatch.setattr(portcheck, "who_is_there",
                        lambda port, timeout=2.0: {"studio": True, "build": "abc123"})
    monkeypatch.setattr(portcheck, "stop", lambda pid: stopped.append(pid) or True)
    monkeypatch.setattr(portcheck, "_sleep", lambda seconds: None)

    assert portcheck.take_the_port(8600, say=said.append) is True
    assert stopped == [41916]
    # It says which build it stopped, because the next question after "did
    # it restart" is always "is this the new one".
    assert "abc123" in " ".join(said)


def test_a_studio_too_old_to_introduce_itself_is_still_recognised(monkeypatch):
    """/api/health was added in the same change as this module, so the
    server that most needs displacing answers it with 404. Measured on a
    live pair: the old studio on 8600 gave 404 and the new one on 8601 gave
    its build. Without the second question the launcher would politely
    refuse to touch the very process it exists to replace."""

    asked = []

    def answer(port, path, timeout):
        asked.append(path)
        if path == "/api/health":
            return None                      # a 404 reads as no answer
        return {"studies": ["a-vault"], "patterns": []}

    monkeypatch.setattr(portcheck, "_ask", answer)
    found = portcheck.who_is_there(8600)
    assert found is not None and found["studio"] is True
    assert asked == ["/api/health", "/api/studies"]


def test_something_that_answers_neither_question_is_left_alone(monkeypatch):
    monkeypatch.setattr(portcheck, "_ask", lambda port, path, timeout: None)
    assert portcheck.who_is_there(8600) is None
    # And a JSON body that is not ours is not ours.
    monkeypatch.setattr(portcheck, "_ask",
                        lambda port, path, timeout: {"jenkins": True})
    assert portcheck.who_is_there(8600) is None


def test_a_free_port_needs_no_action(monkeypatch):
    monkeypatch.setattr(portcheck, "_netstat", lambda: NETSTAT)
    stopped = []
    monkeypatch.setattr(portcheck, "stop", lambda pid: stopped.append(pid) or True)
    assert portcheck.take_the_port(9999, say=lambda line: None) is True
    assert stopped == []


def test_an_unparseable_netstat_is_treated_as_a_free_port(monkeypatch):
    """If the port is actually taken, uvicorn will say so a moment later.
    Refusing to start because netstat could not be read would be worse."""

    monkeypatch.setattr(portcheck, "_netstat", lambda: "")
    assert portcheck.take_the_port(8600, say=lambda line: None) is True


def test_health_says_who_and_which_build(client):
    body = client.get("/api/health").json()
    assert body["studio"] is True
    assert body["build"] == studio_app.static_version()
    assert isinstance(body["pid"], int)


def test_restart_answers_before_it_goes(client, monkeypatch):
    """The response has to reach the browser, or the page has nothing to
    act on but a dropped connection.

    The whole scheduling is replaced, not os.execv underneath it. The first
    version of this test patched execv, finished, monkeypatch put the real
    one back, and the daemon thread then woke up and exec'd the PYTEST
    process mid-run. Anything that acts after a delay cannot be made safe by
    replacing what it will eventually call.
    """

    scheduled = []
    monkeypatch.setattr(studio_app, "schedule_restart",
                        lambda *args, **kwargs: scheduled.append(True))
    body = client.post("/api/restart").json()
    assert body["restarting"] is True
    assert body["build"] == studio_app.static_version()
    assert scheduled == [True], "the route must go through the one function"


def test_the_restart_is_one_replaceable_function():
    """So that a test never has to patch os.execv and hope the thread does
    not outlive the patch. It did, once, and restarted the suite."""

    source = (STUDIO / "app.py").read_text(encoding="utf-8")
    assert "def schedule_restart(delay: float = RESTART_DELAY) -> None:" in source
    route = source[source.index('@app.post("/api/restart")'):]
    route = route[:route.index("\n    @app.")]
    assert "schedule_restart()" in route
    # The CALL, not the name: the docstrings around here talk about execv
    # on purpose and must go on being allowed to.
    assert "os.execv(" not in route, (
        "the route must not build its own thread; that is what made it "
        "impossible to fake in one piece"
    )
    assert "threading.Thread" not in route


def test_the_button_waits_for_the_build_not_for_the_socket():
    """A restart that came back on the OLD build would put us straight back
    in the fault this button exists to end, and the socket answering says
    nothing about which build answered."""

    js = (STATIC / "studio.js").read_text(encoding="utf-8")
    body = js[js.index('getElementById("restart-studio").addEventListener'):]
    body = body[:body.index("\n});")]
    assert '"/api/restart", { method: "POST" }' in body
    # A different PROCESS is what a restart produces; a different build is
    # what an EDIT produces. Waiting only for the build left the page
    # waiting through a restart that had already happened, measured: pid
    # 69756 became 60500 and the stamp never moved because nothing on disk
    # had changed.
    assert "health.pid !== before.pid" in body
    assert "health.build !== before.build" in body
    assert "await fetch(\"/api/health\"" in body, (
        "both halves of 'did it come back' are questions about the OLD "
        "process, so it has to be asked before the restart"
    )
    assert "location.reload()" in body
    # A dropped connection IS the restart on a server that got far enough to
    # replace itself before answering, so it must not abort the wait.
    assert "catch (error)" in body


def test_the_button_is_at_the_very_bottom():
    page = (STATIC / "index.html").read_text(encoding="utf-8")
    assert 'id="restart-studio"' in page
    assert page.index('id="mode-row"') < page.index('id="restart-studio"'), (
        "Param asked for it at the very bottom, under the three views"
    )
    assert page.index('id="restart-studio"') < page.index("</aside>")
