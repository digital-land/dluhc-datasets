# commands for loading csv files into database

import csv
import os
from pathlib import Path

import frontmatter
import requests
from flask.cli import AppGroup

from application.extensions import db
from application.models import (
    ChangeLog,
    ChangeType,
    Dataset,
    Field,
    Record,
    dataset_field,
)

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


@data_cli.command("load")
def load_db():
    print("loading db")

    data_dir = os.path.join(Path(__file__).parent.parent, "data", "registers")

    fields = requests.get(fields_query).json()
    for field in fields:
        f = Field.query.get(field["field"])
        if f is None:
            f = Field(
                field=field["field"],
                name=field["name"],
                datatype=field["datatype"],
                description=field["description"],
            )
            db.session.add(f)
            db.session.commit()

    for filename in os.listdir(data_dir):
        if filename.endswith(".csv"):
            file = Path(filename)
            dataset_name = file.stem
            if not Dataset.query.get(dataset_name):
                human_readable = dataset_name.replace("-", " ").capitalize()
                dataset = Dataset(dataset=dataset_name, name=human_readable)
                try:
                    db.session.add(dataset)
                    db.session.commit()
                    print(f"dataset {dataset.dataset} with name {dataset.name} added")
                except Exception as e:
                    print(e)
                    db.session.rollback()

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

    for filename in os.listdir(data_dir):
        f = Path(filename)
        dataset_name = f.stem
        if dataset_name not in [
            "planning-application-category",
            "development-plan-event",
        ]:
            print(f"load data for {filename}")
            dataset = Dataset.query.get(dataset_name)
            with open(os.path.join(data_dir, f), newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                for row_id, row in enumerate(reader):
                    record = Record(row_id=row_id, data=row)
                    dataset.records.append(record)
                try:
                    db.session.add(dataset)
                    db.session.commit()
                    for record in dataset.records:
                        try:
                            notes = f"Added record {record.data['prefix']}:{record.data['reference']}"
                        except KeyError:
                            notes = f"Added record {record.data}"
                            print(
                                f"Could not find prefix or reference in data for {dataset_name}"
                            )
                        dataset.change_log.append(
                            ChangeLog(
                                change_type=ChangeType.ADD,
                                data=row,
                                notes=notes,
                                record_id=record.id,
                            )
                        )
                    db.session.add(dataset)
                    db.session.commit()
                except Exception as e:
                    print(f"error adding file {file}")
                    print(e)
                    db.session.rollback()
        else:
            print(f"skipping {filename}")

    print("db loaded")


@data_cli.command("drop")
def drop_data():
    db.session.query(dataset_field).delete()
    ChangeLog.query.delete()
    Record.query.delete()
    Dataset.query.delete()
    Field.query.delete()
    db.session.commit()
    print("data dropped")


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
