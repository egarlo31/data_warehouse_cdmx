-- ============================================
-- Migración 003: Extensión unaccent
-- ============================================
-- Habilita la extensión ``unaccent`` de PostgreSQL para
-- realizar comparaciones de texto acento- y mayúsculas-
-- insensibles (útil porque la BD almacena los nombres de
-- alcaldía en MAYÚSCULAS sin acentos, mientras que el
-- GeoJSON los expone con acentos).
--
-- Idempotente: CREATE EXTENSION IF NOT EXISTS no falla si
-- la extensión ya está habilitada.

CREATE EXTENSION IF NOT EXISTS unaccent;