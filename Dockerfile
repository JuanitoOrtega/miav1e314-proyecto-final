# Etapa de construcción: instala las dependencias en un prefijo aislado
#
# Se fija la variante -bookworm en lugar de usar python:3.11-slim a secas:
# el tag flotante saltó a Debian trixie y los repositorios cambiaron, lo que
# rompía el build sin previo aviso. Fijar la distribución lo hace reproducible.
FROM python:3.11-slim-bookworm AS builder

WORKDIR /build

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt

# Etapa final: solo lo necesario en tiempo de ejecución
FROM python:3.11-slim-bookworm

# Sin apt-get: 'useradd' ya viene en la imagen base y el HEALTHCHECK usa
# Python en lugar de curl. Así el build no depende de la red de Debian,
# la imagen queda más pequeña y hay menos superficie que parchear.
RUN useradd --create-home --shell /bin/bash appuser

COPY --from=builder /install /usr/local

WORKDIR /app
COPY --chown=appuser:appuser src/ ./src/

USER appuser

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://localhost:8000/health', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
