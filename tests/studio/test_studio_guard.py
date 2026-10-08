"""The studio must stay a thin client of the solver environments.

bench/studio runs in the main venv, which mirrors Rhino 8. Importing
compas_fea2 there would fight the fea pin; importing ananke_fea would pull
compat shims into an environment they were never written for; importing
numpy, scipy or compas would couple the server to the pinned stack for no
reason: everything the studio does is JSON and subprocess. pyomo and
shapely are on the list for the same reason: pyomo lives in .venv-cra and
reaches for a native IPOPT binary, shapely carries its own GEOS, and
neither belongs in the server process. The solver work is shelled to
.venv-fea, so only import statements are forbidden, matching
tests/test_no_fea_cross_import.py.
"""

from __future__ import annotations

import re
from pathlib import Path

STUDIO = Path(__file__).resolve().parents[2] / "bench" / "studio"

FORBIDDEN = re.compile(
    r"^\s*(import\s+(compas_fea2|compas_cra|compas_assembly|ananke_fea|compas"
    r"|numpy|scipy|pyomo|shapely)\b"
    r"|from\s+(compas_fea2|compas_cra|compas_assembly|ananke_fea|compas"
    r"|numpy|scipy|pyomo|shapely)\b)",
    re.MULTILINE,
)


def test_studio_never_imports_the_solver_stacks():
    offenders = []
    for module in STUDIO.rglob("*.py"):
        if module.name in ("solve_stage.py", "solve_cra.py", "solve_cablenet.py"):
            # The three deliberate exceptions: each executes inside a solver
            # interpreter as its own process, never in the server process;
            # staging.py, the CRA caller and cablenet.py only ever run them
            # as a subprocess under that interpreter.
            #
            # solve_cablenet.py joined them on 7 October 2026, under the same
            # rule and not as a relaxation of it. The staged cable net solve
            # was first written inside cablenet.py, in the server process,
            # and this guard caught it. Note that deleting its numpy import
            # would have turned the test green while the coupling remained,
            # because tree_forest_compas pulls numpy in transitively and no
            # pattern here matches that import. The guard was satisfied by
            # moving the solve behind a subprocess boundary, which is what it
            # was asking for. cablenet.py itself stays on the forbidden side
            # and must never import a solver stack.
            continue
        if FORBIDDEN.search(module.read_text(encoding="utf-8")):
            offenders.append(str(module.relative_to(STUDIO)))
    assert offenders == [], (
        "these studio modules import a solver stack and must not: {}".format(offenders)
    )


def test_the_studio_package_exists():
    assert (STUDIO / "__init__.py").is_file()
