-- Story 4.1 (HOS-24): Add notification preference columns to restaurant_profiles
-- These columns store each manager's preferred delivery channel, contact details,
-- and optional GPS coordinates for location-aware routing.
--
-- Idempotent: ADD COLUMN IF NOT EXISTS is safe to re-run.

ALTER TABLE restaurant_profiles ADD COLUMN IF NOT EXISTS preferred_channel VARCHAR(10) DEFAULT 'whatsapp';
ALTER TABLE restaurant_profiles ADD COLUMN IF NOT EXISTS phone_number VARCHAR(20);
ALTER TABLE restaurant_profiles ADD COLUMN IF NOT EXISTS notification_email VARCHAR(255);
ALTER TABLE restaurant_profiles ADD COLUMN IF NOT EXISTS gps_lat NUMERIC(9,6);
ALTER TABLE restaurant_profiles ADD COLUMN IF NOT EXISTS gps_lng NUMERIC(9,6);

-- Add check constraint for valid channel values (only if it doesn't already exist)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint
        WHERE conname = 'valid_notification_channel'
    ) THEN
        ALTER TABLE restaurant_profiles
            ADD CONSTRAINT valid_notification_channel
            CHECK (preferred_channel IN ('sms', 'whatsapp', 'email'));
    END IF;
END
$$;
