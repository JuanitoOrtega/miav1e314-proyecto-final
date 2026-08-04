# Coordinación del equipo

Quién hace qué, en qué orden, y de quién depende cada uno.

**Documentos relacionados:**
[Enunciado](PROYECTO.md) ·
[Diseño](superpowers/specs/2026-08-03-telco-churn-mlops-design.md) ·
[Plan de implementación](superpowers/plans/2026-08-03-telco-churn-mlops.md)

---

## 1. Los cinco roles

| # | Rol | Responsable de | Tareas del plan |
|---|---|---|---|
| **1** | **Modelo y MLflow - Cristhian** | El dataset, el preprocesamiento, los 6 runs y el versionado del modelo | T2, T3, T4, T5, T19 |
| **2** | **API y contenedor - Ronald** | El servicio de inferencia y su empaquetado en Docker | T1, T8, T9 |
| **3** | **Kubernetes - Perseo** | El clúster, el despliegue y las 4 demostraciones calificadas | T7, T10, T11, T13 |
| **4** | **Drift - Erika y Ricardo** | Los detectores estadísticos, la puerta y el criterio de reentrenamiento | T14, T15, T16, T17 |
| **5** | **Infraestructura, TLS y docs - Juanito** | MLflow, PostgreSQL, nginx, certbot, la UI web y la documentación de entrega | T6, T12, T18, T20 |

---

## 2. Quién va primero

**Dos personas arrancan el reloj de todos los demás. Si una de las dos se retrasa, el proyecto entero se retrasa.**

### Hora 0 — arranque conjunto (30 minutos, los cinco presentes)

El **integrante 2** ejecuta la **Tarea 1** (andamiaje del repositorio: `.gitignore`, `requirements.txt`, estructura de carpetas) y la empuja a `main`. Los otros cuatro clonan y crean su entorno virtual.

Nadie escribe código hasta que esto esté en `main`, porque todos dependen de las mismas versiones fijadas.

### Los dos cuellos de botella

| Quién | Entregable crítico | Plazo | A quién desbloquea |
|---|---|---|---|
| **Integrante 1** | `src/features.py` (Tarea 3) | **Primeras 3 horas** | Integrantes 2 y 4 — no pueden escribir nada hasta tenerlo |
| **Integrante 5** | MLflow operativo (Tarea 6) | **Primeras 4 horas** | Integrantes 1, 2 y 3 — sin esto no hay integración posible |

> **Integrante 1:** `src/features.py` es la tarea más urgente del proyecto. Es un fichero pequeño (constantes del esquema, limpieza, split y preprocesador). Escríbelo, haz que pasen sus tests y empújalo **antes** de ponerte con el entrenamiento. Los integrantes 2 y 4 están parados esperándolo.

> **Integrante 5:** haz los registros DNS **lo primero de todo**, antes incluso de instalar Docker. La propagación tarda y necesitas que esté lista para el día 3. Es lo único del proyecto que no puedes acelerar trabajando más rápido.

---

## 3. Mapa de dependencias

```
  T1 andamiaje (#2)
   │
   ├──▶ T2 dataset (#1) ──▶ T3 features.py (#1) ═══╗ CUELLO DE BOTELLA
   │                                                ║
   │                          ┌─────────────────────╨──────────────┐
   │                          │                     │              │
   │                          ▼                     ▼              ▼
   │                    T4 train (#1)         T8 API (#2)   T14 detectores (#4)
   │                          │                     │              │
   │                          ▼                     ▼              ▼
   │                    T5 registro (#1)      T9 Docker (#2)  T15 generadores (#4)
   │                          │                     │              │
   └──▶ T6 MLflow (#5) ═══════╧═════════════════════╡              ▼
        CUELLO DE BOTELLA                           │        T16 puerta (#4)
             │                                      │              │
             ▼                                      │              ▼
        T7 k3s (#3) ──▶ T10 manifests (#3) ──▶ T11 deploy (#3)  T17 monitor (#4)
                                                    │
                          ┌─────────────────────────┼──────────────┐
                          ▼                         ▼              ▼
                    T12 TLS (#5)            T13 demos (#3)   T18 UI (#5)
                          │                         │              │
                          └─────────────┬───────────┴──────────────┘
                                        ▼
                              T19 modelo real (#1 + #3)
                                        │
                                        ▼
                                  T20 docs (#5)
```

---

## 4. Ficha de cada integrante

### Integrante 1 — Modelo y MLflow

| | |
|---|---|
| **Tareas** | T2 (dataset), T3 (features), T4 (entrenamiento), T5 (registro), T19 (modelo real) |
| **Necesitas antes de empezar** | Que T1 esté en `main` |
| **Bloqueas a** | Integrante 2 y integrante 4 con `src/features.py` |
| **Tu rama** | `feat/modelo` |

**Orden de trabajo:**
1. **T2 y T3 primero, sin excepción.** Empuja `src/features.py` en cuanto pasen sus tests y avisa al grupo.
2. T4 — los 6 runs. Se desarrollan y prueban en local con MLflow en fichero; no necesitas el VPS todavía.
3. T5 — el registro. **Ojo:** los tests usan `sqlite:///`, no `file://`, porque el `FileStore` de MLflow no implementa el Model Registry.
4. Cuando el integrante 5 avise de que MLflow está arriba, ejecuta `register_dummy()` contra el servidor real. Eso desbloquea al integrante 2.
5. T19 (día 3) — entrenamiento real, registro de las 2 versiones y promoción a `champion`.

**Tu parte de la defensa:** por qué ROC-AUC y no accuracy; qué representa cada run; por qué hay dos versiones registradas; cómo se demuestra que el modelo desplegado es el del experimento.

---

### Integrante 2 — API y contenedor

| | |
|---|---|
| **Tareas** | T1 (andamiaje), T8 (API), T9 (Docker) |
| **Necesitas antes de empezar** | `src/features.py` del integrante 1 |
| **Bloqueas a** | Integrante 3, que no puede desplegar sin tu imagen |
| **Tu rama** | `feat/api` |

**Orden de trabajo:**
1. **T1 es lo primero del proyecto entero.** 30 minutos, y empújalo a `main` directamente (no a una rama).
2. Mientras esperas `features.py`, escribe `src/api/schemas.py` — las 19 variables Pydantic no dependen de nada más.
3. T8 — la API. Los tests usan un modelo falso, así que **no necesitas que MLflow esté arriba ni que exista el modelo bueno**.
4. T9 — el Dockerfile. Para verificarlo end-to-end sí necesitas MLflow y el modelo dummy del integrante 1.

**Cuidado con esto:** carga el modelo con `mlflow.sklearn.load_model`, no con `mlflow.pyfunc.load_model`. El segundo no expone `predict_proba` y necesitas la probabilidad, no solo la clase.

**Tu parte de la defensa:** por qué el pod carga el modelo por alias y no horneado en la imagen; qué pasa si MLflow se cae; diferencia entre `livenessProbe` y `readinessProbe`; por qué usuario no-root.

---

### Integrante 3 — Kubernetes

| | |
|---|---|
| **Tareas** | T7 (k3s), T10 (manifiestos), T11 (despliegue), T13 (las 4 demos) |
| **Necesitas antes de empezar** | MLflow arriba (T6) para instalar k3s; la imagen del integrante 2 para desplegar |
| **Bloqueas a** | Integrante 5 (TLS) y la verificación de la UI |
| **Tu rama** | `feat/k8s` |

**Orden de trabajo:**
1. T7 — instala k3s. **Obligatorio: `--disable=traefik`.** Traefik ocupa los puertos 80 y 443 y haría fallar a certbot el día 3 sin dar un error comprensible.
2. **No te saltes el paso 5 del runbook 02.** Es el `curl` desde un pod hacia MLflow. Si eso falla, todo el despliegue posterior falla y habrás perdido horas buscando en el sitio equivocado.
3. T10 — los manifiestos. Se validan en seco con `--dry-run=client` sin necesidad de la imagen.
4. T11 — despliegue real, cuando el integrante 2 te entregue la imagen.
5. T13 — las 4 demostraciones. **Ensáyalas más de una vez**: pueden pedírtelas en vivo.

**Tu parte de la defensa:** cómo se demuestra el balanceo; qué hace la Downward API; por qué `imagePullPolicy: IfNotPresent`; qué pasa exactamente cuando borras un pod.

---

### Integrante 4 — Drift

| | |
|---|---|
| **Tareas** | T14 (detectores), T15 (generadores), T16 (puerta), T17 (monitor) |
| **Necesitas antes de empezar** | `src/features.py` del integrante 1 |
| **Bloqueas a** | A nadie — eres la rama más independiente del proyecto |
| **Tu rama** | `feat/drift` |

**Orden de trabajo:**
1. T14 — detectores. Empieza por los tests de fórmula con valores calculados a mano; son los que demuestran que entiendes la matemática.
2. T15 — generadores de lotes.
3. T16 — la puerta CLI.
4. T17 — concept drift, criterio de reentrenamiento y gráfica.

**Trabajas sin depender del VPS hasta el final.** Solo necesitas MLflow para el paso 5 de T17 (cargar el modelo real y medir su degradación).

**Entiende bien esta distinción, porque es la pregunta trampa:** hay **dos artefactos distintos**. La *puerta* (`drift/check.py`) sale en rojo con datos derivados — eso es lo que pide el enunciado. La *suite de pytest* está **toda en verde**, porque verifica que la puerta funciona. Preséntalos en ese orden: primero pytest en verde, luego la puerta en verde y en rojo.

**Tu parte de la defensa:** de dónde sale el umbral 0.25 del PSI; por qué KS y no un t-test; por qué exigís tamaño del efecto además del p-valor; por qué 3 lotes consecutivos; qué hacéis con el retraso de etiquetas.

---

### Integrante 5 — Infraestructura, TLS, UI y documentación

| | |
|---|---|
| **Tareas** | T6 (MLflow + PostgreSQL), T12 (TLS), T18 (UI web), T20 (documentación) |
| **Necesitas antes de empezar** | Nada. Eres el primero en moverte. |
| **Bloqueas a** | **A todos.** Sin MLflow no hay integración posible. |
| **Tu rama** | `feat/infra` |

**Orden de trabajo:**
1. **Los registros DNS, ahora mismo.** `churn.juanitodev.com` y `mlflow.juanitodev.com` a la IP del VPS. Es lo único que no puedes acelerar.
2. T6 — MLflow y PostgreSQL. Avisa al grupo en cuanto responda; hay tres personas esperándote.
3. T12 — nginx y certbot (día 3, cuando el integrante 3 tenga el servicio desplegado).
4. T18 — la UI web.
5. T20 — la documentación de entrega.

**Tres trampas que están documentadas en tus runbooks. No las improvises:**
- MLflow debe publicarse en `0.0.0.0`, **no** en `127.0.0.1`. Los pods de k3s llegan por la interfaz de flannel, no por loopback: si lo atas a loopback, ningún pod arranca.
- MLflow debe arrancar con `--serve-artifacts`. Sin esa bandera los pods no pueden descargar el modelo.
- `ufw` **no** cierra el puerto 5000: las publicaciones de puertos de Docker se saltan sus reglas. Hay que usar la cadena `DOCKER-USER`. Y luego **verificarlo desde fuera del VPS**, no desde dentro.

**Tu parte de la defensa:** por qué MLflow fuera del clúster; por qué nginx en el host y no un Ingress; por qué dos subdominios y no rutas; cómo se cierra realmente un puerto con Docker de por medio.

---

## 5. Calendario y puntos de sincronización

| Día | Integrante 1 | Integrante 2 | Integrante 3 | Integrante 4 | Integrante 5 |
|---|---|---|---|---|---|
| **1** | T2, **T3** | **T1**, schemas | *espera* → T7 | *espera* → T14 | **DNS**, T6 |
| **2** | T4, T5 | T8, T9 | T10 | T15, T16 | apoyo |
| **3** | apoyo | apoyo | **T11**, T13 | T17 | T12 |
| **4** | **T19** | apoyo | T19 | cierre T17 | T18 |
| **5** | revisión | revisión | evidencias | evidencias | **T20** |
| **6** | ensayo | ensayo | ensayo | ensayo | ensayo |

El día 6 es ensayo de defensa cruzada con los cinco presentes (§8).

### Los cuatro momentos en que el equipo se sincroniza

| Cuándo | Qué se anuncia | Quién queda desbloqueado |
|---|---|---|
| Día 1, ~3h | `src/features.py` está en `main` | Integrantes 2 y 4 |
| Día 1, ~4h | MLflow responde en el VPS | Integrantes 1, 2 y 3 |
| Día 1, fin | El modelo dummy está registrado con alias `champion` | Integrante 2 (verificación end-to-end) |
| Día 3 | El servicio está desplegado en k3s | Integrantes 5 (TLS) y 3 (demos) |

### Cierre de cada día (15 minutos, los cinco)

1. Cada uno empuja su rama y dice en una frase qué terminó.
2. Se nombra en voz alta cualquier bloqueo — **no se espera al día siguiente para decirlo**.
3. Se ejecuta `pytest -v` sobre `main` y debe estar en verde.

---

## 6. Si te bloqueas

| Situación | Qué hacer |
|---|---|
| Esperas `features.py` y no llega | Escribe tus tests contra la interfaz documentada en el plan (sección **Interfaces** de cada tarea). Los nombres y tipos ya están definidos ahí. |
| Esperas que MLflow esté arriba | Todas las tareas de código funcionan con MLflow en fichero o con mocks. Solo la integración final necesita el servidor. |
| Esperas la imagen para desplegar | Valida los manifiestos con `kubectl apply --dry-run=client`. |
| Esperas el modelo bueno | Trabaja contra el dummy registrado el día 1. Cuando llegue el real, no cambia una sola línea de código. |
| Un test falla y no entiendes por qué | Mira las notas de diagnóstico del plan: T11 tiene una tabla de síntomas y causas, y T14 explica el caso de las comparaciones múltiples. |

---

## 7. Reglas de git

**El historial de commits es la evidencia del reparto declarado.** El enunciado (§2) dice explícitamente que se revisará.

- Cada uno trabaja en **su rama** (`feat/modelo`, `feat/api`, `feat/k8s`, `feat/drift`, `feat/infra`).
- Commitea **con tu propio usuario de git**. Verifica antes de empezar:
  ```bash
  git config user.name
  git config user.email
  ```
- Commits frecuentes y pequeños, en español, con prefijo (`feat:`, `test:`, `docs:`, `fix:`, `chore:`).
- **No commitees por otro.** Si ayudas a alguien, que commitee esa persona, o usa `Co-Authored-By:`.
- `infra/.env` **nunca** se commitea. Solo `infra/.env.example`.

Verificación del reparto antes de entregar:
```bash
git shortlog -sne
```

---

## 8. Día 6 — preparación de la defensa

**La defensa es individual y cubre cualquier parte del proyecto, no solo la tuya** (enunciado §2). Este día no es opcional.

### Ejercicio de defensa cruzada

Cada integrante explica al resto **la parte de otro**, no la suya:

| Explica | La parte de |
|---|---|
| Integrante 1 | Kubernetes (#3) |
| Integrante 2 | Drift (#4) |
| Integrante 3 | Infraestructura y TLS (#5) |
| Integrante 4 | Modelo y MLflow (#1) |
| Integrante 5 | API y contenedor (#2) |

Quien construyó esa parte corrige y completa. Si alguien no puede explicar la parte que le tocó, esa es exactamente la pregunta que va a fallar en la defensa.

### Las cinco preguntas que cualquiera debe saber responder

1. **¿Cómo demostráis que el modelo que sirve peticiones es el del experimento que enseñáis?**
   Abriendo `https://churn.juanitodev.com/model-info` y comparando el `run_id` con el de la versión del Model Registry en `https://mlflow.juanitodev.com`. Son el mismo.

2. **¿Por qué ROC-AUC y no accuracy?**
   El dataset tiene 26,5 % de positivos: predecir siempre "no abandona" da 73,5 % de accuracy sin aprender nada. Además ROC-AUC no depende del umbral de decisión.

3. **¿De dónde sale el umbral del PSI?**
   De la escala convencional de las *scorecards* crediticias, donde nació el índice: `<0.10` estable, `0.10–0.25` moderado, `>0.25` significativo.

4. **¿Por qué exigís tamaño del efecto además del p-valor?**
   Con n = 7.043 el test KS rechaza la hipótesis nula ante diferencias sin relevancia práctica. Significancia estadística no es lo mismo que relevancia práctica; sin el filtro del efecto, el monitor alertaría a diario y nadie le haría caso.

5. **En producción la etiqueta real tarda ~30 días. ¿Qué hacéis mientras tanto?**
   El ROC-AUC por lote solo se puede calcular en retrospectiva. Mientras llegan las etiquetas se vigila con tres proxies que no las necesitan: data drift de las entradas, *prediction drift* (KS sobre la distribución de scores) y la tasa de positivos predichos.

### Ensayo técnico

Recorrer en vivo, cronometrado, los runbooks `05` (demos de Kubernetes), `06` (MLflow) y `07` (drift). Si algo tarda más de lo previsto o falla, es mejor descubrirlo hoy.
