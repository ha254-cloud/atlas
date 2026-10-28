"""Add Atlas Copilot conversations and confirmations.

Revision ID: c6f2a8d1e4b9
Revises: e2c7a9f4b1d6
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c6f2a8d1e4b9"
down_revision: Union[str, None] = "e2c7a9f4b1d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "copilot_conversations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("context", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_copilot_conversations_organization_id", "copilot_conversations", ["organization_id"])
    op.create_index("ix_copilot_conversations_user_id", "copilot_conversations", ["user_id"])

    op.create_table(
        "copilot_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("copilot_conversations.id"), nullable=False),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("tool_name", sa.String(100), nullable=True),
        sa.Column("tool_input", sa.JSON(), nullable=True),
        sa.Column("tool_output", sa.JSON(), nullable=True),
        sa.Column("evidence", sa.JSON(), nullable=True),
        sa.Column("navigation_path", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_copilot_messages_organization_id", "copilot_messages", ["organization_id"])
    op.create_index("ix_copilot_messages_conversation_id", "copilot_messages", ["conversation_id"])
    op.create_index("ix_copilot_messages_created_at", "copilot_messages", ["created_at"])

    op.create_table(
        "copilot_confirmations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("organization_id", sa.Integer(), sa.ForeignKey("organizations.id"), nullable=False),
        sa.Column("conversation_id", sa.Integer(), sa.ForeignKey("copilot_conversations.id"), nullable=False),
        sa.Column("requested_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("arguments", sa.JSON(), nullable=False),
        sa.Column("summary", sa.String(1000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_copilot_confirmations_organization_id", "copilot_confirmations", ["organization_id"])
    op.create_index("ix_copilot_confirmations_conversation_id", "copilot_confirmations", ["conversation_id"])
    op.create_index("ix_copilot_confirmations_requested_by", "copilot_confirmations", ["requested_by"])
    op.create_index("ix_copilot_confirmations_token_hash", "copilot_confirmations", ["token_hash"])
    op.create_index("ix_copilot_confirmations_status", "copilot_confirmations", ["status"])


def downgrade() -> None:
    op.drop_table("copilot_confirmations")
    op.drop_table("copilot_messages")
    op.drop_table("copilot_conversations")