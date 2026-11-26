"""REST API endpoint tests demonstrating structured logging, procedure steps, and retry behavior."""

from __future__ import annotations

import logging
import time

import pytest

from stepdoc import step

log = logging.getLogger("endpoints")


# ---------------------------------------------------------------------------
# Simulated HTTP helpers
# ---------------------------------------------------------------------------

_USERS_DB = [
    {"id": 1, "name": "Alice Park", "email": "alice@example.com", "role": "admin"},
    {"id": 2, "name": "Bob Tran", "email": "bob@example.com", "role": "editor"},
    {"id": 3, "name": "Carol Diaz", "email": "carol@example.com", "role": "viewer"},
    {"id": 4, "name": "David Kim", "email": "david@example.com", "role": "editor"},
    {"id": 5, "name": "Eve Novak", "email": "eve@example.com", "role": "viewer"},
]


def _sim_request(method: str, path: str, *, body: dict | None = None, headers: dict | None = None) -> dict:
    """Return a simulated HTTP response dict."""
    default_headers = {
        "Content-Type": "application/json",
        "X-Request-Id": "req_a1b2c3d4",
        "X-RateLimit-Limit": "1000",
        "X-RateLimit-Remaining": "997",
        "X-RateLimit-Reset": "1711929600",
    }
    if headers:
        default_headers.update(headers)

    if method == "GET" and path == "/api/v1/users":
        return {"status": 200, "headers": default_headers, "body": _USERS_DB}
    if method == "GET" and path.startswith("/api/v1/users/"):
        uid = int(path.rsplit("/", 1)[-1])
        user = next((u for u in _USERS_DB if u["id"] == uid), None)
        if user:
            return {"status": 200, "headers": default_headers, "body": user}
        return {"status": 404, "headers": default_headers, "body": {"error": "Not found"}}
    if method == "POST" and path == "/api/v1/users":
        new_user = {**body, "id": 6} if body else {"id": 6}
        return {"status": 201, "headers": default_headers, "body": new_user}
    if method == "PUT" and path.startswith("/api/v1/users/"):
        return {"status": 200, "headers": default_headers, "body": {**(body or {}), "updated": True}}
    if method == "DELETE" and path.startswith("/api/v1/users/"):
        return {"status": 204, "headers": default_headers, "body": None}
    if method == "PATCH" and path.startswith("/api/v1/users/"):
        return {"status": 200, "headers": default_headers, "body": {**(body or {}), "patched": True}}
    if method == "GET" and path == "/api/v1/health":
        return {"status": 200, "headers": default_headers, "body": {"status": "healthy", "uptime_seconds": 86412}}
    return {"status": 405, "headers": default_headers, "body": {"error": "Method not allowed"}}


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path,expected_status",
    [
        ("GET", "/api/v1/users", 200),
        ("POST", "/api/v1/users", 201),
        ("GET", "/api/v1/users/1", 200),
        ("PUT", "/api/v1/users/1", 200),
        ("DELETE", "/api/v1/users/1", 204),
        ("GET", "/api/v1/users/999", 404),
    ],
    ids=["list-users", "create-user", "get-user", "update-user", "delete-user", "not-found"],
)
def test_crud_status_codes(method: str, path: str, expected_status: int) -> None:
    """Verify each CRUD operation returns the correct HTTP status."""
    http = log.getChild("http")
    validation = log.getChild("validation")

    with step("Prepare request"):
        http.info("Building request", extra={"method": method, "path": path})
        http.debug("Setting default headers", extra={"Accept": "application/json", "User-Agent": "test-client/1.0"})
        with step("Attach auth token"):
            http.info("Bearer token attached", extra={"token_prefix": "eyJhbGci..."})

    with step("Send request"):
        time.sleep(0.001)
        resp = _sim_request(method, path, body={"name": "New User", "email": "new@example.com"})
        http.info("Response received", extra={"status": resp["status"], "request_id": resp["headers"]["X-Request-Id"]})
        http.debug("Response headers", extra={"data": resp["headers"]})
        if resp["body"] is not None:
            http.debug("Response body preview", extra={"body": resp["body"] if isinstance(resp["body"], dict) else {"count": len(resp["body"])}})

    with step("Validate status code"):
        validation.info("Comparing status", extra={"expected": expected_status, "actual": resp["status"]})
        assert resp["status"] == expected_status
        validation.info("Status code matches")


def test_list_users_pagination() -> None:
    """Test paginated user listing with offset and limit."""
    http = log.getChild("http")
    pagination = log.getChild("pagination")

    with step("Request first page"):
        http.info("GET /api/v1/users", extra={"params": {"offset": 0, "limit": 2}})
        time.sleep(0.001)
        page1 = _USERS_DB[:2]
        http.info("Page 1 received", extra={"count": len(page1), "users": [u["name"] for u in page1]})
        pagination.debug("Cursor state", extra={"offset": 0, "limit": 2, "total": 5, "has_next": True})

    with step("Request second page"):
        http.info("GET /api/v1/users", extra={"params": {"offset": 2, "limit": 2}})
        page2 = _USERS_DB[2:4]
        http.info("Page 2 received", extra={"count": len(page2), "users": [u["name"] for u in page2]})
        pagination.debug("Cursor state", extra={"offset": 2, "limit": 2, "total": 5, "has_next": True})

    with step("Request last page"):
        http.info("GET /api/v1/users", extra={"params": {"offset": 4, "limit": 2}})
        page3 = _USERS_DB[4:]
        http.info("Page 3 received", extra={"count": len(page3), "users": [u["name"] for u in page3]})
        pagination.debug("Cursor state", extra={"offset": 4, "limit": 2, "total": 5, "has_next": False})

    with step("Verify all pages cover full dataset"):
        all_users = page1 + page2 + page3
        pagination.info("Aggregated results", extra={"total_fetched": len(all_users), "expected": 5})
        assert len(all_users) == 5
        pagination.info("Pagination verified: all users returned across pages")


def test_rate_limit_headers() -> None:
    """Verify rate-limit headers are present and correctly decremented."""
    http = log.getChild("http")
    rate_limit = log.getChild("rate_limit")

    with step("Send initial request"):
        resp = _sim_request("GET", "/api/v1/users")
        http.info("Response received", extra={"status": resp["status"]})
        http.debug("All headers", extra={"data": resp["headers"]})

    with step("Extract rate-limit headers"):
        limit = int(resp["headers"]["X-RateLimit-Limit"])
        remaining = int(resp["headers"]["X-RateLimit-Remaining"])
        reset_ts = int(resp["headers"]["X-RateLimit-Reset"])
        rate_limit.info("Parsed rate-limit values", extra={"limit": limit, "remaining": remaining, "reset": reset_ts})

    with step("Validate rate-limit values"):
        with step("Check limit is positive"):
            rate_limit.info("Limit value", extra={"value": limit})
            assert limit > 0

        with step("Check remaining is within bounds"):
            rate_limit.info("Remaining value", extra={"value": remaining, "max": limit})
            assert 0 <= remaining <= limit

        with step("Check reset timestamp is in the future"):
            rate_limit.info("Reset timestamp", extra={"value": reset_ts})
            assert reset_ts > 0
            rate_limit.info("All rate-limit headers valid")


def test_create_user_with_validation() -> None:
    """Test user creation validates required fields and returns the new resource."""
    http = log.getChild("http")
    validation = log.getChild("validation")

    payload = {"name": "Frank Lee", "email": "frank@example.com", "role": "editor"}

    with step("Validate request payload"):
        validation.info("Checking required fields", extra={"payload": payload})
        for field in ("name", "email", "role"):
            with step(f"Verify field: {field}"):
                validation.debug(f"Field '{field}' present", extra={"value": payload[field]})
                assert field in payload
        validation.info("Payload validation passed")

    with step("Send POST request"):
        time.sleep(0.001)
        resp = _sim_request("POST", "/api/v1/users", body=payload)
        http.info("User creation response", extra={"status": resp["status"], "body": resp["body"]})
        http.debug("Response latency", extra={"ms": 42})

    with step("Verify response"):
        with step("Check 201 status"):
            validation.info("Status code", extra={"expected": 201, "actual": resp["status"]})
            assert resp["status"] == 201

        with step("Check returned user has an ID"):
            validation.info("New user ID", extra={"id": resp["body"]["id"]})
            assert "id" in resp["body"]
            validation.info("User creation verified successfully")


@pytest.mark.parametrize(
    "content_type,accepted",
    [
        ("application/json", True),
        ("application/xml", False),
        ("text/plain", False),
        ("application/json; charset=utf-8", True),
    ],
    ids=["json", "xml", "plaintext", "json-charset"],
)
def test_content_type_negotiation(content_type: str, accepted: bool) -> None:
    """Verify the API only accepts supported content types."""
    http = log.getChild("http")
    negotiation = log.getChild("negotiation")

    with step("Send request with content type"):
        http.info("Preparing request", extra={"Content-Type": content_type})
        http.debug("Request details", extra={"method": "POST", "path": "/api/v1/users", "content_type": content_type})
        time.sleep(0.001)
        is_json = content_type.startswith("application/json")
        negotiation.info("Content type check", extra={"content_type": content_type, "is_json": is_json})

    with step("Validate acceptance"):
        negotiation.info("Comparing result", extra={"expected_accepted": accepted, "actual_accepted": is_json})
        assert is_json == accepted
        negotiation.info("Content negotiation behaves correctly")


def test_health_endpoint() -> None:
    """Test /health returns uptime and status."""
    http = log.getChild("http")
    health = log.getChild("health")

    with step("Request health endpoint"):
        resp = _sim_request("GET", "/api/v1/health")
        http.info("Health response", extra={"status": resp["status"]})
        http.debug("Full response", extra={"data": resp["body"]})

    with step("Validate health payload"):
        body = resp["body"]
        with step("Check status field"):
            health.info("Status value", extra={"status": body["status"]})
            assert body["status"] == "healthy"

        with step("Check uptime"):
            health.info("Uptime", extra={"seconds": body["uptime_seconds"]})
            assert body["uptime_seconds"] > 0
            health.info("Health check passed")


def test_update_user_partial() -> None:
    """Test PATCH for partial user update."""
    http = log.getChild("http")
    validation = log.getChild("validation")

    patch_data = {"email": "alice_new@example.com"}

    with step("Fetch current user"):
        resp = _sim_request("GET", "/api/v1/users/1")
        http.info("Current user data", extra={"data": resp["body"]})
        original_email = resp["body"]["email"]
        validation.debug("Original email", extra={"email": original_email})

    with step("Send PATCH request"):
        resp = _sim_request("PATCH", "/api/v1/users/1", body=patch_data)
        http.info("Patch response", extra={"status": resp["status"], "body": resp["body"]})
        time.sleep(0.001)

    with step("Verify partial update applied"):
        validation.info("Checking patched flag", extra={"patched": resp["body"].get("patched")})
        assert resp["body"]["patched"] is True
        validation.info("Partial update verified")


def test_delete_returns_no_content() -> None:
    """Test DELETE returns 204 with no body."""
    http = log.getChild("http")

    with step("Send DELETE request"):
        http.info("Deleting user", extra={"user_id": 3})
        resp = _sim_request("DELETE", "/api/v1/users/3")
        http.info("Delete response", extra={"status": resp["status"]})
        http.debug("Response body", extra={"body": resp["body"]})

    with step("Validate 204 No Content"):
        assert resp["status"] == 204
        assert resp["body"] is None
        http.info("Delete confirmed: 204 with empty body")


@pytest.mark.parametrize(
    "header_name,header_value",
    [
        ("Authorization", "Bearer eyJhbGciOiJIUzI1NiJ9.test"),
        ("X-Correlation-Id", "corr-abc-123-def"),
        ("X-Idempotency-Key", "idem-key-20260402-001"),
    ],
    ids=["auth-bearer", "correlation-id", "idempotency-key"],
)
def test_custom_headers_forwarded(header_name: str, header_value: str) -> None:
    """Verify custom headers are properly forwarded."""
    http = log.getChild("http")
    headers_log = log.getChild("headers")

    with step("Build request with custom header"):
        custom = {header_name: header_value}
        http.info("Request headers", extra={"data": custom})
        headers_log.debug("Header details", extra={"data": {"name": header_name, "value_length": len(header_value)}})

    with step("Send request"):
        resp = _sim_request("GET", "/api/v1/users", headers=custom)
        http.info("Response received", extra={"status": resp["status"]})
        time.sleep(0.001)

    with step("Validate header echo"):
        echoed = resp["headers"].get(header_name)
        headers_log.info("Header echoed", extra={"data": {"name": header_name, "echoed": echoed is not None or header_name in resp["headers"]}})
        # Custom headers are merged into response headers in our sim
        assert header_name in resp["headers"]
        headers_log.info("Custom header forwarded correctly")


def test_error_response_structure() -> None:
    """Verify error responses have the correct JSON structure."""
    http = log.getChild("http")
    error_log = log.getChild("error_handling")

    with step("Request a non-existent resource"):
        resp = _sim_request("GET", "/api/v1/users/999")
        http.info("Error response", extra={"status": resp["status"], "body": resp["body"]})

    with step("Validate error structure"):
        with step("Check 404 status"):
            error_log.info("Status code", extra={"expected": 404, "actual": resp["status"]})
            assert resp["status"] == 404

        with step("Check error field present"):
            error_log.info("Error body", extra={"data": resp["body"]})
            assert "error" in resp["body"]

        with step("Check error message"):
            error_log.info("Error message", extra={"data": {"message": resp["body"]["error"]}})
            assert resp["body"]["error"] == "Not found"
            error_log.info("Error response structure is correct")


def test_method_not_allowed() -> None:
    """Test that unsupported methods return 405."""
    http = log.getChild("http")

    with step("Send unsupported method"):
        http.info("Sending OPTIONS to /api/v1/users")
        resp = _sim_request("OPTIONS", "/api/v1/users")
        http.info("Response", extra={"status": resp["status"], "body": resp["body"]})

    with step("Validate 405"):
        assert resp["status"] == 405
        http.info("Method not allowed confirmed")


@pytest.mark.parametrize(
    "search_term,expected_count",
    [
        ("alice", 1),
        ("editor", 2),
        ("nonexistent", 0),
    ],
    ids=["by-name", "by-role", "no-match"],
)
def test_user_search(search_term: str, expected_count: int) -> None:
    """Test user search/filter functionality."""
    http = log.getChild("http")
    search = log.getChild("search")

    with step("Perform search"):
        http.info("Searching users", extra={"query": search_term})
        results = [u for u in _USERS_DB if search_term.lower() in str(u).lower()]
        search.info("Search results", extra={"query": search_term, "matches": len(results)})
        search.debug("Matched users", extra={"users": [u["name"] for u in results]})

    with step("Validate result count"):
        search.info("Comparing counts", extra={"expected": expected_count, "actual": len(results)})
        assert len(results) == expected_count
        search.info("Search results match expected count")


@pytest.mark.skip(reason="Batch endpoint not yet implemented")
def test_batch_create_users() -> None:
    """Test batch user creation endpoint."""
    http = log.getChild("http")
    http.info("This test is skipped")


@pytest.mark.skip(reason="Export feature pending review")
def test_export_users_csv() -> None:
    """Test CSV export of user data."""
    http = log.getChild("http")
    http.info("This test is skipped")


# --- Flaky service / retry tests ---


def test_user_service_retry_on_connection_error(flaky_service) -> None:
    """Test that the user service retries on transient connection errors."""
    http = log.getChild("http")
    retry_log = log.getChild("retry")

    with step("Attempt initial request"):
        http.info("Calling user service", extra={"endpoint": "/api/v1/users", "attempt": 1})
        try:
            flaky_service("endpoint_users")
        except ConnectionError as exc:
            retry_log.warning("Connection failed, will retry", extra={"error": str(exc)}, exc_info=exc)

    with step("Retry request"):
        retry_log.info("Retrying after backoff", extra={"backoff_ms": 100, "attempt": 2})
        time.sleep(0.001)
        result = flaky_service("endpoint_users")
        http.info("Retry succeeded", extra={"result": result})

    with step("Validate successful response"):
        assert result == "ok:endpoint_users"
        http.info("User service recovered after retry")


def test_auth_service_retry(flaky_service) -> None:
    """Test authentication service retries on transient failure."""
    http = log.getChild("http")
    auth = log.getChild("auth")

    with step("Request auth token"):
        auth.info("Requesting OAuth token", extra={"grant_type": "client_credentials", "scope": "read write"})
        try:
            flaky_service("endpoint_auth")
        except ConnectionError as exc:
            auth.warning("Auth service unavailable", extra={"error": str(exc)}, exc_info=exc)

    with step("Retry token request"):
        auth.info("Retrying token acquisition", extra={"attempt": 2, "backoff_ms": 200})
        time.sleep(0.001)
        result = flaky_service("endpoint_auth")
        auth.info("Token acquired", extra={"result": result, "expires_in": 3600})

    with step("Validate token"):
        assert result == "ok:endpoint_auth"
        auth.info("Auth token validated successfully")


def test_notification_service_retry(flaky_service) -> None:
    """Test notification dispatch retries on transient error."""
    http = log.getChild("http")
    notif = log.getChild("notification")

    with step("Send notification"):
        notif.info("Dispatching push notification", extra={"user_id": 42, "channel": "email", "template": "welcome"})
        try:
            flaky_service("endpoint_notify")
        except ConnectionError as exc:
            notif.warning("Notification service down", extra={"error": str(exc)}, exc_info=exc)

    with step("Retry notification"):
        notif.info("Retrying dispatch", extra={"attempt": 2})
        result = flaky_service("endpoint_notify")
        notif.info("Notification sent", extra={"result": result})

    with step("Verify dispatch"):
        assert result == "ok:endpoint_notify"
        notif.info("Notification delivery confirmed")


# --- Deliberate failures ---


def test_response_time_sla_breach() -> None:
    """Test that response time stays under SLA threshold (deliberately fails)."""
    http = log.getChild("http")
    perf = log.getChild("performance")

    with step("Send request and measure latency"):
        http.info("Sending GET /api/v1/users")
        resp = _sim_request("GET", "/api/v1/users")
        simulated_latency_ms = 850
        perf.info("Latency measured", extra={"latency_ms": simulated_latency_ms, "sla_ms": 500})
        http.debug("Response status", extra={"status": resp["status"]})

    with step("Check SLA compliance"):
        perf.warning("Latency exceeds SLA", extra={"latency_ms": simulated_latency_ms, "threshold_ms": 500})
        assert simulated_latency_ms < 500, (
            f"Response latency {simulated_latency_ms}ms exceeds 500ms SLA threshold"
        )


def test_concurrent_request_limit() -> None:
    """Test concurrent request limit enforcement (deliberately fails)."""
    http = log.getChild("http")
    concurrency = log.getChild("concurrency")

    with step("Simulate concurrent requests"):
        max_concurrent = 50
        simulated_concurrent = 75
        concurrency.info("Load test", extra={"concurrent": simulated_concurrent, "limit": max_concurrent})
        for i in range(5):
            http.debug(f"Batch {i + 1} dispatched", extra={"connections": 15})
        time.sleep(0.001)

    with step("Verify request limit"):
        concurrency.error(
            "Concurrent limit exceeded",
            extra={"actual": simulated_concurrent, "max_allowed": max_concurrent},
        )
        assert simulated_concurrent <= max_concurrent, (
            f"Server accepted {simulated_concurrent} concurrent requests, "
            f"but limit is {max_concurrent}"
        )


def test_idempotency_key_dedup() -> None:
    """Test that duplicate idempotency keys are rejected (deliberately fails)."""
    http = log.getChild("http")
    idem = log.getChild("idempotency")

    idem_key = "idem-20260402-abc123"

    with step("Send first request with idempotency key"):
        http.info("POST /api/v1/users", extra={"idempotency_key": idem_key})
        resp1 = _sim_request("POST", "/api/v1/users", body={"name": "Test"}, headers={"X-Idempotency-Key": idem_key})
        idem.info("First request succeeded", extra={"status": resp1["status"]})

    with step("Send duplicate request with same key"):
        http.info("POST /api/v1/users (duplicate)", extra={"idempotency_key": idem_key})
        resp2 = _sim_request("POST", "/api/v1/users", body={"name": "Test"}, headers={"X-Idempotency-Key": idem_key})
        idem.info("Duplicate response", extra={"status": resp2["status"]})

    with step("Verify duplicate was rejected"):
        idem.warning("Duplicate was not rejected", extra={"first_status": resp1["status"], "second_status": resp2["status"]})
        assert resp2["status"] == 409, (
            f"Expected 409 Conflict for duplicate idempotency key, got {resp2['status']}"
        )
