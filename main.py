from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from passlib.context import CryptContext
import psycopg2
from psycopg2 import errors

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    confirm_password: str


def get_connection():
    return psycopg2.connect(
        host="localhost",
        port=5432,
        database="dw_cdmx",
        user="emilio",
        password="emilio123"
    )


@app.post("/register")
def register(data: RegisterRequest):
    if data.password != data.confirm_password:
        raise HTTPException(status_code=400, detail="Las contraseñas no coinciden")

    password_hash = pwd_context.hash(data.password)

    conn = None
    cursor = None

    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO usuarios (email, password_hash)
            VALUES (%s, %s)
            RETURNING id, email;
            """,
            (data.email, password_hash)
        )

        user = cursor.fetchone()
        conn.commit()

        return {
            "message": "Usuario registrado correctamente",
            "user": {
                "id": user[0],
                "email": user[1]
            }
        }

    except errors.UniqueViolation:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=400, detail="El correo ya está registrado")

    except Exception as e:
        if conn:
            conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error interno: {str(e)}")

    finally:
        if cursor:
            cursor.close()
        if conn:
            conn.close()

class LoginRequest(BaseModel):
    email: EmailStr
    password: str


@app.post("/login")
def login(data: LoginRequest):
    try:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT id, email, password_hash
            FROM usuarios
            WHERE email = %s;
            """,
            (data.email,)
        )

        user = cursor.fetchone()

        cursor.close()
        conn.close()

        if user is None:
            raise HTTPException(
                status_code=401,
                detail="Correo o contraseña incorrectos"
            )

        user_id = user[0]
        email = user[1]
        password_hash = user[2]

        if not pwd_context.verify(data.password, password_hash):
            raise HTTPException(
                status_code=401,
                detail="Correo o contraseña incorrectos"
            )

        return {
            "message": "Login correcto",
            "user": {
                "id": user_id,
                "email": email
            }
        }

    except HTTPException:
        raise

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error interno: {str(e)}"
        )

@app.get("/api/consumo")
def api_consumo(
    anio: int = None,
    bimestre: int = None,
    alcaldia: str = None,
    colonia: str = None,
    indice_des: str = None,
    limit: int = 50,
    offset: int = 0
):
    conn = get_connection()
    cur = conn.cursor()

    query = """
        SELECT
            t.anio,
            t.bimestre,
            NULL AS fecha_referencia,
            u.alcaldia,
            u.colonia,
            i.indice_des,
            f.consumo_total,
            f.consumo_prom,
            f.consumo_total_dom,
            f.consumo_prom_dom,
            f.consumo_total_mixto,
            f.consumo_total_no_dom
        FROM fact_consumo_agua f
        JOIN dim_tiempo t ON f.id_tiempo = t.id_tiempo
        JOIN dim_ubicacion u ON f.id_ubicacion = u.id_ubicacion
        JOIN dim_indice_des i ON f.id_indice_des = i.id_indice_des
        WHERE 1=1
    """

    params = []

    if anio:
        query += " AND t.anio = %s"
        params.append(anio)

    if bimestre:
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

    count_query = f"SELECT COUNT(*) FROM ({query}) q"

    cur.execute(count_query, params)
    total = cur.fetchone()[0]

    query += " LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    cur.execute(query, params)
    rows = cur.fetchall()

    cur.close()
    conn.close()

    return {
        "total": total,
        "data": [
            {
                "anio": r[0],
                "bimestre": r[1],
                "fecha": str(r[2]) if r[2] else None,
                "alcaldia": r[3],
                "colonia": r[4],
                "indice_des": r[5],
                "consumo_total": float(r[6]) if r[6] else 0,
                "consumo_prom": float(r[7]) if r[7] else 0,
                "consumo_total_dom": float(r[8]) if r[8] else 0,
                "consumo_prom_dom": float(r[9]) if r[9] else 0,
                "consumo_total_mixto": float(r[10]) if r[10] else 0,
                "consumo_total_no_dom": float(r[11]) if r[11] else 0,
            }
            for r in rows
        ]
    }


@app.get("/api/consumo/resumen")
def api_resumen():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            u.alcaldia,
            u.colonia,
            SUM(f.consumo_total) as total_agua,
            AVG(f.consumo_prom) as promedio
        FROM fact_consumo_agua f
        JOIN dim_ubicacion u
            ON f.id_ubicacion = u.id_ubicacion
        GROUP BY u.alcaldia, u.colonia
        LIMIT 500;
    """)

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [
        {
            "alcaldia": r[0],
            "colonia": r[1],
            "total_agua": float(r[2]) if r[2] else 0,
            "promedio": float(r[3]) if r[3] else 0,
        }
        for r in rows
    ]


@app.get("/api/top-consumo")
def api_top_consumo(limit: int = 10):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT
            u.colonia,
            u.alcaldia,
            SUM(f.consumo_total) as total_agua
        FROM fact_consumo_agua f
        JOIN dim_ubicacion u
            ON f.id_ubicacion = u.id_ubicacion
        GROUP BY u.colonia, u.alcaldia
        ORDER BY total_agua DESC
        LIMIT %s;
    """, (limit,))

    rows = cur.fetchall()

    cur.close()
    conn.close()

    return [
        {
            "colonia": r[0],
            "alcaldia": r[1],
            "total_agua": float(r[2]) if r[2] else 0,
        }
        for r in rows
    ]

@app.get("/api/correlacion")
def api_correlacion():
    return []

@app.get("/api/anios")
def api_anios():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT anio
        FROM dim_tiempo
        WHERE anio IS NOT NULL
        ORDER BY anio;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]


@app.get("/api/bimestres")
def api_bimestres():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT bimestre
        FROM dim_tiempo
        WHERE bimestre IS NOT NULL
        ORDER BY bimestre;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]


@app.get("/api/alcaldias")
def api_alcaldias():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT DISTINCT alcaldia
        FROM dim_ubicacion
        WHERE alcaldia IS NOT NULL
        ORDER BY alcaldia;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [r[0] for r in rows]


@app.get("/api/indices")
def api_indices():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id_indice_des, indice_des
        FROM dim_indice_des
        WHERE indice_des IS NOT NULL
        ORDER BY indice_des;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return [
        {
            "id_indice_des": r[0],
            "indice_des": r[1]
        }
        for r in rows
    ]


@app.get("/api/colonias")
def api_colonias(alcaldia: str = None):
    conn = get_connection()
    cur = conn.cursor()

    if alcaldia:
        cur.execute("""
            SELECT DISTINCT colonia
            FROM dim_ubicacion
            WHERE alcaldia ILIKE %s
              AND colonia IS NOT NULL
            ORDER BY colonia;
        """, (f"%{alcaldia}%",))
    else:
        cur.execute("""
            SELECT DISTINCT colonia
            FROM dim_ubicacion
            WHERE colonia IS NOT NULL
            ORDER BY colonia;
        """)

    rows = cur.fetchall()
    cur.close()
    conn.close()

    return [r[0] for r in rows]