"""Descarga el dataset Telco Customer Churn de IBM y lo guarda en data/.

El CSV está versionado en el repositorio, así que este script normalmente no
hace falta: existe para que la obtención del dato sea reproducible y auditable
en lugar de "alguien lo bajó de algún sitio".
"""
import sys
import urllib.request
from pathlib import Path

URL = (
    "https://raw.githubusercontent.com/IBM/"
    "telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv"
)
DESTINO = Path("data/telco_churn.csv")

FILAS_ESPERADAS = 7043
COLUMNAS_ESPERADAS = 21


def descargar(url: str = URL, destino: Path = DESTINO) -> Path:
    """Descarga el CSV y verifica que tiene la forma esperada."""
    destino.parent.mkdir(parents=True, exist_ok=True)

    print(f"Descargando desde {url}")
    urllib.request.urlretrieve(url, destino)

    tamano_kb = destino.stat().st_size / 1024
    print(f"Guardado en {destino} ({tamano_kb:.0f} KB)")
    return destino


def verificar(destino: Path = DESTINO) -> None:
    """Comprueba la forma del CSV descargado.

    Falla ruidosamente si el fichero remoto cambió: es preferible a entrenar
    sobre datos distintos sin enterarse.
    """
    import pandas as pd

    df = pd.read_csv(destino)
    filas, columnas = df.shape

    if (filas, columnas) != (FILAS_ESPERADAS, COLUMNAS_ESPERADAS):
        raise SystemExit(
            f"El dataset no tiene la forma esperada: {filas}x{columnas}, "
            f"se esperaba {FILAS_ESPERADAS}x{COLUMNAS_ESPERADAS}. "
            "El fichero remoto pudo haber cambiado."
        )

    tasa = (df["Churn"] == "Yes").mean()
    print(f"Verificado: {filas} filas x {columnas} columnas, churn={tasa:.1%}")


def main() -> int:
    if DESTINO.exists():
        print(f"{DESTINO} ya existe. Bórralo si quieres volver a descargarlo.")
        verificar()
        return 0

    descargar()
    verificar()
    return 0


if __name__ == "__main__":
    sys.exit(main())
