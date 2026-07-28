"""Small framed-protocol worker used only by the native host race tests."""

from __future__ import annotations

import json
import struct
import sys
import time


SCHEMA = "9.9" if "--bad-schema" in sys.argv else "0.1"
MAX_FRAME_BYTES = 32 * 1024 * 1024


def read_exact(stream, count):
    chunks = []
    remaining = count
    while remaining:
        chunk = stream.read(remaining)
        if not chunk:
            return None
        chunks.append(chunk)
        remaining -= len(chunk)
    return b"".join(chunks)


def read_frame():
    header = read_exact(sys.stdin.buffer, 4)
    if header is None:
        return None
    length = struct.unpack(">I", header)[0]
    if length <= 0 or length > MAX_FRAME_BYTES:
        raise ValueError("invalid frame length")
    payload = read_exact(sys.stdin.buffer, length)
    if payload is None:
        raise EOFError("stream ended inside frame")
    return json.loads(payload.decode("utf-8"))


def write_result(request, result):
    envelope = {
        "v": 1,
        "type": "result",
        "id": request["id"],
        "result": result,
    }
    payload = json.dumps(
        envelope,
        allow_nan=False,
        separators=(",", ":"),
    ).encode("utf-8")
    sys.stdout.buffer.write(struct.pack(">I", len(payload)))
    sys.stdout.buffer.write(payload)
    sys.stdout.buffer.flush()


def health():
    return {
        "status": "ok",
        "worker": {
            "name": "ananke-native-test-worker",
            "version": "0",
            "protocol_version": 1,
            "schema_version": SCHEMA,
        },
        "python": {
            "version": sys.version.split()[0],
            "implementation": "CPython",
            "executable": sys.executable,
        },
        "packages": {},
        "capabilities": {},
    }


def main():
    while True:
        request = read_frame()
        if request is None:
            return
        command = request.get("command")
        if command == "system.hello":
            write_result(
                request,
                {
                    "name": "ananke-native-test-worker",
                    "protocol_version": 1,
                    "schema_version": SCHEMA,
                    "max_frame_bytes": MAX_FRAME_BYTES,
                    "commands": [
                        "system.hello",
                        "system.health",
                        "system.shutdown",
                        "test.delay",
                    ],
                    "health": health(),
                },
            )
        elif command == "system.health":
            write_result(request, health())
        elif command == "system.shutdown":
            write_result(request, {"status": "shutting_down"})
            return
        elif command == "test.delay":
            seconds = float(request.get("payload", {}).get("seconds", 1.0))
            time.sleep(seconds)
            write_result(request, {"status": "complete"})
        else:
            write_result(request, {"status": "unknown"})


if __name__ == "__main__":
    main()
