"""Real estate domain models: properties, listings, valuations, leads."""
from sqlalchemy import String, Text, Boolean, DateTime, Integer, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from api.core.db import Base
from datetime import datetime, timezone
import uuid, enum

class PropertyType(str, enum.Enum):
    RESIDENTIAL = "residential"
    COMMERCIAL = "commercial"
    INDUSTRIAL = "industrial"
    LAND = "land"

class ListingStatus(str, enum.Enum):
    ACTIVE = "active"
    UNDER_CONTRACT = "under_contract"
    SOLD = "sold"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"

class Property(Base):
    __tablename__ = "properties"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    address_line1: Mapped[str] = mapped_column(String(500))
    address_line2: Mapped[str] = mapped_column(String(200), nullable=True)
    city: Mapped[str] = mapped_column(String(100), index=True)
    state: Mapped[str] = mapped_column(String(50), index=True)
    postcode: Mapped[str] = mapped_column(String(20), index=True)
    country: Mapped[str] = mapped_column(String(60), default="AU")
    latitude: Mapped[float] = mapped_column(Numeric(10, 8), nullable=True)
    longitude: Mapped[float] = mapped_column(Numeric(11, 8), nullable=True)
    property_type: Mapped[PropertyType] = mapped_column(default=PropertyType.RESIDENTIAL)
    bedrooms: Mapped[int] = mapped_column(Integer, default=0)
    bathrooms: Mapped[int] = mapped_column(Integer, default=0)
    car_spaces: Mapped[int] = mapped_column(Integer, default=0)
    land_sqm: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    floor_sqm: Mapped[float] = mapped_column(Numeric(10, 2), nullable=True)
    features: Mapped[dict] = mapped_column(JSONB, default={})
    images: Mapped[list] = mapped_column(JSONB, default=[])
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    listings: Mapped[list["Listing"]] = relationship("Listing", back_populates="property")

class Listing(Base):
    __tablename__ = "listings"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("properties.id", ondelete="CASCADE"), index=True)
    agent_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), index=True)
    status: Mapped[ListingStatus] = mapped_column(default=ListingStatus.ACTIVE, index=True)
    asking_price: Mapped[float] = mapped_column(Numeric(14, 2))
    days_on_market: Mapped[int] = mapped_column(Integer, default=0)
    description: Mapped[str] = mapped_column(Text)
    highlights: Mapped[list] = mapped_column(JSONB, default=[])
    ai_valuation: Mapped[float] = mapped_column(Numeric(14, 2), nullable=True)
    ai_valuation_confidence: Mapped[float] = mapped_column(Numeric(5, 4), nullable=True)
    views: Mapped[int] = mapped_column(Integer, default=0)
    saves: Mapped[int] = mapped_column(Integer, default=0)
    listed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    sold_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    sold_price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=True)
    property: Mapped["Property"] = relationship("Property", back_populates="listings")

class Lead(Base):
    __tablename__ = "leads"
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    listing_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("listings.id"), index=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True)
    name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str] = mapped_column(String(255))
    phone: Mapped[str] = mapped_column(String(30), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=True)
    intent: Mapped[str] = mapped_column(String(20), default="enquire")  # enquire, inspect, offer
    ai_score: Mapped[float] = mapped_column(Numeric(5, 4), nullable=True)
    is_qualified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
