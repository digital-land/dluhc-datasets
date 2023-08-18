# commands for loading csv files into database

import csv
import json
import os
from pathlib import Path

import frontmatter
import requests
from flask.cli import AppGroup

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
