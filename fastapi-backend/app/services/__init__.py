"""Services package — all business logic lives here.

Architecture rule: "Fat Backend / Thin Frontend"
ALL business logic, AI prompting, and access control MUST be in this layer.
Next.js components are strictly presentational.

Future services:
  - pms_sync.py       (Story 2.1-2.3: Apaleo/Mews ingestion)
  - prediction_math.py (Story 3.x: vector math / anomaly detection)
  - aetherix_engine.py (Story 3.3c, 5.x: Claude orchestration)
"""
