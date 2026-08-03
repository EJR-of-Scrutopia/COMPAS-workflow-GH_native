# VS Code Design Bench Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a terminal and VS Code bench where a COMPAS vault study is a hand-edited JSON file, a solve is one command, and the result can be validated, plotted, viewed, and committed.

**Architecture:** A new `ananke` CLI reads a study file, wraps its `payload` in the same request envelope the C# Grasshopper components build, and calls `worker.dispatch()` in-process. Parity with Grasshopper is therefore structural rather than asserted, and breakpoints work. Two new worker commands (`dem.tessellate`, `fea.model`) are added at the worker layer so Grasshopper inherits them, and worker-side request capture turns any canvas solve into a replayable study file with no C# changes.

**Tech Stack:** Python 3.9+ language level, pytest, matplotlib (already present), `compas_viewer` behind an opt-in extra, `compas_dem` for tessellation, `compas_fea2` for model expression.

## Global Constraints

- Language level is Python 3.9. No `match`, no PEP 604 `X | Y` unions evaluated at runtime. Use `typing.Optional`, `typing.Dict`, `typing.List`, `typing.Tuple`.
- Every module starts with `from __future__ import annotations`, imports `typing` names one per line, and ends with an explicit `__all__`. Match the surrounding style in `src/ananke_equilibrium/`.
- Pins must not move: `numpy==2.0.2`, `scipy==1.13.1`, `compas==2.15.1`. Task 11 adds a test enforcing this.
- No Rhino or Grasshopper imports anywhere in `src/ananke_equilibrium/`.
- `SCHEMA_VERSION` is `"0.1"`. Contracts reject payloads declaring anything else.
- Prose in docs and commit messages uses no em dashes. Use commas, semicolons, colons, or full stops.
- Commit messages are imperative and descriptive, matching the existing log (for example "Add the ananke CLI skeleton and health command"). Do **not** add `Co-Authored-By` or any AI attribution.
- Do not modify `src/ananke_equilibrium/codec.py`. Another branch is actively rewriting it and every avoided edit is an avoided conflict. Only `worker.py` is modified, in tasks 6, 8, 9, and 10, at the points named there.
- The result envelope differs between `development` and the unmerged `feature/component-surface-redesign`, but only in the `kind` field: that branch's `encode_result` copies the inner payload key for key and overwrites `kind` with `"Result"`. All readers in this plan therefore key off `equilibrium`, `vertices`, `form_graph` and `force_graph`, never off `kind`.

---

## File Structure

**Created:**

| Path | Responsibility |
| --- | --- |
| `src/ananke_equilibrium/cli/__init__.py` | Public CLI exports |
| `src/ananke_equilibrium/cli/__main__.py` | `python -m ananke_equilibrium.cli` entry |
| `src/ananke_equilibrium/cli/main.py` | Argument parsing and subcommand dispatch |
| `src/ananke_equilibrium/cli/study.py` | Study file loading, `$ref` resolution, envelope construction |
| `src/ananke_equilibrium/cli/results.py` | Shape-tolerant result reading shared by plot and view |
| `src/ananke_equilibrium/cli/plot.py` | Headless matplotlib form and force diagrams |
| `src/ananke_equilibrium/cli/view.py` | `compas_viewer` bridge behind the `viz` extra |
| `src/ananke_equilibrium/cli/schema.py` | Problem-file JSON Schema declaration and writer |
| `src/ananke_equilibrium/capture.py` | Worker-side request capture |
| `src/ananke_equilibrium/dem.py` | `compas_dem` tessellation adapter |
| `src/ananke_equilibrium/fea.py` | `compas_fea2` model expression adapter |
| `.vscode/settings.json`, `tasks.json`, `launch.json`, `extensions.json` | Editor wiring |
| `.vscode/ananke-problem.schema.json` | Generated schema, committed |
| `studies/example-arch/problem.json` | Worked example and test fixture |
| `tests/test_cli_study.py`, `test_cli_solve.py`, `test_cli_results.py`, `test_cli_schema.py`, `test_capture.py`, `test_dem_tessellate.py`, `test_fea_model.py`, `test_environment_pins.py` | Tests |

**Modified:**

| Path | Change |
| --- | --- |
| `pyproject.toml` | `[project.scripts]`, `viz` extra, `masonry`/`fea` already present |
| `src/ananke_equilibrium/worker.py` | Capture hook in `serve()`; import-based health; `dem.tessellate` and `fea.model` commands |
| `docs/compas-suite-adoption.md` | Correct the "imports cleanly" claim |

---

## Task 1: CLI skeleton and the health command

**Files:**
- Create: `src/ananke_equilibrium/cli/__init__.py`, `src/ananke_equilibrium/cli/__main__.py`, `src/ananke_equilibrium/cli/main.py`
- Modify: `pyproject.toml`
- Test: `tests/test_cli_health.py`

**Interfaces:**
- Consumes: `ananke_equilibrium.worker.health_payload`
- Produces: `cli.main.build_parser() -> argparse.ArgumentParser`, `cli.main.main(argv: Optional[Sequence[str]] = None) -> int`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_health.py`:

```python
from __future__ import annotations

from ananke_equilibrium.cli.main import main


def test_health_prints_worker_and_packages(capsys):
    exit_code = main(["health"])
    captured = capsys.readouterr()
    assert exit_code == 0
    assert "ananke-equilibrium-worker" in captured.out
    assert "compas" in captured.out


def test_unknown_command_exits_nonzero(capsys):
    exit_code = main(["definitely-not-a-command"])
    assert exit_code == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ananke_equilibrium.cli'`

- [ ] **Step 3: Create the package**

Create `src/ananke_equilibrium/cli/__init__.py`:

```python
"""Terminal bench for COMPAS equilibrium studies."""

from __future__ import annotations

from .main import build_parser
from .main import main


__all__ = ["build_parser", "main"]
```

Create `src/ananke_equilibrium/cli/__main__.py`:

```python
"""Entry point for ``python -m ananke_equilibrium.cli``."""

from __future__ import annotations

from .main import main


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Write the parser and health command**

Create `src/ananke_equilibrium/cli/main.py`:

```python
"""Argument parsing and subcommand dispatch for the ``ananke`` CLI."""

from __future__ import annotations

import argparse
import sys
from typing import Any
from typing import Mapping
from typing import Optional
from typing import Sequence

from ..worker import health_payload


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level parser with one subparser per command."""

    parser = argparse.ArgumentParser(
        prog="ananke",
        description="Run COMPAS equilibrium studies from the terminal.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser(
        "health",
        help="Report worker, interpreter, package, and capability state.",
    )
    return parser


def _format_health(payload: Mapping[str, Any]) -> str:
    lines = []
    worker = payload.get("worker", {})
    lines.append(
        "{} {}  protocol {}  schema {}".format(
            worker.get("name"),
            worker.get("version"),
            worker.get("protocol_version"),
            worker.get("schema_version"),
        )
    )
    python = payload.get("python", {})
    lines.append(
        "python {} ({})".format(
            python.get("version"),
            python.get("executable"),
        )
    )
    lines.append("")
    lines.append("packages")
    for name in sorted(payload.get("packages", {})):
        version = payload["packages"][name]
        lines.append(
            "  {:<24} {}".format(name, version if version else "not installed")
        )
    lines.append("")
    lines.append("capabilities")
    capabilities = payload.get("capabilities", {})
    for name in sorted(capabilities):
        if name == "commands":
            continue
        lines.append("  {:<24} {}".format(name, capabilities[name]))
    return "\n".join(lines)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run one CLI invocation and return its process exit code."""

    parser = build_parser()
    try:
        args = parser.parse_args(list(argv) if argv is not None else None)
    except SystemExit as exit_error:
        return int(exit_error.code or 0)
    if args.command == "health":
        print(_format_health(health_payload()))
        return 0
    print("Unhandled command: {}".format(args.command), file=sys.stderr)
    return 2


__all__ = ["build_parser", "main"]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_cli_health.py -v`
Expected: PASS, both tests

- [ ] **Step 6: Register the console script**

In `pyproject.toml`, after the `[project.urls]` block, add:

```toml
[project.scripts]
ananke = "ananke_equilibrium.cli.main:main"
```

- [ ] **Step 7: Verify the installed entry point**

Run: `python -m pip install -e ".[equilibrium,dev]" && ananke health`
Expected: the health table prints and the process exits 0

- [ ] **Step 8: Commit**

```bash
git add src/ananke_equilibrium/cli tests/test_cli_health.py pyproject.toml
git commit -m "Add the ananke CLI skeleton and health command"
```

---

## Task 2: Study file loading and the check command

**Files:**
- Create: `src/ananke_equilibrium/cli/study.py`, `studies/example-arch/problem.json`
- Modify: `src/ananke_equilibrium/cli/main.py`
- Test: `tests/test_cli_study.py`

**Interfaces:**
- Consumes: `cli.main.build_parser`
- Produces:
  - `cli.study.StudyError(ValueError)`
  - `cli.study.load_study(path: Path) -> Dict[str, Any]` returning the study document with `$ref` resolved
  - `cli.study.build_request(study: Mapping[str, Any]) -> Dict[str, Any]` returning `{"v", "type", "id", "command", "payload"}`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_study.py`:

```python
from __future__ import annotations

import json

import pytest

from ananke_equilibrium.cli.study import StudyError
from ananke_equilibrium.cli.study import build_request
from ananke_equilibrium.cli.study import load_study


TOPOLOGY = {
    "kind": "line",
    "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
    "edges": [[0, 1], [1, 2]],
}
STUDY = {
    "study": "arch",
    "command": "fd.solve",
    "payload": {
        "topology": TOPOLOGY,
        "supports": {"mode": "explicit", "node_ids": [0, 2]},
        "load_case": {
            "name": "gravity",
            "distribution": "point",
            "node_ids": [1],
            "vectors": [[0.0, 0.0, -1.0]],
        },
        "settings": {"force_densities": 1.0},
    },
}


def write(tmp_path, document, name="problem.json"):
    path = tmp_path / name
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def test_load_study_returns_the_document(tmp_path):
    path = write(tmp_path, STUDY)
    study = load_study(path)
    assert study["command"] == "fd.solve"
    assert study["payload"]["topology"]["kind"] == "line"


def test_load_study_resolves_a_topology_ref(tmp_path):
    (tmp_path / "topology.json").write_text(json.dumps(TOPOLOGY), encoding="utf-8")
    document = json.loads(json.dumps(STUDY))
    document["payload"]["topology"] = {"$ref": "topology.json"}
    path = write(tmp_path, document)
    study = load_study(path)
    assert study["payload"]["topology"]["edges"] == [[0, 1], [1, 2]]


def test_load_study_rejects_a_ref_outside_the_study_directory(tmp_path):
    document = json.loads(json.dumps(STUDY))
    document["payload"]["topology"] = {"$ref": "../escape.json"}
    path = write(tmp_path, document)
    with pytest.raises(StudyError, match="outside"):
        load_study(path)


def test_load_study_requires_a_command(tmp_path):
    document = json.loads(json.dumps(STUDY))
    del document["command"]
    path = write(tmp_path, document)
    with pytest.raises(StudyError, match="command"):
        load_study(path)


def test_build_request_produces_the_worker_envelope():
    request = build_request(STUDY)
    assert request["v"] == 1
    assert request["type"] == "request"
    assert request["id"] == "arch"
    assert request["command"] == "fd.solve"
    assert request["payload"] == STUDY["payload"]


def test_build_request_ignores_study_only_keys():
    document = dict(STUDY)
    document["$schema"] = "../../.vscode/ananke-problem.schema.json"
    request = build_request(document)
    assert set(request) == {"v", "type", "id", "command", "payload"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_study.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ananke_equilibrium.cli.study'`

- [ ] **Step 3: Write the study loader**

Create `src/ananke_equilibrium/cli/study.py`:

```python
"""Load a study file and turn it into a worker request envelope.

A study file is the protocol payload plus two authoring keys. Keeping the
``payload`` block byte-identical to what the Grasshopper components send means
a captured canvas solve is already a valid study.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Mapping


PROTOCOL_VERSION = 1
STUDY_KEYS = ("$schema", "study", "command", "payload")


class StudyError(ValueError):
    """Raised when a study file cannot be read or is malformed."""


def _resolve_ref(value: Any, root: Path) -> Any:
    """Replace a ``{"$ref": "sibling.json"}`` object with the file contents."""

    if not isinstance(value, Mapping) or "$ref" not in value:
        return value
    if len(value) != 1:
        raise StudyError(
            "A $ref object must contain only the $ref key."
        )
    reference = value["$ref"]
    if not isinstance(reference, str) or not reference:
        raise StudyError("A $ref must be a non-empty relative path.")
    target = (root / reference).resolve()
    try:
        target.relative_to(root)
    except ValueError:
        raise StudyError(
            "$ref {!r} resolves outside the study directory.".format(reference)
        )
    if not target.is_file():
        raise StudyError("$ref target does not exist: {}".format(target))
    try:
        return json.loads(target.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise StudyError(
            "$ref target {} is not valid JSON: {}".format(target, error)
        )


def load_study(path: Path) -> Dict[str, Any]:
    """Read a study file, resolving payload-level ``$ref`` objects."""

    path = Path(path)
    if not path.is_file():
        raise StudyError("Study file does not exist: {}".format(path))
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise StudyError("{} is not valid JSON: {}".format(path, error))
    if not isinstance(document, Mapping):
        raise StudyError("A study file must contain a JSON object.")
    document = dict(document)
    unknown = sorted(set(document) - set(STUDY_KEYS))
    if unknown:
        raise StudyError(
            "Study file contains unsupported keys: {}.".format(", ".join(unknown))
        )
    command = document.get("command")
    if not isinstance(command, str) or not command:
        raise StudyError("A study file requires a non-empty command string.")
    payload = document.get("payload")
    if not isinstance(payload, Mapping):
        raise StudyError("A study file requires a payload object.")
    root = path.parent.resolve()
    document["payload"] = {
        key: _resolve_ref(value, root) for key, value in payload.items()
    }
    return document


def build_request(study: Mapping[str, Any]) -> Dict[str, Any]:
    """Build the worker request envelope for one loaded study."""

    return {
        "v": PROTOCOL_VERSION,
        "type": "request",
        "id": str(study.get("study") or "study"),
        "command": study["command"],
        "payload": dict(study["payload"]),
    }


__all__ = [
    "PROTOCOL_VERSION",
    "STUDY_KEYS",
    "StudyError",
    "build_request",
    "load_study",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli_study.py -v`
Expected: PASS, all six tests

- [ ] **Step 5: Add the check subcommand**

In `src/ananke_equilibrium/cli/main.py`, add these imports beside the existing ones:

```python
from pathlib import Path

from ..codec import decode_fd_payload
from ..codec import decode_tna_payload
from ..codec import decode_tna_prepare_payload
from ..contracts import ContractError
from ..codec import CodecError
from .study import StudyError
from .study import build_request
from .study import load_study
```

In `build_parser()`, before `return parser`, add:

```python
    check = subparsers.add_parser(
        "check",
        help="Validate a study file without solving it.",
    )
    check.add_argument("problem", type=Path, help="Path to problem.json")
```

Add this module-level mapping after the imports:

```python
_DECODERS = {
    "fd.solve": decode_fd_payload,
    "tna.prepare": decode_tna_prepare_payload,
    "tna.solve": decode_tna_payload,
}
```

Add this function before `main()`:

```python
def _check(path: Path) -> int:
    """Decode a study payload and report the first contract failure."""

    try:
        study = load_study(path)
    except StudyError as error:
        print("{}: {}".format(path, error), file=sys.stderr)
        return 1
    request = build_request(study)
    decoder = _DECODERS.get(request["command"])
    if decoder is None:
        print(
            "{}: no validator for command {!r}; solve it to validate.".format(
                path,
                request["command"],
            ),
            file=sys.stderr,
        )
        return 1
    try:
        decoder(request["payload"])
    except (CodecError, ContractError) as error:
        print("{}: {}".format(path, error), file=sys.stderr)
        return 1
    print("{}: valid {} study".format(path, request["command"]))
    return 0
```

In `main()`, before the `health` branch, add:

```python
    if args.command == "check":
        return _check(args.problem)
```

- [ ] **Step 6: Write the example study**

Create `studies/example-arch/problem.json`:

```json
{
  "$schema": "../../.vscode/ananke-problem.schema.json",
  "study": "example-arch",
  "command": "fd.solve",
  "payload": {
    "topology": {
      "kind": "line",
      "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0], [3.0, 0.0, 0.0], [4.0, 0.0, 0.0]],
      "edges": [[0, 1], [1, 2], [2, 3], [3, 4]],
      "length_unit": "m"
    },
    "supports": {
      "mode": "explicit",
      "node_ids": [0, 4]
    },
    "load_case": {
      "name": "gravity",
      "distribution": "uniform_nodes",
      "vectors": [[0.0, 0.0, -1.0]]
    },
    "settings": {
      "force_densities": 1.0,
      "sign_convention": "positive_tension"
    }
  }
}
```

- [ ] **Step 7: Verify check against the example**

Run: `ananke check studies/example-arch/problem.json`
Expected: prints `... valid fd.solve study` and exits 0

- [ ] **Step 8: Commit**

```bash
git add src/ananke_equilibrium/cli/study.py src/ananke_equilibrium/cli/main.py tests/test_cli_study.py studies/example-arch/problem.json
git commit -m "Load study files, resolve topology refs, and add ananke check"
```

---

## Task 3: The solve command

**Files:**
- Modify: `src/ananke_equilibrium/cli/main.py`
- Test: `tests/test_cli_solve.py`

**Interfaces:**
- Consumes: `cli.study.load_study`, `cli.study.build_request`, `worker.dispatch`
- Produces: `cli.main.solve_study(path: Path, out: Optional[Path] = None, archive: bool = False) -> int`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_solve.py`:

```python
from __future__ import annotations

import json
import shutil
from pathlib import Path

from ananke_equilibrium.cli.main import main
from ananke_equilibrium.cli.study import build_request
from ananke_equilibrium.cli.study import load_study
from ananke_equilibrium.worker import dispatch


EXAMPLE = Path(__file__).resolve().parents[1] / "studies" / "example-arch"


def copy_example(tmp_path):
    target = tmp_path / "example-arch"
    shutil.copytree(EXAMPLE, target)
    return target / "problem.json"


def test_solve_writes_a_result_file(tmp_path):
    problem = copy_example(tmp_path)
    exit_code = main(["solve", str(problem)])
    assert exit_code == 0
    result_path = problem.parent / "results" / "result.json"
    assert result_path.is_file()
    result = json.loads(result_path.read_text(encoding="utf-8"))
    assert result["vertices"]


def test_solve_matches_a_direct_dispatch_call(tmp_path):
    problem = copy_example(tmp_path)
    main(["solve", str(problem)])
    written = json.loads(
        (problem.parent / "results" / "result.json").read_text(encoding="utf-8")
    )
    direct = dispatch(build_request(load_study(problem)))
    assert written == direct["result"]


def test_solve_reports_a_contract_failure_and_exits_one(tmp_path, capsys):
    problem = copy_example(tmp_path)
    document = json.loads(problem.read_text(encoding="utf-8"))
    document["payload"]["supports"]["node_ids"] = [99]
    problem.write_text(json.dumps(document), encoding="utf-8")
    exit_code = main(["solve", str(problem)])
    captured = capsys.readouterr()
    assert exit_code == 1
    assert captured.err.strip()
    assert not (problem.parent / "results" / "result.json").exists()


def test_archive_writes_a_second_timestamped_copy(tmp_path):
    problem = copy_example(tmp_path)
    main(["solve", str(problem), "--archive"])
    results = sorted((problem.parent / "results").glob("*.json"))
    assert len(results) == 2
    assert (problem.parent / "results" / "result.json") in results
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_solve.py -v`
Expected: FAIL, `argument command: invalid choice: 'solve'`

- [ ] **Step 3: Add the solve command**

In `src/ananke_equilibrium/cli/main.py`, add to the imports:

```python
import json
from datetime import datetime

from ..worker import dispatch
```

In `build_parser()`, before `return parser`, add:

```python
    solve = subparsers.add_parser(
        "solve",
        help="Solve a study file and write its result.",
    )
    solve.add_argument("problem", type=Path, help="Path to problem.json")
    solve.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Result path. Defaults to results/result.json beside the study.",
    )
    solve.add_argument(
        "--archive",
        action="store_true",
        help="Also write a timestamped copy beside the result.",
    )
```

Add this function before `main()`:

```python
def solve_study(
    path: Path,
    out: Optional[Path] = None,
    archive: bool = False,
) -> int:
    """Solve one study file through the same dispatch Grasshopper uses."""

    try:
        study = load_study(path)
    except StudyError as error:
        print("{}: {}".format(path, error), file=sys.stderr)
        return 1
    response = dispatch(build_request(study))
    if response.get("type") == "error":
        error = response.get("error", {})
        print(
            "{}: {} ({})".format(
                path,
                error.get("message", "solve failed"),
                error.get("code", "unknown"),
            ),
            file=sys.stderr,
        )
        details = error.get("details")
        if details:
            print(json.dumps(details, indent=2), file=sys.stderr)
        return 1
    destination = out or (path.parent / "results" / "result.json")
    destination.parent.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(response["result"], indent=2, sort_keys=True)
    destination.write_text(payload + "\n", encoding="utf-8")
    print("{} -> {}".format(path, destination))
    if archive:
        stamp = datetime.now().strftime("%Y%m%dT%H%M%S")
        archived = destination.with_name(
            "{}-{}{}".format(destination.stem, stamp, destination.suffix)
        )
        archived.write_text(payload + "\n", encoding="utf-8")
        print("archived -> {}".format(archived))
    return 0
```

In `main()`, before the `check` branch, add:

```python
    if args.command == "solve":
        return solve_study(args.problem, out=args.out, archive=args.archive)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli_solve.py -v`
Expected: PASS, all four tests. The parity test is the important one: it proves the CLI and Grasshopper traverse one code path.

- [ ] **Step 5: Add the results directory to gitignore**

Append to `.gitignore`:

```gitignore
# Study results are build products; the problem file is the source.
studies/**/results/
```

- [ ] **Step 6: Commit**

```bash
git add src/ananke_equilibrium/cli/main.py tests/test_cli_solve.py .gitignore
git commit -m "Solve study files through dispatch and write results to disk"
```

---

## Task 4: Shape-tolerant result reading

**Files:**
- Create: `src/ananke_equilibrium/cli/results.py`
- Test: `tests/test_cli_results.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces:
  - `cli.results.ResultError(ValueError)`
  - `cli.results.thrust_vertices(result: Mapping[str, Any]) -> List[List[float]]`
  - `cli.results.thrust_faces(result: Mapping[str, Any]) -> List[List[int]]`
  - `cli.results.diagram(result: Mapping[str, Any], name: str) -> Optional[Dict[str, Any]]` where `name` is `"form_graph"` or `"force_graph"`, returning `{"vertices": [...], "edges": [...]}`
  - `cli.results.load_result(path: Path) -> Dict[str, Any]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_results.py`:

```python
from __future__ import annotations

import json

import pytest

from ananke_equilibrium.cli.results import ResultError
from ananke_equilibrium.cli.results import diagram
from ananke_equilibrium.cli.results import load_result
from ananke_equilibrium.cli.results import thrust_faces
from ananke_equilibrium.cli.results import thrust_vertices


FLAT_FD = {
    "kind": "solved_case",
    "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, -0.5]],
}
NESTED_TNA = {
    "kind": "tna_result",
    "equilibrium": {"vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 1.0]]},
    "form_graph": {
        "vertices": [
            {"id": 0, "point": [0.0, 0.0, 0.0]},
            {"id": 1, "point": [1.0, 0.0, 0.0]},
        ],
        "edges": [{"u": 0, "v": 1}],
        "faces": [{"vertices": [0, 1]}],
    },
    "force_graph": {
        "vertices": [{"id": 0, "point": [0.0, 0.0, 0.0]}],
        "edges": [],
    },
}
ENVELOPED_TNA = dict(NESTED_TNA, kind="Result", solver="tna", resultSchema="0.2")


def test_flat_fd_result_exposes_vertices():
    assert thrust_vertices(FLAT_FD) == [[0.0, 0.0, 0.0], [1.0, 0.0, -0.5]]


def test_nested_tna_result_prefers_the_equilibrium_block():
    assert thrust_vertices(NESTED_TNA) == [[0.0, 0.0, 0.0], [1.0, 0.0, 1.0]]


def test_enveloped_result_reads_identically_to_the_bare_one():
    assert thrust_vertices(ENVELOPED_TNA) == thrust_vertices(NESTED_TNA)
    assert diagram(ENVELOPED_TNA, "form_graph") == diagram(NESTED_TNA, "form_graph")


def test_faces_come_from_the_form_graph():
    assert thrust_faces(NESTED_TNA) == [[0, 1]]
    assert thrust_faces(FLAT_FD) == []


def test_diagram_returns_none_when_absent():
    assert diagram(FLAT_FD, "form_graph") is None


def test_diagram_rejects_an_unknown_name():
    with pytest.raises(ResultError, match="form_graph"):
        diagram(NESTED_TNA, "nonsense")


def test_load_result_reads_a_file(tmp_path):
    path = tmp_path / "result.json"
    path.write_text(json.dumps(NESTED_TNA), encoding="utf-8")
    assert load_result(path)["kind"] == "tna_result"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_results.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ananke_equilibrium.cli.results'`

- [ ] **Step 3: Write the reader**

Create `src/ananke_equilibrium/cli/results.py`:

```python
"""Read solved results without depending on the envelope shape.

Two result envelopes exist in this project's history. The unified envelope
copies the inner payload key for key and only overwrites ``kind``, so keying
off ``equilibrium``, ``vertices``, ``form_graph`` and ``force_graph`` reads
both shapes and will keep reading the next one.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from typing import Dict
from typing import List
from typing import Mapping
from typing import Optional


DIAGRAM_NAMES = ("form_graph", "force_graph")


class ResultError(ValueError):
    """Raised when a result file cannot be read or lacks required data."""


def _mapping(value: Any) -> Dict[str, Any]:
    return dict(value) if isinstance(value, Mapping) else {}


def load_result(path: Path) -> Dict[str, Any]:
    """Read one result file."""

    path = Path(path)
    if not path.is_file():
        raise ResultError("Result file does not exist: {}".format(path))
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        raise ResultError("{} is not valid JSON: {}".format(path, error))
    if not isinstance(document, Mapping):
        raise ResultError("A result file must contain a JSON object.")
    return dict(document)


def thrust_vertices(result: Mapping[str, Any]) -> List[List[float]]:
    """Return solved 3D vertices, whether TNA-nested or FD-flat."""

    equilibrium = _mapping(result.get("equilibrium"))
    vertices = equilibrium.get("vertices") or result.get("vertices") or []
    return [[float(value) for value in point] for point in vertices]


def thrust_faces(result: Mapping[str, Any]) -> List[List[int]]:
    """Return face cycles from the form diagram, or an empty list."""

    form_graph = _mapping(result.get("form_graph"))
    faces = form_graph.get("faces") or []
    return [
        [int(index) for index in _mapping(face).get("vertices") or []]
        for face in faces
        if isinstance(face, Mapping)
    ]


def diagram(
    result: Mapping[str, Any],
    name: str,
) -> Optional[Dict[str, Any]]:
    """Return one reciprocal diagram as plain vertices and edges."""

    if name not in DIAGRAM_NAMES:
        raise ResultError(
            "Diagram name must be one of {}.".format(", ".join(DIAGRAM_NAMES))
        )
    graph = _mapping(result.get(name))
    vertices = graph.get("vertices") or []
    if not vertices:
        return None
    return {
        "vertices": [
            {
                "id": int(vertex["id"]),
                "point": [float(value) for value in vertex["point"]],
            }
            for vertex in vertices
        ],
        "edges": [
            {"u": int(edge["u"]), "v": int(edge["v"])}
            for edge in graph.get("edges") or []
        ],
    }


__all__ = [
    "DIAGRAM_NAMES",
    "ResultError",
    "diagram",
    "load_result",
    "thrust_faces",
    "thrust_vertices",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli_results.py -v`
Expected: PASS, all seven tests

- [ ] **Step 5: Commit**

```bash
git add src/ananke_equilibrium/cli/results.py tests/test_cli_results.py
git commit -m "Read results without depending on the envelope shape"
```

---

## Task 5: The plot command

**Files:**
- Create: `src/ananke_equilibrium/cli/plot.py`
- Modify: `src/ananke_equilibrium/cli/main.py`
- Test: `tests/test_cli_plot.py`

**Interfaces:**
- Consumes: `cli.results.diagram`, `cli.results.load_result`, `cli.results.ResultError`
- Produces: `cli.plot.plot_result(result: Mapping[str, Any], out: Path) -> Path`

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_plot.py`:

```python
from __future__ import annotations

import json

import pytest

from ananke_equilibrium.cli.main import main
from ananke_equilibrium.cli.plot import plot_result
from ananke_equilibrium.cli.results import ResultError


TNA_RESULT = {
    "kind": "tna_result",
    "equilibrium": {"vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 1.0]]},
    "form_graph": {
        "vertices": [
            {"id": 0, "point": [0.0, 0.0, 0.0]},
            {"id": 1, "point": [1.0, 0.0, 0.0]},
            {"id": 2, "point": [1.0, 1.0, 0.0]},
        ],
        "edges": [{"u": 0, "v": 1}, {"u": 1, "v": 2}],
    },
    "force_graph": {
        "vertices": [
            {"id": 0, "point": [0.0, 0.0, 0.0]},
            {"id": 1, "point": [0.5, 0.0, 0.0]},
        ],
        "edges": [{"u": 0, "v": 1}],
    },
}


def test_plot_writes_a_png(tmp_path):
    out = tmp_path / "diagrams.png"
    written = plot_result(TNA_RESULT, out)
    assert written == out
    assert out.is_file()
    assert out.stat().st_size > 0


def test_plot_writes_an_svg(tmp_path):
    out = tmp_path / "diagrams.svg"
    plot_result(TNA_RESULT, out)
    assert out.read_text(encoding="utf-8").lstrip().startswith("<?xml")


def test_plot_rejects_a_result_without_diagrams(tmp_path):
    with pytest.raises(ResultError, match="no reciprocal diagrams"):
        plot_result({"kind": "solved_case", "vertices": []}, tmp_path / "x.png")


def test_plot_command_defaults_beside_the_result(tmp_path):
    result_path = tmp_path / "result.json"
    result_path.write_text(json.dumps(TNA_RESULT), encoding="utf-8")
    assert main(["plot", str(result_path)]) == 0
    assert (tmp_path / "result.png").is_file()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_plot.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ananke_equilibrium.cli.plot'`

- [ ] **Step 3: Write the plotter**

Create `src/ananke_equilibrium/cli/plot.py`:

```python
"""Headless form and force diagrams from a solved result.

Graphic statics is planar, so this uses matplotlib rather than the 3D viewer.
The output is a committable artefact: it diffs, it goes in a document, and it
needs no display server.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
from typing import Dict
from typing import Mapping

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt  # noqa: E402  (backend must be set first)

from .results import ResultError  # noqa: E402
from .results import diagram  # noqa: E402


def _draw(axis: Any, graph: Dict[str, Any], title: str, colour: str) -> None:
    points = {vertex["id"]: vertex["point"] for vertex in graph["vertices"]}
    for edge in graph["edges"]:
        start = points.get(edge["u"])
        end = points.get(edge["v"])
        if start is None or end is None:
            continue
        axis.plot(
            [start[0], end[0]],
            [start[1], end[1]],
            color=colour,
            linewidth=1.2,
            solid_capstyle="round",
        )
    xs = [point[0] for point in points.values()]
    ys = [point[1] for point in points.values()]
    axis.scatter(xs, ys, s=8, color=colour, zorder=3)
    axis.set_title(title)
    axis.set_aspect("equal", adjustable="datalim")
    axis.axis("off")


def plot_result(result: Mapping[str, Any], out: Path) -> Path:
    """Draw the reciprocal form and force pair side by side."""

    form = diagram(result, "form_graph")
    force = diagram(result, "force_graph")
    if form is None and force is None:
        raise ResultError(
            "This result carries no reciprocal diagrams; it is not a TNA result."
        )
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    figure, axes = plt.subplots(1, 2, figsize=(11, 5))
    try:
        if form is not None:
            _draw(axes[0], form, "Form diagram", "#1f4e79")
        else:
            axes[0].axis("off")
        if force is not None:
            _draw(axes[1], force, "Force diagram", "#a33a1f")
        else:
            axes[1].axis("off")
        figure.tight_layout()
        figure.savefig(out, dpi=200)
    finally:
        plt.close(figure)
    return out


__all__ = ["plot_result"]
```

- [ ] **Step 4: Add the plot subcommand**

In `src/ananke_equilibrium/cli/main.py`, add to the imports:

```python
from .plot import plot_result
from .results import ResultError
from .results import load_result
```

In `build_parser()`, before `return parser`, add:

```python
    plot = subparsers.add_parser(
        "plot",
        help="Draw form and force diagrams from a result file.",
    )
    plot.add_argument("result", type=Path, help="Path to result.json")
    plot.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Image path. Defaults to the result path with a .png suffix.",
    )
```

Add this function before `main()`:

```python
def _plot(path: Path, out: Optional[Path]) -> int:
    try:
        result = load_result(path)
        written = plot_result(result, out or path.with_suffix(".png"))
    except ResultError as error:
        print("{}: {}".format(path, error), file=sys.stderr)
        return 1
    print("{} -> {}".format(path, written))
    return 0
```

In `main()`, add before the `health` branch:

```python
    if args.command == "plot":
        return _plot(args.result, args.out)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_cli_plot.py -v`
Expected: PASS, all four tests

- [ ] **Step 6: Commit**

```bash
git add src/ananke_equilibrium/cli/plot.py src/ananke_equilibrium/cli/main.py tests/test_cli_plot.py
git commit -m "Draw reciprocal form and force diagrams headlessly"
```

---

## Task 6: The view command and the viz extra

**Files:**
- Create: `src/ananke_equilibrium/cli/view.py`
- Modify: `src/ananke_equilibrium/cli/main.py`, `pyproject.toml`
- Test: `tests/test_cli_view.py`

**Interfaces:**
- Consumes: `cli.results.thrust_vertices`, `cli.results.thrust_faces`, `cli.results.diagram`
- Produces:
  - `cli.view.ViewerUnavailableError(RuntimeError)`
  - `cli.view.build_scene_objects(result: Mapping[str, Any]) -> List[Any]` returning COMPAS `Mesh` and `Graph` objects
  - `cli.view.view_result(result: Mapping[str, Any]) -> int`

Note: `build_scene_objects` needs only `compas`, which is a required dependency, so it is testable without installing `compas_viewer`. Only `view_result` needs the viewer, and it imports it lazily.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_view.py`:

```python
from __future__ import annotations

import pytest

from compas.datastructures import Graph
from compas.datastructures import Mesh

from ananke_equilibrium.cli.view import ViewerUnavailableError
from ananke_equilibrium.cli.view import build_scene_objects
from ananke_equilibrium.cli.view import view_result


TNA_RESULT = {
    "kind": "tna_result",
    "equilibrium": {
        "vertices": [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.5],
            [1.0, 1.0, 0.5],
            [0.0, 1.0, 0.0],
        ]
    },
    "form_graph": {
        "vertices": [
            {"id": 0, "point": [0.0, 0.0, 0.0]},
            {"id": 1, "point": [1.0, 0.0, 0.0]},
            {"id": 2, "point": [1.0, 1.0, 0.0]},
            {"id": 3, "point": [0.0, 1.0, 0.0]},
        ],
        "edges": [{"u": 0, "v": 1}, {"u": 1, "v": 2}],
        "faces": [{"vertices": [0, 1, 2, 3]}],
    },
    "force_graph": {
        "vertices": [
            {"id": 0, "point": [0.0, 0.0, 0.0]},
            {"id": 1, "point": [0.5, 0.0, 0.0]},
        ],
        "edges": [{"u": 0, "v": 1}],
    },
}


def test_build_scene_objects_returns_a_mesh_and_graphs():
    objects = build_scene_objects(TNA_RESULT)
    kinds = [type(item).__name__ for item in objects]
    assert "Mesh" in kinds
    assert kinds.count("Graph") == 2


def test_the_mesh_carries_the_solved_z_values():
    mesh = next(
        item for item in build_scene_objects(TNA_RESULT) if isinstance(item, Mesh)
    )
    zs = sorted(mesh.vertex_attribute(key, "z") for key in mesh.vertices())
    assert zs == [0.0, 0.0, 0.5, 0.5]


def test_a_flat_result_still_yields_a_graph_free_scene():
    objects = build_scene_objects({"kind": "solved_case", "vertices": [[0.0, 0.0, 0.0]]})
    assert all(not isinstance(item, Graph) for item in objects)


def test_view_result_raises_when_the_viewer_is_missing(monkeypatch):
    monkeypatch.setattr(
        "ananke_equilibrium.cli.view._import_viewer",
        lambda: (_ for _ in ()).throw(ImportError("no compas_viewer")),
    )
    with pytest.raises(ViewerUnavailableError, match="viz"):
        view_result(TNA_RESULT)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_view.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ananke_equilibrium.cli.view'`

- [ ] **Step 3: Write the viewer bridge**

Create `src/ananke_equilibrium/cli/view.py`:

```python
"""Interactive 3D viewing of a solved result through compas_viewer.

Scene construction is deliberately separate from the viewer import, so the
translation from result JSON to real COMPAS datastructures is testable
without a display or the optional viz extra installed.
"""

from __future__ import annotations

from typing import Any
from typing import List
from typing import Mapping

from compas.datastructures import Graph
from compas.datastructures import Mesh

from .results import diagram
from .results import thrust_faces
from .results import thrust_vertices


class ViewerUnavailableError(RuntimeError):
    """Raised when compas_viewer is not installed."""


def _graph_from_diagram(payload: Mapping[str, Any]) -> Graph:
    graph = Graph()
    for vertex in payload["vertices"]:
        x, y, z = vertex["point"]
        graph.add_node(key=int(vertex["id"]), x=float(x), y=float(y), z=float(z))
    for edge in payload["edges"]:
        graph.add_edge(int(edge["u"]), int(edge["v"]))
    return graph


def build_scene_objects(result: Mapping[str, Any]) -> List[Any]:
    """Turn a result payload into COMPAS objects a scene can hold."""

    objects: List[Any] = []
    vertices = thrust_vertices(result)
    faces = thrust_faces(result)
    if vertices and faces:
        objects.append(Mesh.from_vertices_and_faces(vertices, faces))
    for name in ("form_graph", "force_graph"):
        payload = diagram(result, name)
        if payload is not None:
            objects.append(_graph_from_diagram(payload))
    return objects


def _import_viewer() -> Any:
    """Import compas_viewer lazily so the extra stays optional."""

    from compas_viewer import Viewer

    return Viewer


def view_result(result: Mapping[str, Any]) -> int:
    """Open an interactive viewer on one result."""

    try:
        viewer_class = _import_viewer()
    except ImportError as error:
        raise ViewerUnavailableError(
            "compas_viewer is not installed. Install the viz extra: "
            'python -m pip install -e ".[viz]"'
        ) from error
    objects = build_scene_objects(result)
    if not objects:
        raise ViewerUnavailableError(
            "This result carries no geometry to display."
        )
    viewer = viewer_class()
    for item in objects:
        viewer.scene.add(item)
    viewer.show()
    return 0


__all__ = [
    "ViewerUnavailableError",
    "build_scene_objects",
    "view_result",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_cli_view.py -v`
Expected: PASS, all four tests

- [ ] **Step 5: Add the view subcommand**

In `src/ananke_equilibrium/cli/main.py`, add to the imports:

```python
from .view import ViewerUnavailableError
from .view import view_result
```

In `build_parser()`, before `return parser`, add:

```python
    view = subparsers.add_parser(
        "view",
        help="Open a solved result in the interactive 3D viewer.",
    )
    view.add_argument("result", type=Path, help="Path to result.json")
```

Add this function before `main()`:

```python
def _view(path: Path) -> int:
    try:
        return view_result(load_result(path))
    except (ResultError, ViewerUnavailableError) as error:
        print("{}: {}".format(path, error), file=sys.stderr)
        return 1
```

In `main()`, add before the `health` branch:

```python
    if args.command == "view":
        return _view(args.result)
```

- [ ] **Step 6: Add the viz extra**

In `pyproject.toml`, after the `patterns` extra, add:

```toml
# Interactive 3D viewing. PySide6 is large and Rhino never imports it, so this
# stays opt-in; tests/test_environment_pins.py proves installing it does not
# move the pinned numpy, scipy, or compas.
viz = [
    "compas_viewer==2.0.2",
]
```

- [ ] **Step 7: Commit**

```bash
git add src/ananke_equilibrium/cli/view.py src/ananke_equilibrium/cli/main.py tests/test_cli_view.py pyproject.toml
git commit -m "Add the 3D viewer bridge behind an optional viz extra"
```

---

## Task 7: Worker-side request capture

**Files:**
- Create: `src/ananke_equilibrium/capture.py`
- Modify: `src/ananke_equilibrium/worker.py`
- Test: `tests/test_capture.py`

**Interfaces:**
- Consumes: `cli.study.load_study` (in tests only), `codec.MAX_FRAME_BYTES`
- Produces:
  - `capture.capture_directory() -> Optional[Path]` reading `ANANKE_CAPTURE_DIR`
  - `capture.capture_request(request: Mapping[str, Any], directory: Path) -> Optional[Path]`

- [ ] **Step 1: Write the failing test**

Create `tests/test_capture.py`:

```python
from __future__ import annotations

import json

from ananke_equilibrium.capture import capture_directory
from ananke_equilibrium.capture import capture_request
from ananke_equilibrium.cli.study import build_request
from ananke_equilibrium.cli.study import load_study


REQUEST = {
    "v": 1,
    "type": "request",
    "id": "canvas-1",
    "command": "fd.solve",
    "payload": {
        "topology": {
            "kind": "line",
            "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
            "edges": [[0, 1], [1, 2]],
        },
        "supports": {"mode": "explicit", "node_ids": [0, 2]},
        "load_case": {
            "name": "gravity",
            "distribution": "point",
            "node_ids": [1],
            "vectors": [[0.0, 0.0, -1.0]],
        },
        "settings": {"force_densities": 1.0},
    },
}


def test_capture_directory_is_none_when_unset(monkeypatch):
    monkeypatch.delenv("ANANKE_CAPTURE_DIR", raising=False)
    assert capture_directory() is None


def test_capture_directory_reads_the_variable(monkeypatch, tmp_path):
    monkeypatch.setenv("ANANKE_CAPTURE_DIR", str(tmp_path))
    assert capture_directory() == tmp_path


def test_capture_writes_a_loadable_study_file(tmp_path):
    written = capture_request(REQUEST, tmp_path)
    assert written is not None
    study = load_study(written)
    assert study["command"] == "fd.solve"
    assert build_request(study)["payload"] == REQUEST["payload"]


def test_capture_skips_non_solve_commands(tmp_path):
    request = dict(REQUEST, command="system.health", payload={})
    assert capture_request(request, tmp_path) is None
    assert list(tmp_path.glob("*.json")) == []


def test_capture_skips_oversized_requests(tmp_path):
    from ananke_equilibrium.codec import MAX_FRAME_BYTES

    request = json.loads(json.dumps(REQUEST))
    request["payload"]["topology"]["metadata"] = {"pad": "x" * (MAX_FRAME_BYTES + 1)}
    assert capture_request(request, tmp_path) is None


def test_capture_names_files_distinctly(tmp_path):
    first = capture_request(REQUEST, tmp_path)
    second = capture_request(REQUEST, tmp_path)
    assert first != second
    assert len(list(tmp_path.glob("*.json"))) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_capture.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ananke_equilibrium.capture'`

- [ ] **Step 3: Write the capture module**

Create `src/ananke_equilibrium/capture.py`:

```python
"""Write incoming worker requests to disk as replayable study files.

Rhino's environment is inherited by the worker process it spawns, so setting
one variable turns every canvas solve into a study file that the CLI can
re-run. This needs no C# change, which is the point.
"""

from __future__ import annotations

from datetime import datetime
import json
import os
from pathlib import Path
import sys
from typing import Any
from typing import Mapping
from typing import Optional

from .codec import MAX_FRAME_BYTES


CAPTURE_ENV_VAR = "ANANKE_CAPTURE_DIR"
CAPTURED_COMMANDS = frozenset(
    (
        "fd.solve",
        "tna.prepare",
        "tna.solve",
        "dem.tessellate",
        "fea.model",
    )
)


def capture_directory() -> Optional[Path]:
    """Return the configured capture directory, or None when disabled."""

    raw = os.environ.get(CAPTURE_ENV_VAR, "").strip()
    if not raw:
        return None
    return Path(raw)


def capture_request(
    request: Mapping[str, Any],
    directory: Path,
) -> Optional[Path]:
    """Write one solve request as a study file, returning the path written."""

    command = request.get("command")
    if command not in CAPTURED_COMMANDS:
        return None
    payload = request.get("payload")
    if not isinstance(payload, Mapping):
        return None
    study = {
        "study": str(request.get("id") or "captured"),
        "command": command,
        "payload": dict(payload),
    }
    try:
        document = json.dumps(study, indent=2, sort_keys=True)
    except (TypeError, ValueError) as error:
        print(
            "capture: request {!r} is not JSON serialisable: {}".format(
                request.get("id"),
                error,
            ),
            file=sys.stderr,
        )
        return None
    if len(document.encode("utf-8")) > MAX_FRAME_BYTES:
        print(
            "capture: skipping {} request above {} bytes.".format(
                command,
                MAX_FRAME_BYTES,
            ),
            file=sys.stderr,
        )
        return None
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%dT%H%M%S%f")
    path = directory / "{}-{}.json".format(stamp, command.replace(".", "-"))
    path.write_text(document + "\n", encoding="utf-8")
    return path


__all__ = [
    "CAPTURED_COMMANDS",
    "CAPTURE_ENV_VAR",
    "capture_directory",
    "capture_request",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_capture.py -v`
Expected: PASS, all six tests

- [ ] **Step 5: Hook capture into serve()**

In `src/ananke_equilibrium/worker.py`, add to the imports:

```python
from .capture import capture_directory
from .capture import capture_request
```

In `serve()`, immediately after the `if request is None: return 0` block and before the `with redirect_stdout(sys.stderr):` line, insert:

```python
        capture_root = capture_directory()
        if capture_root is not None and isinstance(request, Mapping):
            try:
                capture_request(request, capture_root)
            except OSError as error:
                # Capture is a diagnostic convenience; never fail a solve for it.
                print(
                    "{}: capture failed: {}".format(WORKER_NAME, error),
                    file=sys.stderr,
                )
```

- [ ] **Step 6: Add an end-to-end capture test**

Append to `tests/test_capture.py`:

```python
def test_serve_captures_a_request_it_processes(monkeypatch, tmp_path):
    from io import BytesIO

    from ananke_equilibrium.codec import encode_frame
    from ananke_equilibrium.worker import serve

    monkeypatch.setenv("ANANKE_CAPTURE_DIR", str(tmp_path))
    source = BytesIO(encode_frame(REQUEST))
    target = BytesIO()
    serve(input_stream=source, output_stream=target)
    captured = list(tmp_path.glob("*-fd-solve.json"))
    assert len(captured) == 1
```

- [ ] **Step 7: Run the full capture suite**

Run: `python -m pytest tests/test_capture.py -v`
Expected: PASS, all seven tests

- [ ] **Step 8: Commit**

```bash
git add src/ananke_equilibrium/capture.py src/ananke_equilibrium/worker.py tests/test_capture.py
git commit -m "Capture worker requests as replayable study files"
```

---

## Task 8: Make the health report honest

**Files:**
- Modify: `src/ananke_equilibrium/worker.py`, `docs/compas-suite-adoption.md`
- Test: `tests/test_health_honesty.py`

**Interfaces:**
- Consumes: nothing from earlier tasks
- Produces: `worker._importable(module_name: str) -> bool`; `health_payload()` gains `masonry.tessellate` and `masonry.stability` and keeps `masonry` as the conjunction of both

Background: `health_payload()` currently derives every capability from `importlib.metadata.version`, which reports a package as present even when importing it raises. `compas_cra` 0.4.0 is exactly that case in this environment: it installs, and `import compas_cra.equilibrium` raises `AttributeError` because its pinned pyomo 6.4.2 calls the removed `np.float_`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_health_honesty.py`:

```python
from __future__ import annotations

import ananke_equilibrium.worker as worker


def test_importable_is_true_for_a_real_module():
    assert worker._importable("json") is True


def test_importable_is_false_for_a_module_that_raises(monkeypatch):
    def explode(name):
        raise AttributeError("`np.float_` was removed in the NumPy 2.0 release.")

    monkeypatch.setattr(worker.importlib, "import_module", explode)
    assert worker._importable("compas_cra.equilibrium") is False


def test_masonry_splits_tessellation_from_stability():
    capabilities = worker.health_payload()["capabilities"]
    assert "masonry.tessellate" in capabilities
    assert "masonry.stability" in capabilities
    assert capabilities["masonry"] == (
        capabilities["masonry.tessellate"] and capabilities["masonry.stability"]
    )


def test_stability_is_false_while_compas_cra_cannot_import():
    capabilities = worker.health_payload()["capabilities"]
    if worker._importable("compas_cra.equilibrium"):
        assert capabilities["masonry.stability"] is True
    else:
        assert capabilities["masonry.stability"] is False
        assert capabilities["masonry"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_health_honesty.py -v`
Expected: FAIL with `AttributeError: module 'ananke_equilibrium.worker' has no attribute '_importable'`

- [ ] **Step 3: Add the import check**

In `src/ananke_equilibrium/worker.py`, add to the imports:

```python
import importlib
```

Add this function immediately after `_distribution_version`:

```python
def _importable(module_name: str) -> bool:
    """Return whether a module actually imports in this environment.

    Distribution metadata only proves a package was installed. A package can
    install cleanly and still fail at import, which is what an incompatible
    transitive pin looks like. Capability flags must follow the import.
    """

    try:
        importlib.import_module(module_name)
    except Exception:
        return False
    return True
```

- [ ] **Step 4: Split the masonry capability**

In `health_payload()`, replace the existing `"masonry"` entry in the capabilities dictionary with:

```python
            # Tessellation needs compas_dem only. Staged stability additionally
            # needs compas_cra, whose pinned pyomo cannot import under numpy 2,
            # so these are separate claims and only one of them is currently
            # true. See docs/superpowers/specs/2026-08-03-vscode-design-bench-design.md.
            "masonry.tessellate": _importable("compas_dem.models"),
            "masonry.stability": _importable("compas_cra.equilibrium"),
            "masonry": (
                _importable("compas_dem.models")
                and _importable("compas_cra.equilibrium")
            ),
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_health_honesty.py -v`
Expected: PASS, all four tests

- [ ] **Step 6: Confirm the reported state**

Run: `ananke health`
Expected: `masonry.tessellate True`, `masonry.stability False`, `masonry False`

- [ ] **Step 7: Correct the adoption document**

In `docs/compas-suite-adoption.md`, replace the paragraph beginning "Every family package is now installed and imports cleanly" with:

```markdown
Every family package is installed, and all but one import cleanly with `compas`,
`numpy` and `scipy` unmoved. The exception is `compas_cra`, which hard-pins
`pyomo==6.4.2`; that pyomo calls `np.float_`, removed in NumPy 2.0, so
`compas_cra.equilibrium` raises on import and `compas_dem.analysis.cra` raises
with it. Overriding the pin does not help: pyomo 6.8.0 and later import cleanly
but fail during the solve in `nl_writer.py`, and pyomo 6.4.2 additionally
breaks on Python 3.11 and later. Coupled rigid-block analysis therefore needs
its own Python 3.10 environment with numpy below 2 and IPOPT on PATH.

So the remaining gap is partly components and partly one genuine version
conflict: the contracts and capability flags exist, most backends are present,
and the Grasshopper surface for masonry, fabrication, engineering and delivery
has still to be built.
```

- [ ] **Step 8: Commit**

```bash
git add src/ananke_equilibrium/worker.py tests/test_health_honesty.py docs/compas-suite-adoption.md
git commit -m "Report capabilities from imports, and split masonry honestly"
```

---

## Task 9: The dem.tessellate worker command

**Files:**
- Create: `src/ananke_equilibrium/dem.py`
- Modify: `src/ananke_equilibrium/worker.py`
- Test: `tests/test_dem_tessellate.py`

**Interfaces:**
- Consumes: `cli.results.thrust_vertices`, `cli.results.thrust_faces`
- Produces:
  - `dem.TessellationError(ValueError)`
  - `dem.PATTERN_NAMES: Tuple[str, ...]`
  - `dem.tessellate_payload(payload: Mapping[str, Any]) -> Dict[str, Any]` returning `{"kind": "BlockModel", "blockModel": <compas json str>, "blocks": int, "contacts": int, "pattern": str, "compasVersion": str}`

Background verified during design: `BlockModel.from_meshpattern(mesh, 'Hex', tmin=0.15, tmax=0.25)` returned 114 blocks on a dome mesh and serialised through `compas.data.json_dumps`. `BlockModel.from_arch` is `raise NotImplementedError`, so do not use the template factories. Pattern names are capitalised and validated by `compas_libigl`; an unknown name raises `ValueError` listing the supported set.

- [ ] **Step 1: Write the failing test**

Create `tests/test_dem_tessellate.py`:

```python
from __future__ import annotations

import math

import pytest

from ananke_equilibrium.dem import PATTERN_NAMES
from ananke_equilibrium.dem import TessellationError
from ananke_equilibrium.dem import tessellate_payload


def dome_result(n=6, span=10.0, rise=3.0):
    vertices = []
    for j in range(n + 1):
        for i in range(n + 1):
            x = i / n * span - span / 2
            y = j / n * span - span / 2
            radius = math.hypot(x, y)
            z = max(0.0, rise * math.cos(radius / (span * 0.7) * math.pi / 2))
            vertices.append([x, y, z])
    faces = [
        {
            "vertices": [
                j * (n + 1) + i,
                j * (n + 1) + i + 1,
                (j + 1) * (n + 1) + i + 1,
                (j + 1) * (n + 1) + i,
            ]
        }
        for j in range(n)
        for i in range(n)
    ]
    return {
        "kind": "tna_result",
        "equilibrium": {"vertices": vertices},
        "form_graph": {"vertices": [], "edges": [], "faces": faces},
    }


def test_hex_is_a_supported_pattern():
    assert "Hex" in PATTERN_NAMES


def test_tessellation_returns_blocks_and_serialises():
    payload = {
        "result": dome_result(),
        "settings": {"pattern": "Hex", "tmin": 0.15, "tmax": 0.25},
    }
    out = tessellate_payload(payload)
    assert out["kind"] == "BlockModel"
    assert out["blocks"] > 0
    assert out["pattern"] == "Hex"
    assert out["blockModel"].startswith("{")


def test_tessellation_reports_contacts():
    payload = {
        "result": dome_result(),
        "settings": {"pattern": "Hex", "tmin": 0.15, "tmax": 0.25},
    }
    out = tessellate_payload(payload)
    assert out["contacts"] > 0, (
        "Contact detection returned no interfaces. Tune the tolerance in "
        "tessellate_payload or record why it cannot be reached."
    )


def test_unknown_pattern_is_rejected_with_the_supported_list():
    payload = {"result": dome_result(), "settings": {"pattern": "hex"}}
    with pytest.raises(TessellationError, match="Hex"):
        tessellate_payload(payload)


def test_a_result_without_faces_is_rejected():
    payload = {
        "result": {"kind": "solved_case", "vertices": [[0.0, 0.0, 0.0]]},
        "settings": {"pattern": "Hex"},
    }
    with pytest.raises(TessellationError, match="faces"):
        tessellate_payload(payload)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_dem_tessellate.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ananke_equilibrium.dem'`

- [ ] **Step 3: Write the tessellation adapter**

Create `src/ananke_equilibrium/dem.py`:

```python
"""Tessellate a solved thrust surface into a discrete block model.

This is the geometric half of the masonry pipeline. It says nothing about
whether the assembly stands up; coupled rigid-block stability needs
compas_cra, which cannot import in this environment. See the design spec.
"""

from __future__ import annotations

from typing import Any
from typing import Dict
from typing import Mapping
from typing import Tuple

from .cli.results import thrust_faces
from .cli.results import thrust_vertices


# The names compas_libigl.mapping.map_pattern_to_mesh accepts. They are
# capitalised, and it rejects lowercase spellings.
PATTERN_NAMES: Tuple[str, ...] = (
    "Hex",
    "Tri",
    "Octo",
    "Square",
    "Rhombus",
    "HexTri",
    "DissectedSquare",
    "DissectedTriangle",
    "DissectedHexQuad",
    "DissectedHexTri",
    "Floret",
    "Pythagorean",
    "Brick",
    "Weave",
    "ZigZag",
    "HexBigTri",
    "Dodeca",
    "SquareTri",
)

DEFAULT_PATTERN = "Hex"


class TessellationError(ValueError):
    """Raised when a block model cannot be built from a result."""


def tessellate_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Build a block model from a solved result and report its size."""

    result = payload.get("result")
    if not isinstance(result, Mapping):
        raise TessellationError("dem.tessellate requires a result object.")
    settings = payload.get("settings")
    settings = dict(settings) if isinstance(settings, Mapping) else {}

    pattern = str(settings.get("pattern", DEFAULT_PATTERN))
    if pattern not in PATTERN_NAMES:
        raise TessellationError(
            "Pattern {!r} is not supported. Choose from: {}.".format(
                pattern,
                ", ".join(PATTERN_NAMES),
            )
        )

    vertices = thrust_vertices(result)
    faces = thrust_faces(result)
    if not vertices:
        raise TessellationError("The result carries no solved vertices.")
    if not faces:
        raise TessellationError(
            "The result carries no faces, so no surface can be tessellated. "
            "Tessellation needs a faced TNA result, not a line network."
        )

    try:
        import compas
        from compas.data import json_dumps
        from compas.datastructures import Mesh
        from compas_dem.models import BlockModel
    except ImportError as error:
        raise TessellationError(
            "compas_dem is not installed. Install the masonry extra: "
            'python -m pip install -e ".[masonry]"'
        ) from error

    mesh = Mesh.from_vertices_and_faces(vertices, faces)
    tmin = settings.get("tmin")
    tmax = settings.get("tmax")
    try:
        model = BlockModel.from_meshpattern(
            mesh,
            pattern,
            tmin=float(tmin) if tmin is not None else None,
            tmax=float(tmax) if tmax is not None else None,
        )
    except ValueError as error:
        raise TessellationError(str(error)) from error

    model.compute_contacts()
    blocks = len(list(model.elements()))
    contacts = len(list(model.contacts()))

    return {
        "kind": "BlockModel",
        "blockModel": json_dumps(model),
        "blocks": blocks,
        "contacts": contacts,
        "pattern": pattern,
        "compasVersion": compas.__version__,
    }


__all__ = [
    "DEFAULT_PATTERN",
    "PATTERN_NAMES",
    "TessellationError",
    "tessellate_payload",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_dem_tessellate.py -v`
Expected: four PASS. `test_tessellation_reports_contacts` may FAIL, because `compute_contacts()` returned zero on a dome fixture during design verification.

- [ ] **Step 5: Resolve the contact count**

If `test_tessellation_reports_contacts` fails, investigate before proceeding. `model.compute_contacts()` accepts tolerance arguments; inspect them with:

```bash
python -c "import inspect; from compas_dem.models import BlockModel; print(inspect.signature(BlockModel.compute_contacts)); print(inspect.getdoc(BlockModel.compute_contacts))"
```

Pass the relevant tolerance through from `settings` (add a `tolerance` key handled the same way as `tmin`) and re-run. If no tolerance produces contacts on this fixture, do **not** delete the test: mark it `@pytest.mark.xfail(reason="...", strict=True)` with the specific finding, and record the finding in the spec's risk section. A tessellation producing no interfaces is a picture, not a model, and that has to stay visible.

- [ ] **Step 6: Register the worker command**

In `src/ananke_equilibrium/worker.py`, add `"dem.tessellate"` to `ALLOWED_COMMANDS`.

In `dispatch()`, before the final defensive `raise ProtocolError`, add:

```python
        if command == "dem.tessellate":
            from .dem import TessellationError
            from .dem import tessellate_payload

            try:
                return result_response(request_id, tessellate_payload(payload))
            except TessellationError as error:
                raise ProtocolError(
                    "dem_tessellate_failed",
                    str(error),
                    {"request_id": request_id},
                )
```

- [ ] **Step 7: Test the command through dispatch**

Append to `tests/test_dem_tessellate.py`:

```python
def test_dispatch_exposes_dem_tessellate():
    from ananke_equilibrium.worker import ALLOWED_COMMANDS
    from ananke_equilibrium.worker import dispatch

    assert "dem.tessellate" in ALLOWED_COMMANDS
    response = dispatch(
        {
            "v": 1,
            "type": "request",
            "id": "t1",
            "command": "dem.tessellate",
            "payload": {
                "result": dome_result(),
                "settings": {"pattern": "Hex", "tmin": 0.15, "tmax": 0.25},
            },
        }
    )
    assert response["type"] == "result"
    assert response["result"]["blocks"] > 0


def test_dispatch_reports_a_bad_pattern_as_a_protocol_error():
    from ananke_equilibrium.worker import dispatch

    response = dispatch(
        {
            "v": 1,
            "type": "request",
            "id": "t2",
            "command": "dem.tessellate",
            "payload": {"result": dome_result(), "settings": {"pattern": "hex"}},
        }
    )
    assert response["type"] == "error"
    assert response["error"]["code"] == "dem_tessellate_failed"
```

- [ ] **Step 8: Run the full suite**

Run: `python -m pytest tests/test_dem_tessellate.py -v`
Expected: PASS (with at most the documented xfail from Step 5)

- [ ] **Step 9: Commit**

```bash
git add src/ananke_equilibrium/dem.py src/ananke_equilibrium/worker.py tests/test_dem_tessellate.py
git commit -m "Tessellate solved thrust surfaces into block models"
```

---

## Task 10: The fea.model worker command

**Files:**
- Create: `src/ananke_equilibrium/fea.py`
- Modify: `src/ananke_equilibrium/worker.py`
- Test: `tests/test_fea_model.py`

**Interfaces:**
- Consumes: `cli.results.thrust_vertices`
- Produces:
  - `fea.ModelExportError(ValueError)`
  - `fea.model_payload(payload: Mapping[str, Any]) -> Dict[str, Any]` returning `{"kind": "StructuralModel", "model": <json str>, "nodes": int, "supportNodes": List[int], "analysable": False, "reason": str}`

Background verified during design: `compas_fea2` 0.2.1 constructs a `Model()` with zero registered backends. Expressing a model and analysing one are different claims, and only the first is available. Per the README's design rule, form-finding supports are **not** converted into restraint degrees of freedom; they are carried through as metadata.

- [ ] **Step 1: Write the failing test**

Create `tests/test_fea_model.py`:

```python
from __future__ import annotations

import json

import pytest

from ananke_equilibrium.fea import ModelExportError
from ananke_equilibrium.fea import model_payload


RESULT = {
    "kind": "tna_result",
    "equilibrium": {
        "vertices": [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.5],
            [2.0, 0.0, 0.0],
        ]
    },
}


def test_model_export_reports_node_count():
    out = model_payload({"result": RESULT, "supports": {"node_ids": [0, 2]}})
    assert out["kind"] == "StructuralModel"
    assert out["nodes"] == 3
    assert out["supportNodes"] == [0, 2]


def test_model_export_never_claims_it_can_be_analysed():
    out = model_payload({"result": RESULT})
    assert out["analysable"] is False
    assert "backend" in out["reason"].lower()


def test_model_is_json_serialisable():
    out = model_payload({"result": RESULT})
    assert isinstance(json.loads(out["model"]), (dict, list))


def test_a_result_without_vertices_is_rejected():
    with pytest.raises(ModelExportError, match="vertices"):
        model_payload({"result": {"kind": "solved_case", "vertices": []}})
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_fea_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ananke_equilibrium.fea'`

- [ ] **Step 3: Write the model adapter**

Create `src/ananke_equilibrium/fea.py`:

```python
"""Express a solved result as a compas_fea2 model.

This produces a model, not an analysis. compas_fea2 0.2.1 registers no solver
backends in this environment and none are published to PyPI, so nothing here
can be solved. The payload says so explicitly rather than letting a caller
infer otherwise.

Form-finding supports are carried through as node IDs and metadata. They are
deliberately not converted into restraint degrees of freedom, because a
support chosen to shape a funicular is not the same statement as a boundary
condition in a finite element model.
"""

from __future__ import annotations

from typing import Any
from typing import Dict
from typing import List
from typing import Mapping

from .cli.results import thrust_vertices


NO_BACKEND_REASON = (
    "compas_fea2 has no registered solver backend in this environment, so "
    "this model can be expressed and exported but not analysed."
)


class ModelExportError(ValueError):
    """Raised when a structural model cannot be built from a result."""


def model_payload(payload: Mapping[str, Any]) -> Dict[str, Any]:
    """Build a compas_fea2 model from a solved result."""

    result = payload.get("result")
    if not isinstance(result, Mapping):
        raise ModelExportError("fea.model requires a result object.")
    vertices = thrust_vertices(result)
    if not vertices:
        raise ModelExportError("The result carries no solved vertices.")

    supports = payload.get("supports")
    supports = dict(supports) if isinstance(supports, Mapping) else {}
    support_nodes: List[int] = [
        int(value) for value in supports.get("node_ids", ())
    ]
    for node_id in support_nodes:
        if node_id < 0 or node_id >= len(vertices):
            raise ModelExportError(
                "Support node ID {} is outside the solved vertices.".format(node_id)
            )

    try:
        from compas.data import json_dumps
        from compas_fea2.model import Model
        from compas_fea2.model import Node
        from compas_fea2.model import DeformablePart
    except ImportError as error:
        raise ModelExportError(
            "compas_fea2 is not installed. Install the fea extra: "
            'python -m pip install -e ".[fea]"'
        ) from error

    model = Model(name="ananke-equilibrium")
    part = DeformablePart(name="thrust")
    for point in vertices:
        part.add_node(Node(xyz=[float(value) for value in point]))
    model.add_part(part)

    return {
        "kind": "StructuralModel",
        "model": json_dumps(model),
        "nodes": len(vertices),
        "supportNodes": support_nodes,
        "analysable": False,
        "reason": NO_BACKEND_REASON,
    }


__all__ = [
    "NO_BACKEND_REASON",
    "ModelExportError",
    "model_payload",
]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_fea_model.py -v`
Expected: PASS, all four tests.

If `DeformablePart`, `Node`, or `Model.add_part` do not exist under this exact spelling, discover the real names before changing the test expectations:

```bash
python -c "import compas_fea2.model as m; print([n for n in dir(m) if not n.startswith('_')])"
python -c "import inspect; from compas_fea2.model import Model; print(inspect.signature(Model.__init__))"
```

Adjust only the construction lines in Step 3. The returned payload keys are consumed by Task 12's documentation and must not change.

- [ ] **Step 5: Register the worker command**

In `src/ananke_equilibrium/worker.py`, add `"fea.model"` to `ALLOWED_COMMANDS`.

In `dispatch()`, beside the `dem.tessellate` branch, add:

```python
        if command == "fea.model":
            from .fea import ModelExportError
            from .fea import model_payload

            try:
                return result_response(request_id, model_payload(payload))
            except ModelExportError as error:
                raise ProtocolError(
                    "fea_model_failed",
                    str(error),
                    {"request_id": request_id},
                )
```

- [ ] **Step 6: Test the command through dispatch**

Append to `tests/test_fea_model.py`:

```python
def test_dispatch_exposes_fea_model():
    from ananke_equilibrium.worker import ALLOWED_COMMANDS
    from ananke_equilibrium.worker import dispatch

    assert "fea.model" in ALLOWED_COMMANDS
    response = dispatch(
        {
            "v": 1,
            "type": "request",
            "id": "f1",
            "command": "fea.model",
            "payload": {"result": RESULT, "supports": {"node_ids": [0, 2]}},
        }
    )
    assert response["type"] == "result"
    assert response["result"]["analysable"] is False
```

- [ ] **Step 7: Run the full suite**

Run: `python -m pytest tests/test_fea_model.py -v`
Expected: PASS, all five tests

- [ ] **Step 8: Commit**

```bash
git add src/ananke_equilibrium/fea.py src/ananke_equilibrium/worker.py tests/test_fea_model.py
git commit -m "Express solved results as compas_fea2 models, without claiming analysis"
```

---

## Task 11: The problem-file JSON Schema and the environment guard

**Files:**
- Create: `src/ananke_equilibrium/cli/schema.py`, `.vscode/ananke-problem.schema.json`
- Modify: `src/ananke_equilibrium/cli/main.py`
- Test: `tests/test_cli_schema.py`, `tests/test_environment_pins.py`

**Interfaces:**
- Consumes: `worker.ALLOWED_COMMANDS`, `codec` decoders, `contracts`
- Produces:
  - `cli.schema.SCHEMA_PATH: Path`
  - `cli.schema.build_schema() -> Dict[str, Any]`
  - `cli.schema.write_schema(path: Optional[Path] = None) -> Path`

The schema is declared here rather than derived by parsing `codec.py`, because that file is being rewritten on another branch and must not be touched. The sync test earns the same guarantee by exercising the real decoders: every enum value the schema advertises must be accepted, and a field the schema forbids must be rejected.

- [ ] **Step 1: Write the failing test**

Create `tests/test_cli_schema.py`:

```python
from __future__ import annotations

import json

import pytest

from ananke_equilibrium.cli.schema import SCHEMA_PATH
from ananke_equilibrium.cli.schema import build_schema
from ananke_equilibrium.cli.schema import write_schema
from ananke_equilibrium.codec import CodecError
from ananke_equilibrium.codec import decode_load_case
from ananke_equilibrium.codec import decode_supports
from ananke_equilibrium.codec import decode_topology
from ananke_equilibrium.contracts import ContractError
from ananke_equilibrium.worker import ALLOWED_COMMANDS


TOPOLOGY = {
    "kind": "line",
    "vertices": [[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [2.0, 0.0, 0.0]],
    "edges": [[0, 1], [1, 2]],
}


def payload_schema(name):
    return build_schema()["properties"]["payload"]["properties"][name]


def test_every_advertised_command_is_a_real_worker_command():
    for command in build_schema()["properties"]["command"]["enum"]:
        assert command in ALLOWED_COMMANDS


def test_every_advertised_support_mode_is_accepted():
    topology = decode_topology(TOPOLOGY)
    for mode in payload_schema("supports")["properties"]["mode"]["enum"]:
        decode_supports({"mode": mode, "node_ids": [0]}, topology)


def test_every_advertised_load_distribution_is_accepted():
    topology = decode_topology(TOPOLOGY)
    for distribution in payload_schema("load_case")["properties"]["distribution"]["enum"]:
        decode_load_case(
            {
                "name": "gravity",
                "distribution": distribution,
                "node_ids": [1],
                "vectors": [[0.0, 0.0, -1.0]],
            },
            topology,
        )


def test_an_undeclared_topology_field_is_rejected_by_the_decoder():
    declared = set(payload_schema("topology")["properties"])
    assert "nonsense" not in declared
    with pytest.raises((CodecError, ContractError)):
        decode_topology(dict(TOPOLOGY, nonsense=1))


def test_declared_topology_fields_are_all_accepted():
    for name in payload_schema("topology")["properties"]:
        assert name in (
            "schema_version",
            "kind",
            "vertices",
            "edges",
            "faces",
            "source_vertex_ids",
            "length_unit",
            "metadata",
            "topology_hash",
        )


def test_write_schema_produces_valid_json(tmp_path):
    path = write_schema(tmp_path / "schema.json")
    assert json.loads(path.read_text(encoding="utf-8"))["$schema"]


def test_the_committed_schema_is_current():
    committed = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    assert committed == build_schema(), (
        "The committed schema is stale. Regenerate it: ananke schema"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_cli_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ananke_equilibrium.cli.schema'`

- [ ] **Step 3: Write the schema module**

Create `src/ananke_equilibrium/cli/schema.py`:

```python
"""JSON Schema for study files, so hand-editing gets completion in VS Code.

The enums here are asserted against the real decoders by
tests/test_cli_schema.py rather than derived by parsing codec.py, which is
under active rewrite on another branch.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from typing import Dict
from typing import Optional

from ..contracts import SCHEMA_VERSION


SCHEMA_PATH = (
    Path(__file__).resolve().parents[3] / ".vscode" / "ananke-problem.schema.json"
)

SUPPORT_MODES = ("explicit", "terminals", "boundary", "corners")
LOAD_DISTRIBUTIONS = (
    "point",
    "uniform_nodes",
    "tributary_area",
    "self_weight",
    "custom",
)
LENGTH_UNITS = ("mm", "cm", "m", "in", "ft")
SOLVE_COMMANDS = ("fd.solve", "tna.prepare", "tna.solve", "dem.tessellate", "fea.model")

_POINT = {
    "type": "array",
    "minItems": 2,
    "maxItems": 3,
    "items": {"type": "number"},
}
_REF = {
    "type": "object",
    "properties": {"$ref": {"type": "string"}},
    "required": ["$ref"],
    "additionalProperties": False,
    "description": "Load this value from a sibling JSON file.",
}


def _one_of(schema: Dict[str, Any]) -> Dict[str, Any]:
    return {"oneOf": [schema, _REF]}


def build_schema() -> Dict[str, Any]:
    """Build the study-file schema."""

    topology = {
        "type": "object",
        "description": "Registered whole-object topology. Usually machine-written.",
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "kind": {
                "enum": ["line", "faced"],
                "description": "line for force density, faced for TNA.",
            },
            "vertices": {"type": "array", "items": _POINT},
            "edges": {
                "type": "array",
                "items": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 2,
                    "items": {"type": "integer", "minimum": 0},
                },
            },
            "faces": {
                "type": "array",
                "items": {
                    "type": "array",
                    "minItems": 3,
                    "items": {"type": "integer", "minimum": 0},
                },
            },
            "source_vertex_ids": {"type": "array"},
            "length_unit": {"enum": list(LENGTH_UNITS)},
            "metadata": {"type": "object"},
            "topology_hash": {"type": "string"},
        },
        "required": ["kind", "vertices", "edges"],
        "additionalProperties": False,
    }
    supports = {
        "type": "object",
        "description": "Form-finding supports. Not FEA restraint degrees of freedom.",
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "topology_hash": {"type": "string"},
            "mode": {"enum": list(SUPPORT_MODES)},
            "points": {"type": "array", "items": _POINT},
            "node_ids": {"type": "array", "items": {"type": "integer", "minimum": 0}},
            "snap_tolerance": {"type": "number", "exclusiveMinimum": 0},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }
    load_case = {
        "type": "object",
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "topology_hash": {"type": "string"},
            "name": {"type": "string", "minLength": 1},
            "distribution": {"enum": list(LOAD_DISTRIBUTIONS)},
            "points": {"type": "array", "items": _POINT},
            "node_ids": {"type": "array", "items": {"type": "integer", "minimum": 0}},
            "vectors": {"type": "array", "items": _POINT},
            "records": {"type": "array", "items": {"type": "object"}},
            "base_vector": _POINT,
            "factor": {"type": "number"},
            "coordinate_system": {"type": "string"},
            "metadata": {"type": "object"},
        },
        "additionalProperties": False,
    }
    settings = {
        "type": "object",
        "description": "Solver controls. Fields depend on the chosen command.",
        "properties": {
            "schema_version": {"const": SCHEMA_VERSION},
            "force_densities": {
                "oneOf": [
                    {"type": "number"},
                    {"type": "array", "items": {"type": "number"}},
                ],
                "description": "fd.solve. Force unit divided by length unit.",
            },
            "sign_convention": {"const": "positive_tension"},
            "pattern": {
                "type": "string",
                "description": "dem.tessellate pattern name, for example Hex.",
            },
            "tmin": {"type": "number", "exclusiveMinimum": 0},
            "tmax": {"type": "number", "exclusiveMinimum": 0},
            "metadata": {"type": "object"},
        },
    }
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "title": "Ananke Equilibrium study",
        "description": (
            "One vault study. The payload block is byte-identical to what the "
            "Grasshopper components send the worker."
        ),
        "type": "object",
        "properties": {
            "$schema": {"type": "string"},
            "study": {
                "type": "string",
                "minLength": 1,
                "description": "Study name. Becomes the request id.",
            },
            "command": {"enum": list(SOLVE_COMMANDS)},
            "payload": {
                "type": "object",
                "properties": {
                    "topology": _one_of(topology),
                    "supports": _one_of(supports),
                    "load_case": _one_of(load_case),
                    "settings": _one_of(settings),
                    "result": {"type": "object"},
                    "control": {"type": "object"},
                },
            },
        },
        "required": ["study", "command", "payload"],
        "additionalProperties": False,
    }


def write_schema(path: Optional[Path] = None) -> Path:
    """Write the schema to disk and return the path written."""

    target = Path(path) if path is not None else SCHEMA_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    document = json.dumps(build_schema(), indent=2, sort_keys=True)
    target.write_text(document + "\n", encoding="utf-8")
    return target


__all__ = [
    "LENGTH_UNITS",
    "LOAD_DISTRIBUTIONS",
    "SCHEMA_PATH",
    "SOLVE_COMMANDS",
    "SUPPORT_MODES",
    "build_schema",
    "write_schema",
]
```

- [ ] **Step 4: Add the schema subcommand and generate the file**

In `src/ananke_equilibrium/cli/main.py`, add to the imports:

```python
from .schema import write_schema
```

In `build_parser()`, before `return parser`, add:

```python
    schema = subparsers.add_parser(
        "schema",
        help="Regenerate the study-file JSON Schema.",
    )
    schema.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Schema path. Defaults to .vscode/ananke-problem.schema.json.",
    )
```

In `main()`, add before the `health` branch:

```python
    if args.command == "schema":
        print("schema -> {}".format(write_schema(args.out)))
        return 0
```

Then run: `ananke schema`
Expected: writes `.vscode/ananke-problem.schema.json`

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/test_cli_schema.py -v`
Expected: PASS, all seven tests

- [ ] **Step 6: Add the environment guard**

Create `tests/test_environment_pins.py`:

```python
"""The development environment exists to represent what Rhino 8 runs.

Optional extras may add packages Rhino does not have, but they must never move
the three pins that make this environment representative.
"""

from __future__ import annotations

import importlib.metadata as metadata

import pytest


PINS = {
    "numpy": "2.0.2",
    "scipy": "1.13.1",
    "compas": "2.15.1",
}


@pytest.mark.parametrize("package,expected", sorted(PINS.items()))
def test_pin_has_not_moved(package, expected):
    assert metadata.version(package) == expected, (
        "{} moved to {}. The environment no longer represents the Rhino 8 "
        "catenary-compas-2026 environment. Move the pin deliberately in "
        "pyproject.toml and retest the solver matrix.".format(
            package,
            metadata.version(package),
        )
    )
```

- [ ] **Step 7: Run the guard**

Run: `python -m pytest tests/test_environment_pins.py -v`
Expected: PASS, three tests

- [ ] **Step 8: Commit**

```bash
git add src/ananke_equilibrium/cli/schema.py src/ananke_equilibrium/cli/main.py .vscode/ananke-problem.schema.json tests/test_cli_schema.py tests/test_environment_pins.py
git commit -m "Generate the study-file schema and guard the environment pins"
```

---

## Task 12: VS Code wiring and documentation

**Files:**
- Create: `.vscode/settings.json`, `.vscode/tasks.json`, `.vscode/launch.json`, `.vscode/extensions.json`, `docs/vscode-design-bench.md`
- Modify: `README.md`
- Test: `tests/test_vscode_config.py`

**Interfaces:**
- Consumes: every command from tasks 1 to 11
- Produces: no Python interfaces

- [ ] **Step 1: Write the failing test**

Create `tests/test_vscode_config.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ananke_equilibrium.cli.main import build_parser


ROOT = Path(__file__).resolve().parents[1]
VSCODE = ROOT / ".vscode"


def read(name):
    return json.loads((VSCODE / name).read_text(encoding="utf-8"))


@pytest.mark.parametrize(
    "name",
    ["settings.json", "tasks.json", "launch.json", "extensions.json"],
)
def test_config_file_is_valid_json(name):
    assert isinstance(read(name), dict)


def test_settings_map_problem_files_to_the_schema():
    schemas = read("settings.json")["json.schemas"]
    entry = next(
        item for item in schemas if "ananke-problem.schema.json" in item["url"]
    )
    assert any("problem.json" in pattern for pattern in entry["fileMatch"])


def test_every_task_invokes_a_real_cli_command():
    parser = build_parser()
    known = set(parser._subparsers._group_actions[0].choices)
    for task in read("tasks.json")["tasks"]:
        if task.get("command") != "ananke":
            continue
        assert task["args"][0] in known, task["label"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_vscode_config.py -v`
Expected: FAIL with `FileNotFoundError` for `.vscode/settings.json`

- [ ] **Step 3: Write settings.json**

Create `.vscode/settings.json`:

```json
{
  "python.defaultInterpreterPath": "${workspaceFolder}/.venv/Scripts/python.exe",
  "python.testing.pytestEnabled": true,
  "python.testing.unittestEnabled": false,
  "python.testing.pytestArgs": ["tests"],
  "json.schemas": [
    {
      "fileMatch": ["**/studies/**/problem.json", "**/*.problem.json"],
      "url": "./.vscode/ananke-problem.schema.json"
    }
  ],
  "files.associations": {
    "*.problem.json": "json"
  }
}
```

- [ ] **Step 4: Write tasks.json**

Create `.vscode/tasks.json`:

```json
{
  "version": "2.0.0",
  "tasks": [
    {
      "label": "Ananke: check current study",
      "type": "process",
      "command": "ananke",
      "args": ["check", "${file}"],
      "problemMatcher": [],
      "presentation": { "reveal": "always", "panel": "shared" }
    },
    {
      "label": "Ananke: solve current study",
      "type": "process",
      "command": "ananke",
      "args": ["solve", "${file}"],
      "problemMatcher": [],
      "group": { "kind": "build", "isDefault": true },
      "presentation": { "reveal": "always", "panel": "shared" }
    },
    {
      "label": "Ananke: plot current result",
      "type": "process",
      "command": "ananke",
      "args": ["plot", "${file}"],
      "problemMatcher": [],
      "presentation": { "reveal": "always", "panel": "shared" }
    },
    {
      "label": "Ananke: view current result",
      "type": "process",
      "command": "ananke",
      "args": ["view", "${file}"],
      "problemMatcher": [],
      "presentation": { "reveal": "always", "panel": "shared" }
    },
    {
      "label": "Ananke: health",
      "type": "process",
      "command": "ananke",
      "args": ["health"],
      "problemMatcher": [],
      "presentation": { "reveal": "always", "panel": "shared" }
    },
    {
      "label": "Ananke: regenerate schema",
      "type": "process",
      "command": "ananke",
      "args": ["schema"],
      "problemMatcher": [],
      "presentation": { "reveal": "silent", "panel": "shared" }
    },
    {
      "label": "Ananke: run tests",
      "type": "process",
      "command": "${command:python.interpreterPath}",
      "args": ["-m", "pytest", "-ra"],
      "problemMatcher": [],
      "group": { "kind": "test", "isDefault": true },
      "presentation": { "reveal": "always", "panel": "shared" }
    }
  ]
}
```

- [ ] **Step 5: Write launch.json**

Create `.vscode/launch.json`:

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Ananke: solve current study",
      "type": "debugpy",
      "request": "launch",
      "module": "ananke_equilibrium.cli",
      "args": ["solve", "${file}"],
      "console": "integratedTerminal",
      "justMyCode": false
    },
    {
      "name": "Ananke: check current study",
      "type": "debugpy",
      "request": "launch",
      "module": "ananke_equilibrium.cli",
      "args": ["check", "${file}"],
      "console": "integratedTerminal",
      "justMyCode": false
    },
    {
      "name": "Ananke: worker on stdin",
      "type": "debugpy",
      "request": "launch",
      "module": "ananke_equilibrium.worker",
      "console": "integratedTerminal",
      "justMyCode": false
    }
  ]
}
```

`justMyCode` is false deliberately: the point of solving in-process is that a breakpoint inside `solve_tna` or inside COMPAS itself is reachable.

- [ ] **Step 6: Write extensions.json**

Create `.vscode/extensions.json`:

```json
{
  "recommendations": [
    "ms-python.python",
    "ms-python.debugpy",
    "charliermarsh.ruff"
  ]
}
```

- [ ] **Step 7: Run test to verify it passes**

Run: `python -m pytest tests/test_vscode_config.py -v`
Expected: PASS, all six tests

- [ ] **Step 8: Write the workflow document**

Create `docs/vscode-design-bench.md` covering, in prose and with runnable commands:

1. Installing the bench: `python -m pip install -e ".[equilibrium,masonry,fea,dev]"`, and `".[viz]"` for the 3D viewer.
2. The study directory layout, with `studies/example-arch/` as the worked example.
3. Each CLI command with one real invocation and its expected output.
4. Getting a problem out of Grasshopper: set `ANANKE_CAPTURE_DIR`, restart Rhino, solve on the canvas, find the study file. State that capture is inert unless the variable is set.
5. What the capability flags mean, specifically that `masonry.stability` and `fea` are false and why, linking to the design spec.
6. The `$ref` convention for keeping bulky topology out of the hand-edited file.

No em dashes.

- [ ] **Step 9: Link it from the README**

In `README.md`, in the "Further project documentation" list, add:

```markdown
- [The VS Code design bench: JSON studies, the ananke CLI, viewing, and capture](docs/vscode-design-bench.md)
```

- [ ] **Step 10: Run the whole suite**

Run: `python -m pytest -ra`
Expected: PASS. Any pre-existing failure unrelated to this branch should be reported, not fixed silently.

- [ ] **Step 11: Commit**

```bash
git add .vscode docs/vscode-design-bench.md README.md tests/test_vscode_config.py
git commit -m "Wire the bench into VS Code and document the workflow"
```

---

## Self-Review

**Spec coverage:**

| Spec section | Task |
| --- | --- |
| 1. Study directory and problem file | 2 |
| 2. The CLI | 1, 2, 3, 5, 6, 11 |
| 3. Viewing (plot and view, viz extra) | 5, 6 |
| Graphic statics as plotted reciprocals, no `ags.solve` | 5, and `SOLVE_COMMANDS` in 11 omits it |
| 4. Capture | 7 |
| 5. DEM tessellation and health honesty | 9, 8 |
| 6. FEA model export, no inferred restraints | 10 |
| 7. VS Code layer | 11, 12 |
| Testing: round trip, parity, schema sync, env guard, capture, tessellation, health honesty | 3, 3, 11, 11, 7, 9, 8 |
| Out of scope: CRA, FEA analysis, importers, generators, tree_forest, sweeps | Nothing implements them |

All spec sections have a task. The parity test in Task 3 Step 1 covers the spec's parity requirement, and the environment guard in Task 11 Step 6 covers the pin requirement the `viz` extra could threaten.

**Placeholder scan:** No TBD, TODO, "handle edge cases", or "similar to Task N". Two tasks contain conditional investigation steps (9 Step 5 for contact tolerances, 10 Step 4 for `compas_fea2` class names), each with the exact discovery command to run and an explicit rule for what to do with the answer. These are honest unknowns named in the spec's risk section, not deferred work.

**Type consistency:** `thrust_vertices`, `thrust_faces`, `diagram`, `load_result` and `ResultError` are defined in Task 4 and used under those names in Tasks 5, 6, 9 and 10. `load_study` and `build_request` are defined in Task 2 and used in Tasks 3 and 7. `StudyError` is raised in Task 2 and caught in Tasks 2 and 3. `capture_request`/`capture_directory` are defined in Task 7 and called in `serve()` in the same task. `PATTERN_NAMES` and `TessellationError` are defined in Task 9 and used in its own dispatch branch. `ModelExportError` likewise in Task 10. `build_parser` is defined in Task 1 and imported by Task 12's test. `SCHEMA_PATH`/`build_schema`/`write_schema` are defined in Task 11 and used in its own test and CLI branch.

One note for the implementer: `SCHEMA_PATH` in Task 11 uses `parents[3]` to climb from `src/ananke_equilibrium/cli/schema.py` to the repository root. Verify that with `python -c "from ananke_equilibrium.cli.schema import SCHEMA_PATH; print(SCHEMA_PATH)"` before relying on it; if the package is installed non-editable the path will differ, and the `--out` argument exists for that case.
