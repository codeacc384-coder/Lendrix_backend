"""
Migration: Create missing PP_ tables in LV_ProcessPolicies_DB
and migrate data from lendrixtest1.
Safe to run multiple times - will not delete existing data.
"""
import psycopg2
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dotenv import load_dotenv
load_dotenv()

from database import Base, engine
import models  # triggers all model registrations

_host = os.getenv("DB_HOST")
_port = int(os.getenv("DB_PORT", 5432))
_user = os.getenv("DB_USER")
_password = os.getenv("DB_PASSWORD")
_sslmode = os.getenv("DB_SSLMODE", "prefer")

TARGET = dict(host=_host, port=_port, dbname=os.getenv("DB_TARGET_NAME", "LV_ProcessPolicies_DB"), user=_user, password=_password, sslmode=_sslmode)
SOURCE = dict(host=_host, port=_port, dbname=os.getenv("DB_SOURCE_NAME", "lendrixtest1"), user=_user, password=_password, sslmode=_sslmode)

MIGRATION_MAP = [
    ("locations",            "PP_Locations",            ["id","state","city","locality","pincode","latitude","longitude"]),
    ("states",               "PP_States",               ["id","name"]),
    ("properties",           "PP_Properties",           ["id","title","property_type","listing_type","location_id","owner_id","verification_status","status","created_at","updated_at"]),
    ("property_attributes",  "PP_PropertyAttributes",   ["property_id","bedrooms","bathrooms","balconies","area_sqft","carpet_area_sqft","furnishing_status","floor_number","total_floors","parking_spaces","age_years"]),
    ("property_pricing",     "PP_PropertyPricing",      ["property_id","asking_price","price_per_sqft","maintenance_monthly","security_deposit","currency","price_negotiable","last_updated"]),
    ("property_media",       "PP_PropertyMedia",        ["id","property_id","media_type","cdn_url","is_primary","display_order","uploaded_at"]),
    ("property_documents",   "PP_PropertyDocuments",    ["id","property_id","document_type","document_url","document_name","uploaded_at"]),
    ("property_clob_content","PP_PropertyClobContent",  ["property_id","content_type","content"]),
    ("verification_log",     "PP_VerificationLogs",     ["id","property_id","verified_by","verification_status","verification_notes","verified_at"]),
]

def create_tables():
    print("Creating missing tables in LV_ProcessPolicies_DB...")
    Base.metadata.create_all(bind=engine, checkfirst=True)
    print("Tables created (existing tables untouched).")

ALLOWED_SOURCE_TABLES = {entry[0] for entry in MIGRATION_MAP}
ALLOWED_TARGET_TABLES = {entry[1] for entry in MIGRATION_MAP}
ALLOWED_COLUMNS = {col for entry in MIGRATION_MAP for col in entry[2]}


def _safe_col_list(cols):
    """Quote each column name to prevent SQL injection if the map is ever extended."""
    return ", ".join(f'"{c}"' for c in cols)


def migrate_data():
    src = psycopg2.connect(**SOURCE)
    tgt = psycopg2.connect(**TARGET)
    src_cur = src.cursor()
    tgt_cur = tgt.cursor()

    for src_table, tgt_table, cols in MIGRATION_MAP:
        col_list = _safe_col_list(cols)
        placeholders = ", ".join(["%s"] * len(cols))

        tgt_cur.execute(f'SELECT COUNT(*) FROM "{tgt_table}"')
        existing = tgt_cur.fetchone()[0]

        src_cur.execute(f'SELECT {col_list} FROM "{src_table}"')
        rows = src_cur.fetchall()

        if existing > 0:
            print(f"  {tgt_table}: already has {existing} rows, skipping migration.")
            continue

        if not rows:
            print(f"  {tgt_table}: no source data to migrate.")
            continue

        tgt_cur.executemany(
            f'INSERT INTO "{tgt_table}" ({col_list}) VALUES ({placeholders}) ON CONFLICT DO NOTHING',
            rows
        )
        tgt.commit()
        print(f"  {tgt_table}: migrated {len(rows)} rows from {src_table}.")

    src_cur.close()
    tgt_cur.close()
    src.close()
    tgt.close()

if __name__ == "__main__":
    create_tables()
    migrate_data()
    print("\nMigration complete.")
