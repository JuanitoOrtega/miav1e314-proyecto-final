"""Tests de la interfaz web.

La UI y la API viven en el mismo contenedor pero se escriben por separado, así
que nada garantiza que los nombres de los campos coincidan. Un typo en un
`name=` del formulario no se detecta hasta que alguien pulsa Predecir y recibe
un 422 — probablemente delante del docente. Estos tests lo detectan antes.
"""
import re
from pathlib import Path

import pytest

from src.api.schemas import CustomerFeatures
from src.features import ALL_FEATURES

ESTATICOS = Path("src/api/static")
HTML = ESTATICOS / "index.html"
JS = ESTATICOS / "app.js"
PRESENTACION = ESTATICOS / "presentacion.html"


@pytest.fixture(scope="module")
def html() -> str:
    return HTML.read_text(encoding="utf-8")


def campos_del_formulario(html: str) -> set[str]:
    """Extrae los name= de los <input> y <select>.

    Se acota a esas dos etiquetas a propósito: un `name=` suelto capturaría
    también <meta name="viewport">.
    """
    return set(re.findall(r'<(?:input|select)[^>]*\bname="([^"]+)"', html))


def test_los_ficheros_estaticos_existen():
    assert HTML.exists(), "Falta src/api/static/index.html"
    assert JS.exists(), "Falta src/api/static/app.js"


def test_el_formulario_cubre_las_19_variables(html):
    """Si falta una, la API responde 422 y la demo se cae."""
    assert campos_del_formulario(html) == set(ALL_FEATURES)


def test_los_campos_coinciden_con_el_esquema_pydantic(html):
    assert campos_del_formulario(html) == set(CustomerFeatures.model_fields)


def test_los_valores_por_defecto_forman_una_peticion_valida(html):
    """El formulario debe venir relleno con un cliente válido.

    En una demo en vivo no se rellenan 19 campos a mano: se pulsa Predecir y
    tiene que funcionar a la primera.
    """
    datos = {}

    for campo, valor in re.findall(r'name="([^"]+)"[^>]*value="([^"]*)"', html):
        datos[campo] = valor

    # De cada <select>, la primera <option> es la seleccionada por defecto
    for nombre, cuerpo in re.findall(
        r'<select[^>]*name="([^"]+)"[^>]*>(.*?)</select>', html, re.DOTALL
    ):
        opciones = re.findall(r"<option(?:\s+value=\"([^\"]*)\")?[^>]*>([^<]*)</option>", cuerpo)
        valor, etiqueta = opciones[0]
        datos[nombre] = valor if valor else etiqueta

    for numerico in ("tenure", "MonthlyCharges", "TotalCharges"):
        datos[numerico] = float(datos[numerico])
    datos["tenure"] = int(datos["tenure"])

    cliente = CustomerFeatures(**datos)
    assert cliente.tenure >= 0


def test_el_js_llama_al_endpoint_correcto():
    contenido = JS.read_text(encoding="utf-8")
    assert '"/predict"' in contenido
    assert '"POST"' in contenido


def test_el_js_muestra_el_pod_que_atiende():
    """served_by es lo que convierte la UI en una demo del balanceo."""
    assert "served_by" in JS.read_text(encoding="utf-8")


def test_la_presentacion_se_sirve_junto_a_la_interfaz(html):
    """El enlace del botón debe resolver contra un fichero que existe.

    La presentación se sirve desde el mismo StaticFiles que la interfaz, así
    que basta con que el fichero esté en src/api/static/. Si alguien lo mueve
    o lo renombra, el botón daría 404 delante del docente.
    """
    assert PRESENTACION.exists(), "Falta src/api/static/presentacion.html"
    assert 'href="/presentacion.html"' in html


def test_la_presentacion_es_autocontenida():
    """No debe cargar nada de fuera: la demo puede hacerse sin conexión."""
    contenido = PRESENTACION.read_text(encoding="utf-8")
    externos = re.findall(r'(?:src|href)="(https?://[^"]+)"', contenido)
    remotos = [u for u in externos if not u.startswith("https://churn.juanitodev.com")
               and not u.startswith("https://mlflow.juanitodev.com")]
    assert not remotos, f"La presentación carga recursos externos: {remotos}"
    assert "data:image/" in contenido, "Las imágenes deberían ir incrustadas"


def test_el_js_no_apunta_a_una_url_absoluta():
    """Debe ser mismo origen: una URL absoluta rompería el despliegue."""
    contenido = JS.read_text(encoding="utf-8")
    llamadas = re.findall(r"fetch\(\s*[\"']([^\"']+)", contenido)
    assert llamadas, "No se encontró ninguna llamada fetch()"
    for url in llamadas:
        assert url.startswith("/"), f"fetch() usa una URL absoluta: {url}"
