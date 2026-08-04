"""Tests del registro de modelos y del alias champion.

El backend es SQLite y no file://, porque el FileStore de MLflow no
implementa el Model Registry: con file:// los alias fallan.
"""
import mlflow
import pytest
from mlflow.tracking import MlflowClient

from src.features import clean, load_raw, split_data
from src.register import (
    ALIAS,
    best_run_id,
    champion_info,
    register_run,
    set_champion,
)
from src.train import RUN_CONFIGS, train_one


@pytest.fixture
def experimento(tmp_path):
    """Experimento aislado con dos runs de verdad."""
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path}/mlflow.db")
    nombre = "test-registro"
    mlflow.set_experiment(nombre)

    df = clean(load_raw("data/telco_churn.csv"))
    X_tr, X_te, y_tr, y_te = split_data(df)
    X_tr, X_te = X_tr.head(500), X_te.head(150)
    y_tr, y_te = y_tr.head(500), y_te.head(150)

    ids = [train_one(c, X_tr, y_tr, X_te, y_te) for c in RUN_CONFIGS[:2]]
    return nombre, ids


def test_best_run_id_elige_el_de_mayor_roc_auc(experimento):
    nombre, ids = experimento
    aucs = {i: mlflow.get_run(i).data.metrics["roc_auc"] for i in ids}
    assert best_run_id(nombre) == max(aucs, key=aucs.get)


def test_best_run_id_falla_si_el_experimento_no_existe(experimento):
    with pytest.raises(ValueError, match="No existe el experimento"):
        best_run_id("experimento-que-no-existe")


def test_register_run_crea_versiones_incrementales(experimento):
    _, ids = experimento
    assert register_run(ids[0], "modelo-incremental") == 1
    assert register_run(ids[1], "modelo-incremental") == 2


def test_set_champion_apunta_el_alias_a_la_version(experimento):
    _, ids = experimento
    version = register_run(ids[0], "modelo-alias")
    set_champion(version, "modelo-alias")

    mv = MlflowClient().get_model_version_by_alias("modelo-alias", ALIAS)
    assert int(mv.version) == version


def test_el_alias_se_puede_mover_a_otra_version(experimento):
    """Promover un modelo a producción es exactamente esto: mover el alias."""
    _, ids = experimento
    v1 = register_run(ids[0], "modelo-movil")
    v2 = register_run(ids[1], "modelo-movil")

    set_champion(v1, "modelo-movil")
    set_champion(v2, "modelo-movil")

    mv = MlflowClient().get_model_version_by_alias("modelo-movil", ALIAS)
    assert int(mv.version) == v2


def test_el_modelo_del_alias_se_puede_cargar_y_predecir(experimento):
    """La prueba que de verdad importa: el URI del alias sirve para inferir."""
    _, ids = experimento
    version = register_run(ids[0], "modelo-cargable")
    set_champion(version, "modelo-cargable")

    modelo = mlflow.sklearn.load_model(f"models:/modelo-cargable@{ALIAS}")

    df = clean(load_raw("data/telco_churn.csv"))
    _, X_te, _, _ = split_data(df)
    proba = modelo.predict_proba(X_te.head(5))
    assert proba.shape == (5, 2)
    assert all(0.0 <= p <= 1.0 for p in proba[:, 1])


def test_champion_info_devuelve_la_trazabilidad(experimento):
    """version + run_id son lo que el endpoint /model-info debe exponer."""
    _, ids = experimento
    version = register_run(ids[0], "modelo-trazable")
    set_champion(version, "modelo-trazable")

    info = champion_info("modelo-trazable")
    assert info["version"] == str(version)
    assert info["run_id"] == ids[0]
    assert info["alias"] == ALIAS
