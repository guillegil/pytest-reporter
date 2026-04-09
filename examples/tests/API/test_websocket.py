"""WebSocket API tests demonstrating structured logging, procedure steps, and retry behavior."""

from __future__ import annotations

import time

import pytest

from pytest_reporter import step, substep


# ---------------------------------------------------------------------------
# Simulated WebSocket helpers
# ---------------------------------------------------------------------------

class _SimulatedWebSocket:
    """Fake WebSocket connection for testing without a real server."""

    def __init__(self, url: str, *, protocols: list[str] | None = None, headers: dict | None = None) -> None:
        self.url = url
        self.protocols = protocols or ["wss"]
        self.headers = headers or {}
        self.connected = False
        self.close_code: int | None = None
        self.close_reason: str | None = None
        self._sent: list[dict | str] = []
        self._recv_queue: list[dict | str] = []
        self._message_counter = 0

    def connect(self) -> dict:
        """Simulate the handshake."""
        self.connected = True
        return {
            "status": 101,
            "upgrade": "websocket",
            "connection": "Upgrade",
            "sec_websocket_accept": "s3pPLMBiTxaQ9kYGzzhZRbK+xOo=",
            "sec_websocket_protocol": self.protocols[0] if self.protocols else None,
        }

    def send(self, message: dict | str) -> None:
        if not self.connected:
            raise RuntimeError("WebSocket is not connected")
        self._sent.append(message)
        self._message_counter += 1
        # Echo back with acknowledgement
        if isinstance(message, dict):
            self._recv_queue.append({"type": "ack", "ref": message.get("id", self._message_counter), "status": "ok"})
        else:
            self._recv_queue.append(f"echo:{message}")

    def recv(self) -> dict | str:
        if not self.connected:
            raise RuntimeError("WebSocket is not connected")
        if self._recv_queue:
            return self._recv_queue.pop(0)
        return {"type": "heartbeat", "ts": "2026-04-02T12:00:00Z"}

    def close(self, code: int = 1000, reason: str = "Normal closure") -> None:
        self.connected = False
        self.close_code = code
        self.close_reason = reason

    def ping(self) -> str:
        if not self.connected:
            raise RuntimeError("WebSocket is not connected")
        return "pong"

    @property
    def sent_messages(self) -> list:
        return list(self._sent)


_CHAT_MESSAGES = [
    {"user": "alice", "text": "Hello everyone!", "room": "general", "ts": "2026-04-02T10:00:01Z"},
    {"user": "bob", "text": "Hi Alice!", "room": "general", "ts": "2026-04-02T10:00:03Z"},
    {"user": "carol", "text": "Good morning", "room": "general", "ts": "2026-04-02T10:00:05Z"},
    {"user": "alice", "text": "How is the deploy going?", "room": "engineering", "ts": "2026-04-02T10:01:00Z"},
    {"user": "david", "text": "Almost done, running final tests", "room": "engineering", "ts": "2026-04-02T10:01:15Z"},
]


_TICKER_DATA = [
    {"symbol": "AAPL", "price": 178.52, "volume": 42100, "ts": "2026-04-02T14:30:01Z"},
    {"symbol": "AAPL", "price": 178.61, "volume": 15300, "ts": "2026-04-02T14:30:02Z"},
    {"symbol": "GOOGL", "price": 155.30, "volume": 28700, "ts": "2026-04-02T14:30:01Z"},
    {"symbol": "GOOGL", "price": 155.28, "volume": 11200, "ts": "2026-04-02T14:30:02Z"},
    {"symbol": "MSFT", "price": 420.15, "volume": 33400, "ts": "2026-04-02T14:30:01Z"},
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_websocket_handshake(log) -> None:
    """Test the WebSocket connection handshake succeeds."""
    ws_log = log.child("websocket")
    handshake = log.child("handshake")

    with step("Initiate connection"):
        ws = _SimulatedWebSocket("wss://api.example.com/ws", protocols=["graphql-ws"])
        ws_log.info("Connecting", data={"url": ws.url, "protocols": ws.protocols})
        ws_log.debug("Request headers", data={"Origin": "https://app.example.com", "Sec-WebSocket-Version": "13"})

    with step("Perform handshake"):
        time.sleep(0.001)
        resp = ws.connect()
        handshake.info("Handshake response", data=resp)
        handshake.debug("Protocol negotiation", data={"requested": ws.protocols, "accepted": resp["sec_websocket_protocol"]})

    with step("Validate handshake"):
        substep("Check 101 Switching Protocols")
        handshake.info("Status code", data={"expected": 101, "actual": resp["status"]})
        assert resp["status"] == 101

        substep("Check Upgrade header")
        handshake.info("Upgrade header", data={"value": resp["upgrade"]})
        assert resp["upgrade"] == "websocket"

        substep("Check connection is open")
        ws_log.info("Connection state", data={"connected": ws.connected})
        assert ws.connected is True
        ws_log.info("Handshake completed successfully")

    ws.close()


def test_send_and_receive_message(log) -> None:
    """Test basic send/receive cycle over WebSocket."""
    ws_log = log.child("websocket")
    messaging = log.child("messaging")

    ws = _SimulatedWebSocket("wss://api.example.com/ws")
    ws.connect()

    with step("Send message"):
        message = {"id": 1, "type": "subscribe", "channel": "notifications"}
        messaging.info("Sending message", data=message)
        ws.send(message)
        messaging.debug("Message queued", data={"buffer_size": len(ws.sent_messages)})

    with step("Receive acknowledgement"):
        time.sleep(0.001)
        response = ws.recv()
        messaging.info("Response received", data={"response": response})
        messaging.debug("Response type", data={"type": response.get("type") if isinstance(response, dict) else "text"})

    with step("Validate response"):
        assert isinstance(response, dict)
        assert response["type"] == "ack"
        assert response["status"] == "ok"
        messaging.info("Send/receive cycle verified")

    ws.close()


@pytest.mark.parametrize(
    "channel,expected_messages",
    [
        ("general", 3),
        ("engineering", 2),
        ("random", 0),
    ],
    ids=["general-channel", "engineering-channel", "empty-channel"],
)
def test_channel_subscription(log, channel: str, expected_messages: int) -> None:
    """Test subscribing to a chat channel and receiving messages."""
    ws_log = log.child("websocket")
    sub = log.child("subscription")

    ws = _SimulatedWebSocket("wss://chat.example.com/ws")
    ws.connect()

    with step("Subscribe to channel"):
        sub_msg = {"id": 1, "type": "subscribe", "channel": channel}
        ws.send(sub_msg)
        ws_log.info("Subscribed", data={"channel": channel})
        sub.debug("Subscription details", data=sub_msg)

    with step("Receive channel messages"):
        messages = [m for m in _CHAT_MESSAGES if m["room"] == channel]
        sub.info("Messages available", data={"channel": channel, "count": len(messages)})
        for msg in messages:
            sub.debug("Message", data=msg)

    with step("Validate message count"):
        sub.info("Comparing counts", data={"expected": expected_messages, "actual": len(messages)})
        assert len(messages) == expected_messages
        sub.info(f"Channel '{channel}' returned correct message count")

    ws.close()


def test_ping_pong_keepalive(log) -> None:
    """Test WebSocket ping/pong keepalive mechanism."""
    ws_log = log.child("websocket")
    keepalive = log.child("keepalive")

    ws = _SimulatedWebSocket("wss://api.example.com/ws")
    ws.connect()

    with step("Send ping frames"):
        for i in range(3):
            keepalive.info(f"Sending ping {i + 1}", data={"sequence": i + 1})
            pong = ws.ping()
            keepalive.debug(f"Pong received", data={"response": pong, "latency_ms": 2 + i})
            time.sleep(0.001)

    with step("Validate pong responses"):
        keepalive.info("All pings answered", data={"ping_count": 3})
        assert ws.connected
        keepalive.info("Keepalive mechanism working")

    ws.close()


def test_graceful_close(log) -> None:
    """Test graceful WebSocket close with status codes."""
    ws_log = log.child("websocket")
    close_log = log.child("close")

    ws = _SimulatedWebSocket("wss://api.example.com/ws")
    ws.connect()
    ws_log.info("Connection established", data={"url": ws.url})

    with step("Send close frame"):
        close_log.info("Initiating close", data={"code": 1000, "reason": "Client done"})
        ws.close(code=1000, reason="Client done")
        close_log.debug("Close frame sent", data={"connected_after": ws.connected})

    with step("Validate close state"):
        substep("Check disconnected")
        close_log.info("Connection state", data={"connected": ws.connected})
        assert ws.connected is False

        substep("Check close code")
        close_log.info("Close code", data={"code": ws.close_code})
        assert ws.close_code == 1000

        substep("Check close reason")
        close_log.info("Close reason", data={"reason": ws.close_reason})
        assert ws.close_reason == "Client done"
        close_log.info("Graceful close verified")


@pytest.mark.parametrize(
    "close_code,close_reason,description",
    [
        (1000, "Normal closure", "normal"),
        (1001, "Going away", "going-away"),
        (1008, "Policy violation", "policy"),
        (1011, "Internal error", "internal-error"),
    ],
    ids=["normal", "going-away", "policy-violation", "internal-error"],
)
def test_close_codes(log, close_code: int, close_reason: str, description: str) -> None:
    """Test various WebSocket close codes."""
    ws_log = log.child("websocket")
    close_log = log.child("close")

    ws = _SimulatedWebSocket("wss://api.example.com/ws")
    ws.connect()

    with step("Close with specific code"):
        close_log.info("Closing connection", data={"code": close_code, "reason": close_reason, "description": description})
        ws.close(code=close_code, reason=close_reason)
        close_log.debug("Connection terminated", data={"connected": ws.connected})

    with step("Verify close code"):
        close_log.info("Validating close code", data={"expected": close_code, "actual": ws.close_code})
        assert ws.close_code == close_code
        assert ws.close_reason == close_reason
        close_log.info(f"Close code {close_code} ({description}) handled correctly")


def test_stock_ticker_stream(log) -> None:
    """Test streaming stock ticker data over WebSocket."""
    ws_log = log.child("websocket")
    ticker = log.child("ticker")

    ws = _SimulatedWebSocket("wss://market.example.com/stream")
    ws.connect()

    with step("Subscribe to ticker feed"):
        sub_msg = {"type": "subscribe", "symbols": ["AAPL", "GOOGL", "MSFT"]}
        ws.send(sub_msg)
        ws_log.info("Subscribed to ticker", data=sub_msg)
        ticker.debug("Subscription confirmed", data={"symbols": sub_msg["symbols"]})

    with step("Process ticker updates"):
        for tick in _TICKER_DATA:
            ticker.info("Tick received", data=tick)
            ticker.debug("Price analysis", data={
                "symbol": tick["symbol"],
                "price": tick["price"],
                "volume": tick["volume"],
                "above_threshold": tick["volume"] > 20000,
            })
            time.sleep(0.001)
        ticker.info("Stream processing complete", data={"total_ticks": len(_TICKER_DATA)})

    with step("Validate ticker data"):
        substep("Check all symbols present")
        symbols = {t["symbol"] for t in _TICKER_DATA}
        ticker.info("Unique symbols", data={"symbols": sorted(symbols)})
        assert "AAPL" in symbols
        assert "GOOGL" in symbols
        assert "MSFT" in symbols

        substep("Check prices are positive")
        for tick in _TICKER_DATA:
            assert tick["price"] > 0
        ticker.info("All ticker prices valid")

    ws.close()


def test_binary_frame_handling(log) -> None:
    """Test sending and receiving binary frames."""
    ws_log = log.child("websocket")
    binary = log.child("binary")

    ws = _SimulatedWebSocket("wss://api.example.com/ws")
    ws.connect()

    with step("Send binary payload"):
        payload = b"\x00\x01\x02\x03\x04\x05\x06\x07"
        binary.info("Sending binary frame", data={"size_bytes": len(payload), "hex_preview": payload[:4].hex()})
        ws.send({"type": "binary", "data": payload.hex(), "size": len(payload)})
        binary.debug("Binary frame queued", data={"opcode": 2, "fin": True, "mask": True})

    with step("Receive binary response"):
        response = ws.recv()
        binary.info("Response received", data={"response": response})
        ws_log.debug("Frame metadata", data={"type": "binary", "compressed": False})

    with step("Validate response"):
        assert isinstance(response, dict)
        assert response["type"] == "ack"
        binary.info("Binary frame round-trip successful")

    ws.close()


def test_message_ordering(log) -> None:
    """Test that messages maintain their send order."""
    ws_log = log.child("websocket")
    ordering = log.child("ordering")

    ws = _SimulatedWebSocket("wss://api.example.com/ws")
    ws.connect()

    with step("Send ordered messages"):
        for i in range(5):
            msg = {"id": i, "type": "data", "payload": f"message_{i}"}
            ws.send(msg)
            ordering.debug(f"Sent message {i}", data=msg)
        ordering.info("All messages sent", data={"count": 5})

    with step("Verify send order"):
        sent = ws.sent_messages
        ordering.info("Sent message IDs", data={"ids": [m["id"] for m in sent]})
        for i, msg in enumerate(sent):
            substep(f"Check message {i}")
            ordering.debug(f"Message {i}", data={"expected_id": i, "actual_id": msg["id"]})
            assert msg["id"] == i
        ordering.info("Message ordering preserved")

    ws.close()


def test_reconnection_logic(log) -> None:
    """Test automatic reconnection after disconnect."""
    ws_log = log.child("websocket")
    reconnect = log.child("reconnect")

    with step("Establish initial connection"):
        ws = _SimulatedWebSocket("wss://api.example.com/ws")
        ws.connect()
        ws_log.info("Connected", data={"url": ws.url, "connected": ws.connected})

    with step("Simulate disconnect"):
        ws.close(code=1006, reason="Abnormal closure")
        reconnect.warning("Connection lost", data={"code": ws.close_code, "reason": ws.close_reason})
        reconnect.info("Initiating reconnection", data={"backoff_ms": 500, "attempt": 1})

    with step("Reconnect"):
        time.sleep(0.001)
        ws2 = _SimulatedWebSocket("wss://api.example.com/ws")
        resp = ws2.connect()
        reconnect.info("Reconnected", data={"status": resp["status"]})
        ws_log.debug("New connection details", data=resp)

    with step("Verify new connection"):
        assert ws2.connected is True
        assert ws2.close_code is None
        reconnect.info("Reconnection successful, session restored")

    ws2.close()


@pytest.mark.parametrize(
    "protocol",
    ["graphql-ws", "graphql-transport-ws", "stomp"],
    ids=["graphql-ws", "graphql-transport-ws", "stomp"],
)
def test_subprotocol_negotiation(log, protocol: str) -> None:
    """Test WebSocket subprotocol negotiation."""
    ws_log = log.child("websocket")
    proto = log.child("protocol")

    with step("Connect with subprotocol"):
        ws = _SimulatedWebSocket("wss://api.example.com/ws", protocols=[protocol])
        ws_log.info("Requesting protocol", data={"protocol": protocol})
        resp = ws.connect()
        proto.info("Negotiation response", data={"requested": protocol, "accepted": resp["sec_websocket_protocol"]})
        proto.debug("Full handshake", data=resp)

    with step("Validate protocol selection"):
        accepted = resp["sec_websocket_protocol"]
        proto.info("Protocol accepted", data={"protocol": accepted})
        assert accepted == protocol
        proto.info(f"Subprotocol '{protocol}' negotiated successfully")

    ws.close()


def test_heartbeat_timeout_detection(log) -> None:
    """Test heartbeat timeout detection when server stops responding."""
    ws_log = log.child("websocket")
    heartbeat = log.child("heartbeat")

    ws = _SimulatedWebSocket("wss://api.example.com/ws")
    ws.connect()

    with step("Monitor heartbeats"):
        heartbeat_count = 0
        for i in range(4):
            msg = ws.recv()
            heartbeat_count += 1
            heartbeat.info(f"Heartbeat {heartbeat_count}", data={"message": msg, "interval_ms": 5000})
            heartbeat.debug("Timing", data={"expected_next_ms": 5000, "jitter_ms": 100})

    with step("Simulate timeout"):
        simulated_gap_ms = 15200
        heartbeat.warning("Heartbeat gap detected", data={"gap_ms": simulated_gap_ms, "threshold_ms": 15000})
        heartbeat.info("Triggering reconnect due to timeout")
        timed_out = simulated_gap_ms > 15000
        assert timed_out
        heartbeat.info("Heartbeat timeout detection working")

    ws.close()


def test_concurrent_subscriptions(log) -> None:
    """Test managing multiple concurrent subscriptions."""
    ws_log = log.child("websocket")
    sub_log = log.child("subscriptions")

    ws = _SimulatedWebSocket("wss://api.example.com/ws")
    ws.connect()

    channels = ["orders", "inventory", "alerts", "analytics"]

    with step("Subscribe to multiple channels"):
        for channel in channels:
            msg = {"type": "subscribe", "channel": channel}
            ws.send(msg)
            sub_log.info(f"Subscribed to {channel}", data=msg)
        sub_log.info("All subscriptions active", data={"channels": channels, "count": len(channels)})

    with step("Receive from each channel"):
        for channel in channels:
            response = ws.recv()
            sub_log.debug(f"Message from {channel}", data={"response": response})
        ws_log.info("Received messages from all channels", data={"count": len(channels)})

    with step("Validate subscription count"):
        assert len(ws.sent_messages) == len(channels)
        sub_log.info("Concurrent subscription management verified")

    ws.close()


@pytest.mark.parametrize(
    "payload_size_kb",
    [1, 10, 64, 128],
    ids=["1kb", "10kb", "64kb", "128kb"],
)
def test_payload_size_handling(log, payload_size_kb: int) -> None:
    """Test handling various message payload sizes."""
    ws_log = log.child("websocket")
    payload_log = log.child("payload")

    ws = _SimulatedWebSocket("wss://api.example.com/ws")
    ws.connect()

    with step("Generate payload"):
        payload = "x" * (payload_size_kb * 1024)
        payload_log.info("Payload generated", data={"size_kb": payload_size_kb, "size_bytes": len(payload)})
        payload_log.debug("Payload stats", data={"is_text": True, "needs_fragmentation": payload_size_kb > 64})

    with step("Send large message"):
        ws.send({"type": "data", "payload_size": len(payload)})
        ws_log.info("Message sent", data={"size_kb": payload_size_kb})
        time.sleep(0.001)

    with step("Validate delivery"):
        assert len(ws.sent_messages) == 1
        payload_log.info(f"Payload of {payload_size_kb}KB delivered successfully")

    ws.close()


@pytest.mark.skip(reason="Compression extension not yet supported")
def test_permessage_deflate(log) -> None:
    """Test per-message deflate compression extension."""
    ws_log = log.child("websocket")
    ws_log.info("This test is skipped")


@pytest.mark.skip(reason="Multiplexing draft spec in review")
def test_multiplexing_extension(log) -> None:
    """Test WebSocket multiplexing extension."""
    ws_log = log.child("websocket")
    ws_log.info("This test is skipped")


# --- Flaky service / retry tests ---


def test_websocket_connect_retry(log, flaky_service) -> None:
    """Test WebSocket connection retries on transient server error."""
    ws_log = log.child("websocket")
    retry = log.child("retry")

    with step("Attempt initial connection"):
        ws_log.info("Connecting to wss://api.example.com/ws", data={"attempt": 1})
        try:
            flaky_service("ws_connect")
        except ConnectionError as exc:
            retry.warning("Connection refused", data={"error": str(exc), "server": "api.example.com"}, exc_info=exc)

    with step("Retry connection"):
        retry.info("Retrying with exponential backoff", data={"attempt": 2, "backoff_ms": 1000})
        time.sleep(0.001)
        result = flaky_service("ws_connect")
        ws_log.info("Connected on retry", data={"result": result})

    with step("Validate connection"):
        assert result == "ok:ws_connect"
        retry.info("WebSocket connection retry succeeded")


def test_subscription_recovery_after_disconnect(log, flaky_service) -> None:
    """Test that subscriptions are restored after reconnection."""
    ws_log = log.child("websocket")
    recovery = log.child("recovery")

    with step("Establish connection and subscribe"):
        ws = _SimulatedWebSocket("wss://api.example.com/ws")
        ws.connect()
        ws.send({"type": "subscribe", "channel": "orders"})
        ws_log.info("Subscribed to orders channel", data={"connected": ws.connected})

    with step("Simulate disconnect"):
        ws.close(code=1006, reason="Connection lost")
        recovery.warning("Connection dropped", data={"code": ws.close_code})
        try:
            flaky_service("ws_recovery")
        except ConnectionError as exc:
            recovery.warning("Reconnection failed", data={"error": str(exc)}, exc_info=exc)

    with step("Retry and restore subscription"):
        recovery.info("Retrying connection", data={"attempt": 2})
        result = flaky_service("ws_recovery")
        recovery.info("Connection restored", data={"result": result})
        ws2 = _SimulatedWebSocket("wss://api.example.com/ws")
        ws2.connect()
        ws2.send({"type": "subscribe", "channel": "orders"})
        ws_log.info("Subscription restored", data={"channel": "orders"})

    with step("Verify recovery"):
        assert ws2.connected
        assert result == "ok:ws_recovery"
        recovery.info("Subscription recovery after disconnect verified")

    ws2.close()


def test_stream_reconnect_with_resume(log, flaky_service) -> None:
    """Test stream resume after transient disconnection."""
    ws_log = log.child("websocket")
    stream = log.child("stream")

    with step("Start stream"):
        ws = _SimulatedWebSocket("wss://stream.example.com/feed")
        ws.connect()
        last_event_id = "evt_00042"
        stream.info("Stream started", data={"last_event_id": last_event_id})

    with step("Simulate stream interruption"):
        ws.close(code=1006, reason="Network error")
        stream.warning("Stream interrupted", data={"last_event_id": last_event_id})
        try:
            flaky_service("ws_stream_resume")
        except ConnectionError as exc:
            stream.warning("Resume failed", data={"error": str(exc)}, exc_info=exc)

    with step("Resume stream"):
        result = flaky_service("ws_stream_resume")
        stream.info("Stream resumed", data={"result": result, "resume_from": last_event_id})
        ws2 = _SimulatedWebSocket("wss://stream.example.com/feed")
        ws2.connect()
        ws_log.info("Stream connection restored")

    with step("Verify stream continuity"):
        assert result == "ok:ws_stream_resume"
        assert ws2.connected
        stream.info("Stream resume verified, no events lost")

    ws2.close()


# --- Deliberate failures ---


def test_max_connections_exceeded(log) -> None:
    """Test server rejects connections above limit (deliberately fails)."""
    ws_log = log.child("websocket")
    limits = log.child("limits")

    connections = []

    with step("Open many connections"):
        for i in range(10):
            ws = _SimulatedWebSocket(f"wss://api.example.com/ws?client={i}")
            ws.connect()
            connections.append(ws)
            limits.debug(f"Connection {i + 1} opened", data={"client": i, "total": len(connections)})
        limits.info("All connections open", data={"count": len(connections)})

    with step("Verify server enforces limit"):
        max_allowed = 5
        limits.error(
            "Connection limit exceeded",
            data={"open_connections": len(connections), "max_allowed": max_allowed},
        )
        assert len(connections) <= max_allowed, (
            f"Server accepted {len(connections)} connections but max allowed is {max_allowed}"
        )

    for ws in connections:
        ws.close()


def test_message_size_limit_enforcement(log) -> None:
    """Test server rejects oversized messages (deliberately fails)."""
    ws_log = log.child("websocket")
    size_log = log.child("size_limit")

    ws = _SimulatedWebSocket("wss://api.example.com/ws")
    ws.connect()

    with step("Send oversized message"):
        max_size_kb = 256
        payload_size_kb = 512
        payload = {"type": "data", "payload": "x" * (payload_size_kb * 1024)}
        ws.send(payload)
        size_log.info("Sent oversized message", data={"size_kb": payload_size_kb, "limit_kb": max_size_kb})
        ws_log.debug("Message details", data={"type": "data", "size_bytes": payload_size_kb * 1024})

    with step("Verify message was rejected"):
        # Our sim accepts everything, so this will fail
        was_rejected = len(ws.sent_messages) == 0
        size_log.warning(
            "Oversized message was not rejected",
            data={"sent_count": len(ws.sent_messages), "expected": 0},
        )
        assert was_rejected, (
            f"Server accepted a {payload_size_kb}KB message "
            f"but the limit is {max_size_kb}KB"
        )

    ws.close()
