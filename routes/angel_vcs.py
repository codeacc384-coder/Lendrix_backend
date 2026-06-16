from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from pydantic import BaseModel
from database import get_db
from models.policy import Policy, PolicyLimitation
from models.user import User
from routes.auth import require_admin_role
from utils_document import generate_and_upload_policy_pdf
import boto3
import os
from dotenv import load_dotenv

load_dotenv()


def _get_s3():
    endpoint = os.getenv("UTHO_ENDPOINT_URL", "").rstrip("/")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=os.getenv("UTHO_ACCESS_KEY"),
        aws_secret_access_key=os.getenv("UTHO_SECRET_KEY"),
        config=boto3.session.Config(signature_version="s3v4")
    )


router = APIRouter(prefix="/angel-vcs/policies", tags=["Angel & VCS - Policy Management"])


class PolicyCreate(BaseModel):
    name: str
    category: str
    description: str


class PolicyUpdate(BaseModel):
    policy_id: int
    name: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None


class PolicyDelete(BaseModel):
    policy_id: Optional[int] = None


class LimitationCreate(BaseModel):
    policy_id: int
    title: str
    description: str
    is_enabled: Optional[bool] = True


class LimitationUpdate(BaseModel):
    limitation_id: int
    title: Optional[str] = None
    description: Optional[str] = None
    is_enabled: Optional[bool] = None


class LimitationDelete(BaseModel):
    limitation_id: int


def _policy_dict(p):
    return {"id": p.id, "name": p.name, "category": p.category, "description": p.description, "document_url": p.document_url, "is_active": p.is_active}


def _limitation_dict(l):
    return {"id": l.id, "policy_id": l.policy_id, "title": l.title, "description": l.description, "is_enabled": l.is_enabled}


@router.get("/stats")
def get_stats(db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    return {
        "active_policies": db.query(Policy).filter(Policy.is_active == True, Policy.is_accepted == True).count(),
        "total_policies": db.query(Policy).filter(Policy.is_accepted == True).count(),
        "processes": 0
    }


@router.get("/")
def list_policies(db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    return [_policy_dict(p) for p in db.query(Policy).filter(Policy.is_accepted == True).all()]


@router.get("/view/{policy_id}")
def view_policy_document(policy_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    policy = db.query(Policy).filter(Policy.id == policy_id).first()
    if not policy or not policy.document_key:
        raise HTTPException(status_code=404, detail="Policy document not found")
    s3 = _get_s3()
    bucket = os.getenv("BUCKET_NAME", "documents")
    presigned_url = s3.generate_presigned_url("get_object", Params={"Bucket": bucket, "Key": policy.document_key, "ResponseContentDisposition": "inline", "ResponseContentType": "application/pdf"}, ExpiresIn=600)
    return {"view_url": presigned_url, "expires_in_seconds": 600}


@router.post("/save")
def save_policy(data: PolicyCreate, db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    if db.query(Policy).filter(Policy.name == data.name, Policy.category == data.category).first():
        raise HTTPException(status_code=400, detail="A policy with the same name and category already exists")
    document_url, document_key = generate_and_upload_policy_pdf(name=data.name, category=data.category, description=data.description, limitations=[])
    new_policy = Policy(name=data.name, category=data.category, description=data.description, document_url=document_url, document_key=document_key, is_active=True)
    db.add(new_policy)
    db.commit()
    db.refresh(new_policy)
    return {"status": "success", "message": "Policy created", "policy_id": new_policy.id, "document_url": document_url}


@router.put("/update")
def update_policy(data: PolicyUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    db_policy = db.query(Policy).filter(Policy.id == data.policy_id).first()
    if not db_policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if data.name is not None: db_policy.name = data.name
    if data.category is not None: db_policy.category = data.category
    if data.description is not None: db_policy.description = data.description
    if data.is_active is not None: db_policy.is_active = data.is_active
    limitations = [{"title": l.title, "description": l.description, "is_enabled": l.is_enabled} for l in db.query(PolicyLimitation).filter(PolicyLimitation.policy_id == db_policy.id).all()]
    document_url, document_key = generate_and_upload_policy_pdf(name=db_policy.name, category=db_policy.category or "", description=db_policy.description or "", limitations=limitations, existing_key=db_policy.document_key)
    db_policy.document_url = document_url
    db_policy.document_key = document_key
    db.commit()
    return {"message": "Policy updated successfully", "policy_id": db_policy.id, "document_url": document_url}


@router.delete("/delete")
def delete_policy(data: PolicyDelete, db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    db_policy = db.query(Policy).filter(Policy.id == data.policy_id).first()
    if not db_policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    if db_policy.document_key:
        try:
            s3 = _get_s3()
            s3.delete_object(Bucket=os.getenv("BUCKET_NAME", "documents"), Key=db_policy.document_key)
        except Exception as e:
            print(f"Warning: could not delete document from bucket: {e}")
    db.delete(db_policy)
    db.commit()
    return {"message": "Policy deleted successfully"}


@router.get("/limitations")
def get_limitations(db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    return [_limitation_dict(l) for l in db.query(PolicyLimitation).all()]


@router.get("/limitations/{policy_id}")
def get_limitations_by_policy(policy_id: int, db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    return [_limitation_dict(l) for l in db.query(PolicyLimitation).filter(PolicyLimitation.policy_id == policy_id).all()]


@router.post("/limitations/save")
def save_limitation(data: LimitationCreate, db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    db_policy = db.query(Policy).filter(Policy.id == data.policy_id).first()
    if not db_policy:
        raise HTTPException(status_code=404, detail="Policy not found")
    new_limit = PolicyLimitation(policy_id=data.policy_id, title=data.title, description=data.description, is_enabled=data.is_enabled)
    db.add(new_limit)
    db.flush()
    limitations = [{"title": l.title, "description": l.description, "is_enabled": l.is_enabled} for l in db.query(PolicyLimitation).filter(PolicyLimitation.policy_id == data.policy_id).all()]
    document_url, document_key = generate_and_upload_policy_pdf(name=db_policy.name, category=db_policy.category or "", description=db_policy.description or "", limitations=limitations, existing_key=db_policy.document_key)
    db_policy.document_url = document_url
    db_policy.document_key = document_key
    db.commit()
    return {"message": "Limitation Saved", "id": new_limit.id, "document_url": document_url}


@router.put("/limitations/update")
def update_limitation(data: LimitationUpdate, db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    limit = db.query(PolicyLimitation).filter(PolicyLimitation.id == data.limitation_id).first()
    if not limit:
        raise HTTPException(status_code=404, detail="Limitation not found")
    if data.title is not None: limit.title = data.title
    if data.description is not None: limit.description = data.description
    if data.is_enabled is not None: limit.is_enabled = data.is_enabled
    db.flush()
    db_policy = db.query(Policy).filter(Policy.id == limit.policy_id).first()
    limitations = [{"title": l.title, "description": l.description, "is_enabled": l.is_enabled} for l in db.query(PolicyLimitation).filter(PolicyLimitation.policy_id == limit.policy_id).all()]
    document_url, document_key = generate_and_upload_policy_pdf(name=db_policy.name, category=db_policy.category or "", description=db_policy.description or "", limitations=limitations, existing_key=db_policy.document_key)
    db_policy.document_url = document_url
    db_policy.document_key = document_key
    db.commit()
    return {"message": "Limitation updated successfully", "policy_id": limit.policy_id, "document_url": document_url}


@router.delete("/limitations/delete")
def delete_limitation(data: LimitationDelete, db: Session = Depends(get_db), current_user: User = Depends(require_admin_role)):
    limit = db.query(PolicyLimitation).filter(PolicyLimitation.id == data.limitation_id).first()
    if not limit:
        raise HTTPException(status_code=404, detail="Limitation not found")
    policy_id = limit.policy_id
    db.delete(limit)
    db.flush()
    db_policy = db.query(Policy).filter(Policy.id == policy_id).first()
    limitations = [{"title": l.title, "description": l.description, "is_enabled": l.is_enabled} for l in db.query(PolicyLimitation).filter(PolicyLimitation.policy_id == policy_id).all()]
    document_url, document_key = generate_and_upload_policy_pdf(name=db_policy.name, category=db_policy.category or "", description=db_policy.description or "", limitations=limitations, existing_key=db_policy.document_key)
    db_policy.document_url = document_url
    db_policy.document_key = document_key
    db.commit()
    return {"message": "Limitation deleted successfully", "document_url": document_url}
