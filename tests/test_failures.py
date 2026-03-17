import pytest

from client.client import DeviceClient, DeviceConnectionError, InvalidResponseError


# Verifies the client reports a clear transport error when no server is reachable.
def test_connection_error_is_reported_when_no_device_is_listening():
    with pytest.raises(DeviceConnectionError, match="unable to connect"):
        DeviceClient(port=65500, timeout=0.05).ping()


# Confirms a non-responsive device becomes a timeout at the client boundary.
def test_timeout_failure_mode_raises_timeout_error(device):
    device.set_failure_mode("timeout")
    with pytest.raises(TimeoutError, match="PING"):
        DeviceClient(port=device.port, timeout=0.1).ping()


# Distinguishes a dropped connection from a normal timeout by checking the message.
def test_disconnect_after_command_is_reported_as_missing_response(device):
    device.set_failure_mode("disconnect")
    with pytest.raises(TimeoutError, match="without response"):
        DeviceClient(port=device.port, timeout=0.1).ping()


# Ensures truncated numeric data is rejected instead of being partially accepted.
def test_truncated_temperature_response_is_rejected(device):
    device.set_failure_mode("partial")
    with pytest.raises(InvalidResponseError, match="invalid numeric payload"):
        DeviceClient(port=device.port, timeout=0.1).read_temp()


# Confirms malformed protocol frames are rejected by the parser.
def test_malformed_response_is_rejected_by_parser(device):
    device.set_failure_mode("corrupt")
    with pytest.raises(InvalidResponseError, match="unexpected response"):
        DeviceClient(port=device.port, timeout=0.1).read_temp()


# Verifies retry logic can recover from one transient timeout on a later attempt.
def test_retry_recovers_from_a_single_transient_timeout(device):
    device.set_failure_mode("flaky_timeout")
    assert DeviceClient(port=device.port, timeout=0.1, retries=1).ping() == "OK", "One retry should recover"


# Rejects syntactically valid but semantically impossible sensor values.
def test_semantically_invalid_temperature_value_is_rejected(device):
    device.set_failure_mode("bad_temp")
    with pytest.raises(InvalidResponseError, match="out-of-range temperature"):
        DeviceClient(port=device.port, timeout=0.1).read_temp()


# Rejects unexpected status values so new firmware states do not slip through silently.
def test_unsupported_status_value_is_rejected(device):
    device.set_failure_mode("bad_status")
    with pytest.raises(InvalidResponseError, match="invalid status"):
        DeviceClient(port=device.port, timeout=0.1).get_status()


# Detects an interrupted file transfer by validating the advertised payload length.
def test_interrupted_file_transfer_is_detected_as_incomplete_payload(device):
    device.set_failure_mode("file_cut")
    with pytest.raises(InvalidResponseError, match="incomplete file payload"):
        DeviceClient(port=device.port, timeout=0.1).read_file("log.txt")
