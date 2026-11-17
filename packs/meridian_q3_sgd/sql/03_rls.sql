-- Row-Level Security (RLS) policies on the certified Cold-Chain Data Product.
-- Beat 4b Identity Switch:
--   cfo_regional  -> sees all 4 SEA markets (SG, MY, TH, ID) -> SGD 842,600.00
--   sg_coldchain  -> restricted strictly to country_code = 'SG' -> SGD 346,480.00

CREATE OR REPLACE ROW ACCESS POLICY rls_cfo_regional_all_markets
ON `${PROJECT_ID}.${DATASET_ID}.cold_chain_margin_gold`
GRANT TO ("${RLS_CFO_PRINCIPAL}")
FILTER USING (TRUE);

CREATE OR REPLACE ROW ACCESS POLICY rls_sg_coldchain_country_sg
ON `${PROJECT_ID}.${DATASET_ID}.cold_chain_margin_gold`
GRANT TO ("${RLS_SG_PRINCIPAL}")
FILTER USING (country_code = 'SG');
