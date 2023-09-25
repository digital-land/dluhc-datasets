import datetime
import io
from csv import DictWriter

from flask import Blueprint, abort, make_response, redirect, render_template, url_for

from application.extensions import db
from application.forms import FormBuilder
from application.models import Dataset, Record, RecordVersion
from application.utils import login_required

main = Blueprint("main", __name__)


@main.route("/")
def index():
    ds = db.session.query(Dataset).order_by(Dataset.dataset).all()
    return render_template("datasets.html", datasets=ds, isHomepage=True)


@main.route("/support")
def support():
    breadcrumbs = {
        "items": [
            {"text": "DLUHC Datasets", "href": url_for("main.index")},
            {"text": "Support"},
        ]
    }
    return render_template("support.html", breadcrumbs=breadcrumbs)


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
        ],
    }
    page = {"title": dataset.name, "caption": "Dataset"}
    return render_template(
        "records.html",
        dataset=dataset,
        breadcrumbs=breadcrumbs,
        sub_navigation=sub_navigation,
        page=page,
    )


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
        ],
    }
    page = {"title": dataset.name, "caption": "Dataset"}
    return render_template(
        "history.html",
        dataset=dataset,
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
        # set prefix to as it is not in form
        data["prefix"] = dataset.dataset

        last_record = (
            db.session.query(Record)
            .filter_by(dataset_id=dataset.dataset)
            .order_by(Record.row_id.desc())
            .first()
        )
        next_id = last_record.row_id + 1 if last_record else 0

        record = Record(row_id=next_id, data=data)
        dataset.records.append(record)
        db.session.add(dataset)
        db.session.commit()
        return redirect(url_for("main.dataset", id=dataset.dataset))

    if form.errors:
        error_list = [
            {"href": f"#{field}", "text": ",".join(errors)}
            for field, errors in form.errors.items()
        ]
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


@main.route(
    "/dataset/<string:id>/record/<string:record_id>/edit", methods=["GET", "POST"]
)
@login_required
def edit_record(id, record_id):
    dataset = Dataset.query.get(id)
    record = Record.query.filter(
        Record.dataset_id == dataset.dataset, Record.id == record_id
    ).one()
    builder = FormBuilder(record.dataset.fields)
    form = builder.build()
    form_fields = builder.form_fields()

    if form.validate_on_submit():
        # capture current record data before updating
        current_version = record.data.copy()

        # update record data
        for key, value in form.data.items():
            record.data[key] = value

        # end current version and store data
        current_version["end-date"] = datetime.datetime.today().strftime("%Y-%m-%d")
        version = RecordVersion(record_id=record.id, data=current_version)

        record.versions.append(version)
        db.session.add(record)
        db.session.commit()
        return redirect(url_for("main.dataset", id=dataset.dataset))

    else:
        for field in form_fields:
            form[field.field].data = record.data.get(field.field, None)

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

        return render_template(
            "edit_record.html",
            dataset=record.dataset,
            record=record,
            form=form,
            form_fields=form_fields,
            breadcrumbs=breadcrumbs,
        )


@main.route("/dataset/<string:id>/record/<string:record_id>")
def end_record(id, record_id):
    dataset = Dataset.query.get(id)
    breadcrumbs = {
        "items": [
            {"text": "Datasets", "href": url_for("main.index")},
            {
                "text": dataset.name,
                "href": url_for("main.dataset", id=dataset.dataset),
            },
            {"text": "View record"},
        ]
    }
    page = {"title": dataset.name, "caption": "Dataset"}
    return render_template(
        "view_record.html",
        dataset=dataset,
        breadcrumbs=breadcrumbs,
        page=page,
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


@main.route("/dataset/<string:id>.csv")
def csv(id):
    dataset = Dataset.query.get(id)
    if dataset is not None and dataset.records:
        output = io.StringIO()
        fieldnames = [field.field for field in dataset.sorted_fields()]
        writer = DictWriter(output, fieldnames)
        writer.writeheader()
        for record in dataset.records:
            writer.writerow(record.data)
            csv_output = output.getvalue().encode("utf-8")

        response = make_response(csv_output)
        response.headers[
            "Content-Disposition"
        ] = f"attachment; filename={dataset.dataset}.csv"
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        return response
    else:
        abort(404)
