# Runbook 07 — Demo de detección de drift

Responsable: integrante #4 (Erika y Ricardo). Presentar en este orden:
primero la suite, luego la puerta.

## 0. Generar los lotes

`data/batches/` NO está versionado (está en el `.gitignore`): hay que
generarlos en la máquina donde se hace la demo antes de empezar.

```bash
python -m drift.generators
ls data/batches/
```

Esperado: `lote_0.csv` … `lote_5.csv`, 500 filas cada uno.

| Lote | Contenido |
|---|---|
| 0 | Limpio. Control: sale verde. |
| 1 | Concept drift 10 % (entradas intactas). |
| 2 | Concept drift 20 %. |
| 3 | Concept drift 30 % + data drift (tarifas +25 %, mezcla de `Contract`). |
| 4 | Concept drift 40 % + data drift más fuerte. |
| 5 | Concept drift 50 % + deriva severa. |

> El concept drift crece de forma **sostenida** en los lotes 1 a 5. Si un
> lote intermedio se saltara la inversión, rompería la racha de 3 lotes
> consecutivos y la alarma de reentrenamiento nunca se dispararía.

## 1. La suite de tests — todo verde

```bash
pytest drift/ -v
```

Esperado: **39 tests PASS**.

Discurso: *"nuestros detectores funcionan y está probado, incluidas las
fórmulas de PSI y Cramér's V verificadas contra valores calculados a mano."*

## 2. La puerta — verde con datos limpios

```bash
python -m drift.check --batch data/batches/lote_0.csv ; echo "exit=$?"
```
Esperado: `VERDE — sin deriva significativa`, `exit=0`

## 3. La puerta — roja con datos derivados

```bash
python -m drift.check --batch data/batches/lote_3.csv ; echo "exit=$?"
```
Esperado: `ROJO — deriva detectada en 2 variable(s): Contract, MonthlyCharges`,
`exit=1`

Valores observados en la corrida de referencia:

| Variable | Prueba | Estadístico | Umbral | Veredicto |
|---|---|---|---|---|
| `MonthlyCharges` | KS | D = 0.2547 (p < 0.0001) | 0.10 | DERIVA |
| `Contract` | PSI | 5.8073 | 0.25 | DERIVA |
| `Contract` | Chi² | V = 0.2498 (p < 0.0001) | 0.10 | DERIVA |

## 3b. La puerta es ciega al concept drift (el momento fuerte de la demo)

Los lotes 1 y 2 llevan **solo** concept drift: las entradas son idénticas al
origen, así que la puerta de data drift sale **verde** aunque el modelo ya
se esté degradando (se ve en la gráfica del paso 4).

```bash
python -m drift.check --batch data/batches/lote_1.csv ; echo "exit=$?"
```
Esperado: `VERDE`, `exit=0`

Discurso: *"la puerta dice que todo está bien, y sin embargo el ROC-AUC del
lote 1 ya cayó de 0.853 a 0.795. Por eso el data drift no basta y
monitoreamos también la métrica del modelo."*

## 4. Concept drift y criterio de reentrenamiento

```bash
export MLFLOW_TRACKING_URI=http://<IP_VPS>:5000
python -m drift.monitor
```

Salida de referencia:

```
Baseline (lote 0): 0.8530
  Lote 0: ROC-AUC=0.8530  caída=+0.0000
  Lote 1: ROC-AUC=0.7952  caída=+0.0578  <-- por debajo del umbral
  Lote 2: ROC-AUC=0.7482  caída=+0.1048  <-- por debajo del umbral
  Lote 3: ROC-AUC=0.7195  caída=+0.1335  <-- por debajo del umbral
  Lote 4: ROC-AUC=0.6849  caída=+0.1681  <-- por debajo del umbral
  Lote 5: ROC-AUC=0.6532  caída=+0.1998  <-- por debajo del umbral

ALARMA: procede reentrenar (lote 3)
```

Mostrar `docs/evidencias/concept_drift.png`: la alarma se dispara en el
lote 3, que es donde se completa la tercera caída consecutiva por debajo
del umbral (baseline − 0.05 = 0.803).

## Preguntas previsibles y sus respuestas

**"¿De dónde sale el umbral de PSI 0.25?"**
De la escala convencional de las scorecards crediticias, donde nació el
índice: <0.10 estable, 0.10-0.25 moderado, >0.25 significativo.

**"¿Por qué KS y no un t-test?"**
KS es no paramétrico. `MonthlyCharges` es bimodal (clientes con y sin
internet), así que un t-test asumiría una normalidad que no existe. KS
compara las distribuciones acumuladas completas, no solo la media.

**"¿Por qué exigen D > 0.10 además del p-valor?"**
Con n = 7.043, KS rechaza H0 ante diferencias sin relevancia práctica: es
hipersensible al tamaño muestral. El tamaño del efecto separa
"estadísticamente significativo" de "prácticamente relevante". Sin eso, el
monitor alertaría a diario y nadie le haría caso.

**"¿Por qué 3 lotes consecutivos y no uno?"**
Un reentrenamiento tiene coste real. La condición de persistencia evita
dispararlo por un lote ruidoso. Hay un test específico que lo comprueba:
`test_un_solo_lote_malo_no_dispara_la_alarma`.

**"¿Por qué el baseline del monitor es el lote 0 y no el AUC de test?"**
Porque el lote 0 comparte tamaño y condiciones de medición con los demás
lotes, así que la comparación es homogénea. El ROC-AUC del conjunto de
test queda registrado en MLflow como referencia del entrenamiento.

**"¿Por qué pytest sale verde si la prueba tiene que fallar con datos derivados?"**
Son **dos artefactos distintos**. La *puerta* (`drift/check.py`) es lo que
el enunciado califica: sale roja con datos derivados. La *suite de pytest*
verifica que la puerta funciona, así que está toda en verde — un test que
se pusiera rojo ante datos derivados significaría que el detector **no**
detecta.

**"En producción la etiqueta real tarda 30 días. ¿Qué hacen mientras tanto?"**
El ROC-AUC por lote no es calculable en tiempo real, solo en retrospectiva.
Mientras llegan las etiquetas se vigila con tres proxies que no las
necesitan: (1) data drift de las entradas, que es un indicador adelantado;
(2) prediction drift, aplicando KS a la distribución de scores del modelo;
(3) la tasa de positivos predichos — si pasa del 26 % histórico al 40 %,
algo cambió aunque nadie pueda confirmarlo todavía.
