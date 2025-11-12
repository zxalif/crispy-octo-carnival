"""Initial schema

Revision ID: 001
Revises: 
Create Date: 2025-01-27 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Create keyword_searches table
    op.create_table(
        'keyword_searches',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=200), nullable=False),
        sa.Column('keywords', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('patterns', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('platforms', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('reddit_config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('linkedin_config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('twitter_config', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('scraping_mode', sa.String(length=20), nullable=True),
        sa.Column('scraping_interval', sa.String(length=10), nullable=True),
        sa.Column('enabled', sa.Boolean(), nullable=True),
        sa.Column('last_scrape_at', sa.DateTime(), nullable=True),
        sa.Column('next_scrape_at', sa.DateTime(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_keyword_search_enabled', 'keyword_searches', ['enabled'], unique=False)
    op.create_index('idx_keyword_search_next_scrape', 'keyword_searches', ['next_scrape_at'], unique=False)
    op.create_index('idx_keyword_search_mode', 'keyword_searches', ['scraping_mode'], unique=False)
    
    # Create leads table
    op.create_table(
        'leads',
        sa.Column('id', sa.String(length=50), nullable=False),
        sa.Column('keyword_search_id', sa.String(length=50), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=False),
        sa.Column('source_type', sa.String(length=20), nullable=False),
        sa.Column('source_id', sa.String(length=100), nullable=False),
        sa.Column('parent_post_id', sa.String(length=100), nullable=True),
        sa.Column('title', sa.String(length=500), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('author', sa.String(length=100), nullable=False),
        sa.Column('url', sa.String(length=500), nullable=False),
        sa.Column('matched_keywords', postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column('detected_pattern', sa.String(length=200), nullable=True),
        sa.Column('domain', sa.String(length=200), nullable=True),
        sa.Column('company', sa.String(length=200), nullable=True),
        sa.Column('email', sa.String(length=200), nullable=True),
        sa.Column('author_profile_url', sa.String(length=500), nullable=True),
        sa.Column('social_profiles', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('opportunity_type', sa.String(length=50), nullable=True),
        sa.Column('opportunity_subtype', sa.String(length=100), nullable=True),
        sa.Column('relevance_score', sa.Float(), nullable=True),
        sa.Column('urgency_score', sa.Float(), nullable=True),
        sa.Column('total_score', sa.Float(), nullable=True),
        sa.Column('extracted_info', postgresql.JSON(astext_type=sa.Text()), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['keyword_search_id'], ['keyword_searches.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_lead_search_id', 'leads', ['keyword_search_id'], unique=False)
    op.create_index('idx_lead_source', 'leads', ['source', 'source_type'], unique=False)
    op.create_index('idx_lead_source_id', 'leads', ['source_id', 'keyword_search_id'], unique=False)
    op.create_index('idx_lead_status', 'leads', ['status'], unique=False)
    op.create_index('idx_lead_score', 'leads', ['total_score'], unique=False)
    op.create_index('idx_lead_opportunity_type', 'leads', ['opportunity_type'], unique=False)
    op.create_index('idx_lead_created', 'leads', ['created_at'], unique=False)


def downgrade() -> None:
    op.drop_index('idx_lead_created', table_name='leads')
    op.drop_index('idx_lead_opportunity_type', table_name='leads')
    op.drop_index('idx_lead_score', table_name='leads')
    op.drop_index('idx_lead_status', table_name='leads')
    op.drop_index('idx_lead_source_id', table_name='leads')
    op.drop_index('idx_lead_source', table_name='leads')
    op.drop_index('idx_lead_search_id', table_name='leads')
    op.drop_table('leads')
    op.drop_index('idx_keyword_search_mode', table_name='keyword_searches')
    op.drop_index('idx_keyword_search_next_scrape', table_name='keyword_searches')
    op.drop_index('idx_keyword_search_enabled', table_name='keyword_searches')
    op.drop_table('keyword_searches')

