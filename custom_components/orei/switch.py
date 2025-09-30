"""Switch platform for OREI Matrix power control."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from homeassistant.components.switch import SwitchEntity

from .const import DOMAIN, LOGGER
from .entity import OreiEntity

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback

    from .coordinator import OreiDataUpdateCoordinator


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up OREI Matrix Switch power control."""
    coordinator = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([OreiPowerSwitch(coordinator)])


class OreiPowerSwitch(OreiEntity, SwitchEntity):
    """Representation of OREI Matrix Switch power control."""

    _attr_name = "Power"
    _attr_icon = "mdi:power"
    _attr_has_entity_name = True

    def __init__(self, coordinator: OreiDataUpdateCoordinator) -> None:
        """Initialize the power switch."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.client.serial_port}_power"

    @property
    def is_on(self) -> bool | None:
        """Return true if the switch is on."""
        if not self.coordinator.data:
            return None
        return self.coordinator.data.power

    async def async_turn_on(self, **_: Any) -> None:
        """Turn the matrix switch on."""
        LOGGER.debug("Turning matrix switch on")
        await self.coordinator.client.power_on()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **_: Any) -> None:
        """Turn the matrix switch off."""
        LOGGER.debug("Turning matrix switch off")
        await self.coordinator.client.power_off()
        await self.coordinator.async_request_refresh()
