-- ============================================================================
-- MÓDULO 3 (SEMANA 3): RED VIAL OSM PURA PURA Y ENRUTAMIENTO DINÁMICO PGROUTING
-- ESTUDIANTE: GIANN KALEF LEDEZMA RAMOS
-- ============================================================================

-- 1. Insertar Nodos Viales y Refugios Seguros en Bosquecillo de Pura Pura (zona_id = 1)
INSERT INTO nodos_viales_osm (id_nodo, zona_id, geom_punto, es_zona_refugio_segura) VALUES
(1, 1, ST_SetSRID(ST_MakePoint(-68.1535, -16.4810), 4326), FALSE), -- Sendero Central Alto
(2, 1, ST_SetSRID(ST_MakePoint(-68.1515, -16.4825), 4326), FALSE), -- Cruce Eucaliptos Centro
(3, 1, ST_SetSRID(ST_MakePoint(-68.1495, -16.4840), 4326), FALSE), -- Conector Ladera Este
(4, 1, ST_SetSRID(ST_MakePoint(-68.1545, -16.4845), 4326), FALSE), -- Desvío Oeste Seguro (Baja pendiente)
(5, 1, ST_SetSRID(ST_MakePoint(-68.1520, -16.4865), 4326), FALSE), -- Conector Sur vía Subestación
(6, 1, ST_SetSRID(ST_MakePoint(-68.1480, -16.4795), 4326), FALSE), -- Paso Norte Ladera
(7, 1, ST_SetSRID(ST_MakePoint(-68.1560, -16.4785), 4326), FALSE), -- Sendero Noroeste
(101, 1, ST_SetSRID(ST_MakePoint(-68.1448, -16.4888), 4326), TRUE), -- REFUGIO 1: Av. Vásquez / Estación Central
(102, 1, ST_SetSRID(ST_MakePoint(-68.1585, -16.4755), 4326), TRUE), -- REFUGIO 2: Explanada Superior Pura Pura
(103, 1, ST_SetSRID(ST_MakePoint(-68.1432, -16.4840), 4326), TRUE); -- REFUGIO 3: Acceso Puente Ferroviario

-- 2. Insertar Aristas Viales ponderadas por Longitud y Pendiente Topográfica (%)
-- Fórmula costo_seguridad_base = longitud_metros * (1 + (pendiente_porcentaje / 15.0))
INSERT INTO aristas_viales_osm (id_arista, zona_id, origen_nodo_id, destino_nodo_id, longitud_metros, pendiente_porcentaje, costo_seguridad_base, geom_linea) VALUES
(1, 1, 1, 2, 270.0, 12.0, 486.0, ST_GeomFromText('LINESTRING(-68.1535 -16.4810, -68.1515 -16.4825)', 4326)),
(2, 1, 2, 3, 275.0, 14.5, 540.8, ST_GeomFromText('LINESTRING(-68.1515 -16.4825, -68.1495 -16.4840)', 4326)),
(3, 1, 3, 101, 720.0, 8.0, 1104.0, ST_GeomFromText('LINESTRING(-68.1495 -16.4840, -68.1448 -16.4888)', 4326)),
(4, 1, 3, 103, 670.0, 6.5, 960.3, ST_GeomFromText('LINESTRING(-68.1495 -16.4840, -68.1432 -16.4840)', 4326)),
(5, 1, 1, 4, 410.0, 5.5, 560.3, ST_GeomFromText('LINESTRING(-68.1535 -16.4810, -68.1545 -16.4845)', 4326)),
(6, 1, 4, 5, 350.0, 6.0, 490.0, ST_GeomFromText('LINESTRING(-68.1545 -16.4845, -68.1520 -16.4865)', 4326)),
(7, 1, 5, 101, 810.0, 4.5, 1053.0, ST_GeomFromText('LINESTRING(-68.1520 -16.4865, -68.1448 -16.4888)', 4326)),
(8, 1, 1, 7, 385.0, 9.0, 616.0, ST_GeomFromText('LINESTRING(-68.1535 -16.4810, -68.1560 -16.4785)', 4326)),
(9, 1, 7, 102, 430.0, 7.5, 645.0, ST_GeomFromText('LINESTRING(-68.1560 -16.4785, -68.1585 -16.4755)', 4326)),
(10, 1, 2, 6, 510.0, 18.0, 1122.0, ST_GeomFromText('LINESTRING(-68.1515 -16.4825, -68.1480 -16.4795)', 4326)),
(11, 1, 6, 103, 715.0, 10.0, 1191.6, ST_GeomFromText('LINESTRING(-68.1480 -16.4795, -68.1432 -16.4840)', 4326)),
(12, 1, 2, 4, 390.0, 7.0, 572.0, ST_GeomFromText('LINESTRING(-68.1515 -16.4825, -68.1545 -16.4845)', 4326));

-- 3. Función SQL Dinámica con Snap-to-Node KNN (<->), Bounding Box (&&) y pgr_dijkstra
CREATE OR REPLACE FUNCTION calcular_ruta_evacuacion_adaptativa(
    p_lat_usuario DOUBLE PRECISION,
    p_lon_usuario DOUBLE PRECISION,
    p_escenario_id INTEGER
)
RETURNS TABLE (
    seq INTEGER,
    nodo_id BIGINT,
    arista_id BIGINT,
    costo_tramo DOUBLE PRECISION,
    longitud_metros DOUBLE PRECISION,
    pendiente_pct DOUBLE PRECISION,
    geom_tramo GEOMETRY
) AS $$
DECLARE
    v_nodo_origen BIGINT;
    v_sql_dinamico TEXT;
BEGIN
    -- Paso 1: Búsqueda espacial KNN (<->) sobre índice GIST para hallar el nodo vial más cercano al ciudadano
    SELECT n.id_nodo INTO v_nodo_origen
    FROM nodos_viales_osm n
    ORDER BY n.geom_punto <-> ST_SetSRID(ST_MakePoint(p_lon_usuario, p_lat_usuario), 4326)
    LIMIT 1;

    -- Paso 2: Subconsulta dinámica inyectada en pgr_dijkstra (One-to-Many no dirigido)
    -- Penaliza en memoria con factor 100000 las aristas cuyo Bounding Box (&&) e intersección toquen el fuego
    v_sql_dinamico := format(
        'SELECT a.id_arista AS id,
                a.origen_nodo_id AS source,
                a.destino_nodo_id AS target,
                CASE
                    WHEN e.poligono_riesgo_generado IS NOT NULL
                         AND a.geom_linea && e.poligono_riesgo_generado
                         AND ST_Intersects(a.geom_linea, e.poligono_riesgo_generado)
                    THEN a.costo_seguridad_base * 100000.0
                    ELSE a.costo_seguridad_base
                END AS cost,
                CASE
                    WHEN e.poligono_riesgo_generado IS NOT NULL
                         AND a.geom_linea && e.poligono_riesgo_generado
                         AND ST_Intersects(a.geom_linea, e.poligono_riesgo_generado)
                    THEN a.costo_seguridad_base * 100000.0
                    ELSE a.costo_seguridad_base
                END AS reverse_cost
         FROM aristas_viales_osm a
         LEFT JOIN escenarios_simulacion e ON e.id = %L',
        p_escenario_id
    );

    -- Paso 3: Retornar la ruta hacia el refugio seguro de menor impedancia acumulada
    RETURN QUERY
    WITH rutas_dijkstra AS (
        SELECT * FROM pgr_dijkstra(
            v_sql_dinamico,
            v_nodo_origen,
            ARRAY(SELECT id_nodo FROM nodos_viales_osm WHERE es_zona_refugio_segura = TRUE),
            directed := FALSE
        )
    ),
    mejor_refugio AS (
        SELECT end_vid
        FROM rutas_dijkstra
        WHERE edge = -1
        ORDER BY agg_cost ASC
        LIMIT 1
    )
    SELECT r.seq,
           r.node AS nodo_id,
           r.edge AS arista_id,
           r.cost AS costo_tramo,
           COALESCE(a.longitud_metros, 0.0) AS longitud_metros,
           COALESCE(a.pendiente_porcentaje, 0.0) AS pendiente_pct,
           a.geom_linea AS geom_tramo
    FROM rutas_dijkstra r
    JOIN mejor_refugio m ON r.end_vid = m.end_vid
    LEFT JOIN aristas_viales_osm a ON a.id_arista = r.edge
    WHERE r.edge <> -1
    ORDER BY r.seq;
END;
$$ LANGUAGE plpgsql;