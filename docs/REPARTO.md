# Reparto del trabajo

El enunciado (§2) establece que el historial de commits se revisa como
evidencia del reparto declarado.

## Tabla de responsabilidades

| # | Integrante | Componente | Ficheros principales | Rama |
|---|---|---|---|---|
| 1 | **Cristhian** | Modelo y MLflow | `src/features.py`, `src/train.py`, `src/register.py`, `scripts/download_data.py`, runbook 06 | `Modelo_y_MLflow` |
| 2 | **Ronal Callisaya** | API y contenedor | `src/api/`, `Dockerfile`, `requirements.txt`, `pytest.ini` | `Api-Contenedor` |
| 3 | **Perseo Andrade** | Kubernetes | `k8s/`, `scripts/demo_balanceo.sh`, runbooks 02, 03, 05 | `Kubernetes` |
| 4 | **Ricardo Pari** y **Erika Uriona** | Detección de drift | `drift/` completo, runbook 07 | `feat/drift`, `Drift` |
| 5 | **Juanito Ortega** | Infraestructura, TLS, UI y documentación | `infra/`, `src/api/static/`, runbooks 01, 04, `docs/` | `main` |

## Verificación

```bash
git shortlog -sne
git log --format='%an | %s' --reverse
```

El fichero `.mailmap` unifica las identidades de quienes commitearon desde más
de un equipo, para que el recuento anterior refleje el reparto real.

---

## Notas de honestidad sobre el historial

Se documentan aquí en lugar de dejar que el docente las descubra:

- **Las ramas no siguen la convención inicial.** El plan preveía
  `feat/modelo`, `feat/api`, `feat/k8s`, `feat/infra`; en la práctica se usaron
  los nombres de la tabla. La correspondencia es la indicada.
- **El rol #4 está desequilibrado.** La mayoría de los commits de `drift/` son
  de Ricardo. La rama `Drift` se integró como histórica porque no llegó a
  tener contenido utilizable.
- **Parte de la integración final la centralizó el integrante #5** para
  resolver conflictos entre ramas y dejar `main` en verde.

> **Recordatorio del enunciado (§2):** la defensa es **individual** y cubre
> **cualquier** parte del proyecto, no solo la que cada integrante construyó.
> Ver el ejercicio de defensa cruzada en [`EQUIPO.md`](EQUIPO.md) §8.
