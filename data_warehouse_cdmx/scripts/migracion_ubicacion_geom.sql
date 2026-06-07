-- ============================================
-- Migración: añadir coordenadas a dim_ubicacion
-- ============================================
-- Para instalaciones existentes (volumen ya inicializado).
-- En instalaciones nuevas, 0_schema.sql + 2_dim.sql ya
-- crean y rellenan latitud/longitud automáticamente.

ALTER TABLE dim_ubicacion
    ADD COLUMN IF NOT EXISTS latitud  NUMERIC,
    ADD COLUMN IF NOT EXISTS longitud NUMERIC;

UPDATE dim_ubicacion d
SET latitud = s.latitud, longitud = s.longitud
FROM (
    SELECT DISTINCT ON (alcaldia, colonia) alcaldia, colonia, latitud, longitud
    FROM staging_consumo
    WHERE colonia IS NOT NULL
      AND latitud IS NOT NULL
      AND longitud IS NOT NULL
    ORDER BY alcaldia, colonia, latitud, longitud
) s
WHERE d.alcaldia = s.alcaldia
  AND d.colonia  = s.colonia
  AND (d.latitud IS NULL OR d.longitud IS NULL);
