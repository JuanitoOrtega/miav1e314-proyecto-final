# drift/tests/test_check.py
import pandas as pd
import pytest

from drift.check import main, run_check
from drift.generators import generate_all_batches
from src.features import TARGET, clean, load_raw, split_data


@pytest.fixture(scope="module")
def lotes(tmp_path_factory):
    directorio = tmp_path_factory.mktemp("lotes")
    df = clean(load_raw("data/telco_churn.csv"))
    _, X_te, _, y_te = split_data(df)
    reserva = X_te.copy()
    reserva[TARGET] = y_te
    return generate_all_batches(reserva, out_dir=directorio, n=500)


def test_puerta_verde_en_lote_limpio(lotes):
    """VERDE: datos del mismo origen que el entrenamiento."""
    _, hay_deriva = run_check(lotes[0])
    assert not hay_deriva


def test_puerta_roja_en_lote_con_data_drift(lotes):
    """ROJO: el lote 3 lleva tarifas +25% y mezcla de Contract alterada."""
    resultados, hay_deriva = run_check(lotes[3])
    assert hay_deriva
    derivadas = {r.variable for r in resultados if r.drifted}
    assert "MonthlyCharges" in derivadas
    assert "Contract" in derivadas


def test_puerta_roja_en_lote_severo(lotes):
    _, hay_deriva = run_check(lotes[5])
    assert hay_deriva


def test_main_devuelve_0_con_lote_limpio(lotes):
    assert main(["--batch", str(lotes[0])]) == 0


def test_main_devuelve_1_con_lote_derivado(lotes):
    assert main(["--batch", str(lotes[3])]) == 1


def test_main_imprime_las_variables_derivadas(lotes, capsys):
    main(["--batch", str(lotes[3])])
    salida = capsys.readouterr().out
    assert "MonthlyCharges" in salida
    assert "DERIVA" in salida
