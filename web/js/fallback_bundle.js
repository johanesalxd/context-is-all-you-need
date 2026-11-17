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
          "prompt": "Why do blind SQL agents frequently inflate revenue figures on clean warehouse tables?",
          "options": [
            {
              "key": "A",
              "text": "The LLM cannot generate valid SQL GROUP BY syntax."
            },
            {
              "key": "B",
              "text": "Gross invoice columns include tax and cancelled rows without schema predicates."
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
          "reveal_takeaway": "Table names alone do not encode revenue recognition rules; enriched column descriptions and Data Insights predicates constrain status and tax filters."
        },
        "blind": {
          "answer_headline": "USD 124,500.00",
          "answer_detail": "Sums gross_invoice_usd across all domestic records, sweeping in indirect tax and cancelled transactions.",
          "numeric_value": 124500.0,
          "unit": "USD",
          "sql_or_gql": "SELECT\n  ROUND(SUM(gross_invoice_usd), 2) AS revenue_usd\nFROM `example-project-id.sample_analytics.fact_orders`\nWHERE market_code = 'DOM';",
          "query_language": "SQL",
          "tokens_used": 1480,
          "exploratory_queries": 4,
          "error_retries": 2,
          "eval_pass_count": 0,
          "eval_total_runs": 5,
          "trust_tier": "TIER_3_REVIEW_REQUIRED",
          "rationale": "Guessed gross_invoice_usd without excluding cancelled rows or indirect tax."
        },
        "governed": {
          "answer_headline": "USD 98,200.00",
          "answer_detail": "Filters status = 'COMPLETED' and sums net_realized_usd ex-tax as defined in Knowledge Catalog metadata.",
          "numeric_value": 98200.0,
          "unit": "USD",
          "sql_or_gql": "SELECT\n  ROUND(SUM(net_realized_usd), 2) AS net_realized_revenue_usd\nFROM `example-project-id.sample_analytics.fact_orders`\nWHERE market_code = 'DOM'\n  AND status = 'COMPLETED';",
          "query_language": "SQL",
          "context_mechanism": "Column descriptions + Knowledge Catalog lookupContext predicate binding",
          "context_payload": "{\n  \"table\": \"fact_orders\",\n  \"metric_column\": \"net_realized_usd\",\n  \"required_predicates\": [\"status = 'COMPLETED'\", \"market_code = 'DOM'\"]\n}",
          "tokens_used": 410,
          "exploratory_queries": 1,
          "error_retries": 0,
          "eval_pass_count": 4,
          "eval_total_runs": 5,
          "trust_tier": "TIER_2_GROUNDED",
          "rationale": "Grounded in governed column metadata and canonical completion status predicate."
        },
        "xray_summary": {
          "context_added": "Column-level revenue recognition description plus Knowledge Catalog lookupContext status predicate.",
          "gcp_primitives": [
            "BigQuery Schema Metadata",
            "BigQuery Data Insights",
            "Knowledge Catalog lookupContext (Preview)"
          ],
          "negative_control_assertion": "Verified schema metadata enforces net_realized_usd over gross_invoice_usd and blocks unverified column guessing."
        }
      },
      {
        "id": "r2_glossary",
        "rung_num": 2,
        "short_label": "R2 · Glossary",
        "title": "Governed Business Glossary Term Resolution",
        "pyramid_layer": "Layer 4 · Knowledge Catalog Business Glossary",
        "release_badges": [
          {
            "capability": "Knowledge Catalog Business Glossary",
            "stage": "GA",
            "region_scope": "asia-southeast1"
          }
        ],
        "question": "Which channel led Closed Q4 Priority Tier Average Order Value?",
        "poll": {
          "prompt": "When two columns look semantically similar (e.g., marketing_tag vs account_tier_code), what fixes agent drift?",
          "options": [
            {
              "key": "A",
              "text": "Renumbering columns alphabetically in the warehouse."
            },
            {
              "key": "B",
              "text": "A governed Business Glossary mapping business terms to exact SQL predicates."
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
          "reveal_takeaway": "Fuzzy label matching traps blind agents on promo tags; a Knowledge Catalog Business Glossary binds 'Priority Tier' deterministically to account_tier_code."
        },
        "blind": {
          "answer_headline": "Self-Serve Portal (USD 195.00)",
          "answer_detail": "Matches marketing_tag LIKE '%Priority%', pulling in low-spend promotional trial campaigns.",
          "numeric_value": 195.0,
          "unit": "USD",
          "sql_or_gql": "SELECT\n  channel,\n  ROUND(AVG(o.net_realized_usd), 2) AS aov_usd\nFROM `example-project-id.sample_analytics.fact_orders` o\nJOIN `example-project-id.sample_analytics.dim_accounts` a USING (account_id)\nWHERE a.marketing_tag LIKE '%Priority%'\nGROUP BY channel\nORDER BY aov_usd DESC\nLIMIT 1;",
          "query_language": "SQL",
          "tokens_used": 1620,
          "exploratory_queries": 5,
          "error_retries": 2,
          "eval_pass_count": 0,
          "eval_total_runs": 5,
          "trust_tier": "TIER_3_REVIEW_REQUIRED",
          "rationale": "String-matched marketing_tag distractor column instead of governed tier_code."
        },
        "governed": {
          "answer_headline": "Enterprise Direct (USD 420.00)",
          "answer_detail": "Resolves Business Glossary term 'Priority Tier' to tier_code = 'TIER_A_EXEC', surfacing Enterprise Direct leadership.",
          "numeric_value": 420.0,
          "unit": "USD",
          "sql_or_gql": "SELECT\n  o.channel,\n  ROUND(AVG(o.net_realized_usd), 2) AS aov_usd\nFROM `example-project-id.sample_analytics.fact_orders` o\nJOIN `example-project-id.sample_analytics.dim_accounts` a USING (account_id)\nWHERE a.tier_code = 'TIER_A_EXEC'\n  AND o.status = 'COMPLETED'\nGROUP BY o.channel\nORDER BY aov_usd DESC\nLIMIT 1;",
          "query_language": "SQL",
          "context_mechanism": "Knowledge Catalog Business Glossary term-to-predicate binding",
          "context_payload": "{\n  \"glossary_term\": \"Priority Tier\",\n  \"canonical_predicate\": \"dim_accounts.tier_code = 'TIER_A_EXEC'\",\n  \"excluded_distractor\": \"dim_accounts.marketing_tag\"\n}",
          "tokens_used": 440,
          "exploratory_queries": 1,
          "error_retries": 0,
          "eval_pass_count": 5,
          "eval_total_runs": 5,
          "trust_tier": "TIER_2_GROUNDED",
          "rationale": "Glossary explicitly binds 'Priority Tier' to tier_code = 'TIER_A_EXEC' across 5/5 evals."
        },
        "xray_summary": {
          "context_added": "Business Glossary definition linking 'Priority Tier' to tier_code = 'TIER_A_EXEC'.",
          "gcp_primitives": [
            "Knowledge Catalog Business Glossary (GA)",
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
          "numeric_value": 11.4,
          "unit": "PCT",
          "sql_or_gql": "SELECT\n  ROUND(100.0 * SUM(o.net_realized_usd - l.line_cogs_usd - h.hop_cost_usd) / SUM(o.net_realized_usd), 1) AS margin_pct\nFROM `example-project-id.sample_analytics.fact_orders` o\nJOIN `example-project-id.sample_analytics.fact_order_lines` l USING (order_id)\nJOIN `example-project-id.sample_analytics.fact_transit_hops` h USING (order_id)\nWHERE o.fulfillment_mode = 'EXPRESS';",
          "query_language": "SQL",
          "tokens_used": 1890,
          "exploratory_queries": 6,
          "error_retries": 3,
          "eval_pass_count": 0,
          "eval_total_runs": 5,
          "trust_tier": "TIER_3_REVIEW_REQUIRED",
          "rationale": "1:N transit hop join duplicated header revenue and line COGS."
        },
        "governed": {
          "answer_headline": "29.6% Contribution Margin",
          "answer_detail": "Grain-locked CTE / Property Graph MEASURE() pre-aggregates transit hops to order grain before margin calculation.",
          "numeric_value": 29.6,
          "unit": "PCT",
          "sql_or_gql": "WITH hop_costs AS (\n  SELECT order_id, SUM(hop_cost_usd) AS total_hop_cost_usd\n  FROM `example-project-id.sample_analytics.fact_transit_hops`\n  GROUP BY order_id\n)\nSELECT\n  ROUND(100.0 * SUM(o.net_realized_usd - o.total_cogs_usd - hc.total_hop_cost_usd) / SUM(o.net_realized_usd), 1) AS margin_pct\nFROM `example-project-id.sample_analytics.fact_orders` o\nJOIN hop_costs hc USING (order_id)\nWHERE o.fulfillment_mode = 'EXPRESS'\n  AND o.status = 'COMPLETED';",
          "query_language": "SQL+GQL",
          "context_mechanism": "Grain-locked BigQuery Graph MEASURE() + Verified Query semantic contract",
          "context_payload": "{\n  \"metric\": \"express_contribution_margin_pct\",\n  \"grain\": \"order_id\",\n  \"measure_formula\": \"(net_realized_usd - total_cogs_usd - SUM(hop_cost_usd)) / net_realized_usd\"\n}",
          "tokens_used": 490,
          "exploratory_queries": 1,
          "error_retries": 0,
          "eval_pass_count": 5,
          "eval_total_runs": 5,
          "trust_tier": "TIER_1_VERIFIED_OR_COMPILED",
          "rationale": "Compiled Verified Query and MEASURE() eliminate 1:N join duplication."
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
          "prompt": "When 100+ staging shadow tables share similar names, how should an enterprise agent choose a source?",
          "options": [
            {
              "key": "A",
              "text": "Pick whichever table was modified most recently by any script."
            },
            {
              "key": "B",
              "text": "Route exclusively to certified Knowledge Catalog Data Products enforced by IAM & RLS."
            },
            {
              "key": "C",
              "text": "Union all tables together and average the outputs."
            },
            {
              "key": "D",
              "text": "Prompt the model to inspect table names and pick the cleanest spelling."
            }
          ],
          "correct_key": "B",
          "reveal_takeaway": "Certified Data Products eliminate stale staging clones, while BigQuery Row-Level Security enforces least-privilege visibility per caller identity."
        },
        "blind": {
          "answer_headline": "False Drop: 21.8% (-320 bps)",
          "answer_detail": "Scans uncertified staging_temp_margin_draft amid dozens of shadow tables, missing late-quarter supplier settlements.",
          "numeric_value": 21.8,
          "unit": "PCT",
          "sql_or_gql": "SELECT\n  ROUND(100.0 * SUM(gross_margin_usd) / SUM(net_revenue_usd), 1) AS margin_pct\nFROM `example-project-id.sample_analytics.staging_temp_margin_draft`;",
          "query_language": "SQL",
          "tokens_used": 2140,
          "exploratory_queries": 7,
          "error_retries": 3,
          "eval_pass_count": 1,
          "eval_total_runs": 5,
          "trust_tier": "TIER_3_REVIEW_REQUIRED",
          "rationale": "Selected stale uncertified draft table from uncurated schema catalog."
        },
        "governed": {
          "answer_headline": "25.0% Margin (-30 bps YoY)",
          "answer_detail": "Routes exclusively to certified temp_margin_gold Data Product (no false drop) and enforces caller Row-Level Security policy.",
          "numeric_value": 25.0,
          "unit": "PCT",
          "sql_or_gql": "SELECT\n  SUM(gross_margin_usd) AS visible_gross_margin_usd,\n  COUNT(*) AS rows_visible\nFROM `example-project-id.sample_analytics.temp_margin_gold`\nWHERE quarter = 'Q4';",
          "query_language": "SQL",
          "context_mechanism": "Knowledge Catalog Data Product certification + BigQuery Row Access Policy",
          "context_payload": "{\n  \"certified_asset\": \"temp_margin_gold\",\n  \"auto_dq_status\": \"PASSED\",\n  \"rls_policies\": [\"rls_global_full_access\", \"rls_apac_region_only\"]\n}",
          "tokens_used": 430,
          "exploratory_queries": 1,
          "error_retries": 0,
          "eval_pass_count": 5,
          "eval_total_runs": 5,
          "trust_tier": "TIER_1_VERIFIED_OR_COMPILED",
          "rationale": "Certified gold Data Product with active BigQuery Row-Level Security per identity."
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
          "context_added": "Certified Data Product routing plus role-bound BigQuery Row Access Policies.",
          "gcp_primitives": [
            "Knowledge Catalog Data Products (GA)",
            "Auto Data Quality (GA)",
            "BigQuery Row-Level Security (GA)"
          ],
          "negative_control_assertion": "Verified unauthorized direct queries to staging/unscoped partitions return explicit 403 accessDenied or strict 0/subset RLS row filtering."
        }
      },
      {
        "id": "r5_graph",
        "rung_num": 5,
        "short_label": "R5 · Graph",
        "title": "4-Hop Multi-Entity Supply Lineage via ISO GQL",
        "pyramid_layer": "Layer 4 · BigQuery Property Graph & ISO GQL",
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
          "numeric_value": 2950.0,
          "unit": "USD",
          "sql_or_gql": "SELECT\n  ROUND(SUM(o.net_realized_usd), 2) AS exposed_usd\nFROM `example-project-id.sample_analytics.fact_orders` o\nJOIN `example-project-id.sample_analytics.dim_batches` b\n  ON o.order_id = b.primary_order_id\nWHERE b.batch_code = '#LOT-804';",
          "query_language": "SQL",
          "tokens_used": 2380,
          "exploratory_queries": 8,
          "error_retries": 4,
          "eval_pass_count": 1,
          "eval_total_runs": 5,
          "trust_tier": "TIER_3_REVIEW_REQUIRED",
          "rationale": "Missed intermediate allocation bridge and Priority Tier glossary predicate."
        },
        "governed": {
          "answer_headline": "USD 12,400.00 across 24 Priority Orders",
          "answer_detail": "Executes 4-hop GRAPH_TABLE ISO GQL traversal from SupplyLot '#LOT-804' through Allocations, Lines, and Orders to TIER_A_EXEC Accounts.",
          "numeric_value": 12400.0,
          "unit": "USD",
          "sql_or_gql": "SELECT\n  COUNT(DISTINCT order_id) AS exposed_orders,\n  ROUND(SUM(net_realized_usd), 2) AS exposed_revenue_usd\nFROM GRAPH_TABLE(\n  `example-project-id.sample_analytics.sample_supply_graph`\n  MATCH (b:SupplyBatch {batch_code: '#LOT-804'})-[:ALLOCATED_TO]->(a:LotAllocation)-[:FULFILLED_BY]->(l:OrderLine)-[:PART_OF]->(o:Order)-[:PLACED_BY]->(c:Account {tier_code: 'TIER_A_EXEC'})\n  RETURN o.order_id, o.net_realized_usd\n);",
          "query_language": "GQL",
          "context_mechanism": "BigQuery Property Graph schema topology + ISO GQL GRAPH_TABLE",
          "context_payload": "{\n  \"graph\": \"sample_supply_graph\",\n  \"traversal\": \"SupplyBatch -> LotAllocation -> OrderLine -> Order -> Account[TIER_A_EXEC]\",\n  \"target_batch\": \"#LOT-804\"\n}",
          "tokens_used": 520,
          "exploratory_queries": 1,
          "error_retries": 0,
          "eval_pass_count": 5,
          "eval_total_runs": 5,
          "trust_tier": "TIER_1_VERIFIED_OR_COMPILED",
          "rationale": "Property Graph edges enforce complete 4-hop lineage consistent with R2 Priority Tier definition."
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
          "numeric_value": 1250.0,
          "unit": "USD",
          "sql_or_gql": "SELECT\n  ROUND(SUM(shipment_fee_usd * 0.05), 2) AS recoverable_credit_usd\nFROM `example-project-id.sample_analytics.base_sla_ledger`\nWHERE peak_temp_c > 5.0\n  AND duration_min >= 90;",
          "query_language": "SQL",
          "tokens_used": 1750,
          "exploratory_queries": 5,
          "error_retries": 1,
          "eval_pass_count": 0,
          "eval_total_runs": 5,
          "trust_tier": "TIER_3_REVIEW_REQUIRED",
          "rationale": "Ignored executed vendor SLA amendment residing in document storage."
        },
        "governed": {
          "answer_headline": "USD 9,600.00 across 12 Qualifying Shipments",
          "answer_detail": "Joins structured contract_sla_overlay extracted from Vendor_Amendment_2.md (> 2.5C for 45m -> 12% credit, capped at USD 25,000).",
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
          "rationale": "Structured SLA overlay reconciles unstructured legal amendments with telemetry."
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
