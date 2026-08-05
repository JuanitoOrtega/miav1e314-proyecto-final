# Evidencias

Salidas reales de terminal de cada requisito del enunciado.

> **Estado de esta evidencia.** Todo lo que sigue se capturó en un **ensayo
> completo sobre minikube + Docker en local**, con el modelo real entrenado y
> registrado en MLflow. Demuestra que el código y los manifiestos funcionan.
> **Antes de la entrega hay que repetir la captura contra el VPS**, porque los
> criterios de TLS, subdominios y cierre de puertos solo son verificables allí,
> y el `run_id` de producción debe ser el del MLflow del servidor.

---

## Fase 1 — MLflow

### Los 6 runs comparables

```
$ python -m src.train
Entrenamiento: 5634 filas · Prueba: 1409 filas
logreg-C0.1    roc_auc=0.8409 f1=0.5913 recall=0.5455
logreg-C1.0    roc_auc=0.8420 f1=0.6040 recall=0.5588
rf-100-d5      roc_auc=0.8400 f1=0.5301 recall=0.4358
rf-300-d10     roc_auc=0.8415 f1=0.5762 recall=0.5107
gb-lr0.05      roc_auc=0.8452 f1=0.5793 recall=0.5080   <-- ganador
gb-lr0.2       roc_auc=0.8386 f1=0.5663 recall=0.5027
```

Los 6 comparten split, semilla (`random_state=42`) y conjunto de métricas,
que es lo que los hace comparables en la vista de comparación de MLflow.

### Registro de versiones y alias

```
$ python -m src.register
v1 = línea base logística (logreg-C1.0, roc_auc=0.8420)
v2 = champion (gb-lr0.05, roc_auc=0.8452)
Alias 'champion' -> telco-churn v2
```

> En el ensayo local las versiones salieron numeradas v3/v4 porque la base de
> datos ya tenía un registro previo. En el VPS, partiendo de cero, serán v1 y v2.

**Pendiente de captura:** pantallazos de la UI de MLflow (experimento con los
6 runs, vista de comparación, Model Registry con el alias).

---

## Fase 2 — Contenedor

### Build

```
$ docker build -t telco-churn-api:v1 .
...
=> => naming to docker.io/library/telco-churn-api:v1

$ docker images telco-churn-api
IMAGE                ID             DISK USAGE
telco-churn-api:v1   89e73134b915   983MB
```

### Arranca y responde sin pasos manuales

```
$ docker run -d --name prueba-api -p 8899:8000 \
    -e MLFLOW_TRACKING_URI=http://<host>:5000 telco-churn-api:v1

READY tras ~6s

$ curl -s localhost:8899/health
{"status":"ok","pod":"local"}

$ curl -s localhost:8899/model-info
{"model_name":"telco-churn","version":"4",
 "run_id":"f34cbea26eb14cddac50700ebfb2d45d",
 "alias":"champion","loaded_at":"2026-08-05T02:07:52.480848+00:00"}

$ curl -s -X POST localhost:8899/predict -H 'Content-Type: application/json' -d '{...}'
{"prediction":1,"probability":0.5799,"served_by":"local","model_version":"4"}
```

### Usuario no-root

```
$ docker exec prueba-api whoami
appuser
```

---

## Fase 3 — Kubernetes (las 4 demostraciones exigidas)

### Demostración 1 — 3 réplicas en Running simultáneo

```
$ kubectl get pods -l app=telco-churn-api -o wide
NAME                              READY   STATUS    RESTARTS   AGE   IP            NODE
telco-churn-api-7dc5d8979-64z86   1/1     Running   0          30s   10.244.0.68   minikube
telco-churn-api-7dc5d8979-z2rhp   1/1     Running   0          30s   10.244.0.67   minikube
telco-churn-api-7dc5d8979-zm59v   1/1     Running   0          30s   10.244.0.69   minikube

$ kubectl get deployment telco-churn-api
NAME              READY   UP-TO-DATE   AVAILABLE   AGE
telco-churn-api   3/3     3            3           31s

$ kubectl get svc telco-churn-api
NAME              TYPE       CLUSTER-IP      PORT(S)        AGE
telco-churn-api   NodePort   10.110.210.84   80:30080/TCP   21s
```

### Demostración 2 — El tráfico se distribuye entre réplicas

12 peticiones sucesivas al `Service`, contadas por pod que las atendió:

```
   3 telco-churn-api-7dc5d8979-64z86
   4 telco-churn-api-7dc5d8979-z2rhp
   3 telco-churn-api-7dc5d8979-zm59v
```

Cada pod recibe su nombre por la **Downward API** en la variable `POD_NAME` y
lo devuelve en el campo `served_by` de cada respuesta.

> **Atención al método de prueba.** `kubectl port-forward` sobre un Service se
> fija a **un solo pod** y no balancea: las 10 primeras peticiones del ensayo
> salieron todas del mismo pod por ese motivo. La demostración debe hacerse
> contra el **NodePort** o desde un pod cliente dentro del clúster.

### Demostración 3 — Autorreparación sin caída de servicio

Bucle de 120 peticiones a `/health` en paralelo al borrado de un pod:

```
$ kubectl delete pod telco-churn-api-7dc5d8979-64z86
pod "telco-churn-api-7dc5d8979-64z86" deleted

$ # códigos HTTP recibidos durante todo el proceso:
 120 200
```

**Ninguna petición falló.** Kubernetes recreó el pod con nombre nuevo:

```
NAME                              READY   STATUS    RESTARTS   AGE
telco-churn-api-7dc5d8979-pqg5d   1/1     Running   0          35s   <-- nuevo
telco-churn-api-7dc5d8979-z2rhp   1/1     Running   0          3m27s
telco-churn-api-7dc5d8979-zm59v   1/1     Running   0          3m27s
```

### Demostración 4 — Escalado

```
$ kubectl scale deployment telco-churn-api --replicas=5
NAME              READY   UP-TO-DATE   AVAILABLE
telco-churn-api   5/5     5            5

$ kubectl scale deployment telco-churn-api --replicas=2
NAME              READY   UP-TO-DATE   AVAILABLE
telco-churn-api   2/2     2            2

$ kubectl scale deployment telco-churn-api --replicas=3   # estado base
```

---

## Trazabilidad — el modelo desplegado es el del experimento

Consultado **desde dentro del clúster**, contra el `Service`:

```
$ curl -s http://telco-churn-api/model-info
{"model_name":"telco-churn","version":"4",
 "run_id":"f34cbea26eb14cddac50700ebfb2d45d","alias":"champion"}
```

Ese `run_id` es exactamente el del run `gb-lr0.05` del experimento
`telco-churn-experimento`, al que apunta el alias `champion` en el Model
Registry. **Ese es el vínculo que exige el enunciado (§3.3).**

---

## Fase 4 — Detección de drift

### La suite completa en verde

```
$ pytest -q
81 passed in 117.46s
```

### La puerta en verde con datos del mismo origen

```
$ python -m drift.check --batch data/batches/lote_0.csv ; echo "exit=$?"
...
VERDE — sin deriva significativa
exit=0
```

### La puerta en rojo con datos derivados

```
$ python -m drift.check --batch data/batches/lote_3.csv ; echo "exit=$?"
MonthlyCharges       ks    stat=  0.2547 p=0.0000     umbral=0.1    DERIVA
Contract             psi   stat=  5.8073 p=n/a        umbral=0.25   DERIVA
Contract             chi2  stat=  0.2498 p=0.0000     umbral=0.1    DERIVA
ROJO — deriva detectada en 2 variable(s): Contract, MonthlyCharges
exit=1
```

### La puerta es ciega al concept drift (por eso hace falta el monitor)

El lote 1 lleva **solo** concept drift: las entradas son idénticas al origen.

```
$ python -m drift.check --batch data/batches/lote_1.csv ; echo "exit=$?"
VERDE — sin deriva significativa
exit=0
```

...y sin embargo el modelo ya se degradó de 0.8530 a 0.7952 en ese mismo lote.

### Concept drift y criterio de reentrenamiento

```
$ python -m drift.monitor
Baseline (lote 0): 0.8530
  Lote 0: ROC-AUC=0.8530  caída=+0.0000
  Lote 1: ROC-AUC=0.7952  caída=+0.0578  <-- por debajo del umbral
  Lote 2: ROC-AUC=0.7482  caída=+0.1048  <-- por debajo del umbral
  Lote 3: ROC-AUC=0.7195  caída=+0.1335  <-- por debajo del umbral
  Lote 4: ROC-AUC=0.6849  caída=+0.1681  <-- por debajo del umbral
  Lote 5: ROC-AUC=0.6532  caída=+0.1998  <-- por debajo del umbral

ALARMA: procede reentrenar (lote 3)
```

Gráfica temporal: [`evidencias/concept_drift.png`](evidencias/concept_drift.png)

---

## Pendiente de capturar en el VPS

| Evidencia | Runbook |
|---|---|
| Pantallazos de la UI de MLflow (runs, comparación, registry) | 06 |
| `https://churn.<dominio>` y `https://mlflow.<dominio>` con certificado válido | 04 |
| `http://` redirige a `https://` (301) | 04 |
| `mlflow.<dominio>` devuelve 401 sin credenciales | 04 |
| `certbot renew --dry-run` sin errores | 04 |
| `nc -zv <IP_PUBLICA> 5000` y `30080` **fallan** desde fuera | 01 y 04 |
| UI web funcionando en el navegador contra el servicio en K8s | 03 |
