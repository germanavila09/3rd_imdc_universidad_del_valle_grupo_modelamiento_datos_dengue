import os
import psycopg2
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env de la carpeta dengue_ia_valle
env_path = Path("dengue_ia_valle/.env")
load_dotenv(env_path)

def obtener_conexion():
    """Retorna una conexion activa a la base de datos PostgreSQL 'dengue_ia'."""
    return psycopg2.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=os.getenv("DB_PORT", "5432"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD", "postgres"),
        database=os.getenv("DB_NAME", "dengue_ia")
    )
