# tests/test_api.py
from unittest.mock import patch

import numpy as np
import pytest
from fastapi.testclient import TestClient

from src.api.schemas import CustomerFeatures

CLIENTE_VALIDO = {
    "tenure": 12, "MonthlyCharges": 70.35, "TotalCharges": 844.20,
    "gender": "Female", "SeniorCitizen": "0", "Partner": "Yes",
    "Dependents": "No", "PhoneService": "Yes", "MultipleLines": "No",
    "InternetService": "Fiber optic", "OnlineSecurity": "No",
    "OnlineBackup": "Yes", "DeviceProtection": "No", "TechSupport": "No",
    "StreamingTV": "Yes", "StreamingMovies": "No",
    "Contract": "Month-to-month", "PaperlessBilling": "Yes",
    "PaymentMethod": "Electronic check",
}


class ModeloFalso:
    def predict(self, X):
        return np.array([1] * len(X))

    def predict_proba(self, X):
        return np.array([[0.3, 0.7]] * len(X))


@pytest.fixture
def cliente(monkeypatch):
    monkeypatch.setenv("POD_NAME", "pod-de-prueba")
    from src.api import main
    main.MODELO = ModeloFalso()
    main.INFO = main.ModelInfo(
        model_name="telco-churn", version="2", run_id="abc123",
        alias="champion", loaded_at="2026-08-03T10:00:00",
    )
    return TestClient(main.app)


def test_schema_acepta_cliente_valido():
    assert CustomerFeatures(**CLIENTE_VALIDO).tenure == 12


def test_schema_rechaza_categoria_invalida():
    malo = {**CLIENTE_VALIDO, "Contract": "Contrato inventado"}
    with pytest.raises(Exception):
        CustomerFeatures(**malo)


def test_schema_rechaza_tenure_negativo():
    malo = {**CLIENTE_VALIDO, "tenure": -5}
    with pytest.raises(Exception):
        CustomerFeatures(**malo)


def test_health_responde_ok(cliente):
    r = cliente.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_ready_responde_200_con_modelo_cargado(cliente):
    assert cliente.get("/ready").status_code == 200


def test_ready_responde_503_sin_modelo(cliente):
    from src.api import main
    main.MODELO = None
    assert cliente.get("/ready").status_code == 503


def test_model_info_expone_la_trazabilidad(cliente):
    datos = cliente.get("/model-info").json()
    assert datos["model_name"] == "telco-churn"
    assert datos["run_id"] == "abc123"
    assert datos["alias"] == "champion"


def test_predict_devuelve_el_contrato_completo(cliente):
    r = cliente.post("/predict", json=CLIENTE_VALIDO)
    assert r.status_code == 200
    datos = r.json()
    assert datos["prediction"] == 1
    assert datos["probability"] == pytest.approx(0.7)
    assert datos["served_by"] == "pod-de-prueba"
    assert datos["model_version"] == "2"


def test_predict_rechaza_entrada_invalida_con_422(cliente):
    r = cliente.post("/predict", json={**CLIENTE_VALIDO, "Contract": "Inventado"})
    assert r.status_code == 422


def test_predict_responde_503_sin_modelo(cliente):
    from src.api import main
    main.MODELO = None
    assert cliente.post("/predict", json=CLIENTE_VALIDO).status_code == 503