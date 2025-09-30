# OREI UHD-401MV Home Assistant integration (development)

This repository contains a Home Assistant custom integration that controls an
OREI UHD-401MV HDMI matrix over a local RS-232 serial connection. The
integration is implemented as a developer-focused example and includes a
serial async client, entities (power switch / input select), a
DataUpdateCoordinator, and a config flow for selecting the serial port.

This project is intended for development, testing, and as a blueprint for
building similar local integrations. It is not a production-ready add-on for
general distribution without additional testing and validation against real
hardware.

## Quick highlights

- Domain: `orei` (custom component under `custom_components/orei`)
- Device: OREI UHD-401MV HDMI matrix (RS-232 ASCII protocol)
- Serial library: `pyserial-asyncio` (declared in the integration manifest)

## Minimum repository layout

Path | Purpose
-- | --
`custom_components/orei/` | Integration source (async client, entities, coordinator, config flow)
`config/` | Development Home Assistant configuration and logs (local dev only)
`scripts/` | Helper scripts (develop, lint, setup)
`requirements.txt` | Development/test dependencies

## Quick start (development)

1. Open this repository in the provided VS Code devcontainer or a Python 3.11+ environment.
2. Install developer dependencies listed in `requirements.txt` (or let the devcontainer handle it).
3. Start the local Home Assistant dev environment using the included script:

```bash
./scripts/develop
```

The `scripts/develop` script starts a Home Assistant process using the
`config/` folder included in the repository. Tail the logs in the terminal to
see startup messages and any integration errors.

## Notes on `configuration.yaml`

- For development the repository includes `config/configuration.yaml`. It
  intentionally does not use `default_config:` because that pulls in several
  integrations which may expect host components (for example `go2rtc` which
  may look for a Docker binary). If Home Assistant fails to start with errors
  referencing `go2rtc`, edit `config/configuration.yaml` and avoid
  `default_config:` — a minimal explicit list is provided in the file.

## How the integration works (short)

- `custom_components/orei/api.py` provides an async serial client that sends
  ASCII commands terminated by CRLF and parses the device responses.
- `coordinator.py` uses Home Assistant's `DataUpdateCoordinator` to poll the
  matrix for power and input state and shares that state with entities.
- `switch.py` implements a `SwitchEntity` to control the matrix power.
- `select.py` implements a `SelectEntity` to change the active input on the matrix.

## Troubleshooting: frontend stuck on "Loading data"

If the Home Assistant web UI is stuck on "Loading data", common causes and
checks are:

- Look at `config/home-assistant.log` for ERROR/WARNING messages. Key
  things to search for: "ERROR", "WARNING", "Traceback", "websocket",
  "frontend", "unhandled exception", and "blocked".
- Check for blocking synchronous I/O in custom integrations. If an integration
  performs long blocking calls during setup or inside the coordinator update
  callback, it can block the Home Assistant event loop and prevent the
  frontend from loading.
- Verify the HTTP server and websocket are bound and listening. If the HTTP
  server fails to bind (port already in use), the frontend cannot connect.
- Recorder / database issues (sqlite warnings) can slow or stall startup.

If you see errors referencing the `orei` integration and the serial client,
ensure the integration uses `asyncio` APIs (via `pyserial-asyncio`) and does
not perform blocking `serial` calls on the event loop.

## Testing and development guidance

- Linting and formatting: use the repository `scripts/lint` script. The
  devcontainer comes pre-configured for common tools used during development.
- Unit tests: write pytest tests that mock `serial_asyncio` to simulate the
  matrix responses. This is the preferred way to validate command formatting and
  response parsing without hardware.
- Hardware testing: when you have the UHD-401MV connected to your development
  machine (via a serial adapter), configure the serial port in the integration
  UI (or `configuration.yaml`) and verify that commands change inputs and power.

## Important developer notes

- Avoid long blocking synchronous calls in integration setup or in
  coordinator update methods — they block the Home Assistant event loop and
  can cause the frontend to show "Loading data" or fail to respond.
- Prefer `asyncio` APIs and the project's `pyserial-asyncio` dependency.
- Use explicit API methods (for example `power_on()` / `power_off()`) instead
  of boolean positional arguments to make intent clear and to satisfy linters.

## Running the project checks

Run linting and tests in the workspace:

```bash
./scripts/lint
pytest
```

## Contributing

See `CONTRIBUTING.md` for the contribution workflow. Pull requests that add
tests, documentation, and small focused improvements are welcome.

## License

This repository includes a `LICENSE` file. Please follow the stated license
when reusing code from this project.
