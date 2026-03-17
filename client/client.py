import logging
import socket


LOG = logging.getLogger(__name__)


class InvalidResponseError(Exception):
    pass


class DeviceClient:
    def __init__(self, host="127.0.0.1", port=9000, timeout=0.2, retries=0):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.retries = retries

    def ping(self):
        return self._expect("PING", "OK")

    def read_temp(self):
        value = self._send("READ_TEMP")
        if not value.startswith("TEMP:"):
            raise InvalidResponseError(f"unexpected response: {value}")
        try:
            return float(value.split(":", 1)[1])
        except ValueError as exc:
            raise InvalidResponseError(f"invalid temperature: {value}") from exc

    def set_mode(self, mode):
        value = self._send(f"SET_MODE {mode}")
        if value != f"MODE:{mode}":
            raise InvalidResponseError(f"unexpected response: {value}")
        return mode

    def get_status(self):
        value = self._send("GET_STATUS")
        if not value.startswith("STATUS:"):
            raise InvalidResponseError(f"unexpected response: {value}")
        return value.split(":", 1)[1]

    def command(self, command):
        return self._send(command)

    def _expect(self, command, expected):
        value = self._send(command)
        if value != expected:
            raise InvalidResponseError(f"unexpected response: {value}")
        return value

    def _send(self, command):
        attempts = self.retries + 1
        for attempt in range(1, attempts + 1):
            try:
                LOG.info("send %s", command)
                with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                    sock.settimeout(self.timeout)
                    sock.sendall(f"{command}\n".encode())
                    data = sock.recv(1024)
                if not data:
                    raise TimeoutError("device closed connection without response")
                response = data.decode().strip()
                LOG.info("recv %s", response)
                return response
            except socket.timeout as exc:
                LOG.error("timeout on %s (%s/%s)", command, attempt, attempts)
                if attempt == attempts:
                    raise TimeoutError(f"timed out waiting for {command}") from exc
            except OSError:
                LOG.exception("socket error on %s", command)
                raise
