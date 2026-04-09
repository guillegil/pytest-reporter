"""Form validation and rendering tests -- simulated input handling, validation rules, and submission."""

from __future__ import annotations

import re

import pytest

from pytest_reporter import step, substep


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def form_engine(log):
    """Set up a simulated form rendering and validation engine."""
    engine = log.child("form-engine")
    engine.info("Initializing form engine v2.4.0")
    engine.info("Loading validation rule library", data={"rules": 18, "locale": "en-US"})
    engine.debug("Rule list: required, email, min_length, max_length, pattern, ...")
    engine.info("Registering custom validators", data={"custom": ["phone_us", "postal_code", "tax_id"]})
    engine.info("i18n messages loaded", data={"locale": "en-US", "messages": 52})
    engine.info("Form engine ready")
    yield {"version": "2.4.0", "rules": 18}
    engine.info("Form engine disposed")


# ---------------------------------------------------------------------------
# Parametrize data
# ---------------------------------------------------------------------------

VALID_EMAILS = [
    "user@example.com",
    "admin+tag@company.co.uk",
    "first.last@subdomain.example.org",
    "test123@numbers.io",
]

INVALID_EMAILS = [
    "",
    "not-an-email",
    "@missing-local.com",
    "missing-domain@",
    "spaces in@email.com",
    "double@@at.com",
]

PASSWORD_CASES = [
    ("Ab1!abcd", True, "meets all requirements"),
    ("short1!", False, "too short (< 8 chars)"),
    ("alllowercase1!", False, "missing uppercase letter"),
    ("ALLUPPERCASE1!", False, "missing lowercase letter"),
    ("NoSpecialChar1", False, "missing special character"),
    ("NoDigits!abc", False, "missing digit"),
]

PHONE_FORMATS = [
    ("+1 (555) 123-4567", True),
    ("555-123-4567", True),
    ("5551234567", True),
    ("123", False),
    ("+44 20 7946 0958", False),  # Non-US number
]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("email", VALID_EMAILS, ids=[e.split("@")[0] for e in VALID_EMAILS])
def test_valid_email_accepted(log, form_engine, email):
    """Verify valid email addresses pass validation."""
    v = log.child("email-validator")

    with step("Parse email address"):
        v.info("Input value", data={"email": email, "length": len(email)})
        local, domain = email.split("@")
        v.debug("Parsed parts", data={"local": local, "domain": domain})
        substep("Validate local part")
        v.info("Local part valid", data={"local": local, "has_plus": "+" in local, "has_dot": "." in local})
        substep("Validate domain part")
        v.info("Domain valid", data={"domain": domain, "tld": domain.split(".")[-1]})

    with step("Run validation pipeline"):
        v.info("Rule: required -- PASS (non-empty)")
        v.info("Rule: format -- checking RFC 5322 pattern")
        v.debug("Pattern: ^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\\.[a-zA-Z]{2,}$")
        v.info("Rule: format -- PASS")
        substep("Check DNS (simulated)")
        v.info("MX record lookup", data={"domain": domain, "mx_found": True})
        v.info("All validation rules passed")

    with step("Update form state"):
        v.info("Field 'email': valid", data={"value": email, "errors": [], "touched": True})
        v.debug("Error message cleared")
        v.info("Submit button enabled")

    assert "@" in email


@pytest.mark.parametrize("email", INVALID_EMAILS, ids=[f"invalid-{i}" for i in range(len(INVALID_EMAILS))])
def test_invalid_email_rejected(log, form_engine, email):
    """Verify invalid email addresses fail validation."""
    v = log.child("email-validator")

    with step("Attempt email validation"):
        v.info("Input value", data={"email": email, "length": len(email)})
        if not email:
            v.info("Rule: required -- FAIL (empty string)")
            error = "Email is required"
        elif "@" not in email:
            v.info("Rule: format -- FAIL (no @ symbol)")
            error = "Invalid email format"
        else:
            parts = email.split("@")
            v.info("Rule: format -- checking parts", data={"parts": parts})
            v.info("Rule: format -- FAIL")
            error = "Invalid email format"

    with step("Display error state"):
        v.info("Field 'email': invalid", data={"value": email, "errors": [error]})
        v.info("Error message displayed", data={"message": error, "color": "#EF4444"})
        substep("Update field visual state")
        v.info("Border color changed to error red")
        v.info("Error icon shown")
        v.debug("Submit button remains disabled")

    # All these should fail validation
    valid_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    assert not valid_pattern.match(email)


@pytest.mark.parametrize(
    "password,expected_valid,reason",
    PASSWORD_CASES,
    ids=[p[2].replace(" ", "-") for p in PASSWORD_CASES],
)
def test_password_strength_validation(log, form_engine, password, expected_valid, reason):
    """Test password validation rules."""
    pw = log.child("password-validator")

    with step("Evaluate password strength"):
        pw.info("Input received", data={"length": len(password), "reason": reason})
        checks = {
            "min_length_8": len(password) >= 8,
            "has_uppercase": any(c.isupper() for c in password),
            "has_lowercase": any(c.islower() for c in password),
            "has_digit": any(c.isdigit() for c in password),
            "has_special": bool(re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)),
        }
        for rule, passed in checks.items():
            substep(f"Check: {rule}")
            pw.info(f"Rule '{rule}': {'PASS' if passed else 'FAIL'}", data={"rule": rule, "passed": passed})

    with step("Compute strength score"):
        score = sum(checks.values())
        strength = "weak" if score < 3 else "fair" if score < 4 else "strong"
        pw.info("Strength computed", data={"score": score, "max": 5, "strength": strength})
        substep("Update strength meter UI")
        colors = {"weak": "#EF4444", "fair": "#F59E0B", "strong": "#22C55E"}
        pw.info("Meter color", data={"color": colors[strength], "width_pct": score * 20})

    with step("Determine validity"):
        is_valid = all(checks.values())
        pw.info("Final result", data={"valid": is_valid, "expected": expected_valid})

    assert is_valid == expected_valid


@pytest.mark.parametrize(
    "phone,expected_valid",
    PHONE_FORMATS,
    ids=[f"phone-{i}" for i in range(len(PHONE_FORMATS))],
)
def test_phone_number_format(log, form_engine, phone, expected_valid):
    """Validate US phone number formats."""
    ph = log.child("phone-validator")

    with step("Normalize phone input"):
        ph.info("Raw input", data={"value": phone})
        digits = re.sub(r"\D", "", phone)
        ph.info("Extracted digits", data={"digits": digits, "count": len(digits)})
        substep("Check country code")
        if digits.startswith("1") and len(digits) == 11:
            digits = digits[1:]
            ph.info("US country code stripped", data={"remaining": digits})
        elif len(digits) == 10:
            ph.info("10-digit US number detected")
        else:
            ph.warning("Unexpected digit count", data={"count": len(digits)})

    with step("Validate format"):
        is_valid = len(digits) == 10 and digits.isdigit()
        ph.info("Validation result", data={"valid": is_valid, "expected": expected_valid})
        if is_valid:
            formatted = f"({digits[:3]}) {digits[3:6]}-{digits[6:]}"
            ph.info("Formatted output", data={"formatted": formatted})
        else:
            ph.info("Validation failed", data={"reason": "incorrect digit count" if len(digits) != 10 else "non-numeric"})

    assert is_valid == expected_valid


def test_registration_form_complete(log, form_engine):
    """Test complete registration form submission workflow."""
    form = log.child("registration")

    fields = {
        "first_name": "Jane",
        "last_name": "Doe",
        "email": "jane.doe@example.com",
        "password": "Str0ng!Pass",
        "confirm_password": "Str0ng!Pass",
        "phone": "555-867-5309",
        "accept_terms": True,
    }

    with step("Fill out registration form"):
        for field_name, value in fields.items():
            substep(f"Set field: {field_name}")
            form.info(f"Setting '{field_name}'", data={"value": str(value), "type": type(value).__name__})
            form.debug(f"onChange fired for '{field_name}'")

    with step("Client-side validation"):
        form.info("Running validation on all fields")
        for field_name in fields:
            form.debug(f"Validating '{field_name}': PASS")
        form.info("All fields valid", data={"field_count": len(fields), "errors": 0})
        substep("Cross-field validation")
        form.info("Password match check: PASS")
        form.info("Terms accepted: PASS")

    with step("Submit form"):
        form.info("Submitting to POST /api/register")
        form.info("Request payload prepared", data={
            "fields": list(fields.keys()),
            "content_type": "application/json",
            "csrf_token": "abc123def456",
        })
        substep("Simulate server response")
        form.info("Response received", data={"status": 201, "user_id": "usr_9f8e7d6c"})
        form.info("Redirect to /welcome")

    assert len(fields) == 7


def test_form_dirty_state_tracking(log, form_engine):
    """Test that form tracks dirty state for unsaved changes warning."""
    form = log.child("dirty-tracking")

    with step("Initialize form with server data"):
        initial = {"name": "Acme Corp", "email": "admin@acme.com", "plan": "pro"}
        form.info("Form initialized", data={"initial_values": initial})
        form.info("Dirty state: False (pristine)")

    with step("Modify field values"):
        form.info("User changed 'name' to 'Acme Corporation'")
        form.debug("Dirty fields: ['name']")
        form.info("Dirty state: True")
        substep("Track field-level changes")
        form.info("Field diff", data={
            "name": {"original": "Acme Corp", "current": "Acme Corporation", "dirty": True},
            "email": {"original": "admin@acme.com", "current": "admin@acme.com", "dirty": False},
            "plan": {"original": "pro", "current": "pro", "dirty": False},
        })

    with step("Revert field to original"):
        form.info("User changed 'name' back to 'Acme Corp'")
        form.debug("Dirty fields: []")
        form.info("Dirty state: False (reverted to pristine)")

    with step("Modify and attempt navigation"):
        form.info("User changed 'plan' to 'enterprise'")
        form.info("Dirty state: True")
        substep("Intercept navigation")
        form.info("beforeunload handler triggered")
        form.info("Unsaved changes dialog shown", data={"message": "You have unsaved changes. Leave anyway?"})

    assert True


def test_multi_step_wizard(log, form_engine):
    """Test multi-step form wizard navigation and state persistence."""
    wiz = log.child("wizard")

    steps_data = [
        ("Personal Info", {"name": "Alice", "dob": "1990-05-15"}),
        ("Address", {"street": "123 Main St", "city": "Portland", "state": "OR", "zip": "97201"}),
        ("Payment", {"card_last4": "4242", "exp": "12/28"}),
        ("Review", {}),
    ]

    with step("Initialize wizard"):
        wiz.info("Wizard created", data={"total_steps": len(steps_data), "current": 0})
        wiz.info("Progress bar: 0% complete")
        wiz.debug("Step validation rules loaded")

    for i, (step_name, data) in enumerate(steps_data[:-1]):
        with step(f"Complete step {i + 1}: {step_name}"):
            wiz.info(f"Step {i + 1} active: {step_name}")
            for field, value in data.items():
                substep(f"Fill: {field}")
                wiz.info(f"Set '{field}' = '{value}'")
            wiz.info("Step validation passed")
            substep("Navigate to next step")
            wiz.info(f"Progress: {(i + 1) * 25}%")

    with step("Review and submit"):
        wiz.info("All steps complete, showing review summary")
        for i, (name, data) in enumerate(steps_data[:-1]):
            wiz.info(f"Section '{name}'", data=data)
        substep("Submit wizard data")
        wiz.info("Wizard submitted successfully", data={"redirect": "/dashboard"})

    assert len(steps_data) == 4


def test_inline_edit_field(log, form_engine):
    """Test inline-editable field component behavior."""
    edit = log.child("inline-edit")

    with step("Render in display mode"):
        edit.info("Rendering inline field", data={"field": "company_name", "value": "Acme Corp", "mode": "display"})
        edit.debug("Pencil icon rendered beside text")
        edit.info("Double-click listener attached")

    with step("Switch to edit mode"):
        edit.info("Double-click detected on field")
        substep("Transform to input")
        edit.info("Display text replaced with <input>", data={"type": "text", "value": "Acme Corp"})
        edit.info("Input focused and text selected")
        edit.debug("Escape key listener attached for cancel")

    with step("Edit and save"):
        edit.info("User typed 'Acme Corporation'")
        edit.info("Enter key pressed")
        substep("Validate inline")
        edit.info("Validation passed (non-empty, max 100 chars)")
        substep("Save via API")
        edit.info("PATCH /api/company/name", data={"old": "Acme Corp", "new": "Acme Corporation"})
        edit.info("API response: 200 OK")
        substep("Return to display mode")
        edit.info("Input replaced with updated text")

    assert True


def test_file_upload_form(log, form_engine):
    """Test file upload with drag-and-drop and validation."""
    upload = log.child("file-upload")

    with step("Render upload zone"):
        upload.info("Drop zone initialized", data={"accept": ".pdf,.png,.jpg", "max_size_mb": 10, "multiple": True})
        upload.debug("Drag-and-drop event listeners attached")
        upload.info("Upload zone rendered with placeholder text")

    with step("Simulate file drop"):
        files = [
            {"name": "report.pdf", "size_kb": 2048, "type": "application/pdf"},
            {"name": "chart.png", "size_kb": 512, "type": "image/png"},
            {"name": "photo.jpg", "size_kb": 3072, "type": "image/jpeg"},
        ]
        upload.info("Drop event received", data={"file_count": len(files)})
        for f in files:
            substep(f"Validate: {f['name']}")
            upload.info(f"File '{f['name']}'", data=f)
            upload.debug(f"Extension check: PASS")
            upload.debug(f"Size check: {f['size_kb']}KB < 10240KB -- PASS")

    with step("Upload files"):
        for f in files:
            substep(f"Upload: {f['name']}")
            upload.info(f"Uploading '{f['name']}'", data={"progress": "0%"})
            upload.info(f"Upload progress", data={"file": f["name"], "progress": "50%"})
            upload.info(f"Upload complete", data={"file": f["name"], "progress": "100%", "url": f"/uploads/{f['name']}"})
        upload.info("All files uploaded", data={"total_files": 3, "total_size_kb": sum(f["size_kb"] for f in files)})

    assert len(files) == 3


@pytest.mark.skip(reason="Captcha service mock not available")
def test_captcha_integration(log, form_engine):
    """Test reCAPTCHA integration in form submission."""
    pass


@pytest.mark.skip(reason="Address autocomplete API key not configured for CI")
def test_address_autocomplete(log, form_engine):
    """Test address autocomplete dropdown from Google Places API."""
    pass


def test_date_picker_rendering(log, form_engine):
    """Test date picker component with range selection."""
    dp = log.child("date-picker")

    with step("Open date picker"):
        dp.info("Click on date input field")
        dp.info("Calendar popup opened", data={"month": "March", "year": 2026})
        dp.debug("Calendar grid rendered: 6 weeks x 7 days")
        substep("Highlight today")
        dp.info("Today marker on March 28", data={"is_today": True, "class": "today"})

    with step("Navigate months"):
        dp.info("Click next month arrow")
        dp.info("Calendar updated", data={"month": "April", "year": 2026})
        substep("Verify disabled dates")
        dp.info("Past dates disabled", data={"disabled_before": "2026-03-28"})
        dp.debug("Weekend styling applied (lighter text)")

    with step("Select date range"):
        dp.info("Click start date: April 5")
        dp.info("Range start set", data={"start": "2026-04-05"})
        substep("Highlight hover range")
        dp.info("Hovering over April 10 -- preview range highlighted")
        dp.info("Click end date: April 10")
        dp.info("Range selected", data={"start": "2026-04-05", "end": "2026-04-10", "days": 6})
        substep("Close picker")
        dp.info("Date picker closed")
        dp.info("Input value updated: 'Apr 5 - Apr 10, 2026'")

    assert True


def test_select_dropdown_search(log, form_engine):
    """Test searchable select dropdown component."""
    sel = log.child("select")

    options = [
        {"value": "us", "label": "United States"},
        {"value": "ca", "label": "Canada"},
        {"value": "uk", "label": "United Kingdom"},
        {"value": "de", "label": "Germany"},
        {"value": "fr", "label": "France"},
        {"value": "jp", "label": "Japan"},
        {"value": "au", "label": "Australia"},
        {"value": "br", "label": "Brazil"},
    ]

    with step("Render select with options"):
        sel.info("Select initialized", data={"options_count": len(options), "searchable": True, "placeholder": "Choose country..."})
        sel.debug("Virtualized list: all options fit in viewport, no virtual scroll needed")

    with step("Open and search"):
        sel.info("Click to open dropdown")
        sel.info("Search input focused")
        substep("Type search query")
        sel.info("User typed 'uni'", data={"query": "uni"})
        filtered = [o for o in options if "uni" in o["label"].lower()]
        sel.info("Filtered results", data={"matches": [o["label"] for o in filtered], "count": len(filtered)})
        substep("Highlight first match")
        sel.info("'United States' highlighted via keyboard")

    with step("Select option"):
        sel.info("Enter pressed -- selecting 'United States'")
        sel.info("Dropdown closed")
        sel.info("Selected value", data={"value": "us", "label": "United States"})
        sel.debug("onChange callback fired")

    assert len(options) == 8


# ---------------------------------------------------------------------------
# Flaky / retry tests
# ---------------------------------------------------------------------------

def test_form_submit_api_flaky(log, form_engine, flaky_service):
    """Form submission endpoint is intermittently unavailable."""
    form = log.child("submit")

    with step("Prepare form submission"):
        form.info("Collecting form data", data={"fields": 5})
        form.info("Client-side validation passed")

    with step("Submit to API"):
        form.info("POST /api/forms/contact")
        result = flaky_service("form_submit_endpoint")
        form.info("API response received", data={"result": result, "status": 201})

    with step("Handle success"):
        form.info("Success toast shown: 'Form submitted successfully'")
        form.info("Form reset to initial state")

    assert result == "ok:form_submit_endpoint"


def test_validation_service_flaky(log, form_engine, flaky_service):
    """Server-side validation endpoint has intermittent failures."""
    val = log.child("server-validation")

    with step("Submit for server-side validation"):
        val.info("Sending data to validation endpoint")
        val.info("POST /api/validate/registration")
        result = flaky_service("server_validation_check")
        val.info("Validation response received", data={"result": result})

    with step("Process validation results"):
        val.info("Server returned: all fields valid")
        val.info("Proceeding with registration")
        val.debug("No duplicate email found")
        val.debug("Username available")

    assert "ok" in result


# ---------------------------------------------------------------------------
# Deliberate failures
# ---------------------------------------------------------------------------

def test_email_format_strict_rfc(log, form_engine):
    """Strict RFC 5322 validation -- deliberately fails on edge case."""
    v = log.child("rfc-validator")

    with step("Validate edge-case email"):
        email = '"quoted local"@example.com'
        v.info("Testing RFC 5322 quoted local part", data={"email": email})
        v.info("Quoted local parts are valid per RFC 5322 but rarely supported")
        v.warning("Most form validators reject quoted local parts")
        v.error("Our validator does not support this edge case")

    # This will fail because our simple regex doesn't handle quoted local parts
    simple_pattern = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    result = simple_pattern.match(email)
    assert result is not None, f"Email '{email}' should be valid per RFC 5322 but was rejected"


def test_max_field_length_overflow(log, form_engine):
    """Test that exceeding max length is caught -- deliberately fails."""
    v = log.child("length-validator")

    with step("Test field with value exceeding max length"):
        value = "A" * 300
        max_len = 255
        v.info("Input length", data={"length": len(value), "max_allowed": max_len})
        v.warning("Value exceeds maximum length")
        v.error("Truncation would lose data", data={"excess_chars": len(value) - max_len})

    assert len(value) <= max_len, f"Field value length {len(value)} exceeds max of {max_len}"


def test_required_field_empty_submit(log, form_engine):
    """Submitting with empty required fields -- deliberately fails."""
    form = log.child("required-check")

    with step("Attempt to submit with empty required fields"):
        fields = {"name": "", "email": "", "message": "Hello"}
        empty_required = [k for k, v in fields.items() if not v and k != "message"]
        form.info("Form submission attempted", data={"fields": fields})
        form.error("Required fields empty", data={"empty_fields": empty_required, "count": len(empty_required)})

    assert len(empty_required) == 0, f"Required fields are empty: {empty_required}"
