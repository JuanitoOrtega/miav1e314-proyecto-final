# Runbook 03 — Construcción de la imagen y despliegue

**Responsable:** integrante #3 (Perseo) · **Cubre:** T11 del plan

**Requiere:** runbook 02 completado y el modelo registrado con alias
`champion` en MLflow (T5/T19 del integrante 1).

---

## 1. Actualizar el código

```bash
cd ~/miav1e314-proyecto-final
git pull
```

## 2. Comprobar que existe el modelo a servir

Sin alias `champion` los pods arrancarán pero nunca pasarán a `Ready`. Mejor
detectarlo ahora que depurando pods después:

```bash
NODE_IP=$(kubectl get node -o jsonpath='{.items[0].status.addresses[0].address}')
curl -s "http://$NODE_IP:5000/api/2.0/mlflow/registered-models/alias?name=telco-churn&alias=champion"
```

Esperado: un JSON con `model_version` y su `run_id`. Si devuelve
`RESOURCE_DOES_NOT_EXIST`, avisar al integrante 1: falta ejecutar
`python -m src.register`.

## 3. Construir la imagen

```bash
docker build -t telco-churn-api:v1 .
docker images telco-churn-api
```

## 4. Importar la imagen a k3s

k3s usa containerd, no el demonio de Docker. Una imagen construida con
`docker build` **no es visible para el clúster** hasta que se importa.

```bash
docker save telco-churn-api:v1 | sudo k3s ctr images import -
sudo k3s ctr images ls | grep telco-churn
```

## 5. Sustituir la IP del nodo en el manifiesto

```bash
sed "s/NODE_IP_PLACEHOLDER/$NODE_IP/" k8s/deployment.yaml > /tmp/deployment.yaml
grep -A1 MLFLOW_TRACKING_URI /tmp/deployment.yaml
```

Verificar que aparece la IP real y no el marcador.

## 6. Desplegar

```bash
kubectl apply -f /tmp/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl rollout status deployment/telco-churn-api --timeout=180s
```

## 7. Verificar

```bash
kubectl get pods -o wide
kubectl get svc telco-churn-api

curl -s http://localhost:30080/health; echo
curl -s http://localhost:30080/model-info; echo
```

Esperado: 3 pods `Running` con `READY 1/1`, y `/model-info` devolviendo el
nombre del modelo, su versión y el `run_id`.

## 8. Verificar de extremo a extremo, a través de nginx

Hasta ahora `churn.juanitodev.com` devolvía 502 porque no había nada detrás.
Debe empezar a responder sin tocar nada de nginx:

```bash
curl -s https://churn.juanitodev.com/health; echo
curl -s https://churn.juanitodev.com/model-info; echo
```

Y la interfaz web, desde un navegador: `https://churn.juanitodev.com/`

Continuar con el **runbook 05** para las cuatro demostraciones.

---

## Diagnóstico

| Síntoma | Causa probable | Comprobación |
|---|---|---|
| `ImagePullBackOff` | No se importó la imagen, o falta `imagePullPolicy: IfNotPresent` | `sudo k3s ctr images ls \| grep telco` |
| Pods `Running` pero `0/1` durante minutos | El readinessProbe falla: el modelo no carga | `kubectl logs <pod>` |
| Logs con `Intento N/5 falló` | El pod no alcanza MLflow | Repetir el paso 5 del runbook 02 |
| Logs con `Invalid Host header` | Falta la IP del nodo en `MLFLOW_SERVER_ALLOWED_HOSTS` | `docker compose exec mlflow env \| grep ALLOWED` |
| Logs con `RESOURCE_DOES_NOT_EXIST` | No existe el alias `champion` | Paso 2 de este runbook |
| `CrashLoopBackOff` | Error de arranque de la aplicación | `kubectl logs <pod> --previous` |
| `churn.juanitodev.com` sigue en 502 | El Service no quedó en el NodePort 30080 | `kubectl get svc telco-churn-api -o wide` |

Para ver los eventos del despliegue:

```bash
kubectl describe deployment telco-churn-api | tail -20
kubectl get events --sort-by=.lastTimestamp | tail -20
```
