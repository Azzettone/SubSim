"""
Block Assembler — sistema modulare per design di altoparlanti.

Ogni blocco (HornBlock, ChamberBlock, PortBlock, DriverBlock) rappresenta
un elemento fisico del cabinet con parametri acustici in input e geometria
costruttiva (lista pannelli) in output.

I blocchi si compongono in un Assembly tramite ConnectionPort.
"""

from .base_block import (
    Block,
    Panel,
    ConnectionPort,
    ValidationWarning,
    Severity,
    DEFAULT_PANEL_THICKNESS,
    DEFAULT_PANEL_MATERIAL,
)
from .horn_block import (
    HornBlock,
    HornSectionGeometry,
    ThroatAdapter,
)
from .chamber_block import ChamberBlock
from .port_block import (
    PortBlock,
    END_CORRECTION_FLANGED_BOTH,
    END_CORRECTION_FLANGED_ONE,
    END_CORRECTION_FREE_BOTH,
)
from .driver_block import DriverBlock
from .assembly import Assembly, Connection

__all__ = [
    "Block",
    "Panel",
    "ConnectionPort",
    "ValidationWarning",
    "Severity",
    "DEFAULT_PANEL_THICKNESS",
    "DEFAULT_PANEL_MATERIAL",
    "HornBlock",
    "HornSectionGeometry",
    "ThroatAdapter",
    "ChamberBlock",
    "PortBlock",
    "END_CORRECTION_FLANGED_BOTH",
    "END_CORRECTION_FLANGED_ONE",
    "END_CORRECTION_FREE_BOTH",
    "DriverBlock",
    "Assembly",
    "Connection",
]
