"""Genera un JSON estatico para la version de GitHub Pages (sin backend).

Produce un unico archivo ``web/consumo.json`` con:
  - catalogos: anios, bimestres, alcaldias, indices
  - colonias_por_alcaldia: nombres de colonias por alcaldia
  - consumo_colonia: registros a nivel colonia (alcaldia, colonia, anio, bimestre, ...)
  - correlacion: datos climaticos por bimestre correlacionados con consumo

Las alcaldias y el orden reflejan las 16 demarcaciones oficiales de la CDMX.
Los numeros son simulaciones realistas (no son datos reales) y sirven solo
para que la pagina estatica tenga contenido creible.
"""
import json
import random
from pathlib import Path

random.seed(42)

ALCALDIAS = [
    "Álvaro Obregón",
    "Azcapotzalco",
    "Benito Juárez",
    "Coyoacán",
    "Cuajimalpa de Morelos",
    "Cuauhtémoc",
    "Gustavo A. Madero",
    "Iztacalco",
    "Iztapalapa",
    "La Magdalena Contreras",
    "Miguel Hidalgo",
    "Milpa Alta",
    "Tlalpan",
    "Venustiano Carranza",
    "Tláhuac",
    "Xochimilco",
]

ANIOS = [2019, 2020, 2021, 2022, 2023]
BIMESTRES = [1, 2, 3, 4, 5, 6]
INDICES = ["Alto", "Medio", "Bajo"]

PESO_BASE = {
    "Iztapalapa": 5.2,
    "Gustavo A. Madero": 4.4,
    "Álvaro Obregón": 3.5,
    "Coyoacán": 2.9,
    "Tlalpan": 2.4,
    "Azcapotzalco": 2.1,
    "Venustiano Carranza": 2.0,
    "Cuauhtémoc": 1.9,
    "Miguel Hidalgo": 1.8,
    "Benito Juárez": 1.7,
    "Xochimilco": 1.5,
    "Tláhuac": 1.4,
    "Iztacalco": 1.3,
    "Cuajimalpa de Morelos": 1.0,
    "La Magdalena Contreras": 0.9,
    "Milpa Alta": 0.8,
}

INDICES_PESO = {"Alto": 0.18, "Medio": 0.42, "Bajo": 0.40}
CENTRALES = {"Cuauhtémoc", "Benito Juárez", "Miguel Hidalgo"}

NOMBRES_COLONIA = [
    "Centro", "San Ángel", "San Pedro", "Santa María la Ribera",
    "Santa María la Ribera Sur", "Roma Norte", "Roma Sur", "Condesa",
    "Hipódromo", "Hipódromo Condesa", "Del Valle", "Del Valle Centro",
    "Del Valle Norte", "Del Valle Sur", "Narvarte", "Narvarte Poniente",
    "Narvarte Oriente", "Portales", "Portales Norte", "Portales Sur",
    "Villa de Cortés", "Xoco", "General Anaya", "Country Club",
    "Pedregal de Santa Úrsula", "Pedregal de San Francisco", "Copilco",
    "Copilco Universidad", "Pedregal de Santo Domingo", "Ajusco",
    "Ciudad Universitaria", "Los Reyes", "San Diego Churubusco",
    "El Rosario", "San José del Olivar", "Lomas de San Ángel Inn",
    "Lomas de las Águilas", "Las Américas", "Sears Roebuck", "Reacomodo",
    "El Cuernito", "Polanco", "Polanco V Sección", "Polanco I Sección",
    "Anzures", "Verónica Anzures", "Mariano Escobedo", "Lomas de Chapultepec",
    "Bosques de las Lomas", "Lomas Altas", "Tacubaya", "Ampliación Tacubaya",
    "Observatorio", "Daniel Garza", "Las Américas", "San Rafael",
    "Tabacalera", "Juárez", "Cuauhtémoc", "Doctores", "Obrera",
    "Buenos Aires", "Algarín", "Paulino Navarro", "Transito",
    "Morelos", "Peralvillo", "Valle Gómez", "Ex-Hipódromo de Peralvillo",
    "Industrial", "Azcapotzalco", "Clavería", "San Álvaro", "Nueva Santa María",
    "San Juan Tlihuaca", "Arenal", "Arenal Puerto Aéreo", "Candelaria",
    "Morelos Puerto Aéreo", "Revolución", "Ampliación 7 de Julio",
    "Leyes de Reforma", "Tezozómoc", "El Rosario", "San Martín Xochinahuac",
    "Santa María Malinalco", "Pasteros", "Santo Domingo", "San Pablo",
    "San Marcos", "Tláhuac Centro", "La Habana", "Miguel Hidalgo",
    "San José", "Santiago", "San Francisco Tlaltenco", "Villa Centroamericana",
    "Del Mar", "La Turba", "Quiahuatla", "San Andrés", "Xochimilco Centro",
    "San Cristóbal", "La Noria", "Madero", "Guadalupe", "Barrio San Antonio",
    "Barrio San Marcos", "Santa Cruz Acalpixca", "Santiago Tepalcatlalpan",
    "San Mateo Xalpa", "San Andrés Ahuayucan", "San Lucas Xochimanca",
    "Bosques de las Lomas", "Lomas de Vista Hermosa", "Lomas de Tecamachalco",
    "Reforma Social", "Verónica Anzures", "Verónica", "Pensil",
    "Popotla", "Tacuba", "Nextitla", "Anáhuac", "Legaria", "Lago Norte",
    "Lago Sur", "Granada", "Ampliación Granada", "Ampliación Torre Blanca",
    "Torre Blanca", "Iztapalapa Centro", "San Lucas", "Santa Bárbara",
    "San José Aculco", "San Andrés Tetepilco", "Mexicaltzingo", "Escuadrón 201",
]

VARIACION_BIMESTRAL = {1: 0.88, 2: 0.96, 3: 1.08, 4: 1.14, 5: 1.06, 6: 0.92}
TENDENCIA_ANUAL = {2019: 1.00, 2020: 0.97, 2021: 1.02, 2022: 1.05, 2023: 1.08}

CLIMA_BIMESTRAL = {
    1: {"temp": 13.5, "lluvia": 35, "ola_calor": 0, "frio": 55},
    2: {"temp": 17.0, "lluvia": 60, "ola_calor": 4, "frio": 22},
    3: {"temp": 19.5, "lluvia": 130, "ola_calor": 14, "frio": 4},
    4: {"temp": 18.8, "lluvia": 220, "ola_calor": 8, "frio": 2},
    5: {"temp": 16.0, "lluvia": 95, "ola_calor": 2, "frio": 18},
    6: {"temp": 12.0, "lluvia": 25, "ola_calor": 0, "frio": 62},
}

FECHA_INICIO_BIM = {1: "01-01", 2: "01-03", 3: "01-05", 4: "01-07", 5: "01-09", 6: "01-11"}


def gen_colonias_por_alcaldia():
    rng = random.Random(123)
    out = {}
    pool = list(NOMBRES_COLONIA)
    rng.shuffle(pool)
    cursor = 0
    for alc in ALCALDIAS:
        n = rng.randint(15, 35)
        cols = []
        for _ in range(n):
            cols.append(pool[cursor % len(pool)])
            cursor += 1
        cols = list(dict.fromkeys(cols))
        out[alc] = sorted(cols)
    return out


def gen_consumo_colonia():
    rng = random.Random(7)
    alcaldia_cols = gen_colonias_por_alcaldia()
    filas = []
    for anio in ANIOS:
        for bim in BIMESTRES:
            for alc, colonias in alcaldia_cols.items():
                peso = PESO_BASE[alc]
                factor_periodo = VARIACION_BIMESTRAL[bim] * TENDENCIA_ANUAL[anio]
                consumo_alcaldia_periodo = 1_350_000 * peso * factor_periodo
                partes = [rng.uniform(0.4, 1.8) for _ in colonias]
                s = sum(partes) or 1
                fecha = f"{anio}-{FECHA_INICIO_BIM[bim]}"
                for col, p in zip(colonias, partes):
                    total_colonia = consumo_alcaldia_periodo * (p / s)
                    dom = total_colonia * rng.uniform(0.6, 0.78)
                    no_dom = total_colonia * rng.uniform(0.10, 0.22)
                    mixto = max(total_colonia - dom - no_dom, 0)
                    prom = total_colonia / rng.uniform(280, 520)
                    indice = "Alto" if rng.random() < 0.25 else ("Medio" if rng.random() < 0.55 else "Bajo")
                    filas.append({
                        "anio": anio,
                        "bimestre": bim,
                        "fecha": fecha,
                        "alcaldia": alc,
                        "colonia": col,
                        "indice_des": indice,
                        "consumo_total": round(total_colonia, 2),
                        "consumo_prom": round(prom, 2),
                        "consumo_total_dom": round(dom, 2),
                        "consumo_prom_dom": round(dom / rng.uniform(220, 420), 2),
                        "consumo_total_mixto": round(mixto, 2),
                        "consumo_prom_mixto": round(mixto / rng.uniform(40, 90), 2) if mixto else 0,
                        "consumo_total_no_dom": round(no_dom, 2),
                        "consumo_prom_no_dom": round(no_dom / rng.uniform(40, 90), 2) if no_dom else 0,
                    })
    return filas, list(alcaldia_cols.keys())


def gen_correlacion():
    rng = random.Random(99)
    out = []
    for anio in ANIOS:
        for bim in BIMESTRES:
            base = CLIMA_BIMESTRAL[bim]
            temp = base["temp"] + rng.uniform(-1.0, 1.0)
            lluvia = max(base["lluvia"] + rng.uniform(-20, 20), 0)
            ola_calor = max(int(round(base["ola_calor"] + rng.uniform(-2, 2))), 0)
            frio = max(int(round(base["frio"] + rng.uniform(-5, 5))), 0)
            total_agua = sum(
                f["consumo_total"]
                for f in DATASET["consumo_colonia"]
                if f["anio"] == anio and f["bimestre"] == bim
            )
            out.append({
                "anio": anio,
                "bimestre": bim,
                "total_agua": round(total_agua, 2),
                "temp_promedio": round(temp, 2),
                "dias_ola_calor": ola_calor,
                "dias_frio": frio,
                "total_lluvia": round(lluvia, 2),
            })
    return out


DATASET = {}

def main():
    DATASET["consumo_colonia"], _ = gen_consumo_colonia()
    DATASET["consumo_alcaldia"] = []  # se calcula en cliente (mapa.html) a partir de consumo_colonia

    alcaldia_cols = {}
    for f in DATASET["consumo_colonia"]:
        alcaldia_cols.setdefault(f["alcaldia"], set()).add(f["colonia"])
    alcaldia_cols = {k: sorted(v) for k, v in alcaldia_cols.items()}

    payload = {
        "anios": ANIOS,
        "bimestres": BIMESTRES,
        "alcaldias": ALCALDIAS,
        "indices": INDICES,
        "colonias_por_alcaldia": alcaldia_cols,
        "consumo_colonia": DATASET["consumo_colonia"],
        "correlacion": gen_correlacion(),
        "generado_en": "estático (sin backend)",
        "nota": "Datos simulados para uso en GitHub Pages.",
    }

    out = Path("web/consumo.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    size_kb = out.stat().st_size / 1024
    print(f"OK -> {out}")
    print(f"  consumo_colonia: {len(payload['consumo_colonia'])} filas")
    print(f"  correlacion: {len(payload['correlacion'])} filas")
    print(f"  alcaldias: {len(payload['alcaldias'])}")
    print(f"  colonias: {sum(len(v) for v in payload['colonias_por_alcaldia'].values())}")
    print(f"  tamaño: {size_kb:.1f} KB ({size_kb/1024:.2f} MB)")


if __name__ == "__main__":
    main()
