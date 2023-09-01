from flask import Blueprint, render_template, request

from application.extensions import db
from application.forms import FormBuilder
from application.models import Dataset
from application.utils import login_required

main = Blueprint("main", __name__)


@main.route("/")
def index():
    return render_template("index.html")


@main.route("/dataset")
@login_required
def datasets():
    ds = db.session.query(Dataset).all()
    return render_template("datasets.html", datasets=ds, isHomepage=True)


@main.route("/dataset/<string:name>")
def dataset(name):
    dataset = Dataset.query.get(name)
    breadcrumbs = {
        "items": [
            {"text": "Datasets", "href": "/dataset"},
            {"text": dataset.name, "href": "/dataset/" + name},
            {"text": "Records", "href": "/dataset/" + name},
        ]
    }
    return render_template("entries.html", dataset=dataset, breadcrumbs=breadcrumbs)


@main.route("/dataset/<string:dataset>/add", methods=["GET", "POST"])
def add_entry(dataset):
    ds = Dataset.query.get(dataset)
    builder = FormBuilder()
    for field in ds.fields:
        builder.with_field(field.field, field.datatype)
    form = builder.build()
    if request.method == "POST":
        # do something with form
        return render_template("add_entry.html", dataset=ds, form=form)
    else:
        return render_template("add_entry.html", dataset=ds, form=form)


@main.route("/dataset/<string:dataset>/schema")
def schema(dataset):
    ds = Dataset.query.get(dataset)
    breadcrumbs = {
        "items": [
            {"text": "Datasets", "href": "/dataset"},
            {"text": ds.name, "href": "/dataset/" + dataset},
            {"text": "Schema", "href": "/" + dataset + "/schema"},
        ]
    }
    return render_template("schema.html", dataset=ds, breadcrumbs=breadcrumbs)


# will give a file download
# @main.route("/dataset/<string:dataset>.csv")
# def csv(dataset):
#     pass
