-- ============================================
-- Migración: poblar lat/lon de dim_ubicacion
-- usando el CSV original (no requiere staging)
-- ============================================
-- Ejecutar desde el host:
--   docker cp data_warehouse_cdmx/data/consumo_agua_historico_2019.csv dw_postgres:/tmp/coords.csv
--   docker exec -i dw_postgres psql -U emilio -d dw_cdmx -f /tmp/coords_migracion.sql
--
-- O más simple, todo en un paso (ver bloque de abajo).

CREATE TEMP TABLE tmp_coords (
    alcaldia  VARCHAR(255),
    colonia   VARCHAR(255),
    latitud   NUMERIC,
    longitud  NUMERIC
);

COPY tmp_coords (alcaldia, colonia, latitud, longitud)
FROM '/tmp/coords.csv'
DELIMITER ','
CSV HEADER
NULL 'NA';

UPDATE dim_ubicacion d
SET latitud = c.latitud, longitud = c.longitud
FROM (
    SELECT DISTINCT ON (alcaldia, colonia) alcaldia, colonia, latitud, longitud
    FROM tmp_coords
    WHERE alcaldia IS NOT NULL
      AND colonia  IS NOT NULL
      AND latitud  IS NOT NULL
      AND longitud IS NOT NULL
    ORDER BY alcaldia, colonia, latitud, longitud
) c
WHERE d.alcaldia = c.alcaldia
  AND d.colonia  = c.colonia
  AND (d.latitud IS NULL OR d.longitud IS NULL);

DROP TABLE tmp_coords;

-- Sanity check
SELECT COUNT(*) AS total_ubicaciones,
       COUNT(latitud) AS con_coordenadas
FROM dim_ubicacion;
