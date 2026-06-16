import logging
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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Lendrix - Process & Policies API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def startup():
    check_db_connection()


@app.exception_handler(OperationalError)
async def db_operational_error_handler(request: Request, exc: OperationalError):
    logger.error(f"DB OperationalError on {request.url}: {exc}")
    return JSONResponse(status_code=503, content={"detail": "Database unavailable. Please try again."})


@app.exception_handler(SQLAlchemyError)
async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    logger.error(f"SQLAlchemyError on {request.url}: {exc}")
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
