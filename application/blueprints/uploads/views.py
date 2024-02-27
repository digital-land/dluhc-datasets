import datetime
import os
import tempfile
from collections import OrderedDict
from csv import DictReader

from flask import Blueprint, flash, redirect, render_template, url_for
from werkzeug.utils import secure_filename

from application.extensions import db
from application.forms import CsvUploadForm
from application.models import (
    ChangeType,
    Dataset,
    Record,
    Update,
    UpdateRecord,
    create_change_log,
)
from application.utils import parse_date

upload = Blueprint("upload", __name__)


def _order_records(records):
    def sort_key(item):
        if item.get("end-date") is None:
            return datetime.date.max
        else:
            return item.get("end-date")

    ordered = sorted(records, key=sort_key)
    return ordered


@upload.route("/dataset/<string:dataset>/upload", methods=["GET", "POST"])
def upload_csv(dataset):
    form = CsvUploadForm()
    ds = Dataset.query.get(dataset)
    fieldnames = [field.field for field in ds.fields]
    if form.validate_on_submit():
        f = form.csv_file.data
        if _allowed_file(f.filename):
            filename = secure_filename(f.filename)
            temp_dir = tempfile.mkdtemp()
            file_path = os.path.join(temp_dir, filename)
            try:
                f.save(file_path)
                starting_entity = ds.entity_minimum
                with open(file_path, "r") as csv_file:
                    reader = DictReader(csv_file)
                    addtional_fields = set(reader.fieldnames) - set(fieldnames)
                    if addtional_fields:
                        flash(
                            f"CSV file contains fields not in specification: {addtional_fields}"
                        )
                        return redirect(
                            url_for("upload.upload_csv", dataset=ds.dataset)
                        )

                    records = OrderedDict()

                    for data in reader:
                        entity = data.get("entity")
                        if entity and int(entity) >= starting_entity:
                            starting_entity = int(entity) + 1

                        reference = data.get("reference")
                        if reference not in records.keys():
                            records[reference] = [data]
                        else:
                            records[reference].append(data)

                for reference, data in records.items():
                    for record in data:
                        for key, value in record.items():
                            if "-date" in key:
                                if not value:
                                    record[key] = None
                                else:
                                    record[key] = parse_date(value)

                for row_id, reference in enumerate(records):
                    data = records[reference]
                    ordered = _order_records(data)
                    original_record = ordered.pop(0)

                    if original_record is not None:
                        if not original_record.get("entity"):
                            original_record["entity"] = starting_entity
                            starting_entity += 1
                        else:
                            original_record["entity"] = int(original_record["entity"])
                        try:
                            record = Record.factory(
                                row_id,
                                original_record.get("entity"),
                                ds.dataset,
                                original_record,
                            )
                            ds.records.append(record)
                            db.session.add(ds)
                            db.session.commit()
                        except Exception as e:
                            print(f"Error: {e}")

                        for rest in ordered:
                            change_log = create_change_log(
                                record, rest, ChangeType.EDIT
                            )
                            ds.change_log.append(change_log)
                            db.session.add(record)
                            db.session.add(ds)
                            db.session.commit()

                return redirect(url_for("main.dataset", id=ds.dataset))
            except Exception as e:
                flash(f"Error: {e}")
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)

    return render_template("upload.html", form=form, dataset=ds, action="upload")


@upload.route("/dataset/<string:dataset>/update", methods=["GET", "POST"])
def update_csv(dataset):
    form = CsvUploadForm()
    ds = Dataset.query.get(dataset)
    fieldnames = [field.field for field in ds.fields]
    if form.validate_on_submit():
        f = form.csv_file.data
        if _allowed_file(f.filename):
            filename = secure_filename(f.filename)
            temp_dir = tempfile.mkdtemp()
            file_path = os.path.join(temp_dir, filename)
            try:
                f.save(file_path)
                with open(file_path, "r") as csv_file:
                    reader = DictReader(csv_file)
                    addtional_fields = set(reader.fieldnames) - set(fieldnames)
                    if addtional_fields:
                        flash(
                            f"CSV file contains fields not in specification: {addtional_fields}"
                        )
                        return redirect(
                            url_for("upload.update_csv", dataset=ds.dataset)
                        )
                    records = []
                    for row in reader:
                        records.append(row)

                update = Update(dataset_id=ds.dataset)
                for record in records:
                    update.records.append(UpdateRecord(data=record))

                db.session.add(update)
                db.session.commit()
            except Exception as e:
                flash(f"Error: {e}")
                return redirect(url_for("upload.update_csv", dataset=ds.dataset))
            finally:
                if os.path.exists(file_path):
                    os.remove(file_path)
            return redirect(url_for("main.dataset", id=ds.dataset))

    else:
        return render_template("upload.html", form=form, dataset=ds, action="update")


@upload.route("/dataset/<string:dataset>/process-updates", methods=["GET", "POST"])
def process_updates(dataset):
    update = Update.query.filter_by(dataset=dataset).first()
    return update


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() == "csv"
