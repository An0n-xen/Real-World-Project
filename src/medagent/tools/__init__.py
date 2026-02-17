"""Tool management for MedAgent-Pro."""

from medagent.tools.registry import ToolRegistry
from medagent.tools.medical_tools import (
    segment_optic_cup,
    segment_optic_disc,
)

__all__ = [
    "ToolRegistry",
    "segment_optic_cup",
    "segment_optic_disc",
]
