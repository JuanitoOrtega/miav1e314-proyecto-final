# Runbook 04 — TLS y subdominios

Responsable: integrante #5. Requiere los runbooks 01, 02 y 03 completados.

## 1. Comprobar que el DNS ha propagado

```bash
source ~/proyecto-final/infra/.env
dig +short churn.$DOMAIN_BASE
dig +short mlflow.$DOMAIN_BASE
```

Ambos deben devolver la IP pública del VPS. **Si no, no continuar**: certbot
fallará el reto HTTP-01.

## 2. Instalar nginx y certbot

```bash
sudo apt-get update
sudo apt-get install -y nginx certbot python3-certbot-nginx apache2-utils
```

## 3. Verificar que nginx tomó los puertos 80 y 443

```bash
sudo systemctl status nginx --no-pager
sudo ss -tlnp | grep -E ':(80|443)\s'
```

Si nginx no arranca por *"address already in use"*, Traefik de k3s sigue vivo.
Volver al paso 4 del runbook 02.

## 4. Crear las credenciales de acceso a MLflow

```bash
sudo htpasswd -c /etc/nginx/.htpasswd docente
# Introducir una contraseña y ANOTARLA: se comparte durante la defensa
```

## 5. Instalar los vhosts sustituyendo el dominio

```bash
cd ~/proyecto-final
for sitio in churn mlflow; do
  sed "s/DOMAIN_BASE/$DOMAIN_BASE/g" infra/nginx/$sitio.conf.template \
    | sudo tee /etc/nginx/sites-available/$sitio.conf > /dev/null
  sudo ln -sf /etc/nginx/sites-available/$sitio.conf /etc/nginx/sites-enabled/$sitio.conf
done

sudo rm -f /etc/nginx/sites-enabled/default
sudo nginx -t
```

> `nginx -t` fallará aquí porque los bloques `listen 443 ssl` todavía no tienen
> certificado. **Es esperado**: certbot los añade en el paso siguiente. Si el
> error es de sintaxis (no de certificado), corregirlo antes de seguir.

## 6. Emitir los certificados

```bash
sudo certbot --nginx -d churn.$DOMAIN_BASE -d mlflow.$DOMAIN_BASE \
  --non-interactive --agree-tos -m <TU_CORREO> --redirect

sudo nginx -t && sudo systemctl reload nginx
```

## 7. Añadir el dominio a los Host permitidos de MLflow

**Paso que se olvida y rompe la demo.** nginx proxya con
`proxy_set_header Host $host`, así que MLflow 3 recibe
`Host: mlflow.<dominio>` y lo **rechaza con 403** si no está en la lista.

Ya viene contemplado en `infra/docker-compose.yml` mediante
`--allowed-hosts 'mlflow.${DOMAIN_BASE},...'`, pero hay que verificarlo:

```bash
curl -sI -u docente:<PASS> https://mlflow.$DOMAIN_BASE/ | head -1
```

Si devuelve 403, revisar `DOMAIN_BASE` en `infra/.env` y reiniciar:
`cd ~/proyecto-final/infra && docker compose up -d`

## 8. Verificar la renovación automática

```bash
sudo certbot renew --dry-run
sudo systemctl list-timers | grep certbot
```

## 9. EVIDENCIA — verificación completa

```bash
curl -sI  https://churn.$DOMAIN_BASE/health
curl -s   https://churn.$DOMAIN_BASE/health
curl -sI  http://churn.$DOMAIN_BASE/health | head -1        # debe ser 301
curl -sI  https://mlflow.$DOMAIN_BASE/ | head -1            # debe ser 401
curl -sI -u docente:<PASS> https://mlflow.$DOMAIN_BASE/ | head -1   # debe ser 200
```

Desde **FUERA** del VPS:
```bash
nc -zv <IP_PUBLICA> 5000     # DEBE FALLAR
nc -zv <IP_PUBLICA> 30080    # DEBE FALLAR
nc -zv <IP_PUBLICA> 443      # debe conectar
```

Pegar todas las salidas en `docs/EVIDENCIAS.md`.
