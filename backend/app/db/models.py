from sqlalchemy import Column, String, Float, Integer, Date, DateTime, JSON, ForeignKey, Boolean, Numeric, Text
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from fastapi_users.db import SQLAlchemyBaseUserTableUUID
from datetime import datetime
import uuid

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

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    tenant_id = Column(String, unique=True, index=True, nullable=False)
    
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

class WeatherForecast(Base):
    """
    Normalized weather forecast data for a property.
    Story 3.1: Ingest Localized Weather Data.
    """
    __tablename__ = "weather_forecasts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    property_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    forecast_timestamp = Column(DateTime(timezone=True), nullable=False)
    condition_code = Column(String, nullable=False)
    temperature_c = Column(Numeric(5, 2))
    precipitation_prob = Column(Integer)
    wind_speed_kmh = Column(Numeric(6, 2))
    raw_payload = Column(JSONB)
    ingested_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class LocalEvent(Base):
    """
    Normalized local event data for a property from PredictHQ.
    Story 3.2: Ingest Localized Event Data.
    """
    __tablename__ = "local_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    property_id = Column(UUID(as_uuid=True), nullable=False, index=True)
    predicthq_event_id = Column(String, nullable=False)
    title = Column(String, nullable=False)
    category = Column(String, nullable=False)
    phq_category = Column(String)
    start_dt = Column(DateTime(timezone=True), nullable=False)
    end_dt = Column(DateTime(timezone=True))
    predicted_attendance = Column(Integer)
    impact_score = Column(Numeric(5, 2))
    rank = Column(Integer)
    location_lat = Column(Numeric(9, 6))
    location_lng = Column(Numeric(9, 6))
    raw_payload = Column(JSONB)
    ingested_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)


class DemandAnomaly(Base):
    """
    Detected demand anomaly window for a property.
    Story 3.3a: Detect Demand Anomalies Against Baseline.

    Status lifecycle:
      'detected' -> 'roi_positive' (3.3b) -> 'ready_to_push' (3.3c) -> 'dispatched' (Epic 4)
    """
    __tablename__ = "demand_anomalies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
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
    tenant_id = Column(UUID(as_uuid=True), nullable=False, index=True)
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

    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


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
