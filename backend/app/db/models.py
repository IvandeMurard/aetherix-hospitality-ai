from sqlalchemy import Column, String, Float, Integer, Date, DateTime, JSON, ForeignKey, Boolean, Numeric
from sqlalchemy.orm import declarative_base, relationship
from sqlalchemy.dialects.postgresql import UUID, TIMESTAMP
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
    
    # Notification preferences
    notification_channel = Column(String, default="whatsapp")
    phone_number = Column(String)
    email_address = Column(String)
    
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
    Hourly weather forecast data ingested from Open-Meteo.
    Story 3.1: Ingest Localized Weather Data (HOS-83).
    Upsert key: (tenant_id, property_id, forecast_timestamp).
    """
    __tablename__ = "weather_forecasts"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    tenant_id = Column(String, ForeignKey("restaurant_profiles.tenant_id"), index=True, nullable=False)
    property_id = Column(String, nullable=False)
    forecast_timestamp = Column(TIMESTAMP(timezone=True), nullable=False, index=True)

    # Normalized weather fields (ready for Story 3.3a cross-reference)
    condition_code = Column(Integer)        # WMO weather interpretation code
    temperature_c = Column(Numeric(5, 2))   # degrees Celsius
    precipitation_prob = Column(Integer)    # 0-100 %
    wind_speed_kmh = Column(Numeric(6, 2))  # km/h

    source = Column(String, nullable=False, default="open-meteo")
    fetched_at = Column(TIMESTAMP(timezone=True), nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, default=datetime.utcnow)

    property = relationship("RestaurantProfile", foreign_keys=[tenant_id],
                            primaryjoin="WeatherForecast.tenant_id == RestaurantProfile.tenant_id")


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
