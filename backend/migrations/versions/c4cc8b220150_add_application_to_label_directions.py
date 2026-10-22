"""add application to label directions

Revision ID: c4cc8b220150
Revises: 8ecd6ca28407
Create Date: 2026-10-21 22:38:09.033673

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c4cc8b220150'
down_revision: Union[str, Sequence[str], None] = '8ecd6ca28407'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Written by hand: autogenerate detects neither CHECK constraints nor
    # expression indexes on SQLite.
    # The index changes to include application. Dropped before the batch
    # below, which recreates the table and would not carry it over.
    op.drop_index('uq_direction_use', table_name='product_label_directions')

    # Existing directions were all for watering plants in soil. The default
    # fills them in, then is removed, so new rows must state an application.
    op.add_column(
        'product_label_directions',
        sa.Column('application', sa.String(), nullable=False, server_default='soil'),
    )
    with op.batch_alter_table('product_label_directions', schema=None) as batch_op:
        batch_op.alter_column('application', server_default=None)
        batch_op.create_check_constraint(
            'valid_application', "application IN ('soil', 'hydroponic', 'foliar')"
        )
        batch_op.create_check_constraint(
            'foliar_not_every_watering',
            "application <> 'foliar' OR frequency_kind <> 'every_watering'",
        )

    op.create_index(
        'uq_direction_use',
        'product_label_directions',
        [sa.text('product_id'), sa.text('application'), sa.text('lower(use)')],
        unique=True,
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Fails if a product has the same use for two applications, since the old
    # index allows each use once per product.
    op.drop_index('uq_direction_use', table_name='product_label_directions')
    with op.batch_alter_table('product_label_directions', schema=None) as batch_op:
        batch_op.drop_constraint('foliar_not_every_watering', type_='check')
        batch_op.drop_constraint('valid_application', type_='check')
        batch_op.drop_column('application')
    op.create_index(
        'uq_direction_use',
        'product_label_directions',
        [sa.text('product_id'), sa.text('lower(use)')],
        unique=True,
    )
