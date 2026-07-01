# Proyecto de Integración de Datos Climatológicos IDEAM (Valle del Cauca)

Este proyecto automatiza la descarga de variables climatológicas clave desde la API de Socrata (Datos Abiertos Colombia) de estaciones en el departamento del Valle del Cauca, realiza el procesamiento y cálculo de agregados mensuales, y los almacena en una base de datos local de PostgreSQL para su posterior uso en modelos predictivos (como el modelo de Dengue).

## Requisitos Previos

1. **Python 3.10+** instalado en el sistema.
2. **PostgreSQL** instalado y ejecutándose en el equipo local (puerto 5432).
3. Credenciales de la base de datos configuradas en el archivo `.env` en la raíz del proyecto.

## Estructura del Proyecto

- `data/`: Almacena los archivos descargados y procesados.
  - `raw/`: Contiene los archivos brutos `.parquet` descargados de Socrata, organizados por municipio.
  - `processed/`: Archivos procesados con los promedios y sumas mensuales.
- `scripts/`: Código de Python.
  - `download.py`: Descarga masiva paralela desde la API de Socrata.
  - `aggregate.py`: Agrupa y realiza los cálculos estadísticos mensuales.
  - `load_db.py`: Crea la base de datos `dengue_valle` y carga las estaciones, observaciones crudas e índices mensuales.
- `sql/`: Definiciones SQL.
  - `schema.sql`: Estructura física de la base de datos e índices.
- `.env`: Archivo de variables de entorno para configurar PostgreSQL.
- `requirements.txt`: Dependencias del proyecto.

## Variables Procesadas Mensualmente

Por cada estación climatológica en el Valle del Cauca, se calculan:
1. **Precipitación total mensual:** Suma acumulada mensual de la lluvia en mm (`total_precipitation`).
2. **Temperatura máxima media mensual:** Promedio de las temperaturas máximas diarias registradas en el mes (`mean_max_temperature`).
3. **Temperatura mínima media mensual:** Promedio de las temperaturas mínimas diarias registradas en el mes (`mean_min_temperature`).
4. **Humedad relativa calculada máxima mensual:** Promedio de las humedades relativas máximas diarias del mes (`mean_max_humidity`).
5. **Humedad relativa calculada mínima mensual:** Promedio de las humedades relativas mínimas diarias del mes (`mean_min_humidity`).

## Cómo Ejecutar el Proyecto

### 1. Instalar las dependencias
Asegúrate de instalar los requerimientos listados:
```bash
pip install -r requirements.txt
```

### 2. Ejecutar la descarga de datos
Descarga los registros crudos de 2019 a 2026 para las 4 variables:
```bash
python scripts/download.py
```

### 3. Ejecutar la agregación mensual
Genera las medias y sumas mensuales por estación y año-mes:
```bash
python scripts/aggregate.py
```

### 4. Cargar en PostgreSQL
Crea la base de datos e importa todos los datos (crudos y agregados):
```bash
python scripts/load_db.py
```

---

## Consultas de Ejemplo en PostgreSQL

Una vez cargados los datos, puedes ingresar a tu base de datos y correr consultas como estas:

### Consulta de los Índices Mensuales por Estación
```sql
SELECT s.nombreestacion, s.municipio, m.year, m.month, m.total_precipitation, m.mean_max_temperature, m.mean_max_humidity
FROM monthly_climate_indices m
JOIN stations s ON m.codigoestacion = s.codigoestacion
ORDER BY s.municipio, m.year, m.month;
```
