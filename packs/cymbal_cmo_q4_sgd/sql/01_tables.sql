-- Deterministic pure-SQL seed for Cymbal Commerce (cymbal_cmo_q4_sgd) in asia-southeast1.
-- Zero external files, uploads, or Python RNG required: all rows are generated via
-- UNNEST(GENERATE_ARRAY(...)) and deterministic MOD arithmetic across 3 datasets:
--   1) ${PROJECT_ID}.cymbal_dw        (blind / raw unannotated warehouse tables)
--   2) ${PROJECT_ID}.cymbal_commerce  (governed / certified tables & fraud graph inputs)
--   3) ${PROJECT_ID}.cymbal_lake      (regional copy of AWS S3 Iceberg click telemetry)

CREATE SCHEMA IF NOT EXISTS `${PROJECT_ID}.cymbal_dw`
  OPTIONS (location = "${BQ_LOCATION}");

CREATE SCHEMA IF NOT EXISTS `${PROJECT_ID}.cymbal_commerce`
  OPTIONS (location = "${BQ_LOCATION}");

CREATE SCHEMA IF NOT EXISTS `${PROJECT_ID}.cymbal_lake`
  OPTIONS (location = "${BQ_LOCATION}");

-- ============================================================================
-- 1. BLIND / RAW TABLES (${PROJECT_ID}.cymbal_dw)
-- ============================================================================

-- R1 & R3 blind trap:
--   - gross_order_value sums to exact SGD 1,850,000.00 (includes 9% GST + organic)
--   - amt_net_settled_sgd resets to 0.00 on RETURNED rows (naive return check = SGD 0)
--   - net_contribution_sgd sums to 332,000.00 at order grain, but fans out to 592,000.00
--     when naively joined 1:N with campaign_clicks_raw (592K - 400K spend = +192K / +48% ROI)
CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_dw.campaign_orders` AS
SELECT
  FORMAT('ORD-RAW-%04d', i) AS order_id,
  'FY26_Q3' AS campaign_quarter,
  DATE_ADD(DATE '2026-07-01', INTERVAL MOD(i * 7, 90) DAY) AS order_date,
  CASE
    WHEN i <= 500 THEN 'SG'
    WHEN i <= 636 THEN 'B2B'
    WHEN i <= 700 THEN 'SG'
    ELSE 'MY'
  END AS market_code,
  CASE
    WHEN i <= 500 THEN 'SG Paid Social'
    WHEN i <= 700 THEN 'B2B / Search'
    ELSE 'MY Paid Social'
  END AS channel,
  CASE
    WHEN MOD(i, 5) = 0 THEN 'RETURNED'
    ELSE 'COMPLETED'
  END AS order_status,
  1850.0 AS gross_order_value,
  CASE
    WHEN MOD(i, 5) = 0 THEN 0.0
    ELSE 1850.0
  END AS amt_net_settled_sgd,
  CASE
    WHEN i BETWEEN 1 AND 320 THEN 200.0
    WHEN i BETWEEN 501 AND 636 THEN 1000.0
    WHEN i BETWEEN 701 AND 832 THEN 1000.0
    ELSE 0.0
  END AS net_contribution_sgd
FROM UNNEST(GENERATE_ARRAY(1, 1000)) AS i;

-- R2 blind trap:
--   - 42% of rows have NULL country_code and promo_tier
--   - Naive GROUP BY market_segment blames Malaysia Mobile at 68.0%
CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_dw.campaign_returns_staging` AS
SELECT
  FORMAT('RET-RAW-%03d', i) AS return_id,
  CASE
    WHEN i <= 42 THEN CAST(NULL AS STRING)
    WHEN i <= 68 THEN 'MY'
    WHEN i <= 89 THEN 'SG'
    ELSE 'SG'
  END AS country_code,
  CASE
    WHEN i <= 42 THEN CAST(NULL AS STRING)
    WHEN i <= 89 THEN 'PROMO_TRIAL'
    ELSE 'STANDARD'
  END AS promo_tier,
  CASE
    WHEN i <= 68 THEN 'Malaysia Mobile'
    WHEN i <= 89 THEN 'Singapore Paid Social'
    ELSE 'B2B / Search'
  END AS market_segment,
  1000.0 AS return_sgd
FROM UNNEST(GENERATE_ARRAY(1, 100)) AS i;

-- R3 blind trap:
--   - 1:N multi-touch ad clicks per order; flat join fans order contribution
--     from 332,000.00 -> 592,000.00 (SG PS 316K, B2B 138K, MY PS 138K)
CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_dw.campaign_clicks_raw` AS
SELECT
  FORMAT('CLK-RAW-%05d', ROW_NUMBER() OVER (ORDER BY o.order_id, click_seq)) AS click_id,
  o.order_id,
  o.channel,
  DATE_SUB(o.order_date, INTERVAL click_seq - 1 DAY) AS click_date
FROM `${PROJECT_ID}.cymbal_dw.campaign_orders` AS o
CROSS JOIN UNNEST(GENERATE_ARRAY(1, 5)) AS click_seq
WHERE click_seq <= (
  CASE
    WHEN CAST(SUBSTR(o.order_id, 9) AS INT64) BETWEEN 1 AND 300 THEN 5
    WHEN CAST(SUBSTR(o.order_id, 9) AS INT64) BETWEEN 301 AND 320 THEN 4
    WHEN CAST(SUBSTR(o.order_id, 9) AS INT64) IN (501, 502) THEN 2
    WHEN CAST(SUBSTR(o.order_id, 9) AS INT64) BETWEEN 701 AND 706 THEN 2
    ELSE 1
  END
);

-- R3 blind campaign spend (400,000.00 SGD total: 220K SG PS, 80K B2B, 100K MY PS)
CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_dw.campaign_spend` AS
SELECT 'CMP-SG-PS-Q3' AS campaign_id, 'SG Paid Social' AS channel, 220000.0 AS spend_sgd
UNION ALL
SELECT 'CMP-B2B-Q3' AS campaign_id, 'B2B / Search' AS channel, 80000.0 AS spend_sgd
UNION ALL
SELECT 'CMP-MY-PS-Q3' AS campaign_id, 'MY Paid Social' AS channel, 100000.0 AS spend_sgd;

-- R4 blind trap:
--   - Exact duplicate email check finds only 14 accounts / SGD 2,800.00 coupons
--   - 640 single-use @example.com burner accounts (SGD 96,000.00) look unique by email
CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_dw.promo_redemptions_raw` AS
SELECT
  FORMAT('PRM-RAW-%04d', i) AS redemption_id,
  CASE
    WHEN i <= 28 THEN FORMAT('repeat_promo_%02d@example.com', MOD(i - 1, 14) + 1)
    ELSE FORMAT('promo_user_%04d@example.com', i - 28)
  END AS customer_email,
  'SG' AS country_code,
  TRUE AS promo_redeemed,
  CASE
    WHEN i <= 28 THEN 100.0
    ELSE 150.0
  END AS coupon_discount_sgd
FROM UNNEST(GENERATE_ARRAY(1, 668)) AS i;

-- R5 blind trap:
--   - Booked non-refundable ERP invoices totaling 220,000.00 with 0.00 recoverable
CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_dw.erp_agency_invoices` AS
SELECT 'INV-Q3-001' AS invoice_id, 'Apex Digital' AS agency_name, 'SG' AS market, 'PAID_SOCIAL' AS channel, 80000.0 AS billed_media_sgd, 0.0 AS recoverable_sgd, 'BOOKED_NON_REFUNDABLE' AS payment_status
UNION ALL
SELECT 'INV-Q3-002' AS invoice_id, 'Apex Digital' AS agency_name, 'SG' AS market, 'PAID_SOCIAL' AS channel, 75000.0 AS billed_media_sgd, 0.0 AS recoverable_sgd, 'BOOKED_NON_REFUNDABLE' AS payment_status
UNION ALL
SELECT 'INV-Q3-003' AS invoice_id, 'Apex Digital' AS agency_name, 'SG' AS market, 'PAID_SOCIAL' AS channel, 65000.0 AS billed_media_sgd, 0.0 AS recoverable_sgd, 'BOOKED_NON_REFUNDABLE' AS payment_status;

-- R6 blind trap:
--   - 13 Q3 weeks x 3 channels where naive extrapolation produces SGD 2,840,000.00
--     from raw Q3 gross sales totaling SGD 1,850,000.00
CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_dw.q3_weekly_gross_raw` AS
SELECT
  w AS week_num,
  DATE_ADD(DATE '2026-07-06', INTERVAL (w - 1) * 7 DAY) AS week_start,
  ch.channel,
  CASE
    WHEN ch.channel = 'SG Paid Social' THEN 80000.0
    WHEN ch.channel = 'MY Paid Social' THEN 40000.0
    WHEN w = 13 THEN 26000.0
    ELSE 22000.0
  END AS q3_gross_sales_sgd,
  CASE
    WHEN ch.channel = 'SG Paid Social' THEN 120000.0
    WHEN ch.channel = 'MY Paid Social' THEN 60000.0
    WHEN w = 13 THEN 44000.0
    ELSE 38000.0
  END AS naive_projected_q4_sgd
FROM UNNEST(GENERATE_ARRAY(1, 13)) AS w
CROSS JOIN (
  SELECT 'SG Paid Social' AS channel
  UNION ALL
  SELECT 'MY Paid Social' AS channel
  UNION ALL
  SELECT 'B2B / Search' AS channel
) AS ch;

-- ============================================================================
-- 2. GOVERNED / CERTIFIED TABLES (${PROJECT_ID}.cymbal_commerce)
-- ============================================================================

-- R1 governed table:
--   - 910 PAID_CAMPAIGN rows (ex-GST) + 90 ORGANIC rows
--   - PAID_CAMPAIGN sums:
--       attributed_ex_gst_sgd      = 860,000.00 (450K SG PS + 230K MY PS + 180K B2B)
--       return_value_sgd           = 240,000.00 (198K SG PS + 30K MY PS + 12K B2B)
--       net_attributed_settled_sgd = 620,000.00
CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_commerce.campaign_orders` (
  order_id STRING OPTIONS(description="Unique order identifier."),
  campaign_quarter STRING OPTIONS(description="Fiscal quarter tag ('FY26_Q3')."),
  order_date DATE OPTIONS(description="Order booking date in SGT."),
  country_code STRING OPTIONS(description="ISO-3166-1 alpha-2 market code: SG or MY."),
  channel STRING OPTIONS(description="Attributed marketing channel: SG Paid Social, MY Paid Social, or B2B / Search."),
  attribution_type STRING OPTIONS(description="Attribution classification: PAID_CAMPAIGN or ORGANIC. Filter PAID_CAMPAIGN for Net Campaign Revenue."),
  attributed_ex_gst_sgd FLOAT64 OPTIONS(description="Gross attributed order value in SGD excluding 9% GST."),
  return_value_sgd FLOAT64 OPTIONS(description="Pre-refund return exposure in SGD preserved even after refund settlement."),
  net_attributed_settled_sgd FLOAT64 OPTIONS(description="Governed Net Campaign Revenue in SGD (ex-GST, net of returns) for PAID_CAMPAIGN orders.")
)
OPTIONS(description="Governed Q3 campaign orders table with ex-GST attribution and preserved return exposure.")
AS
SELECT
  FORMAT('ORD-GOV-%04d', i) AS order_id,
  'FY26_Q3' AS campaign_quarter,
  DATE_ADD(DATE '2026-07-01', INTERVAL MOD(i * 7, 90) DAY) AS order_date,
  CASE
    WHEN i <= 500 THEN 'SG'
    WHEN i <= 730 THEN 'MY'
    WHEN i <= 738 THEN 'SG'
    WHEN i <= 742 THEN 'MY'
    WHEN i <= 830 THEN 'SG'
    WHEN i <= 910 THEN 'MY'
    ELSE 'SG'
  END AS country_code,
  CASE
    WHEN i <= 500 THEN 'SG Paid Social'
    WHEN i <= 730 THEN 'MY Paid Social'
    WHEN i <= 910 THEN 'B2B / Search'
    ELSE 'Organic Direct'
  END AS channel,
  CASE
    WHEN i <= 910 THEN 'PAID_CAMPAIGN'
    ELSE 'ORGANIC'
  END AS attribution_type,
  CASE
    WHEN i <= 500 THEN 900.0
    WHEN i <= 730 THEN 1000.0
    WHEN i <= 910 THEN 1000.0
    ELSE 5000.0
  END AS attributed_ex_gst_sgd,
  CASE
    WHEN i BETWEEN 1 AND 220 THEN 900.0
    WHEN i BETWEEN 501 AND 530 THEN 1000.0
    WHEN i BETWEEN 731 AND 742 THEN 1000.0
    ELSE 0.0
  END AS return_value_sgd,
  CASE
    WHEN i <= 500 THEN 900.0 - (CASE WHEN i <= 220 THEN 900.0 ELSE 0.0 END)
    WHEN i <= 730 THEN 1000.0 - (CASE WHEN i <= 530 THEN 1000.0 ELSE 0.0 END)
    WHEN i <= 910 THEN 1000.0 - (CASE WHEN i <= 742 THEN 1000.0 ELSE 0.0 END)
    ELSE 5000.0
  END AS net_attributed_settled_sgd
FROM UNNEST(GENERATE_ARRAY(1, 1000)) AS i;

-- R2 governed certified returns table (0% NULLs):
--   - Q3 rows (is_q3 = TRUE): 240 rows totaling 240,000.00 SGD
--       198,000.00 SG Paid Social (82.5% share, 44.0% channel rate, 91% promo, +162K vs Q2 36K)
--        30,000.00 MY Paid Social (12.5% share, 13.0% channel rate, 18% promo)
--        12,000.00 B2B / Search   ( 5.0% share,  6.7% channel rate: 8K SG + 4K MY, 4% promo)
--   - Q2 baseline rows (is_q3 = FALSE): 36 SG Paid Social rows totaling 36,000.00 SGD
CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_commerce.campaign_returns_certified` (
  return_id STRING OPTIONS(description="Unique certified return identifier."),
  is_q3 BOOL OPTIONS(description="TRUE for Q3 FY26, FALSE for Q2 FY26 baseline."),
  country_code STRING OPTIONS(description="ISO-3166-1 alpha-2 market code (0% NULL): SG or MY."),
  channel STRING OPTIONS(description="Certified marketing channel."),
  segment_label STRING OPTIONS(description="Certified segment label for root-cause driver grouping."),
  promo_tier STRING OPTIONS(description="Certified promo usage tier (0% NULL)."),
  device_type STRING OPTIONS(description="Originating device category."),
  return_value_sgd FLOAT64 OPTIONS(description="Certified ex-GST return amount in SGD."),
  channel_gross_attributed_sgd FLOAT64 OPTIONS(description="Denominator gross attributed channel sales in SGD for return rate."),
  promo_usage_pct FLOAT64 OPTIONS(description="Channel promotional code usage percentage.")
)
OPTIONS(description="Knowledge Catalog CERTIFIED Data Product (0% NULL) for Q3 vs. Q2 return root-cause analysis.")
AS
SELECT
  FORMAT('RET-CERT-%03d', i) AS return_id,
  i <= 240 AS is_q3,
  CASE
    WHEN i <= 198 THEN 'SG'
    WHEN i <= 228 THEN 'MY'
    WHEN i <= 236 THEN 'SG'
    WHEN i <= 240 THEN 'MY'
    ELSE 'SG'
  END AS country_code,
  CASE
    WHEN i <= 198 THEN 'SG Paid Social'
    WHEN i <= 228 THEN 'MY Paid Social'
    WHEN i <= 240 THEN 'B2B / Search'
    ELSE 'SG Paid Social'
  END AS channel,
  CASE
    WHEN i <= 198 THEN 'SG Paid Social Promo-Trial'
    WHEN i <= 228 THEN 'MY Paid Social'
    WHEN i <= 240 THEN 'B2B / Search'
    ELSE 'SG Paid Social Promo-Trial'
  END AS segment_label,
  CASE
    WHEN i <= 198 THEN 'PROMO_TRIAL'
    WHEN i <= 228 THEN 'STANDARD'
    WHEN i <= 240 THEN 'CORPORATE'
    ELSE 'STANDARD'
  END AS promo_tier,
  CASE
    WHEN MOD(i, 2) = 0 THEN 'MOBILE'
    ELSE 'WEB'
  END AS device_type,
  1000.0 AS return_value_sgd,
  CASE
    WHEN i <= 198 THEN 450000.0
    WHEN i <= 228 THEN 230000.0
    WHEN i <= 240 THEN 180000.0
    ELSE 450000.0
  END AS channel_gross_attributed_sgd,
  CASE
    WHEN i <= 198 THEN 91.0
    WHEN i <= 228 THEN 18.0
    WHEN i <= 240 THEN 4.0
    ELSE 18.0
  END AS promo_usage_pct
FROM UNNEST(GENERATE_ARRAY(1, 276)) AS i;

-- R3 governed order-grain contribution table (sum = 332,000.00 SGD):
--   - SG Paid Social:  64,000.00 (64,000 - 220,000 spend = -156,000.00)
--   - B2B / Search:   136,000.00 (136,000 - 80,000 spend =  +56,000.00)
--   - MY Paid Social: 132,000.00 (132,000 - 100,000 spend = +32,000.00)
CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_commerce.channel_pnl_orders` AS
SELECT
  order_id,
  channel,
  net_contribution_sgd
FROM `${PROJECT_ID}.cymbal_dw.campaign_orders`;

-- R3 governed campaign-grain spend table (sum = 400,000.00 SGD)
CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_commerce.channel_pnl_spend` AS
SELECT
  campaign_id,
  channel,
  spend_sgd
FROM `${PROJECT_ID}.cymbal_dw.campaign_spend`;

-- R4 governed Fraud Graph node & edge tables:
--   - 28 spoofed devices -> 640 burner accounts (499 returned = exact 78%)
--     -> 640 promos x 150 SGD = 96,000.00 SGD -> shared cards -> shared addresses
CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_commerce.fraud_devices` AS
SELECT
  FORMAT('DEV-SPOOF-%02d', d) AS device_id,
  FORMAT('SUBNET-%d', MOD(d - 1, 3) + 1) AS emulator_subnet,
  'SG' AS country_code
FROM UNNEST(GENERATE_ARRAY(1, 28)) AS d;

CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_commerce.fraud_accounts` AS
SELECT
  FORMAT('ACCT-BRN-%03d', a) AS account_id,
  FORMAT('burner_%03d@example.com', a) AS account_email,
  'SG' AS country_code,
  a <= 499 AS is_returned
FROM UNNEST(GENERATE_ARRAY(1, 640)) AS a;

CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_commerce.fraud_promos` AS
SELECT
  FORMAT('PRM-RING-%03d', p) AS promo_id,
  'SG_TRIAL_150' AS campaign_code,
  150.0 AS coupon_sgd
FROM UNNEST(GENERATE_ARRAY(1, 640)) AS p;

CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_commerce.fraud_cards` AS
SELECT
  FORMAT('CARD-SHR-%02d', c) AS card_id,
  'VIRTUAL_PREPAID' AS card_type
FROM UNNEST(GENERATE_ARRAY(1, 56)) AS c;

CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_commerce.fraud_addresses` AS
SELECT
  FORMAT('ADDR-DRP-%02d', addr) AS address_id,
  'SG' AS country_code
FROM UNNEST(GENERATE_ARRAY(1, 14)) AS addr;

CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_commerce.edge_device_account` AS
SELECT
  FORMAT('EDA-%03d', a) AS edge_id,
  FORMAT('DEV-SPOOF-%02d', MOD(a - 1, 28) + 1) AS device_id,
  FORMAT('ACCT-BRN-%03d', a) AS account_id
FROM UNNEST(GENERATE_ARRAY(1, 640)) AS a;

CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_commerce.edge_account_promo` AS
SELECT
  FORMAT('EAP-%03d', a) AS edge_id,
  FORMAT('ACCT-BRN-%03d', a) AS account_id,
  FORMAT('PRM-RING-%03d', a) AS promo_id
FROM UNNEST(GENERATE_ARRAY(1, 640)) AS a;

CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_commerce.edge_account_card` AS
SELECT
  FORMAT('EAC-%03d', a) AS edge_id,
  FORMAT('ACCT-BRN-%03d', a) AS account_id,
  FORMAT('CARD-SHR-%02d', MOD(a - 1, 56) + 1) AS card_id
FROM UNNEST(GENERATE_ARRAY(1, 640)) AS a;

CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_commerce.edge_card_address` AS
SELECT
  FORMAT('ECA-%02d', c) AS edge_id,
  FORMAT('CARD-SHR-%02d', c) AS card_id,
  FORMAT('ADDR-DRP-%02d', MOD(c - 1, 14) + 1) AS address_id
FROM UNNEST(GENERATE_ARRAY(1, 56)) AS c;

-- R5 governed contract stand-in table (illustrative pre-computed stand-in for Object Table + AI.GENERATE extraction)
CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_commerce.agency_msa_clause_7_4` AS
SELECT
  'Apex Digital' AS agency_name,
  'Addendum #2 Clause 7.4' AS clause_ref,
  15.0 AS invalid_threshold_pct,
  100.0 AS refund_rate_pct,
  'gs://example-cymbal-legal/Agency_Media_MSA_Addendum_2.pdf' AS source_doc_path,
  480 AS extraction_tokens;

-- R6 governed Q4 forecast stand-in table (illustrative pre-computed stand-in for TimesFM 3.0 AI.FORECAST + Q4 reallocation plan)
-- Totals:
--   planned_q4_spend_sgd                = 600,000.00 (512,000.00 net new cash after 88K clawback)
--   projected_q4_net_rev_sgd            = 1,420,000.00 (90% band: 1,310,000.00 - 1,540,000.00)
--   projected_q4_profit_sgd             = 258,000.00 (+43.0% ROI)
--   unchanged_counterfactual_profit_sgd = -145,000.00
CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_commerce.q4_forecast` AS
SELECT
  'B2B / Search' AS channel,
  260000.0 AS planned_q4_spend_sgd,
  0.0 AS agency_clawback_offset_sgd,
  620000.0 AS projected_q4_net_rev_sgd,
  570000.0 AS projected_q4_rev_low_sgd,
  670000.0 AS projected_q4_rev_high_sgd,
  169000.0 AS projected_q4_profit_sgd,
  84000.0 AS unchanged_counterfactual_profit_sgd
UNION ALL
SELECT
  'MY Paid Social' AS channel,
  220000.0 AS planned_q4_spend_sgd,
  0.0 AS agency_clawback_offset_sgd,
  480000.0 AS projected_q4_net_rev_sgd,
  445000.0 AS projected_q4_rev_low_sgd,
  515000.0 AS projected_q4_rev_high_sgd,
  66000.0 AS projected_q4_profit_sgd,
  48000.0 AS unchanged_counterfactual_profit_sgd
UNION ALL
SELECT
  'Clean SG Paid Social' AS channel,
  120000.0 AS planned_q4_spend_sgd,
  88000.0 AS agency_clawback_offset_sgd,
  320000.0 AS projected_q4_net_rev_sgd,
  295000.0 AS projected_q4_rev_low_sgd,
  355000.0 AS projected_q4_rev_high_sgd,
  23000.0 AS projected_q4_profit_sgd,
  -277000.0 AS unchanged_counterfactual_profit_sgd;

-- ============================================================================
-- 3. REGIONAL COPY OF AWS S3 CLICK LOG (${PROJECT_ID}.cymbal_lake)
-- ============================================================================

-- R5 governed S3 click log:
--   - 1,420,000 rows via 1,420 x 1,000 array cross-join (avoids BigQuery's 1,048,576
--     single GENERATE_ARRAY limit while numbering click_num 1..1,420,000)
--   - MOD(click_num, 5) < 2 marks exact 40.0% (568,000 rows) as invalid (is_valid_human = FALSE)
--   - billed_media_sgd = 220000.0 / 1420000.0 -> invalid sum = exact 88,000.00 SGD
CREATE OR REPLACE TABLE `${PROJECT_ID}.cymbal_lake.q3_paid_social_clicks` AS
SELECT
  'SG' AS country_code,
  MOD(((chunk - 1) * 1000 + offset_idx), 5) >= 2 AS is_valid_human,
  220000.0 / 1420000.0 AS billed_media_sgd
FROM UNNEST(GENERATE_ARRAY(1, 1420)) AS chunk
CROSS JOIN UNNEST(GENERATE_ARRAY(1, 1000)) AS offset_idx;
