import pytest

from application.extensions import db
from application.models import Dataset, Update, UpdateStatus


def _seed_update(app, dataset_id="example"):
    with app.app_context():
        dataset = Dataset(dataset=dataset_id, name="Example")
        update = Update(dataset=dataset)
        db.session.add_all([dataset, update])
        db.session.commit()
        return update.id


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/dataset/example/process-updates/not-a-uuid"),
        ("post", "/dataset/example/process-updates/not-a-uuid"),
        ("get", "/dataset/example/process-updates/not-a-uuid/cancel"),
    ],
)
def test_update_routes_return_404_for_invalid_update_id(client, method, path):
    response = getattr(client, method)(path)

    assert response.status_code == 404


def test_process_updates_displays_pending_update(client, app):
    update_id = _seed_update(app)

    response = client.get(f"/dataset/example/process-updates/{update_id}")

    assert response.status_code == 200


def test_apply_updates_completes_pending_update(client, app):
    update_id = _seed_update(app)

    response = client.post(f"/dataset/example/process-updates/{update_id}")

    assert response.status_code == 302
    assert response.headers["Location"] == "/dataset/example"
    with app.app_context():
        assert db.session.get(Update, update_id).status == UpdateStatus.COMPLETE


def test_cancel_updates_cancels_pending_update(client, app):
    update_id = _seed_update(app)

    response = client.get(f"/dataset/example/process-updates/{update_id}/cancel")

    assert response.status_code == 302
    assert response.headers["Location"] == "/dataset/example"
    with app.app_context():
        assert db.session.get(Update, update_id).status == UpdateStatus.CANCELLED
