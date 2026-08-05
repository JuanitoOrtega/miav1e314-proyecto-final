# Runbook 03 — Build y despliegue

Responsable: integrante #3. Requiere los runbooks 01 y 02.

## 1. Actualizar el código en el VPS

```bash
cd ~/proyecto-final
git pull
```

## 2. Construir la imagen

```bash
docker build -t telco-churn-api:v1 .
docker images telco-churn-api
```

> La imagen base está fijada a `python:3.11-slim-bookworm`. **No cambiar a
> `python:3.11-slim` a secas**: ese tag flotante saltó a Debian trixie y el
> `apt-get` del build empezó a fallar sin aviso.

## 3. Importar la imagen a k3s

k3s usa containerd, **no** el demonio de Docker: la imagen construida con
`docker build` no es visible para el clúster hasta que se importa.

```bash
docker save telco-churn-api:v1 | sudo k3s ctr images import -
sudo k3s ctr images ls | grep telco-churn
```

## 4. Sustituir la IP del nodo en el manifiesto

```bash
NODE_IP=$(kubectl get node -o jsonpath='{.items[0].status.addresses[0].address}')
sed "s/NODE_IP_PLACEHOLDER/$NODE_IP/" k8s/deployment.yaml > /tmp/deployment.yaml
grep -A1 MLFLOW_TRACKING_URI /tmp/deployment.yaml
```

## 5. Desplegar

```bash
kubectl apply -f /tmp/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl rollout status deployment/telco-churn-api --timeout=240s
```

## 6. Verificar

```bash
kubectl get pods -o wide
curl -s http://localhost:30080/health
curl -s http://localhost:30080/model-info
```

Esperado: 3 pods `Running` con `READY 1/1`, y `/model-info` devolviendo el
`run_id` del champion.

## 7. Verificar la UI web

Abrir `http://<IP_VPS>:30080/` (o el subdominio una vez hecho el runbook 04).
Pulsar **Predecir** varias veces: el campo `served_by` debe cambiar de pod.

## Diagnóstico si algo falla

| Síntoma | Causa probable | Comando |
|---|---|---|
| `ImagePullBackOff` | No se importó la imagen o falta `imagePullPolicy: IfNotPresent` | `sudo k3s ctr images ls \| grep telco` |
| Pods `Running` pero `0/1` | El readinessProbe falla: el modelo no carga | `kubectl logs <pod>` |
| Logs con `Intento N/5 falló` + timeout | El pod no alcanza MLflow | Repetir el paso 5 del runbook 02 |
| Logs con `403 Invalid Host header` | `--allowed-hosts` de MLflow 3 | Añadir la IP del nodo **con su puerto** |
| `CrashLoopBackOff` | Error de arranque de la aplicación | `kubectl logs <pod> --previous` |
