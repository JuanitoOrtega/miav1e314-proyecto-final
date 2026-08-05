# Runbook 01 — Bootstrap del VPS (MLflow + TLS)

**Responsable:** integrante #5 (Juanito) · **Cubre:** T6 y T12 del plan

**Prerrequisitos ya cumplidos:** Docker, nginx y certbot instalados; los
subdominios `churn` y `mlflow` propagados.

Ejecutar en orden. Guardar la salida de los pasos marcados **EVIDENCIA** en
`docs/EVIDENCIAS.md`.

---

## 0. Verificación de partida

```bash
docker --version && docker compose version
nginx -v && certbot --version
```

Confirmar que el DNS resuelve a la IP del VPS:

```bash
dig +short churn.juanitodev.com
dig +short mlflow.juanitodev.com
curl -s ifconfig.me; echo    # debe coincidir con las dos anteriores
```

---

## 1. Clonar el repositorio y configurar el entorno

```bash
git clone https://github.com/JuanitoOrtega/<repo>.git ~/proyecto-final
cd ~/proyecto-final
git checkout Infraestructura

cd infra
cp .env.example .env
nano .env
```

En `.env`: dejar `DOMAIN_BASE=juanitodev.com` y poner una contraseña larga en
`POSTGRES_PASSWORD`. Para generarla:

```bash
openssl rand -base64 32
```

---

## 2. Levantar MLflow y PostgreSQL

La primera vez construye la imagen de MLflow (añade el driver de PostgreSQL,
que la imagen oficial no trae):

```bash
cd ~/proyecto-final/infra
docker compose up -d --build
docker compose ps
```

Esperar a que ambos contenedores estén `healthy`:

```bash
watch -n 3 'docker compose ps'     # Ctrl-C cuando los dos digan healthy
```

Si algo falla:

```bash
docker compose logs mlflow --tail 50
docker compose logs postgres --tail 30
```

---

## 3. EVIDENCIA — MLflow responde

```bash
curl -s http://localhost:5000/health; echo
```

Esperado: `OK`

Comprobar que el backend es PostgreSQL y no ficheros sueltos:

```bash
docker compose exec postgres psql -U mlflow -d mlflow -c '\dt' | head -20
```

Esperado: tablas de MLflow (`experiments`, `runs`, `registered_models`…).

---

## 4. Cerrar el puerto 5000 al exterior

> **Esta es la trampa del proyecto.** `ufw` **no** cierra este puerto: Docker
> inserta sus propias reglas de iptables y las publicaciones de puertos se
> saltan `ufw` por completo. Un `ufw deny 5000` da falsa sensación de
> seguridad mientras el puerto sigue abierto a internet. La cadena
> `DOCKER-USER` sí se evalúa antes que las reglas de Docker.

```bash
# Permitir pods de k3s (10.42.0.0/16) y el propio host; descartar el resto
sudo iptables -I DOCKER-USER -p tcp --dport 5000 -s 10.42.0.0/16 -j RETURN
sudo iptables -I DOCKER-USER -p tcp --dport 5000 -s 127.0.0.1     -j RETURN
sudo iptables -A DOCKER-USER -p tcp --dport 5000                  -j DROP

# Persistir entre reinicios
sudo apt-get install -y iptables-persistent
sudo netfilter-persistent save
```

Verificar que las reglas están en el orden correcto (los dos `RETURN` antes
del `DROP`):

```bash
sudo iptables -L DOCKER-USER -n --line-numbers
```

---

## 5. Firewall

```bash
sudo ufw allow 22/tcp
sudo ufw allow 80/tcp
sudo ufw allow 443/tcp
sudo ufw --force enable
sudo ufw status verbose
```

---

## 6. EVIDENCIA — verificar el cierre DESDE FUERA del VPS

**Desde tu portátil, no desde el servidor.** Es la diferencia entre creer que
el puerto está cerrado y haberlo comprobado.

```bash
nc -zv churn.juanitodev.com 5000    # DEBE FALLAR (timeout o refused)
nc -zv churn.juanitodev.com 22      # debe conectar
nc -zv churn.juanitodev.com 80      # debe conectar
```

---

## 7. Credenciales de acceso a MLflow

MLflow no trae autenticación. Sin esto, cualquiera con la URL puede leer los
experimentos y **escribir** en el tracking server.

```bash
sudo apt-get install -y apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd mlops
```

**Anotar la contraseña.** La necesitan:
- Cristhian, para lanzar los 6 runs desde su máquina (paso 11)
- El docente, durante la defensa

---

## 8. Instalar los vhosts de nginx

```bash
cd ~/proyecto-final
source infra/.env

for sitio in churn mlflow; do
  sed "s/DOMAIN_BASE/$DOMAIN_BASE/g" infra/nginx/$sitio.conf.template \
    | sudo tee /etc/nginx/sites-available/$sitio.conf > /dev/null
  sudo ln -sf /etc/nginx/sites-available/$sitio.conf \
              /etc/nginx/sites-enabled/$sitio.conf
done

sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t && sudo systemctl reload nginx
```

`nginx -t` debe pasar: los vhosts son solo HTTP todavía.

Comprobar que el proxy de MLflow ya funciona (pedirá usuario y contraseña):

```bash
curl -s -u mlops:<PASS> http://mlflow.juanitodev.com/health; echo
curl -sI http://mlflow.juanitodev.com/ | head -1    # 401 sin credenciales
```

> `http://churn.juanitodev.com` devolverá **502** hasta que Perseo despliegue
> el servicio en k3s. Es lo esperado y no impide emitir el certificado.

---

## 9. Emitir los certificados TLS

```bash
sudo certbot --nginx \
  -d churn.juanitodev.com \
  -d mlflow.juanitodev.com \
  --non-interactive --agree-tos --redirect \
  -m ceo@creativa.dev

sudo nginx -t && sudo systemctl reload nginx
```

`--redirect` hace que certbot añada el bloque `443` y la redirección
`80 -> 443` automáticamente.

---

## 10. EVIDENCIA — TLS operativo

```bash
curl -sI https://mlflow.juanitodev.com/ | head -1              # 401
curl -s -u mlops:<PASS> https://mlflow.juanitodev.com/health   # OK
curl -sI http://mlflow.juanitodev.com/ | head -1               # 301
sudo certbot certificates
sudo certbot renew --dry-run
```

---

## 11. Desbloquear al equipo

Avisar al grupo de que MLflow está operativo y pasar estas variables:

```bash
export MLFLOW_TRACKING_URI=https://mlflow.juanitodev.com
export MLFLOW_TRACKING_USERNAME=mlops
export MLFLOW_TRACKING_PASSWORD=<PASS>
```

**Cristhian (T19)** ya puede ejecutar desde su máquina:

```bash
python -m src.train      # los 6 runs
python -m src.register   # registra el mejor y lo promueve a champion
```

**Perseo (T7)** ya puede instalar k3s. Recordarle:

> **Obligatorio `--disable=traefik`.** nginx ya ocupa los puertos 80 y 443;
> si k3s arranca con Traefik, sus pods entrarán en CrashLoop intentando
> enlazarlos.
>
> ```bash
> curl -sfL https://get.k3s.io | INSTALL_K3S_EXEC="--disable=traefik" sh -
> ```

---

## Diagnóstico

| Síntoma | Causa probable | Comprobación |
|---|---|---|
| `docker compose up` falla al construir | Sin red o el tag de la imagen no existe | `docker pull ghcr.io/mlflow/mlflow:v3.15.1` |
| MLflow reinicia en bucle | No conecta a PostgreSQL | `docker compose logs mlflow --tail 50` |
| `certbot` falla el reto HTTP-01 | Algo más ocupa el 80, o el DNS no resuelve | `sudo ss -tlnp \| grep :80` y `dig +short mlflow.juanitodev.com` |
| `log_model` falla con 413 | Falta `client_max_body_size` | `grep client_max_body_size /etc/nginx/sites-enabled/mlflow.conf` |
| Los pods no cargan el modelo | MLflow atado a `127.0.0.1`, o falta la regla `RETURN` de `10.42.0.0/16` | `sudo iptables -L DOCKER-USER -n --line-numbers` |
| `nc` desde fuera SÍ conecta al 5000 | La regla `DROP` no se aplicó o quedó tras un `RETURN` demasiado amplio | `sudo iptables -L DOCKER-USER -n --line-numbers` |
