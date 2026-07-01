import os
import sys
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno del archivo .env
env_path = Path(__file__).resolve().parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

# Asegurar que el paquete ideam_socrata sea importable
try:
    from ideam_socrata.batch import download
except ImportError:
    print("Error: El paquete ideam-data-automator no está instalado en el entorno de Python.")
    sys.exit(1)

# Parámetros comunes de descarga
DEPARTAMENTOS = ["VALLE DEL CAUCA"]
FECHA_INICIO = "2019-01-01"
FECHA_FIN = "2026-07-01"  # Rango exclusivo, incluye hasta el último día de junio de 2026

# Carpeta de salida para datos brutos
BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = str(BASE_DIR / "data" / "raw")

# Datasets a descargar
DATASETS = {
    "s54a-sgyg": "Precipitacion",
    "uext-mhny": "Humedad del Aire",
    "ccvq-rp9s": "Temperatura Maxima",
    "afdg-3zpb": "Temperatura Minima"
}

def main():
    print(f"Iniciando la descarga de datos climatológicos para {DEPARTAMENTOS[0]}...")
    print(f"Período: {FECHA_INICIO} -> {FECHA_FIN}")
    print(f"Directorio de salida: {OUTPUT_DIR}\n")
    
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    
    for dataset_id, name in DATASETS.items():
        print("=" * 60)
        print(f"Descargando dataset: {name} ({dataset_id})")
        print("=" * 60)
        try:
            summary = download(
                dataset_id=dataset_id,
                departments=DEPARTAMENTOS,
                start_date=FECHA_INICIO,
                end_date=FECHA_FIN,
                include_csv=True,
                base_dir=OUTPUT_DIR,
                engine="rapido"
            )
            print(f"\nFinalizado {name}: {summary.get('rows', 0):,} filas descargadas en {summary.get('seconds', 0)}s.\n")
        except Exception as e:
            print(f"\nError al descargar {name}: {e}\n")
            
    print("¡Proceso de descarga completado!")

if __name__ == "__main__":
    main()
