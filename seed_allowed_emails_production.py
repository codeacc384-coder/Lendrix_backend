"""
Run this ONCE to insert allowed emails into the PRODUCTION database.
Usage:
    python seed_allowed_emails_production.py
"""
import sys, os, uuid
sys.path.insert(0, ".")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# ── Direct production DB URL — bypasses .env entirely ─────────────────────────
PROD_DB_URL = (
    "postgresql+psycopg2://dbadmin:MwUJ2C8ny%40MGCnYR"
    "@public-primary-pg-inbangalore-189799-1664910.db.onutho.com"
    ":5432/LV_ProcessPolicies_DB?sslmode=disable"
)

engine = create_engine(PROD_DB_URL, connect_args={"connect_timeout": 30})
SessionLocal = sessionmaker(bind=engine)

# ── Add your emails and roles here ────────────────────────────────────────────
EMAILS_TO_ADD = [
    {"email": "deepakdash@lendrixventech.com", "assigned_role": "angel"},
    {"email": "pavancse.gist@gmail.com",       "assigned_role": "angel"},
    # add more rows here if needed
]

# ── Import model AFTER engine is ready ────────────────────────────────────────
from models.user import AllowedEmail

db = SessionLocal()
try:
    for entry in EMAILS_TO_ADD:
        existing = db.query(AllowedEmail).filter(
            AllowedEmail.email == entry["email"]
        ).first()
        if existing:
            print(f"  SKIP  (already exists): {entry['email']}")
        else:
            db.add(AllowedEmail(
                id=uuid.uuid4(),
                email=entry["email"],
                assigned_role=entry["assigned_role"],
            ))
            print(f"  ADDED: {entry['email']}  role={entry['assigned_role']}")
    db.commit()
    print("\nDone. Production PP_AllowedEmails updated.")
finally:
    db.close()
