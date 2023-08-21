# commands for loading csv files into database

import csv
import json
import os
from pathlib import Path

import frontmatter
import requests
from flask.cli import AppGroup

from application.extensions import db
from application.models import Dataset, DatasetField, Field

data_cli = AppGroup("data")

base_url = "https://raw.githubusercontent.com/digital-land"
specfication_markdown_url = (
    "{base_url}/specification/main/content/dataset/{register}.md"
)


@data_cli.command("load")
def load_data():
    register_fields = {}
    data_dir = os.path.join(Path(__file__).parent.parent, "data")
    data_out_dir = os.path.join(data_dir, "registers")
    with open(os.path.join(data_dir, "dataset-registers.csv"), newline="") as csvfile:
        reader = csv.DictReader(csvfile)
        for row in reader:
            if row["url"]:
                register = row["register"]
                url = specfication_markdown_url.format(register=register)
                markdown = requests.get(url)
                if markdown.status_code == 200:
                    try:
                        front = frontmatter.loads(markdown.text)
                        fields = [field["field"] for field in front["fields"]]
                        register_fields[register] = fields
                        print("\nregister name: ", register)
                        print("fields:", register_fields[register])
                    except json.JSONDecodeError as err:
                        print(err)
                        continue
                else:
                    print(f"no markdown file found at {url}")
                    continue
                try:
                    response = requests.get(row["url"])
                    response.raise_for_status()
                    try:
                        reader = csv.DictReader(response.text.splitlines())
                        rows = []
                        expected_fields = register_fields[register]
                        for row in reader:
                            r = {}
                            for field in expected_fields:
                                r[field] = row.get(field, None)
                            rows.append(r)
                        if rows:
                            with open(
                                os.path.join(data_out_dir, f"{register}.csv"),
                                "w",
                                newline="\n",
                            ) as csvfile:
                                writer = csv.DictWriter(
                                    csvfile, fieldnames=expected_fields
                                )
                                writer.writeheader()
                                for row in rows:
                                    writer.writerow(row)
                    except csv.Error as err:
                        print(err)
                        continue
                except requests.exceptions.HTTPError as err:
                    print(err)
                    continue


@data_cli.command("db")
def load_db():
    print("loading db")

    if not Field.query.get("reference"):
        reference_field = Field(name="reference")
        try:
            db.session.add(reference_field)
            db.session.commit()
        except Exception as e:
            print(e)
            db.session.rollback()

    if not Field.query.get("prefix"):
        prefix_field = Field(name="prefix")
        try:
            db.session.add(prefix_field)
            db.session.commit()
        except Exception as e:
            print(e)
            db.session.rollback()

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

            with open(os.path.join(data_dir, file), newline="") as csvfile:
                reader = csv.DictReader(csvfile)
                for header in reader.fieldnames:
                    field = Field(name=header)
                    if not Field.query.filter_by(name=header).first():
                        try:
                            db.session.add(field)
                            db.session.commit()
                            print(f"field {field.name} added")
                        except Exception as e:
                            print(e)
                            db.session.rollback()

                for row_num, row in enumerate(reader):
                    for key, value in row.items():
                        dataset_field = DatasetField(
                            id=row_num,
                            dataset_name=dataset_name,
                            field_name=key,
                            value=value,
                        )
                        try:
                            db.session.add(dataset_field)
                            db.session.commit()
                        except Exception as e:
                            print(e)
                            db.session.rollback()
                    try:
                        db.session.add(dataset_field)
                        db.session.commit()
                    except Exception as e:
                        print(e)
                        db.session.rollback()
    print("db loaded")


@data_cli.command("drop")
def drop_data():
    DatasetField.query.delete()
    Dataset.query.delete()
    Field.query.delete()
    db.session.commit()
    print("data dropped")
