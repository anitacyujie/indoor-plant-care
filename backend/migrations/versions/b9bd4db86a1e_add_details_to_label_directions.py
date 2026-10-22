"""add details to label directions

Revision ID: b9bd4db86a1e
Revises: 55213188bde5
Create Date: 2026-10-21 23:29:33.012316

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b9bd4db86a1e'
down_revision: Union[str, Sequence[str], None] = '55213188bde5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def recreate_use_index() -> None:
    op.create_index(
        'uq_direction_use',
        'product_label_directions',
        [sa.text('product_id'), sa.text('application'), sa.text('lower(use)')],
        unique=True,
    )


def upgrade() -> None:
    """Upgrade schema."""
    # Existing directions get empty details. The server default fills them
    # in and is then removed, matching the model (a Python-side default).
    op.add_column(
        'product_label_directions',
        sa.Column('details', sa.String(), nullable=False, server_default=''),
    )
    # The batch recreates the table, which would drop the expression index,
    # so the index is dropped first and created again after.
    op.drop_index('uq_direction_use', table_name='product_label_directions')
    with op.batch_alter_table('product_label_directions', schema=None) as batch_op:
        batch_op.alter_column('details', server_default=None)
    recreate_use_index()


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('uq_direction_use', table_name='product_label_directions')
    with op.batch_alter_table('product_label_directions', schema=None) as batch_op:
        batch_op.drop_column('details')
    recreate_use_index()
