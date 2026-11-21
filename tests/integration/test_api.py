"""End-to-end HTTP API integration tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from tests.conftest import auth_header


@pytest.mark.integration
def test_health_and_auth_guards(client: TestClient) -> None:
    health = client.get("/api/v1/health")
    assert health.status_code == 200
    assert health.json()["competencies_loaded"] == 14

    assert client.get("/api/v1/evaluations").status_code == 401
    bad_login = client.post("/api/v1/auth/login", json={"username": "przelozony", "password": "wrong"})
    assert bad_login.status_code == 401


@pytest.mark.integration
def test_full_periodic_evaluation_and_rbac_flow(client: TestClient) -> None:
    sup1 = auth_header(client, "przelozony", "demo-password-1")
    sup2 = auth_header(client, "przelozony2", "demo-password-2")
    hr = auth_header(client, "kadry", "demo-password-hr")

    # 1. Analyze job description
    osp = client.post(
        "/api/v1/competencies/analyze-job-description",
        headers=sup1,
        json={"text": "Radca analizuje przepisy prawa UE i orzecznictwo w obszarze AI."},
    )
    assert osp.status_code == 200
    assert osp.json()["recommended_form"] == "C"

    # 2. Start periodic evaluation for emp-2
    created = client.post(
        "/api/v1/evaluations",
        headers=sup1,
        json={"employee_id": "emp-2", "evaluation_type": "periodic"},
    )
    assert created.status_code == 201
    ev_id = created.json()["id"]

    # Another supervisor cannot access sup1's evaluation
    assert client.get(f"/api/v1/evaluations/{ev_id}", headers=sup2).status_code == 403
    # Supervisor cannot access HR monitoring
    assert client.get("/api/v1/monitoring/dashboard", headers=sup1).status_code == 403

    # 3. Step 1 -> Step 2 (configure criteria)
    assert (
        client.post(
            f"/api/v1/evaluations/{ev_id}/steps/complete",
            headers=sup1,
            json={"step_id": "job_description_analysis"},
        ).status_code
        == 200
    )

    crit = client.put(
        f"/api/v1/evaluations/{ev_id}/criteria",
        headers=sup1,
        json={"additional_criteria": ["myslenie_analityczne"], "goals": ["Opinie AI Act"], "confirm": True},
    )
    assert crit.status_code == 200
    criteria_list = crit.json()["mandatory_criteria"] + crit.json()["additional_criteria"]

    assert (
        client.post(
            f"/api/v1/evaluations/{ev_id}/steps/complete",
            headers=sup1,
            json={"step_id": "criteria_setting"},
        ).status_code
        == 200
    )

    # 4. Assess all criteria using the competency model
    model = client.get("/api/v1/competencies/model", headers=sup1).json()
    by_id = {c["id"]: c for c in model["competencies"]}
    for cid in criteria_list:
        observations = [{"indicator_id": ind["id"], "observed_points": 7} for ind in by_id[cid]["indicators"]]
        resp = client.put(
            f"/api/v1/evaluations/{ev_id}/criteria/{cid}/assessment",
            headers=sup1,
            json={"indicators": observations, "final_points": 7},
        )
        assert resp.status_code == 200
        assert resp.json()["assessments"][cid]["suggestion"]["points"] == 7

    assert (
        client.post(
            f"/api/v1/evaluations/{ev_id}/steps/complete",
            headers=sup1,
            json={"step_id": "competency_assessment"},
        ).status_code
        == 200
    )

    # 5. Assistant conversation prep & formal Q&A
    prep = client.get(f"/api/v1/assistant/conversation-prep/{ev_id}", headers=sup1)
    assert prep.status_code == 200
    assert len(prep.json()["criterion_prompts"]) == len(criteria_list)

    qa = client.post(
        "/api/v1/assistant/ask",
        headers=sup1,
        json={
            "question": "W jakim terminie można wnieść sprzeciw?",
            "mode": "formal",
            "evaluation_id": ev_id,
        },
    )
    assert qa.status_code == 200 and qa.json()["grounded"] is True

    assert (
        client.post(
            f"/api/v1/evaluations/{ev_id}/steps/complete",
            headers=sup1,
            json={"step_id": "evaluation_interview"},
        ).status_code
        == 200
    )

    # 6. Outcome & final steps & PDF export
    outcome = client.post(
        f"/api/v1/evaluations/{ev_id}/outcome",
        headers=sup1,
        json={"development_plan": "Udział w szkoleniu z AI Act."},
    )
    assert outcome.status_code == 200
    assert outcome.json()["positive"] is True

    for step_id in ("decision", "acknowledgement"):
        assert (
            client.post(
                f"/api/v1/evaluations/{ev_id}/steps/complete",
                headers=sup1,
                json={"step_id": step_id},
            ).status_code
            == 200
        )

    pdf = client.get(f"/api/v1/evaluations/{ev_id}/document?fmt=pdf&archive=true", headers=sup1)
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

    # 7. HR monitoring
    dash = client.get("/api/v1/monitoring/dashboard", headers=hr)
    assert dash.status_code == 200
    assert dash.json()["completed"] == 1
