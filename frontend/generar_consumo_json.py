"""Genera un JSON estatico con datos simulados de consumo de agua por
alcaldia, anio (2019-2023) y bimestre (1-6), basado en perfiles realistas
de la CDMX (Iztapalapa la de mayor consumo, Cuajimalpa/Magdalena las menores).

Se usa unicamente para la version sin backend del mapa.html.
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

VARIACION_BIMESTRAL = {1: 0.88, 2: 0.96, 3: 1.08, 4: 1.14, 5: 1.06, 6: 0.92}
TENDENCIA_ANUAL = {2019: 1.00, 2020: 0.97, 2021: 1.02, 2022: 1.05, 2023: 1.08}

BASE_CONSUMO_TOTAL = 1_350_000


def fmt_num(v):
    return float(round(v, 2))


def build_row(alcaldia, anio, bimestre):
    peso = PESO_BASE[alcaldia]
    consumo_total = (
        BASE_CONSUMO_TOTAL
        * peso
        * VARIACION_BIMESTRAL[bimestre]
        * TENDENCIA_ANUAL[anio]
        * random.uniform(0.97, 1.03)
    )
    consumo_total_dom = consumo_total * random.uniform(0.62, 0.72)
    consumo_total_no_dom = consumo_total * random.uniform(0.15, 0.22)
    consumo_total_mixto = max(
        consumo_total - consumo_total_dom - consumo_total_no_dom, 0
    )
    consumo_prom = consumo_total / random.uniform(450, 700)
    consumo_prom_dom = consumo_total_dom / random.uniform(400, 650)
    consumo_prom_mixto = consumo_total_mixto / random.uniform(120, 200) if consumo_total_mixto else 0
    consumo_prom_no_dom = consumo_total_no_dom / random.uniform(80, 150) if consumo_total_no_dom else 0
    num_colonias = random.randint(int(peso * 20), int(peso * 45))
    num_registros = num_colonias * random.randint(20, 60)

    return {
        "anio": anio,
        "bimestre": bimestre,
        "alcaldia": alcaldia,
        "consumo_total": fmt_num(consumo_total),
        "consumo_prom": fmt_num(consumo_prom),
        "consumo_total_dom": fmt_num(consumo_total_dom),
        "consumo_prom_dom": fmt_num(consumo_prom_dom),
        "consumo_total_mixto": fmt_num(consumo_total_mixto),
        "consumo_prom_mixto": fmt_num(consumo_prom_mixto),
        "consumo_total_no_dom": fmt_num(consumo_total_no_dom),
        "consumo_prom_no_dom": fmt_num(consumo_prom_no_dom),
        "num_colonias": num_colonias,
        "num_registros": num_registros,
        "anio_min": anio,
        "anio_max": anio,
        "sin_datos": False,
    }


def main():
    filas = []
    for anio in ANIOS:
        for bim in BIMESTRES:
            for alc in ALCALDIAS:
                filas.append(build_row(alc, anio, bim))

    payload = {
        "anios": ANIOS,
        "bimestres": BIMESTRES,
        "alcaldias": ALCALDIAS,
        "generado_en": "estatico (sin backend)",
        "nota": "Datos simulados para la version estatica del mapa.",
        "filas": filas,
    }

    out = Path("frontend/consumo.json")
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"OK -> {out} ({len(filas)} filas, {out.stat().st_size/1024:.1f} KB)")


if __name__ == "__main__":
    main()
