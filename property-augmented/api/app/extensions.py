from __future__ import annotations

import hashlib
import json
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from fastapi import Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from . import full_stack as stack
from . import main as core
from .bootstrap import SITE_URL, _brevo_send

app = stack.app
ENV = os.getenv("ENV", "development").lower()


class PasswordReset(stack.Base):
    __tablename__ = "pda_password_resets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("pda_users.id"), index=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    used: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))


stack.Base.metadata.create_all(stack.engine)


PROTECTED_PREFIXES = (
    "/api/v1/ai/",
    "/api/v1/research/",
    "/api/v1/planning/",
    "/api/v1/procurement/",
    "/api/v1/quotes/",
    "/api/v1/documents/",
    "/api/v1/reports/",
    "/api/v1/seo/strategy",
    "/api/v1/seo/keywords",
    "/api/v1/seo/measured-keywords",
    "/api/v1/seo/search-console",
)


@app.middleware("http")
async def paid_compute_auth_guard(request: Request, call_next):
    """Protect endpoints that can create AI/provider cost or handle private uploaded project material."""
    if ENV == "production" and request.url.path.startswith(PROTECTED_PREFIXES):
        auth = request.headers.get("authorization", "")
        if not auth.lower().startswith("bearer "):
            return JSONResponse({"detail": "Authentication required"}, status_code=401)
        try:
            stack.decode(auth.split(" ", 1)[1])
        except HTTPException:
            return JSONResponse({"detail": "Invalid or expired token"}, status_code=401)
    response = await call_next(request)
    response.headers.setdefault("Cache-Control", "no-store" if request.url.path.startswith("/api/v1/auth/") else "no-cache")
    return response


class FullSiteRequest(core.SiteRequest):
    pass


@app.post("/api/v1/site/intelligence/full")
async def full_site_intelligence(r: FullSiteRequest):
    result = await core.site(r)
    extras: dict[str, Any] = {}
    if r.company_query:
        if core.COMPANIES_HOUSE_API_KEY:
            url = "https://api.company-information.service.gov.uk/search/companies"
            try:
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get(url, params={"q": r.company_query, "items_per_page": 25}, auth=(core.COMPANIES_HOUSE_API_KEY, ""))
                    response.raise_for_status()
                extras["companies_house"] = {"items": response.json().get("items", []), "source": core.src("Companies House API", url, "Verify company identity, filing status and charges in the authoritative record.")}
            except Exception as exc:
                extras["companies_house"] = {"items": [], "error": str(exc), "source": core.src("Companies House API", url, "Provider request failed; do not infer company status.")}
        else:
            extras["companies_house"] = {"configured": False, "items": [], "note": "Companies House API key not configured."}
    if r.include_epc:
        extras["epc"] = {"configured": bool(core.EPC_API_URL), "source": core.src("Energy Performance of Buildings Data", "https://get-energy-performance-data.communities.gov.uk/", "Current England and Wales service requires authorised API access. EPC data is not inferred when the adapter is not configured.")}
        if core.EPC_API_URL:
            try:
                headers = {"Authorization": f"Bearer {core.EPC_API_TOKEN}"} if core.EPC_API_TOKEN else {}
                async with httpx.AsyncClient(timeout=30) as client:
                    response = await client.get(core.EPC_API_URL, params={"postcode": core.pc(r.postcode)}, headers=headers)
                    response.raise_for_status()
                extras["epc"]["data"] = response.json()
            except Exception as exc:
                extras["epc"]["error"] = str(exc)
    result["optional_sources"] = extras
    return result


class RegisterPatch(BaseModel):
    title: str | None = None
    status: str | None = None
    data: dict[str, Any] | None = None


@app.patch("/api/v1/projects/{project_id}/registers/{register_id}")
def register_update(project_id: int, register_id: int, r: RegisterPatch, user: stack.User = Depends(stack.me), s: Session = Depends(stack.db)):
    item = s.get(stack.Register, register_id)
    if not item or item.project_id != project_id or item.user_id != user.id:
        raise HTTPException(404, "Register item not found")
    new_data = r.data if r.data is not None else json.loads(item.data_json or "{}")
    new_status = r.status if r.status is not None else item.status
    if item.kind.lower() == "variation" and str(new_status).lower() == "approved":
        evidence = new_data.get("approval_evidence") or new_data.get("approval") or (new_data.get("approved_by") and new_data.get("approved_at"))
        if not evidence:
            raise HTTPException(422, "Variation cannot be marked approved without explicit approval evidence")
    if r.title is not None:
        item.title = r.title
    if r.status is not None:
        item.status = r.status
    if r.data is not None:
        item.data_json = json.dumps(r.data)
    item.updated_at = datetime.now(timezone.utc)
    s.add(item); s.commit(); s.refresh(item)
    return {"id": item.id, "kind": item.kind, "title": item.title, "status": item.status, "data": json.loads(item.data_json or "{}"), "updated_at": item.updated_at}


@app.delete("/api/v1/projects/{project_id}/registers/{register_id}")
def register_delete(project_id: int, register_id: int, user: stack.User = Depends(stack.me), s: Session = Depends(stack.db)):
    item = s.get(stack.Register, register_id)
    if not item or item.project_id != project_id or item.user_id != user.id:
        raise HTTPException(404, "Register item not found")
    s.delete(item); s.commit(); return {"deleted": True, "id": register_id}


class ProjectPatch(BaseModel):
    name: str | None = None
    address: str | None = None
    postcode: str | None = None
    strategy: str | None = None
    metadata: dict[str, Any] | None = None


@app.patch("/api/v1/projects/{project_id}")
def project_update(project_id: int, r: ProjectPatch, user: stack.User = Depends(stack.me), s: Session = Depends(stack.db)):
    project = s.get(stack.Project, project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(404, "Project not found")
    if r.name is not None: project.name = r.name
    if r.address is not None: project.address = r.address
    if r.postcode is not None: project.postcode = r.postcode.upper()
    if r.strategy is not None: project.strategy = r.strategy
    if r.metadata is not None: project.metadata_json = json.dumps(r.metadata)
    project.updated_at = datetime.now(timezone.utc)
    s.add(project); s.commit(); s.refresh(project)
    return {"id": project.id, "name": project.name, "address": project.address, "postcode": project.postcode, "strategy": project.strategy, "metadata": json.loads(project.metadata_json or "{}")}


@app.delete("/api/v1/projects/{project_id}")
def project_delete(project_id: int, user: stack.User = Depends(stack.me), s: Session = Depends(stack.db)):
    project = s.get(stack.Project, project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(404, "Project not found")
    regs = s.query(stack.Register).filter(stack.Register.project_id == project_id, stack.Register.user_id == user.id).all()
    for item in regs: s.delete(item)
    s.delete(project); s.commit(); return {"deleted": True, "id": project_id}


@app.get("/api/v1/projects/{project_id}/summary")
def project_summary(project_id: int, user: stack.User = Depends(stack.me), s: Session = Depends(stack.db)):
    project = s.get(stack.Project, project_id)
    if not project or project.user_id != user.id:
        raise HTTPException(404, "Project not found")
    regs = s.query(stack.Register).filter(stack.Register.project_id == project_id, stack.Register.user_id == user.id).all()
    counts: dict[str, int] = {}
    open_counts: dict[str, int] = {}
    for item in regs:
        counts[item.kind] = counts.get(item.kind, 0) + 1
        if item.status.lower() not in {"closed", "complete", "completed", "approved"}:
            open_counts[item.kind] = open_counts.get(item.kind, 0) + 1
    return {"project": {"id": project.id, "name": project.name, "address": project.address, "postcode": project.postcode, "strategy": project.strategy}, "register_counts": counts, "open_counts": open_counts, "updated_at": project.updated_at}


class ForgotPassword(BaseModel):
    email: str


class ResetPassword(BaseModel):
    token: str
    password: str = Field(min_length=10, max_length=128)


@app.post("/api/v1/auth/forgot-password")
async def forgot_password(r: ForgotPassword, s: Session = Depends(stack.db)):
    email = r.email.strip().lower()
    user = s.query(stack.User).filter(stack.User.email == email).first()
    # Deliberately return the same response for known and unknown accounts.
    if user:
        plain = secrets.token_urlsafe(32)
        reset = PasswordReset(user_id=user.id, token_hash=hashlib.sha256(plain.encode()).hexdigest(), expires_at=datetime.now(timezone.utc) + timedelta(minutes=45), used=False)
        s.add(reset); s.commit()
        await _brevo_send(email, "Reset your Property Development, Augmented password", f'<p>A password reset was requested for your account.</p><p><a href="{SITE_URL}/reset-password?token={plain}">Reset password</a></p><p>This link expires in 45 minutes. If you did not request it, ignore this email.</p>')
    return {"status": "ok", "message": "If that account exists, reset instructions have been sent."}


@app.post("/api/v1/auth/reset-password")
def reset_password(r: ResetPassword, s: Session = Depends(stack.db)):
    hashed = hashlib.sha256(r.token.encode()).hexdigest()
    item = s.query(PasswordReset).filter(PasswordReset.token_hash == hashed, PasswordReset.used == False).first()  # noqa: E712
    now = datetime.now(timezone.utc)
    if not item:
        raise HTTPException(400, "Reset token is invalid or expired")
    expiry = item.expires_at if item.expires_at.tzinfo else item.expires_at.replace(tzinfo=timezone.utc)
    if expiry < now:
        raise HTTPException(400, "Reset token is invalid or expired")
    user = s.get(stack.User, item.user_id)
    if not user:
        raise HTTPException(400, "Reset token is invalid or expired")
    user.password_hash = stack.phash(r.password)
    item.used = True
    s.add(user); s.add(item); s.commit()
    return {"status": "password-updated"}
