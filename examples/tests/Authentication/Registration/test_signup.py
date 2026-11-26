"""User registration / signup tests -- validation, email verification, onboarding."""

from __future__ import annotations

import logging
import hashlib
import re
import time

import pytest

from stepdoc import step

log = logging.getLogger("signup")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXISTING_EMAILS = {
    "admin@example.com",
    "alice@example.com",
    "bob@example.com",
}

_PASSWORD_REGEX = re.compile(
    r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[!@#$%^&*]).{8,}$"
)


def _validate_email(email: str) -> dict:
    if not email or "@" not in email:
        return {"valid": False, "reason": "invalid_format"}
    local, _, domain = email.partition("@")
    if not local:
        return {"valid": False, "reason": "empty_local_part"}
    if "." not in domain or domain.startswith(".") or domain.endswith("."):
        return {"valid": False, "reason": "invalid_domain"}
    if email in _EXISTING_EMAILS:
        return {"valid": False, "reason": "duplicate"}
    return {"valid": True, "reason": None}


def _validate_password(password: str) -> dict:
    issues = []
    if len(password) < 8:
        issues.append("too_short")
    if not any(c.isupper() for c in password):
        issues.append("no_uppercase")
    if not any(c.islower() for c in password):
        issues.append("no_lowercase")
    if not any(c.isdigit() for c in password):
        issues.append("no_digit")
    if not any(c in "!@#$%^&*" for c in password):
        issues.append("no_special")
    return {"valid": len(issues) == 0, "issues": issues}


# ---------------------------------------------------------------------------
# Basic registration
# ---------------------------------------------------------------------------


def test_signup_valid_user():
    """Successful registration with all valid data."""
    reg = log.getChild("registration")

    with step("Collect user input"):
        payload = {
            "email": "newuser@example.com",
            "password": "N3wUs3r!Pass",
            "first_name": "New",
            "last_name": "User",
            "terms_accepted": True,
        }
        reg.info("Registration form submitted", extra={"data": payload})

    with step("Validate email"):
        email_result = _validate_email(payload["email"])
        reg.info("Email validation", extra={"data": email_result})
        with step("Check MX record"):
            reg.debug("MX lookup", extra={"domain": "example.com", "mx": "mail.example.com", "priority": 10})

    with step("Validate password"):
        pwd_result = _validate_password(payload["password"])
        reg.info("Password validation", extra={"data": pwd_result})
        with step("Check against breached password list"):
            reg.info("Breach check", extra={"breached": False, "checked_prefix": hashlib.sha1(payload["password"].encode()).hexdigest()[:5]})

    with step("Create user record"):
        user_id = "usr_" + hashlib.sha256(payload["email"].encode()).hexdigest()[:12]
        reg.info("User created", extra={"user_id": user_id, "role": "member"})
        with step("Hash password with bcrypt"):
            reg.debug("Password hashed", extra={"algo": "bcrypt", "rounds": 12})
        with step("Store in database"):
            reg.info("User persisted", extra={"table": "users", "user_id": user_id})

    with step("Send verification email"):
        verification_token = hashlib.sha256(f"verify:{payload['email']}:{time.time()}".encode()).hexdigest()[:32]
        email_log = log.getChild("email")
        email_log.info("Verification email queued", extra={
            "to": payload["email"],
            "template": "email_verification",
            "token_prefix": verification_token[:8],
        })
        email_log.debug("SMTP relay", extra={"relay": "smtp.internal", "port": 587})

    with step("Audit event"):
        audit = log.getChild("audit")
        audit.info("Registration event", extra={
            "event": "user_registered",
            "user_id": user_id,
            "ip": "192.168.1.100",
            "user_agent": "Mozilla/5.0",
        })

    assert email_result["valid"]
    assert pwd_result["valid"]


def test_signup_with_display_name():
    """Registration with optional display name."""
    reg = log.getChild("registration")

    with step("Submit registration with display name"):
        payload = {
            "email": "display@example.com",
            "password": "D!splay123",
            "display_name": "CoolUser42",
        }
        reg.info("Form data", extra={"data": payload})

    with step("Validate display name"):
        name = payload["display_name"]
        reg.info("Display name check", extra={"length": len(name), "valid_chars": name.isalnum()})
        with step("Check uniqueness"):
            reg.info("Uniqueness check", extra={"taken": False})
        with step("Check profanity filter"):
            reg.debug("Profanity check", extra={"flagged": False, "dictionary": "en_US"})

    with step("Create account"):
        reg.info("Account created", extra={"email": payload["email"], "display_name": name})

    assert len(name) >= 3


# ---------------------------------------------------------------------------
# Email validation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "email,expect_valid,reason",
    [
        ("user@example.com", True, None),
        ("user+tag@example.com", True, None),
        ("user@sub.domain.com", True, None),
        ("", False, "invalid_format"),
        ("noatsign", False, "invalid_format"),
        ("@missing-local.com", False, "empty_local_part"),
        ("user@.com", False, "invalid_domain"),
        ("user@com.", False, "invalid_domain"),
        ("admin@example.com", False, "duplicate"),
        ("alice@example.com", False, "duplicate"),
    ],
    ids=[
        "valid-basic",
        "valid-plus-tag",
        "valid-subdomain",
        "empty-string",
        "no-at-sign",
        "empty-local",
        "dot-start-domain",
        "dot-end-domain",
        "duplicate-admin",
        "duplicate-alice",
    ],
)
def test_email_validation_rules(email, expect_valid, reason):
    """Exhaustive email validation against business rules."""
    val = log.getChild("validation")

    with step(f"Validate email: {email!r}"):
        result = _validate_email(email)
        val.info("Validation result", extra={"email": email, "valid": result["valid"], "reason": result["reason"]})
        with step("Format check"):
            val.debug("Format analysis", extra={"has_at": "@" in email, "length": len(email)})
            if "@" in email:
                local, _, domain = email.partition("@")
                with step("Domain check"):
                    val.debug("Domain analysis", extra={"domain": domain, "has_dot": "." in domain})

    assert result["valid"] == expect_valid
    if reason:
        assert result["reason"] == reason


# ---------------------------------------------------------------------------
# Password policy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "password,expect_valid",
    [
        ("Str0ng!Pass", True),
        ("C0mpl3x#Key", True),
        ("short", False),
        ("alllowercase1!", False),
        ("ALLUPPERCASE1!", False),
        ("NoDigitsHere!", False),
        ("N0SpecialChar", False),
        ("12345678", False),
    ],
    ids=[
        "strong-pass",
        "complex-key",
        "too-short",
        "no-uppercase",
        "no-lowercase",
        "no-digit",
        "no-special",
        "only-digits",
    ],
)
def test_password_policy_enforcement(password, expect_valid):
    """Verify password policy with various inputs."""
    policy = log.getChild("password_policy")

    with step("Run password checks"):
        result = _validate_password(password)
        policy.info("Policy evaluation", extra={"password_length": len(password), "valid": result["valid"]})
        with step("Length check"):
            policy.debug("Length", extra={"actual": len(password), "min": 8, "pass": len(password) >= 8})
        with step("Complexity checks"):
            policy.debug("Complexity", extra={"issues": result["issues"]})

    with step("Log verdict"):
        if result["valid"]:
            policy.info("Password accepted")
        else:
            policy.warning("Password rejected", extra={"issues": result["issues"]})

    assert result["valid"] == expect_valid


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


def test_signup_duplicate_email_rejected():
    """Attempting to register with an existing email is rejected."""
    reg = log.getChild("registration")

    with step("Submit registration with existing email"):
        email = "admin@example.com"
        reg.info("Registration attempt", extra={"email": email})

    with step("Check email uniqueness"):
        result = _validate_email(email)
        reg.warning("Duplicate email detected", extra={"email": email, "reason": result["reason"]})
        with step("Query users table"):
            reg.debug("SELECT count from users", extra={"email": email, "count": 1})

    with step("Return error to client"):
        reg.info("HTTP 409 Conflict", extra={"error": "email_already_registered"})

    assert not result["valid"]
    assert result["reason"] == "duplicate"


# ---------------------------------------------------------------------------
# Email verification
# ---------------------------------------------------------------------------


def test_email_verification_token():
    """Verify email confirmation via token link."""
    verify = log.getChild("verification")

    with step("Generate verification token"):
        token = hashlib.sha256(f"verify:newuser@example.com:{time.time()}".encode()).hexdigest()[:32]
        verify.info("Token generated", extra={"token_prefix": token[:8], "ttl_hours": 24})
        with step("Store token in database"):
            verify.debug("Token stored", extra={"table": "email_verifications", "expires_in": 86400})

    with step("User clicks verification link"):
        verify.info("Verification request received", extra={"token_prefix": token[:8]})
        with step("Look up token"):
            verify.info("Token found", extra={"valid": True, "expired": False})
        with step("Mark email as verified"):
            verify.info("Email verified", extra={"email": "newuser@example.com", "verified_at": "2026-04-02T12:00:00Z"})

    with step("Activate account"):
        verify.info("Account activated", extra={"user_id": "usr_abc123", "status": "active"})

    verified = True
    assert verified


def test_email_verification_expired_token():
    """Expired verification token is rejected."""
    verify = log.getChild("verification")

    with step("User clicks old verification link"):
        token = "expired_token_aabbccdd"
        verify.info("Verification attempt", extra={"token_prefix": token[:8]})
        with step("Look up token"):
            verify.warning("Token found but expired", extra={
                "created_at": "2026-03-28T10:00:00Z",
                "expired_at": "2026-03-29T10:00:00Z",
                "now": "2026-04-02T10:00:00Z",
            })

    with step("Offer to resend verification"):
        verify.info("Resend prompt shown", extra={"email": "user@example.com"})

    expired = True
    assert expired


# ---------------------------------------------------------------------------
# Terms of service
# ---------------------------------------------------------------------------


def test_signup_requires_terms_acceptance():
    """Registration must include terms acceptance."""
    reg = log.getChild("registration")

    with step("Submit form without accepting terms"):
        payload = {"email": "terms@example.com", "password": "T3rms!Pass", "terms_accepted": False}
        reg.info("Form submitted", extra={"data": payload})

    with step("Validate terms acceptance"):
        reg.warning("Terms not accepted", extra={"terms_accepted": False, "required": True})
        with step("Check terms version"):
            reg.debug("Terms version", extra={"current": "v2.3", "required": "v2.3"})

    with step("Return validation error"):
        reg.info("HTTP 422", extra={"error": "terms_acceptance_required"})

    assert payload["terms_accepted"] is False


# ---------------------------------------------------------------------------
# Onboarding
# ---------------------------------------------------------------------------


def test_signup_triggers_welcome_email():
    """Verify welcome email is sent after registration."""
    email = log.getChild("email")

    with step("User completes registration"):
        email.info("Registration complete", extra={"user_id": "usr_new001", "email": "welcome@example.com"})

    with step("Queue welcome email"):
        email.info("Welcome email queued", extra={
            "template": "welcome_v3",
            "to": "welcome@example.com",
            "variables": {"first_name": "New", "app_name": "ExampleApp"},
        })
        with step("Render template"):
            email.debug("Template rendered", extra={"subject": "Welcome to ExampleApp!", "body_length": 2048})
        with step("Submit to SMTP relay"):
            email.info("Email submitted", extra={"message_id": "msg_w001", "relay": "smtp.internal"})

    with step("Verify delivery status"):
        email.info("Delivery confirmed", extra={"status": "delivered", "delivery_time_ms": 340})

    assert True


def test_signup_creates_default_preferences():
    """New user gets default notification preferences."""
    prefs = log.getChild("preferences")

    with step("Create default preferences"):
        defaults = {
            "email_notifications": True,
            "push_notifications": False,
            "marketing_emails": False,
            "weekly_digest": True,
            "theme": "system",
            "language": "en",
            "timezone": "UTC",
        }
        prefs.info("Defaults created", extra={"data": defaults})
        with step("Store in preferences table"):
            prefs.debug("INSERT into user_preferences", extra={"user_id": "usr_new001", "columns": list(defaults.keys())})

    with step("Verify preferences stored"):
        prefs.info("Preferences confirmed", extra={"count": len(defaults)})

    assert len(defaults) == 7


# ---------------------------------------------------------------------------
# Rate limiting on signup
# ---------------------------------------------------------------------------


def test_signup_rate_limiting():
    """Rapid registration attempts from same IP are throttled."""
    rl = log.getChild("rate_limit")

    with step("Configure signup rate limiter"):
        rl.info("Rate limit config", extra={"max_signups_per_ip": 3, "window_minutes": 60})

    with step("Simulate 5 signup attempts"):
        for i in range(1, 6):
            with step(f"Attempt {i}"):
                blocked = i > 3
                rl.info("Signup attempt", extra={"attempt": i, "ip": "203.0.113.50", "blocked": blocked})
                if blocked:
                    rl.warning("Rate limit exceeded", extra={"attempt": i, "retry_after_seconds": 3600})

    with step("Verify throttle response"):
        rl.info("HTTP 429 returned for attempts 4-5", extra={"blocked_count": 2})

    assert True


# ---------------------------------------------------------------------------
# Skip and flaky tests
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="Captcha verification requires browser environment")
def test_signup_captcha_validation():
    """Validate reCAPTCHA on signup form."""
    log.info("Skipped -- requires browser")


@pytest.mark.skip(reason="Phone number validation API not available in CI")
def test_signup_phone_verification():
    """Verify phone number via SMS OTP during registration."""
    log.info("Skipped -- requires SMS provider")


def test_signup_with_flaky_email_service(flaky_service):
    """Verification email depends on a flaky SMTP relay."""
    email = log.getChild("email")

    with step("Register user"):
        email.info("User registered", extra={"email": "flaky@example.com"})

    with step("Send verification email via SMTP"):
        email.info("Connecting to SMTP relay", extra={"host": "smtp.internal", "port": 587})
        with step("Authenticate with relay"):
            email.debug("SMTP auth", extra={"method": "PLAIN"})
        with step("Send message"):
            result = flaky_service("signup_smtp_relay")
            email.info("Email sent", extra={"result": result})

    assert result.startswith("ok")


def test_signup_with_flaky_user_db(flaky_service):
    """User creation depends on a flaky database primary."""
    db = log.getChild("database")

    with step("Validate registration data"):
        db.info("Validation passed", extra={"email": "dbflaky@example.com"})

    with step("Insert user record"):
        db.info("Connecting to primary", extra={"host": "pg-primary.internal", "port": 5432})
        with step("Execute INSERT"):
            result = flaky_service("signup_user_insert")
            db.info("User inserted", extra={"result": result})

    with step("Verify record"):
        db.info("SELECT user", extra={"email": "dbflaky@example.com", "found": True})

    assert result == "ok:signup_user_insert"


def test_signup_with_flaky_event_bus(flaky_service):
    """UserRegistered event publish depends on a flaky message broker."""
    events = log.getChild("events")

    with step("Registration complete"):
        events.info("User created", extra={"user_id": "usr_evt001"})

    with step("Publish UserRegistered event"):
        events.info("Publishing to event bus", extra={"topic": "user.registered", "broker": "kafka.internal:9092"})
        with step("Serialize event payload"):
            events.debug("Payload", extra={"schema": "UserRegistered_v2", "size_bytes": 384})
        with step("Publish"):
            result = flaky_service("signup_event_bus")
            events.info("Event published", extra={"result": result, "partition": 3, "offset": 10042})

    assert result.startswith("ok")


# ---------------------------------------------------------------------------
# Deliberate failures
# ---------------------------------------------------------------------------


def test_signup_response_time_budget():
    """Registration must complete within 5 seconds -- deliberate failure."""
    perf = log.getChild("performance")

    with step("Measure end-to-end registration time"):
        perf.info("Timer started")
        with step("Validate input"):
            perf.debug("Validation took 0.1s")
        with step("Hash password"):
            perf.debug("Hashing took 0.3s")
        with step("Insert user"):
            perf.debug("DB insert took 4.2s")
        with step("Send verification email"):
            perf.debug("Email queued in 1.8s")
            total = 6.4
            perf.warning("Total time exceeded budget", extra={"total_seconds": total, "budget": 5.0})

    with step("Evaluate budget"):
        perf.error("Budget exceeded", extra={"actual": total, "limit": 5.0})

    assert total < 5.0, f"Registration took {total}s, expected < 5.0s"


def test_signup_password_hash_cost():
    """Password hash time must stay under 500ms -- deliberate failure."""
    perf = log.getChild("performance")

    with step("Benchmark bcrypt hash"):
        rounds = 14
        hash_time_ms = 720
        perf.info("Hash benchmark", extra={"algo": "bcrypt", "rounds": rounds, "elapsed_ms": hash_time_ms})

    with step("Evaluate target"):
        perf.error("Hash too slow", extra={"actual_ms": hash_time_ms, "target_ms": 500, "rounds": rounds})

    assert hash_time_ms < 500, f"bcrypt with {rounds} rounds took {hash_time_ms}ms, limit is 500ms"
