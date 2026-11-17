-- Uncertified staging clone + 190 automated shadow tables (Rung 4 Trust & Data Products trap).
-- Idempotent table creation ensures re-running after .jsonl ingestion never truncates loaded rows.

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.staging_cold_chain_oct11` (
  country_code STRING NOT NULL,
  quarter STRING NOT NULL,
  net_revenue_sgd FLOAT64 NOT NULL,
  gross_margin_sgd FLOAT64 NOT NULL,
  gross_margin_pct FLOAT64 NOT NULL,
  rebate_settled BOOL NOT NULL,
  certified_at TIMESTAMP,
  prior_year_margin_pct FLOAT64 NOT NULL,
  yoy_delta_bps INT64 NOT NULL
)
OPTIONS(description="Uncertified Oct 11 staging snapshot missing late-Q3 supplier rebates (trap table).");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_001` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_002` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_003` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_004` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_005` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_006` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_007` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_008` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_009` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_010` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_011` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_012` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_013` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_014` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_015` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_016` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_017` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_018` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_019` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_020` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_021` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_022` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_023` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_024` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_025` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_026` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_027` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_028` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_029` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_030` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_031` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_032` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_033` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_034` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_035` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_036` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_037` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_038` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_039` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_040` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_041` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_042` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_043` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_044` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_045` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_046` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_047` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_048` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_049` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_050` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_051` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_052` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_053` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_054` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_055` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_056` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_057` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_058` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_059` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_060` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_061` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_062` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_063` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_064` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_065` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_066` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_067` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_068` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_069` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_070` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_071` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_072` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_073` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_074` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_075` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_076` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_077` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_078` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_079` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_080` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_081` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_082` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_083` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_084` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_085` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_086` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_087` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_088` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_089` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_090` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_091` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_092` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_093` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_094` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_095` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_096` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_097` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_098` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_099` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_100` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_101` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_102` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_103` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_104` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_105` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_106` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_107` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_108` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_109` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_110` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_111` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_112` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_113` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_114` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_115` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_116` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_117` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_118` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_119` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_120` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_121` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_122` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_123` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_124` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_125` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_126` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_127` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_128` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_129` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_130` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_131` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_132` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_133` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_134` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_135` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_136` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_137` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_138` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_139` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_140` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_141` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_142` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_143` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_144` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_145` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_146` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_147` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_148` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_149` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_150` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_151` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_152` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_153` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_154` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_155` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_156` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_157` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_158` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_159` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_160` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_161` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_162` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_163` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_164` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_165` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_166` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_167` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_168` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_169` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_170` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_171` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_172` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_173` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_174` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_175` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_176` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_177` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_178` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_179` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_180` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_181` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_182` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_183` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_184` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_185` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_186` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_187` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_188` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_189` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");

CREATE TABLE IF NOT EXISTS `${PROJECT_ID}.${DATASET_ID}.shadow_auto_tbl_190` (
  country_code STRING,
  quarter STRING,
  net_revenue_sgd FLOAT64,
  gross_margin_sgd FLOAT64,
  gross_margin_pct FLOAT64,
  rebate_settled BOOL,
  snapshot_tag STRING
)
OPTIONS(description="Uncertified automated clone generated during Q3 ad-hoc backfills");
