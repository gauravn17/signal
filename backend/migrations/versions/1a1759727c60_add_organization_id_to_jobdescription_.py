"""add organization_id to jobdescription candidate matchresult

Revision ID: 1a1759727c60
Revises: eab5789c50cd
Create Date: 2026-08-28 18:11:29.429441

"""
import uuid
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = '1a1759727c60'
down_revision: Union[str, Sequence[str], None] = 'eab5789c50cd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Fixed id for the bootstrap org that absorbs any pre-multi-tenancy data
# (e.g. a populated local dev DB predating this migration).
DEFAULT_ORG_ID = uuid.UUID("00000000-0000-0000-0000-000000000001")


def upgrade() -> None:
    # 1. Add nullable first — existing rows have no organization_id yet, so
    # a NOT NULL column can't be added directly against populated tables.
    op.add_column('jobdescription', sa.Column('organization_id', sa.Uuid(), nullable=True))
    op.add_column('candidate', sa.Column('organization_id', sa.Uuid(), nullable=True))
    op.add_column('matchresult', sa.Column('organization_id', sa.Uuid(), nullable=True))

    # 2. Backfill: everything that predates multi-tenancy belongs to a
    # bootstrap "Default Organization".
    conn = op.get_bind()
    conn.execute(
        sa.text(
            "INSERT INTO organization (id, name, created_at) "
            "VALUES (:id, 'Default Organization', now()) "
            "ON CONFLICT (id) DO NOTHING"
        ),
        {"id": str(DEFAULT_ORG_ID)},
    )
    for table in ("jobdescription", "candidate", "matchresult"):
        conn.execute(
            sa.text(f"UPDATE {table} SET organization_id = :org_id WHERE organization_id IS NULL"),
            {"org_id": str(DEFAULT_ORG_ID)},
        )

    # 3. Now safe to enforce NOT NULL and add indexes/FKs.
    op.alter_column('jobdescription', 'organization_id', nullable=False)
    op.alter_column('candidate', 'organization_id', nullable=False)
    op.alter_column('matchresult', 'organization_id', nullable=False)

    op.create_index(op.f('ix_jobdescription_organization_id'), 'jobdescription', ['organization_id'], unique=False)
    op.create_foreign_key(None, 'jobdescription', 'organization', ['organization_id'], ['id'])
    op.create_index(op.f('ix_candidate_organization_id'), 'candidate', ['organization_id'], unique=False)
    op.create_foreign_key(None, 'candidate', 'organization', ['organization_id'], ['id'])
    op.create_index(op.f('ix_matchresult_organization_id'), 'matchresult', ['organization_id'], unique=False)
    op.create_foreign_key(None, 'matchresult', 'organization', ['organization_id'], ['id'])


def downgrade() -> None:
    op.drop_constraint(None, 'matchresult', type_='foreignkey')
    op.drop_index(op.f('ix_matchresult_organization_id'), table_name='matchresult')
    op.drop_column('matchresult', 'organization_id')
    op.drop_constraint(None, 'candidate', type_='foreignkey')
    op.drop_index(op.f('ix_candidate_organization_id'), table_name='candidate')
    op.drop_column('candidate', 'organization_id')
    op.drop_constraint(None, 'jobdescription', type_='foreignkey')
    op.drop_index(op.f('ix_jobdescription_organization_id'), table_name='jobdescription')
    op.drop_column('jobdescription', 'organization_id')
