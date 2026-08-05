# telco-churn-mlops

Ciclo de vida completo de un modelo de machine learning: desde la
experimentación trazable con MLflow hasta un despliegue con alta
disponibilidad en Kubernetes, con detección automatizada de deriva.

Predice el abandono de clientes de telecomunicaciones. El énfasis del proyecto
**no está en la exactitud del modelo** sino en la ingeniería que lo rodea:
empaquetado reproducible, despliegue con réplicas y detección de degradación
en el tiempo.

> Proyecto final del módulo 14 — Maestría en Ciencia de Datos e Inteligencia
> Artificial.

---

## Servicios en producción

| Servicio | URL | Acceso |
|---|---|---|
| API de inferencia y UI web | https://churn.juanitodev.com | Público |
| MLflow — experimentos y Model Registry | https://mlflow.juanitodev.com | Autenticación básica |

```bash
curl -s https://churn.juanitodev.com/model-info
```

```json
{"model_name":"telco-churn","version":"2",
 "run_id":"140470a3690b4e37829cb13bc23ece0b","alias":"champion"}
```

Ese `run_id` es el del experimento que produjo el modelo: el servicio que
atiende peticiones y su origen están vinculados de forma verificable.

---

## Arquitectura en una frase

MLflow y PostgreSQL corren en Docker Compose fuera del clúster; el servicio de
inferencia corre en **k3s con 3 réplicas** y **carga el modelo del Model
Registry por alias** (`models:/telco-churn@champion`) al arrancar; nginx en el
host termina TLS para ambos subdominios.

El detalle y la justificación de cada decisión están en
**[docs/ARQUITECTURA.md](docs/ARQUITECTURA.md)**.

---

## Estado

| Fase | Contenido | Estado |
|---|---|---|
| 1 | MLflow: 6 runs, 2 versiones registradas, alias `champion` | Completa |
| 2 | Contenerización con Dockerfile propio y usuario no-root | Completa |
| 3 | Kubernetes: 3 réplicas, balanceo, autorreparación y escalado | Completa |
| 4 | Data drift y concept drift con pruebas automatizadas | Completa |
| Extra | API REST e interfaz web consumiendo el servicio real | Completa |

**88 tests** en verde. Evidencias de cada requisito en
**[docs/EVIDENCIAS.md](docs/EVIDENCIAS.md)**.

---

## Arranque rápido en local

Requiere Python 3.12.

```bash
git clone <url-del-repositorio>
cd proyecto-final

python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

pytest -v
```

### Entrenar contra el MLflow del proyecto

```bash
export MLFLOW_TRACKING_URI=https://mlflow.juanitodev.com
export MLFLOW_TRACKING_USERNAME=mlops
export MLFLOW_TRACKING_PASSWORD=<contraseña>

python -m src.train      # los 6 runs
python -m src.register   # registra el mejor y lo promueve a champion
```

### Ejecutar la detección de drift

```bash
python -m drift.generators                              # genera los 6 lotes
python -m drift.check --batch data/batches/lote_0.csv   # VERDE, exit 0
python -m drift.check --batch data/batches/lote_3.csv   # ROJO,  exit 1
python -m drift.monitor                                 # gráfica de concept drift
```

### Levantar la API en local

```bash
uvicorn src.api.main:app --reload --port 8000
```

Interfaz en `http://localhost:8000/`, documentación automática en `/docs`.

---

## Contrato de la API

| Método | Ruta | Propósito |
|---|---|---|
| `GET` | `/health` | Liveness. Responde 200 si el proceso vive. |
| `GET` | `/ready` | Readiness. Responde 200 solo si el modelo está cargado. |
| `GET` | `/model-info` | Trazabilidad: nombre, versión, `run_id` y alias. |
| `POST` | `/predict` | Inferencia. Devuelve probabilidad y el pod que atendió. |
| `GET` | `/` | Interfaz web. |

```bash
curl -X POST https://churn.juanitodev.com/predict \
  -H 'Content-Type: application/json' \
  -d '{"tenure":12,"MonthlyCharges":70.35,"TotalCharges":844.20,
       "gender":"Female","SeniorCitizen":"0","Partner":"Yes","Dependents":"No",
       "PhoneService":"Yes","MultipleLines":"No","InternetService":"Fiber optic",
       "OnlineSecurity":"No","OnlineBackup":"Yes","DeviceProtection":"No",
       "TechSupport":"No","StreamingTV":"Yes","StreamingMovies":"No",
       "Contract":"Month-to-month","PaperlessBilling":"Yes",
       "PaymentMethod":"Electronic check"}'
```

```json
{"prediction":1,"probability":0.5799,
 "served_by":"telco-churn-api-5fd68dcc67-m9zsd","model_version":"2"}
```

El campo `served_by` identifica la réplica que respondió: repetir la llamada
devuelve nombres distintos y demuestra el balanceo de carga.

---

## Estructura del repositorio

```
├── data/telco_churn.csv       Dataset versionado (7.043 × 21)
├── src/
│   ├── features.py            Esquema y preprocesamiento compartido train↔serve
│   ├── train.py               Los 6 runs con tracking en MLflow
│   ├── register.py            Registro de versiones y alias champion
│   └── api/                   FastAPI + interfaz web estática
├── drift/
│   ├── detectors.py           KS, PSI, Chi², Cramér's V
│   ├── generators.py          Inyección controlada de deriva
│   ├── check.py               Puerta de calidad (exit 0 verde / 1 rojo)
│   └── monitor.py             Concept drift y criterio de reentrenamiento
├── k8s/                       Deployment (3 réplicas) y Service (NodePort)
├── infra/                     Docker Compose de MLflow y plantillas de nginx
├── scripts/                   Descarga del dataset y demo de balanceo
├── tests/  ·  drift/tests/    88 tests
└── docs/                      Arquitectura, evidencias, reparto y runbooks
```

---

## Documentación

| Documento | Contenido |
|---|---|
| [presentacion.html](src/api/static/presentacion.html) | **Presentación del informe final.** También accesible desde el botón de la interfaz o en `https://churn.juanitodev.com/presentacion.html` |
| [ARQUITECTURA.md](docs/ARQUITECTURA.md) | Decisiones de diseño y su justificación |
| [EVIDENCIAS.md](docs/EVIDENCIAS.md) | Salidas que respaldan cada requisito |
| [REPARTO.md](docs/REPARTO.md) | Qué construyó cada integrante |
| [EQUIPO.md](docs/EQUIPO.md) | Coordinación y preparación de la defensa |
| [runbooks/](docs/runbooks/) | Procedimientos reproducibles del VPS |
| [PROYECTO.md](docs/PROYECTO.md) | Enunciado original |

---

## Detalles que vale la pena mirar

**El preprocesamiento viaja dentro del modelo.** `src/features.py` define un
único `ColumnTransformer` que se serializa junto al clasificador en el
artefacto de MLflow. El servicio de inferencia nunca lo reimplementa, lo que
elimina el train/serve skew.

**Los umbrales de drift están justificados, no copiados.** El criterio
combina significancia estadística con tamaño del efecto: con n = 7.043, el
test KS rechaza la hipótesis nula ante diferencias sin relevancia práctica.
Exigir `D > 0.10` filtra ese ruido.

**Hay dos artefactos de drift, no uno.** `drift/check.py` es la puerta de
calidad —verde con datos limpios, roja con datos derivados—; `drift/tests/` es
la suite que verifica que la puerta funciona, y está siempre en verde.

**El retraso de etiquetas está resuelto como política.** En producción la
etiqueta real tarda ~30 días, así que el ROC-AUC por lote no es calculable en
tiempo real. Se vigila con tres proxies que no necesitan etiquetas.
