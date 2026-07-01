import os
import glob
from pathlib import Path
import pandas as pd
import numpy as np

# Rutas del proyecto
BASE_DIR = Path(__file__).resolve().parent.parent
RAW_DIR = BASE_DIR / "data" / "raw" / "VALLE_DEL_CAUCA"
PROCESSED_DIR = BASE_DIR / "data" / "processed"

# Patrones de búsqueda para archivos Parquet (basados en nombres en español del IDEAM)
DATASET_PATTERNS = {
    "precip": "*precipitaci*.parquet",
    "humidity": "*humedad*.parquet",
    "temp_max": "*temperatura_m*xima*.parquet",
    "temp_min": "*temperatura_m*nima*.parquet"
}

def load_parquet_files(pattern_key):
    """Carga y concatena todos los archivos Parquet para un patrón específico."""
    pattern_str = DATASET_PATTERNS[pattern_key]
    pattern = str(RAW_DIR / "**" / pattern_str)
    files = glob.glob(pattern, recursive=True)
    
    if not files:
        print(f"No se encontraron archivos Parquet para el patrón: {pattern_str}")
        return pd.DataFrame()
    
    print(f"Leyendo {len(files)} archivos Parquet para {pattern_key} ({pattern_str})...")
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

def process_metadata(df_list):
    """Extrae y consolida los metadatos de las estaciones."""
    print("Consolidando metadatos de estaciones...")
    stations_data = []
    
    for df in df_list:
        if df.empty:
            continue
            
        # Requerimos columnas básicas de metadatos
        cols = ['codigoestacion', 'nombreestacion', 'departamento', 'municipio', 'zonahidrografica', 'latitud', 'longitud']
        missing_cols = [c for c in cols if c not in df.columns]
        if missing_cols:
            continue
            
        # Limpieza básica
        station_df = df[cols].copy()
        station_df['latitud'] = pd.to_numeric(station_df['latitud'], errors='coerce')
        station_df['longitud'] = pd.to_numeric(station_df['longitud'], errors='coerce')
        
        # Eliminar filas con código nulo
        station_df = station_df.dropna(subset=['codigoestacion'])
        stations_data.append(station_df)
        
    if not stations_data:
        return pd.DataFrame()
        
    combined = pd.concat(stations_data, ignore_index=True)
    
    # Nos quedamos con la última ubicación o metadatos conocidos por estación para evitar duplicados
    # Agrupamos por codigoestacion y tomamos el primer registro válido
    stations = combined.groupby('codigoestacion').first().reset_index()
    return stations

def main():
    print("Iniciando agregación de datos a resúmenes mensuales...")
    
    # 1. Cargar datasets
    df_temp_max = load_parquet_files("temp_max")
    df_temp_min = load_parquet_files("temp_min")
    df_humidity = load_parquet_files("humidity")
    df_precip = load_parquet_files("precip")
    
    # Extraer metadatos
    stations_metadata = process_metadata([df_temp_max, df_temp_min, df_humidity, df_precip])
    if stations_metadata.empty:
        print("Error: No se pudieron extraer metadatos de estaciones.")
        return
        
    # Guardar metadatos en un CSV auxiliar
    os.makedirs(PROCESSED_DIR, exist_ok=True)
    stations_metadata.to_csv(PROCESSED_DIR / "stations_metadata.csv", index=False, encoding="utf-8")
    print(f"Metadatos guardados ({len(stations_metadata)} estaciones).")
    
    # DataFrames de resultados agregados por variable
    monthly_dfs = []
    
    # 2. Procesar Temperatura Máxima (ccvq-rp9s)
    # Temperatura máxima media mensual: Promedio de las máximas diarias
    if not df_temp_max.empty:
        print("Procesando Temperatura Máxima...")
        df = df_temp_max.copy()
        df['fechaobservacion'] = pd.to_datetime(df['fechaobservacion'])
        df['valorobservado'] = pd.to_numeric(df['valorobservado'], errors='coerce')
        df['date'] = df['fechaobservacion'].dt.date
        df['year'] = df['fechaobservacion'].dt.year
        df['month'] = df['fechaobservacion'].dt.month
        
        # Máxima diaria por estación
        daily_max = df.groupby(['codigoestacion', 'date', 'year', 'month'])['valorobservado'].max().reset_index()
        # Promedio mensual de máximas diarias
        monthly_max_temp = daily_max.groupby(['codigoestacion', 'year', 'month'])['valorobservado'].mean().reset_index()
        monthly_max_temp.rename(columns={'valorobservado': 'mean_max_temperature'}, inplace=True)
        monthly_dfs.append(monthly_max_temp)
        
    # 3. Procesar Temperatura Mínima (afdg-3zpb)
    # Temperatura mínima media mensual: Promedio de las mínimas diarias
    if not df_temp_min.empty:
        print("Procesando Temperatura Mínima...")
        df = df_temp_min.copy()
        df['fechaobservacion'] = pd.to_datetime(df['fechaobservacion'])
        df['valorobservado'] = pd.to_numeric(df['valorobservado'], errors='coerce')
        df['date'] = df['fechaobservacion'].dt.date
        df['year'] = df['fechaobservacion'].dt.year
        df['month'] = df['fechaobservacion'].dt.month
        
        # Mínima diaria por estación
        daily_min = df.groupby(['codigoestacion', 'date', 'year', 'month'])['valorobservado'].min().reset_index()
        # Promedio mensual de mínimas diarias
        monthly_min_temp = daily_min.groupby(['codigoestacion', 'year', 'month'])['valorobservado'].mean().reset_index()
        monthly_min_temp.rename(columns={'valorobservado': 'mean_min_temperature'}, inplace=True)
        monthly_dfs.append(monthly_min_temp)
        
    # 4. Procesar Humedad Relativa (uext-mhny)
    # Húmeda relativa calculada máxima y mínima mensual: Promedio mensual de máximas/mínimas diarias
    if not df_humidity.empty:
        print("Procesando Humedad Relativa...")
        df = df_humidity.copy()
        df['fechaobservacion'] = pd.to_datetime(df['fechaobservacion'])
        df['valorobservado'] = pd.to_numeric(df['valorobservado'], errors='coerce')
        df['date'] = df['fechaobservacion'].dt.date
        df['year'] = df['fechaobservacion'].dt.year
        df['month'] = df['fechaobservacion'].dt.month
        
        # Máxima y mínima diaria
        daily_hum = df.groupby(['codigoestacion', 'date', 'year', 'month'])['valorobservado'].agg(['max', 'min']).reset_index()
        # Promedio mensual de máximas y mínimas
        monthly_hum = daily_hum.groupby(['codigoestacion', 'year', 'month']).agg(
            mean_max_humidity=('max', 'mean'),
            mean_min_humidity=('min', 'mean')
        ).reset_index()
        monthly_dfs.append(monthly_hum)
        
    # 5. Procesar Precipitación (s54a-sgyg)
    # Precipitación total mensual: Suma mensual de precipitaciones
    if not df_precip.empty:
        print("Procesando Precipitación...")
        df = df_precip.copy()
        df['fechaobservacion'] = pd.to_datetime(df['fechaobservacion'])
        df['valorobservado'] = pd.to_numeric(df['valorobservado'], errors='coerce')
        df['year'] = df['fechaobservacion'].dt.year
        df['month'] = df['fechaobservacion'].dt.month
        
        # Suma mensual
        monthly_precip = df.groupby(['codigoestacion', 'year', 'month'])['valorobservado'].sum().reset_index()
        monthly_precip.rename(columns={'valorobservado': 'total_precipitation'}, inplace=True)
        monthly_dfs.append(monthly_precip)
        
    # 6. Unir los resúmenes mensuales
    if not monthly_dfs:
        print("Error: No hay datos agregados mensuales para consolidar.")
        return
        
    print("Consolidando resúmenes mensuales...")
    # Empezamos con la primera variable
    consolidated = monthly_dfs[0]
    for m_df in monthly_dfs[1:]:
        consolidated = pd.merge(consolidated, m_df, on=['codigoestacion', 'year', 'month'], how='outer')
        
    # 7. Unir con los metadatos de las estaciones
    final_dataset = pd.merge(stations_metadata, consolidated, on='codigoestacion', how='right')
    
    # Ordenar por estación, año y mes
    final_dataset = final_dataset.sort_values(by=['codigoestacion', 'year', 'month'])
    
    # 8. Guardar resultado final
    output_path = PROCESSED_DIR / "monthly_climate_indices.csv"
    final_dataset.to_csv(output_path, index=False, encoding="utf-8")
    print(f"Índices mensuales guardados en {output_path} ({len(final_dataset)} filas).")

if __name__ == "__main__":
    main()
