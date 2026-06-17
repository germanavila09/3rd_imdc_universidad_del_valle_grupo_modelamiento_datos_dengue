import os
import pandas as pd
from pathlib import Path
from src.modelo import cargar_y_preparar_datos, entrenar_modelo_arima, generar_predicciones_con_intervalos

def ejecutar_pipeline(ruta_datos_historicos: str, directorio_salida: str, periodos: int = 52):
    """
    Orquesta todo el proceso predictivo:
    1. Carga y preprocesa los datos históricos de dengue.
    2. Entrena el modelo AutoARIMA (pmdarima).
    3. Genera las proyecciones futuras y calcula los intervalos de confianza requeridos.
    4. Guarda el resultado final en formato CSV listo para enviar a Mosqlimate.
    """
    print(f"Cargando datos desde: {ruta_datos_historicos}...")
    df_datos = cargar_y_preparar_datos(ruta_datos_historicos)
    
    # Asumimos que la columna 'y' contiene los casos y 'date' las fechas
    serie = df_datos.set_index('date')['y'] if 'y' in df_datos.columns else df_datos.iloc[:, 1]
    
    print("Entrenando modelo AutoARIMA (puede tomar unos minutos debido a la estacionalidad)...")
    modelo = entrenar_modelo_arima(serie)
    
    print(f"Generando pronóstico para {periodos} semanas...")
    forecast_df = generar_predicciones_con_intervalos(modelo, periodos=periodos)
    
    # Asegurar que el directorio de salida existe
    Path(directorio_salida).mkdir(parents=True, exist_ok=True)
    ruta_guardado = os.path.join(directorio_salida, 'predicciones_desafio.csv')
    
    forecast_df.to_csv(ruta_guardado, index=False)
    print(f"¡Pipeline completado! Predicciones guardadas en: {ruta_guardado}")
    
    return forecast_df
