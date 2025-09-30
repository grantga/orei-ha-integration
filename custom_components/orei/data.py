"""Custom types for OREI Matrix Switch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from .const import NUM_INPUTS

# Input options are fixed based on hardware
VALID_INPUTS: Final = tuple(f"Input {i}" for i in range(1, NUM_INPUTS + 1))


@dataclass
class SwitchState:
    """Switch state data."""

    power: bool
    input_number: int
