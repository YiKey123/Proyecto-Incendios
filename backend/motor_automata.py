import os
import time
import math
from typing import List, Dict, Any, Tuple
import numpy as np
from numba import njit, prange
import rasterio
from rasterio.transform import from_bounds, rowcol
from rasterio.features import rasterize, shapes
from shapely.geometry import shape, LineString, Point, mapping
from shapely.ops import unary_union

# ============================================================================
# ESTADOS DEL AUTÓMATA CELULAR DETERMINISTA
# 0: Barrera / No inflamable (Roca, Cortafuegos, Urbano)
# 1: Combustible Susceptible
# 2: En Ignición (Ardiendo activamente en la iteración t)
# 3: Consumido / Ceniza
# ============================================================================

@njit(parallel=True, fastmath=True)
def kernel_automata_anisotropico(
    estado_actual: np.ndarray,
    dem: np.ndarray,
    factor_combustible: np.ndarray,
    resolucion_metros: float,
    vel_viento_kmh: float,
    azimut_viento_rad: float,
    humedad_pct: float,
    peso_pendiente: float,
    peso_viento: float,
    umbral_ignicion: float,
    iteraciones: int
) -> Tuple[np.ndarray, np.ndarray]:
    """
    Fase 3: Kernel compilado JIT a código máquina con Numba.
    Aplica Doble Buffering (estado_t y estado_t1) sobre vecindad de Moore (8 celdas).
    Retorna la matriz de estados finales y la matriz del paso de ignición.
    """
    filas, cols = estado_actual.shape
    estado_t = estado_actual.copy()
    estado_t1 = estado_actual.copy()
    mapa_iteracion = np.zeros((filas, cols), dtype=np.int16)

    # Desplazamientos de la vecindad de Moore (8 vecinos: N, NE, E, SE, S, SO, O, NO)
    dr = np.array([-1, -1, -1,  0, 0,  1, 1, 1], dtype=np.int32)
    dc = np.array([-1,  0,  1, -1, 1, -1, 0, 1], dtype=np.int32)

    # Vector unitario hacia donde empuja el viento (Azimut geográfico: 0=Norte, 90=Este)
    viento_dx = math.sin(azimut_viento_rad)
    viento_dy = -math.cos(azimut_viento_rad) # En matriz raster, fila disminuye hacia el Norte

    # Factor de amortiguación por humedad relativa
    factor_humedad = max(0.25, 1.0 - (humedad_pct / 130.0))
    vel_viento_norm = min(2.0, vel_viento_kmh / 30.0)

    for paso in range(1, iteraciones + 1):
        # Evaluación paralela libre de condiciones de carrera (Enfoque Pull)
        for r in prange(1, filas - 1):
            for c in range(1, cols - 1):
                estado_celda = estado_t[r, c]

                # Si está ardiendo en t, pasa a consumido en t+1
                if estado_celda == 2:
                    estado_t1[r, c] = 3
                    continue

                # Si es barrera (0) o ya consumido (3), permanece inalterado
                if estado_celda != 1:
                    estado_t1[r, c] = estado_celda
                    continue

                # Si la celda es Susceptible (1), evaluamos transferencia de calor desde sus 8 vecinos
                 inflamabilidad = factor_combustible[r, c]
                if inflamabilidad <= 0.05:
                    estado_t1[r, c] = 0
                    continue

                indice_calor_max = 0.0
                z_destino = dem[r, c]

                for k in range(8):
                    nr = r + dr[k]
                    nc = c + dc[k]

                    # Solo recibe calor de vecinos que están en estado 2 (En Ignición)
                    if estado_t[nr, nc] == 2:
                        # Vector desde el vecino ardiente (nr, nc) hacia la celda susceptible (r, c)
                        vec_y = float(r - nr)
                        vec_x = float(c - nc)
                        dist_celdas = math.sqrt(vec_x * vec_x + vec_y * vec_y)
                        dist_metros = dist_celdas * resolucion_metros

                        # 1. Gradiente direccional de pendiente topográfica
                        z_origen = dem[nr, nc]
                        delta_z = z_destino - z_origen
                        angulo_pendiente = math.atan(delta_z / dist_metros)
                        # El fuego sube pendientes exponencialmente más rápido de lo que baja
                        aporte_pendiente = peso_pendiente * math.sin(angulo_pendiente) * 2.2

                        # 2. Alineación direccional con el vector del viento
                        dir_x = vec_x / dist_celdas
                        dir_y = vec_y / dist_celdas
                        alineacion_viento = (dir_x * viento_dx) + (dir_y * viento_dy)
                        aporte_viento = peso_viento * vel_viento_norm * alineacion_viento

                        # 3. Atenuación geométrica en diagonales (1 / sqrt(2))
                        atenuacion_diagonal = 1.0 / (dist_celdas ** 0.45)

                        # Índice físico determinista acumulado
                        indice_vecino = (
                            (0.42 * inflamabilidad + aporte_pendiente + aporte_viento)
                            * factor_humedad
                            * atenuacion_diagonal
                        )

                        if indice_vecino > indice_calor_max:
                            indice_calor_max = indice_vecino

                # Regla de transición determinista
                if indice_calor_max >= umbral_ignicion:
                    estado_t1[r, c] = 2
                    mapa_iteracion[r, c] = paso
                else:
                    estado_t1[r, c] = 1

        # Intercambio de buffers (estado_t <- estado_t1) para la siguiente iteración
        for r in prange(filas):
            for c in range(cols):
                estado_t[r, c] = estado_t1[r, c]

    return estado_t, mapa_iteracion


class MotorSimulacionSingleton:
    """
    Gestiona las Fases 1, 2, 3 y 4 en memoria RAM (Patrón Singleton).
    """
    _instancia = None

    def __new__(cls):
        if cls._instancia is None:
            cls._instancia = super(MotorSimulacionSingleton, cls).__new__(cls)
            cls._instancia._inicializado = False
        return cls._instancia

    def inicializar_en_ram(self, ruta_dem: str = "rasters/purapura_dem_10m.tif", ruta_cob: str = "rasters/purapura_cobertura_10m.tif"):
        if self._inicializado:
            return

        # Bounding Box del Área Piloto: Bosquecillo de Pura Pura (La Paz)
        self.west, self.south, self.east, self.north = -68.1620, -16.4900, -68.1420, -16.4720
        self.width, self.height = 300, 300
        self.resolucion_metros = 10.0

        if os.path.exists(ruta_dem) and os.path.exists(ruta_cob):
            with rasterio.open(ruta_dem) as src_dem:
                self.dem_ram = src_dem.read(1).astype(np.float32)
                self.transform = src_dem.transform
            with rasterio.open(ruta_cob) as src_cob:
                cobertura_codigos = src_cob.read(1).astype(np.uint8)
        else:
            # Respaldo automático en RAM si no existen los archivos .tif en disco
            self.transform = from_bounds(self.west, self.south, self.east, self.north, self.width, self.height)
            y_grad = np.linspace(4050, 3750, self.height)[:, np.newaxis]
            x_grad = np.linspace(80, -40, self.width)[np.newaxis, :]
            ruido = 25 * np.sin(np.linspace(0, 6 * np.pi, self.width))[np.newaxis, :]
            self.dem_ram = (y_grad + x_grad + ruido).astype(np.float32)

            cobertura_codigos = np.ones((self.height, self.width), dtype=np.uint8) * 3
            cobertura_codigos[40:240, 50:250] = 2   # Bosque denso de Eucalipto
            cobertura_codigos[180:280, 90:270] = 1  # Pastizal seco

        # Mapear códigos de cobertura a factores físicos de inflamabilidad
        # 0: Roca/Cortafuegos (0.0), 1: Pastizal (1.25), 2: Eucalipto (1.50), 3: Matorral (0.85)
        mapa_factores = np.array([0.0, 1.25, 1.50, 0.85], dtype=np.float32)
        self.combustible_base_ram = mapa_factores[np.clip(cobertura_codigos, 0, 3)]

        # Pre-calentamiento (Warm-up) del compilador JIT de Numba con matriz pequeña
        dummy_state = np.ones((10, 10), dtype=np.uint8)
        dummy_state[5, 5] = 2
        dummy_dem = np.zeros((10, 10), dtype=np.float32)
        dummy_fuel = np.ones((10, 10), dtype=np.float32)
        kernel_automata_anisotropico(dummy_state, dummy_dem, dummy_fuel, 10.0, 20.0, 2.35, 30.0, 0.5, 0.4, 0.62, 2)

        self._inicializado = True

    def ejecutar_simulacion(
        self,
        lat_foco: float,
        lon_foco: float,
        vel_viento_kmh: float,
        azimut_viento_grados: float,
        humedad_pct: float,
        iteraciones: int,
        peso_pendiente: float,
        peso_viento: float,
        umbral_ignicion: float,
        barreras_activas: List[Dict[str, Any]],
        infraestructuras: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        t_inicio_total = time.perf_counter()

        # 1. Clonar en memoria para aislamiento de concurrencia (np.copy)
        combustible_trabajo = np.copy(self.combustible_base_ram)
        estado_inicial = np.where(combustible_trabajo > 0.05, 1, 0).astype(np.uint8)

        # 2. Fase 2: Puente Híbrido Vector-Raster (Quemar barreras tácticas en RAM)
        t_inicio_raster = time.perf_counter()
        if barreras_activas:
            geometrias_barreras = []
            for b in barreras_activas:
                coords_lon_lat = [(pt[1], pt[0]) for pt in b["coordenadas"]]
                if len(coords_lon_lat) >= 2:
                    # Buffer ligero para asegurar grosor de cortafuegos de al menos 2 píxeles
                    linea = LineString(coords_lon_lat).buffer(0.00018)
                    geometrias_barreras.append((linea, 0))

            if geometrias_barreras:
                mascara_barreras = rasterize(
                    geometrias_barreras,
                    out_shape=(self.height, self.width),
                    transform=self.transform,
                    fill=1,
                    dtype=np.uint8
                )
                estado_inicial[mascara_barreras == 0] = 0
                combustible_trabajo[mascara_barreras == 0] = 0.0
        t_raster_ms = round((time.perf_counter() - t_inicio_raster) * 1000, 2)

        # 3. Transformación afín de (lon, lat) a (fila, columna) de la matriz
        fila_foco, col_foco = rowcol(self.transform, lon_foco, lat_foco)
        fila_foco = int(np.clip(fila_foco, 2, self.height - 3))
        col_foco = int(np.clip(col_foco, 2, self.width - 3))

        # Encender núcleo inicial (3x3 celdas para estabilidad de ignición)
        estado_inicial[fila_foco - 1:fila_foco + 2, col_foco - 1:col_foco + 2] = 2

        # 4. Fase 3: Ejecución del Kernel Anisotrópico en Numba
        t_inicio_numba = time.perf_counter()
        azimut_rad = math.radians(azimut_viento_grados)
        estado_final, _ = kernel_automata_anisotropico(
            estado_inicial,
            self.dem_ram,
            combustible_trabajo,
            self.resolucion_metros,
            vel_viento_kmh,
            azimut_rad,
            humedad_pct,
            peso_pendiente,
            peso_viento,
            umbral_ignicion,
            iteraciones
        )
        t_numba_ms = round((time.perf_counter() - t_inicio_numba) * 1000, 2)

        # 5. Fase 4: Vectorización Morfológica y Simplificación Topológica (Shapely)
        t_inicio_vec = time.perf_counter()
        mascara_quemada = ((estado_final == 2) | (estado_final == 3)).astype(np.uint8)
        celdas_afectadas = int(np.sum(mascara_quemada))
        area_hectareas = round((celdas_afectadas * (self.resolucion_metros ** 2)) / 10000.0, 2)

        poligonos_extraidos = []
        for geom_dict, val in shapes(mascara_quemada, mask=(mascara_quemada == 1), transform=self.transform):
            if val == 1:
                poligonos_extraidos.append(shape(geom_dict))

        if poligonos_extraidos:
            poligono_unido = unary_union(poligonos_extraidos)
            # Simplificación topológica para eliminar el efecto escalera del raster
            poligono_simplificado = poligono_unido.buffer(0.00008).simplify(0.00006, preserve_topology=True)
            geojson_poligono = mapping(poligono_simplificado)
        else:
            poligono_simplificado = Point(lon_foco, lat_foco).buffer(0.0002)
            geojson_poligono = mapping(poligono_simplificado)

        # Evaluar intersección espacial (ST_Intersects equivalente) con infraestructuras vulnerables
        infraestructuras_comprometidas = []
        for inf in infraestructuras:
            punto_inf = Point(inf["lng"], inf["lat"])
            if poligono_simplificado.intersects(punto_inf):
                infraestructuras_comprometidas.append(inf)

        t_vec_ms = round((time.perf_counter() - t_inicio_vec) * 1000, 2)
        t_total_ms = round((time.perf_counter() - t_inicio_total) * 1000, 2)

        return {
            "foco_matriz": {"fila": fila_foco, "columna": col_foco, "lat": lat_foco, "lng": lon_foco},
            "metricas_simulacion": {
                "celdas_quemadas": celdas_afectadas,
                "area_afectada_hectareas": area_hectareas,
                "iteraciones_ejecutadas": iteraciones,
                "total_infraestructuras_afectadas": len(infraestructuras_comprometidas)
            },
            "metricas_rendimiento_ms": {
                "fase2_rasterizacion_barreras_ms": t_raster_ms,
                "fase3_kernel_numba_jit_ms": t_numba_ms,
                "fase4_vectorizacion_shapely_ms": t_vec_ms,
                "tiempo_total_pipeline_ms": t_total_ms,
                "cumple_rnf01_menor_5000ms": t_total_ms < 5000.0
            },
            "infraestructuras_afectadas": infraestructuras_comprometidas,
            "geojson_amenaza": geojson_poligono
        }
