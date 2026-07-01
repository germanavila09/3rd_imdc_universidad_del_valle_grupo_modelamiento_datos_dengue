import os
import sys
from pathlib import Path
from io import StringIO
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import pandas as pd
from dotenv import load_dotenv
import glob

# Cargar variables de entorno
BASE_DIR = Path(__file__).resolve().parent.parent
env_path = BASE_DIR / '.env'
load_dotenv(dotenv_path=env_path)

DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "dengue_valle")

RAW_DIR = BASE_DIR / "data" / "raw" / "VALLE_DEL_CAUCA"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

# Patrones de búsqueda para archivos Parquet (basados en nombres en español del IDEAM)
DATASET_PATTERNS = {
    "precip": "*precipitaci*.parquet",
    "humidity": "*humedad*.parquet",
    "temp_max": "*temperatura_m*xima*.parquet",
    "temp_min": "*temperatura_m*nima*.parquet"
}

def create_database():
    """Crea la base de datos si no existe."""
    print(f"Conectando a postgres por defecto para verificar/crear la BD '{DB_NAME}'...")
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname="postgres"
    )
    conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
    cursor = conn.cursor()
    
    # Verificar si la base de datos existe
    cursor.execute("SELECT 1 FROM pg_catalog.pg_database WHERE datname = %s", (DB_NAME,))
    exists = cursor.fetchone()
    if not exists:
        print(f"Creando base de datos '{DB_NAME}'...")
        cursor.execute(f"CREATE DATABASE {DB_NAME}")
    else:
        print(f"La base de datos '{DB_NAME}' ya existe.")
        
    cursor.close()
    conn.close()

def execute_schema():
    """Ejecuta el archivo schema.sql en la base de datos del proyecto."""
    schema_path = BASE_DIR / "sql" / "schema.sql"
    if not schema_path.exists():
        print(f"Error: No se encontró el esquema SQL en {schema_path}")
        sys.exit(1)
        
    print(f"Ejecutando esquema SQL en '{DB_NAME}'...")
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME
    )
    cursor = conn.cursor()
    
    with open(schema_path, "r", encoding="utf-8") as f:
        schema_sql = f.read()
        
    cursor.execute(schema_sql)
    conn.commit()
    cursor.close()
    conn.close()
    print("Esquema ejecutado correctamente.")

def copy_df_to_postgres(conn, df, table, columns):
    """Copia un DataFrame de Pandas a una tabla de Postgres de forma masiva y rápida."""
    # Filtrar solo columnas de interés
    df_subset = df[columns].copy()
    
    # Crear buffer en memoria
    buffer = StringIO()
    df_subset.to_csv(buffer, index=False, header=False, sep='\t', na_rep='\\N')
    buffer.seek(0)
    
    cursor = conn.cursor()
    try:
        cursor.copy_from(buffer, table, sep='\t', columns=columns, null='\\N')
        conn.commit()
        print(f"Copiados masivamente {len(df_subset):,} registros a la tabla '{table}'.")
    except Exception as e:
        conn.rollback()
        print(f"Error al copiar datos a '{table}': {e}")
        raise e
    finally:
        cursor.close()

def load_parquet_files(pattern_key):
    """Carga y concatena todos los archivos Parquet para un patrón específico."""
    pattern_str = DATASET_PATTERNS[pattern_key]
    pattern = str(RAW_DIR / "**" / pattern_str)
    files = glob.glob(pattern, recursive=True)
    if not files:
        return pd.DataFrame()
    
    dfs = []
    for file in files:
        try:
            df = pd.read_parquet(file)
            dfs.append(df)
        except Exception as e:
            print(f"Error al leer archivo {file}: {e}")
            
    if not dfs:
        return pd.DataFrame()
        
    return pd.concat(dfs, ignore_index=True)

def populate_database():
    """Carga las estaciones y las observaciones en las tablas de Postgres."""
    # Conexión principal
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        user=DB_USER,
        password=DB_PASSWORD,
        dbname=DB_NAME
    )
    
    # 1. Cargar metadatos de estaciones
    metadata_path = PROCESSED_DIR / "stations_metadata.csv"
    if not metadata_path.exists():
        print("Error: No se encontró stations_metadata.csv. Ejecuta primero scripts/aggregate.py.")
        conn.close()
        return
        
    print("Cargando estaciones en la tabla 'stations'...")
    stations_df = pd.read_csv(metadata_path)
    # Limpieza de nulos en coordenadas
    stations_df['latitud'] = pd.to_numeric(stations_df['latitud'], errors='coerce')
    stations_df['longitud'] = pd.to_numeric(stations_df['longitud'], errors='coerce')
    
    # Limpieza de duplicados
    stations_df = stations_df.drop_duplicates(subset=['codigoestacion'])
    
    # Insertar en stations con ON CONFLICT para evitar fallas
    cursor = conn.cursor()
    for _, row in stations_df.iterrows():
        cursor.execute("""
            INSERT INTO stations (codigoestacion, nombreestacion, departamento, municipio, zonahidrografica, latitud, longitud)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (codigoestacion) DO UPDATE 
            SET nombreestacion = EXCLUDED.nombreestacion,
                departamento = EXCLUDED.departamento,
                municipio = EXCLUDED.municipio,
                zonahidrografica = EXCLUDED.zonahidrografica,
                latitud = EXCLUDED.latitud,
                longitud = EXCLUDED.longitud
        """, (
            str(row['codigoestacion']),
            str(row['nombreestacion']) if pd.notna(row['nombreestacion']) else None,
            str(row['departamento']) if pd.notna(row['departamento']) else None,
            str(row['municipio']) if pd.notna(row['municipio']) else None,
            str(row['zonahidrografica']) if pd.notna(row['zonahidrografica']) else None,
            float(row['latitud']) if pd.notna(row['latitud']) else None,
            float(row['longitud']) if pd.notna(row['longitud']) else None
        ))
    conn.commit()
    cursor.close()
    print(f"Cargadas {len(stations_df)} estaciones.")
    
    # Tablas raw correspondientes a los datasets
    raw_tables = {
        "precip": ("precipitation", ["codigoestacion", "fechaobservacion", "valorobservado"]),
        "humidity": ("humidity", ["codigoestacion", "fechaobservacion", "valorobservado"]),
        "temp_max": ("max_temperature", ["codigoestacion", "fechaobservacion", "valorobservado"]),
        "temp_min": ("min_temperature", ["codigoestacion", "fechaobservacion", "valorobservado"])
    }
    
    # 2. Cargar observaciones brutas
    for key, (table_name, columns) in raw_tables.items():
        print(f"Cargando datos crudos en la tabla '{table_name}' desde archivos Parquet...")
        df = load_parquet_files(key)
        if df.empty:
            print(f"Sin datos crudos para cargar en '{table_name}'.")
            continue
            
        # Preparación de datos
        df['fechaobservacion'] = pd.to_datetime(df['fechaobservacion'])
        # Formato compatible con Postgres timestamp
        df['fechaobservacion'] = df['fechaobservacion'].dt.strftime('%Y-%m-%d %H:%M:%S')
        df['valorobservado'] = pd.to_numeric(df['valorobservado'], errors='coerce')
        
        # Eliminar filas con valores clave nulos o duplicados (para respetar clave primaria)
        df = df.dropna(subset=['codigoestacion', 'fechaobservacion'])
        df = df.drop_duplicates(subset=['codigoestacion', 'fechaobservacion'])
        
        # Filtrar por estaciones que existan en la tabla stations para cumplir clave foránea
        valid_stations = set(stations_df['codigoestacion'].astype(str))
        df = df[df['codigoestacion'].astype(str).isin(valid_stations)]
        
        # Vaciar tabla antes de cargar para evitar duplicados si se corre varias veces
        cursor = conn.cursor()
        cursor.execute(f"TRUNCATE TABLE {table_name} CASCADE;")
        conn.commit()
        cursor.close()
        
        # Copiar datos
        copy_df_to_postgres(conn, df, table_name, columns)
        
    # 3. Cargar índices mensuales procesados
    indices_path = PROCESSED_DIR / "monthly_climate_indices.csv"
    if indices_path.exists():
        print("Cargando índices mensuales en la tabla 'monthly_climate_indices'...")
        indices_df = pd.read_csv(indices_path)
        
        # Las columnas requeridas en BD son: codigoestacion, year, month, total_precipitation, mean_max_temperature, mean_min_temperature, mean_max_humidity, mean_min_humidity
        db_cols = ['codigoestacion', 'year', 'month', 'total_precipitation', 'mean_max_temperature', 'mean_min_temperature', 'mean_max_humidity', 'mean_min_humidity']
        
        # Rellenar columnas faltantes con None/Null si por algún motivo no existen
        for col in db_cols:
            if col not in indices_df.columns:
                indices_df[col] = None
                
        # Limpieza de nulos y duplicados de clave primaria
        indices_df = indices_df.dropna(subset=['codigoestacion', 'year', 'month'])
        indices_df = indices_df.drop_duplicates(subset=['codigoestacion', 'year', 'month'])
        
        # Cumplir clave foránea
        valid_stations = set(stations_df['codigoestacion'].astype(str))
        indices_df = indices_df[indices_df['codigoestacion'].astype(str).isin(valid_stations)]
        
        # Vaciar tabla antes de cargar
        cursor = conn.cursor()
        cursor.execute("TRUNCATE TABLE monthly_climate_indices;")
        conn.commit()
        cursor.close()
        
        # Copiar a Postgres
        copy_df_to_postgres(conn, indices_df, "monthly_climate_indices", db_cols)
    else:
        print("Advertencia: No se encontró monthly_climate_indices.csv. Saltando carga de índices mensuales.")
        
    conn.close()
    print("¡Base de datos poblada exitosamente!")

def main():
    try:
        create_database()
        execute_schema()
        populate_database()
        print("=" * 60)
        print("¡PROCESO COMPLETADO EXITOSAMENTE EN POSTGRESQL!")
        print("=" * 60)
    except Exception as e:
        print(f"\nError en el proceso de base de datos: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
