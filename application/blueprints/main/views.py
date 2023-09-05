from flask import Blueprint, redirect, render_template, url_for

from application.extensions import db
from application.forms import FormBuilder
from application.models import Dataset, Entry
from application.utils import login_required

main = Blueprint("main", __name__)


@main.route("/")
def datasets():
    ds = db.session.query(Dataset).order_by(Dataset.dataset).all()
    return render_template("datasets.html", datasets=ds, isHomepage=True)


@main.route("/dataset/<string:name>")
def dataset(name):
    dataset = Dataset.query.get(name)
    breadcrumbs = {
        "items": [
            {"text": "Datasets", "href": "/dataset"},
            {"text": dataset.name, "href": f"/dataset/{name}"},
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
        last_entry = (
            db.session.query(Entry)
            .filter_by(dataset_id=dataset)
            .order_by(Entry.id.desc())
            .first()
        )
        next_id = last_entry.id + 1 if last_entry else 0
        entry = Entry(id=next_id, dataset=ds, data=form.data)
        ds.entries.append(entry)
        db.session.add(ds)
        db.session.commit()
        return redirect(url_for("main.dataset", name=dataset))
    return render_template(
        "add_record.html", dataset=ds, form=form, form_fields=form_fields
    )


@main.route("/dataset/<string:dataset>/record/<int:record_id>", methods=["GET", "POST"])
@login_required
def edit_record(dataset, record_id):
    record = Entry.query.filter(
        Entry.dataset_id == dataset, Entry.id == record_id
    ).one()
    return render_template("edit_record.html", dataset=record.dataset, record=record)


@main.route("/dataset/<string:dataset>/schema")
def schema(dataset):
    ds = Dataset.query.get(dataset)
    breadcrumbs = {
        "items": [
            {"text": "Datasets", "href": "/dataset"},
            {"text": ds.name, "href": {{url_for("main.dataset", name=dataset)}}},
            {"text": "Schema", "href": {{url_for("main.schema", name=dataset)}}},
        ]
    }
    return render_template("schema.html", dataset=ds, breadcrumbs=breadcrumbs)


# will give a file download
# @main.route("/dataset/<string:dataset>.csv")
# def csv(dataset):
#     pass
