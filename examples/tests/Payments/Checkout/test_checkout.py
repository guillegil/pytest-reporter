"""Checkout flow tests -- payment processing, validation, and order creation."""

from __future__ import annotations

import logging
import pytest

from stepdoc import step

log = logging.getLogger("checkout")


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
def test_checkout_gateway_routing(currency: str, amount: float, gateway: str):
    """Verify that orders are routed to the correct payment gateway."""
    gw = log.getChild("gateway")
    order = log.getChild("order")

    with step("Create pending order"):
        order.info("Generating order ID", extra={"currency": currency, "amount": amount})
        order.debug("Merchant account lookup", extra={"region": currency[:2]})
        order.info("Order created", extra={"order_id": "ord_8cXq2", "status": "pending"})

    with step("Determine gateway"):
        gw.info("Evaluating routing rules", extra={"currency": currency, "amount": amount})
        gw.debug("Rule match", extra={"rule": f"currency={currency}", "gateway": gateway})
        gw.info("Gateway selected", extra={"gateway": gateway, "endpoint": f"https://api.{gateway}.com/v1/charges"})

        with step("Authorize payment"):
            with step("Build charge payload"):
                gw.info("Constructing charge request", extra={
                    "gateway": gateway,
                    "amount_minor": int(amount * 100),
                    "currency": currency,
                    "idempotency_key": "idk_9fZm3kLp",
                })
                gw.debug("TLS handshake completed", extra={"cipher": "TLS_AES_256_GCM_SHA384"})

            with step("Send authorization request"):
                gw.info("POST /v1/charges", extra={"timeout_ms": 5000})
                gw.info("Authorization approved", extra={
                    "charge_id": f"ch_{gateway}_xK8n",
                    "auth_code": "A12345",
                    "network": "visa",
                    "risk_score": 12,
                })

    with step("Confirm order"):
        order.info("Transitioning order status", extra={"from": "pending", "to": "confirmed"})
        order.info("Order confirmed", extra={"order_id": "ord_8cXq2", "gateway": gateway})

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
def test_checkout_discount_application(discount_code: str, pct: float):
    """Apply a percentage discount code during checkout."""
    pricing = log.getChild("pricing")
    audit = log.getChild("audit")

    subtotal = 250.00

    with step("Validate discount code"):
        pricing.info("Looking up discount code", extra={"code": discount_code})
        pricing.debug("Code found in promotions table", extra={"promo_id": "promo_44x", "active": True})
        pricing.info("Discount validated", extra={"code": discount_code, "percentage": pct, "max_uses": 500, "current_uses": 137})

        with step("Calculate discounted total"):
            with step("Compute discount amount"):
                discount_amount = round(subtotal * pct, 2)
                pricing.info("Discount calculated", extra={"subtotal": subtotal, "discount": discount_amount})

            with step("Apply tax after discount"):
                taxable = subtotal - discount_amount
                tax = round(taxable * 0.0875, 2)
                pricing.info("Tax computed", extra={"taxable_amount": taxable, "tax_rate": 0.0875, "tax": tax})
                pricing.debug("Tax jurisdiction", extra={"state": "CA", "county": "Santa Clara", "combined_rate": 0.0875})

            with step("Final total"):
                total = round(taxable + tax, 2)
                pricing.info("Final total", extra={"total": total, "currency": "USD"})

    with step("Record audit trail"):
        audit.info("Discount applied", extra={"order_id": "ord_dsc1", "code": discount_code, "saved": discount_amount, "total": total})
        audit.debug("Audit record written", extra={"table": "order_events", "event_type": "discount_applied"})

        assert total < subtotal
        assert discount_amount == round(subtotal * pct, 2)


# ---------------------------------------------------------------------------
# Individual checkout tests
# ---------------------------------------------------------------------------

def test_checkout_idempotent_submission():
    """Submitting the same checkout twice should not create duplicate charges."""
    api = log.getChild("api")
    db = log.getChild("db")

    with step("First submission"):
        api.info("POST /checkout", extra={"idempotency_key": "idk_dup1", "amount": 75.00, "currency": "USD"})
        api.info("Charge created", extra={"charge_id": "ch_first", "status": "succeeded"})
        db.info("Order row inserted", extra={"order_id": "ord_dup1", "charge_id": "ch_first"})
        db.debug("Idempotency key stored", extra={"key": "idk_dup1", "ttl_hours": 24})

    with step("Duplicate submission with same idempotency key"):
        api.info("POST /checkout (retry)", extra={"idempotency_key": "idk_dup1", "amount": 75.00, "currency": "USD"})
        api.warning("Idempotency key already seen", extra={"key": "idk_dup1"})
        api.info("Returning cached result", extra={"charge_id": "ch_first", "status": "succeeded"})

    with step("Verify single charge"):
        db.info("Counting charges for order", extra={"order_id": "ord_dup1"})
        db.info("Charge count verified", extra={"count": 1})

        charge_count = 1
        assert charge_count == 1


def test_checkout_expired_card():
    """Expired card should be declined with proper error code."""
    pay = log.getChild("payment")
    err = log.getChild("errors")

    with step("Submit payment with expired card"):
        pay.info("Processing payment", extra={
            "card_last4": "4242",
            "exp_month": 1,
            "exp_year": 2024,
            "amount": 50.00,
            "currency": "USD",
        })
        pay.debug("Card BIN lookup", extra={"bin": "424242", "issuer": "Chase", "type": "credit", "brand": "visa"})
        pay.warning("Card expiration check failed", extra={"exp": "01/2024", "now": "2026-04"})

    with step("Handle decline"):
        err.error("Payment declined", extra={"data": {"decline_code": "expired_card", "message": "Your card has expired."}})
        err.info("Decline event recorded", extra={"event_id": "evt_dec1", "order_id": "ord_exp1"})
        pay.info("Customer notified", extra={"notification": "email", "template": "card_expired"})

        decline_code = "expired_card"
        assert decline_code == "expired_card"


def test_checkout_3ds_authentication():
    """3D Secure authentication flow for high-value transactions."""
    tds = log.getChild("3ds")
    api = log.getChild("api")

    with step("Initiate 3DS challenge"):
        with step("Create payment intent"):
            api.info("Creating payment intent", extra={"amount": 2500.00, "currency": "EUR", "requires_3ds": True})
            api.info("Payment intent created", extra={"pi_id": "pi_3ds_abc", "status": "requires_action"})

        with step("Generate 3DS redirect URL"):
            tds.info("Building authentication request", extra={"protocol": "3DS2", "version": "2.2.0"})
            tds.debug("Directory server contacted", extra={"ds": "visa", "timeout_ms": 3000})
            tds.info("Challenge URL generated", extra={"url": "https://acs.issuer.com/3ds/challenge/xyz"})

    with step("Customer completes challenge"):
        with step("Wait for callback"):
            tds.info("Polling for authentication result", extra={"pi_id": "pi_3ds_abc", "poll_interval_ms": 500})
            tds.debug("Attempt 1: status=pending")
            tds.debug("Attempt 2: status=pending")
            tds.info("Authentication completed", extra={"status": "authenticated", "eci": "05", "cavv": "AAABB..."})

        with step("Confirm payment"):
            api.info("Confirming payment intent", extra={"pi_id": "pi_3ds_abc"})
            api.info("Payment confirmed", extra={"charge_id": "ch_3ds_def", "status": "succeeded", "amount": 2500.00})

    with step("Finalize"):
        api.info("Order status updated", extra={"order_id": "ord_3ds1", "status": "paid"})

        assert True


def test_checkout_split_payment():
    """Split payment across two methods (card + store credit)."""
    pay = log.getChild("payment")
    credit = log.getChild("store_credit")

    total = 200.00
    store_credit_balance = 75.00

    with step("Check store credit balance"):
        credit.info("Querying store credit", extra={"customer_id": "cust_sp1"})
        credit.info("Balance retrieved", extra={"balance": store_credit_balance, "currency": "USD"})

    with step("Apply store credit"):
        with step("Deduct from store credit"):
            credit.info("Deducting store credit", extra={"amount": store_credit_balance, "remaining": 0.00})
            credit.debug("Ledger entry created", extra={"type": "debit", "amount": store_credit_balance})

        with step("Calculate card charge"):
            card_amount = total - store_credit_balance
            pay.info("Card charge calculated", extra={"card_amount": card_amount, "currency": "USD"})

    with step("Charge card for remainder"):
        pay.info("Processing card payment", extra={"amount": card_amount, "card_last4": "1234"})
        pay.debug("Network authorization", extra={"network": "mastercard", "auth_code": "B67890"})
        pay.info("Card charged", extra={"charge_id": "ch_split1", "amount": card_amount, "status": "succeeded"})

    with step("Order completed"):
        pay.info("Order finalized", extra={
            "order_id": "ord_split1",
            "total": total,
            "paid_via_credit": store_credit_balance,
            "paid_via_card": card_amount,
        })

        assert card_amount == 125.00


def test_checkout_inventory_reservation():
    """Inventory is reserved during checkout and released on failure."""
    inv = log.getChild("inventory")
    order = log.getChild("order")

    items = [
        {"sku": "SKU-A100", "qty": 2, "warehouse": "us-east-1"},
        {"sku": "SKU-B200", "qty": 1, "warehouse": "us-west-2"},
    ]

    with step("Reserve inventory"):
        for item in items:
            with step(f"Reserve {item['sku']}"):
                inv.info("Checking stock", extra={"sku": item["sku"], "warehouse": item["warehouse"]})
                inv.debug("Current stock level", extra={"sku": item["sku"], "available": 50, "reserved": 3})
                inv.info("Stock reserved", extra={"sku": item["sku"], "qty": item["qty"], "reservation_id": f"res_{item['sku']}"})

    with step("Confirm reservation"):
        inv.info("All items reserved", extra={"reservation_ids": ["res_SKU-A100", "res_SKU-B200"], "ttl_minutes": 15})
        order.info("Reservation attached to order", extra={"order_id": "ord_inv1"})

    with step("Verify stock decremented"):
        for item in items:
            inv.debug("Post-reserve stock check", extra={"sku": item["sku"], "available": 48, "reserved": 5})

        assert len(items) == 2


def test_checkout_currency_conversion():
    """Multi-currency checkout with FX conversion."""
    fx = log.getChild("forex")
    pay = log.getChild("payment")

    with step("Fetch exchange rate"):
        fx.info("Requesting FX rate", extra={"from": "GBP", "to": "USD", "provider": "openexchangerates"})
        fx.debug("Rate cache miss, fetching live rate")
        fx.info("Rate received", extra={"pair": "GBP/USD", "rate": 1.2715, "timestamp": "2026-04-02T10:00:00Z"})

        with step("Convert and charge"):
            with step("Convert amount"):
                gbp_amount = 100.00
                usd_amount = round(gbp_amount * 1.2715, 2)
                fx.info("Conversion complete", extra={"gbp": gbp_amount, "usd": usd_amount, "rate": 1.2715})

            with step("Charge in settlement currency"):
                pay.info("Charging in USD", extra={"amount": usd_amount, "original_currency": "GBP", "original_amount": gbp_amount})
                pay.info("Charge succeeded", extra={"charge_id": "ch_fx1", "settled_amount": usd_amount, "settled_currency": "USD"})

    with step("Record FX details"):
        pay.info("FX metadata saved", extra={"order_id": "ord_fx1", "fx_rate": 1.2715, "fx_provider": "openexchangerates"})

        assert usd_amount == 127.15


def test_checkout_webhook_delivery():
    """Checkout completion fires webhooks to merchant endpoint."""
    hook = log.getChild("webhook")

    with step("Prepare webhook payload"):
        hook.info("Building event payload", extra={"event_type": "checkout.completed", "order_id": "ord_wh1"})
        hook.debug("Serializing payload", extra={"size_bytes": 1842})
        hook.info("Payload signed", extra={"algorithm": "hmac-sha256", "header": "Stripe-Signature"})

        with step("Deliver webhook"):
            with step("First delivery attempt"):
                hook.info("POST https://merchant.com/webhooks", extra={"attempt": 1, "timeout_ms": 5000})
                hook.warning("Timeout on first attempt", extra={"elapsed_ms": 5001})

            with step("Retry delivery"):
                hook.info("POST https://merchant.com/webhooks", extra={"attempt": 2, "timeout_ms": 10000})
                hook.info("Webhook delivered", extra={"status": 200, "elapsed_ms": 342})

    with step("Update delivery status"):
        hook.info("Webhook event marked delivered", extra={"event_id": "evt_wh1", "attempts": 2})
        hook.debug("Next retry window cleared")

        assert True


# ---------------------------------------------------------------------------
# Flaky service tests (retry demonstrations)
# ---------------------------------------------------------------------------

def test_checkout_payment_gateway_flaky(flaky_service):
    """Payment gateway returns transient error on first attempt."""
    gw = log.getChild("gateway")

    with step("Attempt payment"):
        gw.info("Sending charge request", extra={"amount": 99.00, "currency": "USD"})
        try:
            flaky_service("checkout_gateway_charge")
        except ConnectionError:
            gw.warning("Gateway returned transient error, will retry")

    with step("Retry payment"):
        result = flaky_service("checkout_gateway_charge")
        gw.info("Charge succeeded on retry", extra={"result": result, "charge_id": "ch_retry1"})

        assert result == "ok:checkout_gateway_charge"


def test_checkout_fraud_check_flaky(flaky_service):
    """Fraud detection service is temporarily unavailable."""
    fraud = log.getChild("fraud")

    with step("Submit fraud check"):
        fraud.info("Sending transaction for fraud scoring", extra={"order_id": "ord_fr1", "amount": 1200.00})
        try:
            flaky_service("checkout_fraud_scoring")
        except ConnectionError:
            fraud.warning("Fraud service unavailable", extra={"fallback": "manual_review"})

    with step("Retry fraud check"):
        result = flaky_service("checkout_fraud_scoring")
        fraud.info("Fraud check passed", extra={"result": result, "risk_level": "low", "score": 8})

        assert result == "ok:checkout_fraud_scoring"


def test_checkout_inventory_service_flaky(flaky_service):
    """Inventory reservation service has intermittent failures."""
    inv = log.getChild("inventory")

    with step("Reserve inventory"):
        inv.info("Requesting reservation", extra={"sku": "SKU-FL1", "qty": 3})
        try:
            flaky_service("checkout_inventory_reserve")
        except ConnectionError:
            inv.warning("Inventory service connection lost")

    with step("Retry reservation"):
        result = flaky_service("checkout_inventory_reserve")
        inv.info("Reservation confirmed", extra={"result": result, "reservation_id": "res_fl1"})

        assert result == "ok:checkout_inventory_reserve"


# ---------------------------------------------------------------------------
# Deliberate failures
# ---------------------------------------------------------------------------

def test_checkout_negative_amount_accepted():
    """BUG: Negative amounts should be rejected but are not -- this test fails."""
    val = log.getChild("validation")

    with step("Submit negative amount"):
        val.info("Validating checkout amount", extra={"amount": -50.00, "currency": "USD"})
        val.error("Negative amount was not rejected by validation layer")

    with step("Assert rejection"):
        rejected = False  # Bug: validation did not reject
        assert rejected, "Negative amount should have been rejected"


def test_checkout_total_mismatch():
    """Line item sum does not match declared total -- deliberate assertion failure."""
    pricing = log.getChild("pricing")

    items = [
        {"name": "Widget A", "price": 25.00, "qty": 2},
        {"name": "Widget B", "price": 15.00, "qty": 1},
    ]
    declared_total = 100.00  # Wrong: should be 65.00

    with step("Compute line item total"):
        computed = sum(i["price"] * i["qty"] for i in items)
        pricing.info("Computed total from line items", extra={"computed": computed, "declared": declared_total})
        pricing.error("Total mismatch detected", extra={"difference": declared_total - computed})

    with step("Verify totals match"):
        assert computed == declared_total, f"Computed {computed} != declared {declared_total}"


# ---------------------------------------------------------------------------
# Skipped tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Apple Pay integration not yet available in sandbox")
def test_checkout_apple_pay():
    """Apple Pay tokenization and charge."""
    pass


@pytest.mark.skip(reason="Crypto payments feature flagged off")
def test_checkout_crypto_payment():
    """Pay with cryptocurrency via BitPay."""
    pass
