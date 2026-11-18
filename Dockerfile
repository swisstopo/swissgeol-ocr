FROM python:3.14-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ghostscript gcc \
 && rm -rf /var/lib/apt/lists/*

 RUN useradd --create-home appuser \
  && mkdir -p /app \
  && chown appuser /app
USER appuser
WORKDIR /app

RUN python -m venv /home/appuser/venv
ENV PATH="/home/appuser/venv/bin:$PATH"

COPY --chown=appuser requirements.txt .
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir -r requirements.txt

COPY --chown=appuser . .

# Unset PYTHONPATH so /otel-auto-instrumentation-python (if injected via the
# OTel operator / opentelemetry-instrument) never lands on sys.path and its
# sitecustomize.py is never loaded. Everything needed is in the venv.
ENTRYPOINT ["env", "-u", "PYTHONPATH", "fastapi", "run", "api.py"]