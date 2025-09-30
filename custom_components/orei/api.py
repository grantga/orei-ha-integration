"""
OREI UHD-401MV Serial API Client.

This module provides a small async client for communicating with the
OREI UHD-401MV matrix switch over a serial connection. It implements the
commands required by the integration and raises domain-specific
exceptions on failure so the rest of the integration can react.
"""

from __future__ import annotations

import asyncio
from typing import Any

import serial
import serial_asyncio

from .const import (
    BAUDRATE,
    BYTESIZE,
    CMD_POWER_OFF,
    CMD_POWER_ON,
    CMD_QUERY_INPUT,
    CMD_QUERY_POWER,
    CMD_SWITCH_INPUT,
    LOGGER,
    NUM_INPUTS,
    NUM_OUTPUTS,
    PARITY,
    RESPONSE_POWER_OFF,
    RESPONSE_POWER_ON,
    STOPBITS,
    TIMEOUT,
)


class OreiMatrixError(Exception):
    """Base exception for OREI Matrix related errors."""


class OreiSerialConnectionError(OreiMatrixError):
    """Raised when a serial connection cannot be established or used."""


class OreiCommunicationError(OreiMatrixError):
    """Raised when communication (read/write) fails."""


class OreiMatrixClient:
    """
    Async client for the UHD-401MV serial protocol.

    The device uses short ASCII commands terminated by CRLF. This client
    keeps a single open serial connection and a lock so callers can safely
    call methods concurrently.
    """

    def __init__(self, serial_port: str, baudrate: int | None = None) -> None:
        """
        Initialize the client.

        Args:
            serial_port: Path to the serial device (e.g. /dev/ttyUSB0).
            baudrate: Optional baudrate to use for the serial connection. If
                not provided the module-level default `BAUDRATE` is used.

        """
        self.serial_port = serial_port
        # serial_asyncio StreamReader/Writer have runtime types not easily
        # recognised by the linter in this environment; use Any for typing.
        self._reader: Any | None = None
        self._writer: Any | None = None
        self._lock = asyncio.Lock()
        # Allow overriding the default baudrate from constants via init
        self.baudrate = int(baudrate) if baudrate is not None else BAUDRATE

    async def connect(self) -> None:
        """Open the serial connection if not already open."""
        if self._writer is not None and self._reader is not None:
            return

        try:
            self._reader, self._writer = await serial_asyncio.open_serial_connection(
                url=self.serial_port,
                baudrate=self.baudrate,
                bytesize=BYTESIZE,
                parity=PARITY,
                stopbits=STOPBITS,
            )
        except serial.SerialException as exc:  # pragma: no cover - requires hardware
            LOGGER.error("Failed to open serial port %s: %s", self.serial_port, exc)
            raise OreiSerialConnectionError(str(exc)) from exc

    async def disconnect(self) -> None:
        """Close the serial connection if open."""
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            finally:
                self._writer = None
                self._reader = None

    async def _write_command(self, command: str) -> None:
        """Write a command to the device, do not wait for a response."""
        if not command:
            msg = "Empty command"
            raise OreiCommunicationError(msg)

        await self.connect()

        if not self._writer:
            msg = "No serial writer available"
            raise OreiSerialConnectionError(msg)

        async with self._lock:
            try:
                self._writer.write(command.encode())
                await self._writer.drain()
            except serial.SerialException as exc:
                LOGGER.exception("Serial write failed: %s", exc)
                await self.disconnect()
                raise OreiCommunicationError(str(exc)) from exc

    async def _read_response(self) -> str:
        """Read a single-line response from the device."""
        if not self._reader:
            msg = "No serial reader available"
            raise OreiSerialConnectionError(msg)

        try:
            data = await asyncio.wait_for(self._reader.readline(), timeout=TIMEOUT)
            return data.decode().strip()
        except (TimeoutError, serial.SerialException) as exc:
            LOGGER.exception("Serial read failed: %s", exc)
            await self.disconnect()
            raise OreiCommunicationError(str(exc)) from exc

    async def test_connection(self) -> None:
        """Simple test used by the config flow to verify device is reachable."""
        try:
            await self.get_power_state()
        except OreiSerialConnectionError:
            raise
        except OreiMatrixError as exc:
            # Wrap other errors as serial connection failure for config flow UX
            raise OreiSerialConnectionError(str(exc)) from exc

    async def set_input(self, input_num: int, output_num: int = 1) -> None:
        r"""
        Switch an input to an output.

        Validates ranges and sends the sw i{input}v{output}\r\n command.
        """
        if not 1 <= input_num <= NUM_INPUTS:
            msg = f"Input must be between 1 and {NUM_INPUTS}"
            raise OreiMatrixError(msg)
        if not 1 <= output_num <= NUM_OUTPUTS:
            msg = f"Output must be between 1 and {NUM_OUTPUTS}"
            raise OreiMatrixError(msg)

        cmd = CMD_SWITCH_INPUT.format(input=input_num, output=output_num)
        await self._write_command(cmd)

    async def get_input(self, output_num: int = 1) -> int:
        """Query the currently selected input for an output and return it."""
        if not 1 <= output_num <= NUM_OUTPUTS:
            msg = f"Output must be between 1 and {NUM_OUTPUTS}"
            raise OreiMatrixError(msg)

        cmd = CMD_QUERY_INPUT.format(output=output_num)
        await self._write_command(cmd)
        response = await self._read_response()

        # Expecting responses like: "av1 from i1"
        try:
            return int(response.split("from i")[1])
        except (IndexError, ValueError) as exc:
            msg = f"Invalid response format: {response}"
            raise OreiMatrixError(msg) from exc

    async def power_on(self) -> None:
        """Turn the device power on."""
        await self._write_command(CMD_POWER_ON)

    async def power_off(self) -> None:
        """Turn the device power off."""
        await self._write_command(CMD_POWER_OFF)

    async def get_power_state(self) -> bool:
        """Query the device power state and return True if on, False if off."""
        await self._write_command(CMD_QUERY_POWER)
        response = await self._read_response()
        if response == RESPONSE_POWER_ON:
            return True
        if response == RESPONSE_POWER_OFF:
            return False
        msg = f"Invalid power state response: {response}"
        raise OreiMatrixError(msg)
