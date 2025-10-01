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
    CMD_QUERY_MULTIVIEW,
    CMD_QUERY_POWER,
    CMD_SET_AUDIO_OUTPUT,
    CMD_SET_MULTIVIEW,
    LOGGER,
    MULTIVIEW_MAX,
    MULTIVIEW_MIN,
    NUM_INPUTS,
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
        # Prevent concurrent connect() calls from racing
        self._connect_lock = asyncio.Lock()
        # Allow overriding the default baudrate from constants via init
        self.baudrate = int(baudrate) if baudrate is not None else BAUDRATE

    def _safe_hex(self, data: bytes | None) -> str:
        """
        Return hex representation of bytes or a placeholder on failure.

        Kept as a small helper to avoid duplicating try/except logic in the
        hot-path _write_and_read method so that function stays under the
        project's static complexity limits.
        """
        try:
            return data.hex()  # type: ignore[arg-type]
        except (AttributeError, TypeError):
            return "<unhexable>"

    async def _send_command_and_collect_lines(self, command: str) -> list[bytes]:
        """
        Write command and collect response lines while holding the lock.

        Kept as a separate function to keep _write_and_read small and easier to
        reason about for the project's static complexity limits.

        """
        # Ensure writer/reader are available and bind to local names to help
        # static type checkers understand attributes exist during use.
        if not self._writer or not self._reader:
            msg = "No serial connection available"
            raise OreiSerialConnectionError(msg)

        writer = self._writer
        reader = self._reader

        async with self._lock:
            try:
                LOGGER.debug(
                    "_send_command_and_collect_lines: writing to %s: %s",
                    self.serial_port,
                    command,
                )
                writer.write(command.encode())
                await writer.drain()
                LOGGER.debug("_send_command_and_collect_lines: write drained")

                first = await asyncio.wait_for(reader.readline(), timeout=TIMEOUT)

                lines: list[bytes] = []
                if first:
                    lines.append(first)
                    LOGGER.debug(
                        "_send_command_and_collect_lines: first raw: %s",
                        self._safe_hex(first),
                    )

                while True:
                    try:
                        chunk = await asyncio.wait_for(reader.readline(), timeout=0.05)
                    except TimeoutError:
                        LOGGER.debug(
                            "_send_command_and_collect_lines: drain timeout, stopping"
                        )
                        break
                    if not chunk:
                        LOGGER.debug(
                            "_send_command_and_collect_lines: empty chunk,"
                            " stop draining"
                        )
                        break
                    lines.append(chunk)
                    LOGGER.debug(
                        "_send_command_and_collect_lines: drained extra chunk: %s",
                        self._safe_hex(chunk),
                    )

            except serial.SerialException as exc:
                LOGGER.exception("Serial write/read failed: %s", exc)
                await self.disconnect()
                raise OreiCommunicationError(str(exc)) from exc
            except TimeoutError as exc:
                LOGGER.debug("Serial read timeout waiting for response")
                await self.disconnect()
                msg = "Read timeout"
                raise OreiCommunicationError(msg) from exc

        return lines

    def _last_non_empty_text(self, lines: list[bytes]) -> str:
        """Return the last non-empty decoded line or raise OreiCommunicationError."""
        for chunk in reversed(lines):
            text = chunk.decode(errors="replace").strip()
            if text:
                LOGGER.debug("_last_non_empty_text: decoded response: %s", text)
                return text
        msg = "No non-empty response received from serial device"
        raise OreiCommunicationError(msg)

    async def connect(self) -> None:
        """Open the serial connection if not already open."""
        LOGGER.debug("connect(): called for %s", self.serial_port)
        # Fast-path: already connected
        if self._writer is not None and self._reader is not None:
            return

        # Ensure only one coroutine can attempt to open the connection at a time
        async with self._connect_lock:
            if self._writer is not None and self._reader is not None:
                return

            try:
                LOGGER.debug(
                    "connect(): opening serial connection %s @ %s",
                    self.serial_port,
                    self.baudrate,
                )
                (
                    self._reader,
                    self._writer,
                ) = await serial_asyncio.open_serial_connection(
                    url=self.serial_port,
                    baudrate=self.baudrate,
                    bytesize=BYTESIZE,
                    parity=PARITY,
                    stopbits=STOPBITS,
                )
                await asyncio.sleep(1)  # Wait for the device to reset and initialize
                LOGGER.debug(
                    "connect(): initial wait complete for %s", self.serial_port
                )
                LOGGER.debug(
                    "connect(): reader=%s writer=%s",
                    type(self._reader),
                    type(self._writer),
                )
            except (
                serial.SerialException
            ) as exc:  # pragma: no cover - requires hardware
                LOGGER.error("Failed to open serial port %s: %s", self.serial_port, exc)
                raise OreiSerialConnectionError(str(exc)) from exc

    async def disconnect(self) -> None:
        """Close the serial connection if open."""
        LOGGER.debug("disconnect(): called for %s", self.serial_port)
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            finally:
                self._writer = None
                self._reader = None
        LOGGER.debug("disconnect(): finished for %s", self.serial_port)

    async def _write_and_read(self, command: str) -> str:
        """
        Write a command and read all response lines while holding a lock.

        Send the command, read the first line using the configured TIMEOUT
        (device may take time to respond), then drain any immediately
        available additional lines using a short drain timeout loop. The
        last non-empty line received is returned.
        """
        if not command:
            msg = "Empty command"
            raise OreiCommunicationError(msg)

        await self.connect()

        if not self._writer or not self._reader:
            msg = "No serial connection available"
            raise OreiSerialConnectionError(msg)

        lines = await self._send_command_and_collect_lines(command)

        if not lines:
            msg = "No data received from serial device"
            LOGGER.debug(msg)
            await self.disconnect()
            raise OreiCommunicationError(msg)

        raw_hex = self._safe_hex(b" ".join(lines))
        LOGGER.debug(
            "_write_and_read: serial raw response(s) from %s: %s",
            self.serial_port,
            raw_hex,
        )

        try:
            return self._last_non_empty_text(lines)
        except OreiCommunicationError:
            await self.disconnect()
            raise

    async def test_connection(self) -> None:
        """Simple test used by the config flow to verify device is reachable."""
        LOGGER.debug("test_connection(): verifying device %s", self.serial_port)
        try:
            await self.get_power_state()
            LOGGER.debug("test_connection(): success for %s", self.serial_port)
        except OreiSerialConnectionError:
            raise
        except OreiMatrixError as exc:
            # Wrap other errors as serial connection failure for config flow UX
            LOGGER.debug("test_connection(): failed for %s: %s", self.serial_port, exc)
            raise OreiSerialConnectionError(str(exc)) from exc

    async def set_audio_output(self, source: int) -> None:
        r"""
        Set the audio output source for an output.

        source: 0..4 where 0 means "follow window selected source",
        and 1..4 correspond to HDMI 1..4.
        """
        LOGGER.debug("set_audio_output(): requested source=%s", source)
        if not 0 <= source <= NUM_INPUTS:
            msg = f"Audio source must be between 0 and {NUM_INPUTS}"
            LOGGER.debug("set_audio_output(): invalid source %s", source)
            raise OreiMatrixError(msg)

        cmd = CMD_SET_AUDIO_OUTPUT.format(source=source)
        await self._write_and_read(cmd)
        LOGGER.debug("set_audio_output(): set source=%s complete", source)

    async def set_multiview(self, mode: int) -> None:
        """
        Set the multi-viewer display mode.

        mode: MULTIVIEW_MIN..MULTIVIEW_MAX where
        1 = single screen, 2 = PIP, 3 = PBP, 4 = triple, 5 = quad
        """
        LOGGER.debug("set_multiview(): requested mode=%s", mode)
        if not MULTIVIEW_MIN <= mode <= MULTIVIEW_MAX:
            msg = f"Multiview mode must be between {MULTIVIEW_MIN} and {MULTIVIEW_MAX}"
            LOGGER.debug("set_multiview(): invalid mode %s", mode)
            raise OreiMatrixError(msg)

        cmd = CMD_SET_MULTIVIEW.format(mode=mode)
        await self._write_and_read(cmd)
        LOGGER.debug("set_multiview(): set mode=%s complete", mode)

    async def get_multiview(self) -> int:
        """
        Return the current multi-viewer display mode.

        Returns an integer between MULTIVIEW_MIN and MULTIVIEW_MAX.
        """
        LOGGER.debug("get_multiview(): querying device")
        response = await self._write_and_read(CMD_QUERY_MULTIVIEW)
        resp = response.lower().strip()

        # Look for a digit in the response text
        for token in resp.split():
            digits = "".join(ch for ch in token if ch.isdigit())
            if not digits:
                continue
            try:
                val = int(digits)
            except ValueError:
                continue
            if MULTIVIEW_MIN <= val <= MULTIVIEW_MAX:
                LOGGER.debug("get_multiview(): parsed value=%s", val)
                return val

        msg = f"Invalid multiview response: {response}"
        LOGGER.debug("get_multiview(): parse failed: %s", response)
        raise OreiMatrixError(msg)

    async def get_audio_output(self) -> int:
        """Return the current audio source (0=follow, 1..N=HDMI)."""
        # Send query command and read single-line response
        LOGGER.debug("get_audio_output(): querying device")
        response = await self._write_and_read(CMD_QUERY_AUDIO_OUTPUT)

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
            # Accept 0 (follow) as well as 1..NUM_INPUTS
            if 0 <= val <= NUM_INPUTS:
                LOGGER.debug("get_audio_output(): parsed value=%s", val)
                return val

        # If parsing fails, raise an error
        msg = f"Invalid audio output response: {response}"
        LOGGER.debug("get_audio_output(): parse failed: %s", response)
        raise OreiMatrixError(msg)

    async def power_on(self) -> None:
        """Turn the device power on."""
        LOGGER.debug("power_on(): sending power on command")
        await self._write_and_read(CMD_POWER_ON)
        LOGGER.debug("power_on(): command sent")

    async def power_off(self) -> None:
        """Turn the device power off."""
        LOGGER.debug("power_off(): sending power off command")
        await self._write_and_read(CMD_POWER_OFF)
        LOGGER.debug("power_off(): command sent")

    async def get_power_state(self) -> bool:
        """Query the device power state and return True if on, False if off."""
        LOGGER.debug("get_power_state(): querying device")
        response = await self._write_and_read(CMD_QUERY_POWER)
        LOGGER.debug("get_power_state(): raw response: %s", response)
        if response == RESPONSE_POWER_ON:
            LOGGER.debug("get_power_state(): parsed state=on")
            return True
        if response == RESPONSE_POWER_OFF:
            LOGGER.debug("get_power_state(): parsed state=off")
            return False
        msg = f"Invalid power state response: {response}"
        LOGGER.debug("get_power_state(): parse failed: %s", response)
        raise OreiMatrixError(msg)
