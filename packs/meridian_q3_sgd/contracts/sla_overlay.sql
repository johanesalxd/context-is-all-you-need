-- Structured 480-token SLA amendment overlay extracted from contracts/ArcticHaul_Amendment_2.md
-- via BigQuery Object Tables + AI.GENERATE / DocAI (GA in asia-southeast1).
-- Uses CREATE TABLE IF NOT EXISTS so execution before or after sla_overlay.jsonl ingestion is idempotent.

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.sla_overlay` (
  overlay_id STRING NOT NULL OPTIONS(description="Unique structured contract amendment overlay identifier."),
  vendor_name STRING NOT NULL OPTIONS(description="Vendor name covered by the executed amendment."),
  amendment_ref STRING NOT NULL OPTIONS(description="Executed contract amendment title and date."),
  source_doc_path STRING NOT NULL OPTIONS(description="Source contract artifact path."),
  sku_class STRING NOT NULL OPTIONS(description="Thermal SKU class governed by the amendment (BIOLOGIC_CHILLED)."),
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
