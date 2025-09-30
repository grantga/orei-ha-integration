"""OREI UHD-401MV Matrix Switch integration."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

from homeassistant.const import Platform

from .api import OreiMatrixClient
from .const import (
    CONF_SERIAL_PORT,
    DOMAIN,
    NAME,
    UPDATE_INTERVAL,
)
from .coordinator import OreiDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant

PLATFORMS = [
    Platform.SWITCH,  # For power control
    Platform.SELECT,  # For input selection
]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up OREI Matrix Switch from a config entry."""
    client = OreiMatrixClient(
        serial_port=entry.data[CONF_SERIAL_PORT],
    )

    coordinator = OreiDataUpdateCoordinator(
        hass=hass,
        client=client,
        name=NAME,
        update_interval=timedelta(seconds=UPDATE_INTERVAL),
    )

    # Initial data fetch
    await coordinator.async_config_entry_first_refresh()

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = coordinator

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        await coordinator.client.disconnect()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload config entry."""
    await hass.config_entries.async_reload(entry.entry_id)
