<p align="center">
  <img src="img/home_imdc.svg" alt="Sprint Planning" width="800" height="200">
</p>

# 3rd InfoDengue / Mosqlimate Data Challenge (IMDC 2026) - [Nombre de tu Equipo / Team Name]

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

El repositorio está organizado para estructurar la parte predictiva del modelo de la siguiente manera:

* **`src/`**: Contiene los módulos principales de lógica y modelado.
  * **`modelo.py`**: Módulo que maneja la carga de datos, el entrenamiento del modelo predictivo **AutoARIMA** (usando `pmdarima`) y la extracción de múltiples intervalos de confianza.
  * **`pipeline.py`**: Orquestador principal que automatiza el ciclo de carga de datos, ajuste del modelo y exportación del pronóstico formateado.
* **`scripts/`**: Scripts ejecutables para la automatización.
  * **`run_all.py`**: Script de consola que ejecuta el pipeline predictivo completo.
* **`Demo Notebooks/`**: Cuadernos de ejemplo para interactuar con la API de Mosqlimate.
  * **`Python demo.ipynb`**: Ejemplo para subir los pronósticos utilizando `mosqlient` en Python.
  * **`R demo.Rmd`**: Ejemplo de integración con R y `reticulate`.
* **`outputs/`**: Carpeta local de almacenamiento para las predicciones generadas (`predicciones_desafio.csv`), excluida de Git.

---

## 🛠️ 3. Librerías y Dependencias (Libraries and Dependencies)

El proyecto utiliza únicamente las herramientas oficiales especificadas por el desafío:
* **Python (`>=3.10, <3.13`)**
* **`pmdarima`**: Librería para ajuste automatizado de modelos ARIMA con soporte para componentes estacionales.
* **`mosqlient`**: Cliente de API oficial de Mosqlimate para el registro de modelos y envío de predicciones.
* **`epiweeks`**: Gestión de fechas y semanas epidemiológicas.
* **`python-dotenv`**: Carga de variables de entorno y claves de API (.env).
* **`jupyter`**: Para correr cuadernos interactivos y pruebas.

---

## 📊 4. Datos y Variables (Data and Variables)

*(Describe aquí los conjuntos de datos utilizados y la selección de variables:)*
* **Variables utilizadas**: (Ej. casos probables históricos de dengue por semana).
* **Preprocesamiento**: (Ej. agregación semanal, imputación de nulos).
* **Selección**: Especifica cómo se seleccionaron las variables y su relevancia.

---

## 🧠 5. Entrenamiento del Modelo (Model Training)

El modelo predictivo se basa en **AutoARIMA**, configurado para modelar dinámicas estacionales semanales:
* **Algoritmo**: AutoARIMA (ajuste automático de parámetros $p, d, q, P, D, Q$).
* **Configuración del Modelo**:
  * `seasonal = True` con `m = 52` para capturar la estacionalidad anual de 52 semanas epidemiológicas.
  * Búsqueda paso a paso (`stepwise = True`) optimizando el Criterio de Información de Akaike (AIC).
* **Instrucciones de ejecución**:
  El pipeline se ejecuta desde la consola pasándole la ruta del CSV de datos históricos:
  ```bash
  python scripts/run_all.py --input ruta/a/datos_historicos.csv --output outputs
  ```

---

## ⏳ 6. Restricción de Uso de Datos (Data Usage Restriction)

*(Explica aquí cómo garantizaste la regla del desafío de usar datos solo hasta la Semana Epidemiológica 25 (EW 25) para predecir desde la EW 41 del mismo año hasta la EW 40 del año siguiente. Puedes incluir referencias a tu código.)*

---

## 📉 7. Incertidumbre Predictiva (Predictive Uncertainty)

Para estimar los intervalos de confianza requeridos por la plataforma, el modelo utiliza el error estándar de predicción calculado analíticamente por el modelo ARIMA ajustado:
* **Método**: La función predictiva de `pmdarima` calcula el intervalo a partir de diferentes niveles de significancia ($\alpha$):
  * **95%**: $\alpha = 0.05$ $\rightarrow$ Genera `lower_95` y `upper_95`.
  * **90%**: $\alpha = 0.10$ $\rightarrow$ Genera `lower_90` y `upper_90`.
  * **80%**: $\alpha = 0.20$ $\rightarrow$ Genera `lower_80` y `upper_80`.
  * **50%**: $\alpha = 0.50$ $\rightarrow$ Genera `lower_50` y `upper_50`.
* Todos los límites inferiores se truncan en $0$ mediante `np.clip(conf_int, 0, None)` para evitar predicciones de casos negativos inverosímiles.

---

## 📚 8. Referencias (References)

*(Si tu modelo está basado en alguna publicación o manuscrito científico previo, agrega la cita, el DOI y el enlace aquí.)*
