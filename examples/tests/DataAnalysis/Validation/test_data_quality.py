"""Data quality validation tests -- schema checks, statistical tests, and ETL integrity."""

from __future__ import annotations

import math
import random

import pytest

from pytest_reporter import step, substep


# ---------------------------------------------------------------------------
# Synthetic dataset: customer transactions from a data warehouse
# ---------------------------------------------------------------------------

_rng = random.Random(42)

TRANSACTIONS = [
    {
        "txn_id": f"TX-{i:06d}",
        "customer_id": f"C-{1000 + i % 50:04d}",
        "email": f"user{i % 50}@{'example.com' if i % 20 != 0 else ''}",
        "amount": round(_rng.uniform(5.0, 2500.0), 2),
        "currency": ["USD", "EUR", "GBP", "JPY"][i % 4],
        "timestamp": f"2026-03-{1 + i % 28:02d}T{8 + i % 14:02d}:{i % 60:02d}:00Z",
        "status": ["completed", "completed", "completed", "pending", "failed"][i % 5],
        "category": ["retail", "wholesale", "subscription", "refund"][i % 4],
        "country": ["US", "DE", "UK", "JP", "BR", "IN"][i % 6],
        "age": max(0, 25 + i % 60 - 10) if i % 30 != 0 else -3,
        "loyalty_points": i * 10 if i % 25 != 0 else None,
    }
    for i in range(200)
]

SCHEMA = {
    "txn_id": str,
    "customer_id": str,
    "email": str,
    "amount": float,
    "currency": str,
    "timestamp": str,
    "status": str,
    "category": str,
    "country": str,
    "age": int,
    "loyalty_points": (int, type(None)),
}


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


def test_schema_field_presence(log):
    """Verify every record has the required fields."""
    sl = log.child("schema")

    step("Define expected schema")
    expected = list(SCHEMA.keys())
    sl.info("Expected fields", data={"fields": expected, "count": len(expected)})

    step("Scan all records")
    missing_report = []
    for i, txn in enumerate(TRANSACTIONS):
        missing = [f for f in expected if f not in txn]
        if missing:
            sl.warning(f"Record {txn['txn_id']} missing fields", data={"missing": missing})
            missing_report.append({"txn_id": txn["txn_id"], "missing": missing})
        elif i < 3:
            sl.debug(f"Record {txn['txn_id']} OK", data={"fields": list(txn.keys())})

    step("Validate completeness")
    sl.info("Schema scan complete", data={"total": len(TRANSACTIONS), "with_missing": len(missing_report)})
    assert len(missing_report) == 0, f"{len(missing_report)} records with missing fields"


def test_schema_type_conformance(log):
    """Verify field types match the expected schema."""
    tl = log.child("types")

    step("Load schema definition")
    tl.info("Schema loaded", data={"fields": len(SCHEMA)})

    step("Check types for each record")
    violations = []
    for txn in TRANSACTIONS:
        for field, expected_type in SCHEMA.items():
            val = txn.get(field)
            if isinstance(expected_type, tuple):
                ok = isinstance(val, expected_type)
            else:
                ok = isinstance(val, expected_type) or val is None
            if not ok:
                violations.append({"txn_id": txn["txn_id"], "field": field, "expected": str(expected_type), "got": type(val).__name__})

    step("Report violations")
    for v in violations[:5]:
        tl.error(f"Type mismatch in {v['txn_id']}", data=v)
    tl.info("Type check summary", data={"total_records": len(TRANSACTIONS), "violations": len(violations)})

    step("Validate")
    assert len(violations) == 0, f"{len(violations)} type violations found"


@pytest.mark.parametrize("field", ["txn_id", "customer_id", "email", "currency", "status"])
def test_string_field_not_empty(log, field):
    """Verify string fields are non-empty."""
    fl = log.child("non_empty")

    step(f"Check field: {field}")
    empty_count = 0
    for txn in TRANSACTIONS:
        val = txn.get(field, "")
        if not val or not str(val).strip():
            empty_count += 1
            fl.warning(f"Empty {field} in {txn['txn_id']}", data={"value": repr(val)})
    fl.info(f"Field '{field}' scan complete", data={"total": len(TRANSACTIONS), "empty": empty_count})

    step("Validate no empties")
    assert empty_count == 0, f"{empty_count} records have empty '{field}'"


def test_email_format_validation(log):
    """Validate email addresses contain @ and domain."""
    el = log.child("email")

    step("Extract email addresses")
    emails = [(txn["txn_id"], txn["email"]) for txn in TRANSACTIONS]
    el.info("Emails extracted", data={"count": len(emails)})

    step("Validate format")
    invalid = []
    for txn_id, email in emails:
        has_at = "@" in email
        has_domain = "." in email.split("@")[-1] if has_at else False
        if not (has_at and has_domain):
            invalid.append({"txn_id": txn_id, "email": email})
            el.warning(f"Invalid email in {txn_id}", data={"email": email})
        elif len(invalid) == 0 and len(emails) > 3:
            el.debug(f"Valid: {email}")

    step("Report results")
    el.info("Email validation done", data={"total": len(emails), "invalid": len(invalid)})

    step("Assert all valid")
    assert len(invalid) == 0, f"{len(invalid)} invalid emails found"


def test_transaction_id_uniqueness(log):
    """Verify all transaction IDs are unique."""
    ul = log.child("uniqueness")

    step("Collect transaction IDs")
    ids = [txn["txn_id"] for txn in TRANSACTIONS]
    ul.info("IDs collected", data={"count": len(ids)})

    step("Check for duplicates")
    seen = set()
    dupes = []
    for txn_id in ids:
        if txn_id in seen:
            dupes.append(txn_id)
            ul.error(f"Duplicate ID: {txn_id}")
        seen.add(txn_id)

    step("Validate uniqueness")
    ul.info("Uniqueness check", data={"total": len(ids), "unique": len(seen), "duplicates": len(dupes)})
    assert len(dupes) == 0, f"Found {len(dupes)} duplicate IDs"


@pytest.mark.parametrize("currency", ["USD", "EUR", "GBP", "JPY"])
def test_currency_code_valid(log, currency):
    """Check currency codes are ISO 4217 compliant."""
    cl = log.child("currency")

    valid_codes = {"USD", "EUR", "GBP", "JPY", "CAD", "AUD", "CHF", "CNY", "BRL", "INR"}

    step(f"Filter transactions with currency: {currency}")
    filtered = [t for t in TRANSACTIONS if t["currency"] == currency]
    cl.info("Filtered", data={"currency": currency, "count": len(filtered)})

    step("Validate ISO 4217")
    cl.info("Checking against valid codes", data={"valid_codes": sorted(valid_codes)})
    assert currency in valid_codes
    cl.info(f"Currency {currency} is valid ISO 4217")

    step("Check amount consistency")
    amounts = [t["amount"] for t in filtered]
    cl.info("Amount stats", data={"min": round(min(amounts), 2), "max": round(max(amounts), 2), "mean": round(sum(amounts) / len(amounts), 2)})
    assert all(a > 0 for a in amounts), "Negative amounts found"
    cl.info("Currency validation complete")


# ---------------------------------------------------------------------------
# Statistical quality tests
# ---------------------------------------------------------------------------


def test_amount_distribution_normality(log):
    """Check if transaction amounts roughly follow expected distribution."""
    dl = log.child("distribution")

    step("Compute descriptive statistics")
    amounts = [t["amount"] for t in TRANSACTIONS]
    n = len(amounts)
    mean = sum(amounts) / n
    variance = sum((x - mean) ** 2 for x in amounts) / n
    std = math.sqrt(variance)
    dl.info("Descriptive stats", data={"n": n, "mean": round(mean, 2), "std": round(std, 2), "min": round(min(amounts), 2), "max": round(max(amounts), 2)})

    step("Check skewness")
    skewness = sum((x - mean) ** 3 for x in amounts) / (n * std ** 3) if std > 0 else 0
    dl.info("Skewness", data={"value": round(skewness, 4), "interpretation": "right-skewed" if skewness > 0.5 else "left-skewed" if skewness < -0.5 else "approximately symmetric"})

    step("Check kurtosis")
    kurtosis = sum((x - mean) ** 4 for x in amounts) / (n * std ** 4) - 3 if std > 0 else 0
    dl.info("Excess kurtosis", data={"value": round(kurtosis, 4), "interpretation": "leptokurtic" if kurtosis > 1 else "platykurtic" if kurtosis < -1 else "mesokurtic"})

    step("Validate distribution bounds")
    substep("All amounts positive")
    assert all(a > 0 for a in amounts)
    substep("Standard deviation reasonable")
    assert std > 0
    dl.info("Distribution analysis complete")


def test_age_range_validation(log):
    """Ensure all customer ages are within a valid range -- has deliberate failures."""
    al = log.child("age")

    step("Extract ages")
    ages = [(t["txn_id"], t["age"]) for t in TRANSACTIONS]
    al.info("Ages extracted", data={"count": len(ages)})

    step("Validate range (0-120)")
    invalid = []
    for txn_id, age in ages:
        if not (0 <= age <= 120):
            invalid.append({"txn_id": txn_id, "age": age})
            al.error(f"Invalid age in {txn_id}", data={"age": age})

    step("Report")
    al.info("Age validation", data={"total": len(ages), "invalid": len(invalid)})
    assert len(invalid) == 0, f"{len(invalid)} records with out-of-range ages"


def test_null_check_loyalty_points(log):
    """Check for unexpected NULL values in loyalty_points."""
    nl = log.child("nulls")

    step("Scan for NULL loyalty_points")
    nulls = [t for t in TRANSACTIONS if t["loyalty_points"] is None]
    nl.info("NULL scan complete", data={"total": len(TRANSACTIONS), "nulls": len(nulls)})
    for t in nulls[:5]:
        nl.warning(f"NULL loyalty_points: {t['txn_id']}", data={"customer_id": t["customer_id"]})

    step("Compute null rate")
    null_rate = len(nulls) / len(TRANSACTIONS) * 100
    nl.info("Null rate", data={"pct": round(null_rate, 2)})

    step("Assert null rate below threshold")
    threshold = 2.0
    nl.info("Threshold check", data={"null_rate": round(null_rate, 2), "threshold": threshold})
    assert null_rate <= threshold, f"Null rate {null_rate:.1f}% exceeds threshold {threshold}%"


@pytest.mark.parametrize("status", ["completed", "pending", "failed"])
def test_status_value_valid(log, status):
    """Verify transaction status values are from allowed set."""
    sl = log.child("status")

    allowed = {"completed", "pending", "failed", "reversed"}

    step(f"Filter status: {status}")
    filtered = [t for t in TRANSACTIONS if t["status"] == status]
    sl.info("Filtered", data={"status": status, "count": len(filtered)})

    step("Validate status in allowed set")
    sl.info("Allowed statuses", data={"allowed": sorted(allowed)})
    assert status in allowed
    sl.info(f"Status '{status}' is valid")

    step("Check status distribution")
    total = len(TRANSACTIONS)
    pct = len(filtered) / total * 100
    sl.info("Distribution", data={"status": status, "count": len(filtered), "pct": round(pct, 1)})
    assert len(filtered) > 0
    sl.info("Status validation complete")


def test_timestamp_format_iso8601(log):
    """Verify all timestamps are valid ISO 8601 format."""
    tl = log.child("timestamp")

    step("Extract timestamps")
    timestamps = [(t["txn_id"], t["timestamp"]) for t in TRANSACTIONS]
    tl.info("Timestamps collected", data={"count": len(timestamps)})

    step("Validate ISO 8601 format")
    import re
    iso_pattern = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
    invalid = []
    for txn_id, ts in timestamps:
        if not iso_pattern.match(ts):
            invalid.append({"txn_id": txn_id, "timestamp": ts})
            tl.error(f"Bad timestamp in {txn_id}", data={"timestamp": ts})
    tl.info("Format check done", data={"total": len(timestamps), "invalid": len(invalid)})

    step("Validate")
    assert len(invalid) == 0, f"{len(invalid)} invalid timestamps"
    tl.info("Timestamp validation complete")


def test_referential_integrity_customer_ids(log):
    """Check that customer IDs reference valid customers."""
    rl = log.child("referential")

    step("Build customer ID master list")
    master_ids = {f"C-{1000 + i:04d}" for i in range(55)}
    rl.info("Master list loaded", data={"valid_customer_count": len(master_ids)})

    step("Check transaction references")
    orphans = []
    for t in TRANSACTIONS:
        if t["customer_id"] not in master_ids:
            orphans.append({"txn_id": t["txn_id"], "customer_id": t["customer_id"]})
            rl.error(f"Orphan reference: {t['txn_id']}", data={"customer_id": t["customer_id"]})

    step("Report integrity status")
    rl.info("Referential integrity check", data={"total_txns": len(TRANSACTIONS), "orphans": len(orphans)})
    assert len(orphans) == 0, f"{len(orphans)} orphan customer references"
    rl.info("Referential integrity validated")


def test_cross_field_consistency(log):
    """Validate cross-field business rules (e.g., refunds have specific status)."""
    cl = log.child("cross_field")

    step("Define business rules")
    rules = [
        ("refund category must have amount > 0", lambda t: t["category"] != "refund" or t["amount"] > 0),
        ("completed status must have amount > 0", lambda t: t["status"] != "completed" or t["amount"] > 0),
        ("age must be positive", lambda t: t["age"] >= 0),
    ]
    cl.info("Business rules loaded", data={"rule_count": len(rules)})

    step("Evaluate rules across all records")
    for rule_desc, rule_fn in rules:
        violations = [t["txn_id"] for t in TRANSACTIONS if not rule_fn(t)]
        cl.info(f"Rule: {rule_desc}", data={"violations": len(violations)})
        if violations:
            cl.warning(f"Violations for: {rule_desc}", data={"sample_ids": violations[:3]})

    step("Validate all rules pass")
    all_violations = sum(1 for t in TRANSACTIONS for _, fn in rules if not fn(t))
    cl.info("Cross-field validation summary", data={"total_checks": len(TRANSACTIONS) * len(rules), "violations": all_violations})
    # The age rule will catch negative ages
    assert all_violations == 0, f"{all_violations} cross-field violations"


def test_country_code_iso3166(log):
    """Verify country codes are valid ISO 3166-1 alpha-2."""
    cl = log.child("country")

    valid_alpha2 = {"US", "DE", "UK", "JP", "BR", "IN", "CA", "FR", "AU", "SG", "CN", "KR", "MX", "IT", "ES"}

    step("Extract country codes")
    countries = set(t["country"] for t in TRANSACTIONS)
    cl.info("Unique countries found", data={"countries": sorted(countries)})

    step("Validate against ISO 3166-1")
    invalid = countries - valid_alpha2
    for c in sorted(countries):
        status = "valid" if c in valid_alpha2 else "INVALID"
        cl.info(f"Country: {c}", data={"status": status})

    step("Assert all valid")
    cl.info("Country validation", data={"valid": len(countries - invalid), "invalid": len(invalid)})
    assert len(invalid) == 0, f"Invalid country codes: {invalid}"
    cl.info("Country code validation complete")


def test_data_freshness(log):
    """Check that data is not stale (timestamps within expected range)."""
    fl = log.child("freshness")

    step("Define freshness window")
    expected_month = "2026-03"
    fl.info("Expected data month", data={"month": expected_month})

    step("Check timestamp freshness")
    stale = [t for t in TRANSACTIONS if not t["timestamp"].startswith(expected_month)]
    fl.info("Freshness scan", data={"total": len(TRANSACTIONS), "stale": len(stale)})
    for t in stale[:3]:
        fl.warning(f"Stale record: {t['txn_id']}", data={"timestamp": t["timestamp"]})

    step("Validate freshness")
    assert len(stale) == 0, f"{len(stale)} stale records found"
    fl.info("Data freshness validated")


# ---------------------------------------------------------------------------
# Flaky service / retry tests
# ---------------------------------------------------------------------------


def test_data_quality_report_upload(log, flaky_service):
    """Upload quality report to dashboard -- first attempt fails."""
    ul = log.child("upload")

    step("Generate quality report payload")
    payload = {
        "total_records": len(TRANSACTIONS),
        "schema_valid": True,
        "null_rate_pct": 4.0,
        "timestamp": "2026-04-02T12:00:00Z",
    }
    ul.info("Report payload assembled", data=payload)

    step("Upload to dashboard API")
    ul.info("POST /api/quality-reports", data={"endpoint": "https://dashboard.internal/api/quality-reports"})
    result = flaky_service("dq_report_upload")
    ul.info("Upload result", data={"status": result})

    step("Validate upload")
    assert result.startswith("ok")
    ul.info("Report upload confirmed")


def test_schema_registry_sync(log, flaky_service):
    """Sync schema definitions with schema registry -- intermittent failure."""
    rl = log.child("registry")

    step("Prepare schema payload")
    schema_version = "v2.3.1"
    rl.info("Schema version", data={"version": schema_version, "fields": len(SCHEMA)})

    step("Push to schema registry")
    rl.info("Connecting to schema registry", data={"url": "https://registry.internal/schemas/transactions"})
    result = flaky_service("schema_registry_sync")
    rl.info("Registry response", data={"status": result})

    step("Verify registration")
    assert "ok" in result
    rl.info("Schema registered successfully")


def test_anomaly_detector_health(log, flaky_service):
    """Check anomaly detection service health -- flaky endpoint."""
    al = log.child("anomaly")

    step("Ping anomaly detector")
    al.info("GET /health", data={"service": "anomaly-detector", "port": 8080})
    result = flaky_service("anomaly_detector_health")
    al.info("Health check result", data={"status": result})

    step("Validate detector is ready")
    assert result == "ok:anomaly_detector_health"
    al.info("Anomaly detector is healthy")


# ---------------------------------------------------------------------------
# Failure tests
# ---------------------------------------------------------------------------


def test_zero_null_policy(log):
    """Enforce zero-null policy on loyalty_points -- deliberately fails."""
    zl = log.child("zero_null")

    step("Count NULL loyalty_points")
    nulls = [t for t in TRANSACTIONS if t["loyalty_points"] is None]
    zl.info("NULL count", data={"nulls": len(nulls), "total": len(TRANSACTIONS)})
    for t in nulls[:3]:
        zl.error(f"NULL in {t['txn_id']}", data={"customer_id": t["customer_id"]})

    step("Enforce zero-null policy")
    assert len(nulls) == 0, f"Zero-null policy violated: {len(nulls)} NULL loyalty_points found"


def test_no_negative_ages(log):
    """Assert no negative ages in dataset -- deliberately fails."""
    al = log.child("neg_age")

    step("Scan for negative ages")
    negatives = [(t["txn_id"], t["age"]) for t in TRANSACTIONS if t["age"] < 0]
    al.info("Negative age scan", data={"found": len(negatives)})
    for txn_id, age in negatives:
        al.error(f"Negative age: {txn_id}", data={"age": age})

    step("Assert no negatives")
    assert len(negatives) == 0, f"{len(negatives)} records with negative ages"


# ---------------------------------------------------------------------------
# Skip tests
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="PII detection model not deployed in CI")
def test_pii_detection_scan(log):
    """Scan transaction data for PII leakage."""
    log.info("Skipped -- requires PII detection model")


@pytest.mark.skip(reason="Data lineage tracking not implemented yet")
def test_data_lineage_completeness(log):
    """Verify data lineage metadata for all records."""
    log.info("Skipped -- lineage tracking pending")
