-- Correlación entre consumo de agua y temperatura en CDMX

WITH ClimaBimestral AS (
    SELECT
        t.anio,
        t.bimestre,
        ROUND(AVG(fc.temp_promedio), 2) AS temp_promedio,
        COUNT(CASE WHEN fc.temp_maxima >= 28 THEN 1 END) AS dias_ola_calor,
        COUNT(CASE WHEN fc.temp_minima <= 10 THEN 1 END) AS dias_frio,
        SUM(fc.lluvia_total) AS total_lluvia
    FROM fact_clima fc
    JOIN dim_tiempo t ON fc.id_tiempo = t.id_tiempo
    GROUP BY t.anio, t.bimestre
),
AguaBimestral AS (
    SELECT
        t.anio,
        t.bimestre,
        SUM(fca.consumo_total) AS total_agua
    FROM fact_consumo_agua fca
    JOIN dim_tiempo t ON fca.id_tiempo = t.id_tiempo
    GROUP BY t.anio, t.bimestre
)
SELECT
    a.anio,
    a.bimestre,
    a.total_agua,
    c.temp_promedio,
    c.dias_ola_calor,
    c.dias_frio,
    c.total_lluvia
FROM AguaBimestral a
JOIN ClimaBimestral c ON a.anio = c.anio AND a.bimestre = c.bimestre
ORDER BY a.anio, a.bimestre;