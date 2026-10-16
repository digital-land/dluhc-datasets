"""
Record values come from forms and csv uploads, so they must be shown as text
and never interpreted as html.
"""
import uuid

import pytest

from application.extensions import db
from application.models import Dataset, Field, Record, Update, UpdateRecord

SCRIPT = "<script>alert(1)</script>"
ESCAPED_SCRIPT = "&lt;script&gt;alert(1)&lt;/script&gt;"
NON_BREAKING_HYPHEN = "‑"


@pytest.fixture(autouse=True)
def _login(client):
    with client.session_transaction() as session:
        session["user"] = {"email": "test@example.com", "login": "test-user"}


def _seed_dataset(app):
    with app.app_context():
        dataset = Dataset(dataset="example", name="Example")
        for field, datatype in [
            ("entity", "integer"),
            ("name", "string"),
            ("reference", "string"),
            ("notes", "text"),
            ("website", "url"),
        ]:
            dataset.fields.append(Field(field=field, datatype=datatype, name=field))
        db.session.add(dataset)
        db.session.commit()


def _assert_escaped(html):
    assert SCRIPT not in html
    assert ESCAPED_SCRIPT in html
    # & is escaped once, so the browser shows it as typed
    assert "Hammersmith &amp; Fulham" in html
    assert "&amp;amp;" not in html
    # hyphens are swapped for the non-breaking hyphen character, not an html entity
    assert f"https://www{NON_BREAKING_HYPHEN}example.gov.uk/" in html
    assert "&#8209;" not in html
    assert "&amp;#8209;" not in html


def test_dataset_page_escapes_record_values(client, app):
    _seed_dataset(app)
    with app.app_context():
        db.session.add(
            Record(
                id=uuid.uuid4(),
                row_id=1,
                entity=1,
                prefix="example",
                reference="ref",
                dataset_id="example",
                data={
                    "name": SCRIPT,
                    "notes": "Hammersmith & Fulham",
                    "website": "https://www-example.gov.uk/",
                },
            )
        )
        db.session.commit()

    response = client.get("/dataset/example")

    assert response.status_code == 200
    _assert_escaped(response.text)


def test_review_page_escapes_uploaded_values(client, app):
    _seed_dataset(app)
    with app.app_context():
        update = Update(dataset_id="example")
        update.records.append(
            UpdateRecord(
                data={
                    "entity": "1",
                    "name": SCRIPT,
                    "notes": "Hammersmith & Fulham",
                    "website": "https://www-example.gov.uk/",
                }
            )
        )
        db.session.add(update)
        db.session.commit()
        update_id = update.id

    response = client.get(f"/dataset/example/process-updates/{update_id}")

    assert response.status_code == 200
    _assert_escaped(response.text)
