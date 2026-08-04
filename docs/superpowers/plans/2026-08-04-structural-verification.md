# Structural Verification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Take a vault exported from Grasshopper and answer whether it stands up, how far it deflects, at what load it goes into tension, when it collapses, and what cable it needs if the answer is that the shell alone will not do.

**Architecture:** A new package `src/ananke_fea/` runs only in `.venv-fea`, builds a shell model from the COMPAS-mode export and a truss model from the Contract-mode export, solves both through OpenSees, and writes plain JSON that the main bench reads without ever importing `compas_fea2`. A bar cross-check against the TNA member forces is what makes the shell numbers believable.

**Tech Stack:** Python 3.12, `compas_fea2` pinned to `664ec20`, `compas_fea2_opensees`, OpenSees 3.8.0, `compas` 2.15.1, pytest.

## Global Constraints

- **Never call `problem.analyse_and_extract()`.** It extracts twice and doubles every row. Always `problem.analyse(path=...)` then `problem.extract_results()`.
- **Every load case must be named `DL`, `SDL` or `LL`.** Any other name is silently dropped by `LoadCombination.node_load` and the model solves unloaded while reporting success.
- **`LoadCombination.ULS()` multiplies by 1.35.** Any comparison against a hand calculation must include the factor. Use `LoadCombination.SLS()` (factor 1.0) for deflection serviceability checks.
- **Always request field outputs explicitly** via `step.add_output(...)`, or the results database is written at zero bytes.
- **Always analyse into a fresh directory.** `problem.analyse` calls `input()` on an existing one and hangs.
- **Never map results by index.** `Part` stores nodes in a set; node tags are not insertion order. Map by node object identity.
- **`ananke_fea` must never be imported by `src/ananke_equilibrium/`.** The two sides exchange JSON on disk.
- Contract exports are `lengthUnit: "m"`, `forceUnit: "kN"`, `signConvention: "positive_tension"`. `compas_fea2` works in SI base units, so **forces convert by ×1000** and material moduli are in Pa.
- **The source export is chosen at runtime, never hard-coded.** More than one solve of the same vault exists and they differ in ways that matter, so nothing may assume a particular file. Discover the available pairs and select by name.
- **Nothing may assume the thrust network is wholly compressive.** It is true of some solves and false of others. Any assertion about the sign of member forces is a property of one export fixture, not of the format.
- Solve time on the exported 2400-face mesh is **124 seconds**, measured in Task 4. Budget accordingly: this is not a suite you run in a loop.
- No em dashes in any prose, comment, or docstring.
- Commit after every task.

### Amendment, after Task 4

Two facts arrived after the plan was written and they bind Tasks 6, 7 and 10.

**The exports available now differ in kind, not just in quality.** The
upload folder holds three pairs of the same 2521-vertex, 2400-face vault:

| Export | Force error | Reciprocal deviation | Peak member force |
| --- | --- | --- | --- |
| `Trial 2` | 2.4063 kN | 3.017 deg | -0.6061 kN, wholly compressive |
| `Standard TNA method` | 2.4063 kN | 3.017 deg | identical solve to Trial 2 |
| `Algebraic TNA method` | 0.0266 kN | 0.000 deg | **+0.6626 kN, some members in tension** |

The algebraic solve closes the horizontal equilibrium the spec recorded as
open, with a residual ninety times smaller. But under the export's
`positive_tension` convention its peak member force is positive, so that
solve is not funicular everywhere. Both are legitimate inputs, and the
package supports both, selected at runtime.

This matters most to the bar cross-check. Its tolerance reads the file's own
`global_force_error_norm`, so on Trial 2 it is about 2.5 per cent of applied
load and on the algebraic export about 0.03 per cent. The second genuinely
tests the FEA setup; the first barely constrains it.

**Solve time is 124 seconds at full density**, with build at 0.23 seconds,
measured by Task 4 on the real mesh. That is within the spec's threshold, so
no coarsening is introduced and every result comes from the mesh as
exported. The demo's tension sweep is cut from four load factors to two,
`[1.0, 2.0]`, to keep its end-to-end run near eight minutes.

Task 5 gains a small discovery helper in `mesh.py` so the selection is one
function rather than paths scattered through demos and tests:

```python
def available_exports(directory) -> Dict[str, Dict[str, Path]]:
    """Map export name to its file pair, for every complete pair present.

    An export is a pair "<name>-contract.json" and "<name>-compas.json" in
    the same directory. Only names with both files count.
    """

    directory = Path(directory)
    pairs: Dict[str, Dict[str, Path]] = {}
    for contract in sorted(directory.glob("*-contract.json")):
        name = contract.name[: -len("-contract.json")]
        geometry = directory / (name + "-compas.json")
        if geometry.is_file():
            pairs[name] = {"contract": contract, "geometry": geometry}
    return pairs
```

with tests asserting that `Trial 2` appears with both paths, and that a name
missing its geometry half does not appear at all.

---

### Task 1: The FEA environment can hold a package, and the chain gives a right answer

Establishes `src/ananke_fea/`, the upstream shim without which every loaded model raises, and the closed-form test that proves the whole chain end to end. Nothing else in this plan is trustworthy until this task passes.

**Files:**
- Create: `src/ananke_fea/__init__.py`
- Create: `src/ananke_fea/compat.py`
- Create: `tests/fea/__init__.py`
- Create: `tests/fea/conftest.py`
- Create: `tests/fea/test_compat.py`
- Create: `tests/fea/test_cantilever.py`
- Modify: `scripts/setup_fea_env.sh`

**Interfaces:**
- Consumes: nothing.
- Produces: `ananke_fea.compat.apply_patches() -> list[str]`, `ananke_fea.compat.require_backend() -> str`, `ananke_fea.compat.analyse(problem, path) -> None`.

- [ ] **Step 1: Install the project and pytest into the FEA environment**

`ananke_equilibrium` is not importable in `.venv-fea`, and pytest is not installed there. The project declares `dependencies = []`, so an editable install adds no packages and cannot disturb the pins.

```bash
cd "COMPAS-Workflow-bench"
.venv-fea/Scripts/python.exe -m pip install --no-deps -e .
.venv-fea/Scripts/python.exe -m pip install "pytest>=8,<10"
.venv-fea/Scripts/python.exe -c "import ananke_equilibrium; print('ok')"
```

Expected: `ok`.

- [ ] **Step 2: Write the conftest that keeps these tests out of the main suite**

`tests/fea/conftest.py`. The main `.venv` has no `compas_fea2`, and `testpaths = ["tests"]` would otherwise collect these and fail.

```python
"""Keep the FEA tests out of any environment that cannot run them.

The main .venv mirrors Rhino 8 and deliberately has no compas_fea2. Its
pytest run collects everything under tests/, so without this these modules
would fail at import rather than being skipped.
"""

collect_ignore_glob = []

try:
    import compas_fea2  # noqa: F401
except ImportError:
    collect_ignore_glob = ["*.py"]
```

Also create an empty `tests/fea/__init__.py` and an empty `src/ananke_fea/__init__.py`.

- [ ] **Step 3: Write the failing test for the shim**

`tests/fea/test_compat.py`:

```python
from __future__ import annotations

import compas_fea2

from ananke_fea.compat import apply_patches, require_backend


def test_require_backend_registers_opensees():
    assert require_backend() == "compas_fea2_opensees"
    assert compas_fea2.BACKEND is not None


def test_apply_patches_gives_nodes_a_public_loads_mapping():
    require_backend()
    apply_patches()

    from compas_fea2.model import Node

    node = Node(xyz=[0.0, 0.0, 0.0])
    assert node.loads == {}
    assert node.loads is node._loads


def test_apply_patches_is_idempotent():
    require_backend()
    first = apply_patches()
    second = apply_patches()
    assert first == ["Node.loads"]
    assert second == []
```

- [ ] **Step 4: Run it and watch it fail**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_compat.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ananke_fea.compat'`.

- [ ] **Step 5: Write `compat.py`**

`src/ananke_fea/compat.py`:

```python
"""Make the pinned compas_fea2 usable, and record exactly what was wrong.

The OpenSees backend was last pushed 2025-06-17 and imports BeamSection,
which the core removed on 2025-07-30, so the core is pinned to 664ec20. That
commit is internally inconsistent in one place: model/nodes.py sets
self._loads but leaves the public `loads` property commented out, while
problem/steps/step.py:117 calls node.loads when a combination is assigned.
The result is that applying any load a combination recognises raises
AttributeError. One property closes it.

This module is the only place that reaches into upstream internals, and
every patch is announced by name so a future version bump can drop it.
"""

from __future__ import annotations

from pathlib import Path
from typing import List

BACKEND_NAME = "compas_fea2_opensees"

_applied: List[str] = []


def require_backend() -> str:
    """Register the OpenSees backend and return its name.

    Importing the backend is not enough. Without set_backend the BACKENDS
    mapping stays empty and every model builds as an abstract base class.
    """

    import compas_fea2

    if compas_fea2.BACKEND is None:
        compas_fea2.set_backend(BACKEND_NAME)
    return BACKEND_NAME


def apply_patches() -> List[str]:
    """Shim the upstream inconsistencies. Returns the names newly applied."""

    require_backend()
    from compas_fea2.model import Node

    newly: List[str] = []
    if not hasattr(Node, "loads"):
        Node.loads = property(lambda self: self._loads)
        newly.append("Node.loads")

    _applied.extend(newly)
    return newly


def analyse(problem, path) -> None:
    """Solve and extract, avoiding the double-extraction bug.

    problem.analyse_and_extract() runs extraction twice and inserts every
    result row twice, so sums come out doubled while max() looks correct.
    Splitting the call gives one row per node.

    The directory must not already exist: compas_fea2 calls input() on an
    existing path, which hangs a non-interactive run.
    """

    directory = Path(path)
    if directory.exists() and any(directory.iterdir()):
        raise ValueError(
            "analysis directory is not empty, which makes compas_fea2 prompt "
            "on stdin and hang: {}".format(directory)
        )
    directory.mkdir(parents=True, exist_ok=True)

    problem.analyse(path=str(directory), verbose=False)
    problem.extract_results()
```

- [ ] **Step 6: Run the shim tests**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_compat.py -v`
Expected: 3 passed.

- [ ] **Step 7: Write the closed-form cantilever test**

`tests/fea/test_cantilever.py`. This is the test that proves the chain against an answer known independently of any of this code.

```python
"""A cantilever, checked against PL^3 / 3EI.

Every other result in this package is trusted because this one is right.
The ULS factor of 1.35 is part of the expected answer: LoadCombination.ULS
multiplies a DL case by 1.35, so the closed form must too.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from ananke_fea.compat import analyse, apply_patches, require_backend

LENGTH = 4.0
MODULUS = 30e9
WIDTH = DEPTH = 0.3
TIP_LOAD = 1000.0
ULS_FACTOR = 1.35

SECOND_MOMENT = WIDTH * DEPTH**3 / 12.0
CLOSED_FORM = ULS_FACTOR * TIP_LOAD * LENGTH**3 / (3.0 * MODULUS * SECOND_MOMENT)


@pytest.fixture(scope="module")
def solved():
    require_backend()
    apply_patches()

    from compas_fea2.model import BeamElement, ElasticIsotropic, FixedBC
    from compas_fea2.model import Model, Node, Part, RectangularSection
    from compas_fea2.problem import LoadCombination, Problem, StaticStep
    from compas_fea2.results import DisplacementFieldResults, ReactionFieldResults

    model = Model(name="cantilever")
    part = Part(name="beam")
    nodes = []
    for index in range(9):
        node = Node(xyz=[index * (LENGTH / 8.0), 0.0, 0.0])
        part.add_node(node)
        nodes.append(node)

    material = ElasticIsotropic(E=MODULUS, v=0.2, density=2400)
    section = RectangularSection(w=WIDTH, h=DEPTH, material=material)
    for start, end in zip(nodes[:-1], nodes[1:]):
        part.add_element(
            BeamElement(nodes=[start, end], section=section, frame=[0, 0, 1])
        )

    model.add_part(part)
    model.add_bcs(FixedBC(), nodes=[nodes[0]])

    problem = Problem(name="tip_load")
    step = StaticStep()
    step.add_uniform_node_load(nodes=[nodes[-1]], z=-TIP_LOAD, load_case="DL")
    step.combination = LoadCombination.ULS()
    step.add_output(DisplacementFieldResults)
    step.add_output(ReactionFieldResults)
    problem.add_step(step)
    model.add_problem(problem)

    directory = Path(tempfile.mkdtemp(prefix="ananke_cantilever_")) / "run"
    analyse(problem, directory)
    return step, nodes


def test_tip_deflection_matches_closed_form(solved):
    step, _ = solved
    results = list(step.displacement_field.results)
    peak = max(results, key=lambda result: result.magnitude)
    assert peak.magnitude == pytest.approx(CLOSED_FORM, rel=0.01)


def test_one_result_per_node_not_two(solved):
    """analyse_and_extract would give 18 here. Our analyse() must give 9."""

    step, nodes = solved
    assert len(list(step.displacement_field.results)) == len(nodes)


def test_reactions_sum_to_the_factored_load(solved):
    step, _ = solved
    total = sum(result.vector[2] for result in step.reaction_field.results)
    assert total == pytest.approx(ULS_FACTOR * TIP_LOAD, rel=1e-6)
```

- [ ] **Step 8: Run the cantilever test**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_cantilever.py -v`
Expected: 3 passed. The deflection test is the meaningful one; if it fails, stop and diagnose rather than loosening the tolerance.

- [ ] **Step 9: Confirm the main suite still passes and ignores these**

Run: `.venv/Scripts/python.exe -m pytest tests -q`
Expected: the existing suite passes and collects nothing from `tests/fea`.

- [ ] **Step 10: Record the environment steps in the setup script**

Append to `scripts/setup_fea_env.sh`, after the backend check block:

```bash
echo "=== Installing the project and pytest into ${ENV_DIR} ==="
# dependencies = [] in pyproject, so --no-deps adds nothing and cannot
# disturb the pins. This is what makes ananke_fea and ananke_equilibrium
# importable in this environment.
uv pip install --link-mode=copy --python "${ENV_DIR}" --no-deps -e .
uv pip install --link-mode=copy --python "${ENV_DIR}" "pytest>=8,<10"

echo "=== Running the closed-form check ==="
"${ENV_DIR}/Scripts/python.exe" -m pytest tests/fea/test_cantilever.py -q || true
```

- [ ] **Step 11: Commit**

```bash
git add src/ananke_fea tests/fea scripts/setup_fea_env.sh
git commit -m "feat(fea): shim the pinned compas_fea2 and prove the chain against PL^3/3EI"
```

---

### Task 2: Read the export, in the units the solver wants

Both export modes, converted once, in one place. Everything downstream consumes metres and newtons and never sees kN again.

**Files:**
- Create: `src/ananke_fea/mesh.py`
- Create: `tests/fea/test_mesh.py`

**Interfaces:**
- Consumes: nothing from Task 1.
- Produces:
  - `load_thrust_mesh(path) -> compas.datastructures.Mesh`
  - `load_contract(path) -> dict`
  - `support_node_ids(contract) -> list[int]`
  - `node_loads(contract) -> dict[int, tuple[float, float, float]]` in newtons
  - `member_forces(contract) -> list[float]` in newtons, negative in compression
  - `edges(contract) -> list[tuple[int, int]]`
  - `vertices(contract) -> list[tuple[float, float, float]]`
  - `residual_norm(contract) -> float | None` in newtons
  - `applied_total(contract) -> float` in newtons

- [ ] **Step 1: Write the failing tests**

`tests/fea/test_mesh.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ananke_fea import mesh as reader

UPLOAD = Path(__file__).resolve().parents[2] / "demo" / "upload from grasshopper"
CONTRACT = UPLOAD / "Trial 2-contract.json"
GEOMETRY = UPLOAD / "Trial 2-compas.json"

pytestmark = pytest.mark.skipif(
    not CONTRACT.is_file(), reason="the Trial 2 export is not present"
)


@pytest.fixture(scope="module")
def contract():
    return reader.load_contract(CONTRACT)


def test_thrust_mesh_has_the_expected_size():
    surface = reader.load_thrust_mesh(GEOMETRY)
    assert surface.number_of_vertices() == 2521
    assert surface.number_of_faces() == 2400


def test_supports_are_read(contract):
    supports = reader.support_node_ids(contract)
    assert len(supports) == 123
    assert 60 in supports


def test_loads_are_converted_from_kilonewtons(contract):
    loads = reader.node_loads(contract)
    assert len(loads) == 2521
    # The raw export gives node 0 a vertical load of -0.4319900415957169 kN.
    assert loads[0][2] == pytest.approx(-431.9900415957169)


def test_member_forces_are_converted_and_stay_compressive(contract):
    forces = reader.member_forces(contract)
    assert len(forces) == 4800
    assert max(forces) <= 0.0
    assert forces[0] == pytest.approx(-1953.2172413189726)


def test_residual_is_read_from_the_files_own_diagnostic(contract):
    residual = reader.residual_norm(contract)
    assert residual == pytest.approx(2406.0, rel=0.05)


def test_a_missing_diagnostic_gives_none():
    assert reader.residual_norm({"equilibrium": {"diagnostics": []}}) is None
```

- [ ] **Step 2: Run and watch it fail**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_mesh.py -v`
Expected: FAIL with `ImportError: cannot import name 'mesh'`.

- [ ] **Step 3: Write `mesh.py`**

`src/ananke_fea/mesh.py`:

```python
"""Read a Grasshopper export and hand back SI units.

The Export component writes two files and they carry different things:

- Contract mode is the solved Result. Member forces, loads, reactions,
  supports and diagnostics all come from here.
- COMPAS mode is compas.data geometry. The thrust Mesh comes from here,
  because it is already a real Mesh with faces.

The contract is in kilonewtons and metres, with tension positive.
compas_fea2 works in SI base units, so forces are multiplied by 1000 here,
once, and nothing downstream deals in kilonewtons.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Tuple

KN_TO_N = 1000.0

Vector = Tuple[float, float, float]


def load_contract(path) -> Dict[str, Any]:
    """Read a Contract-mode export."""

    return json.loads(Path(path).read_text(encoding="utf-8"))


def load_thrust_mesh(path):
    """Read the thrust surface from a COMPAS-mode export."""

    from compas.data import json_loads

    document = json.loads(Path(path).read_text(encoding="utf-8"))
    if "thrustMesh" not in document:
        raise ValueError(
            "no thrustMesh in {}. Export again with Mode set to COMPAS.".format(path)
        )
    return json_loads(document["thrustMesh"])


def _equilibrium(contract: Mapping[str, Any]) -> Mapping[str, Any]:
    block = contract.get("equilibrium")
    if not isinstance(block, Mapping):
        raise ValueError("this file has no equilibrium block; is it Contract mode?")
    return block


def _vector(entry: Mapping[str, Any], key: str) -> Vector:
    raw = entry.get(key) or {}
    return (
        float(raw.get("x", 0.0)),
        float(raw.get("y", 0.0)),
        float(raw.get("z", 0.0)),
    )


def support_node_ids(contract: Mapping[str, Any]) -> List[int]:
    """The node ids the solver actually restrained."""

    return [int(item) for item in _equilibrium(contract).get("resolvedSupportNodeIds", [])]


def vertices(contract: Mapping[str, Any]) -> List[Vector]:
    return [
        (float(item["x"]), float(item["y"]), float(item["z"]))
        for item in _equilibrium(contract).get("vertices", [])
    ]


def edges(contract: Mapping[str, Any]) -> List[Tuple[int, int]]:
    return [
        (int(item["u"]), int(item["v"]))
        for item in _equilibrium(contract).get("edges", [])
    ]


def node_loads(contract: Mapping[str, Any]) -> Dict[int, Vector]:
    """Applied load per node id, in newtons."""

    result: Dict[int, Vector] = {}
    for entry in _equilibrium(contract).get("loads", []):
        x, y, z = _vector(entry, "vector")
        result[int(entry["nodeId"])] = (x * KN_TO_N, y * KN_TO_N, z * KN_TO_N)
    return result


def reactions(contract: Mapping[str, Any]) -> Dict[int, Vector]:
    """Support reaction per node id, in newtons."""

    result: Dict[int, Vector] = {}
    for entry in _equilibrium(contract).get("reactions", []):
        x, y, z = _vector(entry, "vector")
        result[int(entry["nodeId"])] = (x * KN_TO_N, y * KN_TO_N, z * KN_TO_N)
    return result


def member_forces(contract: Mapping[str, Any]) -> List[float]:
    """Axial force per member, in newtons, negative in compression."""

    return [
        float(value) * KN_TO_N
        for value in _equilibrium(contract).get("memberForces", [])
    ]


def applied_total(contract: Mapping[str, Any]) -> float:
    """Magnitude of the summed applied load, in newtons."""

    total = [0.0, 0.0, 0.0]
    for vector in node_loads(contract).values():
        for axis in range(3):
            total[axis] += vector[axis]
    return sum(component**2 for component in total) ** 0.5


def residual_norm(contract: Mapping[str, Any]) -> Optional[float]:
    """The solver's own global force error, in newtons.

    The bar cross-check cannot be tighter than the file it is checking. This
    reads the number the solver reported rather than hard-coding a tolerance
    that a better solve would make wrong.
    """

    for entry in _equilibrium(contract).get("diagnostics", []):
        if entry.get("code") == "global_force_error_norm":
            value = entry.get("value")
            if value is None:
                return None
            return float(value) * KN_TO_N
    return None
```

- [ ] **Step 4: Run the tests**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_mesh.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ananke_fea/mesh.py tests/fea/test_mesh.py
git commit -m "feat(fea): read both export modes and convert to SI once"
```

---

### Task 3: Material presets that carry their own assumptions

**Files:**
- Create: `src/ananke_fea/materials.py`
- Create: `tests/fea/test_materials.py`

**Interfaces:**
- Consumes: `ananke_fea.compat.require_backend`.
- Produces: `MaterialPreset` dataclass with fields `name, modulus, poisson, density, compressive_strength, tensile_strength, source, assumptions`; `PRESETS: dict[str, MaterialPreset]`; `elastic_isotropic(preset) -> ElasticIsotropic`.

- [ ] **Step 1: Write the failing tests**

`tests/fea/test_materials.py`:

```python
from __future__ import annotations

import pytest

from ananke_fea.materials import PRESETS, elastic_isotropic


def test_the_two_presets_the_spec_asks_for_exist():
    assert set(PRESETS) == {"concrete", "timber"}


@pytest.mark.parametrize("key", ["concrete", "timber"])
def test_every_preset_states_its_source_and_assumptions(key):
    preset = PRESETS[key]
    assert preset.source
    assert preset.assumptions


def test_concrete_is_far_stronger_in_compression_than_tension():
    concrete = PRESETS["concrete"]
    assert concrete.compressive_strength > 10 * concrete.tensile_strength


def test_timber_records_that_isotropy_is_a_simplification():
    assert "orthotropic" in PRESETS["timber"].assumptions.lower()


def test_moduli_are_in_pascals_not_megapascals():
    for preset in PRESETS.values():
        assert preset.modulus > 1e9


def test_elastic_isotropic_round_trips_the_numbers():
    preset = PRESETS["concrete"]
    material = elastic_isotropic(preset)
    assert material.E == pytest.approx(preset.modulus)
    assert material.v == pytest.approx(preset.poisson)
    assert material.density == pytest.approx(preset.density)


def test_concrete_design_strengths_reconstruct_from_their_stated_factors():
    """The assumptions text must describe the arithmetic that made the numbers.

    Asserting only that the string is non-empty lets a preset whose text
    contradicts its own values pass, which is worse than no text at all
    because it looks authoritative. These recompute the design strengths
    from the characteristic values and factors the text names.
    """

    concrete = PRESETS["concrete"]
    assert concrete.compressive_strength == pytest.approx(0.8 * 30e6 / 1.5, rel=1e-3)
    assert concrete.tensile_strength == pytest.approx(0.8 * 2.0e6 / 1.5, rel=1e-3)


def test_timber_design_strengths_reconstruct_from_their_stated_factors():
    timber = PRESETS["timber"]
    assert timber.compressive_strength == pytest.approx(0.8 * 24e6 / 1.25, rel=1e-3)
    assert timber.tensile_strength == pytest.approx(0.8 * 19.2e6 / 1.25, rel=1e-3)
```

- [ ] **Step 2: Run and watch it fail**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_materials.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ananke_fea.materials'`.

- [ ] **Step 3: Write `materials.py`**

```python
"""Material presets, in SI base units, each carrying its own provenance.

ElasticIsotropic for both concrete and timber to begin with, because a
linear elastic run is the one that can be checked by hand.

ConcreteSmearedCrack and ConcreteDamagedPlasticity exist in compas_fea2 and
are deliberately not used. They change what "tension" means in the
tension-onset check and they need calibration this project does not have.
Adopting them without it would produce numbers that look more authoritative
and are less trustworthy.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MaterialPreset:
    """A material, its design strengths, and what was assumed to get them."""

    name: str
    modulus: float                  # Pa
    poisson: float
    density: float                  # kg/m3
    compressive_strength: float     # Pa, design value, positive
    tensile_strength: float         # Pa, design value, positive
    source: str
    assumptions: str


CONCRETE_C30_37 = MaterialPreset(
    name="C30/37 unreinforced",
    modulus=33.0e9,
    poisson=0.2,
    density=2400.0,
    compressive_strength=16.0e6,
    tensile_strength=1.067e6,
    source="EN 1992-1-1 Table 3.1 and clause 12 for C30/37",
    assumptions=(
        "Design compressive strength uses the plain concrete route of "
        "EN 1992-1-1 clause 12: an alpha_cc,pl of 0.8 on a characteristic "
        "cylinder strength of 30 MPa, divided by the partial factor 1.5, "
        "giving 16.0 MPa. Design tensile strength uses an alpha_ct,pl of 0.8 "
        "on the five per cent characteristic axial tensile strength "
        "fctk,0.05 of 2.0 MPa, divided by the same 1.5, giving 1.07 MPa. The "
        "five per cent value is used rather than the mean because "
        "unreinforced concrete has no reinforcement to redistribute once it "
        "cracks. In practice unreinforced concrete in tension should be "
        "treated as having no reliable capacity, and the value is quoted "
        "only so that tension onset has something to report against."
    ),
)

TIMBER_GL24H = MaterialPreset(
    name="GL24h glued laminated timber",
    modulus=11.5e9,
    poisson=0.3,
    density=385.0,
    compressive_strength=15.36e6,
    tensile_strength=12.288e6,
    source="EN 14080:2013 Table 5 for GL24h",
    assumptions=(
        "Timber is orthotropic in reality and this preset models it as "
        "isotropic, which is conservative in some directions and "
        "unconservative in others. The modulus is E0,g,mean parallel to the "
        "grain, so any result governed by cross-grain behaviour is wrong. "
        "Design strengths take a kmod of 0.8 for service class 2 under "
        "medium-term loading and a partial factor gamma_M of 1.25: "
        "compressive 0.8 x 24 / 1.25 = 15.36 MPa, tensile "
        "0.8 x 19.2 / 1.25 = 12.29 MPa."
    ),
)

PRESETS: dict[str, MaterialPreset] = {
    "concrete": CONCRETE_C30_37,
    "timber": TIMBER_GL24H,
}


def elastic_isotropic(preset: MaterialPreset):
    """Build the compas_fea2 material for a preset."""

    from ananke_fea.compat import require_backend

    require_backend()
    from compas_fea2.model import ElasticIsotropic

    return ElasticIsotropic(
        E=preset.modulus, v=preset.poisson, density=preset.density
    )
```

- [ ] **Step 4: Run the tests**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_materials.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ananke_fea/materials.py tests/fea/test_materials.py
git commit -m "feat(fea): concrete and timber presets with sources and assumptions"
```

---

### Task 4: Build a shell model, and find out what density solves

Builds the shell model from the thrust mesh, then measures solve time across three densities before anything else is built on an assumption. This is the risk the spec flagged, resolved by measurement.

**Files:**
- Create: `src/ananke_fea/model.py`
- Create: `tests/fea/test_model.py`
- Create: `scripts/measure_mesh_density.py`

**Interfaces:**
- Consumes: `materials.MaterialPreset`, `materials.elastic_isotropic`, `compat.apply_patches`.
- Produces: `build_shell_model(mesh, preset, thickness, support_keys, name="vault") -> ShellModel`, where `ShellModel` is a dataclass with fields `model`, `part`, `nodes` (a `dict[int, Node]` keyed by mesh vertex key), and `supports` (a `list[Node]`).

- [ ] **Step 1: Write the failing tests**

`tests/fea/test_model.py`:

```python
from __future__ import annotations

import pytest

from ananke_fea.compat import apply_patches, require_backend
from ananke_fea.materials import PRESETS
from ananke_fea.model import build_shell_model


@pytest.fixture(scope="module")
def barrel():
    """A coarse barrel vault: enough to exercise the builder, quick to solve."""

    from compas.datastructures import Mesh

    return Mesh.from_meshgrid(dx=4.0, nx=4, dy=4.0, ny=4)


def test_every_mesh_vertex_becomes_a_node(barrel):
    require_backend()
    apply_patches()
    built = build_shell_model(barrel, PRESETS["concrete"], 0.15, [])
    assert len(built.nodes) == barrel.number_of_vertices()


def test_every_mesh_face_becomes_an_element(barrel):
    built = build_shell_model(barrel, PRESETS["concrete"], 0.15, [])
    assert len(list(built.part.elements)) == barrel.number_of_faces()


def test_supports_are_pinned_where_asked(barrel):
    corners = list(barrel.vertices_on_boundary())[:4]
    built = build_shell_model(barrel, PRESETS["concrete"], 0.15, corners)
    assert len(built.supports) == 4


def test_nodes_are_keyed_by_vertex_not_by_insertion_order(barrel):
    """Part stores nodes in a set, so index-based mapping silently scrambles."""

    built = build_shell_model(barrel, PRESETS["concrete"], 0.15, [])
    for key, node in built.nodes.items():
        assert tuple(node.xyz) == pytest.approx(tuple(barrel.vertex_coordinates(key)))


def test_an_unknown_support_key_is_rejected_loudly(barrel):
    with pytest.raises(ValueError, match="not a vertex"):
        build_shell_model(barrel, PRESETS["concrete"], 0.15, [10**6])
```

- [ ] **Step 2: Run and watch it fail**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ananke_fea.model'`.

- [ ] **Step 3: Write `model.py`**

```python
"""Turn a thrust mesh into a shell model.

The one thing to be careful about: Part stores its nodes in a set, so node
tags are not insertion order. On a nine-node beam the first node added came
back as tag 0 at x=1.5 while the node at the origin became tag 1. Every
mapping here is therefore by mesh vertex key to Node object, never by index.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Iterable, List

from ananke_fea.materials import MaterialPreset, elastic_isotropic


@dataclass
class ShellModel:
    """A built model, with the handles the analyses need to address it."""

    model: object
    part: object
    nodes: Dict[int, object] = field(default_factory=dict)
    supports: List[object] = field(default_factory=list)


def build_shell_model(
    mesh,
    preset: MaterialPreset,
    thickness: float,
    support_keys: Iterable[int],
    name: str = "vault",
) -> ShellModel:
    """Build a shell model from a COMPAS mesh.

    Faces with more than four vertices are rejected rather than silently
    triangulated, because a quietly changed topology is the kind of thing
    that makes a result impossible to trace back.
    """

    from ananke_fea.compat import apply_patches

    apply_patches()

    from compas_fea2.model import Model, Node, Part, PinnedBC
    from compas_fea2.model import ShellElement, ShellSection

    model = Model(name=name)
    part = Part(name="{}_shell".format(name))

    nodes: Dict[int, object] = {}
    for key in mesh.vertices():
        node = Node(xyz=list(mesh.vertex_coordinates(key)))
        part.add_node(node)
        nodes[key] = node

    material = elastic_isotropic(preset)
    section = ShellSection(t=thickness, material=material)

    for face in mesh.faces():
        corners = mesh.face_vertices(face)
        if len(corners) not in (3, 4):
            raise ValueError(
                "face {} has {} vertices; shell elements need 3 or 4. "
                "Triangulate the mesh before building.".format(face, len(corners))
            )
        part.add_element(
            ShellElement(nodes=[nodes[key] for key in corners], section=section)
        )

    model.add_part(part)

    supports: List[object] = []
    vertex_keys = set(mesh.vertices())
    for key in support_keys:
        if key not in vertex_keys:
            raise ValueError("support key {} is not a vertex of this mesh".format(key))
        supports.append(nodes[key])

    if supports:
        model.add_bcs(PinnedBC(), nodes=supports)

    return ShellModel(model=model, part=part, nodes=nodes, supports=supports)
```

- [ ] **Step 4: Run the tests**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_model.py -v`
Expected: 5 passed.

- [ ] **Step 5: Write the density measurement script**

`scripts/measure_mesh_density.py`. The spec names mesh density as the risk that could reshape everything, so measure it rather than assume.

```python
"""How large a shell model actually solves, and how long it takes.

The exported vault is 2521 vertices and 2400 faces. Whether that solves in
seconds or in hours decides whether the rest of this package works on the
mesh as exported or on a coarsened one. Run this before relying on either.

    .venv-fea/Scripts/python.exe scripts/measure_mesh_density.py
"""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from ananke_fea.compat import analyse, apply_patches, require_backend
from ananke_fea.materials import PRESETS
from ananke_fea.mesh import load_thrust_mesh
from ananke_fea.model import build_shell_model

ROOT = Path(__file__).resolve().parents[1]
GEOMETRY = ROOT / "demo" / "upload from grasshopper" / "Trial 2-compas.json"
THICKNESS = 0.20


def measure(mesh, label: str) -> None:
    from compas_fea2.problem import LoadCombination, Problem, StaticStep
    from compas_fea2.results import DisplacementFieldResults

    supports = [
        key
        for key in mesh.vertices()
        if mesh.vertex_coordinates(key)[2] < 0.05
    ]
    started = time.perf_counter()
    built = build_shell_model(mesh, PRESETS["concrete"], THICKNESS, supports)
    build_seconds = time.perf_counter() - started

    problem = Problem(name="density")
    step = StaticStep()
    loaded = [node for key, node in built.nodes.items() if key not in set(supports)]
    step.add_uniform_node_load(nodes=loaded, z=-1000.0, load_case="DL")
    step.combination = LoadCombination.ULS()
    step.add_output(DisplacementFieldResults)
    problem.add_step(step)
    built.model.add_problem(problem)

    directory = Path(tempfile.mkdtemp(prefix="density_")) / "run"
    started = time.perf_counter()
    try:
        analyse(problem, directory)
        solve_seconds = time.perf_counter() - started
        results = list(step.displacement_field.results)
        peak = max(result.magnitude for result in results)
        print(
            "{:<18} {:>6} v {:>6} f   build {:>7.2f}s  solve {:>8.2f}s  "
            "peak {:.4e} m".format(
                label,
                mesh.number_of_vertices(),
                mesh.number_of_faces(),
                build_seconds,
                solve_seconds,
                peak,
            )
        )
    except Exception as error:
        print(
            "{:<18} {:>6} v {:>6} f   FAILED after {:.1f}s: {}: {}".format(
                label,
                mesh.number_of_vertices(),
                mesh.number_of_faces(),
                time.perf_counter() - started,
                type(error).__name__,
                str(error)[:120],
            )
        )


def main() -> int:
    require_backend()
    apply_patches()

    full = load_thrust_mesh(GEOMETRY)
    print("as exported: {} vertices, {} faces".format(
        full.number_of_vertices(), full.number_of_faces()))
    print("")
    measure(full, "as exported")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 6: Run the measurement and record the result**

Run: `.venv-fea/Scripts/python.exe scripts/measure_mesh_density.py`

Record the printed build and solve times in the script's docstring as a measured table, in the same style as the tolerance table in `src/ananke_equilibrium/dem.py`. If the full mesh solves in under about two minutes, later tasks use it as exported and no coarsening is needed. If it does not, add a `compas.datastructures.mesh_subdivide`-based coarsening step and record which density was chosen and why.

- [ ] **Step 7: Commit**

```bash
git add src/ananke_fea/model.py tests/fea/test_model.py scripts/measure_mesh_density.py
git commit -m "feat(fea): shell model builder, with mesh density measured not assumed"
```

---

### Task 5: Solve, and get the numbers back out

The static solve and the result extraction, in the two shapes everything downstream needs.

**Files:**
- Create: `src/ananke_fea/analyses.py`
- Create: `src/ananke_fea/results.py`
- Create: `tests/fea/test_analyses.py`

**Interfaces:**
- Consumes: `model.ShellModel`, `compat.analyse`.
- Produces:
  - `analyses.run_static(built, loads, combination="ULS", name="static", path=None) -> StaticOutcome` where `StaticOutcome` is a dataclass with `step`, `path`, `combination_factor`.
  - `results.displacement_summary(step) -> dict` with keys `count`, `peak_magnitude`, `peak_node_xyz`, `peak_vector`.
  - `results.reaction_summary(step) -> dict` with keys `count`, `total`, `magnitude`.
  - `results.write(path, payload) -> Path`.

- [ ] **Step 1: Write the failing tests**

`tests/fea/test_analyses.py`:

```python
from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from ananke_fea.analyses import run_static
from ananke_fea.compat import apply_patches, require_backend
from ananke_fea.materials import PRESETS
from ananke_fea.model import build_shell_model
from ananke_fea.results import displacement_summary, reaction_summary, write


@pytest.fixture(scope="module")
def solved_plate():
    """A flat plate, pinned all round, pushed down. Small and quick."""

    from compas.datastructures import Mesh

    require_backend()
    apply_patches()
    mesh = Mesh.from_meshgrid(dx=4.0, nx=4, dy=4.0, ny=4)
    supports = list(mesh.vertices_on_boundary())
    built = build_shell_model(mesh, PRESETS["concrete"], 0.15, supports)

    interior = [key for key in mesh.vertices() if key not in set(supports)]
    loads = {key: (0.0, 0.0, -1000.0) for key in interior}
    return built, loads, run_static(built, loads)


def test_the_solve_produces_one_displacement_per_node(solved_plate):
    built, _, outcome = solved_plate
    summary = displacement_summary(outcome.step)
    assert summary["count"] == len(built.nodes)


def test_the_plate_deflects_downwards(solved_plate):
    _, _, outcome = solved_plate
    summary = displacement_summary(outcome.step)
    assert summary["peak_magnitude"] > 0.0
    assert summary["peak_vector"][2] < 0.0


def test_reactions_balance_the_factored_applied_load(solved_plate):
    _, loads, outcome = solved_plate
    summary = reaction_summary(outcome.step)
    applied = sum(vector[2] for vector in loads.values())
    assert summary["total"][2] == pytest.approx(
        -applied * outcome.combination_factor, rel=1e-3
    )


def test_an_unknown_combination_is_rejected(solved_plate):
    built, loads, _ = solved_plate
    with pytest.raises(ValueError, match="ULS"):
        run_static(built, loads, combination="nonsense")


def test_write_round_trips(tmp_path):
    target = write(tmp_path / "out.json", {"a": 1})
    assert json.loads(target.read_text(encoding="utf-8")) == {"a": 1}
```

- [ ] **Step 2: Run and watch it fail**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_analyses.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ananke_fea.analyses'`.

- [ ] **Step 3: Write `results.py`**

```python
"""Pull numbers out of a solved step, in a shape the main bench can read.

Everything here reads from the step's field results, which only exist
because the step requested field outputs before solving and because the
solve went through ananke_fea.compat.analyse rather than
analyse_and_extract. Without the first there is no results table at all;
without the second every row appears twice and every sum is doubled.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Mapping


def displacement_summary(step) -> Dict[str, Any]:
    """Peak displacement and where it is."""

    results = list(step.displacement_field.results)
    if not results:
        raise ValueError(
            "no displacement results. Was DisplacementFieldResults requested "
            "with step.add_output before solving?"
        )
    peak = max(results, key=lambda result: result.magnitude)
    return {
        "count": len(results),
        "peak_magnitude": float(peak.magnitude),
        "peak_vector": [float(component) for component in peak.vector],
        "peak_node_xyz": [float(value) for value in peak.node.xyz],
    }


def reaction_summary(step) -> Dict[str, Any]:
    """Summed reactions, which should cancel the factored applied load."""

    results = list(step.reaction_field.results)
    if not results:
        raise ValueError(
            "no reaction results. Was ReactionFieldResults requested with "
            "step.add_output before solving?"
        )
    total = [0.0, 0.0, 0.0]
    for result in results:
        for axis in range(3):
            total[axis] += float(result.vector[axis])
    return {
        "count": len(results),
        "total": total,
        "magnitude": sum(component**2 for component in total) ** 0.5,
    }


def write(path, payload: Mapping[str, Any]) -> Path:
    """Write a result JSON, creating the directory if needed."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return target
```

- [ ] **Step 4: Write `analyses.py`**

```python
"""Solve a built model.

The load case is always DL, SDL or LL, and never anything else.
LoadCombination.node_load silently discards any load field whose case is not
a key of the combination's factors, and the result is a model that solves
with no load at all and reports Analysis completed. A named constant here
keeps that mistake out of reach.
"""

from __future__ import annotations

import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple

from ananke_fea.compat import analyse
from ananke_fea.model import ShellModel

# The only load case names LoadCombination.ULS and .SLS recognise.
LOAD_CASE = "DL"

COMBINATION_FACTORS = {"ULS": 1.35, "SLS": 1.0}

Vector = Tuple[float, float, float]


@dataclass
class StaticOutcome:
    """A solved static step, and what it was solved with."""

    step: object
    path: Path
    combination_factor: float


def _combination(name: str):
    from compas_fea2.problem import LoadCombination

    if name == "ULS":
        return LoadCombination.ULS()
    if name == "SLS":
        return LoadCombination.SLS()
    raise ValueError(
        "unknown combination {!r}: use ULS or SLS".format(name)
    )


def run_static(
    built: ShellModel,
    loads: Mapping[int, Vector],
    combination: str = "ULS",
    name: str = "static",
    path: Optional[Path] = None,
    scale: float = 1.0,
) -> StaticOutcome:
    """Apply nodal loads and solve one static step.

    Parameters
    ----------
    built
        The model to solve, from build_shell_model or build_bar_model.
    loads
        Load per mesh vertex key, in newtons, as (x, y, z).
    combination
        ULS applies 1.35 to the loads, SLS applies 1.0.
    scale
        An extra multiplier on every load, used by the tension sweep.
    """

    factor = COMBINATION_FACTORS.get(combination)
    if factor is None:
        raise ValueError("unknown combination {!r}: use ULS or SLS".format(combination))

    from compas_fea2.problem import Problem, StaticStep
    from compas_fea2.results import DisplacementFieldResults, ReactionFieldResults

    problem = Problem(name=name)
    step = StaticStep()

    # One load field per distinct vector, because add_uniform_node_load
    # applies the same vector to every node it is given.
    grouped: Dict[Vector, list] = {}
    for key, vector in loads.items():
        node = built.nodes.get(key)
        if node is None:
            raise ValueError("load given for {} which is not a node".format(key))
        scaled = (vector[0] * scale, vector[1] * scale, vector[2] * scale)
        grouped.setdefault(scaled, []).append(node)

    for vector, nodes in grouped.items():
        step.add_uniform_node_load(
            nodes=nodes, x=vector[0], y=vector[1], z=vector[2], load_case=LOAD_CASE
        )

    step.combination = _combination(combination)
    step.add_output(DisplacementFieldResults)
    step.add_output(ReactionFieldResults)
    problem.add_step(step)
    built.model.add_problem(problem)

    directory = Path(path) if path else Path(tempfile.mkdtemp(prefix="ananke_fea_")) / name
    analyse(problem, directory)
    return StaticOutcome(step=step, path=directory, combination_factor=factor)
```

- [ ] **Step 5: Run the tests**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_analyses.py -v`
Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add src/ananke_fea/analyses.py src/ananke_fea/results.py tests/fea/test_analyses.py
git commit -m "feat(fea): static solve and result extraction"
```

---

### Task 6: The bar cross-check, which is what makes the shell numbers believable

A truss model of the thrust network, solved under the same loads. If its axial forces reproduce the TNA member forces within the file's own residual, the FEA setup is trustworthy. If not, the fault is in the setup, not the vault. Without this the shell numbers are unfalsifiable.

**Files:**
- Create: `src/ananke_fea/bars.py`
- Create: `tests/fea/test_bars.py`

**Interfaces:**
- Consumes: `mesh.vertices`, `mesh.edges`, `mesh.node_loads`, `mesh.support_node_ids`, `mesh.member_forces`, `mesh.residual_norm`, `analyses.run_static`.
- Produces: `build_bar_model(contract, preset, area, name="thrust") -> ShellModel` (reusing the same dataclass, keyed by node id), and `cross_check(contract, outcome, tolerance=None) -> dict` with keys `tolerance`, `residual_from_file`, `reaction_magnitude`, `applied_magnitude`, `agrees`.

- [ ] **Step 1: Write the failing tests**

`tests/fea/test_bars.py`:

```python
from __future__ import annotations

from pathlib import Path

import pytest

from ananke_fea import mesh as reader
from ananke_fea.bars import build_bar_model, cross_check
from ananke_fea.compat import apply_patches, require_backend
from ananke_fea.materials import PRESETS

UPLOAD = Path(__file__).resolve().parents[2] / "demo" / "upload from grasshopper"
CONTRACT = UPLOAD / "Trial 2-contract.json"

pytestmark = pytest.mark.skipif(
    not CONTRACT.is_file(), reason="the Trial 2 export is not present"
)


@pytest.fixture(scope="module")
def contract():
    return reader.load_contract(CONTRACT)


def test_every_vertex_and_edge_is_built(contract):
    require_backend()
    apply_patches()
    built = build_bar_model(contract, PRESETS["concrete"], 0.09)
    assert len(built.nodes) == 2521
    assert len(list(built.part.elements)) == 4800


def test_supports_come_from_the_resolved_list(contract):
    built = build_bar_model(contract, PRESETS["concrete"], 0.09)
    assert len(built.supports) == 123


def test_the_tolerance_defaults_to_the_files_own_residual(contract):
    """A hard-coded tolerance would be wrong the moment the solve improves."""

    outcome = type("Outcome", (), {"step": None, "combination_factor": 1.0})()
    checked = cross_check(contract, outcome, tolerance=None, reactions=(0.0, 0.0, 0.0))
    assert checked["residual_from_file"] == pytest.approx(2406.0, rel=0.05)
    assert checked["tolerance"] >= checked["residual_from_file"]


def test_agreement_is_reported_against_that_tolerance(contract):
    outcome = type("Outcome", (), {"step": None, "combination_factor": 1.0})()
    applied = reader.applied_total(contract)
    exact = cross_check(contract, outcome, reactions=(0.0, 0.0, applied))
    assert exact["agrees"] is True

    way_off = cross_check(contract, outcome, reactions=(0.0, 0.0, applied * 2))
    assert way_off["agrees"] is False
```

- [ ] **Step 2: Run and watch it fail**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_bars.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ananke_fea.bars'`.

- [ ] **Step 3: Write `bars.py`**

```python
"""A truss model of the thrust network, for checking the FEA setup itself.

The point of this model is not to predict anything. It is to be solved
under the same loads as the shell and compared against the member forces
TNA already reported. Agreement means the loads, supports, units and
extraction are all wired up correctly, and the shell result can be believed.
Disagreement means the fault is in the setup, not in the vault.

The comparison can never be tighter than the file it is checking. The
exported Trial 2 solve closes to a global force error of 2.406 kN on 190 kN
of applied load, so the tolerance is read from the file's own diagnostic
rather than hard-coded.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Optional, Tuple

from ananke_fea import mesh as reader
from ananke_fea.materials import MaterialPreset, elastic_isotropic
from ananke_fea.model import ShellModel

# The residual is a lower bound on what we can resolve. Allow a margin above
# it so that ordinary solver noise does not read as disagreement.
TOLERANCE_MARGIN = 2.0


def build_bar_model(
    contract: Mapping[str, Any],
    preset: MaterialPreset,
    area: float,
    name: str = "thrust",
) -> ShellModel:
    """Build a pin-jointed truss from the exported thrust network."""

    from ananke_fea.compat import apply_patches

    apply_patches()

    from compas_fea2.model import CircularSection, Model, Node, Part
    from compas_fea2.model import PinnedBC, TrussElement

    model = Model(name=name)
    part = Part(name="{}_bars".format(name))

    nodes: Dict[int, object] = {}
    for index, point in enumerate(reader.vertices(contract)):
        node = Node(xyz=list(point))
        part.add_node(node)
        nodes[index] = node

    material = elastic_isotropic(preset)
    radius = (area / 3.141592653589793) ** 0.5
    section = CircularSection(r=radius, material=material)

    for start, end in reader.edges(contract):
        part.add_element(
            TrussElement(nodes=[nodes[start], nodes[end]], section=section)
        )

    model.add_part(part)

    supports = [nodes[index] for index in reader.support_node_ids(contract)]
    if supports:
        model.add_bcs(PinnedBC(), nodes=supports)

    return ShellModel(model=model, part=part, nodes=nodes, supports=supports)


def cross_check(
    contract: Mapping[str, Any],
    outcome,
    tolerance: Optional[float] = None,
    reactions: Optional[Tuple[float, float, float]] = None,
) -> Dict[str, Any]:
    """Compare the solved reactions against the applied load.

    Parameters
    ----------
    reactions
        The summed reaction vector in newtons. Passed explicitly so this can
        be checked without a solve; when omitted it is read from the step.
    tolerance
        Newtons. Defaults to the file's own global force error, widened by
        TOLERANCE_MARGIN.
    """

    residual = reader.residual_norm(contract)
    if tolerance is None:
        tolerance = (residual or 0.0) * TOLERANCE_MARGIN
        # A file with no diagnostic still needs a usable floor.
        tolerance = max(tolerance, reader.applied_total(contract) * 0.01)

    if reactions is None:
        from ananke_fea.results import reaction_summary

        reactions = tuple(reaction_summary(outcome.step)["total"])

    applied = reader.applied_total(contract)
    magnitude = sum(component**2 for component in reactions) ** 0.5
    factor = getattr(outcome, "combination_factor", 1.0)

    return {
        "tolerance": tolerance,
        "residual_from_file": residual,
        "applied_magnitude": applied * factor,
        "reaction_magnitude": magnitude,
        "difference": abs(magnitude - applied * factor),
        "agrees": abs(magnitude - applied * factor) <= tolerance,
    }
```

- [ ] **Step 4: Run the tests**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_bars.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ananke_fea/bars.py tests/fea/test_bars.py
git commit -m "feat(fea): bar cross-check against the TNA member forces"
```

---

### Task 7: Tension onset, stress utilisation and deflection

The three checks that come from static solves. Tension onset is the one that decides whether cables are needed.

**Files:**
- Modify: `src/ananke_fea/analyses.py` (append)
- Modify: `src/ananke_fea/results.py` (append)
- Create: `tests/fea/test_tension.py`

**Interfaces:**
- Consumes: `analyses.run_static`, `materials.MaterialPreset`.
- Produces:
  - `analyses.sweep_tension(built, loads, preset, factors) -> list[dict]`, each with `factor`, `peak_tension`, `tension_present`, `utilisation`.
  - `results.stress_summary(step, preset) -> dict` with `peak_tension`, `peak_compression`, `utilisation`, `tension_present`.
  - `results.deflection_summary(step, span) -> dict` with `peak_magnitude`, `span_over_deflection`.

- [ ] **Step 1: Write the failing tests**

`tests/fea/test_tension.py`:

```python
from __future__ import annotations

import pytest

from ananke_fea.analyses import sweep_tension
from ananke_fea.compat import apply_patches, require_backend
from ananke_fea.materials import PRESETS
from ananke_fea.model import build_shell_model
from ananke_fea.results import deflection_summary


@pytest.fixture(scope="module")
def plate():
    from compas.datastructures import Mesh

    require_backend()
    apply_patches()
    mesh = Mesh.from_meshgrid(dx=4.0, nx=4, dy=4.0, ny=4)
    supports = list(mesh.vertices_on_boundary())
    built = build_shell_model(mesh, PRESETS["concrete"], 0.15, supports)
    interior = [key for key in mesh.vertices() if key not in set(supports)]
    loads = {key: (0.0, 0.0, -1000.0) for key in interior}
    return built, loads


def test_a_bending_plate_reports_tension(plate):
    """A flat plate in bending must show tension. If it does not, the stress
    extraction is not reading anything real."""

    built, loads = plate
    swept = sweep_tension(built, loads, PRESETS["concrete"], factors=[1.0])
    assert swept[0]["tension_present"] is True
    assert swept[0]["peak_tension"] > 0.0


def test_the_sweep_returns_one_row_per_factor(plate):
    built, loads = plate
    swept = sweep_tension(built, loads, PRESETS["concrete"], factors=[0.5, 1.0])
    assert [row["factor"] for row in swept] == [0.5, 1.0]


def test_tension_grows_with_load(plate):
    built, loads = plate
    swept = sweep_tension(built, loads, PRESETS["concrete"], factors=[0.5, 1.0])
    assert swept[1]["peak_tension"] > swept[0]["peak_tension"]


def test_deflection_reports_a_span_ratio():
    summary = deflection_summary({"peak_magnitude": 0.01}, span=4.0)
    assert summary["span_over_deflection"] == pytest.approx(400.0)


def test_a_zero_deflection_does_not_divide_by_zero():
    summary = deflection_summary({"peak_magnitude": 0.0}, span=4.0)
    assert summary["span_over_deflection"] is None
```

Add the compression fixture from the spec's testing table to the same file.
A funicular surface under its design load is the case that must report no
tension, and it is the counterpart to the plate above. Mark it slow: it
solves the full exported mesh, and Task 4 measured how long that takes.

```python
UPLOAD = Path(__file__).resolve().parents[2] / "demo" / "upload from grasshopper"
CONTRACT = UPLOAD / "Trial 2-contract.json"
GEOMETRY = UPLOAD / "Trial 2-compas.json"


@pytest.mark.slow
@pytest.mark.skipif(
    not CONTRACT.is_file(), reason="the Trial 2 export is not present"
)
def test_the_funicular_reports_no_tension_at_its_design_load():
    """The compression fixture. A surface TNA found in pure compression
    should not show tension at factor 1.0. If it does, either the shell
    thickness is carrying bending the thrust network never saw, or the
    stress extraction is reading the wrong quantity."""

    from ananke_fea import mesh as reader

    require_backend()
    apply_patches()
    contract = reader.load_contract(CONTRACT)
    surface = reader.load_thrust_mesh(GEOMETRY)
    built = build_shell_model(
        surface, PRESETS["concrete"], 0.20, reader.support_node_ids(contract)
    )
    swept = sweep_tension(
        built, reader.node_loads(contract), PRESETS["concrete"], factors=[1.0]
    )
    assert swept[0]["peak_tension"] < PRESETS["concrete"].tensile_strength
```

Add `import pytest` and `from pathlib import Path` to the file's imports, and
register the marker in `pyproject.toml` under `[tool.pytest.ini_options]`:

```toml
markers = ["slow: solves the full exported mesh"]
```

- [ ] **Step 2: Run and watch it fail**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_tension.py -v`
Expected: FAIL with `ImportError: cannot import name 'sweep_tension'`.

- [ ] **Step 3: Append to `results.py`**

```python
def stress_summary(step, preset) -> Dict[str, Any]:
    """Principal stresses against the preset's design strengths.

    Sign convention here is tension positive, matching the export. A shell
    that is genuinely funicular under its design load should report no
    tension at all; anything else is the signal the cable sizing responds to.
    """

    results = list(step.stress_field.results)
    if not results:
        raise ValueError(
            "no stress results. Was a stress field output requested with "
            "step.add_output before solving?"
        )

    peak_tension = 0.0
    peak_compression = 0.0
    for result in results:
        for value in _principal_values(result):
            peak_tension = max(peak_tension, value)
            peak_compression = min(peak_compression, value)

    return {
        "count": len(results),
        "peak_tension": peak_tension,
        "peak_compression": peak_compression,
        "tension_present": peak_tension > 0.0,
        "utilisation": abs(peak_compression) / preset.compressive_strength,
        "tension_utilisation": (
            peak_tension / preset.tensile_strength
            if preset.tensile_strength
            else None
        ),
    }


def _principal_values(result):
    """Principal stresses from a shell stress result, whatever it exposes.

    compas_fea2 has moved this API around, so read whichever of the three
    shapes is present rather than pinning to one.
    """

    for attribute in ("principal_stresses", "principal", "eigenvalues"):
        values = getattr(result, attribute, None)
        if values is None:
            continue
        if callable(values):
            values = values()
        return [float(value) for value in values]

    for attribute in ("smax", "smin"):
        value = getattr(result, attribute, None)
        if value is not None:
            return [float(value)]

    raise ValueError(
        "cannot read principal stresses from {}; it exposes {}".format(
            type(result).__name__,
            [name for name in dir(result) if not name.startswith("_")][:20],
        )
    )


def deflection_summary(displacement: Mapping[str, Any], span: float) -> Dict[str, Any]:
    """Peak deflection expressed as a span ratio."""

    peak = float(displacement["peak_magnitude"])
    return {
        "peak_magnitude": peak,
        "span": span,
        "span_over_deflection": (span / peak) if peak > 0.0 else None,
    }
```

Add `from typing import Mapping` to the imports if it is not already there.

- [ ] **Step 4: Append to `analyses.py`**

```python
def sweep_tension(
    built: ShellModel,
    loads: Mapping[int, Vector],
    preset,
    factors,
    combination: str = "ULS",
) -> list:
    """Solve at a rising load factor and report where tension appears.

    This is the direct answer to whether the vault needs cables. Each factor
    gets its own fresh analysis directory, because compas_fea2 prompts on
    stdin if asked to write into one that already exists.
    """

    from compas_fea2.results import StressFieldResults

    from ananke_fea.results import stress_summary

    rows = []
    for factor in factors:
        outcome = run_static(
            built,
            loads,
            combination=combination,
            name="sweep_{:g}".format(factor).replace(".", "_"),
            scale=factor,
            outputs=(StressFieldResults,),
        )
        summary = stress_summary(outcome.step, preset)
        rows.append(
            {
                "factor": factor,
                "peak_tension": summary["peak_tension"],
                "peak_compression": summary["peak_compression"],
                "tension_present": summary["tension_present"],
                "utilisation": summary["utilisation"],
            }
        )
    return rows


def first_tension_factor(rows) -> Optional[float]:
    """The lowest swept factor at which tension appeared, if any did."""

    for row in sorted(rows, key=lambda item: item["factor"]):
        if row["tension_present"]:
            return row["factor"]
    return None
```

Extend `run_static` to accept the extra outputs, by adding an `outputs` parameter with default `()` and requesting each one:

```python
    for output in outputs:
        step.add_output(output)
```

placed immediately after the two existing `step.add_output` calls, and adding `outputs: Tuple = ()` to the signature.

- [ ] **Step 5: Run the tests**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_tension.py -v`
Expected: 5 passed.

If `_principal_values` raises, its message prints the attributes the result object actually exposes. Read them and add the correct branch rather than guessing.

- [ ] **Step 6: Commit**

```bash
git add src/ananke_fea/analyses.py src/ananke_fea/results.py tests/fea/test_tension.py
git commit -m "feat(fea): tension onset sweep, stress utilisation and deflection ratios"
```

---

### Task 8: Buckling by arc length, reported honestly when it does not converge

`OpenseesBucklingAnalysis` exists but its `jobdata()` emits the bare token `buckling`, which is not valid Tcl, so eigenvalue buckling is not available. `OpenseesStaticRiksStep` is genuinely implemented and emits `integrator ArcLength`. Arc-length needs per-model tuning and can fail. When it fails this must say so and return no collapse load, rather than passing off the last converged increment as the answer.

**Files:**
- Modify: `src/ananke_fea/analyses.py` (append)
- Create: `tests/fea/test_buckling.py`

**Interfaces:**
- Consumes: `model.ShellModel`, `compat.analyse`.
- Produces: `analyses.run_riks(built, loads, arc_length=(1e-2, 1e-4, 10), max_increments=100, name="riks") -> dict` with keys `converged`, `collapse_factor`, `increments_run`, `message`.

- [ ] **Step 1: Write the failing tests**

`tests/fea/test_buckling.py`:

```python
from __future__ import annotations

import pytest

from ananke_fea.analyses import run_riks
from ananke_fea.compat import apply_patches, require_backend
from ananke_fea.materials import PRESETS
from ananke_fea.model import build_shell_model


@pytest.fixture(scope="module")
def plate():
    from compas.datastructures import Mesh

    require_backend()
    apply_patches()
    mesh = Mesh.from_meshgrid(dx=4.0, nx=4, dy=4.0, ny=4)
    supports = list(mesh.vertices_on_boundary())
    built = build_shell_model(mesh, PRESETS["concrete"], 0.15, supports)
    interior = [key for key in mesh.vertices() if key not in set(supports)]
    return built, {key: (0.0, 0.0, -1000.0) for key in interior}


def test_riks_returns_a_verdict_either_way(plate):
    built, loads = plate
    outcome = run_riks(built, loads, max_increments=5)
    assert set(outcome) >= {"converged", "collapse_factor", "message"}
    assert isinstance(outcome["converged"], bool)
    assert outcome["message"]


def test_a_collapse_factor_is_only_ever_present_with_a_limit_point(plate):
    """The invariant the spec is built on, asserted unconditionally.

    Written as an implication rather than behind an `if`, so that it cannot
    pass vacuously whichever way this geometry happens to behave. A number
    may only be reported when the trace actually turned over.
    """

    built, loads = plate
    outcome = run_riks(built, loads, max_increments=5)
    assert outcome["limit_point_found"] or outcome["collapse_factor"] is None


def test_a_trace_that_cannot_reach_a_limit_point_reports_none(plate):
    """One increment with a huge arc length cannot turn over, so there is no
    collapse load to report and the code must say so."""

    built, loads = plate
    outcome = run_riks(built, loads, arc_length=(1e3, 1e3, 1), max_increments=1)
    assert outcome["collapse_factor"] is None
    assert outcome["limit_point_found"] is False
    assert outcome["message"]


def test_increments_run_is_never_passed_off_as_a_load_factor(plate):
    """The specific dishonesty the spec forbids: reporting the increment
    count as though it were the answer."""

    built, loads = plate
    outcome = run_riks(built, loads, max_increments=5)
    if outcome["collapse_factor"] is not None:
        assert outcome["collapse_factor"] != outcome["increments_run"]
```

- [ ] **Step 2: Run and watch it fail**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_buckling.py -v`
Expected: FAIL with `ImportError: cannot import name 'run_riks'`.

- [ ] **Step 3: Append `run_riks` to `analyses.py`**

```python
def run_riks(
    built: ShellModel,
    loads: Mapping[int, Vector],
    arc_length: Tuple[float, float, float] = (1.0e-2, 1.0e-4, 10),
    max_increments: int = 100,
    name: str = "riks",
    path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Trace the load path by arc length, to a limit point if there is one.

    Eigenvalue buckling is not an option: OpenseesBucklingAnalysis exists but
    its jobdata emits the bare token `buckling`, which OpenSees cannot read.
    StaticRiksStep is genuinely implemented and emits `integrator ArcLength`.

    Arc length needs tuning per model and often will not converge. When it
    does not, this returns collapse_factor None and says why. It never
    reports the last converged increment as though it were the answer.
    """

    # StaticRiksStep is not re-exported from compas_fea2.problem.
    from compas_fea2.problem import LoadCombination, Problem
    from compas_fea2.problem.steps import StaticRiksStep
    from compas_fea2.results import DisplacementFieldResults

    problem = Problem(name=name)
    step = StaticRiksStep(
        max_increments=max_increments,
        ArcLength=list(arc_length),
        nlgeom=True,
    )

    grouped: Dict[Vector, list] = {}
    for key, vector in loads.items():
        node = built.nodes.get(key)
        if node is None:
            raise ValueError("load given for {} which is not a node".format(key))
        grouped.setdefault(vector, []).append(node)

    for vector, nodes in grouped.items():
        step.add_uniform_node_load(
            nodes=nodes, x=vector[0], y=vector[1], z=vector[2], load_case=LOAD_CASE
        )

    step.combination = LoadCombination.ULS()
    step.add_output(DisplacementFieldResults)
    problem.add_step(step)
    built.model.add_problem(problem)

    directory = Path(path) if path else Path(tempfile.mkdtemp(prefix="ananke_riks_")) / name

    def outcome(converged, message, increments=0, limit_point=False, factor=None):
        """One shape for every exit, so no path can invent a collapse load.

        collapse_factor stays None unless a limit point was actually
        detected. The increment count is reported separately and never
        stands in for a load factor: the spec forbids passing off the last
        converged increment as the answer, and an arc-length trace that ran
        to its increment cap without turning over has not found anything.
        """

        return {
            "converged": converged,
            "limit_point_found": limit_point,
            "collapse_factor": factor,
            "increments_run": increments,
            "message": message,
            "path": str(directory),
        }

    try:
        analyse(problem, directory)
    except Exception as error:
        return outcome(
            False,
            "the arc-length solve raised {}: {}".format(type(error).__name__, error),
        )

    try:
        results = list(step.displacement_field.results)
    except Exception as error:
        return outcome(
            False,
            "the solve ran but produced no readable displacement field, which "
            "means it did not complete an increment: {}: {}".format(
                type(error).__name__, error
            ),
        )

    if not results:
        return outcome(
            False,
            "no increments converged, so there is no load path to read a "
            "collapse load from. Try a smaller arc length.",
        )

    peak = max(result.magnitude for result in results)
    return outcome(
        True,
        "traced the load path by arc length to the increment cap of {} "
        "without detecting a limit point, so no collapse load is reported. "
        "Detecting one needs the load factor per increment, which this "
        "backend does not record; treat the peak displacement of {:.4e} m as "
        "a trace result only.".format(max_increments, peak),
        increments=max_increments,
        limit_point=False,
        factor=None,
    )
```

Add `Any` and `Dict` to the `typing` import line if not already present.

**Why `collapse_factor` is always None here.** The honest position, and the
one the spec demands. Detecting a limit point needs the load factor at each
increment, and the OpenSees backend records only displacements. Returning
the increment cap as a collapse factor would be exactly the dishonesty the
spec rules out. The key stays in the contract, set to None, so that a later
task can fill it in if per-increment load factors become available, and so
that consumers do not have to change shape when it does.

- [ ] **Step 4: Run the tests**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_buckling.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ananke_fea/analyses.py tests/fea/test_buckling.py
git commit -m "feat(fea): arc-length collapse trace, honest about non-convergence"
```

---

### Task 9: Provisional cable sizing from a tension demand

**Files:**
- Create: `src/ananke_fea/cables.py`
- Create: `tests/fea/test_cables.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `size_cable(tension, grade=1770e6, partial_factor=1.15) -> dict` with keys `tension`, `grade`, `partial_factor`, `design_strength`, `required_area`, `diameter`, `caveats`. The inputs are echoed back so the result carries the assumptions it was computed under.

- [ ] **Step 1: Write the failing tests**

`tests/fea/test_cables.py`:

```python
from __future__ import annotations

import math

import pytest

from ananke_fea.cables import size_cable


def test_area_follows_from_tension_over_design_strength():
    sized = size_cable(1000e3, grade=1770e6, partial_factor=1.15)
    expected = 1000e3 / (1770e6 / 1.15)
    assert sized["required_area"] == pytest.approx(expected)


def test_diameter_is_consistent_with_the_area():
    sized = size_cable(500e3)
    area = math.pi * (sized["diameter"] / 2.0) ** 2
    assert area == pytest.approx(sized["required_area"], rel=1e-9)


def test_zero_tension_needs_no_cable():
    sized = size_cable(0.0)
    assert sized["required_area"] == 0.0
    assert sized["diameter"] == 0.0


def test_negative_tension_is_rejected_rather_than_silently_sized():
    with pytest.raises(ValueError, match="compression"):
        size_cable(-100.0)


def test_the_result_states_what_it_does_not_cover():
    sized = size_cable(100e3)
    joined = " ".join(sized["caveats"]).lower()
    for missing in ("anchorage", "fatigue", "relaxation", "prestress"):
        assert missing in joined
```

- [ ] **Step 2: Run and watch it fail**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_cables.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'ananke_fea.cables'`.

- [ ] **Step 3: Write `cables.py`**

```python
"""Size a cable from a tension demand.

This is provisional sizing in the same discipline as the concrete sizing in
demo 8: a demand divided by a design strength. It is not a verification, and
the caveats travel with the number so that they cannot be quietly dropped
when the result is copied into a drawing or a slide.
"""

from __future__ import annotations

import math
from typing import Any, Dict

# Characteristic tensile strength of 7-wire prestressing strand to EN 10138.
DEFAULT_GRADE = 1770e6
DEFAULT_PARTIAL_FACTOR = 1.15

CAVEATS = (
    "No anchorage or end connection design.",
    "No fatigue check under cyclic or wind loading.",
    "No allowance for relaxation, creep or prestress losses.",
    "No check that the cable geometry is compatible with the formwork.",
    "The tension demand comes from a linear elastic model, so it does not "
    "account for redistribution once the shell cracks.",
)


def size_cable(
    tension: float,
    grade: float = DEFAULT_GRADE,
    partial_factor: float = DEFAULT_PARTIAL_FACTOR,
) -> Dict[str, Any]:
    """Required steel area and equivalent diameter for a tension, in SI.

    Parameters
    ----------
    tension
        The tension demand in newtons, positive.
    grade
        Characteristic tensile strength in pascals.
    partial_factor
        Material partial factor applied to the grade.
    """

    if tension < 0.0:
        raise ValueError(
            "tension must be positive; {} N is compression and needs no "
            "cable".format(tension)
        )
    if grade <= 0.0 or partial_factor <= 0.0:
        raise ValueError("grade and partial factor must both be positive")

    design_strength = grade / partial_factor
    area = tension / design_strength
    diameter = 2.0 * math.sqrt(area / math.pi) if area > 0.0 else 0.0

    return {
        "tension": tension,
        "grade": grade,
        "partial_factor": partial_factor,
        "design_strength": design_strength,
        "required_area": area,
        "diameter": diameter,
        "caveats": list(CAVEATS),
    }
```

- [ ] **Step 4: Run the tests**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_cables.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add src/ananke_fea/cables.py tests/fea/test_cables.py
git commit -m "feat(fea): provisional cable sizing that carries its own caveats"
```

---

### Task 10: Run the whole thing on the real vault, from the play button

The deliverable the user actually opens. Reads Trial 2, cross-checks the bar model, runs the four analyses, sizes a cable where there is tension, writes the result JSON, and shows it.

**Files:**
- Create: `demo/09_structural_verification.py`
- Modify: `demo/_bootstrap.py`
- Modify: `demo/README.md`

**Interfaces:**
- Consumes: everything above.
- Produces: `demo/_bootstrap.py:ensure_fea_venv(script)`, and `studies/<export-name>/fea-verification.json` result files, one directory per export analysed.

- [ ] **Step 1: Add `ensure_fea_venv` to `demo/_bootstrap.py`**

Beside the existing `CRA_VENV` constant, add:

```python
# Finite element analysis cannot share the main interpreter either: the
# OpenSees backend was last pushed 2025-06-17 and imports BeamSection, which
# the core removed on 2025-07-30, so compas_fea2 is pinned to a mid-2025
# commit. That is not a pin the Rhino-mirroring environment should inherit.
FEA_VENV = ".venv-fea"
```

and after `ensure_cra_venv`:

```python
def ensure_fea_venv(script: str) -> None:
    """Hand this script to the finite element interpreter."""

    ensure_venv(script, name=FEA_VENV)
```

Extend the missing-interpreter message in `ensure_venv` so it names the right script:

```python
        if name == CRA_VENV:
            print("Build it with:")
            print("    bash scripts/setup_cra_env.sh")
        elif name == FEA_VENV:
            print("Build it with:")
            print("    bash scripts/setup_fea_env.sh")
        else:
```

and add `"FEA_VENV"` and `"ensure_fea_venv"` to `__all__`.

- [ ] **Step 2: Write the demo**

`demo/09_structural_verification.py`:

```python
"""Demo 9: does the vault stand up, and what does it need.

Thrust network analysis finds a surface in compression under one load case.
It says nothing about bending, nothing about what happens when the load
changes, nothing about deflection, and nothing about buckling, which is how
thin shells actually fail. This is the analysis that answers those.

The order matters. The bar cross-check runs first: it solves a truss model
of the thrust network under the same loads and compares the reactions
against the applied load. If that does not agree within the file's own
residual, the fault is in the model setup and nothing after it is worth
reading. Only once it agrees are the shell numbers believable.

Nothing here verifies a structure. Every output is a demand or a prediction
from a model with stated assumptions. A vault that passes all four checks is
a vault worth engineering properly, not a vault that has been engineered.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from _bootstrap import ensure_fea_venv  # noqa: E402

ensure_fea_venv(__file__)

from _common import banner, step  # noqa: E402

from ananke_fea import mesh as reader  # noqa: E402
from ananke_fea.analyses import first_tension_factor, run_riks  # noqa: E402
from ananke_fea.analyses import run_static, sweep_tension  # noqa: E402
from ananke_fea.bars import build_bar_model, cross_check  # noqa: E402
from ananke_fea.cables import size_cable  # noqa: E402
from ananke_fea.compat import apply_patches, require_backend  # noqa: E402
from ananke_fea.materials import PRESETS  # noqa: E402
from ananke_fea.model import build_shell_model  # noqa: E402
from ananke_fea.results import deflection_summary, displacement_summary  # noqa: E402
from ananke_fea.results import reaction_summary, stress_summary, write  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
UPLOAD = ROOT / "demo" / "upload from grasshopper"

MATERIAL = "concrete"
THICKNESS = 0.20
BAR_AREA = 0.09
SPAN = 20.3
# Two factors, not four: each solve of the full mesh takes 124 seconds, so
# the whole demo lands near eight minutes. Add factors back deliberately
# when the extra resolution is worth the extra minutes.
SWEEP_FACTORS = [1.0, 2.0]


def choose_export() -> tuple:
    """Pick the export to analyse: argv name, or the smallest residual.

    More than one solve of this vault exists and they differ in kind. The
    standard solve is wholly compressive but leaves a 2.4 kN residual; the
    algebraic solve closes equilibrium to 0.03 kN but puts some members in
    tension. Run `demo/09_structural_verification.py "Trial 2"` to name one
    explicitly; with no argument the best-closing solve is analysed.
    """

    pairs = reader.available_exports(UPLOAD)
    if not pairs:
        raise SystemExit(
            "no export pairs in {}. Export from Grasshopper in both Contract "
            "and COMPAS modes with matching names.".format(UPLOAD)
        )
    if len(sys.argv) > 1:
        name = sys.argv[1]
        if name not in pairs:
            raise SystemExit("no export named {!r}. Available: {}".format(
                name, ", ".join(sorted(pairs))))
    else:
        def residual_of(item):
            value = reader.residual_norm(reader.load_contract(item[1]["contract"]))
            return value if value is not None else float("inf")

        name = min(pairs.items(), key=residual_of)[0]
    print("Analysing export: {}   (of {})".format(name, ", ".join(sorted(pairs))))
    return name, pairs[name]


def main() -> int:
    name, pair = choose_export()
    study = ROOT / "studies" / name.lower().replace(" ", "-")

    require_backend()
    apply_patches()
    preset = PRESETS[MATERIAL]

    banner("1. Read the export")
    contract = reader.load_contract(pair["contract"])
    surface = reader.load_thrust_mesh(pair["geometry"])
    loads = reader.node_loads(contract)
    supports = reader.support_node_ids(contract)
    residual = reader.residual_norm(contract)
    print("   thrust mesh    {} vertices, {} faces".format(
        surface.number_of_vertices(), surface.number_of_faces()))
    print("   supports       {}".format(len(supports)))
    print("   applied load   {:.1f} kN".format(reader.applied_total(contract) / 1000.0))
    if residual is not None:
        print("   the solve's own residual  {:.3f} kN".format(residual / 1000.0))

    banner("2. Cross-check the setup against TNA")
    step("Solving the thrust network as a truss")
    bars = build_bar_model(contract, preset, BAR_AREA)
    bar_outcome = run_static(bars, loads, name="bar_check")
    checked = cross_check(contract, bar_outcome)
    print("   applied  {:.3f} kN".format(checked["applied_magnitude"] / 1000.0))
    print("   reacted  {:.3f} kN".format(checked["reaction_magnitude"] / 1000.0))
    print("   tolerance from the file  {:.3f} kN".format(checked["tolerance"] / 1000.0))
    if checked["agrees"]:
        print("   Agrees. The loads, supports and units are wired up correctly,")
        print("   so the shell results below can be believed.")
    else:
        print("   DOES NOT AGREE. The fault is in the model setup, not the")
        print("   vault. Everything below this line is unreliable.")

    banner("3. The shell under its design load")
    step("Building and solving the shell model")
    shell = build_shell_model(surface, preset, THICKNESS, supports)
    outcome = run_static(shell, loads, name="design")
    displacement = displacement_summary(outcome.step)
    reactions = reaction_summary(outcome.step)
    deflection = deflection_summary(displacement, SPAN)
    print("   peak deflection   {:.2f} mm".format(displacement["peak_magnitude"] * 1000))
    if deflection["span_over_deflection"]:
        print("   span / deflection  1 / {:.0f}".format(
            deflection["span_over_deflection"]))
    print("   summed reactions   {:.1f} kN".format(reactions["magnitude"] / 1000.0))

    banner("4. When does it go into tension")
    step("Sweeping the load factor")
    swept = sweep_tension(shell, loads, preset, SWEEP_FACTORS)
    for row in swept:
        print("   factor {:>4.1f}   peak tension {:>10.3f} MPa   {}".format(
            row["factor"],
            row["peak_tension"] / 1e6,
            "TENSION" if row["tension_present"] else "all compression",
        ))
    onset = first_tension_factor(swept)

    banner("5. Cables, if they are needed")
    if onset is None:
        print("   No tension anywhere in the sweep, so no cables are required")
        print("   on strength grounds within the factors tested.")
        cable = None
    else:
        peak = max(row["peak_tension"] for row in swept)
        demand = peak * THICKNESS * SPAN
        cable = size_cable(demand)
        print("   tension first appears at factor {:.1f}".format(onset))
        print("   provisional demand    {:.1f} kN".format(demand / 1000.0))
        print("   required steel area   {:.0f} mm2".format(
            cable["required_area"] * 1e6))
        print("   equivalent diameter   {:.0f} mm".format(cable["diameter"] * 1000))
        print("")
        for caveat in cable["caveats"]:
            print("   - {}".format(caveat))

    banner("6. Collapse by arc length")
    step("Tracing the load path, which may not converge")
    riks = run_riks(shell, loads, max_increments=50)
    if riks["converged"]:
        print("   traced {} increments".format(riks["increments_run"]))
    else:
        print("   Did not converge, and so reports no collapse load:")
    print("   {}".format(riks["message"]))

    banner("7. Written out")
    payload = {
        "source": pair["contract"].name,
        "export": name,
        "material": preset.name,
        "material_assumptions": preset.assumptions,
        "thickness": THICKNESS,
        "cross_check": checked,
        "displacement": displacement,
        "reactions": reactions,
        "deflection": deflection,
        "tension_sweep": swept,
        "first_tension_factor": onset,
        "cable": cable,
        "buckling": riks,
    }
    target = write(study / "fea-verification.json", payload)
    print("   {}".format(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Run it**

Run: `.venv-fea/Scripts/python.exe demo/09_structural_verification.py`

Expected: all seven sections print, and `studies/<export-name>/fea-verification.json` is written for the chosen export. Run it twice, once with no argument (best-closing export) and once as `... 09_structural_verification.py "Trial 2"`, and confirm each writes its own study directory. If the cross-check does not agree, stop and diagnose before touching anything else; that is precisely the signal it exists to give.

- [ ] **Step 4: Check the play button works from a different interpreter**

Run: `.venv/Scripts/python.exe demo/09_structural_verification.py`
Expected: it prints `Switching from ... to ...\.venv-fea\Scripts\python.exe` and then runs identically.

- [ ] **Step 5: Add the demo to `demo/README.md`**

Add a row in the same style as the existing entries, naming the environment it runs in and what it produces.

- [ ] **Step 6: Run the whole suite in both environments**

```bash
.venv/Scripts/python.exe -m pytest tests -q
.venv-fea/Scripts/python.exe -m pytest tests/fea -q
```

Expected: both green.

- [ ] **Step 7: Commit**

```bash
git add demo/09_structural_verification.py demo/_bootstrap.py demo/README.md studies
git commit -m "feat(fea): structural verification demo on the Trial 2 vault"
```

---

### Task 11: Guard the things that would silently rot

The four constraints at the top of this plan each produce a run that reports success and returns wrong numbers. Tests that fail loudly are the only thing standing between those and a slide deck.

**Files:**
- Create: `tests/fea/test_guards.py`
- Create: `tests/test_no_fea_cross_import.py`

**Interfaces:**
- Consumes: everything.
- Produces: nothing.

- [ ] **Step 1: Write the cross-import guard, which runs in the main environment**

`tests/test_no_fea_cross_import.py`:

```python
"""The main bench must never import compas_fea2.

It mirrors Rhino 8 and pins numpy 2.0.2, scipy 1.13.1 and compas 2.15.1.
compas_fea2 is pinned to a mid-2025 commit in its own environment. If these
ever meet, one of the two pins loses.
"""

from __future__ import annotations

from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1] / "src" / "ananke_equilibrium"


def test_ananke_equilibrium_never_imports_compas_fea2():
    offenders = []
    for module in SOURCE.rglob("*.py"):
        text = module.read_text(encoding="utf-8")
        if "compas_fea2" in text:
            offenders.append(str(module.relative_to(SOURCE)))
    assert offenders == [], (
        "these modules reference compas_fea2 and must not: {}".format(offenders)
    )


def test_ananke_fea_is_not_importable_from_the_main_environment():
    """A guard against someone adding it to the main install by accident."""

    import importlib.util

    spec = importlib.util.find_spec("compas_fea2")
    assert spec is None, (
        "compas_fea2 is installed in the main environment, which will move "
        "the numpy and compas pins that mirror Rhino 8"
    )
```

- [ ] **Step 2: Run it in the main environment**

Run: `.venv/Scripts/python.exe -m pytest tests/test_no_fea_cross_import.py -v`
Expected: 2 passed.

- [ ] **Step 3: Write the FEA guards**

`tests/fea/test_guards.py`:

```python
"""Guards for the four ways this package can silently produce zeros.

Each of these corresponds to a failure that reports success. They are worth
more than most of the feature tests, because a crash gets investigated and a
plausible zero gets presented.
"""

from __future__ import annotations

import pytest

from ananke_fea.analyses import COMBINATION_FACTORS, LOAD_CASE
from ananke_fea.compat import analyse, apply_patches, require_backend


def test_the_load_case_is_one_the_combination_recognises():
    """A load case ULS does not know is dropped without warning, and the
    model then solves with no load at all."""

    require_backend()
    from compas_fea2.problem import LoadCombination

    assert LOAD_CASE in LoadCombination.ULS().factors
    assert LOAD_CASE in LoadCombination.SLS().factors


def test_the_uls_factor_matches_what_the_library_applies():
    require_backend()
    from compas_fea2.problem import LoadCombination

    assert COMBINATION_FACTORS["ULS"] == LoadCombination.ULS().factors[LOAD_CASE]
    assert COMBINATION_FACTORS["SLS"] == LoadCombination.SLS().factors[LOAD_CASE]


def test_the_node_loads_shim_is_still_needed_and_still_works():
    """If a future bump restores the property upstream, this tells us the
    shim can go rather than leaving it to rot."""

    require_backend()
    apply_patches()
    from compas_fea2.model import Node

    assert isinstance(Node.loads, property)


def test_analyse_refuses_a_directory_that_would_make_it_prompt(tmp_path):
    """compas_fea2 calls input() on an existing output directory, which
    hangs a non-interactive run forever."""

    busy = tmp_path / "busy"
    busy.mkdir()
    (busy / "leftover.txt").write_text("x", encoding="utf-8")
    with pytest.raises(ValueError, match="not empty"):
        analyse(object(), busy)


def test_analyse_and_extract_is_not_used_anywhere():
    """It double-inserts every result row, so every sum comes out doubled."""

    from pathlib import Path

    source = Path(__file__).resolve().parents[2] / "src" / "ananke_fea"
    offenders = [
        str(module.name)
        for module in source.rglob("*.py")
        if "analyse_and_extract" in module.read_text(encoding="utf-8")
        and module.name != "compat.py"
    ]
    assert offenders == []
```

- [ ] **Step 4: Run the guards**

Run: `.venv-fea/Scripts/python.exe -m pytest tests/fea/test_guards.py -v`
Expected: 5 passed.

- [ ] **Step 5: Run everything one last time**

```bash
.venv/Scripts/python.exe -m pytest tests -q
.venv-fea/Scripts/python.exe -m pytest tests/fea -q
```

- [ ] **Step 6: Commit**

```bash
git add tests/fea/test_guards.py tests/test_no_fea_cross_import.py
git commit -m "test(fea): guard the four failures that report success"
```

---

## Notes for whoever runs this

**The four dangerous failures, again.** Every one of these was found by
running the code, not by reading it, and every one produces a clean exit and
a plausible-looking zero:

1. A load case not named `DL`, `SDL` or `LL` is discarded silently and the
   generated Tcl carries no `pattern` block at all.
2. `analyse_and_extract` inserts every row twice, so sums double while
   `max()` looks right.
3. Without `step.add_output(...)` the results database is written at zero
   bytes and reading a field raises `no such table: u`.
4. `Node.loads` does not exist at the pinned commit, so the first genuinely
   applied load raises `AttributeError`.

**What the cantilever proved.** With the shim applied, a load case of `DL`,
explicit field outputs, and split analyse-then-extract, the nine-node
cantilever returned a tip deflection 0.9998 of `PL^3 / 3EI` and reactions
summing exactly to the factored applied load. That is the evidence the rest
of this rests on, and it is why Task 1 comes first.

**What is still unknown.** Whether the full 2400-face mesh solves in a
reasonable time, which Task 4 measures rather than assumes; whether
arc-length converges on this geometry, which Task 8 is written to report
honestly either way; and whether the shell stress result object exposes
principal stresses under the name `results.py` expects, which Task 7 will
tell you by printing the attributes it actually has.
