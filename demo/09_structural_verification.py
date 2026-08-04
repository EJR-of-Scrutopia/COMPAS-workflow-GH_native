"""Demo 9: does the vault stand up, and what does it need.

Thrust network analysis finds a surface in compression under one load case.
It says nothing about bending, nothing about what happens when the load
changes, nothing about deflection, and nothing about buckling, which is how
thin shells actually fail. This is the analysis that answers those.

The order matters. The bar cross-check runs first: it solves a slender beam
model of the thrust network under the same loads and compares the reacted
load, and the member forces, against what TNA already reported. Reactions
balancing the applied load is the wiring falsifier: it is what proves the
loads, supports, units and extraction are correct. Member forces are
compared too, but this network is statically indeterminate and admits
self-stress, so TNA's member distribution and the elastic one can
legitimately differ bar by bar even when the setup is correct; that
difference is reported for scale, not treated as a fault.

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
from ananke_fea.bars import build_bar_model, cross_check, member_axial_forces  # noqa: E402
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
# Deliberately slender: radius about 18 mm. The bar cross-check now uses
# BeamElement, not TrussElement, because the exported thrust network is an
# undiagonalised quad grid with a shear mechanism in every panel that a
# rotational restraint cannot fix. A small section keeps the bending share
# of the stiffness low enough (about 5e-4 of the axial share) that
# mechanisms are suppressed without the check stopping being an axial one.
BAR_AREA = 1e-3
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
    step("Solving the thrust network as a slender beam frame")
    bars = build_bar_model(contract, preset, BAR_AREA)
    bar_outcome = run_static(bars, loads, name="bar_check")
    forces = member_axial_forces(
        bars, contract, bar_outcome, area=BAR_AREA,
        modulus=preset.modulus,
    )
    checked = cross_check(contract, bar_outcome, axial_forces=forces)
    print("   applied  {:.3f} kN".format(checked["applied_magnitude"] / 1000.0))
    print("   reacted  {:.3f} kN".format(checked["reaction_magnitude"] / 1000.0))
    print("   tolerance from the file  {:.3f} kN".format(checked["tolerance"] / 1000.0))
    print("   members compared         {}".format(checked["member_count"]))
    print("   worst member difference  {:.3f} kN".format(
        checked["max_member_difference"] / 1000.0))
    if checked["strict_agrees"]:
        print("   Agrees per member and in total: the setup is verified against")
        print("   TNA at member level, which this network's determinacy allows.")
    elif checked["reactions_agree"]:
        print("   Reactions balance the applied load exactly, so loads, supports,")
        print("   units and extraction are wired correctly. Member forces differ")
        print("   from TNA by up to {:.1f} kN: this network admits self-stress,".format(
            checked["max_member_difference"] / 1000.0))
        print("   so the two distributions are different members of the same")
        print("   equilibrium family. That is physics, not a fault.")
    else:
        print("   DOES NOT AGREE. The fault is in the model setup, not the")
        print("   vault. Everything below this line is unreliable.")

    banner("3. The shell under its design load")
    step("Building and solving the shell model")
    shell = build_shell_model(surface, preset, THICKNESS, supports)

    from compas_fea2.results import StressFieldResults

    outcome = run_static(shell, loads, name="design",
                         outputs=(StressFieldResults,))
    displacement = displacement_summary(outcome.step)
    reactions = reaction_summary(outcome.step)
    deflection = deflection_summary(displacement, SPAN)
    stresses = stress_summary(outcome.step, preset)
    print("   peak deflection   {:.2f} mm".format(displacement["peak_magnitude"] * 1000))
    if deflection["span_over_deflection"]:
        print("   span / deflection  1 / {:.0f}".format(
            deflection["span_over_deflection"]))
    print("   summed reactions   {:.1f} kN".format(reactions["magnitude"] / 1000.0))
    print("   peak compression   {:.3f} MPa   utilisation {:.1%}".format(
        stresses["peak_compression"] / 1e6, stresses["utilisation"]))

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
        # Crude integration: peak surface tension times thickness times span,
        # not a resolved tie force from the actual stress field. Provisional
        # sizing only, in the same discipline as demo 8's concrete sizing.
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
        "stress": stresses,
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
