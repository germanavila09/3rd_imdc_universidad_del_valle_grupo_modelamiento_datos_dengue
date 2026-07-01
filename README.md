<p align="center">
  <img src="img/home_imdc.svg" alt="Sprint Planning" width="800" height="200">
</p>

# 3rd InfoDengue / Mosqlimate Data Challenge (IMDC 2026) - Grupo de Modelamiento de Datos en Dengue

* **Nombre del Equipo**: Grupo de Modelamiento de Datos en Dengue
* **Institución Principal**: Universidad del Valle
* **País**: Colombia

Este repositorio contiene el desarrollo del modelo predictivo presentado por nuestro equipo para el **3rd IMDC 2026**. El objetivo es pronosticar casos probables de Dengue utilizando modelos avanzados de ciencia de datos y epidemiología, respetando las restricciones de tiempo y uso de datos del desafío.

---

## 👥 1. Equipo y Colaboradores (Team and Contributors)

A continuación se detallan los integrantes del equipo y sus afiliaciones:

| Nombre | Rol | Información Académica y Profesional | Institución / Afiliación |
| :--- | :--- | :--- | :--- |
| **German Avila Rodriguez** | **Líder de Equipo** <br>*(F. Nacimiento: 29 Sept 1989)* | Geógrafo, Magíster en Ciencia de Datos. <br>Estudiante de Doctorado en Ingeniería. | Universidad Pontificia Javeriana (MSc) <br>Universidad del Valle (PhD Student) |
| **Ignacio Alberto Concha-Eastman** | **Colaborador** <br>*(F. Nacimiento: 31 Mayo 1945)* | Médico (MD), Magíster en Epidemiología (MSc). <br>Ex-Asesor Regional de la OPS/OMS (WDC). <br>Ex-Secretario de Salud de Cali. | Investigador Independiente (Retirado) |
| **Ingrid Liliana Minotta** | **Colaboradora** <br>*(F. Nacimiento: 03 Feb 1986)* | Enfermera Registrada. <br>Magíster en Epidemiología y Economía. | Pontificia Universidad Javeriana Cali |
| **Carlos Alberto Reina Bolaños** | **Colaborador** <br>*(F. Nacimiento: 28 Mayo 1990)* | Terapeuta Ocupacional. <br>Magíster en Salud Pública. <br>Doctor (PhD) en Epidemiología. | Universidad de Antioquia |
| **Pablo Roa-Urrutia** | **Colaborador** <br>*(F. Nacimiento: 03 Feb 1991)* | Terapeuta Ocupacional. <br>Magíster en Epidemiología. | Universidad Santiago de Cali |

---

## 📂 2. Estructura del Repositorio (Repository Structure)

El repositorio está organizado de la siguiente manera:

* **`src/`**: Módulos principales de modelado.
  * **`train_imdc.py`**: Modelo **AutoARIMA estacional** (log1p + Fourier m=52) y **baseline climatológico** (cuantiles empíricos por semana epidemiológica). Incluye la construcción del calendario EW41→EW40, el corte EW25 y las reglas de formato (fechas domingo, no negativos, intervalos anidados).
  * **`train_xgb.py`** / **`train_xgb_cities.py`**: Modelo **XGBoost de regresión cuantílica** (`reg:quantileerror`, 9 cuantiles) a nivel estado y ciudad, con ingeniería de variables sin fuga temporal.
* **`scripts/`**: Automatización del flujo.
  * **`run_batch.py`**: Ejecución **reanudable por lotes** del AutoARIMA (26 UF + 15 ciudades × 4 tests).
  * **`build_final_ensemble.py`**: Construye la submission final (ensamble 0.4·XGB + 0.4·clim + 0.2·ARIMA con tope por unidad).
  * **`submit_mosqlient.py`**: Envío de predicciones a la plataforma vía `mosqlient` (con `--dry-run`).
  * **`download_data.py`**, **`db_setup_and_etl.py`**: utilidades de descarga/ETL.
* **`dashboard/`**: Tablero geoespacial descriptivo y predictivo (`index.html` + `bundle.js`, Leaflet + Chart.js). Incluye la comparativa interactiva de los cuatro modelos por unidad y test.
* **`outputs/predictions/`**: Predicciones generadas.
  * **`FINAL_dengue_uf.csv`**, **`FINAL_dengue_cities.csv`**: submission final (ensamble).
  * **`dengue_{uf,cities}_validation.csv`** y **`..._xgb.csv`**: predicciones por modelo.
* **`Informe_Tecnico_IMDC2026.docx`**: informe técnico (datos, EDA, metodología, resultados).
* **`data/`**: datos del FTP de Mosqlimate (**no versionados**, ver `.gitignore`).
* **`Demo Notebooks/`**: ejemplos de la API de Mosqlimate (`Python demo.ipynb`, `R demo.Rmd`).

---

## 🛠️ 3. Librerías y Dependencias (Libraries and Dependencies)

* **Python (`>=3.10, <3.13`)**
* **`pmdarima`**: AutoARIMA con términos de Fourier para la estacionalidad anual.
* **`xgboost` (>=2.0)**: regresión cuantílica multi-cuantil (`reg:quantileerror`).
* **`pandas` / `numpy`**: manipulación de datos y cálculo numérico.
* **`epiweeks`**: semanas epidemiológicas (sistema CDC, inicio en domingo).
* **`geopandas`**: procesamiento de las geometrías (`.gpkg`) para el dashboard.
* **`matplotlib`**: figuras del informe técnico.
* **`mosqlient`**: registro del modelo y envío de predicciones a la plataforma.
* **`python-dotenv`**: carga de la clave de API desde `.env`.

Instalación rápida: `pip install pmdarima xgboost pandas numpy epiweeks geopandas matplotlib mosqlient python-dotenv`

---

## 📊 4. Datos y Variables (Data and Variables)

**Conjuntos de datos** (todos del FTP oficial de Mosqlimate, periodo EW01 2010 – EW10 2026):

* **`dengue.csv.gz`**: casos probables semanales por municipio (geocode), con `uf`, `uf_code` y las banderas `train_i/target_i` de los cuatro tests.
* **`datasus_population_2001_2025.csv.gz`**: población por municipio-año.
* **`climate.csv.gz`**: temperatura, precipitación, humedad y presión por municipio-semana.
* **`ocean_climate_oscillations.csv.gz`**: índices ENSO, IOD y PDO semanales.
* **`shape_*.gpkg`**: geometrías municipio/regional/macrorregional (EPSG:4674), usadas por el dashboard.

**Preprocesamiento**: los casos se agregan a nivel estado (UF, se excluye Espírito Santo) y para las 15 ciudades objetivo, con índice semanal continuo (domingos). Las series faltantes se rellenan con 0.

**Variables del modelo de ML (XGBoost)** — todas calculables en el origen (EW25), sin fuga temporal: armónicos de la semana epidemiológica; señal climatológica de casos por (unidad, semana) expandida solo sobre temporadas previas; nivel epidémico reciente (media EW18–25) y crecimiento interanual; total de la temporada anterior; ENSO/IOD/PDO en el origen; clima climatológico por UF-semana (temperatura, precipitación, humedad esperadas); población; y horizonte de pronóstico (`weeks_ahead`). En el análisis exploratorio, el **IOD** resultó la señal climática de mayor correlación con los casos (r≈0.30, r≈0.37 con rezago de 12 semanas).

---

## 🧠 5. Entrenamiento del Modelo (Model Training)

La submission final es un **ensamble ponderado de tres modelos**, elegido por su desempeño en el Weighted Interval Score (WIS) sobre las cuatro temporadas de validación:

1. **AutoARIMA estacional** (`src/train_imdc.py`): `log1p(casos)` + términos de Fourier (m=52) + AutoARIMA sobre los residuos. Enfoque rápido y estándar para la estacionalidad anual, evitando el costoso SARIMA con periodo 52.
2. **Baseline climatológico** (`src/train_imdc.py`): cuantiles empíricos históricos por semana epidemiológica; robusto y sin extrapolación de tendencia.
3. **XGBoost cuantílico** (`src/train_xgb.py`): modelo global con objetivo `reg:quantileerror` (pérdida pinball) sobre las variables descritas en la Sección 4.

**Ensamble final** = `0.4·XGBoost + 0.4·climatológico + 0.2·AutoARIMA`, con un **tope por unidad** de 3× el máximo semanal histórico en los límites superiores (evita que la cola log del ARIMA explote en horizontes largos).

**Resultados de validación (WIS medio, menor es mejor):**

| Modelo | WIS (UF) | Cobertura IC50 | Cobertura IC95 |
| :--- | :---: | :---: | :---: |
| AutoARIMA | 3191 | 53% | 98% |
| Climatológico | 1368 | 43% | 81% |
| XGBoost | 1462 | 37% | 81% |
| **Ensamble (final)** | **1214** | **59%** | **94%** |

A nivel ciudad, el ensamble obtuvo WIS ≈ 114.

**Ejecución del flujo completo:**
```bash
# 1. AutoARIMA + baseline climatológico (reanudable por lotes)
python scripts/run_batch.py --level uf     --max-combos 6
python scripts/run_batch.py --level cities --max-combos 6
# 2. XGBoost cuantílico
python src/train_xgb.py
python src/train_xgb_cities.py
# 3. Ensamble final (submission)
python scripts/build_final_ensemble.py --level uf
python scripts/build_final_ensemble.py --level cities
```

---

## ⏳ 6. Restricción de Uso de Datos (Data Usage Restriction)

Se respeta estrictamente la regla de usar datos **solo hasta la EW25** del año de temporada para predecir desde la EW41 de ese año hasta la EW40 del siguiente. En el código:

* La función `cutoff_date(Y)` devuelve el domingo de la EW25 del año `Y` (vía `epiweeks`), y cada serie se filtra con `s[s.index <= cutoff]` **antes** de ajustar cualquier modelo (`src/train_imdc.py`).
* En el modelo XGBoost, cada ejemplo de entrenamiento se construye con variables conocidas en el origen EW25, y para cada test de validación solo se entrena con temporadas cuyo origen es **anterior** al año objetivo (`d.oy < Y`), evitando cualquier fuga de información futura (`src/train_xgb.py`).
* La señal climatológica de casos se calcula de forma **expandida**, usando únicamente temporadas previas al origen de cada ejemplo.

---

## 📉 7. Incertidumbre Predictiva (Predictive Uncertainty)

Cada modelo produce la mediana y los intervalos 50/80/90/95% requeridos por la plataforma, mediante métodos complementarios:

* **AutoARIMA**: intervalos analíticos a partir del error estándar de predicción, evaluados a los niveles de significancia $\alpha \in \{0.05, 0.10, 0.20, 0.50\}$ y retransformados con `expm1`.
* **XGBoost**: predicción directa de los nueve cuantiles (0.025, 0.05, 0.10, 0.25, 0.50, 0.75, 0.90, 0.975) optimizando la **pérdida pinball**; los cuantiles se ordenan para garantizar monotonía.
* **Climatológico**: cuantiles empíricos por semana epidemiológica.

En el **ensamble**, los cuantiles se combinan linealmente y se aplican garantías de formato: no negatividad (`np.clip(·, 0, None)`), **anidamiento** consistente (`lower_95 ≤ … ≤ pred ≤ … ≤ upper_95`) y el **tope por unidad** en los límites superiores. Una verificación programática confirma cero violaciones de las reglas de la plataforma (fechas domingo continuas, cobertura EW41→EW40, valores ≥ 0, intervalos anidados) para las 164 combinaciones (unidad × test).

---

## 📚 8. Referencias (References)

* Infodengue–Mosqlimate Dengue Challenge 2026 — Instrucciones y Reglas. https://sprint.mosqlimate.org
* Plantilla oficial del reto: https://github.com/Mosqlimate-project/imdc_template_2026
* Bracher, J., Ray, E. L., Gneiting, T., & Reich, N. G. (2021). *Evaluating epidemic forecasts in an interval format.* PLoS Computational Biology, 17(2), e1008618. https://doi.org/10.1371/journal.pcbi.1008618
* Smith, T. G., et al. *pmdarima: ARIMA estimators for Python.* http://alkaline-ml.com/pmdarima/
* Chen, T., & Guestrin, C. (2016). *XGBoost: A Scalable Tree Boosting System.* KDD '16. https://doi.org/10.1145/2939672.2939785

---

## ⚙️ Reproducibilidad y subida

1. Descargar los datos del FTP de Mosqlimate en `data/` (no versionados).
2. Ejecutar el flujo de la Sección 5 para regenerar las predicciones en `outputs/predictions/`.
3. Configurar `.env` (a partir de `.env.example`) con `API_KEY`, `REPOSITORY` y `COMMIT`.
4. Enviar las predicciones a la plataforma:
   ```bash
   python scripts/submit_mosqlient.py --level uf --dry-run   # validar
   python scripts/submit_mosqlient.py --level uf             # subir
   python scripts/submit_mosqlient.py --level cities
   ```

El **dashboard** interactivo (`dashboard/index.html`) permite explorar los datos descriptivos geoespaciales y comparar el pronóstico de cada modelo frente a lo observado.
