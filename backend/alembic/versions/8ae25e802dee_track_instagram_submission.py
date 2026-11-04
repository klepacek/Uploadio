"""Track ambiguous Instagram publishing submissions."""

import sqlalchemy as sa

from alembic import op

revision = "8ae25e802dee"
down_revision = "521b5c2c46b0"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("post_targets", sa.Column("publish_submitted_at", sa.DateTime(timezone=True)))


def downgrade():
    op.drop_column("post_targets", "publish_submitted_at")
