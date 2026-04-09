"""Checkout flow tests -- payment processing, validation, and order creation."""

from __future__ import annotations

import pytest

from pytest_reporter import step, substep


# ---------------------------------------------------------------------------
# Parametrized: currency + gateway routing
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "currency,amount,gateway",
    [
        ("USD", 149.99, "stripe"),
        ("EUR", 89.50, "stripe"),
        ("GBP", 210.00, "stripe"),
        ("JPY", 15000, "stripe"),
        ("BRL", 499.90, "adyen"),
        ("INR", 8499.00, "razorpay"),
    ],
    ids=["usd-stripe", "eur-stripe", "gbp-stripe", "jpy-stripe", "brl-adyen", "inr-razorpay"],
)
def test_checkout_gateway_routing(log, currency: str, amount: float, gateway: str):
    """Verify that orders are routed to the correct payment gateway."""
    gw = log.child("gateway")
    order = log.child("order")

    step("Create pending order")
    order.info("Generating order ID", data={"currency": currency, "amount": amount})
    order.debug("Merchant account lookup", data={"region": currency[:2]})
    order.info("Order created", data={"order_id": "ord_8cXq2", "status": "pending"})

    step("Determine gateway")
    gw.info("Evaluating routing rules", data={"currency": currency, "amount": amount})
    gw.debug("Rule match", data={"rule": f"currency={currency}", "gateway": gateway})
    gw.info("Gateway selected", data={"gateway": gateway, "endpoint": f"https://api.{gateway}.com/v1/charges"})

    with step("Authorize payment"):
        substep("Build charge payload")
        gw.info("Constructing charge request", data={
            "gateway": gateway,
            "amount_minor": int(amount * 100),
            "currency": currency,
            "idempotency_key": "idk_9fZm3kLp",
        })
        gw.debug("TLS handshake completed", data={"cipher": "TLS_AES_256_GCM_SHA384"})

        substep("Send authorization request")
        gw.info("POST /v1/charges", data={"timeout_ms": 5000})
        gw.info("Authorization approved", data={
            "charge_id": f"ch_{gateway}_xK8n",
            "auth_code": "A12345",
            "network": "visa",
            "risk_score": 12,
        })

    step("Confirm order")
    order.info("Transitioning order status", data={"from": "pending", "to": "confirmed"})
    order.info("Order confirmed", data={"order_id": "ord_8cXq2", "gateway": gateway})

    assert gateway in ("stripe", "adyen", "razorpay")


@pytest.mark.parametrize(
    "discount_code,pct",
    [
        ("SAVE10", 0.10),
        ("SAVE20", 0.20),
        ("HALFOFF", 0.50),
        ("LOYALTY5", 0.05),
    ],
    ids=["10pct", "20pct", "50pct", "5pct-loyalty"],
)
def test_checkout_discount_application(log, discount_code: str, pct: float):
    """Apply a percentage discount code during checkout."""
    pricing = log.child("pricing")
    audit = log.child("audit")

    subtotal = 250.00

    step("Validate discount code")
    pricing.info("Looking up discount code", data={"code": discount_code})
    pricing.debug("Code found in promotions table", data={"promo_id": "promo_44x", "active": True})
    pricing.info("Discount validated", data={"code": discount_code, "percentage": pct, "max_uses": 500, "current_uses": 137})

    with step("Calculate discounted total"):
        substep("Compute discount amount")
        discount_amount = round(subtotal * pct, 2)
        pricing.info("Discount calculated", data={"subtotal": subtotal, "discount": discount_amount})

        substep("Apply tax after discount")
        taxable = subtotal - discount_amount
        tax = round(taxable * 0.0875, 2)
        pricing.info("Tax computed", data={"taxable_amount": taxable, "tax_rate": 0.0875, "tax": tax})
        pricing.debug("Tax jurisdiction", data={"state": "CA", "county": "Santa Clara", "combined_rate": 0.0875})

        substep("Final total")
        total = round(taxable + tax, 2)
        pricing.info("Final total", data={"total": total, "currency": "USD"})

    step("Record audit trail")
    audit.info("Discount applied", data={"order_id": "ord_dsc1", "code": discount_code, "saved": discount_amount, "total": total})
    audit.debug("Audit record written", data={"table": "order_events", "event_type": "discount_applied"})

    assert total < subtotal
    assert discount_amount == round(subtotal * pct, 2)


# ---------------------------------------------------------------------------
# Individual checkout tests
# ---------------------------------------------------------------------------

def test_checkout_idempotent_submission(log):
    """Submitting the same checkout twice should not create duplicate charges."""
    api = log.child("api")
    db = log.child("db")

    step("First submission")
    api.info("POST /checkout", data={"idempotency_key": "idk_dup1", "amount": 75.00, "currency": "USD"})
    api.info("Charge created", data={"charge_id": "ch_first", "status": "succeeded"})
    db.info("Order row inserted", data={"order_id": "ord_dup1", "charge_id": "ch_first"})
    db.debug("Idempotency key stored", data={"key": "idk_dup1", "ttl_hours": 24})

    step("Duplicate submission with same idempotency key")
    api.info("POST /checkout (retry)", data={"idempotency_key": "idk_dup1", "amount": 75.00, "currency": "USD"})
    api.warning("Idempotency key already seen", data={"key": "idk_dup1"})
    api.info("Returning cached result", data={"charge_id": "ch_first", "status": "succeeded"})

    step("Verify single charge")
    db.info("Counting charges for order", data={"order_id": "ord_dup1"})
    db.info("Charge count verified", data={"count": 1})

    charge_count = 1
    assert charge_count == 1


def test_checkout_expired_card(log):
    """Expired card should be declined with proper error code."""
    pay = log.child("payment")
    err = log.child("errors")

    step("Submit payment with expired card")
    pay.info("Processing payment", data={
        "card_last4": "4242",
        "exp_month": 1,
        "exp_year": 2024,
        "amount": 50.00,
        "currency": "USD",
    })
    pay.debug("Card BIN lookup", data={"bin": "424242", "issuer": "Chase", "type": "credit", "brand": "visa"})
    pay.warning("Card expiration check failed", data={"exp": "01/2024", "now": "2026-04"})

    step("Handle decline")
    err.error("Payment declined", data={"decline_code": "expired_card", "message": "Your card has expired."})
    err.info("Decline event recorded", data={"event_id": "evt_dec1", "order_id": "ord_exp1"})
    pay.info("Customer notified", data={"notification": "email", "template": "card_expired"})

    decline_code = "expired_card"
    assert decline_code == "expired_card"


def test_checkout_3ds_authentication(log):
    """3D Secure authentication flow for high-value transactions."""
    tds = log.child("3ds")
    api = log.child("api")

    with step("Initiate 3DS challenge"):
        substep("Create payment intent")
        api.info("Creating payment intent", data={"amount": 2500.00, "currency": "EUR", "requires_3ds": True})
        api.info("Payment intent created", data={"pi_id": "pi_3ds_abc", "status": "requires_action"})

        substep("Generate 3DS redirect URL")
        tds.info("Building authentication request", data={"protocol": "3DS2", "version": "2.2.0"})
        tds.debug("Directory server contacted", data={"ds": "visa", "timeout_ms": 3000})
        tds.info("Challenge URL generated", data={"url": "https://acs.issuer.com/3ds/challenge/xyz"})

    with step("Customer completes challenge"):
        substep("Wait for callback")
        tds.info("Polling for authentication result", data={"pi_id": "pi_3ds_abc", "poll_interval_ms": 500})
        tds.debug("Attempt 1: status=pending")
        tds.debug("Attempt 2: status=pending")
        tds.info("Authentication completed", data={"status": "authenticated", "eci": "05", "cavv": "AAABB..."})

        substep("Confirm payment")
        api.info("Confirming payment intent", data={"pi_id": "pi_3ds_abc"})
        api.info("Payment confirmed", data={"charge_id": "ch_3ds_def", "status": "succeeded", "amount": 2500.00})

    step("Finalize")
    api.info("Order status updated", data={"order_id": "ord_3ds1", "status": "paid"})

    assert True


def test_checkout_split_payment(log):
    """Split payment across two methods (card + store credit)."""
    pay = log.child("payment")
    credit = log.child("store_credit")

    total = 200.00
    store_credit_balance = 75.00

    with step("Check store credit balance"):
        credit.info("Querying store credit", data={"customer_id": "cust_sp1"})
        credit.info("Balance retrieved", data={"balance": store_credit_balance, "currency": "USD"})

    with step("Apply store credit"):
        substep("Deduct from store credit")
        credit.info("Deducting store credit", data={"amount": store_credit_balance, "remaining": 0.00})
        credit.debug("Ledger entry created", data={"type": "debit", "amount": store_credit_balance})

        substep("Calculate card charge")
        card_amount = total - store_credit_balance
        pay.info("Card charge calculated", data={"card_amount": card_amount, "currency": "USD"})

    with step("Charge card for remainder"):
        pay.info("Processing card payment", data={"amount": card_amount, "card_last4": "1234"})
        pay.debug("Network authorization", data={"network": "mastercard", "auth_code": "B67890"})
        pay.info("Card charged", data={"charge_id": "ch_split1", "amount": card_amount, "status": "succeeded"})

    step("Order completed")
    pay.info("Order finalized", data={
        "order_id": "ord_split1",
        "total": total,
        "paid_via_credit": store_credit_balance,
        "paid_via_card": card_amount,
    })

    assert card_amount == 125.00


def test_checkout_inventory_reservation(log):
    """Inventory is reserved during checkout and released on failure."""
    inv = log.child("inventory")
    order = log.child("order")

    items = [
        {"sku": "SKU-A100", "qty": 2, "warehouse": "us-east-1"},
        {"sku": "SKU-B200", "qty": 1, "warehouse": "us-west-2"},
    ]

    with step("Reserve inventory"):
        for item in items:
            substep(f"Reserve {item['sku']}")
            inv.info("Checking stock", data={"sku": item["sku"], "warehouse": item["warehouse"]})
            inv.debug("Current stock level", data={"sku": item["sku"], "available": 50, "reserved": 3})
            inv.info("Stock reserved", data={"sku": item["sku"], "qty": item["qty"], "reservation_id": f"res_{item['sku']}"})

    step("Confirm reservation")
    inv.info("All items reserved", data={"reservation_ids": ["res_SKU-A100", "res_SKU-B200"], "ttl_minutes": 15})
    order.info("Reservation attached to order", data={"order_id": "ord_inv1"})

    step("Verify stock decremented")
    for item in items:
        inv.debug("Post-reserve stock check", data={"sku": item["sku"], "available": 48, "reserved": 5})

    assert len(items) == 2


def test_checkout_currency_conversion(log):
    """Multi-currency checkout with FX conversion."""
    fx = log.child("forex")
    pay = log.child("payment")

    step("Fetch exchange rate")
    fx.info("Requesting FX rate", data={"from": "GBP", "to": "USD", "provider": "openexchangerates"})
    fx.debug("Rate cache miss, fetching live rate")
    fx.info("Rate received", data={"pair": "GBP/USD", "rate": 1.2715, "timestamp": "2026-04-02T10:00:00Z"})

    with step("Convert and charge"):
        substep("Convert amount")
        gbp_amount = 100.00
        usd_amount = round(gbp_amount * 1.2715, 2)
        fx.info("Conversion complete", data={"gbp": gbp_amount, "usd": usd_amount, "rate": 1.2715})

        substep("Charge in settlement currency")
        pay.info("Charging in USD", data={"amount": usd_amount, "original_currency": "GBP", "original_amount": gbp_amount})
        pay.info("Charge succeeded", data={"charge_id": "ch_fx1", "settled_amount": usd_amount, "settled_currency": "USD"})

    step("Record FX details")
    pay.info("FX metadata saved", data={"order_id": "ord_fx1", "fx_rate": 1.2715, "fx_provider": "openexchangerates"})

    assert usd_amount == 127.15


def test_checkout_webhook_delivery(log):
    """Checkout completion fires webhooks to merchant endpoint."""
    hook = log.child("webhook")

    step("Prepare webhook payload")
    hook.info("Building event payload", data={"event_type": "checkout.completed", "order_id": "ord_wh1"})
    hook.debug("Serializing payload", data={"size_bytes": 1842})
    hook.info("Payload signed", data={"algorithm": "hmac-sha256", "header": "Stripe-Signature"})

    with step("Deliver webhook"):
        substep("First delivery attempt")
        hook.info("POST https://merchant.com/webhooks", data={"attempt": 1, "timeout_ms": 5000})
        hook.warning("Timeout on first attempt", data={"elapsed_ms": 5001})

        substep("Retry delivery")
        hook.info("POST https://merchant.com/webhooks", data={"attempt": 2, "timeout_ms": 10000})
        hook.info("Webhook delivered", data={"status": 200, "elapsed_ms": 342})

    step("Update delivery status")
    hook.info("Webhook event marked delivered", data={"event_id": "evt_wh1", "attempts": 2})
    hook.debug("Next retry window cleared")

    assert True


# ---------------------------------------------------------------------------
# Flaky service tests (retry demonstrations)
# ---------------------------------------------------------------------------

def test_checkout_payment_gateway_flaky(log, flaky_service):
    """Payment gateway returns transient error on first attempt."""
    gw = log.child("gateway")

    step("Attempt payment")
    gw.info("Sending charge request", data={"amount": 99.00, "currency": "USD"})
    try:
        flaky_service("checkout_gateway_charge")
    except ConnectionError:
        gw.warning("Gateway returned transient error, will retry")

    step("Retry payment")
    result = flaky_service("checkout_gateway_charge")
    gw.info("Charge succeeded on retry", data={"result": result, "charge_id": "ch_retry1"})

    assert result == "ok:checkout_gateway_charge"


def test_checkout_fraud_check_flaky(log, flaky_service):
    """Fraud detection service is temporarily unavailable."""
    fraud = log.child("fraud")

    step("Submit fraud check")
    fraud.info("Sending transaction for fraud scoring", data={"order_id": "ord_fr1", "amount": 1200.00})
    try:
        flaky_service("checkout_fraud_scoring")
    except ConnectionError:
        fraud.warning("Fraud service unavailable", data={"fallback": "manual_review"})

    step("Retry fraud check")
    result = flaky_service("checkout_fraud_scoring")
    fraud.info("Fraud check passed", data={"result": result, "risk_level": "low", "score": 8})

    assert result == "ok:checkout_fraud_scoring"


def test_checkout_inventory_service_flaky(log, flaky_service):
    """Inventory reservation service has intermittent failures."""
    inv = log.child("inventory")

    step("Reserve inventory")
    inv.info("Requesting reservation", data={"sku": "SKU-FL1", "qty": 3})
    try:
        flaky_service("checkout_inventory_reserve")
    except ConnectionError:
        inv.warning("Inventory service connection lost")

    step("Retry reservation")
    result = flaky_service("checkout_inventory_reserve")
    inv.info("Reservation confirmed", data={"result": result, "reservation_id": "res_fl1"})

    assert result == "ok:checkout_inventory_reserve"


# ---------------------------------------------------------------------------
# Deliberate failures
# ---------------------------------------------------------------------------

def test_checkout_negative_amount_accepted(log):
    """BUG: Negative amounts should be rejected but are not -- this test fails."""
    val = log.child("validation")

    step("Submit negative amount")
    val.info("Validating checkout amount", data={"amount": -50.00, "currency": "USD"})
    val.error("Negative amount was not rejected by validation layer")

    step("Assert rejection")
    rejected = False  # Bug: validation did not reject
    assert rejected, "Negative amount should have been rejected"


def test_checkout_total_mismatch(log):
    """Line item sum does not match declared total -- deliberate assertion failure."""
    pricing = log.child("pricing")

    items = [
        {"name": "Widget A", "price": 25.00, "qty": 2},
        {"name": "Widget B", "price": 15.00, "qty": 1},
    ]
    declared_total = 100.00  # Wrong: should be 65.00

    step("Compute line item total")
    computed = sum(i["price"] * i["qty"] for i in items)
    pricing.info("Computed total from line items", data={"computed": computed, "declared": declared_total})
    pricing.error("Total mismatch detected", data={"difference": declared_total - computed})

    step("Verify totals match")
    assert computed == declared_total, f"Computed {computed} != declared {declared_total}"


# ---------------------------------------------------------------------------
# Skipped tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Apple Pay integration not yet available in sandbox")
def test_checkout_apple_pay(log):
    """Apple Pay tokenization and charge."""
    pass


@pytest.mark.skip(reason="Crypto payments feature flagged off")
def test_checkout_crypto_payment(log):
    """Pay with cryptocurrency via BitPay."""
    pass
