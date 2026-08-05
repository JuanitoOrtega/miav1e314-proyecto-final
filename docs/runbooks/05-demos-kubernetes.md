# Runbook 05 — Las 4 demostraciones exigidas

Responsable: integrante #3. Estas cuatro pruebas **pueden pedirse en vivo**
durante la defensa (enunciado §5.2). Ensayarlas más de una vez.

---

## Demostración 1 — Tres réplicas en Running simultáneo

```bash
kubectl get pods -l app=telco-churn-api -o wide
kubectl get deployment telco-churn-api
kubectl get svc telco-churn-api
```

Evidencia: 3 pods `Running` con `READY 1/1`.

---

## Demostración 2 — El tráfico se distribuye entre réplicas

```bash
./scripts/demo_balanceo.sh http://localhost:30080 10
```

Evidencia: al menos **dos nombres de pod distintos** en `served_by`, y el
recuento final mostrando el reparto.

> **Cómo funciona:** cada pod recibe su nombre por la Downward API en la
> variable `POD_NAME` y lo devuelve en cada respuesta.

> ⚠ **NO uses `kubectl port-forward` para esta demo.** Port-forward sobre un
> Service se fija a **un solo pod** y no balancea: parecerá que el balanceo no
> funciona. Ataca el **NodePort** (`localhost:30080` desde el VPS) o lanza un
> pod cliente dentro del clúster:
>
> ```bash
> kubectl run cliente --rm -it --restart=Never --image=curlimages/curl -- \
>   sh -c 'for i in $(seq 1 12); do curl -s http://telco-churn-api/health; echo; done'
> ```

---

## Demostración 3 — Autorreparación

Usar **dos terminales lado a lado**. Es lo que hace la demostración
visualmente contundente: se ve que el servicio nunca deja de responder.

**Terminal A** (tráfico continuo):
```bash
while true; do
  curl -s -o /dev/null -w "%{http_code} " http://localhost:30080/health
  sleep 0.3
done
```

**Terminal B** (matar un pod):
```bash
kubectl get pods
kubectl delete pod <NOMBRE_DE_UN_POD>
kubectl get pods -w      # Ctrl-C cuando el nuevo esté Running
```

Evidencia: en el terminal A **solo códigos 200**; en el B se ve el pod
terminando y uno nuevo creándose con nombre distinto.

En el ensayo se capturaron **120 peticiones, todas 200**.

---

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

---

## Captura conjunta de evidencia

```bash
{
  echo "=== DEMO 1: réplicas ==="     ; kubectl get pods -o wide
  echo "=== DEMO 2: balanceo ==="     ; ./scripts/demo_balanceo.sh
  echo "=== DEMO 4: escalado a 5 ===" ; kubectl scale deployment telco-churn-api --replicas=5
  sleep 40                            ; kubectl get pods
  echo "=== DEMO 4: vuelta a 3 ==="   ; kubectl scale deployment telco-churn-api --replicas=3
} 2>&1 | tee ~/evidencia-k8s.txt
```

La demostración 3 se captura aparte, con las dos terminales.
