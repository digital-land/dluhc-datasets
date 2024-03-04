"""update design code category

Revision ID: 7b15121db54b
Revises: 9f3288599d13
Create Date: 2024-03-04 10:30:03.516141

"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.orm import Session
from application.models import Dataset

# revision identifiers, used by Alembic.
revision = '7b15121db54b'
down_revision = '9f3288599d13'
branch_labels = None
depends_on = None


def upgrade():
    session = Session(bind=op.get_bind())
    dataset = session.query(Dataset).get("design-code-category")
    renamed = Dataset(dataset="design-code-characteristic", name="Design code characteristic")

    renamed.entity_minimum = dataset.entity_minimum
    renamed.entity_maximum = dataset.entity_maximum
    session.add(renamed)
    session.commit()

    for record in dataset.records:
        record.dataset_id = "design-code-characteristic"
        record.prefix = "design-code-characteristic"
        session.add(record)
        session.commit()

    for change_log in dataset.change_log:
        change_log.dataset_id = "design-code-characteristic"
        session.add(change_log)
        session.commit()

    op.execute(
        "UPDATE dataset_field SET dataset = 'design-code-characteristic' WHERE dataset = 'design-code-category'"
    )
    session.delete(dataset)
    session.commit()


def downgrade():
    session = Session(bind=op.get_bind())
    dataset = session.query(Dataset).get("design-code-characteristic")

    renamed = Dataset(dataset="design-code-category", name="Design code category")
    renamed.entity_minimum = dataset.entity_minimum
    renamed.entity_maximum = dataset.entity_maximum
    session.add(renamed)
    session.commit()

    for record in dataset.records:
        record.dataset_id = "design-code-category"
        record.prefix = "design-code-category"
        session.add(record)
        session.commit()

    for change_log in dataset.change_log:
        change_log.dataset_id = "design-code-category"
        session.add(change_log)
        session.commit()

    op.execute("UPDATE dataset_field SET dataset = 'design-code-category' WHERE dataset = 'design-code-characteristic'")

    session.delete(dataset)
    session.commit()
