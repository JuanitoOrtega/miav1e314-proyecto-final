"""Tests del entrenamiento y su registro en MLflow."""
import mlflow
import pytest
from sklearn.pipeline import Pipeline

from src.features import clean, load_raw, split_data
from src.train import RUN_CONFIGS, build_model, evaluate, train_one


@pytest.fixture(scope="module")
def datos():
    """Submuestra para que los tests corran rápido sin perder realismo."""
    df = clean(load_raw("data/telco_churn.csv"))
    X_tr, X_te, y_tr, y_te = split_data(df)
    return X_tr.head(800), X_te.head(200), y_tr.head(800), y_te.head(200)


def test_hay_al_menos_6_configuraciones():
    """El enunciado exige un mínimo de 5 runs comparables."""
    assert len(RUN_CONFIGS) >= 6


def test_las_configuraciones_tienen_nombres_unicos():
    nombres = [c["nombre"] for c in RUN_CONFIGS]
    assert len(set(nombres)) == len(RUN_CONFIGS)


def test_se_cubren_los_tres_tipos_de_modelo():
    assert {c["kind"] for c in RUN_CONFIGS} == {"logreg", "rf", "gb"}


def test_build_model_devuelve_pipeline_con_preprocesador():
    """El preprocesador va DENTRO del modelo: es lo que evita el train/serve skew."""
    modelo = build_model("logreg", {"C": 1.0})
    assert isinstance(modelo, Pipeline)
    assert "preprocessor" in modelo.named_steps
    assert "classifier" in modelo.named_steps


def test_build_model_rechaza_tipo_desconocido():
    with pytest.raises(ValueError, match="Tipo de modelo desconocido"):
        build_model("red-neuronal-magica", {})


def test_evaluate_devuelve_las_cuatro_metricas(datos):
    X_tr, X_te, y_tr, y_te = datos
    modelo = build_model("logreg", {"C": 1.0}).fit(X_tr, y_tr)
    metricas = evaluate(modelo, X_te, y_te)
    assert set(metricas) == {"roc_auc", "f1", "recall", "accuracy"}
    assert all(0.0 <= v <= 1.0 for v in metricas.values())


def test_evaluate_supera_al_azar(datos):
    """Sanidad mínima: el modelo aprende algo, aunque la nota no dependa de ello."""
    X_tr, X_te, y_tr, y_te = datos
    modelo = build_model("logreg", {"C": 1.0}).fit(X_tr, y_tr)
    assert evaluate(modelo, X_te, y_te)["roc_auc"] > 0.7


def test_train_one_registra_un_run_completo(tmp_path, datos):
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path}/mlflow.db")
    mlflow.set_experiment("test-entrenamiento")

    X_tr, X_te, y_tr, y_te = datos
    run_id = train_one(RUN_CONFIGS[0], X_tr, y_tr, X_te, y_te)

    run = mlflow.get_run(run_id)
    assert run.info.status == "FINISHED"
    assert "roc_auc" in run.data.metrics
    assert run.data.params["modelo"] == RUN_CONFIGS[0]["kind"]
    assert run.data.params["random_state"] == "42"


def test_los_runs_son_comparables_entre_si(tmp_path, datos):
    """Comparables = mismas métricas registradas sobre el mismo split.

    Es lo que permite usar la vista de comparación de MLflow para argumentar
    la elección del modelo desplegado.
    """
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path}/mlflow.db")
    mlflow.set_experiment("test-comparables")

    X_tr, X_te, y_tr, y_te = datos
    ids = [train_one(c, X_tr, y_tr, X_te, y_te) for c in RUN_CONFIGS[:3]]

    metricas = [set(mlflow.get_run(i).data.metrics) for i in ids]
    assert all(m == metricas[0] for m in metricas)
    assert "roc_auc" in metricas[0]
