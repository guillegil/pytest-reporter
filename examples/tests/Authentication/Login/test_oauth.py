"""OAuth / OpenID Connect login tests -- provider flows, token exchange, refresh, revocation."""

from __future__ import annotations

import hashlib
import time
import urllib.parse

import pytest

from pytest_reporter import step, substep


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
def test_oauth_authorize_url(log, provider):
    """Verify the authorization URL is well-formed for each provider."""
    oauth = log.child("oauth")

    with step(f"Build authorize URL for {provider}"):
        state = hashlib.sha256(f"state:{time.time()}".encode()).hexdigest()[:16]
        nonce = hashlib.sha256(f"nonce:{time.time()}".encode()).hexdigest()[:16]
        oauth.info("Generating state + nonce", data={"state": state, "nonce": nonce})
        substep("Assemble query parameters")
        url = _build_auth_url(provider, state, nonce)
        oauth.info("URL built", data={"url_length": len(url), "provider": provider})

    with step("Validate URL components"):
        parsed = urllib.parse.urlparse(url)
        params = urllib.parse.parse_qs(parsed.query)
        oauth.debug("Parsed URL", data={
            "scheme": parsed.scheme,
            "host": parsed.hostname,
            "params": list(params.keys()),
        })
        substep("Check required params present")
        required = {"client_id", "redirect_uri", "response_type", "scope", "state", "nonce"}
        missing = required - set(params.keys())
        oauth.info("Param check", data={"required": list(required), "missing": list(missing)})

    assert parsed.scheme == "https"
    assert len(missing) == 0


# ---------------------------------------------------------------------------
# Token exchange
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("provider", ["google", "github", "microsoft"])
def test_oauth_token_exchange(log, provider):
    """Simulate authorization code -> token exchange."""
    oauth = log.child("oauth")
    token_log = oauth.child("token_exchange")

    with step("Receive authorization callback"):
        code = f"4/0AX4XfW-{provider}-mock-code"
        state = "abc123state"
        oauth.info("Callback received", data={"provider": provider, "code_length": len(code)})
        substep("Validate state parameter")
        oauth.info("State validated", data={"expected": state, "received": state, "match": True})

    with step("Exchange code for tokens"):
        token_log.info("POST to token endpoint", data={
            "url": _PROVIDERS[provider]["token_url"],
            "grant_type": "authorization_code",
        })
        substep("Send request")
        tokens = _simulate_token_exchange(provider, code)
        token_log.info("Token response received", data={
            "has_access_token": bool(tokens["access_token"]),
            "has_refresh_token": bool(tokens["refresh_token"]),
            "expires_in": tokens["expires_in"],
        })
        substep("Validate token type")
        token_log.debug("Token type", data={"type": tokens["token_type"]})

    with step("Decode ID token"):
        id_token = tokens["id_token"]
        oauth.info("ID token received", data={"parts": len(id_token.split(".")), "provider": provider})
        substep("Verify JWT signature")
        oauth.info("Signature verification", data={"valid": True, "algo": "RS256"})
        substep("Extract claims")
        oauth.debug("Claims", data={"sub": f"{provider}_user_001", "email": f"user@{provider}.example"})

    with step("Create local user session"):
        session = log.child("session")
        session.info("User mapped to local account", data={"provider": provider, "local_id": "usr_42"})
        session.info("Session created", data={"ttl": tokens["expires_in"]})

    assert tokens["access_token"]
    assert tokens["token_type"] == "Bearer"


# ---------------------------------------------------------------------------
# Refresh token flow
# ---------------------------------------------------------------------------


def test_oauth_refresh_token(log):
    """Verify access token refresh via refresh_token grant."""
    oauth = log.child("oauth")

    with step("Setup: existing tokens"):
        old_access = "old_access_token_aabbccdd"
        refresh = "refresh_token_11223344"
        oauth.info("Current tokens", data={
            "access_prefix": old_access[:12],
            "refresh_prefix": refresh[:12],
            "access_expires_in": 0,
        })

    with step("Detect expired access token"):
        oauth.warning("Access token expired", data={"checked_at": "2026-04-02T10:00:00Z"})
        substep("Check refresh token validity")
        oauth.info("Refresh token still valid", data={"expires_at": "2026-04-09T10:00:00Z"})

    with step("Request new access token"):
        oauth.info("POST /token", data={"grant_type": "refresh_token", "provider": "google"})
        substep("Send refresh request")
        new_access = hashlib.sha256(b"new_access").hexdigest()[:40]
        oauth.info("New access token received", data={
            "new_prefix": new_access[:12],
            "expires_in": 3600,
        })
        substep("Optionally rotate refresh token")
        new_refresh = hashlib.sha256(b"new_refresh").hexdigest()[:40]
        oauth.debug("Refresh token rotated", data={"old_prefix": refresh[:12], "new_prefix": new_refresh[:12]})

    with step("Update stored tokens"):
        store = log.child("token_store")
        store.info("Tokens updated in database", data={"user_id": "usr_42", "provider": "google"})
        store.debug("Old tokens invalidated")

    assert new_access != old_access


def test_oauth_refresh_token_expired(log):
    """Refresh token itself is expired -- user must re-authenticate."""
    oauth = log.child("oauth")

    with step("Attempt refresh with expired refresh token"):
        oauth.warning("Refresh token expired", data={
            "expired_at": "2026-03-25T10:00:00Z",
            "now": "2026-04-02T10:00:00Z",
        })
        substep("Server returns invalid_grant")
        oauth.error("Token refresh failed", data={"error": "invalid_grant", "status": 400})

    with step("Trigger re-authentication"):
        oauth.info("Clearing stored tokens", data={"user_id": "usr_42"})
        oauth.info("Redirecting to authorization URL", data={"provider": "google"})

    needs_reauth = True
    assert needs_reauth


# ---------------------------------------------------------------------------
# Token revocation
# ---------------------------------------------------------------------------


def test_oauth_token_revocation(log):
    """Revoke an access token on logout."""
    oauth = log.child("oauth")

    with step("User initiates logout"):
        oauth.info("Logout requested", data={"user_id": "usr_42", "provider": "google"})

    with step("Revoke access token"):
        oauth.info("POST to revocation endpoint", data={
            "url": "https://oauth2.googleapis.com/revoke",
            "token_type_hint": "access_token",
        })
        substep("Send revocation request")
        oauth.info("Access token revoked", data={"status": 200})

    with step("Revoke refresh token"):
        oauth.info("POST to revocation endpoint", data={"token_type_hint": "refresh_token"})
        substep("Send revocation request")
        oauth.info("Refresh token revoked", data={"status": 200})

    with step("Clean up local session"):
        session = log.child("session")
        session.info("Local session destroyed", data={"user_id": "usr_42"})
        session.info("Cookies cleared", data={"cookies": ["session_id", "csrf_token"]})

    assert True


# ---------------------------------------------------------------------------
# PKCE (Proof Key for Code Exchange)
# ---------------------------------------------------------------------------


def test_oauth_pkce_flow(log):
    """Verify PKCE challenge/verifier in authorization flow."""
    oauth = log.child("oauth")

    with step("Generate PKCE code verifier"):
        import base64
        import os
        verifier = base64.urlsafe_b64encode(os.urandom(32)).rstrip(b"=").decode()
        oauth.info("Code verifier generated", data={"length": len(verifier)})

    with step("Compute code challenge"):
        import hashlib as _hl
        challenge = base64.urlsafe_b64encode(
            _hl.sha256(verifier.encode()).digest()
        ).rstrip(b"=").decode()
        oauth.info("Code challenge computed", data={
            "method": "S256",
            "challenge_length": len(challenge),
        })

    with step("Include challenge in authorize URL"):
        substep("Append code_challenge param")
        oauth.debug("Authorize params", data={
            "code_challenge": challenge[:20] + "...",
            "code_challenge_method": "S256",
        })

    with step("Token exchange with verifier"):
        substep("Include code_verifier in POST body")
        oauth.info("Verifier sent with token request", data={"verifier_length": len(verifier)})
        substep("Server validates S256(verifier) == challenge")
        oauth.info("PKCE validation passed", data={"match": True})

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
def test_oauth_scope_negotiation(log, requested_scopes, granted_scopes, expect_match):
    """Verify scope negotiation between request and grant."""
    oauth = log.child("oauth")

    with step("Request scopes"):
        oauth.info("Scopes requested", data={"scopes": requested_scopes})

    with step("Evaluate granted scopes"):
        oauth.info("Scopes granted", data={"scopes": granted_scopes})
        substep("Check if all requested scopes granted")
        all_granted = set(requested_scopes).issubset(set(granted_scopes))
        oauth.info("Scope check", data={"all_requested_granted": all_granted, "expected": expect_match})

    assert all_granted == expect_match


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


def test_oauth_callback_invalid_state(log):
    """Reject callback when state parameter does not match."""
    oauth = log.child("oauth")

    with step("Receive callback with mismatched state"):
        oauth.warning("State mismatch", data={
            "expected": "abc123",
            "received": "xyz789",
        })
        substep("Abort token exchange")
        oauth.error("CSRF protection triggered", data={"action": "reject"})

    with step("Return error to user"):
        oauth.info("Redirecting to login with error", data={"error": "state_mismatch"})

    state_valid = False
    assert not state_valid, "Mismatched state should be rejected"


def test_oauth_callback_missing_code(log):
    """Handle callback with error instead of authorization code."""
    oauth = log.child("oauth")

    with step("Receive error callback"):
        error = "access_denied"
        description = "The user denied the request"
        oauth.warning("Authorization denied", data={"error": error, "description": description})

    with step("Map error to user message"):
        oauth.info("User-facing message", data={"message": "You denied access. Please try again."})

    assert error == "access_denied"


# ---------------------------------------------------------------------------
# Provider-specific quirks
# ---------------------------------------------------------------------------


def test_oauth_apple_id_token_name_claim(log):
    """Apple only sends name on first authorization -- verify handling."""
    oauth = log.child("oauth")

    with step("First authorization -- name present"):
        claims_first = {"sub": "apple_001", "email": "user@icloud.com", "name": {"firstName": "Jane", "lastName": "Doe"}}
        oauth.info("First auth claims", data=claims_first)
        substep("Store name locally")
        oauth.info("Name saved", data={"first": "Jane", "last": "Doe"})

    with step("Subsequent authorization -- name absent"):
        claims_second = {"sub": "apple_001", "email": "user@icloud.com"}
        oauth.info("Re-auth claims", data=claims_second)
        substep("Fallback to stored name")
        oauth.info("Using stored name", data={"first": "Jane", "last": "Doe"})

    assert "name" not in claims_second


def test_oauth_github_no_email_in_profile(log):
    """GitHub may hide email -- verify fallback to /user/emails API."""
    oauth = log.child("oauth")

    with step("Fetch GitHub profile"):
        profile = {"login": "octocat", "id": 1, "email": None}
        oauth.info("Profile fetched", data=profile)
        substep("Email is null")
        oauth.warning("Email not in profile, fetching from /user/emails")

    with step("Fetch email from /user/emails"):
        emails = [
            {"email": "octocat@github.com", "primary": True, "verified": True},
            {"email": "octocat@example.com", "primary": False, "verified": True},
        ]
        oauth.info("Emails fetched", data={"count": len(emails)})
        substep("Select primary verified email")
        primary = next(e for e in emails if e["primary"] and e["verified"])
        oauth.info("Email selected", data={"email": primary["email"]})

    assert primary["email"] == "octocat@github.com"


# ---------------------------------------------------------------------------
# Skip and flaky tests
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="LinkedIn OAuth app not provisioned in test environment")
def test_oauth_linkedin_login(log):
    """LinkedIn OAuth login flow."""
    log.info("Skipped")


@pytest.mark.skip(reason="Twitter/X OAuth 2.0 migration pending")
def test_oauth_twitter_login(log):
    """Twitter/X OAuth login flow."""
    log.info("Skipped")


def test_oauth_with_flaky_provider_discovery(log, flaky_service):
    """OpenID Connect discovery endpoint is flaky."""
    oauth = log.child("oauth")

    with step("Fetch .well-known/openid-configuration"):
        oauth.info("GET discovery document", data={"url": "https://accounts.google.com/.well-known/openid-configuration"})
        substep("Send HTTP request")
        result = flaky_service("oauth_discovery")
        oauth.info("Discovery document received", data={"result": result})

    with step("Parse discovery document"):
        oauth.debug("Endpoints extracted", data={
            "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
            "token_endpoint": "https://oauth2.googleapis.com/token",
        })

    assert result.startswith("ok")


def test_oauth_with_flaky_token_endpoint(log, flaky_service):
    """Token endpoint is temporarily unavailable."""
    oauth = log.child("oauth")

    with step("Authorization code received"):
        oauth.info("Code captured", data={"code_prefix": "4/0AX4..."})

    with step("Exchange code for token"):
        oauth.info("POST to token endpoint", data={"provider": "google"})
        substep("Send request")
        result = flaky_service("oauth_token_endpoint")
        oauth.info("Token received", data={"result": result})

    assert result.startswith("ok")


# ---------------------------------------------------------------------------
# Deliberate failures
# ---------------------------------------------------------------------------


def test_oauth_id_token_audience_validation(log):
    """ID token audience must match our client_id -- deliberate failure."""
    oauth = log.child("oauth")

    with step("Decode ID token"):
        claims = {
            "iss": "https://accounts.google.com",
            "sub": "google_user_001",
            "aud": "wrong-client-id.apps.googleusercontent.com",
            "exp": 1711903600,
        }
        oauth.info("ID token claims", data=claims)

    with step("Validate audience claim"):
        expected_aud = "google-client-id-123.apps.googleusercontent.com"
        actual_aud = claims["aud"]
        oauth.error("Audience mismatch", data={"expected": expected_aud, "actual": actual_aud})

    assert actual_aud == expected_aud, (
        f"ID token audience '{actual_aud}' does not match expected '{expected_aud}'"
    )


def test_oauth_token_exchange_latency(log):
    """Token exchange must complete within 3s -- deliberate failure."""
    perf = log.child("performance")

    with step("Measure token exchange time"):
        perf.info("Timer started")
        substep("POST /token")
        elapsed = 4.82
        perf.warning("Slow token exchange", data={"elapsed_seconds": elapsed})

    with step("Evaluate SLA"):
        perf.error("SLA breached", data={"actual": elapsed, "max_allowed": 3.0})

    assert elapsed < 3.0, f"Token exchange took {elapsed}s, expected < 3.0s"
