-- ============================================
-- Migración 001: Eliminar tabla de usuarios
-- ============================================
-- Limpia la tabla `users` que era usada por el sistema
-- de login/registro eliminado del proyecto.
--
-- Es idempotente: no falla si la tabla no existe.

DROP TABLE IF EXISTS users;
