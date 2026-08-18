"""remove company record 2800000 with incorrect reference

Revision ID: b7d41e6a92c3
Revises: 265314c786fe
Create Date: 2026-08-18 10:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'b7d41e6a92c3'
down_revision = '265314c786fe'
branch_labels = None
depends_on = None

DATASET = 'company'
ENTITY = 2800000
REFERENCE = 'prior-partners'


def upgrade():
    # The reference was entered incorrectly and there is no way to edit one in
    # the application, so remove the record and add it again with the correct
    # reference. The reference is matched in both places it can live: the
    # column, and the data blob it gets copied into when a record is edited.
    # change_log rows for the record go with it via ON DELETE CASCADE.
    result = op.get_bind().execute(
        sa.text(
            """
            DELETE FROM record
            WHERE dataset_id = :dataset
              AND entity = :entity
              AND (
                reference = :reference
                OR (reference IS NULL AND data ->> 'reference' = :reference)
              )
            """
        ),
        {"dataset": DATASET, "entity": ENTITY, "reference": REFERENCE},
    )
    print(f"removed {result.rowcount} {DATASET} record(s) for entity {ENTITY}")


def downgrade():
    # The record cannot be restored here - add it again through the application.
    pass
