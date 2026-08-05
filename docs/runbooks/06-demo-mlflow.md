# Runbook 06 — Demo en vivo de MLflow

Responsable: integrante #1. El enunciado (§3.4) exige poder hacer estas cuatro
cosas frente al docente. Ensayarlas.

URL: `https://mlflow.<dominio>` — usuario `docente`, contraseña anotada en el
runbook 04.

---

## 1. Abrir el experimento y explicar qué representa cada run

Experimento **`telco-churn-experimento`**, 6 runs.

Explicar que los 6 comparten **split, semilla y conjunto de métricas**, y que
eso es exactamente lo que los hace comparables entre sí.

| Run | Modelo | Hiperparámetro |
|---|---|---|
| `logreg-C0.1` / `logreg-C1.0` | Regresión logística | Regularización `C` |
| `rf-100-d5` / `rf-300-d10` | Random Forest | Nº de árboles y profundidad |
| `gb-lr0.05` / `gb-lr0.2` | Gradient Boosting | Tasa de aprendizaje |

## 2. Ordenar y filtrar por la métrica principal

Pulsar la columna `roc_auc` para ordenar descendente. Gana **`gb-lr0.05`** con
**0.8452**.

Tener lista la respuesta a *"¿por qué ROC-AUC y no accuracy?"*: el dataset
tiene 26,5 % de positivos, así que un modelo que prediga siempre "no abandona"
saca 73,5 % de accuracy sin aprender nada. Además ROC-AUC es insensible al
umbral de decisión.

## 3. Comparar varios runs

Seleccionar los 6 con las casillas → botón **Compare**. Usar la vista de
coordenadas paralelas para argumentar por qué se eligió el modelo desplegado.

Observación honesta y defendible: **las diferencias son pequeñas** (0.8386 a
0.8452). Eso es normal en este dataset y no resta valor: el proyecto evalúa la
ingeniería alrededor del modelo, no exprimir la métrica.

## 4. Abrir el Model Registry

**Models → `telco-churn`**. Mostrar las 2 versiones y que el alias `champion`
apunta a la v2.

## 5. Cerrar el círculo de la trazabilidad

Abrir en otra pestaña `https://churn.<dominio>/model-info` y comparar el
`run_id` que devuelve con el de la versión del registro. **Son el mismo.**

> Esa es la trazabilidad que pide el enunciado (§3.3): el modelo que está
> sirviendo peticiones y el experimento exacto que lo produjo.

---

## Cómo se promueve un modelo nuevo (por si preguntan)

```bash
python -c "from src.register import set_champion; set_champion(3)"
kubectl rollout restart deployment/telco-churn-api
```

Mover el alias y reiniciar. **No se reconstruye la imagen**, porque el modelo
no vive dentro de ella.
