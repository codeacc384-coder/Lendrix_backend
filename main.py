import logging
import os
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import OperationalError, SQLAlchemyError
from database import Base, engine, check_db_connection

from routes.auth import router as auth_router
from routes.angel_vcs import router as angel_vcs_router
from routes.requests import compliance_router, team_router, admin_router, review_router
from routes.team import router as team_policy_router, compliance_router as compliance_policy_router

import models.user
import models.policy

# Configure logging first so all startup errors are properly formatted
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Fail hard at startup if SECRET_KEY is insecure — do not allow silent fallback
_secret = os.getenv("SECRET_KEY", "")
if not _secret or _secret == "your_super_secret_random_string_here":
    raise RuntimeError("SECRET_KEY env var is not set or is using the insecure default value. Set a strong random SECRET_KEY before deploying.")

ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv("ALLOWED_ORIGINS", "*").split(",")
    if origin.strip()
]

app = FastAPI(title="Lendrix - Process & Policies API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    try:
        check_db_connection()
    except RuntimeError as e:
        logger.error(f"Startup DB check failed: {e}. App will still start but DB may be unavailable.")
        # Do not crash the process — let the app start and surface DB errors per-request


@app.exception_handler(OperationalError)
async def db_operational_error_handler(request: Request, exc: OperationalError):
    logger.error(f"DB OperationalError on {request.url}: {exc}")
    return JSONResponse(status_code=503, content={"detail": "Database unavailable. Please try again."})


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"SQLAlchemyError on {request.url}: {type(exc).__name__}: {exc}")
    return JSONResponse(status_code=500, content={"detail": "A database error occurred."})


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    logger.error(f"RuntimeError on {request.url}: {exc}")
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    logger.error(f"Unhandled exception on {request.url}: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred."})

# Base.metadata.create_all(bind=engine)  # tables pre-created in LV_ProcessPolicies_DB

app.include_router(auth_router)
app.include_router(angel_vcs_router)
app.include_router(compliance_router)
app.include_router(team_router)
app.include_router(admin_router)
app.include_router(review_router)
app.include_router(team_policy_router)
app.include_router(compliance_policy_router)


@app.get("/")
def home():
    return {"msg": "Lendrix Process & Policies API is Online"}


@app.get("/debug/db-check")
def debug_db_check():
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError
    try:
        with engine.connect() as conn:
            db_name = conn.execute(text("SELECT current_database()")).scalar()
            db_host = conn.execute(text("SELECT inet_server_addr()")).scalar()
            user_count = conn.execute(text('SELECT COUNT(*) FROM "PP_Users"')).scalar()
            allowed_count = conn.execute(text('SELECT COUNT(*) FROM "PP_AllowedEmails"')).scalar()
            deepak = conn.execute(text('SELECT email, role, role_group FROM "PP_Users" WHERE email = \'deepakdash@lendrixventech.com\'')).fetchone()
        return {
            "connected_db": db_name,
            "connected_host": str(db_host),
            "PP_Users_count": user_count,
            "PP_AllowedEmails_count": allowed_count,
            "deepak_user_exists": deepak is not None,
            "deepak_row": {"email": deepak[0], "role": deepak[1], "role_group": deepak[2]} if deepak else None,
        }
    except OperationalError as e:
        return {"error": str(e)}


@app.get("/health")
def health():
    """Health check endpoint for DigitalOcean App Platform / load balancer probes."""
    from database import engine
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"status": "ok", "db": "connected"}
    except OperationalError:
        return JSONResponse(status_code=503, content={"status": "error", "db": "unavailable"})
