# telco-churn-mlops — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Llevar un modelo de predicción de abandono de clientes desde el entrenamiento trazable en MLflow hasta un despliegue con 3 réplicas en Kubernetes accesible por HTTPS, con detección automatizada de data drift y concept drift.

**Architecture:** Dos planos en un VPS Ubuntu 24.04. El plano de MLOps (MLflow Server + PostgreSQL) corre en Docker Compose fuera del clúster. El plano de servicio (FastAPI + modelo + UI estática) corre en k3s con 3 réplicas tras un `Service` NodePort. Cada pod carga el modelo del Model Registry por alias `@champion` al arrancar. nginx en el host termina TLS para dos subdominios.

**Tech Stack:** Python 3.12, scikit-learn, MLflow ≥ 2.9, FastAPI, Pydantic, scipy, pytest, Docker, k3s, nginx, certbot.

**Spec:** [`docs/superpowers/specs/2026-08-03-telco-churn-mlops-design.md`](../specs/2026-08-03-telco-churn-mlops-design.md)

---

## Global Constraints

Requisitos que aplican a **todas** las tareas:

- **Python 3.12.** Toda la ejecución local y la imagen base del contenedor.
- **MLflow fijado en `2.19.0`, cliente y servidor.** El piso de `>= 2.9` es
  por los alias del Model Registry (`models:/nombre@alias`), pero cliente y
  servidor deben ir en la **misma línea de versión**: la API de `log_model`
  cambió en MLflow 3.x (`name=` sustituye a `artifact_path=`), así que un
  cliente 3.x contra el servidor `v2.19.0` del `docker-compose.yml` rompe el
  registro de modelos. En `requirements.in` va `mlflow==2.19.0`, no `>=2.9`.
- **`requirements.txt` con todas las versiones fijadas con `==`**, incluida la de MLflow. Se genera con `pip freeze`, nunca a mano.
- **Semilla fija `random_state = 42`** en todo split y todo modelo.
- **Nombre del modelo registrado: `telco-churn`.** Alias de producción: `champion`.
- **Nombre del experimento MLflow: `telco-churn-experimento`.**
- **Etiqueta de imagen: `telco-churn-api:v1`.** Nunca `latest`.
- **Los tests nunca dependen del VPS.** Usan `MLFLOW_TRACKING_URI=file://<tmp>` o mocks.
- **Idioma:** código y nombres de función en inglés; docstrings, documentación y mensajes de commit en español.
- **Commits en español**, con prefijo convencional (`feat:`, `test:`, `docs:`, `chore:`, `fix:`).
- **`infra/.env` NUNCA se commitea.** Solo `infra/.env.example`.

## Convención de tipos de tarea

| Marca | Significado |
|---|---|
| **[LOCAL]** | Código. Se desarrolla en la máquina de cada integrante con ciclo TDD. No requiere el VPS. |
| **[VPS]** | Runbook. Comandos que el equipo ejecuta a mano en el servidor, pegando la salida como evidencia. |

## Orden y paralelismo

```
Día 1:  T1 ─┬─ T2 ─── T3 ─── T4 ─── T5          (#1 modelo)
            ├─ T6 [VPS] ── T7 [VPS]              (#5 infra)
            └─ T8 ─── T9                          (#2 API)
Día 2:  T10 ─── T11 [VPS]                         (#3 kubernetes)
Día 3:  T12 [VPS] ─── T13 [VPS]                   (#5 TLS, #3 demos)
        T14 ─── T15 ─── T16                       (#4 drift)
Día 4:  T17 ─── T18                               (#4 concept drift, #5 UI)
Día 5:  T19 ─── T20                               (documentación y evidencia)
```

**Dependencia crítica rota a propósito:** T5 registra un `DummyClassifier` bajo el alias `champion` *antes* de que exista el modelo bueno, para que T8 (la API) pueda desarrollarse contra un contrato real desde el día 1.

---

## Estructura de ficheros

| Fichero | Responsabilidad |
|---|---|
| `requirements.txt` | Dependencias fijadas con `==` |
| `data/telco_churn.csv` | Dataset crudo versionado |
| `src/features.py` | Constantes de esquema, limpieza, split y preprocesador. Compartido train↔serve |
| `src/train.py` | Los 6 runs con tracking en MLflow |
| `src/register.py` | Registro de versiones y gestión del alias `champion` |
| `src/api/schemas.py` | Contratos Pydantic de entrada y salida |
| `src/api/main.py` | Aplicación FastAPI y carga del modelo |
| `src/api/static/index.html` | UI web |
| `src/api/static/app.js` | Lógica de la UI |
| `drift/detectors.py` | KS, PSI, Chi², Cramér's V. Sin I/O |
| `drift/generators.py` | Construcción de lotes limpios y derivados |
| `drift/check.py` | Puerta CLI: exit 0 verde / exit 1 rojo |
| `drift/monitor.py` | ROC-AUC por lote, criterio de reentrenamiento, gráfica |
| `tests/` | Tests de `src/` |
| `drift/tests/` | Tests de `drift/` |
| `infra/docker-compose.yml` | MLflow Server + PostgreSQL |
| `infra/nginx/*.conf.template` | Vhosts de los dos subdominios |
| `k8s/deployment.yaml` | 3 réplicas, probes, límites |
| `k8s/service.yaml` | NodePort 30080 |
| `Dockerfile` | Imagen del servicio |
| `docs/runbooks/*.md` | Procedimientos ejecutables en el VPS |

---

# Tarea 1 — Andamiaje del repositorio y dependencias **[LOCAL]**

**Files:**
- Create: `.gitignore`, `requirements.in`, `requirements.txt`, `pytest.ini`, `README.md`
- Create: `src/__init__.py`, `src/api/__init__.py`, `drift/__init__.py`, `tests/__init__.py`, `drift/tests/__init__.py`

**Interfaces:**
- Consumes: nada
- Produces: entorno virtual funcional y `pytest` ejecutable

- [ ] **Step 1: Crear el `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
.venv/
venv/
.pytest_cache/
.coverage
htmlcov/
mlruns/
mlartifacts/
infra/.env
data/batches/
docs/evidencias/*.png
!docs/evidencias/.gitkeep
.DS_Store
.idea/
.vscode/
```

- [ ] **Step 2: Crear `requirements.in` con los pisos de versión**

```
scikit-learn>=1.4
pandas>=2.1
numpy>=1.26
scipy>=1.11
mlflow==2.19.0
fastapi>=0.110
uvicorn[standard]>=0.27
pydantic>=2.6
psycopg2-binary>=2.9
matplotlib>=3.8
pytest>=8.0
httpx>=0.27
```

- [ ] **Step 3: Crear el entorno virtual e instalar**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.in
```

- [ ] **Step 4: Congelar las versiones exactas**

```bash
pip freeze > requirements.txt
grep -E "^(mlflow|scikit-learn|fastapi)==" requirements.txt
```

Esperado: tres líneas con `==` y versiones concretas. **Verificar que `mlflow==` sea 2.9 o superior**; si no, `pip install --upgrade mlflow` y volver a congelar.

- [ ] **Step 5: Crear `pytest.ini`**

```ini
[pytest]
testpaths = tests drift/tests
python_files = test_*.py
addopts = -v --strict-markers
```

- [ ] **Step 6: Crear los paquetes Python vacíos**

```bash
mkdir -p src/api/static drift/tests tests data docs/evidencias k8s infra/nginx docs/runbooks
touch src/__init__.py src/api/__init__.py drift/__init__.py drift/tests/__init__.py tests/__init__.py
touch docs/evidencias/.gitkeep
```

- [ ] **Step 7: Verificar que pytest arranca**

Run: `pytest --collect-only`
Esperado: `no tests ran` sin errores de importación.

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "chore: andamiaje del repositorio y dependencias fijadas"
```

---

# Tarea 2 — Dataset y validación de calidad **[LOCAL]**

**Files:**
- Create: `data/telco_churn.csv`, `scripts/download_data.py`, `tests/test_data.py`

**Interfaces:**
- Produces: `data/telco_churn.csv` con 7.043 filas y 21 columnas

- [ ] **Step 1: Escribir el test de calidad del dataset**

```python
# tests/test_data.py
from pathlib import Path
import pandas as pd

CSV = Path("data/telco_churn.csv")

def test_dataset_existe():
    assert CSV.exists(), "Ejecuta: python scripts/download_data.py"

def test_dimensiones_esperadas():
    df = pd.read_csv(CSV)
    assert df.shape == (7043, 21)

def test_columnas_esperadas():
    df = pd.read_csv(CSV)
    esperadas = {
        "customerID", "gender", "SeniorCitizen", "Partner", "Dependents",
        "tenure", "PhoneService", "MultipleLines", "InternetService",
        "OnlineSecurity", "OnlineBackup", "DeviceProtection", "TechSupport",
        "StreamingTV", "StreamingMovies", "Contract", "PaperlessBilling",
        "PaymentMethod", "MonthlyCharges", "TotalCharges", "Churn",
    }
    assert set(df.columns) == esperadas

def test_tasa_de_churn_conocida():
    df = pd.read_csv(CSV)
    tasa = (df["Churn"] == "Yes").mean()
    assert 0.26 < tasa < 0.27

def test_totalcharges_tiene_blancos_conocidos():
    """Documenta el problema de calidad: 11 blancos con tenure = 0."""
    df = pd.read_csv(CSV)
    blancos = df["TotalCharges"].astype(str).str.strip() == ""
    assert blancos.sum() == 11
    assert (df.loc[blancos, "tenure"] == 0).all()
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `pytest tests/test_data.py -v`
Esperado: FAIL con el mensaje "Ejecuta: python scripts/download_data.py"

- [ ] **Step 3: Escribir el script de descarga**

```python
# scripts/download_data.py
"""Descarga el dataset Telco Customer Churn de IBM y lo guarda en data/."""
from pathlib import Path
import urllib.request

URL = (
    "https://raw.githubusercontent.com/IBM/"
    "telco-customer-churn-on-icp4d/master/data/Telco-Customer-Churn.csv"
)
DESTINO = Path("data/telco_churn.csv")


def main() -> None:
    DESTINO.parent.mkdir(parents=True, exist_ok=True)
    print(f"Descargando desde {URL}")
    urllib.request.urlretrieve(URL, DESTINO)
    print(f"Guardado en {DESTINO} ({DESTINO.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Ejecutar la descarga**

```bash
python scripts/download_data.py
```

Esperado: fichero de ~955 KB. Si la URL falla, descargar manualmente de Kaggle (`blastchar/telco-customer-churn`) y guardar como `data/telco_churn.csv`.

- [ ] **Step 5: Ejecutar los tests**

Run: `pytest tests/test_data.py -v`
Esperado: 5 tests PASS

- [ ] **Step 6: Commit**

```bash
git add data/telco_churn.csv scripts/download_data.py tests/test_data.py
git commit -m "feat: dataset Telco Churn versionado con tests de calidad"
```

---

# Tarea 3 — Esquema, limpieza y preprocesador compartido **[LOCAL]**

**Files:**
- Create: `src/features.py`, `tests/test_features.py`

**Interfaces:**
- Consumes: `data/telco_churn.csv` (Tarea 2)
- Produces:
  - `NUMERIC_FEATURES: list[str]`, `CATEGORICAL_FEATURES: list[str]`, `ALL_FEATURES: list[str]`, `TARGET: str = "Churn"`, `MODEL_NAME: str = "telco-churn"`, `EXPERIMENT_NAME: str = "telco-churn-experimento"`, `RANDOM_STATE: int = 42`
  - `load_raw(path) -> pd.DataFrame`
  - `clean(df) -> pd.DataFrame` — devuelve `Churn` como int 0/1 y `TotalCharges` como float
  - `build_preprocessor() -> ColumnTransformer`
  - `split_data(df) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]` — `(X_train, X_test, y_train, y_test)`

- [ ] **Step 1: Escribir los tests**

```python
# tests/test_features.py
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer

from src.features import (
    ALL_FEATURES, CATEGORICAL_FEATURES, NUMERIC_FEATURES, TARGET,
    build_preprocessor, clean, load_raw, split_data,
)


@pytest.fixture(scope="module")
def df_limpio():
    return clean(load_raw("data/telco_churn.csv"))


def test_hay_3_numericas_y_16_categoricas():
    assert len(NUMERIC_FEATURES) == 3
    assert len(CATEGORICAL_FEATURES) == 16
    assert len(ALL_FEATURES) == 19


def test_customerid_no_es_feature():
    assert "customerID" not in ALL_FEATURES


def test_clean_convierte_target_a_entero(df_limpio):
    assert df_limpio[TARGET].dtype.kind in "iu"
    assert set(df_limpio[TARGET].unique()) == {0, 1}


def test_clean_convierte_totalcharges_a_float(df_limpio):
    assert df_limpio["TotalCharges"].dtype.kind == "f"
    assert df_limpio["TotalCharges"].isna().sum() == 0


def test_clean_imputa_los_11_blancos_con_cero(df_limpio):
    sin_antiguedad = df_limpio[df_limpio["tenure"] == 0]
    assert len(sin_antiguedad) == 11
    assert (sin_antiguedad["TotalCharges"] == 0.0).all()


def test_split_es_estratificado_y_reproducible(df_limpio):
    X_tr, X_te, y_tr, y_te = split_data(df_limpio)
    assert len(X_tr) + len(X_te) == len(df_limpio)
    assert abs(y_tr.mean() - y_te.mean()) < 0.01
    X_tr2, _, _, _ = split_data(df_limpio)
    pd.testing.assert_frame_equal(X_tr, X_tr2)


def test_split_solo_devuelve_features(df_limpio):
    X_tr, _, _, _ = split_data(df_limpio)
    assert list(X_tr.columns) == ALL_FEATURES


def test_preprocesador_transforma_sin_nan(df_limpio):
    X_tr, _, _, _ = split_data(df_limpio)
    pre = build_preprocessor()
    assert isinstance(pre, ColumnTransformer)
    matriz = pre.fit_transform(X_tr)
    assert matriz.shape[0] == len(X_tr)
    assert matriz.shape[1] > len(ALL_FEATURES)  # el one-hot expande


def test_preprocesador_tolera_categoria_no_vista(df_limpio):
    """handle_unknown='ignore' evita que una categoría nueva rompa producción."""
    X_tr, X_te, _, _ = split_data(df_limpio)
    pre = build_preprocessor().fit(X_tr)
    fila = X_te.iloc[[0]].copy()
    fila["Contract"] = "Contrato inventado"
    assert pre.transform(fila).shape[0] == 1
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `pytest tests/test_features.py -v`
Esperado: FAIL con `ModuleNotFoundError: No module named 'src.features'`

- [ ] **Step 3: Implementar `src/features.py`**

```python
"""Esquema del dataset, limpieza y preprocesamiento.

Este módulo es la ÚNICA definición del preprocesamiento. El mismo
ColumnTransformer se serializa dentro del modelo MLflow, de modo que el
servicio de inferencia nunca reimplementa la transformación. Es lo que
evita el train/serve skew.
"""
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler

RANDOM_STATE = 42
TEST_SIZE = 0.2
TARGET = "Churn"
ID_COLUMN = "customerID"
MODEL_NAME = "telco-churn"
EXPERIMENT_NAME = "telco-churn-experimento"

NUMERIC_FEATURES = ["tenure", "MonthlyCharges", "TotalCharges"]

CATEGORICAL_FEATURES = [
    "gender", "SeniorCitizen", "Partner", "Dependents", "PhoneService",
    "MultipleLines", "InternetService", "OnlineSecurity", "OnlineBackup",
    "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies",
    "Contract", "PaperlessBilling", "PaymentMethod",
]

ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def load_raw(path: str | Path) -> pd.DataFrame:
    """Lee el CSV crudo sin transformar nada."""
    return pd.read_csv(path)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica las dos correcciones de calidad conocidas del dataset.

    1. TotalCharges viene como texto y contiene 11 cadenas vacías, todas de
       clientes con tenure = 0 que nunca han sido facturados. Se imputan con
       0.0, que es el valor semánticamente correcto.
    2. Churn viene como 'Yes'/'No' y se convierte a 1/0.
    3. SeniorCitizen viene como entero 0/1 pero es conceptualmente
       categórica, así que se pasa a texto para que el OneHotEncoder la trate
       como tal.
    """
    df = df.copy()
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce").fillna(0.0)
    df[TARGET] = (df[TARGET] == "Yes").astype(int)
    df["SeniorCitizen"] = df["SeniorCitizen"].astype(str)
    return df


def build_preprocessor() -> ColumnTransformer:
    """Escala las numéricas y aplica one-hot a las categóricas.

    handle_unknown='ignore' es deliberado: en producción puede llegar una
    categoría que no existía al entrenar, y el servicio debe responder en
    lugar de reventar.
    """
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )


def split_data(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """División estratificada 80/20 con semilla fija."""
    X = df[ALL_FEATURES]
    y = df[TARGET]
    return train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )
```

- [ ] **Step 4: Ejecutar los tests**

Run: `pytest tests/test_features.py -v`
Esperado: 9 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/features.py tests/test_features.py
git commit -m "feat: esquema, limpieza y preprocesador compartido train/serve"
```

---

# Tarea 4 — Entrenamiento con los 6 runs de MLflow **[LOCAL]**

**Files:**
- Create: `src/train.py`, `tests/test_train.py`

**Interfaces:**
- Consumes: `src.features` (Tarea 3)
- Produces:
  - `RUN_CONFIGS: list[dict]` — 6 configuraciones con claves `nombre`, `kind`, `params`
  - `build_model(kind: str, params: dict) -> Pipeline`
  - `evaluate(model, X_test, y_test) -> dict[str, float]` — claves `roc_auc`, `f1`, `recall`, `accuracy`
  - `train_one(config, X_train, y_train, X_test, y_test) -> str` (devuelve `run_id`)
  - `main() -> None`

- [ ] **Step 1: Escribir los tests**

```python
# tests/test_train.py
import mlflow
import pandas as pd
import pytest
from sklearn.pipeline import Pipeline

from src.features import clean, load_raw, split_data
from src.train import RUN_CONFIGS, build_model, evaluate, train_one


@pytest.fixture(scope="module")
def datos():
    df = clean(load_raw("data/telco_churn.csv"))
    X_tr, X_te, y_tr, y_te = split_data(df)
    # Submuestra para que los tests sean rápidos
    return X_tr.head(800), X_te.head(200), y_tr.head(800), y_te.head(200)


def test_hay_6_configuraciones():
    assert len(RUN_CONFIGS) == 6


def test_las_configuraciones_tienen_nombres_unicos():
    nombres = [c["nombre"] for c in RUN_CONFIGS]
    assert len(set(nombres)) == 6


def test_se_cubren_los_tres_tipos_de_modelo():
    assert {c["kind"] for c in RUN_CONFIGS} == {"logreg", "rf", "gb"}


def test_build_model_devuelve_pipeline_con_preprocesador():
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


def test_train_one_registra_un_run_en_mlflow(tmp_path, datos):
    mlflow.set_tracking_uri(f"file://{tmp_path}/mlruns")
    mlflow.set_experiment("test-experimento")
    X_tr, X_te, y_tr, y_te = datos
    run_id = train_one(RUN_CONFIGS[0], X_tr, y_tr, X_te, y_te)

    run = mlflow.get_run(run_id)
    assert run.info.status == "FINISHED"
    assert "roc_auc" in run.data.metrics
    assert run.data.params  # se registraron hiperparámetros
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `pytest tests/test_train.py -v`
Esperado: FAIL con `ModuleNotFoundError: No module named 'src.train'`

- [ ] **Step 3: Implementar `src/train.py`**

```python
"""Entrenamiento de los 6 runs comparables con tracking en MLflow.

Los 6 runs comparten split, semilla y conjunto de métricas, que es lo que
los hace comparables entre sí en la vista de comparación de MLflow.
"""
import mlflow
import mlflow.sklearn
import pandas as pd
from mlflow.models import infer_signature
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, f1_score, recall_score, roc_auc_score
from sklearn.pipeline import Pipeline

from src.features import (
    EXPERIMENT_NAME, RANDOM_STATE, build_preprocessor, clean, load_raw, split_data,
)

RUN_CONFIGS = [
    {"nombre": "logreg-C0.1",  "kind": "logreg", "params": {"C": 0.1}},
    {"nombre": "logreg-C1.0",  "kind": "logreg", "params": {"C": 1.0}},
    {"nombre": "rf-100-d5",    "kind": "rf",     "params": {"n_estimators": 100, "max_depth": 5}},
    {"nombre": "rf-300-d10",   "kind": "rf",     "params": {"n_estimators": 300, "max_depth": 10}},
    {"nombre": "gb-lr0.05",    "kind": "gb",     "params": {"learning_rate": 0.05}},
    {"nombre": "gb-lr0.2",     "kind": "gb",     "params": {"learning_rate": 0.2}},
]


def build_model(kind: str, params: dict) -> Pipeline:
    """Envuelve el clasificador junto al preprocesador compartido.

    Devolver un Pipeline es lo que permite que el artefacto guardado en
    MLflow contenga también el preprocesamiento.
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
    """Calcula las métricas. ROC-AUC es la principal por el desbalance."""
    y_pred = model.predict(X_test)
    y_proba = model.predict_proba(X_test)[:, 1]
    return {
        "roc_auc": float(roc_auc_score(y_test, y_proba)),
        "f1": float(f1_score(y_test, y_pred)),
        "recall": float(recall_score(y_test, y_pred)),
        "accuracy": float(accuracy_score(y_test, y_pred)),
    }


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
        for clave, valor in config["params"].items():
            mlflow.log_param(clave, valor)

        metricas = evaluate(modelo, X_test, y_test)
        mlflow.log_metrics(metricas)

        firma = infer_signature(X_train, modelo.predict(X_train))
        # artifact_path= y NO name=: el parámetro 'name' es API de MLflow 3.x
        # y el servidor está fijado en v2.19.0 (infra/docker-compose.yml).
        # Verificado en ejecución real: con 2.19 'name' lanza TypeError.
        mlflow.sklearn.log_model(
            modelo,
            artifact_path="model",
            signature=firma,
            input_example=X_train.head(3),
        )

        print(f"{config['nombre']:<14} roc_auc={metricas['roc_auc']:.4f}")
        return run.info.run_id


def main() -> None:
    """Ejecuta los 6 runs contra el servidor MLflow configurado."""
    mlflow.set_experiment(EXPERIMENT_NAME)

    df = clean(load_raw("data/telco_churn.csv"))
    X_train, X_test, y_train, y_test = split_data(df)
    print(f"Entrenamiento: {len(X_train)} filas · Prueba: {len(X_test)} filas")

    for config in RUN_CONFIGS:
        train_one(config, X_train, y_train, X_test, y_test)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Ejecutar los tests**

Run: `pytest tests/test_train.py -v`
Esperado: 7 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/train.py tests/test_train.py
git commit -m "feat: entrenamiento de los 6 runs con tracking en MLflow"
```

---

# Tarea 5 — Registro de versiones y alias champion **[LOCAL]**

**Files:**
- Create: `src/register.py`, `tests/test_register.py`

**Interfaces:**
- Consumes: `src.features.MODEL_NAME`, `src.train` (Tareas 3 y 4)
- Produces:
  - `best_run_id(experiment_name: str, metric: str = "roc_auc") -> str`
  - `register_run(run_id: str, model_name: str = MODEL_NAME) -> int` (devuelve el número de versión)
  - `set_champion(version: int, model_name: str = MODEL_NAME) -> None`
  - `model_uri_for_run(run_id: str, artifact_name: str = "model") -> str` — resuelve el `models:/m-<id>` de MLflow 3
  - `champion_info(model_name: str = MODEL_NAME) -> dict` — `model_name`, `version`, `run_id`, `alias`
  - `register_dummy(model_name: str = MODEL_NAME) -> int` — modelo trivial para desbloquear la API el día 1

- [ ] **Step 1: Escribir los tests**

```python
# tests/test_register.py
import mlflow
import pytest
from mlflow.tracking import MlflowClient

from src.features import clean, load_raw, split_data
from src.register import best_run_id, register_run, set_champion
from src.train import RUN_CONFIGS, train_one


@pytest.fixture
def experimento_con_runs(tmp_path):
    # SQLite, no file://. El FileStore de MLflow NO implementa el Model
    # Registry: con file:// los alias fallan con UnsupportedOperation.
    mlflow.set_tracking_uri(f"sqlite:///{tmp_path}/mlflow.db")
    nombre = "exp-registro"
    mlflow.set_experiment(nombre)

    df = clean(load_raw("data/telco_churn.csv"))
    X_tr, X_te, y_tr, y_te = split_data(df)
    X_tr, X_te, y_tr, y_te = X_tr.head(500), X_te.head(150), y_tr.head(500), y_te.head(150)

    ids = [train_one(c, X_tr, y_tr, X_te, y_te) for c in RUN_CONFIGS[:2]]
    return nombre, ids


def test_best_run_id_elige_el_de_mayor_roc_auc(experimento_con_runs):
    nombre, ids = experimento_con_runs
    mejor = best_run_id(nombre)
    aucs = {i: mlflow.get_run(i).data.metrics["roc_auc"] for i in ids}
    assert mejor == max(aucs, key=aucs.get)


def test_register_run_crea_version_1_y_luego_2(experimento_con_runs):
    _, ids = experimento_con_runs
    v1 = register_run(ids[0], "modelo-de-prueba")
    v2 = register_run(ids[1], "modelo-de-prueba")
    assert v1 == 1
    assert v2 == 2


def test_set_champion_apunta_el_alias_a_la_version(experimento_con_runs):
    _, ids = experimento_con_runs
    version = register_run(ids[0], "modelo-alias")
    set_champion(version, "modelo-alias")

    cliente = MlflowClient()
    mv = cliente.get_model_version_by_alias("modelo-alias", "champion")
    assert int(mv.version) == version


def test_el_alias_se_puede_mover_a_otra_version(experimento_con_runs):
    _, ids = experimento_con_runs
    v1 = register_run(ids[0], "modelo-movil")
    v2 = register_run(ids[1], "modelo-movil")

    set_champion(v1, "modelo-movil")
    set_champion(v2, "modelo-movil")

    cliente = MlflowClient()
    mv = cliente.get_model_version_by_alias("modelo-movil", "champion")
    assert int(mv.version) == v2
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `pytest tests/test_register.py -v`
Esperado: FAIL con `ModuleNotFoundError: No module named 'src.register'`

- [ ] **Step 3: Implementar `src/register.py`**

```python
"""Registro de modelos en el Model Registry y gestión del alias champion.

El alias 'champion' es la referencia que consume el servicio de inferencia.
Promover un modelo a producción es exactamente mover este alias.
"""
import mlflow
import mlflow.sklearn
from mlflow.tracking import MlflowClient
from sklearn.dummy import DummyClassifier
from sklearn.pipeline import Pipeline

from src.features import (
    EXPERIMENT_NAME, MODEL_NAME, RANDOM_STATE, build_preprocessor, clean,
    load_raw, split_data,
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
    """Registra el modelo de un run como una nueva versión."""
    resultado = mlflow.register_model(f"runs:/{run_id}/model", model_name)
    return int(resultado.version)


def set_champion(version: int, model_name: str = MODEL_NAME) -> None:
    """Apunta el alias 'champion' a la versión indicada."""
    MlflowClient().set_registered_model_alias(model_name, ALIAS, str(version))
    print(f"Alias '{ALIAS}' -> {model_name} v{version}")


def register_dummy(model_name: str = MODEL_NAME) -> int:
    """Registra un DummyClassifier para desbloquear el desarrollo de la API.

    Se usa el día 1, antes de que exista el modelo bueno, para que el equipo
    de la API pueda trabajar contra un contrato real en lugar de un None.
    """
    df = clean(load_raw("data/telco_churn.csv"))
    X_train, _, y_train, _ = split_data(df)

    modelo = Pipeline([
        ("preprocessor", build_preprocessor()),
        ("classifier", DummyClassifier(strategy="stratified", random_state=RANDOM_STATE)),
    ]).fit(X_train, y_train)

    mlflow.set_experiment(EXPERIMENT_NAME)
    with mlflow.start_run(run_name="dummy-placeholder"):
        mlflow.log_param("modelo", "dummy")
        mlflow.sklearn.log_model(
            modelo, artifact_path="model", input_example=X_train.head(3)
        )
        run_id = mlflow.active_run().info.run_id

    version = register_run(run_id, model_name)
    set_champion(version, model_name)
    return version


def main() -> None:
    """Registra el mejor run y lo promueve a champion."""
    run_id = best_run_id()
    version = register_run(run_id)
    set_champion(version)
    print(f"Run {run_id} registrado como {MODEL_NAME} v{version}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Ejecutar los tests**

Run: `pytest tests/test_register.py -v`
Esperado: 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/register.py tests/test_register.py
git commit -m "feat: registro de versiones y gestión del alias champion"
```

---

# Tarea 6 — MLflow Server y PostgreSQL en el VPS **[VPS]**

**Files:**
- Create: `infra/docker-compose.yml`, `infra/.env.example`, `docs/runbooks/01-bootstrap-vps.md`

**Interfaces:**
- Produces: MLflow accesible en `http://<IP_NODO>:5000` con backend PostgreSQL y `--serve-artifacts` activo

- [ ] **Step 1: Crear `infra/.env.example`**

```bash
# Copiar a infra/.env y rellenar. El .env real NO se commitea.
DOMAIN_BASE=juanitodev.com
POSTGRES_USER=mlflow
POSTGRES_PASSWORD=cambiame-por-algo-largo
POSTGRES_DB=mlflow
```

- [ ] **Step 2: Crear `infra/docker-compose.yml`**

```yaml
services:
  postgres:
    image: postgres:16
    container_name: mlflow-postgres
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      POSTGRES_DB: ${POSTGRES_DB}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    # Sin 'ports': solo accesible desde la red interna de Docker.
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER}"]
      interval: 10s
      retries: 5

  mlflow:
    image: ghcr.io/mlflow/mlflow:v2.19.0
    container_name: mlflow-server
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    # Se publica en 0.0.0.0 a propósito: los pods de k3s llegan por la
    # interfaz de flannel, NO por loopback. Ver §3.2 del spec.
    # El cierre al exterior se hace con la regla de DOCKER-USER del paso 6.
    ports:
      - "5000:5000"
    volumes:
      - mlflow_artifacts:/mlflow/artifacts
    command: >
      sh -c "pip install --no-cache-dir psycopg2-binary boto3 &&
      mlflow server
      --host 0.0.0.0
      --port 5000
      --backend-store-uri postgresql://${POSTGRES_USER}:${POSTGRES_PASSWORD}@postgres:5432/${POSTGRES_DB}
      --serve-artifacts
      --artifacts-destination /mlflow/artifacts"

volumes:
  postgres_data:
  mlflow_artifacts:
```

- [ ] **Step 3: Escribir el runbook `docs/runbooks/01-bootstrap-vps.md`**

````markdown
# Runbook 01 — Bootstrap del VPS

Responsable: integrante #5. Ejecutar como usuario con sudo.

## 1. Crear los registros DNS (hacer PRIMERO, la propagación tarda)

En el panel del proveedor de dominio, dos registros `A` a la IP del VPS:

| Nombre | Tipo | Valor |
|---|---|---|
| `api` | A | `<IP_PUBLICA_DEL_VPS>` |
| `mlflow` | A | `<IP_PUBLICA_DEL_VPS>` |

Verificar (puede tardar minutos):
```bash
dig +short churn.$DOMAIN_BASE
dig +short mlflow.$DOMAIN_BASE
```

## 2. Verificar Docker

```bash
docker --version
docker compose version
```

## 3. Clonar el repositorio y configurar el entorno

```bash
git clone <URL_DEL_REPO> ~/proyecto-final
cd ~/proyecto-final/infra
cp .env.example .env
nano .env    # poner DOMAIN_BASE real y una contraseña larga
```

## 4. Levantar MLflow y PostgreSQL

```bash
docker compose up -d
docker compose ps
docker compose logs -f mlflow    # Ctrl-C cuando aparezca "Listening at: http://0.0.0.0:5000"
```

## 5. Verificar que MLflow responde

```bash
curl -s http://localhost:5000/health
```
Esperado: `OK`

## 6. Cerrar el puerto 5000 al exterior

`ufw` NO basta: las publicaciones de puertos de Docker se saltan sus reglas.
Hay que usar la cadena `DOCKER-USER`, que sí se evalúa antes.

```bash
sudo iptables -I DOCKER-USER -p tcp --dport 5000 -s 10.42.0.0/16 -j RETURN
sudo iptables -I DOCKER-USER -p tcp --dport 5000 -s 127.0.0.1     -j RETURN
sudo iptables -A DOCKER-USER -p tcp --dport 5000                  -j DROP

sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save
```

## 7. Configurar ufw

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status verbose
```

## 8. EVIDENCIA — verificar desde FUERA del VPS

Desde tu portátil, no desde el servidor:
```bash
nc -zv <IP_PUBLICA> 5000     # DEBE FALLAR
nc -zv <IP_PUBLICA> 22       # debe conectar
```

Pegar ambas salidas en `docs/EVIDENCIAS.md`. Es la diferencia entre creer
que el puerto está cerrado y haberlo comprobado.
````

- [ ] **Step 4: Ejecutar el runbook completo en el VPS**

Seguir `docs/runbooks/01-bootstrap-vps.md` paso a paso y guardar las salidas.

- [ ] **Step 5: Registrar el modelo dummy desde la máquina local**

```bash
export MLFLOW_TRACKING_URI=http://<IP_PUBLICA_VPS>:5000
python -c "from src.register import register_dummy; register_dummy()"
```

Esperado: `Alias 'champion' -> telco-churn v1`

> Nota: este paso se hace **antes** de aplicar la regla DROP del paso 6, o
> desde el propio VPS. Si el puerto ya está cerrado, ejecutarlo por SSH
> dentro del servidor.

- [ ] **Step 6: Commit**

```bash
git add infra/docker-compose.yml infra/.env.example docs/runbooks/01-bootstrap-vps.md
git commit -m "feat: MLflow Server y PostgreSQL en Docker Compose"
```

---

# Tarea 7 — Instalación de k3s **[VPS]**

**Files:**
- Create: `docs/runbooks/02-instalar-k3s.md`

**Interfaces:**
- Produces: clúster k3s de un nodo, sin Traefik, con `kubectl` funcional y conectividad verificada hacia MLflow

- [ ] **Step 1: Escribir el runbook `docs/runbooks/02-instalar-k3s.md`**

````markdown
# Runbook 02 — Instalación de k3s

Responsable: integrante #3.

## 1. Instalar k3s SIN Traefik

Traefik viene incluido en k3s y **ocupa los puertos 80 y 443 del host**. Si
se instala con él, nginx no arrancará y el reto HTTP-01 de certbot fallará
sin un diagnóstico obvio. Como la exposición se hace con NodePort + nginx,
no se pierde nada al desactivarlo.

```bash
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable=traefik" sh -
```

## 2. Configurar kubectl para el usuario actual

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
echo 'export KUBECONFIG=~/.kube/config' >> ~/.bashrc
export KUBECONFIG=~/.kube/config
```

## 3. Verificar el clúster

```bash
kubectl get nodes
kubectl get pods -A
```

Esperado: un nodo en `Ready`. **No debe aparecer ningún pod de Traefik.**

## 4. Verificar que los puertos 80 y 443 están libres

```bash
sudo ss -tlnp | grep -E ':(80|443)\s'
```

Esperado: **sin salida**. Si aparece algo, Traefik sigue vivo:
`kubectl -n kube-system delete helmchart traefik`

## 5. VERIFICACIÓN CRÍTICA — un pod alcanza MLflow

Este es el fallo que bloquearía todo el despliegue. Se comprueba ahora,
antes de que nada dependa de ello.

```bash
NODE_IP=$(kubectl get node -o jsonpath='{.items[0].status.addresses[0].address}')
echo "IP del nodo: $NODE_IP"

kubectl run prueba-mlflow --rm -it --restart=Never --image=curlimages/curl -- \
  curl -s -m 10 http://$NODE_IP:5000/health
```

Esperado: `OK`

Si falla, MLflow está atado a `127.0.0.1` en lugar de `0.0.0.0`. Revisar la
sección `ports` de `infra/docker-compose.yml`.

## 6. Guardar la IP del nodo

```bash
echo "NODE_IP=$NODE_IP" | sudo tee -a /etc/environment
```

Se usará en el `deployment.yaml` como valor de `MLFLOW_TRACKING_URI`.
````

- [ ] **Step 2: Ejecutar el runbook en el VPS**

Guardar la salida del paso 5 — es la evidencia de que el clúster alcanza MLflow.

- [ ] **Step 3: Commit**

```bash
git add docs/runbooks/02-instalar-k3s.md
git commit -m "docs: runbook de instalación de k3s sin Traefik"
```

---

# Tarea 8 — Contratos Pydantic y servicio FastAPI **[LOCAL]**

**Files:**
- Create: `src/api/schemas.py`, `src/api/main.py`, `tests/test_api.py`

**Interfaces:**
- Consumes: `src.features.ALL_FEATURES`, `src.features.MODEL_NAME`
- Produces:
  - `CustomerFeatures` — modelo Pydantic con las 19 variables
  - `PredictionResponse` — `prediction: int`, `probability: float`, `served_by: str`, `model_version: str`
  - `ModelInfo` — `model_name`, `version`, `run_id`, `alias`, `loaded_at`
  - `app: FastAPI`
  - `load_model_with_retry(uri: str, max_attempts: int = 5, base_delay: float = 2.0) -> tuple[Any, ModelInfo]`

- [ ] **Step 1: Escribir `src/api/schemas.py`**

```python
"""Contratos de entrada y salida de la API."""
from typing import Literal

from pydantic import BaseModel, Field


class CustomerFeatures(BaseModel):
    """Las 19 variables de entrada del modelo."""

    # Numéricas
    tenure: int = Field(..., ge=0, le=100, description="Meses de antigüedad")
    MonthlyCharges: float = Field(..., ge=0, description="Cargo mensual")
    TotalCharges: float = Field(..., ge=0, description="Cargo total acumulado")

    # Categóricas
    gender: Literal["Male", "Female"]
    SeniorCitizen: Literal["0", "1"]
    Partner: Literal["Yes", "No"]
    Dependents: Literal["Yes", "No"]
    PhoneService: Literal["Yes", "No"]
    MultipleLines: Literal["Yes", "No", "No phone service"]
    InternetService: Literal["DSL", "Fiber optic", "No"]
    OnlineSecurity: Literal["Yes", "No", "No internet service"]
    OnlineBackup: Literal["Yes", "No", "No internet service"]
    DeviceProtection: Literal["Yes", "No", "No internet service"]
    TechSupport: Literal["Yes", "No", "No internet service"]
    StreamingTV: Literal["Yes", "No", "No internet service"]
    StreamingMovies: Literal["Yes", "No", "No internet service"]
    Contract: Literal["Month-to-month", "One year", "Two year"]
    PaperlessBilling: Literal["Yes", "No"]
    PaymentMethod: Literal[
        "Electronic check",
        "Mailed check",
        "Bank transfer (automatic)",
        "Credit card (automatic)",
    ]

    model_config = {
        "json_schema_extra": {
            "examples": [
                {
                    "tenure": 12, "MonthlyCharges": 70.35, "TotalCharges": 844.20,
                    "gender": "Female", "SeniorCitizen": "0", "Partner": "Yes",
                    "Dependents": "No", "PhoneService": "Yes",
                    "MultipleLines": "No", "InternetService": "Fiber optic",
                    "OnlineSecurity": "No", "OnlineBackup": "Yes",
                    "DeviceProtection": "No", "TechSupport": "No",
                    "StreamingTV": "Yes", "StreamingMovies": "No",
                    "Contract": "Month-to-month", "PaperlessBilling": "Yes",
                    "PaymentMethod": "Electronic check",
                }
            ]
        }
    }


class PredictionResponse(BaseModel):
    prediction: int
    probability: float
    served_by: str
    model_version: str


class ModelInfo(BaseModel):
    model_name: str
    version: str
    run_id: str
    alias: str
    loaded_at: str
```

- [ ] **Step 2: Escribir los tests**

```python
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
```

- [ ] **Step 3: Ejecutar y verificar que falla**

Run: `pytest tests/test_api.py -v`
Esperado: FAIL con `ModuleNotFoundError: No module named 'src.api.main'`

- [ ] **Step 4: Implementar `src/api/main.py`**

```python
"""Servicio de inferencia.

El modelo se carga del Model Registry por alias al arrancar. Esa es la
referencia que exige el enunciado: no hay ninguna ruta de fichero suelta.
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
```

- [ ] **Step 5: Ejecutar los tests**

Run: `pytest tests/test_api.py -v`
Esperado: 10 tests PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/schemas.py src/api/main.py tests/test_api.py
git commit -m "feat: API de inferencia con carga del modelo por alias"
```

---

# Tarea 9 — Imagen Docker **[LOCAL]**

**Files:**
- Create: `Dockerfile`, `.dockerignore`

**Interfaces:**
- Produces: imagen `telco-churn-api:v1`

- [ ] **Step 1: Crear `.dockerignore`**

```
.git/
.venv/
.pytest_cache/
__pycache__/
mlruns/
data/batches/
docs/
tests/
drift/tests/
*.md
```

- [ ] **Step 2: Crear el `Dockerfile`**

```dockerfile
# Etapa de construcción: compila las dependencias
FROM python:3.12-slim AS builder

WORKDIR /build
RUN apt-get update && apt-get install -y --no-install-recommends gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Etapa final: solo lo necesario en tiempo de ejecución
FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/* \
    && useradd --create-home --shell /bin/bash appuser

COPY --from=builder /install /usr/local

WORKDIR /app
COPY --chown=appuser:appuser src/ ./src/

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fs http://localhost:8000/health || exit 1

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
```

- [ ] **Step 3: Construir la imagen**

```bash
docker build -t telco-churn-api:v1 .
docker images telco-churn-api
```

- [ ] **Step 4: Verificar que arranca y responde**

```bash
docker run -d --name prueba-api -p 8000:8000 \
  -e MLFLOW_TRACKING_URI=http://<IP_PUBLICA_VPS>:5000 \
  telco-churn-api:v1

sleep 20
curl -s http://localhost:8000/health
curl -s http://localhost:8000/ready
curl -s http://localhost:8000/model-info
```

Esperado: `/health` devuelve `{"status":"ok",...}`, `/ready` devuelve 200 y
`/model-info` muestra el `run_id` del modelo dummy.

- [ ] **Step 5: Verificar que el usuario no es root**

```bash
docker exec prueba-api whoami
```
Esperado: `appuser`

- [ ] **Step 6: Limpiar**

```bash
docker rm -f prueba-api
```

- [ ] **Step 7: Commit**

```bash
git add Dockerfile .dockerignore
git commit -m "feat: imagen Docker multi-stage con usuario no-root"
```

---

# Tarea 10 — Manifiestos de Kubernetes **[LOCAL]**

**Files:**
- Create: `k8s/deployment.yaml`, `k8s/service.yaml`

**Interfaces:**
- Consumes: imagen `telco-churn-api:v1` (Tarea 9)
- Produces: `Deployment telco-churn-api` con 3 réplicas y `Service` NodePort 30080

- [ ] **Step 1: Crear `k8s/deployment.yaml`**

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: telco-churn-api
  labels:
    app: telco-churn-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: telco-churn-api
  template:
    metadata:
      labels:
        app: telco-churn-api
    spec:
      containers:
        - name: api
          image: telco-churn-api:v1
          # Obligatorio: la imagen se importa localmente a k3s y no existe
          # en ningún registry remoto. Sin esto, k3s intentaría descargarla.
          imagePullPolicy: IfNotPresent
          ports:
            - containerPort: 8000
          env:
            # Downward API: cada pod conoce su propio nombre y lo devuelve
            # en served_by. Es lo que hace demostrable el balanceo de carga.
            - name: POD_NAME
              valueFrom:
                fieldRef:
                  fieldPath: metadata.name
            - name: MLFLOW_TRACKING_URI
              value: "http://NODE_IP_PLACEHOLDER:5000"
            - name: MODEL_ALIAS
              value: "champion"
          resources:
            requests:
              memory: "256Mi"
              cpu: "100m"
            limits:
              memory: "512Mi"
              cpu: "500m"
          livenessProbe:
            httpGet:
              path: /health
              port: 8000
            initialDelaySeconds: 20
            periodSeconds: 15
          readinessProbe:
            httpGet:
              path: /ready
              port: 8000
            initialDelaySeconds: 10
            periodSeconds: 5
            failureThreshold: 12
```

> `NODE_IP_PLACEHOLDER` se sustituye por la IP real en el runbook 03 con
> `sed`. No se deja el valor escrito a mano porque cambia entre entornos.

- [ ] **Step 2: Crear `k8s/service.yaml`**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: telco-churn-api
  labels:
    app: telco-churn-api
spec:
  type: NodePort
  selector:
    app: telco-churn-api
  ports:
    - port: 80
      targetPort: 8000
      nodePort: 30080
      protocol: TCP
```

- [ ] **Step 3: Validar la sintaxis en seco**

```bash
kubectl apply --dry-run=client -f k8s/deployment.yaml -f k8s/service.yaml
```
Esperado: `deployment.apps/telco-churn-api created (dry run)` y lo mismo para el Service.

- [ ] **Step 4: Commit**

```bash
git add k8s/
git commit -m "feat: manifiestos de Kubernetes con 3 réplicas y NodePort"
```

---

# Tarea 11 — Build y despliegue en k3s **[VPS]**

**Files:**
- Create: `docs/runbooks/03-build-y-deploy.md`

**Interfaces:**
- Produces: 3 pods `Running` sirviendo en `http://<IP_NODO>:30080`

- [ ] **Step 1: Escribir `docs/runbooks/03-build-y-deploy.md`**

````markdown
# Runbook 03 — Build y despliegue

Responsable: integrante #3.

## 1. Actualizar el código en el VPS

```bash
cd ~/proyecto-final
git pull
```

## 2. Construir la imagen

```bash
docker build -t telco-churn-api:v1 .
docker images telco-churn-api
```

## 3. Importar la imagen a k3s

k3s usa containerd, no el demonio de Docker: la imagen construida con
`docker build` no es visible para el clúster hasta que se importa.

```bash
docker save telco-churn-api:v1 | sudo k3s ctr images import -
sudo k3s ctr images ls | grep telco-churn
```

## 4. Sustituir la IP del nodo en el manifiesto

```bash
NODE_IP=$(kubectl get node -o jsonpath='{.items[0].status.addresses[0].address}')
sed "s/NODE_IP_PLACEHOLDER/$NODE_IP/" k8s/deployment.yaml > /tmp/deployment.yaml
grep MLFLOW_TRACKING_URI -A1 /tmp/deployment.yaml
```

## 5. Desplegar

```bash
kubectl apply -f /tmp/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl rollout status deployment/telco-churn-api --timeout=180s
```

## 6. Verificar

```bash
kubectl get pods -o wide
curl -s http://localhost:30080/health
curl -s http://localhost:30080/model-info
```

Esperado: 3 pods `Running` con `READY 1/1`.

## Diagnóstico si algo falla

| Síntoma | Causa probable | Comando |
|---|---|---|
| `ImagePullBackOff` | No se importó la imagen o falta `imagePullPolicy: IfNotPresent` | `sudo k3s ctr images ls \| grep telco` |
| Pods `Running` pero `0/1` | El readinessProbe falla: el modelo no carga | `kubectl logs <pod>` |
| Logs con "Intento N/5 falló" | El pod no alcanza MLflow | Repetir el paso 5 del runbook 02 |
| `CrashLoopBackOff` | Error de arranque de la aplicación | `kubectl logs <pod> --previous` |
````

- [ ] **Step 2: Ejecutar el runbook en el VPS**

- [ ] **Step 3: Capturar la evidencia**

```bash
kubectl get pods -o wide | tee -a ~/evidencia-deploy.txt
curl -s http://localhost:30080/model-info | tee -a ~/evidencia-deploy.txt
```

- [ ] **Step 4: Commit**

```bash
git add docs/runbooks/03-build-y-deploy.md
git commit -m "docs: runbook de build y despliegue en k3s"
```

---

# Tarea 12 — TLS y subdominios **[VPS]**

**Files:**
- Create: `infra/nginx/churn.conf.template`, `infra/nginx/mlflow.conf.template`, `docs/runbooks/04-tls-y-subdominios.md`

**Interfaces:**
- Produces: `https://churn.juanitodev.com` y `https://mlflow.juanitodev.com` con certificado válido

- [ ] **Step 1: Crear `infra/nginx/churn.conf.template`**

```nginx
server {
    listen 80;
    server_name churn.DOMAIN_BASE;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name churn.DOMAIN_BASE;

    # certbot añade aquí ssl_certificate y ssl_certificate_key

    location / {
        proxy_pass http://127.0.0.1:30080;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

- [ ] **Step 2: Crear `infra/nginx/mlflow.conf.template`**

```nginx
server {
    listen 80;
    server_name mlflow.DOMAIN_BASE;
    return 301 https://$host$request_uri;
}

server {
    listen 443 ssl;
    server_name mlflow.DOMAIN_BASE;

    # MLflow sube artefactos de modelo: sin esto, falla con 413
    client_max_body_size 500M;

    location / {
        auth_basic           "MLflow — acceso restringido";
        auth_basic_user_file /etc/nginx/.htpasswd;

        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host              $host;
        proxy_set_header X-Real-IP         $remote_addr;
        proxy_set_header X-Forwarded-For   $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # La UI de MLflow usa websockets para actualizaciones en vivo
        proxy_http_version 1.1;
        proxy_set_header Upgrade    $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

- [ ] **Step 3: Escribir `docs/runbooks/04-tls-y-subdominios.md`**

````markdown
# Runbook 04 — TLS y subdominios

Responsable: integrante #5. Requiere los runbooks 01, 02 y 03 completados.

## 1. Comprobar que el DNS ha propagado

```bash
source ~/proyecto-final/infra/.env
dig +short churn.$DOMAIN_BASE
dig +short mlflow.$DOMAIN_BASE
```

Ambos deben devolver la IP pública del VPS. **Si no, no continuar**: certbot
fallará el reto HTTP-01.

## 2. Instalar nginx y certbot

```bash
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx apache2-utils
```

## 3. Verificar que nginx tomó los puertos 80 y 443

```bash
sudo systemctl status nginx --no-pager
sudo ss -tlnp | grep -E ':(80|443)\s'
```

Si nginx no arranca por "address already in use", Traefik de k3s sigue vivo.
Volver al paso 4 del runbook 02.

## 4. Crear las credenciales de acceso a MLflow

```bash
sudo htpasswd -c /etc/nginx/.htpasswd docente
# Introducir una contraseña y ANOTARLA: se comparte durante la defensa
```

## 5. Instalar los vhosts sustituyendo el dominio

```bash
cd ~/proyecto-final
for sitio in churn mlflow; do
  sed "s/DOMAIN_BASE/$DOMAIN_BASE/g" infra/nginx/$sitio.conf.template \
    | sudo tee /etc/nginx/sites-available/$sitio.conf > /dev/null
  sudo ln -sf /etc/nginx/sites-available/$sitio.conf /etc/nginx/sites-enabled/$sitio.conf
done

sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
```

> `nginx -t` fallará aquí porque los bloques `listen 443 ssl` todavía no
> tienen certificado. Es esperado: certbot los añade en el paso siguiente.
> Si el error es de sintaxis (no de certificado), corregirlo antes de seguir.

## 6. Emitir los certificados

```bash
sudo certbot --nginx -d churn.$DOMAIN_BASE -d mlflow.$DOMAIN_BASE \
  --non-interactive --agree-tos -m <TU_CORREO> --redirect

sudo nginx -t && sudo systemctl reload nginx
```

## 7. Verificar la renovación automática

```bash
sudo certbot renew --dry-run
sudo systemctl list-timers | grep certbot
```

## 8. EVIDENCIA — verificación completa

```bash
curl -sI  https://churn.$DOMAIN_BASE/health
curl -s   https://churn.$DOMAIN_BASE/health
curl -sI  http://churn.$DOMAIN_BASE/health | head -1     # debe ser 301
curl -sI  https://mlflow.$DOMAIN_BASE/                 # debe ser 401 sin credenciales
curl -sI -u docente:<PASS> https://mlflow.$DOMAIN_BASE/   # debe ser 200
```

Desde FUERA del VPS:
```bash
nc -zv <IP_PUBLICA> 5000     # DEBE FALLAR
nc -zv <IP_PUBLICA> 30080    # DEBE FALLAR
nc -zv <IP_PUBLICA> 443      # debe conectar
```

Pegar todas las salidas en `docs/EVIDENCIAS.md`.
````

- [ ] **Step 4: Ejecutar el runbook en el VPS**

- [ ] **Step 5: Commit**

```bash
git add infra/nginx/ docs/runbooks/04-tls-y-subdominios.md
git commit -m "feat: TLS con nginx y certbot para los dos subdominios"
```

---

# Tarea 13 — Las 4 demostraciones de Kubernetes **[VPS]**

**Files:**
- Create: `docs/runbooks/05-demos-kubernetes.md`, `scripts/demo_balanceo.sh`

**Interfaces:**
- Produces: evidencia capturada de las 4 demostraciones exigidas por §5.2 del enunciado

- [ ] **Step 1: Crear `scripts/demo_balanceo.sh`**

```bash
#!/usr/bin/env bash
# Demuestra el balanceo de carga mostrando qué pod atiende cada petición.
set -euo pipefail

URL="${1:-http://localhost:30080}"
N="${2:-10}"

CLIENTE='{"tenure":12,"MonthlyCharges":70.35,"TotalCharges":844.20,
"gender":"Female","SeniorCitizen":"0","Partner":"Yes","Dependents":"No",
"PhoneService":"Yes","MultipleLines":"No","InternetService":"Fiber optic",
"OnlineSecurity":"No","OnlineBackup":"Yes","DeviceProtection":"No",
"TechSupport":"No","StreamingTV":"Yes","StreamingMovies":"No",
"Contract":"Month-to-month","PaperlessBilling":"Yes",
"PaymentMethod":"Electronic check"}'

echo "Enviando $N peticiones a $URL/predict"
for i in $(seq 1 "$N"); do
  curl -s -X POST "$URL/predict" \
    -H 'Content-Type: application/json' \
    -d "$CLIENTE" \
  | python3 -c 'import sys,json; d=json.load(sys.stdin); print(f"{d[\"served_by\"]}  p={d[\"probability\"]}")'
done

echo
echo "Reparto por pod:"
for i in $(seq 1 "$N"); do
  curl -s -X POST "$URL/predict" -H 'Content-Type: application/json' -d "$CLIENTE" \
  | python3 -c 'import sys,json; print(json.load(sys.stdin)["served_by"])'
done | sort | uniq -c
```

```bash
chmod +x scripts/demo_balanceo.sh
```

- [ ] **Step 2: Escribir `docs/runbooks/05-demos-kubernetes.md`**

````markdown
# Runbook 05 — Las 4 demostraciones exigidas

Responsable: integrante #3. Estas cuatro pruebas pueden pedirse en vivo
durante la defensa. Ensayarlas antes.

## Demostración 1 — Tres réplicas en Running simultáneo

```bash
kubectl get pods -o wide
kubectl get deployment telco-churn-api
```

Evidencia: captura mostrando 3 pods `Running` con `READY 1/1`.

## Demostración 2 — El tráfico se distribuye entre réplicas

```bash
./scripts/demo_balanceo.sh http://localhost:30080 10
```

Evidencia: la salida debe mostrar **al menos dos nombres de pod distintos**
en el campo `served_by`, y el recuento final el reparto entre ellos.

> Cómo funciona: cada pod recibe su nombre por la Downward API en la
> variable `POD_NAME` y lo devuelve en cada respuesta.

## Demostración 3 — Autorreparación

Usar **dos terminales lado a lado**. Es lo que hace la demostración
visualmente contundente: se ve que el servicio nunca deja de responder.

Terminal A (tráfico continuo):
```bash
while true; do
  curl -s -o /dev/null -w "%{http_code} " http://localhost:30080/health
  sleep 0.3
done
```

Terminal B (matar un pod):
```bash
kubectl get pods
kubectl delete pod <NOMBRE_DE_UN_POD>
kubectl get pods -w      # Ctrl-C cuando el nuevo esté Running
```

Evidencia: en el terminal A solo aparecen códigos `200`; en el B se ve el
pod terminando y uno nuevo creándose con nombre distinto.

## Demostración 4 — Escalado

```bash
kubectl scale deployment telco-churn-api --replicas=5
kubectl get pods -w        # esperar a 5 Running
./scripts/demo_balanceo.sh http://localhost:30080 15

kubectl scale deployment telco-churn-api --replicas=2
kubectl get pods
./scripts/demo_balanceo.sh http://localhost:30080 10

kubectl scale deployment telco-churn-api --replicas=3   # volver al estado base
```

Evidencia: capturas de `get pods` con 5, 2 y 3 réplicas, y cómo cambia el
reparto de `served_by`.
````

- [ ] **Step 3: Ejecutar las 4 demostraciones y guardar la evidencia**

```bash
{
  echo "=== DEMO 1: réplicas ==="       ; kubectl get pods -o wide
  echo "=== DEMO 2: balanceo ==="       ; ./scripts/demo_balanceo.sh
  echo "=== DEMO 4: escalado a 5 ==="   ; kubectl scale deployment telco-churn-api --replicas=5
  sleep 30                              ; kubectl get pods
  echo "=== DEMO 4: vuelta a 3 ==="     ; kubectl scale deployment telco-churn-api --replicas=3
} 2>&1 | tee ~/evidencia-k8s.txt
```

La demostración 3 se captura aparte, con las dos terminales.

- [ ] **Step 4: Commit**

```bash
git add scripts/demo_balanceo.sh docs/runbooks/05-demos-kubernetes.md
git commit -m "feat: scripts y runbook de las 4 demostraciones de Kubernetes"
```

---

# Tarea 14 — Detectores estadísticos de drift **[LOCAL]**

**Files:**
- Create: `drift/detectors.py`, `drift/tests/test_detectors.py`

**Interfaces:**
- Consumes: `src.features.NUMERIC_FEATURES`, `src.features.CATEGORICAL_FEATURES`
- Produces:
  - `DriftResult` — dataclass con `variable: str`, `test: str`, `statistic: float`, `p_value: float | None`, `threshold: float`, `drifted: bool`
  - `psi(baseline: pd.Series, current: pd.Series, bins: int = 10) -> float`
  - `cramers_v(contingency: np.ndarray) -> float`
  - `ks_detector(baseline, current, name, alpha=0.05, min_effect=0.10) -> DriftResult`
  - `psi_detector(baseline, current, name, threshold=0.25) -> DriftResult`
  - `chi2_detector(baseline, current, name, alpha=0.05) -> DriftResult`
  - `detect_data_drift(baseline_df, current_df) -> list[DriftResult]`
  - Constantes: `ALPHA = 0.05`, `KS_MIN_EFFECT = 0.10`, `CRAMERS_V_MIN = 0.10`, `PSI_ALERT = 0.25`, `PSI_WARN = 0.10`

- [ ] **Step 1: Escribir los tests**

```python
# drift/tests/test_detectors.py
import numpy as np
import pandas as pd
import pytest

from drift.detectors import (
    KS_MIN_EFFECT, PSI_ALERT, DriftResult, chi2_detector, cramers_v,
    detect_data_drift, ks_detector, psi, psi_detector,
)

RNG = np.random.default_rng(42)


# --- Tests unitarios de las fórmulas -----------------------------------
# Demuestran que entendemos la matemática, no solo que llamamos a scipy.

def test_psi_valor_calculado_a_mano_cambio_pequeno():
    """PSI de [50%,50%] a [60%,40%].

    PSI = (0.6-0.5)*ln(0.6/0.5) + (0.4-0.5)*ln(0.4/0.5) = 0.0405465
    Por debajo de 0.10: población estable.
    """
    base = pd.Series(["A"] * 50 + ["B"] * 50)
    actual = pd.Series(["A"] * 60 + ["B"] * 40)
    assert psi(base, actual) == pytest.approx(0.0405465, abs=1e-6)


def test_psi_valor_calculado_a_mano_cambio_grande():
    """PSI de [50%,50%] a [90%,10%].

    PSI = 0.4*ln(1.8) + (-0.4)*ln(0.2) = 0.8788898
    Muy por encima de 0.25: cambio significativo.

    Tolerancia 1e-4 y no 1e-6: el epsilon anti división-por-cero de la
    implementación perturba el valor exacto en ~3.5e-6.
    """
    base = pd.Series(["A"] * 50 + ["B"] * 50)
    actual = pd.Series(["A"] * 90 + ["B"] * 10)
    assert psi(base, actual) == pytest.approx(0.8788898, abs=1e-4)


def test_psi_de_una_serie_contra_si_misma_es_cero():
    serie = pd.Series(["A"] * 30 + ["B"] * 50 + ["C"] * 20)
    assert psi(serie, serie) == pytest.approx(0.0, abs=1e-9)


def test_psi_no_revienta_si_falta_una_categoria():
    """El epsilon evita la división por cero cuando una categoría desaparece."""
    base = pd.Series(["A"] * 50 + ["B"] * 50)
    actual = pd.Series(["A"] * 100)
    valor = psi(base, actual)
    assert np.isfinite(valor)
    assert valor > PSI_ALERT


def test_cramers_v_sin_asociacion_es_cercano_a_cero():
    tabla = np.array([[50, 50], [50, 50]])
    assert cramers_v(tabla) == pytest.approx(0.0, abs=1e-9)


def test_cramers_v_asociacion_perfecta_es_uno():
    tabla = np.array([[100, 0], [0, 100]])
    assert cramers_v(tabla) == pytest.approx(1.0, abs=1e-6)


# --- Detector KS -------------------------------------------------------

def test_ks_no_alerta_con_la_misma_distribucion():
    base = pd.Series(RNG.normal(50, 10, 2000))
    actual = pd.Series(RNG.normal(50, 10, 2000))
    r = ks_detector(base, actual, "x")
    assert isinstance(r, DriftResult)
    assert r.test == "ks"
    assert not r.drifted


def test_ks_alerta_con_desplazamiento_grande():
    base = pd.Series(RNG.normal(50, 10, 2000))
    actual = pd.Series(RNG.normal(70, 10, 2000))
    assert ks_detector(base, actual, "x").drifted


def test_ks_no_alerta_por_diferencia_trivial_aunque_sea_significativa():
    """El criterio del tamaño del efecto es la clave del diseño.

    Con n grande, KS rechaza H0 ante diferencias sin relevancia práctica.
    Exigir D > 0.10 filtra ese ruido y evita un monitor que grita a diario.
    """
    base = pd.Series(RNG.normal(50, 10, 50000))
    actual = pd.Series(RNG.normal(50.15, 10, 50000))
    r = ks_detector(base, actual, "x")
    assert r.statistic < KS_MIN_EFFECT
    assert not r.drifted


# --- Detectores categóricos -------------------------------------------

def test_psi_detector_no_alerta_con_mezcla_similar():
    base = pd.Series(["A"] * 500 + ["B"] * 300 + ["C"] * 200)
    actual = pd.Series(["A"] * 490 + ["B"] * 310 + ["C"] * 200)
    assert not psi_detector(base, actual, "cat").drifted


def test_psi_detector_alerta_con_mezcla_invertida():
    base = pd.Series(["A"] * 800 + ["B"] * 200)
    actual = pd.Series(["A"] * 200 + ["B"] * 800)
    r = psi_detector(base, actual, "cat")
    assert r.drifted
    assert r.statistic > PSI_ALERT


def test_chi2_alerta_con_cambio_de_proporciones():
    base = pd.Series(["A"] * 800 + ["B"] * 200)
    actual = pd.Series(["A"] * 300 + ["B"] * 700)
    r = chi2_detector(base, actual, "cat")
    assert r.test == "chi2"
    assert r.drifted


# --- Orquestador -------------------------------------------------------

def test_detect_data_drift_cubre_las_19_variables():
    from src.features import clean, load_raw, split_data
    X_tr, X_te, _, _ = split_data(clean(load_raw("data/telco_churn.csv")))
    resultados = detect_data_drift(X_tr, X_te.head(500))

    # 3 numéricas con KS + 16 categóricas con PSI y Chi2
    assert len([r for r in resultados if r.test == "ks"]) == 3
    assert len([r for r in resultados if r.test == "psi"]) == 16
    assert len([r for r in resultados if r.test == "chi2"]) == 16


def test_detect_data_drift_no_alerta_entre_train_y_test():
    """Train y test salen del mismo origen: no debe haber deriva."""
    from src.features import clean, load_raw, split_data
    X_tr, X_te, _, _ = split_data(clean(load_raw("data/telco_churn.csv")))
    resultados = detect_data_drift(X_tr, X_te)
    assert not any(r.drifted for r in resultados)
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `pytest drift/tests/test_detectors.py -v`
Esperado: FAIL con `ModuleNotFoundError: No module named 'drift.detectors'`

- [ ] **Step 3: Implementar `drift/detectors.py`**

```python
"""Detectores estadísticos de data drift.

Implementación propia y no una librería de terceros, porque el enunciado
exige justificar por qué se eligió cada prueba y de dónde sale cada umbral.
Una librería opaca no se puede defender.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from src.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES

# --- Umbrales y su justificación --------------------------------------
# ALPHA: nivel de significancia convencional.
ALPHA = 0.05

# KS_MIN_EFFECT: con n grande, KS rechaza H0 ante diferencias irrelevantes
# en la práctica. Exigir además un tamaño del efecto mínimo separa
# "estadísticamente significativo" de "prácticamente relevante".
KS_MIN_EFFECT = 0.10

# CRAMERS_V_MIN: misma lógica que KS_MIN_EFFECT pero para Chi². Es un
# umbral propio porque V y D son estadísticos distintos, y la tabla de la
# puerta debe mostrar cada estadístico contra su umbral real.
CRAMERS_V_MIN = 0.10

# PSI: escala convencional de las scorecards crediticias, donde nació el
# índice. <0.10 estable, 0.10-0.25 moderado, >0.25 cambio significativo.
PSI_WARN = 0.10
PSI_ALERT = 0.25

EPSILON = 1e-6


@dataclass
class DriftResult:
    """Resultado de una prueba sobre una variable."""

    variable: str
    test: str
    statistic: float
    p_value: float | None
    threshold: float
    drifted: bool

    def __str__(self) -> str:
        estado = "DERIVA" if self.drifted else "ok"
        p = f"p={self.p_value:.4f}" if self.p_value is not None else "p=n/a"
        return (
            f"{self.variable:<20} {self.test:<5} "
            f"stat={self.statistic:>8.4f} {p:<12} "
            f"umbral={self.threshold:<6} {estado}"
        )


def psi(baseline: pd.Series, current: pd.Series, bins: int = 10) -> float:
    """Índice de estabilidad poblacional.

    PSI = Σ (pct_actual − pct_esperado) × ln(pct_actual / pct_esperado)

    Para variables numéricas los bins se derivan de los cuantiles del
    baseline. Se suma un epsilon a las proporciones para evitar la división
    por cero cuando una categoría no aparece en el lote actual.
    """
    if pd.api.types.is_numeric_dtype(baseline):
        cortes = np.unique(np.quantile(baseline, np.linspace(0, 1, bins + 1)))
        cortes[0], cortes[-1] = -np.inf, np.inf
        base_binned = pd.cut(baseline, bins=cortes)
        curr_binned = pd.cut(current, bins=cortes)
        categorias = base_binned.cat.categories
        base_pct = base_binned.value_counts(normalize=True).reindex(categorias, fill_value=0)
        curr_pct = curr_binned.value_counts(normalize=True).reindex(categorias, fill_value=0)
    else:
        categorias = sorted(set(baseline.unique()) | set(current.unique()))
        base_pct = baseline.value_counts(normalize=True).reindex(categorias, fill_value=0)
        curr_pct = current.value_counts(normalize=True).reindex(categorias, fill_value=0)

    b = base_pct.to_numpy() + EPSILON
    c = curr_pct.to_numpy() + EPSILON
    return float(np.sum((c - b) * np.log(c / b)))


def cramers_v(contingency: np.ndarray) -> float:
    """Tamaño del efecto para tablas de contingencia. Rango [0, 1]."""
    chi2 = stats.chi2_contingency(contingency, correction=False)[0]
    n = contingency.sum()
    min_dim = min(contingency.shape) - 1
    if n == 0 or min_dim == 0:
        return 0.0
    return float(np.sqrt(chi2 / (n * min_dim)))


def ks_detector(
    baseline: pd.Series,
    current: pd.Series,
    name: str,
    alpha: float = ALPHA,
    min_effect: float = KS_MIN_EFFECT,
) -> DriftResult:
    """Kolmogorov-Smirnov para variables numéricas.

    Se eligió KS porque es no paramétrico y no asume normalidad:
    MonthlyCharges es claramente bimodal (clientes con y sin internet), así
    que un t-test sería inválido. KS compara las distribuciones acumuladas
    completas, no solo la media.

    Alerta solo si hay significancia estadística Y tamaño del efecto.
    """
    estadistico, p_valor = stats.ks_2samp(baseline, current)
    return DriftResult(
        variable=name,
        test="ks",
        statistic=float(estadistico),
        p_value=float(p_valor),
        threshold=min_effect,
        drifted=bool(p_valor < alpha and estadistico > min_effect),
    )


def psi_detector(
    baseline: pd.Series, current: pd.Series, name: str, threshold: float = PSI_ALERT
) -> DriftResult:
    """PSI para variables categóricas. Da magnitud interpretable, no un sí/no."""
    valor = psi(baseline, current)
    return DriftResult(
        variable=name,
        test="psi",
        statistic=valor,
        p_value=None,
        threshold=threshold,
        drifted=bool(valor > threshold),
    )


def chi2_detector(
    baseline: pd.Series, current: pd.Series, name: str, alpha: float = ALPHA
) -> DriftResult:
    """Chi-cuadrado de independencia, con Cramér's V como tamaño del efecto."""
    categorias = sorted(set(baseline.unique()) | set(current.unique()))
    tabla = np.array([
        baseline.value_counts().reindex(categorias, fill_value=0).to_numpy(),
        current.value_counts().reindex(categorias, fill_value=0).to_numpy(),
    ])

    columnas_no_vacias = tabla.sum(axis=0) > 0
    tabla = tabla[:, columnas_no_vacias]

    if tabla.shape[1] < 2:
        return DriftResult(name, "chi2", 0.0, 1.0, CRAMERS_V_MIN, False)

    _, p_valor = stats.chi2_contingency(tabla, correction=False)[:2]
    v = cramers_v(tabla)
    # threshold es CRAMERS_V_MIN y no alpha: statistic es la V de Cramér,
    # así que la tabla de la puerta compara cada cosa con su propio umbral.
    return DriftResult(
        variable=name,
        test="chi2",
        statistic=v,
        p_value=float(p_valor),
        threshold=CRAMERS_V_MIN,
        drifted=bool(p_valor < alpha and v > CRAMERS_V_MIN),
    )


def detect_data_drift(
    baseline_df: pd.DataFrame, current_df: pd.DataFrame
) -> list[DriftResult]:
    """Aplica una prueba por tipo de variable sobre las 19 features."""
    resultados: list[DriftResult] = []

    for columna in NUMERIC_FEATURES:
        resultados.append(ks_detector(baseline_df[columna], current_df[columna], columna))

    for columna in CATEGORICAL_FEATURES:
        resultados.append(psi_detector(baseline_df[columna], current_df[columna], columna))
        resultados.append(chi2_detector(baseline_df[columna], current_df[columna], columna))

    return resultados
```

- [ ] **Step 4: Ejecutar los tests**

Run: `pytest drift/tests/test_detectors.py -v`
Esperado: 14 tests PASS

> **Si `test_detect_data_drift_no_alerta_entre_train_y_test` falla:** son 35
> pruebas simultáneas (3 KS + 16 PSI + 16 Chi²) y con α = 0.05 cabe algún
> falso positivo por comparaciones múltiples. Los criterios de tamaño del
> efecto (`D > 0.10`, `V > 0.10`) deberían suprimirlos. Si aun así alerta una
> variable, **no relajar el umbral**: inspeccionar cuál es con
> `[r for r in resultados if r.drifted]` y comprobar si es un efecto real del
> split. Esta discusión —comparaciones múltiples en monitoreo de drift— es
> munición excelente para la defensa; documentarla en `ARQUITECTURA.md`.

- [ ] **Step 5: Commit**

```bash
git add drift/detectors.py drift/tests/test_detectors.py
git commit -m "feat: detectores KS, PSI y Chi2 con umbrales justificados"
```

---

# Tarea 15 — Generadores de lotes y de deriva **[LOCAL]**

**Files:**
- Create: `drift/generators.py`, `drift/tests/test_generators.py`

**Interfaces:**
- Consumes: `src.features`, `drift.detectors`
- Produces:
  - `make_clean_batch(df, n=500, random_state=42) -> pd.DataFrame`
  - `inject_numeric_shift(df, column="MonthlyCharges", pct=0.25) -> pd.DataFrame`
  - `inject_categorical_shift(df, column="Contract", target="Month-to-month", pct=0.5, random_state=42) -> pd.DataFrame`
  - `inject_concept_drift(df, mask_column="Contract", mask_value="Two year", flip_pct=0.3, random_state=42) -> pd.DataFrame`
  - `generate_all_batches(df, out_dir="data/batches", n=500) -> list[Path]` — genera `lote_0.csv` … `lote_5.csv`

- [ ] **Step 1: Escribir los tests**

```python
# drift/tests/test_generators.py
import pandas as pd
import pytest

from drift.detectors import detect_data_drift
from drift.generators import (
    generate_all_batches, inject_categorical_shift, inject_concept_drift,
    inject_numeric_shift, make_clean_batch,
)
from src.features import TARGET, clean, load_raw, split_data


@pytest.fixture(scope="module")
def datos():
    df = clean(load_raw("data/telco_churn.csv"))
    X_tr, X_te, y_tr, y_te = split_data(df)
    baseline = X_tr
    reserva = X_te.copy()
    reserva[TARGET] = y_te
    return baseline, reserva


def test_lote_limpio_tiene_el_tamano_pedido(datos):
    _, reserva = datos
    assert len(make_clean_batch(reserva, n=300)) == 300


def test_lote_limpio_es_reproducible(datos):
    _, reserva = datos
    a = make_clean_batch(reserva, n=200, random_state=42)
    b = make_clean_batch(reserva, n=200, random_state=42)
    pd.testing.assert_frame_equal(a, b)


def test_lote_limpio_no_dispara_deriva(datos):
    """VERDE: datos del mismo origen que el entrenamiento."""
    baseline, reserva = datos
    lote = make_clean_batch(reserva, n=500)
    assert not any(r.drifted for r in detect_data_drift(baseline, lote))


def test_desplazamiento_numerico_sube_la_media(datos):
    _, reserva = datos
    lote = make_clean_batch(reserva, n=500)
    derivado = inject_numeric_shift(lote, "MonthlyCharges", pct=0.25)
    assert derivado["MonthlyCharges"].mean() > lote["MonthlyCharges"].mean() * 1.2


def test_desplazamiento_numerico_dispara_ks(datos):
    """ROJO: la variable desplazada debe detectarse."""
    baseline, reserva = datos
    derivado = inject_numeric_shift(make_clean_batch(reserva, n=500), "MonthlyCharges", 0.25)
    resultados = detect_data_drift(baseline, derivado)
    ks_charges = [r for r in resultados if r.variable == "MonthlyCharges" and r.test == "ks"]
    assert ks_charges[0].drifted


def test_cambio_categorico_dispara_psi(datos):
    """ROJO: el cambio de mezcla en Contract debe detectarse."""
    baseline, reserva = datos
    derivado = inject_categorical_shift(make_clean_batch(reserva, n=500), "Contract", pct=0.6)
    resultados = detect_data_drift(baseline, derivado)
    psi_contract = [r for r in resultados if r.variable == "Contract" and r.test == "psi"]
    assert psi_contract[0].drifted


def test_concept_drift_invierte_etiquetas_del_subconjunto(datos):
    _, reserva = datos
    lote = make_clean_batch(reserva, n=500)
    derivado = inject_concept_drift(lote, flip_pct=0.5)
    cambiadas = (lote[TARGET].to_numpy() != derivado[TARGET].to_numpy()).sum()
    assert cambiadas > 0


def test_concept_drift_no_toca_las_variables_de_entrada(datos):
    """Es lo que distingue el concept drift del data drift."""
    _, reserva = datos
    lote = make_clean_batch(reserva, n=500)
    derivado = inject_concept_drift(lote, flip_pct=0.5)
    entradas = [c for c in lote.columns if c != TARGET]
    pd.testing.assert_frame_equal(lote[entradas], derivado[entradas])


def test_generate_all_batches_crea_6_ficheros(datos, tmp_path):
    _, reserva = datos
    rutas = generate_all_batches(reserva, out_dir=tmp_path, n=300)
    assert len(rutas) == 6
    assert all(p.exists() for p in rutas)
    assert rutas[0].name == "lote_0.csv"


def test_todos_los_lotes_derivados_llevan_concept_drift(datos, tmp_path):
    """Regresión doble sobre la construcción de los lotes.

    1. El shift categórico elimina el subgrupo 'Two year', así que el
       concept drift debe inyectarse ANTES o no invertiría ninguna etiqueta.
    2. Los lotes 1 a 5 llevan inversión creciente y SOSTENIDA (spec §9.4).
       Si un lote intermedio se saltara la inversión, rompería la racha de
       3 lotes consecutivos y la alarma de reentrenamiento nunca se
       dispararía en la corrida real del monitor.
    """
    _, reserva = datos
    rutas = generate_all_batches(reserva, out_dir=tmp_path, n=300)
    lote_0 = pd.read_csv(rutas[0])
    invertidas = []
    for indice in range(1, 6):
        lote = pd.read_csv(rutas[indice])
        cambiadas = (lote_0[TARGET].to_numpy() != lote[TARGET].to_numpy()).sum()
        assert cambiadas > 0, f"lote_{indice} no tiene etiquetas invertidas"
        invertidas.append(cambiadas)

    # La proporción invertida crece de lote en lote: 10/20/30/40/50 %
    assert invertidas == sorted(invertidas), f"la inversión no es creciente: {invertidas}"
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `pytest drift/tests/test_generators.py -v`
Esperado: FAIL con `ModuleNotFoundError: No module named 'drift.generators'`

- [ ] **Step 3: Implementar `drift/generators.py`**

```python
"""Construcción de lotes limpios y con deriva inyectada de forma controlada.

El lote 0 es el control: sale del mismo origen que el entrenamiento y debe
pasar en verde. Los lotes 1 a 5 llevan deriva creciente.
"""
from pathlib import Path

import pandas as pd

from src.features import RANDOM_STATE, TARGET


def make_clean_batch(
    df: pd.DataFrame, n: int = 500, random_state: int = RANDOM_STATE
) -> pd.DataFrame:
    """Muestra sin deriva, del mismo origen que el entrenamiento."""
    return df.sample(n=min(n, len(df)), random_state=random_state).reset_index(drop=True)


def inject_numeric_shift(
    df: pd.DataFrame, column: str = "MonthlyCharges", pct: float = 0.25
) -> pd.DataFrame:
    """Sube una variable numérica un porcentaje fijo.

    Historia de negocio: una subida general de tarifas.
    """
    derivado = df.copy()
    derivado[column] = derivado[column] * (1 + pct)
    return derivado


def inject_categorical_shift(
    df: pd.DataFrame,
    column: str = "Contract",
    target: str = "Month-to-month",
    pct: float = 0.5,
    random_state: int = RANDOM_STATE,
) -> pd.DataFrame:
    """Reasigna una fracción de las filas a una categoría concreta.

    Historia de negocio: una campaña comercial empuja a los clientes hacia
    contratos mensuales.
    """
    derivado = df.copy()
    candidatas = derivado.index[derivado[column] != target]
    n_cambiar = int(len(derivado) * pct)
    if n_cambiar > 0 and len(candidatas) > 0:
        elegidas = (
            pd.Series(candidatas)
            .sample(n=min(n_cambiar, len(candidatas)), random_state=random_state)
            .to_numpy()
        )
        derivado.loc[elegidas, column] = target
    return derivado


def inject_concept_drift(
    df: pd.DataFrame,
    mask_column: str = "Contract",
    mask_value: str = "Two year",
    flip_pct: float = 0.3,
    random_state: int = RANDOM_STATE,
) -> pd.DataFrame:
    """Invierte la etiqueta de una fracción de un subgrupo.

    Historia de negocio: un cambio de política de permanencia hace que los
    contratos largos dejen de proteger contra el abandono.

    Las variables de entrada NO se tocan: esa es exactamente la diferencia
    entre concept drift y data drift.
    """
    derivado = df.copy()
    subgrupo = derivado.index[derivado[mask_column] == mask_value]
    n_invertir = int(len(subgrupo) * flip_pct)
    if n_invertir > 0:
        elegidas = (
            pd.Series(subgrupo).sample(n=n_invertir, random_state=random_state).to_numpy()
        )
        derivado.loc[elegidas, TARGET] = 1 - derivado.loc[elegidas, TARGET]
    return derivado


def generate_all_batches(
    df: pd.DataFrame, out_dir: str | Path = "data/batches", n: int = 500
) -> list[Path]:
    """Genera los 6 lotes con deriva creciente y los guarda como CSV.

    | Lote | Contenido                                          |
    |------|----------------------------------------------------|
    | 0    | Limpio. Control: debe salir verde.                  |
    | 1    | Concept drift leve (10% de etiquetas invertidas).   |
    | 2    | Concept drift medio (20%).                          |
    | 3    | Concept drift (30%) + data drift: tarifas y mezcla. |
    | 4    | Data drift más fuerte + concept drift (40%).        |
    | 5    | Deriva severa en ambos ejes (50%).                  |

    El concept drift crece 10/20/30/40/50 % de forma SOSTENIDA en los lotes
    1 a 5 (spec §9.4). Que ningún lote intermedio se salte la inversión es
    lo que permite que la racha de 3 lotes consecutivos por debajo del
    umbral llegue a completarse y dispare la alarma de reentrenamiento.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    base = make_clean_batch(df, n=n)
    rutas: list[Path] = []

    # En los lotes 3, 4 y 5 el concept drift se aplica PRIMERO. El shift
    # categórico convierte a Month-to-month todas las filas que no lo son,
    # así que si se aplicara antes, el subgrupo 'Two year' quedaría vacío y
    # inject_concept_drift no invertiría ninguna etiqueta.
    lotes = [
        base,
        inject_concept_drift(base, flip_pct=0.10),
        inject_concept_drift(base, flip_pct=0.20),
        inject_categorical_shift(
            inject_numeric_shift(inject_concept_drift(base, flip_pct=0.30), pct=0.25),
            pct=0.5,
        ),
        inject_categorical_shift(
            inject_numeric_shift(inject_concept_drift(base, flip_pct=0.40), pct=0.35),
            pct=0.6,
        ),
        inject_categorical_shift(
            inject_numeric_shift(inject_concept_drift(base, flip_pct=0.50), pct=0.50),
            pct=0.8,
        ),
    ]

    for indice, lote in enumerate(lotes):
        ruta = out_dir / f"lote_{indice}.csv"
        lote.to_csv(ruta, index=False)
        rutas.append(ruta)
        print(f"Generado {ruta} ({len(lote)} filas)")

    return rutas


def main() -> None:
    from src.features import clean, load_raw, split_data

    df = clean(load_raw("data/telco_churn.csv"))
    _, X_test, _, y_test = split_data(df)
    reserva = X_test.copy()
    reserva[TARGET] = y_test
    generate_all_batches(reserva)


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Ejecutar los tests**

Run: `pytest drift/tests/test_generators.py -v`
Esperado: 10 tests PASS

- [ ] **Step 5: Generar los lotes reales**

```bash
python -m drift.generators
ls -la data/batches/
```
Esperado: `lote_0.csv` … `lote_5.csv`

- [ ] **Step 6: Commit**

```bash
git add drift/generators.py drift/tests/test_generators.py
git commit -m "feat: generadores de lotes con deriva controlada"
```

---

# Tarea 16 — La puerta de drift **[LOCAL]**

**Files:**
- Create: `drift/check.py`, `drift/tests/test_check.py`

**Interfaces:**
- Consumes: `drift.detectors.detect_data_drift`, `src.features`
- Produces:
  - `load_baseline() -> pd.DataFrame`
  - `run_check(batch_path) -> tuple[list[DriftResult], bool]` — el bool es `hay_deriva`
  - `main(argv=None) -> int` — 0 verde, 1 rojo

- [ ] **Step 1: Escribir los tests**

```python
# drift/tests/test_check.py
import pandas as pd
import pytest

from drift.check import main, run_check
from drift.generators import generate_all_batches
from src.features import TARGET, clean, load_raw, split_data


@pytest.fixture(scope="module")
def lotes(tmp_path_factory):
    directorio = tmp_path_factory.mktemp("lotes")
    df = clean(load_raw("data/telco_churn.csv"))
    _, X_te, _, y_te = split_data(df)
    reserva = X_te.copy()
    reserva[TARGET] = y_te
    return generate_all_batches(reserva, out_dir=directorio, n=500)


def test_puerta_verde_en_lote_limpio(lotes):
    """VERDE: datos del mismo origen que el entrenamiento."""
    _, hay_deriva = run_check(lotes[0])
    assert not hay_deriva


def test_puerta_roja_en_lote_con_data_drift(lotes):
    """ROJO: el lote 3 lleva tarifas +25% y mezcla de Contract alterada."""
    resultados, hay_deriva = run_check(lotes[3])
    assert hay_deriva
    derivadas = {r.variable for r in resultados if r.drifted}
    assert "MonthlyCharges" in derivadas
    assert "Contract" in derivadas


def test_puerta_roja_en_lote_severo(lotes):
    _, hay_deriva = run_check(lotes[5])
    assert hay_deriva


def test_main_devuelve_0_con_lote_limpio(lotes):
    assert main(["--batch", str(lotes[0])]) == 0


def test_main_devuelve_1_con_lote_derivado(lotes):
    assert main(["--batch", str(lotes[3])]) == 1


def test_main_imprime_las_variables_derivadas(lotes, capsys):
    main(["--batch", str(lotes[3])])
    salida = capsys.readouterr().out
    assert "MonthlyCharges" in salida
    assert "DERIVA" in salida
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `pytest drift/tests/test_check.py -v`
Esperado: FAIL con `ModuleNotFoundError: No module named 'drift.check'`

- [ ] **Step 3: Implementar `drift/check.py`**

```python
"""Puerta de calidad de data drift.

Verde (exit 0) con datos del mismo origen que el entrenamiento.
Rojo  (exit 1) cuando se inyecta deriva deliberadamente.

Este es el artefacto que responde al requisito §6.1 del enunciado. Los tests
de pytest son otra cosa: verifican que ESTA puerta se comporta como debe.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

from drift.detectors import DriftResult, detect_data_drift
from src.features import ALL_FEATURES, clean, load_raw, split_data

BASELINE_CSV = "data/telco_churn.csv"


def load_baseline() -> pd.DataFrame:
    """El baseline es siempre el conjunto de entrenamiento."""
    X_train, _, _, _ = split_data(clean(load_raw(BASELINE_CSV)))
    return X_train


def run_check(batch_path: str | Path) -> tuple[list[DriftResult], bool]:
    """Evalúa un lote contra el baseline. Devuelve (resultados, hay_deriva)."""
    baseline = load_baseline()
    lote = pd.read_csv(batch_path)
    lote["SeniorCitizen"] = lote["SeniorCitizen"].astype(str)

    resultados = detect_data_drift(baseline, lote[ALL_FEATURES])
    return resultados, any(r.drifted for r in resultados)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Puerta de detección de data drift")
    parser.add_argument("--batch", required=True, help="Ruta al CSV del lote a evaluar")
    args = parser.parse_args(argv)

    resultados, hay_deriva = run_check(args.batch)

    print(f"\nLote evaluado: {args.batch}")
    print(f"Baseline:      {BASELINE_CSV} (conjunto de entrenamiento)")
    print("-" * 78)
    for resultado in resultados:
        print(resultado)
    print("-" * 78)

    derivadas = sorted({r.variable for r in resultados if r.drifted})
    if hay_deriva:
        print(f"ROJO — deriva detectada en {len(derivadas)} variable(s): {', '.join(derivadas)}")
        return 1

    print("VERDE — sin deriva significativa")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Ejecutar los tests**

Run: `pytest drift/tests/test_check.py -v`
Esperado: 6 tests PASS

- [ ] **Step 5: Verificar la puerta a mano**

```bash
python -m drift.check --batch data/batches/lote_0.csv ; echo "exit=$?"
python -m drift.check --batch data/batches/lote_3.csv ; echo "exit=$?"
```
Esperado: `exit=0` y `exit=1` respectivamente.

- [ ] **Step 6: Commit**

```bash
git add drift/check.py drift/tests/test_check.py
git commit -m "feat: puerta de drift con exit 0 verde y exit 1 rojo"
```

---

# Tarea 17 — Concept drift y criterio de reentrenamiento **[LOCAL]**

**Files:**
- Create: `drift/monitor.py`, `drift/tests/test_monitor.py`

**Interfaces:**
- Consumes: `drift.generators`, `src.features`
- Produces:
  - `AUC_DROP_THRESHOLD = 0.05`, `CONSECUTIVE_BATCHES = 3`
  - `auc_per_batch(model, batch_paths) -> list[float]`
  - `retraining_alarm(aucs, baseline_auc, drop=0.05, consecutive=3) -> bool`
  - `first_alarm_index(aucs, baseline_auc, drop=0.05, consecutive=3) -> int | None`
  - `plot_auc_timeline(aucs, baseline_auc, out_path) -> Path`

- [ ] **Step 1: Escribir los tests**

```python
# drift/tests/test_monitor.py
import pytest

from drift.monitor import (
    AUC_DROP_THRESHOLD, CONSECUTIVE_BATCHES, first_alarm_index,
    plot_auc_timeline, retraining_alarm,
)

BASELINE = 0.85


def test_sin_caida_no_hay_alarma():
    aucs = [0.85, 0.84, 0.85, 0.83, 0.84, 0.85]
    assert not retraining_alarm(aucs, BASELINE)


def test_un_solo_lote_malo_no_dispara_la_alarma():
    """La condición de persistencia evita reentrenar por ruido.

    Un reentrenamiento innecesario tiene coste real, así que la estabilidad
    del criterio importa tanto como su sensibilidad.
    """
    aucs = [0.85, 0.84, 0.60, 0.85, 0.84, 0.85]
    assert not retraining_alarm(aucs, BASELINE)


def test_dos_lotes_malos_seguidos_tampoco_disparan():
    aucs = [0.85, 0.60, 0.61, 0.85, 0.84, 0.85]
    assert not retraining_alarm(aucs, BASELINE)


def test_tres_lotes_malos_seguidos_disparan_la_alarma():
    aucs = [0.85, 0.84, 0.60, 0.61, 0.62, 0.85]
    assert retraining_alarm(aucs, BASELINE)


def test_la_caida_debe_superar_el_umbral():
    """Una caída de 0.02 no supera el umbral de 0.05 aunque sea sostenida."""
    aucs = [0.85, 0.83, 0.83, 0.83, 0.83, 0.83]
    assert not retraining_alarm(aucs, BASELINE)


def test_first_alarm_index_señala_el_tercer_lote_de_la_racha():
    aucs = [0.85, 0.84, 0.60, 0.61, 0.62, 0.85]
    assert first_alarm_index(aucs, BASELINE) == 4


def test_first_alarm_index_es_none_sin_alarma():
    assert first_alarm_index([0.85] * 6, BASELINE) is None


def test_los_umbrales_son_los_documentados():
    assert AUC_DROP_THRESHOLD == 0.05
    assert CONSECUTIVE_BATCHES == 3


def test_plot_genera_el_fichero(tmp_path):
    destino = tmp_path / "grafica.png"
    resultado = plot_auc_timeline([0.85, 0.84, 0.70, 0.65, 0.60, 0.58], BASELINE, destino)
    assert resultado.exists()
    assert resultado.stat().st_size > 1000
```

- [ ] **Step 2: Ejecutar y verificar que falla**

Run: `pytest drift/tests/test_monitor.py -v`
Esperado: FAIL con `ModuleNotFoundError: No module named 'drift.monitor'`

- [ ] **Step 3: Implementar `drift/monitor.py`**

```python
"""Monitoreo de concept drift y criterio de reentrenamiento.

El concept drift cambia la relación entrada-salida: las entradas pueden
verse idénticas y aun así el modelo empieza a equivocarse. Por eso no basta
con el monitoreo de data drift.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sin display, para que funcione en el VPS
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

from src.features import ALL_FEATURES, TARGET  # noqa: E402

# --- Criterio de reentrenamiento y su justificación --------------------
# Se dispara la alarma con una caída de ROC-AUC mayor a 0.05 absolutos
# respecto al baseline, SOSTENIDA durante 3 lotes consecutivos.
#
# La condición de persistencia existe para no reentrenar por un lote
# ruidoso: un reentrenamiento innecesario tiene coste real.
AUC_DROP_THRESHOLD = 0.05
CONSECUTIVE_BATCHES = 3


def auc_per_batch(model, batch_paths: list[str | Path]) -> list[float]:
    """Calcula el ROC-AUC del modelo sobre cada lote sucesivo."""
    aucs: list[float] = []
    for ruta in batch_paths:
        lote = pd.read_csv(ruta)
        lote["SeniorCitizen"] = lote["SeniorCitizen"].astype(str)
        proba = model.predict_proba(lote[ALL_FEATURES])[:, 1]
        aucs.append(float(roc_auc_score(lote[TARGET], proba)))
    return aucs


def first_alarm_index(
    aucs: list[float],
    baseline_auc: float,
    drop: float = AUC_DROP_THRESHOLD,
    consecutive: int = CONSECUTIVE_BATCHES,
) -> int | None:
    """Índice del lote donde se completa la primera racha que dispara alarma."""
    racha = 0
    for indice, auc in enumerate(aucs):
        if baseline_auc - auc > drop:
            racha += 1
            if racha >= consecutive:
                return indice
        else:
            racha = 0
    return None


def retraining_alarm(
    aucs: list[float],
    baseline_auc: float,
    drop: float = AUC_DROP_THRESHOLD,
    consecutive: int = CONSECUTIVE_BATCHES,
) -> bool:
    """True si procede reentrenar según el criterio documentado."""
    return first_alarm_index(aucs, baseline_auc, drop, consecutive) is not None


def plot_auc_timeline(
    aucs: list[float], baseline_auc: float, out_path: str | Path
) -> Path:
    """Gráfica temporal de degradación de la métrica sobre lotes sucesivos."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    umbral = baseline_auc - AUC_DROP_THRESHOLD
    indices = list(range(len(aucs)))

    figura, eje = plt.subplots(figsize=(9, 5))
    eje.plot(indices, aucs, marker="o", linewidth=2, label="ROC-AUC por lote")
    eje.axhline(baseline_auc, linestyle="--", color="green", label=f"Baseline ({baseline_auc:.3f})")
    eje.axhline(umbral, linestyle=":", color="red", label=f"Umbral de alarma ({umbral:.3f})")

    alarma = first_alarm_index(aucs, baseline_auc)
    if alarma is not None:
        eje.axvline(alarma, color="red", alpha=0.25, linewidth=8)
        eje.annotate(
            "Alarma de reentrenamiento\n(3 lotes consecutivos)",
            xy=(alarma, aucs[alarma]),
            xytext=(alarma - 1.8, min(aucs) + 0.03),
            arrowprops={"arrowstyle": "->", "color": "red"},
            fontsize=9,
            color="red",
        )

    eje.set_xlabel("Índice del lote (tiempo)")
    eje.set_ylabel("ROC-AUC")
    eje.set_title("Degradación del modelo sobre lotes sucesivos — concept drift")
    eje.set_xticks(indices)
    eje.grid(alpha=0.3)
    eje.legend(loc="lower left")
    figura.tight_layout()
    figura.savefig(out_path, dpi=150)
    plt.close(figura)

    print(f"Gráfica guardada en {out_path}")
    return out_path


def main() -> None:
    """Ejecuta el monitoreo completo y guarda la gráfica de evidencia."""
    import mlflow

    from src.features import MODEL_NAME

    modelo = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}@champion")

    rutas = [Path(f"data/batches/lote_{i}.csv") for i in range(6)]
    aucs = auc_per_batch(modelo, rutas)
    baseline_auc = aucs[0]

    print(f"Baseline (lote 0): {baseline_auc:.4f}")
    for indice, auc in enumerate(aucs):
        caida = baseline_auc - auc
        marca = "  <-- por debajo del umbral" if caida > AUC_DROP_THRESHOLD else ""
        print(f"  Lote {indice}: ROC-AUC={auc:.4f}  caída={caida:+.4f}{marca}")

    if retraining_alarm(aucs, baseline_auc):
        print(f"\nALARMA: procede reentrenar (lote {first_alarm_index(aucs, baseline_auc)})")
    else:
        print("\nSin alarma: la degradación no cumple el criterio")

    plot_auc_timeline(aucs, baseline_auc, "docs/evidencias/concept_drift.png")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Ejecutar los tests**

Run: `pytest drift/tests/test_monitor.py -v`
Esperado: 9 tests PASS

- [ ] **Step 5: Ejecutar el monitoreo real**

```bash
export MLFLOW_TRACKING_URI=http://<IP_PUBLICA_VPS>:5000
python -m drift.monitor
```
Esperado: la tabla de ROC-AUC por lote y `docs/evidencias/concept_drift.png` generado.

- [ ] **Step 6: Ejecutar la suite completa**

Run: `pytest -v`
Esperado: todos los tests PASS.

- [ ] **Step 7: Commit**

```bash
git add drift/monitor.py drift/tests/test_monitor.py docs/evidencias/concept_drift.png
git commit -m "feat: monitoreo de concept drift con criterio de reentrenamiento"
```

---

# Tarea 18 — Interfaz web **[LOCAL]**

**Files:**
- Create: `src/api/static/index.html`, `src/api/static/app.js`

**Interfaces:**
- Consumes: `POST /predict` del mismo origen (Tarea 8)
- Produces: UI accesible en `https://churn.juanitodev.com/`

- [ ] **Step 1: Crear `src/api/static/index.html`**

```html
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Predicción de abandono — Telco Churn</title>
  <style>
    :root { --borde:#d0d7de; --fondo:#f6f8fa; --texto:#1f2328; --acento:#0969da; }
    * { box-sizing: border-box; }
    body { font-family: system-ui, -apple-system, sans-serif; margin:0;
           padding:2rem 1rem; background:var(--fondo); color:var(--texto); }
    main { max-width:840px; margin:0 auto; background:#fff; padding:2rem;
           border:1px solid var(--borde); border-radius:10px; }
    h1 { margin-top:0; font-size:1.5rem; }
    .sub { color:#636c76; font-size:.9rem; margin-bottom:1.5rem; }
    .grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(210px,1fr)); gap:1rem; }
    label { display:block; font-size:.8rem; font-weight:600; margin-bottom:.25rem; }
    input, select { width:100%; padding:.5rem; border:1px solid var(--borde);
                    border-radius:6px; font-size:.9rem; background:#fff; }
    button { margin-top:1.5rem; padding:.7rem 1.5rem; background:var(--acento);
             color:#fff; border:0; border-radius:6px; font-size:1rem; cursor:pointer; }
    button:disabled { opacity:.6; cursor:wait; }
    #resultado { margin-top:1.5rem; padding:1.25rem; border-radius:8px; display:none; }
    #resultado.churn { background:#fff1f0; border:1px solid #ffaba8; }
    #resultado.retiene { background:#eafaef; border:1px solid #a6e3b8; }
    #resultado.error { background:#fff8e6; border:1px solid #f0d999; }
    .prob { font-size:2rem; font-weight:700; }
    .meta { margin-top:.75rem; font-size:.8rem; color:#636c76; font-family:ui-monospace,monospace; }
    .pod { background:#ddf4ff; padding:.15rem .45rem; border-radius:4px; font-weight:600; }
  </style>
</head>
<body>
<main>
  <h1>Predicción de abandono de clientes</h1>
  <p class="sub">
    Consume <code>POST /predict</code> del servicio desplegado en Kubernetes.
    Cada respuesta indica qué pod la atendió: pulsa varias veces y verás
    cómo cambia — eso es el balanceo de carga en directo.
  </p>

  <form id="formulario">
    <div class="grid">
      <div><label>Antigüedad (meses)</label><input type="number" name="tenure" value="12" min="0" max="100" required></div>
      <div><label>Cargo mensual</label><input type="number" name="MonthlyCharges" value="70.35" step="0.01" min="0" required></div>
      <div><label>Cargo total</label><input type="number" name="TotalCharges" value="844.20" step="0.01" min="0" required></div>

      <div><label>Género</label><select name="gender"><option>Female</option><option>Male</option></select></div>
      <div><label>Tercera edad</label><select name="SeniorCitizen"><option value="0">No</option><option value="1">Sí</option></select></div>
      <div><label>Pareja</label><select name="Partner"><option>Yes</option><option>No</option></select></div>
      <div><label>Dependientes</label><select name="Dependents"><option>No</option><option>Yes</option></select></div>
      <div><label>Servicio telefónico</label><select name="PhoneService"><option>Yes</option><option>No</option></select></div>
      <div><label>Líneas múltiples</label><select name="MultipleLines"><option>No</option><option>Yes</option><option>No phone service</option></select></div>
      <div><label>Servicio de internet</label><select name="InternetService"><option>Fiber optic</option><option>DSL</option><option>No</option></select></div>
      <div><label>Seguridad en línea</label><select name="OnlineSecurity"><option>No</option><option>Yes</option><option>No internet service</option></select></div>
      <div><label>Copia de seguridad</label><select name="OnlineBackup"><option>Yes</option><option>No</option><option>No internet service</option></select></div>
      <div><label>Protección de dispositivo</label><select name="DeviceProtection"><option>No</option><option>Yes</option><option>No internet service</option></select></div>
      <div><label>Soporte técnico</label><select name="TechSupport"><option>No</option><option>Yes</option><option>No internet service</option></select></div>
      <div><label>Streaming TV</label><select name="StreamingTV"><option>Yes</option><option>No</option><option>No internet service</option></select></div>
      <div><label>Streaming películas</label><select name="StreamingMovies"><option>No</option><option>Yes</option><option>No internet service</option></select></div>
      <div><label>Tipo de contrato</label><select name="Contract"><option>Month-to-month</option><option>One year</option><option>Two year</option></select></div>
      <div><label>Facturación sin papel</label><select name="PaperlessBilling"><option>Yes</option><option>No</option></select></div>
      <div><label>Método de pago</label><select name="PaymentMethod">
        <option>Electronic check</option><option>Mailed check</option>
        <option>Bank transfer (automatic)</option><option>Credit card (automatic)</option>
      </select></div>
    </div>

    <button type="submit" id="boton">Predecir</button>
  </form>

  <div id="resultado"></div>
</main>
<script src="/app.js"></script>
</body>
</html>
```

- [ ] **Step 2: Crear `src/api/static/app.js`**

```javascript
// La UI se sirve desde el propio contenedor de la API, así que el fetch es
// del mismo origen: no hace falta CORS ni configurar ninguna URL base.

const NUMERICOS = ["tenure", "MonthlyCharges", "TotalCharges"];

document.getElementById("formulario").addEventListener("submit", async (evento) => {
  evento.preventDefault();

  const boton = document.getElementById("boton");
  const caja = document.getElementById("resultado");
  boton.disabled = true;
  boton.textContent = "Consultando…";

  const datos = {};
  for (const [clave, valor] of new FormData(evento.target).entries()) {
    datos[clave] = NUMERICOS.includes(clave) ? Number(valor) : valor;
  }

  try {
    const respuesta = await fetch("/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(datos),
    });

    if (!respuesta.ok) {
      const detalle = await respuesta.text();
      throw new Error(`HTTP ${respuesta.status} — ${detalle}`);
    }

    const r = await respuesta.json();
    const pct = (r.probability * 100).toFixed(1);

    caja.className = r.prediction === 1 ? "churn" : "retiene";
    caja.innerHTML = `
      <div class="prob">${pct}%</div>
      <div>de probabilidad de abandono —
        <strong>${r.prediction === 1 ? "cliente en riesgo" : "cliente estable"}</strong>
      </div>
      <div class="meta">
        atendido por <span class="pod">${r.served_by}</span>
        · modelo versión ${r.model_version}
      </div>`;
  } catch (error) {
    caja.className = "error";
    caja.innerHTML = `<strong>Error:</strong> ${error.message}`;
  } finally {
    caja.style.display = "block";
    boton.disabled = false;
    boton.textContent = "Predecir";
  }
});
```

- [ ] **Step 3: Probar la UI en local**

```bash
export MLFLOW_TRACKING_URI=http://<IP_PUBLICA_VPS>:5000
uvicorn src.api.main:app --reload --port 8000
```

Abrir `http://localhost:8000/` y pulsar Predecir. Verificar que muestra
porcentaje, veredicto y `served_by` (será `local` fuera de Kubernetes).

- [ ] **Step 4: Verificar que los tests de la API siguen pasando**

Run: `pytest tests/test_api.py -v`
Esperado: 10 tests PASS. El montaje de `StaticFiles` no debe romper las rutas.

- [ ] **Step 5: Reconstruir y redesplegar en el VPS**

```bash
# En el VPS
cd ~/proyecto-final && git pull
docker build -t telco-churn-api:v1 .
docker save telco-churn-api:v1 | sudo k3s ctr images import -
kubectl rollout restart deployment/telco-churn-api
kubectl rollout status deployment/telco-churn-api
```

- [ ] **Step 6: Verificar la UI en producción**

Abrir `https://churn.juanitodev.com/` en el navegador. Pulsar Predecir varias
veces y comprobar que `served_by` cambia entre pods.

- [ ] **Step 7: Commit**

```bash
git add src/api/static/
git commit -m "feat: interfaz web servida por la propia API"
```

---

# Tarea 19 — Entrenamiento real y promoción del modelo **[VPS/LOCAL]**

**Files:**
- Create: `docs/runbooks/06-demo-mlflow.md`, `docs/runbooks/07-demo-drift.md`

**Interfaces:**
- Consumes: `src.train`, `src.register`
- Produces: 6 runs reales en MLflow, 2 versiones registradas, alias `champion` en la v2

- [ ] **Step 1: Ejecutar los 6 runs contra el MLflow del VPS**

```bash
export MLFLOW_TRACKING_URI=http://<IP_PUBLICA_VPS>:5000
python -m src.train
```

Esperado: 6 líneas con `roc_auc` por modelo. Anotar cuál gana.

- [ ] **Step 2: Registrar la v1 (línea base lineal) y la v2 (ganador)**

```python
# Ejecutar en python, con MLFLOW_TRACKING_URI ya exportado
import mlflow
from src.features import EXPERIMENT_NAME
from src.register import best_run_id, register_run, set_champion

exp = mlflow.get_experiment_by_name(EXPERIMENT_NAME)
runs = mlflow.search_runs(experiment_ids=[exp.experiment_id])

# v1: la mejor regresión logística, como línea base
lineales = runs[runs["params.modelo"] == "logreg"].sort_values("metrics.roc_auc", ascending=False)
v1 = register_run(lineales.iloc[0]["run_id"])
print(f"v{v1} = línea base logística")

# v2: el ganador absoluto
v2 = register_run(best_run_id())
set_champion(v2)
print(f"v{v2} = champion")
```

Esperado: dos versiones registradas y el alias apuntando a la v2.

- [ ] **Step 3: Reiniciar los pods para que carguen el modelo bueno**

```bash
# En el VPS
kubectl rollout restart deployment/telco-churn-api
kubectl rollout status deployment/telco-churn-api
curl -s http://localhost:30080/model-info
```

Esperado: `/model-info` devuelve `"version":"2"` y el `run_id` del ganador.

- [ ] **Step 4: Escribir `docs/runbooks/06-demo-mlflow.md`**

````markdown
# Runbook 06 — Demo en vivo de MLflow

Responsable: integrante #1. El enunciado (§3.4) exige poder hacer estas
cuatro cosas frente al docente. Ensayarlas.

URL: `https://mlflow.juanitodev.com` (usuario `docente`, contraseña anotada en el
runbook 04).

## 1. Abrir el experimento y explicar cada run

Experimento `telco-churn-experimento`. Explicar que los 6 runs comparten
split, semilla y métricas, y que eso es lo que los hace comparables.

## 2. Ordenar y filtrar por la métrica principal

Pulsar la columna `roc_auc` para ordenar descendente.

Preparar la respuesta a "¿por qué ROC-AUC y no accuracy?": el dataset tiene
un 26,5% de positivos, así que un modelo que prediga siempre "no abandona"
saca 73,5% de accuracy sin aprender nada. Además ROC-AUC es insensible al
umbral de decisión.

## 3. Comparar varios runs

Seleccionar los 6 con las casillas → botón **Compare**. Usar la vista de
coordenadas paralelas para argumentar por qué se eligió el modelo desplegado.

## 4. Abrir el Model Registry

Models → `telco-churn`. Mostrar las 2 versiones y que el alias `champion`
apunta a la v2.

## 5. Cerrar el círculo de la trazabilidad

Abrir en otra pestaña `https://churn.juanitodev.com/model-info` y comparar el
`run_id` que devuelve con el de la versión del registro. Son el mismo.

**Esa es la trazabilidad que pide el enunciado**: el modelo que está
sirviendo peticiones y el experimento exacto que lo produjo.
````

- [ ] **Step 5: Escribir `docs/runbooks/07-demo-drift.md`**

````markdown
# Runbook 07 — Demo de detección de drift

Responsable: integrante #4. Presentar en este orden: primero la suite,
luego la puerta.

## 0. Generar los lotes

`data/batches/` NO está versionado (está en el `.gitignore`): hay que
generarlos en la máquina donde se hace la demo antes de empezar.

```bash
python -m drift.generators
ls data/batches/
```

Esperado: `lote_0.csv` … `lote_5.csv`

## 1. La suite de tests — todo verde

```bash
pytest drift/ -v
```

Discurso: *"nuestros detectores funcionan y está probado, incluidas las
fórmulas de PSI y Cramér's V verificadas contra valores calculados a mano."*

## 2. La puerta — verde con datos limpios

```bash
python -m drift.check --batch data/batches/lote_0.csv ; echo "exit=$?"
```
Esperado: `VERDE — sin deriva significativa`, `exit=0`

## 3. La puerta — roja con datos derivados

```bash
python -m drift.check --batch data/batches/lote_3.csv ; echo "exit=$?"
```
Esperado: `ROJO — deriva detectada en N variable(s)`, `exit=1`

## 3b. (Opcional, alto impacto) La puerta es ciega al concept drift

Los lotes 1 y 2 llevan SOLO concept drift: las entradas son idénticas al
origen, así que la puerta de data drift sale **verde** sobre ellos aunque
el modelo ya se esté degradando (se ve en la gráfica del paso 4).

```bash
python -m drift.check --batch data/batches/lote_1.csv ; echo "exit=$?"
```
Esperado: `VERDE`, `exit=0` — y ese es el argumento: *"por eso el data
drift no basta y monitoreamos también la métrica del modelo"*.

## 4. Concept drift y criterio de reentrenamiento

```bash
python -m drift.monitor
```

Mostrar `docs/evidencias/concept_drift.png`.

## Preguntas previsibles y sus respuestas

**"¿De dónde sale el umbral de PSI 0.25?"**
De la escala convencional de las scorecards crediticias, donde nació el
índice: <0.10 estable, 0.10-0.25 moderado, >0.25 significativo.

**"¿Por qué KS y no un t-test?"**
KS es no paramétrico. `MonthlyCharges` es bimodal (clientes con y sin
internet), así que un t-test asumiría una normalidad que no existe.

**"¿Por qué exigen D > 0.10 además del p-valor?"**
Con n=7.043, KS rechaza H0 ante diferencias sin relevancia práctica: es
hipersensible al tamaño muestral. El tamaño del efecto separa
"estadísticamente significativo" de "prácticamente relevante". Sin eso, el
monitor alertaría a diario y nadie le haría caso.

**"¿Por qué 3 lotes consecutivos y no uno?"**
Un reentrenamiento tiene coste real. La condición de persistencia evita
dispararlo por un lote ruidoso. Hay un test específico que lo comprueba:
`test_un_solo_lote_malo_no_dispara_la_alarma`.

**"En producción la etiqueta real tarda 30 días. ¿Qué hacen mientras tanto?"**
El ROC-AUC por lote no es calculable en tiempo real, solo en retrospectiva.
Mientras llegan las etiquetas se vigila con tres proxies que no las
necesitan: (1) data drift de las entradas, que es un indicador adelantado;
(2) prediction drift, aplicando KS a la distribución de scores del modelo;
(3) la tasa de positivos predichos — si pasa del 26% histórico al 40%, algo
cambió aunque nadie pueda confirmarlo todavía.
````

- [ ] **Step 6: Commit**

```bash
git add docs/runbooks/06-demo-mlflow.md docs/runbooks/07-demo-drift.md
git commit -m "docs: runbooks de las demos de MLflow y de drift"
```

---

# Tarea 20 — Documentación de entrega **[LOCAL]**

**Files:**
- Create: `docs/ARQUITECTURA.md`, `docs/EVIDENCIAS.md`, `docs/REPARTO.md`, `README.md`

**Interfaces:**
- Consumes: todas las tareas anteriores

- [ ] **Step 1: Escribir `docs/ARQUITECTURA.md`**

Debe contener, como mínimo:

1. **Diagrama de arquitectura** — copiar el de §3 del spec.
2. **Decisiones y su justificación** — una sección por cada una:
   - Por qué MLflow fuera de k3s
   - Por qué el pod carga el modelo por alias y no horneado en la imagen
   - Por qué NO hay caché local del modelo (trade-off consciente)
   - Por qué nginx en el host y no el Ingress de Traefik
   - Por qué ROC-AUC como métrica principal
   - Por qué KS para numéricas y PSI/Chi² para categóricas
   - De dónde sale cada umbral
3. **Modelo desplegado** — tabla con: nombre `telco-churn`, número de versión, `run_id`, alias `champion`, ROC-AUC. **Rellenar con los valores reales de la Tarea 19.**
4. **Política de retraso de etiquetas** — los tres proxies del runbook 07.
5. **Limitaciones de seguridad declaradas** — §13 del spec.
6. **Fuera de alcance y por qué** — §14 del spec.

- [ ] **Step 2: Escribir `docs/EVIDENCIAS.md`**

Recopilar, cada una con su captura o salida de terminal:

| Evidencia | Origen |
|---|---|
| 3 réplicas en Running | Runbook 05, demo 1 |
| Balanceo entre pods | Runbook 05, demo 2 |
| Autorreparación sin caída de servicio | Runbook 05, demo 3 |
| Escalado a 5 y a 2 réplicas | Runbook 05, demo 4 |
| Experimento con los 6 runs | Captura de la UI de MLflow |
| Vista de comparación de runs | Captura de la UI de MLflow |
| Model Registry con 2 versiones y alias | Captura de la UI de MLflow |
| `/model-info` con el mismo `run_id` | `curl https://churn.juanitodev.com/model-info` |
| `pytest` completo en verde | Salida de terminal |
| Puerta de drift en verde (lote 0) | Runbook 07, paso 2 |
| Puerta de drift en rojo (lote 3) | Runbook 07, paso 3 |
| Gráfica de concept drift | `docs/evidencias/concept_drift.png` |
| Certificado TLS válido en ambos subdominios | Runbook 04, paso 8 |
| Puertos 5000 y 30080 cerrados desde fuera | Runbook 04, paso 8 |
| UI web funcionando contra el servicio en K8s | Captura del navegador |

- [ ] **Step 3: Escribir `docs/REPARTO.md`**

```markdown
# Reparto del trabajo

| # | Integrante | Componente | Ficheros principales | Evidencia en git |
|---|---|---|---|---|
| 1 | <nombre> | Modelo y MLflow | `src/features.py`, `src/train.py`, `src/register.py` | commits en `feat/modelo` |
| 2 | <nombre> | Contenedor y API | `src/api/`, `Dockerfile`, `requirements.txt` | commits en `feat/api` |
| 3 | <nombre> | Kubernetes | `k8s/`, runbooks 02, 03, 05 | commits en `feat/k8s` |
| 4 | <nombre> | Drift | `drift/`, runbook 07 | commits en `feat/drift` |
| 5 | <nombre> | Infraestructura, TLS, UI y docs | `infra/`, `src/api/static/`, runbooks 01, 04, `docs/` | commits en `feat/infra` |

Verificación del reparto:
```bash
git shortlog -sne
git log --format='%an %s' --reverse
```

> **Nota sobre la defensa:** el enunciado (§2) establece que la defensa es
> individual y cubre **cualquier** parte del proyecto, no solo la que cada
> integrante construyó. El día 6 se dedica a que los cinco recorran el
> sistema completo.
```

- [ ] **Step 4: Escribir el `README.md` raíz**

Debe incluir: descripción en un párrafo, URLs de los dos subdominios,
arranque rápido local, cómo ejecutar los tests, y enlaces a
`docs/ARQUITECTURA.md`, `docs/EVIDENCIAS.md`, `docs/REPARTO.md` y a los
runbooks.

- [ ] **Step 5: Verificación final completa**

```bash
pytest -v
python -m drift.check --batch data/batches/lote_0.csv ; echo "exit=$?"   # 0
python -m drift.check --batch data/batches/lote_3.csv ; echo "exit=$?"   # 1
curl -s https://churn.juanitodev.com/model-info
curl -sI https://mlflow.juanitodev.com/ | head -1                              # 401
kubectl get pods
```

Recorrer los criterios de aceptación de §15 del spec y marcar cada uno.

- [ ] **Step 6: Generar el archivo comprimido de entrega**

```bash
cd ..
zip -r entrega-telco-churn-mlops.zip proyecto-final \
  -x '*/.git/*' '*/.venv/*' '*/__pycache__/*' '*/mlruns/*' '*/infra/.env'
```

- [ ] **Step 7: Commit final**

```bash
git add docs/ README.md
git commit -m "docs: documentación de arquitectura, evidencias y reparto"
git push
```

---

## Verificación contra los criterios de aceptación del spec

| Criterio (§15 del spec) | Tarea que lo cubre |
|---|---|
| UI de MLflow con ≥6 runs comparables | T19 paso 1, T4 |
| ≥2 versiones registradas con alias `champion` | T19 paso 2, T5 |
| Imagen que levanta sin pasos manuales | T9 |
| `requirements.txt` con `==`, incluido MLflow | T1 pasos 3-4 |
| 3 réplicas en Running | T13 demo 1 |
| ≥2 valores distintos de `served_by` en 10 peticiones | T13 demo 2 |
| Autorreparación sin peticiones fallidas | T13 demo 3 |
| Escalado visible | T13 demo 4 |
| `pytest drift/` completamente en verde | T14, T15, T16, T17 |
| `drift.check` lote 0 → exit 0 | T16 paso 5 |
| `drift.check` lote 3 → exit 1 | T16 paso 5 |
| Gráfica temporal de ROC-AUC | T17 paso 5 |
| `/model-info` coincide con `ARQUITECTURA.md` | T19 paso 3, T20 paso 1 |
| UI web contra `https://churn.juanitodev.com` | T18 paso 6 |
| Certificado válido y redirección 80→443 | T12 paso 4 |
| `certbot renew --dry-run` sin errores | T12, runbook 04 paso 7 |
| 5000 y 30080 cerrados desde fuera | T6 paso 8, T12 paso 4 |
| `REPARTO.md` coherente con el historial | T20 paso 3 |
