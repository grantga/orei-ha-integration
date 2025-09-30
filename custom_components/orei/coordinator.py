"""DataUpdateCoordinator for OREI Matrix Switch."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
    UpdateFailed,
)

from .api import OreiMatrixClient, OreiMatrixError
from .const import LOGGER, NAME

if TYPE_CHECKING:
    from datetime import timedelta

    from homeassistant.core import HomeAssistant


@dataclass
class OreiMatrixData:
    """Class to store matrix switch state data."""

    # Whether the matrix switch is powered on
    power: bool
    # Currently selected audio source (1-4)
    current_audio_src: int
    # Future: EDID and lock state support


class OreiDataUpdateCoordinator(DataUpdateCoordinator[OreiMatrixData]):
    """Class to manage fetching OREI Matrix Switch data."""

    def __init__(
        self,
        hass: HomeAssistant,
        client: OreiMatrixClient,
        name: str,
        update_interval: timedelta,
    ) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass=hass,
            logger=LOGGER,
            name=name,
            update_interval=update_interval,
        )
        self.client = client
        self._attr_has_entity_name = True

    async def _async_update_data(self) -> OreiMatrixData:
        """Fetch data from the matrix switch."""
        try:
            # Get current state
            power = await self.client.get_power_state()
            current_audio_src = await self.client.get_audio_output()

            return OreiMatrixData(
                power=power,
                current_audio_src=current_audio_src,
            )

        except OreiMatrixError as error:
            error_msg = f"Error communicating with device: {error}"
            LOGGER.error(error_msg)
            raise UpdateFailed(str(error)) from error


class OreiCoordinatorEntity(CoordinatorEntity[OreiDataUpdateCoordinator]):
    """Base entity class for OREI Matrix Switch."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: OreiDataUpdateCoordinator,
        entity_type: str,
    ) -> None:
        """Initialize OREI entities."""
        super().__init__(coordinator)
        # Use serial port as part of unique ID since it's unique to the device
        self._attr_unique_id = f"{coordinator.client.serial_port}_{entity_type}"
        self._attr_device_info = {
            "identifiers": {("orei", coordinator.client.serial_port)},
            "name": NAME,
            "manufacturer": "OREI",
            "model": "UHD-401MV",
            "sw_version": "UHD-401MV V1.0",  # From manual page 2
        }
