"""Refund processing tests -- full/partial refunds, credit notes, compliance."""

from __future__ import annotations

import pytest

from pytest_reporter import step, substep


# ---------------------------------------------------------------------------
# Parametrized: refund reasons
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "reason,expected_approval",
    [
        ("defective_product", "auto_approved"),
        ("wrong_item_shipped", "auto_approved"),
        ("changed_mind", "auto_approved"),
        ("never_arrived", "requires_investigation"),
        ("unauthorized_charge", "requires_investigation"),
        ("duplicate_charge", "auto_approved"),
    ],
    ids=["defective", "wrong-item", "changed-mind", "never-arrived", "unauthorized", "duplicate"],
)
def test_refund_reason_routing(log, reason: str, expected_approval: str):
    """Different refund reasons route to different approval workflows."""
    refund = log.child("refund")
    policy = log.child("policy")

    step("Submit refund request")
    refund.info("Refund requested", data={
        "order_id": "ord_rr1",
        "reason": reason,
        "amount": 89.99,
        "currency": "USD",
        "customer_id": "cust_rr1",
    })
    refund.debug("Order details fetched", data={"order_date": "2026-03-15", "payment_method": "card", "charge_id": "ch_rr1"})

    with step("Evaluate refund policy"):
        substep("Check refund window")
        policy.info("Checking return window", data={"order_date": "2026-03-15", "days_since": 18, "max_days": 30})
        policy.debug("Within return window")

        substep("Match reason to workflow")
        policy.info("Reason classification", data={"reason": reason, "category": expected_approval})
        if expected_approval == "requires_investigation":
            policy.warning("Investigation required", data={"reason": reason, "escalated_to": "fraud_team"})
        else:
            policy.info("Auto-approval criteria met", data={"reason": reason})

    step("Route refund")
    refund.info("Refund routed", data={"workflow": expected_approval, "estimated_processing_days": 3 if expected_approval == "auto_approved" else 10})
    refund.debug("Workflow event emitted", data={"event": "refund.routed", "queue": expected_approval})

    assert expected_approval in ("auto_approved", "requires_investigation")


@pytest.mark.parametrize(
    "refund_pct",
    [0.25, 0.50, 0.75, 1.00],
    ids=["25pct", "50pct", "75pct", "full"],
)
def test_refund_partial_amounts(log, refund_pct: float):
    """Partial refunds for various percentages of order total."""
    refund = log.child("refund")
    ledger = log.child("ledger")

    order_total = 200.00
    refund_amount = round(order_total * refund_pct, 2)

    step("Calculate refund amount")
    refund.info("Refund calculation", data={
        "order_total": order_total,
        "refund_pct": refund_pct,
        "refund_amount": refund_amount,
    })
    refund.debug("Tax portion of refund", data={"tax_refunded": round(refund_amount * 0.08, 2)})

    with step("Process refund"):
        substep("Validate amount against original charge")
        refund.info("Validation passed", data={"refund_amount": refund_amount, "original_charge": order_total})

        substep("Issue refund via gateway")
        refund.info("Refund issued", data={
            "refund_id": f"ref_{int(refund_pct * 100)}",
            "charge_id": "ch_partial1",
            "amount": refund_amount,
            "status": "succeeded",
        })

    step("Update ledger")
    ledger.info("Ledger entry created", data={
        "type": "refund",
        "amount": -refund_amount,
        "balance_after": round(order_total - refund_amount, 2),
    })
    ledger.debug("General journal entry", data={"debit": "refunds_payable", "credit": "cash", "amount": refund_amount})

    assert refund_amount <= order_total
    assert refund_amount > 0


# ---------------------------------------------------------------------------
# Individual refund tests
# ---------------------------------------------------------------------------

def test_refund_full_with_credit_note(log):
    """Full refund generates a credit note and reverses the charge."""
    refund = log.child("refund")
    cn = log.child("credit_note")
    gateway = log.child("gateway")

    order_total = 149.99

    step("Initiate full refund")
    refund.info("Full refund requested", data={"order_id": "ord_full1", "amount": order_total, "reason": "defective_product"})
    refund.debug("Customer refund history", data={"prior_refunds": 0, "lifetime_value": 1250.00})

    with step("Reverse payment"):
        substep("Send refund to gateway")
        gateway.info("POST /v1/refunds", data={
            "charge_id": "ch_full1",
            "amount": int(order_total * 100),
            "reason": "requested_by_customer",
        })
        gateway.debug("Gateway response time", data={"elapsed_ms": 287})
        gateway.info("Refund processed", data={"refund_id": "re_full1", "status": "succeeded"})

        substep("Verify refund status")
        gateway.info("GET /v1/refunds/re_full1", data={"status": "succeeded", "amount": int(order_total * 100)})

    with step("Generate credit note"):
        substep("Create credit note document")
        cn.info("Credit note created", data={
            "cn_id": "CN-2026-00142",
            "order_id": "ord_full1",
            "amount": order_total,
            "currency": "USD",
            "issue_date": "2026-04-02",
        })

        substep("Email credit note to customer")
        cn.info("Email sent", data={"to": "customer@example.com", "template": "credit_note", "cn_id": "CN-2026-00142"})
        cn.debug("Email service response", data={"message_id": "msg_cn1", "status": "queued"})

    step("Update order status")
    refund.info("Order status updated", data={"order_id": "ord_full1", "status": "refunded"})

    assert True


def test_refund_to_original_payment_method(log):
    """Refund goes back to the original card used for purchase."""
    refund = log.child("refund")
    card = log.child("card")

    step("Look up original payment method")
    card.info("Fetching payment method", data={"charge_id": "ch_opm1"})
    card.debug("Payment method details", data={
        "type": "card",
        "brand": "visa",
        "last4": "4242",
        "exp_month": 12,
        "exp_year": 2027,
        "fingerprint": "fp_abc123",
    })
    card.info("Original payment method found", data={"method_id": "pm_opm1", "type": "visa ending 4242"})

    with step("Process refund to original method"):
        substep("Create refund object")
        refund.info("Creating refund", data={"amount": 65.00, "method_id": "pm_opm1"})
        refund.debug("Idempotency key generated", data={"key": "idk_ref_opm1"})

        substep("Submit to card network")
        card.info("Refund submitted to Visa network", data={"amount": 65.00, "arn": "74927384950123456789012"})
        card.debug("Network response", data={"response_code": "00", "message": "approved"})
        card.info("Refund will appear in 5-10 business days")

    step("Notify customer")
    refund.info("Refund confirmation sent", data={"channel": "email", "amount": 65.00, "method": "visa ending 4242"})
    refund.debug("Push notification sent", data={"channel": "mobile_push", "title": "Refund Processed"})

    assert True


def test_refund_multi_item_partial(log):
    """Refund specific items from a multi-item order."""
    refund = log.child("refund")
    items_log = log.child("items")

    order_items = [
        {"sku": "SKU-MR1", "name": "Shirt", "price": 39.99, "qty": 2, "refund": True},
        {"sku": "SKU-MR2", "name": "Pants", "price": 59.99, "qty": 1, "refund": False},
        {"sku": "SKU-MR3", "name": "Socks (3-pack)", "price": 12.99, "qty": 1, "refund": True},
    ]

    step("Identify refundable items")
    for item in order_items:
        items_log.info("Item review", data={"sku": item["sku"], "name": item["name"], "refund_requested": item["refund"]})
    refund_items = [i for i in order_items if i["refund"]]
    items_log.info("Refundable items identified", data={"count": len(refund_items)})

    with step("Calculate partial refund"):
        substep("Sum refundable line totals")
        refund_total = sum(i["price"] * i["qty"] for i in refund_items)
        refund.info("Refund total calculated", data={"refund_total": refund_total})

        substep("Calculate proportional tax refund")
        tax_refund = round(refund_total * 0.0875, 2)
        refund.info("Tax refund calculated", data={"tax_refund": tax_refund, "rate": 0.0875})

        substep("Final refund amount")
        final_refund = round(refund_total + tax_refund, 2)
        refund.info("Final refund amount", data={"subtotal_refund": refund_total, "tax_refund": tax_refund, "total": final_refund})

    step("Process partial refund")
    refund.info("Refund issued", data={"refund_id": "re_multi1", "amount": final_refund, "status": "succeeded"})
    refund.debug("Inventory return initiated", data={"skus": [i["sku"] for i in refund_items]})

    assert refund_total == 92.97


def test_refund_restocking_fee(log):
    """Refund with restocking fee deducted for electronics."""
    refund = log.child("refund")
    fee = log.child("fees")

    order_amount = 599.99
    restocking_pct = 0.15

    step("Check restocking fee policy")
    fee.info("Evaluating restocking fee", data={"category": "electronics", "policy": "15% restocking fee after 14 days"})
    fee.debug("Order age check", data={"order_date": "2026-03-10", "days_since": 23, "threshold_days": 14})
    fee.info("Restocking fee applies", data={"rate": restocking_pct})

    with step("Calculate net refund"):
        substep("Compute restocking fee")
        restock_fee = round(order_amount * restocking_pct, 2)
        fee.info("Restocking fee", data={"fee": restock_fee})

        substep("Net refund after fee")
        net_refund = round(order_amount - restock_fee, 2)
        refund.info("Net refund calculated", data={"gross": order_amount, "restocking_fee": restock_fee, "net": net_refund})

    step("Process net refund")
    refund.info("Refund processed", data={"refund_id": "re_restock1", "amount": net_refund, "fee_deducted": restock_fee})
    refund.debug("Fee revenue recorded", data={"revenue_type": "restocking_fee", "amount": restock_fee})

    assert net_refund == 509.99


def test_refund_store_credit_issuance(log):
    """Issue store credit instead of monetary refund."""
    refund = log.child("refund")
    credit = log.child("store_credit")

    amount = 75.00

    step("Customer requests store credit")
    refund.info("Store credit refund selected", data={"order_id": "ord_sc1", "amount": amount})
    refund.debug("Store credit bonus check", data={"bonus_pct": 0.10, "eligible": True})

    with step("Issue store credit with bonus"):
        substep("Calculate bonus amount")
        bonus = round(amount * 0.10, 2)
        total_credit = round(amount + bonus, 2)
        credit.info("Bonus applied", data={"base": amount, "bonus": bonus, "total_credit": total_credit})

        substep("Create credit entry")
        credit.info("Store credit issued", data={
            "credit_id": "sc_001",
            "customer_id": "cust_sc1",
            "amount": total_credit,
            "expires": "2027-04-02",
        })
        credit.debug("Credit balance updated", data={"previous_balance": 0.00, "new_balance": total_credit})

    step("Confirm with customer")
    refund.info("Store credit confirmation sent", data={"email": "customer@example.com", "credit_amount": total_credit})

    assert total_credit == 82.50


def test_refund_subscription_proration(log):
    """Prorated refund for cancelled mid-cycle subscription."""
    refund = log.child("refund")
    sub = log.child("subscription")

    monthly_price = 49.99
    days_in_period = 30
    days_used = 12

    step("Fetch subscription details")
    sub.info("Subscription loaded", data={
        "sub_id": "sub_pro1",
        "plan": "pro_monthly",
        "price": monthly_price,
        "period_start": "2026-03-01",
        "period_end": "2026-03-31",
    })
    sub.debug("Usage stats", data={"api_calls": 1247, "storage_gb": 3.2})

    with step("Calculate prorated refund"):
        substep("Determine unused days")
        unused_days = days_in_period - days_used
        sub.info("Days calculation", data={"total": days_in_period, "used": days_used, "unused": unused_days})

        substep("Compute prorated amount")
        daily_rate = round(monthly_price / days_in_period, 4)
        prorated_refund = round(daily_rate * unused_days, 2)
        refund.info("Prorated refund calculated", data={
            "daily_rate": daily_rate,
            "unused_days": unused_days,
            "refund_amount": prorated_refund,
        })

    step("Process prorated refund")
    refund.info("Refund issued", data={"refund_id": "re_pro1", "amount": prorated_refund})
    sub.info("Subscription cancelled", data={"sub_id": "sub_pro1", "effective_date": "2026-03-12", "access_until": "2026-03-31"})

    assert prorated_refund == round(daily_rate * unused_days, 2)
    assert prorated_refund < monthly_price


def test_refund_batch_processing(log):
    """Process a batch of refunds from a CSV import."""
    batch = log.child("batch")
    refund = log.child("refund")

    refunds = [
        {"order_id": "ord_b1", "amount": 25.00},
        {"order_id": "ord_b2", "amount": 50.00},
        {"order_id": "ord_b3", "amount": 12.99},
        {"order_id": "ord_b4", "amount": 89.00},
    ]

    step("Load refund batch")
    batch.info("Batch loaded from CSV", data={"file": "refunds_2026_04.csv", "row_count": len(refunds)})
    batch.debug("CSV validation passed", data={"columns": ["order_id", "amount"], "encoding": "utf-8"})

    with step("Process each refund"):
        for i, r in enumerate(refunds):
            substep(f"Refund {r['order_id']}")
            refund.info("Processing refund", data=r)
            refund.debug("Gateway call", data={"charge_id": f"ch_{r['order_id']}", "refund_amount": r["amount"]})
            refund.info("Refund succeeded", data={"refund_id": f"re_{r['order_id']}", "status": "succeeded"})

    step("Batch summary")
    total_refunded = sum(r["amount"] for r in refunds)
    batch.info("Batch complete", data={"processed": len(refunds), "failed": 0, "total_refunded": total_refunded})

    assert total_refunded == 176.99


def test_refund_fraud_flagged_order(log):
    """Refund on a fraud-flagged order requires manual approval."""
    refund = log.child("refund")
    fraud = log.child("fraud")

    step("Submit refund for flagged order")
    refund.info("Refund requested", data={"order_id": "ord_fraud1", "amount": 320.00})
    fraud.warning("Order has fraud flag", data={"flag_reason": "velocity_check", "risk_score": 87})

    with step("Escalate to fraud team"):
        substep("Create investigation ticket")
        fraud.info("Ticket created", data={"ticket_id": "FRAUD-2026-0891", "priority": "high"})
        fraud.debug("Assigned to analyst", data={"analyst": "fraud_team_a"})

        substep("Hold refund pending review")
        refund.info("Refund held", data={"refund_id": "re_fraud1", "status": "on_hold", "reason": "fraud_investigation"})

    step("Verify hold status")
    refund.info("Refund status check", data={"refund_id": "re_fraud1", "status": "on_hold"})

    status = "on_hold"
    assert status == "on_hold"


def test_refund_currency_conversion(log):
    """Refund in a different currency than the original charge."""
    refund = log.child("refund")
    fx = log.child("forex")

    original_amount_eur = 85.00
    original_rate = 1.0850

    step("Fetch original FX details")
    fx.info("Original transaction FX", data={
        "charged_currency": "EUR",
        "settled_currency": "USD",
        "original_rate": original_rate,
        "settled_amount": round(original_amount_eur * original_rate, 2),
    })

    with step("Calculate refund in settlement currency"):
        substep("Fetch current FX rate")
        current_rate = 1.0920
        fx.info("Current FX rate", data={"pair": "EUR/USD", "rate": current_rate, "source": "ecb"})
        fx.debug("Rate delta since original charge", data={"delta": round(current_rate - original_rate, 4)})

        substep("Use original rate for refund")
        refund_usd = round(original_amount_eur * original_rate, 2)
        refund.info("Refund amount calculated at original rate", data={
            "refund_eur": original_amount_eur,
            "refund_usd": refund_usd,
            "rate_used": original_rate,
        })

    step("Issue refund")
    refund.info("Refund processed", data={"refund_id": "re_fx1", "amount_usd": refund_usd, "amount_eur": original_amount_eur})
    fx.debug("FX P&L impact", data={"unrealized_gain": round((current_rate - original_rate) * original_amount_eur, 2)})

    assert refund_usd == 92.23


# ---------------------------------------------------------------------------
# Flaky service tests
# ---------------------------------------------------------------------------

def test_refund_gateway_timeout_flaky(log, flaky_service):
    """Refund gateway times out on first attempt."""
    gw = log.child("gateway")

    step("Submit refund to gateway")
    gw.info("POST /v1/refunds", data={"charge_id": "ch_gw_fl1", "amount": 45.00})
    try:
        flaky_service("refund_gateway_post")
    except ConnectionError:
        gw.warning("Gateway timeout on first attempt", data={"elapsed_ms": 30000})

    step("Retry refund submission")
    result = flaky_service("refund_gateway_post")
    gw.info("Refund succeeded on retry", data={"result": result, "refund_id": "re_gw_fl1"})

    assert result == "ok:refund_gateway_post"


def test_refund_notification_service_flaky(log, flaky_service):
    """Customer notification service fails on first call."""
    notify = log.child("notifications")

    step("Send refund notification")
    notify.info("Sending email notification", data={"to": "customer@example.com", "template": "refund_processed"})
    try:
        flaky_service("refund_email_service")
    except ConnectionError:
        notify.warning("Email service unavailable, queuing for retry")

    step("Retry notification delivery")
    result = flaky_service("refund_email_service")
    notify.info("Email sent successfully", data={"result": result, "message_id": "msg_ref_notify1"})

    assert result == "ok:refund_email_service"


def test_refund_ledger_service_flaky(log, flaky_service):
    """Accounting ledger service has intermittent failures."""
    ledger = log.child("ledger")

    step("Post refund to ledger")
    ledger.info("Creating journal entry", data={"debit": "refunds_expense", "credit": "accounts_payable", "amount": 110.00})
    try:
        flaky_service("refund_ledger_post")
    except ConnectionError:
        ledger.warning("Ledger service connection failed")

    step("Retry ledger posting")
    result = flaky_service("refund_ledger_post")
    ledger.info("Journal entry posted", data={"result": result, "entry_id": "je_ref1"})

    assert result == "ok:refund_ledger_post"


# ---------------------------------------------------------------------------
# Deliberate failures
# ---------------------------------------------------------------------------

def test_refund_exceeds_original_charge(log):
    """BUG: Refund amount exceeds original charge -- should be blocked."""
    refund = log.child("refund")

    original = 100.00
    requested = 150.00

    step("Submit over-refund request")
    refund.info("Refund requested", data={"order_id": "ord_over1", "original": original, "requested": requested})
    refund.error("Refund amount exceeds original charge", data={"excess": requested - original})

    step("Assert refund is blocked")
    assert requested <= original, f"Refund {requested} exceeds original charge {original}"


def test_refund_already_refunded(log):
    """Attempting to refund an already-refunded order should fail."""
    refund = log.child("refund")

    step("Check prior refund status")
    refund.info("Querying refund history", data={"order_id": "ord_dup_ref"})
    refund.info("Prior refund found", data={"refund_id": "re_dup1", "status": "succeeded", "amount": 80.00})

    step("Attempt duplicate refund")
    refund.error("Order already fully refunded", data={"order_id": "ord_dup_ref", "existing_refund": "re_dup1"})

    allowed = False
    assert allowed, "Duplicate refund should have been prevented but was incorrectly allowed"


# ---------------------------------------------------------------------------
# Skipped tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Gift card refund policy under legal review")
def test_refund_to_gift_card(log):
    """Refund issued as gift card balance."""
    pass


@pytest.mark.skip(reason="Cryptocurrency refund path not implemented")
def test_refund_crypto_payment(log):
    """Refund for a cryptocurrency payment."""
    pass
