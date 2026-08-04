# Diseño — `telco-churn-mlops`

**Fecha:** 2026-08-03
**Materia:** MOD14 — Maestría en Ciencia de Datos e Inteligencia Artificial
**Requisito fuente:** [`docs/PROYECTO.md`](../../PROYECTO.md)
**Modalidad:** grupo de 5 integrantes
**Plazo:** menos de 1 semana hasta la entrega y defensa

---

## 1. Objetivo

Llevar un modelo de clasificación binaria desde el entrenamiento hasta un despliegue
reproducible y observable en Kubernetes, con trazabilidad completa vía MLflow y detección
automatizada de data drift y concept drift.

El énfasis de la evaluación **no está en la exactitud del modelo** sino en la ingeniería
que lo rodea. Toda decisión de diseño en este documento prioriza lo que la rúbrica
califica y recorta agresivamente lo que no.

---

## 2. Decisiones cerradas

| Decisión | Elección | Motivo |
|---|---|---|
| Dataset | Telco Customer Churn (IBM) | Ya viene a nivel de entidad, con mezcla natural de variables numéricas y categóricas |
| Infraestructura | VPS Ubuntu 24.04 (4 vCore / 8 GB / 256 GB NVMe) | Recurso ya disponible del equipo |
| Kubernetes | k3s, un solo nodo | K8s ligero, adecuado para un nodo, instalación en un comando |
| MLflow | Docker Compose, **fuera** de k3s | Es infraestructura de soporte, no la carga desplegada |
| Exposición | Subdominios con HTTPS, vía nginx + certbot en el host | El equipo ya tiene dominio y sabe operar certbot; da una demo profesional y evita avisos del navegador |
| Entrada TLS | nginx en el host, **no** Traefik de k3s | Un único punto de entrada cubre los dos planos, incluido MLflow que vive fuera del clúster |
| Distribución de imagen | `docker build` en el VPS + `k3s ctr images import` | Cero infraestructura adicional, cero credenciales |
| Detección de drift | Implementación propia con `scipy` + `pytest` | La rúbrica pide justificar cada prueba y cada umbral; una librería opaca no se puede defender |
| UI extra | HTML + JavaScript servido por la propia API | Elimina un Dockerfile, un manifest y el problema de CORS (mismo origen) |
| Modo de trabajo en el VPS | El equipo ejecuta, guiado por runbooks versionados | Cada integrante toca el servidor con sus manos; la defensa es individual |

---

## 3. Arquitectura

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
 │  │    mlflow.juanitodev.com ─proxy─▶ 127.0.0.1:5000              │  │
 │  │    churn.juanitodev.com  ─proxy─▶ 127.0.0.1:30080             │  │
 │  └───────┬───────────────────────────────────┬───────────────────┘  │
 │          │                                   │                      │
 │  PLANO DE MLOps (Docker Compose)             │                      │
 │  ┌───────▼───────────────┐   ┌──────────────┐│                      │
 │  │ MLflow Server :5000   │──▶│ PostgreSQL   ││                      │
 │  │ --serve-artifacts     │   │ :5432 interno││                      │
 │  │ vol /mlflow/artifacts │   └──────────────┘│                      │
 │  └───────▲───────────────┘                   │                      │
 │          │ models:/telco-churn@champion      │                      │
 │          │ (cada pod descarga al arrancar)   │                      │
 │  ════════╪═══════════════════════════════════╪═══════════════════   │
 │          │  PLANO DE SERVICIO (k3s)          │                      │
 │          │                                   ▼                      │
 │          │        ┌─────────────────────────────────────┐           │
 │          │        │ Service telco-churn-api             │           │
 │          │        │ NodePort :30080                     │           │
 │          │        └────┬──────────┬──────────┬──────────┘           │
 │          │             │          │          │                      │
 │          │         ┌───▼───┐  ┌───▼───┐  ┌───▼───┐                  │
 │          └─────────┤ pod 1 │  │ pod 2 │  │ pod 3 │                  │
 │                    └───────┘  └───────┘  └───────┘                  │
 │                      FastAPI + modelo + UI estática                 │
 │                                                                     │
 └─────────────────────────────────────────────────────────────────────┘
```

### Por qué MLflow queda fuera del clúster

Meter MLflow en k3s exige `StatefulSet`, `PersistentVolumeClaim` y depuración de
almacenamiento: cerca de un día de trabajo que la rúbrica no califica. Separarlo además
hace la demostración más honesta, porque el docente ve que el servicio *dentro de
Kubernetes* consulta un Model Registry externo, que es el patrón real de la industria.

### Puertos

| Puerto | Servicio | Expuesto a Internet |
|---|---|---|
| 443 | nginx (TLS) | **Sí** — única puerta de entrada |
| 80 | nginx (redirección a 443 + reto ACME de certbot) | **Sí** |
| 5000 | MLflow UI y API de tracking | No — solo `127.0.0.1`, se alcanza vía nginx |
| 30080 | API de inferencia + UI web | No — solo `127.0.0.1`, se alcanza vía nginx |
| 5432 | PostgreSQL | No — solo red interna de Docker |

### 3.1 Exposición pública con TLS

**Subdominios.** Dos registros `A` apuntando a la IP del VPS:

| Subdominio | Destino | Contenido |
|---|---|---|
| `mlflow.juanitodev.com` | `127.0.0.1:5000` | UI de MLflow y API de tracking |
| `churn.juanitodev.com` | `127.0.0.1:30080` | API de inferencia y UI web |

El dominio concreto se fija una sola vez en `infra/.env` (variable `DOMAIN_BASE`) y las
plantillas de nginx lo consumen desde ahí, para que ninguna configuración lleve el dominio
escrito a mano en varios sitios.

**Por qué dos subdominios y no rutas de un mismo host.** Servir MLflow bajo un subpath
(`/mlflow`) es notoriamente problemático: la UI genera URLs absolutas para sus recursos
estáticos y llamadas a su API, y termina exigiendo reescrituras frágiles que se rompen
entre versiones. Dos subdominios cuestan un registro DNS más y eliminan la clase entera de
problema.

**Por qué nginx en el host y no el Ingress de Traefik de k3s.** MLflow vive **fuera** del
clúster (§3), así que un Ingress de Kubernetes no lo cubriría sin inventar un `Service` de
tipo `ExternalName` apuntando de vuelta al host — una pieza rara de explicar en la defensa.
nginx en el host es un único punto de entrada que cubre los dos planos con la misma
herramienta y el mismo certificado, y certbot es la herramienta que el equipo ya sabe
operar.

**Conflicto de puertos que hay que resolver antes de instalar nada.** k3s incluye Traefik y
**por defecto ocupa los puertos 80 y 443 del host**. Si se instala así, nginx no puede
arrancar y —peor— el reto HTTP-01 de certbot falla sin un diagnóstico obvio. Por eso k3s se
instala con:

```bash
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable=traefik" sh -
```

No se pierde nada, porque la exposición se hace por NodePort más nginx. Esta decisión se
toma en el runbook `02`, **antes** de que ningún otro paso dependa de ella.

**Certificados.** Se emiten con `certbot --nginx` para ambos subdominios en una sola
invocación. La renovación automática viene con el `systemd timer` que instala el paquete;
se verifica con `certbot renew --dry-run` y la salida se guarda como evidencia.

**Consecuencia para el resto del diseño.** La UI web y todas las demostraciones apuntan a
`https://churn.juanitodev.com` en lugar de a `http://<IP>:30080`. El acceso directo por IP y
NodePort sigue funcionando desde dentro del VPS y se conserva a propósito: es el camino que
se usa en los runbooks de Kubernetes para probar el balanceo sin que nginx interfiera.

### 3.2 Dos caminos hacia MLflow, y por qué no puede haber uno solo

Este punto es sutil y hay que tenerlo claro antes de escribir el `docker-compose.yml`,
porque la solución "obvia" rompe el clúster.

| Quién | Camino | Protocolo |
|---|---|---|
| Personas (navegador) | `https://mlflow.juanitodev.com` → nginx → `127.0.0.1:5000` | HTTPS + auth básica |
| Pods de k3s | `http://<IP_INTERNA_NODO>:5000` directo | HTTP, tráfico que nunca sale del VPS |

**Por qué los pods no pueden usar `127.0.0.1`.** Es el error clásico: publicar MLflow como
`127.0.0.1:5000:5000` en Docker Compose parece lo más seguro, pero entonces **los pods de
k3s no lo alcanzan**. El tráfico de un pod hacia el host llega por la interfaz de red de
flannel (`cni0`), no por loopback, así que un servicio atado a `127.0.0.1` es invisible
desde el clúster y todos los pods quedan atascados sin poder cargar el modelo.

**Por qué los pods tampoco usan el subdominio HTTPS.** Sería un único camino más elegante,
pero obliga al tráfico a salir a Internet y volver (*hairpin NAT*), que falla en algunos
proveedores, y además exigiría inyectar las credenciales de la auth básica en un `Secret`.
Complejidad y un modo de fallo nuevo a cambio de elegancia. No compensa con este plazo.

**Cómo se cierra el puerto de verdad.** MLflow se publica en `0.0.0.0:5000` para que los
pods lo alcancen, y el acceso público se bloquea a nivel de firewall. Aquí aparece la
segunda trampa: **Docker inserta sus propias reglas de iptables y las publicaciones de
puertos se saltan `ufw` por completo**. Un `ufw deny 5000` da falsa sensación de seguridad
mientras el puerto sigue abierto a Internet. La solución correcta es una regla explícita en
la cadena `DOCKER-USER`, que sí se evalúa antes:

```bash
# Permitir solo pods de k3s (10.42.0.0/16) y el propio host; descartar el resto
iptables -I DOCKER-USER -p tcp --dport 5000 -s 10.42.0.0/16 -j RETURN
iptables -I DOCKER-USER -p tcp --dport 5000 -s 127.0.0.1     -j RETURN
iptables -A DOCKER-USER -p tcp --dport 5000                  -j DROP
```

Se persiste con `iptables-persistent` y **se verifica desde fuera del VPS** con
`nc -zv <IP_PUBLICA> 5000`, que debe fallar. Esa verificación va a `EVIDENCIAS.md`: es la
diferencia entre creer que el puerto está cerrado y haberlo comprobado.

---

## 4. Decisión arquitectónica central: cómo obtiene el modelo el servicio

Es la única decisión con un trade-off real y la que con más probabilidad será atacada en
la defensa.

**Opción elegida: el pod carga el modelo desde el Model Registry al arrancar, por alias.**

```python
mlflow.pyfunc.load_model("models:/telco-churn@champion")
```

Cumple literalmente el requisito §3.3.2 del enunciado: *"la versión que se despliega se
marca de forma explícita (alias o stage) y el servicio la consume por esa referencia, no
por una ruta de archivo suelta"*. Promover un modelo nuevo a producción se reduce a mover
el alias y ejecutar `kubectl rollout restart`, sin reconstruir la imagen.

**Alternativas descartadas:**

- *Modelo horneado en la imagen durante `docker build`.* Los pods arrancarían sin
  dependencia externa, pero congela la referencia dentro del artefacto y contradice el
  espíritu del requisito.
- *Init container que descarga a un volumen compartido.* Correcto, pero añade una pieza
  que no aporta puntos y sí superficie que defender.

**Riesgo asumido y su mitigación.** Si MLflow está caído, un pod nuevo no puede arrancar.
Se mitiga con reintentos con backoff exponencial en el arranque más un `readinessProbe`
que mantiene al pod fuera del `Service` hasta que el modelo esté cargado: los pods sanos
siguen atendiendo mientras tanto. **Se decide explícitamente NO implementar caché local
del modelo** — añade una ruta de código con su propia invalidación a cambio de resolver
un fallo que en la demo no ocurrirá. El trade-off queda documentado en `ARQUITECTURA.md`
para poder responderlo en la defensa.

---

## 5. Estructura del repositorio

```
proyecto-final/
├── data/
│   ├── telco_churn.csv              7.043 filas × 21 columnas (~955 KB, versionado)
│   └── batches/                     Lotes 0..5 generados por drift/generators.py
├── src/
│   ├── features.py                  Pipeline sklearn COMPARTIDO train ↔ serve
│   ├── train.py                     6 runs con tracking en MLflow
│   ├── register.py                  Registro de versiones + alias @champion
│   └── api/
│       ├── main.py                  FastAPI: /health /ready /model-info /predict
│       ├── schemas.py               Contrato Pydantic de entrada y salida
│       └── static/
│           ├── index.html           UI web
│           └── app.js               fetch() → POST /predict (mismo origen)
├── drift/
│   ├── detectors.py                 KS, PSI, Chi², Cramér's V
│   ├── generators.py                Inyección controlada de data y concept drift
│   ├── check.py                     PUERTA de drift (CLI): exit 0 = verde, exit 1 = rojo
│   ├── monitor.py                   Ejecuta lotes sucesivos → gráfica temporal
│   └── tests/
│       └── test_drift.py            pytest que verifica que la puerta se comporta bien
├── k8s/
│   ├── deployment.yaml              3 réplicas, probes, límites de recursos
│   └── service.yaml                 NodePort 30080
├── infra/
│   ├── docker-compose.yml           MLflow Server + PostgreSQL
│   ├── .env.example                 DOMAIN_BASE y credenciales (el .env real no se commitea)
│   └── nginx/
│       ├── mlflow.conf.template     vhost de mlflow.juanitodev.com
│       └── churn.conf.template        vhost de churn.juanitodev.com
├── docs/
│   ├── PROYECTO.md                  Enunciado original (ya existe)
│   ├── ARQUITECTURA.md              Documento de arquitectura para la entrega
│   ├── EVIDENCIAS.md                Capturas y salidas de terminal de las 4 demos
│   ├── REPARTO.md                   Tabla de quién construyó qué
│   ├── evidencias/                  Imágenes y capturas referenciadas por EVIDENCIAS.md
│   ├── runbooks/                    Comandos paso a paso, ejecutables por el equipo
│   │   ├── 01-bootstrap-vps.md          Docker, MLflow + PostgreSQL, firewall
│   │   ├── 02-instalar-k3s.md           k3s con --disable=traefik y verificación de red
│   │   ├── 03-build-y-deploy.md         docker build → ctr import → kubectl apply
│   │   ├── 04-tls-y-subdominios.md      DNS, nginx y certbot para los dos subdominios
│   │   ├── 05-demos-kubernetes.md       Las 4 demostraciones exigidas
│   │   ├── 06-demo-mlflow.md            Guion de la demo en vivo de la UI de MLflow
│   │   └── 07-demo-drift.md             Ejecución de la puerta de drift en verde y rojo
│   └── superpowers/specs/           Este documento
├── Dockerfile
├── requirements.txt                 Todo fijado con ==, incluido mlflow
└── .gitignore
```

### `features.py` — la pieza que evita el train/serve skew

El `ColumnTransformer` de preprocesamiento se define una sola vez y **se serializa dentro
del modelo MLflow** como parte de un `sklearn.Pipeline`. La API nunca reimplementa la
transformación: recibe el registro crudo y llama a `predict`. Cuando en la defensa
pregunten cómo se garantiza que el preprocesamiento en producción es idéntico al del
entrenamiento, esa es la respuesta, y es verificable abriendo el artefacto en MLflow.

---

## 6. Fase 1 — Modelo, experimentación y trazabilidad

### 6.1 Datos

**Fuente:** IBM Telco Customer Churn, CSV público y estable.
Se descarga una vez y **se versiona en el repositorio** (~955 KB) para que el
entrenamiento sea reproducible sin dependencia de red ni de credenciales.

- **7.043 registros**, 21 columnas.
- **Objetivo:** `Churn` (Yes/No). Tasa de positivos ≈ **26,5 %** → desbalanceado.
- **`customerID`** se descarta (identificador, sin poder predictivo).
- **19 variables de entrada**, de las cuales:
  - **3 numéricas:** `tenure`, `MonthlyCharges`, `TotalCharges`
  - **16 categóricas:** `gender`, `SeniorCitizen`, `Partner`, `Dependents`,
    `PhoneService`, `MultipleLines`, `InternetService`, `OnlineSecurity`,
    `OnlineBackup`, `DeviceProtection`, `TechSupport`, `StreamingTV`,
    `StreamingMovies`, `Contract`, `PaperlessBilling`, `PaymentMethod`

**Problema de calidad conocido y su tratamiento.** `TotalCharges` viene tipada como texto
y contiene 11 cadenas vacías, correspondientes a clientes con `tenure = 0` (nunca
facturados). Se convierte a numérico con coerción y esas 11 filas se imputan con `0`, que
es el valor semánticamente correcto. La decisión queda documentada porque es exactamente
el tipo de detalle que se pregunta en una defensa.

`SeniorCitizen` viene como entero 0/1 pero es conceptualmente categórica y se trata como
tal.

### 6.2 Entrenamiento reproducible

- `random_state = 42` fijado en el split y en todos los modelos.
- **Split estratificado 80/20** sobre `Churn`, documentado en `ARQUITECTURA.md`.
- El conjunto de test se reserva además como fuente de los lotes de drift de la Fase 4.

### 6.3 Los 6 runs

Se ejecutan **6 runs** (el mínimo exigido es 5), comparables entre sí porque comparten
split, semilla y conjunto de métricas registradas:

| Run | Modelo | Hiperparámetros variados |
|---|---|---|
| 1 | LogisticRegression | `C=0.1` |
| 2 | LogisticRegression | `C=1.0` |
| 3 | RandomForest | `n_estimators=100, max_depth=5` |
| 4 | RandomForest | `n_estimators=300, max_depth=10` |
| 5 | GradientBoosting | `learning_rate=0.05` |
| 6 | GradientBoosting | `learning_rate=0.2` |

Cada run registra en MLflow: parámetros, métricas, el modelo como artefacto con su
*signature* e *input example*, y la matriz de confusión como imagen.

### 6.4 Métrica principal

**ROC-AUC.** Justificación: con un 26,5 % de positivos, la exactitud es engañosa — un
clasificador que prediga siempre "no churn" alcanza 73,5 % de accuracy sin aprender nada.
ROC-AUC es además insensible al umbral de decisión, lo que permite comparar modelos sin
fijar antes una política de negocio. Se registran también F1 y recall de la clase
positiva, porque en un caso de abandono el costo de un falso negativo (cliente que se va
sin ser detectado) supera al de un falso positivo.

### 6.5 Model Registry

- Nombre estable del modelo registrado: **`telco-churn`**.
- Se registran **dos versiones** para evidenciar comprensión del versionado:
  - **v1** — el mejor modelo lineal (LogisticRegression), como línea base.
  - **v2** — el ganador por ROC-AUC entre los 6 runs.
- El alias **`@champion`** apunta a **v2**, y es la referencia que consume el servicio.
- `ARQUITECTURA.md` deja constancia de qué versión del registro está desplegada y a qué
  `run_id` corresponde.

### 6.6 Preparación para la demo en vivo de la UI de MLflow

El enunciado (§3.4) exige poder hacer cuatro cosas frente al docente. El runbook
`docs/runbooks/06-demo-mlflow.md` las deja ensayadas paso a paso:

1. Abrir el experimento y explicar qué representa cada run.
2. Ordenar y filtrar los runs por ROC-AUC.
3. Seleccionar varios runs y usar la vista de comparación para argumentar la elección.
4. Abrir el Model Registry y mostrar la versión que corresponde al servicio en producción.

### 6.7 Nota técnica: `--serve-artifacts`

El servidor MLflow debe arrancar con `--serve-artifacts`. Sin esa bandera, el
`artifact_uri` apuntaría a una ruta del sistema de archivos del servidor y los pods de
k3s **no podrían descargar el modelo**, porque esa ruta no existe dentro del contenedor
de la API. Con la bandera activa, MLflow actúa como proxy de artefactos y los clientes
los obtienen por HTTP. Es una trampa clásica y conviene tenerla resuelta desde el día 1.

---

## 7. Fase 2 — Contenerización

- **Dockerfile propio** (el enunciado prohíbe usar únicamente una imagen prearmada de
  terceros), basado en `python:3.11-slim`.
- **Multi-stage build:** etapa de construcción para compilar dependencias, etapa final
  solo con lo necesario en tiempo de ejecución.
- **Usuario no-root** (`appuser`) — buena práctica y punto fácil a favor en la defensa.
- **`HEALTHCHECK`** declarado en la imagen.
- **`requirements.txt` con todas las versiones fijadas mediante `==`, incluida la de
  MLflow**, como exige el enunciado. Las versiones exactas se congelan con `pip freeze`
  durante la implementación. Restricción: MLflow **≥ 2.9**, porque los alias del Model
  Registry (`models:/nombre@alias`) no existen antes de esa versión.
- **Etiquetado explícito de la imagen:** `telco-churn-api:v1`. Nunca `latest`, porque
  demostrar un rollout de Kubernetes exige cambiar el tag.
- El contenedor levanta el servicio y responde inferencias **sin pasos manuales
  adicionales**.

---

## 8. Fase 3 — Kubernetes

### 8.1 Manifiestos

**`deployment.yaml`**
- `replicas: 3`
- `resources`: requests `256Mi` / `100m`, limits `512Mi` / `500m`.
  Tres réplicas consumen como máximo ~1,5 GB de los 8 GB del VPS.
- `livenessProbe` → `GET /health` (responde 200 si el proceso está vivo).
- `readinessProbe` → `GET /ready` (responde 200 **solo** si el modelo está cargado).
- `imagePullPolicy: IfNotPresent`, obligatorio porque la imagen se importa localmente a
  k3s y no existe en ningún registry remoto.
- Variable `POD_NAME` inyectada mediante **Downward API**.

**`service.yaml`**
- `type: NodePort`, puerto `30080`.

### 8.2 El mecanismo que hace demostrable el balanceo

Cada pod recibe su propio nombre en la variable de entorno `POD_NAME` vía Downward API y
lo devuelve en el campo `served_by` de **cada** respuesta de `/predict`. Un bucle de diez
`curl` muestra nombres de pod distintos: el balanceo queda demostrado en una sola línea de
terminal, y también es visible desde la UI web.

### 8.3 Las 4 demostraciones exigidas

Cada una queda como script reproducible en `docs/runbooks/`, con su salida capturada en
`EVIDENCIAS.md`. Pueden ser solicitadas en vivo durante la defensa.

| # | Demostración | Comando | Evidencia esperada |
|---|---|---|---|
| 1 | 3+ réplicas en Running simultáneo | `kubectl get pods -o wide` | Tres pods `Running`, `READY 1/1` |
| 2 | Tráfico distribuido entre réplicas | Bucle de 10 `curl` a `/predict` | El campo `served_by` alterna entre pods |
| 3 | Autorreparación | `kubectl delete pod <X>` mientras corre un bucle de curl | Kubernetes recrea el pod y **ninguna petición falla** |
| 4 | Escalado | `kubectl scale deploy --replicas=5` y luego `=2` | Cambio visible en `get pods` y en los `served_by` |

La demostración 3 se ejecuta con un bucle de peticiones **en paralelo** al borrado; que el
servicio no deje de responder es justamente lo que se está probando, y hacerlo en dos
terminales lado a lado es visualmente contundente.

---

## 9. Fase 4 — Detección de drift

### 9.1 Construcción de los lotes

Del conjunto de test reservado se derivan **6 lotes de ~500 registros**:

- **Lote 0** — muestra limpia del mismo origen que el entrenamiento. Es el control: aquí
  todo debe salir **verde**.
- **Lotes 1 a 5** — deriva inyectada de forma creciente y controlada.

El baseline de referencia es siempre el conjunto de **entrenamiento**.

### 9.2 Data drift

Una prueba estadística **por tipo de variable**, como exige el enunciado, y en ambos casos
el criterio combina significancia con tamaño del efecto:

**Variables numéricas** (`tenure`, `MonthlyCharges`, `TotalCharges`) → **Kolmogorov-Smirnov**

*Por qué esta prueba:* es no paramétrica y no asume normalidad. `MonthlyCharges` tiene una
distribución claramente bimodal (clientes con y sin servicio de internet), así que
cualquier prueba que asuma normalidad — como un t-test — sería inválida. KS compara las
funciones de distribución acumulada completas, no solo la media.

*Umbral de alerta:* `p < 0.05` **y** `D > 0.10`.

**Variables categóricas** (`Contract`, `PaymentMethod`, `InternetService`, …) →
**PSI** (índice de estabilidad poblacional) y **Chi-cuadrado**

*Por qué:* PSI es la métrica estándar para estabilidad de poblaciones categóricas y da una
magnitud interpretable, no solo un sí/no. Chi² lo acompaña aportando significancia
estadística, y **Cramér's V** aporta el tamaño del efecto.

*Umbral de alerta:* `PSI > 0.25`.

### 9.3 De dónde salen los umbrales

El enunciado pide explícitamente explicar el origen de cada número.

- **PSI.** Escala convencional de las *scorecards* crediticias, donde el índice se originó:
  `< 0.10` población estable, `0.10 – 0.25` cambio moderado que amerita vigilancia,
  `> 0.25` cambio significativo que exige acción. Se adopta `0.25` como umbral de alerta
  roja y `0.10` como umbral de advertencia.
- **`p < 0.05`.** Nivel de significancia convencional.
- **`D > 0.10` (el criterio que de verdad importa).** Con n = 7.043, el test KS rechaza la
  hipótesis nula ante diferencias irrelevantes en la práctica: es hipersensible al tamaño
  muestral. Exigir además un tamaño del efecto mínimo filtra ese ruido y evita un
  monitor que grita todos los días. Este razonamiento —significancia estadística no es lo
  mismo que relevancia práctica— es el argumento más fuerte del proyecto en la Fase 4.

**Fórmula del PSI implementada:**

```
PSI = Σ (pct_actual − pct_esperado) × ln(pct_actual / pct_esperado)
```

Para variables numéricas los bins se derivan de **10 cuantiles del baseline**. Se suma un
`ε = 1e-6` a las proporciones para evitar división por cero cuando una categoría no
aparece en un lote.

### 9.4 Concept drift

*Definición operativa:* cambia la relación entre las entradas y el objetivo. Las entradas
pueden verse idénticas y aun así el modelo empieza a equivocarse.

**Simulación.** Se invierte la etiqueta de los clientes con `Contract == 'Two year'` en una
proporción creciente a lo largo de los lotes sucesivos (10 %, 20 %, 30 %, 40 %, 50 %). Es
un escenario con historia de negocio creíble: un cambio de política de permanencia hace
que los contratos largos dejen de proteger contra el abandono. Las distribuciones de
entrada permanecen intactas, que es precisamente lo que distingue el concept drift del
data drift.

**Medición.** Se calcula ROC-AUC sobre cada lote y se grafica contra el índice de lote.
La gráfica temporal se guarda como `docs/evidencias/concept_drift.png` y se registra
también como artefacto en MLflow.

**Criterio de reentrenamiento.** Se dispara la alarma cuando el ROC-AUC cae **más de 0,05
en términos absolutos** respecto al baseline **de forma sostenida durante 3 lotes
consecutivos**. La condición de persistencia existe para no reentrenar por un lote
ruidoso; el costo de un reentrenamiento innecesario es real y la estabilidad del criterio
importa tanto como su sensibilidad.

**Retraso de etiquetas** (§6.2 lo exige explícitamente). En producción la etiqueta de
abandono no llega hasta ~30 días después de la predicción, así que el ROC-AUC por lote
**no es calculable en tiempo real** — el monitoreo descrito arriba sólo funciona en
retrospectiva. Mientras las etiquetas llegan, se vigila con tres proxies que no las
necesitan:

1. **Data drift de las variables de entrada** (§9.2), que es un indicador adelantado.
2. **Prediction drift:** deriva en la distribución de los *scores* que emite el modelo.
   Se aplica KS entre los scores del lote y los del baseline.
3. **Tasa de positivos predichos:** si el modelo empieza a predecir 40 % de abandono
   donde históricamente predecía 26 %, algo cambió aunque nadie pueda confirmarlo todavía.

Esto se documenta como política operativa en `ARQUITECTURA.md`, no como un comentario en
el código.

### 9.5 Dos artefactos distintos: la puerta y la suite

Aquí hay una ambigüedad del enunciado que conviene resolver de forma explícita, porque de
lo contrario genera una discusión incómoda en la defensa. El enunciado dice que *"la prueba
debe fallar (estado rojo) cuando el equipo inyecte deliberadamente datos derivados, y pasar
(estado verde) con datos del mismo origen"*. Eso describe una **puerta de calidad**, no una
suite de tests unitarios: si un test de `pytest` que verifica *"el detector detecta"* se
pusiera en rojo ante datos derivados, significaría que el detector **no** funciona.

Por eso se construyen **dos artefactos separados**, y ambos se muestran en la defensa:

**a) La puerta de drift — `drift/check.py`**

Es lo que el enunciado califica. Un CLI que recibe un lote y lo evalúa contra el baseline:

```bash
python -m drift.check --batch data/batches/lote_0.csv   # → exit 0  ✅ VERDE
python -m drift.check --batch data/batches/lote_3.csv   # → exit 1  ❌ ROJO
```

Imprime una tabla por variable con su estadístico, su umbral y su veredicto, y termina con
código de salida distinto de cero si alguna variable supera el umbral. Verde con datos del
mismo origen, rojo con datos derivados: exactamente el comportamiento exigido, y visible en
una sola línea de terminal.

**b) La suite de pytest — `drift/tests/test_drift.py`**

Verifica que la puerta se comporta como debe. **Todos sus tests están en verde cuando la
implementación es correcta**, incluidos los que comprueban la detección de deriva:

| Test | Qué verifica |
|---|---|
| `test_psi_formula_valores_conocidos` | El PSI implementado coincide con un valor calculado a mano |
| `test_ks_formula_distribuciones_identicas` | KS de una distribución contra sí misma no alerta |
| `test_puerta_verde_en_lote_limpio` | `check.py` devuelve exit 0 sobre el lote 0 |
| `test_puerta_roja_por_desplazamiento_numerico` | `check.py` devuelve exit 1 con `MonthlyCharges` desplazado |
| `test_puerta_roja_por_cambio_categorico` | `check.py` devuelve exit 1 con el mix de `Contract` alterado |
| `test_concept_drift_dispara_criterio` | Tres lotes consecutivos bajo el umbral activan la alarma |
| `test_criterio_no_dispara_por_lote_aislado` | Un solo lote malo **no** dispara la alarma (verifica la persistencia) |

Los dos tests de fórmula son deliberados: demuestran que el equipo entiende la matemática y
no solo que supo llamar a una función de librería.

**Cómo se presenta en la defensa:** primero se corre `pytest drift/` y sale todo verde
(*"nuestros detectores funcionan y está probado"*), y luego se corre la puerta sobre un lote
limpio y sobre uno derivado, mostrando verde y rojo (*"y así es como se comporta ante datos
reales"*). Las dos cosas juntas responden el requisito sin ambigüedad.

---

## 10. Puntos extra — API y UI

### 10.1 Contrato de la API

| Endpoint | Método | Propósito |
|---|---|---|
| `/health` | GET | Liveness. 200 si el proceso vive. |
| `/ready` | GET | Readiness. 200 solo si el modelo está cargado. |
| `/model-info` | GET | `model_name`, `version`, `run_id`, `alias`, `loaded_at` |
| `/predict` | POST | Inferencia. Devuelve `prediction`, `probability`, `served_by`, `model_version` |
| `/` | GET | Sirve la UI estática |

`/model-info` es la pieza de trazabilidad: durante la defensa se abre ese endpoint junto a
la UI de MLflow y se demuestra que el `run_id` que sirve peticiones es exactamente el del
experimento que lo produjo. Ese es el vínculo que el enunciado (§3.3) exige.

La validación de entrada es un modelo **Pydantic** con las 19 variables tipadas, lo que
produce errores 422 legibles ante entradas inválidas.

### 10.2 UI web

Un `index.html` más un `app.js` servidos por FastAPI mediante `StaticFiles`, dentro del
mismo contenedor y por tanto del mismo `Service` de Kubernetes.

- **Mismo origen ⇒ no hace falta CORS.** Es la razón principal de esta elección.
- Formulario con las 19 variables (valores por defecto sensatos para no tener que
  rellenarlo entero en la demo).
- Muestra la probabilidad de abandono y, de forma destacada, el `served_by`: al pulsar
  varias veces el nombre del pod cambia, **lo que convierte la propia UI en una
  demostración visual del balanceo de carga**.

Esto satisface el requisito de que el consumo de la API sea real y funcione contra el
servicio desplegado en Kubernetes, no contra un proceso local: el navegador ataca
`https://churn.juanitodev.com`, que nginx enruta al NodePort del `Service` de Kubernetes.

---

## 11. Reparto entre los 5 integrantes

| # | Rol | Componentes | Entregable verificable |
|---|---|---|---|
| 1 | Modelo y MLflow | `src/features.py`, `src/train.py`, `src/register.py`, runbook `06` | 6 runs, 2 versiones registradas, alias `@champion` |
| 2 | Contenedor y API | `src/api/`, `Dockerfile`, `requirements.txt` | Imagen que levanta y responde sin pasos manuales |
| 3 | Kubernetes | `k8s/`, runbooks `02`, `03`, `05` | Las 4 demostraciones con evidencia capturada |
| 4 | Drift | `drift/` completo, runbook `07` | Puerta en verde y rojo, suite en verde, gráfica temporal |
| 5 | Infraestructura, TLS, UI y documentación | `infra/`, `src/api/static/`, runbooks `01` y `04`, `docs/` | MLflow operativo, HTTPS en ambos subdominios, UI funcional, `ARQUITECTURA.md` |

Cada integrante trabaja en su propia rama y commitea con su autoría de git, de modo que el
historial constituya la evidencia del reparto declarado, que es lo que el enunciado dice
que se revisará.

**Advertencia sobre §2 del enunciado: la defensa es individual y cubre cualquier parte del
proyecto, no solo la que cada quien construyó.** Por eso el día 6 se reserva íntegro para
que los cinco recorran el sistema completo y se hagan preguntas cruzadas.

---

## 12. Calendario (6 días)

| Día | Camino crítico | Paralelo |
|---|---|---|
| **1** | **#5** crea los registros DNS, levanta MLflow + PostgreSQL y k3s (`--disable=traefik`). **#1** prepara los datos y el baseline. | **#2** monta FastAPI contra un modelo dummy. **#4** define el contrato del baseline. |
| **2** | **#1** ejecuta los 6 runs, registra v1 y v2, fija el alias. **#2** conecta la API al registry real. | **#3** escribe los manifiestos de Kubernetes. |
| **3** | **Despliegue end-to-end real.** **#3** ejecuta y captura las 4 demostraciones. **#5** monta nginx + certbot y deja los dos subdominios en HTTPS. | **#4** implementa los detectores y los tests. |
| **4** | **#4** cierra la gráfica temporal y el criterio de reentrenamiento. | **#5** implementa la UI HTML+JS. |
| **5** | `ARQUITECTURA.md`, `EVIDENCIAS.md`, `REPARTO.md`, archivo comprimido de entrega. | Revisión cruzada de código. |
| **6** | Colchón y ensayo de defensa cruzada. | — |

### Riesgo principal y su mitigación

El integrante #2 depende del modelo del integrante #1, lo que serializaría dos días de
trabajo. **Se rompe la dependencia registrando en MLflow un modelo dummy el día 1**: un
`sklearn.DummyClassifier` entrenado sobre el esquema real y publicado bajo el alias
`@champion`. Así la API se desarrolla desde el primer día contra un contrato real y no
contra un `None`, y sustituirlo por el modelo bueno el día 2 no cambia una sola línea del
servicio.

### Riesgos secundarios

| Riesgo | Mitigación |
|---|---|
| Los pods de k3s no alcanzan MLflow en el host | MLflow se publica en `0.0.0.0`, no en `127.0.0.1` (§3.2). Se valida el día 1 con un `curl` desde un pod de prueba. |
| MLflow arranca sin `--serve-artifacts` y los pods no descargan el modelo | Bandera incluida desde el primer arranque (§6.7). |
| Traefik de k3s ocupa los puertos 80 y 443 y certbot falla sin diagnóstico claro | k3s se instala con `--disable=traefik` desde el principio (§3.1). |
| `ufw` no cierra el puerto 5000 porque Docker se lo salta | Regla explícita en la cadena `DOCKER-USER`, verificada desde fuera del VPS (§3.2). |
| El DNS de los subdominios no ha propagado cuando se ejecuta certbot | Los registros `A` se crean el **día 1**, aunque el TLS se configure el día 3. |

---

## 13. Seguridad — alcance y limitaciones declaradas

Este es un proyecto académico con vida corta y las siguientes decisiones se toman a
conciencia, no por descuido. Se documentan en `ARQUITECTURA.md` para poder responderlas si
surgen en la defensa:

- **Todo el tráfico externo va cifrado por TLS** (§3.1), con certificados de Let's Encrypt
  y redirección forzada de `:80` a `:443`.
- **MLflow queda accesible en `mlflow.juanitodev.com` sin autenticación de usuario.** Es
  necesario para la demo en vivo, pero implica que cualquiera con la URL podría ver los
  experimentos y, peor, **escribir** en el tracking server. Se mitiga con **autenticación
  básica de nginx** (`auth_basic`) sobre ese vhost: una sola directiva, credenciales que se
  comparten con el docente durante la defensa. En un entorno real iría detrás de SSO.
- **`ufw` permite únicamente `22`, `80` y `443`.** Los puertos `5000` y `30080` no se
  publican al exterior; se alcanzan solo a través de nginx o desde dentro del VPS.
- **PostgreSQL no se expone en absoluto**; solo es alcanzable desde la red interna de
  Docker, y sus credenciales viven en `infra/.env`, que **no se commitea** (sí se commitea
  `.env.example`).
- **Se recomienda apagar los servicios tras la defensa**, o dejar `ufw` restringido por IP
  de origen.

---

## 14. Fuera de alcance

Recortado deliberadamente por el plazo de menos de una semana. Se enumera aquí para poder
responder "sí, lo consideramos, y esta fue la razón" en lugar de "no se nos ocurrió":

- **CI/CD con GitHub Actions.** Valioso, pero no está en la rúbrica.
- **Ingress de Kubernetes con cert-manager.** Se resuelve TLS con nginx en el host porque
  MLflow vive fuera del clúster (§3.1). Un Ingress solo cubriría la mitad del sistema.
- **Prometheus y Grafana.** La observabilidad exigida se cubre con las probes de
  Kubernetes y el monitoreo de drift.
- **MLflow dentro de k3s.** Justificado en §3.
- **Autoescalado (HPA).** El enunciado pide escalado manual, y eso es lo que se demuestra.
- **Reentrenamiento automático.** Se define y documenta el *criterio* que lo dispararía,
  que es lo que el enunciado pide; automatizar la ejecución no se solicita.
- **Caché local del modelo en el pod.** Justificado en §4.

---

## 15. Criterios de aceptación

El proyecto está terminado cuando todo lo siguiente es cierto y está evidenciado:

- [ ] La UI de MLflow es accesible y muestra ≥ 6 runs comparables en un mismo experimento.
- [ ] El Model Registry contiene ≥ 2 versiones de `telco-churn` y el alias `@champion`
      apunta a una de ellas.
- [ ] `docker build` produce una imagen que levanta y responde inferencias sin pasos
      manuales adicionales.
- [ ] `requirements.txt` tiene todas las versiones fijadas con `==`, incluida la de MLflow.
- [ ] `kubectl get pods` muestra 3 réplicas en `Running` simultáneamente.
- [ ] Diez peticiones sucesivas al `Service` devuelven al menos dos valores distintos de
      `served_by`.
- [ ] Al borrar un pod, Kubernetes lo recrea y ninguna petición del bucle concurrente
      falla.
- [ ] `kubectl scale` a 5 y a 2 réplicas surte efecto visible.
- [ ] `pytest drift/` está **completamente en verde** (la suite verifica que los detectores
      funcionan).
- [ ] `python -m drift.check --batch data/batches/lote_0.csv` sale con código **0 (verde)**.
- [ ] `python -m drift.check --batch data/batches/lote_3.csv` sale con código **1 (rojo)**
      e indica qué variables dispararon la alerta.
- [ ] Existe una gráfica temporal de degradación del ROC-AUC sobre lotes sucesivos.
- [ ] `ARQUITECTURA.md` indica la versión desplegada y su `run_id`, y `/model-info`
      devuelve exactamente ese `run_id`.
- [ ] La UI web ejecuta predicciones reales contra `https://churn.juanitodev.com`.
- [ ] `https://mlflow.juanitodev.com` y `https://churn.juanitodev.com` cargan con certificado válido, y
      `http://` redirige a `https://`.
- [ ] `certbot renew --dry-run` termina sin errores.
- [ ] Desde fuera del VPS, `nc -zv <IP_PUBLICA> 5000` y `nc -zv <IP_PUBLICA> 30080`
      **fallan** (los puertos internos no están expuestos).
- [ ] `REPARTO.md` existe y el historial de git es coherente con lo declarado.
