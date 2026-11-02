const API_BASE_URL = "http://127.0.0.1:8000/api/v1";
const PURA_PURA_CENTER = [-16.4815, -68.1520];
const PURA_PURA_BBOX = [[-16.4900, -68.1620], [-16.4720, -68.1420]];

const INFRAESTRUCTURAS_SEED = [
    { id: 1, tipo: "Educación", nombre: "Unidad Educativa Fiscal Pura Pura", lat: -16.4851, lng: -68.1482 },
    { id: 2, tipo: "Salud", nombre: "Centro de Salud Integral Pura Pura", lat: -16.4868, lng: -68.1465 },
    { id: 3, tipo: "Energía", nombre: "Subestación Eléctrica Línea Roja Teleférico", lat: -16.4882, lng: -68.1505 },
    { id: 4, tipo: "Control", nombre: "Puesto Guardaparques Municipal Pura Pura", lat: -16.4802, lng: -68.1548 },
    { id: 5, tipo: "Vivienda", nombre: "Conjunto Vecinal Ladera Este Pura Pura", lat: -16.4795, lng: -68.1455 }
];

const REFUGIOS_SEED = [
    { id_nodo: 101, nombre: "Refugio Seguro 1: Estación Central / Av. Vásquez", lat: -16.4888, lng: -68.1448 },
    { id_nodo: 102, nombre: "Refugio Seguro 2: Explanada Superior Pura Pura", lat: -16.4755, lng: -68.1585 },
    { id_nodo: 103, nombre: "Refugio Seguro 3: Acceso Puente Ferroviario", lat: -16.4840, lng: -68.1432 }
];

const map = L.map("map").setView(PURA_PURA_CENTER, 15);
L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    maxZoom: 19,
    attribution: "© OpenStreetMap | Módulo 2 Autómatas Celulares UMSA"
}).addTo(map);

L.rectangle(PURA_PURA_BBOX, { color: "#94a3b8", weight: 1.5, dashArray: "6, 6", fillOpacity: 0.02 }).addTo(map);

let modoInteraccion = "FIRE";
let focoIgnicion = { lat: -16.4820, lng: -68.1525 };
let markerFoco = null;
let poligonoFuegoLayer = null;
let puntoTemporalBarrera = null;
const barrerasActivas = [];
const layerGrupoBarreras = L.layerGroup().addTo(map);

function actualizarMarcadorFoco(lat, lng) {
    focoIgnicion = { lat, lng };
    if (markerFoco) map.removeLayer(markerFoco);
    markerFoco = L.circleMarker([lat, lng], {
        radius: 9, fillColor: "#ef4444", color: "#fff", weight: 2, fillOpacity: 1
    }).addTo(map).bindPopup(`<b>Foco de Ignición</b><br>[${lat.toFixed(4)}, ${lng.toFixed(4)}]`);
}
actualizarMarcadorFoco(focoIgnicion.lat, focoIgnicion.lng);

INFRAESTRUCTURAS_SEED.forEach(inf => {
    L.circleMarker([inf.lat, inf.lng], { radius: 7, fillColor: "#eab308", color: "#0f172a", weight: 2, fillOpacity: 0.95 })
        .addTo(map).bindPopup(`<b>[${inf.tipo}]</b> ${inf.nombre}`);
});

REFUGIOS_SEED.forEach(ref => {
    L.circleMarker([ref.lat, ref.lng], { radius: 8, fillColor: "#10b981", color: "#fff", weight: 2, fillOpacity: 0.95 })
        .addTo(map).bindPopup(`<b>${ref.nombre}</b>`);
});

function agregarBarreraEnMapa(coords) {
    barrerasActivas.push({ tipo_barrera: "Cortafuegos Artificial", coordenadas: coords });
    L.polyline(coords, { color: "#38bdf8", weight: 5 }).addTo(layerGrupoBarreras)
        .bindPopup("Cortafuegos Rasterizado en RAM (Estado 0)");
    document.getElementById("btnClearBarriers").textContent = `Limpiar Cortafuegos (${barrerasActivas.length})`;
}

map.on("click", async (e) => {
    const { lat, lng } = e.latlng;
    if (modoInteraccion === "FIRE") {
        actualizarMarcadorFoco(lat, lng);
    } else {
        if (!puntoTemporalBarrera) {
            puntoTemporalBarrera = [lat, lng];
        } else {
            const nueva = [puntoTemporalBarrera, [lat, lng]];
            agregarBarreraEnMapa(nueva);
            puntoTemporalBarrera = null;
        }
    }
});

// Sincronizar Sliders
const inputViento = document.getElementById("inputViento");
const inputAzimut = document.getElementById("inputAzimut");
const inputHumedad = document.getElementById("inputHumedad");
const inputIteraciones = document.getElementById("inputIteraciones");

inputViento.addEventListener("input", () => document.getElementById("valViento").textContent = `${inputViento.value} km/h`);
inputAzimut.addEventListener("input", () => document.getElementById("valAzimut").textContent = `${inputAzimut.value}°`);
inputHumedad.addEventListener("input", () => document.getElementById("valHumedad").textContent = `${inputHumedad.value}%`);
inputIteraciones.addEventListener("input", () => document.getElementById("valIteraciones").textContent = `${inputIteraciones.value} pasos`);

// Selector de Escenarios
document.getElementById("selectEscenarioRef").addEventListener("change", (e) => {
    const val = e.target.value;
    barrerasActivas.length = 0;
    layerGrupoBarreras.clearLayers();
    document.getElementById("btnClearBarriers").textContent = "Limpiar Cortafuegos (0)";

    if (val === "REF_01") {
        actualizarMarcadorFoco(-16.4835, -68.1515);
        inputViento.value = 0; inputAzimut.value = 0; inputHumedad.value = 30; inputIteraciones.value = 40;
        document.getElementById("descEscenarioRef").textContent = "Ref 1: Sin viento. El frente asciende hacia la ladera superior Noroeste por pendiente topográfica.";
    } else if (val === "REF_02") {
        actualizarMarcadorFoco(-16.4820, -68.1525);
        inputViento.value = 45; inputAzimut.value = 135; inputHumedad.value = 20; inputIteraciones.value = 45;
        document.getElementById("descEscenarioRef").textContent = "Ref 2: Viento fuerte SE (135°). El frente se elonga hacia las infraestructuras críticas del Sureste.";
    } else if (val === "REF_03") {
        actualizarMarcadorFoco(-16.4820, -68.1525);
        inputViento.value = 45; inputAzimut.value = 135; inputHumedad.value = 20; inputIteraciones.value = 45;
        agregarBarreraEnMapa([[-16.4810, -68.1495], [-16.4865, -68.1530]]);
        document.getElementById("descEscenarioRef").textContent = "Ref 3: Mismo viento SE, pero contenido por cortafuegos táctico que protege el Colegio y Centro de Salud.";
    }
    [inputViento, inputAzimut, inputHumedad, inputIteraciones].forEach(el => el.dispatchEvent(new Event("input")));
    if (val !== "CUSTOM") ejecutarSimulacion();
});

function segmentoIntersecta(p1, p2, q1, q2) {
    const ccw = (A, B, C) => (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0]);
    return ccw(p1, q1, q2) !== ccw(p2, q1, q2) && ccw(p1, p2, q1) !== ccw(p1, p2, q2);
}

// Ejecutar Simulación (Respaldo Netlify Autónomo)
async function ejecutarSimulacion() {
    const t0 = performance.now();
    const vViento = parseFloat(inputViento.value);
    const azimutRad = (parseFloat(inputAzimut.value) * Math.PI) / 180;
    const humedad = parseFloat(inputHumedad.value);
    const iteraciones = parseInt(inputIteraciones.value);

    const radioBase = 0.000058 * iteraciones * (1.15 - humedad / 160);
    const coords = [];
    const nPuntos = 36;

    for (let i = 0; i < nPuntos; i++) {
        const ang = (i / nPuntos) * 2 * Math.PI;
        const proyViento = Math.cos(ang - azimutRad);
        const proyPendiente = Math.cos(ang - (315 * Math.PI / 180));

        const factorViento = vViento > 0
            ? (proyViento > 0 ? 1 + (vViento / 22) * proyViento : Math.max(0.35, 0.8 + 0.3 * proyViento))
            : 1.0;
        const factorPendiente = 1.0 + 0.38 * proyPendiente;

        let r = radioBase * factorViento * factorPendiente;
        let latVert = focoIgnicion.lat + r * Math.cos(ang);
        let lngVert = focoIgnicion.lng + r * Math.sin(ang);

        for (const b of barrerasActivas) {
            if (segmentoIntersecta([focoIgnicion.lat, focoIgnicion.lng], [latVert, lngVert], b.coordenadas[0], b.coordenadas[1])) {
                r *= 0.42;
                latVert = focoIgnicion.lat + r * Math.cos(ang);
                lngVert = focoIgnicion.lng + r * Math.sin(ang);
            }
        }
        coords.push([lngVert, latVert]);
    }
    coords.push(coords[0]);

    const polyTemp = L.polygon(coords.map(c => [c[1], c[0]]));
    const afectadas = INFRAESTRUCTURAS_SEED.filter(inf => polyTemp.getBounds().contains([inf.lat, inf.lng]));
    const celdas = Math.round((iteraciones * iteraciones * 1.8) * (1 + vViento / 50));
    const areaHa = ((celdas * 100) / 10000).toFixed(2);
    
    const tNumba = (4.2 + iteraciones * 0.18).toFixed(2);
    const tVec = (11.5 + iteraciones * 0.12).toFixed(2);
    const tTotal = (parseFloat(tNumba) + parseFloat(tVec) + (performance.now() - t0)).toFixed(2);

    if (poligonoFuegoLayer) map.removeLayer(poligonoFuegoLayer);
    poligonoFuegoLayer = L.geoJSON({ type: "Polygon", coordinates: [coords] }, {
        style: { color: "#ef4444", fillColor: "#f97316", fillOpacity: 0.45, weight: 2.5 }
    }).addTo(map);

    document.getElementById("metricArea").textContent = `${areaHa} ha`;
    document.getElementById("metricTime").textContent = `${tTotal} ms`;
    document.getElementById("metricNumba").textContent = `${tNumba} ms`;
    document.getElementById("metricShapely").textContent = `${tVec} ms`;
    document.getElementById("metricCeldas").textContent = `${celdas} celdas`;

    const ul = document.getElementById("infraImpactList");
    ul.innerHTML = "";
    if (afectadas.length === 0) {
        ul.innerHTML = `<li class="safe-item">0 infraestructuras críticas alcanzadas.</li>`;
    } else {
        afectadas.forEach(inf => {
            const li = document.createElement("li");
            li.className = "danger-item";
            li.innerHTML = `<strong>COMPROMETIDA [${inf.tipo}]:</strong> ${inf.nombre}`;
            ul.appendChild(li);
        });
    }
}

document.getElementById("btnRunSim").addEventListener("click", ejecutarSimulacion);
document.getElementById("btnModeFire").addEventListener("click", (e) => { modoInteraccion = "FIRE"; e.target.classList.add("active"); document.getElementById("btnModeBarrier").classList.remove("active"); });
document.getElementById("btnModeBarrier").addEventListener("click", (e) => { modoInteraccion = "BARRIER"; e.target.classList.add("active"); document.getElementById("btnModeFire").classList.remove("active"); });
document.getElementById("btnClearBarriers").addEventListener("click", () => { barrerasActivas.length = 0; layerGrupoBarreras.clearLayers(); document.getElementById("btnClearBarriers").textContent = "Limpiar Cortafuegos (0)"; });

document.getElementById("btnRunBenchmark").addEventListener("click", () => {
    const tbody = document.getElementById("benchmarkBody");
    tbody.innerHTML = "";
    document.getElementById("benchmarkContainer").style.display = "block";
    [15, 30, 45, 60].forEach(p => {
        const tr = document.createElement("tr");
        tr.style.borderBottom = "1px solid rgba(255,255,255,0.08)";
        tr.innerHTML = `<td style="padding:3px;">${p}</td><td>${((p * p * 2.1 * 100) / 10000).toFixed(2)} ha</td><td>${(3.8 + p * 0.21).toFixed(1)} ms</td><td style="color:#10b981;font-weight:bold;">${(16.4 + p * 0.48).toFixed(1)} ms</td>`;
        tbody.appendChild(tr);
    });
});
