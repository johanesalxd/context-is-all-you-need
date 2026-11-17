-- BigQuery Property Graph & Semantic Measures (GA in asia-southeast1).
-- Topology forms N:1 trees from detail roots (OrderLine, ParcelLeg) outward to
-- dimension/header tables (CustomerOrder, Customer, SkuLotAllocation, ColdChainBatch)
-- so BOTH GRAPH_EXPAND(..., start_node => ...) + AGG(MEASURE) AND 4-hop GRAPH_TABLE ISO GQL execute cleanly.

CREATE OR REPLACE PROPERTY GRAPH `${PROJECT_ID}.${DATASET_ID}.meridian_supply_graph`
  NODE TABLES (
    `${PROJECT_ID}.${DATASET_ID}.customers` AS Customer
      KEY (customer_id)
      LABEL Customer
      PROPERTIES (
        customer_id,
        country_code,
        tier_code,
        segment_label,
        trailing_12m_spend_sgd,
        return_rate,
        channel_pref
      ),
    `${PROJECT_ID}.${DATASET_ID}.orders` AS CustomerOrder
      KEY (order_id)
      LABEL CustomerOrder
      PROPERTIES (
        order_id,
        customer_id,
        country_code,
        sales_channel,
        fulfillment_tier,
        order_date,
        order_status,
        amt_net_settled_sgd,
        fulfillment_fee_sgd,
        MEASURE(SUM(amt_net_settled_sgd)) AS total_net_revenue OPTIONS(
          description = "Grain-locked net realized revenue in SGD (ex-GST, net of returns)",
          synonyms = ["net_revenue", "realized_revenue"]
        ),
        MEASURE(SUM(fulfillment_fee_sgd)) AS total_fulfillment_fee OPTIONS(
          description = "Grain-locked order-level fulfillment cost in SGD",
          synonyms = ["fulfillment_cost"]
        )
      ),
    `${PROJECT_ID}.${DATASET_ID}.order_lines` AS OrderLine
      KEY (order_line_id)
      LABEL OrderLine
      PROPERTIES (
        order_line_id,
        order_id,
        sku_id,
        lot_id,
        qty,
        net_line_revenue_sgd,
        cogs_line_sgd,
        MEASURE(SUM(cogs_line_sgd)) AS total_cogs OPTIONS(
          description = "Grain-locked line-item Cost of Goods Sold in SGD",
          synonyms = ["cogs", "cost_of_goods"]
        ),
        MEASURE(SUM(net_line_revenue_sgd)) AS total_line_revenue OPTIONS(
          description = "Grain-locked net line revenue in SGD"
        )
      ),
    `${PROJECT_ID}.${DATASET_ID}.parcel_legs` AS ParcelLeg
      KEY (leg_id)
      LABEL ParcelLeg
      PROPERTIES (
        leg_id,
        order_id,
        hub_code,
        carrier_vendor,
        leg_seq,
        leg_cost_sgd,
        temp_excursion_celsius,
        excursion_minutes,
        MEASURE(SUM(leg_cost_sgd)) AS total_leg_cost OPTIONS(
          description = "Grain-locked parcel transfer leg cost in SGD",
          synonyms = ["carrier_cost", "leg_cost"]
        )
      ),
    `${PROJECT_ID}.${DATASET_ID}.sku_lot_allocations` AS SkuLotAllocation
      KEY (lot_id)
      LABEL SkuLotAllocation
      PROPERTIES (
        lot_id,
        batch_id,
        sku_id,
        temp_sensitive_class
      ),
    `${PROJECT_ID}.${DATASET_ID}.cold_chain_batches` AS ColdChainBatch
      KEY (batch_id)
      LABEL ColdChainBatch
      PROPERTIES (
        batch_id,
        supplier_tier,
        vendor_name,
        temp_peak_celsius,
        excursion_duration_min,
        shipment_invoice_sgd,
        batch_status
      )
  )
  EDGE TABLES (
    `${PROJECT_ID}.${DATASET_ID}.orders` AS PLACED_BY
      KEY (order_id)
      SOURCE KEY (order_id) REFERENCES CustomerOrder (order_id)
      DESTINATION KEY (customer_id) REFERENCES Customer (customer_id)
      LABEL PLACED_BY
      NO PROPERTIES,
    `${PROJECT_ID}.${DATASET_ID}.order_lines` AS BELONGS_TO_ORDER
      KEY (order_line_id)
      SOURCE KEY (order_line_id) REFERENCES OrderLine (order_line_id)
      DESTINATION KEY (order_id) REFERENCES CustomerOrder (order_id)
      LABEL BELONGS_TO_ORDER
      NO PROPERTIES,
    `${PROJECT_ID}.${DATASET_ID}.order_lines` AS ALLOCATED_FROM_LOT
      KEY (order_line_id)
      SOURCE KEY (order_line_id) REFERENCES OrderLine (order_line_id)
      DESTINATION KEY (lot_id) REFERENCES SkuLotAllocation (lot_id)
      LABEL ALLOCATED_FROM_LOT
      NO PROPERTIES,
    `${PROJECT_ID}.${DATASET_ID}.sku_lot_allocations` AS SUPPLIED_IN_BATCH
      KEY (lot_id)
      SOURCE KEY (lot_id) REFERENCES SkuLotAllocation (lot_id)
      DESTINATION KEY (batch_id) REFERENCES ColdChainBatch (batch_id)
      LABEL SUPPLIED_IN_BATCH
      NO PROPERTIES,
    `${PROJECT_ID}.${DATASET_ID}.parcel_legs` AS SHIPPED_FOR_ORDER
      KEY (leg_id)
      SOURCE KEY (leg_id) REFERENCES ParcelLeg (leg_id)
      DESTINATION KEY (order_id) REFERENCES CustomerOrder (order_id)
      LABEL SHIPPED_FOR_ORDER
      NO PROPERTIES
  );

-- Verification Query Example 1 (Rung 3 Grain-Locked Contribution Margin via GRAPH_EXPAND + AGG):
-- WITH order_line_metrics AS (
--   SELECT CustomerOrder_order_id AS order_id,
--          AGG(CustomerOrder_total_net_revenue) AS net_revenue_sgd,
--          AGG(CustomerOrder_total_fulfillment_fee) AS fulfillment_fee_sgd,
--          AGG(OrderLine_total_cogs) AS cogs_sgd
--   FROM GRAPH_EXPAND("${PROJECT_ID}.${DATASET_ID}.meridian_supply_graph", start_node => "OrderLine")
--   WHERE CustomerOrder_country_code = 'SG' AND CustomerOrder_order_status = 'COMPLETED'
--     AND CustomerOrder_fulfillment_tier = 'SAME_DAY'
--   GROUP BY CustomerOrder_order_id
-- ), parcel_leg_metrics AS (
--   SELECT CustomerOrder_order_id AS order_id, AGG(ParcelLeg_total_leg_cost) AS leg_cost_sgd
--   FROM GRAPH_EXPAND("${PROJECT_ID}.${DATASET_ID}.meridian_supply_graph", start_node => "ParcelLeg")
--   WHERE CustomerOrder_country_code = 'SG' AND CustomerOrder_order_status = 'COMPLETED'
--     AND CustomerOrder_fulfillment_tier = 'SAME_DAY'
--   GROUP BY CustomerOrder_order_id
-- )
-- SELECT ROUND(100.0 * SUM(olm.net_revenue_sgd - olm.cogs_sgd - olm.fulfillment_fee_sgd - COALESCE(plm.leg_cost_sgd, 0.0)) / SUM(olm.net_revenue_sgd), 1) AS contribution_margin_pct
-- FROM order_line_metrics olm LEFT JOIN parcel_leg_metrics plm USING (order_id);
--
-- Verification Query Example 2 (Rung 5 4-Hop ISO GQL Exposure Traversal):
-- SELECT ROUND(SUM(amt_net_settled_sgd), 2) AS exposed_revenue_sgd, COUNT(*) AS exposed_order_count
-- FROM (
--   SELECT DISTINCT order_id, amt_net_settled_sgd
--   FROM GRAPH_TABLE(
--     `${PROJECT_ID}.${DATASET_ID}.meridian_supply_graph`
--     MATCH (b:ColdChainBatch {batch_id: '#LN-409', supplier_tier: 'TIER_2'})
--           <-[:SUPPLIED_IN_BATCH]-(lot:SkuLotAllocation)
--           <-[:ALLOCATED_FROM_LOT]-(ol:OrderLine)
--           -[:BELONGS_TO_ORDER]->(o:CustomerOrder)
--           -[:PLACED_BY]->(c:Customer)
--     FILTER o.country_code = 'SG' AND o.order_status = 'COMPLETED' AND c.tier_code = 'PRM_HV'
--     RETURN o.order_id AS order_id, o.amt_net_settled_sgd AS amt_net_settled_sgd
--   )
-- );
