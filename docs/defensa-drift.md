# Guion de defensa — Detección de drift (rol #4)

Qué decir, en qué orden, y con qué números. El runbook `07-demo-drift.md`
tiene los comandos; esto es el discurso que los acompaña.

---

## 1. La frase de apertura (30 segundos)

> "Mi parte responde a una pregunta: **¿cómo sabemos que el modelo que está
> en producción sigue siendo válido?** Construimos dos cosas distintas: una
> **puerta de calidad** que bloquea lotes con datos derivados, y un
> **monitor** que vigila la degradación de la métrica en el tiempo. Son dos
> mecanismos porque detectan dos problemas distintos, y uno solo no basta."

Esa frase ya contiene la distinción data drift / concept drift, que es lo
que el enunciado califica en la Fase 4. Dila antes de tocar el teclado.

---

## 2. El guion de la demo (5 minutos)

### Paso 1 — La suite en verde

```bash
pytest drift/ -v
```
**39 tests PASS.**

> "Empiezo por aquí porque demuestra que los detectores funcionan y está
> probado. Dos de estos tests comparan el PSI que implementamos contra un
> valor **calculado a mano**: no llamamos a una librería, implementamos la
> fórmula y la verificamos."

Si te piden ver uno, abre `test_psi_valor_calculado_a_mano_cambio_pequeno`:
PSI de [50/50] a [60/40] = 0.0405465, calculado con la fórmula
`Σ (pct_actual − pct_esperado) × ln(pct_actual / pct_esperado)`.

### Paso 2 — La puerta en verde

```bash
python -m drift.check --batch data/batches/lote_0.csv ; echo "exit=$?"
```
**VERDE, exit=0.**

> "El lote 0 es el control: sale del mismo origen que el entrenamiento.
> Treinta y cinco pruebas, ninguna alerta."

### Paso 3 — La puerta en rojo

```bash
python -m drift.check --batch data/batches/lote_3.csv ; echo "exit=$?"
```
**ROJO, exit=1.** Deriva en `Contract` y `MonthlyCharges`.

| Variable | Prueba | Estadístico | Umbral |
|---|---|---|---|
| `MonthlyCharges` | KS | D = 0.2547 (p < 0.0001) | 0.10 |
| `Contract` | PSI | 5.8073 | 0.25 |
| `Contract` | Chi² | V = 0.2498 (p < 0.0001) | 0.10 |

> "Inyectamos deliberadamente una subida de tarifas del 25 % y un cambio en
> la mezcla de contratos. La puerta lo detecta y devuelve código de salida
> 1, que es lo que permite usarla en un pipeline automático."

### Paso 4 — El golpe de efecto: la puerta es ciega al concept drift

```bash
python -m drift.check --batch data/batches/lote_1.csv ; echo "exit=$?"
```
**VERDE, exit=0** — y sin embargo el ROC-AUC del lote 1 ya cayó de 0.853
a 0.795.

> "Este es el punto más importante de mi parte. La puerta dice que todo
> está bien porque las **entradas** son idénticas al origen. Pero el modelo
> ya se está equivocando más, porque lo que cambió es la **relación** entre
> entradas y salida. Eso es concept drift, y ninguna prueba sobre las
> entradas lo puede ver. Por eso hace falta el segundo mecanismo."

Nadie más del curso va a tener esta demostración. Ensáyala.

### Paso 5 — El monitor y la alarma

```bash
python -m drift.monitor
```

```
Baseline (lote 0): 0.8530
  Lote 1: ROC-AUC=0.7952  caída=+0.0578  <-- por debajo del umbral
  Lote 2: ROC-AUC=0.7482  caída=+0.1048  <-- por debajo del umbral
  Lote 3: ROC-AUC=0.7195  caída=+0.1335  <-- por debajo del umbral
  Lote 4: ROC-AUC=0.6849  caída=+0.1681  <-- por debajo del umbral
  Lote 5: ROC-AUC=0.6532  caída=+0.1998  <-- por debajo del umbral

ALARMA: procede reentrenar (lote 3)
```

Mostrar `docs/evidencias/concept_drift.png`.

> "El criterio es: caída de más de 0.05 absolutos respecto al baseline,
> **sostenida durante 3 lotes consecutivos**. Aquí se cumple en el lote 3,
> que es donde se completa la tercera caída seguida. La condición de
> persistencia no es decorativa: sin ella, un solo lote ruidoso dispararía
> un reentrenamiento que cuesta dinero."

---

## 3. Las cuatro decisiones que tienes que poder justificar

### a) Por qué KS para las numéricas

Es **no paramétrico**: no asume normalidad. `MonthlyCharges` es claramente
**bimodal** — hay dos poblaciones, clientes con y sin servicio de internet.
Un t-test asumiría una campana que no existe y compararía solo medias. KS
compara las **funciones de distribución acumulada completas**.

### b) Por qué PSI + Chi² para las categóricas

- **PSI** da una **magnitud interpretable** (no un sí/no) y es el estándar
  en estabilidad de poblaciones.
- **Chi²** aporta la **significancia estadística**.
- **Cramér's V** aporta el **tamaño del efecto** para el Chi².

Cada una responde una pregunta distinta: *¿cuánto cambió?*, *¿es casualidad?*,
*¿importa?*

### c) De dónde sale cada umbral

| Umbral | Valor | Origen |
|---|---|---|
| PSI | > 0.25 alerta, > 0.10 aviso | Escala convencional de las *scorecards* crediticias, donde nació el índice |
| p-valor | < 0.05 | Nivel de significancia convencional |
| KS efecto | D > 0.10 | **Decisión propia**, ver abajo |
| Cramér's V | > 0.10 | Misma lógica que el anterior |
| Caída de AUC | > 0.05 absoluto, 3 lotes | Compromiso entre sensibilidad y estabilidad |

### d) Por qué exigimos tamaño del efecto además del p-valor

**Este es el argumento más fuerte de toda la Fase 4. Apréndetelo.**

> "Con n = 7.043, el test KS rechaza la hipótesis nula ante diferencias que
> no tienen ninguna relevancia práctica: es hipersensible al tamaño
> muestral. Si alertáramos solo por p-valor, el monitor gritaría todos los
> días y en dos semanas nadie le haría caso — que es la forma más común de
> que un sistema de monitoreo muera. Exigir además un tamaño del efecto
> mínimo separa *estadísticamente significativo* de *prácticamente
> relevante*."

Hay un test que lo demuestra:
`test_ks_no_alerta_por_diferencia_trivial_aunque_sea_significativa` — con
50.000 muestras y una diferencia de medias de 0.15, el p-valor es
significativo pero D < 0.10, así que **no** alerta.

Bonus si quieres rematar, pero **solo si estás seguro del dato**: de las 35
pruebas que corre la puerta, **19 usan p-valor** (3 KS + 16 Chi²; el PSI no
usa p-valor, se juzga por magnitud). Con α = 0.05 y 19 pruebas, la
probabilidad de al menos un falso positivo por puro azar es
`1 − 0.95¹⁹ ≈ 62 %`. El filtro de tamaño del efecto es también lo que
controla ese problema de comparaciones múltiples.

---

## 3 bis. Qué es cada cosa (para explicarlo en voz alta)

### El p-valor

**Qué es:** la probabilidad de observar una diferencia **al menos tan grande
como la que veo**, *suponiendo que en realidad no hubiera ninguna
diferencia*.

**Cómo lo dices:**
> "Si el lote nuevo viniera de la misma población que el entrenamiento,
> ¿qué probabilidad habría de ver una diferencia como esta por pura
> casualidad? Si es menor al 5 %, concluyo que la diferencia no es azar."

**El 0.05 no tiene nada de mágico:** es una convención heredada de la
estadística clásica. Lo elegimos porque es lo estándar y porque **no es el
criterio que de verdad decide** — el que decide es el tamaño del efecto.

**⚠ Trampa clásica:** el p-valor **NO** es "la probabilidad de que no haya
drift". Es al revés: es la probabilidad de los **datos** suponiendo que no
hay drift. Si te preguntan esto y respondes mal, se nota.

### KS — Kolmogorov-Smirnov (variables numéricas)

**Qué es:** compara las dos **distribuciones acumuladas** — la del baseline
y la del lote — y mide la **máxima distancia vertical** entre ambas curvas.
Esa distancia es el estadístico **D**, que va de 0 a 1.

**Cómo lo dices:**
> "Dibujo la curva acumulada de `MonthlyCharges` en el entrenamiento y la
> del lote nuevo. D es la separación máxima entre las dos curvas. D = 0
> significa distribuciones idénticas; D = 0.25 significa que en el punto de
> mayor divergencia hay 25 puntos porcentuales de población de diferencia."

**Por qué KS y no un t-test:** el t-test compara **medias** y asume
normalidad. `MonthlyCharges` es **bimodal** (clientes con y sin internet),
así que la media no representa a nadie. KS es **no paramétrico** y compara
las distribuciones **enteras**.

**Nuestro número:** lote 3 → D = 0.2547 en `MonthlyCharges`.

### PSI — Índice de Estabilidad Poblacional (variables categóricas)

**Qué es:** mide **cuánto se movió** el reparto de una variable entre el
baseline y el lote. No da un sí/no: da una **magnitud**.

```
PSI = Σ (pct_actual − pct_esperado) × ln(pct_actual / pct_esperado)
```

**Cómo lo dices:**
> "Para cada categoría comparo qué porcentaje representaba antes y qué
> porcentaje representa ahora. La diferencia, ponderada por el logaritmo de
> la razón entre ambas, se suma sobre todas las categorías. Cuanto más se
> movió el reparto, mayor el PSI."

**No tiene p-valor** — es una medida de magnitud, no una prueba de
hipótesis. Por eso su umbral es un valor absoluto y no un 0.05.

**La escala** viene de las *scorecards* crediticias, que es donde nació el
índice: `< 0.10` población estable, `0.10 – 0.25` cambio moderado que
amerita vigilancia, `> 0.25` cambio significativo que exige acción.

**Para numéricas** el PSI necesita bins: usamos **10 cuantiles del
baseline**.

**Nuestro número:** lote 3 → PSI = 5.81 en `Contract`. Es enorme porque la
deriva inyectada convirtió casi todos los contratos a "Month-to-month", de
modo que "One year" y "Two year" casi desaparecieron.

### Chi-cuadrado (variables categóricas)

**Qué es:** una prueba de hipótesis sobre una **tabla de contingencia**.
Contrasta si las proporciones de las categorías son las mismas en el
baseline y en el lote, o si difieren más de lo que cabría esperar por azar.
Devuelve un **p-valor**.

**Cómo lo dices:**
> "El PSI me dice **cuánto** cambió el reparto; el Chi² me dice si ese
> cambio es **estadísticamente distinguible del azar**. Se complementan."

**Su debilidad:** es muy sensible al tamaño muestral — con muchos datos
detecta como significativa cualquier diferencia mínima. Por eso lo
acompañamos de Cramér's V.

### Cramér's V — el tamaño del efecto del Chi²

**Qué es:** convierte el estadístico Chi² en una medida **de 0 a 1**
independiente del tamaño muestral. 0 = ninguna asociación, 1 = asociación
perfecta.

```
V = √( χ² / (n × (mín(filas, columnas) − 1)) )
```

**Cómo lo dices:**
> "El Chi² crece con el número de observaciones, así que su valor bruto no
> es interpretable. Cramér's V lo normaliza por n, y por eso sí se puede
> comparar entre variables y poner un umbral fijo."

**Nuestro número:** lote 3 → V = 0.2498 en `Contract`.

### La idea que une todo: significancia ≠ relevancia

| | Pregunta que responde | Herramienta |
|---|---|---|
| **Significancia** | ¿Es real o es azar? | p-valor (KS, Chi²) |
| **Tamaño del efecto** | ¿Es lo bastante grande para importar? | D, Cramér's V, PSI |

**Alertamos solo cuando se cumplen las dos.** Con n = 7.043, exigir solo
significancia produciría alertas diarias por diferencias irrelevantes, y un
monitor que grita todos los días acaba ignorado.

### ROC-AUC y el criterio de reentrenamiento

**Qué es el ROC-AUC:** la probabilidad de que, tomando un cliente que
abandonó y uno que no, el modelo dé **más puntuación al que abandonó**.
0.5 = azar puro; 1.0 = perfecto.

**Cómo lo dices:**
> "Es la capacidad del modelo de **ordenar**: no depende del umbral de
> decisión y no se deja engañar por el desbalance. Con 26,5 % de positivos,
> un modelo que diga siempre 'no abandona' saca 73,5 % de accuracy sin
> haber aprendido nada — pero su ROC-AUC sería 0.5."

**El criterio:** caída de **más de 0.05 absolutos** respecto al baseline,
**sostenida durante 3 lotes consecutivos**. Los dos ingredientes tienen
propósitos distintos: la **magnitud** filtra caídas irrelevantes, la
**persistencia** filtra el ruido de un lote puntual.

---

## 4. Las preguntas trampa

**"Si la prueba tiene que fallar con datos derivados, ¿por qué tu pytest
sale todo verde?"**

> "Porque son **dos artefactos distintos**. La *puerta* (`drift/check.py`)
> es lo que el enunciado califica: sale roja con datos derivados, y se lo
> acabo de mostrar. La *suite de pytest* verifica que la puerta funciona —
> si un test se pusiera rojo ante datos derivados, significaría que el
> detector **no** detecta. Un detector que funciona hace que su test pase."

**"En producción la etiqueta real tarda 30 días. ¿Cómo calculas el ROC-AUC?"**

> "No se puede. El monitoreo que acabo de mostrar solo funciona en
> retrospectiva. Mientras llegan las etiquetas vigilamos con tres proxies
> que no las necesitan:
> 1. **Data drift de las entradas** — es un indicador adelantado.
> 2. **Prediction drift** — KS sobre la distribución de los *scores* que
>    emite el modelo. Si el modelo empieza a puntuar distinto, algo pasó.
> 3. **Tasa de positivos predichos** — si predice 40 % de abandono donde
>    históricamente predecía 26 %, algo cambió aunque nadie pueda
>    confirmarlo todavía."

**"¿Por qué 3 lotes y no 1, o 5?"**

> "Un reentrenamiento tiene coste real: cómputo, validación y riesgo de
> meter un modelo peor. Uno solo dispararía por ruido. Cinco tardaría
> demasiado en reaccionar. Tres es el compromiso, y está probado en las dos
> direcciones: `test_un_solo_lote_malo_no_dispara_la_alarma` y
> `test_tres_lotes_malos_seguidos_disparan_la_alarma`."

**"¿Por qué el baseline del monitor es el lote 0 y no el AUC de test?"**

> "Porque el lote 0 comparte tamaño y condiciones de medición con los demás
> lotes, así que la comparación es homogénea. El ROC-AUC del conjunto de
> test queda en MLflow como referencia del entrenamiento."

**"¿Por qué implementaron el PSI a mano en vez de usar Evidently o similar?"**

> "Porque el enunciado exige justificar cada prueba y cada umbral. Una
> librería opaca no se puede defender: si me preguntan cómo hace el binning
> o qué pasa cuando una categoría desaparece, tengo que poder responder. En
> nuestro caso el binning son 10 cuantiles del baseline y hay un epsilon de
> 1e-6 para evitar la división por cero."

**"¿Qué pasa si una categoría del baseline no aparece en el lote?"**

> "El epsilon evita la división por cero, y el término contribuye ~6.5 al
> PSI, muy por encima del umbral. Es correcto que dispare: una categoría
> que desaparece es un cambio de población grande. Hay un test que lo
> cubre: `test_psi_no_revienta_si_falta_una_categoria`."

---

## 5. Preguntas de OTRAS partes que te pueden caer

**La defensa es individual y cubre todo el proyecto, no solo tu parte**
(enunciado §2). Las tres que más probablemente te toquen:

**"¿Por qué ROC-AUC y no accuracy?"**
El dataset tiene 26,5 % de positivos: predecir siempre "no abandona" da
73,5 % de accuracy sin aprender nada. Además ROC-AUC no depende del umbral
de decisión, así que permite comparar modelos sin fijar antes una política
de negocio.

**"¿Cómo demuestran que el modelo que sirve peticiones es el del experimento?"**
Abriendo `/model-info` del servicio y comparando el `run_id` con el de la
versión del Model Registry en la UI de MLflow. Son el mismo. El pod carga
el modelo por alias (`models:/telco-churn@champion`), no por ruta de
fichero.

**"¿Cómo se demuestra el balanceo de carga?"**
Cada pod recibe su nombre por la Downward API en `POD_NAME` y lo devuelve
en `served_by` en cada respuesta. Diez peticiones seguidas muestran nombres
distintos.

---

## 6. Qué tener abierto en pantalla antes de empezar

1. Terminal en la raíz del proyecto, con el venv activado y
   `MLFLOW_TRACKING_URI` exportado.
2. **Los lotes ya generados** (`python -m drift.generators`) — no están
   versionados, y generarlos en vivo son 30 segundos de silencio incómodo.
3. `docs/evidencias/concept_drift.png` abierto en un visor.
4. La UI de MLflow en otra pestaña, por si preguntan por la trazabilidad.

**Ensaya el recorrido completo cronometrado al menos dos veces.** Si algo
tarda más de lo previsto, es mejor descubrirlo el día 6 que en la defensa.

---

> **Nota sobre los números.** Los valores de este documento salen de una
> corrida contra el modelo `telco-churn` v2 (`gb-lr0.05`, ROC-AUC de test
> 0.8452). Como la semilla, el split y los datos son fijos, deben
> reproducirse igual contra el MLflow del VPS. Si al regenerar la gráfica
> el día 4 salieran distintos, actualizar esta tabla y el runbook 07.
