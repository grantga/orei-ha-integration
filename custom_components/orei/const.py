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
TIMEOUT = 1

# Protocol Commands
CMD_POWER_ON = "s power 1!"
CMD_POWER_OFF = "s power 2!"
CMD_QUERY_POWER = "r power!"

# Audio output command: set audio source for the (single) output.
# Device expects: "s output audio x!" where x is 0..4
CMD_SET_AUDIO_OUTPUT = "s output audio {source}!"

# Query audio output source. Device responds with a text description such
# as "output audio: follow window" or a message indicating which HDMI input is
# selected. The command below requests the current audio source.
CMD_QUERY_AUDIO_OUTPUT = "r output audio!"

# Response patterns
RESPONSE_POWER_ON = "power on"
RESPONSE_POWER_OFF = "power off"

# Number of inputs/outputs
NUM_INPUTS = 4
NUM_OUTPUTS = 1

UPDATE_INTERVAL = 120  # seconds
