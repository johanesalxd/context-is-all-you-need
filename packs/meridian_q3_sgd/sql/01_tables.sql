-- Core relational, cold-chain lineage, certified Data Product, and vendor SLA tables
-- for Meridian Commerce Closed Q3 (2026-07-01 .. 2026-09-30, SGD, asia-southeast1).

CREATE OR REPLACE TABLE `${PROJECT_ID}.${DATASET_ID}.customers` (
  customer_id STRING NOT NULL OPTIONS(description="Unique customer identifier (primary key)."),
  country_code STRING NOT NULL OPTIONS(description="ISO-3166-1 alpha-2 SEA market code: SG, MY, TH, or ID."),
  tier_code STRING NOT NULL OPTIONS(description="Official Knowledge Catalog Business Glossary tier code. Premier Customer = 'PRM_HV' (enforcing trailing_12m_spend_sgd >= 5000.00 AND return_rate < 0.08). Never use segment_label for Premier classification."),
  segment_label STRING NOT NULL OPTIONS(description="Legacy marketing campaign tag (contains distractor labels like 'Premier_Promo_Trial' on unverified promo signups). Do NOT use for governed Premier financial reporting."),
  trailing_12m_spend_sgd FLOAT64 NOT NULL OPTIONS(description="Trailing 12-month realized customer spend in SGD (ex-GST)."),
  return_rate FLOAT64 NOT NULL OPTIONS(description="Trailing 12-month order return ratio in [0.0, 1.0]. Premier Customer requires < 0.08."),
  channel_pref STRING NOT NULL OPTIONS(description="Primary customer acquisition or ordering channel."),
  PRIMARY KEY (customer_id) NOT ENFORCED
)
OPTIONS(description="Meridian Commerce customer master across SG, MY, TH, and ID.");

CREATE OR REPLACE TABLE `${PROJECT_ID}.${DATASET_ID}.cold_chain_batches` (
  batch_id STRING NOT NULL OPTIONS(description="Cold-chain supplier shipment batch identifier (e.g., '#LN-409')."),
  supplier_tier STRING NOT NULL OPTIONS(description="Upstream vendor tier classification ('TIER_1' or 'TIER_2')."),
  vendor_name STRING NOT NULL OPTIONS(description="Cold-chain logistics or supplier vendor name."),
  temp_peak_celsius FLOAT64 NOT NULL OPTIONS(description="Peak telemetry temperature recorded in Celsius during batch transit."),
  excursion_duration_min INT64 NOT NULL OPTIONS(description="Cumulative minutes above nominal biologic storage threshold."),
  shipment_invoice_sgd FLOAT64 NOT NULL OPTIONS(description="Total commercial invoice value for the batch in SGD."),
  batch_status STRING NOT NULL OPTIONS(description="Operational clearance status (e.g., 'CLEARED', 'DELAYED_EXCURSION')."),
  PRIMARY KEY (batch_id) NOT ENFORCED
)
OPTIONS(description="Upstream cold-chain supplier batches with excursion telemetry.");

CREATE OR REPLACE TABLE `${PROJECT_ID}.${DATASET_ID}.sku_lot_allocations` (
  lot_id STRING NOT NULL OPTIONS(description="Warehouse SKU inventory lot identifier."),
  batch_id STRING NOT NULL OPTIONS(description="Upstream cold_chain_batches.batch_id foreign key linking lot to supplier batch."),
  sku_id STRING NOT NULL OPTIONS(description="Product SKU identifier allocated from this lot."),
  temp_sensitive_class STRING NOT NULL OPTIONS(description="Thermal handling class: AMBIENT_STD, CHILLED_FOOD, FROZEN_PHARMA, or BIOLOGIC_CHILLED."),
  PRIMARY KEY (lot_id) NOT ENFORCED,
  FOREIGN KEY (batch_id) REFERENCES `${PROJECT_ID}.${DATASET_ID}.cold_chain_batches`(batch_id) NOT ENFORCED
)
OPTIONS(description="Bridge mapping warehouse inventory lots to upstream cold-chain supplier batches.");

CREATE OR REPLACE TABLE `${PROJECT_ID}.${DATASET_ID}.orders` (
  order_id STRING NOT NULL OPTIONS(description="Unique order header identifier."),
  customer_id STRING NOT NULL OPTIONS(description="Foreign key referencing customers.customer_id."),
  country_code STRING NOT NULL OPTIONS(description="Order fulfillment country code: SG, MY, TH, or ID. Filter country_code = 'SG' for Singapore queries."),
  sales_channel STRING NOT NULL OPTIONS(description="Order sales channel: B2B Corporate Portal, Direct Account Desk, Web Storefront, or Mobile App."),
  fulfillment_tier STRING NOT NULL OPTIONS(description="Delivery SLA tier: SAME_DAY, NEXT_DAY, or STANDARD."),
  order_date DATE NOT NULL OPTIONS(description="Order booking date (Closed Q3 covers DATE '2026-07-01' through DATE '2026-09-30')."),
  order_status STRING NOT NULL OPTIONS(description="Order lifecycle status: COMPLETED, CANCELLED, or RETURNED. Governed Net Realized Revenue filters order_status = 'COMPLETED'."),
  amt_gross_billed_sgd FLOAT64 NOT NULL OPTIONS(description="Gross billed invoice total in SGD INCLUDING 9% Singapore GST across ALL order statuses (COMPLETED, CANCELLED, and RETURNED). Do NOT report as net realized revenue."),
  amt_item_subtotal_sgd FLOAT64 NOT NULL OPTIONS(description="Ex-GST item subtotal in SGD BEFORE deducting cancellations or returns; remains positive on CANCELLED and RETURNED orders and includes pre-return gross item value on partial returns. Do NOT report as net realized revenue."),
  amt_gst_sgd FLOAT64 NOT NULL OPTIONS(description="Goods and Services Tax billed amount in SGD (9% in Singapore)."),
  fulfillment_fee_sgd FLOAT64 NOT NULL OPTIONS(description="Order-level warehouse pick/pack/cold-pack fulfillment cost in SGD (order grain; do not sum across order_lines or parcel_legs joins)."),
  amt_net_settled_sgd FLOAT64 NOT NULL OPTIONS(description="Governed Net Realized Revenue in SGD: ex-GST, net of cancellations and returns, 0.00 on CANCELLED and RETURNED orders. Filter country_code = 'SG' AND order_status = 'COMPLETED'; reconciles with 0.00 SGD drift against SUM(order_lines.net_line_revenue_sgd) for COMPLETED orders."),
  PRIMARY KEY (order_id) NOT ENFORCED,
  FOREIGN KEY (customer_id) REFERENCES `${PROJECT_ID}.${DATASET_ID}.customers`(customer_id) NOT ENFORCED
)
OPTIONS(description="Order header fact table across Closed Q3 2026 (2026-07-01 .. 2026-09-30). ERP revenue semantics: amt_gross_billed_sgd includes 9% SG GST across all statuses; amt_item_subtotal_sgd is ex-GST item subtotal before deducting cancellations/returns (positive even on CANCELLED/RETURNED orders); amt_net_settled_sgd is 0.00 on CANCELLED/RETURNED orders and equals governed Net Realized Revenue (ex-GST, net of returns) on COMPLETED orders, reconciling to 0.00 SGD drift against SUM(order_lines.net_line_revenue_sgd).");

CREATE OR REPLACE TABLE `${PROJECT_ID}.${DATASET_ID}.order_lines` (
  order_line_id STRING NOT NULL OPTIONS(description="Unique order line item identifier."),
  order_id STRING NOT NULL OPTIONS(description="Foreign key referencing orders.order_id."),
  sku_id STRING NOT NULL OPTIONS(description="Product SKU identifier."),
  lot_id STRING NOT NULL OPTIONS(description="Foreign key referencing sku_lot_allocations.lot_id for cold-chain batch lineage."),
  qty INT64 NOT NULL OPTIONS(description="Units ordered on this line."),
  gross_line_sgd FLOAT64 NOT NULL OPTIONS(description="Gross line item amount in SGD before GST and returns."),
  gst_line_sgd FLOAT64 NOT NULL OPTIONS(description="Allocated GST component in SGD."),
  returned_line_sgd FLOAT64 NOT NULL OPTIONS(description="Returned merchandise deduction in SGD."),
  net_line_revenue_sgd FLOAT64 NOT NULL OPTIONS(description="Net realized line revenue in SGD (ex-GST, net of returns). Sums cleanly to orders.amt_net_settled_sgd for COMPLETED orders."),
  cogs_line_sgd FLOAT64 NOT NULL OPTIONS(description="Line-item Cost of Goods Sold in SGD (line grain; do not multiply across parcel_legs joins)."),
  PRIMARY KEY (order_line_id) NOT ENFORCED,
  FOREIGN KEY (order_id) REFERENCES `${PROJECT_ID}.${DATASET_ID}.orders`(order_id) NOT ENFORCED,
  FOREIGN KEY (lot_id) REFERENCES `${PROJECT_ID}.${DATASET_ID}.sku_lot_allocations`(lot_id) NOT ENFORCED
)
OPTIONS(description="Order line item detail linking orders to inventory lots and COGS.");

CREATE OR REPLACE TABLE `${PROJECT_ID}.${DATASET_ID}.parcel_legs` (
  leg_id STRING NOT NULL OPTIONS(description="Unique parcel transfer leg identifier."),
  order_id STRING NOT NULL OPTIONS(description="Foreign key referencing orders.order_id. SAME_DAY orders have 2 to 4 legs per order (1:N fan-out)."),
  hub_code STRING NOT NULL OPTIONS(description="Fulfillment or cross-dock sorting hub code."),
  carrier_vendor STRING NOT NULL OPTIONS(description="Last-mile or inter-hub carrier name."),
  leg_seq INT64 NOT NULL OPTIONS(description="Sequential leg index within the order journey (1..4)."),
  leg_cost_sgd FLOAT64 NOT NULL OPTIONS(description="Carrier transfer leg cost in SGD (leg grain)."),
  temp_excursion_celsius FLOAT64 NOT NULL OPTIONS(description="Peak temperature reading in Celsius recorded on this parcel leg."),
  excursion_minutes INT64 NOT NULL OPTIONS(description="Duration of any minor thermal excursion in minutes."),
  PRIMARY KEY (leg_id) NOT ENFORCED,
  FOREIGN KEY (order_id) REFERENCES `${PROJECT_ID}.${DATASET_ID}.orders`(order_id) NOT ENFORCED
)
OPTIONS(description="1:N parcel transfer leg telemetry and carrier cost table.");

CREATE OR REPLACE TABLE `${PROJECT_ID}.${DATASET_ID}.mart_coldchain_q3_r2` (
  country_code STRING NOT NULL OPTIONS(description="SEA market code (SG, MY, TH, ID). Subject to BigQuery Row-Level Security policies."),
  quarter STRING NOT NULL OPTIONS(description="Fiscal quarter label ('2026-Q3')."),
  net_revenue_sgd FLOAT64 NOT NULL OPTIONS(description="Certified cold-chain net revenue in SGD."),
  gross_margin_sgd FLOAT64 NOT NULL OPTIONS(description="Certified cold-chain gross margin in SGD after late-Q3 supplier rebate settlements (close_batch_code='B26Q3_R2')."),
  gross_margin_pct FLOAT64 NOT NULL OPTIONS(description="Certified cold-chain gross margin percentage."),
  close_batch_code STRING NOT NULL OPTIONS(description="Financial close batch identifier ('B26Q3_R2' = final certified Q3 close including settled supplier rebates)."),
  PRIMARY KEY (country_code, quarter) NOT ENFORCED
)
OPTIONS(description="Certified Knowledge Catalog Data Product (data-product-certification = CERTIFIED, close_batch_code='B26Q3_R2') for Q3 cold-chain margins including settled supplier rebates, protected by BigQuery RLS.");

CREATE OR REPLACE TABLE `${PROJECT_ID}.${DATASET_ID}.mart_coldchain_q3_r1` (
  country_code STRING NOT NULL OPTIONS(description="SEA market code (SG, MY, TH, ID)."),
  quarter STRING NOT NULL OPTIONS(description="Fiscal quarter label ('2026-Q3')."),
  net_revenue_sgd FLOAT64 NOT NULL OPTIONS(description="Preliminary cold-chain net revenue in SGD."),
  gross_margin_sgd FLOAT64 NOT NULL OPTIONS(description="Preliminary Oct 11 gross margin missing late-Q3 supplier rebate settlements (close_batch_code='B26Q3_R1')."),
  gross_margin_pct FLOAT64 NOT NULL OPTIONS(description="Preliminary pre-rebate margin percentage."),
  close_batch_code STRING NOT NULL OPTIONS(description="Financial close batch identifier ('B26Q3_R1' = uncertified preliminary Oct 11 snapshot). Do NOT use for executive margin reporting.")
)
OPTIONS(description="Uncertified preliminary Oct 11 cold-chain margin snapshot (data-product-certification = UNCERTIFIED_STALE, close_batch_code='B26Q3_R1') missing late-Q3 supplier rebates. Do NOT use for executive reporting.");

CREATE OR REPLACE TABLE `${PROJECT_ID}.${DATASET_ID}.vendor_sla_ledger` (
  event_id STRING NOT NULL OPTIONS(description="Unique cold-chain vendor SLA excursion event identifier."),
  vendor_name STRING NOT NULL OPTIONS(description="Cold-chain carrier vendor name (e.g., ArcticHaul, SiamFrost Logistics, StraitsTemp Cargo)."),
  contract_id STRING NOT NULL OPTIONS(description="Base Master Services Agreement identifier."),
  sku_class STRING NOT NULL OPTIONS(description="Product thermal class: BIOLOGIC_CHILLED, CHILLED_FOOD, FROZEN_PHARMA, or AMBIENT_STD."),
  quarter STRING NOT NULL OPTIONS(description="Fiscal quarter ('2026-Q3')."),
  shipment_ref STRING NOT NULL OPTIONS(description="Vendor waybill / shipment reference."),
  temp_peak_celsius FLOAT64 NOT NULL OPTIONS(description="Peak telemetry excursion temperature in Celsius."),
  excursion_duration_min INT64 NOT NULL OPTIONS(description="Cumulative excursion duration in minutes."),
  shipment_invoice_sgd FLOAT64 NOT NULL OPTIONS(description="Freight/shipment invoice value subject to SLA credit in SGD."),
  base_temp_threshold_c FLOAT64 NOT NULL OPTIONS(description="Legacy MSA temperature trigger in Celsius (> 4.0 C)."),
  base_duration_min INT64 NOT NULL OPTIONS(description="Legacy MSA minimum excursion duration in minutes (>= 90 min)."),
  base_credit_rate FLOAT64 NOT NULL OPTIONS(description="Legacy MSA credit rate (0.05 = 5%)."),
  PRIMARY KEY (event_id) NOT ENFORCED
)
OPTIONS(description="Base cold-chain carrier SLA telemetry ledger encoding legacy MSA thresholds.");

CREATE OR REPLACE TABLE `${PROJECT_ID}.${DATASET_ID}.sla_overlay` (
  overlay_id STRING NOT NULL OPTIONS(description="Unique structured contract amendment overlay identifier."),
  vendor_name STRING NOT NULL OPTIONS(description="Vendor name covered by the executed amendment."),
  amendment_ref STRING NOT NULL OPTIONS(description="Executed contract amendment title and date."),
  source_doc_path STRING NOT NULL OPTIONS(description="Source contract artifact path."),
  sku_class STRING NOT NULL OPTIONS(description="Thermal SKU class governed by the amendment (e.g., BIOLOGIC_CHILLED)."),
  effective_date DATE NOT NULL OPTIONS(description="Contractual effective start date."),
  temp_threshold_c FLOAT64 NOT NULL OPTIONS(description="Amended excursion temperature trigger in Celsius (> 2.0 C)."),
  duration_threshold_min INT64 NOT NULL OPTIONS(description="Amended minimum excursion duration in minutes (>= 45 min)."),
  credit_rate FLOAT64 NOT NULL OPTIONS(description="Amended SLA credit percentage (0.12 = 12%)."),
  quarterly_cap_sgd FLOAT64 NOT NULL OPTIONS(description="Maximum recoverable quarterly SLA credit cap in SGD (35,000.00)."),
  extraction_tokens INT64 NOT NULL OPTIONS(description="Compact structured token footprint extracted from the contract amendment (480 tokens)."),
  verified_by STRING NOT NULL OPTIONS(description="Extraction and legal verification provenance."),
  PRIMARY KEY (overlay_id) NOT ENFORCED
)
OPTIONS(description="Structured 480-token SLA amendment overlay extracted via AI.GENERATE / DocAI.");
