# Arquitectura

Documento de arquitectura del proyecto **telco-churn-mlops**: qué se
construyó, cómo encaja y —sobre todo— por qué se tomó cada decisión.

---

## 1. Visión general

Un modelo de clasificación binaria que predice el abandono de clientes de
telecomunicaciones, servido desde Kubernetes con tres réplicas, con
trazabilidad completa hacia el experimento que lo produjo y monitoreo
automatizado de deriva.

Todo corre en un VPS Ubuntu 24.04 (4 vCore, 8 GB RAM, 256 GB NVMe), repartido
en dos planos.

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

| Componente | Tecnología | Dónde vive |
|---|---|---|
| Tracking y registro de modelos | MLflow 3.15.1 + PostgreSQL 16 | Docker Compose |
| Servicio de inferencia | FastAPI + scikit-learn | k3s, 3 réplicas |
| Interfaz web | HTML + JavaScript | Dentro del contenedor de la API |
| Terminación TLS | nginx + certbot | Host |
| Detección de drift | scipy + pytest | Ejecución bajo demanda |

---

## 2. Decisiones de arquitectura

### 2.1 MLflow vive fuera del clúster

Desplegar MLflow dentro de k3s exigiría un `StatefulSet`, un
`PersistentVolumeClaim` y depuración de almacenamiento persistente: cerca de
un día de trabajo que la rúbrica no evalúa.

Separarlo tiene además una ventaja conceptual: el docente ve que el servicio
*dentro* de Kubernetes consulta un Model Registry *externo*, que es el patrón
real de la industria. Un registry acoplado al clúster que sirve el modelo sería
menos representativo.

### 2.2 El pod carga el modelo del registry por alias

```python
mlflow.sklearn.load_model("models:/telco-churn@champion")
```

Es la decisión con más peso del proyecto y cumple literalmente §3.3.2 del
enunciado: *"la versión que se despliega se marca de forma explícita y el
servicio la consume por esa referencia, no por una ruta de archivo suelta"*.

Promover un modelo nuevo a producción se reduce a mover el alias y ejecutar
`kubectl rollout restart`. No se reconstruye la imagen ni se toca una línea de
código.

**Alternativas descartadas:**

- *Modelo horneado en la imagen durante `docker build`.* Los pods arrancarían
  sin dependencia externa, pero congela la referencia dentro del artefacto y
  contradice el espíritu del requisito.
- *Init container que descarga a un volumen compartido.* Correcto, pero añade
  una pieza que no aporta puntos y sí superficie que defender.

**Riesgo asumido.** Si MLflow está caído, un pod nuevo no arranca. Se mitiga
con reintentos de backoff exponencial en el arranque y un `readinessProbe` que
mantiene al pod fuera del `Service` hasta que el modelo esté cargado: los pods
sanos siguen atendiendo mientras tanto.

**Se decidió NO implementar caché local del modelo.** Añadiría una ruta de
código con su propia lógica de invalidación para resolver un fallo que en la
práctica no ocurre —MLflow y el clúster están en la misma máquina—. Es una
omisión deliberada, no un descuido.

### 2.3 `mlflow.sklearn` y no `mlflow.pyfunc`

El sabor `pyfunc` no expone `predict_proba`, y el servicio necesita la
probabilidad de abandono, no solo la clase predicha. Cargar el modelo como
`sklearn` devuelve el `Pipeline` completo.

### 2.4 Preprocesamiento serializado dentro del modelo

`src/features.py` define un único `ColumnTransformer` que se envuelve junto al
clasificador en un `sklearn.Pipeline`. Ese pipeline completo es lo que se
guarda en MLflow.

En consecuencia **el servicio de inferencia nunca reimplementa el
preprocesamiento**: recibe el registro crudo del cliente y llama a `predict`.
Es lo que elimina la clase entera de errores conocida como *train/serve skew*,
y es verificable abriendo el artefacto en la UI de MLflow.

El `OneHotEncoder` usa `handle_unknown="ignore"` a propósito: en producción
puede llegar una categoría que no existía al entrenar, y el servicio debe
responder en lugar de fallar.

### 2.5 nginx en el host, no el Ingress de Traefik

MLflow vive fuera del clúster, así que un `Ingress` de Kubernetes no lo
cubriría sin inventar un `Service` de tipo `ExternalName` apuntando de vuelta
al host: una pieza rara de explicar.

nginx en el host es un único punto de entrada que cubre los dos planos con la
misma herramienta y el mismo certificado. Como consecuencia, **k3s se instala
con `--disable=traefik`**: Traefik ocuparía los puertos 80 y 443 e impediría
arrancar a nginx.

### 2.6 Dos subdominios en lugar de rutas de un mismo host

Servir MLflow bajo un subpath (`/mlflow`) es notoriamente problemático: su
interfaz genera URLs absolutas para recursos estáticos y llamadas a su propia
API, lo que obliga a reescrituras frágiles que se rompen entre versiones. Un
registro DNS adicional elimina la clase entera de problema.

### 2.7 La interfaz web se sirve desde el propio contenedor de la API

En lugar de un segundo `Deployment` con Streamlit. Al compartir origen con la
API, el `fetch` no necesita CORS ni una URL base configurable, y se ahorra un
Dockerfile y un manifiesto.

Como efecto secundario útil, cada respuesta muestra el pod que la atendió: la
interfaz es en sí misma una demostración visual del balanceo de carga.

---

## 3. Modelo desplegado

| Campo | Valor |
|---|---|
| Nombre en el Model Registry | `telco-churn` |
| Alias de producción | `champion` |
| Experimento | `telco-churn-experimento` |
| Métrica principal | ROC-AUC |

La versión concreta y su `run_id` se obtienen del propio servicio:

```bash
curl -s https://churn.juanitodev.com/model-info
```

**La trazabilidad se demuestra en vivo** abriendo ese endpoint junto a
`https://mlflow.juanitodev.com` y comprobando que el `run_id` que sirve
peticiones es exactamente el de la versión marcada con el alias en el Model
Registry. Ese vínculo es el corazón de la fase 1.

### 3.1 Dataset

**Telco Customer Churn (IBM).** 7.043 registros, 21 columnas, versionado en el
repositorio para que el entrenamiento sea reproducible sin dependencias de red.

- 3 variables numéricas: `tenure`, `MonthlyCharges`, `TotalCharges`
- 16 variables categóricas
- Objetivo `Churn`, con **26,5 % de positivos** (desbalanceado)

**Problema de calidad conocido.** `TotalCharges` viene tipada como texto y
contiene 11 cadenas vacías, todas de clientes con `tenure = 0` que nunca han
sido facturados. Se imputan con `0.0`, que es el valor semánticamente correcto,
no una imputación estadística arbitraria.

`SeniorCitizen` llega como entero 0/1 pero es conceptualmente categórica y se
trata como tal.

### 3.2 Reproducibilidad

`random_state = 42` en el split y en todos los modelos. División estratificada
80/20 sobre el objetivo: 5.634 filas de entrenamiento y 1.409 de prueba.

### 3.3 Los seis runs

| Run | Modelo | Hiperparámetro variado |
|---|---|---|
| `logreg-C0.1` | LogisticRegression | `C=0.1` |
| `logreg-C1.0` | LogisticRegression | `C=1.0` |
| `rf-100-d5` | RandomForest | `n_estimators=100, max_depth=5` |
| `rf-300-d10` | RandomForest | `n_estimators=300, max_depth=10` |
| `gb-lr0.05` | GradientBoosting | `learning_rate=0.05` |
| `gb-lr0.2` | GradientBoosting | `learning_rate=0.2` |

Son comparables porque comparten split, semilla y conjunto de métricas
registradas. Cada uno guarda parámetros, las cuatro métricas, el modelo con su
*signature* e *input example*, y la matriz de confusión como artefacto.

### 3.4 Por qué ROC-AUC como métrica principal

Con un 26,5 % de positivos, **la exactitud es engañosa**: un clasificador que
prediga siempre "no abandona" alcanza 73,5 % de accuracy sin haber aprendido
nada. ROC-AUC es además insensible al umbral de decisión, lo que permite
comparar modelos sin fijar antes una política de negocio.

Se registran también F1 y recall de la clase positiva, porque en un caso de
abandono el coste de un falso negativo —un cliente que se va sin ser
detectado— supera al de un falso positivo.

**Nota honesta sobre la selección.** Los seis modelos quedan muy igualados en
ROC-AUC (entre 0,839 y 0,845). Esa diferencia es ruido, no señal, así que
"el de mayor AUC" no es por sí solo un argumento suficiente. Con rendimiento
equivalente, el criterio de desempate razonable es la simplicidad del modelo o
el recall de la clase positiva.

---

## 4. Detección de drift

### 4.1 Data drift — una prueba por tipo de variable

| Tipo | Prueba | Umbral de alerta |
|---|---|---|
| Numéricas | Kolmogorov-Smirnov | `p < 0.05` **y** `D > 0.10` |
| Categóricas | PSI (con Chi² y Cramér's V) | `PSI > 0.25` |

**Por qué Kolmogorov-Smirnov.** Es no paramétrico y no asume normalidad.
`MonthlyCharges` tiene una distribución claramente bimodal —clientes con y sin
servicio de internet—, así que cualquier prueba que asuma normalidad, como un
t-test, sería inválida. KS compara las funciones de distribución acumulada
completas, no solo la media.

**Por qué PSI para las categóricas.** Es la métrica estándar de estabilidad de
poblaciones y da una magnitud interpretable en lugar de un sí/no. Chi² lo
acompaña aportando significancia estadística y Cramér's V el tamaño del efecto.

### 4.2 De dónde salen los umbrales

- **PSI.** Escala convencional de las *scorecards* crediticias, donde se
  originó el índice: `< 0.10` población estable, `0.10 – 0.25` cambio moderado
  que amerita vigilancia, `> 0.25` cambio significativo que exige acción.
- **`p < 0.05`.** Nivel de significancia convencional.
- **`D > 0.10` — el criterio que de verdad importa.** Con n = 7.043, el test KS
  rechaza la hipótesis nula ante diferencias irrelevantes en la práctica: es
  hipersensible al tamaño muestral. Exigir además un tamaño del efecto mínimo
  separa *estadísticamente significativo* de *prácticamente relevante*. Sin ese
  filtro, el monitor alertaría a diario y el equipo dejaría de hacerle caso.

**Comparaciones múltiples.** Se evalúan 35 pruebas simultáneas (3 KS + 16 PSI
+ 16 Chi²). Con α = 0,05 cabría esperar algún falso positivo por azar; los
criterios de tamaño del efecto los suprimen en la práctica. Es una limitación
conocida y asumida: aplicar una corrección tipo Bonferroni haría el monitor
demasiado insensible para su propósito.

### 4.3 Concept drift

Cambia la relación entre las entradas y el objetivo: las entradas pueden verse
idénticas y aun así el modelo empieza a equivocarse.

**Simulación.** Se invierte la etiqueta de los clientes con
`Contract == 'Two year'` en una proporción creciente a lo largo de lotes
sucesivos. Tiene una historia de negocio creíble —un cambio de política de
permanencia hace que los contratos largos dejen de proteger contra el
abandono— y las distribuciones de entrada permanecen intactas, que es
precisamente lo que distingue el concept drift del data drift.

**Criterio de reentrenamiento.** Se dispara la alarma cuando el ROC-AUC cae
**más de 0,05 en términos absolutos** respecto al baseline, **sostenida
durante 3 lotes consecutivos**.

La condición de persistencia existe para no reentrenar por un lote ruidoso: un
reentrenamiento innecesario tiene coste real, así que la estabilidad del
criterio importa tanto como su sensibilidad. Hay un test específico que lo
verifica (`test_un_solo_lote_malo_no_dispara_la_alarma`).

### 4.4 Política ante el retraso de etiquetas

En producción la etiqueta de abandono no se conoce hasta aproximadamente 30
días después de la predicción. **El ROC-AUC por lote no es calculable en tiempo
real**: el monitoreo de la sección anterior solo funciona en retrospectiva.

Mientras las etiquetas llegan, se vigila con tres indicadores que no las
necesitan:

1. **Data drift de las variables de entrada** (§4.1), que actúa como indicador
   adelantado: si las entradas cambian, el rendimiento suele degradarse después.
2. **Prediction drift.** Se aplica KS a la distribución de los *scores* que
   emite el modelo, comparándola con la del baseline.
3. **Tasa de positivos predichos.** Si el modelo empieza a predecir un 40 % de
   abandono donde históricamente predecía un 26 %, algo cambió aunque nadie
   pueda confirmarlo todavía.

Ninguno de los tres prueba que el modelo se haya degradado. Sirven para
decidir cuándo merece la pena adelantar una revisión manual o acelerar la
recolección de etiquetas.

### 4.5 Dos artefactos distintos: la puerta y la suite

El enunciado pide que *"la prueba falle (estado rojo) cuando se inyecten datos
derivados"*. Eso describe una **puerta de calidad**, no una suite de tests
unitarios: si un test que verifica *"el detector detecta"* se pusiera en rojo
ante datos derivados, significaría que el detector **no** funciona.

Por eso se construyeron dos artefactos separados:

**`drift/check.py` — la puerta.** Recibe un lote, lo evalúa contra el baseline
e imprime una tabla por variable con su estadístico, umbral y veredicto.
Termina con código de salida distinto de cero si alguna variable supera el
umbral.

```
lote_0 (limpio)   → exit=0  VERDE — sin deriva significativa
lote_3 (derivado) → exit=1  ROJO — deriva detectada en 2 variable(s)
```

**`drift/tests/` — la suite.** Verifica que la puerta se comporta como debe.
Todos sus tests están en verde cuando la implementación es correcta, incluidos
los que comprueban la detección. Dos de ellos validan las fórmulas de PSI y
Cramér's V contra valores calculados a mano.

---

## 5. Despliegue

### 5.1 Contenedor

Imagen propia basada en `python:3.12-slim`, construcción multi-stage, usuario
no-root (`appuser`) y `HEALTHCHECK` declarado. Todas las dependencias fijadas
con `==`, incluida la versión de MLflow.

La imagen se etiqueta `telco-churn-api:v1`, nunca `latest`: demostrar un
rollout de Kubernetes exige poder cambiar el tag.

Se construye en el propio VPS y se importa a k3s con
`k3s ctr images import`, sin registry intermedio. Para un clúster de un nodo
es la opción correcta: cero infraestructura adicional y cero credenciales.
Por eso el manifiesto usa `imagePullPolicy: IfNotPresent` — sin esa directiva
k3s intentaría descargar una imagen que no existe en ningún registry remoto.

### 5.2 Kubernetes

`Deployment` con 3 réplicas, `requests` de 256 Mi / 100 m y `limits` de
512 Mi / 500 m. Tres réplicas consumen como máximo ~1,5 GB de los 8 GB
disponibles.

| Probe | Endpoint | Semántica |
|---|---|---|
| `livenessProbe` | `/health` | El proceso está vivo. No mira el modelo. |
| `readinessProbe` | `/ready` | Devuelve 200 **solo** si el modelo está cargado. |

La distinción importa: si `/health` comprobara el modelo, un pod que no logra
cargarlo sería reiniciado en bucle en lugar de simplemente quedar fuera del
balanceo.

**Cómo se demuestra el balanceo.** Cada pod recibe su nombre en la variable
`POD_NAME` mediante la Downward API y lo devuelve en el campo `served_by` de
cada respuesta. Un bucle de diez peticiones muestra nombres distintos, y lo
mismo se aprecia desde la interfaz web.

---

## 6. Seguridad

Decisiones tomadas a conciencia, con sus limitaciones declaradas.

- **Todo el tráfico externo va cifrado con TLS**, con certificados de Let's
  Encrypt y redirección forzada de `:80` a `:443`.
- **MLflow está protegido con autenticación básica de nginx.** No trae
  autenticación propia: sin ella, cualquiera con la URL podría leer los
  experimentos y, peor, **escribir** en el tracking server. En un entorno real
  iría detrás de SSO.
- **El puerto 5000 no es accesible desde internet.** Aquí hay una sutileza
  importante: `ufw` **no** basta, porque Docker inserta sus propias reglas de
  iptables y las publicaciones de puertos se saltan `ufw` por completo — `ufw`
  filtra en la cadena `INPUT`, mientras que el tráfico DNAT-eado hacia un
  contenedor pasa por `FORWARD`. El cierre se hace con reglas explícitas en la
  cadena `DOCKER-USER`, y **se verificó desde fuera del VPS**, no desde dentro.
- **MLflow solo escucha a hosts declarados.** MLflow 3 valida la cabecera
  `Host` como protección contra DNS rebinding; su lista por defecto no incluye
  ni el subdominio ni la IP del nodo, así que se configura explícitamente con
  `MLFLOW_SERVER_ALLOWED_HOSTS`.
- **PostgreSQL no se expone en absoluto**: solo es alcanzable desde la red
  interna de Docker, y sus credenciales viven en `infra/.env`, que no se
  versiona.
- **`ufw` permite únicamente 22, 80 y 443**, más los CIDR internos de k3s
  (`10.42.0.0/16` y `10.43.0.0/16`), necesarios porque el tráfico entre pods
  atraviesa la cadena `FORWARD`.

**Recomendación operativa:** apagar los servicios tras la defensa o restringir
`ufw` por IP de origen.

---

## 7. Fuera de alcance

Recortado deliberadamente. Se enumera para poder responder *"sí, lo
consideramos, y esta fue la razón"* en lugar de *"no se nos ocurrió"*:

| Descartado | Motivo |
|---|---|
| CI/CD con GitHub Actions | Valioso, pero no está en la rúbrica |
| Ingress de Kubernetes con cert-manager | Solo cubriría la mitad del sistema (§2.5) |
| Prometheus y Grafana | La observabilidad exigida se cubre con las probes y el monitoreo de drift |
| MLflow dentro de k3s | Justificado en §2.1 |
| Autoescalado (HPA) | El enunciado pide escalado manual, y eso es lo que se demuestra |
| Reentrenamiento automático | Se define y documenta el *criterio* que lo dispararía, que es lo que se pide |
| Caché local del modelo en el pod | Justificado en §2.2 |
