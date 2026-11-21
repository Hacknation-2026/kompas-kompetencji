"""End-to-end HTTP API integration tests."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from tests.conftest import auth_header


@pytest.mark.integration
def test_health_and_auth_guards(client: TestClient) -> None:
    ui = client.get("/")
    assert ui.status_code == 200
    assert "Kompas Kompetencji" in ui.text
    assert client.get("/static/app.js").status_code == 200

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

    # 1. Analyze job description (text + file upload)
    osp = client.post(
        "/api/v1/competencies/analyze-job-description",
        headers=sup1,
        json={"text": "Radca analizuje przepisy prawa UE i orzecznictwo w obszarze AI."},
    )
    assert osp.status_code == 200
    assert osp.json()["recommended_form"] == "C"

    osp_upload = client.post(
        "/api/v1/competencies/analyze-job-description/upload",
        headers=sup1,
        files={"file": ("osp.txt", b"Analizuje przepisy prawa oraz zarzadzania kryzysowego.", "text/plain")},
    )
    assert osp_upload.status_code == 200
    assert osp_upload.json()["recommended_form"] == "C"

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

    promo = client.put(
        f"/api/v1/evaluations/{ev_id}/rank-promotion",
        headers=sup1,
        json={"requested_rank": "III stopień", "rationale": "Bardzo wysoka jakość opinii prawnych."},
    )
    assert promo.status_code == 200
    assert promo.json()["rank_promotion_motion"]["requested_rank"] == "III stopień"

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


@pytest.mark.integration
def test_first_evaluation_e2e_deadlines_and_reevaluation(client: TestClient) -> None:
    sup1 = auth_header(client, "przelozony", "demo-password-1")

    # 1. Create First Evaluation for emp-1 (no preparatory exam passed yet)
    created = client.post(
        "/api/v1/evaluations",
        headers=sup1,
        json={"employee_id": "emp-1", "evaluation_type": "first"},
    )
    assert created.status_code == 201
    ev_id = created.json()["id"]
    assert created.json()["form"] == "FIRST"

    # 2. Initial interview
    assert (
        client.post(
            f"/api/v1/evaluations/{ev_id}/steps/complete",
            headers=sup1,
            json={"step_id": "initial_interview"},
        ).status_code
        == 200
    )

    # 3. Extend deadline for report step (§ 5 rozp. 2015)
    ext = client.post(
        f"/api/v1/evaluations/{ev_id}/deadlines/extend",
        headers=sup1,
        json={"step_id": "report", "new_due_date": "2026-12-15", "reason": "Usprawiedliwiona nieobecność"},
    )
    assert ext.status_code == 200
    assert len(ext.json()["deadline_extensions"]) == 1

    # 4. Report step: < 7 months rejected, >= 7 months accepted with full Załącznik nr 3
    bad_rep = client.put(
        f"/api/v1/evaluations/{ev_id}/first-eval-facts",
        headers=sup1,
        json={
            "report_submitted_on_time": True,
            "report_details": {"tasks_performed": "Analiza aktów", "period_months": 5},
        },
    )
    assert bad_rep.status_code == 422

    good_rep = client.put(
        f"/api/v1/evaluations/{ev_id}/first-eval-facts",
        headers=sup1,
        json={
            "report_submitted_on_time": True,
            "report_details": {
                "tasks_performed": "Przygotowanie projektów odpowiedzi i analiz prawnych.",
                "problems_and_solutions": "Konsultacje z zespołem prawnym.",
                "new_skills_and_knowledge": "Znajomość KPA i procedur MC.",
                "improvement_proposals": "Szablon checklisty dla nowych spraw.",
                "period_months": 8,
            },
        },
    )
    assert good_rep.status_code == 200
    assert (
        client.post(
            f"/api/v1/evaluations/{ev_id}/steps/complete",
            headers=sup1,
            json={"step_id": "report"},
        ).status_code
        == 200
    )

    # 5. Competency assessment with STAR evidence notes
    model = client.get("/api/v1/competencies/model", headers=sup1).json()
    by_id = {c["id"]: c for c in model["competencies"]}
    for cid in good_rep.json()["mandatory_criteria"]:
        observations = [
            {
                "indicator_id": ind["id"],
                "observed_points": 5,
                "evidence": "S: Projekt odpowiedzi; D: Terminowe opracowanie; R: Akceptacja bez uwag.",
            }
            for ind in by_id[cid]["indicators"]
        ]
        resp = client.put(
            f"/api/v1/evaluations/{ev_id}/criteria/{cid}/assessment",
            headers=sup1,
            json={"indicators": observations, "final_points": 5},
        )
        assert resp.status_code == 200

    assert (
        client.post(
            f"/api/v1/evaluations/{ev_id}/steps/complete",
            headers=sup1,
            json={"step_id": "competency_assessment"},
        ).status_code
        == 200
    )

    # 6. Evaluation interview
    assert (
        client.post(
            f"/api/v1/evaluations/{ev_id}/steps/complete",
            headers=sup1,
            json={"step_id": "evaluation_interview"},
        ).status_code
        == 200
    )

    # 7. Decision: negative (exam_passed=False) -> requires justification; then positive (exam_passed=True)
    client.put(
        f"/api/v1/evaluations/{ev_id}/first-eval-facts",
        headers=sup1,
        json={"exam_applicable": True, "exam_passed": False},
    )
    neg_outcome = client.post(
        f"/api/v1/evaluations/{ev_id}/outcome",
        headers=sup1,
        json={"justification": "Niezaliczony egzamin ze służby przygotowawczej."},
    )
    assert neg_outcome.status_code == 200
    assert neg_outcome.json()["positive"] is False

    client.put(
        f"/api/v1/evaluations/{ev_id}/first-eval-facts",
        headers=sup1,
        json={"exam_applicable": True, "exam_passed": True},
    )
    pos_outcome = client.post(
        f"/api/v1/evaluations/{ev_id}/outcome",
        headers=sup1,
        json={"justification": "Pozytywny wynik egzaminu poprawkowego i dobra realizacja zadań."},
    )
    assert pos_outcome.status_code == 200
    assert pos_outcome.json()["positive"] is True

    # 8. Complete decision & acknowledgement -> PDF download
    for step_id in ("decision", "acknowledgement"):
        assert (
            client.post(
                f"/api/v1/evaluations/{ev_id}/steps/complete",
                headers=sup1,
                json={"step_id": step_id},
            ).status_code
            == 200
        )

    pdf = client.get(f"/api/v1/evaluations/{ev_id}/document?fmt=pdf", headers=sup1)
    assert pdf.status_code == 200
    assert pdf.content.startswith(b"%PDF")

    # 9. Post-negative 6-month re-evaluation & form_override
    reeval = client.post(
        "/api/v1/evaluations",
        headers=sup1,
        json={
            "employee_id": "emp-2",
            "evaluation_type": "periodic",
            "form_override": "B",
            "period_anchor": "2026-01-10",
            "is_post_negative_reevaluation": True,
        },
    )
    assert reeval.status_code == 201
    r_data = reeval.json()
    assert r_data["form"] == "B"
    assert r_data["is_post_negative_reevaluation"] is True
    assert r_data["anchors"]["evaluation_due"] == "2026-07-10"
    crit_dl = next(d for d in r_data["deadlines"] if d["step_id"] == "criteria_setting")
    assert crit_dl["due_date"] == "2026-01-17"  # 2026-01-17 is Saturday (7 days after 2026-01-10)
