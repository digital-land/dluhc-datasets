import io
from csv import DictWriter

from flask import Blueprint, abort, make_response, redirect, render_template, url_for

from application.extensions import db
from application.forms import FormBuilder
from application.models import Dataset, Record
from application.utils import login_required

main = Blueprint("main", __name__)


@main.route("/")
def index():
    ds = db.session.query(Dataset).order_by(Dataset.dataset).all()
    return render_template("datasets.html", datasets=ds, isHomepage=True)


@main.route("/support")
def support():
    return render_template("support.html")


@main.route("/dataset/<string:name>")
def dataset(name):
    dataset = Dataset.query.get(name)
    breadcrumbs = {
        "items": [
            {"text": "Datasets", "href": url_for("main.index")},
            {"text": dataset.name, "href": url_for("main.dataset", name=name)},
            {"text": "Records"},
        ]
    }
    return render_template("records.html", dataset=dataset, breadcrumbs=breadcrumbs)


@main.route("/dataset/<string:dataset>/add", methods=["GET", "POST"])
@login_required
def add_record(dataset):
    ds = Dataset.query.get(dataset)
    builder = FormBuilder(ds.fields)
    form = builder.build()
    form_fields = builder.form_fields()
    if form.validate_on_submit():
        last_record = (
            db.session.query(Record)
            .filter_by(dataset_id=dataset)
            .order_by(Record.id.desc())
            .first()
        )
        next_id = last_record.id + 1 if last_record else 0
        record = Record(id=next_id, dataset=ds, data=form.data)
        ds.records.append(record)
        db.session.add(ds)
        db.session.commit()
        return redirect(url_for("main.dataset", name=dataset))

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
            {"text": ds.name, "href": url_for("main.dataset", name=dataset)},
            {"text": "Add a record"},
        ]
    }

    return render_template(
        "add_record.html",
        dataset=ds,
        form=form,
        form_fields=form_fields,
        error_list=error_list,
        breadcrumbs=breadcrumbs,
    )


@main.route(
    "/dataset/<string:dataset>/record/<int:record_id>/edit", methods=["GET", "POST"]
)
@login_required
def edit_record(dataset, record_id):
    ds = Dataset.query.get(dataset)
    record = Record.query.filter(
        Record.dataset_id == dataset, Record.id == record_id
    ).one()
    builder = FormBuilder(record.dataset.fields)
    form = builder.build()
    form_fields = builder.form_fields()

    if form.validate_on_submit():
        record.data = form.data
        db.session.add(record)
        db.session.commit()
        return redirect(url_for("main.dataset", name=dataset))

    else:
        for field in form_fields:
            form[field.field].data = record.data.get(field.field, None)

        breadcrumbs = {
            "items": [
                {"text": "Datasets", "href": url_for("main.index")},
                {"text": ds.name, "href": url_for("main.dataset", name=dataset)},
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


@main.route("/dataset/<string:dataset>/schema")
def schema(dataset):
    ds = Dataset.query.get(dataset)
    breadcrumbs = {
        "items": [
            {"text": "Datasets", "href": url_for("main.index")},
            {"text": ds.name, "href": url_for("main.dataset", name=dataset)},
            {"text": "Schema"},
        ]
    }
    return render_template("schema.html", dataset=ds, breadcrumbs=breadcrumbs)


@main.route("/dataset/<string:dataset>.csv")
def csv(dataset):
    ds = Dataset.query.get(dataset)
    if ds is not None:
        output = io.StringIO()
        fieldnames = [field.field for field in ds.sorted_fields()]
        writer = DictWriter(output, fieldnames)
        writer.writeheader()
        for record in ds.records:
            writer.writerow(record.data)
            csv_output = output.getvalue().encode("utf-8")

        response = make_response(csv_output)
        response.headers["Content-Disposition"] = f"attachment; filename={dataset}.csv"
        response.headers["Content-Type"] = "text/csv; charset=utf-8"
        return response
    else:
        abort(404)
