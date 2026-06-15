from sqlalchemy import Column, String, Integer, Float, Boolean, Text, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import ForeignKey
from database import Base
from datetime import datetime
import uuid


class Property(Base):
    __tablename__ = "PP_Properties"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    title = Column(String, nullable=False)
    property_type = Column(String, nullable=False)
    listing_type = Column(String, nullable=True)
    location_id = Column(UUID(as_uuid=True), ForeignKey("PP_Locations.id"), nullable=False)
    owner_id = Column(UUID(as_uuid=True), nullable=True)
    verification_status = Column(String, nullable=True)
    status = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=True)


class PropertyAttribute(Base):
    __tablename__ = "PP_PropertyAttributes"

    property_id = Column(UUID(as_uuid=True), ForeignKey("PP_Properties.id", ondelete="CASCADE"), primary_key=True)
    bedrooms = Column(Integer, nullable=True)
    bathrooms = Column(Integer, nullable=True)
    balconies = Column(Integer, nullable=True)
    area_sqft = Column(Float, nullable=True)
    carpet_area_sqft = Column(Float, nullable=True)
    furnishing_status = Column(String, nullable=True)
    floor_number = Column(Integer, nullable=True)
    total_floors = Column(Integer, nullable=True)
    parking_spaces = Column(Integer, nullable=True)
    age_years = Column(Integer, nullable=True)


class PropertyPricing(Base):
    __tablename__ = "PP_PropertyPricing"

    property_id = Column(UUID(as_uuid=True), ForeignKey("PP_Properties.id", ondelete="CASCADE"), primary_key=True)
    asking_price = Column(Float, nullable=False)
    price_per_sqft = Column(Float, nullable=True)
    maintenance_monthly = Column(Float, nullable=True)
    security_deposit = Column(Float, nullable=True)
    currency = Column(String, nullable=True)
    price_negotiable = Column(String, nullable=True)
    last_updated = Column(DateTime, nullable=True)


class PropertyMedia(Base):
    __tablename__ = "PP_PropertyMedia"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("PP_Properties.id", ondelete="CASCADE"), nullable=False)
    media_type = Column(String, nullable=False)
    cdn_url = Column(Text, nullable=False)
    is_primary = Column(Boolean, nullable=True)
    display_order = Column(Integer, nullable=True)
    uploaded_at = Column(DateTime, nullable=True)


class PropertyDocument(Base):
    __tablename__ = "PP_PropertyDocuments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("PP_Properties.id", ondelete="CASCADE"), nullable=False)
    document_type = Column(String, nullable=False)
    document_url = Column(Text, nullable=False)
    document_name = Column(String, nullable=True)
    uploaded_at = Column(DateTime, nullable=True)


class PropertyClobContent(Base):
    __tablename__ = "PP_PropertyClobContent"

    property_id = Column(UUID(as_uuid=True), ForeignKey("PP_Properties.id", ondelete="CASCADE"), primary_key=True)
    content_type = Column(String, primary_key=True, nullable=False)
    content = Column(Text, nullable=True)


class VerificationLog(Base):
    __tablename__ = "PP_VerificationLogs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    property_id = Column(UUID(as_uuid=True), ForeignKey("PP_Properties.id", ondelete="CASCADE"), nullable=False)
    verified_by = Column(UUID(as_uuid=True), nullable=False)
    verification_status = Column(String, nullable=False)
    verification_notes = Column(Text, nullable=True)
    verified_at = Column(DateTime, nullable=True)
