import pytest


def test_valid_commands(client):
    assert client.ping() == "OK"
    assert client.read_temp() == 25.0
    assert client.set_mode("MANUAL") == "MANUAL"
    assert client.get_status() == "OK"


def test_invalid_command_returns_error(client):
    assert client.command("BOGUS") == "ERROR:BAD_CMD"


@pytest.mark.parametrize("mode", ["AUTO", "MANUAL"])
def test_mode_roundtrip(client, mode):
    assert client.set_mode(mode) == mode


def test_multiple_rapid_commands(client):
    results = [client.ping() for _ in range(10)]
    assert results == ["OK"] * 10
