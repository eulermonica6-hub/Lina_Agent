import socket
import threading
import time
from collections.abc import Iterator

import pytest
import uvicorn

from lina_agent.config import Settings
from lina_agent.main import create_app


@pytest.fixture(scope="session")
def live_server_url() -> Iterator[str]:
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(("127.0.0.1", 0))
    host, port = server_socket.getsockname()

    app = create_app(Settings(app_name="Lina Browser Test", environment="test"))
    server = uvicorn.Server(uvicorn.Config(app=app, log_level="warning"))
    thread = threading.Thread(
        target=server.run,
        kwargs={"sockets": [server_socket]},
        daemon=True,
    )
    thread.start()

    deadline = time.monotonic() + 10
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)

    if not server.started:
        server.should_exit = True
        thread.join(timeout=5)
        server_socket.close()
        raise RuntimeError("browser test server did not start within 10 seconds")

    try:
        yield f"http://{host}:{port}"
    finally:
        server.should_exit = True
        thread.join(timeout=10)
        server_socket.close()
        if thread.is_alive():
            raise RuntimeError("browser test server did not stop within 10 seconds")
