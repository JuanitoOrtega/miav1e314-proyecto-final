# drift/tests/test_detectors.py
import numpy as np
import pandas as pd
import pytest

from drift.detectors import (
    KS_MIN_EFFECT, PSI_ALERT, DriftResult, chi2_detector, cramers_v,
    detect_data_drift, ks_detector, psi, psi_detector,
)

RNG = np.random.default_rng(42)


# --- Tests unitarios de las fórmulas -----------------------------------
# Demuestran que entendemos la matemática, no solo que llamamos a scipy.

def test_psi_valor_calculado_a_mano_cambio_pequeno():
    """PSI de [50%,50%] a [60%,40%].

    PSI = (0.6-0.5)*ln(0.6/0.5) + (0.4-0.5)*ln(0.4/0.5) = 0.0405465
    Por debajo de 0.10: población estable.
    """
    base = pd.Series(["A"] * 50 + ["B"] * 50)
    actual = pd.Series(["A"] * 60 + ["B"] * 40)
    assert psi(base, actual) == pytest.approx(0.0405465, abs=1e-6)


def test_psi_valor_calculado_a_mano_cambio_grande():
    """PSI de [50%,50%] a [90%,10%].

    PSI = 0.4*ln(1.8) + (-0.4)*ln(0.2) = 0.8788898
    Muy por encima de 0.25: cambio significativo.

    Tolerancia 1e-4 y no 1e-6: el epsilon anti división-por-cero de la
    implementación perturba el valor exacto en ~3.5e-6.
    """
    base = pd.Series(["A"] * 50 + ["B"] * 50)
    actual = pd.Series(["A"] * 90 + ["B"] * 10)
    assert psi(base, actual) == pytest.approx(0.8788898, abs=1e-4)


def test_psi_de_una_serie_contra_si_misma_es_cero():
    serie = pd.Series(["A"] * 30 + ["B"] * 50 + ["C"] * 20)
    assert psi(serie, serie) == pytest.approx(0.0, abs=1e-9)


def test_psi_no_revienta_si_falta_una_categoria():
    """El epsilon evita la división por cero cuando una categoría desaparece."""
    base = pd.Series(["A"] * 50 + ["B"] * 50)
    actual = pd.Series(["A"] * 100)
    valor = psi(base, actual)
    assert np.isfinite(valor)
    assert valor > PSI_ALERT


def test_cramers_v_sin_asociacion_es_cercano_a_cero():
    tabla = np.array([[50, 50], [50, 50]])
    assert cramers_v(tabla) == pytest.approx(0.0, abs=1e-9)


def test_cramers_v_asociacion_perfecta_es_uno():
    tabla = np.array([[100, 0], [0, 100]])
    assert cramers_v(tabla) == pytest.approx(1.0, abs=1e-6)


# --- Detector KS -------------------------------------------------------

def test_ks_no_alerta_con_la_misma_distribucion():
    base = pd.Series(RNG.normal(50, 10, 2000))
    actual = pd.Series(RNG.normal(50, 10, 2000))
    r = ks_detector(base, actual, "x")
    assert isinstance(r, DriftResult)
    assert r.test == "ks"
    assert not r.drifted


def test_ks_alerta_con_desplazamiento_grande():
    base = pd.Series(RNG.normal(50, 10, 2000))
    actual = pd.Series(RNG.normal(70, 10, 2000))
    assert ks_detector(base, actual, "x").drifted


def test_ks_no_alerta_por_diferencia_trivial_aunque_sea_significativa():
    """El criterio del tamaño del efecto es la clave del diseño.

    Con n grande, KS rechaza H0 ante diferencias sin relevancia práctica.
    Exigir D > 0.10 filtra ese ruido y evita un monitor que grita a diario.
    """
    base = pd.Series(RNG.normal(50, 10, 50000))
    actual = pd.Series(RNG.normal(50.15, 10, 50000))
    r = ks_detector(base, actual, "x")
    assert r.statistic < KS_MIN_EFFECT
    assert not r.drifted


# --- Detectores categóricos -------------------------------------------

def test_psi_detector_no_alerta_con_mezcla_similar():
    base = pd.Series(["A"] * 500 + ["B"] * 300 + ["C"] * 200)
    actual = pd.Series(["A"] * 490 + ["B"] * 310 + ["C"] * 200)
    assert not psi_detector(base, actual, "cat").drifted


def test_psi_detector_alerta_con_mezcla_invertida():
    base = pd.Series(["A"] * 800 + ["B"] * 200)
    actual = pd.Series(["A"] * 200 + ["B"] * 800)
    r = psi_detector(base, actual, "cat")
    assert r.drifted
    assert r.statistic > PSI_ALERT


def test_chi2_alerta_con_cambio_de_proporciones():
    base = pd.Series(["A"] * 800 + ["B"] * 200)
    actual = pd.Series(["A"] * 300 + ["B"] * 700)
    r = chi2_detector(base, actual, "cat")
    assert r.test == "chi2"
    assert r.drifted


# --- Orquestador -------------------------------------------------------

def test_detect_data_drift_cubre_las_19_variables():
    from src.features import clean, load_raw, split_data
    X_tr, X_te, _, _ = split_data(clean(load_raw("data/telco_churn.csv")))
    resultados = detect_data_drift(X_tr, X_te.head(500))

    # 3 numéricas con KS + 16 categóricas con PSI y Chi2
    assert len([r for r in resultados if r.test == "ks"]) == 3
    assert len([r for r in resultados if r.test == "psi"]) == 16
    assert len([r for r in resultados if r.test == "chi2"]) == 16


def test_detect_data_drift_no_alerta_entre_train_y_test():
    """Train y test salen del mismo origen: no debe haber deriva."""
    from src.features import clean, load_raw, split_data
    X_tr, X_te, _, _ = split_data(clean(load_raw("data/telco_churn.csv")))
    resultados = detect_data_drift(X_tr, X_te)
    assert not any(r.drifted for r in resultados)
