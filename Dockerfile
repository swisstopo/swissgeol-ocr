FROM python:3.12-alpine3.19

RUN apk add --no-cache ghostscript

WORKDIR /app
COPY api.py .
COPY aws .
COPY ocr .
COPY utils .
COPY requirements.txt .

RUN pip install -r requirements.txt
ENTRYPOINT ["fastapi", "run", "api.py"]