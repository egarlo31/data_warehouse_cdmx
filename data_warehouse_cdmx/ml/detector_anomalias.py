import os
import logging
import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import execute_values
from sklearn.ensemble import IsolationForest
from dotenv import load_dotenv

# Configurar logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("detector_anomalias")

def main():
    # Cargar variables de entorno
    load_dotenv()
    
    DB_HOST = os.getenv("DB_HOST", "localhost")
    DB_PORT = int(os.getenv("DB_PORT", "5435"))
    DB_NAME = os.getenv("DB_NAME", "dw_cdmx")
    DB_USER = os.getenv("DB_USER", "emilio")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "")
    
    if not DB_PASSWORD:
        logger.error("DB_PASSWORD no está definida en el archivo .env")
        return

    logger.info("Conectando a la base de datos...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
    except Exception as e:
        logger.error("Error al conectar a la base de datos: %s", e)
        return

    try:
        logger.info("Cargando datos de fact_consumo_agua...")
        query = """
            SELECT f.id_fact, t.anio, t.bimestre, u.alcaldia, u.colonia, f.consumo_total
            FROM fact_consumo_agua f
            JOIN dim_tiempo t ON f.id_tiempo = t.id_tiempo
            JOIN dim_ubicacion u ON f.id_ubicacion = u.id_ubicacion
            WHERE f.consumo_total IS NOT NULL AND f.consumo_total > 0;
        """
        df = pd.read_sql(query, conn)
        logger.info("Datos cargados. Total filas: %d", len(df))
        
        if len(df) < 10:
            logger.warning("No hay suficientes datos para entrenar el modelo.")
            return

        # Calcular estadísticas por colonia
        logger.info("Calculando desviaciones y estadísticas...")
        colonia_stats = df.groupby('colonia')['consumo_total'].agg(['mean', 'std']).reset_index()
        colonia_stats.rename(columns={'mean': 'colonia_mean', 'std': 'colonia_std'}, inplace=True)
        colonia_stats['colonia_std'] = colonia_stats['colonia_std'].fillna(0)

        # Calcular estadísticas por alcaldía
        alcaldia_stats = df.groupby('alcaldia')['consumo_total'].agg(['mean', 'std']).reset_index()
        alcaldia_stats.rename(columns={'mean': 'alcaldia_mean', 'std': 'alcaldia_std'}, inplace=True)
        alcaldia_stats['alcaldia_std'] = alcaldia_stats['alcaldia_std'].fillna(0)

        # Merge de estadísticas
        df = df.merge(colonia_stats, on='colonia', how='left')
        df = df.merge(alcaldia_stats, on='alcaldia', how='left')

        # Calcular Z-scores para normalizar la desviación
        df['z_colonia'] = (df['consumo_total'] - df['colonia_mean']) / (df['colonia_std'] + 1e-5)
        df['z_alcaldia'] = (df['consumo_total'] - df['alcaldia_mean']) / (df['alcaldia_std'] + 1e-5)
        
        global_mean = df['consumo_total'].mean()
        global_std = df['consumo_total'].std()
        df['z_global'] = (df['consumo_total'] - global_mean) / (global_std + 1e-5)

        logger.info("Entrenando Isolation Forest...")
        X = df[['consumo_total', 'z_colonia', 'z_alcaldia', 'z_global']].values
        
        # 3% de contaminación (porcentaje esperado de anomalías)
        model = IsolationForest(contamination=0.03, random_state=42)
        df['anomaly_pred'] = model.fit_predict(X)
        df['anomaly_score'] = model.decision_function(X) # Menores valores son más atípicos
        
        anomalies = df[df['anomaly_pred'] == -1].copy()
        logger.info("Detección finalizada. Total anomalías encontradas: %d", len(anomalies))
        
        if len(anomalies) > 0:
            # Calcular desviación porcentual y normalizar score de 0 a 1
            anomalies['desviacion_porcentaje'] = ((anomalies['consumo_total'] - anomalies['colonia_mean']) / (anomalies['colonia_mean'] + 1e-5)) * 100
            
            min_score = anomalies['anomaly_score'].min()
            max_score = anomalies['anomaly_score'].max()
            if max_score != min_score:
                anomalies['score'] = (max_score - anomalies['anomaly_score']) / (max_score - min_score)
            else:
                anomalies['score'] = 1.0

            # Guardar alertas en la base de datos
            logger.info("Guardando alertas en la tabla alertas_consumo...")
            cur = conn.cursor()
            
            # Limpiar alertas anteriores
            cur.execute("TRUNCATE TABLE alertas_consumo;")
            
            insert_query = """
                INSERT INTO alertas_consumo (
                    id_fact, alcaldia, colonia, anio, bimestre,
                    consumo_total, consumo_esperado, desviacion_porcentaje,
                    metodo, score, es_anomalo
                ) VALUES %s;
            """
            
            values = [
                (
                    int(row['id_fact']),
                    row['alcaldia'],
                    row['colonia'],
                    int(row['anio']),
                    int(row['bimestre']),
                    float(row['consumo_total']),
                    float(row['colonia_mean']),
                    float(row['desviacion_porcentaje']),
                    'Isolation Forest',
                    float(row['score']),
                    True
                )
                for idx, row in anomalies.iterrows()
            ]
            
            execute_values(cur, insert_query, values)
            conn.commit()
            cur.close()
            logger.info("Alertas guardadas exitosamente en alertas_consumo.")
        else:
            logger.info("No se detectaron anomalías.")

    except Exception as e:
        logger.error("Error durante la ejecución del proceso: %s", e)
    finally:
        conn.close()
        logger.info("Conexión a la base de datos cerrada.")

if __name__ == "__main__":
    main()
