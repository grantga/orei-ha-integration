"""Constants for OREI UHD-401MV integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "orei"
NAME = "OREI UHD-401MV"
MANUFACTURER = "OREI"
MODEL = "UHD-401MV"

# Configuration constants
CONF_SERIAL_PORT = "serial_port"
DEFAULT_SERIAL_PORT = "/dev/ttyUSB0"
CONF_BAUDRATE = "baudrate"

# Serial Protocol Constants
BAUDRATE = 115200
BYTESIZE = 8
PARITY = "N"
STOPBITS = 1
TIMEOUT = 3

# Protocol Commands
CMD_POWER_ON = "power 1!\r\n"
CMD_POWER_OFF = "power 0!\r\n"
CMD_QUERY_POWER = "r power!\r\n"

# Audio output command: set audio source for the (single) output.
# Device expects: "s output audio x!" where x is 0..4
CMD_SET_AUDIO_OUTPUT = "s output audio {source}!\r\n"

# Query audio output source. Device responds with a text description such
# as "output audio: follow window" or a message indicating which HDMI input is
# selected. The command below requests the current audio source.
CMD_QUERY_AUDIO_OUTPUT = "r output audio!\r\n"

# Multiview (display mode) commands
# Set multi-viewer display mode: s multiview x! where x=1..5
# Query multi-viewer display mode: r multiview!
CMD_SET_MULTIVIEW = "s multiview {mode}!\r\n"
CMD_QUERY_MULTIVIEW = "r multiview!\r\n"

# Multiview modes supported by the device
MULTIVIEW_MIN = 1
MULTIVIEW_MAX = 5

# Response patterns
RESPONSE_POWER_ON = "power on"
RESPONSE_POWER_OFF = "power off"

# Number of inputs
NUM_INPUTS = 4

# Number of windows available for multiview layouts
NUM_WINDOWS = 4

# Window (per-view) commands
# Set window input: s window {win} in {src}!
# Query window input: r window {win} in!
CMD_SET_WINDOW_INPUT = "s window {win} in {src}!\r\n"
CMD_QUERY_WINDOW_INPUT = "r window {win} in!\r\n"

# PIP (picture-in-picture) position and size
# Set PIP position: s PIP position x!  (1..4)
# Query PIP position: r PIP position!
CMD_SET_PIP_POSITION = "s PIP position {pos}!\r\n"
CMD_QUERY_PIP_POSITION = "r PIP position!\r\n"

# Set PIP size: s PIP size x!  (1..3)
# Query PIP size: r PIP size!
CMD_SET_PIP_SIZE = "s PIP size {size}!\r\n"
CMD_QUERY_PIP_SIZE = "r PIP size!\r\n"

# PIP ranges
PIP_POSITION_MIN = 1
PIP_POSITION_MAX = 4
PIP_SIZE_MIN = 1
PIP_SIZE_MAX = 3

UPDATE_INTERVAL = 120  # seconds

# PBP (picture-by-picture) mode commands
# Set PBP mode: s PBP mode {mode}!  (1..2)
# Query PBP mode: r PBP mode!
CMD_SET_PBP_MODE = "s PBP mode {mode}!\r\n"
CMD_QUERY_PBP_MODE = "r PBP mode!\r\n"

PBP_MODE_MIN = 1
PBP_MODE_MAX = 2
