"""add_guild_season_reward_configs

Revision ID: f7g8h9i0j1k2
Revises: e6f7g8h9i0j1
Create Date: 2026-03-11 20:10:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "f7g8h9i0j1k2"
down_revision: Union[str, None] = "e6f7g8h9i0j1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS guild_season_reward_configs (
            id VARCHAR(50) PRIMARY KEY,
            season_code VARCHAR(40) NOT NULL,
            family VARCHAR(30) NOT NULL,
            label VARCHAR(80) NOT NULL,
            accent VARCHAR(20) NOT NULL,
            treasury_bonus NUMERIC(12, 2) NOT NULL DEFAULT 0,
            guild_tokens_bonus INTEGER NOT NULL DEFAULT 0,
            badge_name VARCHAR(80) NOT NULL,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_guild_season_reward_config_pair UNIQUE (season_code, family)
        );
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_guild_season_reward_configs_active ON guild_season_reward_configs (season_code, is_active);"
    )
    op.execute(
        """
        INSERT INTO guild_season_reward_configs (
            id, season_code, family, label, accent, treasury_bonus, guild_tokens_bonus, badge_name, is_active
        ) VALUES
            ('gsrc_sigil_forge', 'forge-awakening', 'sigil', 'Forge payroll cache', 'amber', 18.00, 1, 'Sigil Wardens', TRUE),
            ('gsrc_relic_forge', 'forge-awakening', 'relic', 'Archive treasury relay', 'slate', 22.00, 1, 'Archive Keepers', TRUE),
            ('gsrc_banner_forge', 'forge-awakening', 'banner', 'Storm campaign reserve', 'cyan', 40.00, 3, 'Storm Standard', TRUE),
            ('gsrc_artifact_forge', 'forge-awakening', 'artifact', 'Vault pressure release', 'emerald', 55.00, 4, 'Vault Ascendants', TRUE),
            ('gsrc_charter_forge', 'forge-awakening', 'charter', 'Astral expedition grant', 'violet', 65.00, 5, 'Astral Cartographers', TRUE),
            ('gsrc_crown_forge', 'forge-awakening', 'crown', 'Raid command stipend', 'amber', 75.00, 5, 'Raid Regents', TRUE),
            ('gsrc_core_forge', 'forge-awakening', 'core', 'Sun forge ignition', 'gold', 120.00, 8, 'Sunforged Circle', TRUE)
        ON CONFLICT (season_code, family) DO NOTHING;
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS idx_guild_season_reward_configs_active;")
    op.execute("DROP TABLE IF EXISTS guild_season_reward_configs;")