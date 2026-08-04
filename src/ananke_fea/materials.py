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
from typing import Dict


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
    compressive_strength=13.6e6,
    tensile_strength=1.35e6,
    source="EN 1992-1-1 Table 3.1 for C30/37",
    assumptions=(
        "Design compressive strength takes the partial factor 1.5 and the "
        "long-term factor 0.85 on a characteristic 24 MPa. Tensile strength "
        "is the mean axial value reduced by the same partial factor, and is "
        "quoted only so that tension onset has something to report against. "
        "Unreinforced concrete in tension should be treated as having no "
        "reliable capacity."
    ),
)

TIMBER_GL24H = MaterialPreset(
    name="GL24h glued laminated timber",
    modulus=11.5e9,
    poisson=0.3,
    density=385.0,
    compressive_strength=14.8e6,
    tensile_strength=10.6e6,
    source="EN 14080 Table 5 for GL24h",
    assumptions=(
        "Timber is orthotropic in reality and this preset models it as "
        "isotropic, which is conservative in some directions and "
        "unconservative in others. The modulus is the mean parallel to the "
        "grain, so any result governed by cross-grain behaviour is wrong. "
        "Strengths take a partial factor of 1.25 and a modification factor "
        "of 0.8 for service class 2 and medium-term loading."
    ),
)

PRESETS: Dict[str, MaterialPreset] = {
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
