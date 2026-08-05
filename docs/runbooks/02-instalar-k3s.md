# Runbook 02 — Instalación de k3s

**Responsable:** integrante #3 (Perseo) · **Cubre:** T7 del plan

**Requiere:** el runbook 01 completado (MLflow operativo y `ufw` configurado).

---

## 1. Instalar k3s SIN Traefik

> **Obligatorio `--disable=traefik`.** k3s incluye Traefik, que intenta
> enlazar los puertos 80 y 443 del host. Esos puertos ya los ocupa nginx, que
> es la entrada TLS del proyecto y además sirve otros seis sitios en
> producción. Si Traefik arranca, sus pods entran en `CrashLoopBackOff`
> intentando enlazar puertos ocupados.
>
> No se pierde nada: la exposición se hace por NodePort más nginx.

```bash
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable=traefik" sh -
```

## 2. Configurar kubectl para el usuario actual

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
chmod 600 ~/.kube/config
echo 'export KUBECONFIG=~/.kube/config' >> ~/.bashrc
export KUBECONFIG=~/.kube/config
```

## 3. Verificar el clúster

```bash
kubectl get nodes
kubectl get pods -A
```

Esperado: un nodo en `Ready`. **No debe aparecer ningún pod de Traefik.**

Si aparece, eliminarlo:

```bash
kubectl -n kube-system delete helmchart traefik
kubectl -n kube-system delete deployment traefik
```

## 4. Confirmar que nginx sigue en pie

k3s no debe haberle quitado los puertos:

```bash
sudo ss -tlnp | grep -E ':(80|443)\s'
sudo systemctl status nginx --no-pager | head -3
curl -sI https://mlflow.juanitodev.com/ | head -1     # 401, como antes
```

## 5. VERIFICACIÓN CRÍTICA — un pod alcanza MLflow

Este es el fallo que bloquearía todo el despliegue. Se comprueba **ahora**,
antes de que nada dependa de ello.

```bash
NODE_IP=$(kubectl get node -o jsonpath='{.items[0].status.addresses[0].address}')
echo "IP del nodo: $NODE_IP"

kubectl run prueba-mlflow --rm -it --restart=Never --image=curlimages/curl -- \
  curl -s -m 10 http://$NODE_IP:5000/health
```

Esperado: `OK`

Comprobar también que la API de MLflow responde, no solo el healthcheck. La
diferencia importa: `/health` está **exento** de la validación de cabecera
`Host` de MLflow, así que puede responder `OK` mientras `/api/` falla.

```bash
kubectl run prueba-api --rm -it --restart=Never --image=curlimages/curl -- \
  curl -s -m 10 "http://$NODE_IP:5000/api/2.0/mlflow/experiments/search?max_results=1"
```

Esperado: un JSON con la lista de experimentos.

| Si falla con… | Causa | Solución |
|---|---|---|
| Timeout o conexión rechazada | MLflow atado a `127.0.0.1` en lugar de `0.0.0.0` | Revisar `ports` en `infra/docker-compose.yml` |
| Timeout desde el pod pero funciona en el host | Falta la regla `RETURN` de `10.42.0.0/16` en `DOCKER-USER`, o `ufw` tiene `deny (routed)` | Runbook 01, pasos 4 y 5 |
| `Invalid Host header` | `MLFLOW_SERVER_ALLOWED_HOSTS` no incluye la IP del nodo | Añadir `NODE_IP` a `infra/.env` y recrear el contenedor |

## 6. Guardar la IP del nodo

Se usa en el paso siguiente para sustituir el marcador del manifiesto:

```bash
echo "NODE_IP=$NODE_IP"
```

Anotarla. Continuar con el **runbook 03**.
