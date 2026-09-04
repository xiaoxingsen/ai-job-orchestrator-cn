from __future__ import annotations

import re
import secrets
import threading
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256

_EXTENSION_ORIGIN = re.compile(r"^chrome-extension://[a-p]{16,64}$")


class InvalidPairing(ValueError):
    pass


def _digest(token: str) -> str:
    return sha256(token.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class _Session:
    origin: str
    expires_at: datetime


class PairingService:
    def __init__(
        self,
        *,
        token_ttl: timedelta = timedelta(minutes=5),
        session_ttl: timedelta = timedelta(hours=12),
    ) -> None:
        self.token_ttl = token_ttl
        self.session_ttl = session_ttl
        self._tokens: dict[str, datetime] = {}
        self._sessions: dict[str, _Session] = {}
        self._lock = threading.Lock()

    def issue_token(self) -> str:
        raw = secrets.token_urlsafe(32)
        with self._lock:
            self._tokens[_digest(raw)] = datetime.now(UTC) + self.token_ttl
        return raw

    def consume_token(self, token: str, *, origin: str) -> str:
        if not _EXTENSION_ORIGIN.fullmatch(origin):
            raise InvalidPairing("pairing is only available to a Chromium extension origin")
        now = datetime.now(UTC)
        with self._lock:
            expires_at = self._tokens.pop(_digest(token), None)
            if expires_at is None or expires_at < now:
                raise InvalidPairing("pairing token is invalid, expired, or already used")
            raw_session = secrets.token_urlsafe(48)
            self._sessions[_digest(raw_session)] = _Session(
                origin=origin, expires_at=now + self.session_ttl
            )
        return raw_session

    def validate_session(self, session_token: str, *, origin: str) -> bool:
        with self._lock:
            session = self._sessions.get(_digest(session_token))
            if session is None:
                return False
            if session.expires_at < datetime.now(UTC):
                self._sessions.pop(_digest(session_token), None)
                return False
            return secrets.compare_digest(session.origin, origin)

