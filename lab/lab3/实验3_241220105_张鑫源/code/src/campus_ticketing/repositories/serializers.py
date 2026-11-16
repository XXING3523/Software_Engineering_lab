"""领域对象与 SQLite 字段之间的转换。"""

from __future__ import annotations

import json
from datetime import datetime
from decimal import Decimal
from typing import Any

from campus_ticketing.domain.entities import Snapshot


def dt_to_text(value: datetime | None) -> str | None:
    """将时间转换为 SQLite 文本。"""

    return value.isoformat(sep=" ") if value else None


def text_to_dt(value: str | None) -> datetime | None:
    """从 SQLite 文本恢复时间。"""

    return datetime.fromisoformat(value) if value else None


def snapshot_to_text(snapshot: Snapshot) -> str:
    """序列化快照。"""

    return json.dumps(snapshot.as_dict(), ensure_ascii=False, sort_keys=True)


def snapshot_from_text(value: str) -> Snapshot:
    """反序列化快照。"""

    payload: dict[str, Any] = json.loads(value)
    return Snapshot(
        title=str(payload["title"]),
        name=str(payload["name"]),
        price=Decimal(str(payload.get("price", "0"))),
        metadata=dict(payload.get("metadata", {})),
    )


def roles_to_text(roles: set[str]) -> str:
    """序列化角色集合。"""

    return json.dumps(sorted(roles), ensure_ascii=False)


def roles_from_text(value: str) -> set[str]:
    """反序列化角色集合。"""

    return set(json.loads(value))
