from flask import Blueprint, render_template

from application.extensions import db
from application.models import Dataset

main = Blueprint("main", __name__)


@main.route("/")
def index():
    return render_template("index.html")


@main.route("/dataset")
def datasets():
    ds = db.session.query(Dataset).all()
    return render_template("datasets.html", datasets=ds)


@main.route("/dataset/<string:name>")
def dataset(name):
    dataset = Dataset.query.get(name)
    return render_template("dataset.html", dataset=dataset)


@main.route("/dataset/<string:dataset>/entries")
def entries(dataset):
    ds = Dataset.query.get(dataset)
    return render_template("entries.html", dataset=ds)
