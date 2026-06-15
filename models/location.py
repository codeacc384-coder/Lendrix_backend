from sqlalchemy import Column, String, Integer
from sqlalchemy.dialects.postgresql import UUID, TSVECTOR
from database import Base
import uuid


class Location(Base):
    __tablename__ = "PP_Locations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    state = Column(String, nullable=False)
    city = Column(String, nullable=False)
    locality = Column(String, nullable=True)
    pincode = Column(String, nullable=True)
    latitude = Column(String, nullable=True)
    longitude = Column(String, nullable=True)
    search_vector = Column(TSVECTOR, nullable=True)


class State(Base):
    __tablename__ = "PP_States"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
