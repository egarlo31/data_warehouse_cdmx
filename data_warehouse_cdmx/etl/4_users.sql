-- ============================================
-- USUARIO DE APLICACIÓN
-- ============================================
-- Crea el rol usado por la API para conectarse.
-- Es idempotente: si el rol ya existe, no falla.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'emilio') THEN
        CREATE ROLE emilio LOGIN PASSWORD 'emilio123';
    END IF;
END
$$;

GRANT CONNECT ON DATABASE dw_cdmx TO emilio;
GRANT USAGE  ON SCHEMA public TO emilio;
GRANT SELECT, INSERT, UPDATE, DELETE
    ON ALL TABLES    IN SCHEMA public TO emilio;
GRANT USAGE, SELECT
    ON ALL SEQUENCES IN SCHEMA public TO emilio;

ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO emilio;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    GRANT USAGE, SELECT ON SEQUENCES TO emilio;
