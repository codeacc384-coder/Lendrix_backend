import logging
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.policy import LimitationRequest, Policy, PolicyLimitation, PolicyRequest, PolicyReview
from models.user import User
from routes.auth import get_current_user, require_admin_role
from utils_document import generate_and_upload_policy_pdf
from routes.angel_vcs import _get_s3

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def require_compliance_team(current_user: User = Depends(get_current_user)):
    if current_user.role_group != "compliance_team":
        raise HTTPException(status_code=403, detail="Compliance team role required")
    return current_user


def require_team_access(current_user: User = Depends(get_current_user)):
    if current_user.role_group != "team_access":
        raise HTTPException(status_code=403, detail="Team access role required")
    return current_user


compliance_router = APIRouter(prefix="/compliance-team/policy-requests", tags=["Compliance Team - Policy Requests"])
team_router = APIRouter(prefix="/team-access/policy-requests", tags=["Team Access - Policy Requests"])
admin_router = APIRouter(prefix="/angel-vcs/policy-requests", tags=["Angel & VCS - Policy Requests Approval"])
review_router = APIRouter(prefix="/compliance-team/policy-reviews", tags=["Compliance Team - Policy Reviews"])


class PolicyRequestCreate(BaseModel):
    name: str
    category: str
    description: str


class PolicyRequestUpdate(BaseModel):
    policy_id: int
    description: str


class PolicyRequestStatus(BaseModel):
    policy_id: int
    is_active: bool


class LimitationRequestCreate(BaseModel):
    policy_id: int
    title: str
    description: str


class LimitationRequestUpdate(BaseModel):
    limitation_id: int
    description: str


class LimitationRequestDelete(BaseModel):
    limitation_id: int


class ReviewRequest(BaseModel):
    request_id: int
    admin_note: Optional[str] = None


class PolicyReviewCreate(BaseModel):
    policy_id: int
    review: str


class PolicyReviewUpdate(BaseModel):
    review_id: int
    review: str


class PolicyAccept(BaseModel):
    policy_id: int


def _resolve_policy_name(db, policy_id, fallback_name=None):
    if policy_id:
        p = db.query(Policy).filter(Policy.id == policy_id).first()
        if p:
            return p.name
    return fallback_name


def _policy_req_dict(r, db=None):
    requested_by = r.requested_by
    policy_name = r.name  # for action="create", name is on the request itself
    if db:
        user = db.query(User).filter(User.email == r.requested_by).first()
        if user and user.full_name:
            requested_by = user.full_name
        if r.policy_id:
            policy_name = _resolve_policy_name(db, r.policy_id, r.name)
    return {"id": r.id, "action": r.action, "policy_id": r.policy_id, "policy_name": policy_name, "name": r.name, "category": r.category, "description": r.description, "is_active": r.is_active, "requested_by": requested_by, "status": r.status, "admin_note": r.admin_note, "created_at": str(r.created_at), "reviewed_at": str(r.reviewed_at) if r.reviewed_at else None}


def _limit_req_dict(r, db=None):
    policy_name = _resolve_policy_name(db, r.policy_id) if db else None
    return {"id": r.id, "action": r.action, "policy_id": r.policy_id, "policy_name": policy_name, "limitation_id": r.limitation_id, "title": r.title, "description": r.description, "is_enabled": r.is_enabled, "requested_by": r.requested_by, "status": r.status, "admin_note": r.admin_note, "created_at": str(r.created_at), "reviewed_at": str(r.reviewed_at) if r.reviewed_at else None}


def _check_duplicate_policy_request(db, policy_id, action):
    if db.query(PolicyRequest).filter(PolicyRequest.policy_id == policy_id, PolicyRequest.action == action, PolicyRequest.status == "pending").first():
        raise HTTPException(status_code=400, detail=f"A pending {action} request already exists for this policy")


def _check_duplicate_limitation_request(db, limitation_id, action):
    if db.query(LimitationRequest).filter(LimitationRequest.limitation_id == limitation_id, LimitationRequest.action == action, LimitationRequest.status == "pending").first():
        raise HTTPException(status_code=400, detail=f"A pending {action} request already exists for this limitation")


# ── COMPLIANCE TEAM ───────────────────────────────────────────────────────────
@compliance_router.post("/submit")
def compliance_submit_policy(data: PolicyRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(require_compliance_team)):
    if db.query(PolicyRequest).filter(PolicyRequest.name == data.name, PolicyRequest.category == data.category, PolicyRequest.status == "pending").first():
        raise HTTPException(status_code=400, detail="A pending request with the same name and category already exists")
    if db.query(Policy).filter(Policy.name == data.name, Policy.category == data.category).first():
        raise HTTPException(status_code=400, detail="A policy with the same name and category already exists")
    req = PolicyRequest(action="create", name=data.name, category=data.category, description=data.description, requested_by=current_user.email, status="pending")
    db.add(req); db.commit(); db.refresh(req)
    return {"message": "Policy request submitted. Awaiting admin approval.", "request_id": req.id, "policy_id": req.policy_id, "policy_name": req.name, "status": "pending"}


@compliance_router.post("/submit-update")
def compliance_submit_policy_update(data: PolicyRequestUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_compliance_team)):
    policy = db.query(Policy).filter(Policy.id == data.policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    _check_duplicate_policy_request(db, data.policy_id, "update")
    req = PolicyRequest(action="update", policy_id=data.policy_id, description=data.description, requested_by=current_user.email, status="pending")
    db.add(req); db.commit(); db.refresh(req)
    return {"message": "Policy update request submitted. Awaiting admin approval.", "request_id": req.id, "policy_id": req.policy_id, "policy_name": policy.name, "status": "pending"}


@compliance_router.post("/submit-status")
def compliance_submit_policy_status(data: PolicyRequestStatus, db: Session = Depends(get_db), current_user: User = Depends(require_compliance_team)):
    policy = db.query(Policy).filter(Policy.id == data.policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    _check_duplicate_policy_request(db, data.policy_id, "status")
    req = PolicyRequest(action="status", policy_id=data.policy_id, is_active=data.is_active, requested_by=current_user.email, status="pending")
    db.add(req); db.commit(); db.refresh(req)
    return {"message": "Policy status change request submitted. Awaiting admin approval.", "request_id": req.id, "policy_id": req.policy_id, "policy_name": policy.name, "status": "pending"}


@compliance_router.get("/my-requests")
def compliance_my_requests(db: Session = Depends(get_db), current_user: User = Depends(require_compliance_team)):
    return [_policy_req_dict(r, db) for r in db.query(PolicyRequest).filter(PolicyRequest.requested_by == current_user.email).all()]


@compliance_router.get("/my-policies")
def compliance_my_policies(db: Session = Depends(get_db), current_user: User = Depends(require_compliance_team)):
    approved_requests = db.query(PolicyRequest).filter(PolicyRequest.requested_by == current_user.email, PolicyRequest.action == "create", PolicyRequest.status == "approved").all()
    result = []
    for req in approved_requests:
        policy = db.query(Policy).filter(Policy.name == req.name, Policy.category == req.category).first()
        result.append({"request_id": req.id, "name": req.name, "category": req.category, "description": req.description, "request_status": req.status, "admin_note": req.admin_note, "policy_id": policy.id if policy else None, "is_active": policy.is_active if policy else None, "is_accepted": policy.is_accepted if policy else None, "submitted_at": str(req.created_at), "reviewed_at": str(req.reviewed_at) if req.reviewed_at else None})
    return result


@compliance_router.post("/limitations/submit-create")
def compliance_submit_limitation_create(data: LimitationRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(require_compliance_team)):
    policy = db.query(Policy).filter(Policy.id == data.policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    req = LimitationRequest(action="create", policy_id=data.policy_id, title=data.title, description=data.description, requested_by=current_user.email, status="pending")
    db.add(req); db.commit(); db.refresh(req)
    return {"message": "Limitation create request submitted. Awaiting admin approval.", "request_id": req.id, "policy_id": req.policy_id, "policy_name": policy.name, "status": "pending"}


@compliance_router.post("/limitations/submit-update")
def compliance_submit_limitation_update(data: LimitationRequestUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_compliance_team)):
    limitation = db.query(PolicyLimitation).filter(PolicyLimitation.id == data.limitation_id).first()
    if not limitation:
        raise HTTPException(status_code=404, detail="Limitation not found")
    _check_duplicate_limitation_request(db, data.limitation_id, "update")
    policy = db.query(Policy).filter(Policy.id == limitation.policy_id).first()
    req = LimitationRequest(action="update", limitation_id=data.limitation_id, description=data.description, requested_by=current_user.email, status="pending")
    db.add(req); db.commit(); db.refresh(req)
    return {"message": "Limitation update request submitted. Awaiting admin approval.", "request_id": req.id, "policy_id": policy.id, "policy_name": policy.name, "status": "pending"}


@compliance_router.post("/limitations/submit-delete")
def compliance_submit_limitation_delete(data: LimitationRequestDelete, db: Session = Depends(get_db), current_user: User = Depends(require_compliance_team)):
    limitation = db.query(PolicyLimitation).filter(PolicyLimitation.id == data.limitation_id).first()
    if not limitation:
        raise HTTPException(status_code=404, detail="Limitation not found")
    _check_duplicate_limitation_request(db, data.limitation_id, "delete")
    policy = db.query(Policy).filter(Policy.id == limitation.policy_id).first()
    req = LimitationRequest(action="delete", limitation_id=data.limitation_id, requested_by=current_user.email, status="pending")
    db.add(req); db.commit(); db.refresh(req)
    return {"message": "Limitation delete request submitted. Awaiting admin approval.", "request_id": req.id, "policy_id": policy.id, "policy_name": policy.name, "status": "pending"}


@compliance_router.get("/limitations/my-requests")
def compliance_my_limitation_requests(db: Session = Depends(get_db), current_user: User = Depends(require_compliance_team)):
    return [_limit_req_dict(r, db) for r in db.query(LimitationRequest).filter(LimitationRequest.requested_by == current_user.email).all()]


# ── TEAM ACCESS ───────────────────────────────────────────────────────────────
@team_router.post("/submit")
def team_submit_policy(data: PolicyRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(require_team_access)):
    if db.query(PolicyRequest).filter(PolicyRequest.name == data.name, PolicyRequest.category == data.category, PolicyRequest.status == "pending").first():
        raise HTTPException(status_code=400, detail="A pending request with the same name and category already exists")
    if db.query(Policy).filter(Policy.name == data.name, Policy.category == data.category).first():
        raise HTTPException(status_code=400, detail="A policy with the same name and category already exists")
    req = PolicyRequest(action="create", name=data.name, category=data.category, description=data.description, requested_by=current_user.email, status="pending")
    db.add(req); db.commit(); db.refresh(req)
    return {"message": "Policy request submitted. Awaiting admin approval.", "request_id": req.id, "policy_id": req.policy_id, "status": "pending"}


@team_router.post("/submit-update")
def team_submit_policy_update(data: PolicyRequestUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_team_access)):
    if not db.query(Policy).filter(Policy.id == data.policy_id).first():
        raise HTTPException(status_code=404, detail="Policy not found")
    _check_duplicate_policy_request(db, data.policy_id, "update")

    req = PolicyRequest(action="update", policy_id=data.policy_id, description=data.description, requested_by=current_user.email, status="pending")
    db.add(req); db.commit(); db.refresh(req)
    return {"message": "Policy update request submitted. Awaiting admin approval.", "request_id": req.id, "policy_id": req.policy_id, "status": "pending"}


@team_router.post("/submit-status")
def team_submit_policy_status(data: PolicyRequestStatus, db: Session = Depends(get_db), current_user: User = Depends(require_team_access)):
    if not db.query(Policy).filter(Policy.id == data.policy_id).first():
        raise HTTPException(status_code=404, detail="Policy not found")
    _check_duplicate_policy_request(db, data.policy_id, "status")

    req = PolicyRequest(action="status", policy_id=data.policy_id, is_active=data.is_active, requested_by=current_user.email, status="pending")
    db.add(req); db.commit(); db.refresh(req)
    return {"message": "Policy status change request submitted. Awaiting admin approval.", "request_id": req.id, "policy_id": req.policy_id, "status": "pending"}


@team_router.get("/my-requests")
def team_my_requests(db: Session = Depends(get_db), current_user: User = Depends(require_team_access)):
    return [_policy_req_dict(r, db) for r in db.query(PolicyRequest).filter(PolicyRequest.requested_by == current_user.email).all()]


@team_router.post("/limitations/submit-create")
def team_submit_limitation_create(data: LimitationRequestCreate, db: Session = Depends(get_db), current_user: User = Depends(require_team_access)):
    if not db.query(Policy).filter(Policy.id == data.policy_id).first():
        raise HTTPException(status_code=404, detail="Policy not found")
    req = LimitationRequest(action="create", policy_id=data.policy_id, title=data.title, description=data.description, requested_by=current_user.email, status="pending")
    db.add(req); db.commit(); db.refresh(req)
    return {"message": "Limitation create request submitted. Awaiting admin approval.", "request_id": req.id, "policy_id": req.policy_id, "status": "pending"}


@team_router.post("/limitations/submit-update")
def team_submit_limitation_update(data: LimitationRequestUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_team_access)):
    if not db.query(PolicyLimitation).filter(PolicyLimitation.id == data.limitation_id).first():
        raise HTTPException(status_code=404, detail="Limitation not found")
    _check_duplicate_limitation_request(db, data.limitation_id, "update")

    req = LimitationRequest(action="update", limitation_id=data.limitation_id, description=data.description, requested_by=current_user.email, status="pending")
    db.add(req); db.commit(); db.refresh(req)
    return {"message": "Limitation update request submitted. Awaiting admin approval.", "request_id": req.id, "policy_id": req.policy_id, "status": "pending"}


@team_router.post("/limitations/submit-delete")
def team_submit_limitation_delete(data: LimitationRequestDelete, db: Session = Depends(get_db), current_user: User = Depends(require_team_access)):
    if not db.query(PolicyLimitation).filter(PolicyLimitation.id == data.limitation_id).first():
        raise HTTPException(status_code=404, detail="Limitation not found")
    _check_duplicate_limitation_request(db, data.limitation_id, "delete")

    req = LimitationRequest(action="delete", limitation_id=data.limitation_id, requested_by=current_user.email, status="pending")
    db.add(req); db.commit(); db.refresh(req)
    return {"message": "Limitation delete request submitted. Awaiting admin approval.", "request_id": req.id, "policy_id": req.policy_id, "status": "pending"}


@team_router.get("/limitations/my-requests")
def team_my_limitation_requests(db: Session = Depends(get_db), current_user: User = Depends(require_team_access)):
    return [_limit_req_dict(r, db) for r in db.query(LimitationRequest).filter(LimitationRequest.requested_by == current_user.email).all()]


# ── ADMIN ─────────────────────────────────────────────────────────────────────
@admin_router.get("/")
def list_policy_requests(status: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    query = db.query(PolicyRequest)
    if status:
        query = query.filter(PolicyRequest.status == status)
    return [_policy_req_dict(r, db) for r in query.order_by(PolicyRequest.created_at.desc()).all()]


@admin_router.put("/approve")
def approve_policy_request(data: ReviewRequest, db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    req = db.query(PolicyRequest).filter(PolicyRequest.id == data.request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Policy request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {req.status}")

    if req.action == "create":
        if db.query(Policy).filter(Policy.name == req.name, Policy.category == req.category).first():
            raise HTTPException(status_code=400, detail="A policy with the same name and category already exists")
        from_compliance = db.query(User).filter(User.email == req.requested_by, User.role_group == "compliance_team").first()
        submitted_by_role = "compliance_team" if from_compliance else "team_access"
        is_accepted = not bool(from_compliance)
        document_url, document_key = generate_and_upload_policy_pdf(name=req.name, category=req.category or "", description=req.description or "", limitations=[])
        new_policy = Policy(name=req.name, category=req.category, description=req.description, document_url=document_url, document_key=document_key, is_active=True, submitted_by_role=submitted_by_role, is_accepted=is_accepted)
        db.add(new_policy); db.flush()
        msg = "Policy created. Awaiting Angel/VCS acceptance." if not is_accepted else "Policy created and visible to all."
        result = {"message": msg, "policy_id": new_policy.id, "document_url": document_url}

    elif req.action == "update":
        policy = db.query(Policy).filter(Policy.id == req.policy_id).first()
        if not policy:
            raise HTTPException(status_code=404, detail="Policy no longer exists")
        if req.name is not None: policy.name = req.name
        if req.category is not None: policy.category = req.category
        if req.description is not None: policy.description = req.description
        limitations = [{"title": l.title, "description": l.description, "is_enabled": l.is_enabled} for l in db.query(PolicyLimitation).filter(PolicyLimitation.policy_id == policy.id).all()]
        document_url, document_key = generate_and_upload_policy_pdf(name=policy.name, category=policy.category or "", description=policy.description or "", limitations=limitations, existing_key=policy.document_key)
        policy.document_url = document_url; policy.document_key = document_key
        result = {"message": "Policy updated.", "policy_id": policy.id, "document_url": document_url}

    elif req.action == "status":
        policy = db.query(Policy).filter(Policy.id == req.policy_id).first()
        if not policy:
            raise HTTPException(status_code=404, detail="Policy no longer exists")
        policy.is_active = req.is_active
        result = {"message": f"Policy status changed to {'active' if req.is_active else 'inactive'}.", "policy_id": policy.id}
    else:
        raise HTTPException(status_code=400, detail="Unknown action type")

    req.status = "approved"; req.admin_note = data.admin_note; req.reviewed_at = _utcnow()
    db.commit()
    return result


@admin_router.put("/reject")
def reject_policy_request(data: ReviewRequest, db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    req = db.query(PolicyRequest).filter(PolicyRequest.id == data.request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Policy request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {req.status}")
    req.status = "rejected"; req.admin_note = data.admin_note; req.reviewed_at = _utcnow()
    db.commit()
    return {"message": "Policy request rejected", "request_id": req.id, "policy_id": req.policy_id, "policy_name": _resolve_policy_name(db, req.policy_id, req.name)}


@admin_router.get("/limitations")
def list_limitation_requests(status: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    query = db.query(LimitationRequest)
    if status:
        query = query.filter(LimitationRequest.status == status)
    return [_limit_req_dict(r, db) for r in query.order_by(LimitationRequest.created_at.desc()).all()]


@admin_router.put("/limitations/approve")
def approve_limitation_request(data: ReviewRequest, db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    req = db.query(LimitationRequest).filter(LimitationRequest.id == data.request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Limitation request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {req.status}")
    if req.action == "create":
        new_limit = PolicyLimitation(policy_id=req.policy_id, title=req.title, description=req.description, is_enabled=req.is_enabled if req.is_enabled is not None else True)
        db.add(new_limit); db.flush()
        req.limitation_id = new_limit.id
        result = {"message": "Limitation created", "limitation_id": new_limit.id}
    elif req.action == "update":
        limit = db.query(PolicyLimitation).filter(PolicyLimitation.id == req.limitation_id).first()
        if not limit:
            raise HTTPException(status_code=404, detail="Limitation no longer exists")
        if req.title is not None: limit.title = req.title
        if req.description is not None: limit.description = req.description
        if req.is_enabled is not None: limit.is_enabled = req.is_enabled
        result = {"message": "Limitation updated"}
    elif req.action == "delete":
        limit = db.query(PolicyLimitation).filter(PolicyLimitation.id == req.limitation_id).first()
        if not limit:
            raise HTTPException(status_code=404, detail="Limitation no longer exists")
        db.delete(limit)
        result = {"message": "Limitation deleted"}
    else:
        raise HTTPException(status_code=400, detail="Unknown action type")
    req.status = "approved"; req.admin_note = data.admin_note; req.reviewed_at = _utcnow()
    db.commit()
    return result


@admin_router.put("/limitations/reject")
def reject_limitation_request(data: ReviewRequest, db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    req = db.query(LimitationRequest).filter(LimitationRequest.id == data.request_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Limitation request not found")
    if req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Request is already {req.status}")
    req.status = "rejected"; req.admin_note = data.admin_note; req.reviewed_at = _utcnow()
    db.commit()
    return {"message": "Limitation request rejected", "request_id": req.id, "policy_id": req.policy_id, "policy_name": _resolve_policy_name(db, req.policy_id)}


@admin_router.get("/policies/pending-acceptance")
def pending_acceptance_policies(db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    policies = db.query(Policy).filter(Policy.submitted_by_role == "compliance_team", Policy.is_accepted == False).all()
    return [{"id": p.id, "name": p.name, "category": p.category, "description": p.description, "is_active": p.is_active, "document_url": p.document_url} for p in policies]


@admin_router.get("/policies/pending-acceptance/view/{policy_id}")
def view_pending_acceptance_document(policy_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    policy = db.query(Policy).filter(Policy.id == policy_id, Policy.submitted_by_role == "compliance_team", Policy.is_accepted == False).first()
    if not policy or not policy.document_key:
        raise HTTPException(status_code=404, detail="Policy document not found")
    try:
        s3 = _get_s3()
        bucket = os.getenv("BUCKET_NAME", "documents")
        presigned_url = s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": policy.document_key, "ResponseContentDisposition": "inline", "ResponseContentType": "application/pdf"}, ExpiresIn=600)
    except Exception as e:
        logger.error(f"Failed to generate presigned URL for policy {policy_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to generate document URL")
    return {"view_url": presigned_url, "expires_in_seconds": 600}


@admin_router.get("/my-policies")
def angel_vcs_my_policies(db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    policies = db.query(Policy).filter(Policy.submitted_by_role == "admin").all()
    return [{"id": p.id, "name": p.name, "category": p.category, "description": p.description, "is_active": p.is_active, "is_accepted": p.is_accepted} for p in policies]


@admin_router.put("/policies/accept")
def accept_policy(data: PolicyAccept, db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    policy = db.query(Policy).filter(Policy.id == data.policy_id, Policy.submitted_by_role == "compliance_team", Policy.is_accepted == False).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found or already accepted")
    policy.is_accepted = True
    db.commit()
    return {"message": "Policy accepted and is now visible to all.", "policy_id": policy.id}


@admin_router.get("/policy-reviews")
def get_all_reviews(policy_id: Optional[int] = None, status: Optional[str] = None, db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    query = db.query(PolicyReview)
    if policy_id:
        query = query.filter(PolicyReview.policy_id == policy_id)
    if status:
        query = query.filter(PolicyReview.status == status)
    return [{"id": r.id, "policy_id": r.policy_id, "reviewed_by": r.reviewed_by, "review": r.review, "status": r.status, "created_at": str(r.created_at)} for r in query.order_by(PolicyReview.created_at.desc()).all()]


@admin_router.put("/policy-reviews/resolve")
def resolve_review(review_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    rev = db.query(PolicyReview).filter(PolicyReview.id == review_id).first()
    if not rev:
        raise HTTPException(status_code=404, detail="Review not found")
    rev.status = "resolved"
    db.commit()
    return {"message": "Review marked as resolved.", "review_id": rev.id, "policy_id": rev.policy_id, "policy_name": _resolve_policy_name(db, rev.policy_id)}



# ── COMPLIANCE TEAM REVIEWS ───────────────────────────────────────────────────
@review_router.post("/submit")
def submit_review(data: PolicyReviewCreate, db: Session = Depends(get_db), current_user: User = Depends(require_compliance_team)):
    policy = db.query(Policy).filter(Policy.id == data.policy_id).first()
    if not policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    rev = PolicyReview(policy_id=data.policy_id, reviewed_by=current_user.email, review=data.review, status="open")
    db.add(rev); db.commit(); db.refresh(rev)
    return {"message": "Review submitted successfully.", "review_id": rev.id, "policy_id": rev.policy_id, "policy_name": policy.name, "status": "open"}


@review_router.get("/my-reviews")
def my_reviews(db: Session = Depends(get_db), current_user: User = Depends(require_compliance_team)):
    reviews = db.query(PolicyReview).filter(PolicyReview.reviewed_by == current_user.email).all()
    return [{"id": r.id, "policy_id": r.policy_id, "policy_name": _resolve_policy_name(db, r.policy_id), "review": r.review, "status": r.status, "created_at": str(r.created_at)} for r in reviews]


@review_router.put("/update")
def update_review(data: PolicyReviewUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_compliance_team)):
    rev = db.query(PolicyReview).filter(PolicyReview.id == data.review_id, PolicyReview.reviewed_by == current_user.email).first()
    if not rev:
        raise HTTPException(status_code=404, detail="Review not found or not yours")
    rev.review = data.review
    db.commit()
    policy_name = _resolve_policy_name(db, rev.policy_id)
    return {"message": "Review updated successfully.", "policy_id": rev.policy_id, "policy_name": policy_name}


@review_router.delete("/delete/{review_id}")
def delete_review(review_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_compliance_team)):
    rev = db.query(PolicyReview).filter(PolicyReview.id == review_id, PolicyReview.reviewed_by == current_user.email).first()
    if not rev:
        raise HTTPException(status_code=404, detail="Review not found or not yours")
    db.delete(rev); db.commit()
    return {"message": "Review deleted successfully."}
