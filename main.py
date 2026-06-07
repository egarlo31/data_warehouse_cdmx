import os
import re
import json
import logging
import urllib.request
from datetime import datetime, timedelta, timezone
from contextlib import contextmanager

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field, field_validator
from passlib.context import CryptContext
import psycopg2
from psycopg2 import errors
from psycopg2.extras import RealDictCursor
import jwt

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5435"))
DB_NAME = os.getenv("DB_NAME", "dw_cdmx")
DB_USER = os.getenv("DB_USER", "emilio")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

JWT_SECRET = os.getenv("JWT_SECRET")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
JWT_EXPIRES_MINUTES = int(os.getenv("JWT_EXPIRES_MINUTES", "60"))

ALLOWED_ORIGINS = [o.strip() for o in os.getenv("ALLOWED_ORIGINS", "").split(",") if o.strip()]

MAX_LIMIT = 500
MIN_PASSWORD_LENGTH = 8

ALCALDIAS_GEOJSON_URL = (
    "https://raw.githubusercontent.com/PhantomInsights/mexico-geojson/"
    "main/2023/states/Ciudad%20de%20M%C3%A9xico.json"
)
_geojson_cache: dict | None = None

if not JWT_SECRET or len(JWT_SECRET) < 32:
    raise RuntimeError("JWT_SECRET must be defined in .env and be at least 32 characters long")
if not DB_PASSWORD:
    raise RuntimeError("DB_PASSWORD must be defined in .env")

logger = logging.getLogger("dw_cdmx")
logging.basicConfig(level=logging.INFO)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS or [],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Authorization"],
)

app.mount("/frontend", StaticFiles(directory="frontend"), name="frontend")


@app.get("/")
def serve_root():
    return RedirectResponse(url="/login.html")


@app.get("/login.html")
def serve_login():
    return FileResponse("frontend/login.html")


@app.get("/index.html")
def serve_index():
    return FileResponse("frontend/index.html")


@app.get("/Registro.html")
def serve_registro():
    return FileResponse("frontend/Registro.html")


@app.get("/mapa.html")
def serve_mapa():
    return FileResponse(
        "frontend/mapa.html",
        headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
    )


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@contextmanager
def get_cursor():
    conn = None
    cur = None
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
        )
        cur = conn.cursor(cursor_factory=RealDictCursor)
        yield conn, cur
    finally:
        if cur:
            cur.close()
        if conn:
            conn.close()


def create_access_token(user_id: int, email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(minutes=JWT_EXPIRES_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_current_user(request: Request) -> dict:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="No autenticado")
    token = auth.split(" ", 1)[1].strip()
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")
    return {"id": int(payload["sub"]), "email": payload.get("email")}


def require_auth(user: dict = Depends(get_current_user)) -> dict:
    return user


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)
    confirm_password: str = Field(min_length=MIN_PASSWORD_LENGTH, max_length=128)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if not re.search(r"[A-Z]", v):
            raise ValueError("La contraseña debe incluir al menos una mayúscula")
        if not re.search(r"[a-z]", v):
            raise ValueError("La contraseña debe incluir al menos una minúscula")
        if not re.search(r"\d", v):
            raise ValueError("La contraseña debe incluir al menos un número")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


def _generic_500() -> HTTPException:
    return HTTPException(status_code=500, detail="Error interno del servidor")


@app.post("/api/register", status_code=201)
def register(data: RegisterRequest):
    if data.password != data.confirm_password:
        raise HTTPException(status_code=400, detail="Las contraseñas no coinciden")

    password_hash = pwd_context.hash(data.password)

    try:
        with get_cursor() as (conn, cur):
            cur.execute(
                "INSERT INTO usuarios (email, password_hash) VALUES (%s, %s) RETURNING id, email;",
                (data.email, password_hash),
            )
            user = cur.fetchone()
            conn.commit()
    except errors.UniqueViolation:
        raise HTTPException(status_code=400, detail="El correo ya está registrado")
    except Exception as exc:
        logger.exception("register failed: %s", exc)
        raise _generic_500()

    token = create_access_token(user["id"], user["email"])
    return {
        "message": "Usuario registrado correctamente",
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user["id"], "email": user["email"]},
    }


@app.post("/api/login")
def login(data: LoginRequest):
    try:
        with get_cursor() as (conn, cur):
            cur.execute(
                "SELECT id, email, password_hash FROM usuarios WHERE email = %s;",
                (data.email,),
            )
            user = cur.fetchone()
    except Exception as exc:
        logger.exception("login db error: %s", exc)
        raise _generic_500()

    if user is None or not pwd_context.verify(data.password, user["password_hash"]):
        raise HTTPException(status_code=401, detail="Correo o contraseña incorrectos")

    token = create_access_token(user["id"], user["email"])
    return {
        "message": "Login correcto",
        "access_token": token,
        "token_type": "bearer",
        "user": {"id": user["id"], "email": user["email"]},
    }


@app.get("/api/clima")
def api_clima(limit: int = 500, _user: dict = Depends(require_auth)):
    return {"data": []}


@app.get("/api/consumo")
def api_consumo(
    anio: int | None = None,
    bimestre: int | None = None,
    alcaldia: str | None = None,
    colonia: str | None = None,
    indice_des: str | None = None,
    limit: int = 50,
    offset: int = 0,
    _user: dict = Depends(require_auth),
):
    limit = max(1, min(limit, MAX_LIMIT))
    offset = max(0, offset)
    if bimestre is not None and not 1 <= bimestre <= 6:
        raise HTTPException(status_code=400, detail="bimestre debe estar entre 1 y 6")
    if anio is not None and not 1900 <= anio <= 2100:
        raise HTTPException(status_code=400, detail="anio fuera de rango")

    query = """
        SELECT
            t.anio, t.bimestre, NULL::date AS fecha_referencia, u.alcaldia, u.colonia,
            i.indice_des, f.consumo_total, f.consumo_prom, f.consumo_total_dom,
            f.consumo_prom_dom, f.consumo_total_mixto, f.consumo_total_no_dom
        FROM fact_consumo_agua f
        JOIN dim_tiempo t ON f.id_tiempo = t.id_tiempo
        JOIN dim_ubicacion u ON f.id_ubicacion = u.id_ubicacion
        JOIN dim_indice_des i ON f.id_indice_des = i.id_indice_des
        WHERE 1=1
    """
    params: list = []

    if anio is not None:
        query += " AND t.anio = %s"
        params.append(anio)
    if bimestre is not None:
        query += " AND t.bimestre = %s"
        params.append(bimestre)
    if alcaldia:
        query += " AND u.alcaldia ILIKE %s"
        params.append(f"%{alcaldia}%")
    if colonia:
        query += " AND u.colonia = %s"
        params.append(colonia)
    if indice_des:
        query += " AND i.indice_des = %s"
        params.append(indice_des)

    try:
        with get_cursor() as (conn, cur):
            cur.execute(f"SELECT COUNT(*) AS total FROM ({query}) q", params)
            total = cur.fetchone()["total"]

            query += " LIMIT %s OFFSET %s"
            params.extend([limit, offset])
            cur.execute(query, params)
            rows = cur.fetchall()
    except Exception as exc:
        logger.exception("api_consumo error: %s", exc)
        raise _generic_500()

    return {
        "total": total,
        "limit": limit,
        "offset": offset,
        "data": [
            {
                "anio": r["anio"],
                "bimestre": r["bimestre"],
                "fecha": str(r["fecha_referencia"]) if r["fecha_referencia"] else None,
                "alcaldia": r["alcaldia"],
                "colonia": r["colonia"],
                "indice_des": r["indice_des"],
                "consumo_total": float(r["consumo_total"] or 0),
                "consumo_prom": float(r["consumo_prom"] or 0),
                "consumo_total_dom": float(r["consumo_total_dom"] or 0),
                "consumo_prom_dom": float(r["consumo_prom_dom"] or 0),
                "consumo_total_mixto": float(r["consumo_total_mixto"] or 0),
                "consumo_total_no_dom": float(r["consumo_total_no_dom"] or 0),
            }
            for r in rows
        ],
    }


@app.get("/api/consumo/resumen")
def api_resumen(_user: dict = Depends(require_auth)):
    try:
        with get_cursor() as (conn, cur):
            cur.execute(
                """
                SELECT u.alcaldia, u.colonia,
                       SUM(f.consumo_total) AS total_agua,
                       AVG(f.consumo_prom) AS promedio
                FROM fact_consumo_agua f
                JOIN dim_ubicacion u ON f.id_ubicacion = u.id_ubicacion
                GROUP BY u.alcaldia, u.colonia
                LIMIT %s;
                """,
                (MAX_LIMIT,),
            )
            rows = cur.fetchall()
    except Exception as exc:
        logger.exception("api_resumen error: %s", exc)
        raise _generic_500()

    return [
        {
            "alcaldia": r["alcaldia"],
            "colonia": r["colonia"],
            "total_agua": float(r["total_agua"] or 0),
            "promedio": float(r["promedio"] or 0),
        }
        for r in rows
    ]


@app.get("/api/top-consumo")
def api_top_consumo(limit: int = 10, _user: dict = Depends(require_auth)):
    limit = max(1, min(limit, MAX_LIMIT))
    try:
        with get_cursor() as (conn, cur):
            cur.execute(
                """
                SELECT u.colonia, u.alcaldia, SUM(f.consumo_total) AS total_agua
                FROM fact_consumo_agua f
                JOIN dim_ubicacion u ON f.id_ubicacion = u.id_ubicacion
                GROUP BY u.colonia, u.alcaldia
                ORDER BY total_agua DESC
                LIMIT %s;
                """,
                (limit,),
            )
            rows = cur.fetchall()
    except Exception as exc:
        logger.exception("api_top_consumo error: %s", exc)
        raise _generic_500()

    return [
        {
            "colonia": r["colonia"],
            "alcaldia": r["alcaldia"],
            "total_agua": float(r["total_agua"] or 0),
        }
        for r in rows
    ]


@app.get("/api/correlacion")
def api_correlacion(
    anio: int | None = None,
    _user: dict = Depends(require_auth),
):
    """Correlación por bimestre entre consumo de agua y clima (temperatura, lluvia, días extremos)."""
    if anio is not None and not 1900 <= anio <= 2100:
        raise HTTPException(status_code=400, detail="anio fuera de rango")

    where_anio = ""
    params: list = []
    if anio is not None:
        where_anio = " WHERE t.anio = %s"
        params = [anio, anio]

    query = f"""
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
            {where_anio}
            GROUP BY t.anio, t.bimestre
        ),
        AguaBimestral AS (
            SELECT
                t.anio,
                t.bimestre,
                SUM(fca.consumo_total) AS total_agua
            FROM fact_consumo_agua fca
            JOIN dim_tiempo t ON fca.id_tiempo = t.id_tiempo
            {where_anio}
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
    """

    try:
        with get_cursor() as (conn, cur):
            cur.execute(query, params)
            rows = cur.fetchall()
    except Exception as exc:
        logger.exception("api_correlacion error: %s", exc)
        raise _generic_500()

    return [
        {
            "anio": r["anio"],
            "bimestre": r["bimestre"],
            "total_agua": float(r["total_agua"] or 0),
            "temp_promedio": float(r["temp_promedio"] or 0),
            "dias_ola_calor": int(r["dias_ola_calor"] or 0),
            "dias_frio": int(r["dias_frio"] or 0),
            "total_lluvia": float(r["total_lluvia"] or 0),
        }
        for r in rows
    ]


@app.get("/api/anios")
def api_anios(_user: dict = Depends(require_auth)):
    try:
        with get_cursor() as (conn, cur):
            cur.execute("SELECT DISTINCT anio FROM dim_tiempo WHERE anio IS NOT NULL ORDER BY anio;")
            rows = cur.fetchall()
    except Exception as exc:
        logger.exception("api_anios error: %s", exc)
        raise _generic_500()
    return [r["anio"] for r in rows]


@app.get("/api/bimestres")
def api_bimestres(_user: dict = Depends(require_auth)):
    try:
        with get_cursor() as (conn, cur):
            cur.execute("SELECT DISTINCT bimestre FROM dim_tiempo WHERE bimestre IS NOT NULL ORDER BY bimestre;")
            rows = cur.fetchall()
    except Exception as exc:
        logger.exception("api_bimestres error: %s", exc)
        raise _generic_500()
    return [r["bimestre"] for r in rows]


@app.get("/api/alcaldias")
def api_alcaldias(_user: dict = Depends(require_auth)):
    try:
        with get_cursor() as (conn, cur):
            cur.execute("SELECT DISTINCT alcaldia FROM dim_ubicacion WHERE alcaldia IS NOT NULL ORDER BY alcaldia;")
            rows = cur.fetchall()
    except Exception as exc:
        logger.exception("api_alcaldias error: %s", exc)
        raise _generic_500()
    return [r["alcaldia"] for r in rows]


@app.get("/api/indices")
def api_indices(_user: dict = Depends(require_auth)):
    try:
        with get_cursor() as (conn, cur):
            cur.execute(
                "SELECT id_indice_des, indice_des FROM dim_indice_des WHERE indice_des IS NOT NULL ORDER BY indice_des;"
            )
            rows = cur.fetchall()
    except Exception as exc:
        logger.exception("api_indices error: %s", exc)
        raise _generic_500()
    return [{"id_indice_des": r["id_indice_des"], "indice_des": r["indice_des"]} for r in rows]


@app.get("/api/colonias")
def api_colonias(alcaldia: str | None = None, _user: dict = Depends(require_auth)):
    try:
        with get_cursor() as (conn, cur):
            if alcaldia:
                cur.execute(
                    "SELECT DISTINCT colonia FROM dim_ubicacion WHERE alcaldia ILIKE %s AND colonia IS NOT NULL ORDER BY colonia;",
                    (f"%{alcaldia}%",),
                )
            else:
                cur.execute(
                    "SELECT DISTINCT colonia FROM dim_ubicacion WHERE colonia IS NOT NULL ORDER BY colonia;"
                )
            rows = cur.fetchall()
    except Exception as exc:
        logger.exception("api_colonias error: %s", exc)
        raise _generic_500()
    return [r["colonia"] for r in rows]


@app.get("/api/ubicaciones/alcaldias")
def api_ubicaciones_alcaldias(
    anio: int | None = None,
    bimestre: int | None = None,
    alcaldia: str | None = None,
    _user: dict = Depends(require_auth),
):
    """Una entrada por alcaldía con coordenadas (centroide de sus colonias) y consumo agregado."""
    if anio is not None and not 1900 <= anio <= 2100:
        raise HTTPException(status_code=400, detail="anio fuera de rango")
    if bimestre is not None and not 1 <= bimestre <= 6:
        raise HTTPException(status_code=400, detail="bimestre debe estar entre 1 y 6")

    where = " WHERE 1=1"
    params: list = []
    if anio is not None:
        where += " AND t.anio = %s"
        params.append(anio)
    if bimestre is not None:
        where += " AND t.bimestre = %s"
        params.append(bimestre)
    if alcaldia:
        where += " AND u.alcaldia ILIKE %s"
        params.append(f"%{alcaldia}%")

    query = f"""
        SELECT
            u.alcaldia,
            AVG(u.latitud)::float  AS lat,
            AVG(u.longitud)::float AS lon,
            SUM(f.consumo_total)         AS consumo_total,
            AVG(f.consumo_prom)          AS consumo_prom,
            SUM(f.consumo_total_dom)     AS consumo_total_dom,
            AVG(f.consumo_prom_dom)      AS consumo_prom_dom,
            SUM(f.consumo_total_mixto)   AS consumo_total_mixto,
            AVG(f.consumo_prom_mixto)    AS consumo_prom_mixto,
            SUM(f.consumo_total_no_dom)  AS consumo_total_no_dom,
            AVG(f.consumo_prom_no_dom)   AS consumo_prom_no_dom,
            COUNT(DISTINCT u.id_ubicacion) AS num_colonias,
            COUNT(*)                     AS num_registros
        FROM fact_consumo_agua f
        JOIN dim_tiempo t     ON f.id_tiempo = t.id_tiempo
        JOIN dim_ubicacion u  ON f.id_ubicacion = u.id_ubicacion
        {where}
          AND u.latitud  IS NOT NULL
          AND u.longitud IS NOT NULL
        GROUP BY u.alcaldia
        ORDER BY consumo_total DESC NULLS LAST
        LIMIT %s;
    """
    params.append(MAX_LIMIT)
    try:
        with get_cursor() as (conn, cur):
            cur.execute(query, params)
            rows = cur.fetchall()
    except Exception as exc:
        logger.exception("api_ubicaciones_alcaldias error: %s", exc)
        raise _generic_500()

    return [
        {
            "alcaldia": r["alcaldia"],
            "lat": r["lat"],
            "lon": r["lon"],
            "consumo_total": float(r["consumo_total"] or 0),
            "consumo_prom": float(r["consumo_prom"] or 0),
            "consumo_total_dom": float(r["consumo_total_dom"] or 0),
            "consumo_prom_dom": float(r["consumo_prom_dom"] or 0),
            "consumo_total_mixto": float(r["consumo_total_mixto"] or 0),
            "consumo_prom_mixto": float(r["consumo_prom_mixto"] or 0),
            "consumo_total_no_dom": float(r["consumo_total_no_dom"] or 0),
            "consumo_prom_no_dom": float(r["consumo_prom_no_dom"] or 0),
            "num_colonias": r["num_colonias"],
            "num_registros": r["num_registros"],
        }
        for r in rows
    ]


@app.get("/api/ubicaciones/colonias")
def api_ubicaciones_colonias(
    anio: int | None = None,
    bimestre: int | None = None,
    alcaldia: str | None = None,
    limit: int = 500,
    _user: dict = Depends(require_auth),
):
    """Una entrada por colonia con coordenadas y consumo agregado."""
    limit = max(1, min(limit, MAX_LIMIT))
    if anio is not None and not 1900 <= anio <= 2100:
        raise HTTPException(status_code=400, detail="anio fuera de rango")
    if bimestre is not None and not 1 <= bimestre <= 6:
        raise HTTPException(status_code=400, detail="bimestre debe estar entre 1 y 6")

    where = " WHERE 1=1"
    params: list = []
    if anio is not None:
        where += " AND t.anio = %s"
        params.append(anio)
    if bimestre is not None:
        where += " AND t.bimestre = %s"
        params.append(bimestre)
    if alcaldia:
        where += " AND u.alcaldia ILIKE %s"
        params.append(f"%{alcaldia}%")

    query = f"""
        SELECT
            u.alcaldia,
            u.colonia,
            u.latitud::float AS lat,
            u.longitud::float AS lon,
            SUM(f.consumo_total) AS consumo_total,
            AVG(f.consumo_prom)  AS consumo_prom
        FROM fact_consumo_agua f
        JOIN dim_tiempo t     ON f.id_tiempo = t.id_tiempo
        JOIN dim_ubicacion u  ON f.id_ubicacion = u.id_ubicacion
        {where}
          AND u.latitud  IS NOT NULL
          AND u.longitud IS NOT NULL
        GROUP BY u.alcaldia, u.colonia, u.latitud, u.longitud
        ORDER BY consumo_total DESC NULLS LAST
        LIMIT %s;
    """
    params.append(limit)
    try:
        with get_cursor() as (conn, cur):
            cur.execute(query, params)
            rows = cur.fetchall()
    except Exception as exc:
        logger.exception("api_ubicaciones_colonias error: %s", exc)
        raise _generic_500()

    return [
        {
            "alcaldia": r["alcaldia"],
            "colonia": r["colonia"],
            "lat": r["lat"],
            "lon": r["lon"],
            "consumo_total": float(r["consumo_total"] or 0),
            "consumo_prom": float(r["consumo_prom"] or 0),
        }
        for r in rows
    ]


@app.get("/api/health")
def health(_user: dict = Depends(require_auth)):
    return {"status": "ok"}


@app.get("/api/consumo/alcaldia")
def api_consumo_alcaldia(
    alcaldia: str,
    anio: int | None = None,
    bimestre: int | None = None,
    _user: dict = Depends(require_auth),
):
    """Consulta a la BD el consumo de agua agregado de UNA alcaldía.

    Pensado para mostrarse en el popup del mapa al hacer click sobre una alcaldía.
    """
    if not alcaldia or not alcaldia.strip():
        raise HTTPException(status_code=400, detail="alcaldia es requerida")
    if anio is not None and not 1900 <= anio <= 2100:
        raise HTTPException(status_code=400, detail="anio fuera de rango")
    if bimestre is not None and not 1 <= bimestre <= 6:
        raise HTTPException(status_code=400, detail="bimestre debe estar entre 1 y 6")

    where = " WHERE u.alcaldia ILIKE %s"
    params: list = [alcaldia.strip()]
    if anio is not None:
        where += " AND t.anio = %s"
        params.append(anio)
    if bimestre is not None:
        where += " AND t.bimestre = %s"
        params.append(bimestre)

    query = f"""
        SELECT
            u.alcaldia,
            SUM(f.consumo_total)         AS consumo_total,
            AVG(f.consumo_prom)          AS consumo_prom,
            SUM(f.consumo_total_dom)     AS consumo_total_dom,
            AVG(f.consumo_prom_dom)      AS consumo_prom_dom,
            SUM(f.consumo_total_mixto)   AS consumo_total_mixto,
            AVG(f.consumo_prom_mixto)    AS consumo_prom_mixto,
            SUM(f.consumo_total_no_dom)  AS consumo_total_no_dom,
            AVG(f.consumo_prom_no_dom)   AS consumo_prom_no_dom,
            COUNT(DISTINCT u.id_ubicacion) AS num_colonias,
            COUNT(*)                     AS num_registros,
            MIN(t.anio)                  AS anio_min,
            MAX(t.anio)                  AS anio_max
        FROM fact_consumo_agua f
        JOIN dim_tiempo t     ON f.id_tiempo = t.id_tiempo
        JOIN dim_ubicacion u  ON f.id_ubicacion = u.id_ubicacion
        {where}
        GROUP BY u.alcaldia
        LIMIT 1;
    """
    try:
        with get_cursor() as (conn, cur):
            cur.execute(query, params)
            row = cur.fetchone()
    except Exception as exc:
        logger.exception("api_consumo_alcaldia error: %s", exc)
        raise _generic_500()

    if row is None:
        return {
            "alcaldia": alcaldia,
            "consumo_total": 0.0,
            "consumo_prom": 0.0,
            "consumo_total_dom": 0.0,
            "consumo_prom_dom": 0.0,
            "consumo_total_mixto": 0.0,
            "consumo_prom_mixto": 0.0,
            "consumo_total_no_dom": 0.0,
            "consumo_prom_no_dom": 0.0,
            "num_colonias": 0,
            "num_registros": 0,
            "anio_min": None,
            "anio_max": None,
            "sin_datos": True,
        }

    return {
        "alcaldia": row["alcaldia"],
        "consumo_total": float(row["consumo_total"] or 0),
        "consumo_prom": float(row["consumo_prom"] or 0),
        "consumo_total_dom": float(row["consumo_total_dom"] or 0),
        "consumo_prom_dom": float(row["consumo_prom_dom"] or 0),
        "consumo_total_mixto": float(row["consumo_total_mixto"] or 0),
        "consumo_prom_mixto": float(row["consumo_prom_mixto"] or 0),
        "consumo_total_no_dom": float(row["consumo_total_no_dom"] or 0),
        "consumo_prom_no_dom": float(row["consumo_prom_no_dom"] or 0),
        "num_colonias": row["num_colonias"],
        "num_registros": row["num_registros"],
        "anio_min": row["anio_min"],
        "anio_max": row["anio_max"],
        "sin_datos": False,
    }


@app.get("/api/geojson/alcaldias")
def api_geojson_alcaldias(_user: dict = Depends(require_auth)):
    """Sirve el GeoJSON de las 16 alcaldías de la CDMX.

    Prioridad:
    1) Archivo local en ``data/alcaldias_cdmx.geojson`` (recomendado para producción).
    2) Descarga desde la URL pública y la guarda en memoria caché.
    """
    global _geojson_cache

    geojson_path = os.path.join(os.path.dirname(__file__), "data", "alcaldias_cdmx.geojson")
    if os.path.exists(geojson_path):
        try:
            with open(geojson_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as exc:
            logger.exception("Error leyendo GeoJSON local: %s", exc)

    if _geojson_cache is not None:
        return _geojson_cache

    try:
        req = urllib.request.Request(ALCALDIAS_GEOJSON_URL, headers={"User-Agent": "dw-cdmx/1.0"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        _geojson_cache = data
        return data
    except Exception as exc:
        logger.exception("api_geojson_alcaldias error: %s", exc)
        raise HTTPException(
            status_code=503,
            detail=(
                "No se pudo cargar el GeoJSON de alcaldías. "
                f"Coloque el archivo en data/alcaldias_cdmx.geojson o verifique la conexión. "
                f"({exc})"
            ),
        )
