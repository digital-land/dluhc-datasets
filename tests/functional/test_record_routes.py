"""
Functional tests for record routes:
- archive
- unarchive
- edit

These tests exercise Flask routes + database state.
"""
import datetime
import uuid

import pytest

from application.extensions import db
from application.models import ChangeLog, ChangeType, Dataset, Record, Field

def _login(client):
    # Match how your app checks auth in login_required
    with client.session_transaction() as session:
        session["user"] = {"email": "test@example.com"}


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
    archived=False,
    end_date="2025-01-01",
    data=None,
):
    record_id = uuid.uuid4()
    with app.app_context():
        # Ensure dataset exists
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

        if archived:
            # Keep both representations consistent
            record.end_date = datetime.datetime.strptime(end_date, "%Y-%m-%d").date()
            record.data["end-date"] = end_date

        db.session.add(record)
        db.session.commit()

    return record_id


def test_archive_page_loads(client, app):
    _login(client)
    dataset_id = _seed_dataset(app)
    record_id = _seed_record(app, dataset_id)

    resp = client.get(f"/dataset/{dataset_id}/record/{record_id}/archive")
    assert resp.status_code == 200


def test_archive_post_sets_end_date(client, app):
    _login(client)
    dataset_id = _seed_dataset(app)
    record_id = _seed_record(app, dataset_id)

    resp = client.post(
        f"/dataset/{dataset_id}/record/{record_id}/archive",
        data={"end_date": "2025-02-01"},
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    with app.app_context():
        rec = Record.query.get(record_id)
        assert rec.end_date == datetime.date(2025, 2, 1)
        # you set record.data["end-date"] in archive_record
        assert rec.data.get("end-date") == "2025-02-01"

        change = (
            ChangeLog.query.filter(ChangeLog.record_id == record_id)
            .order_by(ChangeLog.created_date.desc())
            .first()
        )
        assert change is not None
        assert change.change_type == ChangeType.ARCHIVE


def test_unarchive_post_clears_end_date_and_json(client, app):
    _login(client)
    dataset_id = _seed_dataset(app)
    record_id = _seed_record(app, dataset_id, archived=True, end_date="2025-01-01")

    resp = client.post(
        f"/dataset/{dataset_id}/record/{record_id}/unarchive",
        follow_redirects=False,
    )
    assert resp.status_code in (302, 303)

    with app.app_context():
        rec = Record.query.get(record_id)
        assert rec.end_date is None
        assert "end-date" not in rec.data

        change = (
            ChangeLog.query.filter(ChangeLog.record_id == record_id)
            .order_by(ChangeLog.created_date.desc())
            .first()
        )
        assert change is not None
        assert change.change_type == ChangeType.EDIT
        assert "Unarchived" in (change.notes or "")


def test_unarchive_active_record_returns_400(client, app):
    _login(client)
    dataset_id = _seed_dataset(app)
    record_id = _seed_record(app, dataset_id, archived=False)

    resp = client.post(f"/dataset/{dataset_id}/record/{record_id}/unarchive")
    assert resp.status_code == 400


def test_edit_post_updates_data_and_creates_changelog(client, app):
    """
    Route-level test: POSTing to edit updates the record and writes an EDIT ChangeLog.

    Key detail: FormBuilder only creates WTForms fields that exist in dataset.fields.
    So we must seed the dataset with a 'region' field, otherwise the posted 'region'
    value will be ignored and no update will occur.
    """
    _login(client)

    dataset_id = _seed_dataset(app)

    # Seed the dataset with the field(s) that the edit form should expose
    with app.app_context():
        dataset = Dataset.query.get(dataset_id)

        # Ensure this dataset has a 'region' field so the POSTed value is accepted
        field = Field(field="region", datatype="curie", name="Region")
        db.session.add(field)
        db.session.commit()

        # Link the field to the dataset (many-to-many)
        dataset.fields.append(field)
        db.session.add(dataset)
        db.session.commit()

    record_id = _seed_record(app, dataset_id, data={"region": "local-authority:ABC"})

    resp = client.post(
        f"/dataset/{dataset_id}/record/{record_id}/edit",
        data={
            # your edit route reads entity from request.form (and Record.entity is separate to Record.data)
            "entity": "123",
            # required because include_edit_notes=True
            "edit_notes": "test edit",
            # field we expect to be written into record.data
            "region": "local-authority:XYZ",
        },
        follow_redirects=False,
    )

    # edit_record redirects back to the dataset page on success
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

        # Optional extra checks: ensure changelog captured the from/to values
        assert change.data is not None
        assert change.data["from"].get("region") == "local-authority:ABC"
        assert change.data["to"].get("region") == "local-authority:XYZ"