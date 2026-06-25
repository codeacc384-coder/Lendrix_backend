"""
Create only PP_Users and PP_AllowedEmails tables.
Safe to run multiple times - will not affect existing tables.
"""
import os
import sys
from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.dirname(__file__))

from database import Base, engine
from models.user import User, AllowedEmail

if __name__ == "__main__":
    print("Creating PP_Users and PP_AllowedEmails tables...")
    Base.metadata.create_all(bind=engine, tables=[User.__table__, AllowedEmail.__table__], checkfirst=True)
    print("Done. Tables created (existing tables untouched).")
