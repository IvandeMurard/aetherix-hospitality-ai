-- IVA-52 Enhancement: Enable RLS and Tenant Isolation
-- Run this in Supabase SQL Editor

-- 1. Enable RLS on all operational tables
ALTER TABLE restaurant_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE pms_sync_logs ENABLE ROW LEVEL SECURITY;
ALTER TABLE recommendation_cache ENABLE ROW LEVEL SECURITY;

-- 2. Create Policies for Tenant Isolation
-- We assume auth.uid() links to the 'created_by' field

-- Restaurant Profiles: Only creator can see/edit their properties
CREATE POLICY "Tenant Isolation: Restaurant Profiles" ON restaurant_profiles
    FOR ALL USING (auth.uid() = created_by);

-- Sync Logs: Only accessible if the user owns the restaurant profile
-- Note: Simplified for MVP to check created_by on the log itself
CREATE POLICY "Tenant Isolation: Sync Logs" ON pms_sync_logs
    FOR ALL USING (auth.uid() = created_by);

-- Recommendation Cache: Only accessible by the creator
CREATE POLICY "Tenant Isolation: Recommendation Cache" ON recommendation_cache
    FOR ALL USING (auth.uid() = created_by);

-- 3. Grant permissions to authenticated users
GRANT ALL ON restaurant_profiles TO authenticated;
GRANT ALL ON pms_sync_logs TO authenticated;
GRANT ALL ON recommendation_cache TO authenticated;
