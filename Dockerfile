FROM python:3.12-alpine3.19

RUN apk add --quiet --no-cache ghostscript build-base

WORKDIR /app
COPY . .

RUN pip install --root-user-action=ignore -r requirements.txt --quiet
ENTRYPOINT ["fastapi", "run", "api.py"]