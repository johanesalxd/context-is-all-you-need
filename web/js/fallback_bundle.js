/* Generic offline fallback ContextScenarioPackBundleV2 for standalone preview.
   Loaded only when data/rungs_bundle.js has not populated window.CONTEXT_PACK_BUNDLE. */
if (typeof window.CONTEXT_PACK_BUNDLE === "undefined") {
  window.CONTEXT_PACK_BUNDLE = {
    "schema_version": "2.0",
    "pack_id": "sample_context_pack",
    "title": "Sample Enterprise Context Pack",
    "subtitle": "5-Layer Context Pyramid Demonstration (Offline Generic Sample)",
    "hero_tagline": "Frontier models are table stakes—governed enterprise context is the differentiator.",
    "closed_period_label": "Closed Q4 Sample Period",
    "currency": "USD",
    "region": "asia-southeast1",
    "rng_seed": 100001,
    "generated_mode": "offline_fixture",
    "eval_methodology": {
      "runs_per_arm": 5,
      "model_id": "gemini-3.8-flash",
      "model_location": "global",
      "data_and_catalog_location": "asia-southeast1",
      "temperature": 0.0,
      "max_turns": 4,
      "timeout_s": 25,
      "note": "Offline generic fallback sample demonstrating Step-0 baselines and Empirical N=5 telemetry structure."
    },
    "overview": {
      "eyebrow": "Executive Briefing · Sample Context Pack",
      "headline": "Same Frontier Model. Two Completely Different Realities.",
      "subheadline": "Why raw warehouse schemas produce confident errors—and how 5 layers of governed enterprise context fix 6 sample traps.",
      "company_name": "Sample Global Commerce",
      "company_profile": "A multi-region retail and logistics enterprise closing Q4 in USD across domestic and international fulfillment tiers.",
      "problem_statement": "Pointing a frontier model straight at raw warehouse tables scales plausible-sounding SQL errors—inflating gross revenue, misreading promo tags, hitting 1:N join fan-traps, and missing policy overlays.",
      "estate_stats": [
        {
          "value": "~200 Tables",
          "label": "Sample Data Sprawl",
          "detail": "Core analytics marts + 190 shadow clones & snapshots"
        },
        {
          "value": "5 Context Layers",
          "label": "6 Sample Rungs",
          "detail": "Schemas, Insights, Glossary, Graph MEASURE(), RLS & Contracts"
        },
        {
          "value": "Sample Policy Docs",
          "label": "Unstructured Policy",
          "detail": "Object Table SLA overlays extracted into structured rules"
        },
        {
          "value": "1 Frontier Model",
          "label": "Held Constant",
          "detail": "The same Gemini model across Blind vs. Governed arms"
        }
      ],
      "experiment": {
        "fixed_control": "Held constant: the same Gemini model, identical 6 Q4 benchmark questions, and identical dataset seed.",
        "blind_arm": "Raw physical schema only (sample_blind): unannotated ERP columns, zero business glossary, zero certification tags, and zero contract overlay.",
        "governed_arm": "Progressive enterprise context: Knowledge Catalog Glossary, Certification Aspects & Auto DQ, Property Graph MEASURE() & ISO GQL, BigQuery RLS, and Object Table contracts."
      },
      "cta_label": "Start Simulation · R1 →"
    },
    "personas": [
      {
        "id": "analyst_global",
        "label": "Global Operations Analyst",
        "principal_display": "analyst-global@example-project-id.iam.gserviceaccount.com",
        "scope_summary": "Unrestricted multi-region visibility across all active territories."
      },
      {
        "id": "analyst_apac",
        "label": "APAC Regional Analyst",
        "principal_display": "analyst-apac@example-project-id.iam.gserviceaccount.com",
        "scope_summary": "Row-level access policy scoped strictly to APAC regional records."
      }
    ],
    "invariants": {
      "sample_r1_blind_gross_usd": 124500.0,
      "sample_r1_governed_net_usd": 98200.0,
      "sample_r2_blind_aov_usd": 195.0,
      "sample_r2_governed_aov_usd": 420.0,
      "sample_r3_blind_margin_pct": 11.4,
      "sample_r3_governed_margin_pct": 29.6,
      "sample_r4_global_margin_usd": 450000.0,
      "sample_r4_apac_margin_usd": 185000.0,
      "sample_r5_exposed_revenue_usd": 12400.0,
      "sample_r6_recoverable_sla_usd": 9600.0
    },
    "rungs": [
      {
        "id": "r1_schema",
        "rung_num": 1,
        "short_label": "R1 · Schema",
        "title": "Schema & Tax/Status Predicate Grounding",
        "pyramid_layer": "Layers 1–2 · BigQuery Schema & Data Insights",
        "difficulty_tier": "Easy",
        "release_badges": [
          {
            "capability": "BigQuery Schema & Data Insights",
            "stage": "GA",
            "region_scope": "asia-southeast1"
          },
          {
            "capability": "Knowledge Catalog lookupContext",
            "stage": "Preview",
            "region_scope": "asia-southeast1"
          }
        ],
        "question": "What was Closed Q4 Domestic Net Realized Revenue?",
        "poll": {
          "prompt": "Why do blind SQL agents frequently inflate revenue figures on cryptic ERP warehouse tables?",
          "options": [
            {
              "key": "A",
              "text": "The LLM cannot generate valid SQL GROUP BY syntax."
            },
            {
              "key": "B",
              "text": "Cryptic gross ERP columns include tax and cancelled rows without schema descriptions or predicates."
            },
            {
              "key": "C",
              "text": "BigQuery rounds floating-point totals unpredictably."
            },
            {
              "key": "D",
              "text": "Larger context windows automatically infer finance recognition rules."
            }
          ],
          "correct_key": "B",
          "reveal_takeaway": "ERP column names alone do not encode revenue recognition rules; enriched column descriptions and Knowledge Catalog lookupContext constrain status and tax filters."
        },
        "blind": {
          "answer_headline": "USD 124,500.00",
          "answer_detail": "Sums ambiguous amt_gross_billed_usd across all domestic records, sweeping in indirect tax and cancelled/returned transactions.",
          "stage_delta_pill": "+26.8% Overstated",
          "stage_summary": "Inflated by +USD 26.3K (+26.8%). Counted indirect tax plus cancelled and returned orders as revenue.",
          "numeric_value": 124500.0,
          "unit": "USD",
          "sql_or_gql": "SELECT\n  ROUND(SUM(amt_gross_billed_usd), 2) AS revenue_usd\nFROM `example-project-id.sample_blind.fact_orders`\nWHERE market_code = 'DOM';",
          "query_language": "SQL",
          "tokens_used": 1480,
          "exploratory_queries": 4,
          "error_retries": 2,
          "eval_pass_count": 0,
          "eval_total_runs": 5,
          "trust_tier": "TIER_3_REVIEW_REQUIRED",
          "rationale": "Guessed amt_gross_billed_usd on stripped raw schema without excluding cancelled rows or indirect tax.",
          "empirical_eval": {
            "model_id": "gemini-3.8-flash",
            "model_location": "global",
            "runs": 5,
            "pass_count": 0,
            "median_tokens": 1520,
            "median_exploratory_queries": 4,
            "median_error_retries": 1,
            "median_latency_ms": 4180.0,
            "sample_sql_or_gql": "SELECT ROUND(SUM(amt_gross_billed_usd), 2) AS total_rev\nFROM `example-project-id.sample_blind.fact_orders`\nWHERE market_code = 'DOM';",
            "observed_signals": [
              "blind_raw_schema_only",
              "selected_amt_gross_billed",
              "missing_status_completed_filter"
            ]
          }
        },
        "governed": {
          "answer_headline": "USD 98,200.00",
          "answer_detail": "Filters status = 'COMPLETED' and sums amt_net_settled_usd ex-tax as defined in Knowledge Catalog metadata.",
          "stage_delta_pill": "Board-Ready · Ex-Tax",
          "stage_summary": "Board-ready Q4 domestic net revenue across completed orders — excluding indirect tax and cancellations.",
          "numeric_value": 98200.0,
          "unit": "USD",
          "sql_or_gql": "SELECT\n  ROUND(SUM(amt_net_settled_usd), 2) AS net_realized_revenue_usd\nFROM `example-project-id.sample_analytics.fact_orders`\nWHERE market_code = 'DOM'\n  AND status = 'COMPLETED';",
          "query_language": "SQL",
          "context_mechanism": "Column descriptions + Knowledge Catalog lookupContext predicate binding",
          "context_payload": "{\n  \"table\": \"fact_orders\",\n  \"metric_column\": \"amt_net_settled_usd\",\n  \"excluded_columns\": [\"amt_gross_billed_usd\", \"amt_item_subtotal_usd\"],\n  \"required_predicates\": [\"status = 'COMPLETED'\", \"market_code = 'DOM'\"]\n}",
          "tokens_used": 410,
          "exploratory_queries": 1,
          "error_retries": 0,
          "eval_pass_count": 4,
          "eval_total_runs": 5,
          "trust_tier": "TIER_2_GROUNDED",
          "rationale": "Grounded in governed column metadata and canonical completion status predicate.",
          "empirical_eval": {
            "model_id": "gemini-3.8-flash",
            "model_location": "global",
            "runs": 5,
            "pass_count": 5,
            "median_tokens": 640,
            "median_exploratory_queries": 1,
            "median_error_retries": 0,
            "median_latency_ms": 2410.0,
            "sample_sql_or_gql": "SELECT ROUND(SUM(amt_net_settled_usd), 2) AS net_realized_revenue_usd\nFROM `example-project-id.sample_analytics.fact_orders`\nWHERE market_code = 'DOM' AND status = 'COMPLETED';",
            "observed_signals": [
              "lookup_catalog_context",
              "selected_amt_net_settled",
              "filtered_status_completed"
            ]
          }
        },
        "xray_summary": {
          "context_added": "Column-level revenue recognition description on amt_net_settled_usd vs amt_gross_billed_usd plus Knowledge Catalog lookupContext status predicate.",
          "gcp_primitives": [
            "BigQuery Schema Metadata",
            "BigQuery Data Insights",
            "Knowledge Catalog lookupContext (Preview)"
          ],
          "negative_control_assertion": "Verified schema metadata enforces amt_net_settled_usd over amt_gross_billed_usd and blocks unverified column guessing."
        }
      },
      {
        "id": "r2_glossary",
        "rung_num": 2,
        "short_label": "R2 · Glossary",
        "title": "Governed Business Glossary Term Resolution",
        "pyramid_layer": "Layer 4 · Knowledge Catalog Business Glossary",
        "difficulty_tier": "Easy",
        "release_badges": [
          {
            "capability": "Knowledge Catalog Business Glossary",
            "stage": "GA",
            "region_scope": "asia-southeast1"
          }
        ],
        "question": "Which channel led Closed Q4 Priority Tier Average Order Value?",
        "poll": {
          "prompt": "When two columns look semantically similar (e.g., marketing_tag vs tier_code), what fixes agent drift?",
          "options": [
            {
              "key": "A",
              "text": "Renumbering columns alphabetically in the warehouse."
            },
            {
              "key": "B",
              "text": "A governed Business Glossary mapping business terms via EntryLinks to exact SQL predicates."
            },
            {
              "key": "C",
              "text": "Lowering model temperature to 0.0 without metadata."
            },
            {
              "key": "D",
              "text": "Allowing the agent to sample 100 random rows and guess."
            }
          ],
          "correct_key": "B",
          "reveal_takeaway": "Fuzzy label matching traps blind agents on promo tags; a Knowledge Catalog Business Glossary EntryLink binds 'Priority Tier' deterministically to tier_code."
        },
        "blind": {
          "answer_headline": "Self-Serve Portal (USD 195.00)",
          "answer_detail": "Matches marketing_tag LIKE '%Priority%', pulling in low-spend promotional trial campaigns.",
          "stage_delta_pill": "Wrong Channel · -53.6% AOV",
          "stage_summary": "Wrong winning channel (-53.6% AOV). Mixed promotional trial signups into the Priority Tier segment.",
          "numeric_value": 195.0,
          "unit": "USD",
          "sql_or_gql": "SELECT\n  channel,\n  ROUND(AVG(o.amt_net_settled_usd), 2) AS aov_usd\nFROM `example-project-id.sample_blind.fact_orders` o\nJOIN `example-project-id.sample_blind.dim_accounts` a USING (account_id)\nWHERE a.marketing_tag LIKE '%Priority%'\nGROUP BY channel\nORDER BY aov_usd DESC\nLIMIT 1;",
          "query_language": "SQL",
          "tokens_used": 1620,
          "exploratory_queries": 5,
          "error_retries": 2,
          "eval_pass_count": 0,
          "eval_total_runs": 5,
          "trust_tier": "TIER_3_REVIEW_REQUIRED",
          "rationale": "String-matched marketing_tag distractor column instead of governed tier_code.",
          "empirical_eval": {
            "model_id": "gemini-3.8-flash",
            "model_location": "global",
            "runs": 5,
            "pass_count": 0,
            "median_tokens": 1710,
            "median_exploratory_queries": 4,
            "median_error_retries": 1,
            "median_latency_ms": 4390.0,
            "sample_sql_or_gql": "SELECT o.channel, ROUND(AVG(o.amt_net_settled_usd), 2) AS aov_usd\nFROM `example-project-id.sample_blind.fact_orders` o\nJOIN `example-project-id.sample_blind.dim_accounts` a USING (account_id)\nWHERE a.marketing_tag LIKE '%Priority%'\nGROUP BY o.channel ORDER BY aov_usd DESC LIMIT 1;",
            "observed_signals": [
              "blind_raw_schema_only",
              "fuzzy_marketing_tag_like"
            ]
          }
        },
        "governed": {
          "answer_headline": "Enterprise Direct (USD 420.00)",
          "answer_detail": "Resolves Business Glossary term 'Priority Tier' via EntryLink to tier_code = 'TIER_A_EXEC', surfacing Enterprise Direct leadership.",
          "stage_delta_pill": "Governed VIP Definition",
          "stage_summary": "Enterprise Direct leads using Finance's official Priority Tier customer definition.",
          "numeric_value": 420.0,
          "unit": "USD",
          "sql_or_gql": "SELECT\n  o.channel,\n  ROUND(AVG(o.amt_net_settled_usd), 2) AS aov_usd\nFROM `example-project-id.sample_analytics.fact_orders` o\nJOIN `example-project-id.sample_analytics.dim_accounts` a USING (account_id)\nWHERE a.tier_code = 'TIER_A_EXEC'\n  AND o.status = 'COMPLETED'\nGROUP BY o.channel\nORDER BY aov_usd DESC\nLIMIT 1;",
          "query_language": "SQL",
          "context_mechanism": "Knowledge Catalog Business Glossary term + definition EntryLink binding",
          "context_payload": "{\n  \"glossary_term\": \"Priority Tier\",\n  \"entry_link_target\": \"dim_accounts.Schema.tier_code\",\n  \"canonical_predicate\": \"dim_accounts.tier_code = 'TIER_A_EXEC'\",\n  \"excluded_distractor\": \"dim_accounts.marketing_tag\"\n}",
          "tokens_used": 440,
          "exploratory_queries": 1,
          "error_retries": 0,
          "eval_pass_count": 5,
          "eval_total_runs": 5,
          "trust_tier": "TIER_2_GROUNDED",
          "rationale": "Glossary EntryLink explicitly binds 'Priority Tier' to tier_code = 'TIER_A_EXEC' across 5/5 evals.",
          "empirical_eval": {
            "model_id": "gemini-3.8-flash",
            "model_location": "global",
            "runs": 5,
            "pass_count": 5,
            "median_tokens": 680,
            "median_exploratory_queries": 1,
            "median_error_retries": 0,
            "median_latency_ms": 2530.0,
            "sample_sql_or_gql": "SELECT o.channel, ROUND(AVG(o.amt_net_settled_usd), 2) AS aov_usd\nFROM `example-project-id.sample_analytics.fact_orders` o\nJOIN `example-project-id.sample_analytics.dim_accounts` a USING (account_id)\nWHERE a.tier_code = 'TIER_A_EXEC' AND o.status = 'COMPLETED'\nGROUP BY o.channel ORDER BY aov_usd DESC LIMIT 1;",
            "observed_signals": [
              "lookup_catalog_context",
              "glossary_entry_link_tier_code",
              "filtered_status_completed"
            ]
          }
        },
        "xray_summary": {
          "context_added": "Business Glossary definition and EntryLink binding 'Priority Tier' to dim_accounts.tier_code = 'TIER_A_EXEC'.",
          "gcp_primitives": [
            "Knowledge Catalog Business Glossary (GA)",
            "Knowledge Catalog EntryLink (GA)",
            "BigQuery Column Lineage"
          ],
          "negative_control_assertion": "Verified distractor tag 'Priority_Promo_Trial' is excluded by governed glossary filter."
        }
      },
      {
        "id": "r3_metrics",
        "rung_num": 3,
        "short_label": "R3 · Metrics",
        "title": "Grain-Locked Semantic Metrics Against 1:N Fan-Out",
        "pyramid_layer": "Layer 4 · BigQuery Graph MEASURE() & Verified Query",
        "difficulty_tier": "Medium",
        "release_badges": [
          {
            "capability": "BigQuery Graph MEASURE()",
            "stage": "GA",
            "region_scope": "asia-southeast1"
          },
          {
            "capability": "Verified Query Contract",
            "stage": "GA",
            "region_scope": "asia-southeast1"
          },
          {
            "capability": "Custom Semantic Contract",
            "stage": "Reference Architecture",
            "region_scope": "asia-southeast1"
          }
        ],
        "question": "What was Q4 Express Fulfillment Contribution Margin %?",
        "poll": {
          "prompt": "Why does joining orders directly to multi-leg shipment events corrupt margin percentages?",
          "options": [
            {
              "key": "A",
              "text": "1:N child rows multiply header revenue once per transit leg (fan-trap)."
            },
            {
              "key": "B",
              "text": "LEFT JOIN drops rows with NULL tracking codes."
            },
            {
              "key": "C",
              "text": "BigQuery SQL evaluates SELECT before FROM."
            },
            {
              "key": "D",
              "text": "Percentages cannot be calculated inside SQL queries."
            }
          ],
          "correct_key": "A",
          "reveal_takeaway": "Header-grain revenue cannot be summed after a 1:N fan-out join; grain-locked MEASURE() and Verified Queries aggregate transit cost before joining."
        },
        "blind": {
          "answer_headline": "11.4% Contribution Margin",
          "answer_detail": "Un-aggregated 3-way JOIN multiplies order header cost and revenue across 2–4 shipment hops per order.",
          "stage_delta_pill": "-18.2 pts Margin Distortion",
          "stage_summary": "Margin understated by -18.2 pts. Double-counted line and transit costs across multi-hop shipments.",
          "numeric_value": 11.4,
          "unit": "PCT",
          "sql_or_gql": "SELECT\n  ROUND(100.0 * SUM(o.amt_net_settled_usd - l.line_cogs_usd - h.hop_cost_usd) / SUM(o.amt_net_settled_usd), 1) AS margin_pct\nFROM `example-project-id.sample_blind.fact_orders` o\nJOIN `example-project-id.sample_blind.fact_order_lines` l USING (order_id)\nJOIN `example-project-id.sample_blind.fact_transit_hops` h USING (order_id)\nWHERE o.fulfillment_mode = 'EXPRESS';",
          "query_language": "SQL",
          "tokens_used": 1890,
          "exploratory_queries": 6,
          "error_retries": 3,
          "eval_pass_count": 0,
          "eval_total_runs": 5,
          "trust_tier": "TIER_3_REVIEW_REQUIRED",
          "rationale": "1:N transit hop join duplicated header revenue and line COGS.",
          "empirical_eval": {
            "model_id": "gemini-3.8-flash",
            "model_location": "global",
            "runs": 5,
            "pass_count": 0,
            "median_tokens": 1960,
            "median_exploratory_queries": 5,
            "median_error_retries": 2,
            "median_latency_ms": 4890.0,
            "sample_sql_or_gql": "SELECT ROUND(100.0 * SUM(o.amt_net_settled_usd - l.line_cogs_usd - h.hop_cost_usd) / SUM(o.amt_net_settled_usd), 1) AS margin_pct\nFROM `example-project-id.sample_blind.fact_orders` o\nJOIN `example-project-id.sample_blind.fact_order_lines` l USING (order_id)\nJOIN `example-project-id.sample_blind.fact_transit_hops` h USING (order_id)\nWHERE o.fulfillment_mode = 'EXPRESS';",
            "observed_signals": [
              "blind_raw_schema_only",
              "unaggregated_1n_fan_trap"
            ]
          }
        },
        "governed": {
          "answer_headline": "29.6% Contribution Margin",
          "answer_detail": "Grain-locked CTE / Property Graph MEASURE() pre-aggregates transit hops to order grain before margin calculation.",
          "stage_delta_pill": "Zero Double-Counting",
          "stage_summary": "True Express fulfillment profitability (29.6% margin) — every order, item, and transit cost counted once.",
          "numeric_value": 29.6,
          "unit": "PCT",
          "sql_or_gql": "WITH hop_costs AS (\n  SELECT order_id, SUM(hop_cost_usd) AS total_hop_cost_usd\n  FROM `example-project-id.sample_analytics.fact_transit_hops`\n  GROUP BY order_id\n)\nSELECT\n  ROUND(100.0 * SUM(o.amt_net_settled_usd - o.total_cogs_usd - hc.total_hop_cost_usd) / SUM(o.amt_net_settled_usd), 1) AS margin_pct\nFROM `example-project-id.sample_analytics.fact_orders` o\nJOIN hop_costs hc USING (order_id)\nWHERE o.fulfillment_mode = 'EXPRESS'\n  AND o.status = 'COMPLETED';",
          "query_language": "SQL+GQL",
          "context_mechanism": "Grain-locked BigQuery Graph MEASURE() + Verified Query semantic contract",
          "context_payload": "{\n  \"metric\": \"express_contribution_margin_pct\",\n  \"grain\": \"order_id\",\n  \"measure_formula\": \"(amt_net_settled_usd - total_cogs_usd - SUM(hop_cost_usd)) / amt_net_settled_usd\"\n}",
          "tokens_used": 490,
          "exploratory_queries": 1,
          "error_retries": 0,
          "eval_pass_count": 5,
          "eval_total_runs": 5,
          "trust_tier": "TIER_1_VERIFIED_OR_COMPILED",
          "rationale": "Compiled Verified Query and MEASURE() eliminate 1:N join duplication.",
          "empirical_eval": {
            "model_id": "gemini-3.8-flash",
            "model_location": "global",
            "runs": 5,
            "pass_count": 5,
            "median_tokens": 710,
            "median_exploratory_queries": 1,
            "median_error_retries": 0,
            "median_latency_ms": 2690.0,
            "sample_sql_or_gql": "WITH hop_costs AS (SELECT order_id, SUM(hop_cost_usd) AS total_hop_cost_usd FROM `example-project-id.sample_analytics.fact_transit_hops` GROUP BY order_id)\nSELECT ROUND(100.0 * SUM(o.amt_net_settled_usd - o.total_cogs_usd - hc.total_hop_cost_usd) / SUM(o.amt_net_settled_usd), 1) AS margin_pct\nFROM `example-project-id.sample_analytics.fact_orders` o JOIN hop_costs hc USING (order_id)\nWHERE o.fulfillment_mode = 'EXPRESS' AND o.status = 'COMPLETED';",
            "observed_signals": [
              "get_verified_metric_contract",
              "grain_locked_preaggregation",
              "MEASURE"
            ]
          }
        },
        "xray_summary": {
          "context_added": "Grain-locked semantic contract preventing 1:N transit-hop join inflation.",
          "gcp_primitives": [
            "BigQuery Property Graph MEASURE() (GA)",
            "Verified Query Contract (GA)",
            "Custom Semantic Contract (Reference Architecture)"
          ],
          "negative_control_assertion": "Verified pre-aggregated hop_costs matches order header grain with zero fan-out drift."
        }
      },
      {
        "id": "r4_trust_access",
        "rung_num": 4,
        "short_label": "R4 · Trust & RLS",
        "title": "Data Product Certification & Row-Level Access",
        "pyramid_layer": "Layers 1 & 5 · KC Data Products, Auto DQ & BigQuery RLS",
        "difficulty_tier": "Medium",
        "release_badges": [
          {
            "capability": "Knowledge Catalog Data Products",
            "stage": "GA",
            "region_scope": "asia-southeast1"
          },
          {
            "capability": "BigQuery Row-Level Security",
            "stage": "GA",
            "region_scope": "asia-southeast1"
          }
        ],
        "question": "Did Temperature-Controlled Margin drop in Q4—and what does each role see?",
        "poll": {
          "prompt": "When neutral candidate marts (mart_temp_margin_q4_r1 vs r2) and 190 shadow tables share identical columns, how does an agent pick the source?",
          "options": [
            {
              "key": "A",
              "text": "Pick whichever table was modified most recently by any script."
            },
            {
              "key": "B",
              "text": "Route exclusively via Knowledge Catalog certification Aspects & Auto DQ, enforced by BigQuery RLS."
            },
            {
              "key": "C",
              "text": "Union all candidate tables together and average the outputs."
            },
            {
              "key": "D",
              "text": "Prompt the model to inspect table names and pick the highest suffix."
            }
          ],
          "correct_key": "B",
          "reveal_takeaway": "When mart tables share neutral names and identical schemas, Knowledge Catalog AspectTypes ('CERTIFIED' vs 'UNCERTIFIED_STALE') and Auto DQ eliminate stale close snapshots while RLS enforces per-role scope."
        },
        "blind": {
          "answer_headline": "False Drop: 21.8% (-320 bps)",
          "answer_detail": "Scans uncertified mart_temp_margin_q4_r1 (close_batch_code = 'B26Q4_R1') amid 190 shadow tables, missing late-quarter supplier settlements.",
          "stage_delta_pill": "False -320 bps Alarm",
          "stage_summary": "False boardroom panic (-320 bps). Pulled an uncertified preliminary snapshot missing late-Q4 rebates.",
          "numeric_value": 21.8,
          "unit": "PCT",
          "sql_or_gql": "SELECT\n  ROUND(100.0 * SUM(gross_margin_usd) / SUM(net_revenue_usd), 1) AS margin_pct\nFROM `example-project-id.sample_blind.mart_temp_margin_q4_r1`;",
          "query_language": "SQL",
          "tokens_used": 2140,
          "exploratory_queries": 7,
          "error_retries": 3,
          "eval_pass_count": 1,
          "eval_total_runs": 5,
          "trust_tier": "TIER_3_REVIEW_REQUIRED",
          "rationale": "Selected uncertified preliminary close mart_temp_margin_q4_r1 from unannotated blind catalog.",
          "empirical_eval": {
            "model_id": "gemini-3.8-flash",
            "model_location": "global",
            "runs": 5,
            "pass_count": 1,
            "median_tokens": 2290,
            "median_exploratory_queries": 6,
            "median_error_retries": 2,
            "median_latency_ms": 5120.0,
            "sample_sql_or_gql": "SELECT ROUND(100.0 * SUM(gross_margin_usd) / SUM(net_revenue_usd), 1) AS margin_pct\nFROM `example-project-id.sample_blind.mart_temp_margin_q4_r1`;",
            "observed_signals": [
              "blind_raw_schema_only",
              "selected_uncertified_r1_mart"
            ]
          }
        },
        "governed": {
          "answer_headline": "25.0% Margin (-30 bps YoY)",
          "answer_detail": "Routes exclusively to Knowledge Catalog CERTIFIED Data Product mart_temp_margin_q4_r2 (no false drop) and enforces caller Row-Level Security policy.",
          "stage_delta_pill": "Certified Close + Role-Scoped",
          "stage_summary": "Steady 25.0% margin (-30 bps YoY) from the certified Q4 close — automatically scoped to the viewer's role.",
          "numeric_value": 25.0,
          "unit": "PCT",
          "sql_or_gql": "SELECT\n  SUM(gross_margin_usd) AS visible_gross_margin_usd,\n  COUNT(*) AS rows_visible\nFROM `example-project-id.sample_analytics.mart_temp_margin_q4_r2`\nWHERE quarter = 'Q4';",
          "query_language": "SQL",
          "context_mechanism": "Knowledge Catalog data-product-certification Aspect + Auto DQ + BigQuery Row Access Policy",
          "context_payload": "{\n  \"certified_asset\": \"mart_temp_margin_q4_r2\",\n  \"aspect_type\": \"data-product-certification\",\n  \"certification_status\": \"CERTIFIED\",\n  \"stale_excluded\": \"mart_temp_margin_q4_r1 (UNCERTIFIED_STALE)\",\n  \"auto_dq_status\": \"PASSED\",\n  \"rls_policies\": [\"rls_global_full_access\", \"rls_apac_region_only\"]\n}",
          "tokens_used": 430,
          "exploratory_queries": 1,
          "error_retries": 0,
          "eval_pass_count": 5,
          "eval_total_runs": 5,
          "trust_tier": "TIER_1_VERIFIED_OR_COMPILED",
          "rationale": "Certified mart_temp_margin_q4_r2 Data Product with active BigQuery Row-Level Security per identity.",
          "empirical_eval": {
            "model_id": "gemini-3.8-flash",
            "model_location": "global",
            "runs": 5,
            "pass_count": 5,
            "median_tokens": 620,
            "median_exploratory_queries": 1,
            "median_error_retries": 0,
            "median_latency_ms": 2380.0,
            "sample_sql_or_gql": "SELECT ROUND(100.0 * SUM(gross_margin_usd) / SUM(net_revenue_usd), 1) AS margin_pct, SUM(gross_margin_usd) AS visible_gross_margin_usd\nFROM `example-project-id.sample_analytics.mart_temp_margin_q4_r2` WHERE quarter = 'Q4';",
            "observed_signals": [
              "search_certified_tables",
              "CERTIFIED",
              "auto_dq_passed",
              "rls_enforced"
            ]
          }
        },
        "identity_variants": {
          "analyst_global": {
            "persona_id": "analyst_global",
            "answer_headline": "USD 450,000.00 (All 4 Regions · 25.0%)",
            "answer_detail": "Global Operations Analyst clears full regional scope across NA, EMEA, LATAM, and APAC certified partitions.",
            "numeric_value": 450000.0,
            "rows_visible": 12,
            "rls_policy_applied": "rls_global_full_access (FILTER USING TRUE)",
            "policy_note": "Full multi-region visibility granted via certified Data Product entry group."
          },
          "analyst_apac": {
            "persona_id": "analyst_apac",
            "answer_headline": "USD 185,000.00 (APAC Region Only)",
            "answer_detail": "APAC Regional Analyst receives only APAC rows from the exact same SQL query under BigQuery Row-Level Security.",
            "numeric_value": 185000.0,
            "rows_visible": 3,
            "rls_policy_applied": "rls_apac_region_only (FILTER USING region_code = 'APAC')",
            "policy_note": "Non-APAC rows filtered natively at storage engine layer; zero cross-region leakage."
          }
        },
        "xray_summary": {
          "context_added": "Knowledge Catalog data-product-certification Aspect routing (mart_temp_margin_q4_r2 over r1) plus role-bound BigQuery Row Access Policies.",
          "gcp_primitives": [
            "Knowledge Catalog Data Products & AspectType (GA)",
            "Auto Data Quality (GA)",
            "BigQuery Row-Level Security (GA)"
          ],
          "negative_control_assertion": "Verified unauthorized direct queries to uncertified r1/unscoped partitions return explicit 403 accessDenied or strict 0/subset RLS row filtering."
        }
      },
      {
        "id": "r5_graph",
        "rung_num": 5,
        "short_label": "R5 · Graph",
        "title": "4-Hop Multi-Entity Supply Lineage via ISO GQL",
        "pyramid_layer": "Layer 4 · BigQuery Property Graph & ISO GQL",
        "difficulty_tier": "Hard",
        "release_badges": [
          {
            "capability": "BigQuery Property Graph",
            "stage": "GA",
            "region_scope": "asia-southeast1"
          },
          {
            "capability": "ISO GQL GRAPH_TABLE",
            "stage": "GA",
            "region_scope": "asia-southeast1"
          }
        ],
        "question": "Which Priority Tier orders & revenue are exposed to delayed Lot #LOT-804?",
        "poll": {
          "prompt": "Why do blind LLM SQL generators fail on 4-hop supply-chain impact queries?",
          "options": [
            {
              "key": "A",
              "text": "They skip intermediate allocation bridge tables or guess wrong foreign-key directions."
            },
            {
              "key": "B",
              "text": "ISO GQL only supports 1-hop graph queries."
            },
            {
              "key": "C",
              "text": "BigQuery Property Graphs require exporting tables to CSV first."
            },
            {
              "key": "D",
              "text": "Foreign keys cannot connect batches to customer accounts."
            }
          ],
          "correct_key": "A",
          "reveal_takeaway": "Declarative Property Graph edges encode the canonical 4-hop lineage path so ISO GQL GRAPH_TABLE traverses Batch -> Allocation -> Line -> Order -> Account cleanly."
        },
        "blind": {
          "answer_headline": "USD 2,950.00 (Incomplete Join)",
          "answer_detail": "Drops the intermediate lot-allocation bridge table and misses multi-SKU orders tied to Lot #LOT-804.",
          "stage_delta_pill": "76% Exposure Missed",
          "stage_summary": "Missed 76% of customer exposure. Direct join dropped the multi-lot allocation bridge table.",
          "numeric_value": 2950.0,
          "unit": "USD",
          "sql_or_gql": "SELECT\n  ROUND(SUM(o.amt_net_settled_usd), 2) AS exposed_usd\nFROM `example-project-id.sample_blind.fact_orders` o\nJOIN `example-project-id.sample_blind.dim_batches` b\n  ON o.order_id = b.primary_order_id\nWHERE b.batch_code = '#LOT-804';",
          "query_language": "SQL",
          "tokens_used": 2380,
          "exploratory_queries": 8,
          "error_retries": 4,
          "eval_pass_count": 1,
          "eval_total_runs": 5,
          "trust_tier": "TIER_3_REVIEW_REQUIRED",
          "rationale": "Missed intermediate allocation bridge and Priority Tier glossary predicate.",
          "empirical_eval": {
            "model_id": "gemini-3.8-flash",
            "model_location": "global",
            "runs": 5,
            "pass_count": 1,
            "median_tokens": 2440,
            "median_exploratory_queries": 7,
            "median_error_retries": 3,
            "median_latency_ms": 5460.0,
            "sample_sql_or_gql": "SELECT ROUND(SUM(o.amt_net_settled_usd), 2) AS exposed_usd\nFROM `example-project-id.sample_blind.fact_orders` o\nJOIN `example-project-id.sample_blind.dim_batches` b ON o.order_id = b.primary_order_id\nWHERE b.batch_code = '#LOT-804';",
            "observed_signals": [
              "blind_raw_schema_only",
              "dropped_allocation_bridge"
            ]
          }
        },
        "governed": {
          "answer_headline": "USD 12,400.00 across 24 Priority Orders",
          "answer_detail": "Executes 4-hop GRAPH_TABLE ISO GQL traversal from SupplyLot '#LOT-804' through Allocations, Lines, and Orders to TIER_A_EXEC Accounts.",
          "stage_delta_pill": "4-Hop Supply Lineage",
          "stage_summary": "Full 4-hop supply-chain blast radius — traces Lot #LOT-804 to all 24 exposed Priority accounts.",
          "numeric_value": 12400.0,
          "unit": "USD",
          "sql_or_gql": "SELECT\n  COUNT(DISTINCT order_id) AS exposed_orders,\n  ROUND(SUM(amt_net_settled_usd), 2) AS exposed_revenue_usd\nFROM GRAPH_TABLE(\n  `example-project-id.sample_analytics.sample_supply_graph`\n  MATCH (b:SupplyBatch {batch_code: '#LOT-804'})-[:ALLOCATED_TO]->(a:LotAllocation)-[:FULFILLED_BY]->(l:OrderLine)-[:PART_OF]->(o:Order)-[:PLACED_BY]->(c:Account {tier_code: 'TIER_A_EXEC'})\n  RETURN o.order_id, o.amt_net_settled_usd\n);",
          "query_language": "GQL",
          "context_mechanism": "BigQuery Property Graph schema topology + ISO GQL GRAPH_TABLE",
          "context_payload": "{\n  \"graph\": \"sample_supply_graph\",\n  \"traversal\": \"SupplyBatch -> LotAllocation -> OrderLine -> Order -> Account[TIER_A_EXEC]\",\n  \"target_batch\": \"#LOT-804\"\n}",
          "tokens_used": 520,
          "exploratory_queries": 1,
          "error_retries": 0,
          "eval_pass_count": 5,
          "eval_total_runs": 5,
          "trust_tier": "TIER_1_VERIFIED_OR_COMPILED",
          "rationale": "Property Graph edges enforce complete 4-hop lineage consistent with R2 Priority Tier definition.",
          "empirical_eval": {
            "model_id": "gemini-3.8-flash",
            "model_location": "global",
            "runs": 5,
            "pass_count": 5,
            "median_tokens": 740,
            "median_exploratory_queries": 1,
            "median_error_retries": 0,
            "median_latency_ms": 2840.0,
            "sample_sql_or_gql": "SELECT COUNT(DISTINCT order_id) AS exposed_orders, ROUND(SUM(amt_net_settled_usd), 2) AS exposed_revenue_usd\nFROM GRAPH_TABLE(`example-project-id.sample_analytics.sample_supply_graph`\n  MATCH (b:SupplyBatch {batch_code: '#LOT-804'})-[:ALLOCATED_TO]->(a:LotAllocation)-[:FULFILLED_BY]->(l:OrderLine)-[:PART_OF]->(o:Order)-[:PLACED_BY]->(c:Account {tier_code: 'TIER_A_EXEC'})\n  RETURN o.order_id, o.amt_net_settled_usd);",
            "observed_signals": [
              "get_verified_metric_contract",
              "GRAPH_TABLE",
              "glossary_entry_link_tier_code"
            ]
          }
        },
        "xray_summary": {
          "context_added": "Property Graph node/edge topology with explicit multi-hop lineage constraints.",
          "gcp_primitives": [
            "BigQuery Property Graph (GA)",
            "ISO GQL GRAPH_TABLE (GA)"
          ],
          "negative_control_assertion": "Verified 4-hop traversal matches exact cohort of TIER_A_EXEC accounts without missing bridge allocations."
        }
      },
      {
        "id": "r6_contracts",
        "rung_num": 6,
        "short_label": "R6 · Contracts",
        "title": "Unstructured Contract Amendments Joined to Warehouse Events",
        "pyramid_layer": "Layer 3 · Gemini Enterprise, Object Tables & AI.GENERATE",
        "difficulty_tier": "Hard",
        "release_badges": [
          {
            "capability": "BigQuery Object Tables & AI.GENERATE",
            "stage": "GA",
            "region_scope": "asia-southeast1"
          },
          {
            "capability": "Gemini Enterprise Drive Connector",
            "stage": "GA",
            "region_scope": "asia-southeast1"
          }
        ],
        "question": "How much carrier SLA credit is recoverable on Q4 cold-storage excursions?",
        "poll": {
          "prompt": "Why did the SQL-only agent under-report recoverable vendor SLA credits by over 80%?",
          "options": [
            {
              "key": "A",
              "text": "The signed Amendment #2 lowered thresholds in an unstructured contract PDF/Markdown file outside base ERP tables."
            },
            {
              "key": "B",
              "text": "BigQuery cannot join structured overlay tables with telemetry ledgers."
            },
            {
              "key": "C",
              "text": "SLA percentages must always be rounded down to integer values."
            },
            {
              "key": "D",
              "text": "SQL joins cannot evaluate inequalities like temperature > threshold."
            }
          ],
          "correct_key": "A",
          "reveal_takeaway": "Enterprise truth often lives in signed contract amendments; extracting a structured policy overlay brings unstructured terms into governed SQL joins."
        },
        "blind": {
          "answer_headline": "USD 1,250.00 (Base Ledger Only)",
          "answer_detail": "Queries legacy base_sla_ledger (> 5.0C for 90m -> 5% credit) and misses executed Amendment #2 terms.",
          "stage_delta_pill": "USD 8.35K Left Unclaimed",
          "stage_summary": "Left USD 8.35K on the table. Used legacy base SLA rules and missed the signed Amendment #2.",
          "numeric_value": 1250.0,
          "unit": "USD",
          "sql_or_gql": "SELECT\n  ROUND(SUM(shipment_fee_usd * 0.05), 2) AS recoverable_credit_usd\nFROM `example-project-id.sample_blind.base_sla_ledger`\nWHERE peak_temp_c > 5.0\n  AND duration_min >= 90;",
          "query_language": "SQL",
          "tokens_used": 1750,
          "exploratory_queries": 5,
          "error_retries": 1,
          "eval_pass_count": 0,
          "eval_total_runs": 5,
          "trust_tier": "TIER_3_REVIEW_REQUIRED",
          "rationale": "Ignored executed vendor SLA amendment residing in document storage.",
          "empirical_eval": {
            "model_id": "gemini-3.8-flash",
            "model_location": "global",
            "runs": 5,
            "pass_count": 0,
            "median_tokens": 1820,
            "median_exploratory_queries": 4,
            "median_error_retries": 1,
            "median_latency_ms": 4220.0,
            "sample_sql_or_gql": "SELECT ROUND(SUM(shipment_fee_usd * 0.05), 2) AS recoverable_credit_usd\nFROM `example-project-id.sample_blind.base_sla_ledger`\nWHERE peak_temp_c > 5.0 AND duration_min >= 90;",
            "observed_signals": [
              "blind_raw_schema_only",
              "missed_sla_overlay_contract"
            ]
          }
        },
        "governed": {
          "answer_headline": "USD 9,600.00 across 12 Qualifying Shipments",
          "answer_detail": "Joins structured contract_sla_overlay extracted from Vendor_Amendment_2.md (> 2.5C for 45m -> 12% credit, capped at USD 25,000).",
          "stage_delta_pill": "7.7x SLA Recovery",
          "stage_summary": "7.7x higher SLA recovery (12 shipments) by applying the signed Amendment #2 rules automatically.",
          "numeric_value": 9600.0,
          "unit": "USD",
          "sql_or_gql": "SELECT\n  COUNT(*) AS qualifying_shipments,\n  ROUND(LEAST(SUM(l.shipment_fee_usd * o.credit_rate), ANY_VALUE(o.quarterly_cap_usd)), 2) AS recoverable_credit_usd\nFROM `example-project-id.sample_analytics.base_sla_ledger` l\nJOIN `example-project-id.sample_analytics.contract_sla_overlay` o\n  ON l.cargo_class = o.cargo_class\nWHERE l.peak_temp_c > o.temp_threshold_c\n  AND l.duration_min >= o.min_duration_min;",
          "query_language": "SQL",
          "context_mechanism": "Structured contract overlay extracted via Object Tables + AI.GENERATE",
          "context_payload": "{\n  \"source_document\": \"Vendor_Amendment_2.md\",\n  \"cargo_class\": \"BIOLOGIC_TEMP_CONTROL\",\n  \"temp_threshold_c\": 2.5,\n  \"min_duration_min\": 45,\n  \"credit_rate\": 0.12,\n  \"quarterly_cap_usd\": 25000.0\n}",
          "tokens_used": 510,
          "exploratory_queries": 1,
          "error_retries": 0,
          "eval_pass_count": 5,
          "eval_total_runs": 5,
          "trust_tier": "TIER_1_VERIFIED_OR_COMPILED",
          "rationale": "Structured SLA overlay reconciles unstructured legal amendments with telemetry.",
          "empirical_eval": {
            "model_id": "gemini-3.8-flash",
            "model_location": "global",
            "runs": 5,
            "pass_count": 5,
            "median_tokens": 760,
            "median_exploratory_queries": 1,
            "median_error_retries": 0,
            "median_latency_ms": 2760.0,
            "sample_sql_or_gql": "SELECT COUNT(*) AS qualifying_shipments, ROUND(LEAST(SUM(l.shipment_fee_usd * o.credit_rate), ANY_VALUE(o.quarterly_cap_usd)), 2) AS recoverable_credit_usd\nFROM `example-project-id.sample_analytics.base_sla_ledger` l\nJOIN `example-project-id.sample_analytics.contract_sla_overlay` o ON l.cargo_class = o.cargo_class\nWHERE l.peak_temp_c > o.temp_threshold_c AND l.duration_min >= o.min_duration_min;",
            "observed_signals": [
              "get_verified_metric_contract",
              "joined_sla_overlay",
              "object_table_ai_generate"
            ]
          }
        },
        "xray_summary": {
          "context_added": "Compact structured SLA policy overlay extracted from unstructured signed amendments.",
          "gcp_primitives": [
            "Gemini Enterprise Drive Connector (GA)",
            "BigQuery Object Tables (GA)",
            "BigQuery AI.GENERATE / DocAI (GA)"
          ],
          "negative_control_assertion": "Verified base ledger alone undercounts qualifying excursions; governed overlay captures full contractual recovery."
        }
      }
    ],
    "horizon_cards": [
      {
        "id": "knowledge_studio",
        "title": "Knowledge Studio (Context Sets & Enrichment Agent)",
        "release_badge": "Preview",
        "region_availability": "US / EU multi-regions (Preview; not yet in asia-southeast1)",
        "summary": "Curates reusable Context Sets and accelerates automated glossary/description enrichment in Knowledge Catalog across supported US and EU multi-regions.",
        "primitives": [
          "Knowledge Catalog Context Sets (Preview)",
          "Automated Metadata Enrichment Agent (Preview)",
          "Decoupled from R1–R6 asia-southeast1 Live Scope"
        ]
      },
      {
        "id": "open_lakehouse_federation",
        "title": "Cross-Cloud Lakehouse Catalog Federation",
        "release_badge": "GA",
        "region_availability": "Global / Multi-Cloud Federation (GA)",
        "summary": "Unifies governance across external lakehouse catalogs using distinct identity standards: Databricks Unity Catalog supports per-user OIDC (GA), Snowflake Horizon Catalog uses Workload Identity Federation (GA), and AWS Glue Data Catalog uses IAM role delegation (GA).",
        "primitives": [
          "Databricks Unity Catalog · Per-User OIDC (GA)",
          "Snowflake Horizon Catalog · Workload Identity Federation (GA)",
          "AWS Glue Data Catalog · IAM Role Delegation (GA)"
        ]
      }
    ]
  };
}
