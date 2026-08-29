from __future__ import annotations

import uuid

from fastapi.testclient import TestClient

from app.production import app

client = TestClient(app)


def _account():
    email = f"ci-{uuid.uuid4().hex}@example.test"
    response = client.post("/api/v1/auth/register", json={"email": email, "password": "SecurePass123!", "name": "CI User"})
    assert response.status_code == 200, response.text
    token = response.json()["token"]
    return email, {"Authorization": f"Bearer {token}"}


def test_health_and_status():
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["status"] == "healthy"
    status = client.get("/api/v1/system/status")
    assert status.status_code == 200
    assert status.json()["providers"]["api"] is True


def test_appraisal_arithmetic_is_transparent():
    response = client.post("/api/v1/calculators/appraisal", json={
        "acquisition": 100000,
        "transaction_costs": 5000,
        "construction": 80000,
        "professional_fees": 10000,
        "finance": 10000,
        "contingency": 5000,
        "other_costs": 0,
        "gdv": 250000,
        "rental_income_annual": 0,
        "holding_months": 12,
    })
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["total_development_cost"] == 210000
    assert body["profit"] == 40000
    assert round(body["margin_on_gdv_pct"], 2) == 16.00
    assert "not a valuation" in body["note"].lower()


def test_public_policy_library_contains_current_nppf_source():
    response = client.get("/api/v1/policy/library")
    assert response.status_code == 200, response.text
    rows = response.json()["items"]
    nppf = next(row for row in rows if row["id"] == "nppf-2026")
    assert nppf["authoritative"] is True
    assert "17 August 2026" in nppf["effective_context"]
    assert nppf["url"].startswith("https://www.gov.uk/")


def test_generated_site_triage_is_a_real_pdf():
    response = client.get("/api/v1/resources/site-triage.pdf")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content.startswith(b"%PDF")
    assert len(response.content) > 1000


def test_project_and_register_lifecycle_and_variation_evidence_gate():
    _, headers = _account()
    created = client.post("/api/v1/projects", headers=headers, json={"name": "CI Project", "postcode": "RG45 7AA", "strategy": "Test"})
    assert created.status_code == 200, created.text
    project_id = created.json()["id"]

    bad = client.post(f"/api/v1/projects/{project_id}/registers", headers=headers, json={
        "kind": "variation", "title": "Move wall", "status": "Approved", "data": {"value": 500}
    })
    assert bad.status_code == 422

    pending = client.post(f"/api/v1/projects/{project_id}/registers", headers=headers, json={
        "kind": "variation", "title": "Move wall", "status": "Approval not evidenced", "data": {"value": 500}
    })
    assert pending.status_code == 200, pending.text
    register_id = pending.json()["id"]

    bad_patch = client.patch(f"/api/v1/projects/{project_id}/registers/{register_id}", headers=headers, json={"status": "Approved", "data": {"value": 500}})
    assert bad_patch.status_code == 422

    good_patch = client.patch(f"/api/v1/projects/{project_id}/registers/{register_id}", headers=headers, json={"status": "Approved", "data": {"value": 500, "approval_evidence": "Written client approval ref CI-001"}})
    assert good_patch.status_code == 200, good_patch.text
    assert good_patch.json()["status"] == "Approved"

    summary = client.get(f"/api/v1/projects/{project_id}/summary", headers=headers)
    assert summary.status_code == 200
    assert summary.json()["register_counts"]["variation"] == 1

    deleted = client.delete(f"/api/v1/projects/{project_id}", headers=headers)
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] is True


def test_paid_compute_requires_authentication_in_production():
    ai = client.post("/api/v1/ai/analyse", json={"question": "Test", "mode": "report-writer"})
    assert ai.status_code == 401
    deep = client.post("/api/v1/research/web-deep", json={"topic": "Current NPPF"})
    assert deep.status_code == 401
    policy = client.post("/api/v1/policy/search", json={"query": "NPPF", "web_research": True})
    assert policy.status_code == 401
