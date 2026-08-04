"""Entrenamiento de los 6 runs comparables con tracking en MLflow.

Los 6 runs comparten split, semilla y conjunto de métricas. Eso es
exactamente lo que los hace comparables entre sí en la vista de comparación
de MLflow, y lo que permite argumentar por qué se eligió el modelo que se
despliega.
"""
import matplotlib

matplotlib.use("Agg")  # backend sin display, para que funcione en el VPS

import matplotlib.pyplot as plt  # noqa: E402
import mlflow  # noqa: E402
import mlflow.sklearn  # noqa: E402
import pandas as pd  # noqa: E402
from mlflow.models import infer_signature  # noqa: E402
from sklearn.ensemble import (  # noqa: E402
    GradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.linear_model import LogisticRegression  # noqa: E402
from sklearn.metrics import (  # noqa: E402
    ConfusionMatrixDisplay,
    accuracy_score,
    f1_score,
    recall_score,
    roc_auc_score,
)
from sklearn.pipeline import Pipeline  # noqa: E402

from src.features import (  # noqa: E402
    EXPERIMENT_NAME,
    RANDOM_STATE,
    build_preprocessor,
    clean,
    load_raw,
    split_data,
)

# Seis configuraciones (el mínimo exigido son cinco). Se varía un
# hiperparámetro por familia de modelo para que la comparación sea legible.
RUN_CONFIGS = [
    {"nombre": "logreg-C0.1", "kind": "logreg", "params": {"C": 0.1}},
    {"nombre": "logreg-C1.0", "kind": "logreg", "params": {"C": 1.0}},
    {"nombre": "rf-100-d5", "kind": "rf", "params": {"n_estimators": 100, "max_depth": 5}},
    {"nombre": "rf-300-d10", "kind": "rf", "params": {"n_estimators": 300, "max_depth": 10}},
    {"nombre": "gb-lr0.05", "kind": "gb", "params": {"learning_rate": 0.05}},
    {"nombre": "gb-lr0.2", "kind": "gb", "params": {"learning_rate": 0.2}},
]


def build_model(kind: str, params: dict) -> Pipeline:
    """Envuelve el clasificador junto al preprocesador compartido.

    Devolver un Pipeline es lo que hace que el artefacto guardado en MLflow
    contenga también el preprocesamiento: el servicio de inferencia recibe el
    registro crudo y no reimplementa ninguna transformación.
    """
    if kind == "logreg":
        clasificador = LogisticRegression(
            max_iter=1000, random_state=RANDOM_STATE, **params
        )
    elif kind == "rf":
        clasificador = RandomForestClassifier(random_state=RANDOM_STATE, **params)
    elif kind == "gb":
        clasificador = GradientBoostingClassifier(random_state=RANDOM_STATE, **params)
    else:
        raise ValueError(f"Tipo de modelo desconocido: {kind}")

    return Pipeline(
        [("preprocessor", build_preprocessor()), ("classifier", clasificador)]
    )


def evaluate(model: Pipeline, X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    """Calcula las métricas del run.

    ROC-AUC es la principal: con un 26,5 % de positivos, la exactitud es
    engañosa (predecir siempre "no abandona" da 73,5 % sin aprender nada) y
    además ROC-AUC no depende del umbral de decisión.

    Se acompaña de recall porque en un caso de abandono el coste de un falso
    negativo —un cliente que se va sin ser detectado— supera al de un falso
    positivo.
    """
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    return {
        "roc_auc": float(roc_auc_score(y_test, y_proba)),
        "f1": float(f1_score(y_test, y_pred)),
        "recall": float(recall_score(y_test, y_pred)),
        "accuracy": float(accuracy_score(y_test, y_pred)),
    }


def _log_confusion_matrix(model: Pipeline, X_test: pd.DataFrame, y_test: pd.Series) -> None:
    """Guarda la matriz de confusión como artefacto del run."""
    figura, eje = plt.subplots(figsize=(4, 4))
    ConfusionMatrixDisplay.from_estimator(
        model, X_test, y_test, ax=eje, colorbar=False, cmap="Blues"
    )
    eje.set_title("Matriz de confusión")
    figura.tight_layout()
    mlflow.log_figure(figura, "matriz_confusion.png")
    plt.close(figura)


def train_one(
    config: dict,
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
) -> str:
    """Entrena, evalúa y registra un run. Devuelve su run_id."""
    with mlflow.start_run(run_name=config["nombre"]) as run:
        modelo = build_model(config["kind"], config["params"])
        modelo.fit(X_train, y_train)

        mlflow.log_param("modelo", config["kind"])
        mlflow.log_param("random_state", RANDOM_STATE)
        mlflow.log_param("n_train", len(X_train))
        mlflow.log_param("n_test", len(X_test))
        for clave, valor in config["params"].items():
            mlflow.log_param(clave, valor)

        metricas = evaluate(modelo, X_test, y_test)
        mlflow.log_metrics(metricas)

        firma = infer_signature(X_train, modelo.predict(X_train))
        mlflow.sklearn.log_model(
            modelo,
            name="model",
            signature=firma,
            input_example=X_train.head(3),
        )
        _log_confusion_matrix(modelo, X_test, y_test)

        print(
            f"{config['nombre']:<14} roc_auc={metricas['roc_auc']:.4f} "
            f"f1={metricas['f1']:.4f} recall={metricas['recall']:.4f}"
        )
        return run.info.run_id


def main() -> None:
    """Ejecuta los 6 runs contra el servidor MLflow configurado.

    Requiere MLFLOW_TRACKING_URI apuntando al servidor del VPS.
    """
    mlflow.set_experiment(EXPERIMENT_NAME)

    df = clean(load_raw("data/telco_churn.csv"))
    X_train, X_test, y_train, y_test = split_data(df)
    print(
        f"Experimento '{EXPERIMENT_NAME}' · "
        f"entrenamiento={len(X_train)} filas · prueba={len(X_test)} filas\n"
    )

    for config in RUN_CONFIGS:
        train_one(config, X_train, y_train, X_test, y_test)

    print(f"\n{len(RUN_CONFIGS)} runs registrados en {mlflow.get_tracking_uri()}")


if __name__ == "__main__":
    main()
