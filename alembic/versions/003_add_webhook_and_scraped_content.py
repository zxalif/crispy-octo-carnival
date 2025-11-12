"""Add webhook URL and scraped content tracking

Revision ID: 003
Revises: 002
Create Date: 2025-01-27 16:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '003'
down_revision: Union[str, None] = '002'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add webhook_url to keyword_searches
    op.add_column('keyword_searches', sa.Column('webhook_url', sa.String(length=500), nullable=True))
    
    # Create scraped_content table
    op.create_table(
        'scraped_content',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('keyword_search_id', sa.String(length=50), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('source_id', sa.String(length=100), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('processed_at', sa.DateTime(), nullable=False),
        sa.Column('created_lead', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['keyword_search_id'], ['keyword_searches.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for scraped_content
    op.create_index('idx_scraped_content_search_source', 'scraped_content', ['keyword_search_id', 'source', 'source_id'], unique=True)
    op.create_index('idx_scraped_content_url', 'scraped_content', ['url'], unique=False)
    op.create_index('idx_scraped_content_processed', 'scraped_content', ['processed_at'], unique=False)
    
    # Add URL index to leads table for better duplicate checking
    op.create_index('idx_lead_url', 'leads', ['url'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_lead_url', table_name='leads')
    op.drop_index('idx_scraped_content_processed', table_name='scraped_content')
    op.drop_index('idx_scraped_content_url', table_name='scraped_content')
    op.drop_index('idx_scraped_content_search_source', table_name='scraped_content')
    op.drop_table('scraped_content')
    op.drop_column('keyword_searches', 'webhook_url')

