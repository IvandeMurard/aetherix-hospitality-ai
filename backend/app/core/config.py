"""Application-level configuration constants for Aetherix backend.

Values here are the system defaults; individual properties can override
avg_spend_per_cover and staff_hourly_rate via the properties table
(added in migration 20260323100000_add_roi_config_to_properties.sql).

[Source: story 3.3b AC 7]
"""
from __future__ import annotations

# ---------------------------------------------------------------------------
# ROI Calculator defaults  (Story 3.3b)
# ---------------------------------------------------------------------------

#: Default average revenue per cover (£) used when the property has no
#: per-property override set.
DEFAULT_AVG_SPEND_PER_COVER: float = 40.0

#: Default hourly cost per additional front-of-house staff member (£).
DEFAULT_STAFF_HOURLY_RATE: float = 14.0

#: Default captation rate — fraction of the excess demand that the property
#: is expected to capture when fully staffed.
DEFAULT_CAPTATION_RATE: float = 0.7
