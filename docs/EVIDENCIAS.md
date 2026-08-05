# Evidencias

Salidas de terminal y capturas que respaldan cada requisito del enunciado.
Cada entrada indica quién la produjo y con qué comando, para que sea
reproducible durante la defensa.

**Estado general:** en construcción. Las secciones marcadas *pendiente*
se completan a medida que avanzan los runbooks.

---

## 1. Infraestructura y seguridad (runbook 01 · integrante #5)

### 1.1 DNS de los subdominios

```
$ dig +short churn.juanitodev.com
152.53.167.147
$ dig +short mlflow.juanitodev.com
152.53.167.147
```

Ambos subdominios resuelven a la IP del VPS.

### 1.2 Firewall — política y reglas

```
$ sudo ufw status verbose
Status: active
Logging: on (low)
Default: deny (incoming), allow (outgoing), allow (routed)
New profiles: skip

To                         Action      From
--                         ------      ----
22/tcp (OpenSSH)           ALLOW IN    Anywhere
80,443/tcp (Nginx Full)    ALLOW IN    Anywhere
Anywhere                   ALLOW IN    10.42.0.0/16    # k3s pods
Anywhere                   ALLOW IN    10.43.0.0/16    # k3s services
22/tcp (OpenSSH (v6))      ALLOW IN    Anywhere (v6)
80,443/tcp (Nginx Full (v6)) ALLOW IN  Anywhere (v6)
```

Solo tres puertos abiertos al exterior: 22, 80 y 443. La política de
enrutado es `allow` porque el tráfico entre pods de Kubernetes atraviesa la
cadena `FORWARD`; con el `deny` por defecto de `ufw`, CoreDNS entra en
`CrashLoopBackOff`.

### 1.3 Cierre del puerto 5000 — cadena DOCKER-USER

```
$ sudo iptables -L DOCKER-USER -n --line-numbers
Chain DOCKER-USER (1 references)
num  target     prot opt source               destination
1    RETURN     6    --  127.0.0.1            0.0.0.0/0    tcp dpt:5000
2    RETURN     6    --  10.42.0.0/16         0.0.0.0/0    tcp dpt:5000
3    DROP       6    --  0.0.0.0/0            0.0.0.0/0    tcp dpt:5000
```

Se permite el acceso desde el propio host (nginx) y desde el CIDR de pods de
k3s; se descarta todo lo demás.

### 1.4 Verificación DESDE FUERA del VPS

Esta es la evidencia que convierte «creemos que está cerrado» en «lo hemos
comprobado». Ejecutada desde una máquina externa, no desde el servidor.

**Antes de aplicar la regla — el puerto estaba abierto a internet:**

```
=== Sondeo desde fuera del VPS ===
  ABIERTO   22
  ABIERTO   80
  ABIERTO   443
  ABIERTO   5000     <-- MLflow expuesto
  cerrado   30080
  cerrado   5432

$ curl -s http://152.53.167.147:5000/health
OK
```

**Después de aplicar la regla:**

```
=== Sondeo desde fuera del VPS — 2026-08-04 20:39:37 ===
  ABIERTO   22
  ABIERTO   80
  ABIERTO   443
  cerrado   5000
  cerrado   30080
  cerrado   5432

$ curl -s -m 8 http://152.53.167.147:5000/health
  (sin respuesta)
```

**Por qué `ufw` no bastaba.** Docker inserta sus propias reglas de iptables y
las publicaciones de puertos se saltan `ufw` por completo: `ufw` filtra en la
cadena `INPUT`, mientras que el tráfico DNAT-eado hacia un contenedor pasa por
`FORWARD`. La cadena `DOCKER-USER` sí se evalúa en esa ruta.

---

## 2. MLflow y trazabilidad (fase 1)

*Pendiente:* experimento con los 6 runs, vista de comparación, Model Registry
con las 2 versiones y el alias `champion`, y `/model-info` devolviendo el
mismo `run_id`.

---

## 3. Contenerización (fase 2)

*Pendiente:* construcción de la imagen, arranque sin pasos manuales y usuario
no-root.

---

## 4. Kubernetes (fase 3)

*Pendiente:* las cuatro demostraciones exigidas — 3 réplicas en Running,
balanceo entre pods, autorreparación y escalado.

---

## 5. Detección de drift (fase 4)

### 5.1 Suite de tests — completamente en verde

```
$ pytest -q
81 passed in 135.57s
```

La suite verifica que los detectores funcionan, incluidas las fórmulas de PSI
y Cramér's V contra valores calculados a mano.

### 5.2 Puerta de drift — verde con datos limpios, roja con datos derivados

```
$ python -m drift.check --batch data/batches/lote_0.csv
VERDE — sin deriva significativa
exit=0

$ python -m drift.check --batch data/batches/lote_3.csv
ROJO — deriva detectada en 2 variable(s): Contract, MonthlyCharges
exit=1
```

Es el comportamiento que exige §6.1 del enunciado: pasa con datos del mismo
origen que el entrenamiento y falla cuando se inyecta deriva deliberadamente.

### 5.3 Gráfica temporal de concept drift

*Pendiente:* `docs/evidencias/concept_drift.png`, generada por
`python -m drift.monitor` contra el modelo real del registry.

---

## 6. TLS y exposición pública

*Pendiente:* certificados válidos en ambos subdominios, redirección 80→443,
`certbot renew --dry-run` y respuesta 401 de MLflow sin credenciales.

---

## 7. Puntos extra — UI web

*Pendiente:* captura de la interfaz ejecutando predicciones reales contra
`https://churn.juanitodev.com`, mostrando el cambio de `served_by` entre pods.
