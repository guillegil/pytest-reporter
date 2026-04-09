"""Shopping cart tests -- add/remove items, pricing rules, promotions."""

from __future__ import annotations

import pytest

from pytest_reporter import step, substep


# ---------------------------------------------------------------------------
# Parametrized: add items with various attributes
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "sku,name,price,qty",
    [
        ("SKU-001", "Wireless Mouse", 29.99, 1),
        ("SKU-002", "Mechanical Keyboard", 89.95, 1),
        ("SKU-003", "USB-C Hub", 45.00, 2),
        ("SKU-004", "Monitor Stand", 119.99, 1),
        ("SKU-005", "Webcam HD", 59.50, 3),
    ],
    ids=["mouse", "keyboard", "usb-hub-x2", "monitor-stand", "webcam-x3"],
)
def test_cart_add_item(log, sku: str, name: str, price: float, qty: int):
    """Add a single product to the cart and verify totals."""
    cart = log.child("cart")
    catalog = log.child("catalog")

    step("Look up product in catalog")
    catalog.info("Fetching product details", data={"sku": sku})
    catalog.debug("Cache hit", data={"cache_key": f"product:{sku}", "ttl_remaining_s": 245})
    catalog.info("Product found", data={"sku": sku, "name": name, "price": price, "in_stock": True})

    with step("Add to cart"):
        substep("Validate quantity")
        cart.info("Checking quantity limit", data={"sku": sku, "requested": qty, "max_per_order": 10})
        cart.debug("Quantity within bounds")

        substep("Insert cart line")
        cart.info("Item added", data={"sku": sku, "qty": qty, "line_total": round(price * qty, 2)})
        cart.debug("Cart cookie updated", data={"cart_id": "cart_aZ9x", "item_count": qty})

    step("Verify cart state")
    expected_total = round(price * qty, 2)
    cart.info("Cart total computed", data={"total": expected_total, "item_count": qty})
    cart.debug("Cart serialized for session storage", data={"size_bytes": 512})

    assert expected_total == round(price * qty, 2)


@pytest.mark.parametrize(
    "promo,min_spend,free_shipping",
    [
        ("FREESHIP50", 50.00, True),
        ("FREESHIP100", 100.00, True),
        ("NONE", 0.00, False),
    ],
    ids=["free-over-50", "free-over-100", "no-promo"],
)
def test_cart_shipping_promo(log, promo: str, min_spend: float, free_shipping: bool):
    """Free shipping promotions based on cart total."""
    ship = log.child("shipping")
    promo_log = log.child("promotions")

    cart_total = 75.00

    step("Evaluate shipping promotion")
    promo_log.info("Checking promotion eligibility", data={"promo": promo, "cart_total": cart_total})
    if promo != "NONE":
        promo_log.debug("Promotion lookup", data={"code": promo, "type": "free_shipping", "min_spend": min_spend})
    qualifies = cart_total >= min_spend and promo != "NONE"
    promo_log.info("Eligibility result", data={"qualifies": qualifies, "promo": promo})

    with step("Calculate shipping cost"):
        substep("Estimate base shipping")
        base_shipping = 9.99
        ship.info("Base shipping rate", data={"rate": base_shipping, "carrier": "UPS", "service": "ground"})
        ship.debug("Package dimensions estimated", data={"weight_lbs": 2.5, "length_in": 12, "width_in": 8, "height_in": 6})

        substep("Apply promotion discount")
        final_shipping = 0.00 if qualifies else base_shipping
        ship.info("Final shipping cost", data={"cost": final_shipping, "free_shipping_applied": qualifies})

    step("Verify shipping")
    ship.info("Shipping summary", data={"cart_total": cart_total, "shipping": final_shipping, "grand_total": cart_total + final_shipping})

    if free_shipping and cart_total >= min_spend:
        assert final_shipping == 0.00
    elif promo == "NONE":
        assert final_shipping == base_shipping


# ---------------------------------------------------------------------------
# Individual cart tests
# ---------------------------------------------------------------------------

def test_cart_remove_item(log):
    """Remove an item from the cart and recalculate."""
    cart = log.child("cart")

    items = [
        {"sku": "SKU-R1", "name": "Headphones", "price": 79.99, "qty": 1},
        {"sku": "SKU-R2", "name": "Phone Case", "price": 19.99, "qty": 2},
        {"sku": "SKU-R3", "name": "Screen Protector", "price": 12.50, "qty": 1},
    ]

    step("Initialize cart with 3 items")
    for item in items:
        cart.info("Adding item", data=item)
    total_before = sum(i["price"] * i["qty"] for i in items)
    cart.info("Cart total before removal", data={"total": total_before, "line_count": 3})

    with step("Remove SKU-R2"):
        substep("Locate item in cart")
        cart.debug("Searching cart lines", data={"target_sku": "SKU-R2"})
        cart.info("Item found at index 1")

        substep("Remove and recalculate")
        items.pop(1)
        total_after = sum(i["price"] * i["qty"] for i in items)
        cart.info("Item removed", data={"removed_sku": "SKU-R2", "new_total": total_after, "line_count": 2})

    step("Verify updated total")
    cart.info("Final cart state", data={"total": total_after, "items_remaining": len(items)})
    cart.debug("Cart event emitted", data={"event": "item_removed", "sku": "SKU-R2"})

    assert total_after == 92.49


def test_cart_quantity_update(log):
    """Update item quantity in the cart."""
    cart = log.child("cart")
    inv = log.child("inventory")

    step("Add item with qty=1")
    cart.info("Adding item", data={"sku": "SKU-QU1", "name": "Notebook", "price": 14.99, "qty": 1})

    with step("Update quantity to 5"):
        substep("Check inventory availability")
        inv.info("Querying stock", data={"sku": "SKU-QU1", "warehouse": "us-central"})
        inv.info("Stock available", data={"available": 120, "requested": 5})
        inv.debug("Reserved stock: 8 units already reserved by other carts")

        substep("Apply new quantity")
        new_qty = 5
        line_total = round(14.99 * new_qty, 2)
        cart.info("Quantity updated", data={"sku": "SKU-QU1", "old_qty": 1, "new_qty": new_qty, "line_total": line_total})

    step("Verify line total")
    cart.info("Line total verified", data={"expected": 74.95, "actual": line_total})

    assert line_total == 74.95


def test_cart_buy_one_get_one(log):
    """BOGO promotion: buy 1 get 1 free on eligible items."""
    cart = log.child("cart")
    promo = log.child("promotions")

    step("Add BOGO-eligible item")
    cart.info("Adding item", data={"sku": "SKU-BOGO", "name": "T-Shirt", "price": 24.99, "qty": 2})

    with step("Evaluate BOGO promotion"):
        substep("Check item eligibility")
        promo.info("Checking BOGO rules", data={"sku": "SKU-BOGO", "category": "apparel"})
        promo.debug("BOGO rule matched", data={"rule_id": "bogo_apparel_2026Q2", "buy": 1, "get": 1})

        substep("Apply discount to second item")
        promo.info("Discount applied", data={"sku": "SKU-BOGO", "free_qty": 1, "discount_amount": 24.99})
        cart.info("Cart line adjusted", data={"sku": "SKU-BOGO", "charged_qty": 1, "free_qty": 1, "line_total": 24.99})

    step("Verify BOGO pricing")
    cart.info("Cart summary", data={"subtotal": 24.99, "savings": 24.99, "promo_applied": "bogo_apparel_2026Q2"})
    promo.debug("Promotion usage counter incremented", data={"rule_id": "bogo_apparel_2026Q2", "uses_today": 47})

    total = 24.99
    assert total == 24.99


def test_cart_weight_based_shipping(log):
    """Shipping cost varies by total cart weight."""
    cart = log.child("cart")
    ship = log.child("shipping")

    items = [
        {"sku": "SKU-W1", "name": "Dumbbells 10lb", "price": 35.00, "weight_lbs": 10.0},
        {"sku": "SKU-W2", "name": "Yoga Mat", "price": 25.00, "weight_lbs": 3.5},
        {"sku": "SKU-W3", "name": "Resistance Bands Set", "price": 18.00, "weight_lbs": 1.2},
    ]

    step("Calculate cart weight")
    total_weight = 0.0
    for item in items:
        cart.info("Item weight", data={"sku": item["sku"], "weight_lbs": item["weight_lbs"]})
        total_weight += item["weight_lbs"]
    cart.info("Total cart weight", data={"weight_lbs": total_weight})

    with step("Determine shipping tier"):
        substep("Evaluate weight brackets")
        ship.info("Weight bracket evaluation", data={
            "brackets": [
                {"max_lbs": 5, "rate": 5.99},
                {"max_lbs": 15, "rate": 12.99},
                {"max_lbs": 50, "rate": 24.99},
            ],
        })
        if total_weight <= 5:
            rate = 5.99
        elif total_weight <= 15:
            rate = 12.99
        else:
            rate = 24.99
        ship.info("Tier selected", data={"weight_lbs": total_weight, "rate": rate, "tier": "medium"})

        substep("Apply carrier surcharge")
        surcharge = 2.00
        ship.debug("Carrier surcharge applied", data={"carrier": "FedEx", "surcharge": surcharge})
        final_rate = rate + surcharge
        ship.info("Final shipping rate", data={"base": rate, "surcharge": surcharge, "total": final_rate})

    step("Verify shipping")
    ship.info("Shipping finalized", data={"rate": final_rate, "estimated_days": 5})
    assert final_rate == 14.99


def test_cart_max_items_limit(log):
    """Cart should enforce a maximum item limit."""
    cart = log.child("cart")
    val = log.child("validation")

    max_items = 50

    step("Fill cart to capacity")
    for i in range(max_items):
        if i % 10 == 0:
            cart.debug(f"Adding batch, current count: {i}", data={"batch_start": i})
    cart.info("Cart at capacity", data={"item_count": max_items, "max_items": max_items})

    step("Attempt to add one more item")
    val.warning("Cart limit reached", data={"current": max_items, "max": max_items, "sku": "SKU-EXTRA"})
    val.info("Item rejected", data={"reason": "max_items_exceeded"})

    step("Verify rejection")
    cart.info("Cart item count unchanged", data={"count": max_items})

    assert max_items == 50


def test_cart_saved_for_later(log):
    """Move item from cart to saved-for-later list."""
    cart = log.child("cart")
    saved = log.child("saved_for_later")

    step("Add item to cart")
    cart.info("Item in cart", data={"sku": "SKU-SFL1", "name": "Bluetooth Speaker", "price": 49.99})

    with step("Move to saved-for-later"):
        substep("Remove from active cart")
        cart.info("Removing from cart", data={"sku": "SKU-SFL1"})
        cart.debug("Cart line deleted", data={"index": 0})

        substep("Add to saved list")
        saved.info("Item saved", data={"sku": "SKU-SFL1", "customer_id": "cust_sfl1"})
        saved.debug("Saved list persisted", data={"storage": "dynamodb", "table": "saved_items"})

    step("Verify cart is empty")
    cart.info("Cart state", data={"item_count": 0, "saved_count": 1})

    cart_count = 0
    saved_count = 1
    assert cart_count == 0
    assert saved_count == 1


def test_cart_merge_guest_to_user(log):
    """Merge guest cart into authenticated user cart on login."""
    cart = log.child("cart")
    auth = log.child("auth")

    guest_items = [
        {"sku": "SKU-G1", "price": 15.00, "qty": 1},
        {"sku": "SKU-G2", "price": 30.00, "qty": 2},
    ]
    user_items = [
        {"sku": "SKU-U1", "price": 45.00, "qty": 1},
    ]

    step("Guest cart state")
    cart.info("Guest cart loaded", data={"session_id": "sess_guest_abc", "items": guest_items})

    step("User logs in")
    auth.info("Authentication successful", data={"user_id": "usr_merge1", "method": "password"})
    auth.debug("Session upgraded", data={"from": "sess_guest_abc", "to": "sess_user_xyz"})

    with step("Merge carts"):
        substep("Load user cart")
        cart.info("User cart loaded", data={"user_id": "usr_merge1", "items": user_items})

        substep("Combine line items")
        merged = guest_items + user_items
        cart.info("Carts merged", data={"total_lines": len(merged), "guest_lines": len(guest_items), "user_lines": len(user_items)})
        cart.debug("Duplicate SKU check", data={"duplicates_found": 0})

        substep("Persist merged cart")
        cart.info("Merged cart saved", data={"user_id": "usr_merge1", "item_count": len(merged)})

    step("Verify merged cart")
    total = sum(i["price"] * i["qty"] for i in merged)
    cart.info("Merged cart total", data={"total": total, "line_count": 3})

    assert len(merged) == 3
    assert total == 120.00


def test_cart_tax_by_jurisdiction(log):
    """Tax rate varies by shipping destination."""
    tax = log.child("tax")

    step("Determine tax jurisdiction")
    tax.info("Shipping address provided", data={
        "street": "123 Main St",
        "city": "San Francisco",
        "state": "CA",
        "zip": "94105",
        "country": "US",
    })
    tax.debug("Geocoding address", data={"lat": 37.7897, "lng": -122.3972})
    tax.info("Tax jurisdiction resolved", data={"state": "CA", "county": "San Francisco", "city_tax": True})

    with step("Calculate tax breakdown"):
        subtotal = 150.00
        substep("State tax")
        state_tax = round(subtotal * 0.0625, 2)
        tax.info("State tax", data={"rate": 0.0625, "amount": state_tax})

        substep("County tax")
        county_tax = round(subtotal * 0.0125, 2)
        tax.info("County tax", data={"rate": 0.0125, "amount": county_tax})

        substep("City tax")
        city_tax = round(subtotal * 0.0125, 2)
        tax.info("City tax", data={"rate": 0.0125, "amount": city_tax})

    step("Verify total tax")
    total_tax = round(state_tax + county_tax + city_tax, 2)
    tax.info("Total tax", data={"total_tax": total_tax, "effective_rate": round(total_tax / subtotal, 4)})

    assert total_tax == round(subtotal * 0.0875, 2)


# ---------------------------------------------------------------------------
# Flaky service tests
# ---------------------------------------------------------------------------

def test_cart_pricing_service_flaky(log, flaky_service):
    """Pricing microservice has intermittent timeouts."""
    pricing = log.child("pricing")

    step("Fetch dynamic pricing")
    pricing.info("Requesting live price", data={"sku": "SKU-DYN1"})
    try:
        flaky_service("cart_pricing_live")
    except ConnectionError:
        pricing.warning("Pricing service timeout, using cached price")

    step("Retry pricing fetch")
    result = flaky_service("cart_pricing_live")
    pricing.info("Live price received", data={"result": result, "price": 34.99})

    assert result == "ok:cart_pricing_live"


def test_cart_recommendation_engine_flaky(log, flaky_service):
    """Product recommendation service is flaky."""
    reco = log.child("recommendations")

    step("Request recommendations")
    reco.info("Fetching related products", data={"cart_skus": ["SKU-R1", "SKU-R2"]})
    try:
        flaky_service("cart_recommendations")
    except ConnectionError:
        reco.warning("Recommendation service unavailable, returning empty list")

    step("Retry recommendation fetch")
    result = flaky_service("cart_recommendations")
    reco.info("Recommendations received", data={"result": result, "count": 5})

    assert result == "ok:cart_recommendations"


# ---------------------------------------------------------------------------
# Deliberate failures
# ---------------------------------------------------------------------------

def test_cart_negative_quantity(log):
    """BUG: Negative quantity should be rejected but passes validation."""
    val = log.child("validation")

    step("Add item with negative quantity")
    val.info("Attempting to add item", data={"sku": "SKU-NEG", "qty": -3, "price": 19.99})
    val.error("Negative quantity not caught by validator")

    step("Assert rejection")
    rejected = False
    assert rejected, "Negative quantity should have been rejected"


def test_cart_price_overflow(log):
    """Line total exceeds maximum representable price."""
    cart = log.child("cart")

    step("Add extremely expensive item")
    price = 99999999.99
    qty = 1000
    line_total = round(price * qty, 2)
    cart.info("Line total computed", data={"price": price, "qty": qty, "line_total": line_total})
    cart.error("Line total exceeds safe limit", data={"limit": 99999999.99, "actual": line_total})

    step("Assert within safe limit")
    assert line_total <= 99999999.99, f"Line total {line_total} exceeds safe limit"


# ---------------------------------------------------------------------------
# Skipped tests
# ---------------------------------------------------------------------------

@pytest.mark.skip(reason="Gift wrapping feature not yet implemented")
def test_cart_gift_wrapping(log):
    """Add gift wrapping option to cart items."""
    pass


@pytest.mark.skip(reason="Subscription items require billing service v3")
def test_cart_subscription_item(log):
    """Add a recurring subscription product to the cart."""
    pass
