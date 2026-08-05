# telco-churn-mlops

Predicción de abandono de clientes de telecomunicaciones, llevada desde el
entrenamiento trazable en MLflow hasta un despliegue con 3 réplicas en
Kubernetes, con detección automatizada de data drift y concept drift.

**MOD14 — Maestría en Ciencia de Datos e Inteligencia Artificial, UAGRM.**

| Servicio | URL |
|---|---|
| API de inferencia + UI web | `https://churn.<dominio>` |
| MLflow (usuario `docente`) | `https://mlflow.<dominio>` |

---

## Documentación

| Documento | Contenido |
|---|---|
| [`docs/ARQUITECTURA.md`](docs/ARQUITECTURA.md) | Decisiones de diseño y su justificación |
| [`docs/EVIDENCIAS.md`](docs/EVIDENCIAS.md) | Salidas de terminal de cada requisito |
| [`docs/REPARTO.md`](docs/REPARTO.md) | Quién construyó qué |
| [`docs/PROYECTO.md`](docs/PROYECTO.md) | Enunciado original |
| [`docs/EQUIPO.md`](docs/EQUIPO.md) | Coordinación y preparación de la defensa |
| [`docs/defensa-drift.md`](docs/defensa-drift.md) | Guion de defensa de la parte de drift |

### Runbooks

| # | Qué hace | Responsable |
|---|---|---|
| [01](docs/runbooks/01-bootstrap-vps.md) | DNS, Docker, MLflow + PostgreSQL, firewall | #5 |
| [02](docs/runbooks/02-instalar-k3s.md) | k3s sin Traefik y verificación de red | #3 |
| [03](docs/runbooks/03-build-y-deploy.md) | build → import → deploy | #3 |
| [04](docs/runbooks/04-tls-y-subdominios.md) | nginx, certbot, dos subdominios | #5 |
| [05](docs/runbooks/05-demos-kubernetes.md) | Las 4 demostraciones exigidas | #3 |
| [06](docs/runbooks/06-demo-mlflow.md) | Demo en vivo de la UI de MLflow | #1 |
| [07](docs/runbooks/07-demo-drift.md) | Puerta de drift en verde y en rojo | #4 |

---

## Arranque rápido en local

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

python scripts/download_data.py          # descarga el dataset
pytest -q                                # 81 tests
```

### Levantar MLflow

```bash
cd infra
cp .env.example .env      # ajustar credenciales y MLFLOW_HOST_PORT
docker compose up -d
```

> En macOS, poner `MLFLOW_HOST_PORT=5001`: AirPlay ocupa el 5000.

### Entrenar y registrar

```bash
export MLFLOW_TRACKING_URI=http://localhost:5000
python -m src.train           # 6 runs
python -m src.register        # registra el mejor y lo marca como champion
```

### Servir la API

```bash
uvicorn src.api.main:app --port 8000
# UI en http://localhost:8000/
```

### Detección de drift

```bash
python -m drift.generators                              # genera los 6 lotes
python -m drift.check --batch data/batches/lote_0.csv   # VERDE, exit 0
python -m drift.check --batch data/batches/lote_3.csv   # ROJO,  exit 1
python -m drift.monitor                                 # gráfica + alarma
```

---

## Estructura

```
├── src/
│   ├── features.py      Esquema, limpieza y preprocesador (compartido train↔serve)
│   ├── train.py         Los 6 runs con tracking en MLflow
│   ├── register.py      Registro de versiones y alias champion
│   └── api/             FastAPI + contratos Pydantic + UI estática
├── drift/
│   ├── detectors.py     KS, PSI, Chi², Cramér's V
│   ├── generators.py    Lotes con deriva inyectada de forma controlada
│   ├── check.py         Puerta de calidad (exit 0 verde / exit 1 rojo)
│   └── monitor.py       ROC-AUC por lote, criterio de reentrenamiento, gráfica
├── k8s/                 Deployment (3 réplicas) y Service (NodePort 30080)
├── infra/               MLflow + PostgreSQL y plantillas de nginx
├── scripts/             Descarga del dataset y demo de balanceo
└── tests/ · drift/tests/
```

---

## Stack

Python 3.11 · scikit-learn · MLflow 3.15 · FastAPI · Pydantic · scipy ·
pytest · Docker · k3s · nginx · certbot · PostgreSQL
