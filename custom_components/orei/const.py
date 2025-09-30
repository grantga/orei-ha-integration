"""Constants for OREI UHD-401MV integration."""

from logging import Logger, getLogger

LOGGER: Logger = getLogger(__package__)

DOMAIN = "orei"
NAME = "OREI UHD-401MV"
MANUFACTURER = "OREI"
MODEL = "UHD-401MV"

# Configuration constants
CONF_SERIAL_PORT = "serial_port"
DEFAULT_SERIAL_PORT = "/dev/ttyUSB"

# Serial Protocol Constants
BAUDRATE = 115200
BYTESIZE = 8
PARITY = "N"
STOPBITS = 1
TIMEOUT = 1

# Protocol Commands
# e.g., "sw i1v1" switches input 1 to output 1
CMD_SWITCH_INPUT = "sw i{input}v{output}\r\n"
CMD_QUERY_INPUT = "r av{output}\r\n"  # e.g., "r av1" reads current input for output 1
CMD_POWER_ON = "on\r\n"
CMD_POWER_OFF = "off\r\n"
CMD_QUERY_POWER = "r power\r\n"

# Response patterns
RESPONSE_INPUT = "av{output} from i{input}"  # e.g., "av1 from i1"
RESPONSE_POWER_ON = "on"
RESPONSE_POWER_OFF = "off"

# Number of inputs/outputs
NUM_INPUTS = 4
NUM_OUTPUTS = 1

UPDATE_INTERVAL = 10  # seconds
