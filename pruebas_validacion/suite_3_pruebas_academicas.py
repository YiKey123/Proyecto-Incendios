import sys
import os
import time

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "backend"))
from motor_automata import MotorSimulacionSingleton
from motor_ruteo import MotorRuteoAdaptativo

def ejecutar_suite_validacion_academica():
    print("=" * 78)
    print("SUITE DE VALIDACIÓN EXPERIMENTAL - 3 PRUEBAS ACADÉMICAS (BOSQUECILLO PURA PURA)")
    print("=" * 78)

    motor_sim = MotorSimulacionSingleton()
    motor_sim.inicializar_en_ram()
    motor_rut = MotorRuteoAdaptativo()

    # -------------------------------------------------------------------------
    # PRUEBA 1: Comparación del modelo de propagación con escenarios de referencia
    # -------------------------------------------------------------------------
    res_sin_viento = motor_sim.ejecutar_simulacion(
        lat_foco=-16.4820, lon_foco=-68.1525, vel_viento_kmh=0.0, azimut_viento_grados=0.0,
        humedad_pct=30.0, iteraciones=40, peso_pendiente=0.5, peso_viento=0.4, umbral_ignicion=0.62,
        barreras_activas=[], infraestructuras=[]
    )
    res_viento_se = motor_sim.ejecutar_simulacion(
        lat_foco=-16.4820, lon_foco=-68.1525, vel_viento_kmh=45.0, azimut_viento_grados=135.0,
        humedad_pct=20.0, iteraciones=40, peso_pendiente=0.5, peso_viento=0.4, umbral_ignicion=0.62,
        barreras_activas=[], infraestructuras=[]
    )
    area_1 = res_sin_viento["metricas_simulacion"]["area_afectada_hectareas"]
    area_2 = res_viento_se["metricas_simulacion"]["area_afectada_hectareas"]
    assert area_2 > area_1, "Error en Prueba 1: El escenario con viento extremo debe expandir mayor área."
    print(f"[OK] PRUEBA 1 (Fidelidad con Escenarios Referencia): Sin Viento = {area_1} ha | Viento SE 45km/h = {area_2} ha")

    # -------------------------------------------------------------------------
    # PRUEBA 2: Verificación de que las rutas evitan zonas de amenaza y pendientes extremas
    # -------------------------------------------------------------------------
    ruta_segura = motor_rut.calcular_ruta_segura(
        lat_usuario=-16.4810,
        lon_usuario=-68.1535,
        geojson_poligono_fuego=res_viento_se["geojson_amenaza"]
    )
    assert ruta_segura["ruta_evita_zona_amenaza"] is True, "Error en Prueba 2: La ruta cruza el fuego."
    print(
        f"[OK] PRUEBA 2 (Evasión y Seguridad Vial): Tramos en fuego = {ruta_segura['tramos_ruta_en_fuego']} | "
        f"Refugio = {ruta_segura['nodo_refugio_destino']['nombre']} | "
        f"Pendiente media = {ruta_segura['pendiente_media_porcentaje']}% | "
        f"Exposición = {ruta_segura['tiempo_exposicion_estimado_seg']} s"
    )

    # -------------------------------------------------------------------------
    # PRUEBA 3: Medición del tiempo total de respuesta bajo condiciones definidas (< 5s)
    # -------------------------------------------------------------------------
    t0 = time.perf_counter()
    sim_60 = motor_sim.ejecutar_simulacion(
        lat_foco=-16.4820, lon_foco=-68.1525, vel_viento_kmh=40.0, azimut_viento_grados=135.0,
        humedad_pct=22.0, iteraciones=60, peso_pendiente=0.5, peso_viento=0.4, umbral_ignicion=0.62,
        barreras_activas=[], infraestructuras=[]
    )
    rut_60 = motor_rut.calcular_ruta_segura(-16.4810, -68.1535, sim_60["geojson_amenaza"])
    tiempo_e2e_ms = round((time.perf_counter() - t0) * 1000, 2)
    assert tiempo_e2e_ms < 5000.0, "Error en Prueba 3: Superó los 5000 ms."
    print(
        f"[OK] PRUEBA 3 (Rendimiento E2E < 5000 ms): Matriz 300x300 (60 pasos) + Dijkstra = {tiempo_e2e_ms} ms"
    )
    print("=" * 78)

if __name__ == "__main__":
    ejecutar_suite_validacion_academica()