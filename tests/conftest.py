import logging

import pytest

from client.client import DeviceClient
from device.mock_device import MockDevice


logging.basicConfig(level=logging.INFO)


@pytest.fixture
def device():
    server = MockDevice()
    server.start()
    yield server
    server.stop()


@pytest.fixture
def client(device):
    return DeviceClient(port=device.port, timeout=0.15, retries=0)
