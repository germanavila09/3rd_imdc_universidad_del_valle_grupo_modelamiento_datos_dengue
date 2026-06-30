import os
import gzip
import psycopg2
from psycopg2 import sql
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env de la carpeta dengue_ia_valle
env_path = Path("dengue_ia_valle/.env")
load_dotenv(env_path)

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "dengue_ia")

def crear_base_de_datos():
    """Conecta a la base de datos default de Postgres para crear la base dengue_ia si no existe."""
    print("Conectando a PostgreSQL para verificar/crear la base de datos...")
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database="postgres"
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    # Verificar si la base de datos ya existe
    cursor.execute("SELECT 1 FROM pg_database WHERE datname = %s;", (DB_NAME,))
    exists = cursor.fetchone()
    
    if not exists:
        print(f"La base de datos '{DB_NAME}' no existe. Creandola...")
        cursor.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(DB_NAME)))
        print(f"Base de datos '{DB_NAME}' creada con exito.")
    else:
        print(f"La base de datos '{DB_NAME}' ya existe.")
        
    cursor.close()
    conn.close()

def crear_tablas(conn):
    """Crea las tablas necesarias en la base de datos."""
    cursor = conn.cursor()
    
    tablas = {
        "dengue": """
            CREATE TABLE IF NOT EXISTS dengue (
                geocode BIGINT,
                date DATE,
                casos INT,
                epiweek INT,
                uf VARCHAR(10),
                macroregional_geocode BIGINT,
                regional_geocode BIGINT,
                uf_code INT,
                target_city BOOLEAN,
                train_1 BOOLEAN,
                target_1 BOOLEAN,
                train_2 BOOLEAN,
                target_2 BOOLEAN,
                train_3 BOOLEAN,
                target_3 BOOLEAN,
                train_4 BOOLEAN,
                target_4 BOOLEAN,
                disease VARCHAR(20)
            );
        """,
        "chikungunya": """
            CREATE TABLE IF NOT EXISTS chikungunya (
                geocode BIGINT,
                date DATE,
                casos INT,
                epiweek INT,
                uf VARCHAR(10),
                macroregional_geocode BIGINT,
                regional_geocode BIGINT,
                uf_code INT,
                target_city BOOLEAN,
                train_1 BOOLEAN,
                target_1 BOOLEAN,
                train_2 BOOLEAN,
                target_2 BOOLEAN,
                train_3 BOOLEAN,
                target_3 BOOLEAN,
                train_4 BOOLEAN,
                target_4 BOOLEAN,
                disease VARCHAR(20)
            );
        """,
        "climate": """
            CREATE TABLE IF NOT EXISTS climate (
                date DATE,
                epiweek INT,
                geocode BIGINT,
                temp_min DOUBLE PRECISION,
                temp_med DOUBLE PRECISION,
                temp_max DOUBLE PRECISION,
                precip_min DOUBLE PRECISION,
                precip_med DOUBLE PRECISION,
                precip_max DOUBLE PRECISION,
                pressure_min DOUBLE PRECISION,
                pressure_med DOUBLE PRECISION,
                pressure_max DOUBLE PRECISION,
                rel_humid_min DOUBLE PRECISION,
                rel_humid_med DOUBLE PRECISION,
                rel_humid_max DOUBLE PRECISION,
                thermal_range DOUBLE PRECISION,
                rainy_days INT
            );
        """,
        "climate_forecast": """
            CREATE TABLE IF NOT EXISTS climate_forecast (
                geocode BIGINT,
                reference_month DATE,
                forecast_months_ahead INT,
                temp_med DOUBLE PRECISION,
                umid_med DOUBLE PRECISION,
                precip_tot DOUBLE PRECISION
            );
        """,
        "ocean_oscillations": """
            CREATE TABLE IF NOT EXISTS ocean_oscillations (
                date DATE,
                enso DOUBLE PRECISION,
                iod DOUBLE PRECISION,
                pdo DOUBLE PRECISION,
                epiweek INT
            );
        """,
        "environ_vars": """
            CREATE TABLE IF NOT EXISTS environ_vars (
                geocode BIGINT,
                uf_code INT,
                koppen VARCHAR(50),
                biome VARCHAR(50)
            );
        """,
        "map_regional_health": """
            CREATE TABLE IF NOT EXISTS map_regional_health (
                macroregion_code INT,
                macroregion_name VARCHAR(100),
                uf_code INT,
                uf VARCHAR(10),
                uf_name VARCHAR(100),
                macroregional_geocode BIGINT,
                macroregional_name VARCHAR(100),
                regional_geocode BIGINT,
                regional_name VARCHAR(100),
                geocode BIGINT,
                geocode_name VARCHAR(100)
            );
        """,
        "population": """
            CREATE TABLE IF NOT EXISTS population (
                geocode BIGINT,
                year INT,
                population BIGINT
            );
        """,
        "access_afya_dengue": """
            CREATE TABLE IF NOT EXISTS access_afya_dengue (
                access_date DATE,
                geocode BIGINT,
                uf VARCHAR(10),
                accessed_disease VARCHAR(100),
                access_count DOUBLE PRECISION
            );
        """
    }
    
    print("Creando tablas en la base de datos...")
    for nombre, query in tablas.items():
        # Para forzar la recreacion de la tabla access_afya_dengue si ya existia con INT
        if nombre == "access_afya_dengue":
            cursor.execute("DROP TABLE IF EXISTS access_afya_dengue;")
        cursor.execute(query)
        
    conn.commit()
    cursor.close()
    print("Todas las tablas creadas exitosamente!")

def cargar_datos_csv_gz(conn, table_name, file_name):
    """Carga un archivo csv o csv.gz en la tabla correspondiente usando COPY FROM."""
    data_path = Path("data") / file_name
    if not data_path.exists():
        print(f"Alerta: El archivo {file_name} no existe en la carpeta data/. Saltando...")
        return
        
    print(f"Cargando {file_name} en la tabla '{table_name}'...")
    cursor = conn.cursor()
    
    # Limpiar tabla primero para evitar duplicados
    cursor.execute(f"TRUNCATE TABLE {table_name};")
    conn.commit()
    
    # Usar psycopg2 copy_expert para streaming ultra rápido
    copy_query = f"COPY {table_name} FROM STDIN WITH CSV HEADER"
    
    try:
        # Abrir con gzip si es .gz, si no como archivo de texto plano
        if file_name.endswith(".gz"):
            with gzip.open(data_path, "rt", encoding="utf-8") as f:
                cursor.copy_expert(copy_query, f)
        else:
            with open(data_path, "r", encoding="utf-8") as f:
                cursor.copy_expert(copy_query, f)
                
        conn.commit()
        
        # Obtener el conteo final de filas insertadas
        cursor.execute(f"SELECT COUNT(*) FROM {table_name};")
        row_count = cursor.fetchone()[0]
        print(f" [OK] Carga exitosa: {row_count} filas insertadas en '{table_name}'.")
    except Exception as e:
        conn.rollback()
        print(f" [ERROR] Al cargar {file_name}: {e}")
        
    cursor.close()

def ejecutar_etl():
    # 1. Crear base de datos
    crear_base_de_datos()
    
    # 2. Conectar a la base de datos dengue_valle
    print(f"Conectando a la base de datos '{DB_NAME}'...")
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )
    
    try:
        # 3. Crear tablas
        crear_tablas(conn)
        
        # 4. Cargar datos masivamente
        cargar_datos_csv_gz(conn, "dengue", "dengue.csv.gz")
        cargar_datos_csv_gz(conn, "chikungunya", "chikungunya.csv.gz")
        cargar_datos_csv_gz(conn, "climate", "climate.csv.gz")
        cargar_datos_csv_gz(conn, "climate_forecast", "forecasting_climate.csv.gz")
        cargar_datos_csv_gz(conn, "ocean_oscillations", "ocean_climate_oscillations.csv.gz")
        cargar_datos_csv_gz(conn, "environ_vars", "environ_vars.csv.gz")
        cargar_datos_csv_gz(conn, "map_regional_health", "map_regional_health.csv")
        cargar_datos_csv_gz(conn, "population", "datasus_population_2001_2025.csv.gz")
        cargar_datos_csv_gz(conn, "access_afya_dengue", "access_afya_dengue_2021_2026.csv.gz")
        
    finally:
        conn.close()
        print("\nProceso ETL completado con exito!")

if __name__ == "__main__":
    ejecutar_etl()
