"""add pushed to github to changelog

Revision ID: 0a3cf05180ed
Revises: 9d4e8b73e32d
Create Date: 2023-11-22 12:54:34.886034

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = "0a3cf05180ed"
down_revision = "9d4e8b73e32d"
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.add_column(sa.Column("pushed_to_github", sa.Boolean(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table("change_log", schema=None) as batch_op:
        batch_op.drop_column("pushed_to_github")

    # ### end Alembic commands ###
