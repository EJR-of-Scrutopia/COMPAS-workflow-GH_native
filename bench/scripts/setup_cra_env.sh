#!/usr/bin/env bash
# Build the coupled rigid-block analysis environment.
#
# compas_cra 0.4.0 cannot share this project's interpreter. It needs all four
# of these at once, and three of them conflict with the Rhino-mirroring pins:
#
#   Python <= 3.10   pyomo 6.4.2 breaks on 3.11+ (__getstate__ returns a tuple)
#   numpy < 2        pyomo 6.4.2 calls np.float_, removed in NumPy 2.0
#   pyomo == 6.4.2   6.8.0+ imports but dies in nl_writer during the solve
#   IPOPT on PATH    every CRA solver calls SolverFactory("ipopt")
#
# So it gets its own interpreter and exchanges COMPAS JSON with the main
# environment. This is the same answer docs/compas-suite-adoption.md already
# gives for compas_cem.
set -euo pipefail

ENV_DIR="${1:-.venv-cra}"

echo "=== Creating Python 3.10 environment at ${ENV_DIR} ==="
uv venv --python 3.10 "${ENV_DIR}"

echo "=== Installing the CRA stack ==="
uv pip install --python "${ENV_DIR}" \
    "numpy==1.26.4" \
    "scipy==1.13.1" \
    "compas==2.15.1" \
    "compas_assembly==0.7.1" \
    "compas_cra==0.4.0" \
    "shapely"

echo "=== Installed versions ==="
"${ENV_DIR}/Scripts/python.exe" -c "
import importlib.metadata as m, sys
print('python', sys.version.split()[0])
for p in ['numpy', 'scipy', 'compas', 'compas_assembly', 'compas_cra', 'pyomo', 'shapely']:
    try:
        print('  {:<18} {}'.format(p, m.version(p)))
    except Exception:
        print('  {:<18} MISSING'.format(p))
"

echo "=== Import check ==="
"${ENV_DIR}/Scripts/python.exe" -c "
import compas_cra.equilibrium as eq
print('compas_cra.equilibrium imports OK')
print('solvers:', [n for n in dir(eq) if n.endswith('_solve')])
"

echo "=== Note on the viewer ==="
echo "compas_cra ships a viewer built on compas_view2, which imports"
echo "compas.robots, a module COMPAS 2 removed. It cannot run here, and"
echo "installing Qt into this environment breaks pyomo. The demo wrappers"
echo "replace the drawing step with a printed summary instead."

echo "=== Done. IPOPT must be on PATH for a solve; see scripts/ipopt_path.txt ==="
