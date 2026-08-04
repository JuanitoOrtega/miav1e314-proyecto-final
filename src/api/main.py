"""Servicio de inferencia.

El modelo se carga del Model Registry por alias al arrancar. Esa es la
referencia que exige el enunciado: no hay ninguna ruta de fichero suelta
"""
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import mlflow
import mlflow.sklearn
import pandas as pd
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from mlflow.tracking import MlflowClient

from src.api.schemas import CustomerFeatures, ModelInfo, PredictionResponse
from src.features import ALL_FEATURES, MODEL_NAME

ALIAS = os.getenv("MODEL_ALIAS", "champion")
MODEL_URI = f"models:/{MODEL_NAME}@{ALIAS}"
POD_NAME = os.getenv("POD_NAME", "local")

MODELO = None
INFO: ModelInfo | None = None

app = FastAPI(
    title="Telco Churn API",
    description="Servicio de inferencia de abandono de clientes",
    version="1.0.0",
)


def load_model_with_retry(
    uri: str = MODEL_URI, max_attempts: int = 5, base_delay: float = 2.0
) -> tuple[object, ModelInfo]:
    """Carga el modelo con reintentos y backoff exponencial.

    Los reintentos existen porque los pods pueden arrancar antes de que
    MLflow esté listo. Si aun así falla, el readinessProbe mantiene al pod
    fuera del Service y los pods sanos siguen atendiendo.
    """
    ultimo_error: Exception | None = None
    for intento in range(1, max_attempts + 1):
        try:
            # mlflow.sklearn y no mlflow.pyfunc: pyfunc no expone
            # predict_proba, y necesitamos la probabilidad, no solo la clase.
            modelo = mlflow.sklearn.load_model(uri)
            version = MlflowClient().get_model_version_by_alias(MODEL_NAME, ALIAS)
            info = ModelInfo(
                model_name=MODEL_NAME,
                version=str(version.version),
                run_id=version.run_id,
                alias=ALIAS,
                loaded_at=datetime.now(timezone.utc).isoformat(),
            )
            print(f"Modelo cargado: {MODEL_NAME} v{version.version} (run {version.run_id})")
            return modelo, info
        except Exception as exc:  # noqa: BLE001
            ultimo_error = exc
            espera = base_delay * (2 ** (intento - 1))
            print(f"Intento {intento}/{max_attempts} falló: {exc}. Reintento en {espera:.0f}s")
            if intento < max_attempts:
                time.sleep(espera)

    print(f"No se pudo cargar el modelo tras {max_attempts} intentos: {ultimo_error}")
    raise RuntimeError(str(ultimo_error))


@app.on_event("startup")
def startup() -> None:
    global MODELO, INFO
    try:
        MODELO, INFO = load_model_with_retry()
    except RuntimeError:
        MODELO, INFO = None, None


@app.get("/health")
def health() -> dict:
    """Liveness: el proceso está vivo. No mira el modelo."""
    return {"status": "ok", "pod": POD_NAME}


@app.get("/ready")
def ready() -> JSONResponse:
    """Readiness: solo 200 si el modelo está cargado."""
    if MODELO is None:
        return JSONResponse(status_code=503, content={"status": "modelo no cargado"})
    return JSONResponse(status_code=200, content={"status": "listo"})


@app.get("/model-info", response_model=ModelInfo)
def model_info() -> ModelInfo:
    """Trazabilidad: qué versión y qué run está sirviendo peticiones."""
    if INFO is None:
        raise HTTPException(status_code=503, detail="modelo no cargado")
    return INFO


@app.post("/predict", response_model=PredictionResponse)
def predict(cliente: CustomerFeatures) -> PredictionResponse:
    """Inferencia. Devuelve served_by para demostrar el balanceo de carga."""
    if MODELO is None or INFO is None:
        raise HTTPException(status_code=503, detail="modelo no cargado")

    fila = pd.DataFrame([cliente.model_dump()])[ALL_FEATURES]
    proba = float(MODELO.predict_proba(fila)[0][1])

    return PredictionResponse(
        prediction=int(proba >= 0.5),
        probability=round(proba, 4),
        served_by=POD_NAME,
        model_version=INFO.version,
    )


_estaticos = Path(__file__).parent / "static"
if _estaticos.exists():
    app.mount("/", StaticFiles(directory=_estaticos, html=True), name="static")