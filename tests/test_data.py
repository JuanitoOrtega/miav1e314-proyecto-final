"""Tests de calidad del dataset crudo.

Documentan los supuestos sobre los datos de los que depende todo lo demás.
Si el CSV cambiara, estos tests lo detectan antes que el entrenamiento.
"""
from pathlib import Path

import pandas as pd

CSV = Path("data/telco_churn.csv")


def test_dataset_existe():
    assert CSV.exists(), "Ejecuta: python scripts/download_data.py"


def test_dimensiones_esperadas():
    df = pd.read_csv(CSV)
    assert df.shape == (7043, 21)


def test_columnas_esperadas():
    df = pd.read_csv(CSV)
    esperadas = {
        "customerID", "gender", "SeniorCitizen", "Partner", "Dependents",
        "tenure", "PhoneService", "MultipleLines", "InternetService",
        "OnlineSecurity", "OnlineBackup", "DeviceProtection", "TechSupport",
        "StreamingTV", "StreamingMovies", "Contract", "PaperlessBilling",
        "PaymentMethod", "MonthlyCharges", "TotalCharges", "Churn",
    }
    assert set(df.columns) == esperadas


def test_tasa_de_churn_conocida():
    """~26,5 % de positivos. Es lo que justifica usar ROC-AUC y no accuracy."""
    df = pd.read_csv(CSV)
    tasa = (df["Churn"] == "Yes").mean()
    assert 0.26 < tasa < 0.27


def test_totalcharges_tiene_blancos_conocidos():
    """Documenta el problema de calidad: 11 blancos, todos con tenure = 0.

    Son clientes que nunca han sido facturados. src.features.clean los imputa
    con 0.0, que es el valor semánticamente correcto.
    """
    df = pd.read_csv(CSV)
    blancos = df["TotalCharges"].astype(str).str.strip() == ""
    assert blancos.sum() == 11
    assert (df.loc[blancos, "tenure"] == 0).all()
