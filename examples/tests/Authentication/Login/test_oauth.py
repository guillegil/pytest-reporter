"""OAuth / OpenID Connect login tests -- provider flows, token exchange, refresh, revocation."""

from __future__ import annotations

import logging
import hashlib
import time
import urllib.parse

import pytest

from stepdoc import step

log = logging.getLogger("oauth")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "google": {
        "auth_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "client_id": "google-client-id-123.apps.googleusercontent.com",
        "scopes": ["openid", "email", "profile"],
    },
    "github": {
        "auth_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "client_id": "gh-client-abc",
        "scopes": ["read:user", "user:email"],
    },
    "microsoft": {
        "auth_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "client_id": "ms-client-xyz-456",
        "scopes": ["openid", "profile", "email", "User.Read"],
    },
    "apple": {
        "auth_url": "https://appleid.apple.com/auth/authorize",
        "token_url": "https://appleid.apple.com/auth/token",
        "client_id": "com.example.signin",
        "scopes": ["name", "email"],
    },
}


def _build_auth_url(provider: str, state: str, nonce: str) -> str:
    cfg = _PROVIDERS[provider]
    params = {
        "client_id": cfg["client_id"],
        "redirect_uri": "https://app.example.com/auth/callback",
        "response_type": "code",
        "scope": " ".join(cfg["scopes"]),
        "state": state,
        "nonce": nonce,
    }
    return f"{cfg['auth_url']}?{urllib.parse.urlencode(params)}"


def _simulate_token_exchange(provider: str, code: str) -> dict:
    return {
        "access_token": hashlib.sha256(f"{provider}:{code}".encode()).hexdigest()[:40],
        "token_type": "Bearer",
        "expires_in": 3600,
        "refresh_token": hashlib.sha256(f"refresh:{provider}:{code}".encode()).hexdigest()[:40],
        "id_token": f"eyJ.{provider}.mock_jwt_payload",
        "scope": " ".join(_PROVIDERS[provider]["scopes"]),
    }


# ---------------------------------------------------------------------------
# Authorization URL generation
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", ["google", "github", "microsoft", "apple"])
def test_oauth_authorize_url(provider):
    """Verify the authorization URL is well-formed for each provider."""
    oauth = log.getChild("oauth")

    with step(f"Build authorize URL for {provider}"):
        state = hashlib.sha256(f"state:{time.time()}".encode()).hexdigest()[:16]
        nonce = hashlib.sha256(f"nonce:{time.time()}".encode()).hexdigest()[:16]
        oauth.info("Generating state + nonce", extra={"state": state, "nonce": nonce})
        with step("Assemble query parameters"):
            url = _build_auth_url(provider, state, nonce)
            oauth.info("URL built", extra={"url_length": len(url), "provider": provider})

    with step("Validate URL components"):
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        oauth.debug("Parsed URL", extra={
            "scheme": parsed.scheme,
            "host": parsed.hostname,
            "params": list(params.keys()),
        })
        with step("Check required params present"):
            required = {"client_id", "redirect_uri", "response_type", "scope", "state", "nonce"}
            missing = required - set(params.keys())
            oauth.info("Param check", extra={"required": list(required), "missing": list(missing)})

    assert parsed.scheme == "https"
    assert len(missing) == 0


# ---------------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", ["google", "github", "microsoft"])
def test_oauth_token_exchange(provider):
    """Simulate authorization code -> token exchange."""
    oauth = log.getChild("oauth")
    token_log = oauth.getChild("token_exchange")

    with step("Receive authorization callback"):
        code = f"4/0AX4XfW-{provider}-mock-code"
        state = "abc123state"
        oauth.info("Callback received", extra={"provider": provider, "code_length": len(code)})
        with step("Validate state parameter"):
            oauth.info("State validated", extra={"expected": state, "received": state, "match": True})

    with step("Exchange code for tokens"):
        token_log.info("POST to token endpoint", extra={
            "url": _PROVIDERS[provider]["token_url"],
            "grant_type": "authorization_code",
        })
        with step("Send request"):
            tokens = _simulate_token_exchange(provider, code)
            token_log.info("Token response received", extra={
                "has_access_token": bool(tokens["access_token"]),
                "has_refresh_token": bool(tokens["refresh_token"]),
                "expires_in": tokens["expires_in"],
            })
        with step("Validate token type"):
            token_log.debug("Token type", extra={"type": tokens["token_type"]})

    with step("Decode ID token"):
        id_token = tokens["id_token"]
        oauth.info("ID token received", extra={"parts": len(id_token.split(".")), "provider": provider})
        with step("Verify JWT signature"):
            oauth.info("Signature verification", extra={"valid": True, "algo": "RS256"})
        with step("Extract claims"):
            oauth.debug("Claims", extra={"sub": f"{provider}_user_001", "email": f"user@{provider}.example"})

    with step("Create local user session"):
        session = log.getChild("session")
        session.info("User mapped to local account", extra={"provider": provider, "local_id": "usr_42"})
        session.info("Session created", extra={"ttl": tokens["expires_in"]})

    assert tokens["access_token"]
    assert tokens["token_type"] == "Bearer"


# ---------------------------------------------------------------------------
# Refresh token flow
# ---------------------------------------------------------------------------


def test_oauth_refresh_token():
    """Verify access token refresh via refresh_token grant."""
    oauth = log.getChild("oauth")

    with step("Setup: existing tokens"):
        old_access = "old_access_token_aabbccdd"
        refresh = "refresh_token_11223344"
        oauth.info("Current tokens", extra={
            "access_prefix": old_access[:12],
            "refresh_prefix": refresh[:12],
            "access_expires_in": 0,
        })

    with step("Detect expired access token"):
        oauth.warning("Access token expired", extra={"checked_at": "2026-04-02T10:00:00Z"})
        with step("Check refresh token validity"):
            oauth.info("Refresh token still valid", extra={"expires_at": "2026-04-09T10:00:00Z"})

    with step("Request new access token"):
        oauth.info("POST /token", extra={"grant_type": "refresh_token", "provider": "google"})
        with step("Send refresh request"):
            new_access = hashlib.sha256(b"new_access").hexdigest()[:40]
            oauth.info("New access token received", extra={
                "new_prefix": new_access[:12],
                "expires_in": 3600,
            })
        with step("Optionally rotate refresh token"):
            new_refresh = hashlib.sha256(b"new_refresh").hexdigest()[:40]
            oauth.debug("Refresh token rotated", extra={"old_prefix": refresh[:12], "new_prefix": new_refresh[:12]})

    with step("Update stored tokens"):
        store = log.getChild("token_store")
        store.info("Tokens updated in database", extra={"user_id": "usr_42", "provider": "google"})
        store.debug("Old tokens invalidated")

    assert new_access != old_access


def test_oauth_refresh_token_expired():
    """Refresh token itself is expired -- user must re-authenticate."""
    oauth = log.getChild("oauth")

    with step("Attempt refresh with expired refresh token"):
        oauth.warning("Refresh token expired", extra={
            "expired_at": "2026-03-25T10:00:00Z",
            "now": "2026-04-02T10:00:00Z",
        })
        with step("Server returns invalid_grant"):
            oauth.error("Token refresh failed", extra={"error": "invalid_grant", "status": 400})

    with step("Trigger re-authentication"):
        oauth.info("Clearing stored tokens", extra={"user_id": "usr_42"})
        oauth.info("Redirecting to authorization URL", extra={"provider": "google"})

    needs_reauth = True
    assert needs_reauth


# ---------------------------------------------------------------------------
# Token revocation
# ---------------------------------------------------------------------------


def test_oauth_token_revocation():
    """Revoke an access token on logout."""
    oauth = log.getChild("oauth")

    with step("User initiates logout"):
        oauth.info("Logout requested", extra={"user_id": "usr_42", "provider": "google"})

    with step("Revoke access token"):
        oauth.info("POST to revocation endpoint", extra={
            "url": "https://oauth2.googleapis.com/revoke",
            "token_type_hint": "access_token",
        })
        with step("Send revocation request"):
            oauth.info("Access token revoked", extra={"status": 200})

    with step("Revoke refresh token"):
        oauth.info("POST to revocation endpoint", extra={"token_type_hint": "refresh_token"})
        with step("Send revocation request"):
            oauth.info("Refresh token revoked", extra={"status": 200})

    with step("Clean up local session"):
        session = log.getChild("session")
        session.info("Local session destroyed", extra={"user_id": "usr_42"})
        session.info("Cookies cleared", extra={"cookies": ["session_id", "csrf_token"]})

    assert True


# ---------------------------------------------------------------------------
# PKCE (Proof Key for Code Exchange)
# ---------------------------------------------------------------------------


def test_oauth_pkce_flow():
    """Verify PKCE challenge/verifier in authorization flow."""
    oauth = log.getChild("oauth")

    with step("Generate PKCE code verifier"):
        import base64
        import os
        verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
        oauth.info("Code verifier generated", extra={"length": len(verifier)})

    with step("Compute code challenge"):
        import hashlib as _hl
        challenge = base64.urlsafe_b64encode(
            _hl.sha256(verifier.encode()).digest()
        ).rstrip(b"=").decode()
        oauth.info("Code challenge computed", extra={
            "method": "S256",
            "challenge_length": len(challenge),
        })

    with step("Include challenge in authorize URL"):
        with step("Append code_challenge param"):
            oauth.debug("Authorize params", extra={
                "code_challenge": challenge[:20] + "...",
                "code_challenge_method": "S256",
            })

    with step("Token exchange with verifier"):
        with step("Include code_verifier in POST body"):
            oauth.info("Verifier sent with token request", extra={"verifier_length": len(verifier)})
        with step("Server validates S256(verifier) == challenge"):
            oauth.info("PKCE validation passed", extra={"match": True})

    assert len(verifier) >= 43
    assert len(challenge) >= 43


# ---------------------------------------------------------------------------
# Scope management
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "requested_scopes,granted_scopes,expect_match",
    [
        (["openid", "email"], ["openid", "email"], True),
        (["openid", "email", "profile"], ["openid", "email"], False),
        (["read:user"], ["read:user", "user:email"], True),
    ],
    ids=["exact-match", "partial-grant", "superset-granted"],
)
def test_oauth_scope_negotiation(requested_scopes, granted_scopes, expect_match):
    """Verify scope negotiation between request and grant."""
    oauth = log.getChild("oauth")

    with step("Request scopes"):
        oauth.info("Scopes requested", extra={"scopes": requested_scopes})

    with step("Evaluate granted scopes"):
        oauth.info("Scopes granted", extra={"scopes": granted_scopes})
        with step("Check if all requested scopes granted"):
            all_granted = set(requested_scopes).issubset(set(granted_scopes))
            oauth.info("Scope check", extra={"all_requested_granted": all_granted, "expected": expect_match})

    assert all_granted == expect_match


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_oauth_callback_invalid_state():
    """Reject callback when state parameter does not match."""
    oauth = log.getChild("oauth")

    with step("Receive callback with mismatched state"):
        oauth.warning("State mismatch", extra={
            "expected": "abc123",
            "received": "xyz789",
        })
        with step("Abort token exchange"):
            oauth.error("CSRF protection triggered", extra={"action": "reject"})

    with step("Return error to user"):
        oauth.info("Redirecting to login with error", extra={"error": "state_mismatch"})

    state_valid = False
    assert not state_valid, "Mismatched state should be rejected"


def test_oauth_callback_missing_code():
    """Handle callback with error instead of authorization code."""
    oauth = log.getChild("oauth")

    with step("Receive error callback"):
        error = "access_denied"
        description = "The user denied the request"
        oauth.warning("Authorization denied", extra={"error": error, "description": description})

    with step("Map error to user message"):
        oauth.info("User-facing message", extra={"data": {"message": "You denied access. Please try again."}})

    assert error == "access_denied"


# ---------------------------------------------------------------------------
# Provider-specific quirks
# ---------------------------------------------------------------------------


def test_oauth_apple_id_token_name_claim():
    """Apple only sends name on first authorization -- verify handling."""
    oauth = log.getChild("oauth")

    with step("First authorization -- name present"):
        claims_first = {"sub": "apple_001", "email": "user@icloud.com", "name": {"firstName": "Jane", "lastName": "Doe"}}
        oauth.info("First auth claims", extra={"data": claims_first})
        with step("Store name locally"):
            oauth.info("Name saved", extra={"first": "Jane", "last": "Doe"})

    with step("Subsequent authorization -- name absent"):
        claims_second = {"sub": "apple_001", "email": "user@icloud.com"}
        oauth.info("Re-auth claims", extra={"data": claims_second})
        with step("Fallback to stored name"):
            oauth.info("Using stored name", extra={"first": "Jane", "last": "Doe"})

    assert "name" not in claims_second


def test_oauth_github_no_email_in_profile():
    """GitHub may hide email -- verify fallback to /user/emails API."""
    oauth = log.getChild("oauth")

    with step("Fetch GitHub profile"):
        profile = {"login": "octocat", "id": 1, "email": None}
        oauth.info("Profile fetched", extra={"data": profile})
        with step("Email is null"):
            oauth.warning("Email not in profile, fetching from /user/emails")

    with step("Fetch email from /user/emails"):
        emails = [
            {"email": "octocat@github.com", "primary": True, "verified": True},
            {"email": "octocat@example.com", "primary": False, "verified": True},
        ]
        oauth.info("Emails fetched", extra={"count": len(emails)})
        with step("Select primary verified email"):
            primary = next(e for e in emails if e["primary"] and e["verified"])
            oauth.info("Email selected", extra={"email": primary["email"]})

    assert primary["email"] == "octocat@github.com"


# ---------------------------------------------------------------------------
# Skip and flaky tests
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="LinkedIn OAuth app not provisioned in test environment")
def test_oauth_linkedin_login():
    """LinkedIn OAuth login flow."""
    log.info("Skipped")


@pytest.mark.skip(reason="Twitter/X OAuth 2.0 migration pending")
def test_oauth_twitter_login():
    """Twitter/X OAuth login flow."""
    log.info("Skipped")


def test_oauth_with_flaky_provider_discovery(flaky_service):
    """OpenID Connect discovery endpoint is flaky."""
    oauth = log.getChild("oauth")

    with step("Fetch .well-known/openid-configuration"):
        oauth.info("GET discovery document", extra={"url": "https://accounts.google.com/.well-known/openid-configuration"})
        with step("Send HTTP request"):
            result = flaky_service("oauth_discovery")
            oauth.info("Discovery document received", extra={"result": result})

    with step("Parse discovery document"):
        oauth.debug("Endpoints extracted", extra={
            "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_endpoint": "https://oauth2.googleapis.com/token",
        })

    assert result.startswith("ok")


def test_oauth_with_flaky_token_endpoint(flaky_service):
    """Token endpoint is temporarily unavailable."""
    oauth = log.getChild("oauth")

    with step("Authorization code received"):
        oauth.info("Code captured", extra={"code_prefix": "4/0AX4..."})

    with step("Exchange code for token"):
        oauth.info("POST to token endpoint", extra={"provider": "google"})
        with step("Send request"):
            result = flaky_service("oauth_token_endpoint")
            oauth.info("Token received", extra={"result": result})

    assert result.startswith("ok")


# ---------------------------------------------------------------------------
# Deliberate failures
# ---------------------------------------------------------------------------


def test_oauth_id_token_audience_validation():
    """ID token audience must match our client_id -- deliberate failure."""
    oauth = log.getChild("oauth")

    with step("Decode ID token"):
        claims = {
            "iss": "https://accounts.google.com",
            "sub": "google_user_001",
            "aud": "wrong-client-id.apps.googleusercontent.com",
            "exp": 1711903600,
        }
        oauth.info("ID token claims", extra={"data": claims})

    with step("Validate audience claim"):
        expected_aud = "google-client-id-123.apps.googleusercontent.com"
        actual_aud = claims["aud"]
        oauth.error("Audience mismatch", extra={"expected": expected_aud, "actual": actual_aud})

    assert actual_aud == expected_aud, (
        f"ID token audience '{actual_aud}' does not match expected '{expected_aud}'"
    )


def test_oauth_token_exchange_latency():
    """Token exchange must complete within 3s -- deliberate failure."""
    perf = log.getChild("performance")

    with step("Measure token exchange time"):
        perf.info("Timer started")
        with step("POST /token"):
            elapsed = 4.82
            perf.warning("Slow token exchange", extra={"elapsed_seconds": elapsed})

    with step("Evaluate SLA"):
        perf.error("SLA breached", extra={"actual": elapsed, "max_allowed": 3.0})

    assert elapsed < 3.0, f"Token exchange took {elapsed}s, expected < 3.0s"
