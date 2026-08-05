# Imagen del servidor MLflow.
#
# La imagen oficial de MLflow no incluye el driver de PostgreSQL, y sin él el
# servidor no puede usar la base como backend store. Se añade aquí en tiempo
# de construcción en lugar de con un 'pip install' dentro del command de
# Compose: así el arranque no depende de la red y es reproducible.
FROM ghcr.io/mlflow/mlflow:v3.15.1

RUN pip install --no-cache-dir psycopg2-binary==2.9.11

# curl para el healthcheck de Compose
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*
