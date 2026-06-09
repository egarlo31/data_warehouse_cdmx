-- ============================================
-- MIGRACIÓN: Tabla de Usuarios
-- ============================================
-- Almacena las credenciales de los usuarios
-- que consumen la API del Data Warehouse.

CREATE TABLE IF NOT EXISTS users (
    id_user        SERIAL PRIMARY KEY,
    username       VARCHAR(50)  UNIQUE NOT NULL,
    email          VARCHAR(255) UNIQUE NOT NULL,
    password_hash  VARCHAR(255) NOT NULL,
    role           VARCHAR(20)  NOT NULL DEFAULT 'user'
                   CHECK (role IN ('admin', 'user', 'analyst')),
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMP    NOT NULL DEFAULT NOW(),
    updated_at     TIMESTAMP    NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email    ON users(email);
