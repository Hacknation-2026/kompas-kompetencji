"""Enterprise SSO providers (OIDC & SAML2 for Active Directory / gov.pl)."""

from __future__ import annotations

import base64
import xml.etree.ElementTree as ET
from abc import ABC, abstractmethod
from typing import Any

import httpx
from pydantic import BaseModel

from kompas.core.exceptions import AuthenticationError, ExternalServiceError
from kompas.core.registry import Registry
from kompas.domain.enums import Role


class SSOIdentity(BaseModel):
    """Normalized identity returned by an enterprise SSO provider."""

    subject: str
    username: str
    full_name: str
    email: str | None = None
    role: Role = Role.SUPERVISOR
    org_unit: str | None = None
    position: str | None = None


class SSOProvider(ABC):
    """Contract for enterprise SSO token/assertion verification."""

    @abstractmethod
    def authenticate(self, assertion_or_token: str) -> SSOIdentity: ...


sso_registry: Registry[SSOProvider] = Registry("sso")


def _map_role(raw_roles: list[str] | str | None, role_mapping: dict[str, str] | None = None) -> Role:
    if raw_roles is None:
        return Role.SUPERVISOR
    values = [raw_roles] if isinstance(raw_roles, str) else list(raw_roles)
    mapping = role_mapping or {"admin": "admin", "hr": "hr", "kadry": "hr", "supervisor": "supervisor"}
    for val in values:
        normalized = val.strip().lower()
        if normalized in mapping:
            return Role(mapping[normalized])
    return Role.SUPERVISOR


@sso_registry.register("oidc")
class OidcSSOProvider(SSOProvider):
    """OIDC / OAuth2 Bearer access-token verification via UserInfo endpoint."""

    def __init__(
        self,
        userinfo_url: str,
        timeout_seconds: float = 10.0,
        role_claim: str = "roles",
        role_mapping: dict[str, str] | None = None,
    ) -> None:
        self.userinfo_url = userinfo_url
        self.timeout_seconds = timeout_seconds
        self.role_claim = role_claim
        self.role_mapping = role_mapping

    def authenticate(self, assertion_or_token: str) -> SSOIdentity:
        if not assertion_or_token.strip():
            raise AuthenticationError("Pusty token OIDC")
        try:
            resp = httpx.get(
                self.userinfo_url,
                headers={"Authorization": f"Bearer {assertion_or_token}"},
                timeout=self.timeout_seconds,
            )
            if resp.status_code in (401, 403):
                raise AuthenticationError("Token OIDC odrzucony przez dostawcę tożsamości")
            resp.raise_for_status()
            claims: dict[str, Any] = resp.json()
        except httpx.HTTPError as exc:
            raise ExternalServiceError(f"Błąd połączenia z dostawcą OIDC: {exc}") from exc

        sub = str(claims.get("sub") or "")
        username = str(claims.get("preferred_username") or claims.get("email") or sub)
        if not sub or not username:
            raise AuthenticationError("Brak wymaganych roszczeń OIDC (sub / preferred_username)")
        return SSOIdentity(
            subject=sub,
            username=username,
            full_name=str(claims.get("name") or username),
            email=claims.get("email"),
            role=_map_role(claims.get(self.role_claim), self.role_mapping),
            org_unit=claims.get("org_unit"),
            position=claims.get("position"),
        )


@sso_registry.register("saml2")
class Saml2SSOProvider(SSOProvider):
    """SAML2 assertion parser for Active Directory / gov.pl Węzeł Krajowy."""

    def __init__(
        self,
        expected_issuer: str | None = None,
        role_mapping: dict[str, str] | None = None,
    ) -> None:
        self.expected_issuer = expected_issuer
        self.role_mapping = role_mapping

    def authenticate(self, assertion_or_token: str) -> SSOIdentity:
        try:
            raw_xml = base64.b64decode(assertion_or_token.encode("ascii"), validate=True).decode("utf-8")
            root = ET.fromstring(raw_xml)
        except Exception as exc:
            raise AuthenticationError("Nieprawidłowa odpowiedź SAML2 (Base64/XML)") from exc

        if self.expected_issuer:
            issuer_el = root.find(".//{*}Issuer")
            issuer = issuer_el.text.strip() if issuer_el is not None and issuer_el.text else ""
            if issuer != self.expected_issuer:
                raise AuthenticationError("Nieautoryzowany wystawca SAML2 (Issuer)")

        name_id_el = root.find(".//{*}NameID")
        subject = name_id_el.text.strip() if name_id_el is not None and name_id_el.text else ""
        if not subject:
            raise AuthenticationError("Brak identyfikatora NameID w asercji SAML2")

        attrs: dict[str, list[str]] = {}
        for attr in root.findall(".//{*}Attribute"):
            name = attr.attrib.get("Name", "")
            vals = [v.text.strip() for v in attr.findall("{*}AttributeValue") if v.text and v.text.strip()]
            if name and vals:
                attrs[name] = vals

        username = (attrs.get("username") or attrs.get("uid") or [subject])[0]
        full_name = (attrs.get("full_name") or attrs.get("cn") or [username])[0]
        email_vals = attrs.get("email") or attrs.get("mail")
        email = email_vals[0] if email_vals else None
        org_vals = attrs.get("org_unit")
        pos_vals = attrs.get("position")
        role = _map_role(attrs.get("role") or attrs.get("roles"), self.role_mapping)
        return SSOIdentity(
            subject=subject,
            username=username,
            full_name=full_name,
            email=email,
            role=role,
            org_unit=org_vals[0] if org_vals else None,
            position=pos_vals[0] if pos_vals else None,
        )
