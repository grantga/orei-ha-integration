"""Adds config flow for OREI UHD-401MV."""

from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import selector

from .api import (
    OreiMatrixClient,
    OreiMatrixError,
    OreiSerialConnectionError,
)
from .const import (
    BAUDRATE,
    CONF_BAUDRATE,
    CONF_SERIAL_PORT,
    DEFAULT_SERIAL_PORT,
    DOMAIN,
    LOGGER,
    NAME,
)


class OreiFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for OREI UHD-401MV."""

    VERSION = 1

    async def async_step_user(
        self,
        user_input: dict | None = None,
    ) -> config_entries.ConfigFlowResult:
        """Handle a flow initialized by the user."""
        _errors = {}

        if user_input is not None:
            try:
                client = OreiMatrixClient(
                    serial_port=user_input[CONF_SERIAL_PORT],
                    baudrate=int(user_input.get(CONF_BAUDRATE, BAUDRATE)),
                )
                # Test the connection
                await client.test_connection()

                # Use the serial port as unique ID since we can only have one
                # device per serial port
                await self.async_set_unique_id(user_input[CONF_SERIAL_PORT])
                self._abort_if_unique_id_configured()

                return self.async_create_entry(
                    title=NAME,
                    data=user_input,
                )

            except OreiSerialConnectionError as exception:
                LOGGER.error(exception)
                _errors["base"] = "cannot_connect"
            except OreiMatrixError as exception:
                LOGGER.exception(exception)
                _errors["base"] = "unknown"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_SERIAL_PORT,
                        default=(user_input or {}).get(
                            CONF_SERIAL_PORT, DEFAULT_SERIAL_PORT
                        ),
                    ): selector.TextSelector(
                        selector.TextSelectorConfig(
                            type=selector.TextSelectorType.TEXT,
                        ),
                    ),
                    vol.Required(
                        CONF_BAUDRATE,
                        default=(user_input or {}).get(CONF_BAUDRATE, BAUDRATE),
                    ): selector.NumberSelector(
                        selector.NumberSelectorConfig(
                            mode=selector.NumberSelectorMode.BOX,
                            min=9600,
                            max=115200,
                            step=1,
                        ),
                    ),
                },
            ),
            errors=_errors,
        )
