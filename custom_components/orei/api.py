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
    CMD_QUERY_PBP_MODE,
    CMD_QUERY_PIP_POSITION,
    CMD_QUERY_PIP_SIZE,
    CMD_QUERY_POWER,
    CMD_QUERY_WINDOW_INPUT,
    CMD_SET_AUDIO_OUTPUT,
    CMD_SET_MULTIVIEW,
    CMD_SET_PBP_MODE,
    CMD_SET_PIP_POSITION,
    CMD_SET_PIP_SIZE,
    CMD_SET_WINDOW_INPUT,
    LOGGER,
    MULTIVIEW_MAX,
    MULTIVIEW_MIN,
    NUM_INPUTS,
    NUM_WINDOWS,
    PARITY,
    PBP_MODE_MAX,
    PBP_MODE_MIN,
    PIP_POSITION_MAX,
    PIP_POSITION_MIN,
    PIP_SIZE_MAX,
    PIP_SIZE_MIN,
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
                        chunk = await asyncio.wait_for(reader.readline(), timeout=0.1)
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

    async def set_window_input(self, window: int, source: int) -> None:
        """
        Set the HDMI input for a specific window.

        window: 1..NUM_WINDOWS
        source: 1..NUM_INPUTS

        """
        LOGGER.debug("set_window_input(): window=%s source=%s", window, source)

        if not 1 <= window <= NUM_WINDOWS:
            msg = f"Window must be between 1 and {NUM_WINDOWS}"
            LOGGER.debug("set_window_input(): invalid window %s", window)
            raise OreiMatrixError(msg)
        if not 1 <= source <= NUM_INPUTS:
            msg = f"Source must be between 1 and {NUM_INPUTS}"
            LOGGER.debug("set_window_input(): invalid source %s", source)
            raise OreiMatrixError(msg)

        cmd = CMD_SET_WINDOW_INPUT.format(win=window, src=source)
        await self._write_and_read(cmd)
        LOGGER.debug("set_window_input(): done for window=%s", window)

    async def set_pip_position(self, position: int) -> None:
        """
        Set the PIP window position.

        position: 1..4 where:
          1 = Left Top
          2 = Left Bottom
          3 = Right Top
          4 = Right Bottom
        """
        LOGGER.debug("set_pip_position(): requested position=%s", position)
        if not PIP_POSITION_MIN <= position <= PIP_POSITION_MAX:
            msg = (
                "PIP position must be between "
                f"{PIP_POSITION_MIN} and {PIP_POSITION_MAX}"
            )
            LOGGER.debug("set_pip_position(): invalid position %s", position)
            raise OreiMatrixError(msg)

        cmd = CMD_SET_PIP_POSITION.format(pos=position)
        await self._write_and_read(cmd)
        LOGGER.debug("set_pip_position(): set position=%s complete", position)

    async def get_pip_position(self) -> int | None:
        """
        Query the PIP window position.

        Returns 1..4 or None when device reports power off.
        """
        LOGGER.debug("get_pip_position(): querying device")
        response = await self._write_and_read(CMD_QUERY_PIP_POSITION)
        resp = response.lower().strip()

        if RESPONSE_POWER_OFF in resp:
            LOGGER.debug("get_pip_position(): device powered off, state unknown")
            return None

        # Example response: "PIP on right top" or similar; look for digits
        for token in resp.split():
            digits = "".join(ch for ch in token if ch.isdigit())
            if not digits:
                continue
            try:
                val = int(digits)
            except ValueError:
                continue
            if PIP_POSITION_MIN <= val <= PIP_POSITION_MAX:
                LOGGER.debug("get_pip_position(): parsed value=%s", val)
                return val

        # Fallback: map textual descriptions
        mapping = {
            "left top": 1,
            "left bottom": 2,
            "right top": 3,
            "right bottom": 4,
        }
        for key, val in mapping.items():
            if key in resp:
                LOGGER.debug("get_pip_position(): parsed text '%s' -> %s", key, val)
                return val

        msg = f"Invalid PIP position response: {response}"
        LOGGER.debug("get_pip_position(): parse failed: %s", response)
        raise OreiMatrixError(msg)

    async def set_pip_size(self, size: int) -> None:
        """
        Set the PIP window size.

        size: 1..3 where 1=small, 2=middle, 3=large
        """
        LOGGER.debug("set_pip_size(): requested size=%s", size)
        if not PIP_SIZE_MIN <= size <= PIP_SIZE_MAX:
            msg = f"PIP size must be between {PIP_SIZE_MIN} and {PIP_SIZE_MAX}"
            LOGGER.debug("set_pip_size(): invalid size %s", size)
            raise OreiMatrixError(msg)

        cmd = CMD_SET_PIP_SIZE.format(size=size)
        await self._write_and_read(cmd)
        LOGGER.debug("set_pip_size(): set size=%s complete", size)

    async def get_pip_size(self) -> int | None:
        """
        Query the PIP window size.

        Returns 1..3 or None when device reports power off.
        """
        LOGGER.debug("get_pip_size(): querying device")
        response = await self._write_and_read(CMD_QUERY_PIP_SIZE)
        resp = response.lower().strip()

        if RESPONSE_POWER_OFF in resp:
            LOGGER.debug("get_pip_size(): device powered off, state unknown")
            return None

        # Try digit parsing first
        for token in resp.split():
            digits = "".join(ch for ch in token if ch.isdigit())
            if not digits:
                continue
            try:
                val = int(digits)
            except ValueError:
                continue
            if PIP_SIZE_MIN <= val <= PIP_SIZE_MAX:
                LOGGER.debug("get_pip_size(): parsed value=%s", val)
                return val

        # Map textual responses
        mapping = {"small": 1, "middle": 2, "large": 3}
        for key, val in mapping.items():
            if key in resp:
                LOGGER.debug("get_pip_size(): parsed text '%s' -> %s", key, val)
                return val

        msg = f"Invalid PIP size response: {response}"
        LOGGER.debug("get_pip_size(): parse failed: %s", response)
        raise OreiMatrixError(msg)

    async def set_pbp_mode(self, mode: int) -> None:
        """
        Set the PBP windows display mode.

        mode: 1..2
        """
        LOGGER.debug("set_pbp_mode(): requested mode=%s", mode)
        if not PBP_MODE_MIN <= mode <= PBP_MODE_MAX:
            msg = f"PBP mode must be between {PBP_MODE_MIN} and {PBP_MODE_MAX}"
            LOGGER.debug("set_pbp_mode(): invalid mode %s", mode)
            raise OreiMatrixError(msg)

        cmd = CMD_SET_PBP_MODE.format(mode=mode)
        await self._write_and_read(cmd)
        LOGGER.debug("set_pbp_mode(): set mode=%s complete", mode)

    async def get_pbp_mode(self) -> int | None:
        """
        Query the PBP windows display mode.

        Returns 1..2 or None when device reports power off.
        """
        LOGGER.debug("get_pbp_mode(): querying device")
        response = await self._write_and_read(CMD_QUERY_PBP_MODE)
        resp = response.lower().strip()

        if RESPONSE_POWER_OFF in resp:
            LOGGER.debug("get_pbp_mode(): device powered off, state unknown")
            return None

        # Try digit parsing
        for token in resp.split():
            digits = "".join(ch for ch in token if ch.isdigit())
            if not digits:
                continue
            try:
                val = int(digits)
            except ValueError:
                continue
            if PBP_MODE_MIN <= val <= PBP_MODE_MAX:
                LOGGER.debug("get_pbp_mode(): parsed value=%s", val)
                return val

        # Fallback textual parsing like 'PBP mode 1'
        for token in resp.split():
            if token.endswith("1"):
                return 1
            if token.endswith("2"):
                return 2

        msg = f"Invalid PBP mode response: {response}"
        LOGGER.debug("get_pbp_mode(): parse failed: %s", response)
        raise OreiMatrixError(msg)

    async def get_window_input(self, window: int) -> int | None:
        """
        Query which HDMI input is selected for a given window.

        Returns 1..NUM_INPUTS, or None when device reports power off.

        """
        LOGGER.debug("get_window_input(): querying window=%s", window)
        if not 0 <= window <= NUM_WINDOWS:
            msg = f"Window must be between 0 and {NUM_WINDOWS}"
            LOGGER.debug("get_window_input(): invalid window %s", window)
            raise OreiMatrixError(msg)

        # 0 means ALL — device may reply with multiple lines; for simplicity
        # request a single window when calling from the coordinator/UI.
        cmd = CMD_QUERY_WINDOW_INPUT.format(win=window)
        response = await self._write_and_read(cmd)
        resp = response.lower().strip()

        # If device is powered off, return unknown
        if RESPONSE_POWER_OFF in resp:
            LOGGER.debug("get_window_input(): device powered off, unknown state")
            return None

        # Example textual response: "window 1 select HDMI 1"
        for token in resp.split():
            digits = "".join(ch for ch in token if ch.isdigit())
            if not digits:
                continue
            try:
                val = int(digits)
            except ValueError:
                continue
            if 1 <= val <= NUM_INPUTS:
                LOGGER.debug("get_window_input(): parsed value=%s", val)
                return val

        msg = f"Invalid window input response: {response}"
        LOGGER.debug("get_window_input(): parse failed: %s", response)
        raise OreiMatrixError(msg)

    async def get_multiview(self) -> int | None:
        """
        Return the current multi-viewer display mode.

        Returns an integer between MULTIVIEW_MIN and MULTIVIEW_MAX.
        """
        LOGGER.debug("get_multiview(): querying device")
        response = await self._write_and_read(CMD_QUERY_MULTIVIEW)
        resp = response.lower().strip()

        # If the device reports it is powered off, multiview state is unknown.
        if RESPONSE_POWER_OFF in resp:
            LOGGER.debug("get_multiview(): device powered off, state unknown")
            return None

        # First try to map common textual responses to the numeric mode.
        # Accept various forms and case-insensitive matches to be robust.
        mapping: dict[str, int] = {
            "single screen": 1,
            "single": 1,
            "pip": 2,
            "pbp": 3,
            "triple screen": 4,
            "quad screen": 5,
        }

        # Check for any mapping key appearing in the response text. Prefer
        # longer keys first so e.g. "single screen" matches before "single".
        for key in sorted(mapping.keys(), key=len, reverse=True):
            if key in resp:
                val = mapping[key]
                LOGGER.debug("get_multiview(): parsed text '%s' -> %s", key, val)
                return val

        msg = f"Invalid multiview response: {response}"
        LOGGER.debug("get_multiview(): parse failed: %s", response)
        raise OreiMatrixError(msg)

    async def get_audio_output(self) -> int | None:
        """
        Return the current audio source (0=follow, 1..N=HDMI).

        Returns None when the device is powered off and the audio state is
        therefore unknown.

        """
        # Send query command and read single-line response
        LOGGER.debug("get_audio_output(): querying device")
        response = await self._write_and_read(CMD_QUERY_AUDIO_OUTPUT)

        # Normalize to lower-case for parsing
        resp = response.lower().strip()

        # If the device reports it is powered off, audio output is unknown.
        if RESPONSE_POWER_OFF in resp:
            LOGGER.debug("get_audio_output(): device powered off, state unknown")
            return None

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
