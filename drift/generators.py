"""Construcción de lotes limpios y con deriva inyectada de forma controlada.

El lote 0 es el control: sale del mismo origen que el entrenamiento y debe
pasar en verde. Los lotes 1 a 5 llevan deriva creciente.
"""
from pathlib import Path

import pandas as pd

from src.features import RANDOM_STATE, TARGET


def make_clean_batch(
    df: pd.DataFrame, n: int = 500, random_state: int = RANDOM_STATE
) -> pd.DataFrame:
    """Muestra sin deriva, del mismo origen que el entrenamiento."""
    return df.sample(n=min(n, len(df)), random_state=random_state).reset_index(drop=True)


def inject_numeric_shift(
    df: pd.DataFrame, column: str = "MonthlyCharges", pct: float = 0.25
) -> pd.DataFrame:
    """Sube una variable numérica un porcentaje fijo.

    Historia de negocio: una subida general de tarifas.
    """
    derivado = df.copy()
    derivado[column] = derivado[column] * (1 + pct)
    return derivado


def inject_categorical_shift(
    df: pd.DataFrame,
    column: str = "Contract",
    target: str = "Month-to-month",
    pct: float = 0.5,
    random_state: int = RANDOM_STATE,
) -> pd.DataFrame:
    """Reasigna una fracción de las filas a una categoría concreta.

    Historia de negocio: una campaña comercial empuja a los clientes hacia
    contratos mensuales.
    """
    derivado = df.copy()
    candidatas = derivado.index[derivado[column] != target]
    n_cambiar = int(len(derivado) * pct)
    if n_cambiar > 0 and len(candidatas) > 0:
        elegidas = (
            pd.Series(candidatas)
            .sample(n=min(n_cambiar, len(candidatas)), random_state=random_state)
            .to_numpy()
        )
        derivado.loc[elegidas, column] = target
    return derivado


def inject_concept_drift(
    df: pd.DataFrame,
    mask_column: str = "Contract",
    mask_value: str = "Two year",
    flip_pct: float = 0.3,
    random_state: int = RANDOM_STATE,
) -> pd.DataFrame:
    """Invierte la etiqueta de una fracción de un subgrupo.

    Historia de negocio: un cambio de política de permanencia hace que los
    contratos largos dejen de proteger contra el abandono.

    Las variables de entrada NO se tocan: esa es exactamente la diferencia
    entre concept drift y data drift.
    """
    derivado = df.copy()
    subgrupo = derivado.index[derivado[mask_column] == mask_value]
    n_invertir = int(len(subgrupo) * flip_pct)
    if n_invertir > 0:
        elegidas = (
            pd.Series(subgrupo).sample(n=n_invertir, random_state=random_state).to_numpy()
        )
        derivado.loc[elegidas, TARGET] = 1 - derivado.loc[elegidas, TARGET]
    return derivado


def generate_all_batches(
    df: pd.DataFrame, out_dir: str | Path = "data/batches", n: int = 500
) -> list[Path]:
    """Genera los 6 lotes con deriva creciente y los guarda como CSV.

    | Lote | Contenido                                          |
    |------|----------------------------------------------------|
    | 0    | Limpio. Control: debe salir verde.                  |
    | 1    | Concept drift leve (10% de etiquetas invertidas).   |
    | 2    | Concept drift medio (20%).                          |
    | 3    | Concept drift (30%) + data drift: tarifas y mezcla. |
    | 4    | Data drift más fuerte + concept drift (40%).        |
    | 5    | Deriva severa en ambos ejes (50%).                  |

    El concept drift crece 10/20/30/40/50 % de forma SOSTENIDA en los lotes
    1 a 5 (spec §9.4). Que ningún lote intermedio se salte la inversión es
    lo que permite que la racha de 3 lotes consecutivos por debajo del
    umbral llegue a completarse y dispare la alarma de reentrenamiento.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    base = make_clean_batch(df, n=n)
    rutas: list[Path] = []

    # En los lotes 3, 4 y 5 el concept drift se aplica PRIMERO. El shift
    # categórico convierte a Month-to-month todas las filas que no lo son,
    # así que si se aplicara antes, el subgrupo 'Two year' quedaría vacío y
    # inject_concept_drift no invertiría ninguna etiqueta.
    lotes = [
        base,
        inject_concept_drift(base, flip_pct=0.10),
        inject_concept_drift(base, flip_pct=0.20),
        inject_categorical_shift(
            inject_numeric_shift(inject_concept_drift(base, flip_pct=0.30), pct=0.25),
            pct=0.5,
        ),
        inject_categorical_shift(
            inject_numeric_shift(inject_concept_drift(base, flip_pct=0.40), pct=0.35),
            pct=0.6,
        ),
        inject_categorical_shift(
            inject_numeric_shift(inject_concept_drift(base, flip_pct=0.50), pct=0.50),
            pct=0.8,
        ),
    ]

    for indice, lote in enumerate(lotes):
        ruta = out_dir / f"lote_{indice}.csv"
        lote.to_csv(ruta, index=False)
        rutas.append(ruta)
        print(f"Generado {ruta} ({len(lote)} filas)")

    return rutas


def main() -> None:
    from src.features import clean, load_raw, split_data

    df = clean(load_raw("data/telco_churn.csv"))
    _, X_test, _, y_test = split_data(df)
    reserva = X_test.copy()
    reserva[TARGET] = y_test
    generate_all_batches(reserva)


if __name__ == "__main__":
    main()
