-- ============================================
-- ETL: Poblar dimensiones
-- ============================================

-- Poblar dim_ubicacion
INSERT INTO dim_ubicacion (alcaldia, colonia)
SELECT DISTINCT alcaldia, colonia
FROM staging_consumo
WHERE colonia IS NOT NULL;

-- Poblar dim_indice_des
INSERT INTO dim_indice_des (indice_des)
SELECT DISTINCT indice_des
FROM staging_consumo
WHERE indice_des IS NOT NULL;

-- Poblar dim_tiempo (desde staging_clima - diarias)
INSERT INTO dim_tiempo (fecha, anio, mes, dia, bimestre)
SELECT DISTINCT
    DATE(fecha_hora),
    EXTRACT(YEAR FROM fecha_hora)::INT,
    EXTRACT(MONTH FROM fecha_hora)::INT,
    EXTRACT(DAY FROM fecha_hora)::INT,
    CASE
        WHEN EXTRACT(MONTH FROM fecha_hora) IN (1,2) THEN 1
        WHEN EXTRACT(MONTH FROM fecha_hora) IN (3,4) THEN 2
        WHEN EXTRACT(MONTH FROM fecha_hora) IN (5,6) THEN 3
        WHEN EXTRACT(MONTH FROM fecha_hora) IN (7,8) THEN 4
        WHEN EXTRACT(MONTH FROM fecha_hora) IN (9,10) THEN 5
        ELSE 6
    END
FROM staging_clima
ON CONFLICT (fecha) DO NOTHING;