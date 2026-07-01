import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

# Cargar variables de entorno
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path)

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "dengue_valle")

def main():
    print("Verificando datos en la base de datos PostgreSQL...")
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            user=DB_USER,
            password=DB_PASSWORD,
            dbname=DB_NAME
        )
        cursor = conn.cursor()
        
        # 1. Verificar conteos de tablas
        tables = ["stations", "precipitation", "humidity", "max_temperature", "min_temperature", "monthly_climate_indices"]
        print("\nRecuento de registros por tabla:")
        print("-" * 50)
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            count = cursor.fetchone()[0]
            print(f"  Tabla '{table:25}': {count:,} filas")
            
        # 2. Consultar muestra de índices mensuales junto con metadatos de estaciones
        print("\nMuestra de 5 registros de índices mensuales consolidados:")
        print("-" * 100)
        query = """
            SELECT s.nombreestacion, s.municipio, m.year, m.month, 
                   m.total_precipitation, m.mean_max_temperature, m.mean_min_temperature, 
                   m.mean_max_humidity, m.mean_min_humidity
            FROM monthly_climate_indices m
            JOIN stations s ON m.codigoestacion = s.codigoestacion
            ORDER BY m.year DESC, m.month DESC, s.municipio
            LIMIT 5;
        """
        cursor.execute(query)
        rows = cursor.fetchall()
        
        print(f"{'Estación':30} | {'Municipio':15} | {'Año':4} | {'Mes':3} | {'Precip (mm)':10} | {'Temp Max':8} | {'Temp Min':8} | {'Hum Max':8} | {'Hum Min':8}")
        print("-" * 125)
        for row in rows:
            precip = f"{float(row[4]):10.1f}" if row[4] is not None else f"{'N/A':>10}"
            t_max = f"{float(row[5]):8.1f}" if row[5] is not None else f"{'N/A':>8}"
            t_min = f"{float(row[6]):8.1f}" if row[6] is not None else f"{'N/A':>8}"
            h_max = f"{float(row[7]):8.1f}" if row[7] is not None else f"{'N/A':>8}"
            h_min = f"{float(row[8]):8.1f}" if row[8] is not None else f"{'N/A':>8}"
            print(f"{row[0][:30]:30} | {row[1][:15]:15} | {row[2]:4} | {row[3]:3} | {precip} | {t_max} | {t_min} | {h_max} | {h_min}")
            
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"Error de conexión o consulta: {e}")

if __name__ == "__main__":
    main()
