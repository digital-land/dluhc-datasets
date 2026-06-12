"""
Functional tests for record routes:
- edit (including end-date)

These tests exercise Flask routes + database state.
"""
import datetime
import uuid

import pytest

from application.extensions import db
from application.models import ChangeLog, ChangeType, Dataset, Record, Field


def _login(client):
    with client.session_transaction() as session:
        session["user"] = {"email": "test@example.com", "login": "test-user"}


def _seed_dataset(app, dataset_id="design-code-status"):
    with app.app_context():
        dataset = Dataset(dataset=dataset_id, name="Design code status")
        db.session.add(dataset)
        db.session.commit()
        return dataset_id


def _seed_record(
    app,
    dataset_id="design-code-status",
    *,
    end_date=None,
    data=None,
):
    record_id = uuid.uuid4()
    with app.app_context():
        if not Dataset.query.get(dataset_id):
            db.session.add(Dataset(dataset=dataset_id, name="Design code status"))

        base_data = {"name": "Test record"}
        if data:
            base_data.update(data)

        record = Record(
            id=record_id,
            row_id=1,
            entity=123,
            prefix=dataset_id,
            reference="abc",
            dataset_id=dataset_id,
            data=base_data,
        )

        if end_date:
            record.end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
            record.data["end-date"] = end_date

        db.session.add(record)
        db.session.commit()

    return record_id


def test_edit_post_updates_data_and_creates_changelog(client, app):
    """
    POSTing to edit updates the record and writes an EDIT ChangeLog.
    """
    _login(client)

    dataset_id = _seed_dataset(app)

    with app.app_context():
        dataset = Dataset.query.get(dataset_id)

        field = Field(field="region", datatype="curie", name="Region")
        db.session.add(field)
        db.session.commit()

        dataset.fields.append(field)
        db.session.add(dataset)
        db.session.commit()

    record_id = _seed_record(app, dataset_id, data={"region": "local-authority:ABC"})

    resp = client.post(
        f"/dataset/{dataset_id}/record/{record_id}/edit",
        data={
            "entity": "123",
            "edit_notes": "test edit",
            "region": "local-authority:XYZ",
        },
        follow_redirects=False,
    )

    assert resp.status_code in (302, 303)

    with app.app_context():
        rec = Record.query.get(record_id)
        assert rec.data.get("region") == "local-authority:XYZ"

        change = (
            ChangeLog.query.filter(ChangeLog.record_id == record_id)
            .order_by(ChangeLog.created_date.desc())
            .first()
        )
        assert change is not None
        assert change.change_type == ChangeType.EDIT
        assert change.data is not None
        assert change.data["from"].get("region") == "local-authority:ABC"
        assert change.data["to"].get("region") == "local-authority:XYZ"


def test_edit_post_sets_end_date(client, app):
    """
    Setting an end-date via the edit form marks the record as ended.
    """
    _login(client)

    dataset_id = _seed_dataset(app)

    with app.app_context():
        dataset = Dataset.query.get(dataset_id)

        field = Field(field="end-date", datatype="datetime", name="End date")
        db.session.add(field)
        db.session.commit()

        dataset.fields.append(field)
        db.session.add(dataset)
        db.session.commit()

    record_id = _seed_record(app, dataset_id)

    resp = client.post(
        f"/dataset/{dataset_id}/record/{record_id}/edit",
        data={
            "entity": "123",
            "edit_notes": "record is no longer active",
            "end-date-day": "01",
            "end-date-month": "02",
            "end-date-year": "2025",
        },
        follow_redirects=False,
    )

    assert resp.status_code in (302, 303)

    with app.app_context():
        rec = Record.query.get(record_id)
        assert rec.end_date == datetime.date(2025, 2, 1)

        change = (
            ChangeLog.query.filter(ChangeLog.record_id == record_id)
            .order_by(ChangeLog.created_date.desc())
            .first()
        )
        assert change is not None
        assert change.change_type == ChangeType.EDIT


def test_edit_post_clears_end_date(client, app):
    """
    Clearing an end-date via the edit form reinstates the record.
    """
    _login(client)

    dataset_id = _seed_dataset(app)

    with app.app_context():
        dataset = Dataset.query.get(dataset_id)

        field = Field(field="end-date", datatype="datetime", name="End date")
        db.session.add(field)
        db.session.commit()

        dataset.fields.append(field)
        db.session.add(dataset)
        db.session.commit()

    record_id = _seed_record(app, dataset_id, end_date="2025-01-01")

    resp = client.post(
        f"/dataset/{dataset_id}/record/{record_id}/edit",
        data={
            "entity": "123",
            "edit_notes": "record is active again",
            "end-date": "",
        },
        follow_redirects=False,
    )

    assert resp.status_code in (302, 303)

    with app.app_context():
        rec = Record.query.get(record_id)
        assert rec.end_date is None

        change = (
            ChangeLog.query.filter(ChangeLog.record_id == record_id)
            .order_by(ChangeLog.created_date.desc())
            .first()
        )
        assert change is not None
        assert change.change_type == ChangeType.EDIT


def test_edit_post_records_github_login(client, app):
    """
    GitHub login is recorded in the change log when a user edits a record.
    """
    _login(client)

    dataset_id = _seed_dataset(app)

    with app.app_context():
        dataset = Dataset.query.get(dataset_id)

        field = Field(field="region", datatype="curie", name="Region")
        db.session.add(field)
        db.session.commit()

        dataset.fields.append(field)
        db.session.add(dataset)
        db.session.commit()

    record_id = _seed_record(app, dataset_id, data={"region": "local-authority:ABC"})

    resp = client.post(
        f"/dataset/{dataset_id}/record/{record_id}/edit",
        data={
            "entity": "123",
            "edit_notes": "test edit",
            "region": "local-authority:XYZ",
        },
        follow_redirects=False,
    )

    assert resp.status_code in (302, 303)

    with app.app_context():
        change = (
            ChangeLog.query.filter(ChangeLog.record_id == record_id)
            .order_by(ChangeLog.created_date.desc())
            .first()
        )
        assert change.github_login == "test-user"