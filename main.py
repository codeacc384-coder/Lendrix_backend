from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from database import Base, engine

from routes.auth import router as auth_router
from routes.angel_vcs import router as angel_vcs_router
from routes.requests import compliance_router, team_router, admin_router, review_router
from routes.team import router as team_policy_router, compliance_router as compliance_policy_router

import models.user
import models.policy

app = FastAPI(title="Lendrix - Process & Policies API")


@app.exception_handler(RuntimeError)
async def runtime_error_handler(request: Request, exc: RuntimeError):
    return JSONResponse(status_code=500, content={"detail": str(exc)})


@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    return JSONResponse(status_code=500, content={"detail": "An unexpected error occurred"})
#  integrartion
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
