-- Agent Constitution columns (Prompt B — HOS sprint 2026-04-16)
-- Adds manager name and tone profile to restaurant_profiles for WhatsApp agent personalisation.
ALTER TABLE restaurant_profiles
    ADD COLUMN IF NOT EXISTS manager_name VARCHAR,
    ADD COLUMN IF NOT EXISTS agent_tone_profile VARCHAR NOT NULL DEFAULT 'luxury';
