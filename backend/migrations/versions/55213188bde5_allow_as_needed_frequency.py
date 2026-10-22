"""allow as_needed frequency

Revision ID: 55213188bde5
Revises: c4cc8b220150
Create Date: 2026-10-21 23:17:24.384143

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '55213188bde5'
down_revision: Union[str, Sequence[str], None] = 'c4cc8b220150'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

FREQUENCY_WITH_AS_NEEDED = (
    "(frequency_kind = 'interval' AND frequency_days IS NOT NULL AND frequency_days > 0)"
    " OR (frequency_kind IN ('every_watering', 'as_needed') AND frequency_days IS NULL)"
)
FREQUENCY_WITHOUT_AS_NEEDED = (
    "(frequency_kind = 'interval' AND frequency_days IS NOT NULL AND frequency_days > 0)"
    " OR (frequency_kind = 'every_watering' AND frequency_days IS NULL)"
)


def replace_frequency_check(sqltext: str) -> None:
    # Written by hand: autogenerate does not detect CHECK changes. The batch
    # recreates the table, which would drop the expression index, so the index
    # is dropped first and created again after.
    op.drop_index('uq_direction_use', table_name='product_label_directions')
    with op.batch_alter_table('product_label_directions', schema=None) as batch_op:
        batch_op.drop_constraint('valid_frequency', type_='check')
        batch_op.create_check_constraint('valid_frequency', sqltext)
    op.create_index(
        'uq_direction_use',
        'product_label_directions',
        [sa.text('product_id'), sa.text('application'), sa.text('lower(use)')],
        unique=True,
    )


def upgrade() -> None:
    """Upgrade schema."""
    replace_frequency_check(FREQUENCY_WITH_AS_NEEDED)


def downgrade() -> None:
    """Downgrade schema."""
    # Fails if a direction is as_needed: the old CHECK has no place for it.
    replace_frequency_check(FREQUENCY_WITHOUT_AS_NEEDED)
