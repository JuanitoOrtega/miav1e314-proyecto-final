"""Monitoreo de concept drift y criterio de reentrenamiento.

El concept drift cambia la relación entrada-salida: las entradas pueden
verse idénticas y aun así el modelo empieza a equivocarse. Por eso no basta
con el monitoreo de data drift.
"""
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # sin display, para que funcione en el VPS
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

from src.features import ALL_FEATURES, TARGET  # noqa: E402

# --- Criterio de reentrenamiento y su justificación --------------------
# Se dispara la alarma con una caída de ROC-AUC mayor a 0.05 absolutos
# respecto al baseline, SOSTENIDA durante 3 lotes consecutivos.
#
# La condición de persistencia existe para no reentrenar por un lote
# ruidoso: un reentrenamiento innecesario tiene coste real.
AUC_DROP_THRESHOLD = 0.05
CONSECUTIVE_BATCHES = 3


def auc_per_batch(model, batch_paths: list[str | Path]) -> list[float]:
    """Calcula el ROC-AUC del modelo sobre cada lote sucesivo."""
    aucs: list[float] = []
    for ruta in batch_paths:
        lote = pd.read_csv(ruta)
        lote["SeniorCitizen"] = lote["SeniorCitizen"].astype(str)
        proba = model.predict_proba(lote[ALL_FEATURES])[:, 1]
        aucs.append(float(roc_auc_score(lote[TARGET], proba)))
    return aucs


def first_alarm_index(
    aucs: list[float],
    baseline_auc: float,
    drop: float = AUC_DROP_THRESHOLD,
    consecutive: int = CONSECUTIVE_BATCHES,
) -> int | None:
    """Índice del lote donde se completa la primera racha que dispara alarma."""
    racha = 0
    for indice, auc in enumerate(aucs):
        if baseline_auc - auc > drop:
            racha += 1
            if racha >= consecutive:
                return indice
        else:
            racha = 0
    return None


def retraining_alarm(
    aucs: list[float],
    baseline_auc: float,
    drop: float = AUC_DROP_THRESHOLD,
    consecutive: int = CONSECUTIVE_BATCHES,
) -> bool:
    """True si procede reentrenar según el criterio documentado."""
    return first_alarm_index(aucs, baseline_auc, drop, consecutive) is not None


def plot_auc_timeline(
    aucs: list[float], baseline_auc: float, out_path: str | Path
) -> Path:
    """Gráfica temporal de degradación de la métrica sobre lotes sucesivos."""
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    umbral = baseline_auc - AUC_DROP_THRESHOLD
    indices = list(range(len(aucs)))

    figura, eje = plt.subplots(figsize=(9, 5))
    eje.plot(indices, aucs, marker="o", linewidth=2, label="ROC-AUC por lote")
    eje.axhline(baseline_auc, linestyle="--", color="green", label=f"Baseline ({baseline_auc:.3f})")
    eje.axhline(umbral, linestyle=":", color="red", label=f"Umbral de alarma ({umbral:.3f})")

    alarma = first_alarm_index(aucs, baseline_auc)
    if alarma is not None:
        eje.axvline(alarma, color="red", alpha=0.25, linewidth=8)
        eje.annotate(
            "Alarma de reentrenamiento\n(3 lotes consecutivos)",
            xy=(alarma, aucs[alarma]),
            xytext=(alarma - 1.8, min(aucs) + 0.03),
            arrowprops={"arrowstyle": "->", "color": "red"},
            fontsize=9,
            color="red",
        )

    eje.set_xlabel("Índice del lote (tiempo)")
    eje.set_ylabel("ROC-AUC")
    eje.set_title("Degradación del modelo sobre lotes sucesivos — concept drift")
    eje.set_xticks(indices)
    eje.grid(alpha=0.3)
    eje.legend(loc="lower left")
    figura.tight_layout()
    figura.savefig(out_path, dpi=150)
    plt.close(figura)

    print(f"Gráfica guardada en {out_path}")
    return out_path


def main() -> None:
    """Ejecuta el monitoreo completo y guarda la gráfica de evidencia."""
    import mlflow

    from src.features import MODEL_NAME

    modelo = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}@champion")

    rutas = [Path(f"data/batches/lote_{i}.csv") for i in range(6)]
    aucs = auc_per_batch(modelo, rutas)
    baseline_auc = aucs[0]

    print(f"Baseline (lote 0): {baseline_auc:.4f}")
    for indice, auc in enumerate(aucs):
        caida = baseline_auc - auc
        marca = "  <-- por debajo del umbral" if caida > AUC_DROP_THRESHOLD else ""
        print(f"  Lote {indice}: ROC-AUC={auc:.4f}  caída={caida:+.4f}{marca}")

    if retraining_alarm(aucs, baseline_auc):
        print(f"\nALARMA: procede reentrenar (lote {first_alarm_index(aucs, baseline_auc)})")
    else:
        print("\nSin alarma: la degradación no cumple el criterio")

    plot_auc_timeline(aucs, baseline_auc, "docs/evidencias/concept_drift.png")


if __name__ == "__main__":
    main()
