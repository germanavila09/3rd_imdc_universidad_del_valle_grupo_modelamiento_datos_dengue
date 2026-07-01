-- Esquema de Base de Datos para Datos Climatológicos del IDEAM

-- 1. Tabla de Estaciones Climatológicas
CREATE TABLE IF NOT EXISTS stations (
    codigoestacion VARCHAR(50) PRIMARY KEY,
    nombreestacion VARCHAR(250),
    departamento VARCHAR(150),
    municipio VARCHAR(150),
    zonahidrografica VARCHAR(250),
    latitud NUMERIC(12, 8),
    longitud NUMERIC(12, 8)
);

-- 2. Tabla para Observaciones de Precipitación
CREATE TABLE IF NOT EXISTS precipitation (
    codigoestacion VARCHAR(50) REFERENCES stations(codigoestacion),
    fechaobservacion TIMESTAMP,
    valorobservado NUMERIC(12, 4),
    PRIMARY KEY (codigoestacion, fechaobservacion)
);

-- 3. Tabla para Observaciones de Humedad
CREATE TABLE IF NOT EXISTS humidity (
    codigoestacion VARCHAR(50) REFERENCES stations(codigoestacion),
    fechaobservacion TIMESTAMP,
    valorobservado NUMERIC(12, 4),
    PRIMARY KEY (codigoestacion, fechaobservacion)
);

-- 4. Tabla para Observaciones de Temperatura Máxima
CREATE TABLE IF NOT EXISTS max_temperature (
    codigoestacion VARCHAR(50) REFERENCES stations(codigoestacion),
    fechaobservacion TIMESTAMP,
    valorobservado NUMERIC(12, 4),
    PRIMARY KEY (codigoestacion, fechaobservacion)
);

-- 5. Tabla para Observaciones de Temperatura Mínima
CREATE TABLE IF NOT EXISTS min_temperature (
    codigoestacion VARCHAR(50) REFERENCES stations(codigoestacion),
    fechaobservacion TIMESTAMP,
    valorobservado NUMERIC(12, 4),
    PRIMARY KEY (codigoestacion, fechaobservacion)
);

-- 6. Tabla para Índices Consolidados Mensuales
CREATE TABLE IF NOT EXISTS monthly_climate_indices (
    codigoestacion VARCHAR(50) REFERENCES stations(codigoestacion),
    year INTEGER,
    month INTEGER,
    total_precipitation NUMERIC(12, 4),
    mean_max_temperature NUMERIC(8, 3),
    mean_min_temperature NUMERIC(8, 3),
    mean_max_humidity NUMERIC(8, 3),
    mean_min_humidity NUMERIC(8, 3),
    PRIMARY KEY (codigoestacion, year, month)
);

-- Creación de Índices para optimizar consultas temporales y de agregación
CREATE INDEX IF NOT EXISTS idx_precipitation_fecha ON precipitation(fechaobservacion);
CREATE INDEX IF NOT EXISTS idx_humidity_fecha ON humidity(fechaobservacion);
CREATE INDEX IF NOT EXISTS idx_max_temp_fecha ON max_temperature(fechaobservacion);
CREATE INDEX IF NOT EXISTS idx_min_temp_fecha ON min_temperature(fechaobservacion);
