"""
seed_admin.py
-------------
Creates initial admin users in PP_Users and PP_AllowedEmails.

Run from inside the process_and_policies directory:
    python seed_admin.py

Edit the ADMIN_USERS list below before running.
"""

import uuid
import sys
from datetime import datetime
from dotenv import load_dotenv

load_dotenv()

from database import SessionLocal
from models.user import User, AllowedEmail
from utils import hash_password, normalize_phone_number

# ── Configure your admin users here ──────────────────────────────────────────
ADMIN_USERS = [
    {
        "full_name": "Angel Admin",
        "email": "angel@lendrixventech.com",
        "password": "Admin@1234",
        "phone": "+919999999901",
        "role": "angel",           # angel | vcs | compliance_team | team_access
    },
    {
        "full_name": "VCS Admin",
        "email": "vcs@lendrixventech.com",
        "password": "Admin@1234",
        "phone": "+919999999902",
        "role": "vcs",
    },
]
# ─────────────────────────────────────────────────────────────────────────────


def get_role_group(role: str) -> str:
    if role in ("angel", "vcs"):
        return "admin"
    elif role == "team_access":
        return "team_access"
    return "compliance_team"


def seed():
    db = SessionLocal()
    created = 0
    skipped = 0

    try:
        for u in ADMIN_USERS:
            role       = u["role"]
            role_group = get_role_group(role)
            email      = u["email"].strip().lower()
            phone      = normalize_phone_number(u["phone"])

            # ── PP_Users ──────────────────────────────────────────────────────
            existing = db.query(User).filter(
                User.email == email,
                User.role_group == role_group
            ).first()

            if existing:
                print(f"  SKIP  PP_Users       | {email} ({role_group}) already exists")
                skipped += 1
            else:
                new_user = User(
                    id=uuid.uuid4(),
                    email=email,
                    full_name=u.get("full_name"),
                    password_hash=hash_password(u["password"]),
                    role=role,
                    role_group=role_group,
                    phone=phone,
                    is_phone_verified=True,
                    created_at=datetime.utcnow(),
                )
                db.add(new_user)
                print(f"  CREATE PP_Users       | {email} role={role} role_group={role_group}")
                created += 1

            # ── PP_AllowedEmails (required for angel/vcs registration) ────────
            if role in ("angel", "vcs"):
                allowed = db.query(AllowedEmail).filter(
                    AllowedEmail.email == email
                ).first()

                if allowed:
                    print(f"  SKIP  PP_AllowedEmails | {email} already in whitelist")
                else:
                    db.add(AllowedEmail(
                        id=uuid.uuid4(),
                        email=email,
                        assigned_role=role,
                    ))
                    print(f"  CREATE PP_AllowedEmails | {email} assigned_role={role}")

        db.commit()
        print()
        print(f"Done. Created: {created}  Skipped: {skipped}")

    except Exception as e:
        db.rollback()
        print(f"ERROR: {e}")
        sys.exit(1)
    finally:
        db.close()


if __name__ == "__main__":
    print("=" * 55)
    print("Seeding admin users into LV_ProcessPolicies_DB")
    print("=" * 55)
    seed()
