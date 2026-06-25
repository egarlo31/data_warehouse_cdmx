-- ============================================
-- Migración: Eliminar tablas relacionadas al login
-- ============================================

DROP TABLE IF EXISTS users CASCADE;
DROP TABLE IF EXISTS usuarios CASCADE;
