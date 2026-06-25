# Despliegue en Render

Render provisiona Postgres gestionado, por lo que los scripts en
`/docker-entrypoint-initdb.d/` del `Dockerfile` **no se ejecutan**. Las
migraciones deben aplicarse manualmente contra la base de datos de Render.

## 1. Crear la base de datos en Render

En el dashboard de Render:

1. **New + → PostgreSQL** y crea la instancia.
2. Copia la **Internal Database URL** (la usan los servicios en el mismo
   region) o la **External Database URL** (para correr cosas desde tu
   máquina).

> Las migraciones crean el esquema `public`; no hace falta crear nada más.

## 2. Aplicar las migraciones

Desde tu máquina local:

```bash
# Simular primero (no toca la BD)
python scripts/migrate.py --url "<EXTERNAL_DATABASE_URL>" --dry-run

# Aplicar de verdad
python scripts/migrate.py --url "<EXTERNAL_DATABASE_URL>"
```

Alternativa directa con `psql`:

```bash
psql "<EXTERNAL_DATABASE_URL>" -f migrations/001_drop_users_table.sql
psql "<EXTERNAL_DATABASE_URL>" -f migrations/002_schema.sql
```

Las migraciones son **idempotentes** (usan `CREATE TABLE IF NOT EXISTS` /
`DROP TABLE IF EXISTS`), así que puedes re-ejecutarlas sin miedo.

## 3. Cargar los datos (ETL)

Las migraciones SQL **no** incluyen la carga de los CSV. Render no tiene
acceso a los archivos locales del repo. Tienes dos opciones:

### Opción A — Ejecutar el ETL desde tu máquina

Levanta un túnel o usa la *External Database URL* y corre:

```bash
# 1. Crear tablas staging con la migración 002
# 2. Cargar los CSV a staging (ajusta las rutas si las moviste)
psql "<EXTERNAL_DATABASE_URL>" -c "\COPY staging_consumo FROM 'data_warehouse_cdmx/data/consumo_agua_historico_2019.csv' DELIMITER ',' CSV HEADER NULL 'NA';"
psql "<EXTERNAL_DATABASE_URL>" -c "\COPY staging_clima FROM 'data_warehouse_cdmx/data/open-meteo-19.44N99.11W2233m.csv' DELIMITER ',' CSV HEADER NULL 'NA';"

# 3. Poblar dimensiones y hechos (los archivos en data_warehouse_cdmx/etl/
#    usan rutas locales del Docker; reemplázalas o adáptalas)
psql "<EXTERNAL_DATABASE_URL>" -f data_warehouse_cdmx/etl/2_dim.sql
psql "<EXTERNAL_DATABASE_URL>" -f data_warehouse_cdmx/etl/3_fact.sql
```

### Opción B — Reemplazar el ETL por un loader Python

Convertir `1_copy.sql`/`2_dim.sql`/`3_fact.sql` a un script Python que use
`pandas` + `psycopg2` (más portable entre local y Render). Esto es trabajo
adicional fuera del alcance de las migraciones.

### Opción C — Servicio separado de cron en Render

Crear un *Background Worker* en Render que clone el repo, lea los CSV de
un *Persistent Disk* y ejecute el ETL periódicamente. Tampoco entra en el
alcance de estas migraciones.

## 4. Servicio web (FastAPI)

En Render, **New + → Web Service**:

| Campo               | Valor                                                  |
| ------------------- | ------------------------------------------------------ |
| Runtime             | Python                                                 |
| Build Command       | `pip install -r requirements.txt`                     |
| Start Command       | `uvicorn main:app --host 0.0.0.0 --port $PORT`         |
| Instance Type       | Free (Starter) o superior                              |

Variables de entorno (Render las inyecta automáticamente si la BD está en
el mismo region):

| Variable          | Fuente                                                  |
| ----------------- | ------------------------------------------------------- |
| `DB_HOST`         | host del *Internal Database URL*                        |
| `DB_PORT`         | `5432` (Render)                                         |
| `DB_NAME`         | nombre de la BD (suele ser `dw_cdmx` o el que definas)  |
| `DB_USER`         | usuario del *Internal Database URL*                     |
| `DB_PASSWORD`     | contraseña del *Internal Database URL*                  |
| `ALLOWED_ORIGINS` | URL pública del web service, p.ej. `https://dw-cdmx.onrender.com` |

> **Nota**: ya no se necesitan `JWT_SECRET`, `JWT_ALGORITHM` ni
> `JWT_EXPIRES_MINUTES` — se eliminaron al quitar el sistema de login.

## 5. Verificar

Una vez desplegado:

```bash
curl https://<tu-servicio>.onrender.com/api/health
# → {"status":"ok"}

curl https://<tu-servicio>.onrender.com/api/anios
# → [2019, ...]
```

Si `/api/anios` devuelve lista vacía pero la BD tiene datos, probablemente
no se ejecutó el ETL (paso 3).

## Estructura

```
migrations/
├── 001_drop_users_table.sql   # Limpia la tabla del login eliminado
└── 002_schema.sql             # Esquema del DW (idempotente)

scripts/
└── migrate.py                 # Runner que aplica los .sql en orden
```
