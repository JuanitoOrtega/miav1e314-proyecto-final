# Runbook 06 — Demostración en vivo de MLflow

**Responsable:** integrante #1 (Cristhian) · **Cubre:** §3.4 del enunciado

El enunciado exige poder hacer cuatro cosas frente al docente, con la interfaz
operativa. Ensayarlas antes.

**URL:** `https://mlflow.juanitodev.com` · usuario `mlops`

---

## 1. Abrir el experimento y explicar qué representa cada run

Experimento: **`telco-churn-experimento`**, seis runs.

| Run | Modelo | Hiperparámetro variado |
|---|---|---|
| `logreg-C0.1` | LogisticRegression | `C=0.1` |
| `logreg-C1.0` | LogisticRegression | `C=1.0` |
| `rf-100-d5` | RandomForest | `n_estimators=100, max_depth=5` |
| `rf-300-d10` | RandomForest | `n_estimators=300, max_depth=10` |
| `gb-lr0.05` | GradientBoosting | `learning_rate=0.05` |
| `gb-lr0.2` | GradientBoosting | `learning_rate=0.2` |

**El punto a transmitir:** los seis son comparables porque comparten split,
semilla (`random_state=42`) y el mismo conjunto de métricas. Sin eso,
compararlos no significaría nada.

---

## 2. Ordenar y filtrar por la métrica principal

Pulsar la cabecera de la columna `roc_auc` para ordenar de mayor a menor.

**Pregunta segura: *¿por qué ROC-AUC y no accuracy?***

El dataset tiene un 26,5 % de positivos. Un modelo que prediga siempre "no
abandona" alcanza un 73,5 % de accuracy sin haber aprendido nada. ROC-AUC es
además insensible al umbral de decisión, lo que permite comparar modelos sin
haber fijado antes una política de negocio.

Se registran también F1 y recall porque el coste de un falso negativo —un
cliente que se va sin ser detectado— supera al de un falso positivo.

---

## 3. Comparar varios runs

Seleccionar los seis con las casillas y pulsar **Compare**. Usar la vista de
coordenadas paralelas.

**Aquí conviene ser honesto, y suma puntos serlo.** Los seis modelos quedan
entre 0,839 y 0,845 de ROC-AUC: esa diferencia es ruido, no señal. Decir "se
eligió el de mayor AUC" es un argumento débil y el docente puede desmontarlo.

El argumento sólido es: *"con rendimiento estadísticamente equivalente, el
criterio de desempate razonable no es el tercer decimal del AUC, sino la
simplicidad del modelo o el recall de la clase positiva, que es la que tiene
coste de negocio"*.

---

## 4. Abrir el Model Registry

**Models → `telco-churn`.** Mostrar:

- Las **dos versiones** registradas, que evidencian comprensión del versionado.
- El alias **`champion`** apuntando a la versión desplegada.

---

## 5. Cerrar el círculo de la trazabilidad

Este es el momento clave de la fase 1. Abrir en otra pestaña:

```
https://churn.juanitodev.com/model-info
```

Comparar el `run_id` que devuelve el servicio con el de la versión marcada en
el Model Registry. **Son el mismo.**

Eso demuestra literalmente lo que pide §3.3 del enunciado: existe trazabilidad
entre el modelo que está sirviendo peticiones en el clúster y el experimento
exacto que lo produjo.

Explicar además que el servicio lo consume **por alias**, no por ruta de
fichero:

```python
mlflow.sklearn.load_model("models:/telco-churn@champion")
```

Promover un modelo nuevo a producción es mover el alias y ejecutar
`kubectl rollout restart`. No se reconstruye la imagen ni se toca código.

---

## Preguntas previsibles

**¿Por qué MLflow está fuera del clúster?**
Es infraestructura de soporte, no la carga desplegada. Meterlo en k3s exigiría
`StatefulSet` y `PersistentVolumeClaim` sin aportar nada a lo que se evalúa.
Además así se ve que el servicio *dentro* de Kubernetes consulta un registry
*externo*, que es el patrón real.

**¿Qué pasa si MLflow se cae?**
Los pods que ya están sirviendo siguen funcionando: el modelo está en memoria.
Un pod nuevo no arrancaría, pero el `readinessProbe` lo mantiene fuera del
`Service`, así que no recibe tráfico y los sanos siguen atendiendo.

**¿Dónde se guardan los artefactos?**
En un volumen de Docker, servidos por el propio MLflow con `--serve-artifacts`.
Sin esa bandera, `artifact_location` sería una ruta del sistema de ficheros del
servidor y los pods no podrían descargar el modelo, porque esa ruta no existe
dentro de su contenedor.

**¿Por qué dos versiones registradas y no una?**
Para evidenciar que se entiende el versionado. La v1 es la línea base lineal y
la v2 el modelo elegido. El alias permite cambiar cuál sirve en producción sin
tocar nada más.
