import logging
import os


from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from database import get_db
from models.policy import Policy, PolicyLimitation
from models.user import User
from routes.auth import get_current_user
from utils_document import get_s3_client



logger = logging.getLogger(__name__)

router = APIRouter(prefix="/team-access/policies", tags=["Team Access - Policy View"])
compliance_router = APIRouter(prefix="/compliance-team/policies", tags=["Compliance Team - Policy View"])


def _get_s3():
    return get_s3_client()


def require_team_access(current_user: User = Depends(get_current_user)):
    if current_user.role_group != "team_access":
        raise HTTPException(status_code=403, detail="Team access role required")
    return current_user


def require_compliance_team(current_user: User = Depends(get_current_user)):
    if current_user.role_group != "compliance_team":
        raise HTTPException(status_code=403, detail="Compliance team role required")
    return current_user


def _policy_dict(p):
    return {"id": p.id, "name": p.name, "category": p.category, "description": p.description, "is_active": p.is_active, "document_url": p.document_url}


def _limitation_dict(l):
    return {"id": l.id, "policy_id": l.policy_id, "title": l.title, "description": l.description, "is_enabled": l.is_enabled}


@router.get("/stats")
def get_stats(db: Session = Depends(get_db), current_user: User = Depends(require_team_access)):
    return {
        "active_policies": db.query(Policy).filter(Policy.is_active == True, Policy.is_accepted == True).count(),
        "total_policies": db.query(Policy).filter(Policy.is_accepted == True).count(),
        "processes": 0,
    }


@router.get("/")
def list_policies(db: Session = Depends(get_db), current_user: User = Depends(require_team_access)):
    return [_policy_dict(p) for p in db.query(Policy).filter(Policy.is_accepted == True).all()]


@router.get("/limitations")
def get_limitations(db: Session = Depends(get_db), current_user: User = Depends(require_team_access)):
    return [
        _limitation_dict(l)
        for l in db.query(PolicyLimitation)
        .join(Policy, PolicyLimitation.policy_id == Policy.id)
        .filter(Policy.is_accepted == True)
        .all()
    ]


@router.get("/limitations/{policy_id}")
def get_limitations_by_policy(policy_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_team_access)):
    policy = db.query(Policy).filter(Policy.id == policy_id, Policy.is_accepted == True).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found or not approved")
    return [_limitation_dict(l) for l in db.query(PolicyLimitation).filter(PolicyLimitation.policy_id == policy_id).all()]


@router.get("/view/{policy_id}")
def team_view_policy_document(policy_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_team_access)):
    policy = db.query(Policy).filter(Policy.id == policy_id, Policy.is_accepted == True).first()
    if not policy or not policy.document_key:
        raise HTTPException(status_code=404, detail="Policy document not found")
    try:
        s3 = _get_s3()
        bucket = os.getenv("BUCKET_NAME", "documents")
        presigned_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": policy.document_key, "ResponseContentDisposition": "inline", "ResponseContentType": "application/pdf"},
            ExpiresIn=600,
        )
    except Exception as e:
        logger.error(f"Failed to generate presigned URL for policy {policy_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate document URL")
    return {"view_url": presigned_url, "expires_in_seconds": 600}


@compliance_router.get("/")
def compliance_list_policies(db: Session = Depends(get_db), current_user: User = Depends(require_compliance_team)):
    return [_policy_dict(p) for p in db.query(Policy).filter(Policy.is_accepted == True).all()]


@compliance_router.get("/limitations/{policy_id}")
def compliance_get_limitations(policy_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_compliance_team)):
    return [_limitation_dict(l) for l in db.query(PolicyLimitation).filter(PolicyLimitation.policy_id == policy_id).all()]


@compliance_router.get("/view/{policy_id}")
def compliance_view_policy_document(policy_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_compliance_team)):
    policy = db.query(Policy).filter(Policy.id == policy_id, Policy.is_accepted == True).first()
    if not policy or not policy.document_key:
        raise HTTPException(status_code=404, detail="Policy document not found")
    try:
        s3 = _get_s3()
        bucket = os.getenv("BUCKET_NAME", "documents")
        presigned_url = s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": policy.document_key, "ResponseContentDisposition": "inline", "ResponseContentType": "application/pdf"},
            ExpiresIn=600,
        )
    except Exception as e:
        logger.error(f"Failed to generate presigned URL for policy {policy_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate document URL")
    return {"view_url": presigned_url, "expires_in_seconds": 600}
