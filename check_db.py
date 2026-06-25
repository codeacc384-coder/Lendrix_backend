import sys, os
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy import create_engine, text

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    rows = conn.execute(text("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)).fetchall()
    print("Tables in DB:")
    for r in rows:
        print(" ", r[0])

    try:
        count = conn.execute(text('SELECT COUNT(*) FROM "PP_Users"')).scalar()
        print(f"\nPP_Users row count: {count}")
    except Exception as e:
        print(f"\nPP_Users error: {e}")

    try:
        emails = conn.execute(text('SELECT email, assigned_role FROM "PP_AllowedEmails"')).fetchall()
        print(f"PP_AllowedEmails rows: {emails}")
    except Exception as e:
        print(f"PP_AllowedEmails error: {e}")
