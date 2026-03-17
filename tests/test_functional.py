import pytest

from client.client import DeviceClient


# Verifies the nominal protocol flow for the core command set.
def test_happy_path_commands_return_expected_values(client):
    assert client.ping() == "OK", "PING should acknowledge a reachable device"
    assert client.read_temp() == 25.0, "READ_TEMP should return the default temperature"
    assert client.set_mode("MANUAL") == "MANUAL", "SET_MODE should echo the selected mode"
    assert client.get_status() == "OK", "GET_STATUS should report the nominal device state"


# Confirms unsupported commands fail at the protocol level, not silently.
def test_invalid_command_returns_protocol_error(client):
    assert client.command("BOGUS") == "ERROR:BAD_CMD", "Unknown commands should map to BAD_CMD"


@pytest.mark.parametrize("mode", ["AUTO", "MANUAL"])
# Ensures both supported operating modes are accepted and echoed back.
def test_mode_change_roundtrip_returns_requested_mode(client, mode):
    assert client.set_mode(mode) == mode, f"SET_MODE should confirm the new mode {mode}"


# Exercises repeated requests to catch simple state or socket instability.
def test_repeated_ping_requests_remain_stable(client):
    assert [client.ping() for _ in range(10)] == ["OK"] * 10, "Repeated commands should stay stable"


# Shows that slow-but-valid responses work when the client timeout is configured correctly.
def test_delayed_response_succeeds_when_client_timeout_is_long_enough(device):
    device.set_failure_mode("delay")
    assert client_with_timeout(device, 0.5).get_status() == "OK", "Delay mode should still succeed"


# Validates the framed file-transfer path on a complete payload.
def test_file_transfer_returns_complete_payload(client):
    assert client.read_file("log.txt") == "firmware-log-v1", "READ_FILE should return the full payload"


def client_with_timeout(device, timeout):
    return DeviceClient(port=device.port, timeout=timeout)
