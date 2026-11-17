"""Deterministic synthetic data generator and invariant evaluator for meridian_q3_sgd."""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import date, timedelta
import json
from pathlib import Path
import random
import sys
from typing import Any

DEFAULT_SEED = 20261126
Q3_START = date(2026, 7, 1)
Q3_DAYS = 92  # 2026-07-01 .. 2026-09-30 inclusive
SHADOW_TABLE_COUNT = 190
HUBS_SG = ("SG-JURONG-01", "SG-CHANGI-02", "SG-TUAS-03", "SG-WOODLANDS-04")
CARRIERS = ("ArcticHaul", "SiamFrost Logistics", "StraitsTemp Cargo")


def _to_cents(amount_sgd: float) -> int:
    return int(round(amount_sgd * 100))


def _from_cents(cents: int) -> float:
    return round(cents / 100.0, 2)


def _partition_cents(
    rng: random.Random,
    total_cents: int,
    count: int,
    min_cents: int,
    max_cents: int,
) -> list[int]:
    """Deterministically splits `total_cents` across `count` bounded integers."""
    if count <= 0:
        raise ValueError("count must be positive")
    if total_cents < count * min_cents or total_cents > count * max_cents:
        raise ValueError(
            f"Cannot partition {total_cents} across {count} items within [{min_cents}, {max_cents}]"
        )
    parts = [min_cents] * count
    remaining = total_cents - count * min_cents
    if remaining == 0:
        return parts

    weights = [rng.uniform(0.5, 1.5) for _ in range(count)]
    weight_sum = sum(weights)
    for idx in range(count):
        cap = max_cents - parts[idx]
        add = min(cap, int(remaining * (weights[idx] / weight_sum)))
        parts[idx] += add

    leftover = total_cents - sum(parts)
    indices = list(range(count))
    rng.shuffle(indices)
    while leftover > 0:
        progressed = False
        for idx in indices:
            if leftover == 0:
                break
            if parts[idx] < max_cents:
                parts[idx] += 1
                leftover -= 1
                progressed = True
        if not progressed:
            raise RuntimeError("Failed to allocate remaining cents within bounds")
    return parts


def _random_q3_date(rng: random.Random) -> str:
    return (Q3_START + timedelta(days=rng.randrange(Q3_DAYS))).isoformat()


def _make_customers(rng: random.Random) -> tuple[list[dict[str, Any]], dict[str, list[str]]]:
    """Generates SG and regional SEA customer cohorts with exact glossary properties."""
    customers: list[dict[str, Any]] = []
    pools: dict[str, list[str]] = defaultdict(list)
    seq = 1

    def add_group(
        pool_key: str,
        count: int,
        country: str,
        tier_code: str,
        segment_label: str,
        spend_range: tuple[float, float],
        return_range: tuple[float, float],
        channel_pref: str,
    ) -> None:
        nonlocal seq
        for _ in range(count):
            cid = f"CUST-{country}-{seq:05d}"
            seq += 1
            customers.append(
                {
                    "customer_id": cid,
                    "country_code": country,
                    "tier_code": tier_code,
                    "segment_label": segment_label,
                    "trailing_12m_spend_sgd": round(rng.uniform(*spend_range), 2),
                    "return_rate": round(rng.uniform(*return_range), 4),
                    "channel_pref": channel_pref,
                }
            )
            pools[pool_key].append(cid)

    # SG PRM_HV customers: all satisfy trailing_12m_spend_sgd >= 5000.00 AND return_rate < 0.08
    add_group("sg_hv_b2b", 60, "SG", "PRM_HV", "Enterprise_Corporate", (14000.0, 48000.0), (0.005, 0.045), "B2B Corporate Portal")
    add_group("sg_hv_direct", 40, "SG", "PRM_HV", "Enterprise_Direct", (10000.0, 32000.0), (0.008, 0.055), "Direct Account Desk")
    add_group("sg_hv_web", 35, "SG", "PRM_HV", "Premier_Loyalty", (6200.0, 19500.0), (0.010, 0.068), "Web Storefront")
    add_group("sg_hv_mobile", 25, "SG", "PRM_HV", "Premier_Loyalty", (5200.0, 14500.0), (0.012, 0.072), "Mobile App")

    # SG Premier_Promo_Trial distractors: fails PRM_HV thresholds (< 5000 spend, >= 0.08 return rate)
    add_group("sg_trial_mobile", 50, "SG", "PRM_TRIAL", "Premier_Promo_Trial", (450.0, 2600.0), (0.095, 0.230), "Mobile App")
    add_group("sg_trial_web", 80, "SG", "PRM_TRIAL", "Premier_Promo_Trial", (380.0, 2200.0), (0.100, 0.250), "Web Storefront")

    # SG Standard Retail cohorts (used for SAME_DAY, STANDARD/NEXT_DAY, and cancelled/returned orders)
    add_group("sg_std_sameday", 200, "SG", "STD_RET", "Standard_Retail", (800.0, 4400.0), (0.020, 0.095), "Web Storefront")
    add_group("sg_std_general", 300, "SG", "STD_RET", "Standard_Retail", (320.0, 4100.0), (0.025, 0.140), "Mobile App")

    # Regional SEA markets (MY, TH, ID) to verify country_code='SG' filtering is essential
    for country in ("MY", "TH", "ID"):
        add_group(f"{country.lower()}_hv", 15, country, "PRM_HV", "Enterprise_Corporate", (7500.0, 28000.0), (0.010, 0.060), "B2B Corporate Portal")
        add_group(f"{country.lower()}_std", 35, country, "STD_RET", "Standard_Retail", (400.0, 3800.0), (0.030, 0.150), "Web Storefront")

    return customers, pools


def _make_supply_chain() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    batches = [
        {
            "batch_id": "BATCH-STD-101",
            "supplier_tier": "TIER_1",
            "vendor_name": "SiamFrost Logistics",
            "temp_peak_celsius": 1.4,
            "excursion_duration_min": 0,
            "shipment_invoice_sgd": 42000.00,
            "batch_status": "CLEARED",
        },
        {
            "batch_id": "BATCH-STD-102",
            "supplier_tier": "TIER_1",
            "vendor_name": "StraitsTemp Cargo",
            "temp_peak_celsius": 1.8,
            "excursion_duration_min": 10,
            "shipment_invoice_sgd": 38500.00,
            "batch_status": "CLEARED",
        },
        {
            "batch_id": "BATCH-STD-203",
            "supplier_tier": "TIER_1",
            "vendor_name": "ArcticHaul",
            "temp_peak_celsius": 1.6,
            "excursion_duration_min": 0,
            "shipment_invoice_sgd": 51000.00,
            "batch_status": "CLEARED",
        },
        {
            "batch_id": "#LN-409",
            "supplier_tier": "TIER_2",
            "vendor_name": "ArcticHaul",
            "temp_peak_celsius": 3.9,
            "excursion_duration_min": 72,
            "shipment_invoice_sgd": 19380.00,
            "batch_status": "DELAYED_EXCURSION",
        },
    ]

    allocations = [
        {
            "lot_id": "LOT-AMB-101",
            "batch_id": "BATCH-STD-101",
            "sku_id": "SKU-AMB-101",
            "temp_sensitive_class": "AMBIENT_STD",
        },
        {
            "lot_id": "LOT-CHL-102",
            "batch_id": "BATCH-STD-102",
            "sku_id": "SKU-CHL-204",
            "temp_sensitive_class": "CHILLED_FOOD",
        },
        {
            "lot_id": "LOT-BIO-203",
            "batch_id": "BATCH-STD-203",
            "sku_id": "SKU-BIO-310",
            "temp_sensitive_class": "BIOLOGIC_CHILLED",
        },
        # Three distinct warehouse lots all belonging to Tier-2 batch #LN-409:
        # Only LOT-LN409-01 embeds '409' in its lot string (8 orders -> SGD 4,120.00 blind trap),
        # while LOT-SG-8841 and LOT-SG-8842 require full 4-hop sku_lot_allocations bridge traversal.
        {
            "lot_id": "LOT-LN409-01",
            "batch_id": "#LN-409",
            "sku_id": "SKU-BIO-409",
            "temp_sensitive_class": "BIOLOGIC_CHILLED",
        },
        {
            "lot_id": "LOT-SG-8841",
            "batch_id": "#LN-409",
            "sku_id": "SKU-BIO-411",
            "temp_sensitive_class": "BIOLOGIC_CHILLED",
        },
        {
            "lot_id": "LOT-SG-8842",
            "batch_id": "#LN-409",
            "sku_id": "SKU-BIO-412",
            "temp_sensitive_class": "BIOLOGIC_CHILLED",
        },
        {
            "lot_id": "LOT-MY-8843",
            "batch_id": "#LN-409",
            "sku_id": "SKU-BIO-415",
            "temp_sensitive_class": "BIOLOGIC_CHILLED",
        },
    ]
    return batches, allocations


def generate_dataset(seed: int = DEFAULT_SEED) -> dict[str, list[dict[str, Any]]]:
    """Deterministically generates all Meridian Commerce Q3 tables matching SPEC.md §3."""
    rng = random.Random(seed)
    customers, pools = _make_customers(rng)
    batches, allocations = _make_supply_chain()

    orders: list[dict[str, Any]] = []
    order_lines: list[dict[str, Any]] = []
    parcel_legs: list[dict[str, Any]] = []

    order_seq = 1
    leg_seq_id = 1

    def append_order(
        *,
        customer_id: str,
        country_code: str,
        sales_channel: str,
        fulfillment_tier: str,
        order_status: str,
        gross_item_cents: int,
        gst_cents: int,
        gross_total_cents: int,
        net_cents: int,
        fulfillment_fee_cents: int,
        line_count: int,
        cogs_cents_total: int,
        leg_costs_cents: list[int],
        primary_lot_id: str,
        secondary_lot_id: str = "LOT-CHL-102",
    ) -> None:
        nonlocal order_seq, leg_seq_id
        oid = f"ORD-{country_code}-{order_seq:06d}"
        order_seq += 1
        odate = _random_q3_date(rng)

        orders.append(
            {
                "order_id": oid,
                "customer_id": customer_id,
                "country_code": country_code,
                "sales_channel": sales_channel,
                "fulfillment_tier": fulfillment_tier,
                "order_date": odate,
                "order_status": order_status,
                "gross_item_sgd": _from_cents(gross_item_cents),
                "gross_total_sgd": _from_cents(gross_total_cents),
                "gst_sgd": _from_cents(gst_cents),
                "fulfillment_fee_sgd": _from_cents(fulfillment_fee_cents),
                "net_realized_revenue_sgd": _from_cents(net_cents),
            }
        )

        # Split line totals so SUM(order_lines.net_line_revenue_sgd) == orders.net_realized_revenue_sgd
        if order_status == "COMPLETED":
            line_net_parts = _partition_cents(
                rng, net_cents, line_count, 0, net_cents
            )
            returned_total = gross_item_cents - net_cents
            line_ret_parts = (
                _partition_cents(rng, returned_total, line_count, 0, returned_total)
                if returned_total > 0
                else [0] * line_count
            )
        else:
            line_net_parts = [0] * line_count
            line_ret_parts = _partition_cents(
                rng, gross_item_cents, line_count, 0, gross_item_cents
            )
        line_gst_parts = _partition_cents(rng, gst_cents, line_count, 0, gst_cents)
        line_cogs_parts = _partition_cents(
            rng, cogs_cents_total, line_count, 0, cogs_cents_total
        )

        lot_sku = {
            "LOT-AMB-101": "SKU-AMB-101",
            "LOT-CHL-102": "SKU-CHL-204",
            "LOT-BIO-203": "SKU-BIO-310",
            "LOT-LN409-01": "SKU-BIO-409",
            "LOT-SG-8841": "SKU-BIO-411",
            "LOT-SG-8842": "SKU-BIO-412",
            "LOT-MY-8843": "SKU-BIO-415",
        }

        for idx in range(line_count):
            lot_id = primary_lot_id if idx == 0 else secondary_lot_id
            line_gross_cents = line_net_parts[idx] + line_ret_parts[idx]
            order_lines.append(
                {
                    "order_line_id": f"OL-{order_seq - 1:06d}-{idx + 1}",
                    "order_id": oid,
                    "sku_id": lot_sku[lot_id],
                    "lot_id": lot_id,
                    "qty": rng.randint(1, 4),
                    "gross_line_sgd": _from_cents(line_gross_cents),
                    "gst_line_sgd": _from_cents(line_gst_parts[idx]),
                    "returned_line_sgd": _from_cents(line_ret_parts[idx]),
                    "net_line_revenue_sgd": _from_cents(line_net_parts[idx]),
                    "cogs_line_sgd": _from_cents(line_cogs_parts[idx]),
                }
            )

        for leg_idx, leg_cost_c in enumerate(leg_costs_cents, start=1):
            parcel_legs.append(
                {
                    "leg_id": f"LEG-{leg_seq_id:07d}",
                    "order_id": oid,
                    "hub_code": HUBS_SG[(leg_idx + order_seq) % len(HUBS_SG)],
                    "carrier_vendor": CARRIERS[(leg_idx + order_seq) % len(CARRIERS)],
                    "leg_seq": leg_idx,
                    "leg_cost_sgd": _from_cents(leg_cost_c),
                    "temp_excursion_celsius": round(rng.uniform(0.8, 2.0), 2),
                    "excursion_minutes": rng.randint(0, 15),
                }
            )
            leg_seq_id += 1

    # -------------------------------------------------------------------------
    # Cohort 1: SG PRM_HV Completed (640 orders, SUM = SGD 317,203.20 -> AOV 495.63)
    # Also contains the exact 38 orders exposed to Tier-2 Batch #LN-409 (SGD 19,380.00)
    # -------------------------------------------------------------------------
    def emit_hv_channel(
        pool: list[str],
        channel: str,
        exposed_count: int,
        exposed_cents: int,
        exposed_lot: str,
        unexposed_count: int,
        unexposed_cents: int,
        unexposed_lot: str,
        min_c: int,
        max_c: int,
    ) -> None:
        exp_parts = _partition_cents(rng, exposed_cents, exposed_count, min_c, max_c)
        rest_parts = _partition_cents(rng, unexposed_cents, unexposed_count, min_c, max_c)
        all_specs = [(amt, exposed_lot) for amt in exp_parts] + [
            (amt, unexposed_lot) for amt in rest_parts
        ]
        for idx, (net_c, lot_id) in enumerate(all_specs):
            cid = pool[idx % len(pool)]
            gross_c = net_c
            gst_c = int(round(gross_c * 0.09))
            total_c = gross_c + gst_c
            cogs_c = int(round(net_c * 0.52))
            fee_c = int(round(net_c * 0.04))
            leg_c = int(round(net_c * 0.03))
            append_order(
                customer_id=cid,
                country_code="SG",
                sales_channel=channel,
                fulfillment_tier="NEXT_DAY",
                order_status="COMPLETED",
                gross_item_cents=gross_c,
                gst_cents=gst_c,
                gross_total_cents=total_c,
                net_cents=net_c,
                fulfillment_fee_cents=fee_c,
                line_count=2,
                cogs_cents_total=cogs_c,
                leg_costs_cents=[leg_c],
                primary_lot_id=lot_id,
            )

    # B2B Corporate Portal: 240 orders, SUM = 147,000.00 (AOV 612.50), 18 exposed = 10,940.00
    emit_hv_channel(
        pools["sg_hv_b2b"],
        "B2B Corporate Portal",
        exposed_count=18,
        exposed_cents=_to_cents(10940.00),
        exposed_lot="LOT-SG-8841",
        unexposed_count=222,
        unexposed_cents=_to_cents(136060.00),
        unexposed_lot="LOT-BIO-203",
        min_c=_to_cents(350.00),
        max_c=_to_cents(1100.00),
    )
    # Direct Account Desk: 160 orders, SUM = 76,800.00 (AOV 480.00), 12 exposed = 4,320.00
    emit_hv_channel(
        pools["sg_hv_direct"],
        "Direct Account Desk",
        exposed_count=12,
        exposed_cents=_to_cents(4320.00),
        exposed_lot="LOT-SG-8842",
        unexposed_count=148,
        unexposed_cents=_to_cents(72480.00),
        unexposed_lot="LOT-BIO-203",
        min_c=_to_cents(250.00),
        max_c=_to_cents(850.00),
    )
    # Web Storefront PRM_HV: 140 orders, SUM = 58,800.00 (AOV 420.00), 4 exposed = 2,060.00
    emit_hv_channel(
        pools["sg_hv_web"],
        "Web Storefront",
        exposed_count=4,
        exposed_cents=_to_cents(2060.00),
        exposed_lot="LOT-LN409-01",
        unexposed_count=136,
        unexposed_cents=_to_cents(56740.00),
        unexposed_lot="LOT-CHL-102",
        min_c=_to_cents(220.00),
        max_c=_to_cents(720.00),
    )
    # Mobile App PRM_HV: 100 orders, SUM = 34,603.20 (AOV 346.03), 4 exposed = 2,060.00
    emit_hv_channel(
        pools["sg_hv_mobile"],
        "Mobile App",
        exposed_count=4,
        exposed_cents=_to_cents(2060.00),
        exposed_lot="LOT-LN409-01",
        unexposed_count=96,
        unexposed_cents=_to_cents(32543.20),
        unexposed_lot="LOT-CHL-102",
        min_c=_to_cents(180.00),
        max_c=_to_cents(650.00),
    )

    # -------------------------------------------------------------------------
    # Cohort 2: SG PRM_TRIAL Completed (260 orders, SUM = SGD 46,216.80)
    # Blind R2 LIKE '%Premier%' catches Mobile App (100+100=200 -> 56,820.00 -> 284.10)
    # and Web Storefront (140+160=300 -> 82,800.00 -> 276.00)
    # -------------------------------------------------------------------------
    for idx, net_c in enumerate(
        _partition_cents(rng, _to_cents(22216.80), 100, _to_cents(110.00), _to_cents(360.00))
    ):
        gross_c = net_c
        gst_c = int(round(gross_c * 0.09))
        append_order(
            customer_id=pools["sg_trial_mobile"][idx % len(pools["sg_trial_mobile"])],
            country_code="SG",
            sales_channel="Mobile App",
            fulfillment_tier="STANDARD",
            order_status="COMPLETED",
            gross_item_cents=gross_c,
            gst_cents=gst_c,
            gross_total_cents=gross_c + gst_c,
            net_cents=net_c,
            fulfillment_fee_cents=int(round(net_c * 0.05)),
            line_count=2,
            cogs_cents_total=int(round(net_c * 0.56)),
            leg_costs_cents=[int(round(net_c * 0.04))],
            primary_lot_id="LOT-AMB-101",
        )

    for idx, net_c in enumerate(
        _partition_cents(rng, _to_cents(24000.00), 160, _to_cents(70.00), _to_cents(250.00))
    ):
        gross_c = net_c
        gst_c = int(round(gross_c * 0.09))
        append_order(
            customer_id=pools["sg_trial_web"][idx % len(pools["sg_trial_web"])],
            country_code="SG",
            sales_channel="Web Storefront",
            fulfillment_tier="STANDARD",
            order_status="COMPLETED",
            gross_item_cents=gross_c,
            gst_cents=gst_c,
            gross_total_cents=gross_c + gst_c,
            net_cents=net_c,
            fulfillment_fee_cents=int(round(net_c * 0.05)),
            line_count=2,
            cogs_cents_total=int(round(net_c * 0.58)),
            leg_costs_cents=[int(round(net_c * 0.04))],
            primary_lot_id="LOT-AMB-101",
        )

    # -------------------------------------------------------------------------
    # Cohort 3: SG SAME_DAY Completed (1,000 orders, SUM = SGD 412,000.00)
    # 2..4 parcel_legs per order (250x2, 500x3, 250x4) with symmetric group totals:
    # True margin = 131,016.00 (31.8%); Naive 3-way JOIN = 14.2% exact!
    # -------------------------------------------------------------------------
    sameday_groups = [
        (2, 250, _to_cents(103000.00), _to_cents(55000.00), _to_cents(9064.00), _to_cents(6182.00)),
        (3, 500, _to_cents(206000.00), _to_cents(110000.00), _to_cents(18128.00), _to_cents(12364.00)),
        (4, 250, _to_cents(103000.00), _to_cents(55000.00), _to_cents(9064.00), _to_cents(6182.00)),
    ]
    sd_customer_idx = 0
    for leg_count, n_orders, rev_c, cogs_c, fee_c, leg_total_c in sameday_groups:
        rev_parts = _partition_cents(rng, rev_c, n_orders, _to_cents(240.00), _to_cents(640.00))
        cogs_parts = _partition_cents(rng, cogs_c, n_orders, _to_cents(110.00), _to_cents(360.00))
        fee_parts = _partition_cents(rng, fee_c, n_orders, _to_cents(18.00), _to_cents(60.00))
        leg_parts = _partition_cents(rng, leg_total_c, n_orders, _to_cents(12.00), _to_cents(45.00))
        for i in range(n_orders):
            cid = pools["sg_std_sameday"][sd_customer_idx % len(pools["sg_std_sameday"])]
            sd_customer_idx += 1
            net_c = rev_parts[i]
            gross_c = net_c
            gst_c = int(round(gross_c * 0.09))
            per_leg = _partition_cents(rng, leg_parts[i], leg_count, _to_cents(2.00), leg_parts[i])
            append_order(
                customer_id=cid,
                country_code="SG",
                sales_channel="Web Storefront" if i % 2 == 0 else "Mobile App",
                fulfillment_tier="SAME_DAY",
                order_status="COMPLETED",
                gross_item_cents=gross_c,
                gst_cents=gst_c,
                gross_total_cents=gross_c + gst_c,
                net_cents=net_c,
                fulfillment_fee_cents=fee_parts[i],
                line_count=3,
                cogs_cents_total=cogs_parts[i],
                leg_costs_cents=per_leg,
                primary_lot_id="LOT-CHL-102",
                secondary_lot_id="LOT-AMB-101",
            )

    # -------------------------------------------------------------------------
    # Cohort 4: SG STD_RET STANDARD/NEXT_DAY Completed (1,500 orders, SUM = 537,030.00)
    # Total SG COMPLETED net_realized_revenue_sgd == 1,312,450.00
    # Also includes 3 STD_RET SG orders linked to LOT-SG-8841 to prove PRM_HV filter matters in R5
    # -------------------------------------------------------------------------
    cohort4_parts = _partition_cents(
        rng, _to_cents(537030.00), 1500, _to_cents(180.00), _to_cents(650.00)
    )
    for i, net_c in enumerate(cohort4_parts):
        cid = pools["sg_std_general"][i % len(pools["sg_std_general"])]
        # Include modest partial returns on first 100 orders so gross_item > net_realized
        partial_ret_c = _to_cents(15.00) if i < 100 else 0
        gross_c = net_c + partial_ret_c
        gst_c = int(round(gross_c * 0.09))
        lot_id = "LOT-SG-8841" if i < 3 else "LOT-AMB-101"
        append_order(
            customer_id=cid,
            country_code="SG",
            sales_channel="Mobile App" if i % 3 == 0 else "Web Storefront",
            fulfillment_tier="NEXT_DAY" if i % 2 == 0 else "STANDARD",
            order_status="COMPLETED",
            gross_item_cents=gross_c,
            gst_cents=gst_c,
            gross_total_cents=gross_c + gst_c,
            net_cents=net_c,
            fulfillment_fee_cents=int(round(net_c * 0.05)),
            line_count=2,
            cogs_cents_total=int(round(net_c * 0.55)),
            leg_costs_cents=[int(round(net_c * 0.04))],
            primary_lot_id=lot_id,
        )

    # -------------------------------------------------------------------------
    # Cohort 5: SG CANCELLED / RETURNED orders
    # Brings ALL SG orders SUM(gross_total_sgd) to EXACT 1,684,200.00
    # -------------------------------------------------------------------------
    sg_completed_gross_total_cents = sum(
        _to_cents(o["gross_total_sgd"]) for o in orders if o["country_code"] == "SG"
    )
    target_sg_gross_total_cents = _to_cents(1684200.00)
    remaining_gross_total_cents = target_sg_gross_total_cents - sg_completed_gross_total_cents
    if remaining_gross_total_cents <= 0:
        raise RuntimeError("SG completed gross total exceeded target 1,684,200.00")

    n_cancel = 500
    cancel_total_parts = _partition_cents(
        rng, remaining_gross_total_cents, n_cancel, _to_cents(150.00), _to_cents(1200.00)
    )
    for i, total_c in enumerate(cancel_total_parts):
        # Set gross_item + gst == total_c with ~9% GST
        gross_c = int(round(total_c / 1.09))
        gst_c = total_c - gross_c
        status = "CANCELLED" if i % 2 == 0 else "RETURNED"
        cid = pools["sg_std_general"][i % len(pools["sg_std_general"])]
        append_order(
            customer_id=cid,
            country_code="SG",
            sales_channel="Mobile App" if i % 2 == 0 else "Web Storefront",
            fulfillment_tier="STANDARD",
            order_status=status,
            gross_item_cents=gross_c,
            gst_cents=gst_c,
            gross_total_cents=total_c,
            net_cents=0,
            fulfillment_fee_cents=0,
            line_count=2,
            cogs_cents_total=0,
            leg_costs_cents=[0],
            primary_lot_id="LOT-AMB-101",
        )

    # -------------------------------------------------------------------------
    # Cohort 6: Regional MY / TH / ID orders (proving country_code='SG' filters matter)
    # -------------------------------------------------------------------------
    for country in ("MY", "TH", "ID"):
        c_key = country.lower()
        for i in range(120):
            is_hv = i < 30
            cid = pools[f"{c_key}_hv" if is_hv else f"{c_key}_std"][i % (15 if is_hv else 35)]
            status = "COMPLETED" if i < 105 else "RETURNED"
            net_c = rng.randint(25000, 75000) if status == "COMPLETED" else 0
            gross_c = net_c if status == "COMPLETED" else rng.randint(25000, 60000)
            gst_c = int(round(gross_c * 0.08))
            lot_id = "LOT-MY-8843" if (country == "MY" and i < 5) else "LOT-CHL-102"
            append_order(
                customer_id=cid,
                country_code=country,
                sales_channel="B2B Corporate Portal" if is_hv else "Web Storefront",
                fulfillment_tier="SAME_DAY" if (i % 5 == 0 and status == "COMPLETED") else "STANDARD",
                order_status=status,
                gross_item_cents=gross_c,
                gst_cents=gst_c,
                gross_total_cents=gross_c + gst_c,
                net_cents=net_c,
                fulfillment_fee_cents=int(round(net_c * 0.05)),
                line_count=2,
                cogs_cents_total=int(round(net_c * 0.54)),
                leg_costs_cents=[int(round(net_c * 0.04))],
                primary_lot_id=lot_id,
            )

    # -------------------------------------------------------------------------
    # R4 Tables: cold_chain_margin_gold (certified) vs staging_cold_chain_oct11 (stale)
    # -------------------------------------------------------------------------
    cold_chain_margin_gold = [
        {
            "country_code": "SG",
            "quarter": "2026-Q3",
            "net_revenue_sgd": 1220000.00,
            "gross_margin_sgd": 346480.00,
            "gross_margin_pct": 28.4,
            "rebate_settled": True,
            "certified_at": "2026-10-14T08:30:00Z",
            "prior_year_margin_pct": 28.55,
            "yoy_delta_bps": -15,
        },
        {
            "country_code": "MY",
            "quarter": "2026-Q3",
            "net_revenue_sgd": 750000.00,
            "gross_margin_sgd": 218250.00,
            "gross_margin_pct": 29.1,
            "rebate_settled": True,
            "certified_at": "2026-10-14T08:30:00Z",
            "prior_year_margin_pct": 29.25,
            "yoy_delta_bps": -15,
        },
        {
            "country_code": "TH",
            "quarter": "2026-Q3",
            "net_revenue_sgd": 550000.00,
            "gross_margin_sgd": 151800.00,
            "gross_margin_pct": 27.6,
            "rebate_settled": True,
            "certified_at": "2026-10-14T08:30:00Z",
            "prior_year_margin_pct": 27.75,
            "yoy_delta_bps": -15,
        },
        {
            "country_code": "ID",
            "quarter": "2026-Q3",
            "net_revenue_sgd": 446900.00,
            "gross_margin_sgd": 126070.00,
            "gross_margin_pct": 28.2,
            "rebate_settled": True,
            "certified_at": "2026-10-14T08:30:00Z",
            "prior_year_margin_pct": 28.35,
            "yoy_delta_bps": -15,
        },
    ]

    staging_cold_chain_oct11 = [
        {
            "country_code": "SG",
            "quarter": "2026-Q3",
            "net_revenue_sgd": 1220000.00,
            "gross_margin_sgd": 296460.00,
            "gross_margin_pct": 24.3,
            "rebate_settled": False,
            "certified_at": None,
            "prior_year_margin_pct": 28.4,
            "yoy_delta_bps": -410,
        },
        {
            "country_code": "MY",
            "quarter": "2026-Q3",
            "net_revenue_sgd": 750000.00,
            "gross_margin_sgd": 182250.00,
            "gross_margin_pct": 24.3,
            "rebate_settled": False,
            "certified_at": None,
            "prior_year_margin_pct": 28.4,
            "yoy_delta_bps": -410,
        },
        {
            "country_code": "TH",
            "quarter": "2026-Q3",
            "net_revenue_sgd": 550000.00,
            "gross_margin_sgd": 133650.00,
            "gross_margin_pct": 24.3,
            "rebate_settled": False,
            "certified_at": None,
            "prior_year_margin_pct": 28.4,
            "yoy_delta_bps": -410,
        },
        {
            "country_code": "ID",
            "quarter": "2026-Q3",
            "net_revenue_sgd": 446900.00,
            "gross_margin_sgd": 108596.70,
            "gross_margin_pct": 24.3,
            "rebate_settled": False,
            "certified_at": None,
            "prior_year_margin_pct": 28.4,
            "yoy_delta_bps": -410,
        },
    ]

    # -------------------------------------------------------------------------
    # R6 Tables: vendor_sla_ledger (base >4.0C >=90m -> 5%) + sla_overlay (Amendment #2)
    # 3 severe ArcticHaul breaches total 28,400.00 * 5% = 1,420.00
    # 14 total ArcticHaul BIOLOGIC_CHILLED (>2.0C >=45m) total 158,000.00 * 12% = 18,960.00
    # -------------------------------------------------------------------------
    severe_invoices = [9600.00, 10400.00, 8400.00]  # sum = 28,400.00 -> 5% = 1,420.00
    moderate_invoices_cents = _partition_cents(
        rng, _to_cents(129600.00), 11, _to_cents(9000.00), _to_cents(15000.00)
    )  # sum = 129,600.00 -> 14 total = 158,000.00 -> 12% = 18,960.00

    vendor_sla_ledger: list[dict[str, Any]] = []
    ev_seq = 1
    for idx, inv in enumerate(severe_invoices):
        vendor_sla_ledger.append(
            {
                "event_id": f"SLA-EVT-{ev_seq:03d}",
                "vendor_name": "ArcticHaul",
                "contract_id": "MSA-ARCTIC-2025",
                "sku_class": "BIOLOGIC_CHILLED",
                "quarter": "2026-Q3",
                "shipment_ref": f"SHP-AH-{9100 + idx}",
                "temp_peak_celsius": round(4.2 + idx * 0.25, 2),
                "excursion_duration_min": 92 + idx * 9,
                "shipment_invoice_sgd": inv,
                "base_temp_threshold_c": 4.0,
                "base_duration_min": 90,
                "base_credit_rate": 0.05,
            }
        )
        ev_seq += 1

    for idx, inv_c in enumerate(moderate_invoices_cents):
        # Moderate excursions (>2.0C and >=45m) failing base >4.0C AND >=90m gate
        temp = round(2.35 + (idx % 6) * 0.26, 2)
        dur = 48 + (idx % 5) * 8
        vendor_sla_ledger.append(
            {
                "event_id": f"SLA-EVT-{ev_seq:03d}",
                "vendor_name": "ArcticHaul",
                "contract_id": "MSA-ARCTIC-2025",
                "sku_class": "BIOLOGIC_CHILLED",
                "quarter": "2026-Q3",
                "shipment_ref": f"SHP-AH-{9200 + idx}",
                "temp_peak_celsius": temp,
                "excursion_duration_min": dur,
                "shipment_invoice_sgd": _from_cents(inv_c),
                "base_temp_threshold_c": 4.0,
                "base_duration_min": 90,
                "base_credit_rate": 0.05,
            }
        )
        ev_seq += 1

    non_qualifying = [
        ("SiamFrost Logistics", "MSA-SIAM-2025", "CHILLED_FOOD", 3.4, 72, 11200.00),
        ("SiamFrost Logistics", "MSA-SIAM-2025", "CHILLED_FOOD", 4.3, 40, 9800.00),
        ("SiamFrost Logistics", "MSA-SIAM-2025", "AMBIENT_STD", 3.1, 55, 7600.00),
        ("StraitsTemp Cargo", "MSA-STRAITS-2025", "CHILLED_FOOD", 3.8, 80, 12400.00),
        ("StraitsTemp Cargo", "MSA-STRAITS-2025", "FROZEN_PHARMA", 4.1, 35, 14500.00),
        ("ArcticHaul", "MSA-ARCTIC-2025", "BIOLOGIC_CHILLED", 1.9, 60, 8900.00),
    ]
    for idx, (vendor, cid, sku_cls, temp, dur, inv) in enumerate(non_qualifying):
        vendor_sla_ledger.append(
            {
                "event_id": f"SLA-EVT-{ev_seq:03d}",
                "vendor_name": vendor,
                "contract_id": cid,
                "sku_class": sku_cls,
                "quarter": "2026-Q3",
                "shipment_ref": f"SHP-OTH-{9300 + idx}",
                "temp_peak_celsius": temp,
                "excursion_duration_min": dur,
                "shipment_invoice_sgd": inv,
                "base_temp_threshold_c": 4.0,
                "base_duration_min": 90,
                "base_credit_rate": 0.05,
            }
        )
        ev_seq += 1

    sla_overlay = [
        {
            "overlay_id": "OVL-ARCTIC-AMD2",
            "vendor_name": "ArcticHaul",
            "amendment_ref": "Amendment #2 (Executed 2026-06-15)",
            "source_doc_path": "contracts/ArcticHaul_Amendment_2.md",
            "sku_class": "BIOLOGIC_CHILLED",
            "effective_date": "2026-07-01",
            "temp_threshold_c": 2.0,
            "duration_threshold_min": 45,
            "credit_rate": 0.12,
            "quarterly_cap_sgd": 35000.00,
            "extraction_tokens": 480,
            "verified_by": "AI.GENERATE + Legal Sign-Off",
        }
    ]

    return {
        "customers": customers,
        "orders": orders,
        "order_lines": order_lines,
        "parcel_legs": parcel_legs,
        "cold_chain_batches": batches,
        "sku_lot_allocations": allocations,
        "cold_chain_margin_gold": cold_chain_margin_gold,
        "staging_cold_chain_oct11": staging_cold_chain_oct11,
        "vendor_sla_ledger": vendor_sla_ledger,
        "sla_overlay": sla_overlay,
    }


def evaluate_invariants(
    tables: dict[str, list[dict[str, Any]]] | None = None,
    seed: int = DEFAULT_SEED,
) -> dict[str, float | int | str | bool]:
    """Computes exact R1-R6 invariants directly from generated table rows."""
    ds = tables if tables is not None else generate_dataset(seed=seed)

    customers_by_id = {c["customer_id"]: c for c in ds["customers"]}
    orders_by_id = {o["order_id"]: o for o in ds["orders"]}

    lines_by_order: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for ol in ds["order_lines"]:
        lines_by_order[ol["order_id"]].append(ol)

    legs_by_order: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pl in ds["parcel_legs"]:
        legs_by_order[pl["order_id"]].append(pl)

    # R1: SG gross total vs SG completed net realized revenue + header-to-line tie-out
    sg_orders = [o for o in ds["orders"] if o["country_code"] == "SG"]
    sg_completed = [o for o in sg_orders if o["order_status"] == "COMPLETED"]
    r1_blind_gross = round(sum(o["gross_total_sgd"] for o in sg_orders), 2)
    r1_governed_net = round(sum(o["net_realized_revenue_sgd"] for o in sg_completed), 2)

    drifts = []
    agg_line_net = 0.0
    agg_order_net = 0.0
    for o in ds["orders"]:
        if o["order_status"] == "COMPLETED":
            line_sum = round(sum(ol["net_line_revenue_sgd"] for ol in lines_by_order[o["order_id"]]), 2)
            drifts.append(abs(line_sum - o["net_realized_revenue_sgd"]))
            agg_line_net += line_sum
            agg_order_net += o["net_realized_revenue_sgd"]
    r1_max_drift = round(max(drifts) if drifts else 0.0, 2)
    r1_agg_drift = round(abs(agg_line_net - agg_order_net), 2)

    # R2: Blind LIKE '%Premier%' vs Governed tier_code = 'PRM_HV'
    blind_channel_rev: dict[str, list[float]] = defaultdict(list)
    gov_channel_rev: dict[str, list[float]] = defaultdict(list)
    for o in sg_completed:
        cust = customers_by_id[o["customer_id"]]
        if "Premier" in cust["segment_label"]:
            blind_channel_rev[o["sales_channel"]].append(o["net_realized_revenue_sgd"])
        if (
            cust["tier_code"] == "PRM_HV"
            and cust["trailing_12m_spend_sgd"] >= 5000.0
            and cust["return_rate"] < 0.08
        ):
            gov_channel_rev[o["sales_channel"]].append(o["net_realized_revenue_sgd"])

    r2_blind_winner, r2_blind_vals = max(
        blind_channel_rev.items(), key=lambda kv: sum(kv[1]) / len(kv[1])
    )
    r2_gov_winner, r2_gov_vals = max(
        gov_channel_rev.items(), key=lambda kv: sum(kv[1]) / len(kv[1])
    )
    all_hv_vals = [v for vals in gov_channel_rev.values() for v in vals]

    # R3: Grain-locked SAME_DAY margin vs naive 3-way JOIN fan-trap
    sameday_sg = [o for o in sg_completed if o["fulfillment_tier"] == "SAME_DAY"]
    true_rev = sum(o["net_realized_revenue_sgd"] for o in sameday_sg)
    true_fee = sum(o["fulfillment_fee_sgd"] for o in sameday_sg)
    true_cogs = sum(
        ol["cogs_line_sgd"] for o in sameday_sg for ol in lines_by_order[o["order_id"]]
    )
    true_leg = sum(
        pl["leg_cost_sgd"] for o in sameday_sg for pl in legs_by_order[o["order_id"]]
    )
    r3_true_margin_sgd = round(true_rev - true_cogs - true_fee - true_leg, 2)
    r3_true_margin_pct = round(100.0 * r3_true_margin_sgd / true_rev, 1)

    naive_rev = 0.0
    naive_cogs = 0.0
    naive_fee = 0.0
    naive_leg = 0.0
    for o in sameday_sg:
        for ol in lines_by_order[o["order_id"]]:
            for pl in legs_by_order[o["order_id"]]:
                naive_rev += ol["net_line_revenue_sgd"]
                naive_cogs += ol["cogs_line_sgd"]
                naive_fee += o["fulfillment_fee_sgd"]
                naive_leg += pl["leg_cost_sgd"]
    r3_blind_margin_pct = round(
        100.0 * (naive_rev - naive_cogs - naive_fee - naive_leg) / naive_rev, 1
    )

    # R4: Certified gold vs staging + Beat 4b RLS projections
    gold_q3 = [r for r in ds["cold_chain_margin_gold"] if r["quarter"] == "2026-Q3"]
    stg_q3 = [r for r in ds["staging_cold_chain_oct11"] if r["quarter"] == "2026-Q3"]
    r4_gold_margin_pct = round(
        100.0 * sum(r["gross_margin_sgd"] for r in gold_q3) / sum(r["net_revenue_sgd"] for r in gold_q3),
        1,
    )
    r4_stg_margin_pct = round(
        100.0 * sum(r["gross_margin_sgd"] for r in stg_q3) / sum(r["net_revenue_sgd"] for r in stg_q3),
        1,
    )
    sg_gold = [r for r in gold_q3 if r["country_code"] == "SG"]

    # R5: 4-hop Batch '#LN-409' -> SkuLotAllocation -> OrderLine -> Order -> Customer['PRM_HV']
    batches_by_id = {b["batch_id"]: b for b in ds["cold_chain_batches"]}
    lots_by_id = {a["lot_id"]: a for a in ds["sku_lot_allocations"]}

    gov_exposed_oids: set[str] = set()
    blind_exposed_oids: set[str] = set()
    for ol in ds["order_lines"]:
        o = orders_by_id[ol["order_id"]]
        if o["country_code"] != "SG" or o["order_status"] != "COMPLETED":
            continue
        cust = customers_by_id[o["customer_id"]]
        lot = lots_by_id.get(ol["lot_id"])
        batch = batches_by_id.get(lot["batch_id"]) if lot else None
        if batch and batch["batch_id"] == "#LN-409" and batch["supplier_tier"] == "TIER_2":
            if cust["tier_code"] == "PRM_HV":
                gov_exposed_oids.add(o["order_id"])
        if "409" in ol["lot_id"] and "Premier" in cust["segment_label"]:
            blind_exposed_oids.add(o["order_id"])

    r5_gov_rev = round(sum(orders_by_id[oid]["net_realized_revenue_sgd"] for oid in gov_exposed_oids), 2)
    r5_blind_rev = round(sum(orders_by_id[oid]["net_realized_revenue_sgd"] for oid in blind_exposed_oids), 2)

    # R6: Base vendor_sla_ledger vs sla_overlay join
    overlays = {(o["vendor_name"], o["sku_class"]): o for o in ds["sla_overlay"]}
    q3_events = [e for e in ds["vendor_sla_ledger"] if e["quarter"] == "2026-Q3"]

    blind_breaches = [
        e
        for e in q3_events
        if e["temp_peak_celsius"] > e["base_temp_threshold_c"]
        and e["excursion_duration_min"] >= e["base_duration_min"]
    ]
    r6_blind_credit = round(
        sum(e["shipment_invoice_sgd"] * e["base_credit_rate"] for e in blind_breaches), 2
    )

    vendor_raw_credits: dict[str, float] = defaultdict(float)
    vendor_caps: dict[str, float] = {}
    gov_qualifying_count = 0
    for e in q3_events:
        ovl = overlays.get((e["vendor_name"], e["sku_class"]))
        if ovl is not None:
            vendor_caps[e["vendor_name"]] = ovl["quarterly_cap_sgd"]
            if (
                e["temp_peak_celsius"] > ovl["temp_threshold_c"]
                and e["excursion_duration_min"] >= ovl["duration_threshold_min"]
            ):
                vendor_raw_credits[e["vendor_name"]] += e["shipment_invoice_sgd"] * ovl["credit_rate"]
                gov_qualifying_count += 1
        elif (
            e["temp_peak_celsius"] > e["base_temp_threshold_c"]
            and e["excursion_duration_min"] >= e["base_duration_min"]
        ):
            vendor_raw_credits[e["vendor_name"]] += e["shipment_invoice_sgd"] * e["base_credit_rate"]
            gov_qualifying_count += 1

    r6_gov_credit = round(
        sum(
            min(total, vendor_caps.get(v, 999999999.0))
            for v, total in vendor_raw_credits.items()
        ),
        2,
    )

    return {
        "r1_blind_sg_gross_total_sgd": r1_blind_gross,
        "r1_governed_sg_net_realized_revenue_sgd": r1_governed_net,
        "r1_header_to_line_max_drift_sgd": r1_max_drift,
        "r1_header_to_line_aggregate_drift_sgd": r1_agg_drift,
        "r2_blind_winning_channel": r2_blind_winner,
        "r2_blind_winning_aov_sgd": round(sum(r2_blind_vals) / len(r2_blind_vals), 2),
        "r2_governed_winning_channel": r2_gov_winner,
        "r2_governed_winning_aov_sgd": round(sum(r2_gov_vals) / len(r2_gov_vals), 2),
        "r2_governed_b2b_order_count": len(r2_gov_vals),
        "r2_governed_b2b_revenue_sgd": round(sum(r2_gov_vals), 2),
        "r2_governed_total_prm_hv_orders": len(all_hv_vals),
        "r2_governed_total_prm_hv_revenue_sgd": round(sum(all_hv_vals), 2),
        "r2_governed_overall_prm_hv_aov_sgd": round(sum(all_hv_vals) / len(all_hv_vals), 2),
        "r3_blind_sameday_margin_pct": r3_blind_margin_pct,
        "r3_governed_sameday_margin_pct": r3_true_margin_pct,
        "r3_governed_sameday_margin_sgd": r3_true_margin_sgd,
        "r3_governed_sameday_revenue_sgd": round(true_rev, 2),
        "r4_blind_staging_margin_pct": r4_stg_margin_pct,
        "r4_blind_yoy_delta_bps": int(stg_q3[0]["yoy_delta_bps"]),
        "r4_governed_gold_margin_pct": r4_gold_margin_pct,
        "r4_governed_yoy_delta_bps": int(gold_q3[0]["yoy_delta_bps"]),
        "r4_cfo_regional_gross_margin_sgd": round(sum(r["gross_margin_sgd"] for r in gold_q3), 2),
        "r4_cfo_regional_rows_visible": len(gold_q3),
        "r4_sg_coldchain_gross_margin_sgd": round(sum(r["gross_margin_sgd"] for r in sg_gold), 2),
        "r4_sg_coldchain_rows_visible": len(sg_gold),
        "r4_shadow_table_count": SHADOW_TABLE_COUNT,
        "r5_blind_exposed_revenue_sgd": r5_blind_rev,
        "r5_blind_exposed_order_count": len(blind_exposed_oids),
        "r5_governed_exposed_order_count": len(gov_exposed_oids),
        "r5_governed_exposed_revenue_sgd": r5_gov_rev,
        "r5_governed_exposed_aov_sgd": round(r5_gov_rev / len(gov_exposed_oids), 2),
        "r6_blind_base_breach_count": len(blind_breaches),
        "r6_blind_base_credit_sgd": r6_blind_credit,
        "r6_governed_qualifying_shipments": gov_qualifying_count,
        "r6_governed_recoverable_credit_sgd": r6_gov_credit,
        "r6_governed_quarterly_cap_sgd": float(ds["sla_overlay"][0]["quarterly_cap_sgd"]),
    }


EXPECTED_INVARIANTS: dict[str, float | int | str | bool] = {
    "r1_blind_sg_gross_total_sgd": 1684200.0,
    "r1_governed_sg_net_realized_revenue_sgd": 1312450.0,
    "r1_header_to_line_max_drift_sgd": 0.0,
    "r1_header_to_line_aggregate_drift_sgd": 0.0,
    "r2_blind_winning_channel": "Mobile App",
    "r2_blind_winning_aov_sgd": 284.1,
    "r2_governed_winning_channel": "B2B Corporate Portal",
    "r2_governed_winning_aov_sgd": 612.5,
    "r2_governed_b2b_order_count": 240,
    "r2_governed_b2b_revenue_sgd": 147000.0,
    "r2_governed_total_prm_hv_orders": 640,
    "r2_governed_total_prm_hv_revenue_sgd": 317203.2,
    "r2_governed_overall_prm_hv_aov_sgd": 495.63,
    "r3_blind_sameday_margin_pct": 14.2,
    "r3_governed_sameday_margin_pct": 31.8,
    "r3_governed_sameday_margin_sgd": 131016.0,
    "r3_governed_sameday_revenue_sgd": 412000.0,
    "r4_blind_staging_margin_pct": 24.3,
    "r4_blind_yoy_delta_bps": -410,
    "r4_governed_gold_margin_pct": 28.4,
    "r4_governed_yoy_delta_bps": -15,
    "r4_cfo_regional_gross_margin_sgd": 842600.0,
    "r4_cfo_regional_rows_visible": 4,
    "r4_sg_coldchain_gross_margin_sgd": 346480.0,
    "r4_sg_coldchain_rows_visible": 1,
    "r4_shadow_table_count": 190,
    "r5_blind_exposed_revenue_sgd": 4120.0,
    "r5_blind_exposed_order_count": 8,
    "r5_governed_exposed_order_count": 38,
    "r5_governed_exposed_revenue_sgd": 19380.0,
    "r5_governed_exposed_aov_sgd": 510.0,
    "r6_blind_base_breach_count": 3,
    "r6_blind_base_credit_sgd": 1420.0,
    "r6_governed_qualifying_shipments": 14,
    "r6_governed_recoverable_credit_sgd": 18960.0,
    "r6_governed_quarterly_cap_sgd": 35000.0,
}


def emit_shadow_ddl(
    project_id: str = "${PROJECT_ID}",
    dataset_id: str = "${DATASET_ID}",
    count: int = SHADOW_TABLE_COUNT,
) -> str:
    """Generates BigQuery DDL for shadow_auto_tbl_001..shadow_auto_tbl_190."""
    statements = []
    for idx in range(1, count + 1):
        tbl = f"`{project_id}.{dataset_id}.shadow_auto_tbl_{idx:03d}`"
        statements.append(
            f"CREATE TABLE IF NOT EXISTS {tbl} (\n"
            "  country_code STRING,\n"
            "  quarter STRING,\n"
            "  net_revenue_sgd FLOAT64,\n"
            "  gross_margin_sgd FLOAT64,\n"
            "  gross_margin_pct FLOAT64,\n"
            "  rebate_settled BOOL,\n"
            "  snapshot_tag STRING\n"
            ")\n"
            'OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");'
        )
    return "\n\n".join(statements) + "\n"


def write_jsonl_tables(
    output_dir: Path, tables: dict[str, list[dict[str, Any]]]
) -> dict[str, int]:
    """Writes one newline-delimited JSON file per table for BigQuery `bq load`."""
    output_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for table_name, rows in tables.items():
        target = output_dir / f"{table_name}.jsonl"
        with target.open("w", encoding="utf-8") as fh:
            for row in rows:
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        counts[table_name] = len(rows)
    return counts


def verify_invariants_report(seed: int = DEFAULT_SEED) -> dict[str, Any]:
    """Evaluates all invariants and reports exact discrepancy against SPEC.md §3.2."""
    tables = generate_dataset(seed=seed)
    computed = evaluate_invariants(tables=tables, seed=seed)
    mismatches: dict[str, dict[str, Any]] = {}
    max_numeric_diff = 0.0

    for key, expected in EXPECTED_INVARIANTS.items():
        actual = computed.get(key)
        if isinstance(expected, (int, float)) and not isinstance(expected, bool):
            diff = abs(float(actual) - float(expected)) if actual is not None else float("inf")
            max_numeric_diff = max(max_numeric_diff, round(diff, 6))
            if diff > 1e-6:
                mismatches[key] = {"expected": expected, "actual": actual, "diff": diff}
        elif actual != expected:
            mismatches[key] = {"expected": expected, "actual": actual}

    return {
        "pack_id": "meridian_q3_sgd",
        "seed": seed,
        "verified": len(mismatches) == 0 and max_numeric_diff == 0.0,
        "max_discrepancy": max_numeric_diff,
        "row_counts": {k: len(v) for k, v in tables.items()},
        "invariants": computed,
        "mismatches": mismatches,
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deterministic Meridian Commerce Q3 fixture generator & invariant verifier."
    )
    parser.add_argument("--seed", type=int, default=DEFAULT_SEED, help="Deterministic RNG seed.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Write <table>.jsonl files into this directory for bq load.",
    )
    parser.add_argument(
        "--emit-shadow-ddl",
        action="store_true",
        help="Print CREATE TABLE IF NOT EXISTS DDL for shadow_auto_tbl_001..190.",
    )
    parser.add_argument(
        "--project-id",
        default="${PROJECT_ID}",
        help="Project placeholder or ID for --emit-shadow-ddl.",
    )
    parser.add_argument(
        "--dataset-id",
        default="${DATASET_ID}",
        help="Dataset placeholder or ID for --emit-shadow-ddl.",
    )
    parser.add_argument(
        "--verify-json",
        action="store_true",
        help="Evaluate invariants and print JSON verification summary (exits 0 iff 0.00 drift).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    if args.output_dir is not None:
        tables = generate_dataset(seed=args.seed)
        counts = write_jsonl_tables(args.output_dir, tables)
        if not args.verify_json and not args.emit_shadow_ddl:
            print(json.dumps({"output_dir": str(args.output_dir), "row_counts": counts}, indent=2))
    if args.emit_shadow_ddl:
        sys.stdout.write(emit_shadow_ddl(project_id=args.project_id, dataset_id=args.dataset_id))
    if args.verify_json:
        report = verify_invariants_report(seed=args.seed)
        print(json.dumps(report, indent=2))
        return 0 if report["verified"] else 1
    if args.output_dir is None and not args.emit_shadow_ddl and not args.verify_json:
        report = verify_invariants_report(seed=args.seed)
        print(json.dumps(report, indent=2))
        return 0 if report["verified"] else 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
