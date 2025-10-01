"""Select platform for OREI Matrix Switch audio output selection."""

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
    """Set up OREI Matrix Switch audio output selection."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [
            OreiAudioOutputSelect(coordinator),
            OreiMultiviewSelect(coordinator),
        ]
    )


class OreiAudioOutputSelect(OreiCoordinatorEntity, SelectEntity):
    """Representation of the OREI Matrix Switch audio output selection."""

    def __init__(self, coordinator: OreiDataUpdateCoordinator) -> None:
        """Initialize the audio output selector."""
        super().__init__(coordinator, "audio_output")
        self._attr_name = "Audio Output Source"
        self._attr_icon = "mdi:audio-input-hdmi"
        self._attr_options = [f"Input {i}" for i in range(1, NUM_INPUTS + 1)]

    @property
    def current_option(self) -> str | None:
        """Return the current selected audio src."""
        if not self.coordinator.data:
            return None
        src = self.coordinator.data.current_audio_src
        if src is None:
            return None
        return f"Input {src}"

    async def async_select_option(self, option: str) -> None:
        """Change the selected audio ouput."""
        input_num = int(option.split()[-1])  # Extract number from "Input X"
        await self.coordinator.client.set_audio_output(input_num)
        await self.coordinator.async_request_refresh()


class OreiMultiviewSelect(OreiCoordinatorEntity, SelectEntity):
    """Representation of the OREI Matrix Switch multiview selection."""

    def __init__(self, coordinator: OreiDataUpdateCoordinator) -> None:
        """Initialize the multiview selector."""
        super().__init__(coordinator, "multiview")
        self._attr_name = "Multiview Mode"
        self._attr_icon = "mdi:view-grid"
        # Options correspond to modes 1..5
        self._attr_options = [
            "Single",
            "PIP",
            "PBP",
            "Triple",
            "Quad",
        ]

    @property
    def current_option(self) -> str | None:
        """Return the current multiview mode as a string."""
        if not self.coordinator.data:
            return None
        mode = self.coordinator.data.current_multiview
        if mode is None:
            return None
        # Modes are 1-based; options list is 0-based
        try:
            return self._attr_options[mode - 1]
        except IndexError:
            return None

    async def async_select_option(self, option: str) -> None:
        """Change the multiview mode."""
        try:
            idx = self._attr_options.index(option)
        except ValueError:
            return
        mode = idx + 1
        await self.coordinator.client.set_multiview(mode)
        await self.coordinator.async_request_refresh()
