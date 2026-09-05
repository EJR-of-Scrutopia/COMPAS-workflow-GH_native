"""Drive the headless Chromium that ships with this machine, over CDP.

There is no Playwright module here, only the browser binary, and every
useful thing beyond "load a page and dump the DOM" needs the DevTools
protocol, which speaks WebSocket. So this is a WebSocket client in the
standard library: an HTTP upgrade, masked client frames, unmasked server
frames, and nothing else. Sixty lines buys the ability to click things in
the studio and photograph what happened, which until today was impossible
here at all.

The other half of the unlock is the flag set. Software WebGL used to take
the GPU process down with it; --enable-unsafe-swiftshader with ANGLE
pointed at SwiftShader gives a real, if slow, WebGL context, and the studio
boots in it.

    from cdp import Browser
    with Browser("http://127.0.0.1:8601/") as page:
        page.eval("document.getElementById('skin-picker').click()")
        page.shot("out.png")
"""

import base64
import json
import os
import random
import socket
import struct
import subprocess
import tempfile
import time
import urllib.request

CHROME = (r"C:\Users\Param\AppData\Local\ms-playwright\chromium-1237"
          r"\chrome-win64\chrome.exe")

FLAGS = [
    "--headless=new", "--no-sandbox", "--no-first-run",
    "--disable-extensions", "--hide-scrollbars",
    # The line that makes WebGL work here at all.
    "--enable-unsafe-swiftshader", "--use-gl=angle", "--use-angle=swiftshader",
]


class Socket:
    """A WebSocket, in as little code as the protocol allows."""

    def __init__(self, url):
        rest = url.split("://", 1)[1]
        hostport, _, path = rest.partition("/")
        host, _, port = hostport.partition(":")
        self.sock = socket.create_connection((host, int(port or 80)), timeout=60)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((
            "GET /{} HTTP/1.1\r\nHost: {}\r\nUpgrade: websocket\r\n"
            "Connection: Upgrade\r\nSec-WebSocket-Key: {}\r\n"
            "Sec-WebSocket-Version: 13\r\n\r\n"
        ).format(path, hostport, key).encode())
        self.buffer = b""
        while b"\r\n\r\n" not in self.buffer:
            self.buffer += self.sock.recv(4096)
        head, _, self.buffer = self.buffer.partition(b"\r\n\r\n")
        if b"101" not in head.split(b"\r\n")[0]:
            raise RuntimeError("no websocket upgrade: {}".format(head[:200]))

    def _read(self, count):
        while len(self.buffer) < count:
            chunk = self.sock.recv(65536)
            if not chunk:
                raise RuntimeError("the browser closed the connection")
            self.buffer += chunk
        head, self.buffer = self.buffer[:count], self.buffer[count:]
        return head

    def send(self, text):
        payload = text.encode("utf-8")
        header = bytes([0x81])
        length = len(payload)
        if length < 126:
            header += bytes([0x80 | length])
        elif length < 65536:
            header += bytes([0x80 | 126]) + struct.pack(">H", length)
        else:
            header += bytes([0x80 | 127]) + struct.pack(">Q", length)
        mask = os.urandom(4)
        masked = bytes(byte ^ mask[i % 4] for i, byte in enumerate(payload))
        self.sock.sendall(header + mask + masked)

    def recv(self):
        while True:
            first, second = self._read(2)
            opcode = first & 0x0F
            length = second & 0x7F
            if length == 126:
                length = struct.unpack(">H", self._read(2))[0]
            elif length == 127:
                length = struct.unpack(">Q", self._read(8))[0]
            body = self._read(length)
            if second & 0x80:          # a server frame should never be masked
                mask = body[:4]
                body = bytes(b ^ mask[i % 4] for i, b in enumerate(body[4:]))
            if opcode == 0x1:
                return body.decode("utf-8")
            if opcode == 0x8:
                raise RuntimeError("the browser closed the socket")
            # 0x9 ping, 0xA pong, 0x0 continuation: not needed for CDP here

    def close(self):
        try:
            self.sock.close()
        except OSError:
            pass


class Browser:
    def __init__(self, url, width=1500, height=950, wait=6.0):
        self.profile = tempfile.mkdtemp(prefix="cdp-")
        self.port = random.randint(9300, 9899)
        self.process = subprocess.Popen(
            [CHROME] + FLAGS
            + ["--remote-debugging-port={}".format(self.port),
               "--user-data-dir=" + self.profile,
               "--window-size={},{}".format(width, height), url],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        target = None
        deadline = time.time() + 30
        while time.time() < deadline and not target:
            try:
                listed = json.loads(urllib.request.urlopen(
                    "http://127.0.0.1:{}/json".format(self.port),
                    timeout=2).read().decode())
                target = next((t for t in listed
                               if t.get("type") == "page"
                               and t.get("webSocketDebuggerUrl")), None)
            except Exception:
                time.sleep(0.4)
        if not target:
            raise RuntimeError("chromium never offered a page target")
        self.ws = Socket(target["webSocketDebuggerUrl"])
        self.next_id = 0
        # The page is already loading; give it its own time before anything
        # is asked of it. A studio has a scene to build and a library to
        # fetch, and both are slower under SwiftShader than on a GPU.
        time.sleep(wait)

    def send(self, method, **params):
        self.next_id += 1
        wanted = self.next_id
        self.ws.send(json.dumps({"id": wanted, "method": method,
                                 "params": params}))
        while True:
            message = json.loads(self.ws.recv())
            if message.get("id") == wanted:
                if "error" in message:
                    raise RuntimeError("{}: {}".format(method, message["error"]))
                return message.get("result", {})

    def eval(self, expression, wait=0.0):
        """Run JavaScript in the page and return its value."""

        result = self.send("Runtime.evaluate", expression=expression,
                           returnByValue=True, awaitPromise=True)
        if wait:
            time.sleep(wait)
        if result.get("exceptionDetails"):
            raise RuntimeError(json.dumps(result["exceptionDetails"])[:500])
        return result.get("result", {}).get("value")

    def shot(self, path):
        data = self.send("Page.captureScreenshot", format="png")["data"]
        with open(path, "wb") as handle:
            handle.write(base64.b64decode(data))
        return path

    def logs(self):
        return self.eval("(window.__studioLog || []).join('\\n')")

    def close(self):
        try:
            self.ws.close()
        finally:
            self.process.terminate()

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.close()
