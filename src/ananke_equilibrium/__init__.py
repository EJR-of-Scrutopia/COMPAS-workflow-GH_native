"""Ananke Equilibrium's neutral workflow and Grasshopper adapter package.

The package root intentionally avoids importing Rhino or optional COMPAS
backends. This keeps contracts and saved workflow data readable in plain Python
and in dedicated downstream FEA or IFC environments.
"""

from .contracts import ContractError
from .contracts import Diagnostic
from .contracts import DiagramBundle
from .contracts import DiagramPrimitive
from .contracts import DiagramStyle
from .contracts import FDConfig
from .contracts import HeightControl
from .contracts import LoadCase
from .contracts import PreparedTNA
from .contracts import SolvedCase
from .contracts import SupportSet
from .contracts import TNAConfig
from .contracts import TNAPrepareConfig
from .contracts import TopologyBundle

__version__ = "0.1.0.dev0"

__all__ = [
    "ContractError",
    "Diagnostic",
    "DiagramBundle",
    "DiagramPrimitive",
    "DiagramStyle",
    "FDConfig",
    "HeightControl",
    "LoadCase",
    "PreparedTNA",
    "SolvedCase",
    "SupportSet",
    "TNAConfig",
    "TNAPrepareConfig",
    "TopologyBundle",
    "__version__",
]
