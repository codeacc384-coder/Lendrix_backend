from sqlalchemy import Column, Integer, String, Boolean, Text, ForeignKey, DateTime
from database import Base
from datetime import datetime


class Policy(Base):
    __tablename__ = "PP_Policies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String)
    category = Column(String)
    description = Column(Text, nullable=True)
    document_url = Column(String, nullable=True)
    document_key = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    submitted_by_role = Column(String(20), default="admin")
    is_accepted = Column(Boolean, default=True)


class PolicyLimitation(Base):
    __tablename__ = "PP_PolicyLimitations"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("PP_Policies.id", ondelete="CASCADE"), nullable=False)
    title = Column(String)
    description = Column(Text)
    is_enabled = Column(Boolean, default=True)


class PolicyRequest(Base):
    __tablename__ = "PP_PolicyRequests"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("PP_Policies.id", ondelete="SET NULL"), nullable=True)
    action = Column(String(20), default="create")
    name = Column(String, nullable=True)
    category = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    is_active = Column(Boolean, nullable=True)
    requested_by = Column(String, nullable=False)
    status = Column(String(20), default="pending")
    admin_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)


class LimitationRequest(Base):
    __tablename__ = "PP_LimitationRequests"

    id = Column(Integer, primary_key=True, index=True)
    action = Column(String(20), nullable=False)
    policy_id = Column(Integer, ForeignKey("PP_Policies.id", ondelete="CASCADE"), nullable=True)
    limitation_id = Column(Integer, nullable=True)
    title = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    is_enabled = Column(Boolean, nullable=True)
    requested_by = Column(String, nullable=False)
    status = Column(String(20), default="pending")
    admin_note = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    reviewed_at = Column(DateTime, nullable=True)


class PolicyReview(Base):
    __tablename__ = "PP_PolicyReviews"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("PP_Policies.id", ondelete="CASCADE"), nullable=False)
    reviewed_by = Column(String, nullable=False)
    review = Column(Text, nullable=False)
    status = Column(String(20), default="open")
    created_at = Column(DateTime, default=datetime.utcnow)
