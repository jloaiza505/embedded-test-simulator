import logging
import socket


LOG = logging.getLogger(__name__)


class DeviceConnectionError(Exception):
    pass


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
        text = self._send("READ_TEMP")
        if not text.startswith("TEMP:"):
            raise InvalidResponseError(f"unexpected response: {text}")
        value = self._float(text)
        if not -40.0 <= value <= 125.0:
            raise InvalidResponseError(f"out-of-range temperature: {text}")
        return value

    def set_mode(self, mode):
        return self._expect(f"SET_MODE {mode}", f"MODE:{mode}").split(":", 1)[1]

    def get_status(self):
        text = self._send("GET_STATUS")
        if not text.startswith("STATUS:"):
            raise InvalidResponseError(f"unexpected response: {text}")
        value = text.split(":", 1)[1]
        if value not in {"OK", "ERROR"}:
            raise InvalidResponseError(f"invalid status: {text}")
        return value

    def read_file(self, name):
        data = self._send_raw(f"READ_FILE {name}")
        line, _, payload = data.partition(b"\n")
        text = line.decode().strip()
        if not text.startswith("FILE:"):
            raise InvalidResponseError(f"unexpected response: {text}")
        _, expected, filename = text.split(":", 2)
        if filename != name:
            raise InvalidResponseError(f"wrong file: {text}")
        if len(payload) != int(expected):
            raise InvalidResponseError(f"incomplete file payload: expected {expected}, got {len(payload)}")
        return payload.decode()

    def command(self, command):
        return self._send(command)

    def _float(self, text):
        try:
            return float(text.split(":", 1)[1])
        except ValueError as exc:
            raise InvalidResponseError(f"invalid numeric payload: {text}") from exc

    def _expect(self, command, expected):
        text = self._send(command)
        if text != expected:
            raise InvalidResponseError(f"unexpected response: {text}")
        return text

    def _send(self, command):
        return self._send_raw(command).decode().strip()

    def _send_raw(self, command):
        attempts = self.retries + 1
        for attempt in range(1, attempts + 1):
            try:
                LOG.info("send %s", command)
                with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
                    sock.settimeout(self.timeout)
                    sock.sendall(f"{command}\n".encode())
                    chunks = []
                    while True:
                        part = sock.recv(1024)
                        if not part:
                            break
                        chunks.append(part)
            except socket.timeout as exc:
                LOG.error("timeout on %s (%s/%s)", command, attempt, attempts)
                if attempt == attempts:
                    raise TimeoutError(f"timed out waiting for {command}") from exc
                continue
            except ConnectionRefusedError as exc:
                LOG.error("device unavailable on %s:%s", self.host, self.port)
                raise DeviceConnectionError(f"unable to connect to {self.host}:{self.port}") from exc
            except OSError as exc:
                LOG.error("socket error on %s: %s", command, exc)
                raise DeviceConnectionError(str(exc)) from exc
            data = b"".join(chunks)
            if not data:
                raise TimeoutError("device closed connection without response")
            LOG.info("recv %r", data)
            return data
