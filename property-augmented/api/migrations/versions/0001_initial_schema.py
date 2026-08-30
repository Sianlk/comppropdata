"""Initial Property Development, Augmented production schema.

Revision ID: 0001_initial_schema
Revises: 
Create Date: 2026-08-30
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = '0001_initial_schema'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('pda_users',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(320), nullable=False),
        sa.Column('password_hash', sa.String(255), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('is_admin', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('email', name='uq_pda_users_email'))
    op.create_index('ix_pda_users_email','pda_users',['email'],unique=True)

    op.create_table('pda_projects',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('pda_users.id'), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('address', sa.String(500), nullable=False),
        sa.Column('postcode', sa.String(20), nullable=False),
        sa.Column('strategy', sa.Text(), nullable=False),
        sa.Column('metadata_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_pda_projects_user_id','pda_projects',['user_id'])

    op.create_table('pda_registers',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('pda_users.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('pda_projects.id'), nullable=False),
        sa.Column('kind', sa.String(40), nullable=False),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('status', sa.String(100), nullable=False),
        sa.Column('data_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_pda_registers_user_id','pda_registers',['user_id'])
    op.create_index('ix_pda_registers_project_id','pda_registers',['project_id'])
    op.create_index('ix_pda_registers_kind','pda_registers',['kind'])

    op.create_table('pda_leads',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('email', sa.String(320), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('consent', sa.Boolean(), nullable=False),
        sa.Column('payload_json', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_pda_leads_email','pda_leads',['email'])

    op.create_table('pda_purchases',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('pda_users.id'), nullable=True),
        sa.Column('email', sa.String(320), nullable=False),
        sa.Column('product_slug', sa.String(120), nullable=False),
        sa.Column('provider_ref', sa.String(255), nullable=False),
        sa.Column('amount', sa.Float(), nullable=False),
        sa.Column('currency', sa.String(10), nullable=False),
        sa.Column('status', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('provider_ref', name='uq_pda_purchases_provider_ref'))
    op.create_index('ix_pda_purchases_user_id','pda_purchases',['user_id'])
    op.create_index('ix_pda_purchases_product_slug','pda_purchases',['product_slug'])

    op.create_table('pda_password_resets',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('pda_users.id'), nullable=False),
        sa.Column('token_hash', sa.String(64), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used', sa.Boolean(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_pda_password_resets_user_id','pda_password_resets',['user_id'])
    op.create_index('ix_pda_password_resets_token_hash','pda_password_resets',['token_hash'],unique=True)

    op.create_table('pda_ai_runs',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('pda_users.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('pda_projects.id'), nullable=True),
        sa.Column('agent_slug', sa.String(80), nullable=False),
        sa.Column('input_sha256', sa.String(64), nullable=False),
        sa.Column('output_sha256', sa.String(64), nullable=False),
        sa.Column('status', sa.String(40), nullable=False),
        sa.Column('model', sa.String(120), nullable=False),
        sa.Column('provider_ref', sa.String(255), nullable=False),
        sa.Column('source_json', sa.Text(), nullable=False),
        sa.Column('output_json', sa.Text(), nullable=False),
        sa.Column('security_flags_json', sa.Text(), nullable=False),
        sa.Column('review_status', sa.String(40), nullable=False),
        sa.Column('review_note', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_pda_ai_runs_user_id','pda_ai_runs',['user_id'])
    op.create_index('ix_pda_ai_runs_project_id','pda_ai_runs',['project_id'])
    op.create_index('ix_pda_ai_runs_agent_slug','pda_ai_runs',['agent_slug'])
    op.create_index('ix_pda_ai_runs_input_sha256','pda_ai_runs',['input_sha256'])

    op.create_table('pda_evidence_claims',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('run_id', sa.Integer(), sa.ForeignKey('pda_ai_runs.id'), nullable=False),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('pda_users.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('pda_projects.id'), nullable=True),
        sa.Column('claim_ref', sa.String(80), nullable=False),
        sa.Column('claim_text', sa.Text(), nullable=False),
        sa.Column('classification', sa.String(60), nullable=False),
        sa.Column('confidence', sa.String(30), nullable=False),
        sa.Column('materiality', sa.String(30), nullable=False),
        sa.Column('source_refs_json', sa.Text(), nullable=False),
        sa.Column('verification_action', sa.Text(), nullable=False),
        sa.Column('review_status', sa.String(40), nullable=False),
        sa.Column('review_note', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_pda_evidence_claims_run_id','pda_evidence_claims',['run_id'])
    op.create_index('ix_pda_evidence_claims_user_id','pda_evidence_claims',['user_id'])
    op.create_index('ix_pda_evidence_claims_project_id','pda_evidence_claims',['project_id'])
    op.create_index('ix_pda_evidence_claims_claim_ref','pda_evidence_claims',['claim_ref'])
    op.create_index('ix_pda_evidence_claims_classification','pda_evidence_claims',['classification'])
    op.create_index('ix_pda_evidence_claims_review_status','pda_evidence_claims',['review_status'])

    op.create_table('pda_documents',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('pda_users.id'), nullable=False),
        sa.Column('project_id', sa.Integer(), sa.ForeignKey('pda_projects.id'), nullable=True),
        sa.Column('original_name', sa.String(500), nullable=False),
        sa.Column('storage_key', sa.String(700), nullable=False),
        sa.Column('sha256', sa.String(64), nullable=False),
        sa.Column('size_bytes', sa.Integer(), nullable=False),
        sa.Column('suffix', sa.String(20), nullable=False),
        sa.Column('mime_type', sa.String(160), nullable=False),
        sa.Column('extraction_status', sa.String(60), nullable=False),
        sa.Column('extracted_text', sa.Text(), nullable=False),
        sa.Column('extraction_note', sa.Text(), nullable=False),
        sa.Column('security_flags_json', sa.Text(), nullable=False),
        sa.Column('retention_until', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint('storage_key', name='uq_pda_documents_storage_key'))
    op.create_index('ix_pda_documents_user_id','pda_documents',['user_id'])
    op.create_index('ix_pda_documents_project_id','pda_documents',['project_id'])
    op.create_index('ix_pda_documents_sha256','pda_documents',['sha256'])

    op.create_table('pda_audit_events',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('user_id', sa.Integer(), sa.ForeignKey('pda_users.id'), nullable=False),
        sa.Column('request_id', sa.String(100), nullable=False),
        sa.Column('method', sa.String(12), nullable=False),
        sa.Column('path', sa.String(500), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=False),
        sa.Column('client_hash', sa.String(64), nullable=False),
        sa.Column('user_agent', sa.String(300), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False))
    op.create_index('ix_pda_audit_events_user_id','pda_audit_events',['user_id'])
    op.create_index('ix_pda_audit_events_request_id','pda_audit_events',['request_id'])
    op.create_index('ix_pda_audit_events_path','pda_audit_events',['path'])
    op.create_index('ix_pda_audit_events_created_at','pda_audit_events',['created_at'])


def downgrade() -> None:
    op.drop_index('ix_pda_audit_events_created_at', table_name='pda_audit_events'); op.drop_index('ix_pda_audit_events_path', table_name='pda_audit_events'); op.drop_index('ix_pda_audit_events_request_id', table_name='pda_audit_events'); op.drop_index('ix_pda_audit_events_user_id', table_name='pda_audit_events'); op.drop_table('pda_audit_events')
    op.drop_index('ix_pda_documents_sha256', table_name='pda_documents'); op.drop_index('ix_pda_documents_project_id', table_name='pda_documents'); op.drop_index('ix_pda_documents_user_id', table_name='pda_documents'); op.drop_table('pda_documents')
    op.drop_index('ix_pda_evidence_claims_review_status', table_name='pda_evidence_claims'); op.drop_index('ix_pda_evidence_claims_classification', table_name='pda_evidence_claims'); op.drop_index('ix_pda_evidence_claims_claim_ref', table_name='pda_evidence_claims'); op.drop_index('ix_pda_evidence_claims_project_id', table_name='pda_evidence_claims'); op.drop_index('ix_pda_evidence_claims_user_id', table_name='pda_evidence_claims'); op.drop_index('ix_pda_evidence_claims_run_id', table_name='pda_evidence_claims'); op.drop_table('pda_evidence_claims')
    op.drop_index('ix_pda_ai_runs_input_sha256', table_name='pda_ai_runs'); op.drop_index('ix_pda_ai_runs_agent_slug', table_name='pda_ai_runs'); op.drop_index('ix_pda_ai_runs_project_id', table_name='pda_ai_runs'); op.drop_index('ix_pda_ai_runs_user_id', table_name='pda_ai_runs'); op.drop_table('pda_ai_runs')
    op.drop_index('ix_pda_password_resets_token_hash', table_name='pda_password_resets'); op.drop_index('ix_pda_password_resets_user_id', table_name='pda_password_resets'); op.drop_table('pda_password_resets')
    op.drop_index('ix_pda_purchases_product_slug', table_name='pda_purchases'); op.drop_index('ix_pda_purchases_user_id', table_name='pda_purchases'); op.drop_table('pda_purchases')
    op.drop_index('ix_pda_leads_email', table_name='pda_leads'); op.drop_table('pda_leads')
    op.drop_index('ix_pda_registers_kind', table_name='pda_registers'); op.drop_index('ix_pda_registers_project_id', table_name='pda_registers'); op.drop_index('ix_pda_registers_user_id', table_name='pda_registers'); op.drop_table('pda_registers')
    op.drop_index('ix_pda_projects_user_id', table_name='pda_projects'); op.drop_table('pda_projects')
    op.drop_index('ix_pda_users_email', table_name='pda_users'); op.drop_table('pda_users')
