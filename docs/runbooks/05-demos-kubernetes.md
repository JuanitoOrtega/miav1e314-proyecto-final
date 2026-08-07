# Runbook 05 — Las cuatro demostraciones exigidas

**Responsable:** integrante #3 (Perseo) · **Cubre:** T13 del plan

El enunciado (§5.2) exige estas cuatro pruebas documentadas con evidencia, y
**pueden pedirse en vivo durante la defensa**. Ensayarlas más de una vez.

Guardar todas las salidas en [`../EVIDENCIAS.md`](../EVIDENCIAS.md).

---

> **En cada sesión SSH nueva, exporta primero `KUBECONFIG`.** Sin ello
> `kubectl` intenta leer `/etc/rancher/k3s/k3s.yaml`, que solo root puede
> abrir, y falla con `permission denied`. La línea está en `~/.bashrc`, pero
> las terminales abiertas antes de añadirla no la recogen.
>
> ```bash
> export KUBECONFIG=~/.kube/config
> ```

## Demostración 1 — Tres réplicas en Running simultáneo

```bash
kubectl get pods -o wide
kubectl get deployment telco-churn-api
```

**Evidencia:** tres pods `Running` con `READY 1/1`, y el deployment mostrando
`3/3` en la columna `READY`.

**Pregunta previsible:** *¿por qué tres y no una?*
Disponibilidad y reparto de carga. Con una sola réplica, cualquier reinicio
—un despliegue, un fallo, un reprogramado del nodo— deja el servicio caído.

---

## Demostración 2 — El tráfico se distribuye entre réplicas

```bash
./scripts/demo_balanceo.sh http://localhost:30080 10
```

**Evidencia:** el campo `served_by` muestra al menos dos nombres de pod
distintos, y el recuento final el reparto entre ellos.

También se aprecia desde la interfaz web: `https://churn.juanitodev.com/`,
pulsando **Predecir** varias veces. El nombre del pod cambia en pantalla.

**Cómo funciona.** Cada pod recibe su propio nombre en la variable de entorno
`POD_NAME` mediante la Downward API de Kubernetes:

```yaml
env:
  - name: POD_NAME
    valueFrom:
      fieldRef:
        fieldPath: metadata.name
```

El servicio lo devuelve en el campo `served_by` de cada respuesta. Sin ese
mecanismo, el balanceo sería invisible desde fuera.

**Pregunta previsible:** *¿quién hace el balanceo?*
`kube-proxy`, mediante reglas de iptables. El `Service` es una IP virtual: no
hay ningún proceso balanceador, el reparto ocurre en el kernel.

---

## Demostración 3 — Autorreparación

Usar **dos terminales lado a lado**. Es lo que hace la demostración
visualmente contundente: se ve que el servicio nunca deja de responder.

**Terminal A — tráfico continuo:**

```bash
while true; do
  curl -s -o /dev/null -w "%{http_code} " http://localhost:30080/health
  sleep 0.3
done
```

**Terminal B — matar un pod:**

```bash
kubectl get pods
kubectl delete pod <NOMBRE_DE_UN_POD>
kubectl get pods -w        # Ctrl-C cuando el nuevo esté Running
```

**Evidencia:** en el terminal A solo aparecen códigos `200`, sin un solo
error. En el terminal B se ve el pod terminando y otro creándose con nombre
distinto.

**Por qué no se cae el servicio.** El `readinessProbe` saca al pod del
`Service` en cuanto empieza a terminar, así que deja de recibir tráfico antes
de morir. Los otros dos siguen atendiendo mientras el ReplicaSet crea el
sustituto.

**Pregunta previsible:** *¿quién recrea el pod?*
El ReplicaSet que gestiona el Deployment. Su trabajo es reconciliar el estado
real con el declarado: si se declaran 3 réplicas y solo hay 2, crea una.

---

## Demostración 4 — Escalado

```bash
# Escalar hacia arriba
kubectl scale deployment telco-churn-api --replicas=5
kubectl get pods -w          # Ctrl-C cuando los 5 estén Running
./scripts/demo_balanceo.sh http://localhost:30080 15

# Escalar hacia abajo
kubectl scale deployment telco-churn-api --replicas=2
kubectl get pods
./scripts/demo_balanceo.sh http://localhost:30080 10

# Volver al estado base
kubectl scale deployment telco-churn-api --replicas=3
kubectl get pods
```

**Evidencia:** capturas de `get pods` con 5, 2 y 3 réplicas, y cómo cambia el
reparto de `served_by` en cada caso.

**Pregunta previsible:** *¿por qué escalado manual y no un HPA?*
El enunciado pide demostrar el efecto de cambiar el número de réplicas. Un
HorizontalPodAutoscaler es la evolución natural, pero requiere métricas
(`metrics-server`) y no está en la rúbrica. Se descartó a conciencia y está
documentado en `ARQUITECTURA.md`, §7.

---

## Captura de evidencia en un solo bloque

```bash
{
  echo "=== DEMO 1: réplicas ==="
  kubectl get pods -o wide
  kubectl get deployment telco-churn-api

  echo; echo "=== DEMO 2: balanceo ==="
  ./scripts/demo_balanceo.sh http://localhost:30080 10

  echo; echo "=== DEMO 4: escalado a 5 ==="
  kubectl scale deployment telco-churn-api --replicas=5
  sleep 40; kubectl get pods

  echo; echo "=== DEMO 4: reducción a 2 ==="
  kubectl scale deployment telco-churn-api --replicas=2
  sleep 20; kubectl get pods

  echo; echo "=== DEMO 4: vuelta a 3 ==="
  kubectl scale deployment telco-churn-api --replicas=3
  sleep 30; kubectl get pods
} 2>&1 | tee ~/evidencia-k8s.txt
```

La demostración 3 se captura aparte, porque necesita las dos terminales.
