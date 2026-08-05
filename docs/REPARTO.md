# Reparto del trabajo

| # | Integrante | Componente | Ficheros principales |
|---|---|---|---|
| 1 | Cristhian B. | Modelo y MLflow | `data/telco_churn.csv`, `src/train.py`, `src/register.py` |
| 2 | Ronal Silvio Callisaya Merlo | API y contenedor | `src/features.py`, `src/api/`, `Dockerfile`, `requirements.txt` |
| 3 | Perseo Andrade | Kubernetes | `k8s/deployment.yaml`, `k8s/service.yaml`, runbooks 02, 03 y 05 |
| 4 | Erika Uriona y Ricardo Pari | Detección de drift | `drift/` completo, runbook 07 |
| 5 | Juanito Ortega | Infraestructura, TLS, UI y documentación | `infra/`, `src/api/static/`, `docs/`, runbooks 01 y 04 |

---

## Detalle por componente

**1 · Modelo y MLflow.** Selección y validación del dataset, pipeline de
entrenamiento reproducible con semilla fija, los 6 runs con distintos
hiperparámetros, registro de las dos versiones en el Model Registry y
promoción de la versión desplegada mediante el alias `champion`.

**2 · API y contenedor.** Esquema y preprocesamiento compartido entre
entrenamiento y servicio, contratos Pydantic de entrada y salida, servicio
FastAPI con carga del modelo desde el registry por alias, probes de
liveness y readiness, e imagen Docker multi-stage con usuario no-root.

**3 · Kubernetes.** Manifiestos de `Deployment` con tres réplicas y
`Service` de tipo NodePort, límites de recursos, inyección del nombre del pod
por Downward API y las cuatro demostraciones exigidas: réplicas simultáneas,
balanceo de carga, autorreparación y escalado.

**4 · Detección de drift.** Detectores estadísticos propios —Kolmogorov-Smirnov
para variables numéricas, PSI y Chi-cuadrado para categóricas—, generadores de
lotes con deriva controlada, puerta de calidad ejecutable, simulación de
concept drift, criterio de reentrenamiento y gráfica temporal de degradación.

**5 · Infraestructura, TLS, UI y documentación.** MLflow Server con backend
PostgreSQL en Docker Compose, cierre del puerto de tracking a internet,
terminación TLS con nginx y certbot sobre dos subdominios, interfaz web de
consumo de la API y documentación de arquitectura y evidencias.

---

## Defensa individual

El enunciado (§2) establece que la defensa es individual y cubre cualquier
parte del proyecto, no solo la que cada integrante construyó. El ejercicio de
defensa cruzada preparado para ello está descrito en [`EQUIPO.md`](EQUIPO.md),
sección 8.
