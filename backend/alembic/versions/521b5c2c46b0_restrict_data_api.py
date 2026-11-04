"""Restrict access to application tables through the Supabase Data API."""

from alembic import op

revision = "521b5c2c46b0"
down_revision = "14329d05ebf8"
branch_labels = None
depends_on = None
TABLES = (
    "users",
    "workspaces",
    "workspace_members",
    "social_accounts",
    "media_assets",
    "posts",
    "post_targets",
    "publish_attempts",
    "oauth_states",
    "audit_logs",
)


def upgrade():
    if op.get_bind().dialect.name != "postgresql":
        return
    for table in TABLES:
        op.execute(f'ALTER TABLE "{table}" ENABLE ROW LEVEL SECURITY')
        op.execute(f'REVOKE ALL ON "{table}" FROM PUBLIC')
        for role in ("anon", "authenticated"):
            op.execute(
                f"DO $$ BEGIN IF EXISTS (SELECT FROM pg_roles WHERE rolname = '{role}') "
                f'THEN REVOKE ALL ON "{table}" FROM {role}; END IF; END $$'
            )


def downgrade():
    if op.get_bind().dialect.name == "postgresql":
        for table in TABLES:
            op.execute(f'ALTER TABLE "{table}" DISABLE ROW LEVEL SECURITY')
