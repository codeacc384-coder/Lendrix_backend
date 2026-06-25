"""
Full diagnostic: DB connection, tables, data counts, and all API endpoints.
"""
import sys, os, json
sys.path.insert(0, ".")
from dotenv import load_dotenv
load_dotenv()

import requests
from sqlalchemy import create_engine, text

BASE_URL = "http://localhost:8000"
DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

# ── 1. DB CONNECTION ──────────────────────────────────────────────────────────
print("=" * 60)
print("1. DATABASE CONNECTION")
print("=" * 60)
try:
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    print("  OK - Connected successfully")
except Exception as e:
    print(f"  FAIL - {e}")
    sys.exit(1)

# ── 2. TABLES & ROW COUNTS ───────────────────────────────────────────────────
print("\n" + "=" * 60)
print("2. TABLES & ROW COUNTS")
print("=" * 60)
with engine.connect() as conn:
    tables = conn.execute(text("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name;
    """)).fetchall()
    for (t,) in tables:
        try:
            count = conn.execute(text(f'SELECT COUNT(*) FROM "{t}"')).scalar()
            print(f"  {t:<35} {count} rows")
        except Exception as e:
            print(f"  {t:<35} ERROR: {e}")

# ── 3. ALLOWED EMAILS ────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("3. PP_AllowedEmails")
print("=" * 60)
with engine.connect() as conn:
    rows = conn.execute(text('SELECT email, assigned_role FROM "PP_AllowedEmails"')).fetchall()
    if rows:
        for email, role in rows:
            print(f"  {email} -> {role}")
    else:
        print("  EMPTY - No allowed emails found")

# ── 4. API HEALTH CHECK ──────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("4. API HEALTH CHECK")
print("=" * 60)
try:
    r = requests.get(f"{BASE_URL}/docs", timeout=5)
    print(f"  /docs -> {r.status_code}")
except Exception as e:
    print(f"  /docs -> FAIL: {e}")

# ── 5. AUTH ENDPOINTS ────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("5. AUTH ENDPOINTS")
print("=" * 60)

TEST_EMAIL = "pavancse.gist@gmail.com"
TEST_PASSWORD = "pavan@123"
TEST_ROLE = "angel"

# Login
try:
    r = requests.post(f"{BASE_URL}/auth/login", json={
        "email": TEST_EMAIL, "password": TEST_PASSWORD, "role": TEST_ROLE
    }, timeout=5)
    print(f"  POST /auth/login -> {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        access_token = data["access_token"]
        refresh_token = data["refresh_token"]
        print(f"    role={data['role']} email={data['email']}")
        print(f"    permissions={data['permissions']}")
    else:
        print(f"    {r.json()}")
        access_token = None
        refresh_token = None
except Exception as e:
    print(f"  POST /auth/login -> FAIL: {e}")
    access_token = None
    refresh_token = None

# /auth/me
if access_token:
    try:
        r = requests.get(f"{BASE_URL}/auth/me",
            headers={"Authorization": f"Bearer {access_token}"}, timeout=5)
        print(f"  GET  /auth/me -> {r.status_code}")
        if r.status_code == 200:
            print(f"    {r.json()}")
        else:
            print(f"    {r.json()}")
    except Exception as e:
        print(f"  GET  /auth/me -> FAIL: {e}")

# Refresh token
if refresh_token:
    try:
        r = requests.post(f"{BASE_URL}/auth/refresh-token",
            json={"refresh_token": refresh_token}, timeout=5)
        print(f"  POST /auth/refresh-token -> {r.status_code}")
        if r.status_code != 200:
            print(f"    {r.json()}")
    except Exception as e:
        print(f"  POST /auth/refresh-token -> FAIL: {e}")

# ── 6. OTHER ROUTES ──────────────────────────────────────────────────────────
print("\n" + "=" * 60)
print("6. OTHER ROUTES (authenticated)")
print("=" * 60)

headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}

routes = [
    ("GET", "/"),
]

# Discover routes from openapi
try:
    r = requests.get(f"{BASE_URL}/openapi.json", timeout=5)
    if r.status_code == 200:
        paths = r.json().get("paths", {})
        for path, methods in paths.items():
            if path in ("/auth/login", "/auth/register", "/auth/refresh-token",
                        "/auth/logout", "/auth/me", "/auth/change-password"):
                continue
            for method in methods:
                if method.upper() == "GET":
                    routes.append((method.upper(), path))
except Exception as e:
    print(f"  Could not fetch openapi.json: {e}")

for method, path in routes:
    try:
        r = requests.request(method, f"{BASE_URL}{path}", headers=headers, timeout=5)
        print(f"  {method:<6} {path:<40} -> {r.status_code}")
    except Exception as e:
        print(f"  {method:<6} {path:<40} -> FAIL: {e}")

print("\n" + "=" * 60)
print("DIAGNOSTIC COMPLETE")
print("=" * 60)
