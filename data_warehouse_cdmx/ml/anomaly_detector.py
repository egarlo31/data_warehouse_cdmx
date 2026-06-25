import os
import sys
import numpy as np
import pandas as pd
import psycopg2
from psycopg2.extras import execute_values
from dotenv import load_dotenv
from sklearn.ensemble import IsolationForest

# Cargar variables de entorno
# El script se ejecuta desde la raíz o dentro de data_warehouse_cdmx
base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
load_dotenv(os.path.join(base_dir, ".env"))

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "5435"))
DB_NAME = os.getenv("DB_NAME", "dw_cdmx")
DB_USER = os.getenv("DB_USER", "emilio")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

def get_connection():
    return psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD
    )

def setup_alertas_table(cur):
    print("Configurando la tabla 'alertas_consumo'...")
    cur.execute("""
        CREATE TABLE IF NOT EXISTS alertas_consumo (
            id_alerta SERIAL PRIMARY KEY,
            id_fact INT REFERENCES fact_consumo_agua(id_fact) ON DELETE CASCADE,
            alcaldia VARCHAR(255),
            colonia VARCHAR(255),
            anio INT,
            bimestre INT,
            consumo_total NUMERIC,
            consumo_esperado NUMERIC,
            desviacion_porcentaje NUMERIC,
            metodo VARCHAR(50),
            score NUMERIC,
            es_anomalo BOOLEAN,
            fecha_deteccion TIMESTAMP DEFAULT NOW()
        );
        TRUNCATE TABLE alertas_consumo;
    """)

def fetch_data():
    print("Obteniendo registros del Data Warehouse...")
    conn = get_connection()
    query = """
        SELECT 
            f.id_fact,
            t.anio,
            t.bimestre,
            u.alcaldia,
            u.colonia,
            f.consumo_total
        FROM fact_consumo_agua f
        JOIN dim_tiempo t ON f.id_tiempo = t.id_tiempo
        JOIN dim_ubicacion u ON f.id_ubicacion = u.id_ubicacion
        WHERE f.consumo_total IS NOT NULL;
    """
    df = pd.read_sql_query(query, conn)
    conn.close()
    
    # Asegurar tipos
    df['consumo_total'] = df['consumo_total'].astype(float)
    df['anio'] = df['anio'].astype(int)
    df['bimestre'] = df['bimestre'].astype(int)
    
    print(f"Se cargaron {len(df)} registros para análisis.")
    return df

def detect_anomalies_iqr(df):
    print("Ejecutando detección de anomalías por Rango Intercuartílico (IQR)...")
    anomalies = []
    
    # Agrupar por colonia para calcular IQR local
    grouped = df.groupby(['alcaldia', 'colonia'])
    
    for (alcaldia, colonia), group in grouped:
        if len(group) < 3:
            # Si hay muy pocos datos, no se calcula IQR confiable
            continue
            
        consumos = group['consumo_total'].values
        q1 = np.percentile(consumos, 25)
        q3 = np.percentile(consumos, 75)
        iqr = q3 - q1
        median = np.median(consumos)
        
        # Umbral exterior amplio (3 * IQR) para detectar anomalías extremas (fugas)
        # Umbral estándar (1.5 * IQR) para anomalías moderadas
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        # Evitar problemas si todos los valores son idénticos e IQR es 0
        if iqr == 0:
            std = np.std(consumos)
            if std > 0:
                lower_bound = median - 3 * std
                upper_bound = median + 3 * std
            else:
                continue
        
        for idx, row in group.iterrows():
            val = row['consumo_total']
            if val > upper_bound or val < lower_bound:
                # Calcular desviación porcentual sobre la mediana esperada
                desviacion = ((val - median) / median * 100) if median > 0 else 0
                
                anomalies.append((
                    int(row['id_fact']),
                    row['alcaldia'],
                    row['colonia'],
                    int(row['anio']),
                    int(row['bimestre']),
                    float(val),
                    float(median),
                    float(desviacion),
                    'IQR',
                    float(1.5 if val > upper_bound else -1.5), # representativo
                    True
                ))
                
    print(f"IQR detectó {len(anomalies)} registros anómalos.")
    return anomalies

def detect_anomalies_isolation_forest(df):
    print("Ejecutando detección de anomalías con Isolation Forest...")
    
    # Dado que los consumos varían drásticamente por colonia, normalizamos el consumo de cada registro
    # dividiéndolo por la mediana histórica de su respectiva colonia.
    medians = df.groupby(['alcaldia', 'colonia'])['consumo_total'].transform('median')
    
    # Evitar divisiones por cero
    medians = medians.replace(0, 1.0)
    df['consumo_normalizado'] = df['consumo_total'] / medians
    
    # Preparar características para el Isolation Forest
    # Usamos consumo_normalizado y bimestre (para capturar estacionalidad)
    X = df[['consumo_normalizado', 'bimestre']].copy()
    
    # Ajustar Isolation Forest
    # contamination es el porcentaje esperado de anomalías (ej: 0.015 para 1.5%)
    clf = IsolationForest(n_estimators=100, contamination=0.015, random_state=42)
    clf.fit(X)
    
    df['scores'] = clf.decision_function(X) # Anomaly score: menor puntuación = más anómalo
    df['prediction'] = clf.predict(X)       # -1 para anomalía, 1 para normal
    
    anom_df = df[df['prediction'] == -1]
    
    anomalies = []
    for idx, row in anom_df.iterrows():
        # Obtener la mediana real de esta colonia para reportar consumo esperado
        col_median = df[(df['alcaldia'] == row['alcaldia']) & (df['colonia'] == row['colonia'])]['consumo_total'].median()
        desviacion = ((row['consumo_total'] - col_median) / col_median * 100) if col_median > 0 else 0
        
        anomalies.append((
            int(row['id_fact']),
            row['alcaldia'],
            row['colonia'],
            int(row['anio']),
            int(row['bimestre']),
            float(row['consumo_total']),
            float(col_median),
            float(desviacion),
            'IsolationForest',
            float(row['scores']),
            True
        ))
        
    print(f"Isolation Forest detectó {len(anomalies)} registros anómalos.")
    return anomalies

def save_anomalies(anomalies):
    if not anomalies:
        print("No se detectaron anomalías para guardar.")
        return
        
    conn = get_connection()
    cur = conn.cursor()
    
    setup_alertas_table(cur)
    
    query = """
        INSERT INTO alertas_consumo (
            id_fact, alcaldia, colonia, anio, bimestre, 
            consumo_total, consumo_esperado, desviacion_porcentaje, 
            metodo, score, es_anomalo
        ) VALUES %s;
    """
    
    print(f"Insertando {len(anomalies)} alertas en la base de datos...")
    execute_values(cur, query, anomalies)
    conn.commit()
    
    # Mostrar resumen
    cur.execute("SELECT COUNT(*), metodo FROM alertas_consumo GROUP BY metodo;")
    for row in cur.fetchall():
        print(f"  - Guardados {row[0]} registros usando método {row[1]}")
        
    cur.close()
    conn.close()
    print("Proceso de guardado completo con éxito.")

def main():
    try:
        df = fetch_data()
        if len(df) == 0:
            print("No hay datos en fact_consumo_agua.")
            sys.exit(0)
            
        iqr_anoms = detect_anomalies_iqr(df)
        
        try:
            if_anoms = detect_anomalies_isolation_forest(df)
            all_anoms = iqr_anoms + if_anoms
        except Exception as e:
            print(f"Advertencia al ejecutar Isolation Forest (posiblemente por falta de scikit-learn): {e}")
            all_anoms = iqr_anoms
            
        save_anomalies(all_anoms)
        
    except Exception as exc:
        print(f"ERROR en la ejecución del detector de anomalías: {exc}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
