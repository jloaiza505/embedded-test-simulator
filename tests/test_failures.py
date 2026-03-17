import pytest

from client.client import DeviceClient, InvalidResponseError


def test_timeout_mode_raises_timeout(device):
    device.set_failure_mode("timeout")
    client = DeviceClient(port=device.port, timeout=0.1)
    with pytest.raises(TimeoutError):
        client.ping()


def test_delay_mode_succeeds_with_longer_timeout(device):
    device.set_failure_mode("delay")
    client = DeviceClient(port=device.port, timeout=0.5)
    assert client.get_status() == "OK"


def test_corrupt_mode_raises_invalid_response(device):
    device.set_failure_mode("corrupt")
    client = DeviceClient(port=device.port, timeout=0.1)
    with pytest.raises(InvalidResponseError):
        client.read_temp()
