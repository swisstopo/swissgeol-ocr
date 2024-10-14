FROM python:3.12-alpine3.19

RUN apk add --no-cache ghostscript

WORKDIR /app
COPY aws .
COPY ocr .
COPY utils .
COPY api.py .
COPY requirements.txt .

RUN pip install --root-user-action=ignore -r requirements.txt
ENTRYPOINT ["fastapi", "run", "api.py"]