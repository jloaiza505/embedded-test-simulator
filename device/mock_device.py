import logging
import socket
import threading
import time


LOG = logging.getLogger(__name__)


class MockDevice:
    def __init__(self, host="127.0.0.1", port=0, delay_seconds=0.3):
        self.host = host
        self.port = port
        self.delay_seconds = delay_seconds
        self.failure_mode = "normal"
        self.mode = "AUTO"
        self.temperature = 25.0
        self.status = "OK"
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread = None
        self._sock = None

    def start(self):
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=1)

    def stop(self):
        self._stop.set()
        if self._sock:
            try:
                self._sock.close()
            except OSError:
                pass
        if self._thread:
            self._thread.join(timeout=1)

    def set_failure_mode(self, mode):
        self.failure_mode = mode

    def _serve(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            server.listen()
            server.settimeout(0.1)
            self.port = server.getsockname()[1]
            self._sock = server
            self._ready.set()
            while not self._stop.is_set():
                try:
                    conn, _ = server.accept()
                except socket.timeout:
                    continue
                except OSError:
                    break
                with conn:
                    self._handle(conn)

    def _handle(self, conn):
        data = conn.recv(1024)
        if not data:
            return
        command = data.decode().strip()
        LOG.info("cmd %s", command)
        if self.failure_mode == "timeout":
            time.sleep(self.delay_seconds * 2)
            return
        if self.failure_mode == "delay":
            time.sleep(self.delay_seconds)
        response = "???" if self.failure_mode == "corrupt" else self._process(command)
        LOG.info("resp %s", response)
        conn.sendall(f"{response}\n".encode())

    def _process(self, command):
        if command == "PING":
            return "OK"
        if command == "READ_TEMP":
            return f"TEMP:{self.temperature:.1f}"
        if command.startswith("SET_MODE "):
            mode = command.split(" ", 1)[1]
            if mode in {"AUTO", "MANUAL"}:
                self.mode = mode
                return f"MODE:{mode}"
            return "ERROR:BAD_MODE"
        if command == "GET_STATUS":
            return f"STATUS:{self.status}"
        return "ERROR:BAD_CMD"
