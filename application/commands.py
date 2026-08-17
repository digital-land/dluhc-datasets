import base64
import csv
import datetime
import hashlib
import os
from pathlib import Path

import click
import frontmatter
import github
import requests
from flask import current_app
from flask.cli import AppGroup

from application.extensions import db
from application.models import Dataset, Field, Record, Reference
from application.specification import Specification

data_cli = AppGroup("data")

base_git_content_url = "https://raw.githubusercontent.com/digital-land"
specfication_markdown_url = (
    "{base_git_content_url}/specification/main/content/dataset/{dataset}.md"
)


def _specification():
    return Specification(
        current_app.config.get("SPECIFICATION_URL"),
        additional_datasets=current_app.config.get("ADDITIONAL_DATASETS"),
    )


@data_cli.command("dataset-fields")
def dataset_fields():
    print("loading dataset fields")
    specification = _specification()
    for dataset in Dataset.query.all():
        fields = specification.dataset_fields(dataset.dataset)
        if not fields:
            print(f"no fields found in the specification for {dataset.dataset}")
            continue

        for field in fields:
            f = _get_or_create_field(field, specification)
            if f is None:
                print(
                    f"field {field} of {dataset.dataset} is not in the specification, skipping"
                )
                continue

            if f not in dataset.fields:
                dataset.fields.append(f)
                db.session.add(dataset)
                db.session.commit()
                print(f"field {f.field} added to {dataset.dataset}")
            else:
                print(f"field {f.field} already in schema for {dataset.dataset}")

    print("db loaded")


@data_cli.command("new-datasets")
def get_new_datasets():
    database_datasets = set([dataset.dataset for dataset in Dataset.query.all()])

    specification = _specification()
    replacement_datasets = specification.replacement_datasets()

    unknown = specification.unknown_additional_datasets()
    if unknown:
        print(
            f"additional datasets not in the specification, skipping: {', '.join(unknown)}"
        )

    data = specification.managed_datasets()
    new_datasets = [
        dataset
        for dataset in data
        if dataset["dataset"] not in database_datasets and dataset["end-date"] == ""
    ]
    ended_datasets = [dataset for dataset in data if dataset["end-date"] != ""]

    # process new datasets first as they may be replacements for existing
    # datasets and therefore need to be available in the database for the
    # processing of replacements
    if new_datasets:
        print("New datasets found")
        _process_new_datasets(new_datasets, specification)
    else:
        print("No new datasets found")

    # end datasets before processing replacements. a replacement only matches
    # an old dataset once that dataset has an end date, so on the run where the
    # specification first marks it ended it has to be ended here first
    if ended_datasets:
        _process_ended_datasets(ended_datasets)

    if replacement_datasets:
        _process_replacement_datasets(replacement_datasets)
    else:
        print("No replacement datasets found")


def _process_ended_datasets(ended_datasets):
    for dataset in ended_datasets:
        d = Dataset.query.filter(
            Dataset.dataset == dataset["dataset"], Dataset.end_date.is_(None)
        ).one_or_none()
        if d is not None:
            end_date_str = dataset["end-date"]
            end_date = datetime.datetime.strptime(end_date_str, "%Y-%m-%d").date()
            d.end_date = end_date
            db.session.add(d)
            db.session.commit()
            print(f"dataset {dataset['dataset']} ended")


def _process_replacement_datasets(replacement_datasets):
    for row in replacement_datasets:
        dataset = row["dataset"]
        replacement_dataset = row["replacement-dataset"]

        d = Dataset.query.filter(Dataset.dataset == replacement_dataset).one_or_none()
        if d is not None:
            if d.records or d.change_log:
                print(
                    f"Replacement dataset {replacement_dataset} has already been processed and contains data. Skipping."
                )
                continue

        print(f"Replacing dataset {dataset} with {replacement_dataset}")

        old_dataset = Dataset.query.filter(
            Dataset.dataset == dataset, Dataset.end_date.is_not(None)
        ).one_or_none()
        new_dataset = Dataset.query.filter(
            Dataset.dataset == replacement_dataset
        ).one_or_none()

        if old_dataset is not None and new_dataset is not None:
            for field in old_dataset.fields:
                if field not in new_dataset.fields:
                    new_dataset.fields.append(field)

            for record in old_dataset.records:
                record.dataset_id = new_dataset.dataset
                record.prefix = new_dataset.dataset
                db.session.add(record)

            for change in old_dataset.change_log:
                change.dataset_id = new_dataset.dataset
                db.session.add(change)

            old_dataset.end_date = datetime.datetime.today()

            db.session.add(old_dataset)
            db.session.add(new_dataset)
            db.session.commit()

            print(f"dataset {dataset} replaced by {replacement_dataset}")

        else:
            if old_dataset is None:
                print(
                    f"Could not replace dataset {dataset} as it does not exist or may have been replaced already"
                )

            if new_dataset is None:
                print(
                    f"Could migrate data to the replacement dataset {replacement_dataset} as it was not found"
                )


def _process_new_datasets(new_datasets, specification):
    for row in new_datasets:
        dataset = Dataset(dataset=row["dataset"], name=row["name"])
        dataset.entity_minimum = _as_int(row["entity-minimum"])
        dataset.entity_maximum = _as_int(row["entity-maximum"])
        dataset.consideration = row["consideration"]
        db.session.add(dataset)
        db.session.commit()
        print(f"dataset {dataset.dataset} with name {dataset.name} added")
        print(f"get fields for {dataset.dataset}")
        for field in specification.dataset_fields(dataset.dataset):
            f = _get_or_create_field(field, specification)
            if f is None:
                print(
                    f"field {field} of {dataset.dataset} is not in the specification, skipping"
                )
                continue
            print(f"field {f.field} added to dataset {dataset.dataset}")
            dataset.fields.append(f)
            db.session.add(dataset)
            db.session.commit()

    print("New datasets added to database")


def _as_int(value):
    return int(value) if value else None


def _get_or_create_field(field, specification):
    """The Field row for a specification field, created from the specification if new.

    Returns None when the specification has no such field, so that one unknown
    field cannot stop the rest of a dataset's schema being loaded.
    """
    f = Field.query.get(field)
    if f is not None:
        return f

    specified = specification.field(field)
    if specified is None:
        return None

    f = Field(field=field, name=field.replace("-", " ").capitalize())
    f.datatype = specified["datatype"]
    if specified["description"]:
        f.description = specified["description"]
    db.session.add(f)
    db.session.commit()
    print(f"new field {f.field} added")
    return f


@data_cli.command("backup-registers")
def backup_registers():
    print("backing up registers")
    subquery = (
        db.session.query(Record.dataset_id)
        .filter(Record.dataset_id == Dataset.dataset)
        .exists()
    )
    datasets = (
        db.session.query(Dataset)
        .filter(Dataset.end_date.is_(None))
        .filter(subquery)
        .order_by(Dataset.dataset)
        .all()
    )
    for dataset in datasets:
        fields = [field.field for field in dataset.sorted_fields()]
        data_dir = Path(__file__).resolve().parent.parent / "data/registers"
        file_path = data_dir / f"{dataset.dataset}.csv"
        records = [record.to_dict() for record in dataset.records]
        try:
            with open(file_path, "w") as csvfile:
                writer = csv.DictWriter(csvfile, fieldnames=fields)
                writer.writeheader()
                writer.writerows(records)
            print(f"backed up {dataset.dataset} to {file_path}")
        except Exception as e:
            print(f"failed to backup {dataset} to {file_path} with error {e}")
    print("registers backed up")


@data_cli.command("push-registers")
def push_registers():
    registers_path = os.getenv("DATASETS_REPO_REGISTERS_PATH")
    repo = _get_repo(os.environ)
    local_registers_directory = (
        Path(__file__).resolve().parent.parent / "data/registers"
    )
    print("Pushing registers to repo", repo, "and path", registers_path)
    datasets = Dataset.query.all()
    for dataset in datasets:
        csv_file = f"{dataset.dataset}.csv"
        local_file_path = os.path.join(local_registers_directory, csv_file)
        try:
            with open(local_file_path, "r") as f:
                local_content = f.read()
        except FileNotFoundError:
            print(f"Local file {local_file_path} not found. Skipping.")
            continue

        remote_path_file_path = f"{registers_path}/{csv_file}"
        remote_file, remote_content = _get_file_contents(repo, remote_path_file_path)

        if remote_file is None and remote_content is None:
            print(f"push new file {csv_file}")
            _commit_new(repo, remote_path_file_path, local_content)

        elif remote_file is not None and remote_content is not None:
            local_content_hash = _get_sha256(local_content)
            remote_content_hash = _get_sha256(remote_content)
            if local_content_hash != remote_content_hash:
                print(f"update file {remote_path_file_path}")
                _commit_update(repo, remote_file, local_content)
            else:
                print(f"No changes to {csv_file}")
        else:
            print(f"Error getting remote file {csv_file}. Skipping.")


@data_cli.command("backup-push-registers")
@click.pass_context
def export(ctx):
    ctx.invoke(backup_registers)
    ctx.invoke(push_registers)


@data_cli.command("load-db-backup")
def load_db_backup():
    import subprocess
    import sys
    import tempfile

    from flask import current_app

    # check heroku cli installed
    result = subprocess.run(["which", "heroku"], capture_output=True, text=True)

    if result.returncode == 1:
        print("Heroku CLI is not installed. Please install it and try again.")
        sys.exit(1)

    # check heroku login
    result = subprocess.run(["heroku", "whoami"], capture_output=True, text=True)

    if "Error: not logged in" in result.stderr:
        print("Please login to heroku using 'heroku login' and try again.")
        sys.exit(1)

    print("Starting load data into", current_app.config["SQLALCHEMY_DATABASE_URI"])
    if (
        input(
            "Completing process will overwrite your local database. Enter 'y' to continue, or anything else to exit. "
        )
        != "y"
    ):
        print("Exiting without making any changes")
        sys.exit(0)

    with tempfile.TemporaryDirectory() as tempdir:
        path = os.path.join(tempdir, "latest.dump")

        # get the latest dump from heroku
        result = subprocess.run(
            [
                "heroku",
                "pg:backups:download",
                "-a",
                "dluhc-datasets",
                "-o",
                path,
            ]
        )

        if result.returncode != 0:
            print("Error downloading the backup")
            sys.exit(1)

        # restore the dump to the local database
        subprocess.run(
            [
                "pg_restore",
                "--verbose",
                "--clean",
                "--no-acl",
                "--no-owner",
                "-h",
                "localhost",
                "-d",
                "dluhc-datasets",
                path,
            ]
        )
        print(
            "\n\nRestored the dump to the local database using pg_restore. You can ignore warnings from pg_restore."
        )

    print("Data loaded successfully")


@data_cli.command("set-considerations")
def set_dataset_considerations():
    print("Setting considerations for datasets")
    for dataset in Dataset.query.filter(Dataset.consideration.is_(None)).all():
        print(f"Consideration for {dataset.dataset} is not set")
        schema_url = specfication_markdown_url.format(
            base_git_content_url=base_git_content_url, dataset=dataset.dataset
        )
        markdown = requests.get(schema_url)
        if markdown.status_code == 200:
            front = frontmatter.loads(markdown.text)
            consideration = front.get("consideration")
            if consideration and consideration.strip() != "":
                dataset.consideration = consideration
                db.session.add(dataset)
                db.session.commit()
                print(f"Set consideration {consideration} for {dataset.dataset}")
            else:
                print(f"No consideration found for {dataset.dataset}")
    print("Done")


@data_cli.command("set-references")
def set_dataset_references():
    print("Setting references for datasets")

    refs = {}
    specification = _specification()

    for dataset in Dataset.query.order_by(Dataset.dataset).all():
        referencing = specification.datasets_referencing(dataset.dataset)
        if not referencing:
            print(f"No references found for {dataset.dataset}")
            continue

        refs[dataset.dataset] = [
            {"referenced_by": referenced_by, "specification": None}
            for referenced_by in referencing
        ]

    for d, r in refs.items():
        print(f"References for {d}")
        for ref in r:
            specification_name = specification.specification_for_dataset(
                ref["referenced_by"]
            )
            if specification_name is None:
                print(f"No specification found for {ref['referenced_by']}")
            else:
                ref["specification"] = specification_name
                print(
                    f"Specification {specification_name} found for {ref['referenced_by']}"
                )

    for d, r in refs.items():
        for ref in r:
            referenced_by = ref["referenced_by"]
            specification_name = ref["specification"]
            if specification_name is None:
                reference = Reference.query.filter(
                    Reference.dataset_id == d, Reference.referenced_by == referenced_by
                ).one_or_none()
            else:
                reference = Reference.query.filter(
                    Reference.dataset_id == d,
                    Reference.referenced_by == referenced_by,
                    Reference.specification == specification_name,
                ).one_or_none()

            if reference is None:
                reference = Reference(
                    dataset_id=d,
                    referenced_by=referenced_by,
                    specification=specification_name,
                )
                db.session.add(reference)
                db.session.commit()
                print(
                    f"Reference {referenced_by} with specification {specification_name} added to {d}"
                )

    print("Done")


def _get_repo(config):
    app_id = config.get("GITHUB_APP_ID")
    repo_name = config.get("DATASETS_REPO")
    base64_key = config.get("GITHUB_APP_PRIVATE_KEY")
    private_key = base64.b64decode(base64_key)
    private_key_decoded = private_key.decode("utf-8")
    auth = github.Auth.AppAuth(app_id, private_key_decoded)
    gi = github.GithubIntegration(auth=auth)
    installation_id = gi.get_installations()[0].id
    gh = gi.get_github_for_installation(installation_id)
    return gh.get_repo(repo_name)


def _get_sha256(content):
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _get_file_contents(repo, file_path):
    try:
        file = repo.get_contents(file_path)
        file_content = file.decoded_content.decode("utf-8")
        return file, file_content
    except github.UnknownObjectException as e:
        print(f"File {file_path} is not on remote repo")
        print(e)
        return None, None


def _commit_update(repo, file, contents, message="Updated dataset registers"):
    repo.update_file(file.path, message, contents, file.sha)
    print(f"Committed {file.path} to remote repo")


def _commit_new(repo, file_path, contents, message="New dataset registers"):
    repo.create_file(file_path, message, contents)
    print(f"Created new {file_path} on remote repo")
