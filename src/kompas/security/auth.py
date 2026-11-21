"""Password hashing (stdlib PBKDF2-HMAC-SHA256) and JWT tokens (PyJWT)."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import jwt
import yaml
from pydantic import BaseModel

from kompas.core.exceptions import AuthenticationError, ConfigurationError
from kompas.domain.enums import Role
from kompas.domain.people import User
from kompas.persistence.repository import Repository


class PasswordHasher:
    """PBKDF2-HMAC-SHA256 password hashing with per-user salt."""

    def __init__(self, iterations: int = 200_000) -> None:
        self.iterations = iterations

    def hash(self, password: str) -> str:
        salt = secrets.token_hex(16)
        dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), self.iterations)
        return f"pbkdf2_sha256${self.iterations}${salt}${dk.hex()}"

    def verify(self, password: str, encoded: str) -> bool:
        try:
            algo, iter_str, salt, expected = encoded.split("$", 3)
            if algo != "pbkdf2_sha256":
                return False
            dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("ascii"), int(iter_str))
            return hmac.compare_digest(dk.hex(), expected)
        except ValueError:
            return False


class TokenClaims(BaseModel):
    sub: str
    username: str
    role: Role
    exp: datetime


class TokenService:
    """Issues and verifies signed JWT access tokens."""

    def __init__(self, secret: str, algorithm: str = "HS256", ttl_minutes: int = 480) -> None:
        if not secret:
            raise ConfigurationError("JWT secret must not be empty")
        self._secret = secret
        self.algorithm = algorithm
        self.ttl_minutes = ttl_minutes

    def issue(self, user: User) -> str:
        now = datetime.now(UTC)
        payload: dict[str, Any] = {
            "sub": user.id,
            "username": user.username,
            "role": user.role.value,
            "iat": now,
            "exp": now + timedelta(minutes=self.ttl_minutes),
        }
        return jwt.encode(payload, self._secret, algorithm=self.algorithm)

    def verify(self, token: str) -> TokenClaims:
        try:
            payload = jwt.decode(token, self._secret, algorithms=[self.algorithm])
            return TokenClaims.model_validate(payload)
        except jwt.PyJWTError as exc:
            raise AuthenticationError("Nieprawidłowy lub wygasły token") from exc


class AuthService:
    """Authenticates users against the user repository."""

    def __init__(
        self,
        users: Repository[User],
        hasher: PasswordHasher,
        tokens: TokenService,
    ) -> None:
        self.users = users
        self.hasher = hasher
        self.tokens = tokens

    def seed_from_yaml(self, path: Path) -> int:
        if not path.is_file():
            return 0
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        count = 0
        for item in raw.get("users", []):
            if self.users.find(item["id"]) is not None:
                continue
            password = item.pop("password", "")
            user = User(**item, password_hash=self.hasher.hash(password))
            self.users.add(user)
            count += 1
        return count

    def authenticate(self, username: str, password: str) -> tuple[User, str]:
        matches = self.users.list(lambda u: u.username == username and u.active)
        if not matches or not self.hasher.verify(password, matches[0].password_hash):
            raise AuthenticationError("Nieprawidłowa nazwa użytkownika lub hasło")
        user = matches[0]
        return user, self.tokens.issue(user)

    def current_user(self, token: str) -> User:
        claims = self.tokens.verify(token)
        user = self.users.find(claims.sub)
        if user is None or not user.active:
            raise AuthenticationError("Konto użytkownika jest nieaktywne")
        return user

