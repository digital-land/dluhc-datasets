import datetime
import io
from collections import OrderedDict
from csv import DictWriter

import requests
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

from application.extensions import db
from application.forms import FormBuilder
from application.models import ChangeLog, ChangeType, Dataset, Record, create_change_log
from application.utils import collect_start_date, login_required

main = Blueprint("main", __name__)


def get_tab_list(dataset):
    return [
        {"title": "Records", "url": url_for("main.dataset", id=dataset.dataset)},
        {"title": "Links", "url": url_for("main.links", id=dataset.dataset)},
        {"title": "History", "url": url_for("main.history", id=dataset.dataset)},
        {"title": "Changes", "url": url_for("main.change_log", id=dataset.dataset)},
    ]


@main.route("/")
@main.route("/index")
def index():
    ds = (
        db.session.query(Dataset)
        .filter(Dataset.end_date.is_(None))
        .order_by(Dataset.dataset)
        .all()
    )
    return render_template("datasets.html", datasets=ds, isHomepage=True)


@main.route("/index.json")
def index_json():
    ds = (
        db.session.query(Dataset)
        .filter(Dataset.end_date.is_(None))
        .order_by(Dataset.dataset)
        .all()
    )
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
    dataset = Dataset.query.get_or_404(id)

    breadcrumbs = {
        "items": [
            {"text": "Datasets", "href": url_for("main.index")},
            {"text": dataset.name, "href": url_for("main.dataset", id=id)},
            {"text": "Records"},
        ]
    }
    sub_navigation = {
        "currentPath": url_for("main.dataset", id=dataset.dataset),
        "itemsList": get_tab_list(dataset),
    }
    page = {"title": dataset.name, "caption": "Dataset"}
    records = [record for record in dataset.records]
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
    dataset = Dataset.query.get_or_404(id)
    return {
        "dataset": dataset.dataset,
        "name": dataset.name,
        "fields": [field.field for field in dataset.fields],
        "records": [r.to_dict() for r in dataset.records],
    }


@main.route("/dataset/<string:id>/change-log")
def change_log(id):
    dataset = Dataset.query.get_or_404(id)
    if dataset.end_date is not None:
        abort(404)
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
        "itemsList": get_tab_list(dataset),
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
    dataset = Dataset.query.get_or_404(id)
    if dataset.end_date is not None:
        abort(404)
    builder = FormBuilder(dataset.fields)
    form = builder.build()
    form_fields = builder.form_fields()
    if form.validate_on_submit():
        data = form.data

        start_date, _ = collect_start_date(request.form)
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
        start_date, format = collect_start_date(request.form)
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
        "add-record.html",
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
    return render_template("view-record.html", record=record)


@main.route(
    "/dataset/<string:id>/record/<string:record_id>/edit", methods=["GET", "POST"]
)
@login_required
def edit_record(id, record_id):
    dataset = Dataset.query.get_or_404(id)
    if dataset.end_date is not None:
        abort(404)
    record = Record.query.filter(
        Record.dataset_id == dataset.dataset, Record.id == record_id
    ).one()
    builder = FormBuilder(
        record.dataset.fields, include_edit_notes=True, require_reference=False
    )
    form = builder.build()
    form_fields = builder.form_fields()

    if form.validate_on_submit():
        # capture current record data as "previous" before updating

        change_log = create_change_log(record, form.data, ChangeType.EDIT)
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
            start_date, format = collect_start_date(request.form)
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
            "edit-record.html",
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
        return render_template("archive-record.html", record=record)

    record.data["end-date"] = datetime.datetime.today().strftime("%Y-%m-%d")
    record.end_date = datetime.datetime.today()

    change_log = ChangeLog(
        change_type=ChangeType.ARCHIVE,
        data=record.data,
        dataset_id=record.dataset_id,
        notes=f"Archived {record.prefix}:{record.reference}",
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
    dataset = Dataset.query.get_or_404(id)
    if dataset.end_date is not None:
        abort(404)
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
        "itemsList": get_tab_list(dataset),
    }
    page = {"title": dataset.name, "caption": "Dataset"}
    return render_template(
        "schema.html",
        dataset=dataset,
        breadcrumbs=breadcrumbs,
        sub_navigation=sub_navigation,
        page=page,
    )


@main.route("/dataset/<string:id>/links")
def links(id):
    from flask import current_app

    dataset = Dataset.query.get_or_404(id)
    if dataset.end_date is not None:
        abort(404)
    breadcrumbs = {
        "items": [
            {"text": "Datasets", "href": url_for("main.index")},
            {
                "text": dataset.name,
                "href": url_for("main.dataset", id=dataset.dataset),
            },
            {"text": "Links"},
        ]
    }
    sub_navigation = {
        "currentPath": url_for("main.links", id=dataset.dataset),
        "itemsList": get_tab_list(dataset),
    }
    page = {"title": dataset.name, "caption": "Dataset"}

    specification_url = f"{current_app.config['SPECIFICATION_REPO_URL']}/blob/main/content/dataset/{dataset.dataset}.md"
    consideration_url = (
        f"{current_app.config['PLANNING_DATA_DESIGN_URL']}/planning-consideration/{dataset.consideration}"
        if dataset.consideration
        else None
    )

    platform_url = f"{current_app.config['PLATFORM_URL']}/dataset/{dataset.dataset}"
    try:
        resp = requests.get(platform_url)
        resp.raise_for_status()
    except requests.exceptions.HTTPError:
        platform_url = None
    except Exception:
        platform_url = None

    return render_template(
        "links.html",
        dataset=dataset,
        breadcrumbs=breadcrumbs,
        sub_navigation=sub_navigation,
        page=page,
        specification_url=specification_url,
        consideration_url=consideration_url,
        platform_url=platform_url,
    )


@main.route("/dataset/<string:id>/schema.json")
def schema_json(id):
    dataset = Dataset.query.get_or_404(id)
    return {
        "dataset": dataset.dataset,
        "fields": [field.to_dict() for field in dataset.fields],
    }


@main.route("/dataset/<string:id>.csv")
def csv(id):
    dataset = Dataset.query.get_or_404(id)
    if dataset.end_date is not None:
        abort(404)
    if dataset.records:
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


@main.route("/dataset/<string:id>/history")
def history(id):
    dataset = Dataset.query.get_or_404(id)
    if dataset.end_date is not None:
        abort(404)
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
        "itemsList": get_tab_list(dataset),
    }
    page = {"title": dataset.name, "caption": "Dataset"}
    records = []
    for record in dataset.records:
        for change in record.change_log:
            if change.data.get("from") is not None:
                records.append(change.data["from"])
        records.append(record)

    return render_template(
        "records.html",
        dataset=dataset,
        breadcrumbs=breadcrumbs,
        sub_navigation=sub_navigation,
        page=page,
        records=records,
        history=True,
    )


@main.route("/dataset/<string:id>/finder")
def finder(id):
    dataset = Dataset.query.get_or_404(id)
    breadcrumbs = {
        "items": [
            {"text": "Datasets", "href": url_for("main.index")},
            {
                "text": dataset.name,
                "href": url_for("main.dataset", id=dataset.dataset),
            },
            {"text": "Category Finder"},
        ]
    }
    active_records = sorted(
        [record for record in dataset.records if record.end_date is None],
        key=lambda record: record.data["name"],
    )
    return render_template(
        "finder.html",
        dataset=dataset,
        breadcrumbs=breadcrumbs,
        active_records=active_records,
    )
