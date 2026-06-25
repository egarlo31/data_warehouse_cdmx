"""Aplica las migraciones SQL del directorio ``migrations/`` contra la BD.

Uso:

    # Usa DATABASE_URL del entorno (recomendado en Render / CI)
    python scripts/migrate.py

    # O explícitamente:
    python scripts/migrate.py --url "postgresql://user:pass@host:5432/dbname"

    # Simular sin ejecutar nada:
    python scripts/migrate.py --dry-run

Las migraciones se aplican en orden lexicográfico. Cada archivo se ejecuta
dentro de su propia transacción; si una falla, se hace rollback y se
detiene el proceso con código de salida != 0.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import psycopg2


MIGRATIONS_DIR = Path(__file__).resolve().parent.parent / "migrations"


def list_migrations() -> list[Path]:
    if not MIGRATIONS_DIR.exists():
        raise FileNotFoundError(f"No se encontró el directorio {MIGRATIONS_DIR}")
    files = sorted(p for p in MIGRATIONS_DIR.glob("*.sql") if p.is_file())
    if not files:
        raise FileNotFoundError(f"No hay archivos .sql en {MIGRATIONS_DIR}")
    return files


def resolve_url(explicit: str | None) -> str:
    if explicit:
        return explicit
    url = os.getenv("DATABASE_URL")
    if not url:
        raise SystemExit(
            "DATABASE_URL no está definida. "
            "Pásala con --url o exporta la variable de entorno."
        )
    # Render suele entregar postgres:// en lugar de postgresql://
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    return url


def apply_migration(conn, path: Path, dry_run: bool) -> None:
    sql = path.read_text(encoding="utf-8")
    print(f"  → {path.name} ({len(sql)} chars)")
    if dry_run:
        return
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()


def main() -> int:
    parser = argparse.ArgumentParser(description="Aplica migraciones SQL a la BD.")
    parser.add_argument("--url", help="Cadena de conexión (si no, usa DATABASE_URL)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Muestra qué se aplicaría sin ejecutar nada",
    )
    args = parser.parse_args()

    url = resolve_url(args.url)
    files = list_migrations()
    print(f"Aplicando {len(files)} migración(es) desde {MIGRATIONS_DIR}")
    print(f"Target: {url.split('@')[-1] if '@' in url else url}")

    conn = None
    try:
        if not args.dry_run:
            conn = psycopg2.connect(url)
        for path in files:
            apply_migration(conn, path, args.dry_run)
    except psycopg2.Error as exc:
        print(f"\nERROR aplicando migración: {exc}", file=sys.stderr)
        if conn is not None:
            conn.rollback()
        return 1
    finally:
        if conn is not None:
            conn.close()

    print("\nMigraciones aplicadas correctamente.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
