# DLUHC Datasets

![ci workflow ](https://github.com/digital-land/dluhc-datasets/actions/workflows/ci.yml/badge.svg)

A tool to manage DLUHC's datasets. For example, the listed-building-grade dataset.


## Quick start

Make python virtualenv then:

    make init

Create a postgres db:

    createdb dluhc-datasets

### Loading production data

The following command will load the production data into you local database, so there's not need to start with a flask db upgrade.

    flask data load-db-backup


## Automated tasks

The following tasks are automatically run daily via the Heroku scheduler to maintain and update the application's data:

1. `flask data new-datasets && flask data dataset-fields`
   - Checks for and adds new datasets to the system
   - Updates the field definitions for all datasets

2. `flask data set-considerations`
   - Updates dataset considerations from the specification

3. `flask data set-references`
   - Updates dataset references and their specifications

4. `flask data backup-push-registers`
   - Creates backups of all registers
   - Pushes the backups to the GitHub repository


The tasks run in the early hours of the morning and are configured via the Heroku dashboard. For details login into the Heroku dashboard, navigate to the application, resources tab and click on Heroku scheduler.

## GitHub Actions

The repository uses GitHub Actions for continuous integration and automated backups:

### CI Workflow
- Runs on every push and pull request to the main branch
- Installs Python dependencies
- Runs flake8 for linting
- Runs pytest for testing

### Database Backup
- Runs daily at 1am UTC
- Downloads the latest database backup from Heroku
- Commits the backup to the repository in the data directory
- Requires Heroku authentication via `HEROKU_OAUTH_TOKEN` secret
