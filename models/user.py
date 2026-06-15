from sqlalchemy import Column, String, Boolean, DateTime, UniqueConstraint
from database import Base
import uuid
from datetime import datetime
from sqlalchemy.dialects.postgresql import UUID


class User(Base):
    __tablename__ = "PP_Users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    password_hash = Column(String)
    email = Column(String(255), nullable=False, index=True)
    full_name = Column(String(255))
    role = Column(String(50), nullable=False)
    role_group = Column(String(50), nullable=False)
    is_phone_verified = Column(Boolean, default=False)
    phone = Column(String(20), nullable=False)
    otp_code = Column(String, nullable=True)
    otp_expiry = Column(DateTime, nullable=True)
    refresh_token = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    __table_args__ = (
        UniqueConstraint("email", "role_group", name="uq_pp_user_email_role_group"),
        UniqueConstraint("phone", "role_group", name="uq_pp_user_phone_role_group"),
    )


class AllowedEmail(Base):
    __tablename__ = "PP_AllowedEmails"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    assigned_role = Column(String(50), nullable=False)
