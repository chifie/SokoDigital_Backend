"""create_seller_follow_table

Revision ID: b8a4f2c7e5d1
Revises: 92c79a66f099
Create Date: 2026-07-29 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8a4f2c7e5d1'
down_revision: Union[str, None] = '92c79a66f099'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table('seller_follows',
    sa.Column('id', sa.UUID(), nullable=False),
    sa.Column('seller_id', sa.UUID(), nullable=False),
    sa.Column('user_id', sa.UUID(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.ForeignKeyConstraint(['seller_id'], ['sellers.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('seller_id', 'user_id', name='uq_user_seller_follow')
    )
    op.create_index(op.f('ix_seller_follows_seller_id'), 'seller_follows', ['seller_id'], unique=False)
    op.create_index(op.f('ix_seller_follows_user_id'), 'seller_follows', ['user_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_seller_follows_user_id'), table_name='seller_follows')
    op.drop_index(op.f('ix_seller_follows_seller_id'), table_name='seller_follows')
    op.drop_table('seller_follows')
