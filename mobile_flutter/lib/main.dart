import 'dartasync';
import 'dartconvert';
import 'packagefluttermaterial.dart';
import 'packageflutter_mapflutter_map.dart';
import 'packagelatlong2latlong.dart';
import 'packagegeolocatorgeolocator.dart';
import 'packagehttphttp.dart' as http;
import 'packageuuiduuid.dart';
import 'packageshared_preferencesshared_preferences.dart';

void main() {
  runApp(const EvacuacionPuraPuraApp());
}

class EvacuacionPuraPuraApp extends StatelessWidget {
  const EvacuacionPuraPuraApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title 'Alerta y Evacuación Pura Pura - UMSA',
      debugShowCheckedModeBanner false,
      theme ThemeData.dark().copyWith(
        scaffoldBackgroundColor const Color(0xFF0F172A),
        colorScheme const ColorScheme.dark(
          primary Color(0xFFEF4444),
          secondary Color(0xFF10B981),
        ),
      ),
      home const PantallaReporteCiudadano(),
    );
  }
}

 ============================================================================
 PANTALLA 1 CAPTURA GPS Y REPORTE DE FOCO DE INCENDIO
 ============================================================================
class PantallaReporteCiudadano extends StatefulWidget {
  const PantallaReporteCiudadano({super.key});

  @override
  StatePantallaReporteCiudadano createState() = _PantallaReporteCiudadanoState();
}

class _PantallaReporteCiudadanoState extends StatePantallaReporteCiudadano {
  final String _sesionUuid = const Uuid().v4();
  LatLng _posicionCiudadano = const LatLng(-16.4810, -68.1535);
  LatLng _focoIncendioMarcado = const LatLng(-16.4822, -68.1518);
  bool _cargandoGps = false;
  bool _procesandoSimulacion = false;

   Endpoint del servidor FastAPI
  static const String _apiUrl = 'http10.0.2.28000apiv1evacuacion-integrada';

  @override
  void initState() {
    super.initState();
    _obtenerUbicacionGps();
  }

  Futurevoid _obtenerUbicacionGps() async {
    setState(() = _cargandoGps = true);
    try {
      LocationPermission permiso = await Geolocator.checkPermission();
      if (permiso == LocationPermission.denied) {
        permiso = await Geolocator.requestPermission();
      }
      if (permiso == LocationPermission.whileInUse  permiso == LocationPermission.always) {
        Position pos = await Geolocator.getCurrentPosition(
          desiredAccuracy LocationAccuracy.high,
        ).timeout(const Duration(seconds 4));
        setState(() {
          _posicionCiudadano = LatLng(pos.latitude, pos.longitude);
        });
      }
    } catch (_) {
       Mantiene coordenada por defecto en Bosquecillo de Pura Pura si el emulador no tiene GPS activo
    } finally {
      setState(() = _cargandoGps = false);
    }
  }

  Futurevoid _reportarYEvacuar() async {
    setState(() = _procesandoSimulacion = true);
    final prefs = await SharedPreferences.getInstance();

    final payload = {
      lat_foco _focoIncendioMarcado.latitude,
      lon_foco _focoIncendioMarcado.longitude,
      lat_usuario _posicionCiudadano.latitude,
      lon_usuario _posicionCiudadano.longitude,
      velocidad_viento_kmh 35.0,
      azimut_viento_grados 135.0,
      humedad_relativa_porcentaje 25.0,
      iteraciones 45,
      sesion_uuid _sesionUuid
    };

    try {
      final response = await http
          .post(
            Uri.parse(_apiUrl),
            headers {'Content-Type' 'applicationjson'},
            body jsonEncode(payload),
          )
          .timeout(const Duration(seconds 5));

      if (response.statusCode == 200) {
        final data = jsonDecode(response.body);
         Guardar en caché local para tolerancia a fallos de conectividad
        await prefs.setString('ultima_respuesta_evacuacion', response.body);

        if (!mounted) return;
        Navigator.push(
          context,
          MaterialPageRoute(
            builder (_) = PantallaRutaSupervivencia(
              datosRespuesta data,
              modoOfflineResiliente false,
            ),
          ),
        );
        return;
      }
    } catch (_) {
       Fallo de conectividad o sin internet en campo activar protocolo resiliente
    } finally {
      if (mounted) setState(() = _procesandoSimulacion = false);
    }

     Recuperar última ruta en caché o generar ruta de contingencia hacia Refugio Seguro
    final cache = prefs.getString('ultima_respuesta_evacuacion');
    final MapString, dynamic datosContingencia = cache != null
         jsonDecode(cache)
         _generarRutaContingenciaOffline();

    if (!mounted) return;
    Navigator.push(
      context,
      MaterialPageRoute(
        builder (_) = PantallaRutaSupervivencia(
          datosRespuesta datosContingencia,
          modoOfflineResiliente true,
        ),
      ),
    );
  }

  MapString, dynamic _generarRutaContingenciaOffline() {
    return {
      evacuacion {
        nodo_refugio_destino {nombre Refugio 2 Explanada Superior Pura Pura},
        distancia_total_metros 815.0,
        pendiente_media_porcentaje 8.2,
        tiempo_exposicion_estimado_seg 680.0,
        geojson_ruta_segura {
          geometry {
            coordinates [
              [_posicionCiudadano.longitude, _posicionCiudadano.latitude],
              [-68.1560, -16.4785],
              [-68.1585, -16.4755]
            ]
          }
        }
      },
      simulacion {
        geojson_amenaza {
          coordinates [
            [
              [-68.1530, -16.4815],
              [-68.1490, -16.4820],
              [-68.1485, -16.4860],
              [-68.1525, -16.4855],
              [-68.1530, -16.4815]
            ]
          ]
        }
      }
    };
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar AppBar(
        backgroundColor const Color(0xFF020617),
        title const Text('1. Reporte Ciudadano de Incendio', style TextStyle(fontSize 16)),
        actions [
          IconButton(
            icon const Icon(Icons.my_location),
            onPressed _obtenerUbicacionGps,
            tooltip 'Actualizar GPS',
          )
        ],
      ),
      body Column(
        children [
          Container(
            width double.infinity,
            padding const EdgeInsets.all(10),
            color const Color(0xFF1E293B),
            child const Text(
              'Toque el mapa para ubicar el foco de fuego observado y presione REPORTAR Y EVACUAR.',
              style TextStyle(fontSize 13, color Colors.white70),
            ),
          ),
          Expanded(
            child FlutterMap(
              options MapOptions(
                initialCenter _posicionCiudadano,
                initialZoom 15.2,
                onTap (_, latlng) = setState(() = _focoIncendioMarcado = latlng),
              ),
              children [
                TileLayer(
                  urlTemplate 'httpstile.openstreetmap.org{z}{x}{y}.png',
                  userAgentPackageName 'bo.umsa.informatica.evacuacion',
                ),
                MarkerLayer(
                  markers [
                    Marker(
                      point _posicionCiudadano,
                      width 44,
                      height 44,
                      child const Icon(Icons.person_pin_circle, color Colors.purpleAccent, size 40),
                    ),
                    Marker(
                      point _focoIncendioMarcado,
                      width 44,
                      height 44,
                      child const Icon(Icons.local_fire_department, color Colors.redAccent, size 40),
                    ),
                  ],
                ),
              ],
            ),
          ),
          Padding(
            padding const EdgeInsets.all(14.0),
            child SizedBox(
              width double.infinity,
              height 52,
              child ElevatedButton.icon(
                style ElevatedButton.styleFrom(backgroundColor const Color(0xFFEF4444)),
                onPressed _procesandoSimulacion  null  _reportarYEvacuar,
                icon const Icon(Icons.warning_amber_rounded, color Colors.white),
                label Text(
                  _procesandoSimulacion  'CALCULANDO RUTA SEGURA (5s)...'  'REPORTAR Y EVACUAR AHORA',
                  style const TextStyle(fontSize 15, fontWeight FontWeight.bold, color Colors.white),
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }
}

 ============================================================================
 PANTALLA 2 RECEPCIÓN DE RUTA SEGURA Y PROTOCOLO DE RESILIENCIA OFFLINE
 ============================================================================
class PantallaRutaSupervivencia extends StatelessWidget {
  final MapString, dynamic datosRespuesta;
  final bool modoOfflineResiliente;

  const PantallaRutaSupervivencia({
    super.key,
    required this.datosRespuesta,
    required this.modoOfflineResiliente,
  });

  @override
  Widget build(BuildContext context) {
    final ev = datosRespuesta['evacuacion'];
    final coordsRutaRaw = ev['geojson_ruta_segura']['geometry']['coordinates'] as List;
    final ListLatLng puntosRuta = coordsRutaRaw
        .map((c) = LatLng((c[1] as num).toDouble(), (c[0] as num).toDouble()))
        .toList();

    final coordsFuegoRaw = datosRespuesta['simulacion']['geojson_amenaza']['coordinates'][0] as List;
    final ListLatLng puntosPoligonoFuego = coordsFuegoRaw
        .map((c) = LatLng((c[1] as num).toDouble(), (c[0] as num).toDouble()))
        .toList();

    return Scaffold(
      appBar AppBar(
        backgroundColor const Color(0xFF020617),
        title const Text('2. Ruta de Evacuación Adaptativa', style TextStyle(fontSize 16)),
      ),
      body Column(
        children [
          if (modoOfflineResiliente)
            Container(
              width double.infinity,
              padding const EdgeInsets.all(10),
              color Colors.amber.shade900,
              child const Text(
                'MODO RESILIENTE SIN SEÑAL ACTIVO Mostrando ruta de caché  protocolo de seguridad. '
                'Camine perpendicular al viento y evite subir cañadones.',
                style TextStyle(fontSize 12, fontWeight FontWeight.bold, color Colors.white),
              ),
            ),
          Container(
            padding const EdgeInsets.all(12),
            color const Color(0xFF1E293B),
            child Column(
              crossAxisAlignment CrossAxisAlignment.start,
              children [
                Text(
                  'Destino ${ev['nodo_refugio_destino']['nombre']}',
                  style const TextStyle(fontWeight FontWeight.bold, color Color(0xFF10B981), fontSize 14),
                ),
                const SizedBox(height 4),
                Text(
                  'Distancia ${ev['distancia_total_metros']} m  '
                  'Pendiente media ${ev['pendiente_media_porcentaje']}%  '
                  'Exposición est. ${ev['tiempo_exposicion_estimado_seg']} seg',
                  style const TextStyle(fontSize 12, color Colors.white70),
                ),
              ],
            ),
          ),
          Expanded(
            child FlutterMap(
              options MapOptions(
                initialCenter puntosRuta.first,
                initialZoom 15.2,
              ),
              children [
                TileLayer(
                  urlTemplate 'httpstile.openstreetmap.org{z}{x}{y}.png',
                  userAgentPackageName 'bo.umsa.informatica.evacuacion',
                ),
                PolygonLayer(
                  polygons [
                    Polygon(
                      points puntosPoligonoFuego,
                      color Colors.deepOrange.withOpacity(0.42),
                      borderColor Colors.redAccent,
                      borderStrokeWidth 2.5,
                      isFilled true,
                    ),
                  ],
                ),
                PolylineLayer(
                  polylines [
                    Polyline(
                      points puntosRuta,
                      color const Color(0xFF22C55E),
                      strokeWidth 6.0,
                    ),
                  ],
                ),
                MarkerLayer(
                  markers [
                    Marker(
                      point puntosRuta.first,
                      width 40,
                      height 40,
                      child const Icon(Icons.directions_run, color Colors.white, size 34),
                    ),
                    Marker(
                      point puntosRuta.last,
                      width 44,
                      height 44,
                      child const Icon(Icons.health_and_safety, color Color(0xFF10B981), size 40),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}