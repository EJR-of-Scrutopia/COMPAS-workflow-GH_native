"""Make the pinned compas_fea2 usable, and record exactly what was wrong.

The OpenSees backend was last pushed 2025-06-17 and imports BeamSection,
which the core removed on 2025-07-30, so the core is pinned to 664ec20. That
commit is internally inconsistent in one place: model/nodes.py sets
self._loads but leaves the public `loads` property commented out, while
problem/steps/step.py:117 calls node.loads when a combination is assigned.
The result is that applying any load a combination recognises raises
AttributeError. One property closes it.

A second, unrelated patch lives here for the same reason: OpenseesStress-
FieldResults.jobdata() returns the bare string "S" (its own input_name)
instead of Tcl, which OpenSees rejects with "invalid command name \"S\""
and aborts the whole run, silently, because the wrapper's own error
detection only matches the literal word "error". The patch replaces it
with a real export loop, matching the pattern the working displacement and
reaction outputs already use.

A third defect is documented here rather than patched: at this pin,
`extract_results` rounds displacements to six decimal places, not six
significant figures, before writing them to SQLite, so any sub-micron
component quantises to zero. Fixtures in this project load-scale well
above that floor and vault-scale results are unaffected, but member-force
statistics computed from displacements (see bars.member_axial_forces)
carry a noise floor on the order of EA/L times 1e-6.

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

    from compas_fea2_opensees.results.fields import OpenseesStressFieldResults

    def _stress_jobdata(self):
        # The upstream stub returns the bare token "S", which is invalid Tcl
        # and aborts the run while the wrapper still reports success. This
        # emits the same export-loop pattern the working displacement and
        # reaction outputs use: the raw eleResponse "stresses" per element,
        # which for shells is 8 resultants per integration point in the
        # element local frame. The conversion to surface stresses happens in
        # ananke_fea.results, not here.
        return (
            'set stressFile [open "{}.out" "w"]\n'
            "set allElements [getEleTags]\n"
            "foreach eleTag $allElements {{\n"
            '    set eleStresses [eleResponse $eleTag "stresses"]\n'
            '    puts $stressFile "$eleTag $eleStresses"\n'
            "}}\n"
            "close $stressFile\n"
        ).format(self.field_name)

    # Marker attribute, not identity: the closure above is rebuilt every
    # call, so it would never equal whatever was assigned last time even
    # once already patched. The marker is what makes a second apply_patches()
    # call a no-op.
    _stress_jobdata._ananke_patch = True
    if not getattr(OpenseesStressFieldResults.jobdata, "_ananke_patch", False):
        OpenseesStressFieldResults.jobdata = _stress_jobdata
        newly.append("OpenseesStressFieldResults.jobdata")

    _applied.extend(newly)
    return newly


def analyse(problem, path) -> None:
    """Solve and extract, avoiding the double-extraction bug.

    The double-extracting convenience wrapper that Problem offers runs
    extraction twice and inserts every result row twice, so sums come out
    doubled while max() looks correct. Splitting the call into analyse()
    then extract_results() gives one row per node instead.

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
