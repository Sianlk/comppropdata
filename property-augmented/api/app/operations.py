from __future__ import annotations

import hashlib
import io
import json
import os
from datetime import datetime, timezone
from typing import Any
from xml.sax.saxutils import escape

from fastapi import Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.lib import colors
from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, Session, mapped_column

from .bootstrap import app
from . import full_stack as stack
from .agents import AIRun, EvidenceClaim, evidence_health
from .documents import DocumentAsset


def now() -> datetime:
    return datetime.now(timezone.utc)


class AuditEvent(stack.Base):
    __tablename__ = "pda_audit_events"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("pda_users.id"), index=True)
    request_id: Mapped[str] = mapped_column(String(100), index=True)
    method: Mapped[str] = mapped_column(String(12))
    path: Mapped[str] = mapped_column(String(500), index=True)
    status_code: Mapped[int] = mapped_column(Integer)
    client_hash: Mapped[str] = mapped_column(String(64), default="")
    user_agent: Mapped[str] = mapped_column(String(300), default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now, index=True)


stack.Base.metadata.create_all(stack.engine)
AUDIT_SALT = os.getenv("AUDIT_HASH_SALT", stack.JWT_SECRET)


@app.middleware("http")
async def audit_mutations(request: Request, call_next):
    user_id: int | None = None
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        try:
            payload = stack.decode(auth.split(" ", 1)[1])
            user_id = int(payload["sub"])
        except Exception:
            user_id = None
    status = 500
    response = None
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        if user_id is not None and request.method in {"POST", "PUT", "PATCH", "DELETE"} and not request.url.path.startswith("/api/v1/audit/"):
            try:
                client = request.client.host if request.client else "unknown"
                ua = request.headers.get("user-agent", "")[:300]
                client_hash = hashlib.sha256(f"{AUDIT_SALT}|{client}|{ua}".encode()).hexdigest()
                rid = getattr(request.state, "request_id", "") or request.headers.get("x-request-id", "")
                with stack.SessionLocal() as s:
                    s.add(AuditEvent(user_id=user_id, request_id=str(rid)[:100], method=request.method, path=request.url.path[:500], status_code=status, client_hash=client_hash, user_agent=ua))
                    s.commit()
            except Exception:
                # Audit persistence failure must not corrupt the underlying user transaction.
                pass


class ScenarioRequest(BaseModel):
    acquisition: float = 0
    transaction_costs: float = 0
    construction: float = 0
    professional_fees: float = 0
    finance: float = 0
    contingency: float = 0
    other_costs: float = 0
    gdv: float = 0
    gdv_steps_pct: list[float] = Field(default_factory=lambda: [-15, -10, -5, 0, 5, 10, 15])
    construction_steps_pct: list[float] = Field(default_factory=lambda: [-15, -10, -5, 0, 5, 10, 15])


def _scenario(r: ScenarioRequest, gdv_pct: float, build_pct: float) -> dict[str, Any]:
    gdv = r.gdv * (1 + gdv_pct / 100)
    construction = r.construction * (1 + build_pct / 100)
    total = r.acquisition + r.transaction_costs + construction + r.professional_fees + r.finance + r.contingency + r.other_costs
    profit = gdv - total
    return {"gdv_change_pct": gdv_pct, "construction_change_pct": build_pct, "gdv": gdv, "construction": construction, "total_cost": total, "profit": profit, "margin_on_cost_pct": (profit / total * 100) if total else None, "margin_on_gdv_pct": (profit / gdv * 100) if gdv else None}


@app.post("/api/v1/calculators/scenario-lab")
def scenario_lab(r: ScenarioRequest):
    gdv_steps = sorted(set(max(-60, min(100, float(x))) for x in r.gdv_steps_pct))[:15]
    build_steps = sorted(set(max(-60, min(100, float(x))) for x in r.construction_steps_pct))[:15]
    matrix = [_scenario(r, g, c) for c in build_steps for g in gdv_steps]
    base = _scenario(r, 0, 0)
    return {"base": base, "break_even_gdv": base["total_cost"], "gdv_steps_pct": gdv_steps, "construction_steps_pct": build_steps, "matrix": matrix, "assumptions": r.model_dump(), "note": "Deterministic sensitivity analysis only. It is not a valuation, probability model, tax calculation, lender decision, QS cost plan or investment recommendation. Change one assumption only if it represents a plausible project scenario."}


@app.get("/api/v1/audit/events")
def audit_events(limit: int = 100, user: stack.User = Depends(stack.me), s: Session = Depends(stack.db)):
    rows = s.query(AuditEvent).filter(AuditEvent.user_id == user.id).order_by(AuditEvent.created_at.desc()).limit(max(1, min(limit, 500))).all()
    return {"events": [{"id": x.id, "request_id": x.request_id, "method": x.method, "path": x.path, "status_code": x.status_code, "client_hash": x.client_hash, "user_agent": x.user_agent, "created_at": x.created_at} for x in rows], "note": "Audit events record authenticated state-changing API requests. They deliberately exclude request bodies and secrets."}


def _project_bundle(project_id: int, user: stack.User, s: Session) -> dict[str, Any]:
    p = s.get(stack.Project, project_id)
    if not p or p.user_id != user.id:
        raise HTTPException(404, "Project not found")
    registers = s.query(stack.Register).filter(stack.Register.project_id == project_id, stack.Register.user_id == user.id).order_by(stack.Register.updated_at.desc()).all()
    documents = s.query(DocumentAsset).filter(DocumentAsset.project_id == project_id, DocumentAsset.user_id == user.id).order_by(DocumentAsset.created_at.desc()).all()
    claims = s.query(EvidenceClaim).filter(EvidenceClaim.project_id == project_id, EvidenceClaim.user_id == user.id).order_by(EvidenceClaim.created_at.desc()).all()
    runs = s.query(AIRun).filter(AIRun.project_id == project_id, AIRun.user_id == user.id).order_by(AIRun.created_at.desc()).all()
    bundle = {
        "generated_at": now().isoformat(),
        "project": {"id": p.id, "name": p.name, "address": p.address, "postcode": p.postcode, "strategy": p.strategy, "metadata": json.loads(p.metadata_json or "{}"), "updated_at": p.updated_at.isoformat() if p.updated_at else None},
        "evidence_health": evidence_health(project_id, user, s),
        "registers": [{"id": x.id, "kind": x.kind, "title": x.title, "status": x.status, "data": json.loads(x.data_json or "{}"), "updated_at": x.updated_at.isoformat() if x.updated_at else None} for x in registers],
        "documents": [{"id": x.id, "filename": x.original_name, "sha256": x.sha256, "size_bytes": x.size_bytes, "extraction_status": x.extraction_status, "security_flags": json.loads(x.security_flags_json or "[]"), "retention_until": x.retention_until.isoformat() if x.retention_until else None, "created_at": x.created_at.isoformat() if x.created_at else None} for x in documents],
        "claims": [{"id": x.id, "run_id": x.run_id, "claim_ref": x.claim_ref, "claim": x.claim_text, "classification": x.classification, "confidence": x.confidence, "materiality": x.materiality, "source_refs": json.loads(x.source_refs_json or "[]"), "verification_action": x.verification_action, "review_status": x.review_status, "review_note": x.review_note, "created_at": x.created_at.isoformat() if x.created_at else None} for x in claims],
        "agent_runs": [{"id": x.id, "agent_slug": x.agent_slug, "model": x.model, "output_sha256": x.output_sha256, "review_status": x.review_status, "security_flags": json.loads(x.security_flags_json or "[]"), "created_at": x.created_at.isoformat() if x.created_at else None} for x in runs],
        "limitations": ["This is an evidence snapshot, not a planning permission, valuation, cost certification, legal opinion, building-regulation approval or investment recommendation.", "Material facts should be checked against the original source and current professional/authority position before reliance."]
    }
    canonical = json.dumps(bundle, sort_keys=True, default=str, ensure_ascii=False)
    bundle["snapshot_sha256"] = hashlib.sha256(canonical.encode()).hexdigest()
    return bundle


@app.get("/api/v1/projects/{project_id}/decision-pack.json")
def decision_pack_json(project_id: int, user: stack.User = Depends(stack.me), s: Session = Depends(stack.db)):
    return _project_bundle(project_id, user, s)


@app.get("/api/v1/projects/{project_id}/decision-pack.pdf")
def decision_pack_pdf(project_id: int, user: stack.User = Depends(stack.me), s: Session = Depends(stack.db)):
    b = _project_bundle(project_id, user, s)
    out = io.BytesIO(); styles = getSampleStyleSheet(); story = []
    story += [Paragraph("Property Development, Augmented", styles["Title"]), Paragraph("Project Decision Pack", styles["Heading1"]), Paragraph(escape(b["project"]["name"]), styles["Heading2"]), Paragraph(escape(" · ".join(x for x in [b["project"].get("address",""), b["project"].get("postcode","")] if x)), styles["BodyText"]), Spacer(1, 10), Paragraph(f"Generated: {escape(b['generated_at'])}", styles["BodyText"]), Paragraph(f"Evidence snapshot SHA-256: {b['snapshot_sha256']}", styles["BodyText"]), Spacer(1, 12)]
    h = b["evidence_health"]
    story += [Paragraph("Evidence health", styles["Heading2"]), Paragraph(escape(f"State: {h['band']} | claims {h['total_claims']} | verified {h['verified']} | contested {h['contested']} | high/critical unreviewed {h['high_or_critical_unreviewed']} | agent runs {h['run_count']}"), styles["BodyText"]), Paragraph(escape(h["note"]), styles["BodyText"])]
    if b["project"].get("strategy"):
        story += [Paragraph("Project strategy", styles["Heading2"]), Paragraph(escape(str(b["project"]["strategy"]))[:6000], styles["BodyText"])]
    story += [Paragraph("Evidence claims", styles["Heading2"])]
    if not b["claims"]: story.append(Paragraph("No structured claims have been recorded.", styles["BodyText"]))
    for c in b["claims"][:250]:
        story += [Paragraph(escape(f"{c['claim_ref']} · {c['classification']} · {c['materiality']} · review: {c['review_status']}"), styles["Heading3"]), Paragraph(escape(c["claim"])[:6000], styles["BodyText"])]
        if c.get("source_refs"): story.append(Paragraph("Sources: " + escape(" | ".join(map(str,c["source_refs"])))[:6000], styles["BodyText"]))
        if c.get("verification_action"): story.append(Paragraph("Verify: " + escape(c["verification_action"])[:4000], styles["BodyText"]))
    story += [PageBreak(), Paragraph("Project registers", styles["Heading2"])]
    if not b["registers"]: story.append(Paragraph("No project-control register items recorded.", styles["BodyText"]))
    for r in b["registers"][:300]:
        story += [Paragraph(escape(f"{r['kind'].upper()} · {r['status']} · {r['title']}"), styles["Heading3"]), Paragraph(escape(json.dumps(r["data"], default=str, ensure_ascii=False))[:5000], styles["BodyText"])]
    story += [Paragraph("Document index", styles["Heading2"])]
    for d in b["documents"][:300]: story.append(Paragraph(escape(f"DOC {d['id']} · {d['filename']} · SHA-256 {d['sha256']} · extraction {d['extraction_status']}"), styles["BodyText"]))
    story += [Paragraph("Agent run index", styles["Heading2"])]
    for r in b["agent_runs"][:300]: story.append(Paragraph(escape(f"RUN {r['id']} · {r['agent_slug']} · review {r['review_status']} · output SHA-256 {r['output_sha256']}"), styles["BodyText"]))
    story += [Spacer(1,12), Paragraph("Limitations", styles["Heading2"])]
    for item in b["limitations"]: story.append(Paragraph(escape(item), styles["BodyText"]))
    doc = SimpleDocTemplate(out, pagesize=A4, title=f"{b['project']['name']} - Decision Pack", author="Property Development, Augmented", rightMargin=36, leftMargin=36, topMargin=40, bottomMargin=40)
    doc.build(story)
    return StreamingResponse(io.BytesIO(out.getvalue()), media_type="application/pdf", headers={"Content-Disposition": f'attachment; filename="project-{project_id}-decision-pack.pdf"', "Cache-Control":"no-store", "X-Evidence-Snapshot-SHA256":b["snapshot_sha256"]})
