"""Detectores estadísticos de data drift.

Implementación propia y no una librería de terceros, porque el enunciado
exige justificar por qué se eligió cada prueba y de dónde sale cada umbral.
Una librería opaca no se puede defender.
"""
from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy import stats

from src.features import CATEGORICAL_FEATURES, NUMERIC_FEATURES

# --- Umbrales y su justificación --------------------------------------
# ALPHA: nivel de significancia convencional.
ALPHA = 0.05

# KS_MIN_EFFECT: con n grande, KS rechaza H0 ante diferencias irrelevantes
# en la práctica. Exigir además un tamaño del efecto mínimo separa
# "estadísticamente significativo" de "prácticamente relevante".
KS_MIN_EFFECT = 0.10

# CRAMERS_V_MIN: misma lógica que KS_MIN_EFFECT pero para Chi². Es un
# umbral propio porque V y D son estadísticos distintos, y la tabla de la
# puerta debe mostrar cada estadístico contra su umbral real.
CRAMERS_V_MIN = 0.10

# PSI: escala convencional de las scorecards crediticias, donde nació el
# índice. <0.10 estable, 0.10-0.25 moderado, >0.25 cambio significativo.
PSI_WARN = 0.10
PSI_ALERT = 0.25

EPSILON = 1e-6


@dataclass
class DriftResult:
    """Resultado de una prueba sobre una variable."""

    variable: str
    test: str
    statistic: float
    p_value: float | None
    threshold: float
    drifted: bool

    def __str__(self) -> str:
        estado = "DERIVA" if self.drifted else "ok"
        p = f"p={self.p_value:.4f}" if self.p_value is not None else "p=n/a"
        return (
            f"{self.variable:<20} {self.test:<5} "
            f"stat={self.statistic:>8.4f} {p:<12} "
            f"umbral={self.threshold:<6} {estado}"
        )


def psi(baseline: pd.Series, current: pd.Series, bins: int = 10) -> float:
    """Índice de estabilidad poblacional.

    PSI = Σ (pct_actual − pct_esperado) × ln(pct_actual / pct_esperado)

    Para variables numéricas los bins se derivan de los cuantiles del
    baseline. Se suma un epsilon a las proporciones para evitar la división
    por cero cuando una categoría no aparece en el lote actual.
    """
    if pd.api.types.is_numeric_dtype(baseline):
        cortes = np.unique(np.quantile(baseline, np.linspace(0, 1, bins + 1)))
        cortes[0], cortes[-1] = -np.inf, np.inf
        base_binned = pd.cut(baseline, bins=cortes)
        curr_binned = pd.cut(current, bins=cortes)
        categorias = base_binned.cat.categories
        base_pct = base_binned.value_counts(normalize=True).reindex(categorias, fill_value=0)
        curr_pct = curr_binned.value_counts(normalize=True).reindex(categorias, fill_value=0)
    else:
        categorias = sorted(set(baseline.unique()) | set(current.unique()))
        base_pct = baseline.value_counts(normalize=True).reindex(categorias, fill_value=0)
        curr_pct = current.value_counts(normalize=True).reindex(categorias, fill_value=0)

    b = base_pct.to_numpy() + EPSILON
    c = curr_pct.to_numpy() + EPSILON
    return float(np.sum((c - b) * np.log(c / b)))


def cramers_v(contingency: np.ndarray) -> float:
    """Tamaño del efecto para tablas de contingencia. Rango [0, 1]."""
    chi2 = stats.chi2_contingency(contingency, correction=False)[0]
    n = contingency.sum()
    min_dim = min(contingency.shape) - 1
    if n == 0 or min_dim == 0:
        return 0.0
    return float(np.sqrt(chi2 / (n * min_dim)))


def ks_detector(
    baseline: pd.Series,
    current: pd.Series,
    name: str,
    alpha: float = ALPHA,
    min_effect: float = KS_MIN_EFFECT,
) -> DriftResult:
    """Kolmogorov-Smirnov para variables numéricas.

    Se eligió KS porque es no paramétrico y no asume normalidad:
    MonthlyCharges es claramente bimodal (clientes con y sin internet), así
    que un t-test sería inválido. KS compara las distribuciones acumuladas
    completas, no solo la media.

    Alerta solo si hay significancia estadística Y tamaño del efecto.
    """
    estadistico, p_valor = stats.ks_2samp(baseline, current)
    return DriftResult(
        variable=name,
        test="ks",
        statistic=float(estadistico),
        p_value=float(p_valor),
        threshold=min_effect,
        drifted=bool(p_valor < alpha and estadistico > min_effect),
    )


def psi_detector(
    baseline: pd.Series, current: pd.Series, name: str, threshold: float = PSI_ALERT
) -> DriftResult:
    """PSI para variables categóricas. Da magnitud interpretable, no un sí/no."""
    valor = psi(baseline, current)
    return DriftResult(
        variable=name,
        test="psi",
        statistic=valor,
        p_value=None,
        threshold=threshold,
        drifted=bool(valor > threshold),
    )


def chi2_detector(
    baseline: pd.Series, current: pd.Series, name: str, alpha: float = ALPHA
) -> DriftResult:
    """Chi-cuadrado de independencia, con Cramér's V como tamaño del efecto."""
    categorias = sorted(set(baseline.unique()) | set(current.unique()))
    tabla = np.array([
        baseline.value_counts().reindex(categorias, fill_value=0).to_numpy(),
        current.value_counts().reindex(categorias, fill_value=0).to_numpy(),
    ])

    columnas_no_vacias = tabla.sum(axis=0) > 0
    tabla = tabla[:, columnas_no_vacias]

    if tabla.shape[1] < 2:
        return DriftResult(name, "chi2", 0.0, 1.0, CRAMERS_V_MIN, False)

    _, p_valor = stats.chi2_contingency(tabla, correction=False)[:2]
    v = cramers_v(tabla)
    # threshold es CRAMERS_V_MIN y no alpha: statistic es la V de Cramér,
    # así que la tabla de la puerta compara cada cosa con su propio umbral.
    return DriftResult(
        variable=name,
        test="chi2",
        statistic=v,
        p_value=float(p_valor),
        threshold=CRAMERS_V_MIN,
        drifted=bool(p_valor < alpha and v > CRAMERS_V_MIN),
    )


def detect_data_drift(
    baseline_df: pd.DataFrame, current_df: pd.DataFrame
) -> list[DriftResult]:
    """Aplica una prueba por tipo de variable sobre las 19 features."""
    resultados: list[DriftResult] = []

    for columna in NUMERIC_FEATURES:
        resultados.append(ks_detector(baseline_df[columna], current_df[columna], columna))

    for columna in CATEGORICAL_FEATURES:
        resultados.append(psi_detector(baseline_df[columna], current_df[columna], columna))
        resultados.append(chi2_detector(baseline_df[columna], current_df[columna], columna))

    return resultados
