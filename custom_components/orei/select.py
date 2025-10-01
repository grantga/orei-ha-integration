"""Select platform for OREI Matrix Switch audio output selection."""

from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.components.select import SelectEntity

from .const import DOMAIN, NUM_INPUTS, NUM_WINDOWS, QUAD_MODE_MAX, TRIPLE_MODE_MAX
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
            # Window selects (Window 1..NUM_WINDOWS)
            *[OreiWindowSelect(coordinator, i) for i in range(1, NUM_WINDOWS + 1)],
            OreiPipPositionSelect(coordinator),
            OreiPipSizeSelect(coordinator),
            OreiPbpModeSelect(coordinator),
            OreiSingleInputSelect(coordinator),
            OreiQuadModeSelect(coordinator),
            OreiTripleModeSelect(coordinator),
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


class OreiWindowSelect(OreiCoordinatorEntity, SelectEntity):
    """Representation of a single window input selector."""

    def __init__(self, coordinator: OreiDataUpdateCoordinator, window: int) -> None:
        """Initialize a window select for a specific window number."""
        super().__init__(coordinator, f"window_{window}")
        self._window = window
        self._attr_name = f"Window {window} Input"
        self._attr_icon = "mdi:television-classic"
        self._attr_options = [f"HDMI {i}" for i in range(1, NUM_INPUTS + 1)]

    @property
    def current_option(self) -> str | None:
        """Return the current HDMI input for this window as a string."""
        if not self.coordinator.data:
            return None
        try:
            val = self.coordinator.data.window_inputs[self._window - 1]
        except (IndexError, TypeError):
            return None
        if val is None:
            return None
        return f"HDMI {val}"

    async def async_select_option(self, option: str) -> None:
        """Select an HDMI input for this window."""
        try:
            idx = int(option.split()[-1])
        except (ValueError, IndexError):
            return
        await self.coordinator.client.set_window_input(self._window, idx)
        await self.coordinator.async_request_refresh()


class OreiPipPositionSelect(OreiCoordinatorEntity, SelectEntity):
    """Select entity for PIP position."""

    def __init__(self, coordinator: OreiDataUpdateCoordinator) -> None:
        """Initialize the PIP position select entity."""
        super().__init__(coordinator, "pip_position")
        self._attr_name = "PIP Position"
        self._attr_icon = "mdi:swap-horizontal"
        self._attr_options = [
            "Left Top",
            "Left Bottom",
            "Right Top",
            "Right Bottom",
        ]

    @property
    def current_option(self) -> str | None:
        """Return the current PIP position as a human-readable option."""
        if not self.coordinator.data:
            return None
        val = self.coordinator.data.pip_position
        if val is None:
            return None
        try:
            return self._attr_options[val - 1]
        except (IndexError, TypeError):
            return None

    async def async_select_option(self, option: str) -> None:
        """Select a new PIP position by option label."""
        try:
            idx = self._attr_options.index(option)
        except ValueError:
            return
        pos = idx + 1
        await self.coordinator.client.set_pip_position(pos)
        await self.coordinator.async_request_refresh()


class OreiPipSizeSelect(OreiCoordinatorEntity, SelectEntity):
    """Select entity for PIP size."""

    def __init__(self, coordinator: OreiDataUpdateCoordinator) -> None:
        """Initialize the PIP size select entity."""
        super().__init__(coordinator, "pip_size")
        self._attr_name = "PIP Size"
        self._attr_icon = "mdi:resize"
        self._attr_options = ["Small", "Middle", "Large"]

    @property
    def current_option(self) -> str | None:
        """Return the current PIP size as a human-readable option."""
        if not self.coordinator.data:
            return None
        val = self.coordinator.data.pip_size
        if val is None:
            return None
        try:
            return self._attr_options[val - 1]
        except (IndexError, TypeError):
            return None

    async def async_select_option(self, option: str) -> None:
        """Select a new PIP size by option label."""
        try:
            idx = self._attr_options.index(option)
        except ValueError:
            return
        size = idx + 1
        await self.coordinator.client.set_pip_size(size)
        await self.coordinator.async_request_refresh()


class OreiPbpModeSelect(OreiCoordinatorEntity, SelectEntity):
    """Select entity for PBP mode."""

    def __init__(self, coordinator: OreiDataUpdateCoordinator) -> None:
        """Initialize the PBP mode select entity."""
        super().__init__(coordinator, "pbp_mode")
        self._attr_name = "PBP Mode"
        self._attr_icon = "mdi:view-grid-variant"
        self._attr_options = ["PBP mode 1", "PBP mode 2"]

    @property
    def current_option(self) -> str | None:
        """Return the current PBP mode as a human-readable option."""
        if not self.coordinator.data:
            return None
        val = getattr(self.coordinator.data, "pbp_mode", None)
        if val is None:
            return None
        try:
            return self._attr_options[val - 1]
        except (IndexError, TypeError):
            return None

    async def async_select_option(self, option: str) -> None:
        """Change the PBP mode by selecting an option."""
        try:
            idx = self._attr_options.index(option)
        except ValueError:
            return
        mode = idx + 1
        await self.coordinator.client.set_pbp_mode(mode)
        await self.coordinator.async_request_refresh()


class OreiSingleInputSelect(OreiCoordinatorEntity, SelectEntity):
    """Select entity for single-screen input routing."""

    def __init__(self, coordinator: OreiDataUpdateCoordinator) -> None:
        """Initialize the single-screen input select entity."""
        super().__init__(coordinator, "single_input")
        self._attr_name = "Single Screen Input"
        self._attr_icon = "mdi:input-hdmi"
        self._attr_options = [f"HDMI {i}" for i in range(1, NUM_INPUTS + 1)]

    @property
    def current_option(self) -> str | None:
        """Return the currently routed input in single-screen mode."""
        if not self.coordinator.data:
            return None
        val = getattr(self.coordinator.data, "single_input", None)
        if val is None:
            return None
        try:
            return f"HDMI {val}"
        except (IndexError, TypeError):
            return None

    async def async_select_option(self, option: str) -> None:
        """Route the single-screen output to a selected HDMI input."""
        try:
            idx = int(option.split()[-1])
        except (ValueError, IndexError):
            return
        await self.coordinator.client.set_single_input(idx)
        await self.coordinator.async_request_refresh()


class OreiQuadModeSelect(OreiCoordinatorEntity, SelectEntity):
    """Select entity for quad display mode."""

    def __init__(self, coordinator: OreiDataUpdateCoordinator) -> None:
        """Initialize the quad mode select entity."""
        super().__init__(coordinator, "quad_mode")
        self._attr_name = "Quad Mode"
        self._attr_icon = "mdi:view-grid"
        # Build options from 1..QUAD_MODE_MAX
        self._attr_options = [f"Mode {i}" for i in range(1, QUAD_MODE_MAX + 1)]

    @property
    def current_option(self) -> str | None:
        """Return the current quad mode as a human-readable option."""
        if not self.coordinator.data:
            return None
        val = getattr(self.coordinator.data, "quad_mode", None)
        if val is None:
            return None
        try:
            return self._attr_options[val - 1]
        except (IndexError, TypeError):
            return None

    async def async_select_option(self, option: str) -> None:
        """Change the quad mode by selecting an option."""
        try:
            idx = self._attr_options.index(option)
        except ValueError:
            return
        mode = idx + 1
        await self.coordinator.client.set_quad_mode(mode)
        await self.coordinator.async_request_refresh()


class OreiTripleModeSelect(OreiCoordinatorEntity, SelectEntity):
    """Select entity for triple display mode."""

    def __init__(self, coordinator: OreiDataUpdateCoordinator) -> None:
        """Initialize the triple mode select entity."""
        super().__init__(coordinator, "triple_mode")
        self._attr_name = "Triple Mode"
        self._attr_icon = "mdi:view-dashboard-variant"
        # Build options from 1..TRIPLE_MODE_MAX
        self._attr_options = [f"Triple mode {i}" for i in range(1, TRIPLE_MODE_MAX + 1)]

    @property
    def current_option(self) -> str | None:
        """Return the current triple mode as a human-readable option."""
        if not self.coordinator.data:
            return None
        val = getattr(self.coordinator.data, "triple_mode", None)
        if val is None:
            return None
        try:
            return self._attr_options[val - 1]
        except (IndexError, TypeError):
            return None

    async def async_select_option(self, option: str) -> None:
        """Change the triple mode by selecting an option."""
        try:
            idx = self._attr_options.index(option)
        except ValueError:
            return
        mode = idx + 1
        await self.coordinator.client.set_triple_mode(mode)
        await self.coordinator.async_request_refresh()
