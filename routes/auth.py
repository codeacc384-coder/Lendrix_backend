import logging
import os
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import HTTPBearer
from jose import JWTError, jwt
from pydantic import BaseModel, EmailStr, field_validator
from sqlalchemy.orm import Session

from database import get_db
from models.user import AllowedEmail, User
from utils import hash_password, normalize_phone_number, verify_password

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("SECRET_KEY", "")
if not SECRET_KEY or SECRET_KEY == "your_super_secret_random_string_here":
    import warnings
    warnings.warn("SECRET_KEY is not set or is using the default insecure value", stacklevel=1)
    SECRET_KEY = "insecure-default-change-me"

ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))
REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))

security_scheme = HTTPBearer()
router = APIRouter(prefix="/auth", tags=["Authentication"])


class UserRole(str, Enum):
    angel = "angel"
    vcs = "vcs"
    compliance_team = "compliance_team"
    team_access = "team_access"


def _get_role_group(role: str) -> str:
    if role in ("angel", "vcs"):
        return "admin"
    elif role == "team_access":
        return "team_access"
    return "compliance_team"


def _get_permissions(role_group: str) -> list:
    if role_group == "admin":
        return ["read", "create", "update", "delete"]
    return ["read"]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_access_token(email: str, role: str, role_group: str) -> str:
    payload = {
        "sub": email,
        "role": role,
        "role_group": role_group,
        "type": "access",
        "exp": _utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(email: str, role_group: str) -> str:
    payload = {
        "sub": email,
        "role_group": role_group,
        "type": "refresh",
        "exp": _utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
    }
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def get_current_user(token=Depends(security_scheme), db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(token.credentials, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "access":
            raise HTTPException(status_code=401, detail="Invalid token type")
        email: str = payload.get("sub")
        role: str = payload.get("role")
        role_group: str = payload.get("role_group")
        if not email or not role or not role_group:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError as e:
        if "expired" in str(e).lower():
            raise HTTPException(status_code=401, detail="Access token has expired")
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.query(User).filter(User.email == email, User.role_group == role_group).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_admin_role(current_user: User = Depends(get_current_user)):
    if current_user.role_group != "admin":
        raise HTTPException(status_code=403, detail="Angel or VCS role required")
    return current_user


def require_view_access(current_user: User = Depends(get_current_user)):
    if current_user.role_group not in ("admin", "team_access", "compliance_team"):
        raise HTTPException(status_code=403, detail="Access denied")
    return current_user


class RegisterRequest(BaseModel):
    full_name: Optional[str] = None
    email: EmailStr
    password: str
    phone: str
    role: UserRole

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v

    @field_validator("full_name")
    @classmethod
    def name_length(cls, v: Optional[str]) -> Optional[str]:
        if v and len(v) > 255:
            raise ValueError("full_name too long")
        return v


class LoginRequest(BaseModel):
    email: EmailStr
    password: str
    role: UserRole


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class ChangePasswordRequest(BaseModel):
    role: UserRole
    email: EmailStr
    current_password: str
    new_password: str
    confirm_password: str

    @field_validator("new_password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters")
        return v


@router.post("/register")
def register(data: RegisterRequest, db: Session = Depends(get_db)):
    role_group = _get_role_group(data.role.value)

    if data.role.value in ("angel", "vcs"):
        allowed = db.query(AllowedEmail).filter(AllowedEmail.email == data.email).first()
        if not allowed:
            raise HTTPException(status_code=403, detail="Your email is not authorized for Angel/VCS registration")
        assigned_role = allowed.assigned_role
    elif data.role.value == "team_access":
        assigned_role = "team_access"
    else:
        assigned_role = "compliance_team"

    if db.query(User).filter(User.email == data.email, User.role_group == role_group).first():
        raise HTTPException(status_code=400, detail=f"Email already registered as {assigned_role}")

    normalized_phone = normalize_phone_number(data.phone)
    if db.query(User).filter(User.phone == normalized_phone, User.role_group == role_group).first():
        raise HTTPException(status_code=400, detail="Phone number already exists for this role")

    new_user = User(
        full_name=data.full_name,
        email=data.email,
        password_hash=hash_password(data.password),
        role=assigned_role,
        role_group=role_group,
        is_phone_verified=False,
        phone=normalized_phone,
    )
    db.add(new_user)
    db.commit()
    logger.info(f"New user registered: {data.email} role={assigned_role}")
    return {"message": "Registered successfully!", "role": assigned_role}


@router.post("/login")
def login(data: LoginRequest, db: Session = Depends(get_db)):
    role_group = _get_role_group(data.role.value)
    user = db.query(User).filter(User.email == data.email, User.role_group == role_group).first()
    if not user or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token = create_access_token(email=user.email, role=user.role, role_group=role_group)
    refresh_token = create_refresh_token(email=user.email, role_group=role_group)
    user.refresh_token = refresh_token
    db.commit()

    return {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "token_type": "bearer",
        "role": user.role,
        "email": user.email,
        "full_name": user.full_name,
        "permissions": _get_permissions(role_group),
        "session_timeout_minutes": ACCESS_TOKEN_EXPIRE_MINUTES,
    }


@router.post("/refresh-token")
def refresh_token(body: RefreshTokenRequest, db: Session = Depends(get_db)):
    try:
        payload = jwt.decode(body.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
        if payload.get("type") != "refresh":
            raise HTTPException(status_code=401, detail="Invalid token type")
        email: str = payload.get("sub")
        role_group: str = payload.get("role_group")
        if not email or not role_group:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Session expired. Please login again")

    user = db.query(User).filter(User.email == email, User.role_group == role_group).first()
    if not user or user.refresh_token != body.refresh_token:
        raise HTTPException(status_code=401, detail="Invalid session. Please login again")

    new_access_token = create_access_token(email=user.email, role=user.role, role_group=role_group)
    return {"access_token": new_access_token, "token_type": "bearer", "session_timeout_minutes": ACCESS_TOKEN_EXPIRE_MINUTES}


@router.post("/logout")
def logout(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    current_user.refresh_token = None
    db.commit()
    return {"message": "Logged out successfully"}


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user)):
    return {
        "email": current_user.email,
        "full_name": current_user.full_name,
        "role": current_user.role,
        "phone": current_user.phone,
        "permissions": _get_permissions(current_user.role_group),
    }


@router.post("/change-password")
def change_password(data: ChangePasswordRequest, db: Session = Depends(get_db)):
    if data.new_password != data.confirm_password:
        raise HTTPException(status_code=400, detail="New password and confirm password do not match")
    role_group = _get_role_group(data.role.value)
    user = db.query(User).filter(User.email == data.email, User.role_group == role_group).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not verify_password(data.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(data.new_password)
    db.commit()
    return {"message": "Password changed successfully"}
