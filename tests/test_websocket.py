"""Tests for WebSocket ConnectionManager and /ws/tps endpoint."""
from __future__ import annotations

import os
import sys
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock

import pytest

# Ensure the plugin root is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


@pytest.fixture(autouse=True)
def mock_hermes_cli():
    """Mock hermes_cli for plugin import compatibility."""
    import types
    mod = types.ModuleType("hermes_cli")
    mod._ACTIVE_CLI_INSTANCE = None
    with patch.dict(sys.modules, {"hermes_cli": mod}):
        yield


@pytest.fixture
def store():
    """Create a temporary PersistentSessionStore for testing."""
    from store import PersistentSessionStore
    fd, path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    s = PersistentSessionStore(path)
    yield s
    s.close()
    try:
        os.unlink(path)
    except OSError:
        pass


@pytest.fixture
def app(store):
    """Create a FastAPI test app backed by the temp store."""
    from api import create_app
    return create_app(store)


@pytest.fixture
def client(app):
    """Create a TestClient for the FastAPI app."""
    from fastapi.testclient import TestClient
    return TestClient(app)


# ---------------------------------------------------------------------------
# ConnectionManager unit tests
# ---------------------------------------------------------------------------

class TestConnectionManager:

    def _make_mock_ws(self):
        """Create a mock WebSocket with async methods."""
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        ws.receive_text = AsyncMock()
        return ws

    @pytest.mark.anyio
    async def test_connect_adds_client(self):
        from api import ConnectionManager
        cm = ConnectionManager()
        ws = self._make_mock_ws()
        assert cm.count == 0
        await cm.connect(ws)
        assert cm.count == 1
        ws.accept.assert_awaited_once()

    @pytest.mark.anyio
    async def test_disconnect_removes_client(self):
        from api import ConnectionManager
        cm = ConnectionManager()
        ws = self._make_mock_ws()
        await cm.connect(ws)
        assert cm.count == 1
        cm.disconnect(ws)
        assert cm.count == 0

    @pytest.mark.anyio
    async def test_disconnect_idempotent(self):
        """Disconnecting a non-connected client doesn't raise."""
        from api import ConnectionManager
        cm = ConnectionManager()
        ws = self._make_mock_ws()
        cm.disconnect(ws)  # Should not raise
        assert cm.count == 0

    @pytest.mark.anyio
    async def test_broadcast_sends_to_all(self):
        from api import ConnectionManager
        cm = ConnectionManager()
        ws1 = self._make_mock_ws()
        ws2 = self._make_mock_ws()
        await cm.connect(ws1)
        await cm.connect(ws2)
        assert cm.count == 2

        msg = {"type": "test", "data": "hello"}
        await cm.broadcast(msg)

        ws1.send_json.assert_awaited_once_with(msg)
        ws2.send_json.assert_awaited_once_with(msg)

    @pytest.mark.anyio
    async def test_broadcast_handles_dead_client(self):
        """Dead clients are removed; live clients still receive messages."""
        from api import ConnectionManager
        cm = ConnectionManager()
        good_ws = self._make_mock_ws()
        dead_ws = self._make_mock_ws()
        dead_ws.send_json = AsyncMock(side_effect=ConnectionError("gone"))

        await cm.connect(good_ws)
        await cm.connect(dead_ws)
        assert cm.count == 2

        msg = {"type": "test"}
        await cm.broadcast(msg)

        # Good client still received the message
        good_ws.send_json.assert_awaited_once_with(msg)
        # Dead client was removed
        assert cm.count == 1

    @pytest.mark.anyio
    async def test_broadcast_empty_is_noop(self):
        """Broadcasting with no clients doesn't raise."""
        from api import ConnectionManager
        cm = ConnectionManager()
        await cm.broadcast({"type": "test"})  # Should not raise

    def test_count_property(self):
        from api import ConnectionManager
        cm = ConnectionManager()
        assert cm.count == 0


# ---------------------------------------------------------------------------
# broadcast_tps_update unit test
# ---------------------------------------------------------------------------

class TestBroadcastTPSUpdate:

    @pytest.mark.anyio
    async def test_wraps_snapshot_in_envelope(self):
        """broadcast_tps_update sends a typed message with data and timestamp."""
        from api import ConnectionManager, broadcast_tps_update
        cm = ConnectionManager()
        ws = MagicMock()
        ws.accept = AsyncMock()
        ws.send_json = AsyncMock()
        await cm.connect(ws)

        snapshot = {"session_id": "test", "last_tps": 42.0}
        await broadcast_tps_update(cm, snapshot)

        ws.send_json.assert_awaited_once()
        msg = ws.send_json.call_args[0][0]
        assert msg["type"] == "tps_update"
        assert msg["data"] == snapshot
        assert "timestamp" in msg


# ---------------------------------------------------------------------------
# WebSocket endpoint integration tests
# ---------------------------------------------------------------------------

class TestWebSocketEndpoint:

    def test_websocket_connect_disconnect(self, app):
        """Client can connect and disconnect from /ws/tps without errors."""
        from fastapi.testclient import TestClient
        client = TestClient(app)
        with client.websocket_connect("/ws/tps") as ws:
            # Connection established — send nothing, just disconnect
            pass
        # No exception means success

    def test_websocket_receives_broadcast(self, app):
        """Client receives TPS updates when broadcast is triggered."""
        from fastapi.testclient import TestClient
        from api import broadcast_tps_update
        import asyncio

        client = TestClient(app)
        manager = app.state.ws_manager

        with client.websocket_connect("/ws/tps") as ws:
            # Trigger a broadcast
            snapshot = {"session_id": "test-sess", "last_tps": 55.5}
            # We need to run the async broadcast in the event loop
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(broadcast_tps_update(manager, snapshot))
            finally:
                loop.close()

            # Client should receive the message
            data = ws.receive_json()
            assert data["type"] == "tps_update"
            assert data["data"]["session_id"] == "test-sess"
            assert data["data"]["last_tps"] == 55.5
            assert "timestamp" in data

    def test_websocket_message_format(self, app):
        """Messages have the correct type, data, and timestamp fields."""
        from fastapi.testclient import TestClient
        from api import broadcast_tps_update
        import asyncio

        client = TestClient(app)
        manager = app.state.ws_manager

        with client.websocket_connect("/ws/tps") as ws:
            snapshot = {"session_id": "fmt-test", "last_tps": 10.0, "peak_tps": 20.0}
            loop = asyncio.new_event_loop()
            try:
                loop.run_until_complete(broadcast_tps_update(manager, snapshot))
            finally:
                loop.close()

            data = ws.receive_json()
            assert data["type"] == "tps_update"
            assert isinstance(data["data"], dict)
            assert isinstance(data["timestamp"], str)
            assert "T" in data["timestamp"]  # ISO format contains T

    def test_multiple_clients_receive_broadcast(self, app):
        """All connected clients receive the same broadcast message."""
        from fastapi.testclient import TestClient
        from api import broadcast_tps_update
        import asyncio

        client = TestClient(app)
        manager = app.state.ws_manager

        with client.websocket_connect("/ws/tps") as ws1:
            with client.websocket_connect("/ws/tps") as ws2:
                assert manager.count == 2

                snapshot = {"session_id": "multi", "last_tps": 30.0}
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(broadcast_tps_update(manager, snapshot))
                finally:
                    loop.close()

                msg1 = ws1.receive_json()
                msg2 = ws2.receive_json()
                assert msg1["type"] == "tps_update"
                assert msg2["type"] == "tps_update"
                assert msg1["data"]["last_tps"] == 30.0
                assert msg2["data"]["last_tps"] == 30.0

    def test_websocket_disconnect_cleanup(self, app):
        """After disconnect, manager count drops to 0."""
        from fastapi.testclient import TestClient

        client = TestClient(app)
        manager = app.state.ws_manager

        with client.websocket_connect("/ws/tps") as ws:
            assert manager.count == 1
        # After exiting the context manager, connection is closed
        assert manager.count == 0
