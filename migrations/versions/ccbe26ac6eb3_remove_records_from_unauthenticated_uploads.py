"""remove records added through the unauthenticated upload routes

Revision ID: ccbe26ac6eb3
Revises: b7d41e6a92c3
Create Date: 2026-10-16 12:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ccbe26ac6eb3'
down_revision = 'b7d41e6a92c3'
branch_labels = None
depends_on = None

# Records added between 18 and 20 September 2026 through the csv upload and
# update routes, which did not require a login at the time. Taken from the rows
# the nightly register export first picked up in commits 0005b67 and 4b42220.
#
# Each record is matched on dataset, entity and reference together, so a genuine
# record that shares an entity number is never removed, and an environment that
# does not have a record simply deletes nothing.
RECORDS = [
    # (dataset, entity, reference)
    ("company", 2777001, "FORMULA5337"),
    ("company", 2777002, "DDE5337"),
    ("company", 2777003, "HYPER5337"),
    ("company", 2777004, "SSTI5337A"),
    ("company", 2777005, "SSTI5337B"),
    ("company", 2777006, "SSTI5337C"),
    ("company", 2777007, "SSTI5337D"),
    ("company", 2777008, "SSTI5337E"),
    ("company", 2777009, "SSTI5337F"),
    ("company", 2777010, "FILE5337"),
    ("company", 2777011, "SSRFI5337"),
    ("company", 2777012, "SSTI5337G"),
    ("company", 2777013, "TRAV5337"),
    ("company", 2888001, "FORMULA4035"),
    ("company", 2888002, "SSTI4035"),
    ("company", 2888888, "PROBE4035INS"),
    ("company", 2999999, "PROBE999DEV"),
    ("permitted-development-right", 11994035, "ARTEX-i4035-SSRF"),
    ("permitted-development-right", 11994036, "ARTEX-i4035-P1"),
    ("permitted-development-right", 11994037, "ARTEX-i4035-BN"),
    ("permitted-development-right", 11994038, "ARTEX-i4035-FL"),
    ("permitted-development-right", 11995000, "PDR5337-0"),
    ("permitted-development-right", 11995001, "PDR5337-1"),
    ("permitted-development-right", 11995002, "PDR5337-2"),
    ("permitted-development-right", 11995003, "PDR5337-3"),
    ("permitted-development-right", 11995004, "PDR5337-4"),
    ("permitted-development-right", 11995005, "PDR5337-5"),
    ("permitted-development-right", 11995006, "PDR5337-6"),
    ("permitted-development-right", 11999999, "ARTEX-SSRF-1"),
]


def upgrade():
    bind = op.get_bind()
    update_ids = set()

    for dataset, entity, reference in RECORDS:
        params = {"dataset": dataset, "entity": entity, "reference": reference}

        # The reference is matched in both places it can live: the column, and
        # the data blob it gets copied into when a record is edited. change_log
        # rows for the record go with it via ON DELETE CASCADE.
        deleted = bind.execute(
            sa.text(
                """
                DELETE FROM record
                WHERE dataset_id = :dataset
                  AND entity = :entity
                  AND (
                    reference = :reference
                    OR (reference IS NULL AND data ->> 'reference' = :reference)
                  )
                RETURNING id
                """
            ),
            params,
        ).fetchall()
        for (record_id,) in deleted:
            print(f"removed {dataset} record {record_id} entity {entity} reference {reference}")

        # Rows of csv updates that would add or change the same record. They
        # hold the uploaded values, so a pending one could otherwise be applied.
        removed_update_rows = bind.execute(
            sa.text(
                """
                DELETE FROM update_record
                USING "update"
                WHERE update_record.update_id = "update".id
                  AND "update".dataset_id = :dataset
                  AND update_record.data ->> 'entity' = :entity_text
                  AND update_record.data ->> 'reference' = :reference
                RETURNING update_record.update_id
                """
            ),
            {**params, "entity_text": str(entity)},
        ).fetchall()
        for (update_id,) in removed_update_rows:
            print(f"removed {dataset} update row for entity {entity} from update {update_id}")
            update_ids.add(update_id)

    # Remove the updates themselves once none of their rows are left. An update
    # that still has other rows is kept and reported, to be looked at by hand.
    for update_id in sorted(update_ids, key=str):
        removed = bind.execute(
            sa.text(
                """
                DELETE FROM "update"
                WHERE id = :update_id
                  AND NOT EXISTS (
                    SELECT 1 FROM update_record WHERE update_record.update_id = :update_id
                  )
                """
            ),
            {"update_id": update_id},
        ).rowcount
        if removed:
            print(f"removed update {update_id}")
        else:
            print(f"WARNING: update {update_id} still has other rows and was kept")


def downgrade():
    # The records cannot be restored here, and must not be.
    pass
