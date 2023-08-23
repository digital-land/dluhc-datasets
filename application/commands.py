# commands for loading csv files into database

import csv
import os
from pathlib import Path

import frontmatter
import requests
from flask.cli import AppGroup

from application.extensions import db
from application.models import Dataset, Entry, Field, dataset_field

data_cli = AppGroup("data")

base_url = "https://raw.githubusercontent.com/digital-land"
specfication_markdown_url = "{base_url}/specification/main/content/dataset/{dataset}.md"


@data_cli.command("load")
def load_db():
    print("loading db")

    data_dir = os.path.join(Path(__file__).parent.parent, "data", "registers")

    for filename in os.listdir(data_dir):
        if filename.endswith(".csv"):
            file = Path(filename)
            dataset_name = file.stem
            if not Dataset.query.get(dataset_name):
                dataset = Dataset(name=dataset_name)
                try:
                    db.session.add(dataset)
                    db.session.commit()
                    print(f"dataset {dataset_name} added")
                except Exception as e:
                    print(e)
                    db.session.rollback()

    for dataset in Dataset.query.all():
        schema_url = specfication_markdown_url.format(
            base_url=base_url, dataset=dataset.name
        )
        markdown = requests.get(schema_url)
        if markdown.status_code == 200:
            front = frontmatter.loads(markdown.text)
            fields = [field["field"] for field in front["fields"]]
            udpated_fields = [field for field in fields if field != dataset.name]

            for field in udpated_fields:
                f = Field.query.get(field)
                if f is None:
                    f = Field(name=field)
                    db.session.add(f)
                    db.session.commit()
                    print(f"field {f.name} added")
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
                    entry = Entry(id=row_num, dataset_name=dataset.name, data=row)
                    dataset.entries.append(entry)
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
    Dataset.query.delete()
    Field.query.delete()
    db.session.commit()
    print("data dropped")
