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
        "on the five per cent characteristic axial tensile strength fctk,0.05 "
        "of 2.0 MPa, divided by the same 1.5, giving 1.07 MPa. The five per "
        "cent value is used rather than the mean because unreinforced concrete "
        "has no reinforcement to redistribute once it cracks. In practice "
        "unreinforced concrete in tension should be treated as having no "
        "reliable capacity, and the value is quoted only so that tension onset "
        "has something to report against."
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
