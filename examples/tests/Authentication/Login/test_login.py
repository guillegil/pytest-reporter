"""Login feature tests -- credential validation, MFA, sessions, rate limiting, lockout."""

from __future__ import annotations

import logging
import hashlib
import time

import pytest

from stepdoc import step

log = logging.getLogger("login")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_VALID_USERS = {
    "admin": {"hash": hashlib.sha256(b"Adm!n2026").hexdigest(), "role": "admin", "mfa": True},
    "alice": {"hash": hashlib.sha256(b"Al1ceP@ss").hexdigest(), "role": "editor", "mfa": False},
    "bob": {"hash": hashlib.sha256(b"B0bSecure!").hexdigest(), "role": "viewer", "mfa": True},
    "carol": {"hash": hashlib.sha256(b"C@rol9876").hexdigest(), "role": "viewer", "mfa": False},
}


def _simulate_login(username: str, password: str) -> dict:
    user = _VALID_USERS.get(username)
    if not user:
        return {"ok": False, "error": "unknown_user", "code": 401}
    if hashlib.sha256(password.encode()).hexdigest() != user["hash"]:
        return {"ok": False, "error": "bad_password", "code": 401}
    return {
        "ok": True,
        "token": hashlib.sha256(f"{username}:{time.time()}".encode()).hexdigest()[:32],
        "role": user["role"],
        "mfa_required": user["mfa"],
    }


# ---------------------------------------------------------------------------
# Basic credential tests
# ---------------------------------------------------------------------------


def test_login_valid_admin():
    """Successful admin login with MFA."""
    auth = log.getChild("auth")

    with step("Prepare credentials"):
        with step("Load admin user record"):
            auth.info("Loaded user from directory", extra={"username": "admin", "source": "ldap"})
        with step("Hash incoming password"):
            pwd_hash = hashlib.sha256(b"Adm!n2026").hexdigest()
            auth.debug("Password hashed", extra={"algo": "sha256", "length": len(pwd_hash)})

    with step("Authenticate against user store"):
        with step("Compare hashes"):
            result = _simulate_login("admin", "Adm!n2026")
            auth.info("Credential check passed", extra={"match": True, "role": result["role"]})
        with step("Verify account not locked"):
            auth.info("Account lock check", extra={"locked": False, "failed_attempts": 0})
        with step("Verify account is active"):
            auth.info("Account status", extra={"active": True, "last_login": "2026-03-30T10:15:00Z"})

    with step("MFA challenge"):
        with step("Generate TOTP seed"):
            auth.info("TOTP challenge issued", extra={"method": "totp", "digits": 6, "interval": 30})
        with step("Validate TOTP code"):
            totp_code = "482917"
            auth.info("TOTP code submitted", extra={"code_length": len(totp_code)})
            auth.info("MFA verification passed", extra={"method": "totp", "verified": True})

    with step("Issue session token"):
        token = result["token"]
        session = log.getChild("session")
        session.info("JWT generated", extra={"token_prefix": token[:8], "ttl_seconds": 3600})
        session.debug("Token claims", extra={"sub": "admin", "role": "admin", "iat": 1711900000, "exp": 1711903600})
        session.info("Session stored in Redis", extra={"key": f"sess:{token[:8]}", "ttl": 3600})

    with step("Audit log entry"):
        audit = log.getChild("audit")
        audit.info("Login event recorded", extra={
            "event": "login_success",
            "user": "admin",
            "ip": "10.0.0.42",
            "user_agent": "Mozilla/5.0 (X11; Linux x86_64)",
            "geo": {"country": "US", "region": "CA"},
        })

    assert result["ok"]
    assert result["role"] == "admin"


def test_login_valid_non_mfa_user():
    """Login for a user without MFA enabled."""
    auth = log.getChild("auth")

    with step("Submit credentials for alice"):
        auth.info("Login attempt", extra={"username": "alice", "ip": "192.168.1.50"})
        with step("Validate username format"):
            auth.debug("Username validated", extra={"length": 5, "allowed_chars": True})
        with step("Rate-limit check"):
            auth.info("Rate limit status", extra={"bucket": "alice", "remaining": 9, "window_seconds": 300})

    with step("Authenticate"):
        result = _simulate_login("alice", "Al1ceP@ss")
        auth.info("Password verification", extra={"match": True})
        auth.info("MFA check", extra={"mfa_required": False, "mfa_enrolled": False})

    with step("Create session"):
        session = log.getChild("session")
        session.info("Session initialized", extra={"user": "alice", "role": "editor"})
        session.info("CSRF token generated", extra={"token_length": 32})
        session.debug("Cookie flags", extra={"httponly": True, "secure": True, "samesite": "strict"})

    assert result["ok"]
    assert result["mfa_required"] is False


def test_login_unknown_user():
    """Reject login for a non-existent user."""
    auth = log.getChild("auth")

    with step("Submit credentials for unknown user"):
        auth.info("Login attempt", extra={"username": "nobody", "ip": "203.0.113.7"})
        with step("Look up user in directory"):
            auth.warning("User not found in LDAP", extra={"username": "nobody", "searched": ["ldap", "local_db"]})

    with step("Return authentication failure"):
        result = _simulate_login("nobody", "anything")
        auth.info("Auth result", extra={"ok": False, "error": result["error"], "code": 401})
        with step("Increment failed attempt counter"):
            auth.info("Failed attempt recorded", extra={"ip": "203.0.113.7", "total_failures": 4})

    with step("Security event"):
        sec = log.getChild("security")
        sec.warning("Unknown user login attempt", extra={
            "username": "nobody",
            "ip": "203.0.113.7",
            "threshold_before_block": 10,
        })

    assert not result["ok"]
    assert result["error"] == "unknown_user"


def test_login_wrong_password():
    """Reject login with incorrect password."""
    auth = log.getChild("auth")

    with step("Submit wrong password"):
        auth.info("Login attempt", extra={"username": "bob", "ip": "10.0.0.99"})
        with step("Hash submitted password"):
            wrong_hash = hashlib.sha256(b"wrong_password").hexdigest()
            auth.debug("Password hashed", extra={"algo": "sha256"})

    with step("Compare hashes"):
        result = _simulate_login("bob", "wrong_password")
        auth.warning("Password mismatch", extra={"username": "bob"})
        with step("Update failed attempt counter"):
            auth.info("Failed attempts", extra={"username": "bob", "count": 2, "max": 5})

    with step("Audit trail"):
        audit = log.getChild("audit")
        audit.warning("Failed login", extra={
            "event": "login_failure",
            "reason": "bad_password",
            "user": "bob",
            "ip": "10.0.0.99",
        })

    assert not result["ok"]
    assert result["code"] == 401


# ---------------------------------------------------------------------------
# Parametrized credential matrix
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "username,password,expect_ok",
    [
        ("admin", "Adm!n2026", True),
        ("admin", "wrongpass", False),
        ("alice", "Al1ceP@ss", True),
        ("alice", "Al1ceP@s", False),
        ("bob", "B0bSecure!", True),
        ("carol", "C@rol9876", True),
        ("carol", "c@rol9876", False),
        ("", "anything", False),
    ],
    ids=[
        "admin-correct",
        "admin-wrong",
        "alice-correct",
        "alice-typo",
        "bob-correct",
        "carol-correct",
        "carol-case-sensitive",
        "empty-username",
    ],
)
def test_login_credential_matrix(username, password, expect_ok):
    """Verify credential matching across the user table."""
    auth = log.getChild("auth")

    with step(f"Authenticate user={username!r}"):
        auth.info("Attempt", extra={"username": username, "password_length": len(password)})
        with step("Hash password"):
            auth.debug("SHA-256 digest computed")
        with step("Look up user record"):
            auth.info("User lookup", extra={"found": username in _VALID_USERS})

    with step("Evaluate result"):
        result = _simulate_login(username, password)
        auth.info("Auth outcome", extra={"ok": result["ok"], "expected": expect_ok})
        if result["ok"]:
            auth.info("Token issued", extra={"prefix": result["token"][:8]})
        else:
            auth.warning("Rejected", extra={"error": result.get("error", "n/a")})

    assert result["ok"] == expect_ok


# ---------------------------------------------------------------------------
# Session management
# ---------------------------------------------------------------------------


def test_session_expiry():
    """Verify session expiration after TTL."""
    session = log.getChild("session")

    with step("Create session"):
        token = "a1b2c3d4e5f60000"
        session.info("Session created", extra={"token_prefix": token[:8], "ttl": 3600})
        with step("Store in session backend"):
            session.info("Stored in Redis", extra={"key": f"sess:{token[:8]}", "db": 2})

    with step("Advance time past TTL"):
        session.info("Simulating clock advance", extra={"advance_seconds": 3601})
        with step("Query session store"):
            session.warning("Session not found -- expired", extra={"key": f"sess:{token[:8]}"})

    with step("Verify expiry behavior"):
        session.info("Client receives 401", extra={"status": 401, "body": "session_expired"})

    expired = True
    assert expired, "Session should have expired"


def test_session_refresh():
    """Verify sliding window session refresh."""
    session = log.getChild("session")

    with step("Create session with 30-min TTL"):
        session.info("Session created", extra={"ttl": 1800, "user": "alice"})
        with step("Record creation timestamp"):
            session.debug("Timestamps", extra={"created_at": 1711900000, "expires_at": 1711901800})

    with step("Activity within window"):
        for i in range(3):
            with step(f"Request {i + 1}"):
                session.info(f"Request received", extra={"request_num": i + 1, "path": f"/api/resource/{i}"})
                session.debug("TTL refreshed", extra={"new_expires_at": 1711901800 + (i + 1) * 600})

    with step("Verify session still active"):
        session.info("Session lookup", extra={"found": True, "remaining_ttl": 1200})

    assert True


def test_concurrent_sessions_limit():
    """Verify max concurrent session enforcement."""
    session = log.getChild("session")

    with step("Create 3 sessions for bob"):
        for i in range(3):
            with step(f"Session {i + 1}"):
                session.info(f"Session created", extra={"session_id": f"sess_{i}", "device": f"device_{i}"})

    with step("Attempt 4th session"):
        session.warning("Max sessions reached", extra={"max": 3, "current": 3})
        with step("Evict oldest session"):
            session.info("Evicted session", extra={"evicted": "sess_0", "reason": "max_concurrent"})
            session.info("New session created", extra={"session_id": "sess_3", "device": "device_3"})

    with step("Verify session count"):
        active = ["sess_1", "sess_2", "sess_3"]
        session.info("Active sessions", extra={"count": len(active), "ids": active})

    assert len(active) == 3


# ---------------------------------------------------------------------------
# MFA flows
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "mfa_method,code,valid",
    [
        ("totp", "123456", True),
        ("totp", "000000", False),
        ("sms", "987654", True),
        ("email", "554433", True),
        ("totp", "", False),
    ],
    ids=["totp-valid", "totp-invalid", "sms-valid", "email-valid", "totp-empty"],
)
def test_mfa_verification(mfa_method, code, valid):
    """Verify MFA code validation across methods."""
    mfa = log.getChild("mfa")

    with step(f"Issue MFA challenge via {mfa_method}"):
        mfa.info("Challenge issued", extra={"method": mfa_method, "user": "admin"})
        with step("Generate expected code"):
            mfa.debug("Expected code generated", extra={"digits": 6, "ttl": 300})

    with step("Validate submitted code"):
        mfa.info("Code submitted", extra={"method": mfa_method, "code_length": len(code)})
        if valid:
            mfa.info("Code accepted", extra={"verified": True})
        else:
            mfa.warning("Code rejected", extra={"verified": False, "reason": "mismatch" if code else "empty"})

    with step("Record MFA event"):
        audit = log.getChild("audit")
        audit.info("MFA event", extra={"method": mfa_method, "success": valid, "user": "admin"})

    assert valid == (code not in ("000000", ""))


# ---------------------------------------------------------------------------
# Rate limiting and lockout
# ---------------------------------------------------------------------------


def test_rate_limiting_enforced():
    """Verify that rapid login attempts trigger rate limiting."""
    rl = log.getChild("rate_limit")

    with step("Configure rate limiter"):
        rl.info("Rate limiter config", extra={"max_attempts": 5, "window_seconds": 300, "lockout_seconds": 600})

    with step("Simulate 7 rapid attempts"):
        for i in range(1, 8):
            with step(f"Attempt {i}"):
                blocked = i > 5
                rl.info("Login attempt", extra={"attempt": i, "ip": "10.0.0.77", "blocked": blocked})
                if blocked:
                    rl.warning("Rate limit exceeded", extra={"attempt": i, "retry_after": 600 - (i - 5) * 10})

    with step("Verify rate limit response"):
        rl.info("Final status", extra={"blocked": True, "remaining_lockout": 580})

    assert True


def test_account_lockout_after_failures():
    """Account locked after too many failed attempts -- deliberate failure."""
    auth = log.getChild("auth")

    with step("Simulate 5 failed login attempts"):
        for i in range(1, 6):
            with step(f"Failed attempt {i}"):
                auth.warning("Bad password", extra={"username": "bob", "attempt": i})

    with step("Attempt login after lockout"):
        auth.info("Login attempt on locked account", extra={"username": "bob", "locked": True})
        with step("Check lockout status"):
            auth.error("Account is locked", extra={"unlock_at": "2026-04-02T12:30:00Z", "failed_count": 5})
            response_code = 423

    with step("Verify lockout response"):
        auth.info("Expected 423 Locked", extra={"actual": response_code})

    assert response_code == 200, f"Expected 200 OK but got {response_code} (account locked)"


# ---------------------------------------------------------------------------
# Password policy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "password,meets_policy",
    [
        ("Ab1!efgh", True),
        ("short", False),
        ("alllowercase1!", False),
        ("ALLUPPERCASE1!", False),
        ("NoDigits!!", False),
        ("N0Special", False),
        ("Str0ng!P@ssw0rd", True),
    ],
    ids=["valid-min", "too-short", "no-upper", "no-lower", "no-digit", "no-special", "strong"],
)
def test_password_policy(password, meets_policy):
    """Verify password policy enforcement."""
    policy = log.getChild("password_policy")

    with step("Evaluate password"):
        policy.info("Checking password", extra={"length": len(password)})
        checks = {
            "min_length": len(password) >= 8,
            "has_upper": any(c.isupper() for c in password),
            "has_lower": any(c.islower() for c in password),
            "has_digit": any(c.isdigit() for c in password),
            "has_special": any(not c.isalnum() for c in password),
        }
        for check_name, passed in checks.items():
            with step(f"Check: {check_name}"):
                lvl = "info" if passed else "warning"
                getattr(policy, lvl)(f"{check_name}: {'pass' if passed else 'fail'}", extra={"value": passed})

    with step("Policy verdict"):
        all_pass = all(checks.values())
        policy.info("Verdict", extra={"meets_policy": all_pass, "checks": checks})

    assert all_pass == meets_policy


# ---------------------------------------------------------------------------
# Skip and flaky tests
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="LDAP integration not available in CI")
def test_ldap_bind_authentication():
    """Test LDAP bind authentication."""
    log.info("This should not execute")
    assert True


@pytest.mark.skip(reason="SAML SSO provider not configured")
def test_saml_sso_login():
    """Test SAML-based single sign-on."""
    log.info("This should not execute")
    assert True


def test_login_with_flaky_auth_service(flaky_service):
    """Login that depends on a flaky authentication micro-service."""
    auth = log.getChild("auth")

    with step("Call authentication service"):
        auth.info("Connecting to auth-svc", extra={"host": "auth.internal", "port": 8443})
        with step("Send credential payload"):
            auth.info("Payload sent", extra={"username": "alice", "encrypted": True})
            result = flaky_service("login_auth_svc")
            auth.info("Service response", extra={"result": result})

    with step("Process auth response"):
        auth.info("Token extracted", extra={"token_prefix": "abc12345"})

    assert result.startswith("ok")


def test_login_with_flaky_session_store(flaky_service):
    """Session creation depends on a flaky Redis cluster."""
    session = log.getChild("session")

    with step("Authenticate user"):
        session.info("Credentials verified", extra={"username": "bob"})

    with step("Store session in Redis"):
        session.info("Connecting to session store", extra={"host": "redis-cluster.internal"})
        with step("Execute SET command"):
            result = flaky_service("login_session_redis")
            session.info("Session stored", extra={"result": result, "ttl": 3600})

    assert result == "ok:login_session_redis"


def test_login_with_flaky_audit_log(flaky_service):
    """Audit log write depends on a flaky message queue."""
    audit = log.getChild("audit")

    with step("Login succeeds"):
        audit.info("User authenticated", extra={"username": "carol"})

    with step("Write audit event to message queue"):
        audit.info("Publishing to audit queue", extra={"queue": "audit.login.events"})
        with step("Serialize event"):
            audit.debug("Event serialized", extra={"format": "avro", "size_bytes": 512})
        with step("Publish"):
            result = flaky_service("login_audit_mq")
            audit.info("Audit event published", extra={"result": result, "message_id": "msg_00a1"})

    assert result.startswith("ok")


# ---------------------------------------------------------------------------
# Deliberate failures
# ---------------------------------------------------------------------------


def test_login_response_time_sla():
    """Login response time must be under 2 seconds -- deliberate failure."""
    perf = log.getChild("performance")

    with step("Measure login latency"):
        perf.info("Starting timer")
        with step("Send login request"):
            perf.info("Request sent", extra={"endpoint": "/api/v1/auth/login", "method": "POST"})
        with step("Receive response"):
            response_time = 3.47
            perf.warning("Slow response", extra={"elapsed_seconds": response_time, "threshold": 2.0})

    with step("Evaluate SLA compliance"):
        perf.error("SLA breached", extra={"actual": response_time, "limit": 2.0})

    assert response_time < 2.0, f"Login took {response_time}s, expected < 2.0s"


def test_login_token_entropy():
    """Token must have sufficient entropy -- deliberate failure."""
    sec = log.getChild("security")

    with step("Generate authentication token"):
        token = "aaaa1111"
        sec.info("Token generated", extra={"token": token, "length": len(token)})

    with step("Measure Shannon entropy"):
        import math
        freq = {}
        for c in token:
            freq[c] = freq.get(c, 0) + 1
        entropy = -sum((f / len(token)) * math.log2(f / len(token)) for f in freq.values())
        sec.info("Entropy calculated", extra={"entropy_bits": round(entropy, 4), "min_required": 3.0})

    assert entropy >= 3.0, f"Token entropy {entropy:.2f} bits is below minimum 3.0 bits"
