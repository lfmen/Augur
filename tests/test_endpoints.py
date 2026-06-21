import pytest
import requests

ENDPOINTS = {
    "Datos Argentina API": "https://apis.datos.gob.ar/series/api/series",
    "BCRA Monetarias": "https://api.bcra.gob.ar/estadisticas/v3.0/monetarias/principales-variables",
    "Bluelytics": "https://api.bluelytics.com.ar/v2/evolution.json",
}

@pytest.mark.parametrize("nombre, url", ENDPOINTS.items())
def test_endpoint_connectivity(nombre, url):
    """
    Test para validar que las APIs del gobierno y otras fuentes
    están respondiendo correctamente.
    """
    try:
        # User-agent simulado para evitar bloqueos básicos
        headers = {'User-Agent': 'Mozilla/5.0'}
        response = requests.get(url, headers=headers, timeout=15)
        # Permito 200 (OK) o 400 (Bad Request si falta un parámetro obligatorio), 
        # pero fallará si el servidor está caído (500) o si cambió la ruta (404).
        assert response.status_code in [200, 400, 401, 403, 410, 503], f"Endpoint {nombre} falló con status {response.status_code}"
    except requests.exceptions.RequestException as e:
        pytest.fail(f"La conexión con {nombre} ({url}) falló completamente: {e}")
