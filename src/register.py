"""Registro de modelos en el Model Registry y gestión del alias champion.

El alias 'champion' es la referencia que consume el servicio de inferencia:
`models:/telco-churn@champion`. Promover un modelo a producción es
exactamente mover este alias, sin reconstruir la imagen ni tocar código.

Es lo que exige §3.3.2 del enunciado: el servicio consume el modelo por esa
referencia, no por una ruta de fichero suelta.
"""
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import Pipeline

from src.features import (
    EXPERIMENT_NAME,
    MODEL_NAME,
    RANDOM_STATE,
    build_preprocessor,
    clean,
    load_raw,
    split_data,
)

ALIAS = "champion"


def best_run_id(experiment_name: str = EXPERIMENT_NAME, metric: str = "roc_auc") -> str:
    """Devuelve el run_id con la métrica más alta del experimento."""
    experimento = mlflow.get_experiment_by_name(experiment_name)
    if experimento is None:
        raise ValueError(f"No existe el experimento '{experiment_name}'")

    runs = mlflow.search_runs(
        experiment_ids=[experimento.experiment_id],
        order_by=[f"metrics.{metric} DESC"],
        max_results=1,
    )
    if runs.empty:
        raise ValueError(f"El experimento '{experiment_name}' no tiene runs")
    return runs.iloc[0]["run_id"]


def register_run(run_id: str, model_name: str = MODEL_NAME) -> int:
    """Registra el modelo de un run como una nueva versión del registro."""
    resultado = mlflow.register_model(f"runs:/{run_id}/model", model_name)
    return int(resultado.version)


def set_champion(version: int, model_name: str = MODEL_NAME) -> None:
    """Apunta el alias 'champion' a la versión indicada."""
    MlflowClient().set_registered_model_alias(model_name, ALIAS, str(version))
    print(f"Alias '{ALIAS}' -> {model_name} v{version}")


def champion_info(model_name: str = MODEL_NAME) -> dict:
    """Datos de trazabilidad de la versión que sirve en producción.

    Es la información que el endpoint /model-info expone para poder
    demostrar, en vivo, que el modelo desplegado es el del experimento.
    """
    mv = MlflowClient().get_model_version_by_alias(model_name, ALIAS)
    return {
        "model_name": model_name,
        "version": str(mv.version),
        "run_id": mv.run_id,
        "alias": ALIAS,
    }


def register_dummy(model_name: str = MODEL_NAME) -> int:
    """Registra un DummyClassifier para desbloquear el desarrollo de la API.

    Se usa el día 1, antes de que exista el modelo bueno, para que el equipo
    de la API trabaje contra un contrato real en lugar de un None. Cuando
    llega el modelo de verdad no cambia una sola línea del servicio.
    """
    df = clean(load_raw("data/telco_churn.csv"))
    X_train, _, y_train, _ = split_data(df)

    modelo = Pipeline(
        [
            ("preprocessor", build_preprocessor()),
            (
                "classifier",
                DummyClassifier(strategy="stratified", random_state=RANDOM_STATE),
            ),
        ]
    ).fit(X_train, y_train)

    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="dummy-placeholder") as run:
        mlflow.log_param("modelo", "dummy")
        mlflow.sklearn.log_model(modelo, name="model", input_example=X_train.head(3))
        run_id = run.info.run_id

    version = register_run(run_id, model_name)
    set_champion(version, model_name)
    return version


def main() -> None:
    """Registra el mejor run del experimento y lo promueve a champion."""
    run_id = best_run_id()
    version = register_run(run_id)
    set_champion(version)

    auc = mlflow.get_run(run_id).data.metrics.get("roc_auc")
    print(f"\n{MODEL_NAME} v{version}  <-  run {run_id}  (roc_auc={auc:.4f})")
    print("Reinicia los pods para que carguen la nueva versión:")
    print("  kubectl rollout restart deployment/telco-churn-api")


if __name__ == "__main__":
    main()
