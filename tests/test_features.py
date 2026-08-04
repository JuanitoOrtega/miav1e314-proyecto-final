# tests/test_features.py
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer

from src.features import (
    ALL_FEATURES, CATEGORICAL_FEATURES, NUMERIC_FEATURES, TARGET,
    build_preprocessor, clean, load_raw, split_data,
)


@pytest.fixture(scope="module")
def df_limpio():
    return clean(load_raw("data/telco_churn.csv"))


def test_hay_3_numericas_y_16_categoricas():
    assert len(NUMERIC_FEATURES) == 3
    assert len(CATEGORICAL_FEATURES) == 16
    assert len(ALL_FEATURES) == 19


def test_customerid_no_es_feature():
    assert "customerID" not in ALL_FEATURES


def test_clean_convierte_target_a_entero(df_limpio):
    assert df_limpio[TARGET].dtype.kind in "iu"
    assert set(df_limpio[TARGET].unique()) == {0, 1}


def test_clean_convierte_totalcharges_a_float(df_limpio):
    assert df_limpio["TotalCharges"].dtype.kind == "f"
    assert df_limpio["TotalCharges"].isna().sum() == 0


def test_clean_imputa_los_11_blancos_con_cero(df_limpio):
    sin_antiguedad = df_limpio[df_limpio["tenure"] == 0]
    assert len(sin_antiguedad) == 11
    assert (sin_antiguedad["TotalCharges"] == 0.0).all()


def test_split_es_estratificado_y_reproducible(df_limpio):
    X_tr, X_te, y_tr, y_te = split_data(df_limpio)
    assert len(X_tr) + len(X_te) == len(df_limpio)
    assert abs(y_tr.mean() - y_te.mean()) < 0.01
    X_tr2, _, _, _ = split_data(df_limpio)
    pd.testing.assert_frame_equal(X_tr, X_tr2)


def test_split_solo_devuelve_features(df_limpio):
    X_tr, _, _, _ = split_data(df_limpio)
    assert list(X_tr.columns) == ALL_FEATURES


def test_preprocesador_transforma_sin_nan(df_limpio):
    X_tr, _, _, _ = split_data(df_limpio)
    pre = build_preprocessor()
    assert isinstance(pre, ColumnTransformer)
    matriz = pre.fit_transform(X_tr)
    assert matriz.shape[0] == len(X_tr)
    assert matriz.shape[1] > len(ALL_FEATURES)  # el one-hot expande


def test_preprocesador_tolera_categoria_no_vista(df_limpio):
    """handle_unknown='ignore' evita que una categoría nueva rompa producción."""
    X_tr, X_te, _, _ = split_data(df_limpio)
    pre = build_preprocessor().fit(X_tr)
    fila = X_te.iloc[[0]].copy()
    fila["Contract"] = "Contrato inventado"
    assert pre.transform(fila).shape[0] == 1