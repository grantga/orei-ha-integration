"""Select platform for OREI Matrix Switch input selection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity

from .const import DOMAIN, NUM_INPUTS
from .coordinator import OreiCoordinatorEntity, OreiDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OREI Matrix Switch input selection."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OreiInputSelect(coordinator)])


class OreiInputSelect(OreiCoordinatorEntity, SelectEntity):
    """Representation of the OREI Matrix Switch input selection."""

    def __init__(self, coordinator: OreiDataUpdateCoordinator) -> None:
        """Initialize the input selector."""
        super().__init__(coordinator, "input")
        self._attr_name = "Input Source"
        self._attr_icon = "mdi:video-input-hdmi"
        self._attr_options = [f"Input {i}" for i in range(1, NUM_INPUTS + 1)]

    @property
    def current_option(self) -> str | None:
        """Return the current selected input."""
        if not self.coordinator.data:
            return None
        return f"Input {self.coordinator.data.current_input}"

    async def async_select_option(self, option: str) -> None:
        """Change the selected input."""
        input_num = int(option.split()[-1])  # Extract number from "Input X"
        await self.coordinator.client.set_input(input_num)
        await self.coordinator.async_request_refresh()
