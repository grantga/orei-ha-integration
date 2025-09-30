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
    CMD_QUERY_AUDIO_OUTPUT,
    CMD_QUERY_POWER,
    CMD_SET_AUDIO_OUTPUT,
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
                data = command.encode()
                LOGGER.debug("Serial write to %s: %s", self.serial_port, command)
                self._writer.write(data)
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
            # Prefer readline which waits for a newline-terminated response.
            data = await asyncio.wait_for(self._reader.readline(), timeout=TIMEOUT)
        except serial.SerialException as exc:
            LOGGER.exception("Serial read failed: %s", exc)
            await self.disconnect()
            raise OreiCommunicationError(str(exc)) from exc

        if not data:
            msg = "No data received from serial device"
            LOGGER.debug(msg)
            await self.disconnect()
            raise OreiCommunicationError(msg)

        LOGGER.debug("Serial raw response from %s: %s", self.serial_port, data.hex())
        return data.decode(errors="replace").strip()

    async def test_connection(self) -> None:
        """Simple test used by the config flow to verify device is reachable."""
        try:
            await self.get_power_state()
        except OreiSerialConnectionError:
            raise
        except OreiMatrixError as exc:
            # Wrap other errors as serial connection failure for config flow UX
            raise OreiSerialConnectionError(str(exc)) from exc

    async def set_audio_output(self, source: int, output_num: int = 1) -> None:
        r"""
        Set the audio output source for an output.

        source: 0..4 where 0 means "follow window selected source",
        and 1..4 correspond to HDMI 1..4.
        """
        if not 0 <= source <= NUM_INPUTS:
            msg = f"Audio source must be between 0 and {NUM_INPUTS}"
            raise OreiMatrixError(msg)
        if not 1 <= output_num <= NUM_OUTPUTS:
            msg = f"Output must be between 1 and {NUM_OUTPUTS}"
            raise OreiMatrixError(msg)

        cmd = CMD_SET_AUDIO_OUTPUT.format(source=source)
        await self._write_command(cmd)

    async def get_audio_output(self) -> int:
        """Return the current audio source (0=follow, 1..N=HDMI)."""
        # Send query command and read single-line response
        await self._write_command(CMD_QUERY_AUDIO_OUTPUT)
        response = await self._read_response()

        # Normalize to lower-case for parsing
        resp = response.lower().strip()

        # Try to find a digit 1..NUM_INPUTS in the response
        for token in resp.split():
            # Remove any non-digit prefix/suffix
            digits = "".join(ch for ch in token if ch.isdigit())
            if not digits:
                continue
            try:
                val = int(digits)
            except ValueError:
                continue
            if 1 <= val <= NUM_INPUTS:
                return val

        # If parsing fails, raise an error
        msg = f"Invalid audio output response: {response}"
        raise OreiMatrixError(msg)

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
