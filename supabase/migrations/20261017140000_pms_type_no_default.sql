-- HOS-347 (Décisions #28, #43) — no PMS vendor is ever assumed.
--
-- restaurant_profiles.pms_type defaulted to 'apaleo' (migration 20260327000000),
-- so a hotel created without saying which PMS it uses was treated as an Apaleo
-- hotel. A hotel's PMS is a fact the hotel provides: without it (and without a
-- PMS property id) the hotel has no PMS connected, and app/services/
-- pms_identity.py says so (pms_not_linked) instead of routing it to a vendor.
--
-- Existing rows keep their value (all sandbox / demo hotels at this date).
-- ORM mirror: app/db/models.py RestaurantProfile.pms_type (no default).

ALTER TABLE public.restaurant_profiles ALTER COLUMN pms_type DROP DEFAULT;
