"""Inventory report tests -- stock tracking, reorder analysis, and warehouse ETL."""

from __future__ import annotations

import math
import random

import pytest

from pytest_reporter import step, substep


WAREHOUSES = ["WH-East", "WH-West", "WH-Central", "WH-South"]
CATEGORIES = ["Electronics", "Apparel", "Home & Garden", "Automotive", "Food & Beverage"]

INVENTORY_RECORDS = [
    {
        "sku": f"SKU-{i:05d}",
        "name": f"Product {chr(65 + i % 26)}-{i:03d}",
        "category": CATEGORIES[i % len(CATEGORIES)],
        "warehouse": WAREHOUSES[i % len(WAREHOUSES)],
        "on_hand": max(0, 500 - i * 3 + random.Random(i).randint(-50, 50)),
        "reorder_point": 100 + (i % 5) * 20,
        "lead_time_days": 3 + i % 10,
        "unit_cost": round(5.0 + i * 0.75, 2),
        "last_received": f"2026-0{1 + i % 3}-{10 + i % 18:02d}",
        "daily_demand": max(1, 10 + random.Random(i * 7).randint(-5, 15)),
    }
    for i in range(100)
]


# ---------------------------------------------------------------------------
# Stock level tests
# ---------------------------------------------------------------------------


def test_total_inventory_valuation(log):
    """Compute total inventory value across all warehouses."""
    vl = log.child("valuation")

    step("Load inventory dataset")
    vl.info("Records loaded", data={"count": len(INVENTORY_RECORDS)})
    vl.debug("Schema fields", data={"fields": list(INVENTORY_RECORDS[0].keys())})

    step("Compute valuation per SKU")
    calc = vl.child("calc")
    total_value = 0.0
    for i, rec in enumerate(INVENTORY_RECORDS):
        value = rec["on_hand"] * rec["unit_cost"]
        total_value += value
        if i < 3:
            calc.debug(f"SKU {rec['sku']}", data={"on_hand": rec["on_hand"], "unit_cost": rec["unit_cost"], "value": round(value, 2)})

    step("Summarize")
    vl.info("Total inventory valuation", data={"total_value": round(total_value, 2), "avg_per_sku": round(total_value / len(INVENTORY_RECORDS), 2)})
    substep("Validate positive valuation")
    assert total_value > 0
    vl.info("Valuation pipeline complete")


@pytest.mark.parametrize("warehouse", WAREHOUSES, ids=[w.lower().replace("-", "_") for w in WAREHOUSES])
def test_warehouse_stock_levels(log, warehouse):
    """Check stock levels for a specific warehouse."""
    wl = log.child("warehouse")

    step(f"Filter inventory for {warehouse}")
    filtered = [r for r in INVENTORY_RECORDS if r["warehouse"] == warehouse]
    wl.info("Filtered records", data={"warehouse": warehouse, "sku_count": len(filtered)})

    step("Compute warehouse metrics")
    substep("Total units on hand")
    total_units = sum(r["on_hand"] for r in filtered)
    wl.info("Total on-hand units", data={"units": total_units})
    substep("Total valuation")
    total_val = sum(r["on_hand"] * r["unit_cost"] for r in filtered)
    wl.info("Warehouse valuation", data={"value": round(total_val, 2)})
    substep("Average lead time")
    avg_lead = sum(r["lead_time_days"] for r in filtered) / len(filtered) if filtered else 0
    wl.info("Average lead time", data={"days": round(avg_lead, 1)})

    step("Identify low-stock SKUs")
    low_stock = [r for r in filtered if r["on_hand"] < r["reorder_point"]]
    for r in low_stock[:5]:
        wl.warning(f"Low stock: {r['sku']}", data={"on_hand": r["on_hand"], "reorder_point": r["reorder_point"], "deficit": r["reorder_point"] - r["on_hand"]})
    wl.info("Low stock summary", data={"low_stock_count": len(low_stock), "total_skus": len(filtered)})

    step("Validate warehouse data")
    assert len(filtered) > 0
    assert total_units >= 0
    wl.info(f"Warehouse {warehouse} analysis complete")


@pytest.mark.parametrize("category", CATEGORIES, ids=[c.lower().replace(" & ", "-").replace(" ", "-") for c in CATEGORIES])
def test_category_stock_distribution(log, category):
    """Analyze stock distribution by product category."""
    cl = log.child("category")

    step(f"Extract category: {category}")
    items = [r for r in INVENTORY_RECORDS if r["category"] == category]
    cl.info("Category filter applied", data={"category": category, "items": len(items)})

    step("Compute distribution metrics")
    on_hand = [r["on_hand"] for r in items]
    mean_stock = sum(on_hand) / len(on_hand) if on_hand else 0
    min_stock = min(on_hand) if on_hand else 0
    max_stock = max(on_hand) if on_hand else 0
    cl.info("Stock distribution", data={"mean": round(mean_stock, 1), "min": min_stock, "max": max_stock})

    step("Compute category valuation")
    total_val = sum(r["on_hand"] * r["unit_cost"] for r in items)
    cl.info("Category valuation", data={"total_value": round(total_val, 2)})

    step("Warehouse breakdown for category")
    wh_counts = {}
    for r in items:
        wh_counts.setdefault(r["warehouse"], 0)
        wh_counts[r["warehouse"]] += r["on_hand"]
    for wh, units in wh_counts.items():
        cl.info(f"{wh}", data={"units": units, "pct": round(units / sum(on_hand) * 100, 1) if sum(on_hand) else 0})

    step("Validate category data")
    assert len(items) > 0
    assert total_val >= 0
    cl.info("Category distribution analysis done")


def test_reorder_point_analysis(log):
    """Identify SKUs that need reordering and compute order quantities."""
    rl = log.child("reorder")

    step("Scan all SKUs for reorder needs")
    needs_reorder = []
    for r in INVENTORY_RECORDS:
        if r["on_hand"] < r["reorder_point"]:
            deficit = r["reorder_point"] - r["on_hand"]
            safety_stock = r["daily_demand"] * r["lead_time_days"]
            order_qty = deficit + safety_stock
            needs_reorder.append({**r, "deficit": deficit, "safety_stock": safety_stock, "order_qty": order_qty})

    rl.info("Reorder scan complete", data={"total_skus": len(INVENTORY_RECORDS), "needs_reorder": len(needs_reorder)})

    step("Generate reorder recommendations")
    rec_log = rl.child("recommendations")
    total_order_cost = 0.0
    for item in needs_reorder[:10]:
        cost = item["order_qty"] * item["unit_cost"]
        total_order_cost += cost
        rec_log.info(f"Reorder: {item['sku']}", data={
            "on_hand": item["on_hand"],
            "reorder_point": item["reorder_point"],
            "order_qty": item["order_qty"],
            "estimated_cost": round(cost, 2),
            "lead_time_days": item["lead_time_days"],
        })

    step("Summarize reorder batch")
    rl.info("Reorder batch summary", data={
        "skus_to_reorder": len(needs_reorder),
        "total_order_cost": round(total_order_cost, 2),
        "avg_lead_time": round(sum(r["lead_time_days"] for r in needs_reorder) / len(needs_reorder), 1) if needs_reorder else 0,
    })

    step("Validate reorder logic")
    substep("All order quantities positive")
    for item in needs_reorder:
        assert item["order_qty"] > 0
    rl.info("Reorder analysis complete")


def test_inventory_turnover_ratio(log):
    """Compute inventory turnover ratio per warehouse."""
    tl = log.child("turnover")

    step("Compute annual demand per warehouse")
    wh_demand = {}
    wh_avg_inv = {}
    for r in INVENTORY_RECORDS:
        annual_demand = r["daily_demand"] * 365
        wh_demand.setdefault(r["warehouse"], 0)
        wh_demand[r["warehouse"]] += annual_demand * r["unit_cost"]
        wh_avg_inv.setdefault(r["warehouse"], 0.0)
        wh_avg_inv[r["warehouse"]] += r["on_hand"] * r["unit_cost"]

    step("Calculate turnover ratios")
    for wh in WAREHOUSES:
        demand = wh_demand.get(wh, 0)
        avg_inv = wh_avg_inv.get(wh, 1)
        turnover = demand / avg_inv if avg_inv > 0 else 0
        days_on_hand = 365 / turnover if turnover > 0 else float("inf")
        tl.info(f"Warehouse: {wh}", data={
            "annual_demand_value": round(demand, 2),
            "avg_inventory_value": round(avg_inv, 2),
            "turnover_ratio": round(turnover, 2),
            "days_on_hand": round(days_on_hand, 1) if days_on_hand != float("inf") else "N/A",
        })

    step("Validate turnover metrics")
    overall_demand = sum(wh_demand.values())
    overall_inv = sum(wh_avg_inv.values())
    overall_turnover = overall_demand / overall_inv if overall_inv > 0 else 0
    tl.info("Overall turnover", data={"ratio": round(overall_turnover, 2)})
    assert overall_turnover > 0
    tl.info("Turnover analysis complete")


def test_dead_stock_identification(log):
    """Identify items with zero demand (dead stock)."""
    dl = log.child("dead_stock")

    step("Scan for zero-demand items")
    dead = [r for r in INVENTORY_RECORDS if r["daily_demand"] <= 0]
    dl.info("Dead stock scan", data={"total_skus": len(INVENTORY_RECORDS), "dead_stock_count": len(dead)})

    step("Compute carrying cost of dead stock")
    carrying_rate = 0.25  # 25% annual carrying cost
    total_carrying = sum(r["on_hand"] * r["unit_cost"] * carrying_rate for r in dead)
    dl.info("Dead stock carrying cost", data={"annual_cost": round(total_carrying, 2), "carrying_rate": carrying_rate})

    step("Validate dead stock analysis")
    dl.info("Dead stock items catalogued", data={"count": len(dead)})
    # All items in our dataset have demand >= 1 by construction
    assert len(dead) == 0, f"Found {len(dead)} dead stock items"
    dl.info("No dead stock found -- inventory is healthy")


def test_lead_time_distribution(log):
    """Analyze supplier lead time distribution."""
    ll = log.child("lead_time")

    step("Collect lead times")
    lead_times = [r["lead_time_days"] for r in INVENTORY_RECORDS]
    ll.info("Lead times collected", data={"count": len(lead_times)})

    step("Compute statistics")
    mean_lt = sum(lead_times) / len(lead_times)
    variance = sum((x - mean_lt) ** 2 for x in lead_times) / len(lead_times)
    std_lt = math.sqrt(variance)
    ll.info("Lead time stats", data={
        "mean": round(mean_lt, 2),
        "std": round(std_lt, 2),
        "min": min(lead_times),
        "max": max(lead_times),
        "median": sorted(lead_times)[len(lead_times) // 2],
    })

    step("Identify long-lead-time items")
    threshold = mean_lt + 2 * std_lt
    long_lead = [r for r in INVENTORY_RECORDS if r["lead_time_days"] > threshold]
    ll.info("Long lead time items", data={"threshold_days": round(threshold, 1), "count": len(long_lead)})
    for r in long_lead[:5]:
        ll.warning(f"Long lead: {r['sku']}", data={"lead_time": r["lead_time_days"], "warehouse": r["warehouse"]})

    step("Validate lead times")
    assert min(lead_times) >= 0
    assert mean_lt > 0
    ll.info("Lead time analysis complete")


def test_abc_classification(log):
    """Classify inventory items using ABC analysis (by value)."""
    al = log.child("abc")

    step("Compute annual usage value per SKU")
    items_with_value = []
    for r in INVENTORY_RECORDS:
        annual_value = r["daily_demand"] * 365 * r["unit_cost"]
        items_with_value.append({"sku": r["sku"], "category": r["category"], "annual_value": annual_value})
    items_with_value.sort(key=lambda x: -x["annual_value"])

    step("Assign ABC classes")
    total_value = sum(i["annual_value"] for i in items_with_value)
    cumulative = 0.0
    class_counts = {"A": 0, "B": 0, "C": 0}
    for item in items_with_value:
        cumulative += item["annual_value"]
        pct = cumulative / total_value * 100
        if pct <= 80:
            item["class"] = "A"
        elif pct <= 95:
            item["class"] = "B"
        else:
            item["class"] = "C"
        class_counts[item["class"]] += 1

    step("Report classification summary")
    for cls, count in class_counts.items():
        cls_items = [i for i in items_with_value if i["class"] == cls]
        cls_value = sum(i["annual_value"] for i in cls_items)
        al.info(f"Class {cls}", data={
            "sku_count": count,
            "pct_of_skus": round(count / len(items_with_value) * 100, 1),
            "total_value": round(cls_value, 2),
            "pct_of_value": round(cls_value / total_value * 100, 1),
        })

    step("Validate ABC coverage")
    assert sum(class_counts.values()) == len(INVENTORY_RECORDS)
    assert class_counts["A"] > 0
    al.info("ABC classification complete", data={"total_skus": len(items_with_value)})


def test_safety_stock_calculation(log):
    """Calculate safety stock levels using service level approach."""
    sl = log.child("safety_stock")

    step("Define service level parameters")
    z_score = 1.65  # ~95% service level
    sl.info("Service level parameters", data={"target_service_level": "95%", "z_score": z_score})

    step("Compute safety stock per SKU")
    results = []
    for r in INVENTORY_RECORDS[:15]:
        demand_std = r["daily_demand"] * 0.3  # assume 30% demand variability
        lead_std = r["lead_time_days"] * 0.2  # 20% lead time variability
        safety = z_score * math.sqrt(r["lead_time_days"] * demand_std ** 2 + r["daily_demand"] ** 2 * lead_std ** 2)
        results.append({"sku": r["sku"], "safety_stock": round(safety, 0), "current_on_hand": r["on_hand"]})
        sl.info(f"SKU {r['sku']}", data={
            "daily_demand": r["daily_demand"],
            "lead_time_days": r["lead_time_days"],
            "safety_stock": round(safety, 0),
            "on_hand": r["on_hand"],
            "buffer_ok": r["on_hand"] >= safety,
        })

    step("Summary")
    understocked = [r for r in results if r["current_on_hand"] < r["safety_stock"]]
    sl.info("Safety stock analysis", data={"total_analyzed": len(results), "understocked": len(understocked)})
    sl.info("Safety stock calculation complete")


@pytest.mark.parametrize("warehouse", WAREHOUSES[:2], ids=["wh_east", "wh_west"])
def test_warehouse_capacity_utilization(log, warehouse):
    """Check warehouse capacity utilization rate."""
    cl = log.child("capacity")

    step(f"Load capacity data for {warehouse}")
    capacity = 15000  # max units per warehouse
    filtered = [r for r in INVENTORY_RECORDS if r["warehouse"] == warehouse]
    current_units = sum(r["on_hand"] for r in filtered)
    cl.info("Capacity data", data={"warehouse": warehouse, "capacity": capacity, "current_units": current_units})

    step("Compute utilization")
    utilization = current_units / capacity * 100
    cl.info("Utilization rate", data={"pct": round(utilization, 1), "remaining_capacity": capacity - current_units})

    step("Check capacity thresholds")
    substep("Below critical threshold (95%)")
    cl.info("Critical threshold check", data={"utilization": round(utilization, 1), "threshold": 95})
    substep("Above minimum threshold (10%)")
    cl.info("Minimum threshold check", data={"utilization": round(utilization, 1), "threshold": 10})

    step("Validate")
    assert 0 <= utilization <= 100
    cl.info(f"Capacity analysis for {warehouse} done")


def test_fifo_cost_calculation(log):
    """Calculate inventory cost using FIFO method."""
    fl = log.child("fifo")

    step("Build receipt history")
    receipts = [
        {"date": "2026-01-15", "units": 200, "unit_cost": 10.00},
        {"date": "2026-02-10", "units": 300, "unit_cost": 11.50},
        {"date": "2026-03-05", "units": 150, "unit_cost": 12.25},
    ]
    fl.info("Receipt history loaded", data={"batches": len(receipts), "total_units": sum(r["units"] for r in receipts)})

    step("Compute FIFO cost for 350 units sold")
    units_to_cost = 350
    remaining = units_to_cost
    total_cost = 0.0
    for batch in receipts:
        take = min(remaining, batch["units"])
        cost = take * batch["unit_cost"]
        total_cost += cost
        fl.info(f"Batch {batch['date']}", data={"take": take, "cost": round(cost, 2), "remaining_to_cost": remaining - take})
        remaining -= take
        if remaining <= 0:
            break

    step("Validate FIFO cost")
    fl.info("FIFO cost result", data={"units_costed": units_to_cost, "total_cost": round(total_cost, 2), "avg_cost_per_unit": round(total_cost / units_to_cost, 2)})
    assert total_cost > 0
    assert remaining == 0
    fl.info("FIFO calculation verified")


def test_inventory_aging_analysis(log):
    """Analyze inventory age based on last received date."""
    al = log.child("aging")

    step("Compute days since last receipt")
    from datetime import date
    reference = date(2026, 4, 2)
    aging_buckets = {"0-30": 0, "31-60": 0, "61-90": 0, "90+": 0}
    for r in INVENTORY_RECORDS:
        parts = r["last_received"].split("-")
        received = date(int(parts[0]), int(parts[1]), int(parts[2]))
        days = (reference - received).days
        if days <= 30:
            aging_buckets["0-30"] += r["on_hand"]
        elif days <= 60:
            aging_buckets["31-60"] += r["on_hand"]
        elif days <= 90:
            aging_buckets["61-90"] += r["on_hand"]
        else:
            aging_buckets["90+"] += r["on_hand"]

    step("Report aging distribution")
    total_units = sum(aging_buckets.values())
    for bucket, units in aging_buckets.items():
        pct = units / total_units * 100 if total_units else 0
        al.info(f"Aging bucket: {bucket} days", data={"units": units, "pct": round(pct, 1)})

    step("Validate aging")
    al.info("Total units in aging analysis", data={"total": total_units})
    assert total_units > 0
    al.info("Aging analysis complete")


def test_demand_forecast_accuracy(log):
    """Compare actual demand against simple moving average forecast."""
    fl = log.child("forecast")

    step("Generate synthetic weekly actuals")
    weekly_actual = [sum(r["daily_demand"] for r in INVENTORY_RECORDS[i*10:(i+1)*10]) for i in range(10)]
    fl.info("Weekly actuals", data={"weeks": len(weekly_actual), "values": weekly_actual})

    step("Compute 3-week moving average forecast")
    forecasts = []
    for i in range(3, len(weekly_actual)):
        forecast = sum(weekly_actual[i-3:i]) / 3
        actual = weekly_actual[i]
        error = abs(actual - forecast)
        pct_error = error / actual * 100 if actual else 0
        forecasts.append({"week": i + 1, "actual": actual, "forecast": round(forecast, 1), "error_pct": round(pct_error, 1)})
        fl.info(f"Week {i+1}", data=forecasts[-1])

    step("Compute MAPE")
    mape = sum(f["error_pct"] for f in forecasts) / len(forecasts) if forecasts else 0
    fl.info("Mean Absolute Percentage Error", data={"mape": round(mape, 2)})

    step("Validate forecast quality")
    fl.info("Checking MAPE is finite")
    assert mape >= 0
    assert len(forecasts) > 0
    fl.info("Forecast accuracy analysis complete", data={"mape": round(mape, 2)})


def test_economic_order_quantity(log):
    """Calculate EOQ for top SKUs."""
    el = log.child("eoq")

    step("Define cost parameters")
    ordering_cost = 50.0  # cost per order
    holding_rate = 0.20   # 20% annual holding cost
    el.info("Cost parameters", data={"ordering_cost": ordering_cost, "holding_rate": holding_rate})

    step("Compute EOQ for top 10 SKUs by demand")
    sorted_skus = sorted(INVENTORY_RECORDS, key=lambda r: -r["daily_demand"])[:10]
    for r in sorted_skus:
        annual_demand = r["daily_demand"] * 365
        holding_cost = r["unit_cost"] * holding_rate
        eoq = math.sqrt(2 * annual_demand * ordering_cost / holding_cost) if holding_cost > 0 else 0
        orders_per_year = annual_demand / eoq if eoq > 0 else 0
        el.info(f"SKU {r['sku']}", data={
            "annual_demand": annual_demand,
            "unit_cost": r["unit_cost"],
            "eoq": round(eoq, 0),
            "orders_per_year": round(orders_per_year, 1),
        })

    step("Validate EOQ calculations")
    el.info("All EOQ values computed for top demand SKUs")
    assert all(r["daily_demand"] > 0 for r in sorted_skus)
    el.info("EOQ analysis complete")


# ---------------------------------------------------------------------------
# Flaky service / retry tests
# ---------------------------------------------------------------------------


def test_inventory_sync_to_erp(log, flaky_service):
    """Sync inventory counts to ERP system -- intermittent failure."""
    el = log.child("erp")

    step("Prepare inventory snapshot")
    snapshot = {"timestamp": "2026-04-02T10:00:00Z", "sku_count": len(INVENTORY_RECORDS)}
    el.info("Snapshot prepared", data=snapshot)

    step("Push to ERP")
    el.info("Connecting to ERP API", data={"endpoint": "https://erp.internal/api/inventory"})
    result = flaky_service("inventory_erp_sync")
    el.info("ERP sync result", data={"status": result})

    step("Validate sync")
    assert result.startswith("ok")
    el.info("ERP sync validated")


def test_barcode_scanner_connection(log, flaky_service):
    """Connect to barcode scanner service -- first attempt drops."""
    bl = log.child("scanner")

    step("Initialize scanner connection")
    bl.info("Discovering scanner devices", data={"protocol": "USB-HID", "timeout_ms": 5000})

    step("Handshake with scanner service")
    result = flaky_service("barcode_scanner_conn")
    bl.info("Scanner connection established", data={"status": result, "device": "Zebra DS9908"})

    step("Run scan test")
    bl.info("Scanning test barcode", data={"barcode": "0123456789012", "format": "EAN-13"})
    assert "ok" in result
    bl.info("Barcode scanner test passed")


# ---------------------------------------------------------------------------
# Failure tests
# ---------------------------------------------------------------------------


def test_zero_stockout_target(log):
    """Assert zero stockouts -- deliberately fails because some items are below reorder."""
    sl = log.child("stockout")

    step("Count stockout-risk items")
    at_risk = [r for r in INVENTORY_RECORDS if r["on_hand"] < r["reorder_point"]]
    sl.info("Stockout risk scan", data={"at_risk": len(at_risk), "total": len(INVENTORY_RECORDS)})
    for r in at_risk[:3]:
        sl.warning(f"At risk: {r['sku']}", data={"on_hand": r["on_hand"], "reorder_point": r["reorder_point"]})

    step("Assert zero stockouts")
    assert len(at_risk) == 0, f"{len(at_risk)} SKUs below reorder point"


def test_all_warehouses_above_minimum(log):
    """Check all warehouses have at least 500 total units -- deliberately fails."""
    wl = log.child("minimum")

    step("Compute units per warehouse")
    wh_units = {}
    for r in INVENTORY_RECORDS:
        wh_units.setdefault(r["warehouse"], 0)
        wh_units[r["warehouse"]] += r["on_hand"]

    step("Check minimum threshold")
    minimum = 5000
    failures = []
    for wh, units in wh_units.items():
        status = "OK" if units >= minimum else "BELOW MINIMUM"
        wl.info(f"Warehouse {wh}", data={"units": units, "minimum": minimum, "status": status})
        if units < minimum:
            failures.append(wh)

    step("Assert all above minimum")
    assert len(failures) == 0, f"Warehouses below {minimum} units: {failures}"


# ---------------------------------------------------------------------------
# Skip tests
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="RFID tracking hardware not available in CI")
def test_rfid_tag_reconciliation(log):
    """Reconcile RFID tag scans with database records."""
    log.info("Skipped -- requires RFID reader hardware")


@pytest.mark.skip(reason="Drone inventory count pilot program not started")
def test_drone_inventory_count(log):
    """Validate drone-based inventory counting accuracy."""
    log.info("Skipped -- drone program pending")
