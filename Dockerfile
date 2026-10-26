# syntax=docker/dockerfile:1

FROM node:20-slim AS frontend-builder
WORKDIR /code
RUN apt-get update && apt-get install -y --no-install-recommends rsync && rm -rf /var/lib/apt/lists/*
COPY package.json .
COPY digital-land-frontend.config.json .
COPY rollup.config.js .
COPY src/ src/
RUN npm install

FROM python:3.13-slim
WORKDIR /code

# DevelopmentConfig turns authentication off, so it must be asked for explicitly
# (docker-compose.yml does) rather than being what a deployment gets by default.
ENV FLASK_CONFIG=application.config.Config
ENV FLASK_APP=application.wsgi:app

ENV FLASK_RUN_HOST=0.0.0.0
ENV FLASK_RUN_PORT=5050

# No system packages are added: every Python requirement is either a prebuilt
# wheel or pure Python, so no compiler is needed. No PostgreSQL client either: the app
# reaches the database through psycopg2-binary, and loading a local backup
# (scripts/docker-load-data.sh) runs in the postgres image, see docker-compose.yml.
COPY --from=frontend-builder /code/application/static/ application/static/
COPY . .
RUN pip install -r requirements/requirements.txt
EXPOSE 5050

ENTRYPOINT ["./docker-entrypoint.sh"]
# The debug server must never run in a deployed environment: its debugger runs
# arbitrary code from the browser. docker-compose.yml overrides this for local work.
CMD ["gunicorn", "--bind", "0.0.0.0:5050", "--workers", "2", "--threads", "4", "--access-logfile", "-", "application.wsgi:app"]
