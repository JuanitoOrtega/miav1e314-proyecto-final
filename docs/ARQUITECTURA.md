# Arquitectura — telco-churn-mlops

Documento de arquitectura para la entrega. Recoge las decisiones tomadas y
**por qué**, que es lo que se defiende oralmente.

---

## 1. Visión general

Dos planos separados a propósito dentro del mismo VPS.

```
                             Internet
                                │  HTTPS :443
                                ▼
 ┌─────────────────────────────────────────────────────────────────────┐
 │                 VPS Ubuntu 24.04 — 4 vCore / 8 GB                   │
 │                                                                     │
 │  ENTRADA TLS · nginx en el host + certbot (Let's Encrypt)           │
 │  ┌───────────────────────────────────────────────────────────────┐  │
 │  │  :80 ─redirige─▶ :443                                         │  │
 │  │    mlflow.<dominio> ─proxy─▶ 127.0.0.1:5000                   │  │
 │  │    churn.<dominio>  ─proxy─▶ 127.0.0.1:30080                  │  │
 │  └───────┬───────────────────────────────────┬───────────────────┘  │
 │          │                                   │                      │
 │  PLANO DE MLOps (Docker Compose)             │                      │
 │  ┌───────▼───────────────┐   ┌──────────────┐│                      │
 │  │ MLflow Server :5000   │──▶│ PostgreSQL   ││                      │
 │  │ --serve-artifacts     │   │ :5432 interno││                      │
 │  └───────▲───────────────┘   └──────────────┘│                      │
 │          │ models:/telco-churn@champion      │                      │
 │  ════════╪═══════════════════════════════════╪═══════════════════   │
 │          │  PLANO DE SERVICIO (k3s)          ▼                      │
 │          │        ┌─────────────────────────────────────┐           │
 │          │        │ Service telco-churn-api  NodePort   │           │
 │          │        │ :30080                              │           │
 │          │        └────┬──────────┬──────────┬──────────┘           │
 │          │         ┌───▼───┐  ┌───▼───┐  ┌───▼───┐                  │
 │          └─────────┤ pod 1 │  │ pod 2 │  │ pod 3 │                  │
 │                    └───────┘  └───────┘  └───────┘                  │
 │                      FastAPI + modelo + UI estática                 │
 └─────────────────────────────────────────────────────────────────────┘
```

---

## 2. El modelo desplegado

| Campo | Valor |
|---|---|
| Nombre en el registro | `telco-churn` |
| Versión desplegada | **v2** (v4 en el ensayo local) |
| Alias | `champion` |
| Run de origen | `gb-lr0.05` — `f34cbea26eb14cddac50700ebfb2d45d` |
| Algoritmo | GradientBoostingClassifier, `learning_rate=0.05` |
| ROC-AUC en test | **0.8452** |
| Experimento | `telco-churn-experimento` |

> **Rellenar con los valores del VPS antes de entregar.** El `run_id` de esta
> tabla debe coincidir exactamente con el que devuelve
> `https://churn.<dominio>/model-info`.

---

## 3. Decisiones y su justificación

### 3.1 Por qué MLflow vive fuera del clúster

Meterlo en k3s exigiría `StatefulSet`, `PersistentVolumeClaim` y depuración de
almacenamiento: cerca de un día de trabajo que la rúbrica no califica.
Separarlo además hace la demostración **más honesta**, porque se ve que el
servicio *dentro* de Kubernetes consulta un Model Registry externo, que es el
patrón real de la industria.

### 3.2 Por qué el pod carga el modelo por alias y no horneado en la imagen

```python
mlflow.sklearn.load_model("models:/telco-churn@champion")
```

Cumple literalmente el §3.3.2 del enunciado: *"la versión que se despliega se
marca de forma explícita y el servicio la consume por esa referencia, no por
una ruta de archivo suelta"*. Promover un modelo nuevo se reduce a **mover el
alias y hacer `kubectl rollout restart`**, sin reconstruir la imagen.

*Alternativas descartadas:* hornear el modelo en la imagen (congela la
referencia dentro del artefacto y contradice el espíritu del requisito) e
init container que lo descarga a un volumen compartido (correcto, pero añade
una pieza que no da puntos y sí superficie que defender).

**Se usa `mlflow.sklearn.load_model` y no `pyfunc`** porque pyfunc no expone
`predict_proba`, y la API necesita la probabilidad, no solo la clase.

### 3.3 Por qué NO hay caché local del modelo (trade-off consciente)

Si MLflow está caído, un pod nuevo no arranca. Se mitiga con **reintentos con
backoff exponencial** más un `readinessProbe` que mantiene al pod fuera del
`Service` hasta que el modelo esté cargado: los pods sanos siguen atendiendo.

Se decidió **no** implementar caché local: añade una ruta de código con su
propia invalidación a cambio de resolver un fallo que en la demo no ocurrirá.

### 3.4 Por qué nginx en el host y no un Ingress

MLflow vive **fuera** del clúster, así que un Ingress solo cubriría la mitad
del sistema. nginx en el host es un único punto de entrada para ambos planos,
con la misma herramienta y el mismo certificado.

Consecuencia obligatoria: **k3s se instala con `--disable=traefik`**, porque
Traefik ocupa los puertos 80 y 443 y haría fallar el reto HTTP-01 de certbot
sin un diagnóstico obvio.

### 3.5 Por qué dos subdominios y no rutas de un mismo host

Servir MLflow bajo un subpath (`/mlflow`) es notoriamente problemático: la UI
genera URLs absolutas para sus recursos y termina exigiendo reescrituras
frágiles que se rompen entre versiones. Dos subdominios cuestan un registro
DNS más y eliminan la clase entera de problema.

### 3.6 Por qué ROC-AUC como métrica principal

El dataset tiene **26,5 % de positivos**: un clasificador que prediga siempre
"no abandona" alcanza 73,5 % de accuracy sin aprender nada. ROC-AUC es además
insensible al umbral de decisión, lo que permite comparar modelos sin fijar
antes una política de negocio. Se registran también F1 y recall porque el
costo de un falso negativo (cliente que se va sin ser detectado) supera al de
un falso positivo.

### 3.7 Por qué KS para numéricas y PSI/Chi² para categóricas

**KS** es no paramétrico y no asume normalidad. `MonthlyCharges` es claramente
**bimodal** (clientes con y sin internet), así que un t-test sería inválido:
compararía medias de una distribución que no tiene una sola moda. KS compara
las funciones de distribución acumulada completas.

**PSI** da una magnitud interpretable, no un sí/no, y es el estándar de la
industria para estabilidad de poblaciones categóricas. **Chi²** lo acompaña
aportando significancia estadística y **Cramér's V** el tamaño del efecto.

### 3.8 De dónde sale cada umbral

| Umbral | Valor | Origen |
|---|---|---|
| PSI | `> 0.25` alerta, `> 0.10` aviso | Escala convencional de las *scorecards* crediticias, donde nació el índice |
| p-valor | `< 0.05` | Nivel de significancia convencional |
| KS efecto | `D > 0.10` | Decisión propia, ver abajo |
| Cramér's V | `> 0.10` | Misma lógica |
| Caída de ROC-AUC | `> 0.05` absoluto, 3 lotes | Compromiso entre sensibilidad y estabilidad |

**Por qué se exige tamaño del efecto además del p-valor.** Con n = 7.043 el
test KS rechaza la hipótesis nula ante diferencias sin relevancia práctica: es
hipersensible al tamaño muestral. Exigir además un efecto mínimo separa
*estadísticamente significativo* de *prácticamente relevante*. Sin ese filtro
el monitor alertaría a diario y nadie le haría caso.

**Comparaciones múltiples.** La puerta corre 35 pruebas por lote (3 KS + 16
PSI + 16 Chi²), de las cuales 19 usan p-valor. Con α = 0.05 la probabilidad de
al menos un falso positivo por azar es ≈ 62 %. El filtro de tamaño del efecto
es también lo que controla ese problema.

### 3.9 Criterio de reentrenamiento

Se dispara la alarma cuando el ROC-AUC cae **más de 0,05 absolutos** respecto
al baseline **de forma sostenida durante 3 lotes consecutivos**. Los dos
ingredientes cumplen funciones distintas: la **magnitud** descarta caídas
irrelevantes, la **persistencia** descarta el ruido de un lote puntual. Un
reentrenamiento innecesario tiene coste real, así que la estabilidad del
criterio importa tanto como su sensibilidad.

### 3.10 Política de retraso de etiquetas

En producción la etiqueta de abandono no llega hasta ~30 días después de la
predicción, así que **el ROC-AUC por lote no es calculable en tiempo real**:
el monitoreo de §3.9 solo funciona en retrospectiva. Mientras las etiquetas
llegan se vigila con tres proxies que no las necesitan:

1. **Data drift de las variables de entrada** — indicador adelantado.
2. **Prediction drift** — KS sobre la distribución de *scores* del modelo.
3. **Tasa de positivos predichos** — si pasa del 26 % histórico al 40 %, algo
   cambió aunque nadie pueda confirmarlo todavía.

### 3.11 Dos artefactos de drift, no uno

La **puerta** (`drift/check.py`) es lo que el enunciado califica: sale en rojo
con datos derivados y en verde con datos del mismo origen. La **suite de
pytest** verifica que la puerta funciona, y por eso está **toda en verde** — un
test que se pusiera rojo ante datos derivados significaría que el detector no
detecta.

---

## 4. Trampas técnicas resueltas

Cada una costó tiempo de depuración y conviene tenerlas documentadas.

| Trampa | Síntoma | Solución |
|---|---|---|
| **MLflow atado a `127.0.0.1`** | Ningún pod arranca | Publicar en `0.0.0.0`: los pods llegan por la interfaz de flannel, no por loopback |
| **MLflow sin `--serve-artifacts`** | Los pods no descargan el modelo | Bandera activa desde el primer arranque |
| **`--allowed-hosts` de MLflow 3** | `403 Invalid Host header - possible DNS rebinding attack` | Listar los Host permitidos. **Las entradas literales deben incluir el puerto** (`localhost` NO acepta `localhost:5000`); los comodines sí lo absorben |
| **Traefik de k3s** | nginx no arranca, certbot falla sin diagnóstico | Instalar k3s con `--disable=traefik` |
| **`ufw` no cierra el puerto 5000** | El puerto sigue abierto a Internet | Regla en la cadena `DOCKER-USER`; Docker se salta ufw |
| **`python:3.11-slim` flotante** | El build rompe sin avisar | Fijar `python:3.11-slim-bookworm`: el tag saltó a Debian trixie y los repos cambiaron |
| **`kubectl port-forward` no balancea** | Las 10 peticiones salen del mismo pod | Demostrar el balanceo contra el NodePort o desde un pod cliente |
| **`FileStore` de MLflow** | Los alias fallan con `UnsupportedOperation` | Los tests del registro usan `sqlite:///`, no `file://` |

---

## 5. Seguridad — alcance y limitaciones declaradas

Proyecto académico de vida corta. Las siguientes decisiones se toman **a
conciencia**, no por descuido:

- **Todo el tráfico externo va cifrado por TLS**, con certificados de Let's
  Encrypt y redirección forzada de `:80` a `:443`.
- **MLflow queda tras autenticación básica de nginx** (`auth_basic`). Sin ella
  cualquiera con la URL podría ver los experimentos y, peor, **escribir** en el
  tracking server. En un entorno real iría detrás de SSO.
- **`ufw` permite únicamente 22, 80 y 443.** Los puertos 5000 y 30080 no se
  publican al exterior; se alcanzan solo por nginx o desde dentro del VPS.
- **PostgreSQL no se expone en absoluto**: solo es alcanzable desde la red
  interna de Docker. Sus credenciales viven en `infra/.env`, que no se commitea.
- **Se recomienda apagar los servicios tras la defensa.**

---

## 6. Fuera de alcance (y por qué)

Recortado deliberadamente por el plazo. Se enumera para poder responder *"sí,
lo consideramos, y esta fue la razón"*:

- **CI/CD con GitHub Actions** — valioso, pero no está en la rúbrica.
- **Ingress con cert-manager** — solo cubriría la mitad del sistema (§3.4).
- **Prometheus y Grafana** — la observabilidad exigida se cubre con las probes
  y el monitoreo de drift.
- **MLflow dentro de k3s** — justificado en §3.1.
- **Autoescalado (HPA)** — el enunciado pide escalado manual.
- **Reentrenamiento automático** — se define y documenta el *criterio*, que es
  lo que se pide; automatizar la ejecución no se solicita.
- **Caché local del modelo en el pod** — justificado en §3.3.
