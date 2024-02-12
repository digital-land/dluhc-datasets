import datetime
import io
import os
import tempfile
from collections import OrderedDict
from csv import DictReader, DictWriter

from flask import (
    Blueprint,
    abort,
    flash,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from sqlalchemy import desc
from werkzeug.utils import secure_filename

from application.extensions import db
from application.forms import CsvUploadForm, FormBuilder
from application.models import ChangeLog, ChangeType, Dataset, Record
from application.utils import date_to_string, login_required, parse_date

main = Blueprint("main", __name__)


def _collect_start_date(data):
    parts = []
    format = ""
    if data.get("year"):
        parts.append(data.get("year"))
        format = "%Y"
    if data.get("month"):
        parts.append(data.get("month"))
        format = f"{format}-%m"
    if data.get("day"):
        parts.append(data.get("day"))
        format = f"{format}-%d"
    if parts:
        return "-".join(parts), format
    else:
        return None, None


@main.route("/")
@main.route("/index")
def index():
    ds = db.session.query(Dataset).order_by(Dataset.dataset).all()
    return render_template("datasets.html", datasets=ds, isHomepage=True)


@main.route("/index.json")
def index_json():
    ds = db.session.query(Dataset).order_by(Dataset.dataset).all()
    return {"datasets": [d.to_dict() for d in ds]}


@main.route("/support")
def support():
    breadcrumbs = {
        "items": [
            {"text": "DLUHC Datasets", "href": url_for("main.index")},
            {"text": "Support"},
        ]
    }
    return render_template("support.html", breadcrumbs=breadcrumbs)


@main.route("/how-we-add-datasets")
def how_we_add_datasets():
    breadcrumbs = {
        "items": [
            {"text": "DLUHC Datasets", "href": url_for("main.index")},
            {"text": "How we add datasets"},
        ]
    }
    return render_template("how-we-add-datasets.html", breadcrumbs=breadcrumbs)


@main.route("/dataset/<string:id>")
def dataset(id):
    dataset = Dataset.query.get(id)
    breadcrumbs = {
        "items": [
            {"text": "Datasets", "href": url_for("main.index")},
            {"text": dataset.name, "href": url_for("main.dataset", id=id)},
            {"text": "Records"},
        ]
    }
    sub_navigation = {
        "currentPath": url_for("main.dataset", id=dataset.dataset),
        "itemsList": [
            {"title": "Records", "url": url_for("main.dataset", id=dataset.dataset)},
            {"title": "Schema", "url": url_for("main.schema", id=dataset.dataset)},
            {"title": "History", "url": url_for("main.history", id=dataset.dataset)},
            {"title": "Changes", "url": url_for("main.change_log", id=dataset.dataset)},
        ],
    }
    page = {"title": dataset.name, "caption": "Dataset"}
    records = [record.to_dict() for record in dataset.records]
    return render_template(
        "records.html",
        dataset=dataset,
        breadcrumbs=breadcrumbs,
        sub_navigation=sub_navigation,
        page=page,
        records=records,
    )


@main.route("/dataset/<string:id>.json")
def dataset_json(id):
    dataset = Dataset.query.get(id)
    return {
        "dataset": dataset.dataset,
        "name": dataset.name,
        "fields": [field.field for field in dataset.fields],
        "records": [r.to_dict() for r in dataset.records],
    }


@main.route("/dataset/<string:id>/change-log.html")
def change_log(id):
    dataset = Dataset.query.get(id)
    breadcrumbs = {
        "items": [
            {"text": "Datasets", "href": url_for("main.index")},
            {
                "text": dataset.name,
                "href": url_for("main.dataset", id=dataset.dataset),
            },
            {"text": "Changes"},
        ]
    }
    sub_navigation = {
        "currentPath": url_for("main.change_log", id=dataset.dataset),
        "itemsList": [
            {"title": "Records", "url": url_for("main.dataset", id=dataset.dataset)},
            {"title": "Schema", "url": url_for("main.schema", id=dataset.dataset)},
            {"title": "History", "url": url_for("main.history", id=dataset.dataset)},
            {"title": "Changes", "url": url_for("main.change_log", id=dataset.dataset)},
        ],
    }
    page = {"title": dataset.name, "caption": "Dataset"}

    changes_by_date = OrderedDict()

    changes = (
        ChangeLog.query.filter(ChangeLog.dataset_id == dataset.dataset)
        .order_by(desc(ChangeLog.created_date), ChangeLog.change_type)
        .all()
    )

    for change in changes:
        if change.created_date not in changes_by_date.keys():
            changes_by_date[change.created_date] = []
        changes_by_date[change.created_date].append(change)

    return render_template(
        "change-log.html",
        dataset=dataset,
        changes_by_date=changes_by_date,
        breadcrumbs=breadcrumbs,
        sub_navigation=sub_navigation,
        page=page,
    )


@main.route("/dataset/<string:id>/add", methods=["GET", "POST"])
@login_required
def add_record(id):
    dataset = Dataset.query.get(id)
    builder = FormBuilder(dataset.fields)
    form = builder.build()
    form_fields = builder.form_fields()
    if form.validate_on_submit():
        data = form.data

        start_date, _ = _collect_start_date(request.form)
        if start_date:
            data["start-date"] = start_date

        # set prefix to as it is not in form
        data["prefix"] = dataset.dataset
        data["entry-date"] = datetime.datetime.today().strftime("%Y-%m-%d")

        last_record = (
            db.session.query(Record)
            .filter_by(dataset_id=dataset.dataset)
            .order_by(Record.row_id.desc())
            .first()
        )
        next_id = last_record.row_id + 1 if last_record else 0
        entity = (
            last_record.entity + 1
            if (last_record is not None and last_record.entity is not None)
            else dataset.entity_minimum
        )
        if not (dataset.entity_minimum <= entity <= dataset.entity_maximum):
            flash(
                f"entity id {entity} is outside of range {dataset.entity_minimum} to {dataset.entity_maximum}"
            )
            return redirect(url_for("main.dataset", id=dataset.dataset))

        if "csrf_token" in data:
            del data["csrf_token"]

        record = Record(row_id=next_id, entity=entity)
        extra_data = {}
        for key, val in data.items():
            if hasattr(record, key):
                setattr(record, key, val)
            else:
                extra_data[key] = val
        if extra_data:
            record.data = extra_data

        dataset.records.append(record)
        db.session.add(dataset)
        db.session.commit()

        notes = f"Added record {record.prefix}:{record.reference}"
        change_log = ChangeLog(
            change_type=ChangeType.ADD,
            data=data,
            record_id=record.id,
            notes=notes,
            dataset_id=dataset.dataset,
        )
        db.session.add(change_log)
        db.session.commit()

        return redirect(url_for("main.dataset", id=dataset.dataset))

    if form.errors:
        error_list = [
            {
                "href": f"#{field}",
                "text": f"{' '.join(errors)} {form[field].label.text}",
            }
            for field, errors in form.errors.items()
        ]
        # if any start date fields present - bind to correct form fields
        start_date, format = _collect_start_date(request.form)
        if start_date:
            start_date = datetime.datetime.strptime(start_date, format)
            form["start-date"].data = start_date
    else:
        error_list = None

    breadcrumbs = {
        "items": [
            {"text": "Datasets", "href": url_for("main.index")},
            {
                "text": dataset.name,
                "href": url_for("main.dataset", id=dataset.dataset),
            },
            {"text": "Add a record"},
        ]
    }

    return render_template(
        "add_record.html",
        dataset=dataset,
        form=form,
        form_fields=form_fields,
        error_list=error_list,
        breadcrumbs=breadcrumbs,
    )


@main.route("/dataset/<string:id>/record/<string:record_id>", methods=["GET"])
@login_required
def get_record(id, record_id):
    record = Record.query.filter(Record.dataset_id == id, Record.id == record_id).one()
    return render_template("view_record.html", record=record)


@main.route(
    "/dataset/<string:id>/record/<string:record_id>/edit", methods=["GET", "POST"]
)
@login_required
def edit_record(id, record_id):
    dataset = Dataset.query.get(id)
    record = Record.query.filter(
        Record.dataset_id == dataset.dataset, Record.id == record_id
    ).one()
    builder = FormBuilder(record.dataset.fields, include_edit_notes=True)
    form = builder.build()
    form_fields = builder.form_fields()

    if form.validate_on_submit():
        # capture current record data as "previous" before updating

        change_log = _create_change_log(record, form.data, ChangeType.EDIT)
        dataset.change_log.append(change_log)
        db.session.add(dataset)
        db.session.commit()
        return redirect(url_for("main.dataset", id=dataset.dataset))

    else:
        breadcrumbs = {
            "items": [
                {"text": "Datasets", "href": url_for("main.index")},
                {
                    "text": dataset.name,
                    "href": url_for("main.dataset", id=dataset.dataset),
                },
                {"text": "Edit record"},
            ]
        }

        if form.errors:
            error_list = [
                {
                    "href": f"#{field}",
                    "text": f"{' '.join(errors)} {form[field].label.text}",
                }
                for field, errors in form.errors.items()
            ]
            start_date, format = _collect_start_date(request.form)
            if start_date != record.start_date:
                start_date = datetime.datetime.strptime(start_date, format)
                form["start-date"].data = start_date
        else:
            for field in form_fields:
                if field.field == "start-date":
                    form[field.field].data = record.start_date
                else:
                    form[field.field].data = record.data.get(field.field, None)

            error_list = None

        return render_template(
            "edit_record.html",
            dataset=record.dataset,
            record=record,
            form=form,
            form_fields=form_fields,
            breadcrumbs=breadcrumbs,
            error_list=error_list,
        )


@main.route(
    "/dataset/<string:id>/record/<string:record_id>/archive", methods=["GET", "POST"]
)
def archive_record(id, record_id):
    record = Record.query.filter(Record.dataset_id == id, Record.id == record_id).one()

    if request.method == "GET":
        return render_template("archive_record.html", record=record)

    record.data["end-date"] = datetime.datetime.today().strftime("%Y-%m-%d")
    record.end_date = datetime.datetime.today()

    change_log = ChangeLog(
        change_type=ChangeType.ARCHIVE,
        data=record.data,
        dataset_id=record.dataset_id,
        notes=f"Archived {record.data['prefix']}:{record.data['reference']}",
        record_id=record.id,
    )

    db.session.add(record)
    db.session.add(change_log)
    db.session.commit()

    return redirect(
        url_for("main.get_record", id=record.dataset_id, record_id=record.id)
    )


@main.route("/dataset/<string:id>/schema")
def schema(id):
    dataset = Dataset.query.get(id)
    breadcrumbs = {
        "items": [
            {"text": "Datasets", "href": url_for("main.index")},
            {
                "text": dataset.name,
                "href": url_for("main.dataset", id=dataset.dataset),
            },
            {"text": "Schema"},
        ]
    }
    sub_navigation = {
        "currentPath": url_for("main.schema", id=dataset.dataset),
        "itemsList": [
            {"title": "Records", "url": url_for("main.dataset", id=dataset.dataset)},
            {"title": "Schema", "url": url_for("main.schema", id=dataset.dataset)},
            {"title": "History", "url": url_for("main.history", id=dataset.dataset)},
        ],
    }
    page = {"title": dataset.name, "caption": "Dataset"}
    return render_template(
        "schema.html",
        dataset=dataset,
        breadcrumbs=breadcrumbs,
        sub_navigation=sub_navigation,
        page=page,
    )


@main.route("/dataset/<string:id>/schema.json")
def schema_json(id):
    dataset = Dataset.query.get(id)
    return {
        "dataset": dataset.dataset,
        "fields": [field.to_dict() for field in dataset.fields],
    }


@main.route("/dataset/<string:id>.csv")
def csv(id):
    dataset = Dataset.query.get(id)
    if dataset is not None and dataset.records:
        output = io.StringIO()
        fieldnames = [field.field for field in dataset.sorted_fields()]
        writer = DictWriter(output, fieldnames)
        writer.writeheader()
        for record in dataset.records:
            writer.writerow(record.to_dict())
            csv_output = output.getvalue().encode("utf-8")

        response = make_response(csv_output)
        response.headers[
            "Content-Disposition"
        ] = f"attachment; filename={dataset.dataset}.csv"
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        return response
    else:
        abort(404)


@main.route("/dataset/<string:dataset>/upload", methods=["GET", "POST"])
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
                        return redirect(url_for("main.upload_csv", dataset=ds.dataset))

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
                            change_log = _create_change_log(
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

    return render_template("upload.html", form=form, dataset=ds)


@main.route("/dataset/<string:id>/history")
def history(id):
    dataset = Dataset.query.get(id)
    breadcrumbs = {
        "items": [
            {"text": "Datasets", "href": url_for("main.index")},
            {
                "text": dataset.name,
                "href": url_for("main.dataset", id=dataset.dataset),
            },
            {"text": "History"},
        ]
    }
    sub_navigation = {
        "currentPath": url_for("main.history", id=dataset.dataset),
        "itemsList": [
            {"title": "Records", "url": url_for("main.dataset", id=dataset.dataset)},
            {"title": "Schema", "url": url_for("main.schema", id=dataset.dataset)},
            {"title": "History", "url": url_for("main.history", id=dataset.dataset)},
            {"title": "Changes", "url": url_for("main.change_log", id=dataset.dataset)},
        ],
    }
    page = {"title": dataset.name, "caption": "Dataset"}
    records = []
    for record in dataset.records:
        for change in record.change_log:
            if change.data.get("from") is not None:
                records.append(change.data["from"])
        records.append(record.to_dict())

    return render_template(
        "records.html",
        dataset=dataset,
        breadcrumbs=breadcrumbs,
        sub_navigation=sub_navigation,
        page=page,
        records=records,
        history=True,
    )


def _allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() == "csv"


def _create_change_log(record, data, change_type):
    previous = record.to_dict()
    reference = previous["reference"]

    for key, value in data.items():
        if key not in ["csrf_token", "edit_notes", "csv_file", "entity"]:
            k = key
            if "-date" in k:
                k = k.replace("-date", "_date")
            if hasattr(record, k):
                setattr(record, k, value)
            else:
                v = value
                if isinstance(value, datetime.date):
                    v = date_to_string(value)
                record.data[key] = v

    # if this comes from a form, start date is in the form
    if data.get("year") or data.get("month") or data.get("day"):
        start_date, format = _collect_start_date(data)
        if start_date:
            start_date = datetime.datetime.strptime(start_date, format)
            if start_date != record.start_date:
                record.start_date = start_date
                record.data["start-date"] = start_date.strftime(format)

    # set existing reference as it is not in data
    record.data["reference"] = reference

    # check for end date in the original record and data
    if change_type == ChangeType.ARCHIVE:
        end_date = data.get("end-date")
        if end_date is None:
            record.end_date = datetime.datetime.today()
        else:
            record.end_date = end_date

    edit_notes = data.get("edit_notes", None)
    if edit_notes:
        edit_notes = f"Updated {record.prefix}:{record.reference}. {edit_notes}"

    current = record.to_dict()

    for key, value in previous.items():
        if value is None:
            previous[key] = ""

    for key, value in current.items():
        if value is None:
            current[key] = ""

    change_log = ChangeLog(
        change_type=change_type,
        data={"from": previous, "to": current},
        notes=edit_notes,
        record_id=record.id,
    )
    return change_log


def _order_records(records):
    def sort_key(item):
        if item.get("end-date") is None:
            return datetime.date.max
        else:
            return item.get("end-date")

    ordered = sorted(records, key=sort_key)
    return ordered
