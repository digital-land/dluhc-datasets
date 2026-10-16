import re

import pytest

from application.extensions import db
from application.models import Dataset, Update, UpdateRecord, UpdateStatus


@pytest.fixture(autouse=True)
def _login(client):
    with client.session_transaction() as session:
        session["user"] = {"email": "test@example.com", "login": "test-user"}


def _seed_update(app, dataset_id="example", rows=()):
    with app.app_context():
        dataset = Dataset(dataset=dataset_id, name="Example")
        update = Update(dataset=dataset)
        for row in rows:
            update.records.append(UpdateRecord(data=row))
        db.session.add_all([dataset, update])
        db.session.commit()
        return update.id


def _csrf_token(response):
    return re.search(r'name="csrf_token" value="([^"]+)"', response.text).group(1)


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/dataset/example/process-updates/not-a-uuid"),
        ("post", "/dataset/example/process-updates/not-a-uuid"),
        ("post", "/dataset/example/process-updates/not-a-uuid/cancel"),
    ],
)
def test_update_routes_return_404_for_invalid_update_id(client, method, path):
    response = getattr(client, method)(path)

    assert response.status_code == 404


def test_process_updates_displays_pending_update(client, app):
    update_id = _seed_update(app)

    response = client.get(f"/dataset/example/process-updates/{update_id}")

    assert response.status_code == 200


def test_process_updates_does_not_change_the_database(client, app):
    update_id = _seed_update(app, rows=[{"entity": "1"}])

    response = client.get(f"/dataset/example/process-updates/{update_id}")

    assert response.status_code == 200
    assert "Add record" in response.text
    with app.app_context():
        (row,) = db.session.get(Update, update_id).records
        assert row.new_record is False
        assert row.changes is None


def test_apply_updates_completes_pending_update(client, app):
    update_id = _seed_update(app)

    response = client.post(f"/dataset/example/process-updates/{update_id}")

    assert response.status_code == 302
    assert response.headers["Location"] == "/dataset/example"
    with app.app_context():
        assert db.session.get(Update, update_id).status == UpdateStatus.COMPLETE


def test_cancel_updates_cancels_pending_update(client, app):
    update_id = _seed_update(app)

    response = client.post(f"/dataset/example/process-updates/{update_id}/cancel")

    assert response.status_code == 302
    assert response.headers["Location"] == "/dataset/example"
    with app.app_context():
        assert db.session.get(Update, update_id).status == UpdateStatus.CANCELLED


def test_cancel_updates_does_not_accept_get(client, app):
    update_id = _seed_update(app)

    response = client.get(f"/dataset/example/process-updates/{update_id}/cancel")

    assert response.status_code == 405
    with app.app_context():
        assert db.session.get(Update, update_id).status == UpdateStatus.PENDING


@pytest.mark.parametrize("action", ["", "/cancel"])
def test_update_actions_reject_post_without_csrf_token(client, app, action):
    app.config["WTF_CSRF_ENABLED"] = True
    update_id = _seed_update(app, rows=[{"entity": "1"}])

    response = client.post(f"/dataset/example/process-updates/{update_id}{action}")

    assert response.status_code == 400
    assert "Your changes were not saved" in response.text
    with app.app_context():
        assert db.session.get(Update, update_id).status == UpdateStatus.PENDING


@pytest.mark.parametrize(
    ("action", "status"),
    [("", UpdateStatus.COMPLETE), ("/cancel", UpdateStatus.CANCELLED)],
)
def test_update_actions_accept_csrf_token_from_review_page(client, app, action, status):
    app.config["WTF_CSRF_ENABLED"] = True
    update_id = _seed_update(app, rows=[{"entity": "1"}])
    review_page = client.get(f"/dataset/example/process-updates/{update_id}")

    response = client.post(
        f"/dataset/example/process-updates/{update_id}{action}",
        data={"csrf_token": _csrf_token(review_page)},
    )

    assert response.status_code == 302
    with app.app_context():
        assert db.session.get(Update, update_id).status == status
