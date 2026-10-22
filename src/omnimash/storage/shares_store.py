"""Share record store for managing active and revoked shares aligned with tottenjordan/adk_pipe."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass
class ShareRecord:
    token: str
    url: str
    scope: str = "video"
    title: str = "Shared OmniMash Video"
    aspect_ratio: str = "16:9"
    session_id: str = "default_session"
    project_id: str = "prj_default"
    owner_user: str = "usr_studio"
    gcs_prefix: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    revoked_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SharesStore:
    """In-memory and storage-backed registry of shares for listing and revocation."""

    def __init__(self) -> None:
        self._records: dict[str, ShareRecord] = {}

    def put(self, record: ShareRecord) -> ShareRecord:
        self._records[record.token] = record
        return record

    def get(self, token: str) -> ShareRecord | None:
        return self._records.get(token)

    def is_revoked(self, token: str) -> bool:
        rec = self._records.get(token)
        return bool(rec and rec.revoked_at is not None)

    def revoke(self, token: str) -> ShareRecord | None:
        rec = self._records.get(token)
        if rec is None:
            # Record revocation even if created in another instance
            rec = ShareRecord(
                token=token,
                url=f"/s/{token}",
                revoked_at=datetime.now(UTC).isoformat(),
            )
            self._records[token] = rec
            return rec
        rec.revoked_at = datetime.now(UTC).isoformat()
        return rec

    def list_for(
        self,
        session_id: str | None = None,
        owner_user: str | None = None,
        include_revoked: bool = False,
    ) -> list[dict[str, Any]]:
        results: list[ShareRecord] = []
        for rec in self._records.values():
            if not include_revoked and rec.revoked_at is not None:
                continue
            if session_id and rec.session_id and rec.session_id != session_id:
                continue
            if owner_user and rec.owner_user and rec.owner_user != owner_user:
                continue
            results.append(rec)
        results.sort(key=lambda r: r.created_at, reverse=True)
        return [r.to_dict() for r in results]


_GLOBAL_SHARES_STORE = SharesStore()


def get_shares_store() -> SharesStore:
    return _GLOBAL_SHARES_STORE
