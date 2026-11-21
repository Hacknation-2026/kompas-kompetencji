"""Unit tests for Phase 5 production hardening, persistence, SSO, GDPR and integrations."""

from __future__ import annotations

import base64
import logging
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import httpx
import pytest

from kompas.api.ratelimit import SlidingWindowRateLimiter
from kompas.container import AppContainer
from kompas.core.exceptions import AuthenticationError, ConfigurationError
from kompas.core.logging import PIIScrubbingFilter, scrub_pii
from kompas.domain.enums import EvaluationStatus, EvaluationType, Role
from kompas.domain.people import User
from kompas.integrations import EzdRpArchiveGateway, QntHrGateway, archive_registry, hr_registry
from kompas.notifications.worker import run_reminder_job
from kompas.persistence import repository_registry
from kompas.security.sso import OidcSSOProvider, Saml2SSOProvider, sso_registry


def test_sqlite_repository_and_postgres_registry() -> None:
    assert "postgres" in repository_registry
    assert "sqlite" in repository_registry

    factory = repository_registry.create("sqlite", {"path": ":memory:"})
    repo = factory.create(User, "users")
    user = User(id="u-1", username="jan", full_name="Jan Kowalski", role=Role.SUPERVISOR)
    repo.add(user)
    assert repo.get("u-1").username == "jan"
    repo.update(user.model_copy(update={"full_name": "Jan Nowak"}))
    assert repo.get("u-1").full_name == "Jan Nowak"
    assert len(repo.list()) == 1
    repo.delete("u-1")
    assert repo.find("u-1") is None


def test_oidc_and_saml2_sso_providers(
    container: AppContainer, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert "oidc" in sso_registry
    assert "saml2" in sso_registry

    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "sub": "ad-123",
        "preferred_username": "ewa.sso",
        "name": "Ewa SSO",
        "email": "ewa.sso@mc.gov.pl",
        "roles": ["hr"],
    }
    monkeypatch.setattr(httpx, "get", lambda *_a, **_kw: resp)
    oidc = OidcSSOProvider(userinfo_url="https://sso.mc.gov.pl/userinfo")
    user, token = container.auth.authenticate_sso(oidc, "valid-bearer-token")
    assert user.role is Role.HR
    assert container.auth.current_user(token).username == "ewa.sso"

    saml_xml = (
        "<Response><Issuer>https://login.gov.pl</Issuer>"
        "<Assertion><Subject><NameID>gov-999</NameID></Subject>"
        "<AttributeStatement>"
        '<Attribute Name="username"><AttributeValue>marek.gov</AttributeValue></Attribute>'
        '<Attribute Name="full_name"><AttributeValue>Marek Gov</AttributeValue></Attribute>'
        '<Attribute Name="role"><AttributeValue>admin</AttributeValue></Attribute>'
        "</AttributeStatement></Assertion></Response>"
    )
    b64 = base64.b64encode(saml_xml.encode("utf-8")).decode("ascii")
    saml = Saml2SSOProvider(expected_issuer="https://login.gov.pl")
    s_user, _ = container.auth.authenticate_sso(saml, b64)
    assert s_user.role is Role.ADMIN
    assert s_user.full_name == "Marek Gov"

    with pytest.raises(AuthenticationError):
        Saml2SSOProvider(expected_issuer="https://other.gov.pl").authenticate(b64)


def test_rate_limiter_and_pii_log_scrubbing() -> None:
    limiter = SlidingWindowRateLimiter(window_seconds=60)
    assert limiter.allow(("127.0.0.1", "/api/v1/auth/login"), limit=2, now=10.0) == (True, 0)
    assert limiter.allow(("127.0.0.1", "/api/v1/auth/login"), limit=2, now=20.0) == (True, 0)
    allowed, retry_after = limiter.allow(("127.0.0.1", "/api/v1/auth/login"), limit=2, now=30.0)
    assert allowed is False
    assert retry_after >= 1

    scrubbed = scrub_pii("PESEL 90010112345 email jan@mc.gov.pl tel +48 600 700 800")
    assert "[PESEL]" in scrubbed
    assert "[EMAIL]" in scrubbed
    assert "[TELEFON]" in scrubbed

    rec = logging.LogRecord("kompas", logging.INFO, __file__, 1, "User %s", ("jan@mc.gov.pl",), None)
    assert PIIScrubbingFilter().filter(rec) is True
    assert "[EMAIL]" in str(rec.msg)


def test_gdpr_audit_log_anonymization_and_reminder_worker(container: AppContainer) -> None:
    sup, _ = container.auth.authenticate("przelozony", "demo-password-1")
    ev = container.evaluation_service.create("emp-2", EvaluationType.PERIODIC, sup)
    ev.status = EvaluationStatus.COMPLETED
    ev.justification = "Szczegółowe uzasadnienie"
    ev.development_plan = "Plan IPRZ"
    ev.updated_at = datetime.now(UTC) - timedelta(days=400)
    container.evaluations_repo.update(ev)

    audit = container.monitoring.export_audit_log()
    assert any(a.evaluation_id == ev.id and a.event_type == "evaluation_created" for a in audit)

    report = container.monitoring.anonymize_completed(older_than_days=365)
    assert report.anonymized_count == 1
    assert container.evaluations_repo.get(ev.id).justification == "[ZANONIMIZOWANO]"

    sent = run_reminder_job(container=container)
    assert isinstance(sent, list)


def test_qnt_and_ezd_rp_gateways(monkeypatch: pytest.MonkeyPatch) -> None:
    assert "qnt" in hr_registry
    assert "ezd_rp" in archive_registry

    monkeypatch.delenv("QNT_API_KEY", raising=False)
    qnt = QntHrGateway(base_url="https://qnt.mc.gov.pl/api")
    with pytest.raises(ConfigurationError):
        qnt.fetch_employees()

    monkeypatch.setenv("QNT_API_KEY", "qnt-secret")
    qnt_resp = MagicMock()
    qnt_resp.json.return_value = {
        "items": [
            {
                "id": "emp-qnt-1",
                "first_name": "Anna",
                "last_name": "Nowak",
                "org_unit": "BDG",
                "position": "Specjalista",
                "supervisor_id": "sup-1",
                "employment_start": "2024-01-01",
                "is_civil_servant": True,
            }
        ]
    }
    monkeypatch.setattr(httpx, "get", lambda *_a, **_kw: qnt_resp)
    employees = qnt.fetch_employees()
    assert len(employees) == 1
    assert employees[0].is_civil_servant is True

    monkeypatch.setenv("EZD_RP_API_KEY", "ezd-secret")
    ezd_resp = MagicMock()
    ezd_resp.json.return_value = {"archive_ref": "ezd-rp://akta/2026/001"}
    monkeypatch.setattr(httpx, "post", lambda *_a, **_kw: ezd_resp)
    ezd = EzdRpArchiveGateway(base_url="https://ezd.mc.gov.pl/api")
    ref = ezd.store("eval-1", "arkusz.pdf", b"%PDF-1.4")
    assert ref == "ezd-rp://akta/2026/001"
