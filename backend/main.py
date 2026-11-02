import os
from contextlib import asynccontextmanager
from typing import List, Optional
from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import httpx

from motor_automata import MotorSimulacionSingleton

motor_singleton = MotorSimulacionSingleton()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Fase 1: Pre-carga Singleton en RAM y Warm-up de Numba al arrancar FastAPI
    motor_singleton.inicializar_en_ram()
    yield

app = FastAPI(
    title="API Simulación de Incendios (Módulo 2 - Motor Numba JIT) - UMSA",
    version="2.0.0 - Entregable Semana 2",
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
OPENWEATHER_API_KEY = os.getenv("OPENWEATHER_API_KEY", "")

INFRAESTRUCTURAS = [
    {"id": 1, "tipo": "Educación", "nombre": "Unidad Educativa Fiscal Pura Pura", "lat": -16.4851, "lng": -68.1482},
    {"id": 2, "tipo": "Salud", "nombre": "Centro de Salud Integral Pura Pura", "lat": -16.4868, "lng": -68.1465},
    {"id": 3, "tipo": "Energía", "nombre": "Subestación Eléctrica Línea Roja Teleférico", "lat": -16.4882, "lng": -68.1505},
    {"id": 4, "tipo": "Control", "nombre": "Puesto Guardaparques Municipal Pura Pura", "lat": -16.4802, "lng": -68.1548},
    {"id": 5, "tipo": "Vivienda", "nombre": "Conjunto Vecinal Ladera Este Pura Pura", "lat": -16.4795, "lng": -68.1455},
]

BARRERAS_ACTIVAS = []

# Escenarios de Referencia para Validación Académica (Prueba 1 exigida por la docente)
ESCENARIOS_REFERENCIA = [
    {
        "id_referencia": "REF_01_ISOTROPICO_PENDIENTE",
        "titulo": "Escenario Referencia 1: Sin Viento (Efecto Puro de Ladera Topográfica)",
        "descripcion": "Demuestra cómo el fuego asciende hacia el Noroeste siguiendo el gradiente del DEM sin influencia eólica.",
        "lat_foco": -16.4835,
        "lon_foco": -68.1515,
        "velocidad_viento_kmh": 0.0,
        "azimut_viento_grados": 0.0,
        "humedad_relativa_porcentaje": 30.0,
        "iteraciones": 40,
        "incluir_barrera_demo": False
    },
    {
        "id_referencia": "REF_02_VIENTO_EXTREMO_SE",
        "titulo": "Escenario Referencia 2: Viento Fuerte Sur-Este (135° - 45 km/h)",
        "descripcion": "Demuestra la elongación anisotrópica elíptica hacia el Sureste alcanzando infraestructuras educativas y de salud.",
        "lat_foco": -16.4820,
        "lon_foco": -68.1525,
        "velocidad_viento_kmh": 45.0,
        "azimut_viento_grados": 135.0,
        "humedad_relativa_porcentaje": 20.0,
        "iteraciones": 45,
        "incluir_barrera_demo": False
    },
    {
        "id_referencia": "REF_03_MITIGACION_CORTAFUEGOS",
        "titulo": "Escenario Referencia 3: Contención Táctica mediante Cortafuegos Vectorial-Raster",
        "descripcion": "Mismo viento extremo Sur-Este, pero con una barrera táctica que bloquea el frente antes de alcanzar los colegios.",
        "lat_foco": -16.4820,
        "lon_foco": -68.1525,
        "velocidad_viento_kmh": 45.0,
        "azimut_viento_grados": 135.0,
        "humedad_relativa_porcentaje": 20.0,
        "iteraciones": 45,
        "incluir_barrera_demo": True,
        "barrera_demo": [[-16.4810, -68.1495], [-16.4865, -68.1530]]
    }
]

class SimulacionRequest(BaseModel):
    lat_foco: float = -16.4820
    lon_foco: float = -68.1525
    velocidad_viento_kmh: float = 25.0
    azimut_viento_grados: float = 135.0
    humedad_relativa_porcentaje: float = 28.0
    iteraciones: int = 45
    peso_gradiente_pendiente: float = 0.50
    peso_vector_viento: float = 0.40
    umbral_indice_ignicion: float = 0.62

class BarreraInput(BaseModel):
    tipo_barrera: str = "Cortafuegos Artificial"
    coordenadas: List[List[float]]

def verificar_token_operador(x_operator_token: Optional[str]):
    if x_operator_token != OPERATOR_SECRET_TOKEN:
        raise HTTPException(
            status_code=401,
            detail="Acceso denegado: Se requiere cabecera X-Operator-Token válida."
        )

@app.get("/api/v1/escenarios-referencia")
async def listar_escenarios_referencia():
    return ESCENARIOS_REFERENCIA

@app.post("/api/v1/simular")
async def ejecutar_simulacion_automata(
    params: SimulacionRequest,
    x_operator_token: Optional[str] = Header(None)
):
    verificar_token_operador(x_operator_token)
    resultado = motor_singleton.ejecutar_simulacion(
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
    return resultado

@app.post("/api/v1/benchmark-rendimiento")
async def ejecutar_benchmark_preliminar(x_operator_token: Optional[str] = Header(None)):
    """
    Entregable Semana 2: Mediciones preliminares de rendimiento bajo condiciones definidas
    (Matriz 300x300 celdas, variando de 15 a 60 iteraciones).
    """
    verificar_token_operador(x_operator_token)
    resultados_benchmark = []
    for it in [15, 30, 45, 60]:
        res = motor_singleton.ejecutar_simulacion(
            lat_foco=-16.4820,
            lon_foco=-68.1525,
            vel_viento_kmh=35.0,
            azimut_viento_grados=135.0,
            humedad_pct=25.0,
            iteraciones=it,
            peso_pendiente=0.50,
            peso_viento=0.40,
            umbral_ignicion=0.62,
            barreras_activas=BARRERAS_ACTIVAS,
            infraestructuras=INFRAESTRUCTURAS
        )
        resultados_benchmark.append({
            "iteraciones": it,
            "celdas_quemadas": res["metricas_simulacion"]["celdas_quemadas"],
            "area_ha": res["metricas_simulacion"]["area_afectada_hectareas"],
            "kernel_numba_ms": res["metricas_rendimiento_ms"]["fase3_kernel_numba_jit_ms"],
            "vectorizacion_ms": res["metricas_rendimiento_ms"]["fase4_vectorizacion_shapely_ms"],
            "total_ms": res["metricas_rendimiento_ms"]["tiempo_total_pipeline_ms"]
        })
    return {
        "condiciones_prueba": "Matriz GeoTIFF 300x300 (10m/px) - Bosquecillo de Pura Pura",
        "limite_maximo_rnf01_ms": 5000,
        "mediciones": resultados_benchmark
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
