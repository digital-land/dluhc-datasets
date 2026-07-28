# DLUHC Datasets

![ci workflow ](https://github.com/digital-land/dluhc-datasets/actions/workflows/ci.yml/badge.svg)

A tool to manage DLUHC's datasets. For example, the listed-building-grade dataset.


## Quick start

There are two ways to run the project locally. Docker Compose is recommended
because it supplies the application runtime, PostgreSQL database, frontend asset
builder and watcher, database migrations, and initial data loading.

### Docker Compose (recommended)

Docker Desktop (or another installation with Docker Compose) is the only local
dependency. Start the complete development environment with:

    docker compose up --build

The application is available at <http://localhost:5050>. Python and frontend
source files are mounted into their containers, so development changes are picked
up without rebuilding the images.

Stop the services with:

    docker compose down

The PostgreSQL and Node modules volumes are retained. Use
`docker compose down --volumes` only when you also want to remove the local
database and installed Node modules.

### Python

This option runs Python and Node.js directly on the host. It requires Python 3.13,
Node.js 20, PostgreSQL, PostgreSQL client tools, and the native GDAL and PROJ
libraries.

Create and activate a Python virtual environment, install the dependencies, and
create the database:

    python -m venv .venv
    source .venv/bin/activate
    make init
    createdb dluhc-datasets

Create a `.env` file containing at least:

    DATABASE_URL=postgresql:///dluhc-datasets
    SECRET_KEY=local-development-only

Apply the migrations and start Flask:

    flask db upgrade
    make run

The application is available at <http://localhost:5050>. In a second terminal,
activate the same virtual environment and start the frontend asset watcher:

    source .venv/bin/activate
    make watch

## Loading data into your local database

The repository includes a production-derived PostgreSQL dump at
`data/latest_backup.dump`. The dump was created on **31 March 2025**
from PostgreSQL 15.8, so it is a historical snapshot and may not reflect current
production data.

### Docker Compose

Compose loads the bundled dump automatically. The one-shot `load-data` service
runs [`scripts/docker-load-data.sh`](scripts/docker-load-data.sh) after PostgreSQL
becomes healthy and before the application starts. It skips the restore when the
database already contains dataset data.

To run the loader manually:

    docker compose run --rm load-data

To discard the existing Compose database and restore the dump from scratch:

    docker compose down --volumes
    docker compose up --build

### Python and local PostgreSQL

Restore the bundled dump into the local PostgreSQL database, then apply any newer
migrations:

    pg_restore --clean --if-exists --no-acl --no-owner \
      --dbname dluhc-datasets data/latest_backup.dump
    DATABASE_URL=postgresql:///dluhc-datasets flask db upgrade

This requires PostgreSQL client tools compatible with the PostgreSQL 15.8 dump.
Set `DATABASE_URL` differently if the local connection requires a username,
password, or host.

## CI & CD

The application is deployed to AWS and using our [standard CI/CD best practices](https://digital-land.github.io/technical-documentation/architecture-and-infrastructure/ci-cd-strategy/), and deployments should follow the [standard deployment procedure](https://digital-land.github.io/technical-documentation/development/deploy-and-release-procedure/).

Key github actions for this:

* Test - runs automated linting and testing on code on pushes to non main branches as well as being called by the publish action on pushes to main
* Publish (currently migrating from Deploy) - builds and publishes docker image to environments in the repo. Can be used to manually deploy to development for testing.

### Environment variables

> [!WARNING]
> These variables are from deploying to Heroku and need to be updated for deployments to AWS

```
DATABASE_URL:                [from deployment environment]
DATASETS_REPO:                digital-land/dluhc-datasets
DATASETS_REPO_REGISTERS_PATH: data/registers
FLASK_CONFIG:                 application.config.Config
GITHUB_APP_ID:                [from github application settings]
GITHUB_APP_PRIVATE_KEY:       [from github application settings]
GITHUB_CLIENT_ID:             [from github application settings]
GITHUB_CLIENT_SECRET:         [from github application settings]
PLANNING_DATA_DESIGN_URL:     https://design.planning.data.gov.uk
PLATFORM_URL:                 https://www.planning.data.gov.uk
SAFE_URLS:                    dluhc-datasets-d47c47408207.herokuapp.com,dluhc-datasets.planning-data.dev,dataset-editor.development.planning.data.gov.uk
SECRET_KEY:                   [generate for deployment env]
SPECIFICATION_REPO_URL:       https://github.com/digital-land/specification
```

## Monitoring

There is monitoring of the application via Sentry and AWS metrics. We could consider adding this to our Uptime monitor too.

## Authentication

The application uses GitHub OAuth for authentication. Only members of the `digital-land` GitHub organization can log in to the application. The authentication flow:

1. Users are redirected to GitHub to authorize the application
2. After authorization, the application checks if the user is a member of the `digital-land` organization
3. If they are a member, they are logged in
4. If they are not a member:
   - Their OAuth token is revoked
   - They are redirected back to the index page with an error message

Configuration of the application in Github is managed [here](https://github.com/organizations/digital-land/settings/installations). For the required application environment variables see the application settings -> config vars in the heroku dashboard.


## Data collection

The application maintains a set of CSV files in the `/data` directory that serve as the source for the planning.data.gov.uk platform:

1. The application manages datasets in a PostgreSQL database
2. Daily automated tasks export the database contents to CSV files in the `/data/registers` directory
3. These CSV files are then collected and processed by the platform pipeline
4. The processed data is published on planning.data.gov.uk

For example, you can access the ancient woodland status dataset at:

`https://raw.githubusercontent.com/digital-land/dluhc-datasets/refs/heads/main/data/registers/ancient-woodland-status.csv`

This process ensures that the authoritative dataset versions are maintained in this repository and then propagated to the platform.

Therefore for ancient woodland status, the endpoint for collection configuration is set [here](https://github.com/digital-land/config/blob/main/collection/ancient-woodland/endpoint.csv?plain=1#L3)


## Automated tasks

> [!WARNING]
> These variables are from deploying to Heroku and need to be updated for deployments to AWS. They may be ran in Github actions now like the database action below

The following tasks are automatically run daily via the Heroku scheduler to maintain and update the application's data:

1. `flask data new-datasets && flask data dataset-fields`
   - Checks for and adds new datasets to the system
   - Updates the field definitions for all datasets

   The new datasets command checks digital land datasette for any new category datasets, or if there has been
   a replacement of the dataset.

2. `flask data set-considerations`
   - Updates dataset considerations from the specification

3. `flask data set-references`
   - Updates dataset references and their specifications

4. `flask data backup-push-registers`
   - Creates backups of all registers
   - Pushes the backups to the GitHub repository

   The registers backup csv files are all stored in the [data/registers](/data/registers) directory.

   The platform collects the csv files from this data directory.


The tasks run in the early hours of the morning and are configured via the Heroku dashboard. For details login into the Heroku dashboard, navigate to the application, resources tab and click on Heroku scheduler.
