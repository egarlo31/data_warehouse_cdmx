-- ============================================
-- ETL: Carga de datos crudos a staging
-- ============================================

COPY staging_consumo
FROM '/docker-entrypoint-initdb.d/data/consumo_agua_historico_2019.csv'
DELIMITER ','
CSV HEADER
NULL 'NA';

COPY staging_clima
FROM '/docker-entrypoint-initdb.d/data/open-meteo-19.44N99.11W2233m.csv'
DELIMITER ','
CSV HEADER
NULL 'NA';