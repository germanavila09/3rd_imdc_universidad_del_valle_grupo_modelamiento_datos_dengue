import pandas as pd
import numpy as np
from pmdarima.arima import auto_arima
from epiweeks import Week

def cargar_y_preparar_datos(ruta_csv: str) -> pd.DataFrame:
    """
    Carga los datos históricos y prepara la serie temporal.
    Retorna un DataFrame con índice de tiempo o formato limpio.
    """
    df = pd.read_csv(ruta_csv)
    df['date'] = pd.to_datetime(df['date'])
    df = df.sort_values('date').reset_index(drop=True)
    return df

def entrenar_modelo_arima(serie_temporal: pd.Series):
    """
    Ajusta un modelo AutoARIMA sobre la serie temporal histórica.
    Configura estacionalidad anual (m=52 para semanas).
    """
    # Ajuste automático del modelo ARIMA
    modelo = auto_arima(
        serie_temporal,
        seasonal=True,
        m=52,  # Estacionalidad semanal (52 semanas por año)
        stepwise=True,
        suppress_warnings=True,
        error_action="ignore"
    )
    return modelo

def generar_predicciones_con_intervalos(modelo, periodos: int = 52) -> pd.DataFrame:
    """
    Genera predicciones puntuales y calcula los intervalos de confianza requeridos:
    50%, 80%, 90% y 95% usando la estimación del modelo ARIMA.
    """
    # Predicción del valor medio (mediana en ARIMA/Normal)
    pred_mediana = modelo.predict(n_periods=periodos)
    
    # Índices/fechas a futuro (ejemplo básico, se debe ajustar al calendario epidemiológico)
    fechas = pd.date_range(start=pd.Timestamp.now(), periods=periodos, freq='W')
    
    forecast_df = pd.DataFrame({
        'date': fechas.strftime('%Y-%m-%d'),
        'pred': np.clip(pred_mediana, 0, None)  # Evitar valores negativos
    })
    
    # Alphas correspondientes para los intervalos de confianza:
    # Intervalo 95% -> alpha = 0.05
    # Intervalo 90% -> alpha = 0.10
    # Intervalo 80% -> alpha = 0.20
    # Intervalo 50% -> alpha = 0.50
    alphas = {
        '95': 0.05,
        '90': 0.10,
        '80': 0.20,
        '50': 0.50
    }
    
    for pct, alpha in alphas.items():
        _, conf_int = modelo.predict(n_periods=periodos, return_conf_int=True, alpha=alpha)
        
        lower_col = f'lower_{pct}'
        upper_col = f'upper_{pct}'
        
        forecast_df[lower_col] = np.clip(conf_int[:, 0], 0, None)
        forecast_df[upper_col] = np.clip(conf_int[:, 1], 0, None)
        
    # Validar que los límites estén ordenados matemáticamente:
    # lower_95 <= lower_90 <= lower_80 <= lower_50 <= pred <= upper_50 <= upper_80 <= upper_90 <= upper_95
    return forecast_df
