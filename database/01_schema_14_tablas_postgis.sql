-- ============================================================================
-- PROYECTO DE GRADO - INGENIERÍA INFORMÁTICA UMSA
-- ESTUDIANTE: GIANN KALEF LEDEZMA RAMOS
-- SCRIPT DDL: 14 TABLAS GEOESPACIALES (POSTGIS + PGROUTING) + DATOS SEMILLA
-- ============================================================================

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS pgrouting;

-- ============================================================================
-- DOMINIO A: CATÁLOGO ESPACIAL Y PARAMETRIZACIÓN DEL MOTOR MATEMÁTICO
-- ============================================================================

-- 1. zonas_estudio
CREATE TABLE zonas_estudio (
    id SERIAL PRIMARY KEY,
    nombre_zona VARCHAR(120) NOT NULL,
    latitud_centro DOUBLE PRECISION NOT NULL,
    longitud_centro DOUBLE PRECISION NOT NULL,
    resolucion_pixel_metros DOUBLE PRECISION NOT NULL DEFAULT 10.0,
    geom_bbox GEOMETRY(Polygon, 4326) NOT NULL,
    ruta_archivo_dem_tif VARCHAR(255) NOT NULL,
    ruta_archivo_cobertura_tif VARCHAR(255) NOT NULL
);
CREATE INDEX idx_zonas_estudio_bbox ON zonas_estudio USING GIST (geom_bbox);

-- 2. tipos_cobertura_suelo
CREATE TABLE tipos_cobertura_suelo (
    id SERIAL PRIMARY KEY,
    valor_pixel_raster INTEGER UNIQUE NOT NULL,
    descripcion VARCHAR(100) NOT NULL,
    factor_inflamabilidad DOUBLE PRECISION NOT NULL CHECK (factor_inflamabilidad >= 0.0 AND factor_inflamabilidad <= 2.0),
    color_renderizado_hex VARCHAR(7) NOT NULL
);

-- 3. parametros_calibracion_automata
CREATE TABLE parametros_calibracion_automata (
    id SERIAL PRIMARY KEY,
    nombre_perfil VARCHAR(100) NOT NULL,
    peso_gradiente_pendiente DOUBLE PRECISION NOT NULL DEFAULT 0.45,
    peso_vector_viento DOUBLE PRECISION NOT NULL DEFAULT 0.35,
    umbral_indice_ignicion DOUBLE PRECISION NOT NULL DEFAULT 0.65,
    iteraciones_maximas INTEGER NOT NULL DEFAULT 45,
    es_perfil_activo BOOLEAN NOT NULL DEFAULT FALSE
);

-- 4. infraestructuras_vulnerables
CREATE TABLE infraestructuras_vulnerables (
    id SERIAL PRIMARY KEY,
    zona_id INTEGER NOT NULL REFERENCES zonas_estudio(id) ON DELETE CASCADE,
    tipo_infraestructura VARCHAR(60) NOT NULL,
    nombre_identificador VARCHAR(150) NOT NULL,
    geom_punto GEOMETRY(Point, 4326) NOT NULL
);
CREATE INDEX idx_infraestructuras_geom ON infraestructuras_vulnerables USING GIST (geom_punto);

-- ============================================================================
-- DOMINIO B: ENTORNO DE SIMULACIÓN PARAMÉTRICA E INGESTA CLIMÁTICA
-- ============================================================================

-- 5. cache_telemetria_openweather
CREATE TABLE cache_telemetria_openweather (
    id SERIAL PRIMARY KEY,
    zona_id INTEGER NOT NULL REFERENCES zonas_estudio(id) ON DELETE CASCADE,
    velocidad_viento_kmh DOUBLE PRECISION NOT NULL,
    azimut_viento_grados DOUBLE PRECISION NOT NULL,
    humedad_relativa_porcentaje DOUBLE PRECISION NOT NULL,
    temperatura_celsius DOUBLE PRECISION NOT NULL,
    timestamp_sincronizacion TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 6. escenarios_simulacion
CREATE TABLE escenarios_simulacion (
    id SERIAL PRIMARY KEY,
    zona_id INTEGER NOT NULL REFERENCES zonas_estudio(id) ON DELETE CASCADE,
    parametro_calibracion_id INTEGER NOT NULL REFERENCES parametros_calibracion_automata(id),
    origen_disparo VARCHAR(30) NOT NULL CHECK (origen_disparo IN ('WEB_DASHBOARD', 'APP_MOVIL')),
    titulo_simulacion VARCHAR(150) NOT NULL,
    area_afectada_hectareas DOUBLE PRECISION NOT NULL DEFAULT 0.0,
    total_infraestructuras_afectadas INTEGER NOT NULL DEFAULT 0,
    tiempo_ejecucion_ms INTEGER NOT NULL DEFAULT 0,
    es_escenario_activo BOOLEAN NOT NULL DEFAULT TRUE,
    timestamp_ejecucion TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    poligono_riesgo_generado GEOMETRY(MultiPolygon, 4326)
);
CREATE INDEX idx_escenarios_poligono ON escenarios_simulacion USING GIST (poligono_riesgo_generado);

-- 7. condiciones_meteorologicas
CREATE TABLE condiciones_meteorologicas (
    id SERIAL PRIMARY KEY,
    escenario_id INTEGER UNIQUE NOT NULL REFERENCES escenarios_simulacion(id) ON DELETE CASCADE,
    fuente_datos VARCHAR(30) NOT NULL CHECK (fuente_datos IN ('OPENWEATHER_API', 'MANUAL_SIMULADOR')),
    velocidad_viento_kmh DOUBLE PRECISION NOT NULL,
    azimut_viento_grados DOUBLE PRECISION NOT NULL,
    humedad_relativa_porcentaje DOUBLE PRECISION NOT NULL
);

-- 8. barreras_tacticas_mitigacion
CREATE TABLE barreras_tacticas_mitigacion (
    id SERIAL PRIMARY KEY,
    zona_id INTEGER NOT NULL REFERENCES zonas_estudio(id) ON DELETE CASCADE,
    escenario_creacion_id INTEGER REFERENCES escenarios_simulacion(id) ON DELETE SET NULL,
    tipo_barrera VARCHAR(50) NOT NULL DEFAULT 'Cortafuegos Artificial',
    factor_reduccion_fuego DOUBLE PRECISION NOT NULL DEFAULT 1.0,
    esta_activa BOOLEAN NOT NULL DEFAULT TRUE,
    geom_linea GEOMETRY(LineString, 4326) NOT NULL
);
CREATE INDEX idx_barreras_geom ON barreras_tacticas_mitigacion USING GIST (geom_linea);

-- 9. puntos_ignicion_simulados
CREATE TABLE puntos_ignicion_simulados (
    id SERIAL PRIMARY KEY,
    escenario_id INTEGER NOT NULL REFERENCES escenarios_simulacion(id) ON DELETE CASCADE,
    fila_matriz_raster INTEGER NOT NULL,
    columna_matriz_raster INTEGER NOT NULL,
    geom_foco GEOMETRY(Point, 4326) NOT NULL
);

-- ============================================================================
-- DOMINIO C: TELEMETRÍA MÓVIL CIUDADANA (THIN CLIENT)
-- ============================================================================

-- 10. sesiones_dispositivos
CREATE TABLE sesiones_dispositivos (
    id_sesion_uuid UUID PRIMARY KEY,
    fecha_registro TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    sistema_operativo VARCHAR(30) NOT NULL DEFAULT 'Android',
    ultimo_reporte_timestamp TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- 11. reportes_emergencia_ciudadana
CREATE TABLE reportes_emergencia_ciudadana (
    id SERIAL PRIMARY KEY,
    sesion_uuid UUID NOT NULL REFERENCES sesiones_dispositivos(id_sesion_uuid) ON DELETE CASCADE,
    escenario_asociado_id INTEGER REFERENCES escenarios_simulacion(id) ON DELETE SET NULL,
    geom_usuario_gps GEOMETRY(Point, 4326) NOT NULL,
    geom_foco_marcado GEOMETRY(Point, 4326) NOT NULL,
    timestamp_reporte TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- ============================================================================
-- DOMINIO D: GRAFOS VIALES Y ENRUTAMIENTO DINÁMICO (PGROUTING)
-- ============================================================================

-- 12. nodos_viales_osm
CREATE TABLE nodos_viales_osm (
    id_nodo BIGSERIAL PRIMARY KEY,
    zona_id INTEGER NOT NULL REFERENCES zonas_estudio(id) ON DELETE CASCADE,
    geom_punto GEOMETRY(Point, 4326) NOT NULL,
    es_zona_refugio_segura BOOLEAN NOT NULL DEFAULT FALSE
);
CREATE INDEX idx_nodos_viales_geom ON nodos_viales_osm USING GIST (geom_punto);

-- 13. aristas_viales_osm
CREATE TABLE aristas_viales_osm (
    id_arista BIGSERIAL PRIMARY KEY,
    zona_id INTEGER NOT NULL REFERENCES zonas_estudio(id) ON DELETE CASCADE,
    origen_nodo_id BIGINT NOT NULL REFERENCES nodos_viales_osm(id_nodo) ON DELETE CASCADE,
    destino_nodo_id BIGINT NOT NULL REFERENCES nodos_viales_osm(id_nodo) ON DELETE CASCADE,
    longitud_metros DOUBLE PRECISION NOT NULL,
    pendiente_porcentaje DOUBLE PRECISION NOT NULL DEFAULT 5.0,
    costo_seguridad_base DOUBLE PRECISION NOT NULL,
    geom_linea GEOMETRY(LineString, 4326) NOT NULL
);
CREATE INDEX idx_aristas_viales_geom ON aristas_viales_osm USING GIST (geom_linea);

-- 14. rutas_evacuacion_calculadas
CREATE TABLE rutas_evacuacion_calculadas (
    id SERIAL PRIMARY KEY,
    reporte_id INTEGER REFERENCES reportes_emergencia_ciudadana(id) ON DELETE CASCADE,
    escenario_id INTEGER NOT NULL REFERENCES escenarios_simulacion(id) ON DELETE CASCADE,
    nodo_origen_id BIGINT NOT NULL REFERENCES nodos_viales_osm(id_nodo),
    nodo_refugio_destino_id BIGINT NOT NULL REFERENCES nodos_viales_osm(id_nodo),
    distancia_total_metros DOUBLE PRECISION NOT NULL,
    tiempo_exposicion_estimado_seg DOUBLE PRECISION NOT NULL,
    tiempo_calculo_ruteo_ms INTEGER NOT NULL,
    geom_ruta_segura GEOMETRY(LineString, 4326) NOT NULL
);

-- ============================================================================
-- CARGA INICIAL VERIFICABLE (ÁREA PILOTO: BOSQUECILLO DE PURA PURA - LA PAZ)
-- ============================================================================

INSERT INTO zonas_estudio (nombre_zona, latitud_centro, longitud_centro, resolucion_pixel_metros, geom_bbox, ruta_archivo_dem_tif, ruta_archivo_cobertura_tif)
VALUES (
    'Bosquecillo de Pura Pura (La Paz)',
    -16.4815,
    -68.1520,
    10.0,
    ST_GeomFromText('POLYGON((-68.1620 -16.4900, -68.1420 -16.4900, -68.1420 -16.4720, -68.1620 -16.4720, -68.1620 -16.4900))', 4326),
    'rasters/purapura_dem_10m.tif',
    'rasters/purapura_cobertura_10m.tif'
);

INSERT INTO tipos_cobertura_suelo (valor_pixel_raster, descripcion, factor_inflamabilidad, color_renderizado_hex) VALUES
(0, 'Suelo Desnudo / Roca / Cortafuegos', 0.00, '#64748b'),
(1, 'Pastizal Seco de Ladera (Alta Inflamabilidad)', 1.25, '#eab308'),
(2, 'Bosque Denso de Eucalipto (Pura Pura)', 1.50, '#15803d'),
(3, 'Matorral Nativo / Arbustivo Semi-húmedo', 0.85, '#84cc16');

INSERT INTO parametros_calibracion_automata (nombre_perfil, peso_gradiente_pendiente, peso_vector_viento, umbral_indice_ignicion, iteraciones_maximas, es_perfil_activo)
VALUES ('Perfil Determinista Estándar - Laderas La Paz', 0.50, 0.40, 0.62, 45, TRUE);

INSERT INTO infraestructuras_vulnerables (zona_id, tipo_infraestructura, nombre_identificador, geom_punto) VALUES
(1, 'Educación', 'Unidad Educativa Fiscal Pura Pura', ST_SetSRID(ST_MakePoint(-68.1482, -16.4851), 4326)),
(1, 'Salud', 'Centro de Salud Integral Pura Pura', ST_SetSRID(ST_MakePoint(-68.1465, -16.4868), 4326)),
(1, 'Energía / Servicios', 'Subestación Eléctrica Línea Roja Teleférico', ST_SetSRID(ST_MakePoint(-68.1505, -16.4882), 4326)),
(1, 'Recreación / Guardaparques', 'Puesto de Control Guardaparques Municipal', ST_SetSRID(ST_MakePoint(-68.1548, -16.4802), 4326)),
(1, 'Vivienda Alta Densidad', 'Conjunto Vecinal Ladera Este Pura Pura', ST_SetSRID(ST_MakePoint(-68.1455, -16.4795), 4326));

INSERT INTO cache_telemetria_openweather (zona_id, velocidad_viento_kmh, azimut_viento_grados, humedad_relativa_porcentaje, temperatura_celsius)
VALUES (1, 22.5, 135.0, 28.0, 19.5);