import sys, os
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

from database import SessionLocal
from models.user import AllowedEmail
import uuid

db = SessionLocal()

try:
    existing = db.query(AllowedEmail).filter(
        AllowedEmail.email == "pavancse.gist@gmail.com"
    ).first()

    if existing:
        print("Email already exists in allowed list.")
    else:
        entry = AllowedEmail(
            id=uuid.uuid4(),
            email="pavancse.gist@gmail.com",
            assigned_role="angel"
        )
        db.add(entry)
        db.commit()
        print("Email added to allowed list.")

finally:
    db.close()
