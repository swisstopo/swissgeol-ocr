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

# disable the injected instrumentation abd strip all OTel env
ENTRYPOINT ["sh", "-c", "unset PYTHONPATH; unset $(env | grep '^OTEL_' | cut -d= -f1) 2>/dev/null; exec fastapi run api.py"]