# drift/tests/test_generators.py
import pandas as pd
import pytest

from drift.detectors import detect_data_drift
from drift.generators import (
    generate_all_batches, inject_categorical_shift, inject_concept_drift,
    inject_numeric_shift, make_clean_batch,
)
from src.features import TARGET, clean, load_raw, split_data


@pytest.fixture(scope="module")
def datos():
    df = clean(load_raw("data/telco_churn.csv"))
    X_tr, X_te, y_tr, y_te = split_data(df)
    baseline = X_tr
    reserva = X_te.copy()
    reserva[TARGET] = y_te
    return baseline, reserva


def test_lote_limpio_tiene_el_tamano_pedido(datos):
    _, reserva = datos
    assert len(make_clean_batch(reserva, n=300)) == 300


def test_lote_limpio_es_reproducible(datos):
    _, reserva = datos
    a = make_clean_batch(reserva, n=200, random_state=42)
    b = make_clean_batch(reserva, n=200, random_state=42)
    pd.testing.assert_frame_equal(a, b)


def test_lote_limpio_no_dispara_deriva(datos):
    """VERDE: datos del mismo origen que el entrenamiento."""
    baseline, reserva = datos
    lote = make_clean_batch(reserva, n=500)
    assert not any(r.drifted for r in detect_data_drift(baseline, lote))


def test_desplazamiento_numerico_sube_la_media(datos):
    _, reserva = datos
    lote = make_clean_batch(reserva, n=500)
    derivado = inject_numeric_shift(lote, "MonthlyCharges", pct=0.25)
    assert derivado["MonthlyCharges"].mean() > lote["MonthlyCharges"].mean() * 1.2


def test_desplazamiento_numerico_dispara_ks(datos):
    """ROJO: la variable desplazada debe detectarse."""
    baseline, reserva = datos
    derivado = inject_numeric_shift(make_clean_batch(reserva, n=500), "MonthlyCharges", 0.25)
    resultados = detect_data_drift(baseline, derivado)
    ks_charges = [r for r in resultados if r.variable == "MonthlyCharges" and r.test == "ks"]
    assert ks_charges[0].drifted


def test_cambio_categorico_dispara_psi(datos):
    """ROJO: el cambio de mezcla en Contract debe detectarse."""
    baseline, reserva = datos
    derivado = inject_categorical_shift(make_clean_batch(reserva, n=500), "Contract", pct=0.6)
    resultados = detect_data_drift(baseline, derivado)
    psi_contract = [r for r in resultados if r.variable == "Contract" and r.test == "psi"]
    assert psi_contract[0].drifted


def test_concept_drift_invierte_etiquetas_del_subconjunto(datos):
    _, reserva = datos
    lote = make_clean_batch(reserva, n=500)
    derivado = inject_concept_drift(lote, flip_pct=0.5)
    cambiadas = (lote[TARGET].to_numpy() != derivado[TARGET].to_numpy()).sum()
    assert cambiadas > 0


def test_concept_drift_no_toca_las_variables_de_entrada(datos):
    """Es lo que distingue el concept drift del data drift."""
    _, reserva = datos
    lote = make_clean_batch(reserva, n=500)
    derivado = inject_concept_drift(lote, flip_pct=0.5)
    entradas = [c for c in lote.columns if c != TARGET]
    pd.testing.assert_frame_equal(lote[entradas], derivado[entradas])


def test_generate_all_batches_crea_6_ficheros(datos, tmp_path):
    _, reserva = datos
    rutas = generate_all_batches(reserva, out_dir=tmp_path, n=300)
    assert len(rutas) == 6
    assert all(p.exists() for p in rutas)
    assert rutas[0].name == "lote_0.csv"


def test_los_lotes_4_y_5_llevan_concept_drift(datos, tmp_path):
    """Regresión: el shift categórico elimina el subgrupo 'Two year', así que
    el concept drift debe inyectarse ANTES. Si el orden se invirtiera, estos
    lotes saldrían sin ninguna etiqueta cambiada y la gráfica del monitor no
    mostraría la degradación que dispara la alarma."""
    _, reserva = datos
    rutas = generate_all_batches(reserva, out_dir=tmp_path, n=300)
    lote_0 = pd.read_csv(rutas[0])
    for indice in (4, 5):
        lote = pd.read_csv(rutas[indice])
        cambiadas = (lote_0[TARGET].to_numpy() != lote[TARGET].to_numpy()).sum()
        assert cambiadas > 0, f"lote_{indice} no tiene etiquetas invertidas"
