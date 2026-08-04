"""Puerta de calidad de data drift.

Verde (exit 0) con datos del mismo origen que el entrenamiento.
Rojo  (exit 1) cuando se inyecta deriva deliberadamente.

Este es el artefacto que responde al requisito §6.1 del enunciado. Los tests
de pytest son otra cosa: verifican que ESTA puerta se comporta como debe.
"""
import argparse
import sys
from pathlib import Path

import pandas as pd

from drift.detectors import DriftResult, detect_data_drift
from src.features import ALL_FEATURES, clean, load_raw, split_data

BASELINE_CSV = "data/telco_churn.csv"


def load_baseline() -> pd.DataFrame:
    """El baseline es siempre el conjunto de entrenamiento."""
    X_train, _, _, _ = split_data(clean(load_raw(BASELINE_CSV)))
    return X_train


def run_check(batch_path: str | Path) -> tuple[list[DriftResult], bool]:
    """Evalúa un lote contra el baseline. Devuelve (resultados, hay_deriva)."""
    baseline = load_baseline()
    lote = pd.read_csv(batch_path)
    # El roundtrip por CSV devuelve SeniorCitizen como entero; el baseline
    # la trata como categórica en texto.
    lote["SeniorCitizen"] = lote["SeniorCitizen"].astype(str)

    resultados = detect_data_drift(baseline, lote[ALL_FEATURES])
    return resultados, any(r.drifted for r in resultados)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Puerta de detección de data drift")
    parser.add_argument("--batch", required=True, help="Ruta al CSV del lote a evaluar")
    args = parser.parse_args(argv)

    resultados, hay_deriva = run_check(args.batch)

    print(f"\nLote evaluado: {args.batch}")
    print(f"Baseline:      {BASELINE_CSV} (conjunto de entrenamiento)")
    print("-" * 78)
    for resultado in resultados:
        print(resultado)
    print("-" * 78)

    derivadas = sorted({r.variable for r in resultados if r.drifted})
    if hay_deriva:
        print(f"ROJO — deriva detectada en {len(derivadas)} variable(s): {', '.join(derivadas)}")
        return 1

    print("VERDE — sin deriva significativa")
    return 0


if __name__ == "__main__":
    sys.exit(main())
