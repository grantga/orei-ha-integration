"""OREI Matrix Switch entity base class."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo

from .const import DOMAIN, NAME
from .coordinator import OreiCoordinatorEntity, OreiDataUpdateCoordinator


class OreiEntity(OreiCoordinatorEntity):
    """Base entity class for OREI Matrix Switch."""

    def __init__(self, coordinator: OreiDataUpdateCoordinator) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, "base")
        self._attr_device_info = DeviceInfo(
            entry_type=DeviceEntryType.SERVICE,
            identifiers={(DOMAIN, coordinator.client.serial_port)},
            manufacturer="OREI",
            model="UHD-401MV",
            name=NAME,
            sw_version="UHD-401MV V1.0",  # From manual page 2
        )
