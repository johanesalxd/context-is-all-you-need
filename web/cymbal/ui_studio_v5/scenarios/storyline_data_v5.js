/**
 * Data Leaders Forum Singapore (Nov 26, 2026) - "Context Is All You Need"
 * Version 2.1 Shared Data Module: window.DEMO_SCENARIOS_V5
 *
 * Storyline A (CMO Marketing - "The Phantom Holiday Boom: Rescue Q4") is set as defaultScenarioId.
 * Zero spoilers in Raw Schema mode; reconciled arithmetic verified end-to-end.
 */
(function (global) {
  "use strict";

  const DEMO_SCENARIOS_V5 = {
    schemaVersion: "5.0.0",
    defaultScenarioId: "storyline_a_cmo_q4",
    productMeta: {
      agentName: "Gemini for Cymbal",
      defaultMode: "blind",
      ungroundedLabel: "Raw Schema",
      groundedLabel: "Knowledge Catalog",
      catalogName: "Knowledge Catalog",
      mcpEndpoint: "https://dataplex.googleapis.com/mcp",
      previewBadges: [
        "Knowledge Studio",
        "Enrichment Agent",
        "Context Sets",
        "Governance Workflows"
      ],
      benchmark: {
        spider1: 91.2,
        bird: 73.0,
        spider2: 21.3,
        tagline: "Intelligence did not fall 70 points. Context did."
      },
      shortcuts: [
        { key: "Space / Enter", label: "Next step (Raw -> Knowledge Catalog -> Next Q)" },
        { key: "G", label: "Flip current turn: Raw Schema <-> Knowledge Catalog" },
        { key: "X", label: "Open / close simplified Context panel (Jo)" },
        { key: "1 - 7", label: "Jump to Q1 - Q6 (or 7 for Session Audit)" },
        { key: "T", label: "Toggle Daylight / Dark theme" },
        { key: "F", label: "Toggle clean stage fullscreen" },
        { key: "N", label: "Start new chat" },
        { key: "Shift + P", label: "Open discreet presenter settings" }
      ]
    },

    scenarios: {
      storyline_a_cmo_q4: {
        id: "storyline_a_cmo_q4",
        shortLabel: "Cymbal Commerce - CMO Q4 Rescue (6 Turns)",
        company: "Cymbal Commerce",
        period: "Q3 FY26 -> 12.12 & LNY Plan (SGD)",
        currency: "SGD",
        region: "Singapore (Demo Environment)",
        projectId: "cymbal-commerce-prod",
        contextSetId: "cymbal-commerce-1212-marketing",
        contextSetDisplay: "Cymbal Commerce Marketing & Fraud Context",
        autoThreadTitle: "Q3 Campaign ROI & 12.12 / LNY Plan",
        persona: {
          name: "Samir Gupta",
          role: "Cymbal Commerce",
          initials: "SG",
          email: "samir.gupta@example.com",
          greeting: "What's top of mind?",
          greetingSub: ""
        },
        ambientHistory: [
          {
            id: "hist-cmo-1",
            title: "Q3 SEA agency status sync",
            when: "Yesterday",
            note: "Weekly agency creative and pacing notes."
          },
          {
            id: "hist-cmo-2",
            title: "Find pending action items from com...",
            when: "2 days ago",
            note: "Cross-team leadership follow-ups."
          },
          {
            id: "hist-cmo-3",
            title: "Google Calendar meeting preparati...",
            when: "3 days ago",
            note: "Briefing notes for upcoming executive reviews."
          },
          {
            id: "hist-cmo-4",
            title: "Executive board deck review notes",
            when: "Last week",
            note: "Regional retail trends and brand metrics."
          },
          {
            id: "hist-cmo-5",
            title: "12.12 creative assets sign-off",
            when: "Last week",
            note: "Final approvals for seasonal creative banners."
          }
        ],
        starterOptions: [
          {
            label: "How much net revenue did our Q3 campaign actually keep after returns?",
            subtitle: "Attributed ex-GST settled sales and return impact",
            kind: "primary",
            targetTurnIndex: 0
          },
          {
            label: "Summarize our Q3 SGD 400K media spend split across SEA channels",
            subtitle: "SG Paid Social, MY Paid Social, and B2B/Search allocation",
            kind: "sibling",
            siblingId: "starter_q3_spend"
          },
          {
            label: "Break down Q3 campaign order volumes across Singapore and Malaysia",
            subtitle: "Channel volume mix across SG, MY, and B2B/Search",
            kind: "sibling",
            siblingId: "starter_q3_volumes"
          }
        ],

        turns: [
          {
            id: "t1",
            simpleContext: {
              mainVisual: "waterfall_bridge",
              badge: "Agreed Definitions",
              productTag: "Knowledge Catalog · Business Glossary + Verified Query",
              oneLiner: "Finance's official definition of Net Revenue and Returns is stored once, so the AI never guesses which column to sum.",
              withoutLabel: "Raw Schema guessed",
              withoutText: "Summed raw gross orders (with 9% GST + organic traffic) and read zeroed post-refund rows as SGD 0 returns.",
              withLabel: "Knowledge Catalog enforced",
              withText: "Applied Finance's Net Campaign Revenue rule and Verified Query to separate SGD 620K net from SGD 240K returns.",
              deltaBefore: "SGD 1.85M Sales · SGD 0 Returns",
              deltaAfter: "SGD 620K Net · SGD 240K Returns",
              swingTag: "3x overstatement caught"
            },
            index: 1,
            turnTitle: "Q3 Net Campaign Revenue",
            prompt: "How much net revenue did our Q3 campaign actually keep after returns?",
            layerFeature: "Business Glossary + Verified Queries",
            layerStatus: "GA",
            visualStory: {
              archetype: "column_spotlight",
              contextBuildingBlock: "Business Glossary + Verified Queries",
              kicker: "Inside the Table: Gross Inflation & Zeroed Post-Refund Cash",
              gapHeadline: "Raw SQL sums gross orders (incl. GST + organic) & zeroed refunds",
              groundedHeadline: "Glossary + #VQ-M1 separates SGD 620K net from SGD 240K returns",
              rawSummary: "SGD 1.85M sales | SGD 0 returns",
              governedSummary: "SGD 620K net | SGD 240K returns",
              rawPrecision: "4 exploratory SQLs",
              governedPrecision: "1 governed SQL",
              tableName: "cymbal_commerce.campaign_orders",
              columns: [
                "order_segment",
                "gross_order_value",
                "net_settled & return_sgd"
              ],
              rawColIndex: 1,
              governedColIndex: 2,
              rawCallout: "Sums gross_order_value (incl. 9% GST + organic) & reads zeroed post-refund cash",
              governedCallout: "KC Glossary + #VQ-M1 locks net_attributed_settled_sgd & return_value_sgd",
              rows: [
                ["Attributed Settled", "SGD 1.85M (incl. GST + org)", "SGD 620K net settled"],
                ["Attributed Returned", "SGD 0.00 post-refund", "SGD 240K return_value_sgd"],
                ["Attributed Gross Base", "Unfiltered gross rows", "SGD 860K ex-GST & organic"]
              ],
              takeaway: "Business Glossary definitions and Verified Query #VQ-M1 strip 9% GST and organic traffic to reveal SGD 620K net sales and SGD 240K in returns."
            },
            blind: {
              headlineValue: "SGD 1.85M Sales | SGD 0 Returns",
              headlineUnit: "+198% vs. Q3 target - full campaign revenue retained",
              badgeText: "BigQuery · Raw Schema",
              badgeTone: "neutral",
              summary: "Your Q3 campaign delivered a breakout quarter with **SGD 1.85M in campaign sales** (**+198% vs. target**) across Singapore and Malaysia, with **SGD 0** recorded in return losses - meaning the full **SGD 1.85M** stayed on the books.",
              consequence: "",
              rootCauseTitle: "Gross Order Inflation & Post-Refund Zeroing",
              rootCause: "Without catalog definitions, raw SQL summed `gross_order_value` (including 9% GST and unattributed organic orders) and read `amt_net_settled_sgd`, which resets to `0.00` once a refund clears.",
              thinkingSteps: [
                { active: "Scanning 199 tables in cymbal_dw...", done: "Scanned 199 raw tables in cymbal_dw", meta: "0.5s", code: "INFORMATION_SCHEMA" },
                { active: "Probing campaign order and return columns...", done: "Probed gross_order_value and amt_net_settled_sgd", meta: "1.4s", code: "4 exploratory SQLs" },
                { active: "Running BigQuery aggregation...", done: "Aggregated Q3 campaign sales and post-refund balance", meta: "4.6s", code: "BigQuery SQL" }
              ],
              queryLang: "SQL",
              queryCode: "SELECT\n  ROUND(SUM(gross_order_value), 2) AS campaign_sales_sgd,\n  ROUND(SUM(IF(order_status = 'RETURNED', amt_net_settled_sgd, 0)), 2) AS return_losses_sgd\nFROM cymbal_dw.campaign_orders\nWHERE campaign_quarter = 'FY26_Q3';",
              kpis: [
                { label: "Campaign Sales", value: "SGD 1.85M", delta: "+198% vs Q3 target", tone: "neutral" },
                { label: "Campaign Returns", value: "SGD 0", delta: "Zero net return impact", tone: "neutral" },
                { label: "Query Execution", value: "4 exploratory SQLs", delta: "199 warehouse tables", tone: "neutral" }
              ],
              chart: {
                type: "bar",
                title: "Q3 Campaign Sales & Returns (Raw Schema)",
                items: [
                  { label: "Campaign Sales (SG + MY)", value: 1850000, display: "SGD 1.85M", tone: "primary" },
                  { label: "Post-Refund Return Balance", value: 0, display: "SGD 0", tone: "slate" }
                ]
              },
              table: {
                headers: ["Campaign Segment", "Gross Order Value", "Post-Refund Settled"],
                rows: [
                  ["SG & MY Campaign Orders", "SGD 1,850,000", "SGD 1,850,000"],
                  ["Returned Campaign Rows", "Included in gross", "SGD 0.00"]
                ]
              },
              citations: [
                { title: "cymbal_dw.campaign_orders", subtitle: "BigQuery Table", snippet: "Campaign orders and settlement amounts in cymbal_dw." }
              ],
              telemetry: { tokens: 3000, sqlCount: 4, latencySec: 4.6, tablesScanned: 199, accuracy: 0, queryLabel: "4 exploratory SQLs · 199 tables" }
            },
            governed: {
              headlineValue: "SGD 620K Net | SGD 240K Returns",
              headlineUnit: "On SGD 860K gross attributed orders (ex-9% GST & organic)",
              badgeText: "Grounded in Knowledge Catalog",
              badgeTone: "success",
              summary: "Cymbal Commerce kept only **SGD 620K in real net sales** on **SGD 860K gross attributed orders** (once 9% GST and organic traffic are stripped out) - and **SGD 240K came straight back as returns**.",
              consequence: "Separates real SGD 620K settled revenue from 9% GST and organic traffic while exposing the SGD 240K return bleed immediately.",
              fixTitle: "Business Glossary + Verified Query #VQ-M1",
              fixSummary: "Knowledge Catalog binds `Net Campaign Revenue` to ex-GST attributed settled orders (`net_attributed_settled_sgd`) and preserves pre-refund return exposure via `return_value_sgd` in 1 governed SQL.",
              thinkingSteps: [
                { active: "Searching Knowledge Catalog Glossary...", done: "Matched 'Net Campaign Revenue' & campaign_orders", meta: "0.2s", code: "SearchEntries" },
                { active: "Calling LookupContext via MCP...", done: "Loaded curated table semantics + Verified Query #VQ-M1", meta: "0.3s", code: "LookupContext" },
                { active: "Running Verified Query #VQ-M1...", done: "Executed 1 governed BigQuery SQL query", meta: "1.2s", code: "Verified Query #VQ-M1" }
              ],
              queryLang: "SQL",
              queryCode: "SELECT\n  ROUND(SUM(attributed_ex_gst_sgd), 0) AS gross_attributed_sgd,\n  ROUND(SUM(return_value_sgd), 0) AS campaign_returns_sgd,\n  ROUND(SUM(net_attributed_settled_sgd), 0) AS net_settled_sales_sgd\nFROM cymbal_commerce.campaign_orders\nWHERE campaign_quarter = 'FY26_Q3'\n  AND attribution_type = 'PAID_CAMPAIGN';",
              kpis: [
                { label: "Net Settled Sales", value: "SGD 620K", delta: "On SGD 860K gross attributed", tone: "success" },
                { label: "Campaign Returns", value: "SGD 240K", delta: "27.9% gross return rate", tone: "danger" },
                { label: "Query Precision", value: "1 governed SQL", delta: "Verified Query #VQ-M1", tone: "primary" }
              ],
              chart: {
                type: "bar",
                title: "Q3 Attributed Campaign Revenue vs. Returns (ex-GST SGD)",
                items: [
                  { label: "Net Settled Campaign Sales", value: 620000, display: "SGD 620K", tone: "success" },
                  { label: "Pre-Refund Campaign Returns", value: 240000, display: "SGD 240K", tone: "danger" },
                  { label: "Gross Attributed Orders", value: 860000, display: "SGD 860K", tone: "primary" }
                ]
              },
              table: {
                headers: ["Governed Metric", "Scope", "Amount (ex-GST)", "Catalog Rule"],
                rows: [
                  ["Gross Attributed Orders", "SG PS + MY PS + B2B", "SGD 860K", "Excl. 9% GST & organic"],
                  ["Campaign Returns", "Returned orders", "SGD 240K", "SUM(return_value_sgd)"],
                  ["Net Settled Sales", "Kept post-return", "SGD 620K", "net_attributed_settled_sgd"]
                ]
              },
              citations: [
                { title: "cymbal_commerce.campaign_orders", subtitle: "Knowledge Catalog Table Aspect", snippet: "Use return_value_sgd for pre-refund return exposure; net_attributed_settled_sgd excludes 9% GST & organic." },
                { title: "net-campaign-revenue", subtitle: "Business Glossary Term (GA)", snippet: "Settled ex-GST revenue attributed to paid campaign touchpoints after returns." },
                { title: "Verified Query #VQ-M1", subtitle: "Context Set Query Template", snippet: "Governed Q3 campaign net revenue and return-bleed calculation." }
              ],
              telemetry: { tokens: 900, sqlCount: 1, latencySec: 1.2, tablesScanned: 1, accuracy: 100, queryLabel: "1 governed SQL · Verified Query #VQ-M1" }
            },
            rlsRoles: null,
            kcProvenance: {
              aggregation: {
                source: "BigQuery Table (Zero Movement)",
                assetPath: "bigquery://cymbal-commerce-prod.cymbal_commerce.campaign_orders",
                signals: ["Column descriptions & profiles harvested", "Marketing Q2/Q3 query logs analyzed"]
              },
              enrichment: {
                loop: "Observe -> Enrich -> Validate -> Promote",
                observedGap: "Raw queries summed gross_order_value (incl. 9% GST + organic) and read zeroed post-refund settlement columns.",
                proposalText: "Bind Business Glossary 'net-campaign-revenue' to net_attributed_settled_sgd and document return_value_sgd.",
                confidence: "98% (High)",
                evalCheck: "12/12 attribution evals passed",
                changeRequest: {
                  id: "CR-2026-0301",
                  status: "APPROVED",
                  steward: "Mei Ling Chong (Marketing Finance Steward)",
                  timestamp: "2026-10-19 09:15 SGT"
                }
              },
              retrieval: {
                contextSet: "cymbal-commerce-1212-marketing [Preview]",
                mcpCall: "dataplex.googleapis.com/mcp -> lookup_context",
                assetsCount: 1,
                tokenBudget: "Context Set Verified Query #VQ-M1",
                yamlSnippet: "resources:\n  - simpleName: cymbal_commerce.campaign_orders\n    glossaryTerm: net-campaign-revenue\n    guidelines:\n      - \"Net Settled Sales = SUM(net_attributed_settled_sgd) WHERE attribution_type = 'PAID_CAMPAIGN' (ex-GST).\"\n      - \"Return exposure = SUM(return_value_sgd); do not use post-refund zeroed cash columns.\""
              }
            },
            blindFollowUps: [
              {
                label: "Re-run Q1 with Knowledge Catalog",
                kind: "ground"
              },
              {
                label: "Summarize our Q3 SGD 400K media spend split across SEA channels",
                kind: "sibling",
                siblingId: "starter_q3_spend"
              },
              {
                label: "Break down Q3 campaign order volumes across Singapore and Malaysia",
                kind: "sibling",
                siblingId: "starter_q3_volumes"
              }
            ],
            followUps: [
              {
                label: "What actually drove that spike in our Q3 campaign returns?",
                kind: "primary",
                targetTurnIndex: 1
              },
              {
                label: "Break down the SGD 860K gross attributed orders by market and channel",
                kind: "sibling",
                siblingId: "q1_market_split"
              },
              {
                label: "Compare Q3 campaign return volume against our Q2 SGD 36K baseline",
                kind: "sibling",
                siblingId: "q1_q2_returns"
              }
            ]
          },

          {
            id: "t2",
            simpleContext: {
              mainVisual: "donut_drivers",
              badge: "Certified Data + Root Cause",
              productTag: "Certified Table · AI.KEY_DRIVERS() · End-User Credentials",
              oneLiner: "Blocks messy staging tables and runs automated root-cause analysis on clean, certified data.",
              withoutLabel: "Raw Schema guessed",
              withoutText: "Picked a staging copy where 42% of country rows were blank, falsely blaming Malaysia Mobile (68%).",
              withLabel: "Knowledge Catalog enforced",
              withText: "Routed to the 0%-blank Certified table so AI.KEY_DRIVERS() pinned 82.5% of returns (SGD 198K) on SG Paid Social.",
              deltaBefore: "Blamed Malaysia (68%)",
              deltaAfter: "SG Paid Social: SGD 198K (82.5%)",
              swingTag: "Saved profitable MY market",
              eucNote: "Every query runs under End-User Credentials (EUC): as CMO you see SG + MY, while a SG Manager automatically sees only SG (SGD 206K)."
            },
            index: 2,
            turnTitle: "Return Spike Root Cause",
            prompt: "What actually drove that spike in our Q3 campaign returns?",
            layerFeature: "Certified Data + AI.KEY_DRIVERS()",
            layerStatus: "GA",
            visualStory: {
              archetype: "dq_driver_rls",
              contextBuildingBlock: "Certified Data + AI.KEY_DRIVERS()",
              kicker: "Data Quality Gate + AI.KEY_DRIVERS() + BigQuery Row-Level Security",
              gapHeadline: "42% NULL staging copy blames Malaysia Mobile & leaks all markets",
              groundedHeadline: "Certified 0% NULL table isolates SG Paid Social + enforces RLS",
              rawSummary: "Malaysia Mobile (68%)",
              governedSummary: "SG Paid Social: SGD 198K",
              rawPrecision: "42% NULL staging · 0 RLS",
              governedPrecision: "0% NULL certified · RLS",
              stagingGateLabel: "Staging Copy: 42% NULL - BLOCKED",
              certifiedGateLabel: "Certified Table: 0% NULL - ACTIVE",
              driverTitle: "SG Paid Social Promo-Trial",
              driverDelta: "+SGD 162K vs Q2 (SGD 198K · 44.0% ret · 91% promo)",
              rlsMarkets: [
                { code: "SG", name: "SG Paid Social Promo-Trial", rate: "44.0% ret · 91% promo", amount: "SGD 198K", rawAmount: "21% share", sgAllowed: true, tone: "danger" },
                { code: "SG", name: "SG B2B / Search", rate: "6.7% ret", amount: "SGD 8K", rawAmount: "7% share", sgAllowed: true, tone: "ok" },
                { code: "MY", name: "MY Paid Social", rate: "13.0% ret", amount: "SGD 30K", rawAmount: "68% share", sgAllowed: false, tone: "ok" },
                { code: "MY", name: "MY B2B / Search", rate: "6.7% ret", amount: "SGD 4K", rawAmount: "4% share", sgAllowed: false, tone: "ok" }
              ],
              takeaway: "Routing to the Certified 0%-NULL table lets AI.KEY_DRIVERS() isolate SG Paid Social (+SGD 162K) while BigQuery RLS restricts non-authorized markets at storage."
            },
            blind: {
              headlineValue: "Malaysia Mobile (68%)",
              headlineUnit: "Drove the Q3 return spike - recommend pausing Malaysia",
              badgeText: "BigQuery · Raw Schema",
              badgeTone: "neutral",
              summary: "Root-cause analysis flags **Malaysia Mobile shoppers** as driving **68% of Q3 campaign returns**, while Singapore and B2B/Search remain minor slices. **Recommendation: pause Malaysia Paid Social immediately**.",
              consequence: "",
              rootCauseTitle: "42% NULL Staging Copy & Missing RLS Policy",
              rootCause: "Raw schema routed to `campaign_returns_raw` with 42% blank country/channel values, distorting attribution toward Malaysia Mobile while exposing cross-country rows without Row-Level Security.",
              thinkingSteps: [
                { active: "Scanning campaign return tables...", done: "Selected cymbal_dw.campaign_returns_raw", meta: "0.5s", code: "BigQuery Table" },
                { active: "Running segment breakdown across return rows...", done: "Aggregated return share by device and market", meta: "1.9s", code: "5 exploratory SQLs" },
                { active: "Generating recommendation...", done: "Identified Malaysia Mobile (68%) as primary driver", meta: "5.1s", code: "BigQuery SQL" }
              ],
              queryLang: "SQL",
              queryCode: "SELECT\n  market_segment,\n  ROUND(100.0 * SUM(return_sgd) / SUM(SUM(return_sgd)) OVER(), 1) AS return_share_pct\nFROM cymbal_dw.campaign_returns_raw\nGROUP BY market_segment\nORDER BY return_share_pct DESC;",
              kpis: [
                { label: "Top Return Driver", value: "Malaysia Mobile", delta: "68% share of returns", tone: "neutral" },
                { label: "Recommended Action", value: "Pause MY Social", delta: "Halt Malaysia spend", tone: "neutral" },
                { label: "Query Execution", value: "5 exploratory SQLs", delta: "Q3 campaign returns dataset", tone: "neutral" }
              ],
              chart: {
                type: "bar",
                title: "Q3 Campaign Return Share by Segment (Raw Schema)",
                items: [
                  { label: "Malaysia Mobile", value: 68, display: "68.0%", tone: "primary" },
                  { label: "Singapore Paid Social", value: 21, display: "21.0%", tone: "slate" },
                  { label: "B2B / Search", value: 11, display: "11.0%", tone: "slate" }
                ]
              },
              table: {
                headers: ["Market / Segment", "Return Share", "Action", "Dataset Scope"],
                rows: [
                  ["Malaysia Mobile", "68.0%", "Pause campaign", "MY + SG regional dataset"],
                  ["Singapore Paid Social", "21.0%", "Keep running", "MY + SG regional dataset"],
                  ["B2B / Search", "11.0%", "Keep running", "MY + SG regional dataset"]
                ]
              },
              citations: [
                { title: "cymbal_dw.campaign_returns_raw", subtitle: "BigQuery Table", snippet: "Campaign returns segment table in cymbal_dw." }
              ],
              telemetry: { tokens: 3400, sqlCount: 5, latencySec: 5.1, tablesScanned: 199, accuracy: 0, queryLabel: "5 exploratory SQLs · 199 tables" }
            },
            governed: {
              headlineValue: "SG Paid Social: SGD 198K (82.5%)",
              headlineUnit: "82.5% share of returns | 44.0% channel return rate | +SGD 162K vs Q2",
              badgeText: "Grounded in Knowledge Catalog",
              badgeTone: "success",
              summary: "Not Malaysia - automated root-cause analysis (**AI.KEY_DRIVERS**) on certified data isolates **Singapore Paid Social promo-trial signups** as driving **82.5% of all returns (SGD 198K)**, with a **44.0% return rate** and **91% promo usage** (+SGD 162K vs. Q2). Malaysia (**SGD 30K**, 13.0%) and B2B/Search (**SGD 12K**, 6.7%) stayed completely healthy.",
              consequence: "Stops you from pausing profitable Malaysia Paid Social - and because queries execute under End-User Credentials (EUC), country managers stay scoped to their own market.",
              fixTitle: "Certified Data + AI.KEY_DRIVERS() + BigQuery RLS",
              fixSummary: "Auto Data Quality blocks the 42%-NULL staging copy and routes `AI.KEY_DRIVERS()` to the Certified table across 4 key dimensions while BigQuery RLS masks non-authorized markets for SG Managers.",
              thinkingSteps: [
                { active: "Filtering Knowledge Catalog for CERTIFIED aspect...", done: "Locked cymbal_commerce.campaign_returns_certified (0% NULL)", meta: "0.2s", code: "CERTIFIED + Auto DQ" },
                { active: "Running AI.KEY_DRIVERS() + BigQuery RLS...", done: "Scanned 4 key dimensions (Q3 vs Q2) under caller RLS", meta: "0.4s", code: "AI.KEY_DRIVERS()" },
                { active: "Summarizing driver rates...", done: "Pinned 82.5% share (SGD 198K) to SG Paid Social Promo-Trial", meta: "1.1s", code: "1 governed SQL" }
              ],
              queryLang: "SQL",
              queryCode: "SELECT *\nFROM AI.KEY_DRIVERS(\n  TABLE cymbal_commerce.campaign_returns_certified,\n  metric_col => 'return_value_sgd',\n  dimension_cols => ['country_code', 'channel', 'promo_tier', 'device_type'],\n  interest_label_col => 'is_q3'\n);",
              kpis: [
                { label: "Primary Culprit", value: "SG Paid Social", delta: "SGD 198K (82.5% share)", tone: "danger" },
                { label: "Channel Return Rate", value: "44.0% ret | 91%", delta: "+SGD 162K vs SGD 36K Q2", tone: "warning" },
                { label: "Healthy Channels", value: "MY 13.0% | B2B 6.7%", delta: "12.5% & 5.0% shares", tone: "success" }
              ],
              chart: {
                type: "bar",
                title: "Q3 Campaign Returns by Channel (CMO - All Markets)",
                items: [
                  { label: "SG Paid Social Promo-Trial (44.0% channel rate)", value: 198000, display: "SGD 198K (82.5% share)", tone: "danger" },
                  { label: "MY Paid Social (13.0% channel rate)", value: 30000, display: "SGD 30K (12.5% share)", tone: "success" },
                  { label: "B2B / Search (6.7% channel rate: 8K SG + 4K MY)", value: 12000, display: "SGD 12K (5.0% share)", tone: "primary" }
                ]
              },
              table: {
                headers: ["Channel / Segment", "Q3 Returns", "Share of Returns", "Channel Return Rate", "RLS Scope"],
                rows: [
                  ["SG Paid Social Promo-Trial", "SGD 198K", "82.5%", "44.0% (91% promo)", "Authorized (SG)"],
                  ["MY Paid Social", "SGD 30K", "12.5%", "13.0% (18% promo)", "Authorized (MY)"],
                  ["B2B / Search (8K SG + 4K MY)", "SGD 12K", "5.0%", "6.7% (4% promo)", "Authorized (All)"]
                ]
              },
              citations: [
                { title: "cymbal_commerce.campaign_returns_certified", subtitle: "KC Certified Data Product (GA)", snippet: "Auto DQ PASSED (0% NULL); staging copy with 42% NULL marked UNCERTIFIED." },
                { title: "AI.KEY_DRIVERS()", subtitle: "BigQuery Root-Cause Engine (GA)", snippet: "Isolated SG Paid Social Promo-Trial (+SGD 162K vs SGD 36K Q2) across 4 key dimensions." },
                { title: "BigQuery Row-Level Security", subtitle: "rls_cmo_all_markets / rls_sg_manager_only", snippet: "Storage-layer row masking enforced automatically with identical SQL." }
              ],
              telemetry: { tokens: 640, sqlCount: 1, latencySec: 1.1, tablesScanned: 1, accuracy: 100, queryLabel: "1 governed SQL · Certified + AI.KEY_DRIVERS()" }
            },
            rlsRoles: null,
            kcProvenance: {
              aggregation: {
                source: "BigQuery Certified Data Product + Auto DQ + RLS",
                assetPath: "bigquery://cymbal-commerce-prod.cymbal_commerce.campaign_returns_certified",
                signals: ["Auto Data Quality PASSED (0% NULL)", "Staging copy (42% NULL) tagged UNCERTIFIED", "RLS policies synced"]
              },
              enrichment: {
                loop: "Observe -> Enrich -> Validate -> Promote",
                observedGap: "Queries hit campaign_returns_raw (42% NULL values, no RLS), blaming Malaysia Mobile.",
                proposalText: "Promote Certified Data Product aspect on campaign_returns_certified and bind BigQuery RLS policies.",
                confidence: "100% (Deterministic)",
                evalCheck: "Auto DQ + SG Manager RLS isolation verified",
                changeRequest: {
                  id: "CR-2026-0302",
                  status: "APPROVED",
                  steward: "Wei Jie Tan (Data Governance Lead)",
                  timestamp: "2026-10-20 11:20 SGT"
                }
              },
              retrieval: {
                contextSet: "cymbal-commerce-1212-marketing [Preview]",
                mcpCall: "dataplex.googleapis.com/mcp -> lookup_context",
                assetsCount: 1,
                tokenBudget: "Certified Data Product + RLS",
                yamlSnippet: "resources:\n  - simpleName: cymbal_commerce.campaign_returns_certified\n    certification: CERTIFIED\n    qualityStatus: PASSED (0% NULL)\n    rowAccessPolicies: [rls_cmo_all_markets, rls_sg_manager_only]\n    guidelines:\n      - \"Always run AI.KEY_DRIVERS() on campaign_returns_certified; never query staging tables.\""
              }
            },
            blindFollowUps: [
              {
                label: "Re-run Q2 with Knowledge Catalog",
                kind: "ground"
              },
              {
                label: "Summarize our Q3 SGD 400K media spend split across SEA channels",
                kind: "sibling",
                siblingId: "starter_q3_spend"
              },
              {
                label: "Break down Q3 campaign order volumes across Singapore and Malaysia",
                kind: "sibling",
                siblingId: "starter_q3_volumes"
              }
            ],
            followUps: [
              {
                label: "After ad spend, discounts, and shipping, which channels actually made money?",
                kind: "primary",
                targetTurnIndex: 2
              },
              {
                label: "Compare SG Paid Social vs. MY Paid Social promo code usage rates",
                kind: "sibling",
                siblingId: "q2_promo_split"
              },
              {
                label: "Inspect the 42% NULL anomalies blocked in the staging table",
                kind: "sibling",
                siblingId: "q2_dq_blocked"
              }
            ]
          },

          {
            id: "t3",
            simpleContext: {
              mainVisual: "diverging_pnl",
              badge: "Locked Metric Math",
              productTag: "BigQuery Semantic MEASURE()",
              oneLiner: "Locks revenue to the order level and spend to the campaign level so AI queries can never double-count.",
              withoutLabel: "Raw Schema guessed",
              withoutText: "Joined orders to multi-touch ad clicks, inflating contribution 1.78x and inventing a fake +48% ROI (+SGD 192K).",
              withLabel: "Knowledge Catalog enforced",
              withText: "Used grain-locked MEASURE() definitions so revenue counts once per order, revealing -SGD 68K overall (-SGD 156K SG).",
              deltaBefore: "+SGD 192K (+48% ROI)",
              deltaAfter: "-SGD 68K (-17% ROI)",
              swingTag: "SGD 260K profit swing"
            },
            index: 3,
            turnTitle: "Channel P&L & MEASURE()",
            prompt: "After ad spend, discounts, and shipping, which channels actually made money?",
            layerFeature: "BigQuery Semantic MEASURE()",
            layerStatus: "GA",
            visualStory: {
              archetype: "fanout_exploder",
              contextBuildingBlock: "BigQuery Semantic MEASURE()",
              kicker: "1.78x Click Fan-Out Trap vs. Grain-Locked MEASURE()",
              gapHeadline: "Flat SQL joins orders x clicks, inflating contribution 1.78x (+48%)",
              groundedHeadline: "MEASURE() locks Order & Campaign grain -> 332K - 400K = -SGD 68K",
              rawSummary: "+48% ROI (+SGD 192K)",
              governedSummary: "-SGD 68K (-17% ROI)",
              rawPrecision: "4 exploratory SQLs",
              governedPrecision: "1 governed SQL · 0 fan-out",
              leftNodeTitle: "1 Order",
              orderFee: "SGD 332K Contrib.",
              leftSub: "620K net - COGS/ship",
              midTopLabel: "~1.78 Clicks/Order",
              midTopSub: "ad_clicks fan-out",
              midBotLabel: "1x Ad Spend",
              vanLegCost: "SGD 400K",
              dupBanner: "~1.78 CLICKS/ORDER = 1.78x FAN-OUT",
              cellText: "1.78x",
              dupSub: "Contribution inflated to SGD 592K vs 400K spend",
              rawFormula: "1.78x contrib (SGD 592K) - SGD 400K spend = Fake +SGD 192K",
              govShieldTitle: "BIGQUERY SEMANTIC MEASURE() GRAIN LOCK",
              govLeftBadge: "KEY: order_id",
              govLeftLabel: "Net Contribution",
              govLeftValue: "SGD 332K",
              govLeftSub: "620K net - COGS/ship (1x)",
              govMidBadge: "KEY: campaign_id",
              govMidLabel: "Ad Spend",
              govMidValue: "SGD 400K",
              govMidSub: "Pre-aggregated campaign (1x)",
              govOperator: "-",
              govRightTitle: "TRUE NET P&L",
              govRightValue: "-SGD 68K",
              govRightBadge: "-17% ROI",
              govRightSub: "332K - 400K = -68K",
              governedFormula: "SGD 332K Contrib - SGD 400K Spend = -SGD 68K (-17%)",
              takeaway: "Valid flat SQL inflated SGD 332K order contribution 1.78x (to SGD 592K) across ad clicks while summing SGD 400K spend once. BigQuery MEASURE() locks each grain automatically."
            },
            blind: {
              headlineValue: "+48% ROI (+SGD 192K)",
              headlineUnit: "Every channel won - double down across all channels",
              badgeText: "BigQuery · Raw Schema",
              badgeTone: "neutral",
              summary: "All three Q3 channels generated strong profits after ad spend, discounts, and shipping, delivering **+SGD 192K net profit (+48% portfolio ROI on SGD 400K spend)**. SG Paid Social, MY Paid Social, and B2B/Search all outperformed - **we recommend doubling down everywhere for Q4**.",
              consequence: "",
              rootCauseTitle: "1:N Order-to-Click Join Fan-Out (1.78x Contribution Inflation)",
              rootCause: "Flat SQL joined orders to multi-touch `ad_clicks` (~1.78 clicks per order), inflating SGD 332K order contribution to SGD 592K while pre-aggregated campaign spend (SGD 400K) was subtracted once.",
              thinkingSteps: [
                { active: "Joining campaign_orders with ad_clicks and ad_spend...", done: "Joined orders, ad_clicks, and campaign_spend", meta: "1.1s", code: "BigQuery SQL" },
                { active: "Resolving channel aggregation keys...", done: "Evaluated 4 SQL aggregations across channels", meta: "2.1s", code: "4 exploratory SQLs" },
                { active: "Computing net channel ROI...", done: "Computed +48% portfolio ROI (+SGD 192K)", meta: "4.9s", code: "BigQuery SQL" }
              ],
              queryLang: "SQL",
              queryCode: "WITH spend_by_channel AS (\n  SELECT channel, SUM(spend_sgd) AS spend_sgd\n  FROM cymbal_dw.campaign_spend\n  GROUP BY channel\n)\nSELECT\n  o.channel,\n  ROUND(MAX(s.spend_sgd), 0) AS spend_sgd,\n  ROUND(SUM(o.net_contribution_sgd) - MAX(s.spend_sgd), 0) AS net_profit_sgd\nFROM cymbal_dw.campaign_orders o\nJOIN cymbal_dw.ad_clicks clk USING (order_id)\nJOIN spend_by_channel s USING (channel)\nGROUP BY o.channel;",
              kpis: [
                { label: "Portfolio Net Profit", value: "+SGD 192K", delta: "+48% ROI on SGD 400K", tone: "neutral" },
                { label: "Winning Channels", value: "3 of 3", delta: "All channels positive", tone: "neutral" },
                { label: "Query Execution", value: "4 exploratory SQLs", delta: "Orders & ad spend tables", tone: "neutral" }
              ],
              chart: {
                type: "bar",
                title: "Channel Net Profit After Spend (Raw Schema)",
                items: [
                  { label: "SG Paid Social (SGD 220K spend)", value: 96000, display: "+SGD 96K (+44%)", tone: "primary" },
                  { label: "B2B / Search (SGD 80K spend)", value: 58000, display: "+SGD 58K (+73%)", tone: "primary" },
                  { label: "MY Paid Social (SGD 100K spend)", value: 38000, display: "+SGD 38K (+38%)", tone: "primary" }
                ]
              },
              table: {
                headers: ["Channel", "Ad Spend", "Net Profit", "ROI"],
                rows: [
                  ["SG Paid Social", "SGD 220K", "+SGD 96K", "+43.6%"],
                  ["B2B / Search", "SGD 80K", "+SGD 58K", "+72.5%"],
                  ["MY Paid Social", "SGD 100K", "+SGD 38K", "+38.0%"],
                  ["Total Portfolio", "SGD 400K", "+SGD 192K", "+48.0%"]
                ]
              },
              citations: [
                { title: "cymbal_dw.campaign_orders + ad_clicks", subtitle: "BigQuery Tables", snippet: "Combined campaign orders, ad clicks, and channel spend tables." }
              ],
              telemetry: { tokens: 2900, sqlCount: 4, latencySec: 4.9, tablesScanned: 199, accuracy: 0, queryLabel: "4 exploratory SQLs · 199 tables" }
            },
            governed: {
              headlineValue: "-SGD 68K Net (-17% ROI)",
              headlineUnit: "SG Paid Social bled -SGD 156K; B2B (+56K) & MY (+32K) won",
              badgeText: "Grounded in Knowledge Catalog",
              badgeTone: "success",
              summary: "Overall Q3 **lost -SGD 68K (-17% ROI on SGD 400K spend)** ONLY because **SG Paid Social bled -SGD 156K (-71% ROI)**. Underneath, **B2B/Search earned +SGD 56K (+70% ROI)** and **Malaysia Paid Social earned +SGD 32K (+32% ROI)**.",
              consequence: "Stops the blind +48% scaling plan and isolates the entire -SGD 68K loss to SG Paid Social while protecting profitable B2B and Malaysia channels.",
              fixTitle: "BigQuery Semantic MEASURE() Grain Lock",
              fixSummary: "Knowledge Catalog indexes `MEASURE()` definitions locked to `order_id` and `campaign_id` keys, eliminating 1.78x click fan-out in 1 governed SQL.",
              thinkingSteps: [
                { active: "Searching Knowledge Catalog semantic models...", done: "Loaded cymbal_marketing_model with grain-locked MEASURE()", meta: "0.2s", code: "SearchEntries" },
                { active: "Calling LookupContext via MCP...", done: "Bound order-grain contribution and campaign-grain spend", meta: "0.2s", code: "LookupContext" },
                { active: "Running BigQuery MEASURE() query...", done: "Executed 1 grain-locked SQL query (0 fan-out)", meta: "1.1s", code: "MEASURE() + AGG()" }
              ],
              queryLang: "SQL",
              queryCode: "SELECT\n  channel,\n  AGG(ad_spend_sgd) AS spend_sgd,\n  AGG(net_contribution_sgd) - AGG(ad_spend_sgd) AS net_profit_sgd\nFROM cymbal_commerce.cymbal_marketing_model\nGROUP BY channel;",
              kpis: [
                { label: "Portfolio Net P&L", value: "-SGD 68K", delta: "-17% ROI on SGD 400K spend", tone: "danger" },
                { label: "SG Paid Social", value: "-SGD 156K", delta: "-71% ROI on SGD 220K", tone: "danger" },
                { label: "Profitable Channels", value: "+SGD 88K", delta: "B2B +56K (+70%) · MY +32K (+32%)", tone: "success" }
              ],
              chart: {
                type: "bar",
                title: "True Channel Net Profit After Spend, Discounts & Shipping (SGD)",
                items: [
                  { label: "B2B / Search (SGD 80K spend)", value: 56000, display: "+SGD 56K (+70%)", tone: "success" },
                  { label: "MY Paid Social (SGD 100K spend)", value: 32000, display: "+SGD 32K (+32%)", tone: "primary" },
                  { label: "SG Paid Social (SGD 220K spend)", value: -156000, display: "-SGD 156K (-71%)", tone: "danger" }
                ]
              },
              table: {
                headers: ["Channel (Grain-Locked)", "Ad Spend", "Net Profit", "ROI"],
                rows: [
                  ["B2B / Search", "SGD 80K", "+SGD 56K", "+70.0%"],
                  ["MY Paid Social", "SGD 100K", "+SGD 32K", "+32.0%"],
                  ["SG Paid Social", "SGD 220K", "-SGD 156K", "-70.9%"],
                  ["Portfolio Total", "SGD 400K", "-SGD 68K", "-17.0%"]
                ]
              },
              citations: [
                { title: "cymbal_marketing_model", subtitle: "BigQuery Semantic MEASURE() (GA)", snippet: "Locks order contribution margin to order_id and ad spend to campaign_id." },
                { title: "Verified Query #VQ-M3", subtitle: "Context Set Query Template", snippet: "No 1.78x click fan-out across multi-touch click logs." }
              ],
              telemetry: { tokens: 620, sqlCount: 1, latencySec: 1.1, tablesScanned: 2, accuracy: 100, queryLabel: "1 governed SQL · Grain-locked MEASURE()" }
            },
            rlsRoles: null,
            kcProvenance: {
              aggregation: {
                source: "BigQuery Semantic Layer (MEASURE() GA)",
                assetPath: "bigquery://cymbal-commerce-prod.cymbal_commerce.cymbal_marketing_model",
                signals: ["Order grain locked to order_id", "Spend grain locked to campaign_id", "Zero join fan-out"]
              },
              enrichment: {
                loop: "Observe -> Enrich -> Validate -> Promote",
                observedGap: "Ad-hoc joins between orders and ad_clicks inflated channel profit to +48% ROI (+SGD 192K).",
                proposalText: "Publish MEASURE() definitions locking net_contribution_sgd and campaign_spend_sgd to native primary keys.",
                confidence: "99% (High)",
                evalCheck: "10/10 fan-trap regression checks passed",
                changeRequest: {
                  id: "CR-2026-0303",
                  status: "APPROVED",
                  steward: "Daniel Lim (Marketing Analytics Lead)",
                  timestamp: "2026-10-21 14:10 SGT"
                }
              },
              retrieval: {
                contextSet: "cymbal-commerce-1212-marketing [Preview]",
                mcpCall: "dataplex.googleapis.com/mcp -> lookup_context",
                assetsCount: 2,
                tokenBudget: "Grain-locked MEASURE() model",
                yamlSnippet: "resources:\n  - simpleName: cymbal_commerce.cymbal_marketing_model\n    measures:\n      - name: net_contribution_sgd\n        key: order_id\n      - name: campaign_spend_sgd\n        key: campaign_id\n    guidelines:\n      - \"Never join orders directly to ad_clicks; always aggregate via MEASURE().\""
              }
            },
            blindFollowUps: [
              {
                label: "Check grain-locked channel P&L with Knowledge Catalog before scaling Q4",
                kind: "ground"
              },
              {
                label: "Summarize our Q3 SGD 400K media spend split across SEA channels",
                kind: "sibling",
                siblingId: "starter_q3_spend"
              },
              {
                label: "Break down Q3 campaign order volumes across Singapore and Malaysia",
                kind: "sibling",
                siblingId: "starter_q3_volumes"
              }
            ],
            followUps: [
              {
                label: "Are linked accounts gaming Singapore promo codes and driving those heavy returns?",
                kind: "primary",
                targetTurnIndex: 3
              },
              {
                label: "Break down SG Paid Social's -SGD 156K loss by discount vs. return cost",
                kind: "sibling",
                siblingId: "q3_sg_loss_split"
              },
              {
                label: "Show why Malaysia Paid Social (+32% ROI) succeeded with the same creative",
                kind: "sibling",
                siblingId: "q3_my_success"
              }
            ]
          },

          {
            id: "t4",
            simpleContext: {
              mainVisual: "fraud_network",
              badge: "Connected Entity Graph",
              productTag: "BigQuery Property Graph (4-Hop ISO GQL)",
              oneLiner: "Links devices, accounts, coupons, cards, and addresses together so hidden fraud rings light up in one query.",
              withoutLabel: "Raw Schema guessed",
              withoutText: "Only matched exact duplicate email strings, finding 14 emails (SGD 2,800) and missing 640 throwaway burners.",
              withLabel: "Knowledge Catalog enforced",
              withText: "Traversed 4 hops (Device -> Account -> Promo -> Card -> Address) to bust 28 spoofed devices & SGD 96,000 coupons.",
              deltaBefore: "14 emails · SGD 2,800",
              deltaAfter: "28 devices · 640 burners · SGD 96K",
              swingTag: "34x more abuse uncovered"
            },
            index: 4,
            turnTitle: "4-Hop Promo Fraud Graph",
            prompt: "Are linked accounts gaming Singapore promo codes and driving those heavy returns?",
            layerFeature: "BigQuery Property Graph (4-Hop ISO GQL)",
            layerStatus: "GA",
            visualStory: {
              archetype: "graph_hops",
              graphVariant: "fraud_ring",
              contextBuildingBlock: "BigQuery Graph (4-Hop ISO GQL)",
              kicker: "14 Isolated Emails vs. 4-Hop Device-to-Address Fraud Ring",
              gapHeadline: "Flat SQL checks exact duplicate emails only (14 accts / SGD 2,800)",
              groundedHeadline: "4-hop ISO GQL busts 28 spoofed devices -> 640 burners -> SGD 96K",
              rawSummary: "14 emails (SGD 2,800)",
              governedSummary: "640 accts / SGD 96,000 (34x)",
              rawPrecision: "5 exploratory SQLs",
              governedPrecision: "1 ISO GQL query · 4 hops",
              deviceHubs: "28 Spoofed Devices",
              burnerAccounts: "640 Burner Accts",
              couponTotal: "SGD 96,000 Coupons",
              returnRate: "78% Orders Returned",
              isolatedCount: "14 isolated dots",
              isolatedAmount: "SGD 2,800",
              takeaway: "One 4-hop BigQuery Graph traversal (Click Device -> Account -> Promo -> Card -> Address) caught 34x more promo abuse than flat email matching."
            },
            blind: {
              headlineValue: "No organized abuse",
              headlineUnit: "14 duplicate emails totaling SGD 2,800 in promo coupons",
              badgeText: "BigQuery · Raw Schema",
              badgeTone: "neutral",
              summary: "Checking `cymbal_dw.orders` for duplicate customer emails shows **no organized promo abuse** - only **14 duplicate email signups** totaling **SGD 2,800 in coupon redemptions**. Normal promotional friction rather than a coordinated fraud ring.",
              consequence: "",
              rootCauseTitle: "Exact-Email String Match Misses Multi-Hop Entity Ring",
              rootCause: "Flat SQL grouped only by exact `customer_email` in `orders`, completely missing throwaway burner emails linked across shared click devices, promo codes, payment cards, and delivery addresses.",
              thinkingSteps: [
                { active: "Scanning customer emails in cymbal_dw.orders...", done: "Grouped promo orders by exact customer_email", meta: "0.9s", code: "GROUP BY email" },
                { active: "Checking email frequency across promo orders...", done: "Ran 5 flat SQL queries across orders and coupons", meta: "2.3s", code: "5 exploratory SQLs" },
                { active: "Summarizing promo reuse...", done: "Found 14 duplicate emails (SGD 2,800 coupons)", meta: "5.4s", code: "BigQuery SQL" }
              ],
              queryLang: "SQL",
              queryCode: "WITH dup_emails AS (\n  SELECT customer_email, SUM(coupon_discount_sgd) AS coupon_sgd\n  FROM cymbal_dw.orders\n  WHERE country_code = 'SG' AND promo_redeemed = TRUE\n  GROUP BY customer_email\n  HAVING COUNT(*) > 1\n)\nSELECT\n  COUNT(DISTINCT customer_email) AS duplicate_emails,\n  ROUND(SUM(coupon_sgd), 0) AS coupon_sgd\nFROM dup_emails;",
              kpis: [
                { label: "Duplicate Emails", value: "14 accounts", delta: "Exact email match", tone: "neutral" },
                { label: "Flagged Coupons", value: "SGD 2,800", delta: "Low isolated exposure", tone: "neutral" },
                { label: "Query Execution", value: "5 exploratory SQLs", delta: "Campaign orders table", tone: "neutral" }
              ],
              chart: {
                type: "bar",
                title: "Promo Coupon Anomaly Check (Raw Schema)",
                items: [
                  { label: "Duplicate Email Coupons (14 accts)", value: 2800, display: "SGD 2,800", tone: "primary" },
                  { label: "Single-Use Promo Baseline", value: 12400, display: "Normal baseline", tone: "slate" }
                ]
              },
              table: {
                headers: ["Check Type", "Accounts Flagged", "Coupon Value", "Assessment"],
                rows: [
                  ["Exact email duplicates", "14 accounts", "SGD 2,800", "Minor / isolated"],
                  ["Single-use promo orders", "3,120 orders", "Standard promos", "Normal baseline"]
                ]
              },
              citations: [
                { title: "cymbal_dw.orders", subtitle: "BigQuery Orders Table", snippet: "Campaign orders table containing customer_email and coupon_discount_sgd." }
              ],
              telemetry: { tokens: 3300, sqlCount: 5, latencySec: 5.4, tablesScanned: 199, accuracy: 0, queryLabel: "5 exploratory SQLs · 199 tables" }
            },
            governed: {
              headlineValue: "640-Account Fraud Ring Busted",
              headlineUnit: "28 spoofed devices | SGD 96,000 coupons (34x) | 78% returned",
              badgeText: "Grounded in Knowledge Catalog",
              badgeTone: "success",
              summary: "**Organized promo & click-fraud ring busted!** A 4-hop entity graph check exposed **640 linked burner accounts** tied to just **28 spoofed devices** - stacking **SGD 96,000 in coupons (34x)** and returning **78% of orders**.",
              consequence: "Identifies the exact 28 spoofed device IDs and 640 burner accounts to block immediately and substantiate an agency invalid-traffic audit.",
              fixTitle: "BigQuery Property Graph (4-Hop ISO GQL)",
              fixSummary: "Knowledge Catalog exposes `cymbal_fraud_graph`, enabling 1 ISO GQL traversal across click devices, burner accounts, promo codes, cards, and addresses.",
              thinkingSteps: [
                { active: "Searching Knowledge Catalog for entity graphs...", done: "Found cymbal_fraud_graph (5 node / 4 edge tables)", meta: "0.2s", code: "SearchEntries" },
                { active: "Calling LookupContext via MCP...", done: "Loaded 4-hop graph topology and Verified Query #VQ-M4", meta: "0.2s", code: "LookupContext" },
                { active: "Running 4-hop ISO GQL traversal...", done: "Traversed Device -> Account -> Promo -> Card -> Address", meta: "1.3s", code: "ISO GQL (GA)" }
              ],
              queryLang: "ISO GQL",
              queryCode: "WITH ring_redemptions AS (\n  SELECT DISTINCT\n    device_id, account_id, promo_id, coupon_sgd, is_returned\n  FROM GRAPH_TABLE(\n    cymbal_commerce.cymbal_fraud_graph\n    MATCH (d:ClickDevice)-[:SPAWNED]->(a:Account)\n          -[:REDEEMED]->(p:PromoCode),\n          (a)-[:PAID_WITH]->(c:PaymentCard)-[:SHIPS_TO]->(addr:Address)\n    WHERE a.country_code = 'SG'\n    COLUMNS (d.device_id, a.account_id, p.promo_id, p.coupon_sgd, a.is_returned)\n  )\n)\nSELECT\n  device_id,\n  COUNT(DISTINCT account_id) AS burner_accounts,\n  ROUND(SUM(coupon_sgd), 0) AS stacked_coupons_sgd,\n  ROUND(100.0 * COUNT(DISTINCT IF(is_returned, account_id, NULL)) / COUNT(DISTINCT account_id), 0) AS return_pct\nFROM ring_redemptions\nGROUP BY device_id\nHAVING COUNT(DISTINCT account_id) > 5;",
              kpis: [
                { label: "Linked Burner Ring", value: "640 accounts", delta: "Tied to 28 spoofed devices", tone: "danger" },
                { label: "Stacked Coupons", value: "SGD 96,000", delta: "34x flat SQL (SGD 2,800)", tone: "danger" },
                { label: "Ring Return Rate", value: "78% returned", delta: "1 4-hop ISO GQL query", tone: "primary" }
              ],
              chart: {
                type: "bar",
                title: "Promo Fraud Caught: Flat Email Check vs. 4-Hop Graph (SGD)",
                items: [
                  { label: "4-Hop Fraud Ring (640 accts / 28 devices)", value: 96000, display: "SGD 96,000 (34x)", tone: "danger" },
                  { label: "Flat Exact-Email Check (14 accts)", value: 2800, display: "SGD 2,800", tone: "muted" }
                ]
              },
              table: {
                headers: ["Graph Hop", "Entities Caught", "Behavior / Exposure", "Action"],
                rows: [
                  ["Hop 1: Spoofed Click Devices", "28 devices", "Bot & spoofed Paid Social clicks", "Block device fingerprints"],
                  ["Hop 2: Burner Accounts", "640 accounts", "Throwaway signups rotating emails", "Suspend promo eligibility"],
                  ["Hop 3-4: Promo -> Card -> Addr", "640 orders", "SGD 96,000 coupons · 78% returns", "Feed agency audit"]
                ]
              },
              citations: [
                { title: "cymbal_fraud_graph", subtitle: "BigQuery Property Graph (GA)", snippet: "4-hop traversal: ClickDevice -> Account -> PromoCode -> PaymentCard -> Address." },
                { title: "Verified Query #VQ-M4", subtitle: "ISO GQL Template", snippet: "Deduplicates multi-hop ring counts via COUNT(DISTINCT)." }
              ],
              telemetry: { tokens: 670, sqlCount: 1, latencySec: 1.3, tablesScanned: 5, accuracy: 100, queryLabel: "1 ISO GQL query · 4-hop graph traversal" }
            },
            rlsRoles: null,
            kcProvenance: {
              aggregation: {
                source: "BigQuery Property Graph (In-Place Virtual Graph)",
                assetPath: "bigquery://cymbal-commerce-prod.cymbal_commerce.cymbal_fraud_graph",
                signals: ["5 node tables + 4 edge tables", "Zero graph ETL", "Inherits BigQuery IAM"]
              },
              enrichment: {
                loop: "Observe -> Enrich -> Validate -> Promote",
                observedGap: "Flat SQL email matching caught only SGD 2,800 (14 emails) while missing 640 device-linked burners.",
                proposalText: "Catalog cymbal_fraud_graph edges and promote 4-hop ISO GQL Verified Query #VQ-M4.",
                confidence: "99% (High)",
                evalCheck: "14/14 multi-hop entity resolution tests passed",
                changeRequest: {
                  id: "CR-2026-0304",
                  status: "APPROVED",
                  steward: "Siti Rahman (Fraud & Identity Architect)",
                  timestamp: "2026-10-22 10:15 SGT"
                }
              },
              retrieval: {
                contextSet: "cymbal-commerce-1212-marketing [Preview]",
                mcpCall: "dataplex.googleapis.com/mcp -> lookup_context",
                assetsCount: 1,
                tokenBudget: "BigQuery Graph 4-Hop ISO GQL",
                yamlSnippet: "resources:\n  - simpleName: cymbal_commerce.cymbal_fraud_graph\n    type: BIGQUERY_PROPERTY_GRAPH\n    paths:\n      - \"ClickDevice -> Account -> PromoCode -> PaymentCard -> Address\"\n    guidelines:\n      - \"Use GRAPH_TABLE for promo abuse investigations; never rely on exact email equality.\""
              }
            },
            blindFollowUps: [
              {
                label: "Re-run Q4 with Knowledge Catalog",
                kind: "ground"
              },
              {
                label: "Summarize our Q3 SGD 400K media spend split across SEA channels",
                kind: "sibling",
                siblingId: "starter_q3_spend"
              },
              {
                label: "Break down Q3 campaign order volumes across Singapore and Malaysia",
                kind: "sibling",
                siblingId: "starter_q3_volumes"
              }
            ],
            followUps: [
              {
                label: "How much fraudulent Paid Social spend can we claw back under our contract?",
                kind: "primary",
                targetTurnIndex: 4
              },
              {
                label: "Inspect the top spoofed device clusters and shared payment cards",
                kind: "sibling",
                siblingId: "q4_device_clusters"
              },
              {
                label: "Verify whether Malaysia Paid Social shows any linked device rings",
                kind: "sibling",
                siblingId: "q4_my_clean"
              }
            ]
          },

          {
            id: "t5",
            simpleContext: {
              mainVisual: "convergence_flow",
              badge: "Cross-Cloud + Contract PDFs",
              productTag: "AWS S3 Iceberg [Preview] + Object Tables & AI.GENERATE()",
              oneLiner: "Queries raw click logs in AWS S3 in place and reads the 45-page signed Agency PDF right inside SQL - zero ETL.",
              withoutLabel: "Raw Schema guessed",
              withoutText: "Only saw paid ERP invoices in BigQuery - blind to AWS S3 click logs and the Agency PDF, reporting SGD 0.",
              withLabel: "Knowledge Catalog enforced",
              withText: "Matched 40.0% invalid S3 clicks against Clause 7.4 (>15% = 100% refund) to recover SGD 88,000 cash.",
              deltaBefore: "SGD 0 Recoverable",
              deltaAfter: "+SGD 88,000 Cash Back (Q3 +SGD 20K)",
              swingTag: "Flips Q3 into profit"
            },
            index: 5,
            turnTitle: "AWS S3 + Agency PDF Clawback",
            prompt: "How much fraudulent Paid Social spend can we claw back under our contract?",
            layerFeature: "AWS S3 Iceberg + GCS Object Tables",
            layerStatus: "GA + Preview",
            visualStory: {
              archetype: "cross_cloud_pdf_bridge",
              contextBuildingBlock: "AWS S3 Federation + Object Table AI.GENERATE",
              kicker: "Cross-Cloud + Multimodal PDF Bridge: S3 Clicks + Contract Clause 7.4",
              gapHeadline: "ERP-only SQL cannot read AWS S3 click logs or Agency MSA PDF -> SGD 0",
              groundedHeadline: "AWS S3 (40% invalid) + Clause 7.4 PDF -> +SGD 88K cash clawback",
              rawSummary: "SGD 0 recoverable",
              governedSummary: "SGD 88,000 cash clawback",
              rawPrecision: "3 exploratory SQLs",
              governedPrecision: "AWS S3 + PDF unified",
              s3Label: "AWS S3 Iceberg Clicks",
              s3Meta: "1.42M rows · 40.0% invalid",
              s3Sub: "28 spoofed devices + bots",
              pdfLabel: "Agency Addendum #2 PDF",
              pdfMeta: "Clause 7.4 extracted",
              pdfSub: ">15% invalid = 100% refund",
              outcomeValue: "+SGD 88,000 Cash",
              outcomeSub: "Flips Q3: -68K -> +20K net",
              outcomeExtra: "Clean SG: +28K (+21.2%)",
              takeaway: "Borderless Lakehouse queries AWS S3 click logs in place while Object Tables + AI.GENERATE extract Clause 7.4 in SQL - recovering SGD 88,000 cash and flipping Q3 to +SGD 20K."
            },
            blind: {
              headlineValue: "SGD 0 recoverable",
              headlineUnit: "ERP invoices booked non-refundable; 0 dispute records in BigQuery",
              badgeText: "BigQuery · Raw Schema",
              badgeTone: "neutral",
              summary: "Checking ERP media payables, **SGD 0 is recoverable**. All three Q3 Singapore Paid Social invoices totaling **SGD 220K** are booked as settled and non-refundable, with zero open dispute credits in the payables ledger.",
              consequence: "",
              rootCauseTitle: "Cross-Cloud S3 Silo & Unreadable Agency PDF",
              rootCause: "Ad-click telemetry lives in AWS S3 Iceberg and refund terms sit inside a 45-page Agency MSA PDF in Cloud Storage - leaving BigQuery-only raw SQL blind to both.",
              thinkingSteps: [
                { active: "Querying erp_media_invoices in cymbal_dw...", done: "Read SGD 220K booked SG Paid Social invoices", meta: "0.7s", code: "erp_media_invoices" },
                { active: "Checking BigQuery for agency dispute records...", done: "Checked dispute credit ledger in BigQuery", meta: "1.8s", code: "3 exploratory SQLs" },
                { active: "Returning recoverability status...", done: "Reported SGD 0 recoverable under ERP records", meta: "4.3s", code: "BigQuery SQL" }
              ],
              queryLang: "SQL",
              queryCode: "SELECT\n  agency_name,\n  SUM(billed_media_sgd) AS billed_sgd,\n  SUM(dispute_credit_sgd) AS recoverable_sgd\nFROM cymbal_dw.erp_media_invoices\nWHERE market = 'SG' AND channel = 'PAID_SOCIAL'\nGROUP BY agency_name;",
              kpis: [
                { label: "Recoverable Spend", value: "SGD 0", delta: "Booked non-refundable in ERP", tone: "neutral" },
                { label: "Payables Ledger", value: "SGD 220K billed", delta: "ERP media payables ledger", tone: "neutral" },
                { label: "Query Execution", value: "3 exploratory SQLs", delta: "3 BigQuery SQLs", tone: "neutral" }
              ],
              chart: {
                type: "bar",
                title: "SG Paid Social Spend Recoverability (Raw Schema)",
                items: [
                  { label: "Booked Non-Refundable (SG Paid Social)", value: 220000, display: "SGD 220K", tone: "primary" },
                  { label: "Recoverable Dispute Credit", value: 0, display: "SGD 0", tone: "slate" }
                ]
              },
              table: {
                headers: ["Source System", "Status", "Recoverable Amount"],
                rows: [
                  ["BigQuery ERP Invoices", "Booked & Paid", "SGD 220,000 non-refundable"],
                  ["Agency Dispute Table", "0 rows", "SGD 0"]
                ]
              },
              citations: [
                { title: "cymbal_dw.erp_media_invoices", subtitle: "BigQuery ERP Table", snippet: "ERP media payables and booked invoice ledger." }
              ],
              telemetry: { tokens: 2000, sqlCount: 3, latencySec: 4.3, tablesScanned: 199, accuracy: 0, queryLabel: "3 exploratory SQLs · 199 tables" }
            },
            governed: {
              headlineValue: "SGD 88,000 Cash Clawback",
              headlineUnit: "Flips Q3 from -SGD 68K to +SGD 20K | Clean SG Social +21.2%",
              badgeText: "Grounded in Knowledge Catalog",
              badgeTone: "success",
              summary: "You can claw back **SGD 88,000 in cash** from the agency! **AWS S3 click logs** prove **40.0%** of SG Paid Social spend came from those 28 spoofed devices & bots, triggering **Addendum #2 Clause 7.4** (>15% invalid = 100% refund) - **flipping Q3 from -SGD 68K to +SGD 20K net profit** and restoring clean SG Paid Social to **+21.2% ROI**.",
              consequence: "Unifies AWS S3 click logs and the signed Agency PDF directly in SQL - recovering SGD 88,000 cash from the agency and flipping Q3 into +SGD 20K profit.",
              fixTitle: "AWS S3 Iceberg Federation + Object Tables & AI.GENERATE()",
              fixSummary: "Borderless Lakehouse queries `aws_adtech_iceberg.q3_paid_social_clicks` in AWS S3 without ETL, while Object Tables + `AI.GENERATE()` extract Clause 7.4 from `Agency_Media_MSA_Addendum_2.pdf` directly in SQL.",
              thinkingSteps: [
                { active: "Querying AWS S3 Iceberg via Borderless Lakehouse...", done: "Scanned 1.42M S3 clicks -> 40.0% invalid (SGD 88K)", meta: "0.5s", code: "AWS S3 Iceberg" },
                { active: "Extracting Clause 7.4 via Object Table + AI.GENERATE...", done: "Extracted Addendum #2 Clause 7.4 (>15% -> 100% refund)", meta: "0.4s", code: "AI.GENERATE()" },
                { active: "Joining S3 click logs with Agency PDF terms...", done: "Verified SGD 88,000 agency cash clawback -> Q3 +SGD 20K", meta: "1.4s", code: "1 unified SQL" }
              ],
              queryLang: "SQL",
              queryCode: "WITH s3_invalid AS (\n  SELECT SUM(IF(NOT is_valid_human, billed_media_sgd, 0)) AS invalid_sgd,\n         ROUND(100.0 * COUNTIF(NOT is_valid_human) / COUNT(*), 1) AS invalid_pct\n  FROM aws_adtech_iceberg.q3_paid_social_clicks\n  WHERE country_code = 'SG'\n),\nclause AS (\n  SELECT threshold_pct, refund_rate_pct FROM cymbal_commerce.agency_msa_clause_7_4\n)\nSELECT\n  s.invalid_pct,\n  IF(s.invalid_pct > c.threshold_pct, s.invalid_sgd * (c.refund_rate_pct / 100.0), 0) AS cash_clawback_sgd\nFROM s3_invalid s CROSS JOIN clause c;",
              kpis: [
                { label: "Agency Cash Clawback", value: "SGD 88,000", delta: "40.0% invalid of SGD 220K", tone: "success" },
                { label: "Q3 Net Profit Flip", value: "+SGD 20K", delta: "Up from -SGD 68K (-68 + 88)", tone: "success" },
                { label: "Sources Unified", value: "AWS S3 + PDF", delta: "1.42M clicks + Clause 7.4", tone: "primary" }
              ],
              chart: {
                type: "bar",
                title: "Q3 Profit Recovery & Clean SG Paid Social Bridge (SGD)",
                items: [
                  { label: "Governed Q3 Loss (Before Clawback)", value: -68000, display: "-SGD 68K", tone: "danger" },
                  { label: "Agency Cash Clawback (S3 + Clause 7.4)", value: 88000, display: "+SGD 88K cash", tone: "primary" },
                  { label: "Restored Q3 Net Profit (-68K + 88K)", value: 20000, display: "+SGD 20K net", tone: "success" },
                  { label: "Clean SG Social (excl. 88K + 96K coupons)", value: 28000, display: "+SGD 28K (+21.2%)", tone: "success" }
                ]
              },
              table: {
                headers: ["Source / Evidence", "Measured Signal", "Contract / Math", "Outcome"],
                rows: [
                  ["AWS S3 Iceberg (1.42M clicks)", "40.0% invalid (28 devices/bots)", "40% x SGD 220K spend", "SGD 88K invalid media"],
                  ["Agency Addendum #2 PDF", "Clause 7.4 (>15% invalid)", "100% refund of invalid spend", "SGD 88,000 cash clawback"],
                  ["Q3 P&L + Clean SG", "-68K + 88K = +20K net", "-156K + 88K + 96K coupons", "+28K (+21.2% on 132K)"]
                ]
              },
              citations: [
                { title: "aws_adtech_iceberg.q3_paid_social_clicks", subtitle: "AWS S3 Iceberg Federation [Preview]", snippet: "1.42M click rows in ap-southeast-1 queried in place via AWS Glue Iceberg REST Catalog." },
                { title: "Agency_Media_MSA_Addendum_2.pdf", subtitle: "GCS Object Table + AI.GENERATE (GA)", snippet: "Clause 7.4: Invalid bot/spoofed traffic >15% triggers 100% refund of invalid spend." }
              ],
              telemetry: { tokens: 580, sqlCount: 1, latencySec: 1.4, tablesScanned: 2, accuracy: 100, queryLabel: "1 unified SQL · AWS S3 + Agency PDF" }
            },
            rlsRoles: null,
            kcProvenance: {
              aggregation: {
                source: "AWS S3 Iceberg (ap-southeast-1) + GCS Object Table",
                assetPath: "iceberg://aws-glue-ap-southeast-1/aws_adtech_iceberg.q3_paid_social_clicks",
                signals: ["1.42M S3 click rows synced via KC Metadata Sync", "Agency_Media_MSA_Addendum_2.pdf indexed via Object Table"]
              },
              enrichment: {
                loop: "Observe -> Enrich -> Validate -> Promote",
                observedGap: "ERP-only queries could not join AWS S3 click logs or parse Clause 7.4 from the signed Agency PDF.",
                proposalText: "Register AWS S3 Iceberg catalog in Knowledge Catalog and materialize Clause 7.4 once via Object Table + AI.GENERATE().",
                confidence: "97% (High - Cited to Clause 7.4)",
                evalCheck: "Cross-cloud join & PDF clause extraction verified",
                changeRequest: {
                  id: "CR-2026-0305",
                  status: "APPROVED",
                  steward: "Karen Ong (Legal Ops & Procurement Steward)",
                  timestamp: "2026-10-23 15:45 SGT"
                }
              },
              retrieval: {
                contextSet: "cymbal-commerce-1212-marketing [Preview]",
                mcpCall: "dataplex.googleapis.com/mcp -> lookup_context",
                assetsCount: 2,
                tokenBudget: "Cross-Cloud S3 + Object Table PDF",
                yamlSnippet: "resources:\n  - simpleName: aws_adtech_iceberg.q3_paid_social_clicks\n    federation: AWS_GLUE_ICEBERG_REST [Preview]\n  - simpleName: cymbal_commerce.agency_msa_clause_7_4\n    sourceDocument: gs://cymbal-commerce-legal/Agency_Media_MSA_Addendum_2.pdf\n    extractedRule: \"Clause 7.4: >15% invalid traffic triggers 100% cash refund of invalid spend.\""
              }
            },
            blindFollowUps: [
              {
                label: "Re-run Q5 with Knowledge Catalog",
                kind: "ground"
              },
              {
                label: "Summarize our Q3 SGD 400K media spend split across SEA channels",
                kind: "sibling",
                siblingId: "starter_q3_spend"
              },
              {
                label: "Break down Q3 campaign order volumes across Singapore and Malaysia",
                kind: "sibling",
                siblingId: "starter_q3_volumes"
              }
            ],
            followUps: [
              {
                label: "If we block fraud and reallocate Q4 spend, what will Q4 actually deliver?",
                kind: "primary",
                targetTurnIndex: 5
              },
              {
                label: "Generate the legal audit packet citing AWS S3 device logs and Clause 7.4",
                kind: "sibling",
                siblingId: "q5_legal_packet"
              },
              {
                label: "Reconcile clean SG Paid Social unit economics (+SGD 28K on SGD 132K)",
                kind: "sibling",
                siblingId: "q5_clean_sg"
              }
            ]
          },

          {
            id: "t6",
            simpleContext: {
              mainVisual: "forecast_cone",
              badge: "Clean Forecast + Future Drivers",
              productTag: "BigQuery AI.FORECAST · TimesFM 3.0 [Preview]",
              oneLiner: "Feeds fraud-scrubbed certified net history into AI.FORECAST() with 90% confidence bands and joins the planned Q4 spend reallocation table.",
              withoutLabel: "Raw Schema guessed",
              withoutText: "Ran AI.FORECAST() directly on dirty gross sales (with September's bot spike), projecting SGD 2.84M and ranking SG Social #1.",
              withLabel: "Knowledge Catalog enforced",
              withText: "Ran TimesFM 3.0 on clean history + reallocated SGD 600K plan -> SGD 1.42M net rev & +SGD 258K profit (+43% ROI).",
              deltaBefore: "SGD 2.84M Bot Mirage",
              deltaAfter: "SGD 1.42M Rev · +SGD 258K Profit",
              swingTag: "+SGD 403K swing vs. unchanged"
            },
            index: 6,
            turnTitle: "Q4 Forecast & Spend Reallocation",
            prompt: "If we block fraud and reallocate Q4 spend, what will Q4 actually deliver?",
            layerFeature: "AI.FORECAST (TimesFM 3.0)",
            layerStatus: "Preview",
            visualStory: {
              archetype: "forecast_cone",
              contextBuildingBlock: "AI.FORECAST (TimesFM 3.0) + Q4 Reallocation",
              kicker: "Runaway Bot Mirage vs. Fraud-Scrubbed Q4 Confidence Cone",
              gapHeadline: "Dirty history extrapolates SGD 2.84M mirage into SG Social bots",
              groundedHeadline: "AI.FORECAST (TimesFM 3.0) delivers SGD 1.42M rev & +SGD 258K profit (+43%)",
              rawSummary: "SGD 2.84M mirage",
              governedSummary: "SGD 1.42M rev | +SGD 258K (+43%)",
              rawPrecision: "Dirty gross trend",
              governedPrecision: "AI.FORECAST (TimesFM 3.0)",
              miragePeak: "SGD 2.84M",
              governedTarget: "SGD 1.42M",
              governedRange: "1.31M - 1.54M",
              governedProfit: "+SGD 258K (+43% ROI)",
              unchangedLoss: "-SGD 145K unchanged",
              cfoSignOff: "Rebalanced Q4 plan: SGD 600K (512K net cash)",
              takeaway: "Running AI.FORECAST (TimesFM 3.0) on fraud-scrubbed history plus Q4 spend reallocation yields +SGD 258K profit (+43% ROI) vs. -SGD 145K unchanged."
            },
            blind: {
              headlineValue: "SGD 2.84M 12.12 & LNY Boom",
              headlineUnit: "Extrapolates Q3 gross trend - recommends pouring Q4 budget into SG Social",
              badgeText: "BigQuery · Raw Schema",
              badgeTone: "neutral",
              summary: "Extrapolating Q3's gross campaign velocity into 12.12 and Lunar New Year peak weeks forecasts **SGD 2.84M in Q4 campaign revenue**. Because Singapore Paid Social generated the fastest gross order spike in September, the model recommends **pouring the largest share of 12.12 & LNY budget into Singapore Paid Social**.",
              consequence: "",
              rootCauseTitle: "Unscrubbed History Extrapolation Without Spend Reallocation",
              rootCause: "Forecasting directly on dirty gross orders extrapolated September's bot-driven gross spike without scrubbing spoofed devices or reallocating channel spend.",
              thinkingSteps: [
                { active: "Aggregating weekly gross_order_value from cymbal_dw.campaign_orders...", done: "Built 26-week raw gross revenue series by channel", meta: "1.1s", code: "cymbal_dw.campaign_orders" },
                { active: "Running BigQuery AI.FORECAST() over raw channel series...", done: "Executed 13-week AI.FORECAST() across 3 channels", meta: "2.2s", code: "AI.FORECAST()" },
                { active: "Ranking channels by forecasted Q4 revenue...", done: "Projected SGD 2.84M total (SG Paid Social ranked #1)", meta: "4.7s", code: "BigQuery SQL" }
              ],
              queryLang: "SQL",
              queryCode: "WITH weekly_gross AS (\n  SELECT\n    DATE_TRUNC(order_date, WEEK(MONDAY)) AS week_start,\n    channel,\n    SUM(gross_order_value) AS gross_sales_sgd\n  FROM cymbal_dw.campaign_orders\n  WHERE order_date BETWEEN '2026-04-01' AND '2026-09-30'\n  GROUP BY 1, 2\n),\nraw_forecast AS (\n  SELECT\n    channel,\n    SUM(forecast_value) AS projected_q4_gross_sgd\n  FROM AI.FORECAST(\n    TABLE weekly_gross,\n    data_col => 'gross_sales_sgd',\n    timestamp_col => 'week_start',\n    id_cols => ['channel'],\n    horizon => 13\n  )\n  GROUP BY channel\n)\nSELECT\n  channel,\n  ROUND(projected_q4_gross_sgd, 0) AS projected_q4_sgd,\n  RANK() OVER (ORDER BY projected_q4_gross_sgd DESC) AS growth_rank\nFROM raw_forecast\nORDER BY projected_q4_sgd DESC;",
              kpis: [
                { label: "Projected Q4 Revenue", value: "SGD 2.84M", delta: "AI.FORECAST() on raw gross", tone: "neutral" },
                { label: "Top Ranked Channel", value: "SG Paid Social (#1)", delta: "Steepest Sep gross trajectory", tone: "neutral" },
                { label: "Query Execution", value: "AI.FORECAST() SQL", delta: "Raw cymbal_dw.campaign_orders", tone: "neutral" }
              ],
              chart: {
                type: "bar",
                title: "12.12 & LNY Revenue Projection (Raw Schema)",
                items: [
                  { label: "Q3 Gross Baseline", value: 1850000, display: "SGD 1.85M", tone: "slate" },
                  { label: "Q4 Projected Holiday Boom", value: 2840000, display: "SGD 2.84M", tone: "primary" }
                ]
              },
              table: {
                headers: ["Model Input", "Assumption", "Q4 Projection"],
                rows: [
                  ["Q2-Q3 Raw History", "Uncleaned gross_order_value", "SGD 1.85M Q3 base"],
                  ["13-Week AI.FORECAST()", "SG Paid Social ranked #1", "SGD 2.84M projected"]
                ]
              },
              citations: [
                { title: "cymbal_dw.campaign_orders", subtitle: "BigQuery Raw Table + AI.FORECAST()", snippet: "26-week uncleaned gross_order_value series passed directly into AI.FORECAST()." }
              ],
              telemetry: { tokens: 2900, sqlCount: 4, latencySec: 4.7, tablesScanned: 199, accuracy: 0, queryLabel: "4 exploratory SQLs · 199 tables" }
            },
            governed: {
              headlineValue: "SGD 1.42M Rev | +SGD 258K Profit",
              headlineUnit: "Rebalanced SGD 600K Q4 plan (SGD 512K net new cash, +43% ROI)",
              badgeText: "Grounded in Knowledge Catalog",
              badgeTone: "success",
              summary: "**Rebalanced SGD 600K Q4 plan** (only **SGD 512K net new cash** after the SGD 88K agency refund): **SGD 260K B2B/Search (+169K)**, **SGD 220K MY Social (+66K)**, and **SGD 120K clean SG Social (+23K)**. Powered by **AI.FORECAST (TimesFM 3.0)** on fraud-scrubbed history, Q4 projects **SGD 1.42M net revenue** (90% range **1.31M - 1.54M**) and **+SGD 258K profit (+43% ROI)** - vs. **-SGD 145K** if left unchanged.",
              consequence: "Delivers a rebalanced SGD 600K 12.12 & LNY plan (SGD 512K net new cash) forecasting +SGD 258K profit (+43% ROI) vs. a -SGD 145K loss on the unblocked Q3 mix.",
              fixTitle: "AI.FORECAST (TimesFM 3.0) + Q4 Spend Reallocation SQL",
              fixSummary: "Knowledge Catalog feeds fraud-scrubbed certified channel history into BigQuery `AI.FORECAST(..., model => 'TimesFM 3.0')` and joins the baseline forecast with planned Q4 channel spend reallocation in SQL.",
              thinkingSteps: [
                { active: "Loading fraud-scrubbed certified Q2-Q3 history...", done: "Excluded 28 spoofed devices & 640 burner accounts", meta: "0.3s", code: "Certified History" },
                { active: "Running AI.FORECAST (TimesFM 3.0) baseline...", done: "Generated 13-week fraud-scrubbed channel forecast", meta: "0.5s", code: "AI.FORECAST" },
                { active: "Applying Q4 SGD 600K spend reallocation...", done: "Projected SGD 1.42M net rev & +SGD 258K profit (+43% ROI)", meta: "1.4s", code: "1 governed SQL" }
              ],
              queryLang: "SQL",
              queryCode: "WITH baseline AS (\n  SELECT channel, SUM(forecast_value) AS base_q4_rev_sgd\n  FROM AI.FORECAST(\n    (SELECT week_start, channel, net_rev_sgd\n     FROM cymbal_commerce.q3_scrubbed_weekly_channel),\n    model => 'TimesFM 3.0',\n    data_col => 'net_rev_sgd',\n    timestamp_col => 'week_start',\n    id_cols => ['channel'],\n    horizon => 13,\n    confidence_level => 0.90\n  )\n  GROUP BY channel\n)\nSELECT\n  b.channel,\n  p.planned_q4_spend_sgd,\n  ROUND(b.base_q4_rev_sgd * (p.planned_q4_spend_sgd / p.q3_clean_spend_sgd), 0) AS projected_q4_rev_sgd\nFROM baseline b\nJOIN cymbal_commerce.q4_reallocation_plan p USING (channel);",
              kpis: [
                { label: "Q4 Net Revenue", value: "SGD 1.42M", delta: "Range: SGD 1.31M - 1.54M", tone: "primary" },
                { label: "Q4 Net Profit & ROI", value: "+SGD 258K (+43%)", delta: "vs -SGD 145K unchanged mix", tone: "success" },
                { label: "Net New Cash Needed", value: "SGD 512K", delta: "600K plan - 88K clawback", tone: "success" }
              ],
              chart: {
                type: "bar",
                title: "Q4 Reallocated Spend & Projected Profit by Channel (SGD)",
                items: [
                  { label: "B2B / Search (SGD 260K spend)", value: 169000, display: "+SGD 169K profit", tone: "success" },
                  { label: "MY Paid Social (SGD 220K spend)", value: 66000, display: "+SGD 66K profit", tone: "primary" },
                  { label: "Clean SG Paid Social (SGD 120K spend)", value: 23000, display: "+SGD 23K profit", tone: "accent" },
                  { label: "Unchanged 55/25/20 Mix at 600K (Unblocked)", value: -145000, display: "-SGD 145K loss", tone: "danger" }
                ]
              },
              table: {
                headers: ["Q4 Channel Plan", "Q4 Spend", "Projected Profit", "Plan Action"],
                rows: [
                  ["B2B / Search", "SGD 260K", "+SGD 169K", "Scale (+225%)"],
                  ["MY Paid Social", "SGD 220K", "+SGD 66K", "Scale (+120%)"],
                  ["Clean SG Paid Social (fraud blocked)", "SGD 120K", "+SGD 23K", "Protected & clean"],
                  ["Total Q4 Plan (512K net cash)", "SGD 600K", "+SGD 258K (+43% ROI)", "Recommended mix"]
                ]
              },
              citations: [
                { title: "AI.FORECAST (TimesFM 3.0)", subtitle: "BigQuery Forecasting [Preview]", snippet: "Forecasts fraud-scrubbed weekly channel history joined with Q4 spend reallocation in SQL." },
                { title: "cymbal_commerce.q3_scrubbed_weekly_channel", subtitle: "Certified Fraud-Scrubbed History", snippet: "Excludes 28 spoofed devices and incorporates SGD 88K agency cash clawback." }
              ],
              telemetry: { tokens: 770, sqlCount: 1, latencySec: 1.4, tablesScanned: 2, accuracy: 100, queryLabel: "1 governed SQL · AI.FORECAST (TimesFM 3.0)" }
            },
            rlsRoles: null,
            kcProvenance: {
              aggregation: {
                source: "Fraud-Scrubbed Certified History + Q4 Reallocation Table",
                assetPath: "bigquery://cymbal-commerce-prod.cymbal_commerce.q3_scrubbed_weekly_channel",
                signals: ["28 spoofed devices excluded", "Joined with q4_reallocation_plan spend ratios"]
              },
              enrichment: {
                loop: "Observe -> Enrich -> Validate -> Promote",
                observedGap: "Raw trend forecasting extrapolated bot-driven September gross revenue into a SGD 2.84M mirage.",
                proposalText: "Bind AI.FORECAST Verified Query #VQ-M6 to fraud-scrubbed history and Q4 channel reallocation.",
                confidence: "90% prediction interval (SGD 1.31M - 1.54M)",
                evalCheck: "Backtest WAPE < 5.2% on clean Q2-Q3 holdout",
                changeRequest: {
                  id: "CR-2026-0306",
                  status: "APPROVED",
                  steward: "Rachel Lim (VP Finance)",
                  timestamp: "2026-10-24 08:45 SGT"
                }
              },
              retrieval: {
                contextSet: "cymbal-commerce-1212-marketing [Preview]",
                mcpCall: "dataplex.googleapis.com/mcp -> lookup_context",
                assetsCount: 2,
                tokenBudget: "AI.FORECAST (TimesFM 3.0) Verified Query",
                yamlSnippet: "resources:\n  - simpleName: cymbal_commerce.q3_scrubbed_weekly_channel\n    forecastFunction: AI.FORECAST (TimesFM 3.0)\n    joinTable: cymbal_commerce.q4_reallocation_plan\n    guidelines:\n      - \"Always exclude flagged device_ring_28 rows before running Q4 budget forecasts.\""
              }
            },
            blindFollowUps: [
              {
                label: "Re-run Q6 with Knowledge Catalog",
                kind: "ground"
              },
              {
                label: "Summarize our Q3 SGD 400K media spend split across SEA channels",
                kind: "sibling",
                siblingId: "starter_q3_spend"
              },
              {
                label: "Break down Q3 campaign order volumes across Singapore and Malaysia",
                kind: "sibling",
                siblingId: "starter_q3_volumes"
              }
            ],
            followUps: [
              {
                label: "Compare Raw Schema vs. Knowledge Catalog runs from this session",
                kind: "sibling",
                siblingId: "closing_session_audit"
              },
              {
                label: "Generate the Executive Q4 Budget & Clawback Brief",
                kind: "sibling",
                siblingId: "closing_cfo_brief"
              },
              {
                label: "Break down weekly Q4 spend pacing across B2B, Malaysia, and clean SG",
                kind: "sibling",
                siblingId: "closing_q4_pacing"
              }
            ]
          }
        ],

        siblingResponses: {
          starter_q3_spend: {
            turnTitle: "Q3 Media Spend Allocation",
            summary: "Cymbal Commerce invested **SGD 400K** in Q3 campaign media across three channels: **SGD 220K (55%)** in Singapore Paid Social, **SGD 100K (25%)** in Malaysia Paid Social, and **SGD 80K (20%)** in B2B / Search.",
            headlineValue: "SGD 400K Q3 Spend",
            headlineUnit: "220K SG Social | 100K MY Social | 80K B2B/Search",
            kpis: [
              { label: "SG Paid Social", value: "SGD 220K", delta: "55% of Q3 budget", tone: "neutral" },
              { label: "MY Paid Social", value: "SGD 100K", delta: "25% of Q3 budget", tone: "primary" },
              { label: "B2B / Search", value: "SGD 80K", delta: "20% of Q3 budget", tone: "success" }
            ],
            citations: [{ title: "cymbal_commerce.campaign_spend", subtitle: "Campaign Ledger", snippet: "Approved Q3 FY26 SEA paid media allocation." }]
          },
          starter_q3_volumes: {
            turnTitle: "Q3 Campaign Order Volumes",
            summary: "Cymbal Commerce logged **4,850 paid campaign orders** across SEA in Q3 FY26: **Singapore Paid Social** drove **2,640 orders (54.4%)**, **Malaysia Paid Social** drove **1,460 orders (30.1%)**, and **B2B / Search** drove **750 orders (15.5%)**.",
            headlineValue: "4,850 Campaign Orders",
            headlineUnit: "54.4% SG Social | 30.1% MY Social | 15.5% B2B/Search",
            kpis: [
              { label: "SG Paid Social", value: "2,640 orders", delta: "54.4% of Q3 volume", tone: "neutral" },
              { label: "MY Paid Social", value: "1,460 orders", delta: "30.1% of Q3 volume", tone: "primary" },
              { label: "B2B / Search", value: "750 orders", delta: "15.5% of Q3 volume", tone: "success" }
            ],
            citations: [{ title: "cymbal_commerce.campaign_orders", subtitle: "Order Volume Summary", snippet: "Q3 FY26 SEA paid campaign order volume distribution." }]
          },
          starter_promo_rules: {
            turnTitle: "Q3 Promo & Agency MSA Terms",
            summary: "Active Q3 marketing policies cap single-use promotional trial codes at one redemption per verified buyer and bind paid media placements to **Agency Addendum #2 Clause 7.4**: if invalid bot or spoofed-device traffic exceeds **15%**, the agency owes a **100% cash refund** on all invalid spend.",
            headlineValue: "Clause 7.4 (>15% Trigger)",
            headlineUnit: "100% cash refund on invalid spend above 15% threshold",
            kpis: [
              { label: "Promo Rule", value: "1x per buyer", delta: "Single-use trial cap", tone: "primary" },
              { label: "Clause 7.4 Trigger", value: ">15% invalid", delta: "Verified in Agency PDF", tone: "warning" },
              { label: "Refund Rate", value: "100% of invalid", delta: "Cash credit from agency", tone: "success" }
            ],
            citations: [{ title: "Agency_Media_MSA_Addendum_2.pdf", subtitle: "GCS Object Table", snippet: "Clause 7.4 invalid-traffic audit & refund clause." }]
          },
          q1_market_split: {
            turnTitle: "Q3 Gross Attributed Split",
            summary: "Under Knowledge Catalog definitions (ex-9% GST and organic), Cymbal Commerce's **SGD 860K gross attributed Q3 orders** split across **SG Paid Social (SGD 450K gross / SGD 198K returns)**, **MY Paid Social (SGD 230K gross / SGD 30K returns)**, and **B2B / Search (SGD 180K gross / SGD 12K returns)** - yielding **SGD 620K net settled sales**.",
            headlineValue: "SGD 860K -> SGD 620K Net",
            headlineUnit: "450K SG PS + 230K MY PS + 180K B2B less 240K returns",
            kpis: [
              { label: "SG Paid Social Gross", value: "SGD 450K", delta: "SGD 198K returns (44.0%)", tone: "danger" },
              { label: "MY Paid Social Gross", value: "SGD 230K", delta: "SGD 30K returns (13.0%)", tone: "success" },
              { label: "B2B / Search Gross", value: "SGD 180K", delta: "SGD 12K returns (6.7%)", tone: "primary" }
            ],
            citations: [{ title: "cymbal_commerce.campaign_orders", subtitle: "Verified Query #VQ-M1", snippet: "Ex-GST attributed orders split by channel." }]
          },
          q1_q2_returns: {
            turnTitle: "Q3 vs. Q2 Return Baseline",
            summary: "SG Paid Social returns surged **+SGD 162K QoQ** from a healthy **SGD 36K Q2 baseline** to **SGD 198K in Q3** (+450% QoQ), driving **82.5% of Q3's SGD 240K total campaign returns**. Meanwhile Malaysia (SGD 30K) and B2B/Search (SGD 12K) tracked normal historical return rates.",
            headlineValue: "+SGD 162K SG Surge",
            headlineUnit: "SG Paid Social jumped from SGD 36K (Q2) to SGD 198K (Q3)",
            kpis: [
              { label: "Q2 SG Social Returns", value: "SGD 36K", delta: "Historical healthy baseline", tone: "success" },
              { label: "Q3 SG Social Returns", value: "SGD 198K", delta: "+SGD 162K spike (82.5%)", tone: "danger" },
              { label: "All Other Channels", value: "SGD 42K", delta: "MY 30K + B2B 12K steady", tone: "primary" }
            ],
            citations: [{ title: "cymbal_commerce.campaign_returns_certified", subtitle: "Certified Data Product", snippet: "QoQ return comparison across Q2 and Q3 FY26." }]
          },
          q2_promo_split: {
            turnTitle: "SG vs. MY Promo Code Usage",
            summary: "In Singapore Paid Social, **91% of orders** applied promotional trial codes (averaging a **44.0% return rate**). In Malaysia Paid Social, only **18% of orders** used promo codes and returns stayed healthy at **13.0%** (**SGD 30K**).",
            headlineValue: "91% SG vs. 18% MY",
            headlineUnit: "Promo-code concentration explains the Singapore return spike",
            kpis: [
              { label: "SG Paid Social Promos", value: "91% orders", delta: "44.0% return rate", tone: "danger" },
              { label: "MY Paid Social Promos", value: "18% orders", delta: "13.0% return rate", tone: "success" },
              { label: "B2B / Search Promos", value: "4% orders", delta: "6.7% return rate", tone: "primary" }
            ],
            citations: [{ title: "cymbal_commerce.campaign_returns_certified", subtitle: "AI.KEY_DRIVERS() Dimension", snippet: "Promo code share by market and channel." }]
          },
          q2_dq_blocked: {
            turnTitle: "Staging DQ Block Audit",
            summary: "Knowledge Catalog Auto Data Quality flagged `campaign_returns_raw` as **UNCERTIFIED** because **42% of `country_code` and `promo_tier` cells were NULL** and no BigQuery RLS policies were attached - preventing `AI.KEY_DRIVERS()` from misattributing returns to Malaysia.",
            headlineValue: "42% NULL Blocked",
            headlineUnit: "Auto Data Quality routed query to 0%-NULL certified table",
            kpis: [
              { label: "Staging Copy NULLs", value: "42% blank", delta: "Auto DQ FAILED", tone: "danger" },
              { label: "Certified Table NULLs", value: "0% blank", delta: "Auto DQ PASSED", tone: "success" },
              { label: "RLS Protection", value: "Enforced", delta: "country_code = 'SG' for SG Mgr", tone: "primary" }
            ],
            citations: [{ title: "cymbal_commerce.campaign_returns_certified", subtitle: "Auto DQ Aspect", snippet: "Blocks uncertified staging copies from agent context." }]
          },
          q3_sg_loss_split: {
            turnTitle: "SG Paid Social Loss Drivers",
            summary: "SG Paid Social's **-SGD 156K net loss** on **SGD 220K ad spend** reflects **SGD 88K in invalid bot/spoofed clicks** plus **SGD 96K in stacked promo coupons** (78% returned). Excluding both fraud vectors restores clean SG Paid Social to **+SGD 28K profit (+21.2% ROI on SGD 132K clean spend)**.",
            headlineValue: "-SGD 156K -> +SGD 28K Clean",
            headlineUnit: "Clean SG Paid Social earns +21.2% ROI on SGD 132K clean spend",
            kpis: [
              { label: "Reported SG PS Loss", value: "-SGD 156K", delta: "-71% ROI on SGD 220K", tone: "danger" },
              { label: "Invalid Spend + Coupons", value: "88K + 96K", delta: "Bot clicks + burner ring", tone: "warning" },
              { label: "Clean SG PS Profit", value: "+SGD 28K", delta: "+21.2% ROI on 132K spend", tone: "success" }
            ],
            citations: [{ title: "cymbal_marketing_model", subtitle: "BigQuery MEASURE()", snippet: "Reconciles -156K + 88K + 96K = +28K clean SG Paid Social." }]
          },
          q3_my_success: {
            turnTitle: "Why Malaysia Paid Social Won",
            summary: "Malaysia Paid Social generated **SGD 230K gross attributed sales** with only **SGD 30K returns (13.0%)** on **SGD 100K spend**, delivering **+SGD 32K net profit (+32% ROI)** - proving the campaign creative works wherever promo-code ring abuse is absent.",
            headlineValue: "+SGD 32K (+32% ROI)",
            headlineUnit: "Healthy 13.0% return rate on SGD 100K MY spend",
            kpis: [
              { label: "MY Gross Attributed", value: "SGD 230K", delta: "Only SGD 30K returns (13%)", tone: "success" },
              { label: "MY Media Spend", value: "SGD 100K", delta: "Clean human traffic", tone: "primary" },
              { label: "MY Net Profit", value: "+SGD 32K", delta: "+32.0% ROI", tone: "success" }
            ],
            citations: [{ title: "cymbal_marketing_model", subtitle: "BigQuery MEASURE()", snippet: "Malaysia Paid Social unit economics." }]
          },
          q4_device_clusters: {
            turnTitle: "Top Spoofed Device Clusters",
            summary: "All **28 spoofed devices** concentrated inside 3 emulator subnets hitting Singapore Paid Social promo links, spinning up an average of **22.9 burner accounts per device** (**640 accounts total**, **SGD 96,000** stacked coupons, **78%** order return rate).",
            headlineValue: "28 Devices -> 640 Burners",
            headlineUnit: "22.9 burner accounts per spoofed device",
            kpis: [
              { label: "Spoofed Devices", value: "28 hubs", delta: "3 emulator subnets", tone: "danger" },
              { label: "Linked Accounts", value: "640 burners", delta: "Shared cards & addresses", tone: "danger" },
              { label: "Stacked Coupons", value: "SGD 96,000", delta: "78% returned orders", tone: "warning" }
            ],
            citations: [{ title: "cymbal_fraud_graph", subtitle: "4-Hop ISO GQL", snippet: "ClickDevice -> Account -> PromoCode -> PaymentCard -> Address." }]
          },
          q4_my_clean: {
            turnTitle: "Malaysia Ring Verification",
            summary: "Running the identical 4-hop `GRAPH_TABLE` traversal across Malaysia Paid Social orders finds **0 linked burner rings** (device-to-account ratio `1.04x`), confirming Malaysia's **+32% ROI** is organic consumer demand.",
            headlineValue: "0 Rings in Malaysia",
            headlineUnit: "1.04 accounts per device - clean human traffic",
            kpis: [
              { label: "MY Device Ratio", value: "1.04x", delta: "Normal household sharing", tone: "success" },
              { label: "MY Fraud Ring Share", value: "0%", delta: "0 spoofed clusters", tone: "success" },
              { label: "Q4 Scale Readiness", value: "Cleared", delta: "Scale MY to SGD 220K", tone: "primary" }
            ],
            citations: [{ title: "cymbal_fraud_graph", subtitle: "BigQuery Property Graph", snippet: "Country-scoped ring verification." }]
          },
          q5_legal_packet: {
            turnTitle: "Agency Clawback Audit Packet",
            summary: "Audit notice prepared for Legal: cites **40.0% invalid Singapore Paid Social clicks** in `aws_adtech_iceberg.q3_paid_social_clicks` (**SGD 88,000 of SGD 220K** across 28 spoofed device fingerprints) exceeding **Agency Addendum #2 Clause 7.4's 15% threshold**, demanding a **SGD 88,000 cash refund**.",
            headlineValue: "SGD 88,000 Demand Ready",
            headlineUnit: "AWS S3 device hash log + Addendum #2 Clause 7.4 attached",
            kpis: [
              { label: "Cash Clawback", value: "SGD 88,000", delta: "100% refund (>15% breach)", tone: "success" },
              { label: "Invalid Traffic Rate", value: "40.0%", delta: "2.67x contractual threshold", tone: "danger" },
              { label: "Q3 Net Profit Flip", value: "+SGD 20K", delta: "-SGD 68K + SGD 88K refund", tone: "success" }
            ],
            citations: [
              { title: "aws_adtech_iceberg.q3_paid_social_clicks", subtitle: "AWS S3 Iceberg", snippet: "1.42M click audit trail." },
              { title: "Agency_Media_MSA_Addendum_2.pdf", subtitle: "GCS Object Table", snippet: "Clause 7.4 refund trigger." }
            ]
          },
          q5_clean_sg: {
            turnTitle: "Clean SG Paid Social Economics",
            summary: "Adding back the **SGD 88K agency cash clawback** and **SGD 96K blocked coupon bleed** to SG Paid Social's reported **-SGD 156K** loss yields **+SGD 28K net profit** on **SGD 132K clean media spend** (**+21.2% ROI**), justifying a targeted **SGD 120K** fraud-scrubbed Q4 SG allocation.",
            headlineValue: "+SGD 28K (+21.2% ROI)",
            headlineUnit: "On SGD 132K clean SG Paid Social spend (-156 + 88 + 96 = +28)",
            kpis: [
              { label: "Clean SG Spend", value: "SGD 132K", delta: "220K less 88K bot spend", tone: "primary" },
              { label: "Clean SG Net Profit", value: "+SGD 28K", delta: "+21.2% ROI", tone: "success" },
              { label: "Q4 Clean Allocation", value: "SGD 120K", delta: "Projects +SGD 23K profit", tone: "success" }
            ],
            citations: [{ title: "cymbal_marketing_model", subtitle: "Reconciled P&L", snippet: "Separates agency cash clawback (88K) from coupon bleed prevention (96K)." }]
          },
          closing_session_audit: {
            turnTitle: "Session Audit & LLM-as-a-Judge Scoreboard",
            customVisual: "session_audit_scoreboard",
            badgeLabel: "BigQuery Agent Analytics + AI.GENERATE_BOOL() Judge",
            summary: "Audited all **12 session runs** in **BigQuery Agent Analytics** (`cymbal_obs.agent_events`) and **`INFORMATION_SCHEMA.JOBS`** using an in-SQL **LLM-as-a-Judge (`AI.GENERATE_BOOL`)**: **Raw Schema scored 0 / 6** despite zero SQL errors (**17,500 tokens**, **25 SQLs**), while **Knowledge Catalog scored 6 / 6** with **76% fewer tokens (4,180)**, **SGD 88K cash back**, and **+SGD 258K Q4 profit**.",
            headlineValue: "0 / 6 Raw -> 6 / 6 Governed",
            headlineUnit: "-76% tokens (17.5K -> 4.18K) | 25 -> 6 SQLs | +SGD 88K cash + SGD 258K profit",
            thinkingSteps: [
              { active: "Querying BigQuery Agent Analytics (cymbal_obs.agent_events)...", done: "Loaded 12 session traces (6 Raw Schema vs. 6 Knowledge Catalog)", meta: "0.4s", code: "agent_events" },
              { active: "Running LLM-as-a-Judge (AI.GENERATE_BOOL) on SQL traces vs. Catalog rules...", done: "Graded 12 SQL traces against certified tables, MEASURE() & catalog rules (0/6 vs. 6/6)", meta: "0.8s", code: "AI.GENERATE_BOOL()" },
              { active: "Joining INFORMATION_SCHEMA.JOBS token & latency telemetry...", done: "Reconciled -76% token burn (17,500 -> 4,180) & 25 -> 6 SQLs", meta: "1.6s", code: "INFORMATION_SCHEMA.JOBS" }
            ],
            queryLang: "SQL",
            queryCode: "WITH session_traces AS (\n  SELECT\n    e.turn_number,\n    e.grounding_mode,\n    e.generated_sql,\n    e.usage_prompt_tokens + e.usage_completion_tokens AS total_tokens,\n    COUNT(DISTINCT j.job_id) AS sql_queries_run,\n    ROUND(AVG(TIMESTAMP_DIFF(j.end_time, j.start_time, MILLISECOND)) / 1000.0, 1) AS avg_latency_s\n  FROM cymbal_obs.agent_events e\n  JOIN `region-asia-southeast1`.INFORMATION_SCHEMA.JOBS j\n    ON e.bq_job_id = j.job_id\n  WHERE e.session_id = @current_session_id\n  GROUP BY 1, 2, 3, 4\n),\njudged AS (\n  SELECT\n    t.*,\n    AI.GENERATE_BOOL(\n      CONCAT(\n        'Audit this SQL trace against Knowledge Catalog rules (certified tables, ',\n        'Finance Net Revenue glossary, MEASURE(), cymbal_fraud_graph, S3/PDF, scrubbed forecast). ',\n        'Return TRUE only if the query complied with governed context: ', t.generated_sql\n      ),\n      connection_id => 'asia-southeast1.gemini_judge'\n    ).result AS passed_catalog_audit\n  FROM session_traces t\n)\nSELECT\n  grounding_mode,\n  COUNTIF(passed_catalog_audit) AS judge_passed_turns,\n  COUNT(*) AS total_turns,\n  SUM(sql_queries_run) AS total_sqls,\n  SUM(total_tokens) AS total_tokens,\n  ROUND(AVG(avg_latency_s), 1) AS avg_latency_sec\nFROM judged\nGROUP BY grounding_mode;",
            simpleContext: {
              badge: "BigQuery Agent Analytics + LLM-as-a-Judge",
              productTag: "agent_events + AI.GENERATE_BOOL() + INFORMATION_SCHEMA.JOBS",
              oneLiner: "Every agent prompt, SQL trace, and token count streams into BigQuery Agent Analytics, enabling an in-SQL LLM-as-a-Judge to verify whether each query followed Knowledge Catalog's certified tables, measures, and rules."
            },
            kpis: [
              { label: "LLM-as-a-Judge Pass", value: "0 / 6 -> 6 / 6", delta: "Same Gemini 4 Neon model", tone: "success" },
              { label: "Token Consumption", value: "-76% tokens", delta: "17,500 -> 4,180 tokens", tone: "primary" },
              { label: "Business Impact", value: "SGD 88K + 258K", delta: "Cash clawback + Q4 profit", tone: "success" }
            ],
            table: {
              headers: ["Turn", "Raw Schema (0/6 FAIL)", "Knowledge Catalog (6/6 PASS)", "SQLs", "Tokens"],
              rows: [
                ["Q1 Revenue", "SGD 1.85M / 0 ret (incl. GST + organic)", "SGD 620K Net / 240K Ret (Glossary + #VQ-M1)", "4 -> 1", "3,000 -> 900"],
                ["Q2 Root Cause", "Malaysia 68% (42% NULL staging table)", "SG Paid Social 82.5% / 198K (Certified + Key Drivers)", "5 -> 1", "3,400 -> 640"],
                ["Q3 True P&L", "+SGD 192K / +48% ROI (fan-trap join)", "-SGD 68K / -17% ROI (grain-locked MEASURE)", "4 -> 1", "2,900 -> 620"],
                ["Q4 Fraud Ring", "14 emails / SGD 2.8K (flat email check)", "640 burners / 28 devices / SGD 96K (4-hop Graph)", "5 -> 1", "3,300 -> 670"],
                ["Q5 Clawback", "SGD 0 recoverable (ERP payables only)", "+SGD 88,000 cash (AWS S3 + Agency PDF Clause 7.4)", "3 -> 1", "2,000 -> 580"],
                ["Q6 Q4 Plan", "SGD 2.84M mirage (bot-spike raw gross)", "SGD 1.42M rev / +SGD 258K profit (TimesFM 3.0)", "4 -> 1", "2,900 -> 770"],
                ["Session Total", "0 / 6 Judge Pass · Avg 4.8s", "6 / 6 Judge Pass · Avg 1.3s (-74%)", "25 -> 6", "17,500 -> 4,180 (-76%)"]
              ]
            },
            citations: [
              { title: "cymbal_obs.agent_events", subtitle: "BigQuery Agent Analytics", snippet: "Streams prompts, generated SQL, tables touched, token burn, and latency via Storage Write API." },
              { title: "AI.GENERATE_BOOL() Judge", subtitle: "In-SQL Trace Evaluation (GA)", snippet: "Audits every logged SQL trace against Knowledge Catalog certified tables, MEASURE(), graph, and rules." },
              { title: "INFORMATION_SCHEMA.JOBS", subtitle: "BigQuery Job Telemetry", snippet: "Confirms 25 exploratory SQLs -> 6 governed queries and avg latency 4.8s -> 1.3s." }
            ],
            telemetry: { tokens: 520, sqlCount: 1, latencySec: 1.6, queryLabel: "BigQuery Agent Analytics + AI.GENERATE_BOOL() Judge" }
          },
          closing_cfo_brief: {
            turnTitle: "Executive Q4 Budget & Clawback Brief",
            summary: "**Executive Decision Summary:** **(1)** Q3 real net sales = **SGD 620K** with **SGD 240K** returns; **(2)** `AI.KEY_DRIVERS()` + RLS isolated **SGD 198K (82.5% share)** to SG Paid Social; **(3)** `MEASURE()` proved **-SGD 68K** overall while B2B (**+56K**) & MY (**+32K**) won; **(4)** 4-hop Graph busted **640 burners / 28 devices / SGD 96K coupons**; **(5)** AWS S3 + Clause 7.4 recovers **SGD 88,000 cash** from the agency, flipping Q3 to **+SGD 20K**; **(6)** **Rebalanced SGD 600K Q4 plan** (**SGD 512K net new cash**) forecasts **SGD 1.42M revenue** & **+SGD 258K profit (+43% ROI)** vs. `-SGD 145K` on the unblocked Q3 mix.",
            headlineValue: "6 / 6 Grounded · Q4 Plan Ready",
            headlineUnit: "+SGD 88K Q3 clawback + SGD 258K Q4 profit (+43% ROI)",
            kpis: [
              { label: "Q3 Agency Clawback", value: "SGD 88,000", delta: "Flips Q3 to +SGD 20K", tone: "success" },
              { label: "Q4 Plan (Net Cash)", value: "SGD 600K (512K)", delta: "260K B2B · 220K MY · 120K SG", tone: "primary" },
              { label: "Q4 Forecast Profit", value: "+SGD 258K", delta: "+43% ROI on SGD 1.42M rev", tone: "success" }
            ],
            citations: [{ title: "cymbal-commerce-1212-marketing [Preview]", subtitle: "Context Set", snippet: "End-to-end 6-turn Q3 audit and Q4 budget reallocation loop." }]
          },
          closing_q4_pacing: {
            turnTitle: "Q4 Channel Budget & Profit Plan",
            summary: "The rebalanced **SGD 600K Q4 budget** (**SGD 512K net new cash** after the SGD 88K agency refund) shifts capital into proven high-ROI channels: **SGD 260K B2B/Search (+169K profit)**, **SGD 220K Malaysia Paid Social (+66K profit)**, and **SGD 120K fraud-scrubbed SG Paid Social (+23K profit)** = **+SGD 258K total profit (+43% ROI)**.",
            headlineValue: "SGD 600K -> +SGD 258K",
            headlineUnit: "Only SGD 512K net new cash needed after SGD 88K clawback",
            kpis: [
              { label: "B2B / Search", value: "SGD 260K -> +169K", delta: "65.0% channel ROI", tone: "success" },
              { label: "MY Paid Social", value: "SGD 220K -> +66K", delta: "30.0% channel ROI", tone: "primary" },
              { label: "Clean SG Social", value: "SGD 120K -> +23K", delta: "28 spoofed devices blocked", tone: "accent" }
            ],
            citations: [{ title: "AI.FORECAST (TimesFM 3.0)", subtitle: "Q4 Reallocation Forecast", snippet: "Joins baseline AI.FORECAST (TimesFM 3.0) with planned Q4 spend reallocation." }]
          },
          closing_kc_audit: {
            turnTitle: "Session Lineage & Context Audit",
            summary: "All 6 turns executed as single-shot governed queries over **`cymbal-commerce-1212-marketing`**, combining **Business Glossary + Verified Queries (GA)**, **Certified Data + AI.KEY_DRIVERS() + RLS (GA)**, **Semantic MEASURE() (GA)**, **4-Hop BigQuery Graph (GA)**, **AWS S3 Federation [Preview] + Object Tables/AI.GENERATE (GA)**, and **AI.FORECAST (TimesFM 3.0) [Preview]**.",
            headlineValue: "6 / 6 Single-Shot Grounded",
            headlineUnit: "CR-2026-0301 through CR-2026-0306 | Zero ETL movement",
            kpis: [
              { label: "Catalog Precision", value: "6 / 6 queries", delta: "1 governed query per turn", tone: "success" },
              { label: "Cross-Cloud & PDF", value: "AWS S3 + GCS PDF", delta: "Queried in place via SQL", tone: "primary" },
              { label: "Row Security", value: "BigQuery RLS", delta: "CMO vs SG Manager enforced", tone: "success" }
            ],
            citations: [{ title: "cymbal-commerce-1212-marketing [Preview]", subtitle: "Knowledge Catalog Context Set", snippet: "Managed grounding via dataplex.googleapis.com/mcp." }]
          }
        }
      }
    }
  };

  global.DEMO_SCENARIOS_V5 = DEMO_SCENARIOS_V5;
})(window);
