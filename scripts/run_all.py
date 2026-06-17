import argparse
import sys
import os

# Asegurar que la raíz del proyecto esté en el PYTHONPATH para importar el módulo src
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.pipeline import ejecutar_pipeline

def main():
    parser = argparse.ArgumentParser(description="Pipeline Predictivo de Dengue - IMDC 2026")
    
    parser.add_argument(
        '--input', 
        type=str, 
        required=True, 
        help="Ruta del archivo CSV con datos históricos de dengue"
    )
    
    parser.add_argument(
        '--output', 
        type=str, 
        default='outputs', 
        help="Directorio donde se guardarán las predicciones generadas"
    )
    
    parser.add_argument(
        '--periods', 
        type=int, 
        default=52, 
        help="Número de semanas a predecir a futuro"
    )

    args = parser.parse_args()
    
    try:
        ejecutar_pipeline(
            ruta_datos_historicos=args.input, 
            directorio_salida=args.output, 
            periodos=args.periods
        )
    except Exception as e:
        print(f"Error durante la ejecución del pipeline: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
