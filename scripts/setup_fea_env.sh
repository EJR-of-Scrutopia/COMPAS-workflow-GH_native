#!/usr/bin/env bash
# Build the finite element environment, with the OpenSees backend.
#
# Earlier notes in this repository said the compas_fea2 OpenSees bridge was
# unpublished. That was wrong. The backends live under their own GitHub
# organisation, `fea2`, not under `compas-dev` or `BlockResearchGroup`:
#
#   fea2/compas_fea2_opensees      fea2/compas_fea2_abaqus
#   fea2/compas_fea2_sofistik      fea2/compas_fea2_ansys
#   fea2/compas_fea2_castem        fea2/compas_fea2_viewer
#   fea2/compas_fea2_vedo
#
# Three things this environment has to get right:
#
# 1. The backend needs compas_fea2 from git, not the PyPI 0.2.1.
#
# 2. The two repositories have drifted. The OpenSees backend was last pushed
#    2025-06-17 and imports BeamSection, which compas_fea2 removed on
#    2025-07-30 in e8b97e8. So the core is pinned to 664ec20 (2025-06-16),
#    the last commit contemporary with the backend.
#
# 3. compas_fea2 gets its own interpreter rather than sharing the main one,
#    because pinning the core to a mid-2025 commit is not something the
#    Rhino-mirroring environment should inherit.
#
# After this script, one manual step remains: the backend shells out to a
# standalone OpenSees executable, and `openseespy` only provides
# `opensees.pyd`, a Python extension module. Download OpenSees from
# https://opensees.berkeley.edu/ (the page drives it through JavaScript, so it
# cannot be scripted), then run:
#
#     .venv/Scripts/python.exe scripts/install_opensees.py <extracted folder>
#
# That writes the .env the backend reads. compas_fea2 needs four more keys
# there besides EXE (VERBOSE, POINT_OVERLAP, GLOBAL_TOLERANCE, PRECISION);
# it reads them with no fallback and raises AttributeError on a missing one.
#
# Registration is explicit. Importing the backend is not enough:
#
#     compas_fea2.set_backend("compas_fea2_opensees")
set -euo pipefail

ENV_DIR="${1:-.venv-fea}"
CORE_COMMIT="664ec20"

echo "=== Creating the FEA environment at ${ENV_DIR} ==="
uv venv --python 3.12 "${ENV_DIR}"

echo "=== Installing compas_fea2 pinned to ${CORE_COMMIT}, plus the backend ==="
# --link-mode=copy: this repository lives in OneDrive, and uv's hardlinking
# fails on cloud-backed files with os error 396.
uv pip install --link-mode=copy --python "${ENV_DIR}" \
    "git+https://github.com/fea2/compas_fea2@${CORE_COMMIT}" \
    "git+https://github.com/fea2/compas_fea2_opensees@main" \
    openseespy

echo "=== Versions ==="
"${ENV_DIR}/Scripts/python.exe" -c "
import importlib.metadata as m, sys
print('python', sys.version.split()[0])
for p in ['compas_fea2', 'compas_fea2_opensees', 'openseespy', 'numpy']:
    try:
        print('  {:<24} {}'.format(p, m.version(p)))
    except Exception:
        print('  {:<24} MISSING'.format(p))
"

echo "=== Backend check ==="
"${ENV_DIR}/Scripts/python.exe" -c "
try:
    import compas_fea2_opensees
    from compas_fea2 import BACKENDS
    print('backend registered:', list(dict(BACKENDS).keys()))
except NotImplementedError:
    print('The backend imported but could not locate an OpenSees executable.')
    print('')
    print('Download OpenSees for Windows from https://opensees.berkeley.edu/')
    print('then create a .env file beside this script containing:')
    print('    EXE=C:/path/to/OpenSees.exe')
except Exception as error:
    print('backend failed:', type(error).__name__, error)
" || true

echo "=== Installing the project and pytest into ${ENV_DIR} ==="
# dependencies = [] in pyproject, so --no-deps adds nothing and cannot
# disturb the pins. This is what makes ananke_fea and ananke_equilibrium
# importable in this environment.
uv pip install --link-mode=copy --python "${ENV_DIR}" --no-deps -e .
uv pip install --link-mode=copy --python "${ENV_DIR}" "pytest>=8,<10"

echo "=== Running the closed-form check ==="
"${ENV_DIR}/Scripts/python.exe" -m pytest tests/fea/test_cantilever.py -q || true
