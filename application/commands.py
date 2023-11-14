import csv
from pathlib import Path

import frontmatter
import requests
from flask.cli import AppGroup

from application.extensions import db
from application.models import Dataset, Field

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
