-- BigQuery Property Graph (GA in asia-southeast1) for Cymbal Commerce promo & click fraud ring.
-- 4-hop entity lineage:
--   (ClickDevice)-[:SPAWNED]->(Account)-[:REDEEMED]->(PromoCode)
--   (Account)-[:PAID_WITH]->(PaymentCard)-[:SHIPS_TO]->(Address)

CREATE OR REPLACE PROPERTY GRAPH `${PROJECT_ID}.cymbal_commerce.cymbal_fraud_graph`
  NODE TABLES (
    `${PROJECT_ID}.cymbal_commerce.fraud_devices` AS ClickDevice
      KEY (device_id)
      LABEL ClickDevice
      PROPERTIES (
        device_id,
        emulator_subnet,
        country_code
      ),
    `${PROJECT_ID}.cymbal_commerce.fraud_accounts` AS Account
      KEY (account_id)
      LABEL Account
      PROPERTIES (
        account_id,
        account_email,
        country_code,
        is_returned
      ),
    `${PROJECT_ID}.cymbal_commerce.fraud_promos` AS PromoCode
      KEY (promo_id)
      LABEL PromoCode
      PROPERTIES (
        promo_id,
        campaign_code,
        coupon_sgd
      ),
    `${PROJECT_ID}.cymbal_commerce.fraud_cards` AS PaymentCard
      KEY (card_id)
      LABEL PaymentCard
      PROPERTIES (
        card_id,
        card_type
      ),
    `${PROJECT_ID}.cymbal_commerce.fraud_addresses` AS Address
      KEY (address_id)
      LABEL Address
      PROPERTIES (
        address_id,
        country_code
      )
  )
  EDGE TABLES (
    `${PROJECT_ID}.cymbal_commerce.edge_device_account` AS SPAWNED
      KEY (edge_id)
      SOURCE KEY (device_id) REFERENCES ClickDevice (device_id)
      DESTINATION KEY (account_id) REFERENCES Account (account_id)
      LABEL SPAWNED
      NO PROPERTIES,
    `${PROJECT_ID}.cymbal_commerce.edge_account_promo` AS REDEEMED
      KEY (edge_id)
      SOURCE KEY (account_id) REFERENCES Account (account_id)
      DESTINATION KEY (promo_id) REFERENCES PromoCode (promo_id)
      LABEL REDEEMED
      NO PROPERTIES,
    `${PROJECT_ID}.cymbal_commerce.edge_account_card` AS PAID_WITH
      KEY (edge_id)
      SOURCE KEY (account_id) REFERENCES Account (account_id)
      DESTINATION KEY (card_id) REFERENCES PaymentCard (card_id)
      LABEL PAID_WITH
      NO PROPERTIES,
    `${PROJECT_ID}.cymbal_commerce.edge_card_address` AS SHIPS_TO
      KEY (edge_id)
      SOURCE KEY (card_id) REFERENCES PaymentCard (card_id)
      DESTINATION KEY (address_id) REFERENCES Address (address_id)
      LABEL SHIPS_TO
      NO PROPERTIES
  );
