# commands for loading csv files into database

import csv
import os
from pathlib import Path

import frontmatter
import requests
from flask.cli import AppGroup

from application.extensions import db
from application.models import Dataset, Field, Record, dataset_field

data_cli = AppGroup("data")

base_url = "https://raw.githubusercontent.com/digital-land"
specfication_markdown_url = "{base_url}/specification/main/content/dataset/{dataset}.md"

datasette_url = "https://datasette.planning.data.gov.uk/digital-land"
datasette_query = "{datasette_url}/field.json?field__exact={field}&_shape=object"


@data_cli.command("load")
def load_db():
    print("loading db")

    data_dir = os.path.join(Path(__file__).parent.parent, "data", "registers")

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
                    field_query = datasette_query.format(
                        datasette_url=datasette_url, field=field
                    )
                    resp = requests.get(field_query)
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
                for row_num, row in enumerate(reader):
                    record = Record(id=row_num, data=row)
                    dataset.records.append(record)
                try:
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
    Record.query.delete()
    Dataset.query.delete()
    Field.query.delete()
    db.session.commit()
    print("data dropped")
