-- ============================================
-- DDL: Esquema del Data Warehouse
-- ============================================

-- ============================================
-- STAGING: Consumo de Agua
-- ============================================
CREATE TABLE staging_consumo (
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
CREATE TABLE staging_clima (
    fecha_hora TIMESTAMP,
    temperatura NUMERIC,
    humedad_relativa INT,
    lluvia NUMERIC
);

-- ============================================
-- DIMENSIONES
-- ============================================

-- Dimensión de Tiempo
CREATE TABLE dim_tiempo (
    id_tiempo SERIAL PRIMARY KEY,
    fecha DATE UNIQUE,
    anio INT,
    mes INT,
    dia INT,
    bimestre INT
);

-- Dimensión de Ubicación (sin lat/long)
CREATE TABLE dim_ubicacion (
    id_ubicacion SERIAL PRIMARY KEY,
    alcaldia VARCHAR(255),
    colonia VARCHAR(255)
);

-- Dimensión de Índice de Desarrollo
CREATE TABLE dim_indice_des (
    id_indice_des SERIAL PRIMARY KEY,
    indice_des VARCHAR(50)
);

-- ============================================
-- TABLAS DE HECHOS
-- ============================================

-- Tabla de Hechos: Consumo de Agua
CREATE TABLE fact_consumo_agua (
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

-- Tabla de Hechos: Clima
CREATE TABLE fact_clima (
    id_fact_clima SERIAL PRIMARY KEY,
    id_tiempo INT REFERENCES dim_tiempo(id_tiempo),
    temp_maxima NUMERIC,
    temp_minima NUMERIC,
    temp_promedio NUMERIC,
    humedad_promedio NUMERIC,
    lluvia_total NUMERIC
);