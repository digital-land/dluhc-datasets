"""add missing decription fields

Revision ID: 1fcdb1b367a3
Revises: 8dcfe9d15b1b
Create Date: 2024-01-15 11:21:50.702931

"""
from sqlalchemy.orm.session import Session
from alembic import op
from sqlalchemy import select

import sqlalchemy as sa


from application.models import Dataset, Field, dataset_field


# revision identifiers, used by Alembic.
revision = "1fcdb1b367a3"
down_revision = "8dcfe9d15b1b"
branch_labels = None
depends_on = None

datasets = (
    "development-plan-geography-type",
    "flood-risk-level",
    "flood-risk-type",
    "park-and-garden-grade",
    "planning-application-status",
    "planning-application-type",
    "planning-decision",
    "provision-reason",
    "site-category",
    "tree-preservation-zone-type",
)


def upgrade():
    session = Session(bind=op.get_bind())
    description_field = session.query(Field).filter(Field.field == "description").one()
    for dataset in datasets:
        ds = session.query(Dataset).filter(Dataset.dataset == dataset).one()
        if ds is not None and description_field not in ds.fields:
            ds.fields.append(description_field)
            session.add(ds)
            session.commit()
            print(f"Added description field to {ds.dataset}")


def downgrade():
    session = Session(bind=op.get_bind())
    description_field = session.query(Field).filter(Field.field == "description").one()
    for dataset in datasets:
        ds = session.query(Dataset).filter(Dataset.dataset == dataset).one()
        if ds is not None and description_field in ds.fields:
            ds.fields.remove(description_field)
            session.add(ds)
            session.commit()
            print(f"Removed description field from {ds.dataset}")
