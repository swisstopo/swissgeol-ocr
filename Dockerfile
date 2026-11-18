FROM python:3.14-slim

RUN apt-get update \
 && apt-get install -y --no-install-recommends ghostscript gcc \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . .

RUN pip install --root-user-action=ignore --no-cache-dir --upgrade pip \
 && pip install --root-user-action=ignore --no-cache-dir -r requirements.txt

RUN useradd --create-home appuser && chown -R appuser /app
USER appuser

ENTRYPOINT ["fastapi", "run", "api.py"]