import os
import time
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from motor_automata import MotorSimulacionSingleton
from motor_ruteo import MotorRuteoAdaptativo

motor_singleton = MotorSimulacionSingleton()
motor_ruteo = MotorRuteoAdaptativo()

@asynccontextmanager
async def lifespan(app: FastAPI):
    motor_singleton.inicializar_en_ram()
    yield

app = FastAPI(
    title="API Integrada: Autómatas Celulares + pgRouting + Telemetría Móvil - UMSA",
    version="4.0.0 - Entregable Semanas 3 y 4",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

OPERATOR_SECRET_TOKEN = os.getenv("OPERATOR_TOKEN", "UMSA-RIESGOS-2026")

INFRAESTRUCTURAS = [
    {"id": 1, "tipo": "Educación", "nombre": "Unidad Educativa Fiscal Pura Pura", "lat": -16.4851, "lng": -68.1482},
    {"id": 2, "tipo": "Salud", "nombre": "Centro de Salud Integral Pura Pura", "lat": -16.4868, "lng": -68.1465},
    {"id": 3, "tipo": "Energía", "nombre": "Subestación Eléctrica Línea Roja Teleférico", "lat": -16.4882, "lng": -68.1505},
    {"id": 4, "tipo": "Control", "nombre": "Puesto Guardaparques Municipal Pura Pura", "lat": -16.4802, "lng": -68.1548},
    {"id": 5, "tipo": "Vivienda", "nombre": "Conjunto Vecinal Ladera Este Pura Pura", "lat": -16.4795, "lng": -68.1455},
]

BARRERAS_ACTIVAS = []

class SimulacionRuteoRequest(BaseModel):
    lat_foco: float = -16.4820
    lon_foco: float = -68.1525
    lat_usuario: float = -16.4812
    lon_usuario: float = -68.1532
    velocidad_viento_kmh: float = 35.0
    azimut_viento_grados: float = 135.0
    humedad_relativa_porcentaje: float = 25.0
    iteraciones: int = 45
    peso_gradiente_pendiente: float = 0.50
    peso_vector_viento: float = 0.40
    umbral_indice_ignicion: float = 0.62
    sesion_uuid: Optional[str] = "UUID-OPERADOR-WEB"

class BarreraInput(BaseModel):
    tipo_barrera: str = "Cortafuegos Artificial"
    coordenadas: List[List[float]]

def verificar_token_operador(x_operator_token: Optional[str]):
    if x_operator_token != OPERATOR_SECRET_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Acceso denegado: Se requiere cabecera X-Operator-Token válida."
        )

@app.get("/api/v1/red-vial")
async def obtener_grafo_vial():
    return motor_ruteo.obtener_red_vial_geojson()

@app.post("/api/v1/simular")
async def ejecutar_simulacion_web(
    params: SimulacionRuteoRequest,
    x_operator_token: Optional[str] = Header(None)
):
    verificar_token_operador(x_operator_token)
    return motor_singleton.ejecutar_simulacion(
        lat_foco=params.lat_foco,
        lon_foco=params.lon_foco,
        vel_viento_kmh=params.velocidad_viento_kmh,
        azimut_viento_grados=params.azimut_viento_grados,
        humedad_pct=params.humedad_relativa_porcentaje,
        iteraciones=params.iteraciones,
        peso_pendiente=params.peso_gradiente_pendiente,
        peso_viento=params.peso_vector_viento,
        umbral_ignicion=params.umbral_indice_ignicion,
        barreras_activas=BARRERAS_ACTIVAS,
        infraestructuras=INFRAESTRUCTURAS
    )

@app.post("/api/v1/evacuacion-integrada")
async def simular_y_calcular_ruta_evacuacion(params: SimulacionRuteoRequest):
    """
    Endpoint Transaccional Único (Módulos 2, 3 y 4):
    Ejecuta el autómata celular en Numba + Enrutamiento adaptativo Dijkstra
    y retorna tanto el polígono de amenaza como la ruta óptima de evacuación en < 5 segundos.
    """
    t0 = time.perf_counter()

    sim = motor_singleton.ejecutar_simulacion(
        lat_foco=params.lat_foco,
        lon_foco=params.lon_foco,
        vel_viento_kmh=params.velocidad_viento_kmh,
        azimut_viento_grados=params.azimut_viento_grados,
        humedad_pct=params.humedad_relativa_porcentaje,
        iteraciones=params.iteraciones,
        peso_pendiente=params.peso_gradiente_pendiente,
        peso_viento=params.peso_vector_viento,
        umbral_ignicion=params.umbral_indice_ignicion,
        barreras_activas=BARRERAS_ACTIVAS,
        infraestructuras=INFRAESTRUCTURAS
    )

    ruteo = motor_ruteo.calcular_ruta_segura(
        lat_usuario=params.lat_usuario,
        lon_usuario=params.lon_usuario,
        geojson_poligono_fuego=sim["geojson_amenaza"]
    )

    tiempo_total_e2e_ms = round((time.perf_counter() - t0) * 1000, 2)

    return {
        "simulacion": sim,
        "evacuacion": ruteo,
        "rendimiento_extremo_a_extremo": {
            "tiempo_total_respuesta_ms": tiempo_total_e2e_ms,
            "cumple_rnf01_menor_5000ms": tiempo_total_e2e_ms < 5000.0
        },
        "protocolo_seguridad_ciudadana": [
            "Desplácese por la ruta verde calculada (evita el frente proyectado y pendientes extremas).",
            "En caso de pérdida de señal GPS/Internet, camine en dirección perpendicular al viento y cuesta abajo.",
            "Cubra nariz y boca con tela húmeda y diríjase al Refugio Seguro asignado."
        ]
    }

@app.post("/api/v1/barreras")
async def registrar_barrera(barrera: BarreraInput, x_operator_token: Optional[str] = Header(None)):
    verificar_token_operador(x_operator_token)
    nueva = {"id": len(BARRERAS_ACTIVAS) + 1, "tipo_barrera": barrera.tipo_barrera, "coordenadas": barrera.coordenadas}
    BARRERAS_ACTIVAS.append(nueva)
    return {"mensaje": "Barrera activa", "total_barreras": len(BARRERAS_ACTIVAS)}

@app.delete("/api/v1/barreras")
async def limpiar_barreras(x_operator_token: Optional[str] = Header(None)):
    verificar_token_operador(x_operator_token)
    BARRERAS_ACTIVAS.clear()
    return {"mensaje": "Barreras limpiadas"}
