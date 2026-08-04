# drift/tests/test_monitor.py
import pytest

from drift.monitor import (
    AUC_DROP_THRESHOLD, CONSECUTIVE_BATCHES, first_alarm_index,
    plot_auc_timeline, retraining_alarm,
)

BASELINE = 0.85


def test_sin_caida_no_hay_alarma():
    aucs = [0.85, 0.84, 0.85, 0.83, 0.84, 0.85]
    assert not retraining_alarm(aucs, BASELINE)


def test_un_solo_lote_malo_no_dispara_la_alarma():
    """La condición de persistencia evita reentrenar por ruido.

    Un reentrenamiento innecesario tiene coste real, así que la estabilidad
    del criterio importa tanto como su sensibilidad.
    """
    aucs = [0.85, 0.84, 0.60, 0.85, 0.84, 0.85]
    assert not retraining_alarm(aucs, BASELINE)


def test_dos_lotes_malos_seguidos_tampoco_disparan():
    aucs = [0.85, 0.60, 0.61, 0.85, 0.84, 0.85]
    assert not retraining_alarm(aucs, BASELINE)


def test_tres_lotes_malos_seguidos_disparan_la_alarma():
    aucs = [0.85, 0.84, 0.60, 0.61, 0.62, 0.85]
    assert retraining_alarm(aucs, BASELINE)


def test_la_caida_debe_superar_el_umbral():
    """Una caída de 0.02 no supera el umbral de 0.05 aunque sea sostenida."""
    aucs = [0.85, 0.83, 0.83, 0.83, 0.83, 0.83]
    assert not retraining_alarm(aucs, BASELINE)


def test_first_alarm_index_señala_el_tercer_lote_de_la_racha():
    aucs = [0.85, 0.84, 0.60, 0.61, 0.62, 0.85]
    assert first_alarm_index(aucs, BASELINE) == 4


def test_first_alarm_index_es_none_sin_alarma():
    assert first_alarm_index([0.85] * 6, BASELINE) is None


def test_los_umbrales_son_los_documentados():
    assert AUC_DROP_THRESHOLD == 0.05
    assert CONSECUTIVE_BATCHES == 3


def test_plot_genera_el_fichero(tmp_path):
    destino = tmp_path / "grafica.png"
    resultado = plot_auc_timeline([0.85, 0.84, 0.70, 0.65, 0.60, 0.58], BASELINE, destino)
    assert resultado.exists()
    assert resultado.stat().st_size > 1000
