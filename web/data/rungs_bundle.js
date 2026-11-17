window.CONTEXT_PACK_BUNDLE = {
  "schema_version": "2.0",
  "pack_id": "meridian_q3_sgd",
  "title": "Meridian Commerce · Closed Q3 Context Benchmark",
  "subtitle": "6-Rung Enterprise Context Progression in BigQuery & Knowledge Catalog (SGD)",
  "hero_tagline": "Frontier models are table stakes—governed enterprise context is the differentiator.",
  "closed_period_label": "Closed Q3 (2026-07-01 to 2026-09-30)",
  "currency": "SGD",
  "region": "asia-southeast1",
  "rng_seed": 20261126,
  "generated_mode": "live_gcp_verified",
  "personas": [
    {
      "id": "cfo_regional",
      "label": "Regional CFO (SEA)",
      "principal_display": "cfo-regional@example-project-id.iam.gserviceaccount.com",
      "scope_summary": "Unrestricted regional visibility across SG, MY, TH, and ID certified Cold-Chain Data Products."
    },
    {
      "id": "sg_coldchain",
      "label": "SG Cold-Chain Ops Lead",
      "principal_display": "sg-coldchain@example-project-id.iam.gserviceaccount.com",
      "scope_summary": "Row-Level Security restricted strictly to country_code = 'SG' across certified Cold-Chain margins."
    }
  ],
  "invariants": {
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
    "r6_governed_quarterly_cap_sgd": 35000.0
  },
  "horizon_cards": [
    {
      "id": "knowledge_studio",
      "title": "Knowledge Studio (Context Sets & Enrichment Agent)",
      "release_badge": "Preview",
      "region_availability": "US / EU multi-regions (Preview; not yet in asia-southeast1)",
      "summary": "Curates domain Context Sets and deploys the Enrichment Agent inside Knowledge Catalog to bootstrap glossary bindings, verified queries, and semantic descriptions. Kept strictly decoupled from R1–R6 production scope in asia-southeast1 until regional GA availability.",
      "primitives": [
        "Knowledge Catalog",
        "Knowledge Studio Context Sets",
        "Enrichment Agent"
      ]
    },
    {
      "id": "open_lakehouse_federation",
      "title": "Cross-Cloud Lakehouse Catalog Federation",
      "release_badge": "GA",
      "region_availability": "GA (Multi-region & asia-southeast1 via BigQuery / Knowledge Catalog)",
      "summary": "Federates external Iceberg and Delta lakehouse catalogs directly into Knowledge Catalog and BigQuery governance with distinct cloud-native identity delegation models: Databricks Unity Catalog via per-user OIDC (GA), Snowflake Horizon Catalog via Workload Identity Federation (GA—never per-user OIDC), and AWS Glue Data Catalog via IAM role delegation (GA).",
      "primitives": [
        "Knowledge Catalog",
        "Databricks Unity Catalog (per-user OIDC)",
        "Snowflake Horizon Catalog (Workload Identity Federation)",
        "AWS Glue Data Catalog (IAM role delegation)"
      ]
    }
  ],
  "rungs": [
    {
      "id": "r1_schema",
      "rung_num": 1,
      "short_label": "R1 · Schema",
      "title": "Schema Enrichment & Data Insights",
      "pyramid_layer": "Layers 1–2 · Physical Schema, Column Descriptions & Data Insights",
      "release_badges": [
        {
          "capability": "BigQuery Schema + Data Insights",
          "stage": "GA",
          "region_scope": "asia-southeast1"
        },
        {
          "capability": "Knowledge Catalog lookupContext",
          "stage": "Preview",
          "region_scope": "Global / Preview"
        }
      ],
      "question": "What was Singapore's Closed Q3 Net Realized Revenue?",
      "poll": {
        "prompt": "Myth-Buster #1: If we point a frontier model directly at our clean BigQuery `orders` schema, how accurately does it answer Q3 Net Realized Revenue?",
        "options": [
          {
            "key": "A",
            "text": "5/5 — Frontier reasoning models automatically infer ex-GST and completed-order rules from column names."
          },
          {
            "key": "B",
            "text": "0/5 — Without column descriptions and Data Insights predicates, it sums gross_total_sgd including 9% GST and cancelled orders (+28% inflation)."
          },
          {
            "key": "C",
            "text": "3/5 — It fails only because SQL syntax is wrong in BigQuery Standard SQL."
          },
          {
            "key": "D",
            "text": "It refuses to run SQL unless LookML is deployed first."
          }
        ],
        "correct_key": "B",
        "reveal_takeaway": "Syntax is easy; financial semantics are invisible in raw column names. Enriched column descriptions plus Data Insights eliminate GST and cancelled-order overcounting (+SGD 371,750 false inflation), lifting eval accuracy from 0/5 to 4/5."
      },
      "blind": {
        "answer_headline": "SGD 1,684,200.00",
        "answer_detail": "Overstated by SGD 371,750.00 (+28.3%) because the blind agent summed gross_total_sgd (including 9% Singapore GST) across all SG rows including CANCELLED and RETURNED orders.",
        "numeric_value": 1684200.0,
        "unit": "SGD",
        "query_language": "SQL",
        "context_mechanism": "Raw BigQuery DDL only (no column descriptions, no Data Insights predicates)",
        "context_payload": "Table: example-project-id.meridian_commerce.orders\nColumns exposed without descriptions:\n  order_id STRING, country_code STRING, order_date DATE,\n  order_status STRING, gross_item_sgd FLOAT64, gross_total_sgd FLOAT64,\n  gst_sgd FLOAT64, net_realized_revenue_sgd FLOAT64\n",
        "sql_or_gql": "SELECT\n  ROUND(SUM(gross_total_sgd), 2) AS gross_total_sgd,\n  COUNT(*) AS order_count\nFROM `example-project-id.meridian_commerce.orders`\nWHERE country_code = 'SG'\n  AND order_date BETWEEN DATE '2026-07-01' AND DATE '2026-09-30'\n",
        "tokens_used": 3120,
        "exploratory_queries": 5,
        "error_retries": 2,
        "eval_pass_count": 0,
        "eval_total_runs": 5,
        "trust_tier": "TIER_3_REVIEW_REQUIRED",
        "rationale": "Ungrounded scan over gross_total_sgd without order_status = 'COMPLETED' or ex-GST semantics."
      },
      "governed": {
        "answer_headline": "SGD 1,312,450.00",
        "answer_detail": "Exact Singapore Closed Q3 Net Realized Revenue across 3,400 COMPLETED orders (ex-GST, net of returns), reconciled to 0.00 SGD drift against order_lines.net_line_revenue_sgd.",
        "numeric_value": 1312450.0,
        "unit": "SGD",
        "query_language": "SQL",
        "context_mechanism": "BigQuery Column OPTIONS(description) + Data Insights Predicates + Knowledge Catalog lookupContext (Preview)",
        "context_payload": "{\n  \"lookup_context_stage\": \"Preview\",\n  \"table\": \"example-project-id.meridian_commerce.orders\",\n  \"column_descriptions\": {\n    \"gross_total_sgd\": \"Gross invoice total INCLUDING 9% SG GST and unadjusted for cancellations/returns. Do NOT report as net realized revenue.\",\n    \"net_realized_revenue_sgd\": \"Governed Net Realized Revenue in SGD: ex-GST, net of returns, 0.00 for CANCELLED/RETURNED orders.\"\n  },\n  \"data_insights_predicate\": \"country_code = 'SG' AND order_status = 'COMPLETED' AND order_date BETWEEN DATE '2026-07-01' AND DATE '2026-09-30'\"\n}\n",
        "sql_or_gql": "SELECT\n  ROUND(SUM(o.net_realized_revenue_sgd), 2) AS net_realized_revenue_sgd,\n  COUNT(*) AS completed_order_count\nFROM `example-project-id.meridian_commerce.orders` AS o\nWHERE o.country_code = 'SG'\n  AND o.order_status = 'COMPLETED'\n  AND o.order_date BETWEEN DATE '2026-07-01' AND DATE '2026-09-30'\n",
        "tokens_used": 980,
        "exploratory_queries": 1,
        "error_retries": 0,
        "eval_pass_count": 4,
        "eval_total_runs": 5,
        "trust_tier": "TIER_2_GROUNDED",
        "rationale": "Grounded via column descriptions and Data Insights filter predicates (4/5 pass; remaining 1/5 edge risk motivates R2 Glossary governance)."
      },
      "xray_summary": {
        "context_added": "Enriched BigQuery column OPTIONS(description), PK/FK NOT ENFORCED metadata, Data Insights Q3 predicates, and Knowledge Catalog lookupContext (Preview).",
        "gcp_primitives": [
          "BigQuery Schema & Column Descriptions (GA)",
          "BigQuery Data Insights (GA)",
          "Knowledge Catalog lookupContext (Preview)"
        ],
        "negative_control_assertion": "Unannotated orders scan triggers blind inflation (+28.3% GST/cancellation error) and classifies as TIER_3_REVIEW_REQUIRED."
      }
    },
    {
      "id": "r2_glossary",
      "rung_num": 2,
      "short_label": "R2 · Glossary",
      "title": "Knowledge Catalog Business Glossary",
      "pyramid_layer": "Layer 4 · Knowledge Catalog Business Glossary (GA)",
      "release_badges": [
        {
          "capability": "Knowledge Catalog Business Glossary",
          "stage": "GA",
          "region_scope": "asia-southeast1"
        }
      ],
      "question": "Which sales channel led Closed Q3 Singapore Premier segment AOV?",
      "poll": {
        "prompt": "Myth-Buster #2: When a customer table has a column called `segment_label` containing `'Premier_Promo_Trial'`, what happens without a governed Business Glossary?",
        "options": [
          {
            "key": "A",
            "text": "The model reads our finance committee policy from memory and skips promo rows."
          },
          {
            "key": "B",
            "text": "It filters segment_label LIKE '%Premier%', crowning Mobile App (SGD 284.10) instead of true PRM_HV leader B2B Corporate Portal (SGD 612.50)."
          },
          {
            "key": "C",
            "text": "BigQuery throws a compilation error on LIKE '%Premier%'."
          },
          {
            "key": "D",
            "text": "Both queries return the exact same winning channel."
          }
        ],
        "correct_key": "B",
        "reveal_takeaway": "Marketing labels are not financial definitions. Binding 'Premier Customer' in Knowledge Catalog Business Glossary to tier_code = 'PRM_HV' (spend >= SGD 5,000 and return_rate < 0.08) recovers B2B Corporate Portal at SGD 612.50 AOV across 240 orders (overall SG PRM_HV AOV SGD 495.63 across 640 orders)."
      },
      "blind": {
        "answer_headline": "Mobile App (SGD 284.10)",
        "answer_detail": "Wrong channel and -53.6% understated AOV: filtering segment_label LIKE '%Premier%' swept in 260 low-value 'Premier_Promo_Trial' mobile/web coupon orders while excluding Enterprise_Corporate B2B Premier accounts.",
        "numeric_value": 284.1,
        "unit": "SGD",
        "query_language": "SQL",
        "context_mechanism": "Unresolved string heuristic (`segment_label LIKE '%Premier%'`)",
        "context_payload": "No Business Glossary term bound for \"Premier Customer\".\nAgent inferred predicate from sample values in customers.segment_label:\n  'Premier_Promo_Trial', 'Premier_Loyalty', 'Enterprise_Corporate', 'Enterprise_Direct'\n",
        "sql_or_gql": "SELECT\n  ROUND(AVG(o.net_realized_revenue_sgd), 2) AS aov_sgd,\n  o.sales_channel,\n  COUNT(*) AS order_count\nFROM `example-project-id.meridian_commerce.orders` AS o\nJOIN `example-project-id.meridian_commerce.customers` AS c\n  ON o.customer_id = c.customer_id\nWHERE o.country_code = 'SG'\n  AND o.order_status = 'COMPLETED'\n  AND o.order_date BETWEEN DATE '2026-07-01' AND DATE '2026-09-30'\n  AND c.segment_label LIKE '%Premier%'\nGROUP BY o.sales_channel\nORDER BY aov_sgd DESC\nLIMIT 1\n",
        "tokens_used": 2640,
        "exploratory_queries": 4,
        "error_retries": 1,
        "eval_pass_count": 0,
        "eval_total_runs": 5,
        "trust_tier": "TIER_3_REVIEW_REQUIRED",
        "rationale": "Conflates legacy marketing campaign tag 'Premier_Promo_Trial' with official Premier Customer cohort."
      },
      "governed": {
        "answer_headline": "B2B Corporate Portal (SGD 612.50)",
        "answer_detail": "B2B Corporate Portal led with SGD 612.50 AOV across 240 orders (SGD 147,000.00), within the 640 total SG PRM_HV completed orders averaging SGD 495.63 (SGD 317,203.20 total).",
        "numeric_value": 612.5,
        "unit": "SGD",
        "query_language": "SQL",
        "context_mechanism": "Knowledge Catalog Business Glossary Term Binding (`Premier Customer` -> `tier_code = 'PRM_HV'`)",
        "context_payload": "{\n  \"glossary\": \"meridian_enterprise_glossary\",\n  \"term\": \"Premier Customer\",\n  \"canonical_predicate\": \"c.tier_code = 'PRM_HV' AND c.trailing_12m_spend_sgd >= 5000.00 AND c.return_rate < 0.08\",\n  \"excluded_distractors\": [\"segment_label LIKE '%Premier%'\", \"PRM_TRIAL\"],\n  \"steward\": \"Regional Finance & Revenue Governance\"\n}\n",
        "sql_or_gql": "SELECT\n  ROUND(AVG(o.net_realized_revenue_sgd), 2) AS aov_sgd,\n  o.sales_channel,\n  COUNT(*) AS order_count,\n  ROUND(SUM(o.net_realized_revenue_sgd), 2) AS total_net_revenue_sgd\nFROM `example-project-id.meridian_commerce.orders` AS o\nJOIN `example-project-id.meridian_commerce.customers` AS c\n  ON o.customer_id = c.customer_id\nWHERE o.country_code = 'SG'\n  AND o.order_status = 'COMPLETED'\n  AND o.order_date BETWEEN DATE '2026-07-01' AND DATE '2026-09-30'\n  AND c.tier_code = 'PRM_HV'\n  AND c.trailing_12m_spend_sgd >= 5000.00\n  AND c.return_rate < 0.08\nGROUP BY o.sales_channel\nORDER BY aov_sgd DESC\nLIMIT 1\n",
        "tokens_used": 760,
        "exploratory_queries": 1,
        "error_retries": 0,
        "eval_pass_count": 5,
        "eval_total_runs": 5,
        "trust_tier": "TIER_2_GROUNDED",
        "rationale": "Resolves canonical Business Glossary term Premier Customer deterministically to tier_code = 'PRM_HV' (5/5 pass)."
      },
      "xray_summary": {
        "context_added": "Knowledge Catalog Business Glossary binding 'Premier Customer' to tier_code = 'PRM_HV' and explicit threshold guardrails.",
        "gcp_primitives": [
          "Knowledge Catalog Business Glossary (GA)",
          "Knowledge Catalog Glossary Term-to-Column Linking (GA)"
        ],
        "negative_control_assertion": "Queries matching segment_label LIKE '%Premier%' fail glossary reconciliation against PRM_HV cohort invariants."
      }
    },
    {
      "id": "r3_metrics",
      "rung_num": 3,
      "short_label": "R3 · Metrics",
      "title": "Grain-Locked Measures & Fan-Trap Elimination",
      "pyramid_layer": "Layer 4 · BigQuery Graph MEASURE() + Verified Query + Semantic Contract",
      "release_badges": [
        {
          "capability": "BigQuery Graph MEASURE()",
          "stage": "GA",
          "region_scope": "asia-southeast1"
        },
        {
          "capability": "Verified Query",
          "stage": "GA",
          "region_scope": "asia-southeast1"
        },
        {
          "capability": "Semantic Contract",
          "stage": "Reference Architecture",
          "region_scope": "Cross-region pattern (LookML excluded from R1–R6)"
        }
      ],
      "question": "What was Singapore's Q3 Same-Day Contribution Margin %?",
      "poll": {
        "prompt": "Myth-Buster #3: Every Same-Day order spans 2 to 4 `parcel_legs` and multiple `order_lines`. What happens when an LLM joins `orders`, `order_lines`, and `parcel_legs` directly?",
        "options": [
          {
            "key": "A",
            "text": "SQL engines automatically deduplicate 1:N joins before running SUM()."
          },
          {
            "key": "B",
            "text": "Cartesian fan-out multiplies order fulfillment fees and parcel leg costs across lines, distorting 31.8% margin down to 14.2%."
          },
          {
            "key": "C",
            "text": "BigQuery rejects a 3-way JOIN unless LookML is attached."
          },
          {
            "key": "D",
            "text": "It only changes row order, never percentages."
          }
        ],
        "correct_key": "B",
        "reveal_takeaway": "The 1:N chasm/fan-trap silently corrupts financial ratios by -17.6 percentage points without throwing any SQL error. BigQuery Graph MEASURE() with GRAPH_EXPAND + AGG() locks every metric to its native PK grain, recovering exact 31.8% (SGD 131,016.00 on SGD 412,000.00)."
      },
      "blind": {
        "answer_headline": "14.2%",
        "answer_detail": "Severely distorted by a 1:N Cartesian chasm trap: joining orders -> order_lines (3 lines) -> parcel_legs (2–4 legs) multiplied fulfillment_fee_sgd up to 12x and leg_cost_sgd 3x.",
        "numeric_value": 14.2,
        "unit": "%",
        "query_language": "SQL",
        "context_mechanism": "Naive 3-way SQL JOIN across mixed order, line, and parcel-leg grains",
        "context_payload": "No semantic grain contract or BigQuery Graph MEASURE() provided.\nAgent joined orders (1) -> order_lines (N) -> parcel_legs (M) in a single flat SELECT.\n",
        "sql_or_gql": "SELECT\n  ROUND(\n    100.0 * (\n      SUM(ol.net_line_revenue_sgd)\n      - SUM(ol.cogs_line_sgd)\n      - SUM(o.fulfillment_fee_sgd)\n      - SUM(pl.leg_cost_sgd)\n    ) / NULLIF(SUM(ol.net_line_revenue_sgd), 0),\n    1\n  ) AS contribution_margin_pct\nFROM `example-project-id.meridian_commerce.orders` AS o\nJOIN `example-project-id.meridian_commerce.order_lines` AS ol\n  ON o.order_id = ol.order_id\nJOIN `example-project-id.meridian_commerce.parcel_legs` AS pl\n  ON o.order_id = pl.order_id\nWHERE o.country_code = 'SG'\n  AND o.order_status = 'COMPLETED'\n  AND o.fulfillment_tier = 'SAME_DAY'\n  AND o.order_date BETWEEN DATE '2026-07-01' AND DATE '2026-09-30'\n",
        "tokens_used": 2910,
        "exploratory_queries": 4,
        "error_retries": 1,
        "eval_pass_count": 0,
        "eval_total_runs": 5,
        "trust_tier": "TIER_3_REVIEW_REQUIRED",
        "rationale": "Un-aggregated 3-way JOIN over 1:N parcel_legs and order_lines triggers silent fan-out overcounting."
      },
      "governed": {
        "answer_headline": "31.8% (SGD 131,016.00)",
        "answer_detail": "Exact Same-Day Contribution Margin of SGD 131,016.00 on SGD 412,000.00 net revenue (31.8%), computed via grain-locked BigQuery Graph MEASURE() definitions and AGG().",
        "numeric_value": 31.8,
        "unit": "%",
        "query_language": "SQL+GQL",
        "context_mechanism": "BigQuery Property Graph MEASURE() + GRAPH_EXPAND AGG() + Verified Query",
        "context_payload": "{\n  \"property_graph\": \"example-project-id.meridian_commerce.meridian_supply_graph\",\n  \"measures\": {\n    \"CustomerOrder\": [\"MEASURE(SUM(net_realized_revenue_sgd)) AS total_net_revenue\", \"MEASURE(SUM(fulfillment_fee_sgd)) AS total_fulfillment_fee\"],\n    \"OrderLine\": [\"MEASURE(SUM(cogs_line_sgd)) AS total_cogs\"],\n    \"ParcelLeg\": [\"MEASURE(SUM(leg_cost_sgd)) AS total_leg_cost\"]\n  },\n  \"semantic_contract\": \"Contribution Margin % = (total_net_revenue - total_cogs - total_fulfillment_fee - total_leg_cost) / total_net_revenue\",\n  \"lookml_in_r1_r6\": false\n}\n",
        "sql_or_gql": "WITH order_line_metrics AS (\n  SELECT\n    CustomerOrder_order_id AS order_id,\n    AGG(CustomerOrder_total_net_revenue) AS net_revenue_sgd,\n    AGG(CustomerOrder_total_fulfillment_fee) AS fulfillment_fee_sgd,\n    AGG(OrderLine_total_cogs) AS cogs_sgd\n  FROM GRAPH_EXPAND(\n    \"example-project-id.meridian_commerce.meridian_supply_graph\",\n    start_node => \"OrderLine\"\n  )\n  WHERE CustomerOrder_country_code = 'SG'\n    AND CustomerOrder_order_status = 'COMPLETED'\n    AND CustomerOrder_fulfillment_tier = 'SAME_DAY'\n    AND CustomerOrder_order_date BETWEEN DATE '2026-07-01' AND DATE '2026-09-30'\n  GROUP BY CustomerOrder_order_id\n),\nparcel_leg_metrics AS (\n  SELECT\n    CustomerOrder_order_id AS order_id,\n    AGG(ParcelLeg_total_leg_cost) AS leg_cost_sgd\n  FROM GRAPH_EXPAND(\n    \"example-project-id.meridian_commerce.meridian_supply_graph\",\n    start_node => \"ParcelLeg\"\n  )\n  WHERE CustomerOrder_country_code = 'SG'\n    AND CustomerOrder_order_status = 'COMPLETED'\n    AND CustomerOrder_fulfillment_tier = 'SAME_DAY'\n    AND CustomerOrder_order_date BETWEEN DATE '2026-07-01' AND DATE '2026-09-30'\n  GROUP BY CustomerOrder_order_id\n)\nSELECT\n  ROUND(\n    100.0 * SUM(\n      olm.net_revenue_sgd - olm.cogs_sgd - olm.fulfillment_fee_sgd - COALESCE(plm.leg_cost_sgd, 0.0)\n    ) / NULLIF(SUM(olm.net_revenue_sgd), 0),\n    1\n  ) AS contribution_margin_pct,\n  ROUND(\n    SUM(olm.net_revenue_sgd - olm.cogs_sgd - olm.fulfillment_fee_sgd - COALESCE(plm.leg_cost_sgd, 0.0)),\n    2\n  ) AS contribution_margin_sgd,\n  ROUND(SUM(olm.net_revenue_sgd), 2) AS net_revenue_sgd\nFROM order_line_metrics AS olm\nLEFT JOIN parcel_leg_metrics AS plm\n  USING (order_id)\n",
        "tokens_used": 620,
        "exploratory_queries": 1,
        "error_retries": 0,
        "eval_pass_count": 5,
        "eval_total_runs": 5,
        "trust_tier": "TIER_1_VERIFIED_OR_COMPILED",
        "rationale": "Compiled via BigQuery Graph MEASURE() + GRAPH_EXPAND AGG() locking order, line, and parcel-leg grains (5/5 pass)."
      },
      "xray_summary": {
        "context_added": "BigQuery Property Graph MEASURE() definitions on CustomerOrder, OrderLine, and ParcelLeg queried via GRAPH_EXPAND(..., start_node) + AGG().",
        "gcp_primitives": [
          "BigQuery Property Graph MEASURE() (GA)",
          "BigQuery GRAPH_EXPAND & AGG() (GA)",
          "Verified Query Template (GA)",
          "Semantic Contract Pattern (Reference Architecture)"
        ],
        "negative_control_assertion": "Direct 3-way relational join fails grain-lock verification and outputs distorted 14.2% margin (TIER_3_REVIEW_REQUIRED)."
      }
    },
    {
      "id": "r4_trust_access",
      "rung_num": 4,
      "short_label": "R4 · Trust & RLS",
      "title": "Certified Data Products, Shadow Sprawl & Row-Level Security",
      "pyramid_layer": "Layers 1 & 5 · Knowledge Catalog Data Products + Auto Data Quality + BigQuery RLS",
      "release_badges": [
        {
          "capability": "Knowledge Catalog Data Products",
          "stage": "GA",
          "region_scope": "asia-southeast1"
        },
        {
          "capability": "Auto Data Quality",
          "stage": "GA",
          "region_scope": "asia-southeast1"
        },
        {
          "capability": "BigQuery RLS & EntryGroup IAM",
          "stage": "GA",
          "region_scope": "asia-southeast1"
        }
      ],
      "question": "Did Cold-Chain Gross Margin really drop 410 bps in Q3—and what does each role see?",
      "poll": {
        "prompt": "Myth-Buster #4: Your dataset has 190 automated clone tables plus `staging_cold_chain_oct11`. Why did a blind agent raise a board panic over a -410 bps cold-chain margin crash?",
        "options": [
          {
            "key": "A",
            "text": "The model hallucinated random numbers without running any query."
          },
          {
            "key": "B",
            "text": "It queried an uncertified Oct 11 staging clone missing late-Q3 supplier rebates (24.3%) instead of the certified Knowledge Catalog Data Product (28.4%)."
          },
          {
            "key": "C",
            "text": "BigQuery deleted the SG rows automatically."
          },
          {
            "key": "D",
            "text": "RLS policies alter gross margin percentages globally."
          }
        ],
        "correct_key": "B",
        "reveal_takeaway": "Real enterprise lakes accumulate hundreds of uncertified staging clones (190 shadow_auto_tbl_* tables here). Knowledge Catalog Data Products + Auto Data Quality route agents exclusively to certified cold_chain_margin_gold (28.4%, -15 bps YoY), while BigQuery RLS enforces identity-scoped visibility (SGD 842,600.00 vs SGD 346,480.00)."
      },
      "blind": {
        "answer_headline": "24.3% (-410 bps drop)",
        "answer_detail": "False executive alarm: blind discovery scanned uncertified staging_cold_chain_oct11 amid 190 shadow_auto_tbl_* tables, missing late-Q3 supplier rebate settlements.",
        "numeric_value": 24.3,
        "unit": "%",
        "query_language": "SQL",
        "context_mechanism": "Uncertified table discovery across 190 shadow clones (`staging_cold_chain_oct11`)",
        "context_payload": "Dataset discovery returned 190 shadow_auto_tbl_* clones + staging_cold_chain_oct11.\nNo Knowledge Catalog Data Product certification or Auto Data Quality gate applied.\n",
        "sql_or_gql": "SELECT\n  ROUND(100.0 * SUM(gross_margin_sgd) / NULLIF(SUM(net_revenue_sgd), 0), 1) AS gross_margin_pct,\n  ROUND(SUM(gross_margin_sgd), 2) AS gross_margin_sgd,\n  COUNT(*) AS rows_scanned\nFROM `example-project-id.meridian_commerce.staging_cold_chain_oct11`\nWHERE quarter = '2026-Q3'\n",
        "tokens_used": 3480,
        "exploratory_queries": 6,
        "error_retries": 1,
        "eval_pass_count": 1,
        "eval_total_runs": 5,
        "trust_tier": "TIER_3_REVIEW_REQUIRED",
        "rationale": "Scanned uncertified staging clone (rebate_settled = FALSE) amid 190 shadow tables."
      },
      "governed": {
        "answer_headline": "28.4% (-15 bps YoY) · SGD 842,600.00",
        "answer_detail": "Certified Knowledge Catalog Data Product cold_chain_margin_gold confirms steady 28.4% gross margin (-15 bps YoY, SGD 842,600.00 across 4 SEA markets; SGD 346,480.00 under SG RLS).",
        "numeric_value": 28.4,
        "unit": "%",
        "query_language": "SQL",
        "context_mechanism": "Knowledge Catalog Certified Data Product + Auto Data Quality + BigQuery Row Access Policies",
        "context_payload": "{\n  \"data_product\": \"Cold-Chain Margin Gold (Certified 2026-10-14T08:30:00Z)\",\n  \"authoritative_table\": \"example-project-id.meridian_commerce.cold_chain_margin_gold\",\n  \"auto_data_quality_assertions\": [\"rebate_settled = TRUE\", \"no_null_country_code\"],\n  \"excluded_clones\": [\"staging_cold_chain_oct11\", \"shadow_auto_tbl_001..190\"],\n  \"row_access_policies\": {\n    \"cfo_regional\": \"rls_cfo_regional_all_markets -> FILTER USING (TRUE)\",\n    \"sg_coldchain\": \"rls_sg_coldchain_country_sg -> FILTER USING (country_code = 'SG')\"\n  }\n}\n",
        "sql_or_gql": "SELECT\n  ROUND(100.0 * SUM(gross_margin_sgd) / NULLIF(SUM(net_revenue_sgd), 0), 1) AS gross_margin_pct,\n  ROUND(SUM(gross_margin_sgd), 2) AS gross_margin_sgd,\n  COUNT(*) AS rows_visible\nFROM `example-project-id.meridian_commerce.cold_chain_margin_gold`\nWHERE quarter = '2026-Q3'\n",
        "tokens_used": 590,
        "exploratory_queries": 1,
        "error_retries": 0,
        "eval_pass_count": 5,
        "eval_total_runs": 5,
        "trust_tier": "TIER_1_VERIFIED_OR_COMPILED",
        "rationale": "Routed strictly to certified Data Product cold_chain_margin_gold with active BigQuery Row Access Policies (5/5 pass)."
      },
      "identity_variants": {
        "cfo_regional": {
          "persona_id": "cfo_regional",
          "answer_headline": "SGD 842,600.00 (4 SEA Markets · 28.4%)",
          "answer_detail": "Regional CFO sees all 4 certified SEA market rows (SG, MY, TH, ID) totaling SGD 842,600.00 gross margin under rls_cfo_regional_all_markets.",
          "numeric_value": 842600.0,
          "rows_visible": 4,
          "rls_policy_applied": "rls_cfo_regional_all_markets",
          "policy_note": "BigQuery Row Access Policy FILTER USING (TRUE) grants full 4-market visibility."
        },
        "sg_coldchain": {
          "persona_id": "sg_coldchain",
          "answer_headline": "SGD 346,480.00 (SG Only · 28.4%)",
          "answer_detail": "SG Cold-Chain Ops Lead executes the exact same SQL query and sees only 1 row (SG) totaling SGD 346,480.00 under rls_sg_coldchain_country_sg.",
          "numeric_value": 346480.0,
          "rows_visible": 1,
          "rls_policy_applied": "rls_sg_coldchain_country_sg",
          "policy_note": "BigQuery Row Access Policy FILTER USING (country_code = 'SG') transparently filters MY/TH/ID rows at storage scan."
        }
      },
      "xray_summary": {
        "context_added": "Knowledge Catalog Data Product certification, Auto Data Quality rebate checks, EntryGroup IAM separation, and BigQuery Row Access Policies.",
        "gcp_primitives": [
          "Knowledge Catalog Data Products (GA)",
          "Knowledge Catalog Auto Data Quality (GA)",
          "BigQuery Row-Level Security (GA)",
          "Knowledge Catalog EntryGroup IAM (GA)"
        ],
        "negative_control_assertion": "Unauthorized principal or staging clone fails policy/certification checks with explicit access denial or TIER_3_REVIEW_REQUIRED downgrade."
      }
    },
    {
      "id": "r5_graph",
      "rung_num": 5,
      "short_label": "R5 · Graph",
      "title": "4-Hop BigQuery Property Graph Lineage (ISO GQL)",
      "pyramid_layer": "Layer 4 · BigQuery Property Graph (CREATE PROPERTY GRAPH + ISO GQL, GA)",
      "release_badges": [
        {
          "capability": "BigQuery Property Graph (ISO GQL + MEASURE())",
          "stage": "GA",
          "region_scope": "asia-southeast1"
        }
      ],
      "question": "Which SG Premier orders & revenue are exposed to delayed Tier-2 Batch #LN-409?",
      "poll": {
        "prompt": "Myth-Buster #5: Batch `#LN-409` sits 4 hops upstream across warehouse lots (`LOT-LN409-01`, `LOT-SG-8841`, `LOT-SG-8842`). What happens when an LLM guesses lineage via string patterns?",
        "options": [
          {
            "key": "A",
            "text": "String matching `lot_id LIKE '%409%'` finds every affected order automatically."
          },
          {
            "key": "B",
            "text": "It catches only 8 Premier_Loyalty orders (SGD 4,120.00) and misses 30 Enterprise orders tied via opaque lot IDs—missing SGD 15,260.00 of the SGD 19,380.00 total."
          },
          {
            "key": "C",
            "text": "ISO GQL requires moving BigQuery tables into a separate graph database."
          },
          {
            "key": "D",
            "text": "SG Premier orders in R5 belong to a different population than R2."
          }
        ],
        "correct_key": "B",
        "reveal_takeaway": "Zero-ETL BigQuery Property Graph traverses ColdChainBatch -> SkuLotAllocation -> OrderLine -> CustomerOrder -> Customer in native ISO GQL, uncovering all 38 SG PRM_HV orders and SGD 19,380.00 exposed revenue (SGD 510.00 AOV)—100% consistent with R2's 640 PRM_HV cohort."
      },
      "blind": {
        "answer_headline": "SGD 4,120.00 (8 orders)",
        "answer_detail": "Missed 78.7% of exposure (SGD 15,260.00 across 30 orders): brittle heuristic filtered lot_id LIKE '%409%' and segment_label LIKE '%Premier%', dropping LOT-SG-8841/8842 and Enterprise PRM_HV accounts.",
        "numeric_value": 4120.0,
        "unit": "SGD",
        "query_language": "SQL",
        "context_mechanism": "Brittle lot-string heuristic (`lot_id LIKE '%409%'`) skipping sku_lot_allocations bridge",
        "context_payload": "No Property Graph edge lineage provided.\nAgent guessed lot_id LIKE '%409%' and segment_label LIKE '%Premier%', missing opaque lot mappings in sku_lot_allocations.\n",
        "sql_or_gql": "SELECT\n  ROUND(SUM(o.net_realized_revenue_sgd), 2) AS exposed_revenue_sgd,\n  COUNT(DISTINCT o.order_id) AS exposed_order_count\nFROM `example-project-id.meridian_commerce.orders` AS o\nJOIN `example-project-id.meridian_commerce.customers` AS c\n  ON o.customer_id = c.customer_id\nJOIN `example-project-id.meridian_commerce.order_lines` AS ol\n  ON o.order_id = ol.order_id\nWHERE o.country_code = 'SG'\n  AND o.order_status = 'COMPLETED'\n  AND o.order_date BETWEEN DATE '2026-07-01' AND DATE '2026-09-30'\n  AND c.segment_label LIKE '%Premier%'\n  AND ol.lot_id LIKE '%409%'\n",
        "tokens_used": 3340,
        "exploratory_queries": 5,
        "error_retries": 2,
        "eval_pass_count": 1,
        "eval_total_runs": 5,
        "trust_tier": "TIER_3_REVIEW_REQUIRED",
        "rationale": "Drops Tier-2 sku_lot_allocations multi-lot bridge and misapplies legacy segment_label filter."
      },
      "governed": {
        "answer_headline": "SGD 19,380.00 (38 SG Premier orders · SGD 510.00 AOV)",
        "answer_detail": "4-hop ISO GQL GRAPH_TABLE traversal from ColdChainBatch '#LN-409' through SkuLotAllocation, OrderLine, CustomerOrder, and Customer['PRM_HV'] identifies all 38 SG Premier orders totaling SGD 19,380.00.",
        "numeric_value": 19380.0,
        "unit": "SGD",
        "query_language": "SQL+GQL",
        "context_mechanism": "BigQuery Property Graph 4-Hop ISO GQL (`GRAPH_TABLE` over `meridian_supply_graph`)",
        "context_payload": "{\n  \"property_graph\": \"example-project-id.meridian_commerce.meridian_supply_graph\",\n  \"traversal_path\": \"(ColdChainBatch {batch_id: '#LN-409'})<-[:SUPPLIED_IN_BATCH]-(SkuLotAllocation)<-[:ALLOCATED_FROM_LOT]-(OrderLine)-[:BELONGS_TO_ORDER]->(CustomerOrder)-[:PLACED_BY]->(Customer)\",\n  \"glossary_filter\": \"c.tier_code = 'PRM_HV'\",\n  \"cross_rung_tie_out\": \"38 orders are a strict subset of R2's 640 SG PRM_HV completed orders\"\n}\n",
        "sql_or_gql": "SELECT\n  ROUND(SUM(net_realized_revenue_sgd), 2) AS exposed_revenue_sgd,\n  COUNT(*) AS exposed_order_count,\n  ROUND(AVG(net_realized_revenue_sgd), 2) AS exposed_aov_sgd\nFROM (\n  SELECT DISTINCT\n    order_id,\n    net_realized_revenue_sgd\n  FROM GRAPH_TABLE(\n    `example-project-id.meridian_commerce.meridian_supply_graph`\n    MATCH\n      (b:ColdChainBatch {batch_id: '#LN-409', supplier_tier: 'TIER_2'})\n      <-[:SUPPLIED_IN_BATCH]-(lot:SkuLotAllocation)\n      <-[:ALLOCATED_FROM_LOT]-(ol:OrderLine)\n      -[:BELONGS_TO_ORDER]->(o:CustomerOrder)\n      -[:PLACED_BY]->(c:Customer)\n    FILTER o.country_code = 'SG'\n      AND o.order_status = 'COMPLETED'\n      AND o.order_date BETWEEN DATE '2026-07-01' AND DATE '2026-09-30'\n      AND c.tier_code = 'PRM_HV'\n    RETURN\n      o.order_id AS order_id,\n      o.net_realized_revenue_sgd AS net_realized_revenue_sgd\n  )\n)\n",
        "tokens_used": 680,
        "exploratory_queries": 1,
        "error_retries": 0,
        "eval_pass_count": 5,
        "eval_total_runs": 5,
        "trust_tier": "TIER_1_VERIFIED_OR_COMPILED",
        "rationale": "Deterministic 4-hop ISO GQL traversal over BigQuery Property Graph aligned with PRM_HV glossary (5/5 pass)."
      },
      "xray_summary": {
        "context_added": "4-hop BigQuery Property Graph traversal connecting ColdChainBatch '#LN-409' through SkuLotAllocation, OrderLine, CustomerOrder, and PRM_HV Customer.",
        "gcp_primitives": [
          "BigQuery Property Graph (GA in asia-southeast1)",
          "ISO GQL GRAPH_TABLE Pattern Matching (GA)",
          "Knowledge Catalog Business Glossary (GA)"
        ],
        "negative_control_assertion": "Direct string-pattern join misses opaque warehouse lots LOT-SG-8841 and LOT-SG-8842 (80% revenue gap)."
      }
    },
    {
      "id": "r6_contracts",
      "rung_num": 6,
      "short_label": "R6 · Contracts",
      "title": "Unstructured Contract Overlays & SLA Recovery",
      "pyramid_layer": "Layer 3 · Gemini Enterprise Drive Connector + Object Tables + AI.GENERATE / DocAI (GA)",
      "release_badges": [
        {
          "capability": "Gemini Enterprise Drive Connector",
          "stage": "GA",
          "region_scope": "Global / asia-southeast1"
        },
        {
          "capability": "BigQuery Object Tables",
          "stage": "GA",
          "region_scope": "asia-southeast1"
        },
        {
          "capability": "AI.GENERATE / DocAI",
          "stage": "GA",
          "region_scope": "asia-southeast1"
        }
      ],
      "question": "How much vendor SLA credit is recoverable on Q3 Cold-Chain excursions?",
      "poll": {
        "prompt": "Myth-Buster #6: Base `vendor_sla_ledger` captures legacy MSA rules (`> 4.0°C for 90m -> 5%`). Executed `ArcticHaul_Amendment_2.md` sits in Drive (`> 2.0°C for 45m -> 12%`). Should we dump 40-page PDFs into every SQL prompt?",
        "options": [
          {
            "key": "A",
            "text": "Yes—paste all raw contract PDFs into the context window at query time."
          },
          {
            "key": "B",
            "text": "No—compile executed amendments once via Object Tables + AI.GENERATE / DocAI into a 480-token `sla_overlay` table, recovering SGD 18,960.00 (14 shipments) vs SGD 1,420.00 (3 breaches)."
          },
          {
            "key": "C",
            "text": "SQL agents can ignore executed Drive amendments because ERP tables always lead legal."
          },
          {
            "key": "D",
            "text": "The quarterly cap is exceeded, reducing recovery to zero."
          }
        ],
        "correct_key": "B",
        "reveal_takeaway": "Stuffing unstructured PDFs into every prompt burns tokens and fails deterministic arithmetic. Compiling executed Drive amendments via Object Tables + AI.GENERATE / DocAI into a compact 480-token `sla_overlay` table unlocks 13.3x SLA recovery (SGD 18,960.00 across 14 chilled shipments, safely within the SGD 35,000.00 cap)."
      },
      "blind": {
        "answer_headline": "SGD 1,420.00 (3 breaches)",
        "answer_detail": "Missed SGD 17,540.00 in recoverable credits because base vendor_sla_ledger applies legacy > 4.0 C for >= 90 min (5% credit), overlooking executed ArcticHaul Amendment #2.",
        "numeric_value": 1420.0,
        "unit": "SGD",
        "query_language": "SQL",
        "context_mechanism": "Structured ERP table only (base `vendor_sla_ledger`, unaware of Drive Amendment #2)",
        "context_payload": "Unstructured Drive contracts not connected or compiled.\nAgent evaluated only base_temp_threshold_c (> 4.0 C), base_duration_min (>= 90), and base_credit_rate (0.05).\n",
        "sql_or_gql": "SELECT\n  ROUND(SUM(shipment_invoice_sgd * base_credit_rate), 2) AS recoverable_credit_sgd,\n  COUNT(*) AS qualifying_breaches\nFROM `example-project-id.meridian_commerce.vendor_sla_ledger`\nWHERE quarter = '2026-Q3'\n  AND temp_peak_celsius > base_temp_threshold_c\n  AND excursion_duration_min >= base_duration_min\n",
        "tokens_used": 2150,
        "exploratory_queries": 3,
        "error_retries": 0,
        "eval_pass_count": 0,
        "eval_total_runs": 5,
        "trust_tier": "TIER_3_REVIEW_REQUIRED",
        "rationale": "Ignores executed ArcticHaul Amendment #2 governing BIOLOGIC_CHILLED excursions."
      },
      "governed": {
        "answer_headline": "SGD 18,960.00 (14 qualifying chilled shipments)",
        "answer_detail": "Joining structured 480-token sla_overlay extracted from ArcticHaul_Amendment_2.md (> 2.0 C for >= 45 min -> 12% credit, cap SGD 35,000.00) recovers SGD 18,960.00 across 14 shipments.",
        "numeric_value": 18960.0,
        "unit": "SGD",
        "query_language": "SQL",
        "context_mechanism": "Gemini Enterprise Drive Connector + BigQuery Object Tables + AI.GENERATE / DocAI (`sla_overlay`)",
        "context_payload": "{\n  \"overlay_id\": \"OVL-ARCTIC-AMD2\",\n  \"source_doc\": \"contracts/ArcticHaul_Amendment_2.md\",\n  \"extraction_tokens\": 480,\n  \"rule\": \"vendor_name='ArcticHaul' AND sku_class='BIOLOGIC_CHILLED' AND temp_peak_celsius > 2.0 AND excursion_duration_min >= 45 -> 12% credit\",\n  \"quarterly_cap_sgd\": 35000.00\n}\n",
        "sql_or_gql": "WITH evaluated_claims AS (\n  SELECT\n    l.event_id,\n    l.vendor_name,\n    COALESCE(o.quarterly_cap_sgd, 999999999.0) AS quarterly_cap_sgd,\n    CASE\n      WHEN o.overlay_id IS NOT NULL\n        AND l.temp_peak_celsius > o.temp_threshold_c\n        AND l.excursion_duration_min >= o.duration_threshold_min\n      THEN l.shipment_invoice_sgd * o.credit_rate\n      WHEN o.overlay_id IS NULL\n        AND l.temp_peak_celsius > l.base_temp_threshold_c\n        AND l.excursion_duration_min >= l.base_duration_min\n      THEN l.shipment_invoice_sgd * l.base_credit_rate\n      ELSE 0.0\n    END AS raw_credit_sgd\n  FROM `example-project-id.meridian_commerce.vendor_sla_ledger` AS l\n  LEFT JOIN `example-project-id.meridian_commerce.sla_overlay` AS o\n    ON l.vendor_name = o.vendor_name\n   AND l.sku_class = o.sku_class\n  WHERE l.quarter = '2026-Q3'\n),\nvendor_capped AS (\n  SELECT\n    vendor_name,\n    SUM(CASE WHEN raw_credit_sgd > 0 THEN 1 ELSE 0 END) AS qualifying_shipments,\n    CASE\n      WHEN SUM(raw_credit_sgd) > MAX(quarterly_cap_sgd) THEN MAX(quarterly_cap_sgd)\n      ELSE SUM(raw_credit_sgd)\n    END AS recoverable_credit_sgd\n  FROM evaluated_claims\n  GROUP BY vendor_name\n)\nSELECT\n  ROUND(SUM(recoverable_credit_sgd), 2) AS recoverable_credit_sgd,\n  SUM(qualifying_shipments) AS qualifying_shipments\nFROM vendor_capped\n",
        "tokens_used": 540,
        "exploratory_queries": 1,
        "error_retries": 0,
        "eval_pass_count": 5,
        "eval_total_runs": 5,
        "trust_tier": "TIER_1_VERIFIED_OR_COMPILED",
        "rationale": "Deterministic SQL join against compiled 480-token sla_overlay extracted from ArcticHaul_Amendment_2.md (5/5 pass)."
      },
      "xray_summary": {
        "context_added": "Structured 480-token sla_overlay table compiled from contracts/ArcticHaul_Amendment_2.md (> 2.0 C for >= 45m -> 12%, cap SGD 35K).",
        "gcp_primitives": [
          "Gemini Enterprise Drive Connector (GA)",
          "BigQuery Object Tables (GA)",
          "BigQuery AI.GENERATE / DocAI (GA)"
        ],
        "negative_control_assertion": "Base vendor_sla_ledger scan alone misses 11 moderate biologic excursions and understates credit recovery by 92.5%."
      }
    }
  ]
};
