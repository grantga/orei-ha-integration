"""OREI UHD-401MV Matrix Switch integration."""

from __future__ import annotations

from datetime import timedelta
from typing import TYPE_CHECKING

import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.helpers import config_validation as cv

from .api import OreiMatrixClient
from .const import (
    CONF_SERIAL_PORT,
    DOMAIN,
    NAME,
    NUM_INPUTS,
    UPDATE_INTERVAL,
)
from .coordinator import OreiDataUpdateCoordinator

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant, ServiceCall

PLATFORMS = [
    Platform.SWITCH,  # For power control
    Platform.SELECT,  # For audio output and multiview selects
]

# Service names
SERVICE_SET_AUDIO = "set_audio_output"

# Multiview service
SERVICE_SET_MULTIVIEW = "set_multiview"

# Service schema: source 0..NUM_INPUTS; optional output and entry_id
SERVICE_SET_AUDIO_SCHEMA = vol.Schema(
    {
        vol.Required("source"): vol.All(
            int,
            vol.Range(min=0, max=NUM_INPUTS),
        ),
        vol.Optional("entry_id"): cv.string,
    }
)


SERVICE_SET_MULTIVIEW_SCHEMA = vol.Schema(
    {
        vol.Required("mode"): vol.All(int, vol.Range(min=1, max=5)),
        vol.Optional("entry_id"): cv.string,
    }
)


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
    # Register service to set audio output. Register once when the first
    # entry is created.
    if not hass.services.async_services().get(DOMAIN, {}).get(SERVICE_SET_AUDIO):

        async def _async_set_audio_service(call: ServiceCall) -> None:
            data = call.data
            source = int(data["source"])
            output = int(data.get("output", 1))
            entry_id = data.get("entry_id")

            # Choose coordinator
            if entry_id:
                coord = hass.data[DOMAIN].get(entry_id)
                if not coord:
                    msg = f"Config entry {entry_id} not found"
                    raise RuntimeError(msg)
            else:
                # If only one entry, use it; otherwise require entry_id
                entries = list(hass.data[DOMAIN].values())
                if len(entries) == 1:
                    coord = entries[0]
                else:
                    msg = "More than one OREI config entry present; specify entry_id"
                    raise RuntimeError(msg)

            await coord.client.set_audio_output(source, output)
            await coord.async_request_refresh()

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_AUDIO,
            _async_set_audio_service,
            schema=SERVICE_SET_AUDIO_SCHEMA,
        )

    # Register multiview service if not already present
    if not hass.services.async_services().get(DOMAIN, {}).get(SERVICE_SET_MULTIVIEW):

        async def _async_set_multiview_service(call: ServiceCall) -> None:
            data = call.data
            mode = int(data["mode"])
            entry_id = data.get("entry_id")

            # Choose coordinator
            if entry_id:
                coord = hass.data[DOMAIN].get(entry_id)
                if not coord:
                    msg = f"Config entry {entry_id} not found"
                    raise RuntimeError(msg)
            else:
                entries = list(hass.data[DOMAIN].values())
                if len(entries) == 1:
                    coord = entries[0]
                else:
                    msg = "More than one OREI config entry present; specify entry_id"
                    raise RuntimeError(msg)

            await coord.client.set_multiview(mode)
            await coord.async_request_refresh()

        hass.services.async_register(
            DOMAIN,
            SERVICE_SET_MULTIVIEW,
            _async_set_multiview_service,
            schema=SERVICE_SET_MULTIVIEW_SCHEMA,
        )

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
