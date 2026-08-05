# Runbook 01 — Bootstrap del VPS

Responsable: integrante #5. Ejecutar como usuario con sudo.

## 1. Crear los registros DNS (HACER PRIMERO — la propagación tarda)

En el panel del proveedor de dominio, dos registros `A` a la IP del VPS:

| Nombre | Tipo | Valor |
|---|---|---|
| `churn` | A | `<IP_PUBLICA_DEL_VPS>` |
| `mlflow` | A | `<IP_PUBLICA_DEL_VPS>` |

Verificar (puede tardar minutos u horas):
```bash
dig +short churn.<DOMINIO>
dig +short mlflow.<DOMINIO>
```

## 2. Verificar Docker

```bash
docker --version
docker compose version
```

## 3. Clonar el repositorio y configurar el entorno

```bash
git clone <URL_DEL_REPO> ~/proyecto-final
cd ~/proyecto-final/infra
cp .env.example .env
nano .env     # DOMAIN_BASE real, contraseña larga, MLFLOW_HOST_PORT=5000
```

## 4. Levantar MLflow y PostgreSQL

```bash
docker compose up -d
docker compose ps
docker compose logs -f mlflow    # Ctrl-C al ver "Listening at: http://0.0.0.0:5000"
```

> El contenedor instala MLflow al arrancar, así que la primera vez tarda
> ~2 minutos. Es normal.

## 5. Verificar que MLflow responde

```bash
curl -s http://localhost:5000/health     # -> OK
```

Verificar también que acepta el Host con el que llegarán los pods:

```bash
curl -s -o /dev/null -w "%{http_code}\n" -H "Host: $(hostname -I | awk '{print $1}'):5000" \
  http://localhost:5000/health
```

Esperado: `200`. Si sale **403 `Invalid Host header`**, falta añadir ese host a
`--allowed-hosts` en `docker-compose.yml`. Ojo: las entradas literales tienen
que incluir el puerto.

## 6. Cerrar el puerto 5000 al exterior

`ufw` NO basta: las publicaciones de puertos de Docker se saltan sus reglas.
Hay que usar la cadena `DOCKER-USER`, que sí se evalúa antes.

```bash
sudo iptables -I DOCKER-USER -p tcp --dport 5000 -s 10.42.0.0/16 -j RETURN
sudo iptables -I DOCKER-USER -p tcp --dport 5000 -s 127.0.0.1     -j RETURN
sudo iptables -A DOCKER-USER -p tcp --dport 5000                  -j DROP

sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save
```

## 7. Configurar ufw

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status verbose
```

## 8. EVIDENCIA — verificar desde FUERA del VPS

Desde tu portátil, **no** desde el servidor:

```bash
nc -zv <IP_PUBLICA> 5000     # DEBE FALLAR
nc -zv <IP_PUBLICA> 22       # debe conectar
```

Pegar ambas salidas en `docs/EVIDENCIAS.md`. Es la diferencia entre creer que
el puerto está cerrado y haberlo comprobado.
