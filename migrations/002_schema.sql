-- ============================================
-- Migración 002: Esquema del Data Warehouse
-- ============================================
-- Crea el esquema del DW si no existe. Es idempotente
-- (usa CREATE TABLE IF NOT EXISTS) por lo que puede
-- ejecutarse múltiples veces sin fallar.
--
-- Incluye:
--   - Tablas staging (datos crudos antes del ETL)
--   - Dimensiones (tiempo, ubicación, índice)
--   - Tablas de hechos (consumo de agua, clima)
--   - Tabla de alertas (consumo anómalo vía ML)

-- ============================================
-- STAGING: Consumo de Agua
-- ============================================
CREATE TABLE IF NOT EXISTS staging_consumo (
    fecha_referencia DATE,
    anio INT,
    bimestre INT,
    consumo_total_mixto NUMERIC,
    consumo_prom_dom NUMERIC,
    consumo_total_dom NUMERIC,
    consumo_prom_mixto NUMERIC,
    consumo_total NUMERIC,
    consumo_prom NUMERIC,
    consumo_prom_no_dom NUMERIC,
    consumo_total_no_dom NUMERIC,
    indice_des VARCHAR(50),
    colonia VARCHAR(255),
    alcaldia VARCHAR(255),
    latitud NUMERIC,
    longitud NUMERIC
);

-- ============================================
-- STAGING: Clima
-- ============================================
CREATE TABLE IF NOT EXISTS staging_clima (
    fecha_hora TIMESTAMP,
    temperatura NUMERIC,
    humedad_relativa INT,
    lluvia NUMERIC
);

-- ============================================
-- DIMENSIONES
-- ============================================

CREATE TABLE IF NOT EXISTS dim_tiempo (
    id_tiempo SERIAL PRIMARY KEY,
    fecha DATE UNIQUE,
    anio INT,
    mes INT,
    dia INT,
    bimestre INT
);

CREATE TABLE IF NOT EXISTS dim_ubicacion (
    id_ubicacion SERIAL PRIMARY KEY,
    alcaldia VARCHAR(255),
    colonia VARCHAR(255),
    latitud NUMERIC,
    longitud NUMERIC
);

CREATE TABLE IF NOT EXISTS dim_indice_des (
    id_indice_des SERIAL PRIMARY KEY,
    indice_des VARCHAR(50)
);

-- ============================================
-- TABLAS DE HECHOS
-- ============================================

CREATE TABLE IF NOT EXISTS fact_consumo_agua (
    id_fact SERIAL PRIMARY KEY,
    id_tiempo INT REFERENCES dim_tiempo(id_tiempo),
    id_ubicacion INT REFERENCES dim_ubicacion(id_ubicacion),
    id_indice_des INT REFERENCES dim_indice_des(id_indice_des),
    consumo_total_mixto NUMERIC,
    consumo_prom_dom NUMERIC,
    consumo_total_dom NUMERIC,
    consumo_prom_mixto NUMERIC,
    consumo_total NUMERIC,
    consumo_prom NUMERIC,
    consumo_prom_no_dom NUMERIC,
    consumo_total_no_dom NUMERIC
);

CREATE TABLE IF NOT EXISTS fact_clima (
    id_fact_clima SERIAL PRIMARY KEY,
    id_tiempo INT REFERENCES dim_tiempo(id_tiempo),
    temp_maxima NUMERIC,
    temp_minima NUMERIC,
    temp_promedio NUMERIC,
    humedad_promedio NUMERIC,
    lluvia_total NUMERIC
);

-- ============================================
-- ALERTAS (resultado del pipeline de ML)
-- ============================================
CREATE TABLE IF NOT EXISTS alertas_consumo (
    id_alerta SERIAL PRIMARY KEY,
    id_fact INT REFERENCES fact_consumo_agua(id_fact) ON DELETE CASCADE,
    alcaldia VARCHAR(255),
    colonia VARCHAR(255),
    anio INT,
    bimestre INT,
    consumo_total NUMERIC,
    consumo_esperado NUMERIC,
    desviacion_porcentaje NUMERIC,
    metodo VARCHAR(50),
    score NUMERIC,
    es_anomalo BOOLEAN,
    fecha_deteccion TIMESTAMP DEFAULT NOW()
);
