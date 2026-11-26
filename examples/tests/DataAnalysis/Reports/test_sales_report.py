"""Sales report generation tests -- ETL pipelines, aggregation, and revenue analysis."""

from __future__ import annotations

import logging
import random
import time

import pytest

from stepdoc import step

log = logging.getLogger("sales_report")


REGIONS = ["North America", "Europe", "Asia Pacific", "Latin America", "Middle East"]
PRODUCTS = ["Widget Pro", "Widget Lite", "Widget Enterprise", "Widget Starter"]
QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

SALES_RECORDS = [
    {"id": f"TXN-{i:04d}", "region": REGIONS[i % len(REGIONS)], "product": PRODUCTS[i % len(PRODUCTS)],
     "quarter": QUARTERS[i % 4], "units": 100 + i * 17, "unit_price": 49.99 + (i % 5) * 10,
     "discount_pct": round(random.Random(i).uniform(0, 15), 2), "channel": ["online", "retail", "partner"][i % 3],
     "sales_rep": f"rep_{i % 8:02d}", "customer_tier": ["bronze", "silver", "gold", "platinum"][i % 4]}
    for i in range(120)
]


# ---------------------------------------------------------------------------
# Basic aggregation tests
# ---------------------------------------------------------------------------


def test_total_revenue_calculation():
    """Compute total revenue across all transactions."""
    pipe = log.getChild("pipeline")

    with step("Initialize revenue pipeline"):
        pipe.info("Loading sales dataset", extra={"record_count": len(SALES_RECORDS)})
        pipe.debug("Memory allocated for aggregation buffer", extra={"buffer_kb": 512})
        with step("Validate input schema"):
            pipe.info("Schema check passed", extra={"required_fields": ["units", "unit_price", "discount_pct"]})

    with step("Compute gross revenue per transaction"):
        calc = pipe.getChild("calc")
        total_gross = 0.0
        total_net = 0.0
        for i, rec in enumerate(SALES_RECORDS):
            gross = rec["units"] * rec["unit_price"]
            net = gross * (1 - rec["discount_pct"] / 100)
            total_gross += gross
            total_net += net
            if i < 5 or i == len(SALES_RECORDS) - 1:
                calc.debug(f"Transaction {rec['id']}", extra={"gross": round(gross, 2), "net": round(net, 2)})
        calc.info("Gross revenue computed", extra={"total_gross": round(total_gross, 2)})
        calc.info("Net revenue computed", extra={"total_net": round(total_net, 2), "avg_discount_impact": round(total_gross - total_net, 2)})

    with step("Validate revenue totals"):
        with step("Check gross > 0"):
            pipe.info("Asserting positive gross revenue")
            assert total_gross > 0
        with step("Check net <= gross"):
            pipe.info("Asserting net <= gross", extra={"delta": round(total_gross - total_net, 2)})
            assert total_net <= total_gross
        with step("Check net > 0"):
            assert total_net > 0
            pipe.info("Revenue pipeline complete", extra={"total_gross": round(total_gross, 2), "total_net": round(total_net, 2)})


@pytest.mark.parametrize("region", REGIONS, ids=[r.lower().replace(" ", "-") for r in REGIONS])
def test_regional_revenue_breakdown(region):
    """Break down revenue by region and validate regional contribution."""
    rl = log.getChild("regional")

    with step(f"Filter transactions for {region}"):
        regional = [r for r in SALES_RECORDS if r["region"] == region]
        rl.info("Filtered dataset", extra={"region": region, "count": len(regional)})
        rl.debug("Sample transaction", extra={"data": regional[0] if regional else {}})

    with step("Aggregate regional metrics"):
        with step("Sum units sold"):
            total_units = sum(r["units"] for r in regional)
            rl.info("Total units", extra={"units": total_units})
        with step("Sum gross revenue"):
            total_rev = sum(r["units"] * r["unit_price"] for r in regional)
            rl.info("Gross revenue", extra={"revenue": round(total_rev, 2)})
        with step("Average discount"):
            avg_disc = sum(r["discount_pct"] for r in regional) / len(regional) if regional else 0
            rl.info("Average discount rate", extra={"avg_discount_pct": round(avg_disc, 2)})

    with step("Compute channel mix"):
        channels = {}
        for r in regional:
            channels[r["channel"]] = channels.get(r["channel"], 0) + r["units"] * r["unit_price"]
        channel_rows = [
            {"Channel": ch, "Revenue": round(rev, 2),
             "% of Regional": round(rev / total_rev * 100, 1) if total_rev else 0}
            for ch, rev in channels.items()
        ]
        rl.info(f"channel_mix_{region.lower().replace(' ', '_')}", extra={"report_table": channel_rows})

    with step("Validate regional data"):
        rl.info("Checking region has transactions")
        assert len(regional) > 0, f"No transactions for {region}"
        rl.info("Checking revenue is positive")
        assert total_rev > 0
        rl.info("Regional analysis complete", extra={"region": region, "transactions": len(regional), "revenue": round(total_rev, 2)})


@pytest.mark.parametrize("product", PRODUCTS, ids=[p.lower().replace(" ", "-") for p in PRODUCTS])
def test_product_performance_summary(product):
    """Analyze product performance across all regions."""
    pl = log.getChild("product")

    with step(f"Extract data for {product}"):
        product_data = [r for r in SALES_RECORDS if r["product"] == product]
        pl.info("Product filter applied", extra={"product": product, "records": len(product_data)})

    with step("Compute quarterly breakdown"):
        quarterly = {q: {"units": 0, "revenue": 0.0} for q in QUARTERS}
        for r in product_data:
            gross = r["units"] * r["unit_price"]
            quarterly[r["quarter"]]["units"] += r["units"]
            quarterly[r["quarter"]]["revenue"] += gross
        for q, vals in quarterly.items():
            pl.info(f"{q} performance", extra={"units": vals["units"], "revenue": round(vals["revenue"], 2)})

    with step("Calculate growth trajectory"):
        with step("Quarter-over-quarter growth"):
            q_revs = [quarterly[q]["revenue"] for q in QUARTERS]
            for i in range(1, len(q_revs)):
                growth = ((q_revs[i] - q_revs[i - 1]) / q_revs[i - 1] * 100) if q_revs[i - 1] else 0
                pl.info(f"{QUARTERS[i-1]} -> {QUARTERS[i]}", extra={"growth_pct": round(growth, 1)})

    with step("Validate product metrics"):
        total_rev = sum(v["revenue"] for v in quarterly.values())
        pl.info("Total product revenue", extra={"product": product, "revenue": round(total_rev, 2)})
        assert total_rev > 0
        assert len(product_data) > 0
        pl.info("Product analysis done")


def test_quarter_over_quarter_trend():
    """Validate overall quarterly trend is upward."""
    tl = log.getChild("trend")

    with step("Aggregate revenue by quarter"):
        quarterly_rev = {q: 0.0 for q in QUARTERS}
        for r in SALES_RECORDS:
            quarterly_rev[r["quarter"]] += r["units"] * r["unit_price"]
        for q, rev in quarterly_rev.items():
            tl.info(f"{q} total revenue", extra={"revenue": round(rev, 2)})

    with step("Compute sequential growth rates"):
        revs = [quarterly_rev[q] for q in QUARTERS]
        growth_rates = []
        for i in range(1, len(revs)):
            rate = (revs[i] - revs[i - 1]) / revs[i - 1] * 100 if revs[i - 1] else 0
            growth_rates.append(rate)
            tl.info(f"Growth {QUARTERS[i-1]}->{QUARTERS[i]}", extra={"pct": round(rate, 1)})

    with step("Validate trend direction"):
        tl.info("Growth rates computed", extra={"rates": [round(r, 1) for r in growth_rates]})
        tl.info("Checking for overall positive trajectory")
        assert len(growth_rates) == 3
        tl.info("Quarterly trend validation complete")


def test_discount_impact_analysis():
    """Measure the impact of discounts on net revenue."""
    dl = log.getChild("discount")

    with step("Segment transactions by discount tier"):
        tiers = {"none": (0, 0), "low": (0.01, 5), "medium": (5.01, 10), "high": (10.01, 100)}
        tier_data = {t: {"count": 0, "gross": 0.0, "net": 0.0} for t in tiers}

        for r in SALES_RECORDS:
            gross = r["units"] * r["unit_price"]
            net = gross * (1 - r["discount_pct"] / 100)
            for tier_name, (lo, hi) in tiers.items():
                if lo <= r["discount_pct"] <= hi:
                    tier_data[tier_name]["count"] += 1
                    tier_data[tier_name]["gross"] += gross
                    tier_data[tier_name]["net"] += net
                    break

    with step("Report per-tier metrics"):
        for tier_name, vals in tier_data.items():
            dl.info(f"Discount tier: {tier_name}", extra={
                "transactions": vals["count"],
                "gross": round(vals["gross"], 2),
                "net": round(vals["net"], 2),
                "leakage": round(vals["gross"] - vals["net"], 2),
            })

    with step("Compute aggregate leakage"):
        total_leakage = sum(v["gross"] - v["net"] for v in tier_data.values())
        total_gross = sum(v["gross"] for v in tier_data.values())
        dl.info("Total discount leakage", extra={
            "leakage": round(total_leakage, 2),
            "pct_of_gross": round(total_leakage / total_gross * 100, 2) if total_gross else 0,
        })

    with step("Validate discount bounds"):
        with step("All discounts non-negative"):
            assert all(r["discount_pct"] >= 0 for r in SALES_RECORDS)
        with step("Leakage within tolerance"):
            dl.info("Discount impact analysis complete")
            assert total_leakage >= 0


def test_channel_distribution():
    """Verify revenue distribution across sales channels."""
    cl = log.getChild("channel")

    with step("Aggregate revenue by channel"):
        channels = {}
        for r in SALES_RECORDS:
            rev = r["units"] * r["unit_price"]
            channels.setdefault(r["channel"], {"revenue": 0.0, "count": 0, "units": 0})
            channels[r["channel"]]["revenue"] += rev
            channels[r["channel"]]["count"] += 1
            channels[r["channel"]]["units"] += r["units"]

    with step("Compute channel share"):
        total = sum(v["revenue"] for v in channels.values())
        for ch, vals in channels.items():
            share = vals["revenue"] / total * 100 if total else 0
            cl.info(f"Channel: {ch}", extra={
                "revenue": round(vals["revenue"], 2),
                "transactions": vals["count"],
                "units": vals["units"],
                "share_pct": round(share, 1),
            })

    with step("Validate channel coverage"):
        cl.info("Expected channels present", extra={"channels": list(channels.keys())})
        assert "online" in channels
        assert "retail" in channels
        assert total > 0
        cl.info("Channel analysis complete", extra={"total_revenue": round(total, 2)})


def test_sales_rep_leaderboard():
    """Rank sales reps by revenue generated."""
    rl = log.getChild("leaderboard")

    with step("Aggregate rep performance"):
        reps = {}
        for r in SALES_RECORDS:
            rev = r["units"] * r["unit_price"]
            reps.setdefault(r["sales_rep"], {"revenue": 0.0, "deals": 0, "avg_deal": 0.0})
            reps[r["sales_rep"]]["revenue"] += rev
            reps[r["sales_rep"]]["deals"] += 1

    with step("Compute average deal size"):
        for rep, vals in reps.items():
            vals["avg_deal"] = vals["revenue"] / vals["deals"] if vals["deals"] else 0

    with step("Rank and report"):
        ranked = sorted(reps.items(), key=lambda x: -x[1]["revenue"])
        rl.info("sales_rep_leaderboard", extra={"report_table": [{"Rank": rank, "Rep": rep,
              "Revenue": round(vals["revenue"], 2),
              "Deals": vals["deals"],
              "Avg Deal": round(vals["avg_deal"], 2)}
             for rank, (rep, vals) in enumerate(ranked, 1)]})

    with step("Validate leaderboard"):
        with step("At least 3 reps"):
            assert len(ranked) >= 3
        with step("Top rep has highest revenue"):
            assert ranked[0][1]["revenue"] >= ranked[-1][1]["revenue"]
            rl.info("Leaderboard generated", extra={"total_reps": len(ranked)})


def test_customer_tier_revenue():
    """Revenue split by customer tier (bronze/silver/gold/platinum)."""
    tl = log.getChild("tiers")

    with step("Group transactions by customer tier"):
        tier_rev = {}
        for r in SALES_RECORDS:
            rev = r["units"] * r["unit_price"]
            tier_rev.setdefault(r["customer_tier"], {"revenue": 0.0, "count": 0})
            tier_rev[r["customer_tier"]]["revenue"] += rev
            tier_rev[r["customer_tier"]]["count"] += 1

    with step("Report tier breakdown"):
        total = sum(v["revenue"] for v in tier_rev.values())
        tier_order = ["platinum", "gold", "silver", "bronze"]
        tl.info("customer_tier_breakdown", extra={"report_table": [{"Tier": tier.capitalize(),
              "Revenue": round(tier_rev[tier]["revenue"], 2),
              "Transactions": tier_rev[tier]["count"],
              "Share (%)": round(tier_rev[tier]["revenue"] / total * 100, 1) if total else 0}
             for tier in tier_order if tier in tier_rev]})

    with step("Validate all tiers present"):
        for expected in ["bronze", "silver", "gold", "platinum"]:
            tl.info(f"Checking tier: {expected}")
            assert expected in tier_rev, f"Missing tier: {expected}"
        tl.info("Tier analysis complete", extra={"total_revenue": round(total, 2)})


def test_yoy_growth_projection():
    """Project year-over-year growth from quarterly data."""
    gl = log.getChild("growth")

    with step("Compute current year totals"):
        current_total = sum(r["units"] * r["unit_price"] for r in SALES_RECORDS)
        gl.info("Current year revenue", extra={"revenue": round(current_total, 2)})

    with step("Simulate prior year baseline"):
        prior_total = current_total * 0.82
        gl.info("Prior year revenue (simulated)", extra={"revenue": round(prior_total, 2)})

    with step("Calculate YoY growth"):
        yoy = (current_total - prior_total) / prior_total * 100
        gl.info("Year-over-year growth", extra={"yoy_pct": round(yoy, 2)})
        with step("Project next year"):
            projected = current_total * (1 + yoy / 100)
            gl.info("Next year projection", extra={"projected_revenue": round(projected, 2)})

    with step("Validate growth rate"):
        gl.info("Checking growth is positive")
        assert yoy > 0
        gl.info("Growth projection complete", extra={"yoy_pct": round(yoy, 2), "projection": round(projected, 2)})


@pytest.mark.parametrize("channel", ["online", "retail", "partner"])
def test_channel_avg_order_value(channel):
    """Average order value per channel."""
    cl = log.getChild("aov")

    with step(f"Filter transactions for channel: {channel}"):
        filtered = [r for r in SALES_RECORDS if r["channel"] == channel]
        cl.info("Filtered", extra={"channel": channel, "count": len(filtered)})

    with step("Compute average order value"):
        revenues = [r["units"] * r["unit_price"] for r in filtered]
        aov = sum(revenues) / len(revenues) if revenues else 0
        cl.info("AOV computed", extra={"aov": round(aov, 2), "min": round(min(revenues), 2), "max": round(max(revenues), 2)})

    with step("Compute standard deviation"):
        mean = aov
        variance = sum((x - mean) ** 2 for x in revenues) / len(revenues) if revenues else 0
        std = variance ** 0.5
        cl.info("Revenue distribution", extra={"mean": round(mean, 2), "std": round(std, 2)})

    with step("Validate AOV"):
        assert aov > 0
        assert len(filtered) > 0
        cl.info(f"Channel {channel} AOV analysis complete")


def test_top_region_product_combos():
    """Find highest-revenue region+product combinations."""
    cl = log.getChild("combos")

    with step("Build combination matrix"):
        combos = {}
        for r in SALES_RECORDS:
            key = f"{r['region']} / {r['product']}"
            rev = r["units"] * r["unit_price"]
            combos[key] = combos.get(key, 0) + rev

    with step("Rank combinations"):
        ranked = sorted(combos.items(), key=lambda x: -x[1])
        for i, (combo, rev) in enumerate(ranked[:10]):
            cl.info(f"#{i+1} {combo}", extra={"revenue": round(rev, 2)})

    with step("Validate top combination"):
        cl.info("Top combination identified", extra={"combo": ranked[0][0], "revenue": round(ranked[0][1], 2)})
        assert ranked[0][1] > 0
        assert len(ranked) >= 5
        cl.info("Combination analysis done", extra={"total_combos": len(ranked)})


# ---------------------------------------------------------------------------
# Flaky service / retry tests
# ---------------------------------------------------------------------------


def test_sales_data_warehouse_sync(flaky_service):
    """Sync sales data to warehouse -- first attempt fails."""
    wl = log.getChild("warehouse")

    with step("Prepare batch for warehouse sync"):
        batch_size = len(SALES_RECORDS)
        wl.info("Batch prepared", extra={"records": batch_size, "destination": "warehouse.sales_facts"})

    with step("Upload batch to warehouse"):
        wl.info("Initiating connection to data warehouse")
        result = flaky_service("sales_warehouse_sync")
        wl.info("Warehouse sync completed", extra={"status": result, "records_synced": batch_size})

    with step("Verify sync"):
        wl.info("Querying warehouse row count")
        assert result.startswith("ok")
        wl.info("Warehouse sync verified")


def test_sales_report_email_delivery(flaky_service):
    """Send sales report via email -- first attempt times out."""
    el = log.getChild("email")

    with step("Generate report PDF"):
        el.info("Rendering sales summary to PDF", extra={"pages": 4, "format": "A4"})
        el.debug("PDF buffer allocated", extra={"size_kb": 1240})

    with step("Send email with attachment"):
        el.info("Connecting to SMTP relay", extra={"host": "smtp.internal", "port": 587})
        result = flaky_service("sales_email_delivery")
        el.info("Email sent", extra={"status": result, "recipients": ["cfo@example.com", "vp-sales@example.com"]})

    with step("Confirm delivery"):
        assert result == "ok:sales_email_delivery"
        el.info("Email delivery confirmed")


def test_crm_revenue_push(flaky_service):
    """Push revenue summary to CRM -- intermittent API failure."""
    cl = log.getChild("crm")

    with step("Prepare CRM payload"):
        payload = {"total_revenue": 1_250_000, "quarter": "Q4", "region_count": len(REGIONS)}
        cl.info("CRM payload assembled", extra={"data": payload})

    with step("Push to CRM API"):
        cl.info("POST /api/v2/revenue-summary")
        result = flaky_service("crm_revenue_push")
        cl.info("CRM response", extra={"status": result, "http_code": 200})

    with step("Validate CRM acknowledgment"):
        assert "ok" in result
        cl.info("CRM push confirmed")


# ---------------------------------------------------------------------------
# Failure tests
# ---------------------------------------------------------------------------


def test_revenue_target_achieved():
    """Check if revenue target was met -- deliberately fails."""
    tl = log.getChild("target")

    with step("Load revenue target"):
        target = 50_000_000
        tl.info("Annual target loaded", extra={"target": target, "currency": "USD"})

    with step("Compute actual revenue"):
        actual = sum(r["units"] * r["unit_price"] for r in SALES_RECORDS)
        tl.info("Actual revenue computed", extra={"actual": round(actual, 2)})
        tl.warning("Revenue below target", extra={"shortfall": round(target - actual, 2)})

    with step("Assert target met"):
        assert actual >= target, f"Revenue ${actual:,.2f} missed target ${target:,.2f}"


def test_all_regions_profitable():
    """Check all regions are profitable after discounts -- deliberately fails."""
    pl = log.getChild("profitability")

    with step("Compute net revenue by region"):
        region_net = {}
        cost_per_unit = 45.00
        for r in SALES_RECORDS:
            net = r["units"] * r["unit_price"] * (1 - r["discount_pct"] / 100) - r["units"] * cost_per_unit
            region_net.setdefault(r["region"], 0.0)
            region_net[r["region"]] += net

    with step("Report profitability"):
        unprofitable = []
        for region, profit in region_net.items():
            status = "profitable" if profit > 0 else "LOSS"
            pl.info(f"Region: {region}", extra={"net_profit": round(profit, 2), "status": status})
            if profit <= 0:
                unprofitable.append(region)

    with step("Validate profitability"):
        pl.info("Profitability check", extra={"unprofitable_regions": unprofitable})
        # Force a failure
        assert False, f"Profitability audit flagged regions: revenue model needs review"


# ---------------------------------------------------------------------------
# Skip tests
# ---------------------------------------------------------------------------


@pytest.mark.skip(reason="Forecasting model v2 not deployed yet")
def test_ml_forecast_accuracy():
    """Validate ML forecast accuracy against actuals."""
    log.info("This test is skipped pending model deployment")


@pytest.mark.skip(reason="Real-time pipeline not available in test environment")
def test_realtime_revenue_stream():
    """Validate real-time revenue stream ingestion."""
    log.info("Skipped -- requires Kafka cluster")


def test_seasonal_decomposition():
    """Decompose sales into trend + seasonal + residual components."""
    sl = log.getChild("seasonal")

    with step("Prepare time series"):
        monthly = [sum(r["units"] * r["unit_price"] for r in SALES_RECORDS if r["quarter"] == q) for q in QUARTERS]
        sl.info("Quarterly revenue series", extra={"values": [round(v, 2) for v in monthly]})

    with step("Compute moving average (trend)"):
        trend = []
        for i in range(len(monthly)):
            window = monthly[max(0, i - 1):i + 2]
            trend.append(sum(window) / len(window))
        sl.info("Trend component", extra={"values": [round(v, 2) for v in trend]})

    with step("Extract seasonal component"):
        seasonal = [monthly[i] - trend[i] for i in range(len(monthly))]
        sl.info("Seasonal component", extra={"values": [round(v, 2) for v in seasonal]})

    with step("Compute residual"):
        residual = [monthly[i] - trend[i] - seasonal[i] for i in range(len(monthly))]
        sl.info("Residual component", extra={"values": [round(v, 2) for v in residual]})

    with step("Validate decomposition"):
        for i in range(len(monthly)):
            reconstructed = trend[i] + seasonal[i] + residual[i]
            sl.debug(f"Q{i+1} reconstruction check", extra={"original": round(monthly[i], 2), "reconstructed": round(reconstructed, 2)})
            assert abs(monthly[i] - reconstructed) < 0.01
        sl.info("Decomposition validated")


def test_outlier_detection_in_transactions():
    """Detect outlier transactions using IQR method."""
    ol = log.getChild("outliers")

    with step("Compute transaction values"):
        values = sorted([r["units"] * r["unit_price"] for r in SALES_RECORDS])
        ol.info("Transaction values computed", extra={"count": len(values), "min": round(values[0], 2), "max": round(values[-1], 2)})

    with step("Calculate IQR bounds"):
        n = len(values)
        q1 = values[n // 4]
        q3 = values[3 * n // 4]
        iqr = q3 - q1
        lower = q1 - 1.5 * iqr
        upper = q3 + 1.5 * iqr
        ol.info("IQR statistics", extra={"Q1": round(q1, 2), "Q3": round(q3, 2), "IQR": round(iqr, 2), "lower_fence": round(lower, 2), "upper_fence": round(upper, 2)})

    with step("Identify outliers"):
        outliers = [v for v in values if v < lower or v > upper]
        ol.info("Outliers found", extra={"count": len(outliers), "values": [round(v, 2) for v in outliers[:5]]})

    with step("Validate outlier detection"):
        ol.info("Checking bounds are reasonable")
        assert lower < upper
        assert q1 < q3
        ol.info("Outlier detection complete", extra={"total_transactions": len(values), "outlier_count": len(outliers)})


def test_cohort_analysis_by_quarter():
    """Analyze customer tier cohorts across quarters."""
    cl = log.getChild("cohort")

    with step("Build cohort matrix"):
        matrix = {}
        for r in SALES_RECORDS:
            key = (r["customer_tier"], r["quarter"])
            matrix.setdefault(key, {"revenue": 0.0, "count": 0})
            matrix[key]["revenue"] += r["units"] * r["unit_price"]
            matrix[key]["count"] += 1

    with step("Report cohort metrics"):
        for tier in ["bronze", "silver", "gold", "platinum"]:
            tier_log = cl.getChild(tier)
            for q in QUARTERS:
                data = matrix.get((tier, q), {"revenue": 0, "count": 0})
                tier_log.info(f"{q}", extra={"revenue": round(data["revenue"], 2), "transactions": data["count"]})

    with step("Validate cohort coverage"):
        tiers_seen = set(k[0] for k in matrix.keys())
        cl.info("Tiers observed", extra={"tiers": sorted(tiers_seen)})
        assert len(tiers_seen) == 4
        cl.info("Cohort analysis complete", extra={"cells": len(matrix)})
