import csv
from pathlib import Path

import frontmatter
import github
import requests
from flask.cli import AppGroup

from application.extensions import db
from application.models import ChangeLog, ChangeType, Dataset, Field

data_cli = AppGroup("data")

base_url = "https://raw.githubusercontent.com/digital-land"
specfication_markdown_url = "{base_url}/specification/main/content/dataset/{dataset}.md"

datasette_url = "https://datasette.planning.data.gov.uk/digital-land"
field_query = "{datasette_url}/field.json?field__exact={field}&_shape=object"
fields_query = f"{datasette_url}/field.json?_shape=array"
dataset_query_part = "dataset__not=category&realm__exact=dataset&typology__exact=category&_shape=array"  # noqa
dataset_query = f"{datasette_url}/dataset.json?{dataset_query_part}"
dataset_field_query = (
    "{datasette_url}/dataset_field.json?dataset__exact={dataset}&_shape=array"
)

dataset_editor_base_url = "https://dluhc-datasets.planning-data.dev"


@data_cli.command("dataset-fields")
def dataset_fields():
    print("loading dataset fields")
    for dataset in Dataset.query.all():
        schema_url = specfication_markdown_url.format(
            base_url=base_url, dataset=dataset.dataset
        )
        markdown = requests.get(schema_url)
        if markdown.status_code == 200:
            front = frontmatter.loads(markdown.text)
            fields = [field["field"] for field in front["fields"]]
            udpated_fields = [field for field in fields if field != dataset.name]

            for field in udpated_fields:
                f = Field.query.get(field)
                if f is None:
                    human_readable = field.replace("-", " ").capitalize()
                    f = Field(field=field, name=human_readable)
                    query = field_query.format(datasette_url=datasette_url, field=field)
                    resp = requests.get(query)
                    data = resp.json()
                    f.datatype = data[field]["datatype"]
                    if data[field].get("description"):
                        f.description = data[field]["description"]
                    db.session.add(f)
                    db.session.commit()
                    print(f"field {f.field} with name {f.name} added")
                dataset.fields.append(f)
            db.session.add(dataset)
            db.session.commit()
        else:
            print(f"no markdown file found at {schema_url}")

    print("db loaded")


@data_cli.command("check")
def check_dataset_fields():
    for dataset in Dataset.query.all():
        schema_url = specfication_markdown_url.format(
            base_url=base_url, dataset=dataset.dataset
        )
        markdown = requests.get(schema_url)
        if markdown.status_code == 200:
            front = frontmatter.loads(markdown.text)
            print(f"\n{dataset.dataset} fields")
            dataset_fields = set([field.field for field in dataset.fields])
            specfication_fields = set([field["field"] for field in front["fields"]])

            print(f"dataset \t {sorted(dataset_fields)}")
            print(f"specification \t {sorted(specfication_fields)}")

            if dataset_fields != specfication_fields:
                print(f"missing fields {specfication_fields - dataset_fields}")
                print(f"extra fields {dataset_fields - specfication_fields}")
            else:
                print(f"{dataset.dataset} has all fields in specification")
                print("\n")


@data_cli.command("new-datasets")
def check_for_new_datasets():
    resp = requests.get(dataset_query)
    data = resp.json()
    database_datasets = set([dataset.dataset for dataset in Dataset.query.all()])
    new_datasets = [
        dataset for dataset in data if dataset["dataset"] not in database_datasets
    ]
    for dataset in new_datasets:
        dataset = Dataset(dataset=dataset["dataset"], name=dataset["name"])
        db.session.add(dataset)
        db.session.commit()
        print(f"dataset {dataset.dataset} with name {dataset.name} added")
        print(f"get fields for {dataset.dataset}")
        fields = requests.get(
            dataset_field_query.format(
                datasette_url=datasette_url, dataset=dataset.dataset
            )
        ).json()
        print(
            dataset_field_query.format(
                datasette_url=datasette_url, dataset=dataset.dataset
            )
        )
        for field in fields:
            f = Field.query.get(field["field"])
            if f is None:
                print("Something went wrong, field not found in database")
                continue
            print(f"field {f.field} added to dataset {dataset.dataset}")
            dataset.fields.append(f)
            db.session.add(dataset)
            db.session.commit()

    print("new datasets added to database")


@data_cli.command("backup-registers")
def backup_registers():
    print("backing up registers")
    resp = requests.get(f"{dataset_editor_base_url}/index.json")
    dataset_json = resp.json()
    for dataset in dataset_json["datasets"]:
        if dataset["total_records"] > 0:
            resp = requests.get(dataset["data"])
            data = resp.json()
            fields = [field for field in data["fields"]]
            dataset = data["dataset"]
            data_dir = Path(__file__).resolve().parent.parent / "data/registers"
            file_path = data_dir / f"{dataset}.csv"
            try:
                with open(file_path, "w") as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(data["records"])
                # print(f"backed up {dataset} to {file_path}")
            except Exception as e:
                print(f"failed to backup {dataset} to {file_path} with error {e}")
    print("registers backed up")


@data_cli.command("push-registers")
def push_registers():
    from dotenv import dotenv_values

    print("Pushing registers")
    config = dotenv_values(".env")
    registers_path = config.get("DATASETS_REPO_REGISTERS_PATH")
    repo = _get_repo(config)

    datasets = Dataset.query.all()
    for dataset in datasets:
        updates = ChangeLog.query.filter(
            ChangeLog.dataset_id == dataset.dataset,
            ChangeLog.pushed_to_github.isnot(None),
            ChangeLog.pushed_to_github.is_(False),
            ChangeLog.change_type == ChangeType.EDIT,
        ).all()
        additions = ChangeLog.query.filter(
            ChangeLog.dataset_id == dataset.dataset,
            ChangeLog.pushed_to_github.isnot(None),
            ChangeLog.pushed_to_github.is_(False),
            ChangeLog.change_type == ChangeType.ADD,
        ).all()

        if updates or additions:
            file_path = f"{registers_path}/{dataset.dataset}.csv"
            file, contents = _get_file_contents(repo, file_path)
            lines = contents.split("\n")
            headers = lines[0].split(",")

            for update in updates:
                row_parts = []
                data = update.data["to"]
                for header in headers:
                    value = data.get(header, "")
                    if value is None:
                        value = ""
                    if not isinstance(value, str):
                        value = str(value)
                    row_parts.append(value)
                row_string = ",".join(row_parts)
                lines[update.record.row_id] = row_string

            for addition in additions:
                row_parts = []
                data = addition.data
                for header in headers:
                    value = data.get(header, "")
                    if value is None:
                        value = ""
                    if not isinstance(value, str):
                        value = str(value)
                    row_parts.append(value)
                row_string = ",".join(row_parts)
                lines.append(row_string)

            updated_contents = "\n".join(lines)
            _commit(repo, file, updated_contents)

        all_changes = updates + additions
        for change in all_changes:
            change.pushed_to_github = True
            db.session.add(change)

        if db.session.dirty:
            db.session.commit()

    print("Done")


def _get_repo(config):
    app_id = int(config.get("GITHUB_APP_ID"))
    private_key = config.get("GITHUB_APP_PRIVATE_KEY")
    repo_name = config.get("DATASETS_REPO")
    auth = github.Auth.AppAuth(app_id, private_key)
    gi = github.GithubIntegration(auth=auth)
    installation_id = gi.get_installations()[0].id
    gh = gi.get_github_for_installation(installation_id)
    return gh.get_repo(repo_name)


def _get_file_contents(repo, file_path):
    file = repo.get_contents(file_path)
    file_content = file.decoded_content.decode("utf-8")
    return file, file_content


def _commit(repo, file, contents):
    repo.update_file(file.path, "Updating file", contents, file.sha)
    print(f"{file.path} updated successfully!")
