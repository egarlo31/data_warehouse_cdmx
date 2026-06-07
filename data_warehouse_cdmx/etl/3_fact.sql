-- ============================================
-- ETL: Poblar tablas de hechos
-- ============================================

-- Poblar fact_consumo_agua
INSERT INTO fact_consumo_agua (
    id_tiempo,
    id_ubicacion,
    id_indice_des,
    consumo_total_mixto,
    consumo_prom_dom,
    consumo_total_dom,
    consumo_prom_mixto,
    consumo_total,
    consumo_prom,
    consumo_prom_no_dom,
    consumo_total_no_dom
)
SELECT
    t.id_tiempo,
    u.id_ubicacion,
    i.id_indice_des,
    s.consumo_total_mixto,
    s.consumo_prom_dom,
    s.consumo_total_dom,
    s.consumo_prom_mixto,
    s.consumo_total,
    s.consumo_prom,
    s.consumo_prom_no_dom,
    s.consumo_total_no_dom
FROM staging_consumo s
JOIN dim_tiempo t ON s.fecha_referencia = t.fecha
JOIN dim_ubicacion u ON s.colonia = u.colonia AND s.alcaldia = u.alcaldia
JOIN dim_indice_des i ON s.indice_des = i.indice_des;

-- Poblar fact_clima
INSERT INTO fact_clima (
    id_tiempo,
    temp_maxima,
    temp_minima,
    temp_promedio,
    humedad_promedio,
    lluvia_total
)
SELECT
    t.id_tiempo,
    MAX(s.temperatura),
    MIN(s.temperatura),
    AVG(s.temperatura),
    AVG(s.humedad_relativa),
    SUM(s.lluvia)
FROM staging_clima s
JOIN dim_tiempo t ON DATE(s.fecha_hora) = t.fecha
GROUP BY t.id_tiempo;

-- ============================================
-- LIMPIEZA: Eliminar tablas staging
-- ============================================
DROP TABLE staging_consumo;
DROP TABLE staging_clima;