# Executed Amendment #2 to ArcticHaul Master Services Agreement (`MSA-ARCTIC-2025`)

- **Amendment Reference:** `Amendment #2` (Executed `2026-06-15`, Effective `2026-07-01` — Closed Q3 2026)
- **Covered Vendor:** `ArcticHaul` (`MSA-ARCTIC-2025`)
- **Covered Thermal SKU Class:** `BIOLOGIC_CHILLED`
- **Overlay ID:** `OVL-ARCTIC-AMD2`

## Clause 1 · Superseding Biologic Chilled SLA Thresholds

Effective **2026-07-01**, Section 4 of `MSA-ARCTIC-2025` is superseded strictly for shipments containing `BIOLOGIC_CHILLED` SKUs as follows:

1. **Tightened Excursion Trigger:** Any `ArcticHaul` shipment carrying `BIOLOGIC_CHILLED` inventory that experiences a peak cabin temperature strictly exceeding **`2.0°C`** for a duration of **`45` minutes or longer** (`temp_peak_celsius > 2.0 AND excursion_duration_min >= 45`) constitutes a qualifying SLA breach, regardless of whether it meets the legacy `4.0°C / 90 min` baseline.
2. **Enhanced Recovery Credit Rate:** Qualifying `BIOLOGIC_CHILLED` breaches carry a **`12%` (`0.12`)** SLA credit calculated against `shipment_invoice_sgd` (replacing the `5%` base rate).
3. **Quarterly Recovery Cap:** Aggregate recoverable SLA credits across `ArcticHaul` `BIOLOGIC_CHILLED` shipments within a single fiscal quarter are capped at **`SGD 35,000.00`**.
4. **Structured Extraction Footprint:** Extracted via BigQuery Object Tables + `AI.GENERATE` / DocAI into a compact **`480`-token** structured `sla_overlay` row (`OVL-ARCTIC-AMD2`) for deterministic SQL joins against `vendor_sla_ledger`.

## Execution Signatures

- Signed on behalf of **Meridian Commerce Pte. Ltd.:** VP Supply Chain & Regional Counsel (`2026-06-15`)
- Signed on behalf of **ArcticHaul Cold Logistics Pte. Ltd.:** Managing Director, Pharma & Cold Fleet (`2026-06-15`)
