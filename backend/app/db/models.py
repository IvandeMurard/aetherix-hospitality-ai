import uuid
from datetime import datetime

from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy import (
    JSON as JSONB,  # JSON is dialect-agnostic (works with SQLite in tests)
)
from sqlalchemy.dialects.postgresql import ARRAY as _PgArray
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.types import TypeDecorator


class StringArray(TypeDecorator):
    """ARRAY(String) on PostgreSQL, JSON list on every other dialect.

    HOS-150 AC3 — `mcp_api_tokens.scopes` and `agent_action_log.scopes` are
    `TEXT[]` in Supabase; the previous `Column(JSON, ...)` mapping caused
    asyncpg to return None on read, breaking `require_scope` end-to-end.
    Tests use SQLite (no native ARRAY), so we transparently fall back to JSON
    there.
    """

    impl = JSON
    cache_ok = True

    def load_dialect_impl(self, dialect):  # type: ignore[override]
        if dialect.name == "postgresql":
            return dialect.type_descriptor(_PgArray(String))
        return dialect.type_descriptor(JSON())

# pgvector: use real Vector type on PostgreSQL, fall back to JSON for SQLite tests
# Dimension: 1024 (Mistral mistral-embed, per migration 20260323220000)
try:
    from pgvector.sqlalchemy import Vector as _PgVector
    _VECTOR_1024 = _PgVector(1024)
    _VECTOR_1536 = _PgVector(1536)  # kept for legacy fb_patterns column
except ImportError:  # pragma: no cover
    from sqlalchemy import JSON as _PgVector  # type: ignore[assignment]
    _VECTOR_1024 = JSON
    _VECTOR_1536 = JSON

Base = declarative_base()

class User(SQLAlchemyBaseUserTableUUID, Base):
    """
    User model for Aetherix.
    """
    __tablename__ = "users"
    
    full_name = Column(String)
    department_role = Column(String) # f&b, front_office, operations
    
    # Relationship to owned properties
    properties = relationship("RestaurantProfile", back_populates="owner")

class RestaurantProfile(Base):
    """
    Hospitality profile for a property (outlet).
    Aligned with Supabase migration 20250203000000.
    """
    __tablename__ = "restaurant_profiles"

    # HOS-165 — `id` is UUID in Supabase (migration 20250203000000); the previous
    # String mapping was an ORM drift documented in HOS-163.
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, unique=True, index=True, nullable=False)
    # `property_id` mirrors `id` and is the cross-table FK target referenced
    # by DemandAnomaly / StaffingRecommendation / ConversationalQuery.
    property_id = Column(UUID(as_uuid=True), unique=True, default=uuid.uuid4)
    
    # Administrative Link
    owner_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    owner = relationship("User", back_populates="properties")
    property_name = Column(String, nullable=False)
    outlet_name = Column(String, nullable=False)
    outlet_type = Column(String, default="restaurant")
    
    # Capacity
    total_seats = Column(Integer, nullable=False)
    turns_breakfast = Column(Float, default=1.0)
    turns_lunch = Column(Float, default=1.5)
    turns_dinner = Column(Float, default=2.0)
    
    # Staffing Ratios (covers per staff member)
    covers_per_server = Column(Integer, default=16)
    covers_per_host = Column(Integer, default=60)
    covers_per_runner = Column(Integer, default=40)
    covers_per_kitchen = Column(Integer, default=30)
    
    # PMS Configuration (Aetherix extensions)
    pms_type = Column(String, default="apaleo")
    pms_property_id = Column(String)
    
    # Location for semantic engine
    latitude = Column(Float)
    longitude = Column(Float)
    
    # Notification preferences (Story 4.1 — HOS-24)
    preferred_channel = Column(String, default="whatsapp")   # sms / whatsapp / email
    phone_number = Column(String)
    notification_email = Column(String)
    gps_lat = Column(Float)
    gps_lng = Column(Float)

    # ROI configuration (Story 3.3b) — overrides system defaults when set
    avg_spend_per_cover = Column(Numeric(8, 2), nullable=True)   # £ per cover
    staff_hourly_rate = Column(Numeric(8, 2), nullable=True)     # £ per staff/hour

    # Agent constitution (Prompt B — WhatsApp conversational agent)
    manager_name = Column(String, nullable=True)
    # agent_tone_profile: "luxury" | "professional" | "casual"
    # For existing databases run:
    #   ALTER TABLE restaurant_profiles
    #     ADD COLUMN manager_name VARCHAR,
    #     ADD COLUMN agent_tone_profile VARCHAR NOT NULL DEFAULT 'luxury';
    agent_tone_profile = Column(String, default="luxury", nullable=False)

    # HOS-150 AC5 — soft-disable flag used by anomaly_scan.run_full_scan
    is_active = Column(Boolean, nullable=False, default=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PMSSyncLog(Base):
    """
    History of occupancy and revenue data synced from the PMS.
    Story 2.2: Data persistence for historical baseline.
    """
    __tablename__ = "pms_sync_logs"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(String, ForeignKey("restaurant_profiles.tenant_id"), index=True, nullable=False)
    sync_date = Column(Date, index=True, nullable=False)
    
    occupancy = Column(Integer)
    fb_revenue = Column(Float)
    
    # Metadata for back-channel safety/auditing
    raw_payload_summary = Column(JSON)
    status = Column(String) # success, failed
    error_message = Column(String)
    
    created_at = Column(DateTime, default=datetime.utcnow)

class CaptationBaseline(Base):
    """
    Stores calculated captation rate baselines per tenant/property.
    Story 2.4: Calculate Baseline Captation Rates (FR3).

    Captation rate = F&B revenue per occupied room.
    Adjustment factors normalise the baseline by day-of-week and month
    so that Story 3.3a can detect anomalies relative to the expected pattern.
    """
    __tablename__ = "captation_baselines"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(String, ForeignKey("restaurant_profiles.tenant_id"), index=True, nullable=False)

    # Date range of PMSSyncLog data used for this computation
    period_start = Column(Date, nullable=False)
    period_end = Column(Date, nullable=False)

    # Core metric: average F&B revenue per occupied room across all data
    avg_fb_revenue_per_room = Column(Float, nullable=False)

    # Day-of-week factors (JSON): {"0": 1.05, "1": 0.98, ...} (0=Monday … 6=Sunday)
    # Each value is the ratio of that weekday's avg captation rate to the overall avg.
    dow_factors = Column(JSON, nullable=False)

    # Monthly factors (JSON): {"1": 0.90, "2": 0.85, ..., "12": 1.10}
    # Each value is the ratio of that month's avg captation rate to the overall avg.
    monthly_factors = Column(JSON, nullable=False)

    # Number of non-zero occupancy records used in the computation
    data_points_count = Column(Integer, nullable=False)

    computed_at = Column(DateTime, default=datetime.utcnow, nullable=False)


class WeatherForecast(Base):
    """
    Normalized weather forecast records ingested from Open-Meteo.
    Story 3.1: one row per (tenant_id, property_id, forecast_timestamp).
    Unique constraint enforces idempotent upserts (SC #7).
    """
    __tablename__ = "weather_forecasts"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(String, ForeignKey("restaurant_profiles.tenant_id"), index=True, nullable=False)
    property_id = Column(String, nullable=False)

    # Normalized weather fields (SC #4)
    condition_code = Column(Integer)          # WMO weather interpretation code
    temperature_c = Column(Float)
    precipitation_prob = Column(Integer)      # 0-100 %
    wind_speed_kmh = Column(Float)
    forecast_timestamp = Column(DateTime(timezone=True), nullable=False, index=True)
    source = Column(String, nullable=False, default="open-meteo")

    fetched_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        # Idempotency: upsert on this composite key (SC #7)
        __import__("sqlalchemy").UniqueConstraint(
            "tenant_id", "property_id", "forecast_timestamp",
            name="uq_weather_forecast",
        ),
    )


class DemandAnomaly(Base):
    """
    Detected demand anomaly window for a property.
    Story 3.3a: Detect Demand Anomalies Against Baseline.

    Status lifecycle:
      'detected' -> 'roi_positive' (3.3b) -> 'ready_to_push' (3.3c) -> 'dispatched' (Epic 4)
    """
    __tablename__ = "demand_anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # HOS-165 — tenant_id is a human-readable slug (TEXT in Postgres).
    tenant_id = Column(String, nullable=False, index=True)
    property_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)
    expected_demand = Column(Numeric(10, 2), nullable=False)
    baseline_demand = Column(Numeric(10, 2), nullable=False)
    deviation_pct = Column(Numeric(6, 2), nullable=False)
    direction = Column(String, nullable=False)           # 'surge' | 'lull'
    triggering_factors = Column(JSONB, nullable=False, default=list)
    status = Column(String, nullable=False, default="detected")
    detected_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    # Populated by downstream stories:
    roi_revenue_opp = Column(Numeric(10, 2))
    roi_labor_cost = Column(Numeric(10, 2))
    roi_net = Column(Numeric(10, 2))
    recommendation_text = Column(Text)


class LocalEvent(Base):
    """
    Localized event data ingested from PredictHQ.
    Story 3.2: one row per (tenant_id, event_id).
    Unique constraint on (tenant_id, event_id) enforces idempotent upserts.
    """
    __tablename__ = "local_events"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(String, ForeignKey("restaurant_profiles.tenant_id"), index=True, nullable=False)

    # PredictHQ event identifier (stable across re-syncs)
    event_id = Column(String, nullable=False)

    # Event metadata
    title = Column(String, nullable=False)
    category = Column(String, nullable=False)   # e.g. "conferences", "concerts", "sports"
    rank = Column(Integer)                       # PredictHQ rank (0-100)
    local_rank = Column(Integer)                 # Local rank within radius
    phq_attendance = Column(Integer)             # Predicted attendance

    # Temporal data
    start_dt = Column(DateTime(timezone=True), nullable=False, index=True)
    end_dt = Column(DateTime(timezone=True))

    # Location (centroid of the event)
    latitude = Column(Float)
    longitude = Column(Float)

    # Raw payload for auditing / future feature extraction
    raw_labels = Column(JSON)

    fetched_at = Column(DateTime(timezone=True), default=datetime.utcnow)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow)

    __table_args__ = (
        # Idempotency: upsert on (tenant_id, event_id)
        __import__("sqlalchemy").UniqueConstraint(
            "tenant_id", "event_id",
            name="uq_local_event",
        ),
    )


class StaffingRecommendation(Base):
    """
    Ready-to-dispatch staffing recommendations produced by the
    RecommendationFormatterService from ROI-positive demand anomalies.

    Story 3.3c (HOS-23): Format Staffing Recommendations for Dispatch.

    Status lifecycle:  ready_to_push → dispatched
    Idempotency: UNIQUE constraint on anomaly_id prevents duplicates.
    """
    __tablename__ = "staffing_recommendations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # HOS-165 — tenant_id is a human-readable slug (TEXT in Postgres).
    tenant_id = Column(String, nullable=False, index=True)
    property_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    anomaly_id = Column(
        UUID(as_uuid=True),
        ForeignKey("demand_anomalies.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,  # idempotency: one recommendation per anomaly
    )

    message_text = Column(Text, nullable=False)
    triggering_factor = Column(Text)
    recommended_headcount = Column(Integer)

    window_start = Column(DateTime(timezone=True), nullable=False)
    window_end = Column(DateTime(timezone=True), nullable=False)

    roi_net = Column(Numeric(10, 2))
    roi_labor_cost = Column(Numeric(10, 2))

    status = Column(String, nullable=False, default="ready_to_push")  # ready_to_push | dispatched | accepted | rejected

    # Story 4.2 (HOS-25): dispatch tracking
    dispatched_at = Column(DateTime(timezone=True), nullable=True)
    dispatch_channel = Column(String(10), nullable=True)  # whatsapp | sms | email

    # Story 4.3 (HOS-26): manager action logging
    actioned_at = Column(DateTime(timezone=True), nullable=True)
    action = Column(String(10), nullable=True)  # accepted | rejected

    # Story 10.10 (HOS-200): close the prediction → outcome loop.
    # predicted_covers is copied from demand_anomalies.expected_demand at
    # formatting time; actual_covers is reported by the manager via WhatsApp
    # feedback. Both are needed to compute real MAPE (Story 10.12 / HOS-202).
    # Mirror of migration 20260603120000 (schema drift gate — Décision #16).
    predicted_covers = Column(Numeric(10, 2), nullable=True)
    actual_covers = Column(Numeric(10, 2), nullable=True)
    actual_covers_source = Column(String, nullable=True)  # manager_feedback | pos_data (Phase 4)
    actual_covers_at = Column(DateTime(timezone=True), nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class ConversationalQuery(Base):
    """
    Inbound conversational queries from managers via Twilio webhooks.

    Story 5.1 (HOS-28): Parse Conversational Inbound Queries (FR13).

    Status lifecycle: pending → processing → answered
    Idempotency: same (from_number, body) within 60 s does not create a duplicate.
    """
    __tablename__ = "conversational_queries"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # HOS-165 — tenant_id is a human-readable slug (TEXT in Postgres).
    tenant_id = Column(String, nullable=False, index=True)
    property_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    from_number = Column(String, nullable=False)
    body = Column(Text, nullable=False)
    recommendation_id = Column(
        UUID(as_uuid=True),
        ForeignKey("staffing_recommendations.id", ondelete="SET NULL"),
        nullable=True,
    )
    status = Column(String, nullable=False, default="pending")  # pending | processing | answered
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class RecommendationCache(Base):
    """
    Persistence for AI staffing recommendations.
    Ensures the "Push" action can be performed on the correct data.
    """
    __tablename__ = "recommendation_cache"

    id = Column(Integer, primary_key=True)
    tenant_id = Column(String, ForeignKey("restaurant_profiles.tenant_id"), index=True, nullable=False)
    target_date = Column(Date, index=True, nullable=False)

    prediction_data = Column(JSON)
    reasoning_summary = Column(String)
    staffing_recommendation = Column(JSON)

    is_pushed = Column(Boolean, default=False)
    pushed_at = Column(DateTime)

    created_at = Column(DateTime, default=datetime.utcnow)


class FBPattern(Base):
    """
    F&B operational patterns stored as embeddings.

    HOS-99 (T2): replaces Qdrant `fb_patterns` collection.
    Enables pgvector cosine similarity search with SQL filters.

    In production (Supabase): column type is vector(1536) with HNSW index.
    In test (SQLite): falls back to JSON (no vector ops, mocked in tests).
    """
    __tablename__ = "fb_patterns"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, nullable=True, index=True)  # null = global pattern

    # Rich metadata filters (replaces Qdrant payload filters)
    service_type = Column(String, nullable=False, index=True)   # breakfast|lunch|dinner|room_service
    occupancy_band = Column(String, nullable=True)              # low|medium|high|full
    day_of_week = Column(String, nullable=True)                 # Mon-Sun
    weather_condition = Column(String, nullable=True)
    feedback_status = Column(String, nullable=False, default="neutral")  # followed|rejected|neutral

    # Pattern payload
    pattern_text = Column(Text, nullable=False)
    outcome_description = Column(Text, nullable=True)
    embedding = Column(_VECTOR_1536, nullable=True)

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class TrainingRun(Base):
    """
    Audit log for Prophet training runs (P0-1 / Decision #13).
    One row per POST /predictions/train call.
    """
    __tablename__ = "training_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(String, nullable=False, index=True)
    source = Column(String, nullable=False)           # mcp_sandbox | synthetic | hybrid
    records_count = Column(Integer, nullable=False)
    mape_training = Column(Float, nullable=True)      # in-sample MAPE, null if not computable
    duration_ms = Column(Integer, nullable=False)
    model_path = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class MCPApiToken(Base):
    """Bearer token for the inbound MCP Server (ADR 0001 · P1-2).

    Tokens are opaque strings (atx_<env>_<random>), SHA-256 hashed at rest.
    hotel_id is carried by the token — NEVER accepted as a client parameter.
    """
    __tablename__ = "mcp_api_tokens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hotel_id = Column(String, nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    token_prefix = Column(String, nullable=False)
    # HOS-150 AC3 — TEXT[] on Postgres (matches migration 20260418000000),
    # JSON list on SQLite for tests.
    scopes = Column(StringArray, nullable=False, default=lambda: ["predict", "recommend", "feedback"])
    label = Column(String, nullable=True)
    expires_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    last_used_at = Column(DateTime(timezone=True), nullable=True)
    revoked_at = Column(DateTime(timezone=True), nullable=True)


class OperationalMemory(Base):
    """
    Per-hotel operational memory: manager decisions, reflections, feedback.

    HOS-99 (T3): replaces Backboard.io API.
    Enables hybrid retrieval (vector similarity + SQL filters) in a single query.
    """
    __tablename__ = "operational_memory"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    hotel_id = Column(String, nullable=False, index=True)   # maps to tenant_id
    session_id = Column(String, nullable=True, index=True)

    # Stored content — aligned with migration 20260323240000
    reflection = Column(Text, nullable=False)       # reflection / feedback / context string
    reco_json = Column(JSON, nullable=True)          # cached recommendation payload
    manager_feedback = Column(String, nullable=True) # followed|rejected|neutral
    outcome = Column(Text, nullable=True)            # free-text outcome description
    memory_type = Column(String, nullable=False, default="reflection")
    # 'reflection' | 'feedback' | 'recommendation_cache'
    tags = Column(JSON, nullable=True)               # list of string tags

    embedding = Column(_VECTOR_1024, nullable=True)  # Mistral 1024d
    embedding_pending = Column(Boolean, nullable=False, default=False)

    # P2-2: backlink to the agent_action_log request that triggered this write.
    # Empty string for rows pre-dating this column (migration 20260419000200).
    request_id = Column(String, nullable=False, default="")

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class KpiDaily(Base):
    """Per-tenant daily KPI timeseries — HOS-177 (P3-3 Trust-KPI).

    tenant_id maps to hotel_id in agent_action_log / operational_memory
    (see docs/context/data-conventions.md and migration 20260521000000).
    """

    __tablename__ = "kpi_daily"

    tenant_id = Column(String, primary_key=True, nullable=False)
    kpi_date = Column(Date, primary_key=True, nullable=False)
    kpi_name = Column(String, primary_key=True, nullable=False)
    value = Column(Float, nullable=True)
    numerator = Column(Integer, nullable=True)
    denominator = Column(Integer, nullable=True)
    computed_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class AgentActionLog(Base):
    """One row per MCP tool call — billing + observability meter (ADR 0003 D1)."""

    __tablename__ = "agent_action_log"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    hotel_id = Column(String, nullable=False, index=True)
    tool_name = Column(String, nullable=False)
    # HOS-150 AC3 — TEXT[] on Postgres (matches migration 20260418000100),
    # JSON list on SQLite for tests.
    scopes = Column(StringArray, nullable=True)      # list[str]
    status = Column(String, nullable=False)          # ok|auth_error|tool_error|rate_limited
    error_code = Column(String, nullable=True)
    latency_ms = Column(Integer, nullable=True)
    embedding_latency_ms = Column(Integer, nullable=True)
    dedup_hit = Column(Boolean, nullable=True)
    top_similarity = Column(Float, nullable=True)
    request_id = Column(String, nullable=False, default="")
    payload = Column(JSON, nullable=True)          # arbitrary event payload (e.g. kpi_alert rows)

    # HOS-206 (EVAL-2 / ADR-0007 §6.a) — abstention + eval telemetry.
    # Mirror of migration 20260605000000 (schema drift gate — Décision #16).
    abstention_reason = Column(String, nullable=True)    # AbstentionReason | null
    abstention_context = Column(JSONB, nullable=True)
    abstention_layer = Column(String, nullable=True)     # forecast|recommendation|receipt|parser
    eval_run_id = Column(UUID(as_uuid=True), nullable=True)
    drift_score = Column(JSONB, nullable=True)


class EvalBaseline(Base):
    """Historical audit log of eval baselines (ADR-0007 §6.c, HOS-216 AC7).

    The git-tracked `eval/baselines/*.json` files stay the RUNTIME source of truth
    — the CI gate reads them directly. This table answers "what was our baseline on
    date X / which PR set it and why". Décision #16 ORM mirror of migration
    20260619010000. The partial unique index (one active baseline per layer) lives
    in the migration; the drift gate compares columns only, not indexes.
    """

    __tablename__ = "eval_baselines"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    layer = Column(String, nullable=False)              # forecast|parser|drift|latency|recall
    git_sha = Column(String, nullable=False)
    baseline_json = Column(JSONB, nullable=False)       # per-category metrics frozen
    reason = Column(String, nullable=False)             # why this baseline was set/reset
    pr_number = Column(Integer, nullable=True)
    is_active = Column(Boolean, nullable=False, default=False)
    superseded_by = Column(UUID(as_uuid=True), ForeignKey("eval_baselines.id"), nullable=True)
