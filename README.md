# Embedded Test Simulation

This project is a minimal, production-style Python simulation of a GUI-to-embedded-device test environment. It models a PC-side client that sends commands over TCP to a mock embedded device, then validates normal behavior, error handling, and failure scenarios with automated tests.

The implementation is intentionally small. The focus is not realism or UI, but disciplined structure, deterministic behavior, and reproducible automated verification.

## What The Project Simulates

The system represents a common embedded workflow:

- A desktop-side test tool sends commands to a device.
- The device returns line-based responses.
- The client applies timeouts and validates those responses.
- Tests exercise both expected behavior and injected failures.

This is useful as a compact example of how to structure communication-heavy test systems without adding unnecessary layers or dependencies.

## Project Layout

```text
project/
├── client/
│   ├── __init__.py
│   └── client.py
├── device/
│   ├── __init__.py
│   └── mock_device.py
├── tests/
│   ├── conftest.py
│   ├── test_failures.py
│   └── test_functional.py
├── .github/workflows/
│   └── ci.yml
├── requirements.txt
└── README.md
```

## Architecture

The code is split into three clear responsibilities.

### 1. Client

`client/client.py` contains `DeviceClient`, the PC-side communication layer.

Its responsibilities are:

- open a TCP connection to the device
- send one text command per request
- wait for a response with a configurable timeout
- parse known response formats
- raise clear exceptions when the device does not respond or returns malformed data
- emit lightweight logs for sent commands, received responses, and errors

The client opens a fresh socket for each command. That keeps the behavior easy to reason about and makes the tests deterministic, because each request is isolated from previous ones.

### 2. Mock Embedded Device

`device/mock_device.py` contains `MockDevice`, a lightweight TCP server that simulates firmware behavior.

It maintains internal state:

- `mode`: `AUTO` or `MANUAL`
- `temperature`: floating-point value, default `25.0`
- `status`: `OK` by default

It also supports runtime failure injection so tests can force specific communication problems without changing the client code.

### 3. Tests

The `tests/` directory uses `pytest` to verify the system from the outside, the same way a real test harness would interact with a device-facing client.

The tests:

- start the mock device
- build a client bound to the device’s dynamic port
- exercise functional behavior
- inject failures
- stop the server cleanly after each test

## Communication Model

The client and device communicate over TCP on `localhost`. The protocol is intentionally simple:

- one command per connection
- newline-terminated strings
- one response per command

This keeps the protocol human-readable and easy to test while still modeling real request/response communication.

## Protocol Definition

Supported commands:

- `PING`
- `READ_TEMP`
- `SET_MODE AUTO`
- `SET_MODE MANUAL`
- `GET_STATUS`
- `READ_FILE <name>`

Supported response formats:

- `OK`
- `TEMP:<value>`
- `MODE:<value>`
- `STATUS:<value>`
- `FILE:<size>:<name>` followed by payload bytes
- `ERROR:<code>`

Examples:

- `PING` -> `OK`
- `READ_TEMP` -> `TEMP:25.0`
- `SET_MODE MANUAL` -> `MODE:MANUAL`
- `GET_STATUS` -> `STATUS:OK`
- `BOGUS` -> `ERROR:BAD_CMD`
- `READ_FILE log.txt` -> `FILE:15:log.txt` + `firmware-log-v1`

## How The Client Works

`DeviceClient` provides a small API:

- `ping()`
- `read_temp()`
- `set_mode(mode)`
- `get_status()`
- `command(command)` for raw command access
- `read_file(name)` for small framed file reads

Internally, `_send()` handles the transport behavior:

- connects to the configured host and port
- sends the command followed by `\n`
- reads the reply
- enforces socket timeout
- optionally retries if configured

Response parsing is strict by design:

- `read_temp()` only accepts `TEMP:<value>`
- `get_status()` only accepts `STATUS:<value>`
- `set_mode()` only accepts the exact `MODE:<value>` it asked for

If a reply is malformed, the client raises `InvalidResponseError`. If the server does not respond in time, the client raises `TimeoutError`.

This is the main reliability boundary in the project: transport and parsing failures are surfaced clearly to callers instead of being silently ignored.

## How The Mock Device Works

`MockDevice` starts a background thread and listens on a TCP socket bound to `127.0.0.1`.

Important behavior:

- `port=0` lets the OS assign an available ephemeral port
- the actual port is stored back on `self.port` after bind
- a readiness event ensures tests do not talk to the server before it is listening
- the server loop accepts one connection at a time and handles a single request per connection

The request handler:

1. receives raw bytes from the socket
2. decodes the incoming command
3. applies any configured failure mode
4. generates a protocol response
5. sends the response back over the socket

This keeps the implementation compact while still modeling enough device behavior for meaningful tests.

## Failure Injection

The device supports these runtime modes through `set_failure_mode(...)`:

- `normal`: process requests normally
- `timeout`: intentionally do not respond before the client timeout expires
- `delay`: pause before returning a valid response
- `corrupt`: return malformed data (`???`) instead of a valid protocol response
- `disconnect`: accept the request and close the connection without a reply
- `partial`: send a truncated response
- `flaky_timeout`: fail once, then succeed to validate retries
- `bad_temp`: send a syntactically valid but semantically invalid temperature
- `bad_status`: send an unsupported status value
- `file_cut`: interrupt a file transfer mid-payload

These modes are the key to testing robustness:

- `timeout` validates client-side timeout handling
- `delay` validates that the client still works when given a large enough timeout
- `corrupt` validates strict response parsing
- `disconnect` validates mid-transaction link loss handling
- `partial` validates truncated payload handling
- `flaky_timeout` validates retry recovery
- `bad_temp` and `bad_status` validate semantic response checking
- `file_cut` validates interrupted transfer detection

Because failure mode is controlled at runtime, the same server implementation can be reused across all tests.

## Logging

Both sides use the standard library `logging` module.

Client logs include:

- command sent
- response received
- timeout or socket errors

Device logs include:

- command received
- response returned

The logging is intentionally lightweight. It is enough for debugging tests or protocol issues without complicating the code.

## Test Strategy

The test suite is organized around behavior rather than implementation details.

### `tests/conftest.py`

This file defines shared pytest fixtures:

- `device()`: starts a fresh `MockDevice` and stops it after the test
- `client(device)`: creates a `DeviceClient` connected to that device

This ensures each test runs against an isolated server instance and does not depend on global state from earlier tests.

### `tests/test_functional.py`

These tests validate expected behavior:

- valid commands return expected values
- invalid commands return protocol-level errors
- mode changes work for both `AUTO` and `MANUAL`
- rapid repeated commands remain stable
- file reads return complete payloads

The rapid-command test is a simple stability check. It does not try to benchmark performance; it verifies that repeated calls do not break the request/response flow.

### `tests/test_failures.py`

These tests validate failure handling:

- timeout mode raises `TimeoutError`
- no-device mode raises `DeviceConnectionError`
- disconnect mode raises a transport failure
- partial and corrupt responses raise `InvalidResponseError`
- delay mode succeeds when the client timeout is large enough
- flaky timeout succeeds when retries are enabled
- invalid temperature and status values are rejected
- interrupted file transfer is detected

This is the core of the project’s testing value: the client is verified not only for the happy path, but also for realistic communication failures.

## Determinism And Reproducibility

The project is intentionally designed to be deterministic:

- no external services
- no random behavior
- no real hardware
- local-only sockets
- fixed initial device state
- isolated server instance per test

That makes the test suite reliable in local development and CI.

## Running Locally

Create a virtual environment, install dependencies, and run the tests:

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -q
```

If your system Python blocks virtual environment creation, install the distro package for venv support first, such as `python3-venv`.

## Manual Example

You can also use the system manually from Python:

```python
from client.client import DeviceClient
from device.mock_device import MockDevice

device = MockDevice()
device.start()

client = DeviceClient(port=device.port, timeout=0.2)
print(client.ping())
print(client.read_temp())
print(client.set_mode("MANUAL"))
print(client.get_status())

device.set_failure_mode("corrupt")

try:
    client.read_temp()
except Exception as exc:
    print(type(exc).__name__, exc)

device.stop()
```

## Dependency Model

The project uses only one external dependency:

- `pytest` for test execution

Everything else is standard library:

- `socket`
- `threading`
- `time`
- `logging`

This keeps setup simple and aligns with the goal of a small, production-quality example.

## Continuous Integration

GitHub Actions is configured in [ci.yml](/home/james/unlisted/.github/workflows/ci.yml).

The workflow:

- runs on push
- runs on pull request
- installs Python 3.11
- installs `requirements.txt`
- runs `pytest`

That gives the project a reproducible automated verification path and helps catch regressions immediately when code changes.

## Why The Design Is Intentionally Small

This project avoids several things on purpose:

- no GUI
- no async framework
- no serialization library
- no persistent connections
- no heavy abstraction layers

Those choices keep attention on the essential engineering problems:

- command/response communication
- protocol validation
- failure handling
- deterministic testing
- CI automation

For a simulation intended to demonstrate test discipline, this is a better tradeoff than adding realism at the cost of clarity.

## Current Verification Status

The test suite has already passed locally with:

```bash
python -m pytest -q
```

Result:

- `8 passed`

## Summary

This repository is a compact example of a testable embedded communication simulation:

- a client that enforces protocol expectations
- a mock device with internal state and failure injection
- a deterministic pytest suite
- a CI workflow for automated regression checking

It is small enough to understand quickly and structured enough to reflect real engineering practice.
