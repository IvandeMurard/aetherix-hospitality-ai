-- HOS-345 (Décisions #43, #44) — staffing rules per context class.
--
-- The hotel's own high season (high_season_start_month / high_season_end_month,
-- app/services/hotel_parameters.py) is a month number, a unit the closed
-- vocabulary did not have. Per-class staffing rules (covers_per_server.event_night
-- ...) reuse the existing units and need no schema change: parameter names are
-- validated by the bounded catalog in code.
-- Same pattern as 20261017100000 (set_via).

ALTER TABLE public.hotel_decision_parameters
    DROP CONSTRAINT IF EXISTS hotel_decision_parameters_unit_check;
ALTER TABLE public.hotel_decision_parameters
    ADD CONSTRAINT hotel_decision_parameters_unit_check
    CHECK (unit IN ('money', 'covers', 'staff', 'hours', 'month'));
