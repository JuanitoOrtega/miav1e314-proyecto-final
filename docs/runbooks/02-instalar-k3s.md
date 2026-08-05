# Runbook 02 — Instalación de k3s

Responsable: integrante #3. Requiere el runbook 01 completado.

## 1. Instalar k3s SIN Traefik

Traefik viene incluido en k3s y **ocupa los puertos 80 y 443 del host**. Si se
instala con él, nginx no arrancará y el reto HTTP-01 de certbot fallará sin un
diagnóstico obvio. Como la exposición se hace con NodePort + nginx, no se
pierde nada al desactivarlo.

```bash
curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable=traefik" sh -
```

## 2. Configurar kubectl para el usuario actual

```bash
mkdir -p ~/.kube
sudo cp /etc/rancher/k3s/k3s.yaml ~/.kube/config
sudo chown $(id -u):$(id -g) ~/.kube/config
echo 'export KUBECONFIG=~/.kube/config' >> ~/.bashrc
export KUBECONFIG=~/.kube/config
```

## 3. Verificar el clúster

```bash
kubectl get nodes
kubectl get pods -A
```

Esperado: un nodo en `Ready`. **No debe aparecer ningún pod de Traefik.**

## 4. Verificar que los puertos 80 y 443 están libres

```bash
sudo ss -tlnp | grep -E ':(80|443)\s'
```

Esperado: **sin salida**. Si aparece algo, Traefik sigue vivo:
`kubectl -n kube-system delete helmchart traefik`

## 5. VERIFICACIÓN CRÍTICA — un pod alcanza MLflow

Este es el fallo que bloquearía todo el despliegue. Se comprueba **ahora**,
antes de que nada dependa de ello. **No te saltes este paso.**

```bash
NODE_IP=$(kubectl get node -o jsonpath='{.items[0].status.addresses[0].address}')
echo "IP del nodo: $NODE_IP"

kubectl run prueba-mlflow --rm -it --restart=Never --image=curlimages/curl -- \
  curl -s -m 10 http://$NODE_IP:5000/health
```

Esperado: `OK`

| Si falla con... | Causa | Solución |
|---|---|---|
| timeout / sin respuesta | MLflow atado a `127.0.0.1` | Revisar `ports` en `docker-compose.yml` |
| `403 Invalid Host header` | `--allowed-hosts` de MLflow 3 no cubre la IP del nodo | Añadir `10.*` / la IP con su puerto |

## 6. Guardar la IP del nodo

```bash
echo "NODE_IP=$NODE_IP" | sudo tee -a /etc/environment
```

Se usará en el `deployment.yaml` como valor de `MLFLOW_TRACKING_URI`.
