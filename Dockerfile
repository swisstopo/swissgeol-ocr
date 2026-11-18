FROM python:3.14-alpine3.23

RUN apk add --quiet --no-cache ghostscript build-base

WORKDIR /app
COPY . .

RUN pip install --upgrade pip --quiet
RUN pip install --root-user-action=ignore -r requirements.txt --quiet
ENTRYPOINT ["fastapi", "run", "api.py"]