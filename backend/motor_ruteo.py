import time
import math
import heapq
from typing import Dict, Any, List
from shapely.geometry import shape, LineString, Point

# Red vial topológica georreferenciada del Bosquecillo de Pura Pura (La Paz)
NODOS_VIALES_PURA_PURA = {
    1: {"id": 1, "nombre": "Sendero Central Alto", "lat": -16.4810, "lng": -68.1535, "es_refugio": False},
    2: {"id": 2, "nombre": "Cruce Eucaliptos Centro", "lat": -16.4825, "lng": -68.1515, "es_refugio": False},
    3: {"id": 3, "nombre": "Conector Ladera Este", "lat": -16.4840, "lng": -68.1495, "es_refugio": False},
    4: {"id": 4, "nombre": "Desvío Oeste Seguro", "lat": -16.4845, "lng": -68.1545, "es_refugio": False},
    5: {"id": 5, "nombre": "Conector Sur Subestación", "lat": -16.4865, "lng": -68.1520, "es_refugio": False},
    6: {"id": 6, "nombre": "Paso Norte Ladera", "lat": -16.4795, "lng": -68.1480, "es_refugio": False},
    7: {"id": 7, "nombre": "Sendero Noroeste", "lat": -16.4785, "lng": -68.1560, "es_refugio": False},
    101: {"id": 101, "nombre": "Refugio Seguro 1: Estación Central / Av. Vásquez", "lat": -16.4888, "lng": -68.1448, "es_refugio": True},
    102: {"id": 102, "nombre": "Refugio Seguro 2: Explanada Superior Pura Pura", "lat": -16.4755, "lng": -68.1585, "es_refugio": True},
    103: {"id": 103, "nombre": "Refugio Seguro 3: Acceso Puente Ferroviario", "lat": -16.4840, "lng": -68.1432, "es_refugio": True},
}

ARISTAS_VIALES_PURA_PURA = [
    {"id": 1, "u": 1, "v": 2, "longitud_m": 270.0, "pendiente_pct": 12.0},
    {"id": 2, "u": 2, "v": 3, "longitud_m": 275.0, "pendiente_pct": 14.5},
    {"id": 3, "u": 3, "v": 101, "longitud_m": 720.0, "pendiente_pct": 8.0},
    {"id": 4, "u": 3, "v": 103, "longitud_m": 670.0, "pendiente_pct": 6.5},
    {"id": 5, "u": 1, "v": 4, "longitud_m": 410.0, "pendiente_pct": 5.5},
    {"id": 6, "u": 4, "v": 5, "longitud_m": 350.0, "pendiente_pct": 6.0},
    {"id": 7, "u": 5, "v": 101, "longitud_m": 810.0, "pendiente_pct": 4.5},
    {"id": 8, "u": 1, "v": 7, "longitud_m": 385.0, "pendiente_pct": 9.0},
    {"id": 9, "u": 7, "v": 102, "longitud_m": 430.0, "pendiente_pct": 7.5},
    {"id": 10, "u": 2, "v": 6, "longitud_m": 510.0, "pendiente_pct": 18.0},
    {"id": 11, "u": 6, "v": 103, "longitud_m": 715.0, "pendiente_pct": 10.0},
    {"id": 12, "u": 2, "v": 4, "longitud_m": 390.0, "pendiente_pct": 7.0},
]


class MotorRuteoAdaptativo:
    """
    Módulo 3: Enrutador Dinámico Dijkstra One-to-Many (pgRouting / PostGIS).
    Evalúa intersección con el polígono de incendio, pendiente topográfica (%)
    y tiempo estimado de exposición peatonal.
    """

    def obtener_red_vial_geojson(self) -> Dict[str, Any]:
        features = []
        for a in ARISTAS_VIALES_PURA_PURA:
            n_u = NODOS_VIALES_PURA_PURA[a["u"]]
            n_v = NODOS_VIALES_PURA_PURA[a["v"]]
            features.append({
                "type": "Feature",
                "properties": {
                    "id_arista": a["id"],
                    "longitud_m": a["longitud_m"],
                    "pendiente_pct": a["pendiente_pct"]
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": [[n_u["lng"], n_u["lat"]], [n_v["lng"], n_v["lat"]]]
                }
            })
        return {"type": "FeatureCollection", "features": features}

    def snap_to_node_knn(self, lat_usuario: float, lon_usuario: float) -> int:
        """Equivalente al operador KNN (<->) sobre índice GIST de PostGIS."""
        mejor_nodo = 1
        menor_dist = float("inf")
        for id_nodo, n in NODOS_VIALES_PURA_PURA.items():
            dist = math.hypot(n["lat"] - lat_usuario, n["lng"] - lon_usuario)
            if dist < menor_dist:
                menor_dist = dist
                mejor_nodo = id_nodo
        return mejor_nodo

    def calcular_ruta_segura(
        self,
        lat_usuario: float,
        lon_usuario: float,
        geojson_poligono_fuego: Dict[str, Any]
    ) -> Dict[str, Any]:
        t0 = time.perf_counter()
        poligono_fuego = shape(geojson_poligono_fuego)
        bbox_fuego = poligono_fuego.bounds  # (minx, miny, maxx, maxy) para filtro rápido &&

        nodo_origen = self.snap_to_node_knn(lat_usuario, lon_usuario)

        # Construir lista de adyacencia con costos dinámicos en memoria
        grafo: Dict[int, List[Dict[str, Any]]] = {nid: [] for nid in NODOS_VIALES_PURA_PURA}
        aristas_bloqueadas_por_fuego = []

        for a in ARISTAS_VIALES_PURA_PURA:
            u, v = a["u"], a["v"]
            nu, nv = NODOS_VIALES_PURA_PURA[u], NODOS_VIALES_PURA_PURA[v]
            linea_arista = LineString([(nu["lng"], nu["lat"]), (nv["lng"], nv["lat"])])

            # Costo base ponderado por longitud y pendiente topográfica (Función de Tobler adaptada)
            costo_seguridad_base = a["longitud_m"] * (1.0 + (a["pendiente_pct"] / 15.0))

            # Pre-filtro por Bounding Box (&&) seguido de intersección exacta (ST_Intersects)
            minx, miny, maxx, maxy = linea_arista.bounds
            bbox_overlap = not (maxx < bbox_fuego[0] or minx > bbox_fuego[2] or maxy < bbox_fuego[1] or miny > bbox_fuego[3])
            intersecta_fuego = bbox_overlap and linea_arista.intersects(poligono_fuego)

            if intersecta_fuego:
                costo_dinamico = costo_seguridad_base * 100000.0
                aristas_bloqueadas_por_fuego.append(a["id"])
            else:
                costo_dinamico = costo_seguridad_base

            datos_arista = {
                "id_arista": a["id"],
                "costo": costo_dinamico,
                "longitud_m": a["longitud_m"],
                "pendiente_pct": a["pendiente_pct"],
                "en_fuego": intersecta_fuego
            }
            # Grafo no dirigido (directed := false para evacuación peatonal)
            grafo[u].append({"vecino": v, **datos_arista})
            grafo[v].append({"vecino": u, **datos_arista})

        # Algoritmo de Dijkstra One-to-Many hacia todos los nodos con es_refugio = True
        distancias = {nid: float("inf") for nid in NODOS_VIALES_PURA_PURA}
        predecesores = {nid: None for nid in NODOS_VIALES_PURA_PURA}
        distancias[nodo_origen] = 0.0

        cola_prioridad = [(0.0, nodo_origen)]
        while cola_prioridad:
            costo_actual, u = heapq.heappop(cola_prioridad)
            if costo_actual > distancias[u]:
                continue
            for arista in grafo[u]:
                v = arista["vecino"]
                nuevo_costo = costo_actual + arista["costo"]
                if nuevo_costo < distancias[v]:
                    distancias[v] = nuevo_costo
                    predecesores[v] = (u, arista)
                    heapq.heappush(cola_prioridad, (nuevo_costo, v))

        # Seleccionar el Refugio Seguro óptimo (menor costo de impedancia total)
        refugios_ids = [nid for nid, n in NODOS_VIALES_PURA_PURA.items() if n["es_refugio"]]
        mejor_refugio_id = min(refugios_ids, key=lambda rid: distancias[rid])

        # Reconstruir la ruta óptima y auditar métricas físicas
        nodos_ruta = []
        aristas_usadas = []
        curr = mejor_refugio_id
        while curr is not None:
            nodos_ruta.append(curr)
            pred = predecesores[curr]
            if pred is not None:
                aristas_usadas.append(pred[1])
                curr = pred[0]
            else:
                curr = None
        nodos_ruta.reverse()
        aristas_usadas.reverse()

        # Construir polilínea GeoJSON desde la posición GPS del ciudadano pasando por los nodos viales
        coordenadas_ruta = [[lon_usuario, lat_usuario]]
        for nid in nodos_ruta:
            nodo_obj = NODOS_VIALES_PURA_PURA[nid]
            coordenadas_ruta.append([nodo_obj["lng"], nodo_obj["lat"]])

        distancia_total_m = round(sum(a["longitud_m"] for a in aristas_usadas), 1)
        pendiente_max_pct = round(max((a["pendiente_pct"] for a in aristas_usadas), default=0.0), 1)
        pendiente_media_pct = round(
            sum(a["pendiente_pct"] for a in aristas_usadas) / max(1, len(aristas_usadas)), 1
        )
        tramos_en_fuego = sum(1 for a in aristas_usadas if a["en_fuego"])

        # Velocidad peatonal ajustada por pendiente en ladera (promedio 1.25 m/s en terreno plano)
        velocidad_peatonal_ms = max(0.55, 1.25 * (1.0 - (pendiente_media_pct / 45.0)))
        tiempo_exposicion_seg = round(distancia_total_m / velocidad_peatonal_ms, 1)
        tiempo_ruteo_ms = round((time.perf_counter() - t0) * 1000, 2)

        return {
            "nodo_origen_id": nodo_origen,
            "nodo_refugio_destino": NODOS_VIALES_PURA_PURA[mejor_refugio_id],
            "distancia_total_metros": distancia_total_m,
            "pendiente_media_porcentaje": pendiente_media_pct,
            "pendiente_maxima_porcentaje": pendiente_max_pct,
            "tiempo_exposicion_estimado_seg": tiempo_exposicion_seg,
            "tiempo_exposicion_minutos": round(tiempo_exposicion_seg / 60.0, 1),
            "aristas_bloqueadas_por_fuego": aristas_bloqueadas_por_fuego,
            "tramos_ruta_en_fuego": tramos_en_fuego,
            "ruta_evita_zona_amenaza": tramos_en_fuego == 0,
            "tiempo_calculo_ruteo_ms": tiempo_ruteo_ms,
            "geojson_ruta_segura": {
                "type": "Feature",
                "properties": {
                    "refugio_destino": NODOS_VIALES_PURA_PURA[mejor_refugio_id]["nombre"],
                    "distancia_m": distancia_total_m,
                    "tiempo_exposicion_seg": tiempo_exposicion_seg
                },
                "geometry": {
                    "type": "LineString",
                    "coordinates": coordenadas_ruta
                }
            }
        }
