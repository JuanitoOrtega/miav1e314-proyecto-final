"""Esquema del dataset, limpieza y preprocesamiento.

Este módulo es la ÚNICA definición del preprocesamiento. El mismo
ColumnTransformer se serializa dentro del modelo MLflow, de modo que el
servicio de inferencia nunca reimplementa la transformación. Es lo que
evita el train/serve skew.
"""
from pathlib import Path

import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import OneHotEncoder, StandardScaler

RANDOM_STATE = 42
TEST_SIZE = 0.2
TARGET = "Churn"
ID_COLUMN = "customerID"
MODEL_NAME = "telco-churn"
EXPERIMENT_NAME = "telco-churn-experimento"

NUMERIC_FEATURES = ["tenure", "MonthlyCharges", "TotalCharges"]

CATEGORICAL_FEATURES = [
    "gender", "SeniorCitizen", "Partner", "Dependents", "PhoneService",
    "MultipleLines", "InternetService", "OnlineSecurity", "OnlineBackup",
    "DeviceProtection", "TechSupport", "StreamingTV", "StreamingMovies",
    "Contract", "PaperlessBilling", "PaymentMethod",
]

ALL_FEATURES = NUMERIC_FEATURES + CATEGORICAL_FEATURES


def load_raw(path: str | Path) -> pd.DataFrame:
    """Lee el CSV crudo sin transformar nada."""
    return pd.read_csv(path)


def clean(df: pd.DataFrame) -> pd.DataFrame:
    """Aplica las dos correcciones de calidad conocidas del dataset.

    1. TotalCharges viene como texto y contiene 11 cadenas vacías, todas de
       clientes con tenure = 0 que nunca han sido facturados. Se imputan con
       0.0, que es el valor semánticamente correcto.
    2. Churn viene como 'Yes'/'No' y se convierte a 1/0.
    3. SeniorCitizen viene como entero 0/1 pero es conceptualmente
       categórica, así que se pasa a texto para que el OneHotEncoder la trate
       como tal.
    """
    df = df.copy()
    df["TotalCharges"] = pd.to_numeric(df["TotalCharges"], errors="coerce").fillna(0.0)
    df[TARGET] = (df[TARGET] == "Yes").astype(int)
    df["SeniorCitizen"] = df["SeniorCitizen"].astype(str)
    return df


def build_preprocessor() -> ColumnTransformer:
    """Escala las numéricas y aplica one-hot a las categóricas.

    handle_unknown='ignore' es deliberado: en producción puede llegar una
    categoría que no existía al entrenar, y el servicio debe responder en
    lugar de reventar.
    """
    return ColumnTransformer(
        transformers=[
            ("num", StandardScaler(), NUMERIC_FEATURES),
            (
                "cat",
                OneHotEncoder(handle_unknown="ignore", sparse_output=False),
                CATEGORICAL_FEATURES,
            ),
        ],
        remainder="drop",
    )


def split_data(
    df: pd.DataFrame,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.Series, pd.Series]:
    """División estratificada 80/20 con semilla fija."""
    X = df[ALL_FEATURES]
    y = df[TARGET]
    return train_test_split(
        X, y, test_size=TEST_SIZE, random_state=RANDOM_STATE, stratify=y
    )