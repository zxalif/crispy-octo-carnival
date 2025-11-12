"""Add job tracking fields

Revision ID: 002
Revises: 001
Create Date: 2025-01-27 15:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '002'
down_revision: Union[str, None] = '001'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add job tracking columns to keyword_searches table
    op.add_column('keyword_searches', sa.Column('scraping_status', sa.String(length=20), nullable=True))
    op.add_column('keyword_searches', sa.Column('scraping_started_at', sa.DateTime(), nullable=True))
    op.add_column('keyword_searches', sa.Column('scraping_completed_at', sa.DateTime(), nullable=True))
    op.add_column('keyword_searches', sa.Column('scraping_error', sa.Text(), nullable=True))
    
    # Add index for status queries
    op.create_index('idx_keyword_search_status', 'keyword_searches', ['scraping_status'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_keyword_search_status', table_name='keyword_searches')
    op.drop_column('keyword_searches', 'scraping_error')
    op.drop_column('keyword_searches', 'scraping_completed_at')
    op.drop_column('keyword_searches', 'scraping_started_at')
    op.drop_column('keyword_searches', 'scraping_status')

