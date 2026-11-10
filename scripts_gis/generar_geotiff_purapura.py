import os
import numpy as np
import rasterio
from rasterio.transform import from_bounds

os.makedirs("rasters", exist_ok=True)

# Coordenadas del Bounding Box: Bosquecillo de Pura Pura, La Paz
WEST, SOUTH, EAST, NORTH = -68.1620, -16.4900, -68.1420, -16.4720
WIDTH, HEIGHT = 300, 300

transform = from_bounds(WEST, SOUTH, EAST, NORTH, WIDTH, HEIGHT)

# 1. Generar Modelo Digital de Elevación (DEM) realista (3750 msnm a 4050 msnm)
y_grad = np.linspace(4050, 3750, HEIGHT)[:, np.newaxis]
x_grad = np.linspace(80, -40, WIDTH)[np.newaxis, :]
ruido_cañadones = 25 * np.sin(np.linspace(0, 6 * np.pi, WIDTH))[np.newaxis, :]
dem_matrix = (y_grad + x_grad + ruido_cañadones).astype(np.float32)

with rasterio.open(
    "rasters/purapura_dem_10m.tif", "w",
    driver="GTiff", height=HEIGHT, width=WIDTH, count=1,
    dtype=dem_matrix.dtype, crs="EPSG:4326", transform=transform
) as dst:
    dst.write(dem_matrix, 1)

# 2. Generar Cobertura de Suelo (0: Cortafuegos/Roca, 1: Pastizal, 2: Eucalipto, 3: Matorral)
cobertura_matrix = np.ones((HEIGHT, WIDTH), dtype=np.uint8) * 3
cobertura_matrix[50:230, 60:240] = 2   # Mancha central densa de Eucalipto
cobertura_matrix[180:280, 100:270] = 1 # Pastizal seco en ladera sur-este

with rasterio.open(
    "rasters/purapura_cobertura_10m.tif", "w",
    driver="GTiff", height=HEIGHT, width=WIDTH, count=1,
    dtype=cobertura_matrix.dtype, crs="EPSG:4326", transform=transform
) as dst:
    dst.write(cobertura_matrix, 1)

print("GeoTIFFs co-registrados de Pura Pura (300x300) generados con éxito en /rasters")